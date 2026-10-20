#!/usr/bin/env python3
"""Compact heavy idle sessions while the cache is warm (CEO 2026-10-20). Fakes only."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                               # noqa: E402
from agent.execution import session_weight as sw, conversation_dispatch as cd   # noqa: E402

KARNAK = "0aaaaaaa-5555-7000-8000-00000000000a"
MEMPHIS = "0ddddddd-5555-7000-8000-00000000000d"
ORCH = "0eeeeeee-5555-7000-8000-00000000000e"


class FakeCli:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def agents(self):
        return self.rows

    @staticmethod
    def find_by_sid(rows, sid):
        return next((r for r in rows if r["sessionId"] == sid), None)

    def stop(self, short):
        self.calls.append(("stop", short))

    def wait_stopped(self, sid, timeout, pid=None):
        return True

    def bg_resume(self, sid, prompt, cwd):
        self.calls.append(("resume", sid, prompt))


class SessionWeightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        for seat, sid in (("orchestrator", ORCH), ("karnak", KARNAK), ("memphis", MEMPHIS)):
            store.bind_role_session(seat, "claude", sid, "/h", "ceo")
        self.now = time.time()

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ctx(self, tokens, idle_min):
        return lambda sid: {"tokens": tokens, "at": self.now - idle_min * 60, "path": "/x"}

    def run_pass(self, cli, context_fn):
        return sw.compact_idle(state_store=store, cli=cli, now=self.now, context_fn=context_fn)

    def rows(self, **states):
        return [{"sessionId": sid, "state": st, "pid": 1} for sid, st in states.items()]

    def test_the_context_is_read_from_the_last_assistant_turn_of_the_transcript(self):
        d = os.path.join(self.tmp, "home", ".claude", "projects", "p")
        os.makedirs(d)
        with open(os.path.join(d, KARNAK + ".jsonl"), "w") as fh:
            for u, ts in (({"input_tokens": 1, "cache_read_input_tokens": 10, "cache_creation_input_tokens": 0}, "2026-10-20T08:00:00.000Z"),
                          ({"input_tokens": 5, "cache_read_input_tokens": 200000, "cache_creation_input_tokens": 300}, "2026-10-20T09:00:00.000Z")):
                fh.write(json.dumps({"type": "assistant", "timestamp": ts, "message": {"usage": u}}) + "\n")
            fh.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        with mock.patch.dict(os.environ, {"HOME": os.path.join(self.tmp, "home")}):
            got = sw.context_of(KARNAK)
        self.assertEqual(got["tokens"], 200305)
        self.assertGreater(got["at"], 0)

    def test_a_session_compacted_since_its_last_answer_reports_unknown_not_stale(self):
        d = os.path.join(self.tmp, "home2", ".claude", "projects", "p")
        os.makedirs(d)
        with open(os.path.join(d, MEMPHIS + ".jsonl"), "w") as fh:
            fh.write(json.dumps({"type": "assistant", "timestamp": "2026-10-20T08:00:00.000Z", "message": {
                "usage": {"input_tokens": 1, "cache_read_input_tokens": 540000, "cache_creation_input_tokens": 0}}}) + "\n")
            fh.write(json.dumps({"type": "system", "subtype": "compact_boundary",
                                 "timestamp": "2026-10-20T10:19:50.000Z"}) + "\n")
        with mock.patch.dict(os.environ, {"HOME": os.path.join(self.tmp, "home2")}):
            got = sw.context_of(MEMPHIS)
        self.assertTrue(got["compacted"])
        self.assertIsNone(got["tokens"])
        cli = FakeCli(self.rows(**{MEMPHIS: "idle"}))
        self.assertEqual(self.run_pass(cli, lambda sid: got), [], "never compacted twice")

    def test_a_heavy_idle_team_with_a_warm_cache_is_compacted(self):
        cli = FakeCli(self.rows(**{KARNAK: "idle"}))
        out = self.run_pass(cli, self.ctx(260_000, 10))
        self.assertEqual([(o["action"], o["team"]) for o in out], [("compact-started", "karnak")])
        self.assertEqual([c[0] for c in cli.calls], ["stop", "resume"])
        self.assertTrue(cli.calls[1][2].startswith("/compact Keep only what is needed"))
        self.assertTrue(sw.compacting(KARNAK, self.now), "busy while it runs")

    def test_a_working_team_is_never_touched(self):
        cli = FakeCli(self.rows(**{KARNAK: "working"}))
        self.assertEqual(self.run_pass(cli, self.ctx(900_000, 1)), [])
        self.assertEqual(cli.calls, [])

    def test_light_sessions_and_a_cold_medium_one_are_left_alone(self):
        cli = FakeCli(self.rows(**{KARNAK: "idle", MEMPHIS: "idle"}))
        self.assertEqual(self.run_pass(cli, self.ctx(100_000, 5)), [], "light")
        self.assertEqual(self.run_pass(cli, self.ctx(250_000, 300)), [], "medium and cold: its next wake pays anyway")
        self.assertEqual(cli.calls, [])

    def test_a_huge_cold_session_is_still_shrunk(self):
        cli = FakeCli(self.rows(**{MEMPHIS: "idle"}))
        out = self.run_pass(cli, self.ctx(540_000, 300))
        self.assertEqual([o["team"] for o in out], ["memphis"])

    def test_the_orchestrator_is_never_compacted_from_here(self):
        cli = FakeCli(self.rows(**{ORCH: "idle"}))
        self.assertEqual(self.run_pass(cli, self.ctx(900_000, 1)), [])

    def test_a_team_with_an_open_dispatch_is_left_alone_and_a_compacted_one_waits_three_hours(self):
        did = store.new_id("conversation_dispatch")
        store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": KARNAK, "target_seat_id": "karnak",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "delivered", "delivery_status": "DELIVERED"}, rid=did)
        cli = FakeCli(self.rows(**{KARNAK: "idle"}))
        self.assertEqual(self.run_pass(cli, self.ctx(400_000, 5)), [], "open dispatch")
        store.update("conversation_dispatch", did, store.read("conversation_dispatch", did)["revision"],
                     {"status": "withdrawn", "withdrawn_at": store.now()})
        self.assertEqual(len(self.run_pass(cli, self.ctx(400_000, 5))), 1)
        self.now += sw.COMPACTING_SECONDS + 60
        cli2 = FakeCli(self.rows(**{KARNAK: "idle"}))
        self.assertEqual(self.run_pass(cli2, self.ctx(400_000, 5)), [], "compacted less than 3 hours ago")
        self.now += sw.COMPACT_EVERY
        self.assertEqual(len(self.run_pass(cli2, self.ctx(400_000, 5))), 1)

    def test_a_compacting_team_counts_as_busy_for_dispatches(self):
        cli = FakeCli(self.rows(**{KARNAK: "idle"}))
        self.run_pass(cli, self.ctx(400_000, 5))
        self.assertIn("compacting", cd.open_work_for(KARNAK, store))

    def test_compact_team_is_the_trackers_button_and_refuses_what_it_must(self):
        cli = FakeCli(self.rows(**{KARNAK: "idle", MEMPHIS: "working"}))
        self.assertIn("orchestrator compacts itself", sw.compact_team("orchestrator", state_store=store, cli=cli)["reason"])
        self.assertIn("middle of a turn", sw.compact_team("memphis", state_store=store, cli=cli)["reason"])
        self.assertEqual(sw.compact_team("karnak", state_store=store, cli=cli, now=self.now)["action"], "compact-started")
        self.assertEqual([c[0] for c in cli.calls], ["stop", "resume"])
        self.assertIn("compacting", sw.compact_team("karnak", state_store=store, cli=cli)["reason"],
                      "already running: refused, not stopped again")

    def test_a_failed_stop_clears_the_marker_and_reports(self):
        cli = FakeCli(self.rows(**{KARNAK: "idle"}))
        cli.wait_stopped = lambda *a, **k: False
        out = self.run_pass(cli, self.ctx(400_000, 5))
        self.assertEqual(out[0]["action"], "compact-failed")
        self.assertFalse(sw.compacting(KARNAK, self.now))


if __name__ == "__main__":
    unittest.main()
