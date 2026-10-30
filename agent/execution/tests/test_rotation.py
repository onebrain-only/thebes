#!/usr/bin/env python3
"""D-044: the orchestrator moves to a fresh session after 4 compactions or a new day, and only
when nothing is in flight; the handoff carries the CEO's words verbatim and the fact block."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

from agent.state import store, validate                              # noqa: E402
from agent.execution import orders, watchdog                         # noqa: E402
import ceo_prompt_hook                                               # noqa: E402

OLD = "c0000000-0000-4000-8000-0000000000a1"
NEW = "c0000000-0000-4000-8000-0000000000b2"


class FakeCli:
    def __init__(self, state="idle"):
        self.rows = [{"sessionId": OLD, "name": "thebes-orchestrator", "state": state, "pid": 1}]
        self.stopped = []
        self.prompts = []

    def agents(self, include_completed=False):
        return list(self.rows)

    @staticmethod
    def find_by_sid(rows, sid):
        return next((r for r in rows if r.get("sessionId") == sid), None)

    def stop(self, short_id):
        self.stopped.append(short_id)

    def launch(self, cli, prompt, home):
        self.prompts.append(prompt)
        self.rows.append({"sessionId": NEW, "name": "thebes-orchestrator", "state": "working"})


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", OLD, "/tmp", "ceo")
        self.now = time.time()

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def compacted(self, n):
        for _ in range(n):
            ceo_prompt_hook.handle({"session_id": OLD, "hook_event_name": "PreCompact"})

    def rotate(self, cli):
        return watchdog.rotate_orchestrator(cli=cli, now=self.now, launch=cli.launch,
                                            sleep=lambda s: None)

    def test_three_compactions_on_the_same_day_is_not_due(self):
        self.compacted(3)
        self.assertIsNone(self.rotate(FakeCli()))

    def test_the_fourth_compaction_rotates_and_carries_the_ceos_words(self):
        orders.record_message(OLD, "اعمل تذكرة للـ recurring games",
                              now=self.now - watchdog.ROTATE_QUIET_SECONDS - 60)
        self.compacted(4)
        cli = FakeCli()
        out = self.rotate(cli)
        self.assertEqual((out["action"], out["reason"], out["to"]),
                         ("rotated-orchestrator", "compactions", NEW))
        self.assertEqual(store.active_role_session("orchestrator")["session_id"], NEW)
        self.assertIn(OLD, store.active_role_session("orchestrator")["previous_session_ids"])
        self.assertEqual(cli.stopped, [OLD[:8]])
        self.assertIn("اعمل تذكرة للـ recurring games", cli.prompts[0])
        self.assertIn("<thebes-facts", cli.prompts[0])
        self.assertEqual(ceo_prompt_hook.read_count(store),
                         dict(ceo_prompt_hook.read_count(store), session_id=NEW, count=0))
        self.assertEqual(orders.recent(1)[0]["action"], "rotated-orchestrator")

    def test_a_new_day_rotates(self):
        rec = store.active_role_session("orchestrator")
        self.assertEqual(watchdog.rotation_due(rec, now=self.now + 86400), "new-day")

    def test_nothing_rotates_while_a_lease_is_open_or_work_reports_to_the_old_session(self):
        self.compacted(4)
        os.makedirs(os.path.join(store.RUNTIME, "execution_lease"), exist_ok=True)
        orig = store.read_all

        def read_all(kind):
            if kind == "execution_lease":
                return [{"execution_lease_id": "lease-1"}]
            if kind == "conversation_dispatch":
                return [{"dispatch_id": "d1", "origin_provider": "claude",
                         "origin_thread_id": OLD, "status": "delivered"}]
            return orig(kind)
        store.read_all = read_all
        try:
            cli = FakeCli()
            out = self.rotate(cli)
        finally:
            store.read_all = orig
        self.assertEqual(out["action"], "rotation-waiting")
        self.assertIn("execution-lease-open", out["blocked_by"])
        self.assertIn("dispatches-open", out["blocked_by"])
        self.assertEqual((cli.prompts, cli.stopped), ([], []))
        self.assertEqual(store.active_role_session("orchestrator")["session_id"], OLD)

    def test_never_mid_turn_or_while_the_ceo_is_writing(self):
        self.compacted(4)
        orders.record_message(OLD, "مين ماسك KAN-693 دلوقتي؟", now=self.now - 30)
        cli = FakeCli(state="working")
        out = self.rotate(cli)
        self.assertEqual(sorted(out["blocked_by"]), ["ceo-talking", "mid-turn"])
        self.assertEqual(cli.prompts, [])


if __name__ == "__main__":
    unittest.main()
