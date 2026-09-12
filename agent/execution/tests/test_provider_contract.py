#!/usr/bin/env python3
"""Slice 1 contract, safety, and current-Claude characterization tests."""

import dataclasses
import inspect
import json
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution.provider import (  # noqa: E402
    ChangedFileClaim,
    EvidenceClaim,
    ExecutionFeature,
    ExecutionKind,
    ExecutionProvider,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ExecutionTarget,
    Failure,
    FailureCode,
    ModelIntent,
    MutationMode,
    PROVIDER_FAILURE_CODES,
    ProviderCapabilities,
    ReasoningEffort,
    ReportedEnvironment,
    ReturnContract,
    TestClaim as ProviderTestClaim,
    TestStatus,
    ValidationTarget,
    Workspace,
)
from agent.execution.testing import FakeProvider  # noqa: E402


FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "current_claude.json")


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()


def binding_fields(path):
    wanted = {"role", "model", "effort"}
    values = {}
    for line in read(path).splitlines():
        key, sep, value = line.partition(":")
        if sep and key in wanted:
            values[key] = value.strip().strip('"').strip("'")
    return values


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.capabilities = ProviderCapabilities(
            provider_id="fake",
            available=True,
            execution_features=frozenset({
                ExecutionFeature.REPOSITORY_READ,
                ExecutionFeature.REPOSITORY_EDIT,
                ExecutionFeature.SHELL,
            }),
            supported_reasoning_efforts=frozenset(ReasoningEffort),
            supported_model_intents=frozenset(ModelIntent),
        )
        self.result = ExecutionResult(
            invocation_id="inv-1",
            status=ExecutionStatus.COMPLETED,
            summary="bounded work reported complete",
            evidence=(EvidenceClaim("command", "evidence:1"),),
            changed_files=(ChangedFileClaim("agent/example.py", "modified"),),
            tests=(ProviderTestClaim("python3 test.py", TestStatus.PASSED,
                                     "test:evidence", 0),),
            provider_id="fake",
        )
        self.request = ExecutionRequest(
            invocation_id="inv-1",
            work_item_id="SYS-1",
            seat_id="backend-1",
            required_capability="backend",
            execution_kind=ExecutionKind.IMPLEMENTATION,
            objective="Make the exact bounded maintenance change.",
            role_contract_ref="agent/roles/backend.md",
            context_refs=("CLAUDE.md", "agent/ROADMAP.md"),
            workspace=Workspace(
                repository_root="/repo",
                working_directory="/repo/worktree",
                worktree_path="/repo/worktree",
                expected_revision="abc123",
                mutation_mode=MutationMode.REPOSITORY_EDIT,
            ),
            allowed_surfaces=("agent/execution/provider.py",),
            prohibited_actions=("select another ticket", "transition Jira"),
            operating_mode="SYSTEM_MAINTENANCE",
            operating_mode_revision=1,
            claim_ref=None,
            execution_lease_id=None,
            reported_environment=ReportedEnvironment("local", "python", "macos", "repo"),
            primary_target=ExecutionTarget("local", "python", "macos", "repo"),
            validation_targets=(ValidationTarget("contract-tests", "automated", True,
                                                 surface="agent/execution"),),
            model_intent=ModelIntent.BALANCED,
            reasoning_effort=ReasoningEffort.MEDIUM,
            required_execution_features=frozenset({
                ExecutionFeature.REPOSITORY_READ,
                ExecutionFeature.REPOSITORY_EDIT,
                ExecutionFeature.SHELL,
            }),
            timeout_seconds=300,
            return_contract=ReturnContract(
                return_to="controller",
                required_evidence=("changed files", "tests"),
                required_sections=("summary", "evidence"),
            ),
        )

    def test_interface_has_only_two_operations(self):
        operations = {name for name, value in ExecutionProvider.__dict__.items()
                      if not name.startswith("_") and callable(value)}
        self.assertEqual({"capabilities", "execute"}, operations)
        self.assertIsInstance(FakeProvider(self.capabilities, self.result), ExecutionProvider)

    def test_request_and_nested_values_are_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.request.objective = "different work"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.request.workspace.working_directory = "/elsewhere"
        self.assertIsInstance(self.request.context_refs, tuple)
        self.assertIsInstance(self.request.required_execution_features, frozenset)
        values = {field.name: getattr(self.request, field.name)
                  for field in dataclasses.fields(ExecutionRequest)}
        values["context_refs"] = ["CLAUDE.md"]
        values["required_execution_features"] = [ExecutionFeature.REPOSITORY_READ]
        normalized = ExecutionRequest(**values)
        self.assertEqual(("CLAUDE.md",), normalized.context_refs)
        self.assertEqual(frozenset({ExecutionFeature.REPOSITORY_READ}),
                         normalized.required_execution_features)

    def test_contract_has_no_workflow_authority(self):
        request_fields = {field.name for field in dataclasses.fields(ExecutionRequest)}
        result_fields = {field.name for field in dataclasses.fields(ExecutionResult)}
        forbidden = {
            "next_work", "work_queue", "authorize_product_execution", "claim_work",
            "set_operating_mode", "validation_route", "reviewer", "transition_jira",
            "update_lifecycle", "launch_executor", "swarm", "acceptance_result",
            "review_result", "product_failure", "select_another_ticket",
            "claim_another_ticket", "choose_self_qa_peer", "appoint_reviewer",
        }
        self.assertFalse(request_fields & forbidden)
        self.assertFalse(result_fields & forbidden)
        fake = FakeProvider(self.capabilities, self.result)
        for name in ("select_next_work", "select_another_ticket",
                     "authorize_product_execution", "claim", "claim_another_ticket",
                     "set_operating_mode", "transition_operating_mode",
                     "choose_validation_route", "choose_self_qa_peer",
                     "appoint_reviewer", "transition_jira", "launch_swarm"):
            self.assertFalse(hasattr(fake, name), name)

    def test_product_request_requires_existing_claim_and_lease(self):
        values = {field.name: getattr(self.request, field.name)
                  for field in dataclasses.fields(ExecutionRequest)}
        values["operating_mode"] = "PRODUCT_EXECUTION"
        with self.assertRaisesRegex(ValueError, "existing claim and execution lease"):
            ExecutionRequest(**values)

    def test_environment_and_validation_targets_pass_through_unchanged(self):
        fake = FakeProvider(self.capabilities, self.result)
        returned = fake.execute(self.request)
        self.assertIs(returned, self.result)
        self.assertIs(fake.requests[0], self.request)
        self.assertEqual(self.request.reported_environment, fake.requests[0].reported_environment)
        self.assertEqual(self.request.primary_target, fake.requests[0].primary_target)
        self.assertEqual(self.request.validation_targets, fake.requests[0].validation_targets)

    def test_unsupported_intent_and_features_fail_without_downgrade(self):
        cases = (
            ("supported_model_intents", frozenset({ModelIntent.COST_EFFICIENT}),
             FailureCode.UNSUPPORTED_MODEL),
            ("supported_reasoning_efforts", frozenset({ReasoningEffort.LOW}),
             FailureCode.UNSUPPORTED_EFFORT),
            ("execution_features", frozenset({ExecutionFeature.REPOSITORY_READ}),
             FailureCode.UNSUPPORTED_CAPABILITY),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                declared = dataclasses.replace(self.capabilities, **{field: value})
                outcome = FakeProvider(declared, self.result).execute(self.request)
                self.assertEqual(ExecutionStatus.PROVIDER_FAILED, outcome.status)
                self.assertEqual(expected, outcome.failure.code)
                self.assertIsNone(outcome.resolved_model_ref)
                self.assertIsNone(outcome.resolved_effort_ref)

    def test_all_normalized_provider_failures_are_distinct_from_execution_failure(self):
        for code in PROVIDER_FAILURE_CODES:
            with self.subTest(code=code):
                result = ExecutionResult(
                    invocation_id="inv-fail",
                    status=ExecutionStatus.PROVIDER_FAILED,
                    summary=code.value,
                    failure=Failure(code, code.value),
                )
                self.assertEqual(code, result.failure.code)
        execution = ExecutionResult(
            invocation_id="inv-execution-fail",
            status=ExecutionStatus.EXECUTION_FAILED,
            summary="the bounded execution failed",
            failure=Failure(FailureCode.EXECUTION_FAILURE, "test failed"),
        )
        self.assertNotIn(execution.failure.code, PROVIDER_FAILURE_CODES)
        with self.assertRaisesRegex(ValueError, "provider failure code"):
            ExecutionResult(
                invocation_id="bad",
                status=ExecutionStatus.PROVIDER_FAILED,
                summary="wrong domain",
                failure=Failure(FailureCode.EXECUTION_FAILURE, "wrong domain"),
            )

    def test_fake_has_no_external_or_workflow_dependencies(self):
        source = inspect.getsource(sys.modules[FakeProvider.__module__])
        for forbidden in ("subprocess", "agent.state", "integrations.jira", "claude", "codex"):
            self.assertNotIn(forbidden, source.lower())


class CurrentClaudeCharacterizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)

    def test_exact_current_roster_role_model_and_effort(self):
        binding_dir = os.path.join(ROOT, ".claude", "bindings")
        actual = {}
        for filename in sorted(os.listdir(binding_dir)):
            if filename.endswith(".yml"):
                seat = filename[:-4]
                actual[seat] = binding_fields(".claude/bindings/" + filename)
        self.assertEqual(self.fixture["seat_count"], len(actual))
        self.assertEqual(self.fixture["seats"], actual)
        self.assertEqual(20, sum(v["model"] == "opus" for v in actual.values()))
        self.assertEqual(6, sum(v["model"] == "sonnet" for v in actual.values()))
        self.assertEqual(21, sum(v["effort"] == "low" for v in actual.values()))
        self.assertEqual(5, sum(v["effort"] == "medium" for v in actual.values()))

    def test_prompt_contract_remains_in_current_source(self):
        contract = self.fixture["prompt_contract"]
        source = read(contract["source"])
        for phrase in contract["required_phrases"]:
            self.assertIn(phrase, source)

    def test_workspace_and_lease_expectations_remain_in_current_source(self):
        expected = self.fixture["workspace_and_lease"]
        worktrees = read(expected["worktree_source"])
        gate = read(expected["gate_source"])
        self.assertIn(expected["worktree_identity_phrase"], worktrees)
        self.assertIn(expected["gate_phrase"], gate)
        self.assertIn(expected["lease_open_phrase"], gate)
        self.assertIn(expected["lease_close_phrase"], gate)

    def test_current_return_behavior_remains_unstructured_and_direct(self):
        expected = self.fixture["return_behavior"]
        source = read(expected["source"])
        self.assertIn(expected["direct_phrase"], source)
        self.assertIn(expected["return_target"], source)
        self.assertIn(expected["fallback_phrase"], source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
