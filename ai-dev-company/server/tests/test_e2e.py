"""End-to-end tests of the control panel + execution worker.

Real: HTTP server, Postgres, auth/CSRF, worker process, git worktrees, OS sandbox
(bubblewrap + the real Codex sandbox in the worker self-test and the manager's test re-run),
process kills. SIMULATED: the AI model (tests/sim_codex.py), so no subscription quota is used.

Requires AIDC_TEST_DATABASE_URL pointing at a Postgres server where databases can be created.
"""

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

import psycopg
import psycopg.conninfo

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
SIM = os.path.join(HERE, "sim_codex.py")
REAL_CODEX = os.path.join(PROJECT, ".tools", "node_modules", ".bin", "codex")
ADMIN_URL = os.environ.get("AIDC_TEST_DATABASE_URL")

sys.path.insert(0, PROJECT)
from server import auth  # noqa: E402

INITIAL = "initial-password-123"
NEW = "owner-chosen-password-456"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    with open(f"/proc/{pid}/stat") as fh:
        return fh.read().split(")")[-1].split()[0] != "Z"


def wait_for(pred, timeout=60, interval=0.3, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        v = pred()
        if v:
            return v
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {what}")


class Client:
    def __init__(self, port):
        self.port, self.cookie, self.csrf = port, None, None

    def req(self, method, path, body=None, headers=None, raw=False):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = dict(headers or {})
        if self.cookie:
            h["Cookie"] = self.cookie
        if body is not None:
            h["Content-Type"] = "application/json"
            if self.csrf and "X-CSRF" not in h:
                h["X-CSRF"] = self.csrf
        conn.request(method, path, json.dumps(body) if body is not None else None, h)
        res = conn.getresponse()
        data = res.read()
        sc = res.getheader("Set-Cookie")
        if sc and sc.startswith(auth.COOKIE + "="):
            self.cookie = sc.split(";")[0] if not sc.startswith(auth.COOKIE + "=;") else None
        if raw:
            return res, data
        return res.status, (json.loads(data) if data and data[:1] in b"{[" else data)

    def login(self, password):
        status, body = self.req("POST", "/api/login", {"password": password})
        assert status == 200, body
        self.csrf = self.state()["csrf"]

    def state(self):
        status, body = self.req("GET", "/api/state")
        assert status == 200, body
        self.csrf = body["csrf"]
        return body

    def control(self, action, **kw):
        status, body = self.req("POST", "/api/control", {"action": action, **kw})
        assert status == 200, body
        return body


@unittest.skipUnless(ADMIN_URL, "AIDC_TEST_DATABASE_URL not set")
class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dbname = "aidc_e2e_" + uuid.uuid4().hex[:8]
        with psycopg.connect(ADMIN_URL, autocommit=True) as c:
            c.execute(f"CREATE DATABASE {cls.dbname}")
        cls.db_url = psycopg.conninfo.make_conninfo(ADMIN_URL, dbname=cls.dbname)
        cls.tmp = tempfile.TemporaryDirectory(prefix="aidc-e2e-", dir=os.path.join(PROJECT, ".aidc-worktrees")
                                              if os.path.isdir(os.path.join(PROJECT, ".aidc-worktrees")) else None)
        cls.simdir = os.path.join(cls.tmp.name, "sim")
        os.makedirs(cls.simdir)
        cls.port = free_port()
        cls.server_env = dict(os.environ, DATABASE_URL=cls.db_url, PORT=str(cls.port), PYTHONPATH=PROJECT,
                              AIDC_INITIAL_PASSWORD_HASH=auth.hash_password(INITIAL))
        cls.server = cls.start_server()
        cls.worker = None

    @classmethod
    def logfile(cls, name):
        fh = open(os.path.join(cls.tmp.name, name), "a")
        cls._files = getattr(cls, "_files", []) + [fh]
        return fh

    @classmethod
    def start_server(cls):
        proc = subprocess.Popen([sys.executable, "-m", "server.app"], cwd=PROJECT, env=cls.server_env,
                                stdout=subprocess.DEVNULL, stderr=cls.logfile("server.log"))
        wait_for(lambda: cls._health(), 30, what="server health")
        return proc

    @classmethod
    def _health(cls):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=2)
            conn.request("GET", "/healthz")
            return conn.getresponse().status == 200
        except OSError:
            return False

    @classmethod
    def tearDownClass(cls):
        for p in (cls.worker, cls.server):
            if p and p.poll() is None:
                p.kill()
                p.wait()
        subprocess.run(["pkill", "-f", "^python[0-9.]* " + SIM], capture_output=True)
        for fh in getattr(cls, "_files", []):
            fh.close()
        if os.environ.get("AIDC_E2E_KEEP"):
            print("kept", cls.tmp.name, cls.dbname)
            return
        with psycopg.connect(ADMIN_URL, autocommit=True) as c:
            c.execute(f"DROP DATABASE IF EXISTS {cls.dbname} WITH (FORCE)")
        cls.tmp.cleanup()

    # -- helpers ----------------------------------------------------------------

    def owner(self):
        c = Client(self.port)
        c.login(NEW)
        return c

    def start_worker(self, token, worker_id="w1", extra_env=None):
        env = dict(os.environ, AIDC_SERVER_URL=f"http://127.0.0.1:{self.port}", AIDC_WORKER_TOKEN=token,
                   AIDC_WORKER_ID=worker_id, AIDC_DATA_DIR=os.path.join(self.tmp.name, f"data-{worker_id}"),
                   AIDC_CODEX_BIN=SIM, SIM_REAL_CODEX=REAL_CODEX, SIM_DIR=self.simdir,
                   AIDC_HEARTBEAT_S="1", AIDC_IDLE_POLL_S="0.5", OPENAI_API_KEY="sk-should-be-stripped-123456789",
                   **(extra_env or {}))
        return subprocess.Popen([sys.executable, os.path.join(PROJECT, "worker", "main.py")], env=env,
                                stdout=self.logfile(f"{worker_id}.log"), stderr=subprocess.STDOUT)

    def mission(self, c, title):
        status, body = c.req("POST", "/api/missions", {"project_id": 1, "title": title, "request": f"{title} please"})
        self.assertEqual(status, 200, body)
        return body["mission_id"]

    def mission_state(self, c, mid):
        return next(m for m in c.state()["missions"] if m["id"] == mid)

    def wait_status(self, c, mid, status, timeout=120):
        return wait_for(lambda: self.mission_state(c, mid)["status"] == status and self.mission_state(c, mid),
                        timeout, 0.5, f"mission {mid} -> {status}")

    def approve(self, c, mid, kind):
        a = wait_for(lambda: next((a for a in c.state()["approvals"] if a["mission_id"] == mid and a["kind"] == kind), None),
                     60, 0.5, f"{kind} approval for {mid}")
        status, body = c.req("POST", f"/api/approvals/{a['id']}", {"decision": "approve"})
        self.assertEqual(status, 200, body)

    def events(self, c):
        return [e["kind"] for e in reversed(c.state()["events"])]

    # -- tests (run in order) ---------------------------------------------------

    def test_01_security_surface(self):
        anon = Client(self.port)
        res, body = anon.req("GET", "/", raw=True)
        self.assertEqual(res.status, 200)
        for h in ("Content-Security-Policy", "X-Frame-Options", "Strict-Transport-Security", "X-Robots-Tag"):
            self.assertTrue(res.getheader(h), h)
        self.assertNotIn(b"<script>", body)  # no inline script; everything under CSP
        self.assertEqual(anon.req("GET", "/api/state")[0], 401)
        self.assertEqual(anon.req("POST", "/api/missions", {"title": "x"})[0], 401)
        self.assertEqual(anon.req("POST", "/worker/claim", {})[0], 401)
        self.assertEqual(anon.req("POST", "/worker/claim", {}, {"Authorization": "Bearer aidcw_forged"})[0], 401)
        res, body = anon.req("GET", "/healthz", raw=True)
        self.assertEqual(json.loads(body), {"ok": True})

        # Initial password works only to set a new one.
        c = Client(self.port)
        c.login(INITIAL)
        self.assertTrue(c.state()["must_change_password"])
        self.assertEqual(c.req("POST", "/api/missions", {"project_id": 1, "title": "t", "request": "r"})[0], 403)
        self.assertEqual(c.req("POST", "/api/password", {"current": INITIAL, "new": "short"})[0], 400)
        self.assertEqual(c.req("POST", "/api/password", {"current": INITIAL, "new": NEW})[0], 200)
        self.assertEqual(c.req("GET", "/api/state")[0], 401)  # all sessions signed out
        self.assertEqual(Client(self.port).req("POST", "/api/login", {"password": INITIAL})[0], 403)

        c = self.owner()
        # CSRF: same session, missing or wrong token is refused.
        self.assertEqual(c.req("POST", "/api/control", {"action": "pause"}, {"X-CSRF": "wrong"})[0], 403)
        # Rate limit: 5 bad passwords from one IP lock that IP out, even with the right password afterwards.
        bad = Client(self.port)
        hdr = {"X-Forwarded-For": "203.0.113.9"}
        for _ in range(5):
            self.assertEqual(bad.req("POST", "/api/login", {"password": "nope-nope-nope"}, hdr)[0], 403)
        status, body = bad.req("POST", "/api/login", {"password": NEW}, hdr)
        self.assertEqual(status, 403)
        self.assertIn("too many", body["error"])

    def test_02_worker_and_device_login(self):
        c = self.owner()
        status, body = c.req("POST", "/api/worker-tokens", {"name": "w1"})
        self.assertEqual(status, 200)
        token = body["token"]
        type(self).token = token
        self.assertNotIn(token, json.dumps(c.state()))  # never shown again
        type(self).worker = self.start_worker(token)
        w = wait_for(lambda: next((w for w in c.state()["workers"] if w["id"] == "w1"), None), 60, 0.5, "worker online")
        wait_for(lambda: c.state()["workers"][0]["info"].get("sandbox_ok"), 60, 0.5, "sandbox self-test")
        self.assertEqual(c.state()["workers"][0]["info"]["auth_mode"], "none")

        # Agent work is not claimable without ChatGPT auth: a plan job stays pending.
        mid = self.mission(c, "Before login")
        time.sleep(3)
        self.assertEqual(self.mission_state(c, mid)["status"], "planning")

        c.control("codex_login")
        login = wait_for(lambda: c.state()["login"].get("user_code") and c.state()["login"], 30, 0.5, "device code")
        self.assertEqual(login["verification_url"], "https://auth.openai.com/codex/device")
        self.assertEqual(login["user_code"], "SIMU-1234")
        open(os.path.join(self.simdir, "approve-login"), "w").close()  # owner completes sign-in on OpenAI's site
        wait_for(lambda: c.state()["workers"][0]["info"].get("auth_mode") == "chatgpt", 30, 0.5, "chatgpt auth")
        # The queued plan now runs (planning is allowed while paused; nothing executes before approval).
        self.wait_status(c, mid, "awaiting_plan_approval")
        status, _ = c.req("POST", f"/api/missions/{mid}/cancel", {})
        self.assertEqual(status, 200)

    def test_03_full_loop_with_correction_round(self):
        c = self.owner()
        with open(os.path.join(self.simdir, "review-1"), "w") as fh:
            fh.write("correct")
        mid = self.mission(c, "Add notes")
        self.wait_status(c, mid, "awaiting_plan_approval")
        self.approve(c, mid, "plan")
        self.assertEqual(self.mission_state(c, mid)["status"], "approved")
        time.sleep(2)  # loop is paused: nothing starts without the owner
        self.assertEqual(self.mission_state(c, mid)["status"], "approved")
        c.control("start")
        m = self.wait_status(c, mid, "awaiting_merge_approval", 180)
        self.assertEqual(m["round"], 2)
        kinds = self.events(c)
        self.assertIn("correction.assigned", kinds)
        jobs = sorted((j for j in c.state()["jobs"] if j["mission_id"] == mid), key=lambda j: j["id"])
        self.assertEqual([j["kind"] for j in jobs], ["plan", "develop", "qa", "review", "develop", "qa", "review"])
        reviews = [j for j in jobs if j["kind"] == "review"]
        self.assertTrue(all(r["tests"]["exit_code"] == 0 for r in reviews), reviews)  # real npm test in sandbox
        self.assertEqual(c.state()["loop"]["state"], "paused")  # auto-continue off -> stops after the mission
        repo = os.path.join(self.tmp.name, "data-w1", "repo")
        before = subprocess.run(["git", "-C", repo, "log", "--oneline", "main"], capture_output=True, text=True).stdout
        self.assertNotIn("Merge", before)  # nothing merged without approval
        self.approve(c, mid, "merge")
        self.wait_status(c, mid, "completed", 60)
        after = subprocess.run(["git", "-C", repo, "log", "--oneline", "main"], capture_output=True, text=True).stdout
        self.assertIn("owner approved", after)
        self.assertEqual(subprocess.run(["git", "-C", repo, "remote"], capture_output=True, text=True).stdout, "")

    def running_dev(self, c, mid):
        return wait_for(lambda: next((j for j in c.state()["jobs"] if j["mission_id"] == mid and j["kind"] == "develop"
                                      and j["status"] == "running"), None), 60, 0.5, "running develop job")

    def dev_pid(self):
        path = os.path.join(self.simdir, "dev-pid")
        def read():
            try:
                with open(path) as fh:
                    return fh.read().strip()
            except FileNotFoundError:
                return None
        return int(wait_for(read, 30, 0.2, "dev pid"))

    def start_hanging_mission(self, c, title):
        open(os.path.join(self.simdir, "hang"), "w").close()
        dev_pid_file = os.path.join(self.simdir, "dev-pid")
        if os.path.exists(dev_pid_file):
            os.remove(dev_pid_file)
        mid = self.mission(c, title)
        self.wait_status(c, mid, "awaiting_plan_approval")
        self.approve(c, mid, "plan")
        c.control("start")
        self.running_dev(c, mid)
        return mid, self.dev_pid()

    def test_04_cancel_kills_agent(self):
        c = self.owner()
        mid, pid = self.start_hanging_mission(c, "Cancel me")
        t0 = time.time()
        self.assertEqual(c.req("POST", f"/api/missions/{mid}/cancel", {})[0], 200)
        wait_for(lambda: not alive(pid), 20, 0.2, "agent killed after cancel")
        self.assertLess(time.time() - t0, 20)
        self.assertEqual(self.mission_state(c, mid)["status"], "cancelled")
        os.remove(os.path.join(self.simdir, "hang"))

    def test_05_emergency_stop(self):
        c = self.owner()
        mid, pid = self.start_hanging_mission(c, "Stop everything")
        c.control("estop")
        wait_for(lambda: not alive(pid), 20, 0.2, "agent killed after estop")
        s = c.state()
        self.assertTrue(s["estop"]["active"])
        self.assertEqual(s["loop"]["state"], "paused")
        dev = next(j for j in s["jobs"] if j["mission_id"] == mid and j["kind"] == "develop")
        self.assertEqual(dev["status"], "pending")  # released, not judged
        status, body = c.req("POST", "/api/control", {"action": "start"})
        self.assertEqual(status, 400)  # cannot start while e-stop is active
        time.sleep(3)
        self.assertEqual(next(j for j in c.state()["jobs"] if j["id"] == dev["id"])["status"], "pending")
        c.control("clear_estop")
        c.req("POST", f"/api/missions/{mid}/cancel", {})
        os.remove(os.path.join(self.simdir, "hang"))

    def test_06_worker_crash_recovery(self):
        c = self.owner()
        mid, pid = self.start_hanging_mission(c, "Survive a crash")
        dev = self.running_dev(c, mid)
        self.worker.send_signal(signal.SIGKILL)
        self.worker.wait()
        wait_for(lambda: not alive(pid), 20, 0.2, "agent died with its worker (PDEATHSIG)")
        os.remove(os.path.join(self.simdir, "hang"))
        type(self).worker = self.start_worker(self.token)
        m = self.wait_status(c, mid, "awaiting_merge_approval", 180)
        job = next(j for j in c.state()["jobs"] if j["id"] == dev["id"])
        self.assertEqual(job["attempts"], 2)
        self.assertTrue(any("released" in (e.get("error") or "") for e in job["errors"]))
        self.assertEqual(m["round"], 1)

    def test_07_server_restart_keeps_state(self):
        c = self.owner()
        before = c.state()
        self.server.kill()
        self.server.wait()
        type(self).server = self.start_server()
        c2 = self.owner()
        after = c2.state()
        self.assertEqual([m["id"] for m in before["missions"]], [m["id"] for m in after["missions"]])
        self.assertEqual(len(after["approvals"]), len(before["approvals"]))
        wait_for(lambda: c2.state()["workers"][0]["online"], 30, 0.5, "worker reconnects")

    def test_08_secrets_never_reach_the_browser(self):
        c = self.owner()
        blob = json.dumps(c.state())
        for needle in ("sk-should-be-stripped", self.token, "postgresql://", "password_hash", "scrypt$"):
            self.assertNotIn(needle, blob)

    def test_09_unsandboxed_worker_refuses_agent_work(self):
        c = self.owner()
        self.worker.kill()
        self.worker.wait()
        status, body = c.req("POST", "/api/worker-tokens", {"name": "nosandbox"})
        home = os.path.join(self.tmp.name, "data-w-nosandbox", "codex")
        os.makedirs(home)
        open(os.path.join(home, "sim-chatgpt-auth"), "w").close()  # signed in: only the sandbox is missing
        w2 = self.start_worker(body["token"], "w-nosandbox", {"AIDC_BWRAP": "/bin/false"})
        try:
            wait_for(lambda: any(w["id"] == "w-nosandbox" for w in c.state()["workers"]), 30, 0.5, "w2 online")
            info = next(w for w in c.state()["workers"] if w["id"] == "w-nosandbox")["info"]
            self.assertFalse(info["sandbox_ok"])
            open(os.path.join(self.simdir, "approve-login"), "w").close()
            mid = self.mission(c, "Must not run")
            time.sleep(5)
            self.assertEqual(self.mission_state(c, mid)["status"], "planning")  # nobody safe to run it
        finally:
            w2.kill()
            w2.wait()


if __name__ == "__main__":
    unittest.main()
