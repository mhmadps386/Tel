"""End-to-end tests of `aidc dispatch` against a fake Codex binary in a throwaway git repo."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest

from aidc import cli, codex_runner, policy

FAKE = os.path.join(os.path.dirname(__file__), "fake_codex.py")


class DispatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.repo)
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "t"], ["commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git", "-C", self.repo, *cmd], check=True)
        self.env = {"AIDC_REPO_ROOT": self.repo, "AIDC_RUNS_ROOT": os.path.join(self.tmp.name, "runs"),
                    "AIDC_WORKTREES_ROOT": os.path.join(self.tmp.name, "worktrees"),
                    "FAKE_CODEX_MODE": "ok", "FAKE_CODEX_AUTH": "chatgpt", "OPENAI_API_KEY": "sk-should-be-scrubbed"}
        self.old_env = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.run_cli("init", "--goal", "g", "--run-id", "r1")
        plan = {"tasks": [
            {"id": "dev", "title": "Build", "role": "developer", "spec": "do it", "timeout_s": 20},
            {"id": "qa", "title": "Review", "role": "qa", "spec": "check it", "depends_on": ["dev"], "timeout_s": 20},
        ]}
        plan_file = os.path.join(self.tmp.name, "plan.json")
        with open(plan_file, "w") as fh:
            json.dump(plan, fh)
        self.run_cli("plan", "--run", "r1", "--file", plan_file)

    def tearDown(self):
        for k, v in self.old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def dispatch(self):
        return self.run_cli("dispatch", "--run", "r1", "--codex-bin", FAKE)

    def state(self):
        return cli.board_for("r1").state()

    def test_developer_then_independent_qa(self):
        code, out, err = self.dispatch()
        self.assertEqual(code, 0, err)
        tasks = self.state()["tasks"]
        self.assertEqual(tasks["dev"]["result"], "pass")
        self.assertEqual(tasks["qa"]["result"], "pass")
        self.assertTrue(tasks["dev"]["branch"].startswith("aidc/r1/dev"))
        # Developer commit landed on the isolated branch only, never on main.
        log = subprocess.run(["git", "-C", self.repo, "log", "--oneline", "main"], capture_output=True, text=True).stdout
        self.assertNotIn("aidc", log)
        files = subprocess.run(["git", "-C", self.repo, "show", "--name-only", "--format=", tasks["dev"]["branch"]],
                               capture_output=True, text=True).stdout
        self.assertIn("feature.txt", files)
        with open(os.path.join(cli.board_for("r1").run_dir, "reports", "qa.md")) as fh:
            qa_report = fh.read()
        self.assertIn("read-only", qa_report)

    def test_qa_failure_is_recorded(self):
        os.environ["FAKE_CODEX_MODE"] = "qa_fail"
        self.dispatch()
        self.assertEqual(self.state()["tasks"]["qa"]["result"], "fail")

    def test_refuses_api_key_auth(self):
        os.environ["FAKE_CODEX_AUTH"] = "api_key"
        code, _, err = self.dispatch()
        self.assertEqual(code, 2)
        self.assertIn("API key", err)
        self.assertEqual(self.state()["tasks"]["dev"]["attempts"], 0)

    def test_refuses_when_not_logged_in(self):
        os.environ["FAKE_CODEX_AUTH"] = "none"
        code, _, err = self.dispatch()
        self.assertEqual(code, 2)
        self.assertIn("codex login", err)

    def test_usage_limit_halts_without_retry(self):
        os.environ["FAKE_CODEX_MODE"] = "limit"
        self.dispatch()
        state = self.state()
        self.assertEqual(state["halted"]["reason"], "subscription_usage_limit")
        self.assertEqual(state["tasks"]["dev"]["status"], "failed")
        self.assertEqual(state["tasks"]["dev"]["attempts"], 1)
        self.assertEqual(state["tasks"]["qa"]["status"], "cancelled")

    def test_crash_is_retried_once(self):
        os.environ["FAKE_CODEX_COUNTER"] = os.path.join(self.tmp.name, "count")
        os.environ["FAKE_CODEX_FAIL_FIRST"] = "1"
        try:
            self.dispatch()
        finally:
            os.environ.pop("FAKE_CODEX_COUNTER")
            os.environ.pop("FAKE_CODEX_FAIL_FIRST")
        dev = self.state()["tasks"]["dev"]
        self.assertEqual((dev["status"], dev["attempts"], len(dev["errors"])), ("done", 2, 1))

    def test_timeout_kills_agent(self):
        os.environ["FAKE_CODEX_MODE"] = "sleep"
        board = cli.board_for("r1")
        with board._mutate() as st:
            st["tasks"]["dev"]["timeout_s"] = 1
            st["tasks"]["dev"]["max_attempts"] = 1
        self.dispatch()
        dev = self.state()["tasks"]["dev"]
        self.assertEqual(dev["status"], "failed")
        self.assertIn("timed out", dev["errors"][0]["error"])


class PolicyTest(unittest.TestCase):
    def test_dangerous_sandbox_rejected(self):
        with self.assertRaises(policy.PolicyError):
            codex_runner.build_command("codex", "/tmp", "/tmp/o", "danger-full-access")

    def test_command_never_bypasses_approvals(self):
        cmd = codex_runner.build_command("codex", "/w", "/o", "workspace-write")
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertIn('approval_policy="never"', cmd)

    def test_paths_confined(self):
        with self.assertRaises(policy.PolicyError):
            policy.ensure_inside("/etc/passwd", "/home")
        with self.assertRaises(policy.PolicyError):
            policy.safe_branch("r1", "../../main")

    def test_usage_limit_detection(self):
        self.assertTrue(policy.hits_usage_limit("You've hit your usage limit"))
        self.assertFalse(policy.hits_usage_limit("all 12 tests passed"))


if __name__ == "__main__":
    unittest.main()
