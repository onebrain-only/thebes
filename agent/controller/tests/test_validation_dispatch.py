#!/usr/bin/env python3
"""VALIDATION DISPATCH IN THE EXECUTION PATH.

The REAL `agent/state/store.py` runs here, pointed at a temp runtime directory —
the established pattern from `agent/state/tests`. That matters: the review
context, the owner resolution, the verdict writer and all three FAIL semantics
are the canonical ones with their real CAS and their real refusals, not a double
that could drift from them. Git is a synthetic repository, Jira is a double, the
providers are doubles. No real Jira, Product repository or Supabase is reachable.
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
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                       # noqa: E402
import validate as state_validate                                  # noqa: E402

from agent.controller import execute                               # noqa: E402
from agent.controller.validation import (                          # noqa: E402
    FAIL, PASS, VALIDATION_DISPATCH_FAILED, VALIDATION_FAILED,
    VALIDATION_PASSED, VALIDATION_RESULT_MALFORMED,
    VALIDATION_ROUTE_UNRESOLVED, VALIDATION_WAITING_FOR_REVIEWER,
    ValidationRefused, build_validation_request, propose_peer_reviewer,
    route_for, run_validation, verdict_from,
)
from agent.controller.workspace import conclude_workspace, realize_workspace  # noqa: E402
from agent.controller.tests.test_canonical_intent import Authorization, issue  # noqa: E402
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402
from agent.execution.brief import (                                # noqa: E402
    CONTROL_PLANE_TOKENS, render_executor_brief,
)
from agent.execution.provider import (                             # noqa: E402
    ChangedFileClaim, EvidenceClaim, ExecutionResult, ExecutionStatus,
    Failure, FailureCode, MutationMode, ProviderCapabilities, TestClaim,
    TestStatus, ExecutionFeature, ModelIntent, ReasoningEffort,
)
from agent.state import board, policy                              # noqa: E402


SELF_REVIEW, PEER_REVIEW, QA_TEST = "10044", "10045", "10009"
BACKEND_DEV, DONE = "10043", board.DONE_STATUS_ID


# --------------------------------------------------------------- doubles

class Jira:
    """Behaves like the board: a transition actually moves the status."""

    def __init__(self, status_id=BACKEND_DEV):
        self.status_id = str(status_id)
        self.reads, self.transitions = [], []

    def get_issue(self, key):
        self.reads.append(key)
        record = dict(issue())
        record["status_id"] = self.status_id
        record["status"] = board.name_for(self.status_id)
        return record

    def transition_issue(self, key, transition_id):
        self.transitions.append((key, transition_id))
        for sid, row in board.STATUSES.items():
            if row[3] == str(transition_id):
                self.status_id = sid
                return {"key": key}
        raise AssertionError("unknown transition id %r" % transition_id)

    def update_issue(self, *a, **k):     # pragma: no cover - guard
        raise AssertionError("a dry flow test must not edit Jira fields")

    def add_comment(self, *a, **k):      # pragma: no cover - guard
        raise AssertionError("a dry flow test must not comment on Jira")


class Validator:
    """A provider double standing in for the reviewer seat."""

    def __init__(self, verdict=PASS, status=ExecutionStatus.COMPLETED,
                 evidence=None, summary="validation complete"):
        self.verdict, self.status, self.summary = verdict, status, summary
        self.custom_evidence = evidence
        self.requests = []

    def capabilities(self):
        return ProviderCapabilities(
            provider_id="claude-code", available=True,
            execution_features=frozenset(ExecutionFeature),
            supported_reasoning_efforts=frozenset(ReasoningEffort),
            supported_model_intents=frozenset(ModelIntent))

    def execute(self, request):
        self.requests.append(request)
        if self.custom_evidence is not None:
            evidence = self.custom_evidence
        elif self.verdict is None:
            evidence = ()
        else:
            evidence = (EvidenceClaim("verdict", self.verdict, "reviewer judgement"),)
        failure = (Failure(FailureCode.EXECUTION_FAILURE, self.summary)
                   if self.status is ExecutionStatus.EXECUTION_FAILED else None)
        return ExecutionResult(invocation_id=request.invocation_id,
                               status=self.status, summary=self.summary,
                               evidence=evidence, failure=failure,
                               provider_id="claude-code")


class ProductExecutor:
    """A provider double standing in for the Product executor seat."""

    def __init__(self, edit=None):
        self.edit, self.wakes = edit, []

    def capabilities(self):
        return ProviderCapabilities(
            provider_id="claude-code", available=True,
            execution_features=frozenset(ExecutionFeature),
            supported_reasoning_efforts=frozenset(ReasoningEffort),
            supported_model_intents=frozenset(ModelIntent))

    def execute(self, request):
        self.wakes.append(request)
        if self.edit:
            self.edit(request.workspace.working_directory)
        return ExecutionResult(
            invocation_id=request.invocation_id, status=ExecutionStatus.COMPLETED,
            summary="implemented the change", provider_id="claude-code",
            changed_files=(ChangedFileClaim("alpha.dart", "modified"),),
            tests=(TestClaim("flutter test", TestStatus.PASSED, exit_code=0),))


class RoutingProvider:
    """Product executor first, validator afterwards — one seam, two acts."""

    def __init__(self, product, validator):
        self.product, self.validator = product, validator

    def capabilities(self):
        return self.product.capabilities()

    def execute(self, request):
        if request.execution_kind.value == "validation":
            return self.validator.execute(request)
        return self.product.execute(request)


# --------------------------------------------------------------- fixtures

SEATS = {"backend": ("backend-1", "backend-2"), "qa": ("qa",)}


def isolated_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    state_validate.RUNTIME = store.RUNTIME
    for kind, (folder, _prefix) in store.KINDS.items():
        os.makedirs(os.path.join(store.RUNTIME, folder), exist_ok=True)
    os.makedirs(store.LOCKS, exist_ok=True)
    store.create("operating_mode", {"operating_mode_id": "current",
                                    "mode": "PRODUCT_EXECUTION",
                                    "changed_by": "ceo", "reason_ref": "fixture"},
                 rid="current")
    return tmp


def make_task(work_item_id="KAN-900", characteristics=None, status_id=BACKEND_DEV,
              owner="backend-1", surfaces=("alpha.dart", "beta.dart")):
    """A real task record, written through the real store."""
    characteristics = ({"schema_change": True} if characteristics is None
                       else characteristics)
    record = {
        "work_item_id": work_item_id, "product_id": "dabbler", "project_id": "app",
        "record_type": "executable", "surfaces": list(surfaces),
        "lifecycle": {"canonical": board.canonical_for(status_id),
                      "jira_column": board.column_for(status_id),
                      "jira_status_id": status_id,
                      "jira_status_name": board.name_for(status_id),
                      "source": "jira", "observed_at": store.now()},
        "ownership": ({"seat_id": owner, "claim_ref": "claim:%s" % work_item_id,
                       "claimed_at": store.now()} if owner else None),
        "executor_evidence": [],
        "execution_profile": {
            "required_capability": "backend", "work_effort": 2,
            "characteristics": dict(characteristics),
            "validation_route": policy.validation_route(characteristics),
            "completion_route": "DONE", "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "characteristics", "validation_route",
                                 "completion_route"],
            "provenance": {"validation_route": {"by": "system-policy",
                                                "at": store.now()}},
        },
        "review_context": None,
        "operational_context": {
            "intent": "implementation", "initial_phase": "implementation",
            "reported_environment": {"locality": "local", "runtime": "flutter_web",
                                     "platform": "chrome",
                                     "environment_ref": "fixture"},
            "primary_target": {"locality": "local", "runtime": "flutter_web",
                               "platform": "chrome", "browser_automation": False,
                               "environment_ref": "fixture",
                               "launch_method": "terminal",
                               "launch_command": "flutter run -d chrome",
                               "source": "reported_environment"},
            "comparative_targets": [],
            "provenance": {"by": "po", "at": store.now(),
                           "evidence_ref": "fixture operational context"},
        },
    }
    return store.create("task", record, rid=work_item_id)


class ValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_tmp = isolated_runtime()
        self.addCleanup(shutil.rmtree, self.runtime_tmp, ignore_errors=True)
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

    def edit(self, path, text="// executor change\n"):
        with open(os.path.join(path, "alpha.dart"), "a") as handle:
            handle.write(text)

    def execution_result(self):
        return ExecutionResult(
            invocation_id="inv-1", status=ExecutionStatus.COMPLETED,
            summary="implemented the change", provider_id="claude-code",
            changed_files=(ChangedFileClaim("alpha.dart", "modified"),),
            tests=(TestClaim("flutter test", TestStatus.PASSED, exit_code=0),))

    def run_route(self, task, jira, validator, realized=None):
        work_item_id = task["work_item_id"]
        return run_validation(work_item_id, task, self.execution_result(),
                              realized or self.realize(work_item_id=work_item_id),
                              store, jira,
                              (validator,), seats_by_capability=SEATS,
                              receipt_ref="execution receipt for %s" % work_item_id)


# --------------------------------------------------------------- route tests

class RouteTests(ValidationTestCase):
    def test_the_route_comes_only_from_canonical_policy(self):
        for index, (characteristics, expected) in enumerate((
                ({}, policy.SELF),
                ({"user_visible_runtime": True}, policy.QA),
                ({"schema_change": True}, policy.PEER))):
            with self.subTest(route=expected):
                task = make_task("KAN-91%d" % index, characteristics=characteristics)
                self.assertEqual(expected, route_for(task))

    def test_an_unclassified_item_has_no_route_and_refuses(self):
        task = make_task()
        task["execution_profile"]["characteristics"] = None
        with self.assertRaises(ValidationRefused) as caught:
            route_for(task)
        self.assertEqual(VALIDATION_ROUTE_UNRESOLVED, caught.exception.outcome)

    def test_a_peer_reviewer_is_never_the_executor(self):
        self.assertEqual("backend-2",
                         propose_peer_reviewer(make_task(), SEATS, ("backend-1",)))
        self.assertEqual("backend-1",
                         propose_peer_reviewer(make_task("KAN-901"), SEATS,
                                               ("backend-2",)))
        # Both seats are executors: no eligible peer remains.
        self.assertIsNone(propose_peer_reviewer(make_task("KAN-902"), SEATS,
                                                ("backend-1", "backend-2")))


class VerdictReadingTests(ValidationTestCase):
    def test_a_completed_provider_result_alone_is_not_a_pass(self):
        bare = ExecutionResult(invocation_id="inv-1",
                               status=ExecutionStatus.COMPLETED,
                               summary="I ran", provider_id="claude-code")
        with self.assertRaises(ValidationRefused) as caught:
            verdict_from(bare)
        self.assertEqual(VALIDATION_RESULT_MALFORMED, caught.exception.outcome)

    def test_an_explicit_verdict_is_read_in_both_directions(self):
        for verdict in (PASS, FAIL):
            with self.subTest(verdict=verdict):
                result = ExecutionResult(
                    invocation_id="inv-1", status=ExecutionStatus.COMPLETED,
                    summary="judged", provider_id="claude-code",
                    evidence=(EvidenceClaim("verdict", verdict, "because"),))
                self.assertEqual(verdict, verdict_from(result))

    def test_a_contradictory_verdict_is_refused_not_guessed(self):
        result = ExecutionResult(
            invocation_id="inv-1", status=ExecutionStatus.COMPLETED,
            summary="judged", provider_id="claude-code",
            evidence=(EvidenceClaim("verdict", PASS, "a"),
                      EvidenceClaim("verdict", FAIL, "b")))
        with self.assertRaises(ValidationRefused) as caught:
            verdict_from(result)
        self.assertEqual(VALIDATION_RESULT_MALFORMED, caught.exception.outcome)

    def test_a_failed_validation_act_is_not_a_failed_product(self):
        failed = ExecutionResult(
            invocation_id="inv-1", status=ExecutionStatus.EXECUTION_FAILED,
            summary="the checks could not run", provider_id="claude-code",
            failure=Failure(FailureCode.EXECUTION_FAILURE, "the checks could not run"))
        with self.assertRaises(ValidationRefused) as caught:
            verdict_from(failed)
        self.assertEqual(VALIDATION_DISPATCH_FAILED, caught.exception.outcome)

    def test_a_provider_failure_is_not_a_failed_product_either(self):
        broken = ExecutionResult(
            invocation_id="inv-1", status=ExecutionStatus.PROVIDER_FAILED,
            summary="provider unavailable", provider_id="claude-code",
            failure=Failure(FailureCode.UNAVAILABLE, "provider unavailable"))
        with self.assertRaises(ValidationRefused) as caught:
            verdict_from(broken)
        self.assertEqual(VALIDATION_DISPATCH_FAILED, caught.exception.outcome)


class ValidatorBriefTests(ValidationTestCase):
    def _request(self, route_characteristics=None, reviewer="backend-2"):
        task = make_task(characteristics=route_characteristics)
        realized = self.realize()
        task = dict(task, review_context={"review_type": "peer",
                                          "review_owner": reviewer,
                                          "review_result": "pending",
                                          "review_cycle": 1})
        return build_validation_request(
            "KAN-900", task, issue(), self.execution_result(), realized, reviewer,
            "review:KAN-900:peer:1", "execution receipt for KAN-900")

    def test_the_validation_request_is_read_only_and_context_bound(self):
        request = self._request()
        self.assertEqual("validation", request.execution_kind.value)
        self.assertIs(MutationMode.READ_ONLY, request.workspace.mutation_mode)
        self.assertEqual("review:KAN-900:peer:1", request.review_context_ref)
        self.assertIsNone(request.claim_ref)
        self.assertIsNone(request.execution_lease_id)
        self.assertEqual("backend-2", request.seat_id)

    def test_a_validation_request_that_could_write_is_refused_by_the_contract(self):
        request = self._request()
        import dataclasses
        from agent.execution.provider import Workspace
        with self.assertRaisesRegex(ValueError, "read-only"):
            dataclasses.replace(request, workspace=Workspace(
                request.workspace.repository_root, request.workspace.working_directory,
                MutationMode.REPOSITORY_EDIT))
        with self.assertRaisesRegex(ValueError, "open review context"):
            dataclasses.replace(request, review_context_ref=None)

    def test_the_validator_brief_is_product_evidence_only(self):
        brief = render_executor_brief(self._request())
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), brief.lower())
        self.assertIn("Validate KAN-900", brief)
        self.assertIn(issue()["summary"], brief)
        self.assertIn("## Changed surfaces", brief)
        self.assertIn("alpha.dart", brief)
        self.assertIn("flutter test -> passed", brief)
        self.assertIn("## Your verdict", brief)
        self.assertIn("- Mutation mode: read_only", brief)
        # The reviewer is told not to implement, and not told how Thebes works.
        self.assertIn("- implement Product changes", brief)
        self.assertNotIn("claim:KAN-900", brief)
        self.assertNotIn("PRODUCT_EXECUTION", brief)
        self.assertNotIn("review:KAN-900", brief)


# ------------------------------------------------------- dispatch per route

class SelfRouteTests(ValidationTestCase):
    def test_self_dispatches_a_real_validation_act_and_records_the_verdict(self):
        task = make_task(characteristics={})
        jira, validator = Jira(), Validator(PASS)
        evidence = self.run_route(task, jira, validator)
        self.assertEqual(VALIDATION_PASSED, evidence["outcome"])
        self.assertEqual("self", evidence["validation_route"])
        # SELF's owner is the evidenced executor — created by the release.
        self.assertEqual("backend-1", evidence["reviewer"])
        self.assertEqual(1, len(validator.requests))
        self.assertEqual(SELF_REVIEW, jira.status_id)
        settled = store.read("task", "KAN-900")
        self.assertEqual("pass", settled["review_context"]["review_result"])
        self.assertEqual("self", settled["review_context"]["review_type"])
        self.assertEqual(["backend-1"], store.evidenced_executors(settled))

    def test_self_fail_returns_execution_to_the_same_seat(self):
        task = make_task(characteristics={})
        jira, validator = Jira(), Validator(FAIL)
        evidence = self.run_route(task, jira, validator)
        self.assertEqual(VALIDATION_FAILED, evidence["outcome"])
        self.assertEqual("backend-1", evidence["remediation_owner"])
        settled = store.read("task", "KAN-900")
        self.assertEqual("fail", settled["review_context"]["review_result"])
        # self_fail_reentry re-establishes ownership on the exact same seat.
        self.assertEqual("backend-1", settled["ownership"]["seat_id"])
        self.assertEqual(BACKEND_DEV, settled["lifecycle"]["jira_status_id"])


class QaRouteTests(ValidationTestCase):
    def test_qa_resolves_the_canonical_qa_seat(self):
        task = make_task(characteristics={"user_visible_runtime": True})
        jira, validator = Jira(), Validator(PASS)
        evidence = self.run_route(task, jira, validator)
        self.assertEqual(VALIDATION_PASSED, evidence["outcome"])
        self.assertEqual("qa", evidence["validation_route"])
        self.assertEqual("qa", evidence["reviewer"])
        self.assertEqual(QA_TEST, jira.status_id)
        self.assertEqual("qa", validator.requests[0].seat_id)
        # The executor is not the reviewer.
        self.assertNotEqual("backend-1", validator.requests[0].seat_id)

    def test_qa_fail_returns_the_work_to_its_executor_and_qa_never_owns(self):
        task = make_task(characteristics={"user_visible_runtime": True})
        jira, validator = Jira(), Validator(FAIL)
        evidence = self.run_route(task, jira, validator)
        self.assertEqual(VALIDATION_FAILED, evidence["outcome"])
        self.assertEqual("backend-1", evidence["remediation_owner"])
        settled = store.read("task", "KAN-900")
        self.assertEqual("fail", settled["review_context"]["review_result"])
        self.assertIsNone(settled["ownership"])
        self.assertEqual(["backend-1"], store.evidenced_executors(settled))
        self.assertEqual(BACKEND_DEV, settled["lifecycle"]["jira_status_id"])


class PeerRouteTests(ValidationTestCase):
    def test_peer_selects_an_eligible_same_capability_seat_that_is_not_the_executor(self):
        task = make_task()
        jira, validator = Jira(), Validator(PASS)
        evidence = self.run_route(task, jira, validator)
        self.assertEqual(VALIDATION_PASSED, evidence["outcome"])
        self.assertEqual("peer", evidence["validation_route"])
        self.assertEqual("backend-2", evidence["reviewer"])
        self.assertEqual(PEER_REVIEW, jira.status_id)
        self.assertEqual("backend", validator.requests[0].required_capability)

    def test_a_peer_route_with_no_eligible_peer_waits_rather_than_downgrading(self):
        task = make_task()
        jira, validator = Jira(), Validator(PASS)
        with self.assertRaises(ValidationRefused) as caught:
            run_validation("KAN-900", task, self.execution_result(), self.realize(),
                           store, jira, (validator,),
                           seats_by_capability={"backend": ("backend-1",), "qa": ("qa",)},
                           receipt_ref="ref")
        self.assertEqual(VALIDATION_WAITING_FOR_REVIEWER, caught.exception.outcome)
        self.assertEqual([], validator.requests)
        settled = store.read("task", "KAN-900")
        # It waits in Peer-review with a null owner; the route never weakens.
        self.assertEqual("peer", settled["review_context"]["review_type"])
        self.assertIsNone(settled["review_context"]["review_owner"])

    def test_peer_fail_transfers_execution_to_the_reviewer_with_no_second_peer_loop(self):
        task = make_task()
        jira, validator = Jira(), Validator(FAIL)
        evidence = self.run_route(task, jira, validator)
        self.assertEqual(VALIDATION_FAILED, evidence["outcome"])
        self.assertEqual("backend-2", evidence["remediation_owner"])
        self.assertEqual(policy.SELF, evidence["remediation_route"])
        settled = store.read("task", "KAN-900")
        # The reviewer is now the evidenced executor and self-reviews its fix.
        self.assertEqual(["backend-2"], store.evidenced_executors(settled))
        self.assertEqual("self", settled["review_context"]["review_type"])
        self.assertEqual("backend-2", settled["review_context"]["review_owner"])
        self.assertEqual("backend-1", settled["review_context"]["previous_owner"])
        self.assertEqual(2, settled["review_context"]["review_cycle"])
        self.assertEqual(BACKEND_DEV, settled["lifecycle"]["jira_status_id"])

    def test_the_controller_cannot_substitute_itself_as_reviewer(self):
        task = make_task()
        jira, validator = Jira(), Validator(PASS)
        self.run_route(task, jira, validator)
        settled = store.read("task", "KAN-900")
        # Only the recorded owner may record a verdict; anyone else is refused.
        for impostor in ("backend-1", "orchestrator", "qa"):
            with self.subTest(impostor=impostor):
                with self.assertRaises(store.StateError):
                    store.record_review_result("KAN-900", settled["revision"],
                                               impostor, "pass", "ref")


class IntegrationGateTests(ValidationTestCase):
    def test_a_pending_verdict_blocks_integration_and_a_pass_unlocks_it(self):
        import queue as state_queue
        task = make_task()
        jira, validator = Jira(), Validator(PASS)
        # Before validation: not in review at all.
        self.assertTrue(state_queue.completion_reasons(task, interventions=[]))
        self.run_route(task, jira, validator)
        settled = store.read("task", "KAN-900")
        self.assertEqual([], state_queue.completion_reasons(settled, interventions=[]))

    def test_a_failed_verdict_keeps_the_gate_shut(self):
        import queue as state_queue
        # SELF FAIL leaves the failure on the record: the gate names it.
        self.run_route(make_task(characteristics={}), Jira(), Validator(FAIL))
        self.assertIn("review-failed", state_queue.completion_reasons(
            store.read("task", "KAN-900"), interventions=[]))

    def test_a_failed_peer_verdict_also_keeps_the_gate_shut(self):
        import queue as state_queue
        # PEER FAIL consumes the failure into the transfer, so the reasons read
        # differently — but the gate is shut either way, which is the claim.
        self.run_route(make_task("KAN-905"), Jira(), Validator(FAIL))
        reasons = state_queue.completion_reasons(store.read("task", "KAN-905"),
                                                 interventions=[])
        self.assertTrue(reasons)
        self.assertIn("review-not-passed", reasons)


# ------------------------------------------------------- full flow proof

class FullFlowTests(ValidationTestCase):
    """One work-item key, PEER route, all the way to Done."""

    def _execute(self, characteristics=None, verdict=PASS, jira=None,
                 seats=None, work_item_id="KAN-900"):
        jira = jira or Jira()
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
                          worktree_root=self.wtroot,
                          seats_by_capability=seats or SEATS)
        return outcome, jira, product, validator

    def test_peer_pass_runs_all_the_way_from_key_to_done(self):
        make_task()
        outcome, jira, product, validator = self._execute()

        # Execution
        self.assertEqual("completed", outcome["execution_status"])
        self.assertEqual(1, len(product.wakes))
        # Validation
        self.assertEqual(VALIDATION_PASSED, outcome["validation_status"])
        self.assertEqual("peer", outcome["validation_route"])
        self.assertEqual("backend-2", outcome["reviewer"])
        self.assertEqual(PASS, outcome["verdict"])
        self.assertEqual(1, len(validator.requests))
        # The validator saw a read-only Product brief and nothing else.
        brief = render_executor_brief(validator.requests[0])
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), brief.lower())
        # Integration
        self.assertEqual("integrated", outcome["integration_status"])
        self.assertEqual(["alpha.dart"], outcome["attributed_files"])
        self.assertEqual(outcome["integrated_as"], sh(self.repo, "rev-parse", "Canary"))
        # Lifecycle
        self.assertEqual("completed", outcome["completion_status"])
        self.assertEqual("done", outcome["lifecycle"])
        # Validation released ownership when it entered review, so completion
        # correctly finds nothing left to release.
        self.assertEqual("already-released", outcome["ownership_status"])
        self.assertEqual([], outcome["open_leases"])
        settled = store.read("task", "KAN-900")
        self.assertIsNone(settled["ownership"])
        self.assertEqual(DONE, settled["lifecycle"]["jira_status_id"])
        self.assertEqual("released", outcome["workspace_status"])
        self.assertEqual(self.main_before, sh(self.repo, "rev-parse", "main"))
        # Peer-review, then Done: two transitions, both legal targets.
        self.assertEqual(2, len(jira.transitions))

    def test_peer_fail_produces_the_canonical_transfer_and_stops_there(self):
        make_task()
        first, jira, _, _ = self._execute(verdict=FAIL)
        self.assertEqual(VALIDATION_FAILED, first["validation_status"])
        self.assertEqual("backend-2", first["remediation_owner"])
        self.assertEqual(policy.SELF, first["remediation_route"])
        self.assertEqual("not-attempted", first["integration_status"])
        self.assertEqual("not-attempted", first["completion_status"])
        self.assertEqual("preserved", first["workspace_status"])
        after = store.read("task", "KAN-900")
        # peer_fail_transfer's exact canonical effect, verbatim.
        self.assertEqual(["backend-2"], store.evidenced_executors(after))
        self.assertEqual("self", after["review_context"]["review_type"])
        self.assertEqual("backend-2", after["review_context"]["review_owner"])
        self.assertEqual("backend-1", after["review_context"]["previous_owner"])
        self.assertEqual(2, after["review_context"]["review_cycle"])
        self.assertEqual(BACKEND_DEV, after["lifecycle"]["jira_status_id"])
        # Nothing reached Canary and nothing reached Done.
        self.assertNotEqual(DONE, after["lifecycle"]["jira_status_id"])
        self.assertEqual(self.main_before, sh(self.repo, "rev-parse", "main"))

    def test_peer_fail_does_not_re_establish_ownership_for_the_reviewer(self):
        # A truthful characterisation, not an aspiration: `peer_fail_transfer`
        # moves evidence and the review context but writes no ownership, and an
        # item in Development is not claimable. Remediation therefore still
        # needs an ownership act the canonical model does not currently provide.
        import queue as state_queue
        make_task()
        self._execute(verdict=FAIL)
        after = store.read("task", "KAN-900")
        self.assertIsNone(after["ownership"])
        self.assertIn("not-ready", state_queue.unclaimable_reasons(after,
                                                                   interventions=[]))

    def test_a_reviewer_that_owns_its_transferred_work_self_validates_to_done(self):
        # The state a PEER FAIL transfer leads to, once ownership is with the
        # reviewer: SELF route, reviewer is both executor and validator.
        make_task(characteristics={}, owner="backend-2")
        outcome, jira, _, _ = self._execute(jira=Jira(BACKEND_DEV))
        self.assertEqual(VALIDATION_PASSED, outcome["validation_status"])
        self.assertEqual("self", outcome["validation_route"])
        self.assertEqual("backend-2", outcome["reviewer"])
        self.assertEqual("integrated", outcome["integration_status"])
        self.assertEqual("completed", outcome["completion_status"])
        final = store.read("task", "KAN-900")
        self.assertEqual(DONE, final["lifecycle"]["jira_status_id"])
        self.assertIsNone(final["ownership"])
        # No second PEER loop anywhere on this path.
        self.assertEqual("self", final["review_context"]["review_type"])

    def test_a_waiting_peer_route_stops_the_flow_without_touching_canary(self):
        make_task()
        canary = sh(self.repo, "rev-parse", "Canary")
        outcome, jira, _, validator = self._execute(
            seats={"backend": ("backend-1",), "qa": ("qa",)})
        self.assertEqual(VALIDATION_WAITING_FOR_REVIEWER, outcome["validation_status"])
        self.assertEqual("not-attempted", outcome["integration_status"])
        self.assertEqual("not-attempted", outcome["completion_status"])
        self.assertEqual([], validator.requests)
        self.assertEqual(canary, sh(self.repo, "rev-parse", "Canary"))
        self.assertEqual("preserved", outcome["workspace_status"])
        self.assertNotEqual(DONE, store.read("task", "KAN-900")
                            ["lifecycle"]["jira_status_id"])

    def test_a_malformed_verdict_never_moves_jira_to_done(self):
        make_task()
        product = ProductExecutor(edit=self.edit)
        validator = Validator(verdict=None)          # returns no verdict evidence
        provider = RoutingProvider(product, validator)
        jira = Jira()

        def allocator(item, seat_id, workspace):
            return realize_workspace(item, seat_id,
                                     dict(workspace, repository_root=self.repo),
                                     root=self.wtroot)

        outcome = execute("KAN-900", None, authorization=Authorization(),
                          state_store=store, jira_client=jira,
                          seat_registry=_Roster(), providers=(provider,),
                          workspace_allocator=allocator,
                          workspace_concluder=lambda *a, **k: {
                              "workspace_status": "preserved",
                              "workspace_reason": "validation pending",
                              "workspace_path": None, "workspace_branch_kept": True},
                          interventions=[], worktree_root=self.wtroot,
                          seats_by_capability=SEATS)
        self.assertEqual(VALIDATION_RESULT_MALFORMED, outcome["validation_status"])
        self.assertEqual("not-attempted", outcome["integration_status"])
        self.assertNotEqual(DONE, jira.status_id)
        settled = store.read("task", "KAN-900")
        self.assertEqual("pending", settled["review_context"]["review_result"])


class _Roster:
    def read(self):
        return {"backend-1": {"seat_id": "backend-1", "role": "backend",
                              "capability": "backend"},
                "backend-2": {"seat_id": "backend-2", "role": "backend",
                              "capability": "backend"},
                "qa": {"seat_id": "qa", "role": "qa", "capability": "qa"}}


class RealSystemsUntouchedTests(ValidationTestCase):
    def test_no_module_on_this_path_can_reach_supabase(self):
        for name in ("validation", "completion", "integration", "workspace", "intent"):
            path = os.path.join(ROOT, "agent", "controller", "%s.py" % name)
            with open(path, encoding="utf-8") as handle:
                source = handle.read().lower()
            with self.subTest(module=name):
                for forbidden in ("supabase", "psycopg", "postgres"):
                    self.assertNotIn(forbidden, source)

    def test_this_suite_never_reached_the_real_repository_or_runtime(self):
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
