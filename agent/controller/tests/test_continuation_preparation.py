#!/usr/bin/env python3
"""Continuation preparation from a needs-input result.

The REAL `agent/state/store.py` runs against a temp runtime, so the
preparation writer's identity, session and permission-boundary checks are the
canonical ones. Git is synthetic, Jira and the providers are doubles. No real
Jira, Product repository or Supabase is reachable.
"""

import copy
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                        # noqa: E402

from agent.controller import execute                                # noqa: E402
from agent.controller.continuation import (                         # noqa: E402
    continuable, denied_permissions, prepare, preparation_scope,
)
from agent.controller.workspace import conclude_workspace, realize_workspace  # noqa: E402
from agent.controller.tests.test_canonical_intent import Authorization  # noqa: E402
from agent.controller.tests.test_entry import no_validation          # noqa: E402
from agent.controller.tests.test_validation_dispatch import (        # noqa: E402
    BACKEND_DEV, SEATS, Jira, _Roster, isolated_runtime, make_task,
)
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402
from agent.execution.brief import CONTROL_PLANE_TOKENS, render_executor_brief  # noqa: E402
from agent.execution.provider import (                               # noqa: E402
    ExecutionFeature, ExecutionResult, ExecutionStatus, EscalationRequirement,
    ModelIntent, ProviderCapabilities, ReasoningEffort,
)


DENIAL_REASON = (
    "Claude Code native permission required: "
    "{'tool_name': 'mcp__claude_ai_Supabase__execute_sql', 'tool_use_id': 'toolu_1'}; "
    "{'tool_name': 'Bash', 'tool_use_id': 'toolu_2'}; "
    "{'tool_name': 'Write', 'tool_use_id': 'toolu_3'}")
SESSION = "8a55a5ae-92dc-4fc7-bc5c-6a44f79d2da4"


class NeedsInputProvider:
    """A provider double that stops at a native permission boundary."""

    def __init__(self, status=ExecutionStatus.NEEDS_INPUT, reason=DENIAL_REASON,
                 session=SESSION):
        self.status, self.reason, self.session = status, reason, session
        self.requests = []

    def capabilities(self):
        return ProviderCapabilities(
            provider_id="claude-code", available=True,
            execution_features=frozenset(ExecutionFeature),
            supported_reasoning_efforts=frozenset(ReasoningEffort),
            supported_model_intents=frozenset(ModelIntent))

    def execute(self, request):
        self.requests.append(request)
        if self.status is ExecutionStatus.NEEDS_INPUT:
            return ExecutionResult(
                invocation_id=request.invocation_id, status=self.status,
                summary="blocked at the permission boundary",
                provider_id="claude-code", continuation_ref=self.session,
                escalation=EscalationRequirement(self.reason, "CEO"))
        return ExecutionResult(
            invocation_id=request.invocation_id, status=ExecutionStatus.COMPLETED,
            summary="done", provider_id="claude-code", continuation_ref=self.session)


class PreparationTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_tmp = isolated_runtime()
        self.addCleanup(shutil.rmtree, self.runtime_tmp, ignore_errors=True)
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run(self, provider=None, work_item_id="KAN-900"):
        provider = provider or NeedsInputProvider()

        def allocator(item, seat_id, workspace):
            return realize_workspace(item, seat_id,
                                     dict(workspace, repository_root=self.repo),
                                     root=self.wtroot)

        def concluder(item, seat_id, result, task_record, realized, integration=None):
            return conclude_workspace(item, seat_id, result, task_record, realized,
                                      root=self.wtroot, integration=integration)

        outcome = execute(work_item_id, None, authorization=Authorization(),
                          state_store=store, jira_client=Jira(), seat_registry=_Roster(),
                          providers=(provider,), workspace_allocator=allocator,
                          workspace_concluder=concluder, interventions=[],
                          worktree_root=self.wtroot, seats_by_capability=SEATS,
                          validator=no_validation)
        return outcome, provider


class BoundaryReadingTests(PreparationTestCase):
    def test_every_denied_tool_is_read_in_order_without_duplicates(self):
        receipt = {"status": "needs_input", "provider_id": "claude-code",
                   "normalized_result": {"continuation_ref": SESSION,
                                         "escalation": {"reason": DENIAL_REASON}}}
        self.assertEqual(("mcp__claude_ai_Supabase__execute_sql", "Bash", "Write"),
                         denied_permissions(receipt))
        self.assertTrue(continuable(receipt))

    def test_nothing_terminal_or_sessionless_is_continuable(self):
        base = {"status": "needs_input", "provider_id": "claude-code",
                "normalized_result": {"continuation_ref": SESSION,
                                      "escalation": {"reason": DENIAL_REASON}}}
        cases = {
            "completed": dict(base, status="completed"),
            "provider failure": dict(base, status="provider_failed"),
            "execution failure": dict(base, status="execution_failed"),
            "another provider": dict(base, provider_id="codex-cli"),
            "no session": dict(base, normalized_result={
                "continuation_ref": None, "escalation": {"reason": DENIAL_REASON}}),
            "no named permission": dict(base, normalized_result={
                "continuation_ref": SESSION,
                "escalation": {"reason": "something went wrong"}}),
            "malformed": "not a receipt",
        }
        for name, receipt in cases.items():
            with self.subTest(case=name):
                self.assertFalse(continuable(receipt))


class PreparationFromExecutionTests(PreparationTestCase):
    def test_a_needs_input_execution_prepares_a_bound_continuation(self):
        make_task()
        outcome, provider = self._run()
        self.assertEqual("needs_input", outcome["execution_status"])
        prepared_id = outcome["continuation_prepared"]
        self.assertTrue(prepared_id.startswith("continuation-"), prepared_id)

        record = store.read_execution_continuation_preparation(outcome["invocation_id"])
        self.assertIsNotNone(record)
        # 2-5: exact work item, workspace, session and receipt lineage.
        self.assertEqual("KAN-900", record["work_item_id"])
        self.assertEqual("backend-1", record["seat_id"])
        self.assertEqual("claude-code", record["provider_id"])
        self.assertEqual(SESSION, record["claude_session_id"])
        self.assertEqual(outcome["workspace_path"], record["worktree_path"])
        self.assertEqual(outcome["workspace_path"], record["working_directory"])
        self.assertEqual(self.repo, record["repository_root"])
        self.assertEqual("exec/backend-1/KAN-900", record["branch"])
        self.assertEqual(outcome["expected_revision"], record["expected_revision"])
        self.assertEqual(outcome["invocation_id"], record["original_invocation_id"])
        original = store.read_execution_receipt(outcome["invocation_id"])
        self.assertEqual(original["execution_receipt_id"], record["original_receipt_id"])
        self.assertEqual("needs_input", original["status"])
        # The boundary that caused it, and the canonical route to come back to.
        self.assertEqual("mcp__claude_ai_Supabase__execute_sql", record["permission"])
        self.assertEqual("peer", record["validation_route"])
        self.assertEqual("backend", record["required_capability"])
        self.assertFalse(record["historical_request_persisted"])
        self.assertIn("Bash", record["authorization_scope"])
        self.assertIn("Write", record["authorization_scope"])

    def test_the_workspace_is_preserved_for_the_prepared_continuation(self):
        make_task()
        outcome, _ = self._run()
        self.assertEqual("preserved", outcome["workspace_status"])
        self.assertIn("continuation", outcome["workspace_reason"])
        self.assertTrue(os.path.isdir(outcome["workspace_path"]))
        record = store.read_execution_continuation_preparation(outcome["invocation_id"])
        self.assertTrue(os.path.isdir(record["worktree_path"]))

    def test_a_completed_execution_prepares_nothing(self):
        make_task()
        outcome, _ = self._run(NeedsInputProvider(status=ExecutionStatus.COMPLETED))
        self.assertEqual("completed", outcome["execution_status"])
        self.assertIsNone(outcome["continuation_prepared"])
        self.assertIsNone(
            store.read_execution_continuation_preparation(outcome["invocation_id"]))
        self.assertEqual([], store.read_all("execution_continuation_preparation"))

    def test_a_needs_input_with_no_named_permission_is_not_continuable(self):
        make_task()
        outcome, _ = self._run(NeedsInputProvider(reason="the run was interrupted"))
        self.assertEqual("needs_input", outcome["execution_status"])
        self.assertEqual("not-continuable", outcome["continuation_prepared"])
        self.assertEqual([], store.read_all("execution_continuation_preparation"))

    def test_the_executor_never_sees_the_continuation_machinery(self):
        make_task()
        outcome, provider = self._run()
        brief = render_executor_brief(provider.requests[0])
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), brief.lower())
        for internal in ("continuation", "execution_continuation_id", SESSION,
                         outcome["continuation_prepared"]):
            self.assertNotIn(str(internal).lower(), brief.lower())


class PreparationRefusalTests(PreparationTestCase):
    def _needs_input_state(self):
        make_task()
        outcome, _ = self._run()
        return outcome, store.read_execution_receipt(outcome["invocation_id"])

    def test_a_foreign_receipt_cannot_prepare_this_work_item(self):
        outcome, receipt = self._needs_input_state()
        make_task("KAN-901", owner="backend-2")
        realized = realize_workspace("KAN-901", "backend-2",
                                     {"repository_root": self.repo,
                                      "working_directory": None, "worktree_path": None,
                                      "expected_revision": None,
                                      "mutation_mode": "repository_edit"},
                                     root=self.wtroot)
        before = copy.deepcopy(store.read("task", "KAN-901"))
        with self.assertRaises(store.StateError) as caught:
            prepare("KAN-901", "backend-2", receipt, realized, "ref", store)
        self.assertIn("does not match original execution", str(caught.exception))
        self.assertEqual(before, store.read("task", "KAN-901"))
        self.assertIsNone(
            store.read_execution_continuation_preparation(outcome["invocation_id"]) and None)

    def test_a_wrong_seat_is_rejected(self):
        _, receipt = self._needs_input_state()
        realized = realize_workspace("KAN-900", "backend-2",
                                     {"repository_root": self.repo,
                                      "working_directory": None, "worktree_path": None,
                                      "expected_revision": None,
                                      "mutation_mode": "repository_edit"},
                                     root=self.wtroot)
        with self.assertRaises(store.StateError) as caught:
            prepare("KAN-900", "backend-2", receipt, realized, "ref", store)
        self.assertIn("original active claim", str(caught.exception))

    def test_a_session_that_does_not_match_the_receipt_is_rejected(self):
        outcome, receipt = self._needs_input_state()
        realized = {"repository_root": self.repo, "path": outcome["workspace_path"],
                    "branch": "exec/backend-1/KAN-900",
                    "expected_revision": outcome["expected_revision"],
                    "workspace": {"working_directory": outcome["workspace_path"]}}
        forged = copy.deepcopy(receipt)
        forged["normalized_result"]["continuation_ref"] = "not-the-session"
        with self.assertRaises(store.StateError) as caught:
            prepare("KAN-900", "backend-1", forged, realized, "ref", store)
        self.assertIn("session does not match", str(caught.exception))

    def test_preparing_twice_is_idempotent_not_duplicated(self):
        outcome, receipt = self._needs_input_state()
        realized = {"repository_root": self.repo, "path": outcome["workspace_path"],
                    "branch": "exec/backend-1/KAN-900",
                    "expected_revision": outcome["expected_revision"],
                    "workspace": {"working_directory": outcome["workspace_path"]}}
        again = prepare("KAN-900", "backend-1", receipt, realized,
                        "CEO fixture authorization KAN-900", store)
        self.assertEqual(outcome["continuation_prepared"],
                         again["execution_continuation_id"])
        self.assertEqual(1, len(store.read_all("execution_continuation_preparation")))

    def test_the_scope_names_every_refused_permission(self):
        scope = preparation_scope("KAN-900", ("Write", "Bash"))
        self.assertIn("KAN-900", scope)
        self.assertIn("Write", scope)
        self.assertIn("Bash", scope)
        self.assertIn("same workspace", scope)


class RealSystemsUntouchedTests(PreparationTestCase):
    def test_this_suite_never_reached_the_real_runtime_or_repository(self):
        self.assertNotIn(os.path.join("agent", "state", "runtime"), store.RUNTIME)
        real = os.path.join(ROOT, "Dabbler", "dabbler-code")
        if not os.path.isdir(real):
            self.skipTest("the real Product checkout is not present")
        listed = subprocess.run(["git", "-C", real, "worktree", "list"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("KAN-900", listed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
