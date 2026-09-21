#!/usr/bin/env python3
"""VALIDATE_WORK_ITEM — dispatching a review that is ALREADY open. (T-091)

Same isolation as `test_validation_dispatch`: the real store on a temp runtime,
a synthetic git repository, a Jira double and provider doubles. What is proved
here is the complement of the execution-time path: an item that po opened and
the CEO named an owner for can be dispatched to that owner with no execution in
this process, and every state that is NOT exactly that is refused with its own
reason rather than repaired.
"""

import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                       # noqa: E402

from agent.controller import validate                              # noqa: E402
from agent.controller.validation import (                          # noqa: E402
    FAIL, PASS, VALIDATION_ALREADY_SETTLED, VALIDATION_CONTEXT_REFUSED,
    VALIDATION_FAILED, VALIDATION_PASSED, VALIDATION_WAITING_FOR_REVIEWER,
    ValidationRefused, run_open_review,
)
from agent.controller.tests.test_validation_dispatch import (      # noqa: E402
    PEER_REVIEW, SEATS, Jira, ValidationTestCase, Validator, make_task,
)


def open_peer_review(work_item_id="KAN-950"):
    """A PEER item whose execution this process never saw: no owner, no
    evidence, opened by po, waiting for a reviewer."""
    task = make_task(work_item_id, status_id=PEER_REVIEW, owner=None)
    return store.open_review_context(work_item_id, task["revision"], opened_by="po")


class OpenReviewDispatch(ValidationTestCase):
    def test_a_named_owner_is_dispatched_and_the_verdict_is_recorded(self):
        task = open_peer_review()
        self.assertIsNone(task["review_context"]["review_owner"])
        task = store.resolve_review_owner("KAN-950", task["revision"], "backend-2",
                                          "ceo named backend-2; executor unknown")
        validator = Validator(PASS)
        evidence = run_open_review("KAN-950", task, self.realize("backend-2", "KAN-950"),
                                   store, Jira(PEER_REVIEW), (validator,))
        self.assertEqual(VALIDATION_PASSED, evidence["outcome"])
        self.assertEqual("backend-2", evidence["reviewer"])
        self.assertEqual(1, len(validator.requests))
        request = validator.requests[0]
        self.assertEqual("validation", request.execution_kind.value)
        self.assertIn("open review context review:KAN-950:peer:1", request.objective)
        settled = store.read("task", "KAN-950")["review_context"]
        self.assertEqual("pass", settled["review_result"])
        self.assertEqual("backend-2", settled["review_owner"])

    def test_a_fail_on_an_evidence_less_item_records_the_verdict_and_surfaces(self):
        # The canonical PEER-fail transfer records `previous_owner` from the ONE
        # evidenced executor. An item routed up under T-090 has none, so the
        # transfer is refused by the store's own invariant. The verdict is still
        # durably recorded first; what is surfaced is that the hand-over could
        # not be completed — never a silently passed or silently dropped review.
        task = open_peer_review("KAN-951")
        task = store.resolve_review_owner("KAN-951", task["revision"], "backend-2",
                                          "ceo named backend-2")
        with self.assertRaises(store.StateError) as caught:
            run_open_review("KAN-951", task, self.realize("backend-2", "KAN-951"),
                            store, Jira(PEER_REVIEW), (Validator(FAIL),))
        self.assertIn("previous_owner", str(caught.exception))
        after = store.read("task", "KAN-951")["review_context"]
        self.assertEqual(FAIL, after["review_result"])
        self.assertEqual("backend-2", after["review_owner"])

    def test_a_fail_with_one_evidenced_executor_transfers_to_the_reviewer(self):
        task = make_task("KAN-955", status_id=PEER_REVIEW, owner="backend-1")
        task = store.release("KAN-955", "backend-1", task["revision"],
                             "execution receipt for KAN-955")
        task = store.open_review_context("KAN-955", task["revision"], opened_by="po")
        task = store.resolve_review_owner("KAN-955", task["revision"], "backend-2",
                                          "ceo named backend-2; executor backend-1")
        evidence = run_open_review("KAN-955", task, self.realize("backend-2", "KAN-955"),
                                   store, Jira(PEER_REVIEW), (Validator(FAIL),))
        self.assertEqual(VALIDATION_FAILED, evidence["outcome"])
        after = store.read("task", "KAN-955")
        self.assertEqual("backend-2", (after.get("ownership") or {}).get("seat_id"))
        self.assertEqual("backend-1", after["review_context"]["previous_owner"])

    def test_waiting_with_no_owner_is_refused_never_filled(self):
        task = open_peer_review("KAN-952")
        with self.assertRaises(ValidationRefused) as caught:
            run_open_review("KAN-952", task, self.realize("backend-2", "KAN-952"),
                            store, Jira(PEER_REVIEW), (Validator(PASS),))
        self.assertEqual(VALIDATION_WAITING_FOR_REVIEWER, caught.exception.outcome)
        self.assertIsNone(store.read("task", "KAN-952")["review_context"]["review_owner"])

    def test_no_context_and_a_settled_context_are_both_refused(self):
        bare = make_task("KAN-953", status_id=PEER_REVIEW, owner=None)
        with self.assertRaises(ValidationRefused) as caught:
            run_open_review("KAN-953", bare, self.realize("backend-2", "KAN-953"),
                            store, Jira(PEER_REVIEW), (Validator(PASS),))
        self.assertEqual(VALIDATION_CONTEXT_REFUSED, caught.exception.outcome)

        task = open_peer_review("KAN-954")
        task = store.resolve_review_owner("KAN-954", task["revision"], "backend-2", "ceo")
        run_open_review("KAN-954", task, self.realize("backend-2", "KAN-954"),
                        store, Jira(PEER_REVIEW), (Validator(PASS),))
        settled = store.read("task", "KAN-954")
        with self.assertRaises(ValidationRefused) as caught:
            run_open_review("KAN-954", settled, self.realize("backend-2", "KAN-954"),
                            store, Jira(PEER_REVIEW), (Validator(PASS),))
        self.assertEqual(VALIDATION_ALREADY_SETTLED, caught.exception.outcome)


class ValidateEntryPoint(ValidationTestCase):
    """`agent.controller.validate` — the process-callable half the Listener runs."""

    def test_maintenance_mode_refuses_before_reading_anything(self):
        mode = store.read("operating_mode", "current")
        store.set_operating_mode("SYSTEM_MAINTENANCE", "ceo", "fixture",
                                 expected_revision=mode["revision"])
        result = validate("KAN-960", state_store=store, jira_client=Jira(PEER_REVIEW),
                          providers=(Validator(PASS),))
        self.assertEqual("system-maintenance-active", result["blocker"])
        self.assertEqual("not-attempted", result["validation_status"])

    def test_an_item_not_in_review_is_refused(self):
        make_task("KAN-961")                          # Back-end, owned, not in review
        result = validate("KAN-961", state_store=store, jira_client=Jira(),
                          providers=(Validator(PASS),))
        self.assertEqual("not-in-review", result["blocker"])

    def test_a_waiting_review_reports_waiting_and_dispatches_nothing(self):
        open_peer_review("KAN-962")
        validator = Validator(PASS)
        result = validate("KAN-962", state_store=store, jira_client=Jira(PEER_REVIEW),
                          providers=(validator,))
        self.assertEqual(VALIDATION_WAITING_FOR_REVIEWER, result["validation_status"])
        self.assertEqual([], validator.requests)

    def test_a_stop_on_the_item_blocks_the_review(self):
        task = open_peer_review("KAN-963")
        store.resolve_review_owner("KAN-963", task["revision"], "backend-2", "ceo")
        stop = [{"kind": "stop", "target": "KAN-963", "cleared_at": None}]
        validator = Validator(PASS)
        result = validate("KAN-963", state_store=store, jira_client=Jira(PEER_REVIEW),
                          providers=(validator,), interventions=stop)
        self.assertEqual("task-stopped", result["blocker"])
        self.assertEqual([], validator.requests)


if __name__ == "__main__":
    unittest.main()
