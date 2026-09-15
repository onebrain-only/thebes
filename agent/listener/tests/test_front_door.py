#!/usr/bin/env python3
"""Phase-4 proof that the Listener is the operational front door.

Three claims, tested separately because they are three different things:

  1. The Controller's orchestrating commands refuse a direct operational
     invocation and succeed when the Listener launches them — and the read-only
     and recovery commands are untouched, because Phase 4 retires an execution
     front door, not an architecture.
  2. The Listener carries the authorizing intent into the Controller's process,
     so an operational result names the intake that caused it.
  3. The executor firewall knows the Listener exists. Phase 3 created a second
     control-plane surface and this list did not learn about it; an executor
     told to submit an intent is orchestrating its own execution by a new route.

Isolated: temporary runtime root, no Persistent State writes, no Jira, no
Supabase, no Product repository.
"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _isolation import IsolatedRuntime                       # noqa: E402
from agent.controller import entry                           # noqa: E402
from agent.execution.brief import (                          # noqa: E402
    CONTROL_PLANE_TOKENS, ExecutorBriefViolation,
    assert_no_control_plane_concept, assert_no_control_plane_identifier)
from agent.listener import contract, dispatch, store          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def envelope(work_item_id="KAN-999999", key="k-1"):
    return contract.normalize({
        "schema_version": 1, "intent_type": contract.EXECUTE_WORK_ITEM,
        "source": "codex-controller", "actor": "ceo", "idempotency_key": key,
        "correlation_id": "c-" + key, "payload": {"work_item_id": work_item_id}})


def run_controller(args, environment=None):
    return subprocess.run([sys.executable, "-m", "agent.controller"] + args,
                          cwd=ROOT, capture_output=True, text=True, timeout=180,
                          env=dict(os.environ, **(environment or {})))


class FrontDoorClassification(unittest.TestCase):
    def test_only_the_orchestrating_commands_are_gated(self):
        self.assertEqual(("execute", "resume", "decide"), entry.ORCHESTRATING_COMMANDS)
        for internal in ("integrate", "plan-sprint", "plan-backlog", "authority-manifest"):
            permitted, classification, _ = entry.caller(internal, environ={})
            self.assertTrue(permitted)
            self.assertEqual("internal-interface", classification)

    def test_direct_operational_invocation_is_refused(self):
        for command in entry.ORCHESTRATING_COMMANDS:
            permitted, classification, detail = entry.caller(command, environ={})
            self.assertFalse(permitted)
            self.assertEqual(entry.FRONT_DOOR_REFUSAL, classification)
            self.assertIn("agent.listener", detail)

    def test_a_listener_launch_is_permitted_and_names_its_intent(self):
        permitted, classification, detail = entry.caller(
            "execute", environ={entry.INTENT_ENV: "intent-abc"})
        self.assertTrue(permitted)
        self.assertEqual("listener", classification)
        self.assertEqual("intent-abc", detail)

    def test_maintenance_requires_a_stated_reason(self):
        permitted, classification, detail = entry.caller(
            "execute", maintenance_reason="recovering a stuck continuation", environ={})
        self.assertTrue(permitted)
        self.assertEqual("maintenance-override", classification)
        self.assertEqual("recovering a stuck continuation", detail)
        # An empty reason is not a reason.
        self.assertFalse(entry.caller("execute", maintenance_reason="", environ={})[0])

    def test_a_blank_marker_is_not_a_listener_launch(self):
        for blank in ("", "   "):
            self.assertFalse(entry.caller("execute", environ={entry.INTENT_ENV: blank})[0])


class RealControllerProcess(unittest.TestCase):
    """The guard as the operating system actually sees it."""

    def test_direct_execute_refuses_and_exits_nonzero(self):
        result = run_controller(["execute", "KAN-999999"],
                                {entry.INTENT_ENV: ""})
        self.assertEqual(2, result.returncode)
        self.assertIn(entry.FRONT_DOOR_REFUSAL, result.stdout)
        # It refused BEFORE reaching authorization: nothing was consulted.
        self.assertNotIn("authorization_status", result.stdout)

    def test_a_listener_launched_execute_runs_and_reports_its_entry_path(self):
        result = run_controller(["execute", "KAN-999999"],
                                {entry.INTENT_ENV: "intent-phase4"})
        self.assertIn('"entry_path": "listener"', result.stdout)
        self.assertIn('"entry_reference": "intent-phase4"', result.stdout)
        # The gate answered. KAN-999999 has no task record, so whatever the live
        # authorization state is, this never becomes a claim.
        self.assertIn('"claim_status": "not-started"', result.stdout)

    def test_maintenance_override_runs_and_records_its_reason(self):
        result = run_controller(["execute", "KAN-999999",
                                 "--maintenance-reason", "phase-4 suite"],
                                {entry.INTENT_ENV: ""})
        self.assertIn('"entry_path": "maintenance-override"', result.stdout)
        self.assertIn('"entry_reference": "phase-4 suite"', result.stdout)

    def test_read_only_and_recovery_commands_are_not_gated(self):
        # KAN-183 rather than a synthetic key: `authority-manifest` raises an
        # unhandled ValueError on a work item that does not exist. That is a
        # pre-existing rough edge, unrelated to the front door, and Phase 4 does
        # not need it and so does not opportunistically repair it.
        for args in (["plan-sprint"], ["plan-backlog"],
                     ["authority-manifest", "KAN-183"]):
            result = run_controller(args, {entry.INTENT_ENV: ""})
            self.assertEqual(0, result.returncode, args)
            self.assertNotIn(entry.FRONT_DOOR_REFUSAL, result.stdout)
        recovery = run_controller(["integrate", "KAN-999999"], {entry.INTENT_ENV: ""})
        self.assertNotIn(entry.FRONT_DOOR_REFUSAL, recovery.stdout)


class IntentProvenance(unittest.TestCase):
    def test_the_dispatcher_hands_the_intent_id_to_the_controller_process(self):
        intent = envelope()
        environment = dispatch.controller_environment(intent, environ={"PATH": "/usr/bin"})
        self.assertEqual(intent["intent_id"], environment[entry.INTENT_ENV])
        self.assertEqual("/usr/bin", environment["PATH"])

    def test_a_real_listener_dispatch_reaches_the_controller_as_a_listener_caller(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="provenance"))
            settled = dispatch.dispatch(record["intent_id"], timeout=180)
            result = settled["result"]["controller_result"]["result"]
            self.assertEqual("listener", result["entry_path"])
            self.assertEqual(record["intent_id"], result["entry_reference"])
            self.assertTrue(result["authorization_status"])
            self.assertEqual("not-started", result["claim_status"])


class DecisionPathAcrossTheRealBoundary(unittest.TestCase):
    """A DECISION_RESPONSE reaches the real `agent.controller decide` process.

    The positive resume is proven deterministically in `test_decision_loop.py`;
    it cannot be run live without authorized Product work that stops at a native
    permission boundary, and Phase 4 does not manufacture such work. What IS
    provable here, for real, is the part Phase 4 changed: the decision crosses a
    genuine process boundary, is admitted as a Listener caller rather than
    refused as a direct one, and is then refused by the canonical gate.
    """

    def _waiting_intent(self):
        waiting, _ = store.accept(envelope(work_item_id="KAN-999999", key="await"))
        dispatch.begin = store.begin_dispatch(waiting["intent_id"])
        store.settle(waiting["intent_id"], store.WAITING_INPUT,
                     {"transport": "returned", "exit_code": 1,
                      "result": {"work_item_id": "KAN-999999",
                                 "execution_status": "needs_input",
                                 "invocation_id": "invocation-phase4",
                                 "needs_input": "denied {'tool_name': 'Bash'}"}},
                     "ceo-input-required")
        return waiting

    def test_a_decision_crosses_the_boundary_as_a_listener_caller(self):
        with IsolatedRuntime():
            waiting = self._waiting_intent()
            answer = contract.normalize({
                "schema_version": 1, "intent_type": contract.DECISION_RESPONSE,
                "source": "codex-controller", "actor": "ceo",
                "idempotency_key": "decide-phase4", "correlation_id": "c-await",
                "responds_to": waiting["intent_id"],
                "payload": {"work_item_id": "KAN-999999", "decision": "approve",
                            "original_invocation_id": "invocation-phase4",
                            "permission": "Bash",
                            "approval_scope": "resume past the boundary"}})
            store.assert_decision_reference(answer)
            decision, _ = store.accept(answer)
            settled = dispatch.dispatch(decision["intent_id"], timeout=180)

            result = settled["result"]["controller_result"]["result"]
            self.assertEqual("listener", result["entry_path"])
            self.assertEqual(decision["intent_id"], result["entry_reference"])
            # It refused AFTER the front door admitted it, which is the thing
            # this test exists to show. WHICH canonical refusal depends on live
            # state — maintenance mode, or no prepared continuation for this
            # synthetic invocation — and either proves the same point.
            self.assertIn(result["blocker"],
                          ("system-maintenance-active", "no-prepared-continuation"))
            self.assertEqual("not-recorded", result["decision_status"])

    def test_the_same_decision_typed_directly_is_refused_at_the_front_door(self):
        result = run_controller(
            ["decide", "KAN-999999", "--invocation", "invocation-phase4",
             "--permission", "Bash", "--scope", "resume past the boundary"],
            {entry.INTENT_ENV: ""})
        self.assertEqual(2, result.returncode)
        self.assertIn(entry.FRONT_DOOR_REFUSAL, result.stdout)
        self.assertNotIn("decision_status", result.stdout)


class ExecutorBoundary(unittest.TestCase):
    """The executor must not be able to drive the new front door either."""

    LEAKS = (
        "Implement KAN-900 by running python3 -m agent.listener submit KAN-901.",
        "Use from agent.listener import store to check your intent.",
        "Post a DECISION_RESPONSE to the listener when you are blocked.",
        "Submit an intent to http://127.0.0.1:8787/intents to continue.",
        "import agent.listener and dispatch yourself.",
        "Send an EXECUTE_WORK_ITEM for the follow-up ticket.",
        "Reuse the idempotency key from the previous run.",
    )

    PRODUCT_TEXT = (
        "Fix the RLS policy on public.profiles so anon cannot read it.",
        "Run flutter test and report the output.",
        "The user's intent is to see recent searches cleared.",
        "Return a RESULT and EVIDENCE section to the controller.",
        "Add an index on meetups.creator_user_id.",
    )

    def _violations(self, text):
        categories = []
        for check in (assert_no_control_plane_identifier, assert_no_control_plane_concept):
            try:
                check(text, "objective")
            except ExecutorBriefViolation as exc:
                categories.append(exc.category)
        return categories

    def test_listener_is_a_control_plane_identifier(self):
        for token in ("agent.listener", "EXECUTE_WORK_ITEM", "DECISION_RESPONSE"):
            self.assertIn(token, CONTROL_PLANE_TOKENS)

    def test_every_listener_instruction_is_refused(self):
        for text in self.LEAKS:
            self.assertTrue(self._violations(text),
                            "executor brief still accepts: %r" % text)

    def test_ordinary_product_text_still_passes(self):
        for text in self.PRODUCT_TEXT:
            self.assertEqual([], self._violations(text),
                             "false positive on product text: %r" % text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
