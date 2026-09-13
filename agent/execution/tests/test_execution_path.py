#!/usr/bin/env python3
"""Provider remediation Slice 7.1 — authoritative execution-path integration."""

import dataclasses
import os
import sys
import threading
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agent.execution.claude import ClaudeProvider  # noqa: E402
from agent.execution.codex import CodexProvider  # noqa: E402
from agent.execution.provider import (  # noqa: E402
    ExecutionFeature, ExecutionResult, ExecutionStatus, FailureCode, ModelIntent,
    ProviderCapabilities,
    ReasoningEffort,
)
from agent.execution.wake import (  # noqa: E402
    WakeOrderError,
    build_prepared_continuation_request,
    execute_approved_claude_continuation,
    execute_product_wake,
)
from test_claude_wake import FakeStore, RecordingTransport, request  # noqa: E402


class UnavailableProvider:
    def __init__(self):
        self.calls = []

    def capabilities(self):
        return ProviderCapabilities(
            provider_id="claude-code", available=False,
            availability_reason="fixture unavailable",
            execution_features=frozenset(ExecutionFeature),
            supported_model_intents=frozenset(),
            supported_reasoning_efforts=frozenset(),
        )

    def execute(self, execution_request):
        self.calls.append(execution_request)
        raise AssertionError("an unavailable provider must not execute")


class ExecutionPathIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.store = FakeStore(self.events)

    def _factory(self, task, lease):
        self.events.append("request")
        return request(
            claim_ref=task["ownership"]["claim_ref"],
            execution_lease_id=lease["execution_lease_id"],
            operating_mode_revision=lease["mode_revision"],
        )

    def _execute(self, providers, override=None):
        return execute_product_wake(
            "KAN-900", "backend-1", "authorization:bounded", self._factory,
            providers, provider_override=override, state_store=self.store,
        )

    def test_claude_is_selected_executed_received_and_closed_once(self):
        transport = RecordingTransport("Claude normalized")
        provider = ClaudeProvider(transport)
        with patch("agent.execution.wake.receive_execution_result", wraps=lambda result: result) as receipt:
            result = self._execute((provider,))
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(1, len(transport.wakes))
        self.assertEqual(1, receipt.call_count)
        self.assertEqual(["permission", "lease-open", "request", "receipt", "lease-close"], self.events)

    def test_codex_override_uses_the_same_request_and_full_rendered_brief(self):
        original = self._factory
        observed = []

        def factory(task, lease):
            built = original(task, lease)
            observed.append(built)
            return built

        self._factory = factory
        transport = RecordingTransport("Codex normalized")
        provider = CodexProvider(transport)
        with patch("agent.execution.wake.receive_execution_result", wraps=lambda result: result) as receipt:
            result = self._execute((provider,), override="codex-cli")
        invocation = transport.wakes[0]
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertIs(observed[0], invocation.request)
        self.assertIn(observed[0].role_contract_ref, invocation.prompt)
        self.assertIn(observed[0].context_refs[0], invocation.prompt)
        self.assertIn(observed[0].allowed_surfaces[0], invocation.prompt)
        self.assertIn(observed[0].prohibited_actions[0], invocation.prompt)
        self.assertIn(observed[0].reported_environment.environment_ref, invocation.prompt)
        self.assertIn(observed[0].primary_target.environment_ref, invocation.prompt)
        self.assertIn(observed[0].validation_targets[0].target_id, invocation.prompt)
        self.assertIn(observed[0].return_contract.required_sections[0], invocation.prompt)
        self.assertEqual(1, receipt.call_count)
        self.assertEqual(1, self.events.count("lease-close"))

    def test_selection_failure_is_received_without_provider_execution(self):
        provider = UnavailableProvider()
        with patch("agent.execution.wake.receive_execution_result", wraps=lambda result: result) as receipt:
            result = self._execute((provider,))
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
        self.assertEqual(FailureCode.UNAVAILABLE, result.failure.code)
        self.assertEqual([], provider.calls)
        self.assertEqual(1, receipt.call_count)
        self.assertEqual(1, self.events.count("lease-close"))

    def test_execution_failure_has_no_retry_or_fallback(self):
        calls = []

        def failed_transport(wake):
            calls.append(wake)
            return {"status": "execution_failed", "summary": "test failed",
                    "failure_message": "one bounded failure"}

        selected = ClaudeProvider(failed_transport)
        fallback = CodexProvider(RecordingTransport("must not run"))
        with patch("agent.execution.wake.receive_execution_result", wraps=lambda result: result) as receipt:
            result = self._execute((selected, fallback))
        self.assertEqual(ExecutionStatus.EXECUTION_FAILED, result.status)
        self.assertEqual(1, len(calls))
        self.assertEqual([], fallback._transport.wakes)
        self.assertEqual(1, receipt.call_count)
        self.assertEqual(1, self.events.count("lease-close"))

    def test_selector_and_renderer_leave_the_request_immutable(self):
        original = request()
        before = dataclasses.asdict(original)
        transport = RecordingTransport("Codex normalized")
        provider = CodexProvider(transport)
        result = execute_product_wake(
            "KAN-900", "backend-1", "authorization:bounded",
            lambda task, lease: original, (provider,), provider_override="codex-cli",
            state_store=self.store,
        )
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(before, dataclasses.asdict(original))

    def test_observer_can_end_while_one_wake_persists_result_before_lease_close(self):
        started, finish = threading.Event(), threading.Event()
        calls, receipts = [], {}

        class ReceiptStore(FakeStore):
            def record_execution_receipt(self, invocation_id, work_item_id, seat_id,
                                         execution_lease_id, normalized_result,
                                         provider_selection=None):
                self.events.append("receipt")
                receipts[invocation_id] = normalized_result

        class DelayedProvider:
            def capabilities(self):
                return ProviderCapabilities(
                    provider_id="codex-cli", available=True,
                    execution_features=frozenset(ExecutionFeature),
                    supported_model_intents=frozenset(ModelIntent),
                    supported_reasoning_efforts=frozenset(ReasoningEffort),
                )

            def execute(self, execution_request):
                calls.append(execution_request.invocation_id)
                started.set()
                finish.wait(2)
                return ExecutionResult(
                    invocation_id=execution_request.invocation_id,
                    status=ExecutionStatus.COMPLETED,
                    summary="completed after observer interruption",
                    provider_id="codex-cli",
                )

        events = []
        state = ReceiptStore(events)
        outcome = []
        worker = threading.Thread(target=lambda: outcome.append(execute_product_wake(
            "KAN-900", "backend-1", "authorization:bounded",
            lambda task, lease: request(
                claim_ref=task["ownership"]["claim_ref"],
                execution_lease_id=lease["execution_lease_id"],
                operating_mode_revision=lease["mode_revision"],
            ), (DelayedProvider(),), provider_override="codex-cli", state_store=state,
        )))
        worker.start()
        self.assertTrue(started.wait(1))
        # Deliberately stop observing the initiating wake before completion.
        self.assertEqual(1, len(calls))
        finish.set()
        worker.join(2)

        self.assertEqual(ExecutionStatus.COMPLETED, outcome[0].status)
        self.assertEqual(1, len(calls))
        self.assertEqual("completed", receipts[calls[0]]["status"])
        self.assertLess(events.index("receipt"), events.index("lease-close"))

    def test_approved_continuation_keeps_lineage_and_refuses_replay_or_provider_switch(self):
        approval = {
            "execution_approval_id": "approval-1", "original_invocation_id": "original-1",
            "work_item_id": "KAN-900", "seat_id": "backend-1", "provider_id": "claude-code",
            "claude_session_id": "session-1", "permission": "mcp__example__write",
        }
        original = {"status": "needs_input", "provider_id": "claude-code"}
        preparation = {
            "execution_continuation_id": "continuation-1", "work_item_id": "KAN-900",
            "seat_id": "backend-1", "required_capability": "backend",
            "validation_route": "peer", "repository_root": "/repo",
            "working_directory": "/repo", "worktree_path": "/repo", "expected_revision": "abc",
            "historical_request_persisted": False,
        }

        class ContinuationStore(FakeStore):
            def __init__(self, events):
                super().__init__(events)
                self.receipts = {}

            def read_execution_approval(self, approval_id):
                return approval if approval_id == approval["execution_approval_id"] else None

            def read_execution_receipt(self, invocation_id):
                if invocation_id == "original-1":
                    return original
                return self.receipts.get(invocation_id)

            def read_execution_continuation_preparation(self, invocation_id):
                return preparation if invocation_id == "original-1" else None

            def record_execution_receipt(self, invocation_id, work_item_id, seat_id,
                                         execution_lease_id, normalized_result,
                                         provider_selection=None, continuation_of=None,
                                         approval_id=None):
                self.events.append("receipt")
                self.receipts[invocation_id] = {
                    "normalized_result": normalized_result, "continuation_of": continuation_of,
                    "approval_id": approval_id,
                }

        events, state = [], ContinuationStore([])
        transport = RecordingTransport({"status": "completed", "summary": "continued"})
        provider = ClaudeProvider(transport, session_ref="session-1",
                                  approved_permission="mcp__example__write")
        result = execute_approved_claude_continuation(
            "approval-1", lambda task, lease, approval, original: build_prepared_continuation_request(
                preparation, task, lease), provider,
            state_store=state)
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual("session-1", transport.wakes[0].session_ref)
        persisted = state.receipts["continuation-approval-1"]
        self.assertEqual("original-1", persisted["continuation_of"])
        self.assertEqual("approval-1", persisted["approval_id"])
        self.assertEqual("original-1", original.get("invocation_id", "original-1"))
        with self.assertRaisesRegex(WakeOrderError, "already executed"):
            execute_approved_claude_continuation(
                "approval-1", lambda task, lease, approval, original: request(), provider,
                state_store=state)
        codex = CodexProvider(RecordingTransport("must not execute"))
        with self.assertRaisesRegex(WakeOrderError, "provider switch"):
            execute_approved_claude_continuation(
                "approval-1", lambda task, lease, approval, original: request(), codex,
                state_store=ContinuationStore([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
