"""aidc — AI Dev Company Phase 1 orchestrator CLI.

The manager plans tasks on a board; developer and QA agents claim, execute and report.
Agents may be Codex CLI processes (`dispatch --runner codex`) or any officially
supported agent session driving this CLI by hand (`claim` / `complete` / `fail`).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from . import policy, sandbox
from .board import Board, BoardError

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROMPTS_DIR = os.path.join(PROJECT_ROOT, "agents")


def runs_root():
    return os.environ.get("AIDC_RUNS_ROOT", os.path.join(PROJECT_ROOT, "runs"))


def worktrees_root():
    return os.environ.get("AIDC_WORKTREES_ROOT", os.path.join(PROJECT_ROOT, ".aidc-worktrees"))


def repo_root():
    if os.environ.get("AIDC_REPO_ROOT"):
        return os.environ["AIDC_REPO_ROOT"]
    out = subprocess.run(["git", "-C", PROJECT_ROOT, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def board_for(run_id):
    return Board(policy.ensure_inside(os.path.join(runs_root(), run_id), runs_root()))


def emit(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def tool_version(argv):
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


# -- commands ---------------------------------------------------------------

def forced_login_method():
    """Read only the `forced_login_method` line of Codex's config (never auth files)."""
    path = os.path.join(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")), "config.toml")
    try:
        with open(path) as fh:
            for line in fh:
                if line.split("=")[0].strip() == "forced_login_method":
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


def cmd_preflight(args):
    codex = shutil.which(args.codex_bin) or args.codex_bin
    info = {
        "node": tool_version(["node", "--version"]),
        "python": sys.version.split()[0],
        "git": tool_version(["git", "--version"]),
        "codex": tool_version([codex, "--version"]),
        "codex_auth_mode": policy.codex_auth_mode(codex),
        "codex_multi_agent": None,
        "codex_forced_login_method": forced_login_method(),
        "os_sandbox_available": sandbox.available(),
        "claude_code": tool_version(["claude", "--version"]),
        "api_key_env_present": {k: k in os.environ for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")},
    }
    try:
        feats = subprocess.run([codex, "features", "list"], capture_output=True, text=True, timeout=30).stdout
        info["codex_multi_agent"] = {
            line.split()[0]: " ".join(line.split()[1:]) for line in feats.splitlines()
            if line.split() and line.split()[0] in ("multi_agent", "multi_agent_v2")
        }
    except (OSError, subprocess.TimeoutExpired):
        pass
    emit(info)


def cmd_init(args):
    board = Board.create(runs_root(), args.goal, run_id=args.run_id)
    emit({"run_id": board.state()["run_id"], "run_dir": board.run_dir})


def cmd_plan(args):
    board = board_for(args.run)
    with open(args.file) as fh:
        plan = json.load(fh)
    if plan.get("notes"):
        board.log("manager.plan_notes", notes=plan["notes"])
    for t in plan["tasks"]:
        board.add_task(t["id"], t["title"], t["role"], t["spec"], depends_on=t.get("depends_on", ()),
                       timeout_s=t.get("timeout_s", 1800), max_attempts=t.get("max_attempts", 2),
                       branch=t.get("branch"))
    emit({"planned": [t["id"] for t in plan["tasks"]]})


def cmd_ready(args):
    emit([{"id": t["id"], "role": t["role"], "title": t["title"]} for t in board_for(args.run).ready_tasks(args.role)])


def cmd_claim(args):
    board = board_for(args.run)
    role = board.state()["tasks"].get(args.task, {}).get("role")
    if role == "developer":
        # Hand-driven agents (e.g. chat-session subagents) are not OS-sandboxed by aidc.
        # Write tasks require an explicit acknowledgement, which is recorded in the run log.
        if not args.unsandboxed_ack:
            raise policy.PolicyError("manual claims of developer tasks are not OS-sandboxed; use "
                                     "`aidc dispatch` (Codex sandbox) or pass --unsandboxed-ack")
        board.log("policy.unsandboxed_claim", task=args.task, agent=args.agent)
    emit(board.claim(args.task, args.agent))


def cmd_complete(args):
    with open(args.report_file) as fh:
        report = fh.read()
    emit(board_for(args.run).complete(args.task, args.agent, args.result, args.summary, report))


def cmd_fail(args):
    emit(board_for(args.run).fail(args.task, args.agent, args.error, retryable=not args.no_retry))


def cmd_cancel(args):
    board_for(args.run).cancel(args.task, args.reason)
    emit({"cancelled": args.task})


def cmd_halt(args):
    board_for(args.run).halt(args.reason)
    emit({"halted": args.reason})


def cmd_resume(args):
    board_for(args.run).resume(args.note)
    emit({"resumed": True})


def cmd_recover(args):
    emit({"recovered": board_for(args.run).recover()})


def cmd_note(args):
    board_for(args.run).log(args.kind, actor=args.actor, message=args.message)
    emit({"logged": args.kind})


def cmd_worktree(args):
    board = board_for(args.run)
    path, branch = policy.create_worktree(repo_root(), worktrees_root(), args.run, args.task, base=args.base)
    board.log("workspace.created", task=args.task, path=os.path.relpath(path, repo_root()), branch=branch, base=args.base)
    emit({"path": path, "branch": branch})


def cmd_status(args):
    state = board_for(args.run).state()
    print(f"run {state['run_id']}: {state['goal']}")
    if state.get("halted"):
        print(f"HALTED: {state['halted']['reason']}")
    for t in state["tasks"].values():
        deps = ",".join(t["depends_on"]) or "-"
        print(f"  {t['id']:<12} {t['role']:<10} {t['status']:<10} result={t['result'] or '-':<5} "
              f"attempts={t['attempts']}/{t['max_attempts']} deps={deps} agent={t['agent'] or '-'}")


def cmd_metrics(args):
    emit(board_for(args.run).metrics())


def snapshot_ignore(root):
    ignore = []
    for path in (runs_root(), worktrees_root(), os.path.join(PROJECT_ROOT, ".tools")):
        rel = os.path.relpath(path, root)
        if not rel.startswith(".."):
            ignore.append(rel)
    return ignore


def cmd_sandbox_exec(args):
    """Run a command in the OS sandbox (used for verification and by hand-driven agents)."""
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    hide = [repo_root()] if not args.no_hide_repo else []
    code, out, timed_out = sandbox.run(cmd, args.workdir, args.timeout, writable=args.writable,
                                       readable=args.readable, hide=hide, network=args.network)
    sys.stdout.write(out)
    if timed_out:
        print(f"aidc: sandbox timed out after {args.timeout}s", file=sys.stderr)
    return code


def cmd_review(args):
    """Manager acceptance gate: objective checks, re-run tests in the OS sandbox, record the decision."""
    board = board_for(args.run)
    state = board.state()
    dev = state["tasks"].get(args.task)
    if not dev or dev["role"] != "developer":
        raise BoardError(f"{args.task} is not a developer task")
    qa = [t for t in state["tasks"].values() if args.task in t["depends_on"] and t["role"] == "qa"]
    checks = {
        "developer_done_pass": dev["status"] == "done" and dev["result"] == "pass",
        "independent_qa_exists": bool(qa),
        "qa_done_pass": bool(qa) and all(t["status"] == "done" and t["result"] == "pass" for t in qa),
        "qa_agent_differs": bool(qa) and all(t["agent"] != dev["agent"] for t in qa),
        "branch_recorded": bool(dev["branch"]),
    }
    test = {"exit_code": None}
    if checks["branch_recorded"]:
        root = repo_root()
        path, branch = policy.create_worktree(root, worktrees_root(), args.run,
                                              f"{args.task}-review-{int(time.time() * 1000)}", base=dev["branch"])
        board.log("workspace.created", task=args.task, path=os.path.relpath(path, root), branch=branch, base=dev["branch"])
        code, out, timed_out = sandbox.run(["sh", "-c", args.test_cmd], os.path.join(path, args.test_dir),
                                           args.timeout, hide=[root])
        evidence = os.path.join(board.run_dir, "evidence")
        os.makedirs(evidence, exist_ok=True)
        with open(os.path.join(evidence, f"manager-review-{args.task}.txt"), "w") as fh:
            fh.write(f"$ {args.test_cmd}   (cwd={args.test_dir}, OS sandbox, no network)\n{out}\nexit={code} timed_out={timed_out}\n")
        test = {"exit_code": code, "timed_out": timed_out, "evidence": f"evidence/manager-review-{args.task}.txt"}
        checks["manager_tests_pass"] = code == 0 and not timed_out
    accepted = all(checks.values()) and "manager_tests_pass" in checks
    board.log("manager.accepted" if accepted else "manager.rejected", task=args.task, checks=checks, test=test)
    emit({"task": args.task, "accepted": accepted, "checks": checks, "test": test})
    return 0 if accepted else 1


def cmd_dispatch(args):
    """Run every ready task through Codex until the board is drained, halted or max-tasks hit."""
    from .codex_runner import run_codex

    board = board_for(args.run)
    codex = shutil.which(args.codex_bin) or args.codex_bin
    policy.require_subscription_auth(policy.codex_auth_mode(codex))
    root = repo_root()
    dispatched = 0
    while dispatched < args.max_tasks:
        board.recover()
        if board.state()["halted"]:
            break
        ready = board.ready_tasks()
        if not ready:
            break
        task = ready[0]
        state = board.state()
        base = "HEAD"
        if task["role"] == "qa":
            dev_branches = [state["tasks"][d]["branch"] for d in task["depends_on"] if state["tasks"][d]["branch"]]
            base = dev_branches[0] if dev_branches else "HEAD"
        attempt_id = f"{task['id']}-a{task['attempts'] + 1}"
        path, branch = policy.create_worktree(root, worktrees_root(), args.run, attempt_id, base=base)
        board.log("workspace.created", task=task["id"], path=os.path.relpath(path, root), branch=branch, base=base)
        agent = f"codex-{task['role']}"
        claimed = board.claim(task["id"], agent)
        with open(os.path.join(PROMPTS_DIR, f"{task['role']}.md")) as fh:
            prompt = fh.read().format(task_id=task["id"], title=task["title"], spec=task["spec"],
                                      branch=branch, base=base)
        mode = "read-only" if task["role"] == "qa" else "workspace-write"
        result = run_codex(board, claimed, path, prompt, agent, codex_bin=codex, sandbox=mode,
                           repo_root=root, snapshot_ignore=snapshot_ignore(root))
        if task["role"] == "developer" and result["status"] == "done":
            subprocess.run(["git", "-C", path, "add", "-A"], check=True)
            subprocess.run(["git", "-C", path, "commit", "-q", "-m", f"aidc {args.run}: {task['title']}"], check=False)
            with board._mutate() as st:  # remember the branch for dependants
                st["tasks"][task["id"]]["branch"] = branch
        dispatched += 1
    metrics = board.metrics()
    emit(metrics)
    return 3 if metrics["halted"] else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="aidc", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *arguments, run=True):
        sp = sub.add_parser(name)
        if run:
            sp.add_argument("--run", required=True)
        for a, kw in arguments:
            sp.add_argument(*a, **kw)
        sp.set_defaults(fn=fn)

    add("preflight", cmd_preflight, (("--codex-bin",), {"default": "codex"}), run=False)
    add("init", cmd_init, (("--goal",), {"required": True}), (("--run-id",), {}), run=False)
    add("plan", cmd_plan, (("--file",), {"required": True}))
    add("ready", cmd_ready, (("--role",), {"choices": ["developer", "qa"]}))
    add("claim", cmd_claim, (("--task",), {"required": True}), (("--agent",), {"required": True}),
        (("--unsandboxed-ack",), {"action": "store_true"}))
    add("complete", cmd_complete, (("--task",), {"required": True}), (("--agent",), {"required": True}),
        (("--result",), {"choices": ["pass", "fail"], "required": True}),
        (("--summary",), {"required": True}), (("--report-file",), {"required": True}))
    add("fail", cmd_fail, (("--task",), {"required": True}), (("--agent",), {"required": True}),
        (("--error",), {"required": True}), (("--no-retry",), {"action": "store_true"}))
    add("cancel", cmd_cancel, (("--task",), {"required": True}), (("--reason",), {"required": True}))
    add("halt", cmd_halt, (("--reason",), {"required": True}))
    add("resume", cmd_resume, (("--note",), {"required": True}))
    add("recover", cmd_recover)
    add("note", cmd_note, (("--actor",), {"required": True}), (("--message",), {"required": True}),
        (("--kind",), {"default": "manager.note"}))
    add("worktree", cmd_worktree, (("--task",), {"required": True}), (("--base",), {"default": "HEAD"}))
    add("status", cmd_status)
    add("metrics", cmd_metrics)
    add("dispatch", cmd_dispatch, (("--codex-bin",), {"default": "codex"}),
        (("--max-tasks",), {"type": int, "default": 4}))

    add("review", cmd_review, (("--task",), {"required": True}),
        (("--test-cmd",), {"default": "npm test"}), (("--test-dir",), {"default": "ai-dev-company/demo-app"}),
        (("--timeout",), {"type": int, "default": 600}))
    add("sandbox-exec", cmd_sandbox_exec, (("--workdir",), {"required": True}),
        (("--writable",), {"action": "append", "default": []}), (("--readable",), {"action": "append", "default": []}),
        (("--network",), {"action": "store_true"}), (("--no-hide-repo",), {"action": "store_true"}),
        (("--timeout",), {"type": int, "default": 600}), (("command",), {"nargs": argparse.REMAINDER}), run=False)

    args = p.parse_args(argv)
    try:
        return args.fn(args) or 0
    except (BoardError, policy.PolicyError, sandbox.SandboxUnavailable) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
