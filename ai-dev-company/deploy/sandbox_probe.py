"""Report what OS sandboxing the host kernel allows (no secrets, read-only checks)."""
import ctypes
import os
import platform
import subprocess
import sys


def out(*a):
    print("PROBE", *a, flush=True)


out("kernel", platform.release())
with open("/proc/self/status") as fh:
    for line in fh:
        if line.split(":")[0] in ("Seccomp", "CapEff", "NoNewPrivs"):
            out(line.strip())
for path in ("/proc/sys/user/max_user_namespaces", "/proc/sys/kernel/unprivileged_userns_clone"):
    try:
        out(path, open(path).read().strip())
    except OSError as e:
        out(path, "n/a", e)
libc = ctypes.CDLL(None, use_errno=True)
abi = libc.syscall(444, None, 0, 1)  # landlock_create_ruleset(NULL, 0, VERSION)
out("landlock_abi", abi, "errno", ctypes.get_errno())
pid = os.fork()
if pid == 0:
    try:
        os.unshare(os.CLONE_NEWUSER)
        out("unshare_user", "ok")
    except OSError as e:
        out("unshare_user", "fail", e)
    os._exit(0)
os.waitpid(pid, 0)
for name, cmd in (
    ("bwrap_full", ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--unshare-all",
                    "--die-with-parent", "--", "sh", "-c", "touch /etc/x 2>/dev/null && echo WRITE-ALLOWED || echo write-blocked"]),
    ("bwrap_noproc", ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--unshare-user", "--unshare-net", "--", "true"]),
    ("aidc_sandbox", ["python3", "-c", "import sys; sys.path.insert(0, '/app/orchestrator'); from aidc import sandbox; print(sandbox.available())"]),
):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out(name, "rc", p.returncode, (p.stdout + p.stderr).strip()[:300])
    except Exception as e:
        out(name, "error", e)

# Codex's own sandbox, with the runner's hardened config, run from a scratch workspace.
codex = "/app/.tools/node_modules/.bin/codex"
work = "/srv/probe-work"
os.makedirs(work, exist_ok=True)
try:
    p = subprocess.run([codex, "sandbox", "-c", 'sandbox_mode="workspace-write"',
                        "-c", "sandbox_workspace_write.exclude_slash_tmp=true",
                        "-c", "sandbox_workspace_write.exclude_tmpdir_env_var=true",
                        "-c", "sandbox_workspace_write.network_access=false", "--",
                        "sh", "-c", "echo in > inside.txt; echo out > /srv/outside.txt; echo t > /tmp/codex-probe"],
                       cwd=work, capture_output=True, text=True, timeout=60)
    out("codex_sandbox", "rc", p.returncode, (p.stdout + p.stderr).strip()[:400].replace("\n", " | "))
    out("codex_sandbox_result", "inside_written", os.path.exists(f"{work}/inside.txt"),
        "outside_written", os.path.exists("/srv/outside.txt"), "tmp_written", os.path.exists("/tmp/codex-probe"))
except Exception as e:
    out("codex_sandbox", "error", e)

# Full negative test suite (real bubblewrap + real Codex sandbox).
env = dict(os.environ, AIDC_CODEX_BIN=codex, PYTHONPATH="/app/orchestrator")
p = subprocess.run([sys.executable, "-m", "unittest", "tests.test_sandbox", "-v"], cwd="/app/orchestrator",
                   capture_output=True, text=True, timeout=300, env=env)
for line in (p.stdout + p.stderr).splitlines():
    if " ... " in line or line.startswith(("Ran ", "OK", "FAILED")) or "Error" in line:
        out("unittest", line[:300])
out("DONE")
