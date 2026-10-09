#!/usr/bin/env python3
"""The desk's door into Jira (D-042). A fake Jira only."""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                              # noqa: E402
from agent.execution import intake                                   # noqa: E402

GOOD = """SUMMARY: Venues list shows the distance to each venue
TYPE: work
COMPONENT: Listings
CAPABILITY: frontend
ESTIMATE: 2h
BLOCKED BY: KAN-12

GOAL: show the distance on every venue card
BRANCH: alpha-<team>
ALLOWED PATHS: lib/features/venues/
FORBIDDEN: lib/core/, the database
DECISIONS MADE: kilometres with one decimal
IF BLOCKED: return decision_required with ONE question
CHECKS:
C1 | run | flutter test test/features/venues/venue_card_test.dart | exit 0

Acceptance criteria:
1. Every card shows the distance.
"""

ASK = """SUMMARY: How many active venues have no photo
TYPE: ask
CAPABILITY: analyst
ESTIMATE: 30m

GOAL: Answer: how many active venues have no photo
BRANCH: none
ALLOWED PATHS: none
FORBIDDEN: any write
DECISIONS MADE: none
IF BLOCKED: return decision_required with ONE question
CHECKS:
C1 | judge | the answer gives the count and the query | the team's report

Acceptance criteria:
1. A count and its query.
"""


class FakeJira:
    def __init__(self, open_issues=()):
        self.open_issues, self.created, self.links = list(open_issues), [], []

    def search_issues(self, jql, fields=None, limit=50, raw=False):
        return self.open_issues

    def create_issue(self, project, summary, description, **kw):
        key = "KAN-%d" % (900 + len(self.created))
        self.created.append(dict(kw, key=key, project=project, summary=summary,
                                 description=description))
        return key

    def link_issues(self, blocker, blocked):
        self.links.append((blocker, blocked))


class IntakeTests(unittest.TestCase):
    def test_a_good_work_ticket_lands_in_backlog_with_its_labels_component_and_estimate(self):
        j = FakeJira()
        out = intake.create(GOOD, jira=j)
        self.assertEqual((out["status"], out["where"]), ("created", "Backlog (To Do)"))
        c = j.created[0]
        self.assertEqual(c["labels"], ["intake", "cap:frontend"])
        self.assertEqual(c["components"], ["Listings"])
        self.assertEqual(c["original_estimate_seconds"], 7200)
        self.assertTrue(c["description"].startswith("GOAL:"), "the header is not in the ticket")
        self.assertEqual(j.links, [("KAN-12", "KAN-900")])

    def test_an_ask_needs_no_component_and_is_labelled_ask(self):
        j = FakeJira()
        intake.create(ASK, jira=j)
        self.assertEqual(j.created[0]["labels"], ["intake", "cap:analyst", "ask"])
        self.assertIsNone(j.created[0]["components"])

    def test_everything_wrong_is_reported_at_once_and_nothing_is_created(self):
        bad = GOOD.replace("COMPONENT: Listings", "COMPONENT: Venues") \
                  .replace("ESTIMATE: 2h", "ESTIMATE: soon") \
                  .replace("flutter test", "bash run") \
                  .replace("Acceptance criteria:", "Notes:")
        j = FakeJira()
        with self.assertRaises(intake.IntakeError) as ctx:
            intake.create(bad, jira=j)
        text = " ".join(ctx.exception.problems)
        for part in ("COMPONENT", "ESTIMATE", "C1 command refused", "Acceptance criteria"):
            self.assertIn(part, text)
        self.assertEqual(j.created, [])

    def test_code_work_needs_a_component_because_it_picks_the_owner(self):
        with self.assertRaises(intake.IntakeError) as ctx:
            intake.create(GOOD.replace("COMPONENT: Listings\n", ""), jira=FakeJira())
        self.assertIn("decides the owning team", " ".join(ctx.exception.problems))

    def test_a_likely_duplicate_is_refused_unless_forced(self):
        j = FakeJira([{"key": "KAN-77", "summary": "Venues list shows distance to each venue",
                       "status": "Ready"}])
        with self.assertRaises(intake.IntakeError) as ctx:
            intake.create(GOOD, jira=j)
        self.assertIn("KAN-77", ctx.exception.problems[0])
        self.assertEqual(intake.create(GOOD, jira=j, force_new=True)["status"], "created")

    def test_at_most_five_per_call(self):
        with self.assertRaises(intake.IntakeError):
            intake.create_many([GOOD] * 6, jira=FakeJira())

    def test_estimates(self):
        self.assertEqual(intake.estimate_seconds("30m"), 1800)
        self.assertEqual(intake.estimate_seconds("1.5h"), 5400)
        self.assertEqual(intake.estimate_seconds("1d"), 21600)
        self.assertIsNone(intake.estimate_seconds("2 weeks"))

    def test_status_is_read_only_and_names_who_works_on_what(self):
        tmp = tempfile.mkdtemp()
        old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        try:
            j = FakeJira([{"key": "KAN-5", "summary": "x", "status": "Ready",
                           "labels": ["needs-ceo"]}])
            out = intake.status(jira=j, state_store=store)
            self.assertEqual(out["board"], {"Ready": ["KAN-5 x"]})
            self.assertEqual(out["needs_ceo"], ["KAN-5"])
            self.assertEqual({t["team"] for t in out["teams"]} >= {"Karnak", "Memphis"}, True)
            self.assertEqual(j.created, [], "status writes nothing")
        finally:
            store.RUNTIME, store.LOCKS, validate.RUNTIME = old
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
