#!/usr/bin/env python3
"""PEER-FAIL OWNERSHIP HANDOFF — the transfer doctrine, made whole.

The REAL `agent/state/store.py` runs here against a temp runtime, so the
transfer's authority checks, its CAS and its atomicity are the canonical ones.
Git is a synthetic repository, Jira and the providers are doubles. No real Jira,
Product repository or Supabase is reachable.
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

import store                                                       # noqa: E402
import queue as state_queue                                        # noqa: E402

from agent.controller import execute                               # noqa: E402
from agent.controller.validation import (                          # noqa: E402
    FAIL, PASS, VALIDATION_FAILED, VALIDATION_PASSED,
)
from agent.controller.workspace import conclude_workspace, realize_workspace  # noqa: E402
from agent.controller.tests.test_canonical_intent import Authorization  # noqa: E402
from agent.controller.tests.test_validation_dispatch import (      # noqa: E402
    BACKEND_DEV, DONE, PEER_REVIEW, SEATS, Jira, ProductExecutor,
    RoutingProvider, Validator, _Roster, isolated_runtime, make_task,
)
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402


class HandoffTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_tmp = isolated_runtime()
        self.addCleanup(shutil.rmtree, self.runtime_tmp, ignore_errors=True)
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.main_before = sh(self.repo, "rev-parse", "main")

    def failed_peer_review(self, work_item_id="KAN-900", reviewer="backend-2",
                           owner="backend-1"):
        """Drive real state to the exact moment before the transfer."""
        task = make_task(work_item_id, owner=owner)
        task = store.release(work_item_id, owner, task["revision"],
                             "execution of %s" % work_item_id,
                             authority="orchestrator")
        task = store.observe_lifecycle(work_item_id, task["revision"], PEER_REVIEW)
        task = store.open_review_context(work_item_id, task["revision"],
                                         opened_by="orchestrator",
                                         evidenced_reviewer=reviewer)
        return store.record_review_result(work_item_id, task["revision"], reviewer,
                                          FAIL, "ref:peer-fail")

    def edit(self, path, text="// remediation\n"):
        with open(os.path.join(path, "alpha.dart"), "a") as handle:
            handle.write(text)


class TransferInvariantTests(HandoffTestCase):
    """After a successful transfer the state is internally consistent."""

    def test_the_transfer_is_complete_in_one_write(self):
        failed = self.failed_peer_review()
        self.assertIsNone(failed["ownership"])
        transferred = store.peer_fail_transfer("KAN-900", failed["revision"],
                                               "backend-2", "ref:transfer")
        # 1-6: every field the doctrine names, in one record.
        self.assertEqual("backend-2", transferred["ownership"]["seat_id"])
        self.assertEqual("ref:transfer", transferred["ownership"]["claim_ref"])
        self.assertEqual(["backend-2"], store.evidenced_executors(transferred))
        self.assertEqual("self", transferred["review_context"]["review_type"])
        self.assertEqual("backend-2", transferred["review_context"]["review_owner"])
        self.assertEqual("pending", transferred["review_context"]["review_result"])
        self.assertEqual("backend-1",
                         transferred["review_context"]["previous_owner"])
        self.assertEqual(2, transferred["review_context"]["review_cycle"])
        self.assertEqual("backend",
                         transferred["execution_profile"]["required_capability"])

    def test_the_item_returns_to_its_capability_execution_status(self):
        failed = self.failed_peer_review()
        transferred = store.peer_fail_transfer("KAN-900", failed["revision"],
                                               "backend-2", "ref:transfer")
        import board
        self.assertEqual(BACKEND_DEV, board.execution_status_for(
            transferred["execution_profile"]["required_capability"]))
        observed = store.observe_lifecycle("KAN-900", transferred["revision"],
                                           BACKEND_DEV)
        self.assertEqual(BACKEND_DEV, observed["lifecycle"]["jira_status_id"])
        # Owner and evidence survive the lifecycle observation.
        self.assertEqual("backend-2", observed["ownership"]["seat_id"])

    def test_no_fresh_claim_is_needed_and_none_would_be_accepted(self):
        failed = self.failed_peer_review()
        transferred = store.peer_fail_transfer("KAN-900", failed["revision"],
                                               "backend-2", "ref:transfer")
        # The item is owned, so the ordinary claim path correctly refuses — the
        # transfer replaced it rather than routing through it.
        with self.assertRaisesRegex(store.StateError, "already-owned"):
            store.claim("KAN-900", "backend-2", "ref", transferred["revision"],
                        capability_of_seat="backend")

    def test_the_review_cycle_advances_exactly_once(self):
        failed = self.failed_peer_review()
        self.assertEqual(1, failed["review_context"]["review_cycle"])
        transferred = store.peer_fail_transfer("KAN-900", failed["revision"],
                                               "backend-2", "ref:transfer")
        self.assertEqual(2, transferred["review_context"]["review_cycle"])
        # A replay cannot advance it again.
        with self.assertRaisesRegex(store.StateError, "PEER route only"):
            store.peer_fail_transfer("KAN-900", transferred["revision"],
                                     "backend-2", "ref:transfer")
        self.assertEqual(2, store.read("task", "KAN-900")
                         ["review_context"]["review_cycle"])


class AuthorityBoundaryTests(HandoffTestCase):
    """Who may take over, and every way of getting it wrong."""

    def _assert_untouched(self, work_item_id, before, call):
        with self.assertRaises(store.StateError) as caught:
            call()
        after = store.read("task", work_item_id)
        # 14: a refusal writes nothing at all.
        self.assertEqual(before, after)
        return caught.exception

    def test_a_pending_peer_review_cannot_be_taken_over(self):
        task = make_task()
        task = store.release("KAN-900", "backend-1", task["revision"], "ref",
                             authority="orchestrator")
        task = store.observe_lifecycle("KAN-900", task["revision"], PEER_REVIEW)
        opened = store.open_review_context("KAN-900", task["revision"],
                                           opened_by="orchestrator",
                                           evidenced_reviewer="backend-2")
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(opened),
            lambda: store.peer_fail_transfer("KAN-900", opened["revision"],
                                             "backend-2", "ref"))
        self.assertIn("review-not-failed", str(error))

    def test_a_passed_peer_review_cannot_be_taken_over(self):
        task = make_task()
        task = store.release("KAN-900", "backend-1", task["revision"], "ref",
                             authority="orchestrator")
        task = store.observe_lifecycle("KAN-900", task["revision"], PEER_REVIEW)
        opened = store.open_review_context("KAN-900", task["revision"],
                                           opened_by="orchestrator",
                                           evidenced_reviewer="backend-2")
        passed = store.record_review_result("KAN-900", opened["revision"],
                                            "backend-2", PASS, "ref:pass")
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(passed),
            lambda: store.peer_fail_transfer("KAN-900", passed["revision"],
                                             "backend-2", "ref"))
        self.assertIn("review-not-failed", str(error))

    def test_the_wrong_reviewer_is_rejected(self):
        failed = self.failed_peer_review()
        before = copy.deepcopy(failed)
        for impostor in ("backend-1", "qa", "frontend-1"):
            with self.subTest(impostor=impostor):
                error = self._assert_untouched(
                    "KAN-900", before,
                    lambda seat=impostor: store.peer_fail_transfer(
                        "KAN-900", failed["revision"], seat, "ref"))
                self.assertIn("only the recorded review owner", str(error))

    def test_the_orchestrator_cannot_become_the_remediation_owner(self):
        failed = self.failed_peer_review()
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(failed),
            lambda: store.peer_fail_transfer("KAN-900", failed["revision"],
                                             "orchestrator", "ref"))
        self.assertIn("only the recorded review owner", str(error))

    def test_a_qa_review_context_cannot_use_the_peer_transfer(self):
        task = make_task(characteristics={"user_visible_runtime": True})
        task = store.release("KAN-900", "backend-1", task["revision"], "ref",
                             authority="orchestrator")
        task = store.observe_lifecycle("KAN-900", task["revision"], "10009")
        opened = store.open_review_context("KAN-900", task["revision"],
                                           opened_by="orchestrator")
        failed = store.record_review_result("KAN-900", opened["revision"], "qa",
                                            FAIL, "ref:qa-fail")
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(failed),
            lambda: store.peer_fail_transfer("KAN-900", failed["revision"], "qa",
                                             "ref"))
        self.assertIn("PEER route only", str(error))

    def test_a_stale_revision_is_rejected(self):
        failed = self.failed_peer_review()
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(failed),
            lambda: store.peer_fail_transfer("KAN-900", failed["revision"] + 5,
                                             "backend-2", "ref"))
        self.assertIn("stale write refused", str(error))

    def test_a_wrong_review_cycle_is_rejected(self):
        failed = self.failed_peer_review()
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(failed),
            lambda: store.peer_fail_transfer("KAN-900", failed["revision"],
                                             "backend-2", "ref", expected_cycle=7))
        self.assertIn("stale-review-cycle", str(error))
        # The real cycle is accepted.
        transferred = store.peer_fail_transfer("KAN-900", failed["revision"],
                                               "backend-2", "ref", expected_cycle=1)
        self.assertEqual(2, transferred["review_context"]["review_cycle"])

    def test_a_reviewer_who_already_owns_other_work_cannot_take_this_too(self):
        other = make_task("KAN-901", owner="backend-2")
        self.assertEqual("backend-2", other["ownership"]["seat_id"])
        failed = self.failed_peer_review()
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(failed),
            lambda: store.peer_fail_transfer("KAN-900", failed["revision"],
                                             "backend-2", "ref"))
        self.assertIn("seat-already-owns", str(error))

    def test_a_transfer_requires_the_evidence_that_caused_it(self):
        failed = self.failed_peer_review()
        error = self._assert_untouched(
            "KAN-900", copy.deepcopy(failed),
            lambda: store.peer_fail_transfer("KAN-900", failed["revision"],
                                             "backend-2", ""))
        self.assertIn("evidence_ref is required", str(error))

    def test_the_executor_cannot_nominate_its_own_reviewer(self):
        # The reviewer is resolved by policy with the executors EXCLUDED, so a
        # context naming the executor never exists to be transferred from.
        task = make_task()
        task = store.release("KAN-900", "backend-1", task["revision"], "ref",
                             authority="orchestrator")
        task = store.observe_lifecycle("KAN-900", task["revision"], PEER_REVIEW)
        opened = store.open_review_context("KAN-900", task["revision"],
                                           opened_by="orchestrator",
                                           evidenced_reviewer="backend-1")
        self.assertIsNone(opened["review_context"]["review_owner"])
        with self.assertRaises(store.StateError):
            store.peer_fail_transfer("KAN-900", opened["revision"], "backend-1",
                                     "ref")


class FullPeerFailFlowTests(HandoffTestCase):
    """CEO key, PEER FAIL, remediation, SELF PASS, Done — no human step."""

    def _execute(self, verdict, jira, work_item_id="KAN-900"):
        product = ProductExecutor(edit=self.edit)
        validator = Validator(verdict)
        provider = RoutingProvider(product, validator)

        def allocator(item, seat_id, workspace):
            return realize_workspace(item, seat_id,
                                     dict(workspace, repository_root=self.repo),
                                     root=self.wtroot)

        def concluder(item, seat_id, result, task_record, realized, integration=None):
            return conclude_workspace(item, seat_id, result, task_record, realized,
                                      root=self.wtroot, integration=integration)

        outcome = execute(work_item_id, None, authorization=Authorization(),
                          state_store=store, jira_client=jira,
                          seat_registry=_Roster(), providers=(provider,),
                          workspace_allocator=allocator,
                          workspace_concluder=concluder, interventions=[],
                          worktree_root=self.wtroot, seats_by_capability=SEATS)
        return outcome, product, validator

    def test_peer_fail_recovers_end_to_end_with_no_human_intervention(self):
        make_task()
        jira = Jira()

        # ---- leg 1: execution, PEER dispatch, PEER FAIL, ownership handoff
        first, product, validator = self._execute(FAIL, jira)
        self.assertEqual("completed", first["execution_status"])
        self.assertEqual(VALIDATION_FAILED, first["validation_status"])
        self.assertEqual("peer", first["validation_route"])
        self.assertEqual("backend-2", first["reviewer"])
        self.assertEqual("backend-2", first["remediation_owner"])
        self.assertEqual("self", first["remediation_route"])
        self.assertEqual("not-attempted", first["integration_status"])
        self.assertEqual("preserved", first["workspace_status"])
        after_fail = store.read("task", "KAN-900")
        self.assertEqual("backend-2", after_fail["ownership"]["seat_id"])
        self.assertEqual(["backend-2"], store.evidenced_executors(after_fail))
        self.assertEqual(BACKEND_DEV, after_fail["lifecycle"]["jira_status_id"])
        self.assertNotEqual(DONE, after_fail["lifecycle"]["jira_status_id"])

        # ---- leg 2: THE SAME COMMAND. No claim, no verdict, no git, no Jira move.
        second, product2, validator2 = self._execute(PASS, jira)
        self.assertEqual("completed", second["execution_status"])
        self.assertEqual("backend-2", second["seat_id"])
        self.assertEqual("preserved", second["claim_status"])
        # SELF, not a second PEER loop.
        self.assertEqual(VALIDATION_PASSED, second["validation_status"])
        self.assertEqual("self", second["validation_route"])
        self.assertEqual("backend-2", second["reviewer"])
        self.assertEqual(PASS, second["verdict"])
        # Integration and lifecycle completion follow automatically.
        self.assertEqual("integrated", second["integration_status"])
        self.assertEqual(["alpha.dart"], second["attributed_files"])
        self.assertEqual(second["integrated_as"], sh(self.repo, "rev-parse", "Canary"))
        self.assertEqual("completed", second["completion_status"])
        self.assertEqual("done", second["lifecycle"])
        self.assertEqual([], second["open_leases"])

        final = store.read("task", "KAN-900")
        self.assertEqual(DONE, final["lifecycle"]["jira_status_id"])
        self.assertIsNone(final["ownership"])
        self.assertEqual("self", final["review_context"]["review_type"])
        self.assertEqual("pass", final["review_context"]["review_result"])
        self.assertEqual("backend-1", final["review_context"]["previous_owner"])
        # The only remaining reason is that it IS done — the terminal state.
        self.assertEqual(["already-done"],
                         state_queue.completion_reasons(final, interventions=[]))
        self.assertEqual("released", second["workspace_status"])
        self.assertEqual(self.main_before, sh(self.repo, "rev-parse", "main"))

    def test_the_peer_route_is_never_re_derived_after_the_transfer(self):
        # The task's characteristics still compute PEER; the transfer's SELF
        # route is what governs, and the second leg must not go back to a peer.
        import policy
        make_task()
        jira = Jira()
        self._execute(FAIL, jira)
        task = store.read("task", "KAN-900")
        self.assertEqual(policy.PEER, policy.validation_route(
            task["execution_profile"]["characteristics"]))
        second, _, validator = self._execute(PASS, jira)
        self.assertEqual("self", second["validation_route"])
        self.assertEqual("backend-2", validator.requests[0].seat_id)
        self.assertEqual("self", store.read("task", "KAN-900")
                         ["review_context"]["review_type"])


class RealSystemsUntouchedTests(HandoffTestCase):
    def test_this_suite_never_reached_the_real_runtime_or_repository(self):
        self.assertNotIn(os.path.join("agent", "state", "runtime"), store.RUNTIME)
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
