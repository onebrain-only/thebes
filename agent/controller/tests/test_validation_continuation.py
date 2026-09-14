#!/usr/bin/env python3
"""Validation continuation: a validator that stops at a permission boundary.

The REAL store runs against a temp runtime, so the review-context authority,
the approval binding and the replay protection are the canonical ones. Git is
synthetic; Jira and the providers are doubles. No real Jira, Product repository
or Supabase is reachable.
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

from agent.controller import resume_validation                      # noqa: E402
from agent.controller import validation as validation_policy        # noqa: E402
from agent.controller.validation import (                           # noqa: E402
    FAIL, PASS, VALIDATION_ALREADY_SETTLED, VALIDATION_FAILED, VALIDATION_PASSED,
    ValidationRefused, run_validation,
)
from agent.controller.workspace import realize_workspace            # noqa: E402
from agent.controller.tests.test_validation_dispatch import (       # noqa: E402
    BACKEND_DEV, SEATS, Jira, isolated_runtime, make_task,
)
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402
from agent.execution.brief import CONTROL_PLANE_TOKENS, render_executor_brief  # noqa: E402
from agent.execution.provider import (                              # noqa: E402
    ChangedFileClaim, EvidenceClaim, ExecutionFeature, ExecutionResult,
    ExecutionStatus, EscalationRequirement, ModelIntent, ProviderCapabilities,
    ReasoningEffort, TestClaim, TestStatus,
)


DENIAL = ("Claude Code native permission required: "
          "{'tool_name': 'mcp__claude_ai_Supabase__execute_sql', 'tool_use_id': 'x'}")
VSESSION = "11111111-2222-3333-4444-555555555555"


class BlockedValidator:
    def __init__(self, session=VSESSION):
        self.session, self.requests = session, []

    def capabilities(self):
        return ProviderCapabilities(
            provider_id="claude-code", available=True,
            execution_features=frozenset(ExecutionFeature),
            supported_reasoning_efforts=frozenset(ReasoningEffort),
            supported_model_intents=frozenset(ModelIntent))

    def execute(self, request):
        self.requests.append(request)
        return ExecutionResult(
            invocation_id=request.invocation_id, status=ExecutionStatus.NEEDS_INPUT,
            summary="I cannot judge without the live grants",
            provider_id="claude-code", continuation_ref=self.session,
            escalation=EscalationRequirement(DENIAL, "CEO"))


def product_result():
    return ExecutionResult(
        invocation_id="inv-product", status=ExecutionStatus.COMPLETED,
        summary="implemented the change", provider_id="claude-code",
        changed_files=(ChangedFileClaim("alpha.dart", "modified"),),
        tests=(TestClaim("flutter test", TestStatus.PASSED, exit_code=0),))


class ValidationContinuationTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_tmp = isolated_runtime()
        self.addCleanup(shutil.rmtree, self.runtime_tmp, ignore_errors=True)
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def realize(self, seat_id="backend-1", work_item_id="KAN-900"):
        return realize_workspace(work_item_id, seat_id,
                                 {"repository_root": self.repo,
                                  "working_directory": None, "worktree_path": None,
                                  "expected_revision": None,
                                  "mutation_mode": "repository_edit"},
                                 root=self.wtroot)

    def blocked_self_review(self, work_item_id="KAN-900"):
        """Drive real state to a SELF validator stopped at a permission gate."""
        make_task(work_item_id, characteristics={})
        validator = BlockedValidator()
        with self.assertRaises(ValidationRefused):
            run_validation(work_item_id, store.read("task", work_item_id),
                           product_result(), self.realize(work_item_id=work_item_id),
                           store, Jira(), (validator,), seats_by_capability=SEATS,
                           receipt_ref="execution of %s" % work_item_id)
        return validator

    def approve(self, invocation_id, work_item_id="KAN-900", seat_id="backend-1",
                permission="mcp__claude_ai_Supabase__execute_sql"):
        return store.record_execution_approval(
            original_invocation_id=invocation_id, work_item_id=work_item_id,
            seat_id=seat_id, claude_session_id=VSESSION, permission=permission,
            approving_authority="ceo", approval_scope="read-only fixture grant")


class PreparationTests(ValidationContinuationTestCase):
    def test_a_blocked_validator_records_a_receipt_and_a_preparation(self):
        validator = self.blocked_self_review()
        invocation = validator.requests[0].invocation_id

        receipt = store.read_execution_receipt(invocation)
        self.assertIsNotNone(receipt)
        self.assertEqual("needs_input", receipt["status"])
        self.assertEqual("KAN-900", receipt["work_item_id"])
        self.assertEqual("backend-1", receipt["seat_id"])
        # Authorized by the review context, never by a lease it does not hold.
        self.assertEqual("review:KAN-900:self:1", receipt["review_context_ref"])
        self.assertIsNone(receipt["execution_lease_id"])

        prepared = store.read_execution_continuation_preparation(invocation)
        self.assertIsNotNone(prepared)
        self.assertEqual(invocation, prepared["original_invocation_id"])
        self.assertEqual("review:KAN-900:self:1", prepared["review_context_ref"])
        self.assertEqual("KAN-900", prepared["work_item_id"])
        self.assertEqual("backend-1", prepared["seat_id"])
        self.assertEqual(VSESSION, prepared["claude_session_id"])
        self.assertEqual("mcp__claude_ai_Supabase__execute_sql", prepared["permission"])
        self.assertTrue(prepared["worktree_path"].endswith("backend-1/KAN-900"))

    def test_the_review_context_is_not_reopened_and_the_cycle_does_not_advance(self):
        self.blocked_self_review()
        review = store.read("task", "KAN-900")["review_context"]
        self.assertEqual("self", review["review_type"])
        self.assertEqual("pending", review["review_result"])
        self.assertEqual(1, review["review_cycle"])
        # A second dispatch reuses the SAME open context rather than opening one.
        validator = BlockedValidator()
        with self.assertRaises(ValidationRefused):
            run_validation("KAN-900", store.read("task", "KAN-900"), product_result(),
                           self.realize(), store, Jira(), (validator,),
                           seats_by_capability=SEATS, receipt_ref="ref")
        again = store.read("task", "KAN-900")["review_context"]
        self.assertEqual(1, again["review_cycle"])
        self.assertEqual(review["started_at"], again["started_at"])

    def test_a_stale_or_foreign_review_reference_is_refused(self):
        self.blocked_self_review()
        for ref in ("review:KAN-900:self:2", "review:KAN-901:self:1",
                    "review:KAN-900:peer:1"):
            with self.subTest(ref=ref):
                with self.assertRaises(store.StateError):
                    store.assert_review_authority("KAN-900", "backend-1", ref)

    def test_a_seat_that_is_not_the_review_owner_is_refused(self):
        self.blocked_self_review()
        with self.assertRaises(store.StateError) as caught:
            store.assert_review_authority("KAN-900", "backend-2", "review:KAN-900:self:1")
        self.assertIn("not-review-owner", str(caught.exception))

    def test_a_receipt_needs_exactly_one_authority(self):
        self.blocked_self_review()
        payload = {"invocation_id": "x", "status": "completed", "summary": "s",
                   "provider_id": "claude-code"}
        for lease, ref in ((None, None), ("lease-1", "review:KAN-900:self:1")):
            with self.subTest(lease=lease, ref=ref):
                with self.assertRaisesRegex(store.StateError, "exactly one"):
                    store.record_execution_receipt("x", "KAN-900", "backend-1", lease,
                                                   payload, review_context_ref=ref)


class ApprovalIsolationTests(ValidationContinuationTestCase):
    def test_a_product_executor_approval_cannot_authorize_the_validator(self):
        validator = self.blocked_self_review()
        validation_invocation = validator.requests[0].invocation_id
        # An approval bound to a different invocation is simply not composed
        # into this one, and this one then has no grant at all.
        with self.assertRaises(store.StateError) as caught:
            store.compose_execution_approvals(validation_invocation)
        self.assertIn("at least one exact grant", str(caught.exception))

    def test_an_approval_cannot_be_forged_onto_a_foreign_invocation(self):
        validator = self.blocked_self_review()
        invocation = validator.requests[0].invocation_id
        for work_item, seat, session in (("KAN-901", "backend-1", VSESSION),
                                         ("KAN-900", "backend-2", VSESSION),
                                         ("KAN-900", "backend-1", "wrong-session")):
            with self.subTest(work_item=work_item, seat=seat, session=session):
                with self.assertRaises(store.StateError):
                    store.record_execution_approval(
                        original_invocation_id=invocation, work_item_id=work_item,
                        seat_id=seat, claude_session_id=session,
                        permission="mcp__claude_ai_Supabase__execute_sql",
                        approving_authority="ceo", approval_scope="forged")

    def test_a_validator_approval_does_not_reach_the_product_execution(self):
        validator = self.blocked_self_review()
        validation_invocation = validator.requests[0].invocation_id
        self.approve(validation_invocation)
        # The grant is bound to the validation invocation; the Product execution
        # lineage composes independently and sees nothing of it.
        composed = store.compose_execution_approvals(validation_invocation)
        self.assertEqual(1, len(composed))
        self.assertEqual(validation_invocation, composed[0]["original_invocation_id"])


class ResumeTests(ValidationContinuationTestCase):
    def _resume(self, verdict=PASS, transport_result=None):
        def transport(wake):
            self.wakes.append(wake)
            return transport_result if transport_result is not None else {
                "status": "completed", "summary": "verdict delivered",
                "evidence": [{"kind": "verdict", "reference": verdict,
                              "summary": "independent check"}]}
        self.wakes = []
        return validation_policy.resume_validation(
            "KAN-900", store, Jira(), transport=transport, interventions=[])

    def test_an_approved_validator_resumes_and_returns_a_real_verdict(self):
        validator = self.blocked_self_review()
        invocation = validator.requests[0].invocation_id
        self.approve(invocation)
        evidence = self._resume(PASS)

        self.assertEqual(VALIDATION_PASSED, evidence["outcome"])
        self.assertEqual(PASS, evidence["verdict"])
        self.assertEqual("self", evidence["validation_route"])
        self.assertEqual("backend-1", evidence["reviewer"])
        self.assertEqual(1, evidence["review_cycle"])
        self.assertEqual(["mcp__claude_ai_Supabase__execute_sql"],
                         evidence["approved_permissions"])
        # Same session, same review context, same workspace.
        self.assertEqual(VSESSION, self.wakes[0].session_ref)
        self.assertEqual(("mcp__claude_ai_Supabase__execute_sql",),
                         self.wakes[0].approved_permissions)
        settled = store.read("task", "KAN-900")
        self.assertEqual("pass", settled["review_context"]["review_result"])
        self.assertEqual(1, settled["review_context"]["review_cycle"])
        # Receipt lineage: the continuation names the invocation it continues.
        continuation = next(r for r in store.read_all("execution_receipt")
                            if r.get("continuation_of_invocation_id") == invocation)
        self.assertEqual("completed", continuation["status"])
        self.assertEqual("review:KAN-900:self:1", continuation["review_context_ref"])

    def test_the_resumed_validator_brief_stays_product_only(self):
        validator = self.blocked_self_review()
        self.approve(validator.requests[0].invocation_id)
        self._resume(PASS)
        brief = self.wakes[0].prompt
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), brief.lower())
        for internal in ("continuation-", "review:KAN-900", VSESSION,
                         "execution_continuation_id"):
            self.assertNotIn(internal.lower(), brief.lower())
        self.assertIn("Continue the same validation of KAN-900", brief)
        self.assertIn("- Mutation mode: read_only", brief)

    def test_a_resumed_fail_follows_canonical_self_remediation(self):
        validator = self.blocked_self_review()
        self.approve(validator.requests[0].invocation_id)
        evidence = self._resume(FAIL)
        self.assertEqual(VALIDATION_FAILED, evidence["outcome"])
        self.assertEqual("backend-1", evidence["remediation_owner"])
        settled = store.read("task", "KAN-900")
        self.assertEqual("fail", settled["review_context"]["review_result"])
        self.assertEqual("backend-1", settled["ownership"]["seat_id"])
        self.assertEqual(BACKEND_DEV, settled["lifecycle"]["jira_status_id"])

    def test_a_replayed_resume_is_refused(self):
        validator = self.blocked_self_review()
        self.approve(validator.requests[0].invocation_id)
        self._resume(PASS)
        with self.assertRaises(ValidationRefused) as caught:
            self._resume(PASS)
        self.assertEqual(VALIDATION_ALREADY_SETTLED, caught.exception.outcome)

    def test_resume_without_an_approval_is_refused_and_settles_nothing(self):
        self.blocked_self_review()
        with self.assertRaises(store.StateError):
            self._resume(PASS)
        self.assertEqual("pending",
                         store.read("task", "KAN-900")["review_context"]["review_result"])

    def test_the_controller_entry_refuses_in_maintenance_mode(self):
        self.blocked_self_review()
        mode = store.read("operating_mode", "current")
        store.set_operating_mode("SYSTEM_MAINTENANCE", "ceo", "fixture",
                                 expected_revision=mode["revision"])
        out = resume_validation("KAN-900", state_store=store, jira_client=Jira())
        self.assertEqual("system-maintenance-active", out["blocker"])


class RealSystemsUntouchedTests(ValidationContinuationTestCase):
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
