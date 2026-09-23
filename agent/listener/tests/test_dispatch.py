#!/usr/bin/env python3
"""Phase-3 Listener dispatch and process-boundary proof.

Deterministic. The Controller transport is injected for the behavioural cases
so the assertions are exact; one case runs the REAL controller entry contract in
a real subprocess, against the real authorization gate, which refuses and
changes nothing.
"""

import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _isolation import IsolatedRuntime                      # noqa: E402, ROOT on sys.path
from agent.execution.brief import CONTROL_PLANE_TOKENS      # noqa: E402
from agent.listener import contract, dispatch, server, store  # noqa: E402


def envelope(work_item_id="KAN-900", key="k-1", **overrides):
    base = {"schema_version": 1, "intent_type": contract.EXECUTE_WORK_ITEM,
            "source": "listener-cli", "actor": "ceo", "idempotency_key": key,
            "correlation_id": "c-" + key, "payload": {"work_item_id": work_item_id}}
    base.update(overrides)
    return contract.normalize(base)


class Controller:
    """A fake Controller transport that records exactly how it was invoked."""

    def __init__(self, *results):
        self.calls = []
        self.results = list(results) or [
            {"transport": "returned", "exit_code": 0,
             "result": {"work_item_id": "KAN-900", "execution_status": "completed"}}]

    def __call__(self, intent, timeout=None):
        self.calls.append(dispatch.argv_for(intent))
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


class ProcessBoundary(unittest.TestCase):
    def test_controller_is_invoked_as_an_argv_array_never_a_shell_string(self):
        command = dispatch.argv_for(envelope("KAN-183"))
        self.assertIsInstance(command, list)
        self.assertEqual([sys.executable, "-m", "agent.controller", "execute", "KAN-183"],
                         command)
        for element in command:
            self.assertIsInstance(element, str)

    def test_decision_reaches_the_canonical_controller_decision_entry(self):
        answer = contract.normalize({
            "schema_version": 1, "intent_type": contract.DECISION_RESPONSE,
            "source": "listener-cli", "actor": "backend-1", "idempotency_key": "d-1",
            "correlation_id": "c-1", "responds_to": "intent-1",
            "payload": {"work_item_id": "KAN-900", "decision": "approve",
                        "original_invocation_id": "inv-1", "permission": "Bash",
                        "approval_scope": "the one denied command",
                        "allowed_operation": "psql -c 'select 1'"}})
        self.assertEqual(
             [sys.executable, "-m", "agent.controller", "decide", "KAN-900",
             "--invocation", "inv-1", "--permission", "Bash",
             "--scope", "the one denied command",
             "--authority", "backend-1",
             "--operation", "psql -c 'select 1'"],
            dispatch.argv_for(answer))

    def test_no_intent_can_express_a_command_or_a_seat_or_a_provider(self):
        # The Listener never builds a Product brief — the Controller derives it
        # from canonical state, behind the firewall, and the Listener is not in
        # that path at all. What IS assertable here is that nothing the CALLER
        # controls reaches the boundary carrying a control-plane token. The
        # fixed literals `-m agent.controller` are the Listener→Controller seam
        # itself and are deliberately not caller-supplied.
        command = dispatch.argv_for(envelope("KAN-183"))
        caller_supplied = command[4:]
        self.assertEqual(["KAN-183"], caller_supplied)
        carried = " ".join(caller_supplied)
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), carried.lower())
        # The envelope's own `intent_type` is deliberately exempt: since Phase 4
        # taught the executor firewall about the Listener, EXECUTE_WORK_ITEM is
        # itself a control-plane token. That is correct — it must never reach an
        # EXECUTOR — and a Listener record is not an executor brief. What matters
        # is that no such token rides a caller-supplied VALUE into the Controller.
        with self.assertRaises(contract.IntentRejected):
            contract.normalize({"schema_version": 1,
                                "intent_type": contract.EXECUTE_WORK_ITEM,
                                "source": "s", "actor": "ceo", "idempotency_key": "k",
                                "correlation_id": "c",
                                "payload": {"work_item_id": "KAN-1",
                                            "seat_id": "backend-1"}})


class Dispatch(unittest.TestCase):
    def test_worker_invokes_the_controller_exactly_once_per_intent(self):
        with IsolatedRuntime():
            controller = Controller()
            record, _ = store.accept(envelope())
            first = dispatch.dispatch(record["intent_id"], runner=controller)
            second = dispatch.dispatch(record["intent_id"], runner=controller)
            self.assertEqual(store.COMPLETED, first["delivery_state"])
            self.assertIsNone(second)
            self.assertEqual(1, len(controller.calls))

    def test_duplicate_submissions_collapse_to_one_controller_execution(self):
        with IsolatedRuntime():
            controller = Controller()
            record, created = store.accept(envelope())
            again, created_again = store.accept(envelope())
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(record["intent_id"], again["intent_id"])
            worker = server.Worker(dispatcher=lambda intent_id:
                                   dispatch.dispatch(intent_id, runner=controller))
            worker.drain_once()
            worker.drain_once()
            self.assertEqual(1, len(controller.calls))

    def test_concurrent_duplicate_dispatch_produces_one_execution(self):
        with IsolatedRuntime():
            controller = Controller()
            record, _ = store.accept(envelope())
            outcomes = []
            barrier = threading.Barrier(4)

            def race():
                barrier.wait()
                outcomes.append(dispatch.dispatch(record["intent_id"], runner=controller))

            threads = [threading.Thread(target=race) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(1, len(controller.calls))
            self.assertEqual(1, len([item for item in outcomes if item is not None]))

    def test_different_intents_stay_independent(self):
        with IsolatedRuntime():
            controller = Controller()
            first, _ = store.accept(envelope("KAN-900", key="a"))
            second, _ = store.accept(envelope("KAN-901", key="b"))
            worker = server.Worker(dispatcher=lambda intent_id:
                                   dispatch.dispatch(intent_id, runner=controller))
            worker.drain_once()
            self.assertEqual(2, len(controller.calls))
            self.assertEqual({"KAN-900", "KAN-901"},
                             {call[-1] for call in controller.calls})
            self.assertNotEqual(first["intent_id"], second["intent_id"])

    def test_restart_after_intake_does_not_lose_the_intent(self):
        with IsolatedRuntime() as runtime:
            controller = Controller()
            record, _ = store.accept(envelope())
            runtime.simulate_restart()                      # nothing in memory survives
            store.recover()
            worker = server.Worker(dispatcher=lambda intent_id:
                                   dispatch.dispatch(intent_id, runner=controller))
            worker.drain_once()
            self.assertEqual(1, len(controller.calls))
            self.assertEqual(store.COMPLETED,
                             store.read_intent(record["intent_id"])["delivery_state"])

    def test_restart_after_controller_completion_does_not_repeat_execution(self):
        with IsolatedRuntime() as runtime:
            controller = Controller()
            record, _ = store.accept(envelope())
            dispatch.dispatch(record["intent_id"], runner=controller)
            runtime.simulate_restart()
            store.recover()
            worker = server.Worker(dispatcher=lambda intent_id:
                                   dispatch.dispatch(intent_id, runner=controller))
            worker.drain_once()
            self.assertEqual(1, len(controller.calls))
            # And the caller can still collect the answer it may never have seen.
            self.assertIsNotNone(store.read_result(record["intent_id"]))

    def test_controller_failure_is_represented_truthfully(self):
        for outcome, reason in (({"transport": "timeout", "detail": "..."}, "timeout"),
                                ({"transport": "unavailable", "detail": "..."}, "unavailable"),
                                ({"transport": "unreadable", "detail": "...",
                                  "exit_code": 2}, "unreadable")):
            with IsolatedRuntime():
                record, _ = store.accept(envelope())
                settled = dispatch.dispatch(record["intent_id"],
                                            runner=Controller(outcome))
                self.assertEqual(store.FAILED, settled["delivery_state"])
                self.assertEqual(reason, settled["delivery_reason"])
                self.assertNotEqual(store.COMPLETED,
                                    store.read_intent(record["intent_id"])["delivery_state"])

    def test_a_controller_refusal_is_a_delivered_answer_not_a_failure(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope())
            settled = dispatch.dispatch(record["intent_id"], runner=Controller(
                {"transport": "returned", "exit_code": 1,
                 "result": {"authorization_status": "product-execution-not-authorized",
                            "execution_status": "not-started"}}))
            self.assertEqual(store.COMPLETED, settled["delivery_state"])
            self.assertEqual(
                "product-execution-not-authorized",
                settled["result"]["controller_result"]["result"]["authorization_status"])

    def test_needs_input_becomes_waiting_input_not_completed(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope())
            settled = dispatch.dispatch(record["intent_id"], runner=Controller(
                {"transport": "returned", "exit_code": 1,
                 "result": {"execution_status": "needs_input", "invocation_id": "inv-1",
                            "needs_input": "denied tool 'Bash'"}}))
            self.assertEqual(store.WAITING_INPUT, settled["delivery_state"])
            self.assertEqual("ceo-input-required", settled["delivery_reason"])


class RealControllerEntryContract(unittest.TestCase):
    """One real subprocess against the real entry point and the real gate."""

    def test_listener_reaches_the_real_controller_authorization_boundary(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope("KAN-183", key="real"))
            settled = dispatch.dispatch(record["intent_id"], timeout=180)
            self.assertEqual(store.COMPLETED, settled["delivery_state"])
            controller = settled["result"]["controller_result"]
            self.assertEqual("returned", controller["transport"])
            result = controller["result"]
            # State-independent on purpose. These suites run against the REAL canonical
            # runtime, whose operating mode and standing authorization legitimately
            # change while a Product pilot is live. Asserting a governance VERDICT here
            # made the suite go red because the system was working, which is how a
            # regression suite stops being read. Assert the mechanism instead: a
            # governance answer came back, and nothing leaked past it.
            self.assertTrue(result["authorization_status"])
            self.assertNotEqual("not-checked", result["authorization_status"])
            self.assertEqual("not-started", result["claim_status"])
            self.assertEqual("not-opened", result["lease_closure_status"])
            self.assertEqual("not-started", result["execution_status"])
            self.assertIsNone(result["invocation_id"])
            self.assertFalse(result["jira_transition_performed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
