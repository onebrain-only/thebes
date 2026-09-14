#!/usr/bin/env python3
"""LIFECYCLE COMPLETION AFTER INTEGRATION.

Synthetic git repository, fake Jira, fake provider, real controller and real
canonical policy. No real Jira issue is read or transitioned, no real Product
repository is touched, and no Supabase call exists anywhere on this path.
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

from agent.controller import execute, integrate as controller_integrate  # noqa: E402
from agent.controller.completion import (  # noqa: E402
    ALREADY_DONE, COMPLETED, FINALIZATION_INCOMPLETE,
    INTEGRATION_EVIDENCE_INVALID, JIRA_STATE_DIVERGED_AFTER_TRANSITION,
    JIRA_TRANSITION_FAILED, LIFECYCLE_NOT_COMPLETABLE, OWNERSHIP_RELEASE_FAILED,
    CompletionRefused, complete_lifecycle, valid_integration_receipt,
)
from agent.controller.workspace import conclude_workspace, realize_workspace  # noqa: E402
from agent.controller.tests.test_canonical_intent import (  # noqa: E402
    Authorization, Registry, issue,
)
from agent.controller.tests.test_entry import no_validation  # noqa: E402
from agent.controller.tests.test_integration_flow import (  # noqa: E402
    IntegrationStore, SURFACES, validated_task,
)
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402
from agent.execution.brief import CONTROL_PLANE_TOKENS  # noqa: E402
from agent.execution.claude import ClaudeProvider  # noqa: E402
from agent.state import board  # noqa: E402


DONE = board.DONE_STATUS_ID          # 10007
QA_TEST = "10009"
DONE_TRANSITION = board.transition_for(DONE)


class LifecycleJira:
    """A Jira double that behaves like the board: a transition moves the status."""

    def __init__(self, status_id=QA_TEST, fail_transition=None,
                 status_after_transition=None):
        self.status_id = str(status_id)
        self.fail_transition = fail_transition
        self.status_after_transition = status_after_transition
        self.reads = []
        self.transitions = []
        self.other_writes = []

    def get_issue(self, key):
        self.reads.append(key)
        record = dict(issue())
        record["status_id"] = self.status_id
        record["status"] = board.name_for(self.status_id)
        return record

    def transition_issue(self, key, transition_id):
        self.transitions.append((key, transition_id))
        if self.fail_transition:
            raise RuntimeError(self.fail_transition)
        # A divergence fixture: Jira accepts the call and lands elsewhere.
        self.status_id = str(self.status_after_transition or DONE)
        return {"key": key, "transition": transition_id}

    def update_issue(self, *args, **kwargs):      # pragma: no cover - guard
        self.other_writes.append(("update", args))
        raise AssertionError("a dry flow test must not edit Jira fields")

    def add_comment(self, *args, **kwargs):       # pragma: no cover - guard
        self.other_writes.append(("comment", args))
        raise AssertionError("a dry flow test must not comment on Jira")


def receipt(**changes):
    value = {"integration_receipt_id": "integration-abc123",
             "work_item_id": "KAN-900", "seat_id": "backend-1",
             "outcome": "integrated", "product_commit": "a" * 40,
             "integrated_as": "b" * 40, "integration_branch": "Canary",
             "previous_head": "c" * 40, "source_branch": "exec/backend-1/KAN-900",
             "validation_route": "qa", "validation_result": "pass",
             "attributed_files": ["alpha.dart"], "conflict_paths": [],
             "remediation_required": False, "created_at": "2026-09-14T00:00:00Z"}
    value.update(changes)
    return value


class ReceiptEvidenceTests(unittest.TestCase):
    """The receipt proves orchestration facts. It is never lifecycle authority."""

    def test_a_valid_receipt_is_accepted(self):
        chosen = valid_integration_receipt("KAN-900", validated_task(), [receipt()])
        self.assertEqual("integration-abc123", chosen["integration_receipt_id"])

    def test_the_newest_usable_receipt_wins_without_erasing_earlier_ones(self):
        older = receipt(integration_receipt_id="integration-old",
                        created_at="2026-09-13T00:00:00Z")
        newer = receipt(integration_receipt_id="integration-new",
                        created_at="2026-09-14T12:00:00Z")
        failed = receipt(integration_receipt_id="integration-bad",
                         outcome="integration-conflict", remediation_required=True,
                         created_at="2026-09-14T23:00:00Z")
        chosen = valid_integration_receipt("KAN-900", validated_task(),
                                           [older, failed, newer])
        self.assertEqual("integration-new", chosen["integration_receipt_id"])

    def test_every_unusable_receipt_is_refused(self):
        cases = {
            "no receipt at all": [],
            "foreign work item": [receipt(work_item_id="KAN-901")],
            "foreign seat": [receipt(seat_id="backend-2")],
            "conflicted": [receipt(outcome="integration-conflict",
                                   remediation_required=True)],
            "attribution failed": [receipt(outcome="attribution-failed",
                                           remediation_required=True)],
            "remediation flagged": [receipt(remediation_required=True)],
            "protected target": [receipt(integration_branch="main")],
            "no product commit recorded": [receipt(product_commit=None)],
            "no integrated sha": [receipt(integrated_as=None)],
            "malformed": ["not a receipt"],
            "no-commit receipt carrying a commit": [
                receipt(outcome="no-product-commit-required")],
        }
        for name, receipts in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(CompletionRefused) as caught:
                    valid_integration_receipt("KAN-900", validated_task(), receipts)
                self.assertEqual(INTEGRATION_EVIDENCE_INVALID, caught.exception.outcome)

    def test_a_legitimate_no_commit_receipt_is_usable(self):
        clean = receipt(outcome="no-product-commit-required", product_commit=None,
                        integrated_as=None, attributed_files=[])
        chosen = valid_integration_receipt("KAN-900", validated_task(), [clean])
        self.assertEqual("no-product-commit-required", chosen["outcome"])


class CompletionGateTests(unittest.TestCase):
    def _complete(self, task_record, receipts=None, jira=None, store=None):
        store = store or IntegrationStore(task_record)
        jira = jira or LifecycleJira()
        return complete_lifecycle("KAN-900", task_record,
                                  receipts if receipts is not None else [receipt()],
                                  store, jira, interventions=[]), store, jira

    def test_every_validation_route_completes_when_it_has_passed(self):
        for route in ("self", "qa", "peer"):
            with self.subTest(route=route):
                record = validated_task(route=route)
                evidence, store, jira = self._complete(record)
                self.assertEqual(COMPLETED, evidence["outcome"])
                self.assertEqual(route, evidence["validation_route"])
                self.assertEqual("done", evidence["lifecycle"])
                self.assertEqual([("KAN-900", DONE_TRANSITION)], jira.transitions)

    def test_pending_and_failed_validation_cannot_transition(self):
        for name, record in (("pending", validated_task(result="pending")),
                             ("failed", validated_task(result="fail"))):
            with self.subTest(case=name):
                with self.assertRaises(CompletionRefused) as caught:
                    self._complete(record)
                self.assertEqual(LIFECYCLE_NOT_COMPLETABLE, caught.exception.outcome)

    def test_a_stopped_task_cannot_be_completed(self):
        store = IntegrationStore(validated_task())
        jira = LifecycleJira()
        with self.assertRaises(CompletionRefused) as caught:
            complete_lifecycle("KAN-900", validated_task(), [receipt()], store, jira,
                               interventions=[{"kind": "stop", "target": "KAN-900"}])
        self.assertEqual(LIFECYCLE_NOT_COMPLETABLE, caught.exception.outcome)
        self.assertEqual([], jira.transitions)

    def test_the_gate_refuses_before_any_jira_write(self):
        jira = LifecycleJira()
        with self.assertRaises(CompletionRefused):
            self._complete(validated_task(result="pending"), jira=jira)
        self.assertEqual([], jira.transitions)
        self.assertEqual([], jira.other_writes)

    def test_bad_evidence_refuses_before_any_jira_write(self):
        jira = LifecycleJira()
        with self.assertRaises(CompletionRefused) as caught:
            self._complete(validated_task(),
                           receipts=[receipt(outcome="integration-conflict",
                                             remediation_required=True)], jira=jira)
        self.assertEqual(INTEGRATION_EVIDENCE_INVALID, caught.exception.outcome)
        self.assertEqual([], jira.transitions)


class JiraLifecycleTests(unittest.TestCase):
    def test_the_transition_target_is_asserted_legal_before_the_write(self):
        # Done is a live board target with a real transition id; a legacy status
        # would be refused by the same guard.
        self.assertEqual(DONE, board.assert_transition_target(DONE))
        for legacy in board.LEGACY_STATUS_IDS:
            with self.subTest(legacy=legacy):
                with self.assertRaises(ValueError):
                    board.assert_transition_target(legacy)

    def test_exactly_one_transition_is_fired_and_jira_is_reread(self):
        store, jira = IntegrationStore(validated_task()), LifecycleJira()
        evidence = complete_lifecycle("KAN-900", validated_task(), [receipt()],
                                      store, jira, interventions=[])
        self.assertEqual(1, len(jira.transitions))
        self.assertEqual([("KAN-900", DONE_TRANSITION)], jira.transitions)
        # Read once before the transition, once after to confirm it.
        self.assertEqual(["KAN-900", "KAN-900"], jira.reads)
        self.assertTrue(evidence["jira_transition_performed"])
        self.assertEqual(QA_TEST, evidence["jira_status_before"])
        self.assertEqual(DONE, evidence["jira_status_after"])

    def test_persistent_state_is_written_from_the_authoritative_reread(self):
        store, jira = IntegrationStore(validated_task()), LifecycleJira()
        complete_lifecycle("KAN-900", validated_task(), [receipt()], store, jira,
                           interventions=[])
        self.assertEqual(DONE, store.task["lifecycle"]["jira_status_id"])
        self.assertIn("observe", store.events)

    def test_an_already_done_issue_is_idempotent_with_zero_writes(self):
        record = validated_task(lifecycle="done")
        store = IntegrationStore(record)
        jira = LifecycleJira(status_id=DONE)
        evidence = complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                                      interventions=[])
        self.assertEqual(ALREADY_DONE, evidence["outcome"])
        self.assertEqual([], jira.transitions)
        self.assertFalse(evidence["jira_transition_performed"])
        self.assertEqual("done", evidence["lifecycle"])
        self.assertEqual("released", evidence["ownership_status"])

    def test_locally_done_but_jira_not_done_is_a_divergence_not_a_transition(self):
        record = validated_task(lifecycle="done")
        store, jira = IntegrationStore(record), LifecycleJira(status_id=QA_TEST)
        with self.assertRaises(CompletionRefused) as caught:
            complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                               interventions=[])
        self.assertEqual(JIRA_STATE_DIVERGED_AFTER_TRANSITION,
                         caught.exception.outcome)
        self.assertEqual([], jira.transitions)
        self.assertIsNotNone(store.task["ownership"])

    def test_a_transition_that_lands_elsewhere_is_surfaced_and_preserves_ownership(self):
        record = validated_task()
        store = IntegrationStore(record)
        jira = LifecycleJira(status_after_transition=QA_TEST)
        with self.assertRaises(CompletionRefused) as caught:
            complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                               interventions=[])
        self.assertEqual(JIRA_STATE_DIVERGED_AFTER_TRANSITION,
                         caught.exception.outcome)
        self.assertEqual(1, len(jira.transitions))
        # No local Done, and the owner is still the owner.
        self.assertNotIn("observe", store.events)
        self.assertNotIn("release", store.events)
        self.assertIsNotNone(store.task["ownership"])

    def test_a_failed_transition_preserves_ownership_and_records_no_done(self):
        record = validated_task()
        store = IntegrationStore(record)
        jira = LifecycleJira(fail_transition="jira is unavailable")
        with self.assertRaises(CompletionRefused) as caught:
            complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                               interventions=[])
        self.assertEqual(JIRA_TRANSITION_FAILED, caught.exception.outcome)
        self.assertIn("jira is unavailable", caught.exception.detail)
        self.assertNotIn("observe", store.events)
        self.assertNotIn("release", store.events)
        self.assertEqual({"seat_id": "backend-1", "claim_ref": "claim:KAN-900"},
                         store.task["ownership"])


class OwnershipAndFinalizationTests(unittest.TestCase):
    def test_ownership_releases_only_after_authoritative_done(self):
        record = validated_task()
        store, jira = IntegrationStore(record), LifecycleJira()
        evidence = complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                                      interventions=[])
        self.assertEqual("released", evidence["ownership_status"])
        self.assertIsNone(store.task["ownership"])
        # Order: observation of Done precedes the release.
        self.assertLess(store.events.index("observe"), store.events.index("release"))

    def test_a_release_failure_is_its_own_outcome(self):
        record = validated_task()
        store, jira = IntegrationStore(record), LifecycleJira()

        def refuse(*args, **kwargs):
            raise RuntimeError("stale write refused")
        store.release = refuse
        with self.assertRaises(CompletionRefused) as caught:
            complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                               interventions=[])
        self.assertEqual(OWNERSHIP_RELEASE_FAILED, caught.exception.outcome)

    def test_open_leases_are_reported_not_force_closed(self):
        record = validated_task()
        store, jira = IntegrationStore(record), LifecycleJira()
        evidence = complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                                      interventions=[])
        self.assertEqual([], evidence["open_leases"])

    def test_a_still_open_lease_is_surfaced(self):
        record = validated_task()
        store, jira = IntegrationStore(record), LifecycleJira()
        store.read_all = lambda kind: ([{"execution_lease_id": "lease-900",
                                         "work_item_id": "KAN-900",
                                         "closed_at": None}] if kind == "execution_lease"
                                       else [])
        evidence = complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                                      interventions=[])
        self.assertEqual(["lease-900"], evidence["open_leases"])

    def test_the_durable_evidence_survives_completion(self):
        record = validated_task()
        store, jira = IntegrationStore(record), LifecycleJira()
        evidence = complete_lifecycle("KAN-900", record, [receipt()], store, jira,
                                      interventions=[])
        self.assertEqual("a" * 40, evidence["product_commit"])
        self.assertEqual("b" * 40, evidence["integrated_as"])
        self.assertEqual("Canary", evidence["integration_branch"])
        self.assertEqual("integration-abc123", evidence["integration_receipt_id"])
        self.assertEqual("qa", evidence["validation_route"])
        self.assertEqual("pass", evidence["validation_result"])


class EndToEndFlowTests(unittest.TestCase):
    """CEO gives one work-item key; Thebes does everything else."""

    def setUp(self):
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.main_before = sh(self.repo, "rev-parse", "main")

    def _controller(self, record, jira, edit=True, provider_result="fixture complete"):
        store = IntegrationStore(record)
        wakes = []

        edited = []

        def allocator(work_item_id, seat_id, workspace):
            realized = realize_workspace(work_item_id, seat_id,
                                         dict(workspace, repository_root=self.repo),
                                         root=self.wtroot)
            # Stand in for the executor. Only ever touches a declared surface;
            # a marker file in the tree would itself be an undeclared change.
            if edit and not edited:
                with open(os.path.join(realized["path"], "alpha.dart"), "a") as handle:
                    handle.write("// executor change\n")
                edited.append(True)
            return realized

        def concluder(work_item_id, seat_id, result, task_record, realized,
                      integration=None):
            return conclude_workspace(work_item_id, seat_id, result, task_record,
                                      realized, root=self.wtroot,
                                      integration=integration)

        def transport(wake):
            wakes.append(wake)
            return provider_result

        return store, wakes, allocator, concluder, transport

    def test_one_work_item_key_reaches_done_with_no_human_orchestration(self):
        # The item's review has already passed, which is what makes the whole
        # tail legal in a single command.
        record = validated_task()
        jira = LifecycleJira()
        store, wakes, allocator, concluder, transport = self._controller(record, jira)

        outcome = execute("KAN-900", None, authorization=Authorization(),
                          state_store=store, jira_client=jira,
                          seat_registry=Registry(),
                          providers=(ClaudeProvider(transport),),
                          workspace_allocator=allocator,
                          workspace_concluder=concluder,
                          interventions=[], worktree_root=self.wtroot,
                          validator=no_validation)

        # Execution
        self.assertEqual("canonical-state", outcome["brief_source"])
        self.assertEqual("completed", outcome["execution_status"])
        self.assertEqual(1, len(wakes))
        # Product-only brief, still
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), wakes[0].prompt.lower())
        # Integration
        self.assertEqual("integrated", outcome["integration_status"])
        self.assertEqual(["alpha.dart"], outcome["attributed_files"])
        self.assertEqual(40, len(outcome["product_commit"]))
        self.assertEqual(outcome["integrated_as"], sh(self.repo, "rev-parse", "Canary"))
        self.assertEqual("recorded", outcome["receipt_status"])
        # Lifecycle
        self.assertEqual(COMPLETED, outcome["completion_status"])
        self.assertTrue(outcome["jira_transition_performed"])
        self.assertEqual([("KAN-900", DONE_TRANSITION)], jira.transitions)
        self.assertEqual("done", outcome["lifecycle"])
        self.assertEqual("released", outcome["ownership_status"])
        self.assertIsNone(store.task["ownership"])
        self.assertEqual([], outcome["open_leases"])
        # Workspace and repository truth
        self.assertEqual("released", outcome["workspace_status"])
        self.assertFalse(os.path.isdir(outcome["workspace_path"]))
        self.assertEqual(self.main_before, sh(self.repo, "rev-parse", "main"))
        self.assertEqual([], jira.other_writes)
        self.assertEqual(1, len(store.integration_receipts))

    def test_a_jira_failure_yields_no_false_done_and_no_provider_rerun(self):
        record = validated_task()
        jira = LifecycleJira(fail_transition="jira is unavailable")
        store, wakes, allocator, concluder, transport = self._controller(record, jira)

        outcome = execute("KAN-900", None, authorization=Authorization(),
                          state_store=store, jira_client=jira,
                          seat_registry=Registry(),
                          providers=(ClaudeProvider(transport),),
                          workspace_allocator=allocator,
                          workspace_concluder=concluder,
                          interventions=[], worktree_root=self.wtroot,
                          validator=no_validation)

        # The Product work remains truthful: it integrated, and that stands.
        self.assertEqual("integrated", outcome["integration_status"])
        self.assertEqual(outcome["integrated_as"], sh(self.repo, "rev-parse", "Canary"))
        # The lifecycle did not complete, and says exactly why.
        self.assertEqual(JIRA_TRANSITION_FAILED, outcome["completion_status"])
        self.assertIn("jira is unavailable", outcome["completion_blocker"])
        self.assertIsNone(outcome["lifecycle"])
        # Ownership is preserved and the provider ran exactly once.
        self.assertIsNotNone(store.task["ownership"])
        self.assertEqual("backend-1", store.task["ownership"]["seat_id"])
        self.assertEqual(1, len(wakes))
        self.assertNotIn("release", store.events)

    def test_an_unvalidated_execution_completes_nothing_and_changes_no_jira(self):
        record = validated_task(result="pending", lifecycle="development")
        jira = LifecycleJira(status_id="10043")
        store, wakes, allocator, concluder, transport = self._controller(record, jira)

        outcome = execute("KAN-900", None, authorization=Authorization(),
                          state_store=store, jira_client=jira,
                          seat_registry=Registry(),
                          providers=(ClaudeProvider(transport),),
                          workspace_allocator=allocator,
                          workspace_concluder=concluder,
                          interventions=[], worktree_root=self.wtroot,
                          validator=no_validation)

        self.assertEqual("completed", outcome["execution_status"])
        # Validation refused, so integration was never even attempted — the
        # gate now sits one step earlier than it used to.
        self.assertEqual("validation-route-unresolved", outcome["validation_status"])
        self.assertEqual("not-attempted", outcome["integration_status"])
        self.assertEqual("not-attempted", outcome["completion_status"])
        self.assertEqual([], jira.transitions)
        self.assertIsNotNone(store.task["ownership"])
        # Canary is untouched and the executor's work waits in its own tree.
        self.assertEqual("", sh(self.repo, "log", "--format=%H",
                                "%s..Canary" % self.main_before).strip()
                         .replace(sh(self.repo, "rev-parse", "Canary"), ""))
        # An automatic attempt that only found a pending review files no receipt.
        self.assertEqual([], store.integration_receipts)
        self.assertEqual("preserved", outcome["workspace_status"])

    def test_the_command_is_idempotent_once_the_item_is_done(self):
        record = validated_task()
        jira = LifecycleJira()
        store, _, allocator, concluder, transport = self._controller(record, jira)
        execute("KAN-900", None, authorization=Authorization(), state_store=store,
                jira_client=jira, seat_registry=Registry(),
                providers=(ClaudeProvider(transport),),
                workspace_allocator=allocator, workspace_concluder=concluder,
                interventions=[], worktree_root=self.wtroot,
                validator=no_validation)
        self.assertEqual(1, len(jira.transitions))

        # Running the recovery command again must not fire a second transition.
        second = controller_integrate(
            "KAN-900", state_store=store, jira_client=jira,
            workspace_allocator=allocator, workspace_concluder=concluder,
            interventions=[], worktree_root=self.wtroot)
        self.assertEqual(1, len(jira.transitions))
        self.assertIn(second["completion_status"], (ALREADY_DONE, "not-attempted"))
        self.assertEqual([], jira.other_writes)


class RealSystemsUntouchedTests(unittest.TestCase):
    def test_no_module_on_this_path_can_reach_supabase(self):
        for name in ("completion", "integration", "workspace", "intent"):
            path = os.path.join(ROOT, "agent", "controller", "%s.py" % name)
            with open(path, encoding="utf-8") as handle:
                source = handle.read().lower()
            with self.subTest(module=name):
                for forbidden in ("supabase", "psycopg", "postgres"):
                    self.assertNotIn(forbidden, source)

    def test_this_suite_never_reached_the_real_product_repository(self):
        real = os.path.join(ROOT, "Dabbler", "dabbler-code")
        if not os.path.isdir(real):
            self.skipTest("the real Product checkout is not present")
        listed = subprocess.run(["git", "-C", real, "worktree", "list"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("KAN-900", listed)
        subject = subprocess.run(["git", "-C", real, "log", "-1", "--format=%s",
                                  "Canary"], capture_output=True, text=True).stdout
        self.assertNotIn("KAN-900", subject)


if __name__ == "__main__":
    unittest.main(verbosity=2)
