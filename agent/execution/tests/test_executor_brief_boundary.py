#!/usr/bin/env python3
"""EXECUTOR BRIEF BOUNDARY — the executor never orchestrates its own execution.

Deterministic FLOW proof. No Product repository, Jira, Supabase or network is
touched: the store is the existing in-memory ``FakeStore`` double and the
provider transports are the existing recording doubles.
"""

import dataclasses
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agent.execution.brief import (  # noqa: E402
    CONTROL_PLANE_FIELDS,
    CONTROL_PLANE_TOKENS,
    PRODUCT_BRIEF_FIELDS,
    ExecutorBriefViolation,
    assert_no_control_plane_concept,
    assert_product_scoped,
    render_executor_brief,
)
from agent.execution.claude import ClaudeProvider, prepare_claude_wake  # noqa: E402
from agent.execution.codex import CodexProvider, prepare_codex_invocation  # noqa: E402
from agent.execution.provider import (  # noqa: E402
    ExecutionRequest, ExecutionStatus,
)
from agent.execution.wake import (  # noqa: E402
    WakeOrderError, build_prepared_continuation_request, execute_product_wake,
)
from test_claude_wake import FakeStore, RecordingTransport, request  # noqa: E402


CONTROL_PLANE_OBJECTIVES = {
    "self_invocation": "Implement KAN-900, then launch another Claude session to continue.",
    "self_resume": "Implement KAN-900. If you run out of permission, resume yourself.",
    "continuation_driver": "Implement KAN-900 and then invoke the continuation driver.",
    "continuation_identifier": ("Implement KAN-900, then call "
                               "execute_approved_claude_continuation with the approval id."),
    "lease_orchestration": "Implement KAN-900 after you open an execution lease for it.",
    "claim_orchestration": "Claim the work item first, then implement KAN-900.",
    "provider_selection": "Implement KAN-900 and select another provider if Claude stalls.",
    "provider_override": "Implement KAN-900 using the provider override registry.",
    "controller_bootstrap": "Implement KAN-900, but run the controller bootstrap first.",
    "controller_import": "Implement KAN-900 by running python3 -m agent.controller first.",
    "session_mechanics": "Implement KAN-900 and create a new session for the follow-up.",
    "jira_orchestration": "Implement KAN-900, then transition the Jira ticket to QA-Test.",
    "next_work_item": "Implement KAN-900 and then select the next work item from the queue.",
    "reviewer_appointment": "Implement KAN-900 and appoint a peer reviewer for it.",
    "validation_route": "Implement KAN-900 and choose the validation route that fits.",
}


class CanonicalBriefTests(unittest.TestCase):
    """1-4: one Product-only brief, built from canonical request state."""

    def test_normal_request_produces_one_product_only_brief(self):
        original = request()
        before = dataclasses.asdict(original)
        brief = render_executor_brief(original)
        self.assertTrue(brief.startswith("# Thebes Product Execution Brief"))
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), brief.lower())
        # The request is evidence, not a mutable buffer.
        self.assertEqual(before, dataclasses.asdict(original))

    def test_product_objective_and_context_survive(self):
        original = request()
        brief = render_executor_brief(original)
        self.assertIn(original.objective, brief)
        for reference in original.context_refs:
            self.assertIn(reference, brief)
        self.assertIn(original.role_contract_ref, brief)
        for surface in original.allowed_surfaces:
            self.assertIn(surface, brief)
        for section in original.return_contract.required_sections:
            self.assertIn(section, brief)
        self.assertIn(original.return_contract.return_to, brief)
        self.assertIn(original.validation_targets[0].target_id, brief)
        self.assertIn(original.reported_environment.environment_ref, brief)

    def test_work_item_capability_and_workspace_binding_survive(self):
        original = request()
        brief = render_executor_brief(original)
        self.assertIn("- Work item ID: %s" % original.work_item_id, brief)
        self.assertIn("- Required capability: %s" % original.required_capability, brief)
        self.assertIn("- Repository root: %s" % original.workspace.repository_root, brief)
        self.assertIn("- Working directory: %s" % original.workspace.working_directory, brief)
        self.assertIn("- Expected revision: %s" % original.workspace.expected_revision, brief)
        self.assertIn("- Mutation mode: %s" % original.workspace.mutation_mode.value, brief)

    def test_controller_only_fields_have_no_rendering_path(self):
        # Structural, not textual: the builder reads a closed field allowlist.
        self.assertEqual(set(), set(PRODUCT_BRIEF_FIELDS) & set(CONTROL_PLANE_FIELDS))
        declared = set(field.name for field in dataclasses.fields(ExecutionRequest))
        self.assertEqual(declared, set(PRODUCT_BRIEF_FIELDS) | set(CONTROL_PLANE_FIELDS))
        source = open(os.path.join(ROOT, "agent", "execution", "brief.py"),
                      encoding="utf-8").read()
        rendering = source[source.index("def render_executor_brief"):]
        for field in CONTROL_PLANE_FIELDS:
            self.assertNotIn("request.%s" % field, rendering, field)
        brief = render_executor_brief(request())
        for withheld in ("inv-claude-1", "claim:KAN-900", "lease-900", "PRODUCT_EXECUTION"):
            self.assertNotIn(withheld, brief)


class ControlPlaneFirewallTests(unittest.TestCase):
    """5-7: an executor brief that orchestrates is refused before dispatch."""

    def test_every_control_plane_objective_is_rejected(self):
        for name, objective in CONTROL_PLANE_OBJECTIVES.items():
            with self.subTest(objective=name):
                with self.assertRaises(ExecutorBriefViolation):
                    assert_product_scoped(request(objective=objective))

    def test_self_continuation_provider_and_lease_categories_are_named(self):
        cases = {
            "self_invocation": "executor_self_invocation",
            "continuation_driver": "continuation_driver",
            "continuation_identifier": "control_plane_identifier",
            "lease_orchestration": "lease_or_claim_orchestration",
            "claim_orchestration": "lease_or_claim_orchestration",
            "provider_selection": "provider_selection",
            "controller_bootstrap": "controller_bootstrap",
            "session_mechanics": "session_mechanics",
            "jira_orchestration": "jira_orchestration",
        }
        for name, category in cases.items():
            with self.subTest(case=name):
                try:
                    assert_product_scoped(request(objective=CONTROL_PLANE_OBJECTIVES[name]))
                except ExecutorBriefViolation as exc:
                    self.assertEqual(category, exc.category)
                    self.assertEqual("objective", exc.field)
                else:
                    self.fail("%s was not refused" % name)

    def test_a_rejected_brief_is_never_rendered(self):
        for objective in CONTROL_PLANE_OBJECTIVES.values():
            with self.assertRaises(ExecutorBriefViolation):
                render_executor_brief(request(objective=objective))

    def test_internal_identifiers_are_refused_even_inside_a_prohibition(self):
        # KAN-186: a prohibition that names the continuation driver still puts
        # the driver's name in the executor's prompt.
        leaky = request(prohibited_actions=(
            "launch another executor", "do not call execute_approved_claude_continuation"))
        with self.assertRaises(ExecutorBriefViolation) as caught:
            assert_product_scoped(leaky)
        self.assertEqual("control_plane_identifier", caught.exception.category)
        self.assertTrue(caught.exception.field.startswith("prohibited_actions"))

    def test_plain_product_prohibitions_remain_legal(self):
        allowed = request(prohibited_actions=(
            "select next work item", "transition Jira lifecycle", "launch another executor"))
        self.assertIs(allowed, assert_product_scoped(allowed))
        self.assertIn("- transition Jira lifecycle", render_executor_brief(allowed))

    def test_context_surfaces_and_return_contract_are_also_firewalled(self):
        for field, changes in (
            ("context_refs", {"context_refs": ("CLAUDE.md", "resume yourself after approval")}),
            ("validation_targets", {"validation_targets": (dataclasses.replace(
                request().validation_targets[0],
                target_id="after passing, transition the ticket to Done"),)}),
            ("return_contract.required_sections",
             {"return_contract": dataclasses.replace(
                 request().return_contract,
                 required_sections=("RESULT", "then transition the ticket to Done"))}),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ExecutorBriefViolation) as caught:
                    assert_product_scoped(request(**changes))
                self.assertTrue(caught.exception.field.startswith(field.split(".")[0]))


class FirewalledDispatchTests(unittest.TestCase):
    """8-10: the provider boundary, the result and the durable semantics."""

    def setUp(self):
        self.events = []
        self.store = FakeStore(self.events)

    def _factory(self, objective=None):
        def factory(task, lease):
            self.events.append("request")
            changes = {} if objective is None else {"objective": objective}
            return request(
                claim_ref=task["ownership"]["claim_ref"],
                execution_lease_id=lease["execution_lease_id"],
                operating_mode_revision=lease["mode_revision"],
                **changes
            )
        return factory

    def _execute(self, providers, objective=None, override=None):
        return execute_product_wake(
            "KAN-900", "backend-1", "authorization:bounded", self._factory(objective),
            providers, provider_override=override, state_store=self.store,
        )

    def test_claude_provider_receives_the_sanitized_bounded_brief(self):
        transport = RecordingTransport("Claude normalized")
        result = self._execute((ClaudeProvider(transport),))
        wake = transport.wakes[0]
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(1, len(transport.wakes))
        self.assertEqual(render_executor_brief(request()), wake.prompt)
        self.assertEqual(wake.prompt, dict(wake.native_arguments)["prompt"])
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), wake.prompt.lower())
        # Thebes still binds claim, lease and seat — outside the prompt.
        self.assertEqual("claim:KAN-900", wake.claim_ref)
        self.assertEqual("lease-900", wake.execution_lease_id)
        self.assertEqual("backend-1", wake.subagent_type)

    def test_normalized_execution_result_still_returns(self):
        transport = RecordingTransport({
            "status": "completed", "summary": "Product work complete",
            "changed_files": [{"path": "supabase/migrations/kan-900.sql"}],
            "tests": [{"command": "flutter test", "status": "passed", "exit_code": 0}],
        })
        result = self._execute((ClaudeProvider(transport),))
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual("claude-code", result.provider_id)
        self.assertEqual("inv-claude-1", result.invocation_id)
        self.assertEqual("supabase/migrations/kan-900.sql", result.changed_files[0].path)
        self.assertEqual("passed", result.tests[0].status.value)

    def test_receipt_and_lease_ordering_is_unchanged(self):
        transport = RecordingTransport("Claude normalized", self.events)
        self._execute((ClaudeProvider(transport),))
        self.assertEqual(
            ["permission", "lease-open", "request", "transport", "receipt", "lease-close"],
            self.events,
        )

    def test_a_leaking_request_is_refused_before_any_provider_runs(self):
        transport = RecordingTransport("must not run", self.events)
        with self.assertRaises(WakeOrderError) as caught:
            self._execute((ClaudeProvider(transport),),
                          objective=CONTROL_PLANE_OBJECTIVES["continuation_identifier"])
        self.assertIn("control-plane instruction", str(caught.exception))
        self.assertEqual([], transport.wakes)
        # The lease still closes; no receipt is written for work never dispatched.
        self.assertEqual(["permission", "lease-open", "request", "lease-close"], self.events)

    def test_the_firewall_is_provider_independent(self):
        codex = RecordingTransport("must not run", self.events)
        with self.assertRaises(WakeOrderError):
            self._execute((CodexProvider(codex),),
                          objective=CONTROL_PLANE_OBJECTIVES["provider_selection"],
                          override="codex-cli")
        self.assertEqual([], codex.wakes)


class ThebesRetainsAuthorityTests(unittest.TestCase):
    """11-12: continuation stays Thebes-side and nothing Product is mutated."""

    def test_prepared_continuation_request_is_product_scoped(self):
        preparation = {
            "historical_request_persisted": False,
            "execution_continuation_id": "cont-1", "work_item_id": "KAN-900",
            "seat_id": "backend-1", "required_capability": "backend",
            "repository_root": "/repo", "working_directory": "/repo/wt",
            "worktree_path": "/repo/wt", "expected_revision": "abc123",
            "validation_route": "peer",
        }
        task = {"surfaces": ["supabase/migrations/kan-900.sql"],
                "ownership": {"claim_ref": "claim:KAN-900"}}
        lease = {"mode_revision": 7, "execution_lease_id": "lease-900"}
        prepared = build_prepared_continuation_request(preparation, task, lease)
        self.assertIs(prepared, assert_product_scoped(prepared))
        brief = render_executor_brief(prepared)
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), brief.lower())
        # Thebes keeps the control-plane bindings on the request itself.
        self.assertEqual("lease-900", prepared.execution_lease_id)
        self.assertEqual("claim:KAN-900", prepared.claim_ref)
        self.assertEqual("PRODUCT_EXECUTION", prepared.operating_mode)

    def test_continuation_wake_still_carries_its_granted_capabilities(self):
        provider = ClaudeProvider(
            RecordingTransport("continued"), session_ref="claude-session-9",
            approved_permissions=("mcp__claude_ai_Supabase__apply_migration",),
        )
        result = provider.execute(request())
        wake = provider._transport.wakes[0]
        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertIn("Continue the existing task", wake.prompt)
        self.assertIn("mcp__claude_ai_Supabase__apply_migration", wake.prompt)
        self.assertIn(request().objective, wake.prompt)
        self.assertEqual("claude-session-9", wake.session_ref)

    def test_the_boundary_holds_without_product_jira_or_supabase_access(self):
        # The brief builder is pure text: it reaches no store, board or network.
        with open(os.path.join(ROOT, "agent", "execution", "brief.py"),
                  encoding="utf-8") as handle:
            imports = [line.strip() for line in handle
                       if line.startswith(("import ", "from "))]
        self.assertEqual(["import re"], imports)
        # Both providers prepare the identical brief without leaving the process.
        wake = prepare_claude_wake(request())
        invocation = prepare_codex_invocation(request())
        self.assertEqual(wake.prompt, invocation.prompt)


class ProviderSelectionPhrasing(unittest.TestCase):
    """An adjective must not be a way through the provider-selection rule.

    "select a different provider" leaked until the final operations smoke proof
    probed it: the pattern allowed a determiner but no adjective, so the single
    most natural phrasing of the prohibited instruction was the one that passed.
    """

    LEAKS = (
        "select a different provider",
        "choose another execution provider",
        "switch to a faster provider",
        "pick a more capable provider",
        "override the currently selected provider",
        "fall back to the other provider",
    )

    ORDINARY_ENGLISH = (
        "the provider of these figures is the finance team",
        "a provider network outage is the cause",
        "document who the data provider is",
    )

    def test_every_phrasing_of_provider_selection_is_refused(self):
        for text in self.LEAKS:
            with self.assertRaises(ExecutorBriefViolation, msg=text):
                assert_no_control_plane_concept(text, "objective")

    def test_ordinary_uses_of_the_word_provider_still_pass(self):
        for text in self.ORDINARY_ENGLISH:
            assert_no_control_plane_concept(text, "objective")


class NegatedReportPhrasing(unittest.TestCase):
    """A report of an act NOT done is evidence, not an instruction to do it.

    KAN-367's SELF review was refused because the executor's own report, quoted
    into the reviewer objective, said "no Jira transition was made". Only a
    negator directly before the phrase exempts it; a negator elsewhere in the
    sentence, or cut off by punctuation, must not open a way through.
    """

    NEGATED = (
        "Nothing is committed and no Jira transition was made.",
        "No Jira transition performed; no claim, no wake.",
        "The executor did not transition the Jira ticket.",
        "Scope: never transition this ticket from inside a worker.",
        "Finished without any Jira workflow change.",
    )

    STILL_INSTRUCTIONS = (
        "Don't forget to transition the Jira ticket to QA-Test.",
        "No problem — transition the Jira ticket afterwards.",
        "No, transition the ticket now.",
        "Implement KAN-900, then transition the Jira ticket to QA-Test.",
        "It is not hard: select the next work item when done.",
    )

    def test_a_negated_report_passes(self):
        for text in self.NEGATED:
            assert_no_control_plane_concept(text, "objective")

    def test_a_negator_elsewhere_does_not_exempt_an_instruction(self):
        for text in self.STILL_INSTRUCTIONS:
            with self.assertRaises(ExecutorBriefViolation, msg=text):
                assert_no_control_plane_concept(text, "objective")


if __name__ == "__main__":
    unittest.main(verbosity=2)
