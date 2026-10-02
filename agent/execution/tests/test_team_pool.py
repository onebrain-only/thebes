#!/usr/bin/env python3
"""Teams (execution islands) and the shared, time-exclusive seat pool.

Fakes only. A team is a role_session whose id is a declared team; a dispatch
to a team carries the team block; a team reserves a seat per dispatch and
another team is refused with free alternatives; reservations release when
the dispatch settles.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate, teams                       # noqa: E402
from agent.execution import codex_runtime as cr                      # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution import team_pool as tp                          # noqa: E402

KARNAK = "0aaaaaaa-1111-7000-8000-00000000000a"
LUXOR = "0bbbbbbb-1111-7000-8000-00000000000b"
SEAT_SID = "0ccccccc-1111-7000-8000-00000000000c"
THREAD = "0ddddddd-1111-7000-8000-00000000000d"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class TeamPoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        store.bind_role_session("frontend-1", "claude", SEAT_SID, HOME, "ceo")
        store.create("codex_runtime", {"runtime_id": cr.RUNTIME_ID, "status": "running",
                                       "socket_path": cr.socket_path(store)}, rid=cr.RUNTIME_ID)
        store.create("codex_conversation", {"thread_id": THREAD, "runtime_id": cr.RUNTIME_ID,
                                            "registered_by": "ceo", "status": "active"}, rid=THREAD)
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_dispatch(self, team_sid, team_id):
        """A delivered dispatch to a team, written the way dispatch() writes it."""
        did = store.new_id("conversation_dispatch")
        rec = store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "codex", "origin_thread_id": THREAD,
            "target_provider": "claude", "target_session_id": team_sid,
            "target_seat_id": team_id, "delivery_id": did,
            "capability_sha256": store.capability_sha256("cap-" + did),
            "prompt_ref": "/x", "status": "delivered", "delivery_status": "DELIVERED",
            "outcome": None, "result_ref": None, "result_sha256": None,
            "reported_session_id": None, "attested_delivery_id": None, "outcome_at": None,
            "result_event_id": None, "error": None}, rid=did)
        store.record_session_delivery(did, {
            "dispatch_id": did, "work_item_id": None, "seat_id": team_id, "provider": "claude",
            "session_id": team_sid, "status": "DELIVERED", "stopped_before_resume": "YES",
            "resumed_same_sid": "YES", "session_count_before": 1, "session_count_after": 1,
            "delivered_at": store.now()})
        return rec

    def clean(self):
        return [e for e in validate.check(store.RUNTIME)
                if any(k in e for k in ("team", "reserv", "conversation", "role session"))]

    def test_registry_names_five_temples_and_a_team_binds_like_a_session(self):
        self.assertEqual([t["display_name"] for t in sorted(teams.delivery_teams().values(),
                                                            key=lambda t: t["number"])],
                         ["Karnak", "Habu", "Luxor", "Ramesseum", "Deir el-Bahari"])
        self.assertTrue(teams.is_orchestrator("orchestrator"))
        self.assertFalse(teams.is_orchestrator("karnak"))
        self.assertNotIn("orchestrator", teams.delivery_teams(), "Codex never sends WORK to it")
        self.assertEqual(store.active_role_session("karnak")["session_id"], KARNAK)
        with self.assertRaises(store.StateError):
            store.bind_role_session("thebes", "claude", KARNAK, HOME, "ceo")
        self.assertEqual(self.clean(), [])

    def test_a_dispatch_to_a_team_carries_the_team_block_and_a_seat_dispatch_does_not(self):
        d = self.open_dispatch(KARNAK, "karnak")
        text = cd.build_envelope(d, "cap")
        self.assertIn("team: you are team Karnak (karnak)", text)
        self.assertIn("team_pool reserve <seat> --dispatch %s" % d["dispatch_id"], text)
        self.assertIn("report_shape: one report", text)
        seat = dict(d, target_seat_id="frontend-1", target_session_id=SEAT_SID)
        self.assertNotIn("team:", cd.build_envelope(seat, "cap"))

    def test_identity_is_the_session_and_a_seat_session_cannot_reserve(self):
        d = self.open_dispatch(KARNAK, "karnak")
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("frontend-1", d["dispatch_id"], env={"CLAUDE_CODE_SESSION_ID": SEAT_SID},
                       state_store=store)
        self.assertEqual(ctx.exception.code, "not-a-team-session")
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("frontend-1", d["dispatch_id"], env={}, state_store=store)
        self.assertEqual(ctx.exception.code, "team-identity-missing")

    def test_one_team_at_a_time_per_seat_with_free_alternatives_named(self):
        dk = self.open_dispatch(KARNAK, "karnak")
        dl = self.open_dispatch(LUXOR, "luxor")
        k = tp.reserve("frontend-1", dk["dispatch_id"], env={"CLAUDE_CODE_SESSION_ID": KARNAK},
                       state_store=store)
        self.assertEqual(k["status"], "reserved")
        again = tp.reserve("frontend-1", dk["dispatch_id"],
                           env={"CLAUDE_CODE_SESSION_ID": KARNAK}, state_store=store)
        self.assertEqual(again["status"], "already-reserved")
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("frontend-1", dl["dispatch_id"], env={"CLAUDE_CODE_SESSION_ID": LUXOR},
                       state_store=store)
        self.assertEqual(ctx.exception.code, "seat-held")
        self.assertIn("frontend-2", str(ctx.exception), "a free seat of the same capability")
        self.assertNotIn("backend-1", str(ctx.exception))
        # Luxor cannot reserve against Karnak's dispatch either.
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("frontend-2", dk["dispatch_id"], env={"CLAUDE_CODE_SESSION_ID": LUXOR},
                       state_store=store)
        self.assertEqual(ctx.exception.code, "not-your-dispatch")
        self.assertEqual(self.clean(), [])

    def test_reservations_release_when_the_dispatch_settles_and_can_release_early(self):
        d = self.open_dispatch(KARNAK, "karnak")
        env = {"CLAUDE_CODE_SESSION_ID": KARNAK}
        tp.reserve("frontend-1", d["dispatch_id"], env=env, state_store=store)
        tp.reserve("backend-1", d["dispatch_id"], env=env, state_store=store)
        self.assertEqual(tp.release("backend-1", d["dispatch_id"], env=env,
                                    state_store=store)["status"], "released")
        self.assertIsNone(store.active_seat_reservation("backend-1"))
        self.assertIsNotNone(store.active_seat_reservation("frontend-1"))
        store.record_conversation_result(d["dispatch_id"], "completed", KARNAK,
                                         "cap-" + d["dispatch_id"], "one report")
        self.assertIsNone(store.active_seat_reservation("frontend-1"))
        kept = [r for r in store.read_all("seat_reservation") if r["status"] == "released"]
        self.assertEqual(sorted(r["release_reason"] for r in kept),
                         ["dispatch-completed", "team-released"], "released, never deleted")
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("frontend-1", d["dispatch_id"], env=env, state_store=store)
        self.assertEqual(ctx.exception.code, "dispatch-not-open")
        self.assertEqual(self.clean(), [])

    def test_a_hold_whose_work_has_settled_is_reaped_on_the_next_reserve(self):
        """Live 2026-10-02: po stayed held after its work settled; a CEO order was refused."""
        dk = self.open_dispatch(KARNAK, "karnak")
        tp.reserve("po", dk["dispatch_id"], env={"CLAUDE_CODE_SESSION_ID": KARNAK},
                   state_store=store)
        # settle the dispatch WITHOUT the normal release (the leak)
        cur = store.read("conversation_dispatch", dk["dispatch_id"])
        store.update("conversation_dispatch", dk["dispatch_id"], cur["revision"],
                     {"status": "withdrawn", "withdrawn_at": store.now()})
        self.assertIsNotNone(store.active_seat_reservation("po"), "the leak, reproduced")
        dl = self.open_dispatch(LUXOR, "luxor")
        out = tp.reserve("po", dl["dispatch_id"], env={"CLAUDE_CODE_SESSION_ID": LUXOR},
                         state_store=store)
        self.assertEqual(out["status"], "reserved", "the stale hold is reaped, not obeyed")
        reaped = [r for r in store.read_all("seat_reservation")
                  if r.get("release_reason") == "stale-work-settled"]
        self.assertEqual(len(reaped), 1)
        self.assertEqual(self.clean(), [])

    def test_status_lists_direct_seat_sessions_for_direct_orders(self):
        seats = {s["seat_id"]: s for s in tp.status(store)["direct_seats"]}
        self.assertEqual(seats["frontend-1"]["session_id"], SEAT_SID)
        self.assertNotIn("karnak", seats, "teams are not direct seats")

    def test_bootstrap_lists_teams_with_busy_state_and_free_teams_are_derived(self):
        text = cr.bootstrap_prompt(THREAD, store)
        self.assertIn("team 1 Karnak (karnak): %s" % KARNAK, text)
        self.assertIn("team 3 Luxor (luxor): %s" % LUXOR, text)
        self.assertNotIn("Habu (habu): ", text, "an unbound team is not offered")
        self.assertIn("- frontend-1: %s" % SEAT_SID, text)
        self.open_dispatch(KARNAK, "karnak")
        self.assertIn("Karnak (karnak): %s — BUSY now" % KARNAK, cr.bootstrap_prompt(THREAD, store))
        self.assertEqual([t["team_id"] for t in tp.free_teams(store)], ["luxor"])


if __name__ == "__main__":
    unittest.main()
