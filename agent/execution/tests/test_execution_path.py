#!/usr/bin/env python3
"""Provider remediation Slice 7.1 — authoritative execution-path integration."""

import dataclasses
import os
import sys
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
    ExecutionFeature, ExecutionResult, ExecutionStatus, FailureCode,
    ProviderCapabilities,
)
from agent.execution.wake import execute_product_wake  # noqa: E402
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
        self.assertEqual(["permission", "lease-open", "request", "lease-close"], self.events)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
