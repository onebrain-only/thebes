#!/usr/bin/env python3
"""Migration Slice 5 — normalized Claude results and provider failures."""

import inspect
import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agent.execution.claude import (  # noqa: E402
    ClaudeAuthenticationFailure,
    ClaudeExecutorProcessFailure,
    ClaudeProvider,
    ClaudeUnavailable,
    ClaudeUnsupportedCapability,
    ClaudeUnsupportedEffort,
    ClaudeUnsupportedModel,
)
from agent.execution.provider import (  # noqa: E402
    ExecutionResult,
    ExecutionStatus,
    FailureCode,
    TestStatus,
)
from agent.execution.result import receive_execution_result  # noqa: E402
from agent.execution.wake import execute_product_wake  # noqa: E402
from test_claude_wake import FakeStore, RecordingTransport, request  # noqa: E402


class ResultNormalizationTests(unittest.TestCase):
    def test_completed_normalizes_only_explicit_claims_and_metadata(self):
        raw = {
            "status": "completed",
            "summary": "bounded invocation complete",
            "evidence": [{"kind": "command", "reference": "artifact:test",
                          "summary": "reported test output"}],
            "changed_files": [{"path": "agent/example.py", "change_kind": "modified"}],
            "tests": [{"command": "python3 test.py", "status": "passed",
                       "evidence_ref": "artifact:test", "exit_code": 0}],
            "duration_seconds": 4.5,
            "continuation_ref": "claude-session-2",
            "raw_artifact_ref": "artifact:raw-2",
        }
        result = ClaudeProvider(RecordingTransport(raw)).execute(request())
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(raw["summary"], result.summary)
        self.assertEqual("artifact:test", result.evidence[0].reference)
        self.assertEqual("agent/example.py", result.changed_files[0].path)
        self.assertEqual(TestStatus.PASSED, result.tests[0].status)
        self.assertEqual("claude-code", result.provider_id)
        self.assertEqual("opus", result.resolved_model_ref)
        self.assertEqual("low", result.resolved_effort_ref)
        self.assertEqual(4.5, result.duration_seconds)
        self.assertEqual("claude-session-2", result.continuation_ref)
        self.assertEqual("artifact:raw-2", result.raw_artifact_ref)

    def test_plain_native_text_is_completed_invocation_not_acceptance(self):
        raw = "executor returned a report; claims remain unverified"
        result = ClaudeProvider(RecordingTransport(raw)).execute(request())
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(raw, result.summary)
        self.assertEqual((), result.evidence)
        self.assertEqual((), result.changed_files)
        self.assertEqual((), result.tests)

    def test_needs_input_requires_a_bounded_escalation(self):
        raw = {
            "status": "needs_input",
            "summary": "schema authority is required",
            "escalation": {"reason": "schema shape is not decided",
                           "required_authority": "cto",
                           "required_capability": "backend"},
            "continuation_ref": "claude-session-waiting",
        }
        result = ClaudeProvider(RecordingTransport(raw)).execute(request())
        self.assertEqual(ExecutionStatus.NEEDS_INPUT, result.status)
        self.assertEqual("cto", result.escalation.required_authority)
        self.assertEqual("backend", result.escalation.required_capability)
        self.assertEqual("claude-session-waiting", result.continuation_ref)

        malformed = ClaudeProvider(RecordingTransport({
            "status": "needs_input", "summary": "uncertain"
        })).execute(request())
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED, malformed.status)
        self.assertEqual(FailureCode.MALFORMED_RESULT, malformed.failure.code)

    def test_execution_failure_is_distinct_from_provider_failure(self):
        raw = {"status": "execution_failed", "summary": "assigned check failed",
               "failure_message": "test command exited 1"}
        result = ClaudeProvider(RecordingTransport(raw)).execute(request())
        self.assertEqual(ExecutionStatus.EXECUTION_FAILED, result.status)
        self.assertEqual(FailureCode.EXECUTION_FAILURE, result.failure.code)
        self.assertNotEqual(ExecutionStatus.PROVIDER_FAILED, result.status)

    def test_all_provider_failures_normalize_without_retry(self):
        cases = (
            (ClaudeUnavailable("native Agent unavailable"), FailureCode.UNAVAILABLE),
            (ClaudeAuthenticationFailure("Claude authentication failed"),
             FailureCode.AUTHENTICATION_FAILURE),
            (ClaudeUnsupportedModel("model rejected"), FailureCode.UNSUPPORTED_MODEL),
            (ClaudeUnsupportedEffort("effort rejected"), FailureCode.UNSUPPORTED_EFFORT),
            (ClaudeUnsupportedCapability("tool unavailable"),
             FailureCode.UNSUPPORTED_CAPABILITY),
            (TimeoutError("native Agent timed out"), FailureCode.TIMEOUT),
            (ClaudeExecutorProcessFailure("Agent process terminated"),
             FailureCode.EXECUTOR_PROCESS_FAILURE),
        )
        for failure, code in cases:
            with self.subTest(code=code):
                calls = []

                def transport(wake, failure=failure):
                    calls.append(wake)
                    raise failure

                result = ClaudeProvider(transport).execute(request())
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
                self.assertEqual(code, result.failure.code)
                self.assertEqual(1, len(calls))
                self.assertIsNone(result.escalation)
                self.assertEqual((), result.evidence)

    def test_configuration_failures_normalize_before_transport(self):
        for field, value, code in (
            ("model", "unknown-model", FailureCode.UNSUPPORTED_MODEL),
            ("effort", "extreme", FailureCode.UNSUPPORTED_EFFORT),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                binding = {"name": "backend-1", "role": "backend",
                           "model": "opus", "effort": "low"}
                binding[field] = value
                with open(os.path.join(directory, "backend-1.yml"), "w",
                          encoding="utf-8") as fh:
                    for key, item in binding.items():
                        fh.write("%s: %s\n" % (key, item))
                with open(os.path.join(directory, "backend-1.md"), "w",
                          encoding="utf-8") as fh:
                    fh.write("generated definition fixture\n")
                transport = RecordingTransport("must not run")
                result = ClaudeProvider(
                    transport, bindings_dir=directory, agents_dir=directory
                ).execute(request())
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
                self.assertEqual(code, result.failure.code)
                self.assertEqual([], transport.wakes)

        with tempfile.TemporaryDirectory() as directory:
            transport = RecordingTransport("must not run")
            result = ClaudeProvider(
                transport, bindings_dir=directory, agents_dir=directory
            ).execute(request())
            self.assertEqual(FailureCode.UNAVAILABLE, result.failure.code)
            self.assertEqual([], transport.wakes)

    def test_malformed_results_are_provider_failures_with_safe_artifact_reference(self):
        malformed = (
            None,
            "",
            {},
            {"status": "completed", "summary": ""},
            {"status": "provider_failed", "summary": "self declared"},
            {"status": "completed", "summary": "x", "unknown": True},
            {"status": "execution_failed", "summary": "x"},
            {"status": "completed", "summary": "x", "tests": "not-a-list"},
            {"status": "completed", "summary": "x",
             "evidence": [{"kind": "command", "reference": "artifact:x",
                           "summary": 7}]},
            {"status": "completed", "summary": "x",
             "tests": [{"command": "test", "status": "passed",
                        "exit_code": "zero"}]},
            {"status": "needs_input", "summary": "x",
             "escalation": {"reason": "need a decision",
                            "required_authority": 7}},
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                result = ClaudeProvider(RecordingTransport(raw)).execute(request())
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
                self.assertEqual(FailureCode.MALFORMED_RESULT, result.failure.code)
        result = ClaudeProvider(RecordingTransport({
            "status": "completed", "summary": "x", "unknown": True,
            "raw_artifact_ref": "artifact:malformed-safe",
        })).execute(request())
        self.assertEqual("artifact:malformed-safe", result.raw_artifact_ref)


class LeaseAndAuthoritySafetyTests(unittest.TestCase):
    def execute_with(self, raw_or_exception):
        events = []
        store = FakeStore(events)
        calls = []

        def transport(wake):
            events.append("transport")
            calls.append(wake)
            if isinstance(raw_or_exception, BaseException):
                raise raw_or_exception
            return raw_or_exception

        def factory(task, lease):
            events.append("request")
            return request()

        result = execute_product_wake(
            ClaudeProvider(transport), "KAN-900", "backend-1",
            "authorization:bounded", factory, state_store=store
        )
        return result, events, calls

    def test_timeout_and_malformed_result_close_exact_lease(self):
        for raw, code in ((TimeoutError("slow"), FailureCode.TIMEOUT),
                          ({}, FailureCode.MALFORMED_RESULT)):
            with self.subTest(code=code):
                result, events, calls = self.execute_with(raw)
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
                self.assertEqual(code, result.failure.code)
                self.assertEqual(1, len(calls))
                self.assertEqual("lease-close", events[-1])
                self.assertEqual(1, events.count("lease-open"))
                self.assertEqual(1, events.count("lease-close"))

    def test_result_receipt_is_inert_and_preserves_external_authority(self):
        outcomes = (
            {"status": "completed", "summary": "invocation ended"},
            {"status": "needs_input", "summary": "decision required",
             "escalation": {"reason": "bounded authority is absent"}},
            ClaudeUnavailable("native Agent unavailable"),
        )
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                authorization = {"authorized": False}
                route = {"validation_route": "peer", "review_result": None,
                         "jira_status": "In Progress", "next_ticket": None}
                result, events, calls = self.execute_with(outcome)
                received = receive_execution_result(result)
                self.assertIs(result, received)
                self.assertEqual({"authorized": False}, authorization)
                self.assertEqual(
                    {"validation_route": "peer", "review_result": None,
                     "jira_status": "In Progress", "next_ticket": None}, route
                )
                self.assertEqual(1, len(calls))
                self.assertEqual("lease-close", events[-1])

    def test_core_result_boundary_has_no_workflow_mutation_dependencies(self):
        import agent.execution.result as result_module
        source = inspect.getsource(result_module).lower()
        for forbidden in ("agent.state.store", "jira", "set_operating_mode",
                          "record_review", "transition", "select_next", "retry"):
            self.assertNotIn(forbidden, source)
        with self.assertRaises(TypeError):
            receive_execution_result("raw provider text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
