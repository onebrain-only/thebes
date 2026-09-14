#!/usr/bin/env python3
"""COMMIT AND INTEGRATION IN THE EXECUTION PATH.

Every test runs against a SYNTHETIC git repository in a temp directory, with an
in-memory store and Jira double. Nothing here reaches the real Product checkout,
the real Canary, Jira or Supabase — a suite that proved integration by landing a
commit on the real Canary would be the defect it claims to defend against.
"""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.controller import integrate as controller_integrate  # noqa: E402
from agent.controller import integration  # noqa: E402
from agent.controller.integration import (  # noqa: E402
    ATTRIBUTION_FAILED, INTEGRATED, INTEGRATION_CONFLICT,
    NO_PRODUCT_COMMIT_REQUIRED, VALIDATION_NOT_PASSED,
    IntegrationRefused, attributed_changes, commit_message,
    integrate_validated_work, validation_reasons,
)
from agent.controller.workspace import (  # noqa: E402
    PRESERVE, RELEASE, conclude_workspace, realize_workspace, release_decision,
)
from agent.controller.tests.test_canonical_intent import (  # noqa: E402
    Authorization, Jira, Registry, State, issue, task,
)
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402
from agent.state import worktrees  # noqa: E402


SURFACES = ["alpha.dart", "beta.dart"]


def validated_task(route="qa", result="pass", lifecycle="review", **changes):
    """A task whose canonical validation route has been recorded as passed."""
    record = task()
    record["surfaces"] = list(SURFACES)
    record["lifecycle"] = {"canonical": lifecycle, "jira_column": "Review",
                           "jira_status_id": "10009", "jira_status_name": "QA-Test",
                           "source": "jira", "observed_at": "2026-09-14T00:00:00Z"}
    record["ownership"] = {"seat_id": "backend-1", "claim_ref": "claim:KAN-900"}
    record["execution_profile"]["validation_route"] = route
    record["execution_profile"]["completion_route"] = "DONE"
    record["review_context"] = {"review_type": route, "review_owner": "qa",
                                "review_result": result, "review_cycle": 1,
                                "started_at": "2026-09-14T00:00:00Z",
                                "previous_owner": None}
    record.update(changes)
    return record


class IntegrationStore(State):
    """State double that also holds integration receipts in memory."""

    def __init__(self, record=None):
        super().__init__(record or validated_task())
        self.integration_receipts = []

    def active_interventions(self):
        return []

    def record_integration_receipt(self, work_item_id, seat_id, outcome, evidence):
        record = {"work_item_id": work_item_id, "seat_id": seat_id,
                  "outcome": outcome, **evidence}
        self.integration_receipts.append(record)
        return record


class IntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.main_before = sh(self.repo, "rev-parse", "main")

    def realize(self, seat_id="backend-1", work_item_id="KAN-900"):
        return realize_workspace(work_item_id, seat_id,
                                 {"repository_root": self.repo,
                                  "working_directory": None, "worktree_path": None,
                                  "expected_revision": None,
                                  "mutation_mode": "repository_edit"},
                                 root=self.wtroot)

    def executor_edits(self, realized, name="alpha.dart", text="// executor change\n"):
        """Stand in for the Product executor: it edits files and returns."""
        with open(os.path.join(realized["path"], name), "a") as handle:
            handle.write(text)

    def run_integration(self, record=None, realized=None, interventions=None):
        record = record or validated_task()
        realized = realized or self.realize()
        return integrate_validated_work(
            "KAN-900", "backend-1", record, issue(), realized, repo=self.repo,
            root=self.wtroot, interventions=interventions or [])

    def assert_main_untouched(self):
        self.assertEqual(self.main_before, sh(self.repo, "rev-parse", "main"))


class ValidationGateTests(IntegrationTestCase):
    """No Product work reaches the integration branch before its route passes."""

    def test_a_passed_route_is_the_only_thing_that_opens_the_gate(self):
        for route in ("self", "qa", "peer"):
            with self.subTest(route=route):
                self.assertEqual((), validation_reasons(
                    validated_task(route=route), interventions=[]))

    def test_every_unpassed_route_refuses_before_anything_is_staged(self):
        cases = {
            "pending verdict": validated_task(result="pending"),
            "failed verdict": validated_task(result="fail"),
            "still in development": validated_task(lifecycle="development"),
        }
        for name, record in cases.items():
            with self.subTest(case=name):
                realized = self.realize()
                self.executor_edits(realized)
                before = sh(self.repo, "rev-parse", "Canary")
                with self.assertRaises(IntegrationRefused) as caught:
                    self.run_integration(record, realized)
                self.assertEqual(VALIDATION_NOT_PASSED, caught.exception.outcome)
                self.assertEqual(before, sh(self.repo, "rev-parse", "Canary"))
                # And the executor's edit is still uncommitted in its own tree.
                self.assertEqual("", sh(realized["path"], "log", "Canary..HEAD",
                                        "--format=%H"))

    def test_a_route_mismatch_and_an_unresolved_owner_both_refuse(self):
        mismatch = validated_task(route="peer")
        mismatch["review_context"]["review_type"] = "self"
        unresolved = validated_task()
        unresolved["review_context"]["review_owner"] = None
        for name, record, reason in (("route mismatch", mismatch, "review-route-mismatch"),
                                     ("no owner", unresolved, "review-owner-unresolved")):
            with self.subTest(case=name):
                self.assertIn(reason, validation_reasons(record, interventions=[]))

    def test_a_stopped_task_is_never_integrated(self):
        stop = [{"kind": "stop", "target": "KAN-900"}]
        self.assertIn("task-stopped",
                      validation_reasons(validated_task(), interventions=stop))

    def test_a_completed_provider_result_alone_proves_nothing(self):
        # Execution completed; nobody reviewed it. That is not integrable.
        record = validated_task(result="pending", lifecycle="development")
        record["executor_evidence"] = [{"seat_id": "backend-1",
                                        "evidence_ref": "provider said completed",
                                        "evidenced_at": "2026-09-14T00:00:00Z"}]
        self.assertTrue(validation_reasons(record, interventions=[]))


class AttributionTests(IntegrationTestCase):
    def test_declared_changes_are_attributed_and_committed(self):
        realized = self.realize()
        self.executor_edits(realized)
        evidence = self.run_integration(realized=realized)
        self.assertEqual(INTEGRATED, evidence["outcome"])
        self.assertEqual(["alpha.dart"], evidence["attributed_files"])
        self.assertEqual("fix(KAN-900): %s" % issue()["summary"],
                         evidence["commit_message"])

    def test_an_undeclared_change_refuses_before_a_single_file_is_staged(self):
        realized = self.realize()
        self.executor_edits(realized)
        with open(os.path.join(realized["path"], "stray.dart"), "w") as handle:
            handle.write("// never declared by this task\n")
        before = sh(self.repo, "rev-parse", "Canary")
        with self.assertRaises(IntegrationRefused) as caught:
            self.run_integration(realized=realized)
        self.assertEqual(ATTRIBUTION_FAILED, caught.exception.outcome)
        self.assertIn("stray.dart", caught.exception.detail)
        self.assertEqual(before, sh(self.repo, "rev-parse", "Canary"))
        # Nothing staged, and the undeclared file is left exactly where it is.
        self.assertEqual("", sh(realized["path"], "diff", "--cached", "--name-only"))
        self.assertTrue(os.path.isfile(os.path.join(realized["path"], "stray.dart")))

    def test_unrelated_dirt_is_never_swept_into_the_commit(self):
        realized = self.realize()
        self.executor_edits(realized)
        evidence = self.run_integration(realized=realized)
        landed = sh(self.repo, "show", "--name-only", "--format=",
                    evidence["integrated_as"]).split()
        self.assertEqual(["alpha.dart"], landed)
        self.assertNotIn("beta.dart", landed)

    def test_attribution_is_computed_from_declared_surfaces(self):
        realized = self.realize()
        self.executor_edits(realized, name="beta.dart")
        self.assertEqual(("beta.dart",),
                         attributed_changes("KAN-900", "backend-1",
                                            validated_task(), root=self.wtroot))

    def test_the_commit_message_follows_the_product_convention(self):
        self.assertEqual("fix(KAN-900): a summary",
                         commit_message("KAN-900", {"issue_type": "Bug",
                                                    "summary": "a summary"}))
        self.assertEqual("feat(KAN-900): a summary",
                         commit_message("KAN-900", {"issue_type": "Story",
                                                    "summary": "a summary"}))


class NoChangeTests(IntegrationTestCase):
    def test_completed_work_with_no_file_change_creates_no_empty_commit(self):
        realized = self.realize()
        before = sh(self.repo, "rev-parse", "Canary")
        evidence = self.run_integration(realized=realized)
        self.assertEqual(NO_PRODUCT_COMMIT_REQUIRED, evidence["outcome"])
        self.assertEqual([], evidence["attributed_files"])
        self.assertIsNone(evidence.get("product_commit"))
        self.assertEqual(before, sh(self.repo, "rev-parse", "Canary"))
        self.assertEqual("", sh(realized["path"], "log", "Canary..HEAD", "--format=%H"))


class IntegrationTests(IntegrationTestCase):
    def test_the_product_commit_and_the_canary_sha_are_both_captured(self):
        realized = self.realize()
        self.executor_edits(realized)
        before = sh(self.repo, "rev-parse", "Canary")
        evidence = self.run_integration(realized=realized)
        self.assertEqual(INTEGRATED, evidence["outcome"])
        self.assertEqual(40, len(evidence["product_commit"]))
        self.assertEqual(40, len(evidence["integrated_as"]))
        self.assertEqual(before, evidence["previous_head"])
        self.assertEqual("Canary", evidence["integration_branch"])
        self.assertEqual("exec/backend-1/KAN-900", evidence["source_branch"])
        # Git agrees, independently of the exit code.
        self.assertEqual(evidence["integrated_as"], sh(self.repo, "rev-parse", "Canary"))
        self.assertEqual(0, subprocess.run(
            ["git", "-C", self.repo, "merge-base", "--is-ancestor",
             evidence["integrated_as"], "Canary"]).returncode)
        self.assert_main_untouched()

    def test_canary_advancing_independently_still_integrates_cleanly(self):
        realized = self.realize()
        self.executor_edits(realized)
        # Somebody else lands unrelated work on Canary after allocation.
        with open(os.path.join(self.repo, "beta.dart"), "a") as handle:
            handle.write("// unrelated canary work\n")
        sh(self.repo, "commit", "-qam", "chore: unrelated canary work")
        unrelated = sh(self.repo, "rev-parse", "Canary")

        evidence = self.run_integration(realized=realized)
        self.assertEqual(INTEGRATED, evidence["outcome"])
        self.assertEqual(unrelated, evidence["previous_head"])
        # The other task's commit is still on Canary.
        self.assertEqual(0, subprocess.run(
            ["git", "-C", self.repo, "merge-base", "--is-ancestor", unrelated,
             "Canary"]).returncode)
        with open(os.path.join(self.repo, "beta.dart")) as handle:
            self.assertIn("unrelated canary work", handle.read())
        self.assert_main_untouched()

    def test_a_real_conflict_preserves_the_workspace_and_never_overwrites_canary(self):
        realized = self.realize()
        self.executor_edits(realized, text="// executor version\n")
        # Canary changes the same line region first.
        with open(os.path.join(self.repo, "alpha.dart"), "a") as handle:
            handle.write("// canary version\n")
        sh(self.repo, "commit", "-qam", "chore: conflicting canary work")
        canary_before = sh(self.repo, "rev-parse", "Canary")

        with self.assertRaises(IntegrationRefused) as caught:
            self.run_integration(realized=realized)
        self.assertEqual(INTEGRATION_CONFLICT, caught.exception.outcome)
        self.assertIn("alpha.dart", caught.exception.conflict_paths)
        # Canary is exactly where it was, and clean: no half-applied cherry-pick.
        self.assertEqual(canary_before, sh(self.repo, "rev-parse", "Canary"))
        self.assertEqual("", sh(self.repo, "status", "--porcelain"))
        with open(os.path.join(self.repo, "alpha.dart")) as handle:
            content = handle.read()
        self.assertIn("canary version", content)
        self.assertNotIn("executor version", content)
        self.assert_main_untouched()
        # The Product commit survives in the seat's own branch for remediation.
        self.assertTrue(os.path.isdir(realized["path"]))
        self.assertTrue(sh(realized["path"], "log", "-1", "--format=%H"))

    def test_the_integration_branch_is_never_a_protected_branch(self):
        realized = self.realize()
        self.executor_edits(realized)
        with self.assertRaises(IntegrationRefused) as caught:
            integrate_validated_work("KAN-900", "backend-1", validated_task(),
                                     issue(), realized, repo=self.repo,
                                     root=self.wtroot, integration_branch="main",
                                     interventions=[])
        self.assertIn("protected-branch", caught.exception.detail)
        self.assert_main_untouched()

    def test_a_committed_but_unlanded_branch_is_retried_not_declared_changeless(self):
        # An earlier attempt committed and then failed to land. The tree is
        # clean, but the work is real and must still be offered.
        realized = self.realize()
        self.executor_edits(realized)
        committed = worktrees.commit("backend-1", "KAN-900",
                                     "fix(KAN-900): earlier attempt",
                                     ["alpha.dart"], root=self.wtroot)
        evidence = self.run_integration(realized=realized)
        self.assertEqual(INTEGRATED, evidence["outcome"])
        self.assertEqual(committed, evidence["product_commit"])
        self.assertEqual(["alpha.dart"], evidence["attributed_files"])

    def test_integrating_the_same_commit_twice_is_detected_not_duplicated(self):
        realized = self.realize()
        self.executor_edits(realized)
        first = self.run_integration(realized=realized)
        head = sh(self.repo, "rev-parse", "Canary")
        # Retry after a lost receipt: the commit is still the branch tip and is
        # already on Canary, so it must be recognised rather than landed twice.
        second = self.run_integration(realized=realized)
        self.assertEqual("already-present", second["outcome"])
        self.assertEqual(first["product_commit"], second["product_commit"])
        self.assertEqual(head, sh(self.repo, "rev-parse", "Canary"))

    def test_integration_is_serialized_across_concurrent_callers(self):
        seats = ("backend-1", "backend-2", "backend-3")
        realizations = {}
        for index, seat in enumerate(seats):
            realized = realize_workspace("KAN-90%d" % index, seat,
                                         {"repository_root": self.repo,
                                          "working_directory": None,
                                          "worktree_path": None,
                                          "expected_revision": None,
                                          "mutation_mode": "repository_edit"},
                                         root=self.wtroot)
            with open(os.path.join(realized["path"], "alpha.dart"), "a") as handle:
                handle.write("// %s change\n" % seat)
            realizations[seat] = realized

        results, errors = {}, {}
        barrier = threading.Barrier(len(seats))

        def land(index, seat):
            record = validated_task()
            record["work_item_id"] = "KAN-90%d" % index
            record["surfaces"] = list(SURFACES)
            record["ownership"] = {"seat_id": seat, "claim_ref": "claim"}
            try:
                barrier.wait(timeout=10)
                results[seat] = integrate_validated_work(
                    "KAN-90%d" % index, seat, record, issue(),
                    realizations[seat], repo=self.repo, root=self.wtroot,
                    interventions=[])
            except Exception as exc:                       # noqa: BLE001
                errors[seat] = exc

        threads = [threading.Thread(target=land, args=(i, s))
                   for i, s in enumerate(seats)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        landed = [r for r in results.values() if r["outcome"] == INTEGRATED]
        conflicted = [e for e in errors.values()
                      if getattr(e, "outcome", None) == INTEGRATION_CONFLICT]
        # Whatever the mix, history is linear and nothing was lost: every
        # integration that reported success is an ancestor of Canary, and the
        # count of Canary commits equals the count of successful integrations.
        self.assertEqual(len(seats), len(landed) + len(conflicted) + len(
            [r for r in results.values() if r["outcome"] != INTEGRATED]))
        for outcome in landed:
            self.assertEqual(0, subprocess.run(
                ["git", "-C", self.repo, "merge-base", "--is-ancestor",
                 outcome["integrated_as"], "Canary"]).returncode)
        new_commits = sh(self.repo, "log", "--format=%H",
                         "%s..Canary" % realizations["backend-1"]["expected_revision"])
        self.assertEqual(len(landed), len([c for c in new_commits.splitlines() if c]))
        self.assertEqual("", sh(self.repo, "status", "--porcelain"))
        self.assert_main_untouched()


class WorkspaceLifecycleTests(IntegrationTestCase):
    def test_a_successful_integration_makes_a_clean_workspace_releasable(self):
        realized = self.realize()
        self.executor_edits(realized)
        evidence = self.run_integration(realized=realized)
        decision, reason = release_decision(None, validated_task(), realized, evidence)
        self.assertEqual(RELEASE, decision)
        self.assertIn("integrated", reason)
        outcome = conclude_workspace("KAN-900", "backend-1", None, validated_task(),
                                     realized, root=self.wtroot, integration=evidence)
        self.assertEqual("released", outcome["workspace_status"])
        self.assertFalse(os.path.isdir(realized["path"]))
        self.assertTrue(outcome["workspace_branch_kept"])

    def test_a_conflict_preserves_the_workspace_for_remediation(self):
        realized = self.realize()
        conflicted = {"outcome": INTEGRATION_CONFLICT, "conflict_paths": ["alpha.dart"]}
        decision, reason = release_decision(None, validated_task(), realized, conflicted)
        self.assertEqual(PRESERVE, decision)
        self.assertIn("remediation", reason)
        outcome = conclude_workspace("KAN-900", "backend-1", None, validated_task(),
                                     realized, root=self.wtroot,
                                     integration=conflicted)
        self.assertEqual("preserved", outcome["workspace_status"])
        self.assertTrue(os.path.isdir(realized["path"]))

    def test_an_integrated_but_still_dirty_workspace_is_preserved(self):
        realized = self.realize()
        self.executor_edits(realized)
        evidence = self.run_integration(realized=realized)
        with open(os.path.join(realized["path"], "beta.dart"), "a") as handle:
            handle.write("// work that did not go into the commit\n")
        decision, reason = release_decision(None, validated_task(), realized, evidence)
        self.assertEqual(PRESERVE, decision)
        self.assertIn("uncommitted", reason)

    def test_no_integration_yet_still_follows_the_validation_preservation_rule(self):
        realized = self.realize()
        decision, reason = release_decision(None, validated_task(), realized, None)
        self.assertEqual(PRESERVE, decision)
        self.assertIn("qa", reason)


class ControllerIntegrateCommandTests(IntegrationTestCase):
    """CEO runs `integrate KAN-XXX`; Thebes does the git."""

    def _run(self, record=None, prepare=None, interventions=None,
             integration_branch=None):
        state = IntegrationStore(record or validated_task())
        realized_holder = {}

        def allocator(work_item_id, seat_id, workspace):
            realized = realize_workspace(work_item_id, seat_id,
                                         dict(workspace, repository_root=self.repo),
                                         root=self.wtroot)
            realized_holder["realized"] = realized
            if prepare:
                prepare(realized)
            return realized

        def concluder(work_item_id, seat_id, result, task_record, realized,
                      integration=None):
            return conclude_workspace(work_item_id, seat_id, result, task_record,
                                      realized, root=self.wtroot,
                                      integration=integration)

        outcome = controller_integrate(
            "KAN-900", state_store=state, jira_client=Jira(),
            workspace_allocator=allocator, workspace_concluder=concluder,
            interventions=interventions if interventions is not None else [],
            integration_branch=integration_branch, worktree_root=self.wtroot)
        return outcome, state, realized_holder.get("realized")

    def test_the_whole_command_lands_validated_work_without_human_git(self):
        outcome, state, realized = self._run(prepare=self.executor_edits)
        self.assertEqual(INTEGRATED, outcome["integration_status"])
        self.assertEqual("backend-1", outcome["seat_id"])
        self.assertEqual("qa", outcome["validation_route"])
        self.assertEqual("pass", outcome["validation_result"])
        self.assertEqual(["alpha.dart"], outcome["attributed_files"])
        self.assertEqual(40, len(outcome["product_commit"]))
        self.assertEqual(outcome["integrated_as"], sh(self.repo, "rev-parse", "Canary"))
        self.assertFalse(outcome["remediation_required"])
        self.assertEqual("recorded", outcome["receipt_status"])
        self.assertEqual("released", outcome["workspace_status"])
        self.assertFalse(os.path.isdir(realized["path"]))
        self.assert_main_untouched()

    def test_the_receipt_answers_every_evidence_question(self):
        outcome, state, _ = self._run(prepare=self.executor_edits)
        self.assertEqual(1, len(state.integration_receipts))
        receipt = state.integration_receipts[0]
        self.assertEqual("KAN-900", receipt["work_item_id"])
        self.assertEqual("backend-1", receipt["seat_id"])
        self.assertEqual(INTEGRATED, receipt["outcome"])
        self.assertEqual(outcome["product_commit"], receipt["product_commit"])
        self.assertEqual(outcome["integrated_as"], receipt["integrated_as"])
        self.assertEqual("Canary", receipt["integration_branch"])
        self.assertEqual("exec/backend-1/KAN-900", receipt["source_branch"])
        self.assertEqual("qa", receipt["validation_route"])
        self.assertEqual("pass", receipt["validation_result"])
        self.assertEqual(["alpha.dart"], receipt["attributed_files"])
        self.assertFalse(receipt["remediation_required"])

    def test_an_unvalidated_item_is_refused_and_the_refusal_is_recorded(self):
        outcome, state, _ = self._run(record=validated_task(result="pending"),
                                      prepare=self.executor_edits)
        self.assertEqual(VALIDATION_NOT_PASSED, outcome["integration_status"])
        self.assertIn("review-not-passed", outcome["blocker"])
        self.assertIsNone(outcome["product_commit"])
        self.assertEqual("recorded", outcome["receipt_status"])
        self.assertEqual(VALIDATION_NOT_PASSED, state.integration_receipts[0]["outcome"])
        # The workspace was never even allocated for a refused gate.
        self.assertEqual("not-allocated", outcome["workspace_status"])
        self.assertEqual("Canary", sh(self.repo, "rev-parse", "--abbrev-ref", "HEAD"))

    def test_a_conflict_is_reported_as_remediation_not_as_a_product_failure(self):
        def prepare(realized):
            self.executor_edits(realized, text="// executor version\n")
            with open(os.path.join(self.repo, "alpha.dart"), "a") as handle:
                handle.write("// canary version\n")
            sh(self.repo, "commit", "-qam", "chore: conflicting canary work")

        canary_before = None
        outcome, state, realized = self._run(prepare=prepare)
        self.assertEqual(INTEGRATION_CONFLICT, outcome["integration_status"])
        self.assertTrue(outcome["remediation_required"])
        self.assertIn("alpha.dart", outcome["conflict_paths"])
        self.assertEqual("preserved", outcome["workspace_status"])
        self.assertTrue(os.path.isdir(realized["path"]))
        self.assertEqual(INTEGRATION_CONFLICT, state.integration_receipts[0]["outcome"])
        self.assertTrue(state.integration_receipts[0]["remediation_required"])
        self.assertEqual("", sh(self.repo, "status", "--porcelain"))
        self.assert_main_untouched()

    def test_maintenance_mode_refuses_integration_outright(self):
        state = IntegrationStore()
        state.current_operating_mode = lambda: "SYSTEM_MAINTENANCE"
        outcome = controller_integrate("KAN-900", state_store=state,
                                       jira_client=Jira())
        self.assertEqual("system-maintenance-active", outcome["blocker"])
        self.assertEqual("not-started", outcome["integration_status"])

    def test_unowned_work_is_refused(self):
        record = validated_task()
        record["ownership"] = None
        outcome, _, _ = self._run(record=record)
        self.assertEqual("not-owned", outcome["blocker"])

    def test_no_change_work_records_its_truth_and_releases(self):
        outcome, state, realized = self._run()
        self.assertEqual(NO_PRODUCT_COMMIT_REQUIRED, outcome["integration_status"])
        self.assertIsNone(outcome["product_commit"])
        self.assertFalse(outcome["remediation_required"])
        self.assertEqual(NO_PRODUCT_COMMIT_REQUIRED,
                         state.integration_receipts[0]["outcome"])
        self.assertEqual("released", outcome["workspace_status"])

    def test_no_jira_write_happens_anywhere_in_the_command(self):
        jira_double = Jira()
        state = IntegrationStore()

        def allocator(work_item_id, seat_id, workspace):
            realized = realize_workspace(work_item_id, seat_id,
                                         dict(workspace, repository_root=self.repo),
                                         root=self.wtroot)
            self.executor_edits(realized)
            return realized

        controller_integrate("KAN-900", state_store=state, jira_client=jira_double,
                             worktree_root=self.wtroot, workspace_allocator=allocator,
                             workspace_concluder=lambda *a, **k: {
                                 "workspace_status": "preserved",
                                 "workspace_reason": "fixture",
                                 "workspace_path": None,
                                 "workspace_branch_kept": True},
                             interventions=[])
        self.assertEqual(["KAN-900"], jira_double.reads)
        self.assertEqual([], jira_double.writes)


class RealRepositoryUntouchedTests(IntegrationTestCase):
    def test_this_suite_never_reaches_the_real_product_repository(self):
        realized = self.realize()
        self.executor_edits(realized)
        self.run_integration(realized=realized)
        real = os.path.join(ROOT, "Dabbler", "dabbler-code")
        if not os.path.isdir(real):
            self.skipTest("the real Product checkout is not present")
        listed = subprocess.run(["git", "-C", real, "worktree", "list"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("KAN-900", listed)
        branches = subprocess.run(["git", "-C", real, "branch", "--list",
                                   "exec/*/KAN-90*"], capture_output=True,
                                  text=True).stdout
        self.assertEqual("", branches.strip())
        subject = subprocess.run(["git", "-C", real, "log", "-1", "--format=%s",
                                  "Canary"], capture_output=True, text=True).stdout
        self.assertNotIn("KAN-900", subject)


if __name__ == "__main__":
    unittest.main(verbosity=2)
