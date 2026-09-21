#!/usr/bin/env python3
"""Migration Slice 4 — current Claude wake behind the provider seam."""

import inspect
import json
import os
import subprocess
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution.claude import standing_tools  # noqa: E402
from agent.execution.claude import (  # noqa: E402
    ClaudeProvider,
    ClaudeCliTransport,
    ClaudeWakeError,
    capabilities,
    prepare_claude_continuation_wake,
    prepare_claude_wake,
)
from agent.execution.brief import render_executor_brief  # noqa: E402
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
    def test_product_execution_capability_is_truthfully_foreground_only(self):
        constraints = capabilities().constraints
        self.assertIn("Product execution is foreground-only; observable async execution is unsupported",
                      constraints)

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
        expected_brief = render_executor_brief(original)
        self.assertEqual((
            ("subagent_type", "backend-1"),
            ("prompt", expected_brief),
        ), wake.native_arguments)
        self.assertEqual(expected_brief, wake.prompt)
        self.assertIn(original.objective, wake.prompt)
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
        self.assertEqual(27, len(fixture))
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


class ClaudeCliTransportTests(unittest.TestCase):
    def test_cli_transport_uses_print_json_workspace_and_request_timeout(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command, 0,
                '{"result":"safe result","is_error":false,"session_id":"s-1",'
                '"permission_denials":[]}', "",
            )

        transport = ClaudeCliTransport(runner=runner)
        wake = prepare_claude_wake(request(timeout_seconds=321))
        raw = transport(wake)
        command, kwargs = calls[0]
        self.assertEqual("claude", command[0])
        self.assertIn("--print", command)
        self.assertIn("--output-format", command)
        self.assertIn("dontAsk", command)
        self.assertEqual(wake.workspace.working_directory, kwargs["cwd"])
        self.assertEqual(321, kwargs["timeout"])
        self.assertEqual("completed", raw["status"])
        self.assertEqual("s-1", raw["continuation_ref"])

    def test_native_permission_denial_becomes_needs_input_not_a_bypass(self):
        transport = ClaudeCliTransport(runner=lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0,
            '{"result":"write denied","is_error":false,"session_id":"s-2",'
            '"permission_denials":["Edit(supabase/migration.sql)"]}', "",
        ))
        result = ClaudeProvider(transport).execute(prepare_request_for_cli())
        self.assertEqual(ExecutionStatus.NEEDS_INPUT, result.status)
        self.assertIn("native permission required", result.escalation.reason)
        self.assertEqual("s-2", result.continuation_ref)

    def test_approved_continuation_resumes_same_session_with_one_exact_tool(self):
        wake = prepare_claude_continuation_wake(
            request(), "claude-session-9", "mcp__claude_ai_Supabase__apply_migration")
        command = ClaudeCliTransport().command(wake)
        self.assertIn("--resume", command)
        self.assertEqual("claude-session-9", command[command.index("--resume") + 1])
        self.assertIn("--allowedTools", command)
        # Since the standing executor tool set exists, --allowedTools carries the
        # ordinary working tools PLUS this invocation's exact grant. The claim
        # that matters is unchanged and still asserted: the grant is present, it
        # is exact, and nothing beyond standing + granted appears.
        allowed = command[command.index("--allowedTools") + 1].split(",")
        self.assertIn("mcp__claude_ai_Supabase__apply_migration", allowed)
        self.assertEqual(set(), set(allowed) - set(standing_tools())
                         - {"mcp__claude_ai_Supabase__apply_migration"})
        self.assertNotIn("mcp__claude_ai_Supabase__apply_migration", standing_tools())
        self.assertIn("dontAsk", command)
        self.assertNotIn("bypassPermissions", command)
        self.assertIn("Continue the existing task", wake.prompt)
        with self.assertRaisesRegex(ClaudeWakeError, "exact permission"):
            prepare_claude_continuation_wake(request(), "claude-session-9", "*")

    def test_authorized_replacement_creates_the_exact_new_session_foreground(self):
        provider = ClaudeProvider(
            RecordingTransport("replacement complete"),
            session_id="23389001-2e1b-4791-aeac-2050254c1c4d",
            approved_permissions=("Bash", "mcp__claude_ai_Supabase__apply_migration"),
            authorized_execution=True,
        )
        result = provider.execute(request())
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        wake = provider._transport.wakes[0]
        command = ClaudeCliTransport().command(wake)
        self.assertIn("--session-id", command)
        self.assertEqual("23389001-2e1b-4791-aeac-2050254c1c4d",
                         command[command.index("--session-id") + 1])
        self.assertNotIn("--resume", command)
        self.assertIn("--allowedTools", command)
        allowed = command[command.index("--allowedTools") + 1].split(",")
        self.assertIn("mcp__claude_ai_Supabase__apply_migration", allowed)
        self.assertIn("Bash", allowed)
        self.assertEqual(set(), set(allowed) - set(standing_tools())
                         - {"Bash", "mcp__claude_ai_Supabase__apply_migration"})
        # Bash is standing now, so it must appear once rather than twice.
        self.assertEqual(1, allowed.count("Bash"))
        self.assertEqual("--", command[-2])
        self.assertEqual(render_executor_brief(request()), command[-1])
        self.assertEqual(render_executor_brief(request()), wake.prompt)

    def test_authorized_replacement_can_allocate_its_native_session_handle(self):
        provider = ClaudeProvider(
            RecordingTransport("replacement complete"),
            approved_permissions=("Bash", "mcp__claude_ai_Supabase__apply_migration"),
            authorized_execution=True,
        )
        result = provider.execute(request())
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        wake = provider._transport.wakes[0]
        command = ClaudeCliTransport().command(wake)
        self.assertNotIn("--session-id", command)
        self.assertNotIn("--resume", command)
        self.assertEqual(render_executor_brief(request()), wake.prompt)

    def test_composed_exact_grants_are_finite_and_reject_unapproved_third_tool(self):
        grants = ("Bash(python3 -c 'resume()')", "mcp__example__write")
        wake = prepare_claude_continuation_wake(request(), "claude-session-9", grants)
        command = ClaudeCliTransport().command(wake)
        position = command.index("--allowedTools")
        allowed = command[position + 1].split(",")
        # Finite and exact is still the claim: standing working tools, plus these
        # two grants, and nothing else. A third tool nobody approved does not
        # appear, which is the assertion this test exists for.
        self.assertEqual(set(), set(allowed) - set(standing_tools()) - set(grants))
        for grant in grants:
            self.assertIn(grant, allowed)
        self.assertEqual("--", command[position + 2])
        self.assertEqual(wake.prompt, command[position + 3])
        self.assertEqual(grants, wake.approved_permissions)
        self.assertNotIn("mcp__example__third", command)
        with self.assertRaisesRegex(ClaudeWakeError, "exact permission"):
            prepare_claude_continuation_wake(
                request(), "claude-session-9", grants + ("mcp__example__*",))


def prepare_request_for_cli():
    return request()


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

    def record_execution_receipt(self, invocation_id, work_item_id, seat_id,
                                 execution_lease_id, normalized_result,
                                 provider_selection=None):
        self.events.append("receipt")


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
            ["permission", "lease-open", "request", "transport", "receipt", "lease-close"],
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


# ---------------------------------------------------------------------------
# A scoped grant must be resumable. The wake compared against
# "permission(allowed_operation)" while controller.resume built the provider
# from the bare "permission", so narrowing a grant to one exact operation — the
# safer thing to do — made its continuation permanently unresumable. The defect
# punished precision and rewarded breadth, which is why an unscoped Phase-2 run
# never hit it. One renderer now serves both sides.

class GrantedPermissionRendering(unittest.TestCase):
    def test_an_unscoped_grant_renders_as_the_bare_permission(self):
        from agent.execution.wake import granted_permissions
        self.assertEqual(("Bash",), granted_permissions([{"permission": "Bash"}]))
        self.assertEqual(("Bash",),
                         granted_permissions([{"permission": "Bash",
                                               "allowed_operation": None}]))

    def test_a_scoped_grant_renders_with_its_exact_operation(self):
        from agent.execution.wake import granted_permissions
        self.assertEqual(
            ("mcp__x__execute_sql(read-only SELECT)",),
            granted_permissions([{"permission": "mcp__x__execute_sql",
                                  "allowed_operation": "read-only SELECT"}]))

    def test_the_controller_and_the_wake_render_identically(self):
        # The two callers that diverged. If this ever fails again, a scoped
        # approval has become unresumable for the same reason as before.
        import inspect
        from agent.execution import wake
        from agent import controller
        self.assertIn("granted_permissions", inspect.getsource(controller.resume))
        source = inspect.getsource(controller.resume)
        self.assertNotIn('record["permission"] for record in approvals', source)
        self.assertTrue(callable(wake.granted_permissions))

    def test_mixed_grants_keep_their_order_and_their_scoping(self):
        from agent.execution.wake import granted_permissions
        self.assertEqual(
            ("Write", "Bash(ls -la)"),
            granted_permissions([{"permission": "Write"},
                                 {"permission": "Bash", "allowed_operation": "ls -la"}]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
