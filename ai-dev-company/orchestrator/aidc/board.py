"""File-backed task board: the manager's single source of truth for a run.

Each run lives in runs/<run_id>/:
  board.json    current state of every task (rewritten atomically under a lock)
  events.jsonl  append-only run log; every state change is one line
  reports/      one markdown report per finished task

Nothing here stores credentials. Agent identities are free-text labels.
"""

import contextlib
import fcntl
import json
import os
import time
import uuid
from datetime import datetime, timezone

ROLES = ("developer", "qa")
TERMINAL = ("done", "failed", "cancelled")
DEFAULT_TIMEOUT_S = 1800
DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_LEASE_S = 2400


class BoardError(Exception):
    pass


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Board:
    def __init__(self, run_dir):
        self.run_dir = os.path.abspath(run_dir)
        self.board_path = os.path.join(self.run_dir, "board.json")
        self.events_path = os.path.join(self.run_dir, "events.jsonl")
        self.lock_path = os.path.join(self.run_dir, ".lock")
        self.reports_dir = os.path.join(self.run_dir, "reports")

    # -- persistence -------------------------------------------------------

    @classmethod
    def create(cls, runs_root, goal, run_id=None):
        run_id = run_id or datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        board = cls(os.path.join(runs_root, run_id))
        if os.path.exists(board.board_path):
            raise BoardError(f"run {run_id} already exists")
        os.makedirs(board.reports_dir, exist_ok=True)
        state = {
            "run_id": run_id,
            "goal": goal,
            "created_at": now_iso(),
            "halted": None,
            "tasks": {},
        }
        with board._locked():
            board._write(state)
            board._event(state, "run.created", goal=goal)
        return board

    @contextlib.contextmanager
    def _locked(self):
        os.makedirs(self.run_dir, exist_ok=True)
        with open(self.lock_path, "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _read(self):
        if not os.path.exists(self.board_path):
            raise BoardError(f"no board at {self.board_path}")
        with open(self.board_path) as fh:
            return json.load(fh)

    def _write(self, state):
        tmp = self.board_path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, self.board_path)

    def _event(self, state, kind, **fields):
        record = {"ts": now_iso(), "run_id": state["run_id"], "event": kind, **fields}
        with open(self.events_path, "a") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    @contextlib.contextmanager
    def _mutate(self):
        with self._locked():
            state = self._read()
            yield state
            self._write(state)

    def state(self):
        with self._locked():
            return self._read()

    def events(self):
        if not os.path.exists(self.events_path):
            return []
        with open(self.events_path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def log(self, kind, **fields):
        """Record a free-form event (e.g. manager notes) in the run log."""
        with self._locked():
            self._event(self._read(), kind, **fields)

    # -- planning ----------------------------------------------------------

    def add_task(self, task_id, title, role, spec, depends_on=(), timeout_s=DEFAULT_TIMEOUT_S,
                 max_attempts=DEFAULT_MAX_ATTEMPTS, branch=None):
        if role not in ROLES:
            raise BoardError(f"unknown role {role!r}; expected one of {ROLES}")
        if not 0 < timeout_s <= 4 * 3600:
            raise BoardError("timeout_s must be between 1s and 4h")
        if not 1 <= max_attempts <= 5:
            raise BoardError("max_attempts must be between 1 and 5")
        with self._mutate() as state:
            if task_id in state["tasks"]:
                raise BoardError(f"task {task_id} already exists")
            for dep in depends_on:
                if dep not in state["tasks"]:
                    raise BoardError(f"task {task_id} depends on unknown task {dep}")
            state["tasks"][task_id] = {
                "id": task_id,
                "title": title,
                "role": role,
                "spec": spec,
                "depends_on": list(depends_on),
                "branch": branch,
                "status": "pending",
                "attempts": 0,
                "max_attempts": max_attempts,
                "timeout_s": timeout_s,
                "agent": None,
                "lease_expires": None,
                "started_at": None,
                "finished_at": None,
                "duration_s": None,
                "durations_s": [],
                "result": None,
                "summary": None,
                "report": None,
                "errors": [],
            }
            self._event(state, "task.planned", task=task_id, role=role, depends_on=list(depends_on),
                        title=title, timeout_s=timeout_s, max_attempts=max_attempts)

    def ready_tasks(self, role=None):
        state = self.state()
        return [t for t in self._ready(state) if role is None or t["role"] == role]

    @staticmethod
    def _ready(state):
        tasks = state["tasks"]
        if state.get("halted"):
            return []
        return [
            t for t in tasks.values()
            if t["status"] == "pending" and all(tasks[d]["status"] == "done" for d in t["depends_on"])
        ]

    # -- execution lifecycle -----------------------------------------------

    def claim(self, task_id, agent, lease_s=None):
        with self._mutate() as state:
            if state.get("halted"):
                raise BoardError(f"run is halted: {state['halted']['reason']}")
            task = self._task(state, task_id)
            if task not in self._ready(state):
                raise BoardError(f"task {task_id} is not ready (status={task['status']})")
            task["status"] = "running"
            task["agent"] = agent
            task["attempts"] += 1
            task["started_at"] = now_iso()
            task["_started_monotonic"] = time.time()
            task["lease_expires"] = time.time() + (lease_s or task["timeout_s"] + 600)
            self._event(state, "task.claimed", task=task_id, agent=agent, attempt=task["attempts"])
            return dict(task)

    def complete(self, task_id, agent, result, summary, report_md):
        if result not in ("pass", "fail"):
            raise BoardError("result must be 'pass' or 'fail'")
        with self._mutate() as state:
            task = self._task(state, task_id)
            self._check_owner(task, agent)
            report_path = os.path.join(self.reports_dir, f"{task_id}.md")
            with open(report_path, "w") as fh:
                fh.write(report_md.rstrip() + "\n")
            self._finish(task, "done")
            task["result"] = result
            task["summary"] = summary
            task["report"] = os.path.relpath(report_path, self.run_dir)
            self._event(state, "task.completed", task=task_id, agent=agent, result=result,
                        summary=summary, duration_s=task["duration_s"], report=task["report"])
            return dict(task)

    def fail(self, task_id, agent, error, retryable=True):
        """Record a failed attempt. Retries are bounded by max_attempts."""
        with self._mutate() as state:
            task = self._task(state, task_id)
            self._check_owner(task, agent)
            self._finish(task, None)
            task["errors"].append({"attempt": task["attempts"], "error": error, "at": now_iso()})
            if retryable and task["attempts"] < task["max_attempts"] and not state.get("halted"):
                task["status"] = "pending"
                task["agent"] = None
                self._event(state, "task.retry_scheduled", task=task_id, agent=agent, error=error,
                            attempt=task["attempts"], max_attempts=task["max_attempts"])
            else:
                task["status"] = "failed"
                self._event(state, "task.failed", task=task_id, agent=agent, error=error,
                            attempt=task["attempts"])
                self._block_dependents(state, task_id)
            return dict(task)

    def cancel(self, task_id, reason):
        with self._mutate() as state:
            task = self._task(state, task_id)
            if task["status"] in TERMINAL:
                raise BoardError(f"task {task_id} already {task['status']}")
            if task["status"] == "running":
                self._finish(task, None)
            task["status"] = "cancelled"
            self._event(state, "task.cancelled", task=task_id, reason=reason)
            self._block_dependents(state, task_id)

    def halt(self, reason, detail=None):
        """Stop dispatching any new work (e.g. subscription usage limit reached)."""
        with self._mutate() as state:
            state["halted"] = {"reason": reason, "detail": detail, "at": now_iso()}
            self._event(state, "run.halted", reason=reason, detail=detail)

    def resume(self, note):
        with self._mutate() as state:
            state["halted"] = None
            self._event(state, "run.resumed", note=note)

    def recover(self, now=None):
        """Return expired-lease tasks to the queue (crash/timeout recovery)."""
        now = now or time.time()
        recovered = []
        with self._mutate() as state:
            for task in state["tasks"].values():
                if task["status"] == "running" and task["lease_expires"] and task["lease_expires"] < now:
                    agent = task["agent"]
                    self._finish(task, None)
                    task["errors"].append({"attempt": task["attempts"], "error": "lease expired", "at": now_iso()})
                    if task["attempts"] < task["max_attempts"]:
                        task["status"] = "pending"
                        task["agent"] = None
                    else:
                        task["status"] = "failed"
                        self._block_dependents(state, task["id"])
                    recovered.append(task["id"])
                    self._event(state, "task.recovered", task=task["id"], agent=agent, new_status=task["status"])
        return recovered

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _task(state, task_id):
        try:
            return state["tasks"][task_id]
        except KeyError:
            raise BoardError(f"unknown task {task_id}") from None

    @staticmethod
    def _check_owner(task, agent):
        if task["status"] != "running":
            raise BoardError(f"task {task['id']} is not running (status={task['status']})")
        if task["agent"] != agent:
            raise BoardError(f"task {task['id']} is claimed by {task['agent']!r}, not {agent!r}")

    @staticmethod
    def _finish(task, status):
        started = task.pop("_started_monotonic", None)
        task["finished_at"] = now_iso()
        task["lease_expires"] = None
        if started is not None:
            elapsed = round(time.time() - started, 1)
            task["durations_s"].append(elapsed)
            task["duration_s"] = round(sum(task["durations_s"]), 1)
        if status:
            task["status"] = status

    def _block_dependents(self, state, task_id):
        for other in state["tasks"].values():
            if task_id in other["depends_on"] and other["status"] == "pending":
                other["status"] = "cancelled"
                self._event(state, "task.cancelled", task=other["id"], reason=f"dependency {task_id} did not succeed")
                self._block_dependents(state, other["id"])

    # -- reporting ---------------------------------------------------------

    def metrics(self):
        state = self.state()
        tasks = list(state["tasks"].values())
        by_status = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        return {
            "run_id": state["run_id"],
            "tasks_total": len(tasks),
            "by_status": by_status,
            "attempts_total": sum(t["attempts"] for t in tasks),
            "failed_attempts": sum(len(t["errors"]) for t in tasks),
            "agent_seconds": round(sum(t["duration_s"] or 0 for t in tasks), 1),
            "halted": state.get("halted"),
            # The orchestrator itself never calls a model API; agents run on subscription tools.
            "orchestrator_api_calls": 0,
        }
