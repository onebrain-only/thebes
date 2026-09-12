#!/usr/bin/env python3
"""Migration Slice 7 — deterministic provider-selection policy tests."""

import dataclasses
import inspect
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agent.execution.claude import ClaudeProvider  # noqa: E402
from agent.execution.codex import CodexProvider  # noqa: E402
from agent.execution.provider import (  # noqa: E402
    ExecutionFeature,
    ExecutionResult,
    ExecutionStatus,
    Failure,
    FailureCode,
    ModelIntent,
    ProviderCapabilities,
    ReasoningEffort,
)
from agent.execution.selection import select_provider  # noqa: E402
from test_claude_wake import RecordingTransport, request  # noqa: E402


class StubProvider:
    def __init__(self, declared, result=None):
        self._declared = declared
        self._result = result
        self.calls = []

    def capabilities(self):
        return self._declared

    def execute(self, execution_request):
        self.calls.append(execution_request)
        return self._result or ExecutionResult(
            invocation_id=execution_request.invocation_id,
            status=ExecutionStatus.COMPLETED,
            summary="stub completed",
            provider_id=self._declared.provider_id,
        )


def declared(provider_id, available=True, features=None, models=None, efforts=None):
    return ProviderCapabilities(
        provider_id=provider_id,
        available=available,
        availability_reason=None if available else "fixture unavailable",
        execution_features=frozenset(ExecutionFeature if features is None else features),
        supported_model_intents=frozenset(ModelIntent if models is None else models),
        supported_reasoning_efforts=frozenset(
            ReasoningEffort if efforts is None else efforts
        ),
    )


class ProviderSelectionTests(unittest.TestCase):
    def test_default_selection_is_deterministic_and_preserves_request(self):
        original = request()
        before = dataclasses.asdict(original)
        claude_transport = RecordingTransport("Claude")
        codex_transport = RecordingTransport("Codex")
        providers = (ClaudeProvider(claude_transport), CodexProvider(codex_transport))

        first = select_provider(original, providers)
        second = select_provider(original, providers)
        self.assertEqual("claude-code", first.provider_id)
        self.assertIs(first.provider, second.provider)
        self.assertEqual(before, dataclasses.asdict(original))
        self.assertEqual([], claude_transport.wakes)
        self.assertEqual([], codex_transport.wakes)

    def test_capability_filter_selects_claude_and_forced_codex_fails_closed(self):
        browser_request = request(required_execution_features=frozenset({
            ExecutionFeature.REPOSITORY_READ,
            ExecutionFeature.BROWSER_AUTOMATION,
        }))
        providers = (ClaudeProvider(RecordingTransport("Claude")),
                     CodexProvider(RecordingTransport("Codex")))
        selected = select_provider(browser_request, providers)
        self.assertEqual("claude-code", selected.provider_id)

        forced = select_provider(browser_request, providers, override="codex-cli")
        self.assertIsNone(forced.provider)
        self.assertEqual(FailureCode.UNSUPPORTED_CAPABILITY, forced.failure.code)
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED,
                         forced.failure_result(browser_request).status)

    def test_explicit_override_selects_only_the_requested_eligible_provider(self):
        claude_transport = RecordingTransport("Claude")
        codex_transport = RecordingTransport("Codex")
        providers = (ClaudeProvider(claude_transport), CodexProvider(codex_transport))
        selected = select_provider(request(), providers, override="codex-cli")
        self.assertEqual("codex-cli", selected.provider_id)
        self.assertIs(selected.provider, providers[1])
        self.assertEqual([], claude_transport.wakes)
        self.assertEqual([], codex_transport.wakes)

        invalid = select_provider(request(), providers, override="unknown")
        self.assertIsNone(invalid.provider)
        self.assertEqual(FailureCode.UNSUPPORTED_CAPABILITY, invalid.failure.code)

    def test_unavailable_claude_allows_eligible_codex_without_fallback(self):
        claude = StubProvider(declared("claude-code", available=False))
        codex = StubProvider(declared("codex-cli"))
        selected = select_provider(request(), (claude, codex))
        self.assertEqual("codex-cli", selected.provider_id)
        self.assertEqual([], claude.calls)
        self.assertEqual([], codex.calls)

        forced = select_provider(request(), (claude, codex), override="claude-code")
        self.assertIsNone(forced.provider)
        self.assertEqual(FailureCode.UNAVAILABLE, forced.failure.code)

    def test_no_eligible_provider_reports_the_correct_normalized_failure(self):
        cases = (
            ((), FailureCode.UNAVAILABLE),
            ((StubProvider(declared("claude-code", available=False)),),
             FailureCode.UNAVAILABLE),
            ((StubProvider(declared("claude-code", features=frozenset())),),
             FailureCode.UNSUPPORTED_CAPABILITY),
            ((StubProvider(declared("claude-code", models=frozenset())),),
             FailureCode.UNSUPPORTED_MODEL),
            ((StubProvider(declared("claude-code", efforts=frozenset())),),
             FailureCode.UNSUPPORTED_EFFORT),
        )
        for providers, code in cases:
            with self.subTest(code=code):
                selected = select_provider(request(), providers)
                self.assertIsNone(selected.provider)
                self.assertEqual(code, selected.failure.code)
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED,
                                 selected.failure_result(request()).status)
                self.assertTrue(all(not provider.calls for provider in providers))

    def test_selected_execution_failure_never_retries_or_falls_back(self):
        failed = ExecutionResult(
            invocation_id=request().invocation_id,
            status=ExecutionStatus.PROVIDER_FAILED,
            summary="selected provider unavailable",
            failure=Failure(FailureCode.UNAVAILABLE, "selected provider unavailable"),
            provider_id="claude-code",
        )
        claude = StubProvider(declared("claude-code"), failed)
        codex = StubProvider(declared("codex-cli"))
        selected = select_provider(request(), (claude, codex))
        result = selected.provider.execute(request())
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
        self.assertEqual(1, len(claude.calls))
        self.assertEqual([], codex.calls)

    def test_selection_has_no_product_or_lifecycle_authority(self):
        state = {
            "product_authorized": False,
            "operating_mode": "SYSTEM_MAINTENANCE",
            "owner": "backend-1",
            "validation_route": "peer",
            "jira_status": "In Progress",
            "lifecycle": "execution",
            "next_ticket": None,
        }
        expected = dict(state)
        select_provider(request(), (StubProvider(declared("claude-code")),))
        self.assertEqual(expected, state)

    def test_policy_source_has_no_execution_or_workflow_mutation_path(self):
        import agent.execution.selection as selection_module
        source = inspect.getsource(selection_module).lower()
        for forbidden in (".execute(", "agent.state.store", "execute_product_wake",
                          "select_next", "record_review", "transition_jira", "retry"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
