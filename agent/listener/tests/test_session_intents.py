#!/usr/bin/env python3
"""The two persistent-session intent families at the Listener boundary.

Pure contract and argv checks: nothing here starts a Listener or a Controller.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _isolation import IsolatedRuntime                      # noqa: E402, F401 (ROOT on sys.path)
from agent.execution.brief import CONTROL_PLANE_TOKENS      # noqa: E402
from agent.listener import contract, dispatch, store        # noqa: E402

SID = "55555555-5555-4555-8555-555555555555"


def submit(intent_type, payload, key="k-1"):
    return contract.normalize({
        "schema_version": 1, "intent_type": intent_type, "source": "listener-cli",
        "actor": "ceo", "idempotency_key": key, "correlation_id": "c-" + key,
        "payload": payload})


def outcome_payload(**changes):
    payload = {"work_item_id": "KAN-900", "dispatch_id": "dispatch-abc_1.2",
               "outcome": "completed", "summary": "implemented and committed",
               "session_id": SID, "reference": "abc1234", "delivery_id": "dispatch-abc_1.2"}
    payload.update(changes)
    return {key: value for key, value in payload.items() if value is not None}


class ContractTests(unittest.TestCase):
    def test_prepare_takes_only_a_work_item(self):
        intent = submit(contract.PREPARE_SESSION_DISPATCH, {"work_item_id": "KAN-900"})
        self.assertEqual({"work_item_id": "KAN-900"}, intent["payload"])
        with self.assertRaises(contract.IntentRejected) as refused:
            submit(contract.PREPARE_SESSION_DISPATCH,
                   {"work_item_id": "KAN-900", "session_id": SID})
        self.assertEqual("unknown-field", refused.exception.reason)

    def test_record_accepts_the_full_payload(self):
        intent = submit(contract.RECORD_SESSION_OUTCOME, outcome_payload())
        self.assertEqual(outcome_payload(), intent["payload"])

    def test_every_outcome_in_the_vocabulary_is_accepted(self):
        for outcome in contract.SESSION_OUTCOMES:
            session = None if outcome == contract.UNREACHABLE else SID
            intent = submit(contract.RECORD_SESSION_OUTCOME,
                            outcome_payload(outcome=outcome, session_id=session), key=outcome)
            self.assertEqual(outcome, intent["payload"]["outcome"])

    def test_session_id_is_required_unless_the_worker_was_unreachable(self):
        with self.assertRaises(contract.IntentRejected) as refused:
            submit(contract.RECORD_SESSION_OUTCOME, outcome_payload(session_id=None))
        self.assertEqual("missing-field", refused.exception.reason)
        intent = submit(contract.RECORD_SESSION_OUTCOME,
                        outcome_payload(outcome="worker_unreachable", session_id=None))
        self.assertNotIn("session_id", intent["payload"])

    def test_refusals(self):
        cases = (
            ("unknown outcome", outcome_payload(outcome="done"), "unsupported-outcome"),
            ("a session name is not an id", outcome_payload(session_id="developer"),
             "invalid-field"),
            ("control characters in the summary",
             outcome_payload(summary="ok\x1b[2Jcleared"), "invalid-field"),
            ("unbounded summary", outcome_payload(summary="x" * (contract.MAX_TEXT + 1)),
             "field-too-long"),
            ("a shell-shaped dispatch id", outcome_payload(dispatch_id="d; rm -rf /"),
             "invalid-field"),
            ("a shell-shaped reference", outcome_payload(reference="$(whoami)"),
             "invalid-field"),
            ("an unknown field", outcome_payload(seat_id="backend-1"), "unknown-field"),
            ("a missing summary", outcome_payload(summary=None), "missing-field"),
        )
        for name, payload, reason in cases:
            with self.subTest(name):
                with self.assertRaises(contract.IntentRejected) as refused:
                    submit(contract.RECORD_SESSION_OUTCOME, payload)
                self.assertEqual(reason, refused.exception.reason)


class TransportTests(unittest.TestCase):
    def test_prepare_maps_to_dispatch_session_as_an_argv_list(self):
        argv = dispatch.argv_for(submit(contract.PREPARE_SESSION_DISPATCH,
                                        {"work_item_id": "KAN-900"}))
        self.assertIsInstance(argv, list)
        self.assertEqual(["-m", "agent.controller", "dispatch-session", "KAN-900"], argv[1:])

    def test_record_maps_to_session_outcome_with_every_supplied_field(self):
        argv = dispatch.argv_for(submit(contract.RECORD_SESSION_OUTCOME, outcome_payload()))
        self.assertEqual(["-m", "agent.controller", "session-outcome", "KAN-900",
                          "--dispatch", "dispatch-abc_1.2", "--outcome", "completed",
                          "--summary", "implemented and committed",
                          "--session-id", SID, "--reference", "abc1234",
                          "--delivery-id", "dispatch-abc_1.2"], argv[1:])
        unreachable = dispatch.argv_for(submit(
            contract.RECORD_SESSION_OUTCOME,
            outcome_payload(outcome="worker_unreachable", session_id=None, reference=None)))
        self.assertNotIn("--session-id", unreachable)
        self.assertNotIn("--reference", unreachable)

    def test_new_intent_families_are_control_plane_tokens(self):
        for name in (contract.PREPARE_SESSION_DISPATCH, contract.RECORD_SESSION_OUTCOME):
            self.assertIn(name, CONTROL_PLANE_TOKENS)

    def test_a_prepared_packet_is_a_completed_delivery_not_needs_input(self):
        prepared = {"transport": "returned", "exit_code": 0,
                    "result": {"work_item_id": "KAN-900", "dispatch_status": "dispatched",
                               "execution_status": "not-started",
                               "ceo_input_required": False,
                               "dispatch_packet": {"dispatch_id": "dispatch-x"}}}
        self.assertEqual((store.COMPLETED, "controller-answered"), dispatch.classify(prepared))
        refused = {"transport": "returned", "exit_code": 1,
                   "result": {"work_item_id": "KAN-900", "blocker": "no-bound-session",
                              "execution_status": "not-started"}}
        self.assertEqual(store.COMPLETED, dispatch.classify(refused)[0])


if __name__ == "__main__":
    unittest.main()
