#!/usr/bin/env python3
"""Phase-3 Listener contract and durable-store proof.

Deterministic and fully isolated: a temporary runtime root, no Controller, no
Persistent State writes, no Jira, no Supabase, no Product repository.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _isolation import IsolatedRuntime                    # noqa: E402
from agent.listener import contract, store                # noqa: E402


def envelope(**overrides):
    base = {"schema_version": 1, "intent_type": contract.EXECUTE_WORK_ITEM,
            "source": "listener-cli", "actor": "ceo",
            "idempotency_key": "k-1", "correlation_id": "c-1",
            "payload": {"work_item_id": "KAN-183"}}
    base.update(overrides)
    return base


def decision(**overrides):
    base = {"schema_version": 1, "intent_type": contract.DECISION_RESPONSE,
            "source": "listener-cli", "actor": "ceo",
            "idempotency_key": "d-1", "correlation_id": "c-1",
            "responds_to": "intent-x",
            "payload": {"work_item_id": "KAN-900", "decision": "approve",
                        "original_invocation_id": "inv-1", "permission": "Bash",
                        "approval_scope": "run the one denied command"}}
    base.update(overrides)
    return base


class Contract(unittest.TestCase):
    def test_valid_intent_round_trips(self):
        normalized = contract.normalize(envelope())
        self.assertEqual(contract.EXECUTE_WORK_ITEM, normalized["intent_type"])
        self.assertEqual("KAN-183", normalized["payload"]["work_item_id"])
        restored = json.loads(json.dumps(normalized))
        self.assertEqual(normalized["intent_id"], restored["intent_id"])
        self.assertEqual(normalized["intent_id"], contract.intent_id(restored))

    def test_malformed_body_is_rejected(self):
        for raw in (b"{", b"[]", b"not json", b'"string"'):
            with self.assertRaises(contract.IntentRejected):
                contract.normalize(contract.parse_body(raw))

    def test_oversized_body_is_rejected_before_parsing(self):
        with self.assertRaises(contract.IntentRejected) as caught:
            contract.parse_body(b"x" * (contract.MAX_BODY_BYTES + 1))
        self.assertEqual("body-too-large", caught.exception.reason)

    def test_unknown_intent_type_is_rejected(self):
        with self.assertRaises(contract.IntentRejected) as caught:
            contract.normalize(envelope(intent_type="RUN_SHELL"))
        self.assertEqual("unknown-intent-type", caught.exception.reason)

    def test_unknown_fields_are_rejected_not_ignored(self):
        with self.assertRaises(contract.IntentRejected) as caught:
            contract.normalize(envelope(payload={"work_item_id": "KAN-1",
                                                 "command": "rm -rf /"}))
        self.assertEqual("unknown-field", caught.exception.reason)
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(dict(envelope(), provider="claude-code"))

    def test_no_field_can_carry_a_path_seat_or_provider(self):
        allowed = set(contract.PAYLOAD_FIELDS[contract.EXECUTE_WORK_ITEM][0])
        for forbidden in ("seat_id", "provider", "workspace", "worktree_path",
                          "validation_route", "capability", "command", "brief"):
            self.assertNotIn(forbidden, allowed)

    def test_work_item_id_must_look_like_a_jira_key(self):
        for bad in ("KAN 183", "kan-183", "KAN-183; rm -rf /", "../../etc/passwd", ""):
            with self.assertRaises(contract.IntentRejected):
                contract.normalize(envelope(payload={"work_item_id": bad}))

    def test_wildcard_permission_is_refused(self):
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(decision(payload=dict(
                decision()["payload"], permission="Bash*")))

    def test_decision_requires_a_reference(self):
        body = decision()
        body.pop("responds_to")
        with self.assertRaises(contract.IntentRejected) as caught:
            contract.normalize(body)
        self.assertEqual("invalid-field", caught.exception.reason)

    def test_identity_is_derived_from_the_callers_own_key(self):
        first = contract.normalize(envelope())
        second = contract.normalize(envelope(correlation_id="c-2"))
        self.assertEqual(first["intent_id"], second["intent_id"])
        other = contract.normalize(envelope(idempotency_key="k-2"))
        self.assertNotEqual(first["intent_id"], other["intent_id"])


class DurableStore(unittest.TestCase):
    def test_received_record_survives_a_new_store_view(self):
        with IsolatedRuntime() as runtime:
            record, created = store.accept(contract.normalize(envelope()))
            self.assertTrue(created)
            self.assertEqual(store.RECEIVED, record["delivery_state"])
            path = os.path.join(store.RUNTIME, "intents", record["intent_id"] + ".json")
            self.assertTrue(os.path.exists(path))
            survivors = runtime.simulate_restart()
            self.assertEqual([record["intent_id"]],
                             [rec["intent_id"] for rec in survivors])
            self.assertEqual(store.RECEIVED,
                             store.read_intent(record["intent_id"])["delivery_state"])

    def test_duplicate_key_returns_the_existing_canonical_intent(self):
        with IsolatedRuntime():
            first, created_first = store.accept(contract.normalize(envelope()))
            second, created_second = store.accept(contract.normalize(envelope()))
            self.assertTrue(created_first)
            self.assertFalse(created_second)
            self.assertEqual(first["intent_id"], second["intent_id"])
            self.assertEqual(first["received_at"], second["received_at"])
            self.assertEqual(1, len(store.read_intents()))

    def test_reused_key_with_different_content_is_refused(self):
        with IsolatedRuntime():
            store.accept(contract.normalize(envelope()))
            with self.assertRaises(store.ListenerStoreError):
                store.accept(contract.normalize(
                    envelope(payload={"work_item_id": "KAN-999"})))

    def test_duplicate_does_not_create_a_second_dispatch_eligibility(self):
        with IsolatedRuntime():
            record, _ = store.accept(contract.normalize(envelope()))
            store.accept(contract.normalize(envelope()))
            self.assertEqual(1, len(store.pending()))
            self.assertIsNotNone(store.begin_dispatch(record["intent_id"]))
            self.assertEqual([], store.pending())
            self.assertIsNone(store.begin_dispatch(record["intent_id"]))

    def test_result_persists_and_stays_queryable_after_restart(self):
        with IsolatedRuntime() as runtime:
            record, _ = store.accept(contract.normalize(envelope()))
            store.begin_dispatch(record["intent_id"])
            store.settle(record["intent_id"], store.COMPLETED,
                         {"transport": "returned", "result": {"blocker": "not-authorized"}},
                         "controller-answered")
            runtime.simulate_restart()
            result = store.read_result(record["intent_id"])
            self.assertEqual(store.COMPLETED, result["delivery_state"])
            self.assertEqual("not-authorized",
                             result["controller_result"]["result"]["blocker"])
            self.assertEqual("KAN-183", result["work_item_id"])
            self.assertEqual("c-1", result["correlation_id"])

    def test_terminal_intent_cannot_be_restarted_or_re_settled(self):
        with IsolatedRuntime():
            record, _ = store.accept(contract.normalize(envelope()))
            store.begin_dispatch(record["intent_id"])
            store.settle(record["intent_id"], store.COMPLETED, {"transport": "returned"})
            self.assertEqual([], store.pending())
            self.assertIsNone(store.begin_dispatch(record["intent_id"]))
            _, _, settled = store.settle(record["intent_id"], store.FAILED,
                                         {"transport": "timeout"})
            self.assertFalse(settled)
            self.assertEqual(store.COMPLETED,
                             store.read_intent(record["intent_id"])["delivery_state"])
            self.assertEqual(store.COMPLETED,
                             store.read_result(record["intent_id"])["delivery_state"])

    def test_interrupted_dispatch_is_recovered_without_re_dispatch(self):
        with IsolatedRuntime() as runtime:
            record, _ = store.accept(contract.normalize(envelope()))
            store.begin_dispatch(record["intent_id"])
            runtime.simulate_restart()
            self.assertEqual([record["intent_id"]], store.recover())
            recovered = store.read_intent(record["intent_id"])
            self.assertEqual(store.DISPATCHING, recovered["delivery_state"])
            self.assertEqual("dispatch-interrupted", recovered["recovery"])
            self.assertEqual([], store.pending())

    def test_a_crash_before_dispatch_leaves_the_intent_eligible(self):
        with IsolatedRuntime() as runtime:
            record, _ = store.accept(contract.normalize(envelope()))
            runtime.simulate_restart()
            self.assertEqual([], store.recover())
            self.assertEqual([record["intent_id"]],
                             [rec["intent_id"] for rec in store.pending()])


class DecisionCorrelation(unittest.TestCase):
    def _waiting(self, work_item_id="KAN-900", invocation_id="inv-1"):
        waiting, _ = store.accept(contract.normalize(envelope(
            idempotency_key="w-1", payload={"work_item_id": work_item_id})))
        store.begin_dispatch(waiting["intent_id"])
        store.settle(waiting["intent_id"], store.WAITING_INPUT,
                     {"transport": "returned",
                      "result": {"invocation_id": invocation_id,
                                 "execution_status": "needs_input",
                                 "needs_input": "denied tool 'Bash'"}},
                     "ceo-input-required")
        return waiting

    def test_decision_binds_to_the_waiting_workflow(self):
        with IsolatedRuntime():
            waiting = self._waiting()
            answer = contract.normalize(decision(responds_to=waiting["intent_id"]))
            self.assertEqual(waiting["intent_id"],
                             store.assert_decision_reference(answer)["intent_id"])

    def test_foreign_decision_reference_is_rejected(self):
        with IsolatedRuntime():
            self._waiting()
            answer = contract.normalize(decision(responds_to="intent-does-not-exist"))
            with self.assertRaises(contract.IntentRejected) as caught:
                store.assert_decision_reference(answer)
            self.assertEqual("unknown-decision-reference", caught.exception.reason)

    def test_decision_for_the_wrong_work_item_is_rejected(self):
        with IsolatedRuntime():
            waiting = self._waiting(work_item_id="KAN-900")
            answer = contract.normalize(decision(
                responds_to=waiting["intent_id"],
                payload=dict(decision()["payload"], work_item_id="KAN-901")))
            with self.assertRaises(contract.IntentRejected) as caught:
                store.assert_decision_reference(answer)
            self.assertEqual("decision-work-item-mismatch", caught.exception.reason)

    def test_decision_for_the_wrong_invocation_is_rejected(self):
        with IsolatedRuntime():
            waiting = self._waiting(invocation_id="inv-1")
            answer = contract.normalize(decision(
                responds_to=waiting["intent_id"],
                payload=dict(decision()["payload"], original_invocation_id="inv-99")))
            with self.assertRaises(contract.IntentRejected) as caught:
                store.assert_decision_reference(answer)
            self.assertEqual("decision-invocation-mismatch", caught.exception.reason)

    def test_decision_against_a_terminal_workflow_is_rejected(self):
        with IsolatedRuntime():
            done, _ = store.accept(contract.normalize(envelope(
                idempotency_key="t-1", payload={"work_item_id": "KAN-900"})))
            store.begin_dispatch(done["intent_id"])
            store.settle(done["intent_id"], store.COMPLETED, {"transport": "returned"})
            answer = contract.normalize(decision(responds_to=done["intent_id"]))
            with self.assertRaises(contract.IntentRejected) as caught:
                store.assert_decision_reference(answer)
            self.assertEqual("decision-target-not-waiting", caught.exception.reason)

    def test_duplicate_decision_response_is_idempotent(self):
        with IsolatedRuntime():
            waiting = self._waiting()
            answer = contract.normalize(decision(responds_to=waiting["intent_id"]))
            first, created_first = store.accept(answer)
            second, created_second = store.accept(
                contract.normalize(decision(responds_to=waiting["intent_id"])))
            self.assertTrue(created_first)
            self.assertFalse(created_second)
            self.assertEqual(first["intent_id"], second["intent_id"])
            self.assertEqual(1, len([rec for rec in store.read_intents()
                                     if rec["intent_type"] == contract.DECISION_RESPONSE]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
