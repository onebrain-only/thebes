#!/usr/bin/env python3
"""Durable receipt recovery after the initiating observer has gone away.

The provider is deliberately invoked once in a worker thread.  The test stops
joining that worker after dispatch (the observation interruption), lets it
finish, and then uses the independent core lookup.  It proves a later
controller can recover evidence without another wake, retry, fallback, or a
synthetic Product result.
"""
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store  # noqa: E402
import validate  # noqa: E402
from agent.execution.provider import (ExecutionResult, ExecutionStatus, Failure,
                                      FailureCode)  # noqa: E402
from agent.execution.receipt import normalized_result_payload  # noqa: E402


class DurableReceiptRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_runtime, self.old_locks = store.RUNTIME, store.LOCKS
        self.old_validate_runtime = validate.RUNTIME
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        self.old_seats = validate.SEATS_JSON
        roster = os.path.join(self.tmp, "seats.json")
        with open(roster, "w") as fh:
            fh.write('{"record_type":"seat_registry","schema_version":1,"seats":{"frontend-1":{"role":"frontend"}}}')
        validate.SEATS_JSON = roster
        self.lease = store.create("execution_lease", {
            "work_item_id": "KAN-198", "seat_id": "frontend-1", "mode_revision": 12,
            "reason_ref": "authorized:KAN-198", "closed_at": None, "closed_by": None,
        })

    def tearDown(self):
        store.RUNTIME, store.LOCKS = self.old_runtime, self.old_locks
        validate.RUNTIME = self.old_validate_runtime
        validate.SEATS_JSON = self.old_seats

    def test_terminal_result_survives_observer_interruption_and_recovers_once(self):
        started, complete = threading.Event(), threading.Event()
        calls = []
        invocation = "controller-observer-interrupted"

        def provider_completion():
            calls.append("provider")
            started.set()
            complete.wait(2)
            result = ExecutionResult(invocation_id=invocation,
                                     status=ExecutionStatus.COMPLETED,
                                     summary="provider completed after observer ended",
                                     provider_id="codex-cli")
            store.record_execution_receipt(
                invocation, "KAN-198", "frontend-1",
                self.lease["execution_lease_id"], normalized_result_payload(result),
                provider_selection={
                    "primary_provider_id": "claude-code",
                    "selected_provider_id": "codex-cli",
                    "primary_ineligibility": {
                        "code": "unavailable", "message": "usage quota exhausted",
                    },
                })
            store.close_execution_lease(self.lease["execution_lease_id"],
                                        self.lease["revision"], "orchestrator")

        worker = threading.Thread(target=provider_completion)
        worker.start()
        self.assertTrue(started.wait(1))
        # The initiating observer deliberately does not wait for completion here.
        self.assertEqual(["provider"], calls)
        self.assertIsNone(store.read_execution_receipt(invocation))
        complete.set()
        worker.join(2)

        recovered = store.read_execution_receipt(invocation)
        self.assertEqual("completed", recovered["status"])
        self.assertEqual("provider completed after observer ended",
                         recovered["normalized_result"]["summary"])
        self.assertTrue(store.read("execution_lease", self.lease["execution_lease_id"])["closed_at"])
        self.assertEqual(["provider"], calls)
        self.assertEqual("codex-cli", recovered["provider_id"])
        self.assertEqual("claude-code", recovered["provider_selection"]["primary_provider_id"])

        # Idempotent recovery stores no second result and does not invoke anything.
        again = store.record_execution_receipt(
            invocation, "KAN-198", "frontend-1", self.lease["execution_lease_id"],
            recovered["normalized_result"], provider_selection=recovered["provider_selection"])
        self.assertEqual(recovered["execution_receipt_id"], again["execution_receipt_id"])
        self.assertEqual(["provider"], calls)

    def test_selection_failure_keeps_a_receipt_when_no_executor_was_dispatched(self):
        invocation = "controller-no-eligible-provider"
        result = ExecutionResult(
            invocation_id=invocation, status=ExecutionStatus.PROVIDER_FAILED,
            summary="claude-code cannot execute: usage quota exhausted",
            failure=Failure(FailureCode.UNAVAILABLE, "usage quota exhausted"),
            provider_id="thebes-provider-selection",
        )
        receipt = store.record_execution_receipt(
            invocation, "KAN-198", "frontend-1", self.lease["execution_lease_id"],
            normalized_result_payload(result), provider_selection={
                "primary_provider_id": "claude-code", "selected_provider_id": None,
                "primary_ineligibility": {
                    "code": "unavailable", "message": "usage quota exhausted",
                },
            })
        self.assertEqual("provider_failed", receipt["status"])
        self.assertIsNone(receipt["provider_selection"]["selected_provider_id"])

    def test_exact_ceo_approval_is_immutable_and_rejects_wrong_boundary(self):
        invocation = "controller-permission-boundary"
        result = {
            "invocation_id": invocation, "status": "needs_input", "summary": "blocked",
            "provider_id": "claude-code", "continuation_ref": "claude-session-1",
            "escalation": {"reason": "Claude Code native permission required: "
                           "mcp__claude_ai_Supabase__apply_migration",
                           "required_authority": "CEO", "required_capability": None},
            "evidence": [], "changed_files": [], "tests": [], "failure": None,
            "resolved_model_ref": None, "resolved_effort_ref": None,
            "duration_seconds": None, "raw_artifact_ref": None,
        }
        store.record_execution_receipt(
            invocation, "KAN-198", "frontend-1", self.lease["execution_lease_id"], result,
            provider_selection={"primary_provider_id": "claude-code",
                                "selected_provider_id": "claude-code"})
        before = store.read_execution_receipt(invocation)
        approval = store.record_execution_approval(
            invocation, "KAN-198", "frontend-1", "claude-session-1",
            "mcp__claude_ai_Supabase__apply_migration", "ceo", "one native tool call")
        self.assertEqual("claude-code", approval["provider_id"])
        self.assertEqual(before, store.read_execution_receipt(invocation))
        with self.assertRaisesRegex(store.StateError, "does not match"):
            store.record_execution_approval(
                invocation, "KAN-198", "frontend-1", "wrong-session",
                "mcp__claude_ai_Supabase__apply_migration", "ceo", "one native tool call")
        with self.assertRaisesRegex(store.StateError, "does not match"):
            store.record_execution_approval(
                invocation, "KAN-198", "frontend-1", "claude-session-1",
                "mcp__claude_ai_Supabase__other", "ceo", "one native tool call")
        with self.assertRaisesRegex(store.StateError, "wildcarded"):
            store.record_execution_approval(
                invocation, "KAN-198", "frontend-1", "claude-session-1",
                "mcp__claude_ai_Supabase__*", "ceo", "one native tool call")


if __name__ == "__main__":
    unittest.main(verbosity=2)
