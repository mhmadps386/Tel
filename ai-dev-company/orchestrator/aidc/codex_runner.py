"""Run one board task with the official Codex CLI (`codex exec`).

Safety properties:
  * sandbox is workspace-write (or read-only for QA) inside an isolated git worktree;
    network stays off (Codex default for workspace-write);
  * approvals are never auto-granted: `approval_policy="never"` in exec mode means a
    command needing escalation is refused, not approved;
  * API-key env vars are stripped so Codex cannot silently bill an API account;
  * a hard wall-clock timeout kills the whole process group;
  * a usage-limit message halts the run instead of retrying.
"""

import os
import signal
import subprocess
import time

from . import policy

SCRUBBED_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "AZURE_OPENAI_API_KEY")


def build_command(codex_bin, workdir, prompt_file_out, sandbox, extra_config=()):
    if sandbox not in policy.ALLOWED_SANDBOXES:
        raise policy.PolicyError(f"sandbox {sandbox!r} not allowed")
    cmd = [
        codex_bin, "exec",
        "--cd", workdir,
        "--sandbox", sandbox,
        "-c", 'approval_policy="never"',
        "--json",
        "--output-last-message", prompt_file_out,
    ]
    for item in extra_config:
        cmd += ["-c", item]
    cmd.append("-")  # prompt on stdin
    return cmd


def child_env():
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}
    return env


def run_codex(board, task, workdir, prompt, agent, codex_bin="codex", sandbox="workspace-write"):
    """Execute a claimed task. Returns the board's final view of the task."""
    out_dir = os.path.join(board.run_dir, "codex", task["id"], f"attempt-{task['attempts']}")
    os.makedirs(out_dir, exist_ok=True)
    last_msg = os.path.join(out_dir, "last-message.md")
    events_log = os.path.join(out_dir, "codex-events.jsonl")
    cmd = build_command(codex_bin, workdir, last_msg, sandbox)
    board.log("codex.exec", task=task["id"], agent=agent, sandbox=sandbox, workdir=workdir,
              argv=[a for a in cmd if a != "-"], timeout_s=task["timeout_s"])

    start = time.time()
    with open(events_log, "w") as log_fh:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_fh, stderr=subprocess.STDOUT,
                                text=True, env=child_env(), start_new_session=True)
        try:
            proc.communicate(prompt, timeout=task["timeout_s"])
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            return board.fail(task["id"], agent, f"timed out after {task['timeout_s']}s")
        except KeyboardInterrupt:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait()
            board.cancel(task["id"], "operator interrupt")
            raise

    with open(events_log) as fh:
        output = fh.read()
    final = ""
    if os.path.exists(last_msg):
        with open(last_msg) as fh:
            final = fh.read()
    board.log("codex.exited", task=task["id"], exit_code=proc.returncode, seconds=round(time.time() - start, 1))

    if policy.hits_usage_limit(output) and proc.returncode != 0:
        board.halt("subscription_usage_limit", detail=f"task {task['id']}: Codex reported a usage limit")
        return board.fail(task["id"], agent, "subscription usage limit reached", retryable=False)
    if proc.returncode != 0:
        return board.fail(task["id"], agent, f"codex exited with {proc.returncode}")

    verdict = "fail" if "RESULT: FAIL" in final.upper() else "pass"
    summary = next((l.strip() for l in final.splitlines() if l.strip()), "(no summary)")[:300]
    return board.complete(task["id"], agent, verdict, summary, final or "(empty report)")
