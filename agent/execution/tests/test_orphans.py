#!/usr/bin/env python3
"""D-047: a working-column ticket with no team on it is found by the liveness sweep, not by luck."""
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store                                         # noqa: E402
from agent.execution import orphans                                   # noqa: E402

NOW = 1_800_000_000
OLD = "2026-01-01T00:00:00.000+0000"


def fresh():
    return time.strftime("%Y-%m-%dT%H:%M:%S.000+0000", time.gmtime(NOW - 120))


def issue(key="KAN-1", status="Development", updated=OLD):
    return {"key": key, "status": status, "updated": updated}


def disp(key, status, n=1, seat="karnak", outcome=None):
    return {"dispatch_id": "d%d" % n, "jira_key": key, "status": status, "target_seat_id": seat,
            "created_at": "2026-01-01T00:0%d:00Z" % n, "outcome": outcome}


class FakeJira:
    def __init__(self, issues):
        self.issues = issues

    def search_issues(self, jql, fields=None, limit=50, **kw):
        return self.issues


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def read_all(self, kind):
        return self.rows if kind == "conversation_dispatch" else []


class ClassifyTest(unittest.TestCase):
    def state(self, iss, dispatches, items=()):
        return orphans.classify(iss, dispatches, list(items), NOW)

    def test_open_dispatch_is_ok(self):
        r = self.state(issue(), [disp("KAN-1", "delivered")])
        self.assertEqual((r["state"], r["team"]), ("ok", "karnak"))

    def test_no_dispatch_after_grace_is_orphan(self):
        self.assertEqual(self.state(issue(), [])["state"], "orphan")

    def test_recent_jira_move_is_ok(self):
        self.assertEqual(self.state(issue(updated=fresh()), [])["state"], "ok")

    def test_dead_dispatches_are_dead_ends_with_the_reason(self):
        for status in ("blocked", "failed", "delivery_failed", "withdrawn"):
            r = self.state(issue(), [disp("KAN-1", status, outcome="no branch")])
            self.assertEqual(r["state"], "dead-end", status)
            self.assertIn(status, r["why"])

    def test_only_the_last_dispatch_counts(self):
        r = self.state(issue(), [disp("KAN-1", "blocked", 1), disp("KAN-1", "completed", 2)])
        self.assertEqual(r["state"], "orphan")
        r = self.state(issue(), [disp("KAN-1", "completed", 1), disp("KAN-1", "blocked", 2)])
        self.assertEqual(r["state"], "dead-end")

    def test_a_question_is_waiting_human_not_a_dead_end(self):
        r = self.state(issue(), [disp("KAN-1", "decision_required")])
        self.assertEqual(r["state"], "waiting-human")

    def test_other_tickets_dispatches_do_not_count(self):
        self.assertEqual(self.state(issue(), [disp("KAN-2", "delivered")])["state"], "orphan")

    def test_unclaimed_review_item_waits_for_a_judge(self):
        from agent.execution import review_queue
        real = review_queue.holder
        review_queue.holder = lambda item_id: None
        try:
            r = self.state(issue(status="Self-review"), [], [{"item_id": "i1", "ticket": "KAN-1"}])
        finally:
            review_queue.holder = real
        self.assertEqual(r["state"], "waiting-judge")


class ScanTest(unittest.TestCase):
    def test_scan_joins_jira_and_dispatches(self):
        jira = FakeJira([issue("KAN-1"), issue("KAN-2")])
        st = FakeStore([disp("KAN-2", "delivered")])
        rows = {r["key"]: r["state"] for r in orphans.scan(state_store=st, jira=jira, now=NOW)}
        self.assertEqual(rows, {"KAN-1": "orphan", "KAN-2": "ok"})


class RescueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = store.RUNTIME
        store.RUNTIME = self.tmp

    def tearDown(self):
        store.RUNTIME = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rescues_are_counted_and_capped(self):
        row = {"key": "KAN-1", "state": "dead-end", "jira": "Development"}
        self.assertFalse(orphans.exhausted(row))
        for _ in range(orphans.MAX_RESCUES):
            orphans.note_rescue("KAN-1", NOW)
        self.assertEqual(orphans.rescue_state("KAN-1")["n"], orphans.MAX_RESCUES)
        self.assertTrue(orphans.exhausted(row))

    def test_a_review_column_is_never_re_sent_to_a_dev_team(self):
        row = {"key": "KAN-9", "state": "orphan", "jira": "Self-review"}
        self.assertTrue(orphans.exhausted(row))

    def test_ok_tickets_are_never_exhausted(self):
        self.assertFalse(orphans.exhausted({"key": "KAN-1", "state": "ok", "jira": "Development"}))


if __name__ == "__main__":
    unittest.main()
