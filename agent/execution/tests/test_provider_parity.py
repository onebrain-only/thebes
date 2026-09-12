#!/usr/bin/env python3
"""Thebes-facing parity between the explicit Claude and Codex providers."""

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
    ExecutionResult,
    ExecutionStatus,
    PROVIDER_FAILURE_CODES,
)
from agent.execution.result import receive_execution_result  # noqa: E402
from test_claude_wake import RecordingTransport, request  # noqa: E402


class ProviderParityTests(unittest.TestCase):
    def test_both_providers_receive_the_same_core_work_identity_and_constraints(self):
        original = request()
        claude_transport = RecordingTransport("Claude completed")
        codex_transport = RecordingTransport("Codex completed")
        claude = ClaudeProvider(claude_transport)
        codex = CodexProvider(codex_transport)

        claude_result = claude.execute(original)
        codex_result = codex.execute(original)
        claude_wake = claude_transport.wakes[0]
        codex_invocation = codex_transport.wakes[0]

        self.assertEqual(original.work_item_id, codex_invocation.request.work_item_id)
        self.assertEqual(original.seat_id, claude_wake.subagent_type)
        self.assertEqual(original.seat_id, codex_invocation.request.seat_id)
        self.assertEqual(original.required_capability,
                         codex_invocation.request.required_capability)
        self.assertEqual(original.role_contract_ref, claude_wake.role_contract_ref)
        self.assertEqual(original.role_contract_ref,
                         codex_invocation.request.role_contract_ref)
        self.assertEqual(original.context_refs, claude_wake.context_refs)
        self.assertEqual(original.context_refs, codex_invocation.request.context_refs)
        self.assertEqual(original.workspace, claude_wake.workspace)
        self.assertEqual(original.workspace, codex_invocation.request.workspace)
        self.assertEqual(original.reported_environment, claude_wake.reported_environment)
        self.assertEqual(original.reported_environment,
                         codex_invocation.request.reported_environment)
        self.assertEqual(original.primary_target, claude_wake.primary_target)
        self.assertEqual(original.primary_target,
                         codex_invocation.request.primary_target)
        self.assertEqual(original.validation_targets, claude_wake.validation_targets)
        self.assertEqual(original.validation_targets,
                         codex_invocation.request.validation_targets)
        self.assertEqual(original.objective, claude_wake.prompt)
        self.assertIn(original.objective, codex_invocation.prompt)
        self.assertEqual(ExecutionStatus.COMPLETED, claude_result.status)
        self.assertEqual(ExecutionStatus.COMPLETED, codex_result.status)

    def test_result_status_and_failure_vocabulary_are_provider_neutral(self):
        self.assertEqual(
            {"completed", "needs_input", "execution_failed", "provider_failed"},
            {status.value for status in ExecutionStatus},
        )
        self.assertEqual(
            {"unavailable", "authentication_failure", "unsupported_model",
             "unsupported_effort", "unsupported_capability", "timeout",
             "executor_process_failure", "malformed_result"},
            {code.value for code in PROVIDER_FAILURE_CODES},
        )
        for provider in (ClaudeProvider(RecordingTransport("Claude")),
                         CodexProvider(RecordingTransport("Codex"))):
            with self.subTest(provider=provider.capabilities().provider_id):
                result = provider.execute(request())
                self.assertIsInstance(result, ExecutionResult)
                self.assertIn(result.status, ExecutionStatus)

    def test_result_receipt_preserves_core_workflow_authority_for_both_providers(self):
        workflow = {
            "product_authorized": False,
            "operating_mode": "SYSTEM_MAINTENANCE",
            "validation_route": "peer",
            "jira_status": "In Progress",
            "lifecycle": "execution",
            "next_ticket": None,
        }
        expected = dict(workflow)
        for provider in (ClaudeProvider(RecordingTransport("Claude")),
                         CodexProvider(RecordingTransport("Codex"))):
            with self.subTest(provider=provider.capabilities().provider_id):
                received = receive_execution_result(provider.execute(request()))
                self.assertEqual(ExecutionStatus.COMPLETED, received.status)
                self.assertEqual(expected, workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
