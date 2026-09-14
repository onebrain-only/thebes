#!/usr/bin/env python3
"""WORKSPACE ALLOCATION IN THE EXECUTION PATH — a real isolated Product worktree.

Every test runs against a SYNTHETIC git repository in a temp directory. Nothing
here reaches ~/Desktop/Thebes-Canonical/Dabbler/dabbler-code, and nothing writes
Jira, Supabase or Persistent State on disk: a suite that proved isolation by
allocating inside the real Product checkout would be the defect it claims to
defend against.
"""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.controller import execute  # noqa: E402
from agent.controller.workspace import (  # noqa: E402
    PRESERVE,
    RELEASE,
    WorkspaceUnavailable,
    conclude_workspace,
    realize_workspace,
    release_decision,
)
from agent.controller.tests.test_canonical_intent import (  # noqa: E402
    Authorization, Jira, Registry, State, issue, task,
)
from agent.execution.brief import CONTROL_PLANE_TOKENS  # noqa: E402
from agent.execution.claude import ClaudeProvider  # noqa: E402
from agent.execution.provider import (  # noqa: E402
    ExecutionResult, ExecutionStatus, Failure, FailureCode,
)
from agent.state import worktrees  # noqa: E402


def sh(cwd, *args):
    result = subprocess.run(["git", "-C", cwd] + list(args),
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("git %s -> %s" % (" ".join(args), result.stderr))
    return result.stdout.strip()


def fresh_repo():
    """A synthetic Product repo: a Canary branch, a protected main, two files."""
    tmp = tempfile.mkdtemp()
    repo = os.path.join(tmp, "product")
    os.makedirs(repo)
    sh(repo, "init", "-q", "-b", "main")
    sh(repo, "config", "user.email", "test@example.invalid")
    sh(repo, "config", "user.name", "test")
    for name in ("alpha.dart", "beta.dart"):
        with open(os.path.join(repo, name), "w") as handle:
            handle.write("// %s\n" % name)
    sh(repo, "add", "-A")
    sh(repo, "commit", "-qm", "baseline")
    sh(repo, "branch", "Canary")
    sh(repo, "checkout", "-q", "Canary")
    return tmp, repo, os.path.join(tmp, "wt")


def result_of(status, failure=None):
    return ExecutionResult(invocation_id="inv-1", status=status, summary="fixture",
                           failure=failure, provider_id="claude-code")


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def workspace(self, **changes):
        value = {"repository_root": self.repo, "working_directory": self.repo,
                 "worktree_path": None, "expected_revision": None,
                 "mutation_mode": "repository_edit"}
        value.update(changes)
        return value

    def realize(self, work_item_id="KAN-900", seat_id="backend-1", **changes):
        return realize_workspace(work_item_id, seat_id, self.workspace(**changes),
                                 root=self.wtroot)


class AllocationTests(WorkspaceTestCase):
    def test_allocation_creates_a_real_isolated_tree_bound_to_seat_and_item(self):
        realized = self.realize()
        path = realized["path"]
        self.assertTrue(os.path.isdir(path))
        self.assertEqual(("backend-1", "KAN-900"),
                         worktrees.owner_of(path, root=self.wtroot))
        self.assertEqual("exec/backend-1/KAN-900", realized["branch"])
        self.assertEqual("exec/backend-1/KAN-900", sh(path, "rev-parse",
                                                      "--abbrev-ref", "HEAD"))
        self.assertNotEqual(os.path.realpath(path), os.path.realpath(self.repo))
        self.assertFalse(realized["reused"])
        # The executor's working directory is the isolated tree, not the checkout.
        self.assertEqual(path, realized["workspace"]["working_directory"])
        self.assertEqual(path, realized["workspace"]["worktree_path"])

    def test_expected_revision_is_git_truth_and_not_invented(self):
        realized = self.realize()
        self.assertEqual(sh(realized["path"], "rev-parse", "HEAD"),
                         realized["expected_revision"])
        self.assertEqual(sh(self.repo, "rev-parse", "Canary"),
                         realized["expected_revision"])
        self.assertEqual(realized["expected_revision"],
                         realized["workspace"]["expected_revision"])
        self.assertEqual(40, len(realized["expected_revision"]))

    def test_the_branch_starts_from_canary_and_never_from_protected_main(self):
        realized = self.realize()
        self.assertEqual("Canary", realized["base"])
        self.assertNotIn(realized["branch"], worktrees.PROTECTED_BRANCHES)
        with self.assertRaises(WorkspaceUnavailable) as caught:
            realize_workspace("KAN-900", "backend-1", self.workspace(),
                              root=self.wtroot, base="main")
        self.assertEqual("workspace-allocation-refused", caught.exception.reason)
        self.assertIn("protected-branch", caught.exception.detail)

    def test_same_seat_same_work_item_reuses_the_existing_tree(self):
        first = self.realize()
        with open(os.path.join(first["path"], "alpha.dart"), "a") as handle:
            handle.write("// work in progress\n")
        second = self.realize()
        self.assertEqual(first["path"], second["path"])
        self.assertTrue(second["reused"])
        # Reuse means reuse: the in-progress edit is still there.
        with open(os.path.join(second["path"], "alpha.dart")) as handle:
            self.assertIn("work in progress", handle.read())

    def test_a_different_seat_gets_a_different_tree(self):
        mine = self.realize(seat_id="backend-1")
        theirs = self.realize(seat_id="backend-2")
        self.assertNotEqual(mine["path"], theirs["path"])
        self.assertEqual(("backend-2", "KAN-900"),
                         worktrees.owner_of(theirs["path"], root=self.wtroot))

    def test_a_foreign_branch_standing_at_our_path_is_refused(self):
        realized = self.realize()
        # Somebody checked another work item's branch out in this seat's tree.
        sh(self.repo, "branch", "exec/backend-1/KAN-800", "Canary")
        sh(realized["path"], "checkout", "-q", "exec/backend-1/KAN-800")
        with self.assertRaises(WorkspaceUnavailable) as caught:
            self.realize()
        self.assertEqual("workspace-branch-mismatch", caught.exception.reason)
        self.assertIn("exec/backend-1/KAN-800", caught.exception.detail)

    def test_an_occupied_unmanaged_path_is_refused_not_overwritten(self):
        path = worktrees.worktree_path("backend-1", "KAN-900", root=self.wtroot)
        os.makedirs(path)
        with open(os.path.join(path, "someone-elses.dart"), "w") as handle:
            handle.write("// not a registered worktree\n")
        with self.assertRaises(WorkspaceUnavailable) as caught:
            self.realize()
        self.assertEqual("workspace-allocation-refused", caught.exception.reason)
        self.assertIn("occupied", caught.exception.detail)
        # The stranger's file is still there.
        self.assertTrue(os.path.isfile(os.path.join(path, "someone-elses.dart")))

    def test_a_missing_or_non_git_repository_is_a_bounded_failure(self):
        for root, reason in ((os.path.join(self.tmp, "nowhere"),
                              "workspace-repository-unavailable"),
                             (None, "workspace-repository-unresolved")):
            with self.subTest(reason=reason):
                with self.assertRaises(WorkspaceUnavailable) as caught:
                    realize_workspace("KAN-900", "backend-1",
                                      self.workspace(repository_root=root),
                                      root=self.wtroot)
                self.assertEqual(reason, caught.exception.reason)

    def test_the_canonical_checkout_is_never_the_allocated_workspace(self):
        realized = self.realize()
        self.assertNotEqual(os.path.realpath(self.repo),
                            os.path.realpath(realized["path"]))
        registered = {entry["path"] for entry in worktrees.list_worktrees(self.repo)}
        self.assertIn(os.path.realpath(realized["path"]), registered)
        # And the canonical checkout is untouched by the allocation.
        self.assertEqual("Canary", sh(self.repo, "rev-parse", "--abbrev-ref", "HEAD"))
        self.assertEqual("", sh(self.repo, "status", "--porcelain"))


class ReleasePolicyTests(WorkspaceTestCase):
    def decide(self, status, lifecycle=None, route="qa", failure=None, dirty=False,
               reused=False):
        realized = self.realize()
        realized["reused"] = reused
        if dirty:
            with open(os.path.join(realized["path"], "alpha.dart"), "a") as handle:
                handle.write("// uncommitted product work\n")
        record = task()
        record["lifecycle"] = {"canonical": lifecycle} if lifecycle else {}
        record["execution_profile"]["validation_route"] = route
        return release_decision(result_of(status, failure), record, realized), realized

    def test_needs_input_preserves_the_workspace_for_continuation(self):
        (decision, reason), _ = self.decide(ExecutionStatus.NEEDS_INPUT)
        self.assertEqual(PRESERVE, decision)
        self.assertIn("continuation", reason)

    def test_pending_validation_does_not_release_early(self):
        for route in ("peer", "qa", "self"):
            with self.subTest(route=route):
                (decision, reason), _ = self.decide(
                    ExecutionStatus.COMPLETED, lifecycle="review", route=route)
                self.assertEqual(PRESERVE, decision)
                self.assertIn(route, reason)

    def test_execution_failure_keeps_its_evidence(self):
        (decision, reason), _ = self.decide(ExecutionStatus.EXECUTION_FAILED,
                                            failure=Failure(FailureCode.EXECUTION_FAILURE,
                                                            "product tests failed"))
        self.assertEqual(PRESERVE, decision)
        self.assertIn("evidence", reason)

    def test_provider_failure_before_mutation_is_safe_to_clean_up(self):
        (decision, reason), _ = self.decide(
            ExecutionStatus.PROVIDER_FAILED,
            failure=Failure(FailureCode.UNAVAILABLE, "provider unavailable"))
        self.assertEqual(RELEASE, decision)
        self.assertIn("before-any-product-mutation", reason)

    def test_provider_failure_never_deletes_work_that_is_already_there(self):
        for dirty, reused, expected in ((True, False, "uncommitted"),
                                        (False, True, "predates")):
            with self.subTest(dirty=dirty, reused=reused):
                (decision, reason), _ = self.decide(
                    ExecutionStatus.PROVIDER_FAILED, dirty=dirty, reused=reused,
                    failure=Failure(FailureCode.UNAVAILABLE, "provider unavailable"))
                self.assertEqual(PRESERVE, decision)
                self.assertIn(expected, reason)

    def test_a_canonically_done_work_item_releases_a_clean_workspace(self):
        (decision, reason), _ = self.decide(ExecutionStatus.COMPLETED, lifecycle="done")
        self.assertEqual(RELEASE, decision)
        self.assertIn("canonically-done", reason)

    def test_a_done_work_item_with_uncommitted_work_is_still_preserved(self):
        (decision, reason), _ = self.decide(ExecutionStatus.COMPLETED,
                                            lifecycle="done", dirty=True)
        self.assertEqual(PRESERVE, decision)
        self.assertIn("uncommitted", reason)

    def test_release_actually_removes_the_tree_and_keeps_the_branch(self):
        realized = self.realize()
        record = task()
        record["lifecycle"] = {"canonical": "done"}
        outcome = conclude_workspace("KAN-900", "backend-1",
                                     result_of(ExecutionStatus.COMPLETED), record,
                                     realized, root=self.wtroot)
        self.assertEqual("released", outcome["workspace_status"])
        self.assertTrue(outcome["workspace_branch_kept"])
        self.assertFalse(os.path.isdir(realized["path"]))
        # The branch survives: the commits on it are not this decision's to discard.
        self.assertIn("exec/backend-1/KAN-900",
                      sh(self.repo, "branch", "--list", "exec/backend-1/KAN-900"))

    def test_a_dirty_tree_survives_conclude_as_a_fact_not_an_error(self):
        realized = self.realize()
        with open(os.path.join(realized["path"], "alpha.dart"), "a") as handle:
            handle.write("// uncommitted product work\n")
        record = task()
        record["lifecycle"] = {"canonical": "done"}
        outcome = conclude_workspace("KAN-900", "backend-1",
                                     result_of(ExecutionStatus.COMPLETED), record,
                                     realized, root=self.wtroot)
        self.assertEqual("preserved", outcome["workspace_status"])
        self.assertTrue(os.path.isdir(realized["path"]))


class ControllerWorkspaceFlowTests(WorkspaceTestCase):
    """CEO key in, real isolated workspace out, lifecycle-aware on the way back."""

    def _run(self, record=None, transport=None, base=None):
        state, jira_double = State(record), Jira()
        wakes = []

        def allocator(work_item_id, seat_id, workspace):
            return realize_workspace(work_item_id, seat_id,
                                     dict(workspace, repository_root=self.repo),
                                     root=self.wtroot, base=base)

        def concluder(work_item_id, seat_id, result, observed, realized):
            return conclude_workspace(work_item_id, seat_id, result, observed,
                                      realized, root=self.wtroot)

        def record_wake(wake):
            # The provider's working directory must exist AT INVOCATION TIME.
            wakes.append((wake, os.path.isdir(wake.workspace.working_directory),
                          sh(wake.workspace.working_directory, "rev-parse", "HEAD")))
            return "fixture complete" if transport is None else transport(wake)

        outcome = execute("KAN-900", None, authorization=Authorization(),
                          state_store=state, jira_client=jira_double,
                          seat_registry=Registry(),
                          providers=(ClaudeProvider(record_wake),),
                          workspace_allocator=allocator,
                          workspace_concluder=concluder)
        return outcome, state, jira_double, wakes

    def test_execute_allocates_before_dispatch_and_the_cwd_exists(self):
        outcome, state, jira_double, wakes = self._run()
        self.assertEqual("completed", outcome["execution_status"])
        self.assertEqual(1, len(wakes))
        wake, cwd_existed, head = wakes[0]
        self.assertTrue(cwd_existed, "provider cwd must exist at invocation time")
        self.assertEqual(outcome["workspace_path"], wake.workspace.working_directory)
        self.assertEqual("exec/backend-1/KAN-900", outcome["workspace_branch"])
        self.assertEqual(head, wake.workspace.expected_revision)
        self.assertEqual(head, outcome["expected_revision"])
        self.assertEqual(["mode", "observe", "claim", "continuation", "lease-open",
                          "receipt", "lease-close"], state.events)
        self.assertEqual([], jira_double.writes)

    def test_the_request_carries_the_isolated_tree_not_the_canonical_checkout(self):
        _, _, _, wakes = self._run()
        wake = wakes[0][0]
        self.assertEqual(("backend-1", "KAN-900"),
                         worktrees.owner_of(wake.workspace.working_directory,
                                            root=self.wtroot))
        self.assertNotEqual(os.path.realpath(self.repo),
                            os.path.realpath(wake.workspace.working_directory))
        self.assertEqual(self.repo, wake.workspace.repository_root)

    def test_the_executor_brief_stays_product_only(self):
        _, _, _, wakes = self._run()
        prompt = wakes[0][0].prompt
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), prompt.lower())
        self.assertIn("- Work item ID: KAN-900", prompt)
        self.assertIn("- Working directory:", prompt)
        self.assertNotIn("lease-900", prompt)
        self.assertNotIn("PRODUCT_EXECUTION", prompt)

    def test_allocation_failure_means_zero_provider_invocations(self):
        outcome, state, _, wakes = self._run(base="main")
        self.assertEqual("workspace-allocation-refused", outcome["workspace_status"])
        self.assertIn("protected-branch", outcome["blocker"])
        self.assertEqual([], wakes)
        self.assertEqual("not-started", outcome["execution_status"])
        self.assertEqual("not-opened", outcome["lease_closure_status"])
        # Claimed, but no lease was ever opened and no provider was ever reached.
        self.assertEqual(["mode", "observe", "claim"], state.events)
        # And the canonical checkout was not used as a fallback.
        self.assertEqual("Canary", sh(self.repo, "rev-parse", "--abbrev-ref", "HEAD"))
        self.assertEqual("", sh(self.repo, "status", "--porcelain"))

    def test_needs_input_preserves_the_workspace_through_the_whole_flow(self):
        def needs_input(wake):
            return {"status": "needs_input", "summary": "native permission required",
                    "escalation": {"reason": "Supabase migration tool required",
                                   "required_authority": "CEO"}}
        outcome, state, _, wakes = self._run(transport=needs_input)
        self.assertEqual("needs_input", outcome["execution_status"])
        self.assertEqual("preserved", outcome["workspace_status"])
        self.assertIn("continuation", outcome["workspace_reason"])
        self.assertTrue(os.path.isdir(outcome["workspace_path"]))
        self.assertEqual("closed", outcome["lease_closure_status"])
        self.assertEqual(1, state.events.count("receipt"))

    def test_a_continuation_reuses_the_same_durable_workspace(self):
        first, _, _, _ = self._run()
        second, _, _, wakes = self._run()
        self.assertEqual(first["workspace_path"], second["workspace_path"])
        self.assertEqual(first["workspace_branch"], second["workspace_branch"])
        self.assertTrue(second["workspace_reused"])
        self.assertTrue(os.path.isdir(second["workspace_path"]))

    def test_provider_failure_closes_the_lease_and_leaks_no_workspace(self):
        class Unavailable:
            def capabilities(self):
                from agent.execution.provider import (
                    ExecutionFeature, ProviderCapabilities,
                )
                return ProviderCapabilities(
                    provider_id="claude-code", available=False,
                    availability_reason="fixture unavailable",
                    execution_features=frozenset(ExecutionFeature),
                    supported_model_intents=frozenset(),
                    supported_reasoning_efforts=frozenset())

            def execute(self, request):    # pragma: no cover - never selected
                raise AssertionError("an unavailable provider must not execute")

        state = State()

        def allocator(work_item_id, seat_id, workspace):
            return realize_workspace(work_item_id, seat_id,
                                     dict(workspace, repository_root=self.repo),
                                     root=self.wtroot)

        def concluder(work_item_id, seat_id, result, observed, realized):
            return conclude_workspace(work_item_id, seat_id, result, observed,
                                      realized, root=self.wtroot)

        outcome = execute("KAN-900", None, authorization=Authorization(),
                          state_store=state, jira_client=Jira(),
                          seat_registry=Registry(), providers=(Unavailable(),),
                          workspace_allocator=allocator, workspace_concluder=concluder)
        self.assertEqual("provider_failed", outcome["execution_status"])
        self.assertEqual("released", outcome["workspace_status"])
        self.assertFalse(os.path.isdir(outcome["workspace_path"]))
        self.assertEqual("closed", outcome["lease_closure_status"])
        self.assertEqual(1, state.events.count("lease-close"))
        self.assertEqual(1, state.events.count("receipt"))

    def test_nothing_in_this_suite_touched_the_real_product_repository(self):
        self._run()
        real = os.path.join(ROOT, "Dabbler", "dabbler-code")
        if not os.path.isdir(real):
            self.skipTest("the real Product checkout is not present")
        listed = subprocess.run(["git", "-C", real, "worktree", "list"],
                                capture_output=True, text=True).stdout
        self.assertNotIn("KAN-900", listed)
        branches = subprocess.run(["git", "-C", real, "branch", "--list",
                                   "exec/*/KAN-900"], capture_output=True,
                                  text=True).stdout
        self.assertEqual("", branches.strip())


if __name__ == "__main__":
    unittest.main(verbosity=2)
