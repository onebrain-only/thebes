#!/usr/bin/env python3
"""Jira follows a team dispatch (D-040), and the PO's Ready command.

A fake Jira only. A temp runtime never reaches the real board even without the
fake: jira_sync refuses a runtime that is not the canonical workspace's.
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

from agent.state import store, validate, ready                       # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution import jira_sync                                # noqa: E402

ORCH = "0eeeeeee-4444-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-4444-7000-8000-00000000000a"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


def brief_for(key, team_branch="none"):
    """The smallest brief a ticket dispatch is allowed to carry (D-041)."""
    return ("Work on %s.\n\nGOAL: do it\nBRANCH: %s\nDECISIONS MADE: none\nCHECKS:\n"
            "C1 | judge | it looks right | a screenshot\n" % (key, team_branch))


class FakeJira:
    TRANSITIONS = {"10008": "2", "10046": "8", "10043": "5", "10049": "12",
                   "10044": "6", "10045": "7", "10009": "3", "10047": "9",
                   "10007": "41"}
    BY_ID = {v: k for k, v in TRANSITIONS.items()}

    def __init__(self, status="10008", fail=False):
        self.status, self.fail = {}, fail
        self.default = status
        self.comments, self.moves = [], []

    def get_issue(self, key):
        if self.fail:
            raise RuntimeError("Jira did not answer")
        return {"key": key, "status_id": self.status.get(key, self.default),
                "status": "x"}

    def get_transitions(self, key):
        return [{"id": t, "to_status_id": s} for s, t in self.TRANSITIONS.items()]

    def transition_issue(self, key, tid):
        self.moves.append((key, self.BY_ID[tid]))
        self.status[key] = self.BY_ID[tid]

    def add_comment(self, key, body):
        self.comments.append((key, body))
        return {"id": "1"}


class JiraSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        self.jira = FakeJira()
        self.launched = []
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        # Route every sync through the fake (the temp runtime would otherwise skip it).
        real = jira_sync._client
        self.patches.append(mock.patch.object(
            jira_sync, "_client", lambda jira, state_store: real(jira or self.jira, state_store)))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dispatch(self, prompt, **kw):
        if "ticket" not in kw:
            import re
            m = re.search(r"KAN-\d+", prompt)
            kw["ticket"] = m.group(0) if m else None
        out = cd.dispatch(prompt, KARNAK, env={"CLAUDE_CODE_SESSION_ID": ORCH},
                          state_store=store, detach=True,
                          launcher=lambda did, cap: self.launched.append((did, cap)), **kw)
        did, cap = self.launched[-1]
        rec = store.read("conversation_dispatch", did)
        rec = store.update("conversation_dispatch", did, rec["revision"],
                           {"status": "delivered", "delivery_status": "DELIVERED"})
        store.record_session_delivery(did, {
            "dispatch_id": did, "work_item_id": None, "seat_id": "karnak", "provider": "claude",
            "session_id": KARNAK, "status": "DELIVERED", "stopped_before_resume": "YES",
            "resumed_same_sid": "YES", "session_count_before": 1, "session_count_after": 1,
            "delivered_at": store.now()})
        jira_sync.on_start(rec, state_store=store)
        return out, did, cap

    def submit(self, did, cap, outcome, text):
        return cd.submit(did, outcome, text, env={"CLAUDE_CODE_SESSION_ID": KARNAK,
                                                  cd.CAPABILITY_ENV: cap}, state_store=store,
                         decision_router=lambda r, state_store: {"route": "escalate"},
                         verify_launcher=lambda d: None)

    def clean(self):
        return [e for e in validate.check(store.RUNTIME)
                if any(k in e for k in ("task", "conversation", "decision"))]

    # -- which ticket ------------------------------------------------------------
    def test_the_ticket_is_only_ever_named_never_inferred_from_a_mention(self):
        self.assertEqual(jira_sync.ticket_for("x", "KAN-12"), ("KAN-12", "explicit"))
        key, why = jira_sync.ticket_for("Summarize KAN-12 in one line.")
        self.assertIsNone(key)
        self.assertIn("pass --ticket", why)
        self.assertEqual(jira_sync.ticket_for("count the Dart files")[0], None)
        with self.assertRaises(ValueError):
            jira_sync.ticket_for("x", "kan 12")

    # -- the loop ------------------------------------------------------------------
    def test_start_moves_to_the_lane_and_completed_moves_to_review_with_comments(self):
        out, did, cap = self.dispatch(brief_for("KAN-50"), lane_capability="frontend")
        self.assertEqual(out["jira_key"], "KAN-50")
        self.assertEqual(self.jira.moves, [("KAN-50", "10046")])
        self.assertIn("team Karnak started", self.jira.comments[0][1])
        self.submit(did, cap, "completed", "Done: widget + 3 tests, analyze clean.")
        self.assertEqual(self.jira.moves[-1], ("KAN-50", "10044"), "untracked → Self-review")
        self.assertIn("reported completed", self.jira.comments[-1][1])
        self.assertIn("widget + 3 tests", self.jira.comments[-1][1])
        sync = store.read("conversation_dispatch", did)["jira_sync"]
        self.assertEqual((sync["start"]["status"], sync["finish"]["status"]), ("ok", "ok"))
        self.assertEqual(self.clean(), [])

    def test_an_acceptance_ruling_that_says_accepted_closes_the_ticket(self):
        """Malfunction #18: the ticket stayed in Self-review although the PO accepted it."""
        self.jira.status["KAN-60"] = "10044"
        out = jira_sync.on_accepted("KAN-60", "ACCEPTED - every criterion met.", state_store=store)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(self.jira.moves[-1], ("KAN-60", "10007"))
        self.jira.moves.clear()
        self.assertIsNone(jira_sync.on_accepted("KAN-60", "REJECTED - C2 fails.", state_store=store))
        self.assertIsNone(jira_sync.on_accepted("KAN-60", "Not accepted yet", state_store=store))
        self.assertEqual(self.jira.moves, [])

    def test_a_tracked_ticket_uses_its_own_capability_and_policy_route(self):
        t = store.admit_task("KAN-60", "app", "10008", "backend", "po", "po: api")
        t = store.set_work_profile("KAN-60", t["revision"], "po", "po: two widgets",
                                   required_capability="backend", work_effort=2)
        prof = dict(t["execution_profile"], validation_route="peer")
        store.update("task", "KAN-60", t["revision"], {"execution_profile": prof})
        _, did, cap = self.dispatch(brief_for("KAN-60"))
        self.assertEqual(self.jira.moves, [("KAN-60", "10043")])
        self.assertEqual(store.read("task", "KAN-60")["lifecycle"]["jira_status_name"],
                         "Back-end", "Persistent State observed what Jira says")
        self.submit(did, cap, "completed", "ok")
        self.assertEqual(self.jira.moves[-1], ("KAN-60", "10045"), "policy route peer")

    def test_failed_comments_without_moving(self):
        _, did, cap = self.dispatch(brief_for("KAN-70"), lane_capability="frontend")
        self.submit(did, cap, "failed", "flutter test red: 2 failures")
        self.assertEqual(self.jira.moves, [("KAN-70", "10046")], "no review move")
        self.assertIn("stopped — failed", self.jira.comments[-1][1])

    def test_no_lane_known_means_comment_only(self):
        _, did, _ = self.dispatch(brief_for("KAN-80"))
        self.assertIsNone(store.read("conversation_dispatch", did)["jira_capability"],
                          "live 2026-10-03: the dispatch secret was stored as the lane")
        self.assertEqual(self.jira.moves, [])
        self.assertIn("started", self.jira.comments[0][1])
        self.assertIn("--capability", store.read("conversation_dispatch", did)
                      ["jira_sync"]["start"]["reason"])

    def test_a_jira_failure_never_blocks_the_work_and_alerts_the_origin(self):
        self.jira.fail = True
        _, did, cap = self.dispatch(brief_for("KAN-90"), lane_capability="frontend")
        rec = store.read("conversation_dispatch", did)
        self.assertEqual(rec["jira_sync"]["start"]["status"], "failed")
        self.assertEqual(rec["watchdog_alert"]["kind"], "jira-sync-failed")
        out = self.submit(did, cap, "completed", "ok")
        self.assertEqual(out["status"], "recorded", "the report still lands")

    def test_a_dropped_connection_is_retried_and_a_failed_start_is_tried_again_later(self):
        class Flaky(FakeJira):
            drops = 2

            def get_issue(self, key):
                if Flaky.drops:
                    Flaky.drops -= 1
                    raise ConnectionResetError("reset by peer")
                return FakeJira.get_issue(self, key)
        self.jira = Flaky()
        with mock.patch.object(jira_sync.time if hasattr(jira_sync, "time") else __import__("time"),
                               "sleep", lambda s: None):
            _, did, cap = self.dispatch(brief_for("KAN-95"), lane_capability="frontend")
        self.assertEqual(self.jira.moves, [("KAN-95", "10046")], "two resets, then it worked")
        rec = store.read("conversation_dispatch", did)
        self.assertEqual(rec["jira_sync"]["start"]["status"], "ok")
        # a start that failed outright is not considered done
        self.assertFalse(jira_sync._done({"jira_sync": {"start": {"status": "failed"}}}, "start"))
        self.assertTrue(jira_sync._done({"jira_sync": {"start": {"status": "ok"}}}, "start"))

    def test_a_dispatch_without_a_ticket_touches_nothing(self):
        _, did, cap = self.dispatch("count the Dart files")
        self.submit(did, cap, "completed", "728")
        self.assertEqual((self.jira.moves, self.jira.comments), ([], []))

    def test_a_temp_runtime_never_reaches_the_real_board(self):
        self.patches[-1].stop()
        self.patches.pop()
        self.assertIsNone(jira_sync._client(None, store))

    # -- the PO's Ready command ------------------------------------------------------
    def test_ready_admits_records_effort_moves_to_ready_and_lists_what_remains(self):
        self.jira.default = "10004"                         # To Do
        out = ready.set_ready("KAN-99", "frontend", 2, "po: one screen, pattern in repo",
                              project="app", move_ready=True, jira=self.jira)
        self.assertTrue(out["admitted"])
        self.assertEqual((out["required_capability"], out["work_effort"], out["lifecycle"]),
                         ("frontend", 2, "Ready"))
        self.assertEqual(out["moved_to"], "Ready")
        self.assertIn("surfaces-unassessed", out["unclaimable_reasons"],
                      "the PO never invents paths; the executing seat assesses them")
        self.assertNotIn("missing-work-effort", out["unclaimable_reasons"])
        self.assertEqual(self.clean(), [])

    def test_ready_can_admit_a_ticket_already_in_an_execution_lane(self):
        self.jira.default = "10046"                          # already Front-end in Jira
        out = ready.set_ready("KAN-96", "frontend", 1, "po: small", project="app",
                              jira=self.jira)
        self.assertEqual((out["lifecycle"], out["work_effort"]), ("Front-end", 1))
        self.assertEqual(self.clean(), [])

    def test_only_the_po_states_effort_and_a_new_ticket_needs_a_project(self):
        with self.assertRaises(store.StateError):
            ready.set_ready("KAN-98", "frontend", 1, "basis", jira=self.jira)
        t = store.admit_task("KAN-97", "app", "10008", "frontend", "po", "po: ui")
        with self.assertRaises(store.StateError):
            store.set_work_profile("KAN-97", t["revision"], "worker:frontend-1", "b",
                                   work_effort=1)


if __name__ == "__main__":
    unittest.main()
