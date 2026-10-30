"""Negative tests: the OS sandbox must block writes outside the workspace, hide
credentials, cut the network and drop privileges, regardless of what the agent
is told. These run real commands under bubblewrap; nothing is mocked.
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlparse

from aidc import sandbox

AVAILABLE = sandbox.available()
CODEX = os.environ.get("AIDC_CODEX_BIN") or shutil.which("codex") or os.path.join(
    os.path.dirname(__file__), "..", "..", ".tools", "node_modules", ".bin", "codex")


@unittest.skipUnless(AVAILABLE, "bubblewrap sandbox unavailable on this host")
class SandboxTest(unittest.TestCase):
    def setUp(self):
        # Fixtures must live outside /tmp: the sandbox gives each run a private /tmp,
        # so a fixture under /tmp would be shadowed rather than protected.
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".aidc-worktrees")
        os.makedirs(root, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root, prefix="sbx-")
        t = self.tmp.name
        self.project = os.path.join(t, "project")          # stands in for the manager's checkout
        self.work = os.path.join(self.project, "worktree")  # the only writable place
        self.secrets = os.path.join(t, "fake-home")
        os.makedirs(self.work)
        os.makedirs(self.secrets)
        with open(os.path.join(self.project, "existing.txt"), "w") as fh:
            fh.write("original\n")
        with open(os.path.join(self.secrets, "auth.json"), "w") as fh:
            fh.write('{"token": "decoy"}\n')

    def tearDown(self):
        self.tmp.cleanup()

    def sh(self, script, **kw):
        code, out, timed_out = sandbox.run(["sh", "-c", script], self.work, kw.pop("timeout_s", 30),
                                           hide=[self.secrets], **kw)
        return code, out, timed_out

    def test_write_inside_workspace_allowed(self):
        code, out, _ = self.sh("echo ok > inside.txt && cat inside.txt")
        self.assertEqual((code, out.strip()), (0, "ok"))
        self.assertTrue(os.path.exists(os.path.join(self.work, "inside.txt")))

    def test_write_to_parent_project_blocked(self):
        target = os.path.join(self.project, "existing.txt")
        code, out, _ = self.sh(f"echo pwned > {target}")
        self.assertNotEqual(code, 0)
        self.assertIn("Read-only file system", out)
        with open(target) as fh:
            self.assertEqual(fh.read(), "original\n")

    def test_new_file_outside_workspace_blocked(self):
        for target in (os.path.join(self.project, "new.txt"), os.path.join(self.tmp.name, "new.txt"),
                       "/home/user/aidc-escape-test.txt", "/etc/aidc-escape-test"):
            code, _, _ = self.sh(f"echo x > {target}")
            self.assertNotEqual(code, 0, target)
            self.assertFalse(os.path.exists(target), f"escaped write landed at {target}")

    def test_hidden_paths_are_read_only(self):
        # Writes next to the workspace inside a hidden tree must fail, not vanish into a tmpfs.
        code, out, _ = sandbox.run(["sh", "-c", "echo x > ../sibling.txt"], self.work, 30, hide=[self.project])
        self.assertNotEqual(code, 0)
        self.assertIn("Read-only file system", out)
        self.assertFalse(os.path.exists(os.path.join(self.project, "sibling.txt")))

    def test_refuses_broad_writable_roots(self):
        for root in ("/", os.path.expanduser("~")):
            with self.assertRaises(sandbox.SandboxUnavailable):
                sandbox.run(["true"], root, 10)

    def test_symlink_escape_blocked(self):
        target = os.path.join(self.project, "via-symlink.txt")
        code, _, _ = self.sh(f"ln -s {self.project} link && echo x > link/via-symlink.txt")
        self.assertNotEqual(code, 0)
        self.assertFalse(os.path.exists(target))

    def test_delete_outside_workspace_blocked(self):
        code, _, _ = self.sh(f"rm -f {self.project}/existing.txt")
        self.assertNotEqual(code, 0)
        self.assertTrue(os.path.exists(os.path.join(self.project, "existing.txt")))

    def test_credentials_hidden(self):
        code, out, _ = self.sh(f"cat {self.secrets}/auth.json; ls -A {os.path.expanduser('~')}")
        self.assertNotIn("decoy", out)
        self.assertNotIn(".codex", out)

    def test_network_blocked(self):
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        host, port = ("1.1.1.1", 443)
        if proxy:
            u = urlparse(proxy)
            host, port = u.hostname, u.port or 80
        # Sanity: the target is reachable from outside the sandbox.
        try:
            socket.create_connection((host, port), timeout=5).close()
        except OSError:
            self.skipTest(f"{host}:{port} unreachable even outside the sandbox")
        probe = f"import socket; socket.create_connection(('{host}', {port}), timeout=5); print('CONNECTED')"
        code, out, _ = sandbox.run([sys.executable, "-c", probe], self.work, 30)
        self.assertNotEqual(code, 0)
        self.assertNotIn("CONNECTED", out.splitlines())

    def test_runs_unprivileged_with_private_pids(self):
        code, out, _ = self.sh(f"id -u; test -e /proc/{os.getpid()} && echo HOST_PID_VISIBLE || echo pid-hidden")
        self.assertEqual(code, 0)
        uid, pidline = out.split()
        self.assertEqual(int(uid), sandbox.SANDBOX_UID)
        self.assertEqual(pidline, "pid-hidden")

    def test_environment_scrubbed(self):
        os.environ["AIDC_TEST_SECRET"] = "should-not-leak"
        try:
            _, out, _ = self.sh("env")
        finally:
            del os.environ["AIDC_TEST_SECRET"]
        self.assertNotIn("should-not-leak", out)
        self.assertNotIn("OPENAI_API_KEY", out)

    def test_timeout_kills_sandbox(self):
        start = time.time()
        _, _, timed_out = self.sh("sleep 60", timeout_s=2)
        self.assertTrue(timed_out)
        self.assertLess(time.time() - start, 15)

    def test_file_size_limit(self):
        limits = dict(sandbox.DEFAULT_LIMITS)
        limits[sandbox.resource.RLIMIT_FSIZE] = 1024 * 1024
        code, _, _ = sandbox.run(["sh", "-c", "head -c 5000000 /dev/zero > big"], self.work, 30, limits=limits)
        self.assertNotEqual(code, 0)
        self.assertLessEqual(os.path.getsize(os.path.join(self.work, "big")), 1024 * 1024)


@unittest.skipUnless(os.path.exists(CODEX), "Codex CLI not installed")
class CodexSandboxTest(unittest.TestCase):
    """The sandbox Codex applies to every model-issued command (official Codex feature),
    with the same config the runner forces."""

    def setUp(self):
        # Codex's default workspace-write also allows /tmp, so test outside /tmp.
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".aidc-worktrees")
        os.makedirs(root, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root, prefix="codex-sbx-")
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(self.work)

    def tearDown(self):
        self.tmp.cleanup()

    def codex_sandbox(self, mode, script):
        from aidc.codex_runner import FORCED_CONFIG
        cfg = [x for c in FORCED_CONFIG if c.startswith("sandbox_") for x in ("-c", c)]
        return subprocess.run([CODEX, "sandbox", "-c", f'sandbox_mode="{mode}"', *cfg, "--", "sh", "-c", script],
                              cwd=self.work, capture_output=True, text=True, timeout=60)

    def test_codex_workspace_write_blocks_outside_writes(self):
        outside = os.path.join(self.tmp.name, "outside.txt")
        tmp_probe = f"/tmp/aidc-codex-probe-{os.getpid()}"
        proc = self.codex_sandbox("workspace-write", f"echo in > inside.txt; echo out > {outside}; echo t > {tmp_probe}")
        self.assertTrue(os.path.exists(os.path.join(self.work, "inside.txt")), proc.stdout + proc.stderr)
        self.assertFalse(os.path.exists(outside), "Codex sandbox allowed a write outside the workspace")
        self.assertFalse(os.path.exists(tmp_probe), "Codex sandbox allowed a write to /tmp")

    def test_codex_read_only_blocks_workspace_writes(self):
        self.codex_sandbox("read-only", "echo x > attempt.txt")
        self.assertFalse(os.path.exists(os.path.join(self.work, "attempt.txt")))


if __name__ == "__main__":
    unittest.main()
