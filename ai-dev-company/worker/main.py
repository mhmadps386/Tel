"""AI Dev Company execution worker.

Runs on a host that supports OS sandboxing (Linux with unprivileged user namespaces).
It connects OUT to the control panel over HTTPS with a revocable worker token, so the
host needs no inbound ports. It never stores the panel's database credentials.

Safety gates (checked continuously, reported in every heartbeat):
  * sandbox self-test: aidc bubblewrap sandbox + Codex's own sandbox must block an
    outside write; otherwise the worker refuses every agent job (fails closed);
  * Codex auth must be "ChatGPT" (forced_login_method="chatgpt" is written to its
    CODEX_HOME); API-key variables are stripped from agent environments;
  * agents only touch a disposable git repository under the worker data dir;
  * every job has a wall-clock timeout; cancel / emergency stop from the panel kills
    the agent's whole process group within one heartbeat (default 3 s);
  * a git-status canary on the disposable repo's main checkout reports isolation violations.

Configuration (environment):
  AIDC_SERVER_URL     https://<panel>  (http only allowed for localhost)
  AIDC_WORKER_TOKEN   token created in the panel (shown once)
  AIDC_WORKER_ID      optional name, default hostname
  AIDC_DATA_DIR       default ~/.aidc-worker   (repo/, worktrees/, codex/)
  AIDC_CODEX_BIN      default: codex on PATH, else ../.tools/node_modules/.bin/codex
"""

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT, "orchestrator"))

from aidc import codex_runner, policy, sandbox  # noqa: E402

VERSION = "aidc-worker/0.1"
HEARTBEAT_S = float(os.environ.get("AIDC_HEARTBEAT_S", "3"))
IDLE_POLL_S = float(os.environ.get("AIDC_IDLE_POLL_S", "5"))
SELFTEST_EVERY_S = 600
TEXT_LIMIT = 20000
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Stopped(Exception):
    pass


class Worker:
    def __init__(self):
        self.server = os.environ["AIDC_SERVER_URL"].rstrip("/")
        host = re.sub(r"^https?://", "", self.server).split("/")[0].split(":")[0]
        if not self.server.startswith("https://") and host not in ("localhost", "127.0.0.1"):
            raise SystemExit("AIDC_SERVER_URL must use https:// (http is only allowed for localhost)")
        self.token = os.environ["AIDC_WORKER_TOKEN"]
        self.worker_id = re.sub(r"[^A-Za-z0-9._-]", "-", os.environ.get("AIDC_WORKER_ID") or socket.gethostname())[:60]
        self.data = os.path.abspath(os.environ.get("AIDC_DATA_DIR") or os.path.expanduser("~/.aidc-worker"))
        self.repo = os.path.join(self.data, "repo")
        self.worktrees = os.path.join(self.data, "worktrees")
        self.codex_home = os.path.join(self.data, "codex")
        self.codex = os.environ.get("AIDC_CODEX_BIN") or shutil.which("codex") or os.path.join(
            PROJECT, ".tools", "node_modules", ".bin", "codex")
        self.current = None          # job id being executed
        self.stop_reason = None      # set by heartbeat thread to stop the current job
        self.sandbox_ok, self.sandbox_detail, self.selftest_at = False, "not tested", 0
        self.lock = threading.Lock()

    # -- setup -------------------------------------------------------------------

    def setup(self):
        for d in (self.data, self.worktrees, self.codex_home):
            os.makedirs(d, exist_ok=True)
        os.chmod(self.data, 0o700)
        os.chmod(self.codex_home, 0o700)
        cfg = os.path.join(self.codex_home, "config.toml")
        text = open(cfg).read() if os.path.exists(cfg) else ""
        if not re.search(r'(?m)^\s*forced_login_method\s*=\s*"chatgpt"', text):
            if re.search(r"(?m)^\s*forced_login_method\s*=", text):
                raise SystemExit(f"{cfg} sets a different forced_login_method; refusing to run")
            text = 'forced_login_method = "chatgpt"\ncli_auth_credentials_store = "file"\n' + text
            with open(cfg, "w") as fh:
                fh.write(text)
        if not os.path.isdir(os.path.join(self.repo, ".git")):
            self.create_disposable_repo()
        self.selftest()

    def create_disposable_repo(self):
        """Fresh local-only git repo seeded from the demo app. Never has a remote."""
        shutil.copytree(os.path.join(PROJECT, "demo-app"), self.repo,
                        ignore=shutil.ignore_patterns("node_modules"))
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"],
                    ["-c", "user.name=aidc", "-c", "user.email=aidc@localhost", "commit", "-q", "-m",
                     "Disposable demo baseline"]):
            subprocess.run(["git", "-C", self.repo, *cmd], check=True, capture_output=True)
        log("created disposable repo", self.repo)

    def env(self):
        env = codex_runner.child_env()
        env["CODEX_HOME"] = self.codex_home
        return env

    def selftest(self):
        """Prove both sandboxes block an outside write right now; fail closed otherwise."""
        ok, detail = False, ""
        try:
            if not sandbox.available():
                raise RuntimeError("aidc bubblewrap sandbox unavailable (user namespaces blocked?)")
            with tempfile.TemporaryDirectory(dir=self.data, prefix="selftest-") as t:
                work, outside = os.path.join(t, "work"), os.path.join(t, "outside.txt")
                os.makedirs(work)
                cfg = [x for c in codex_runner.FORCED_CONFIG if c.startswith("sandbox_") for x in ("-c", c)]
                p = subprocess.run([self.codex, "sandbox", "-c", 'sandbox_mode="workspace-write"', *cfg, "--",
                                    "sh", "-c", f"echo in > inside.txt; echo out > {outside}"],
                                   cwd=work, capture_output=True, text=True, timeout=60, env=self.env())
                inside = os.path.exists(os.path.join(work, "inside.txt"))
                if not inside:
                    raise RuntimeError("codex sandbox did not run: " + (p.stdout + p.stderr).strip()[:200])
                if os.path.exists(outside):
                    raise RuntimeError("codex sandbox allowed an outside write")
            ok, detail = True, "aidc bwrap + codex sandbox verified"
        except Exception as e:  # noqa: BLE001 - any failure means "not safe"
            detail = str(e)[:300]
        self.sandbox_ok, self.sandbox_detail, self.selftest_at = ok, detail, time.time()
        log("sandbox self-test:", "OK" if ok else "FAILED", detail)

    def auth_mode(self):
        if not os.path.exists(self.codex):
            return "codex_missing"
        old = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = self.codex_home
        try:
            return policy.codex_auth_mode(self.codex)
        finally:
            if old is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old

    def capabilities(self):
        return {"sandbox_ok": self.sandbox_ok, "auth_mode": self.auth_mode(),
                "login_ok": os.path.exists(self.codex), "repo_ok": os.path.isdir(os.path.join(self.repo, ".git"))}

    # -- HTTP --------------------------------------------------------------------

    def post(self, path, body, timeout=30):
        req = urllib.request.Request(self.server + path, data=json.dumps(body).encode(), method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.token}", "X-Worker-Id": self.worker_id})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.status, json.loads(res.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def heartbeat_loop(self):
        while True:
            try:
                status, res = self.post("/worker/heartbeat", {
                    "version": VERSION, "host": socket.gethostname(), "sandbox_ok": self.sandbox_ok,
                    "sandbox_detail": self.sandbox_detail, "auth_mode": self.auth_mode(),
                    "forced_login_method": "chatgpt", "codex_version": self.codex_version(),
                    "current_job": self.current, "repo_ok": os.path.isdir(self.repo)})
                if status == 200 and self.current and (self.current in res.get("stop_jobs", []) or res.get("estop")):
                    self.stop_reason = "emergency stop" if res.get("estop") else "cancelled or released by the manager"
            except Exception as e:  # noqa: BLE001
                log("heartbeat failed:", type(e).__name__)
            time.sleep(HEARTBEAT_S)

    _codex_version = None

    def codex_version(self):
        if self._codex_version is None:
            try:
                self._codex_version = subprocess.run([self.codex, "--version"], capture_output=True, text=True,
                                                     timeout=20).stdout.strip()
            except OSError:
                self._codex_version = "missing"
        return self._codex_version

    # -- main loop ----------------------------------------------------------------

    def run(self):
        self.setup()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        log(f"worker {self.worker_id} connected to {self.server}")
        while True:
            if time.time() - self.selftest_at > SELFTEST_EVERY_S:
                self.selftest()
            try:
                status, res = self.post("/worker/claim", {"capabilities": self.capabilities()})
            except Exception as e:  # noqa: BLE001
                log("claim failed:", type(e).__name__)
                time.sleep(IDLE_POLL_S)
                continue
            job = res.get("job") if status == 200 else None
            if not job:
                time.sleep(IDLE_POLL_S)
                continue
            self.execute(job)

    def execute(self, job):
        self.current, self.stop_reason = job["id"], None
        log(f"job {job['id']} {job['kind']} (mission {job.get('mission_id')}, round {job['round']})")
        start = time.time()
        before = self.canary()
        body = {}
        try:
            result = getattr(self, f"job_{job['kind']}")(job)
            body = {"ok": True, "result": result}
        except Stopped as e:
            body = {"ok": False, "error": f"stopped: {e}", "retryable": True}
        except UsageLimit:
            body = {"ok": False, "usage_limit": True, "error": "subscription usage limit"}
        except Exception as e:  # noqa: BLE001
            body = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}", "retryable": True}
        if self.canary() != before and job["kind"] != "merge":
            body = {"ok": False, "isolation_violation": True, "error": "disposable repo main checkout changed"}
        body["seconds"] = round(time.time() - start, 1)
        status, _ = self.post(f"/worker/jobs/{job['id']}/result", body)
        log(f"job {job['id']} finished ok={body.get('ok')} accepted={status == 200}")
        self.current = None

    def canary(self):
        return subprocess.run(["git", "-C", self.repo, "status", "--porcelain", "--untracked-files=all"],
                              capture_output=True, text=True).stdout

    def note(self, job, message, kind="note"):
        try:
            self.post(f"/worker/jobs/{job['id']}/event", {"kind": kind, "message": message[:2000]})
        except Exception:  # noqa: BLE001
            pass

    # -- process control --------------------------------------------------------

    def run_process(self, cmd, timeout_s, cwd=None, stdin_text=None, on_line=None, env=None):
        """Run with PDEATHSIG + own process group; kill on timeout or stop request. Returns (rc, output)."""
        proc = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, env=env or self.env(), preexec_fn=codex_runner._preexec)
        if stdin_text is not None:
            proc.stdin.write(stdin_text)
        proc.stdin.close()
        lines = []
        reader = threading.Thread(target=lambda: [lines.append(l) or (on_line and on_line(l)) for l in proc.stdout],
                                  daemon=True)
        reader.start()
        start = time.time()
        while proc.poll() is None:
            reason = self.stop_reason or ("timeout" if time.time() - start > timeout_s else None)
            if reason:
                codex_runner._kill(proc)
                reader.join(5)
                if reason == "timeout":
                    raise TimeoutError(f"timed out after {timeout_s}s")
                raise Stopped(reason)
            time.sleep(0.5)
        reader.join(5)
        return proc.returncode, "".join(lines)

    def codex_exec(self, job, workdir, prompt, mode, schema=None):
        """One sandboxed Codex agent turn. Returns the agent's final message."""
        if not self.sandbox_ok:
            raise RuntimeError("sandbox self-test failing; refusing to start an agent")
        if self.auth_mode() != "chatgpt":
            raise RuntimeError("Codex is not signed in with ChatGPT; refusing to start an agent")
        with tempfile.TemporaryDirectory(dir=self.data, prefix="codexio-") as io:
            last = os.path.join(io, "last.md")
            cmd = codex_runner.build_command(self.codex, workdir, last, mode)
            if schema:
                schema_path = os.path.join(io, "schema.json")
                with open(schema_path, "w") as fh:
                    json.dump(schema, fh)
                cmd = cmd[:-1] + ["--output-schema", schema_path, "-"]
            self.note(job, f"codex exec --sandbox {mode} started", "codex_started")
            rc, out = self.run_process(cmd, job["timeout_s"], stdin_text=prompt)
            if rc != 0:
                if policy.hits_usage_limit(out):
                    raise UsageLimit()
                raise RuntimeError(f"codex exited {rc}: {ANSI.sub('', out)[-400:]}")
            with open(last) as fh:
                return fh.read()

    # -- git helpers ------------------------------------------------------------

    def git(self, *args, cwd=None):
        return subprocess.run(["git", "-C", cwd or self.repo, *args], check=True, capture_output=True, text=True,
                              timeout=120).stdout

    def worktree(self, job, ref, branch=None):
        path = os.path.join(self.worktrees, f"job-{job['id']}-a{job['attempts']}")
        if os.path.exists(path):
            self.git("worktree", "remove", "--force", path)
        if branch:
            # A crashed or stopped attempt may still hold this branch in its worktree; drop it first.
            current = None
            for line in self.git("worktree", "list", "--porcelain").splitlines():
                if line.startswith("worktree "):
                    current = line.split(" ", 1)[1]
                elif line == f"branch refs/heads/{branch}" and current != self.repo:
                    self.git("worktree", "remove", "--force", current)
            self.git("worktree", "prune")
            self.git("worktree", "add", "-B", branch, path, ref)
        else:
            self.git("worktree", "add", "--detach", path, ref)
        return path

    def diffstat(self, ref):
        return self.git("diff", "--stat", f"main...{ref}")[-3000:]

    # -- job kinds ----------------------------------------------------------------

    def job_plan(self, job):
        m = job["mission"]
        wt = self.worktree(job, "main")
        text = self.codex_exec(job, wt, PLAN_PROMPT.format(title=m["title"], request=m["request"]), "read-only", PLAN_SCHEMA)
        plan = json.loads(text)
        return {"plan": plan, "summary": plan.get("summary", "")[:300], "verdict": "pass"}

    def job_develop(self, job):
        m, spec = job["mission"], job["spec"]
        base = spec.get("base_branch") or "main"
        branch = f"aidc/m{m['id']}/r{job['round']}"
        wt = self.worktree(job, base, branch)
        prompt = DEV_PROMPT.format(title=m["title"], request=m["request"], instructions=spec.get("instructions", ""),
                                   acceptance="\n".join(f"- {a}" for a in spec.get("acceptance", [])) or "- (see request)",
                                   round=job["round"], correction="yes" if spec.get("correction") else "no")
        report = self.codex_exec(job, wt, prompt, "workspace-write")
        self.git("add", "-A", cwd=wt)
        changed = subprocess.run(["git", "-C", wt, "diff", "--cached", "--quiet"]).returncode != 0
        if changed:
            self.git("-c", "user.name=aidc-developer", "-c", "user.email=aidc@localhost", "commit", "-q", "-m",
                     f"mission {m['id']} round {job['round']}: {m['title'][:60]}", cwd=wt)
        verdict = "fail" if "RESULT: FAIL" in report.upper() or not changed else "pass"
        return {"verdict": verdict, "report": report[-TEXT_LIMIT:], "branch": branch, "changed": changed,
                "commit": self.git("rev-parse", "HEAD", cwd=wt).strip(), "diffstat": self.diffstat(branch),
                "summary": first_line(report)}

    def job_qa(self, job):
        m, spec = job["mission"], job["spec"]
        wt = self.worktree(job, spec["branch"])
        plan = m.get("plan") or {}
        prompt = QA_PROMPT.format(title=m["title"], request=m["request"], focus=plan.get("qa_focus", ""),
                                  acceptance="\n".join(f"- {a}" for a in plan.get("acceptance_criteria", [])) or "- (see request)",
                                  diff=self.git("diff", f"main...{spec['branch']}")[-TEXT_LIMIT:])
        report = self.codex_exec(job, wt, prompt, "read-only")
        return {"verdict": "fail" if "RESULT: FAIL" in report.upper() else "pass", "report": report[-TEXT_LIMIT:],
                "summary": first_line(report)}

    def job_review(self, job):
        m, spec = job["mission"], job["spec"]
        wt = self.worktree(job, spec["branch"])
        # Objective check: the manager re-runs the test suite itself, inside the OS sandbox, no network.
        code, out, timed_out = sandbox.run(["npm", "test"], wt, 600, hide=[self.data])
        counts = dict(re.findall(r"^# (tests|pass|fail) (\d+)", out, re.M))
        tests = {"exit_code": code, "timed_out": timed_out, "summary": f"{counts.get('pass', '?')}/{counts.get('tests', '?')} pass, "
                 f"{counts.get('fail', '?')} fail", "output_tail": out[-3000:]}
        self.note(job, f"manager re-ran npm test in sandbox: {tests['summary']} (exit {code})", "tests")
        prompt = REVIEW_PROMPT.format(title=m["title"], request=m["request"], round=job["round"],
                                      max_rounds=5, dev_report=spec.get("dev_report", "")[:8000],
                                      qa_report=spec.get("qa_report", "")[:8000], tests=out[-4000:],
                                      diff=self.git("diff", f"main...{spec['branch']}")[-12000:])
        decision = json.loads(self.codex_exec(job, wt, prompt, "read-only", REVIEW_SCHEMA))
        return {"tests": tests, "decision": decision, "verdict": decision.get("decision"),
                "diffstat": self.diffstat(spec["branch"]), "summary": decision.get("rationale", "")[:300]}

    def job_merge(self, job):
        branch = job["spec"]["branch"]
        if not re.fullmatch(r"aidc/m\d+/r\d+", branch or ""):
            raise RuntimeError("refusing to merge a non-aidc branch")
        if self.git("remote").strip():
            raise RuntimeError("disposable repo unexpectedly has a remote; refusing")
        self.git("-c", "user.name=aidc-manager", "-c", "user.email=aidc@localhost", "merge", "--no-ff", "-q", "-m",
                 f"Merge {branch} (owner approved)", branch)
        return {"commit": self.git("rev-parse", "HEAD").strip(), "verdict": "pass", "summary": f"merged {branch} locally"}

    def job_login(self, job):
        """Official device-code sign-in. Only the verification URL and one-time code leave this host."""
        if self.auth_mode() == "chatgpt":
            return {"auth_mode": "chatgpt", "summary": "already signed in with ChatGPT", "verdict": "pass"}
        seen = {}

        def on_line(line):
            clean = ANSI.sub("", line).strip()
            url = re.search(r"https://(?:auth\.openai\.com|chatgpt\.com)/[^\s]*", clean)
            code = re.search(r"\b([A-Z0-9]{4,8}-[A-Z0-9]{4,8})\b", clean)
            if url and "url" not in seen:
                seen["url"] = url.group(0)
            if code and "code" not in seen:
                seen["code"] = code.group(1)
            if "url" in seen and "code" in seen and not seen.get("sent"):
                seen["sent"] = True
                self.post("/worker/login", {"verification_url": seen["url"], "user_code": seen["code"],
                                            "status": "waiting for owner", "expires_in_s": 900})
        env = self.env()
        rc, out = self.run_process([self.codex, "login", "--device-auth"], job["timeout_s"], on_line=on_line, env=env)
        mode = self.auth_mode()
        status = "signed in with ChatGPT" if mode == "chatgpt" else f"sign-in failed (exit {rc})"
        self.post("/worker/login", {"status": status})
        if mode != "chatgpt":
            raise RuntimeError(f"{status}: {ANSI.sub('', out)[-300:]}")
        return {"auth_mode": mode, "summary": status, "verdict": "pass"}


class UsageLimit(Exception):
    pass


def first_line(text):
    return next((l.strip() for l in (text or "").splitlines() if l.strip()), "")[:300]


PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["summary", "developer_task", "qa_focus", "acceptance_criteria", "risks"],
    "properties": {
        "summary": {"type": "string"}, "developer_task": {"type": "string"}, "qa_focus": {"type": "string"},
        "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
}
REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["decision", "rationale", "correction"],
    "properties": {
        "decision": {"type": "string", "enum": ["accept", "correct"]},
        "rationale": {"type": "string"}, "correction": {"type": "string"},
    },
}

PLAN_PROMPT = """You are the AI Manager of a small software team (one developer agent, one independent QA agent).
You are read-only. Inspect this repository (a disposable Node web app: src/, public/, test/; tests run with `npm test`).

Owner request
Title: {title}
{request}

Produce a plan: a precise, self-contained task for the developer (files to touch, behaviour, tests to add),
what QA must focus on, objective acceptance criteria that can be verified by tests, and risks.
Keep the scope to what the request asks. Never plan deployments, network access or changes outside this repo."""

DEV_PROMPT = """You are the developer agent. Work only in the current directory (an isolated git worktree of a
disposable Node app). Network is disabled; do not install packages. Do not commit; the worker commits for you.

Mission: {title}
Owner request: {request}
Round: {round} (correction round: {correction})

Task from the manager:
{instructions}

Acceptance criteria:
{acceptance}

Implement the change with focused edits matching the existing style, add node:test coverage for every rule,
and run `npm test` until it passes. Finish with a short report: summary line, files changed, tests run with
exact pass/fail counts, known limitations, and a last line `RESULT: PASS` or `RESULT: FAIL`."""

QA_PROMPT = """You are the independent QA agent. You did not write this change and you must not modify files.
The current directory is a read-only checkout of the developer's branch of a disposable Node app.

Mission: {title}
Owner request: {request}
QA focus from the manager: {focus}
Acceptance criteria:
{acceptance}

Diff under review (main...branch):
{diff}

Run `npm test` and record exact counts, check every acceptance criterion against the code, probe edge cases
by reading code paths, and list bugs with file:line and severity (high/medium/low). End with
`RESULT: PASS` only if every criterion is met and no high/medium bug exists, otherwise `RESULT: FAIL`."""

REVIEW_PROMPT = """You are the AI Manager reviewing round {round} of at most {max_rounds} for mission "{title}".
You are read-only. Decide whether the work is ready for the owner's merge approval.

Owner request: {request}

Developer report:
{dev_report}

Independent QA report:
{qa_report}

Test suite re-run by the manager in an isolated sandbox (tail):
{tests}

Diff (main...branch, truncated):
{diff}

Return "accept" only if the request is fully met, QA found no high/medium issue and the tests pass.
Otherwise return "correct" with a precise, self-contained correction task for the developer that addresses
each QA finding and failing test. `correction` must be empty when accepting."""


def main():
    def _term(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, _term)
    Worker().run()


if __name__ == "__main__":
    main()
