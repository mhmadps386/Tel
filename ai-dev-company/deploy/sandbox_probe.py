"""Report what OS sandboxing the host kernel allows (no secrets, read-only checks)."""
import ctypes
import os
import platform
import subprocess


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
