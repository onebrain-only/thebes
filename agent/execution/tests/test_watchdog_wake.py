#!/usr/bin/env python3
"""The watchdog wakes an idle orchestrator and reports a blocked session (D-042). Fakes only."""
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
from agent.execution import watchdog as wd                           # noqa: E402

ORCH = "0eeeeeee-8888-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-8888-7000-8000-00000000000a"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class FakeCli:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def agents(self, include_completed=False):
        return self.rows

    @staticmethod
    def find_by_sid(rows, sid):
        return next((r for r in rows if r.get("sessionId") == sid), None)

    def stop(self, short):
        self.calls.append(("stop", short))

    def wait_stopped(self, sid, timeout, pid=None):
        self.calls.append(("wait", sid))
        return True

    def bg_resume(self, sid, prompt, cwd):
        self.calls.append(("resume", sid, prompt, cwd))
        return "ok"


class WakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches:
            p.start()
        self.req = store.create("priority_request", {
            "reasons": [{"kind": "new-in-backlog", "keys": ["KAN-1"]}], "status": "open",
            "backlog_signature": "KAN-1@u", "collected_at": None})
        self.t0 = time.time()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rows(self, state="done"):
        return [{"sessionId": ORCH, "state": state, "pid": 4242}]

    def wake(self, cli, minutes, waiter=False):
        return wd.wake_orchestrator(state_store=store, cli=cli, waiter=lambda: waiter,
                                    now=self.t0 + minutes * 60)

    def test_an_idle_orchestrator_with_nobody_listening_is_woken_after_five_minutes(self):
        cli = FakeCli(self.rows())
        self.assertIsNone(self.wake(cli, 2), "not yet")
        out = self.wake(cli, 6)
        self.assertEqual(out["action"], "woke-orchestrator")
        self.assertEqual([c[0] for c in cli.calls], ["stop", "wait", "resume"])
        self.assertIn("THEBES_WAKE", cli.calls[-1][2])
        self.assertIn("priority", cli.calls[-1][2])
        self.assertEqual(cli.calls[-1][1], ORCH, "the SAME session id")

    def test_a_running_waiter_or_a_turn_in_progress_is_never_disturbed(self):
        cli = FakeCli(self.rows())
        self.assertIsNone(self.wake(cli, 30, waiter=True))
        working = FakeCli(self.rows("working"))
        self.assertIsNone(self.wake(working, 30))
        self.assertEqual(cli.calls + working.calls, [])

    def test_at_most_one_wake_per_fifteen_minutes(self):
        cli = FakeCli(self.rows())
        self.assertIsNotNone(self.wake(cli, 6))
        self.assertIsNone(self.wake(cli, 10), "too soon after the last wake")
        self.assertIsNotNone(self.wake(cli, 25))

    def test_nothing_waiting_or_session_not_running_means_no_wake(self):
        store.update("priority_request", self.req["priority_request_id"], self.req["revision"],
                     {"status": "collected"})
        self.assertIsNone(self.wake(FakeCli(self.rows()), 60), "nothing waits")
        store.update("priority_request", self.req["priority_request_id"], 2, {"status": "open"})
        self.assertIsNone(self.wake(FakeCli([]), 60), "not running: thebes-up's job")

    def test_a_blocked_team_is_reported_with_what_it_waits_for_and_not_resumed(self):
        did = "cdispatch-" + "1" * 8 + "-0000-4000-8000-" + "2" * 12
        store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": KARNAK, "target_seat_id": "karnak",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "delivered", "delivery_status": "DELIVERED", "outcome": None}, rid=did)
        projects = os.path.join(self.tmp, "projects", "p")
        os.makedirs(projects)
        with open(os.path.join(projects, KARNAK + ".jsonl"), "w") as fh:
            fh.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "mcp__claude_ai_Supabase__apply_migration",
                 "input": {"name": "venues_listing_match"}}]}}) + "\n")
        self.assertEqual(wd.pending_tool(KARNAK, os.path.join(self.tmp, "projects"))[0],
                         "mcp__claude_ai_Supabase__apply_migration")
        resumed = []
        rows = [{"sessionId": KARNAK, "state": "blocked", "pid": 1}]
        with mock.patch.object(wd, "pending_tool", lambda sid, projects=None: (
                "mcp__claude_ai_Supabase__apply_migration", "{}")):
            out = wd.tick(state_store=store, cli=FakeCli(rows), now=time.time() + 400,
                          resume=lambda *a, **k: resumed.append(a), launcher=_refuse)
        blocked = [d for d in out if d.get("action") == "alerted-blocked"]
        self.assertEqual(len(blocked), 1)
        self.assertIn("apply_migration", blocked[0]["waiting_for"])
        self.assertEqual(resumed, [], "a permission prompt cannot be answered by a resume")
        alert = store.read("conversation_dispatch", did)["watchdog_alert"]
        self.assertEqual(alert["kind"], "blocked-on-permission")
        self.assertIn("claude attach", alert["text"])


if __name__ == "__main__":
    unittest.main()
