import os
import tempfile
import time
import unittest

from aidc.board import Board, BoardError


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.board = Board.create(self.tmp.name, "demo goal", run_id="r1")
        self.board.add_task("dev", "Build", "developer", "spec", timeout_s=60)
        self.board.add_task("qa", "Review", "qa", "spec", depends_on=["dev"], timeout_s=60)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dependencies_gate_readiness(self):
        self.assertEqual([t["id"] for t in self.board.ready_tasks()], ["dev"])
        with self.assertRaises(BoardError):
            self.board.claim("qa", "qa-agent")
        self.board.claim("dev", "dev-agent")
        self.board.complete("dev", "dev-agent", "pass", "done", "# report")
        self.assertEqual([t["id"] for t in self.board.ready_tasks()], ["qa"])
        self.assertTrue(os.path.exists(os.path.join(self.board.run_dir, "reports", "dev.md")))

    def test_only_owner_can_complete(self):
        self.board.claim("dev", "dev-agent")
        with self.assertRaises(BoardError):
            self.board.complete("dev", "intruder", "pass", "x", "x")

    def test_retries_are_bounded_and_dependents_cancelled(self):
        self.board.claim("dev", "a")
        self.assertEqual(self.board.fail("dev", "a", "boom")["status"], "pending")
        self.board.claim("dev", "a")
        self.assertEqual(self.board.fail("dev", "a", "boom again")["status"], "failed")
        state = self.board.state()
        self.assertEqual(state["tasks"]["qa"]["status"], "cancelled")
        self.assertEqual(state["tasks"]["dev"]["attempts"], 2)

    def test_cancel_and_halt(self):
        self.board.cancel("dev", "operator request")
        self.assertEqual(self.board.state()["tasks"]["qa"]["status"], "cancelled")
        with self.assertRaises(BoardError):
            self.board.cancel("dev", "again")

    def test_halt_blocks_dispatch_until_resumed(self):
        self.board.halt("subscription_usage_limit")
        self.assertEqual(self.board.ready_tasks(), [])
        with self.assertRaises(BoardError):
            self.board.claim("dev", "a")
        self.board.resume("limit reset")
        self.assertEqual(len(self.board.ready_tasks()), 1)

    def test_recover_expired_lease(self):
        self.board.claim("dev", "a", lease_s=1)
        self.assertEqual(self.board.recover(now=time.time() + 5), ["dev"])
        self.assertEqual(self.board.state()["tasks"]["dev"]["status"], "pending")

    def test_validation(self):
        with self.assertRaises(BoardError):
            self.board.add_task("x", "t", "hacker", "s")
        with self.assertRaises(BoardError):
            self.board.add_task("y", "t", "qa", "s", depends_on=["missing"])
        with self.assertRaises(BoardError):
            self.board.add_task("z", "t", "qa", "s", max_attempts=50)

    def test_event_log_and_metrics(self):
        self.board.claim("dev", "a")
        self.board.complete("dev", "a", "pass", "ok", "r")
        kinds = [e["event"] for e in self.board.events()]
        self.assertEqual(kinds[:4], ["run.created", "task.planned", "task.planned", "task.claimed"])
        m = self.board.metrics()
        self.assertEqual(m["attempts_total"], 1)
        self.assertEqual(m["by_status"], {"done": 1, "pending": 1})


if __name__ == "__main__":
    unittest.main()
