#!/usr/bin/env python3
"""Phase-3 proof of the CEO decision loop, end to end and deterministic.

Two halves, because they are two different claims:

  1. The LISTENER half — a needs-input controller result becomes a durable
     WAITING_INPUT, a correlated decision enters, and the SAME workflow is
     resumed. Wrong work item, wrong invocation, stale reference, duplicate
     replay and already-terminal workflow are each refused.

  2. The CONTROLLER half — `controller.decide` records the approval through the
     EXISTING `store.record_execution_approval` writer, with the seat and the
     provider session derived from the canonical continuation preparation rather
     than from the caller, and then hands off to the EXISTING `resume`. No new
     approval architecture, and no Phase-2 binding weakened.

Nothing here touches Persistent State, Jira, Supabase, a provider or a Product
repository.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _isolation import IsolatedRuntime                     # noqa: E402
from agent.listener import contract, dispatch, server, store  # noqa: E402
import agent.controller as controller                      # noqa: E402


WORK_ITEM = "KAN-900"
INVOCATION = "invocation-1"
SESSION = "claude-session-1"


def execute_envelope(key="w-1", work_item_id=WORK_ITEM):
    return contract.normalize({
        "schema_version": 1, "intent_type": contract.EXECUTE_WORK_ITEM,
        "source": "listener-cli", "actor": "ceo", "idempotency_key": key,
        "correlation_id": "corr-" + key,
        "payload": {"work_item_id": work_item_id}})


def decision_envelope(responds_to, key="d-1", work_item_id=WORK_ITEM,
                      invocation=INVOCATION, permission="Bash"):
    return contract.normalize({
        "schema_version": 1, "intent_type": contract.DECISION_RESPONSE,
        "source": "listener-cli", "actor": "backend-1", "idempotency_key": key,
        "correlation_id": "corr-w-1", "responds_to": responds_to,
        "payload": {"work_item_id": work_item_id, "decision": "approve",
                    "original_invocation_id": invocation, "permission": permission,
                    "approval_scope": "resume the same execution past the boundary"}})


NEEDS_INPUT = {"transport": "returned", "exit_code": 1,
               "result": {"work_item_id": WORK_ITEM, "execution_status": "needs_input",
                          "invocation_id": INVOCATION,
                          "needs_input": "denied {'tool_name': 'Bash'}",
                          "continuation_prepared": "continuation-1"}}
RESUMED = {"transport": "returned", "exit_code": 0,
           "result": {"work_item_id": WORK_ITEM, "execution_status": "completed",
                      "continuation_status": "executed",
                      "decision_status": "recorded",
                      "invocation_id": "invocation-2",
                      "lifecycle": "done"}}


class Controller:
    def __init__(self, *results):
        self.calls, self.results = [], list(results)

    def __call__(self, intent, timeout=None):
        self.calls.append(dispatch.argv_for(intent))
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


def waiting_intent(controller_transport):
    record, _ = store.accept(execute_envelope())
    dispatch.dispatch(record["intent_id"], runner=controller_transport)
    return record


class ListenerDecisionLoop(unittest.TestCase):
    def test_same_workflow_is_resumed_through_the_canonical_decision_entry(self):
        with IsolatedRuntime():
            transport = Controller(NEEDS_INPUT, RESUMED)
            original = waiting_intent(transport)
            waiting = store.read_intent(original["intent_id"])
            self.assertEqual(store.WAITING_INPUT, waiting["delivery_state"])
            # The bounded decision request the accountable employee reads back.
            result = store.read_result(original["intent_id"])
            self.assertEqual(INVOCATION,
                             result["controller_result"]["result"]["invocation_id"])

            answer = decision_envelope(original["intent_id"])
            self.assertEqual(original["intent_id"],
                             store.assert_decision_reference(answer)["intent_id"])
            decision, created = store.accept(answer)
            self.assertTrue(created)
            settled = dispatch.dispatch(decision["intent_id"], runner=transport)

            self.assertEqual(store.COMPLETED, settled["delivery_state"])
            # It went to `decide`, naming the SAME work item and the SAME
            # invocation the workflow actually stopped at.
            self.assertEqual("decide", transport.calls[1][3])
            self.assertEqual(WORK_ITEM, transport.calls[1][4])
            self.assertEqual(INVOCATION,
                             transport.calls[1][transport.calls[1].index("--invocation") + 1])
            # The terminal result reaches the ORIGINAL correlation.
            self.assertEqual("corr-w-1", settled["result"]["correlation_id"])
            self.assertEqual("done",
                             settled["result"]["controller_result"]["result"]["lifecycle"])
            # And the original intent is untouched: resuming is not re-running.
            self.assertEqual(store.WAITING_INPUT,
                             store.read_intent(original["intent_id"])["delivery_state"])
            self.assertEqual(1, store.read_intent(original["intent_id"])["dispatch_attempts"])

    def test_a_decision_cannot_start_unrelated_product_work(self):
        with IsolatedRuntime():
            transport = Controller(NEEDS_INPUT, RESUMED)
            original = waiting_intent(transport)
            answer = decision_envelope(original["intent_id"])
            store.accept(answer)
            dispatch.dispatch(answer["intent_id"], runner=transport)
            # Every controller invocation this loop produced is either the
            # original execute or a decide against the SAME work item. There is
            # no path here that names another ticket.
            for call in transport.calls:
                self.assertIn(call[3], ("execute", "decide"))
                self.assertEqual(WORK_ITEM, call[4])

    def test_each_refusal_reason_is_distinct_and_blocks_the_decision(self):
        cases = (
            ("unknown-decision-reference",
             lambda original: decision_envelope("intent-nonexistent")),
            ("decision-work-item-mismatch",
             lambda original: decision_envelope(original["intent_id"],
                                                work_item_id="KAN-901")),
            ("decision-invocation-mismatch",
             lambda original: decision_envelope(original["intent_id"],
                                                invocation="invocation-stale")),
        )
        for reason, build in cases:
            with IsolatedRuntime():
                transport = Controller(NEEDS_INPUT, RESUMED)
                original = waiting_intent(transport)
                answer = build(original)
                with self.assertRaises(contract.IntentRejected) as caught:
                    store.assert_decision_reference(answer)
                self.assertEqual(reason, caught.exception.reason)
                # Refused at intake means the Controller was never invoked again.
                self.assertEqual(1, len(transport.calls))

    def test_a_refused_decision_is_recorded_rejected_and_never_dispatched(self):
        with IsolatedRuntime():
            transport = Controller(NEEDS_INPUT, RESUMED)
            original = waiting_intent(transport)
            answer = decision_envelope(original["intent_id"], invocation="invocation-stale")
            code, body = server.intake(answer)
            self.assertEqual(400, code)
            self.assertEqual("decision-invocation-mismatch", body["reason"])
            self.assertEqual(store.REJECTED,
                             store.read_intent(answer["intent_id"])["delivery_state"])
            self.assertEqual([], store.pending())
            self.assertEqual(1, len(transport.calls))

    def test_duplicate_decision_replay_does_not_resume_twice(self):
        with IsolatedRuntime():
            transport = Controller(NEEDS_INPUT, RESUMED)
            original = waiting_intent(transport)
            answer = decision_envelope(original["intent_id"])
            store.accept(answer)
            dispatch.dispatch(answer["intent_id"], runner=transport)
            # The identical decision, submitted again.
            replay = decision_envelope(original["intent_id"])
            code, body = server.intake(replay)
            self.assertEqual(200, code)
            self.assertTrue(body["duplicate"])
            self.assertIsNone(dispatch.dispatch(replay["intent_id"], runner=transport))
            self.assertEqual(2, len(transport.calls))       # execute + one decide

    def test_a_decision_against_an_already_terminal_workflow_is_refused(self):
        with IsolatedRuntime():
            transport = Controller(NEEDS_INPUT, RESUMED)
            original = waiting_intent(transport)
            answer = decision_envelope(original["intent_id"])
            store.accept(answer)
            dispatch.dispatch(answer["intent_id"], runner=transport)
            # The original intent settled WAITING_INPUT and stays there; a
            # SECOND decision against a now-answered boundary still refers to a
            # waiting intent, so the canonical refusal is the Controller's.
            # What the Listener refuses is a decision against a COMPLETED one.
            later = decision_envelope(answer["intent_id"], key="d-2")
            with self.assertRaises(contract.IntentRejected) as caught:
                store.assert_decision_reference(later)
            self.assertEqual("decision-target-not-waiting", caught.exception.reason)


class StubState:
    """Only what `controller.decide` is allowed to touch."""

    def __init__(self, mode="PRODUCT_EXECUTION", preparation=None):
        self.mode = mode
        self.preparation = preparation
        self.approvals = []

    def current_operating_mode(self):
        return self.mode

    def read_execution_continuation_preparation(self, invocation_id):
        if self.preparation and self.preparation["original_invocation_id"] == invocation_id:
            return self.preparation
        return None

    def record_execution_approval(self, **fields):
        self.approvals.append(fields)
        return dict(fields, execution_approval_id="approval-1")


PREPARATION = {"original_invocation_id": INVOCATION, "work_item_id": WORK_ITEM,
               "seat_id": "backend-1", "claude_session_id": SESSION,
               "authorization_ref": "CEO fixture"}


class ControllerDecision(unittest.TestCase):
    def test_decision_records_through_the_existing_approval_writer_then_resumes(self):
        state = StubState(preparation=PREPARATION)
        resumed = {}

        def resumer(work_item_id, **kwargs):
            resumed.update(work_item_id=work_item_id, kwargs=kwargs)
            return {"work_item_id": work_item_id, "execution_status": "completed",
                    "continuation_status": "executed"}

        result = controller.decide(WORK_ITEM, INVOCATION, "Bash",
                                   "resume past the boundary",
                                   approving_authority="backend-1",
                                   state_store=state, resumer=resumer)
        self.assertEqual(1, len(state.approvals))
        approval = state.approvals[0]
        # Seat and session are DERIVED from canonical state, never accepted
        # from the caller — a decision can answer a question, not redirect it.
        self.assertEqual("backend-1", approval["seat_id"])
        self.assertEqual(SESSION, approval["claude_session_id"])
        self.assertEqual("backend-1", approval["approving_authority"])
        self.assertEqual("task_local_technical", approval["decision_class"])
        self.assertEqual("Bash", approval["permission"])
        self.assertEqual(WORK_ITEM, resumed["work_item_id"])
        self.assertEqual("recorded", result["decision_status"])
        self.assertEqual("approval-1", result["execution_approval_id"])

    def test_decision_is_refused_in_system_maintenance_before_anything_is_written(self):
        state = StubState(mode="SYSTEM_MAINTENANCE", preparation=PREPARATION)
        result = controller.decide(WORK_ITEM, INVOCATION, "Bash", "scope",
                                   state_store=state,
                                   resumer=lambda *a, **k: self.fail("resumed"))
        self.assertEqual("system-maintenance-active", result["blocker"])
        self.assertEqual("not-recorded", result["decision_status"])
        self.assertEqual([], state.approvals)

    def test_decision_for_a_foreign_work_item_is_refused(self):
        state = StubState(preparation=PREPARATION)
        result = controller.decide("KAN-901", INVOCATION, "Bash", "scope",
                                   state_store=state,
                                   resumer=lambda *a, **k: self.fail("resumed"))
        self.assertEqual("decision-work-item-mismatch", result["blocker"])
        self.assertEqual([], state.approvals)

    def test_decision_without_a_prepared_continuation_is_refused(self):
        state = StubState(preparation=None)
        result = controller.decide(WORK_ITEM, INVOCATION, "Bash", "scope",
                                   state_store=state,
                                   resumer=lambda *a, **k: self.fail("resumed"))
        self.assertEqual("no-prepared-continuation", result["blocker"])
        self.assertEqual([], state.approvals)

    def test_the_approval_writers_own_refusal_is_surfaced_not_swallowed(self):
        from agent.state.store import StateError

        class Refusing(StubState):
            def record_execution_approval(self, **fields):
                raise StateError("execution approval permission does not match "
                                 "original boundary")

        state = Refusing(preparation=PREPARATION)
        result = controller.decide(WORK_ITEM, INVOCATION, "Write", "scope",
                                   state_store=state,
                                   resumer=lambda *a, **k: self.fail("resumed"))
        self.assertIn("does not match original boundary", result["blocker"])
        self.assertEqual("not-recorded", result["decision_status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
