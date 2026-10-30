"""Run one board task with the official Codex CLI (`codex exec`).

Safety properties:
  * every command the model runs goes through Codex's own OS sandbox
    (bubblewrap/seccomp on Linux): workspace-write inside an isolated git worktree
    for developers, read-only for QA, network off;
  * approvals are never auto-granted: `approval_policy="never"` in exec mode means a
    command needing escalation is refused, not approved;
  * `forced_login_method="chatgpt"` makes Codex itself refuse API-key auth, and
    API-key env vars are stripped, so nothing can silently bill an API account;
  * a hard wall-clock timeout kills the whole process group; the agent also dies
    if the orchestrator dies (PDEATHSIG), and stops within POLL_S of a cancel/halt;
  * the manager's checkout is snapshotted before and after; any change outside
    the worktree halts the run as an isolation violation;
  * a usage-limit message halts the run instead of retrying.
"""

import ctypes
import os
import signal
import subprocess
import time

from . import policy

SCRUBBED_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "AZURE_OPENAI_API_KEY")
POLL_S = float(os.environ.get("AIDC_POLL_S", "1.0"))
PR_SET_PDEATHSIG = 1

FORCED_CONFIG = (
    'approval_policy="never"',
    'forced_login_method="chatgpt"',
    "sandbox_workspace_write.network_access=false",
    # Without these, workspace-write also allows writes to /tmp and $TMPDIR (shared with the host).
    "sandbox_workspace_write.exclude_slash_tmp=true",
    "sandbox_workspace_write.exclude_tmpdir_env_var=true",
)


def build_command(codex_bin, workdir, last_message_out, sandbox, extra_config=()):
    if sandbox not in policy.ALLOWED_SANDBOXES:
        raise policy.PolicyError(f"sandbox {sandbox!r} not allowed")
    cmd = [codex_bin, "exec", "--cd", workdir, "--sandbox", sandbox]
    for item in (*FORCED_CONFIG, *extra_config):
        cmd += ["-c", item]
    cmd += ["--json", "--output-last-message", last_message_out, "-"]  # prompt on stdin
    return cmd


def child_env():
    return {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}


def _preexec():
    os.setsid()
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGKILL)


def _kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def checkout_snapshot(repo_root, ignore=()):
    """Porcelain status of the manager's checkout, excluding orchestrator-owned paths."""
    excludes = [f":(exclude){p}" for p in ignore]
    out = subprocess.run(["git", "-C", repo_root, "status", "--porcelain", "--untracked-files=all", "--", ".", *excludes],
                         capture_output=True, text=True, timeout=60)
    return out.stdout


def run_codex(board, task, workdir, prompt, agent, codex_bin="codex", sandbox="workspace-write",
              repo_root=None, snapshot_ignore=()):
    """Execute a claimed task. Returns the board's final view of the task."""
    out_dir = os.path.join(board.run_dir, "codex", task["id"], f"attempt-{task['attempts']}")
    os.makedirs(out_dir, exist_ok=True)
    last_msg = os.path.join(out_dir, "last-message.md")
    events_log = os.path.join(out_dir, "codex-events.jsonl")
    cmd = build_command(codex_bin, workdir, last_msg, sandbox)
    before = checkout_snapshot(repo_root, snapshot_ignore) if repo_root else None
    board.log("codex.exec", task=task["id"], agent=agent, sandbox=sandbox, workdir=workdir,
              argv=[a for a in cmd if a != "-"], timeout_s=task["timeout_s"])

    start = time.time()
    stop_reason = None
    with open(events_log, "w") as log_fh:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_fh, stderr=subprocess.STDOUT,
                                text=True, env=child_env(), preexec_fn=_preexec)
        proc.stdin.write(prompt)
        proc.stdin.close()
        try:
            while proc.poll() is None:
                if time.time() - start > task["timeout_s"]:
                    stop_reason = "timeout"
                elif (state := board.state())["halted"]:
                    stop_reason = "halted"
                elif state["tasks"][task["id"]]["status"] != "running":
                    stop_reason = "cancelled"
                if stop_reason:
                    _kill(proc)
                    break
                time.sleep(POLL_S)
        except KeyboardInterrupt:
            _kill(proc)
            board.cancel(task["id"], "operator interrupt")
            raise
    seconds = round(time.time() - start, 1)
    board.log("codex.exited", task=task["id"], exit_code=proc.returncode, seconds=seconds, stop_reason=stop_reason)

    if repo_root and checkout_snapshot(repo_root, snapshot_ignore) != before:
        board.halt("isolation_violation", detail=f"task {task['id']}: files changed outside the worktree")
        if board.state()["tasks"][task["id"]]["status"] == "running":
            return board.fail(task["id"], agent, "isolation violation: manager checkout modified", retryable=False)
        return board.state()["tasks"][task["id"]]
    if stop_reason == "timeout":
        return board.fail(task["id"], agent, f"timed out after {task['timeout_s']}s")
    if stop_reason == "halted":
        return board.release(task["id"], agent, "run halted")
    if stop_reason == "cancelled":
        return board.state()["tasks"][task["id"]]

    with open(events_log) as fh:
        output = fh.read()
    final = ""
    if os.path.exists(last_msg):
        with open(last_msg) as fh:
            final = fh.read()

    if policy.hits_usage_limit(output) and proc.returncode != 0:
        board.halt("subscription_usage_limit", detail=f"task {task['id']}: Codex reported a usage limit")
        return board.fail(task["id"], agent, "subscription usage limit reached", retryable=False)
    if proc.returncode != 0:
        return board.fail(task["id"], agent, f"codex exited with {proc.returncode}")

    verdict = "fail" if "RESULT: FAIL" in final.upper() else "pass"
    summary = next((l.strip() for l in final.splitlines() if l.strip()), "(no summary)")[:300]
    return board.complete(task["id"], agent, verdict, summary, final or "(empty report)")
