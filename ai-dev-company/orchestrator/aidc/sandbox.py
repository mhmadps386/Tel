"""OS-level sandbox for agent and verification commands (Linux, bubblewrap).

Enforced by the kernel, not by agent instructions:
  * the whole filesystem is mounted read-only; only `workdir` and explicit
    `writable` paths are writable;
  * $HOME and /root are replaced by empty tmpfs mounts (credential stores such as
    ~/.codex, ~/.ssh, ~/.config/gh are invisible); `readable` paths are re-exposed read-only;
  * private /tmp, new user/pid/ipc/uts/net namespaces (no network unless asked);
  * runs as an unprivileged uid inside the namespace (no root capabilities);
  * empty environment except a minimal allow-list;
  * process dies with its parent; wall-clock timeout kills the whole sandbox;
  * rlimits cap file size, open files and core dumps.

If bubblewrap is missing or broken the sandbox fails closed (SandboxUnavailable).
"""

import ctypes
import glob
import os
import resource
import shutil
import signal
import subprocess
import tempfile

SANDBOX_UID = 1000
ENV_ALLOW = ("PATH", "LANG", "LC_ALL", "TERM", "TZ")
PR_SET_PDEATHSIG = 1


class SandboxUnavailable(Exception):
    pass


def find_bwrap():
    candidates = [os.environ.get("AIDC_BWRAP"), shutil.which("bwrap")]
    # The Codex CLI npm package ships a bubblewrap build; reuse it when no system bwrap exists.
    here = os.path.dirname(os.path.abspath(__file__))
    project = os.path.abspath(os.path.join(here, "..", ".."))
    candidates += sorted(glob.glob(os.path.join(project, ".tools", "node_modules", "@openai", "codex-linux-*",
                                                "vendor", "*", "codex-resources", "bwrap")))
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise SandboxUnavailable("bubblewrap not found: install `bwrap` or the pinned Codex CLI in .tools/")


def _preexec(limits):
    def apply():
        os.setsid()
        # Kill the sandbox if the orchestrator dies (no orphaned agents).
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGKILL)
        for res, value in limits.items():
            resource.setrlimit(res, (value, value))
    return apply


DEFAULT_LIMITS = {
    resource.RLIMIT_FSIZE: 512 * 1024 * 1024,
    resource.RLIMIT_NOFILE: 1024,
    resource.RLIMIT_CORE: 0,
}


def build_argv(cmd, workdir, writable=(), readable=(), hide=(), network=False, env=None, bwrap=None):
    bwrap = bwrap or find_bwrap()
    workdir = os.path.realpath(workdir)
    for path in (workdir, *writable):
        if os.path.realpath(path) in ("/", "/home", "/usr", "/etc", "/var", os.path.expanduser("~")):
            raise SandboxUnavailable(f"refusing to make {path} writable")
    argv = [bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp"]
    hidden = sorted({os.path.realpath(p) for p in (os.path.expanduser("~"), "/root", *hide) if p and os.path.isdir(p)})
    for path in hidden:
        argv += ["--tmpfs", path]
    for path in readable:
        argv += ["--ro-bind", os.path.realpath(path), os.path.realpath(path)]
    for path in (workdir, *writable):
        argv += ["--bind", os.path.realpath(path), os.path.realpath(path)]
    # The empty overlays that hide paths are read-only too, so writes there fail loudly
    # instead of landing in a throwaway tmpfs. Nested binds above keep their own mode.
    for path in hidden:
        argv += ["--remount-ro", path]
    argv += ["--dir", "/tmp/home"]
    argv += ["--unshare-all", "--unshare-user", "--uid", str(SANDBOX_UID), "--gid", str(SANDBOX_UID)]
    if network:
        argv.append("--share-net")
    argv += ["--die-with-parent", "--new-session", "--clearenv"]
    base_env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
    base_env.update({"HOME": "/tmp/home", "TMPDIR": "/tmp"})
    base_env.update(env or {})
    for k, v in base_env.items():
        argv += ["--setenv", k, v]
    argv += ["--chdir", workdir, "--", *cmd]
    return argv


def run(cmd, workdir, timeout_s, writable=(), readable=(), hide=(), network=False, env=None, limits=None):
    """Run `cmd` sandboxed. Returns (exit_code, combined_output, timed_out)."""
    argv = build_argv(cmd, workdir, writable, readable, hide, network, env)
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            preexec_fn=_preexec(limits or DEFAULT_LIMITS))
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        return proc.returncode, out, False
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return proc.returncode, out, True


def available():
    try:
        with tempfile.TemporaryDirectory() as work:
            code, _, _ = run(["sh", "-c", "touch probe"], work, timeout_s=20)
            return code == 0 and os.path.exists(os.path.join(work, "probe"))
    except (SandboxUnavailable, OSError):
        return False
