#!/usr/bin/env python3
"""Migration Slice 6 — Codex CLI provider characterization and safety tests."""

import os
import inspect
import subprocess
import sys
import unittest
import dataclasses


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agent.execution.brief import render_executor_brief  # noqa: E402
from agent.execution.codex import (  # noqa: E402
    CODEX_MODEL_MAP,
    CodexAuthenticationFailure,
    CodexCliTransport,
    CodexExecutorProcessFailure,
    CodexProvider,
    CodexTimeout,
    CodexUnavailable,
    CodexUnsupportedCapability,
    CodexUnsupportedEffort,
    CodexUnsupportedModel,
    capabilities,
    prepare_codex_invocation,
)
from agent.execution.provider import (  # noqa: E402
    ExecutionFeature,
    ExecutionResult,
    ExecutionStatus,
    FailureCode,
    ModelIntent,
    ReasoningEffort,
)
from agent.execution.wake import execute_product_wake  # noqa: E402
from test_claude_wake import FakeStore, RecordingTransport, request  # noqa: E402


class CodexProviderTests(unittest.TestCase):
    def test_capabilities_are_limited_to_evidenced_codex_cli_features(self):
        declared = capabilities()
        self.assertEqual("codex-cli", declared.provider_id)
        self.assertEqual(
            {ExecutionFeature.REPOSITORY_READ, ExecutionFeature.REPOSITORY_EDIT,
             ExecutionFeature.SHELL},
            declared.execution_features,
        )
        self.assertNotIn(ExecutionFeature.BROWSER_AUTOMATION, declared.execution_features)
        self.assertNotIn(ExecutionFeature.COMPUTER_CONTROL, declared.execution_features)
        self.assertNotIn(ExecutionFeature.RESUMABLE_SESSIONS, declared.execution_features)
        self.assertEqual(
            {ReasoningEffort.LOW, ReasoningEffort.MEDIUM, ReasoningEffort.HIGH},
            declared.supported_reasoning_efforts,
        )

    def test_invocation_preserves_the_exact_core_request_and_maps_models(self):
        expected_models = {
            ModelIntent.COST_EFFICIENT: "gpt-5.6-luna",
            ModelIntent.BALANCED: "gpt-5.6-terra",
            ModelIntent.HIGHEST_CAPABILITY: "gpt-6-astra",
        }
        self.assertEqual(expected_models, CODEX_MODEL_MAP)
        for intent, model in expected_models.items():
            with self.subTest(intent=intent):
                original = request(model_intent=intent)
                invocation = prepare_codex_invocation(original, session_ref="codex-session-1")
                self.assertIs(original, invocation.request)
                self.assertIn(original.objective, invocation.prompt)
                self.assertEqual(model, invocation.model)
                self.assertEqual("high", invocation.reasoning_effort)
                self.assertEqual("workspace-write", invocation.sandbox)
                self.assertEqual("codex-session-1", invocation.session_ref)
                self.assertEqual(original.context_refs, invocation.request.context_refs)
                self.assertEqual(original.workspace, invocation.request.workspace)
                self.assertEqual(original.primary_target, invocation.request.primary_target)
                self.assertEqual(original.validation_targets,
                                 invocation.request.validation_targets)

    def test_rendered_brief_preserves_every_executor_facing_constraint(self):
        original = request()
        before = dataclasses.asdict(original)
        invocation = prepare_codex_invocation(original)
        self.assertEqual(invocation.prompt, render_executor_brief(original))
        for required in (
            original.work_item_id, original.required_capability,
            original.execution_kind.value, original.objective,
            original.role_contract_ref, *original.context_refs,
            original.workspace.repository_root, original.workspace.working_directory,
            original.workspace.worktree_path, original.workspace.expected_revision,
            *original.allowed_surfaces, *original.prohibited_actions,
            original.reported_environment.environment_ref,
            original.primary_target.environment_ref,
            *(target.target_id for target in original.validation_targets),
            original.return_contract.return_to,
            *original.return_contract.required_evidence,
            *original.return_contract.required_sections,
        ):
            self.assertIn(required, invocation.prompt)
        # Control-plane identity is Thebes-owned and is not executor context.
        for withheld in (original.invocation_id, original.claim_ref,
                         original.execution_lease_id, original.operating_mode,
                         invocation.model):
            self.assertNotIn(withheld, invocation.prompt)
        for label in ("Seat ID", "Claim reference", "Execution lease", "Operating mode",
                      "Model intent", "Reasoning effort", "Resolved"):
            self.assertNotIn(label, invocation.prompt)
        self.assertLess(invocation.prompt.index(original.context_refs[0]),
                        invocation.prompt.index(original.context_refs[1]))
        self.assertLess(invocation.prompt.index(original.context_refs[1]),
                        invocation.prompt.index(original.context_refs[2]))
        self.assertIn("transport-enforced", invocation.prompt)
        self.assertIn("executor instruction", invocation.prompt)
        self.assertIn("Do not substitute another environment", invocation.prompt)
        self.assertEqual(before, dataclasses.asdict(original))

    def test_unsupported_request_features_models_and_efforts_fail_closed(self):
        calls = []
        unsupported_feature = request(required_execution_features=frozenset({
            ExecutionFeature.REPOSITORY_READ, ExecutionFeature.BROWSER_AUTOMATION,
        }))
        result = CodexProvider(lambda invocation: calls.append(invocation)).execute(
            unsupported_feature
        )
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
        self.assertEqual(FailureCode.UNSUPPORTED_CAPABILITY, result.failure.code)
        self.assertEqual([], calls)

        result = CodexProvider(lambda invocation: calls.append(invocation),
                               model_map={}).execute(request())
        self.assertEqual(FailureCode.UNSUPPORTED_MODEL, result.failure.code)
        self.assertEqual([], calls)

        result = CodexProvider(lambda invocation: calls.append(invocation),
                               supported_efforts=frozenset()).execute(request())
        self.assertEqual(FailureCode.UNSUPPORTED_EFFORT, result.failure.code)
        self.assertEqual([], calls)

    def test_completion_needs_input_and_execution_failure_use_shared_result_contract(self):
        completion = CodexProvider(RecordingTransport({
            "status": "completed", "summary": "bounded Codex invocation complete",
            "evidence": [{"kind": "command", "reference": "artifact:codex-test"}],
            "changed_files": [{"path": "agent/example.py", "change_kind": "modified"}],
            "tests": [{"command": "python3 test.py", "status": "passed", "exit_code": 0}],
            "duration_seconds": 2.5,
            "continuation_ref": "codex-thread-2",
        })).execute(request())
        self.assertIsInstance(completion, ExecutionResult)
        self.assertEqual(ExecutionStatus.COMPLETED, completion.status)
        self.assertEqual("codex-cli", completion.provider_id)
        self.assertEqual("gpt-5.6-luna", completion.resolved_model_ref)
        self.assertEqual("high", completion.resolved_effort_ref)
        self.assertEqual("codex-thread-2", completion.continuation_ref)

        needs_input = CodexProvider(RecordingTransport({
            "status": "needs_input", "summary": "authority required",
            "escalation": {"reason": "schema decision is absent",
                           "required_authority": "cto"},
        })).execute(request())
        self.assertEqual(ExecutionStatus.NEEDS_INPUT, needs_input.status)
        self.assertEqual("cto", needs_input.escalation.required_authority)

        failed = CodexProvider(RecordingTransport({
            "status": "execution_failed", "summary": "assigned test failed",
            "failure_message": "test command exited 1",
        })).execute(request())
        self.assertEqual(ExecutionStatus.EXECUTION_FAILED, failed.status)
        self.assertEqual(FailureCode.EXECUTION_FAILURE, failed.failure.code)

    def test_provider_failure_vocabulary_is_normalized_without_retry_or_fallback(self):
        cases = (
            (CodexUnavailable("CLI unavailable"), FailureCode.UNAVAILABLE),
            (CodexAuthenticationFailure("authentication failed"),
             FailureCode.AUTHENTICATION_FAILURE),
            (CodexUnsupportedModel("model rejected"), FailureCode.UNSUPPORTED_MODEL),
            (CodexUnsupportedEffort("effort rejected"), FailureCode.UNSUPPORTED_EFFORT),
            (CodexUnsupportedCapability("capability rejected"),
             FailureCode.UNSUPPORTED_CAPABILITY),
            (CodexTimeout("timed out"), FailureCode.TIMEOUT),
            (CodexExecutorProcessFailure("process exited"),
             FailureCode.EXECUTOR_PROCESS_FAILURE),
        )
        for failure, code in cases:
            with self.subTest(code=code):
                calls = []

                def transport(invocation, failure=failure):
                    calls.append(invocation)
                    raise failure

                result = CodexProvider(transport).execute(request())
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
                self.assertEqual(code, result.failure.code)
                self.assertEqual(1, len(calls))
                self.assertEqual((), result.evidence)
                self.assertIsNone(result.escalation)

    def test_malformed_result_is_a_provider_failure_with_safe_artifact_reference(self):
        malformed = CodexProvider(RecordingTransport({
            "status": "completed", "summary": "x", "unknown": True,
            "raw_artifact_ref": "artifact:codex-malformed",
        })).execute(request())
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED, malformed.status)
        self.assertEqual(FailureCode.MALFORMED_RESULT, malformed.failure.code)
        self.assertEqual("artifact:codex-malformed", malformed.raw_artifact_ref)

    def test_cli_transport_prepares_the_evidenced_command_without_running_codex(self):
        captured = []

        def runner(command, **kwargs):
            captured.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "Codex report", "")

        invocation = prepare_codex_invocation(request())
        raw = CodexCliTransport(runner=runner)(invocation)
        command, kwargs = captured[0]
        self.assertEqual("codex", command[0])
        self.assertEqual("exec", command[1])
        self.assertIn("--model", command)
        self.assertIn("gpt-5.6-luna", command)
        self.assertIn('model_reasoning_effort="high"', command)
        self.assertIn(request().workspace.working_directory, command)
        self.assertIn("workspace-write", command)
        self.assertIn(request().objective, command[-1])
        self.assertIn(request().allowed_surfaces[0], command[-1])
        self.assertIn(request().primary_target.environment_ref, command[-1])
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual("Codex report", raw)

    def test_provider_has_no_workflow_or_provider_selection_authority(self):
        import agent.execution.codex as codex_module
        source = inspect.getsource(codex_module).lower()
        for forbidden in ("agent.state.store", "execute_product_wake", "select_next",
                          "record_review", "transition_jira", "provider_registry"):
            self.assertNotIn(forbidden, source)


class CodexLeaseSafetyTests(unittest.TestCase):
    def test_timeout_and_malformed_results_close_the_exact_lease_once(self):
        for outcome, code in ((CodexTimeout("slow"), FailureCode.TIMEOUT),
                              ({}, FailureCode.MALFORMED_RESULT)):
            with self.subTest(code=code):
                events = []
                store = FakeStore(events)
                calls = []

                def transport(invocation, outcome=outcome):
                    events.append("transport")
                    calls.append(invocation)
                    if isinstance(outcome, BaseException):
                        raise outcome
                    return outcome

                provider = CodexProvider(transport)
                result = execute_product_wake(
                    "KAN-900", "backend-1", "authorization:bounded",
                    lambda task, lease: request(), (provider,), state_store=store,
                )
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
                self.assertEqual(code, result.failure.code)
                self.assertEqual(1, len(calls))
                self.assertEqual(1, events.count("lease-open"))
                self.assertEqual(1, events.count("lease-close"))
                self.assertEqual("lease-close", events[-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
