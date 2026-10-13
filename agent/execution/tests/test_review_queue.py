#!/usr/bin/env python3
"""The Codex reviewer's queue (D-043 draft). Fakes only."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                               # noqa: E402
from agent.execution import review_queue as rq, verify, jira_sync    # noqa: E402

ORCH = "0eeeeeee-9999-7000-8000-00000000000e"
LUXOR = "0bbbbbbb-9999-7000-8000-00000000000b"
HOME = "/stable/home"
SHA = "a" * 40


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        os.environ["CODEX_THREAD_ID"] = "thread-A"

    def tearDown(self):
        os.environ.pop("CODEX_THREAD_ID", None)
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def judge_root(self, key="KAN-9"):
        did = store.new_id("conversation_dispatch")
        results = {"C1": {"status": "pass", "what": "analyze"},
                   "C2": {"status": "pending-judge", "what": "chips equal height",
                          "by": "judge", "cycle": 1},
                   "C3": {"status": "pending-judge", "what": "same in Arabic", "by": "judge",
                          "cycle": 1}}
        store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": LUXOR, "target_seat_id": "luxor",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "completed", "delivery_status": "DELIVERED", "outcome": "completed",
            "result_ref": "/x", "result_sha256": "0" * 64, "outcome_at": store.now(),
            "attested_delivery_id": did, "reported_session_id": LUXOR, "jira_key": key, "branch": "alpha-luxor",
            "checks": [{"id": "C1", "kind": "run", "what": "flutter analyze", "pass": "exit 0"},
                       {"id": "C2", "kind": "judge", "what": "chips equal height",
                        "pass": "screenshot en light"},
                       {"id": "C3", "kind": "judge", "what": "same in Arabic",
                        "pass": "screenshot ar"}],
            "verification": {"verdict": "needs_judge", "cycle": 1, "branch": "alpha-luxor",
                             "sha": SHA, "results": results}}, rid=did)
        return did

    def test_a_judge_item_is_offered_once_and_only_to_the_claimant(self):
        did = self.judge_root()
        item = rq.next_item(with_qa=False)
        self.assertEqual((item["kind"], item["ticket"], item["dispatch_id"]), ("judge", "KAN-9", did))
        self.assertEqual([c["id"] for c in item["checks"]], ["C2", "C3"])
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        self.assertIsNone(rq.next_item(with_qa=False), "claimed by thread A: nobody else gets it")
        os.environ["CODEX_THREAD_ID"] = "thread-A"
        self.assertEqual(rq.next_item(with_qa=False)["item_id"], item["item_id"],
                         "the holder asking again gets the same item")

    def test_a_stale_claim_is_offered_again(self):
        self.judge_root()
        item = rq.next_item(with_qa=False)
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        self.assertTrue(rq.claim(item["item_id"], now=__import__("time").time() + rq.CLAIM_SECONDS + 5))
        self.assertEqual(rq.holder(item["item_id"]), "thread-B")

    def test_only_the_claimant_can_submit_and_evidence_is_required(self):
        self.judge_root()
        item = rq.next_item(with_qa=False)
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        with self.assertRaises(rq.Refused) as ctx:
            rq.submit_judge(item["item_id"], ["C2", "C3"], {}, {}, "looked", state_store=store)
        self.assertEqual(ctx.exception.code, "not-your-claim")
        os.environ["CODEX_THREAD_ID"] = "thread-A"
        with self.assertRaises(rq.Refused) as ctx:
            rq.submit_judge(item["item_id"], ["C2", "C3"], {}, {}, "  ", state_store=store)
        self.assertEqual(ctx.exception.code, "evidence-required")

    def test_pass_and_skip_close_the_checks_and_the_item_is_done(self):
        did = self.judge_root()
        item = rq.next_item(with_qa=False)
        with mock.patch.object(jira_sync, "on_verified", return_value=None):
            out = rq.submit_judge(item["item_id"], ["C2"], {}, {"C3": "needs-write"},
                                  "opened Home en/light, screenshot x.png", state_store=store,
                                  jira=mock.Mock(), dispatcher=mock.Mock(), launcher=mock.Mock())
        self.assertEqual(out["status"], "recorded")
        res = store.read("conversation_dispatch", did)["verification"]["results"]
        self.assertEqual((res["C2"]["status"], res["C2"]["by"]), ("pass", "reviewer"))
        self.assertIn("SKIPPED", res["C3"]["detail"])
        self.assertIsNone(rq.next_item(with_qa=False), "a settled item is never offered again")
        self.assertTrue(rq.is_done(item["item_id"]))

    def test_an_item_whose_ticket_is_already_done_is_dropped(self):
        """Live 2026-10-13: a stale KAN-438 item the PO had closed was reviewed and failed."""
        self.judge_root("KAN-9")
        jira = mock.Mock()
        jira.get_issue.return_value = {"status": "Done"}
        self.assertEqual(rq.candidates(jira=jira, with_qa=False), [])
        self.judge_root("KAN-10")                 # the Done one is marked finished for good
        jira.get_issue.return_value = {"status": "Self-review"}
        jira.get_comments.return_value = [{"created": "t", "body": "PO accepted AC1-6"}]
        items = rq.candidates(jira=jira, with_qa=False)
        self.assertEqual(items[0]["ticket_status"], "Self-review")
        self.assertEqual(items[0]["latest_comments"][0]["text"], "PO accepted AC1-6")

    def test_wait_returns_the_item_or_times_out(self):
        clock = {"t": 0.0}
        self.assertIsNone(rq.wait(10, sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
                                  clock=lambda: clock["t"]))
        self.judge_root()
        self.assertEqual(rq.wait(10, sleep=lambda s: None)["kind"], "judge")


if __name__ == "__main__":
    unittest.main()
