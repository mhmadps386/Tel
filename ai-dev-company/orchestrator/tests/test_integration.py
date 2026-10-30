"""Integration tests: the dispatcher runs as a real separate process and is controlled
from other processes exactly as an operator would (`aidc cancel`, `halt`, `resume`,
`recover`, SIGKILL). Agents are real child processes (the fake Codex binary), so
timeouts, process-tree kills and parent-death behaviour are exercised for real.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ORCH = os.path.dirname(HERE)
FAKE = os.path.join(HERE, "fake_codex.py")


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); treat it as dead.
    with open(f"/proc/{pid}/stat") as fh:
        return fh.read().split(")")[-1].split()[0] != "Z"


def wait_for(predicate, timeout=20, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.repo = os.path.join(t, "repo")
        os.makedirs(self.repo)
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "t"], ["commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git", "-C", self.repo, *cmd], check=True)
        self.pidfile = os.path.join(t, "agent.pid")
        self.modefile = os.path.join(t, "mode")
        self.env = dict(os.environ, PYTHONPATH=ORCH, AIDC_REPO_ROOT=self.repo,
                        AIDC_RUNS_ROOT=os.path.join(t, "runs"), AIDC_WORKTREES_ROOT=os.path.join(t, "wt"),
                        AIDC_POLL_S="0.2", FAKE_CODEX_AUTH="chatgpt", FAKE_CODEX_PIDFILE=self.pidfile,
                        FAKE_CODEX_MODE_FILE=self.modefile, FAKE_CODEX_ESCAPE_PATH=os.path.join(self.repo, "ESCAPED"))
        self.cli("init", "--goal", "integration", "--run-id", "r1")

    def tearDown(self):
        subprocess.run(["pkill", "-f", "fake_codex.py"], capture_output=True)
        self.tmp.cleanup()

    # -- helpers -----------------------------------------------------------

    def cli(self, *argv, check=True):
        proc = subprocess.run([sys.executable, "-m", "aidc", *argv], env=self.env, capture_output=True, text=True,
                              timeout=120)
        if check and proc.returncode not in (0, 3):
            self.fail(f"aidc {argv} -> {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
        return proc

    def plan(self, dev_timeout=30, dev_attempts=2):
        plan = {"tasks": [
            {"id": "dev", "title": "Build", "role": "developer", "spec": "s", "timeout_s": dev_timeout,
             "max_attempts": dev_attempts},
            {"id": "qa", "title": "Review", "role": "qa", "spec": "s", "depends_on": ["dev"], "timeout_s": 30},
        ]}
        path = os.path.join(self.tmp.name, "plan.json")
        with open(path, "w") as fh:
            json.dump(plan, fh)
        self.cli("plan", "--run", "r1", "--file", path)

    def mode(self, m):
        with open(self.modefile, "w") as fh:
            fh.write(m)

    def start_dispatch(self):
        return subprocess.Popen([sys.executable, "-m", "aidc", "dispatch", "--run", "r1", "--codex-bin", FAKE],
                                env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def agent_pids(self):
        def read():
            try:
                with open(self.pidfile) as fh:
                    return fh.read().split()
            except FileNotFoundError:
                return []
        assert wait_for(lambda: len(read()) == 2), "agent never started"
        return [int(p) for p in read()]

    def state(self):
        with open(os.path.join(self.tmp.name, "runs", "r1", "board.json")) as fh:
            return json.load(fh)

    def events(self):
        with open(os.path.join(self.tmp.name, "runs", "r1", "events.jsonl")) as fh:
            return [json.loads(l)["event"] for l in fh]

    # -- tests -------------------------------------------------------------

    def test_timeout_kills_whole_process_tree(self):
        self.plan(dev_timeout=2, dev_attempts=1)
        self.mode("sleep")
        disp = self.start_dispatch()
        pids = self.agent_pids()
        disp.wait(timeout=30)
        self.assertTrue(wait_for(lambda: not any(alive(p) for p in pids), 10), "agent or grandchild survived timeout")
        dev = self.state()["tasks"]["dev"]
        self.assertEqual(dev["status"], "failed")
        self.assertIn("timed out after 2s", dev["errors"][0]["error"])
        self.assertEqual(self.state()["tasks"]["qa"]["status"], "cancelled")

    def test_cancel_running_task_from_another_process(self):
        self.plan()
        self.mode("sleep")
        disp = self.start_dispatch()
        pids = self.agent_pids()
        t0 = time.time()
        self.cli("cancel", "--run", "r1", "--task", "dev", "--reason", "operator cancel")
        disp.wait(timeout=30)
        self.assertLess(time.time() - t0, 15)
        self.assertTrue(wait_for(lambda: not any(alive(p) for p in pids), 10), "agent survived cancel")
        st = self.state()["tasks"]
        self.assertEqual((st["dev"]["status"], st["qa"]["status"]), ("cancelled", "cancelled"))
        self.assertNotIn("task.completed", self.events())

    def test_retry_limit_is_enforced(self):
        self.plan(dev_attempts=3)
        self.mode("crash")
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE, "--max-tasks", "10")
        dev = self.state()["tasks"]["dev"]
        self.assertEqual((dev["status"], dev["attempts"], len(dev["errors"])), ("failed", 3, 3))
        self.assertEqual(self.events().count("task.retry_scheduled"), 2)
        self.assertEqual(self.state()["tasks"]["qa"]["status"], "cancelled")
        # A further dispatch must not start a fourth attempt.
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE)
        self.assertEqual(self.state()["tasks"]["dev"]["attempts"], 3)

    def test_halt_stops_running_agent_and_resume_completes(self):
        self.plan(dev_attempts=2)
        self.mode("sleep")
        disp = self.start_dispatch()
        pids = self.agent_pids()
        self.cli("halt", "--run", "r1", "--reason", "operator stop")
        self.assertEqual(disp.wait(timeout=30), 3, "dispatch should exit 3 when halted")
        self.assertTrue(wait_for(lambda: not any(alive(p) for p in pids), 10), "agent survived halt")
        self.assertEqual(self.state()["tasks"]["dev"]["status"], "pending")
        # While halted, dispatch claims nothing.
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE)
        self.assertEqual(self.state()["tasks"]["dev"]["attempts"], 1)
        self.cli("resume", "--run", "r1", "--note", "approved to continue")
        self.mode("ok")
        self.assertEqual(self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE).returncode, 0)
        st = self.state()["tasks"]
        self.assertEqual((st["dev"]["status"], st["dev"]["attempts"], st["qa"]["status"]), ("done", 2, "done"))

    def test_recovery_after_dispatcher_crash(self):
        self.env["AIDC_LEASE_GRACE_S"] = "0"
        self.plan(dev_timeout=3)
        self.mode("sleep")
        disp = self.start_dispatch()
        agent_pid = self.agent_pids()[0]
        disp.send_signal(signal.SIGKILL)
        disp.wait()
        # Parent-death signal: the agent must not outlive the orchestrator.
        self.assertTrue(wait_for(lambda: not alive(agent_pid), 10), "agent orphaned after dispatcher crash")
        self.assertEqual(self.state()["tasks"]["dev"]["status"], "running")
        self.assertTrue(wait_for(lambda: json.loads(self.cli("recover", "--run", "r1").stdout)["recovered"] == ["dev"],
                                 15, 0.5))
        self.assertEqual(self.state()["tasks"]["dev"]["status"], "pending")
        self.mode("ok")
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE)
        st = self.state()["tasks"]
        self.assertEqual((st["dev"]["status"], st["dev"]["attempts"], st["qa"]["status"]), ("done", 2, "done"))
        self.assertIn("task.recovered", self.events())

    def test_max_tasks_stop_condition(self):
        self.plan()
        self.mode("ok")
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE, "--max-tasks", "1")
        st = self.state()["tasks"]
        self.assertEqual((st["dev"]["status"], st["qa"]["status"]), ("done", "pending"))

    def test_usage_limit_stop_condition(self):
        self.plan()
        self.mode("limit")
        self.assertEqual(self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE).returncode, 3)
        st = self.state()
        self.assertEqual(st["halted"]["reason"], "subscription_usage_limit")
        self.assertEqual(st["tasks"]["dev"]["attempts"], 1)

    def test_isolation_violation_halts_run(self):
        self.plan()
        self.mode("escape")
        self.assertEqual(self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE).returncode, 3)
        st = self.state()
        self.assertEqual(st["halted"]["reason"], "isolation_violation")
        self.assertEqual(st["tasks"]["dev"]["status"], "failed")
        self.assertEqual(st["tasks"]["qa"]["status"], "cancelled")

    def test_manager_review_gate(self):
        self.plan()
        self.mode("ok")
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE)
        ok = self.cli("review", "--run", "r1", "--task", "dev", "--test-cmd", "test -f feature.txt",
                      "--test-dir", ".", check=False)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["accepted"])
        # A failing objective check (tests) must reject, even though both agents said PASS.
        bad = self.cli("review", "--run", "r1", "--task", "dev", "--test-cmd", "test -f missing.txt",
                       "--test-dir", ".", check=False)
        self.assertEqual(bad.returncode, 1)
        self.assertFalse(json.loads(bad.stdout)["checks"]["manager_tests_pass"])
        self.assertEqual(self.events()[-1], "manager.rejected")

    def test_manager_review_rejects_failed_qa(self):
        self.plan()
        self.mode("qa_fail")
        self.cli("dispatch", "--run", "r1", "--codex-bin", FAKE)
        res = self.cli("review", "--run", "r1", "--task", "dev", "--test-cmd", "true", "--test-dir", ".", check=False)
        self.assertEqual(res.returncode, 1)
        self.assertFalse(json.loads(res.stdout)["checks"]["qa_done_pass"])

    def test_manual_developer_claim_requires_ack(self):
        self.plan()
        proc = self.cli("claim", "--run", "r1", "--task", "dev", "--agent", "someone", check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not OS-sandboxed", proc.stderr)
        self.cli("claim", "--run", "r1", "--task", "dev", "--agent", "someone", "--unsandboxed-ack")
        self.assertIn("policy.unsandboxed_claim", self.events())


if __name__ == "__main__":
    unittest.main()
