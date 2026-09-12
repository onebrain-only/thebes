#!/usr/bin/env python3
"""Migration Slice 4 — current Claude wake behind the provider seam."""

import inspect
import json
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution.claude import (  # noqa: E402
    ClaudeProvider,
    ClaudeWakeError,
    prepare_claude_wake,
)
from agent.execution.provider import (  # noqa: E402
    ExecutionFeature,
    ExecutionKind,
    ExecutionProvider,
    ExecutionRequest,
    ExecutionStatus,
    FailureCode,
    ExecutionTarget,
    ModelIntent,
    MutationMode,
    ReasoningEffort,
    ReportedEnvironment,
    ReturnContract,
    ValidationTarget,
    Workspace,
)
from agent.execution.wake import WakeOrderError, execute_product_wake  # noqa: E402


class RecordingTransport:
    def __init__(self, result=None, events=None):
        self.result = result if result is not None else object()
        self.wakes = []
        self.events = events

    def __call__(self, wake):
        if self.events is not None:
            self.events.append("transport")
        self.wakes.append(wake)
        return self.result


def request(**changes):
    values = dict(
        invocation_id="inv-claude-1",
        work_item_id="KAN-900",
        seat_id="backend-1",
        required_capability="backend",
        execution_kind=ExecutionKind.IMPLEMENTATION,
        objective=("## Context (carry forward)\n- settled architecture\n\n"
                   "Implement exactly KAN-900. Return evidence to qa."),
        role_contract_ref="agent/roles/backend.md",
        context_refs=("CLAUDE.md", "agent/CONTRACT.md", "agent/status/backend-1.md"),
        workspace=Workspace(
            repository_root="/repo",
            working_directory="/repo/.claude/worktrees/product/backend-1/KAN-900",
            worktree_path="/repo/.claude/worktrees/product/backend-1/KAN-900",
            expected_revision="abc123",
            mutation_mode=MutationMode.REPOSITORY_EDIT,
        ),
        allowed_surfaces=("supabase/migrations/kan-900.sql",),
        prohibited_actions=("select next work", "transition Jira", "launch another worker"),
        operating_mode="PRODUCT_EXECUTION",
        operating_mode_revision=7,
        claim_ref="claim:KAN-900",
        execution_lease_id="lease-900",
        reported_environment=ReportedEnvironment(
            "local", "flutter", "chrome", "reported:localhost"
        ),
        primary_target=ExecutionTarget(
            "local", "flutter", "chrome", "reported:localhost",
            browser_automation=False, launch_method="flutter-run"
        ),
        validation_targets=(
            ValidationTarget("local-chrome", "runtime", True, platform="chrome"),
            ValidationTarget("canary", "comparative", False, platform="web"),
        ),
        model_intent=ModelIntent.COST_EFFICIENT,
        reasoning_effort=ReasoningEffort.HIGH,
        required_execution_features=frozenset({
            ExecutionFeature.REPOSITORY_READ,
            ExecutionFeature.REPOSITORY_EDIT,
            ExecutionFeature.SHELL,
        }),
        timeout_seconds=900,
        return_contract=ReturnContract(
            "qa", ("changed files", "test output"), ("RESULT", "EVIDENCE")
        ),
    )
    values.update(changes)
    return ExecutionRequest(**values)


class ClaudeWakeCharacterizationTests(unittest.TestCase):
    def test_controller_instruction_routes_every_wake_through_selection_and_seam(self):
        path = os.path.join(ROOT, "agent", "skills", "route-to-seat", "SKILL.md")
        with open(path, encoding="utf-8") as fh:
            instruction = fh.read()
        self.assertIn("agent.execution.wake.execute_product_wake", instruction)
        self.assertIn("selects exactly one", instruction)
        self.assertIn("provider registry", instruction)
        self.assertIn("When the selector chooses Claude", instruction)
        self.assertIn("controller-native external\n`Agent` tool", instruction)
        self.assertIn("subagent_type=<seat>", instruction)
        self.assertIn("`ExecutionResult`", instruction)

    def test_exact_native_wake_and_request_order_are_preserved(self):
        original = request()
        wake = prepare_claude_wake(original, session_ref="existing-session")
        self.assertEqual("Agent", wake.native_tool)
        self.assertEqual("backend-1", wake.subagent_type)
        self.assertEqual((
            ("subagent_type", "backend-1"),
            ("prompt", original.objective),
        ), wake.native_arguments)
        self.assertEqual(original.objective, wake.prompt)
        self.assertEqual(original.role_contract_ref, wake.role_contract_ref)
        self.assertEqual(original.context_refs, wake.context_refs)
        self.assertEqual(original.workspace, wake.workspace)
        self.assertEqual(original.allowed_surfaces, wake.allowed_surfaces)
        self.assertEqual(original.prohibited_actions, wake.prohibited_actions)
        self.assertEqual(original.reported_environment, wake.reported_environment)
        self.assertEqual(original.primary_target, wake.primary_target)
        self.assertEqual(original.validation_targets, wake.validation_targets)
        self.assertEqual(original.return_contract, wake.return_contract)
        self.assertEqual("existing-session", wake.session_ref)

    def test_every_neutral_seat_maps_to_itself_with_current_model_and_effort(self):
        fixture_path = os.path.join(
            ROOT, "agent", "execution", "tests", "fixtures", "current_claude.json"
        )
        with open(fixture_path, encoding="utf-8") as fh:
            fixture = json.load(fh)["seats"]
        self.assertEqual(26, len(fixture))
        for seat, expected in sorted(fixture.items()):
            with self.subTest(seat=seat):
                wake = prepare_claude_wake(request(
                    seat_id=seat,
                    required_capability=expected["role"],
                    role_contract_ref="agent/roles/%s.md" % expected["role"],
                ))
                self.assertEqual(seat, wake.subagent_type)
                self.assertEqual(expected["model"], wake.model)
                self.assertEqual(expected["effort"], wake.effort)

    def test_binding_model_and_effort_override_no_current_defaults(self):
        wake = prepare_claude_wake(request())
        self.assertEqual("opus", wake.model)
        self.assertEqual("low", wake.effort)
        self.assertEqual(ModelIntent.COST_EFFICIENT, request().model_intent)
        self.assertEqual(ReasoningEffort.HIGH, request().reasoning_effort)

    def test_provider_calls_one_transport_and_normalizes_raw_text(self):
        raw = "current unstructured Claude return"
        transport = RecordingTransport(raw)
        provider = ClaudeProvider(transport)
        self.assertIsInstance(provider, ExecutionProvider)
        result = provider.execute(request())
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(raw, result.summary)
        self.assertEqual(1, len(transport.wakes))

    def test_neutral_seat_capability_and_role_are_not_provider_choices(self):
        with self.assertRaisesRegex(ClaudeWakeError, "unknown neutral Seat"):
            prepare_claude_wake(request(seat_id="backend-99"))
        with self.assertRaisesRegex(ClaudeWakeError, "has capability 'backend'"):
            prepare_claude_wake(request(required_capability="frontend"))
        with self.assertRaisesRegex(ClaudeWakeError, "Role contract must be"):
            prepare_claude_wake(request(role_contract_ref="agent/roles/frontend.md"))

    def test_reported_environment_and_core_targets_cannot_be_replaced(self):
        original = request()
        wake = prepare_claude_wake(original)
        self.assertEqual("reported:localhost", wake.reported_environment.environment_ref)
        self.assertEqual("reported:localhost", wake.primary_target.environment_ref)
        self.assertFalse(wake.primary_target.browser_automation)
        self.assertEqual("canary", wake.validation_targets[1].target_id)
        self.assertFalse(wake.validation_targets[1].required)

    def test_provider_owns_no_workflow_or_second_worker_operation(self):
        provider = ClaudeProvider(RecordingTransport())
        forbidden = (
            "select_next_work", "claim", "authorize_product_execution",
            "set_operating_mode", "choose_validation_route", "appoint_reviewer",
            "transition_jira", "launch_executor", "launch_second_worker", "swarm",
        )
        self.assertTrue(all(not hasattr(provider, name) for name in forbidden))
        source = inspect.getsource(sys.modules[ClaudeProvider.__module__]).lower()
        self.assertNotIn("agent.state.store", source)
        self.assertNotIn("jira", source)


class FakeStore:
    def __init__(self, events):
        self.events = events

    def assert_execution_permitted(self, work_item_id, seat_id):
        self.events.append("permission")
        return {"work_item_id": work_item_id,
                "ownership": {"seat_id": seat_id, "claim_ref": "claim:KAN-900"}}

    def open_execution_lease(self, work_item_id, seat_id, reason_ref):
        self.events.append("lease-open")
        return {"execution_lease_id": "lease-900", "mode_revision": 7,
                "revision": 1}

    def close_execution_lease(self, lease_id, revision, closed_by):
        self.events.append("lease-close")


class WakeOrderTests(unittest.TestCase):
    def test_permission_then_lease_then_request_then_transport_then_close(self):
        events = []
        store = FakeStore(events)
        raw = "bounded invocation returned"
        provider = ClaudeProvider(RecordingTransport(raw, events))

        def factory(task, lease):
            events.append("request")
            return request(
                claim_ref=task["ownership"]["claim_ref"],
                execution_lease_id=lease["execution_lease_id"],
                operating_mode_revision=lease["mode_revision"],
            )

        result = execute_product_wake(
            "KAN-900", "backend-1", "authorization:bounded", factory, (provider,),
            state_store=store
        )
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(raw, result.summary)
        self.assertEqual(
            ["permission", "lease-open", "request", "transport", "lease-close"],
            events,
        )

    def test_mismatched_lease_or_core_identity_never_reaches_transport(self):
        for field, value in (("execution_lease_id", "different"),
                             ("seat_id", "backend-2"),
                             ("claim_ref", "different"),
                             ("operating_mode_revision", 8)):
            with self.subTest(field=field):
                events = []
                store = FakeStore(events)
                transport = RecordingTransport(events=events)
                provider = ClaudeProvider(transport)

                def factory(task, lease, field=field, value=value):
                    events.append("request")
                    return request(**{field: value})

                with self.assertRaises(WakeOrderError):
                    execute_product_wake(
                        "KAN-900", "backend-1", "authorization:bounded", factory,
                        (provider,), state_store=store
                    )
                self.assertEqual([], transport.wakes)
                self.assertEqual("lease-close", events[-1])

    def test_lease_closes_when_external_transport_raises(self):
        events = []
        store = FakeStore(events)

        def failing_transport(wake):
            events.append("transport")
            raise RuntimeError("raw external failure")

        def factory(task, lease):
            events.append("request")
            return request()

        provider = ClaudeProvider(failing_transport)
        result = execute_product_wake(
            "KAN-900", "backend-1", "authorization:bounded", factory, (provider,),
            state_store=store
        )
        self.assertEqual(ExecutionStatus.PROVIDER_FAILED, result.status)
        self.assertEqual(FailureCode.EXECUTOR_PROCESS_FAILURE, result.failure.code)
        self.assertEqual("lease-close", events[-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
