#!/usr/bin/env python3
"""The watchdog: stalled work is resumed once, then flagged; failures and CEO
escalations are flagged; each alert is raised once and reaches an inline `wait`."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                              # noqa: E402
from agent.execution import codex_runtime as cr                      # noqa: E402
from agent.execution import conversation_dispatch as cd             # noqa: E402
from agent.execution import watchdog as wd                           # noqa: E402
from agent.execution.claude_cli import ClaudeCli                     # noqa: E402

TEAM = "0aaaaaaa-3333-7000-8000-00000000000a"
PUSH = "0bbbbbbb-3333-7000-8000-00000000000b"
INLINE = "0ccccccc-3333-7000-8000-00000000000c"
HOME = "/stable/home"


class Completed:
    def __init__(self, stdout=""):
        self.stdout, self.stderr, self.returncode = stdout, "", 0


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("karnak", "claude", TEAM, HOME, "ceo")
        for t, mode in ((PUSH, "push"), (INLINE, "inline")):
            store.create("codex_conversation", {"thread_id": t, "runtime_id": cr.DAEMON_RUNTIME_ID,
                                                "registered_by": "ceo", "status": "active",
                                                "reply_mode": mode}, rid=t)
        self.launched, self.resumed = [], []
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches:
            p.start()
        self.later = time.time() + cd.STALL_SECONDS + 5

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dispatch(self, origin, status="delivered"):
        did = store.new_id("conversation_dispatch")
        return store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "codex", "origin_thread_id": origin,
            "target_provider": "claude", "target_session_id": TEAM, "target_seat_id": "karnak",
            "delivery_id": did, "capability_sha256": store.capability_sha256("c"),
            "prompt_ref": "/x", "status": status, "delivery_status": None, "outcome": None,
            "result_ref": None, "result_sha256": None, "reported_session_id": None,
            "attested_delivery_id": None, "outcome_at": None, "result_event_id": None,
            "error": "resume failed: limit" if status == "delivery_failed" else None}, rid=did)

    def cli(self, state):
        return ClaudeCli(runner=lambda argv, **kw: Completed(json.dumps(
            [{"sessionId": TEAM, "id": TEAM[:8], "state": state}])))

    def resume(self, did, state_store):
        self.resumed.append(did)
        store.record_session_delivery(did + "-resume1", {
            "dispatch_id": did, "work_item_id": None, "seat_id": "karnak", "provider": "claude",
            "session_id": TEAM, "status": "DELIVERED", "stopped_before_resume": "NO",
            "resumed_same_sid": "YES", "session_count_before": 1, "session_count_after": 1,
            "delivered_at": store.now()})
        return {"status": "resumed"}

    def tick(self, state="idle"):
        return wd.tick(state_store=store, cli=self.cli(state), launcher=self.launched.append,
                       resume=self.resume, now=self.later)

    def test_stalled_work_is_resumed_once_then_flagged_once_in_the_push_conversation(self):
        d = self.dispatch(PUSH)
        self.tick()
        self.assertEqual(self.resumed, [d["dispatch_id"]], "first: recover silently")
        self.assertEqual(self.launched, [])
        self.tick()
        self.assertEqual(self.launched, [PUSH], "second: the CEO's conversation is told")
        ev = [e for e in store.read_all("codex_turn_event") if e["event_kind"] == "alert"]
        self.assertEqual(len(ev), 1)
        with open(ev[0]["text_ref"], encoding="utf-8") as fh:
            self.assertIn("THEBES_ALERT stalled", fh.read())
        self.tick()
        self.assertEqual(self.launched, [PUSH], "once, not every minute")
        self.assertEqual(self.resumed, [d["dispatch_id"]])

    def test_a_working_session_is_left_alone(self):
        self.dispatch(PUSH)
        self.assertEqual(self.tick("working"), [])
        self.assertEqual((self.resumed, self.launched), ([], []))

    def test_inline_wait_returns_stopped_the_moment_the_watchdog_flags(self):
        d = self.dispatch(INLINE)
        self.tick(); self.tick()
        self.assertEqual(self.launched, [], "nothing is pushed into an inline thread")
        out = cd.wait_for_result(d["dispatch_id"], 1, state_store=store, sleep=lambda s: None)
        self.assertEqual((out["status"], out["alert"]["kind"]), ("stopped", "stalled"))

    def test_old_failures_are_not_alerted(self):
        """Live first pass flooded the CEO with a day of historical alerts."""
        self.dispatch(PUSH, status="delivery_failed")
        done = wd.tick(state_store=store, cli=self.cli("working"), launcher=self.launched.append,
                       resume=self.resume, now=time.time() + wd.ALERT_WINDOW_SECONDS + 60)
        self.assertEqual((done, self.launched), ([], []))

    def test_a_failed_delivery_and_a_ceo_escalation_are_flagged(self):
        f = self.dispatch(PUSH, status="delivery_failed")
        o = self.dispatch(PUSH)
        store.create("decision_request", {
            "decision_request_id": store.new_id("decision_request"),
            "origin_dispatch_id": o["dispatch_id"], "origin_thread_id": PUSH,
            "origin_outcome": "decision_required", "asker_seat_id": "karnak",
            "asker_session_id": TEAM, "question_ref": "/q", "route": "escalate",
            "capability_sha256": store.capability_sha256("x"), "status": "escalated",
            "escalation_reason": "ceo-only:production"})
        done = wd.tick(state_store=store, cli=self.cli("working"), launcher=self.launched.append,
                       resume=self.resume, now=time.time())
        kinds = sorted(a["action"] for a in done)
        self.assertEqual(kinds, ["alerted-delivery-failed", "alerted-needs-ceo"])
        self.assertEqual(store.read("conversation_dispatch", f["dispatch_id"])["watchdog_alert"]["kind"],
                         "delivery-failed")
        self.assertEqual(wd.tick(state_store=store, cli=self.cli("working"),
                                 launcher=self.launched.append, resume=self.resume,
                                 now=time.time()), [], "each alert once")
        self.assertEqual([e for e in validate.check(store.RUNTIME)
                          if any(k in e for k in ("conversation", "codex", "decision"))], [])


if __name__ == "__main__":
    unittest.main()
