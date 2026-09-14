#!/usr/bin/env python3
"""CONTROLLER BRIEF FROM CANONICAL STATE — execute KAN-XXX with no human brief.

Deterministic. The store, Jira and provider are in-memory doubles; the only real
file read is the canonical Product/Project registry, which is read-only truth.
Nothing here writes Jira, Supabase, Product code or Persistent State on disk.
"""

import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.controller import execute  # noqa: E402
from agent.controller.intent import (  # noqa: E402
    CEO_INPUT_REQUIRED,
    DERIVABLE,
    NEVER_INFERRED,
    ExecutionIntentUnresolved,
    derive_objective,
    resolve_execution_intent,
    split_description,
)
from agent.controller.tests.test_entry import Workspace  # noqa: E402
from agent.execution.brief import CONTROL_PLANE_TOKENS  # noqa: E402
from agent.execution.claude import ClaudeProvider  # noqa: E402
from agent.state import policy  # noqa: E402


SUMMARY = "Persist social search history across app restarts"
DESCRIPTION = """Search history currently lives only in memory, so it is empty
after every cold start. Persist it locally and restore it when the search screen
mounts.

Acceptance criteria
- A search performed before a restart appears in history after the restart.
- History is capped at 20 entries, most recent first.
- Clearing history removes it from storage as well as from state.
"""


def issue(**changes):
    value = {"key": "KAN-900", "summary": SUMMARY, "description": DESCRIPTION,
             "status_id": "10008", "status": "Development", "issue_type": "Task"}
    value.update(changes)
    return value


def task(**changes):
    value = {
        "work_item_id": "KAN-900", "revision": 1, "record_type": "executable",
        "product_id": "dabbler", "project_id": "app", "ownership": None,
        "surfaces": ["lib/features/social/presentation/providers/search_history_provider.dart",
                     "test/features/social/search_history_test.dart"],
        "execution_profile": {
            "required_capability": "backend", "work_effort": 2,
            "characteristics": {"user_visible_runtime": True,
                                "shared_or_contended_surface": False},
            "validation_route": "qa", "completion_route": "DONE",
        },
        "operational_context": {
            "intent": "implementation", "initial_phase": "implementation",
            "reported_environment": {"locality": "local", "runtime": "flutter_web",
                                     "platform": "chrome",
                                     "environment_ref": "CEO report 2026-09-14"},
            "primary_target": {"locality": "local", "runtime": "flutter_web",
                               "platform": "chrome", "browser_automation": False,
                               "environment_ref": "CEO report 2026-09-14",
                               "launch_method": "terminal",
                               "launch_command": "flutter run -d chrome",
                               "source": "reported_environment"},
            "comparative_targets": [],
        },
    }
    value.update(changes)
    return value


class Authorization:
    def for_work_item(self, work_item_id):
        return {"authorized": True, "reason": "authorized",
                "reference": "CEO fixture authorization %s" % work_item_id}


class Registry:
    def read(self):
        return {"backend-1": {"seat_id": "backend-1", "role": "backend",
                              "capability": "backend"}}


class Jira:
    def __init__(self, record=None):
        self.record = record or issue()
        self.reads = []
        self.writes = []

    def get_issue(self, key):
        self.reads.append(key)
        return copy.deepcopy(self.record)

    def transition_issue(self, *args, **kwargs):     # pragma: no cover - guard
        self.writes.append(("transition", args, kwargs))
        raise AssertionError("a dry flow test must not transition Jira")

    def update_issue(self, *args, **kwargs):         # pragma: no cover - guard
        self.writes.append(("update", args, kwargs))
        raise AssertionError("a dry flow test must not write Jira")

    def add_comment(self, *args, **kwargs):          # pragma: no cover - guard
        self.writes.append(("comment", args, kwargs))
        raise AssertionError("a dry flow test must not comment on Jira")


class State:
    """In-memory Persistent State. Every write lands here and nowhere else."""

    def __init__(self, record=None):
        self.events = []
        self.integration_receipts = []
        self.task = record or task()
        self.lease = None
        self.receipt = None

    def current_operating_mode(self):
        self.events.append("mode")
        return "PRODUCT_EXECUTION"

    def read(self, kind, rid):
        if kind == "task":
            return copy.deepcopy(self.task) if rid == self.task["work_item_id"] else None
        if kind == "execution_lease" and self.lease and rid == self.lease["execution_lease_id"]:
            return copy.deepcopy(self.lease)
        return None

    def read_all(self, kind):
        if kind == "task":
            return [copy.deepcopy(self.task)]
        if kind == "dependency":
            return [{"relation": "BLOCKS", "source_work_item": "KAN-899",
                     "target_work_item": "KAN-900", "retired_at": None}]
        return []

    def observe_lifecycle(self, work_item_id, revision, status_id):
        # Faithful to store.observe_lifecycle: the canonical state and column are
        # DERIVED from the board, never taken from the caller's word.
        from agent.state import board
        self.events.append("observe")
        self.task["revision"] += 1
        self.task["lifecycle"] = {
            "jira_status_id": str(status_id),
            "jira_status_name": board.name_for(status_id),
            "jira_column": board.column_for(status_id),
            "canonical": board.canonical_for(status_id),
            "source": "jira", "observed_at": "2026-09-14T00:00:00Z"}
        return copy.deepcopy(self.task)

    def claim(self, work_item_id, seat_id, claim_ref, revision, **kwargs):
        self.events.append("claim")
        self.task["ownership"] = {"seat_id": seat_id, "claim_ref": claim_ref}
        self.task["revision"] += 1
        return copy.deepcopy(self.task)

    def assert_execution_permitted(self, work_item_id, seat_id):
        self.events.append("continuation")
        return copy.deepcopy(self.task)

    def open_execution_lease(self, work_item_id, seat_id, reason_ref):
        self.events.append("lease-open")
        self.lease = {"execution_lease_id": "lease-900", "mode_revision": 1,
                      "revision": 1, "closed_at": None}
        return copy.deepcopy(self.lease)

    def close_execution_lease(self, lease_id, revision, closed_by):
        self.events.append("lease-close")
        self.lease["closed_at"] = "fixture-time"
        self.lease["revision"] = 2
        return copy.deepcopy(self.lease)

    def record_execution_receipt(self, invocation_id, work_item_id, seat_id,
                                 execution_lease_id, normalized_result,
                                 provider_selection=None):
        self.events.append("receipt")
        self.receipt = {"invocation_id": invocation_id,
                        "normalized_result": normalized_result,
                        "provider_selection": provider_selection}

    def record_integration_receipt(self, work_item_id, seat_id, outcome, evidence):
        record = {"work_item_id": work_item_id, "seat_id": seat_id,
                  "outcome": outcome, "created_at": "2026-09-14T00:00:00Z", **evidence}
        self.integration_receipts.append(record)
        return record

    def read_integration_receipts(self, work_item_id=None):
        return [r for r in self.integration_receipts
                if work_item_id is None or r.get("work_item_id") == work_item_id]

    def release(self, work_item_id, seat_id, expected_revision, release_ref,
                authority=None):
        self.events.append("release")
        self.task["ownership"] = None
        self.task["revision"] += 1
        return copy.deepcopy(self.task)



def resolve(record=None, issue_record=None, seat_id="backend-1"):
    state = State(record)
    return resolve_execution_intent("KAN-900", record or state.task,
                                    issue_record or issue(), seat_id, state)


class JiraObjectiveDerivationTests(unittest.TestCase):
    def test_objective_derives_from_jira_summary_description_and_criteria(self):
        objective = derive_objective("KAN-900", issue())
        self.assertIn(SUMMARY, objective)
        self.assertIn("## Product requirement (Jira KAN-900)", objective)
        self.assertIn("## Acceptance criteria (Jira KAN-900)", objective)
        self.assertIn("capped at 20 entries", objective)
        self.assertIn("empty\nafter every cold start", objective)
        # Bounded, not a ticket dump: the heading line itself is not replayed.
        self.assertNotIn("Acceptance criteria\n- A search performed", objective)

    def test_criteria_split_keeps_the_completion_contract_whole(self):
        narrative, criteria = split_description(DESCRIPTION)
        self.assertIn("only in memory", narrative)
        self.assertNotIn("Acceptance criteria", narrative)
        self.assertTrue(criteria.startswith("- A search performed"))
        self.assertIn("Clearing history", criteria)

    def test_a_long_narrative_is_clipped_and_says_so(self):
        long_issue = issue(description="x" * 9000 + "\nAcceptance criteria\n- one\n")
        objective = derive_objective("KAN-900", long_issue)
        self.assertIn("truncated by Thebes; full text stays in Jira", objective)
        self.assertLess(len(objective), 5000)
        self.assertIn("- one", objective)

    def test_dependencies_are_named_when_recorded(self):
        objective = derive_objective("KAN-900", issue(), ("KAN-899",))
        self.assertIn("## Depends on (already satisfied)", objective)
        self.assertIn("KAN-899", objective)

    def test_a_ticket_too_thin_to_bound_is_a_governance_input(self):
        for thin in (issue(summary=""), issue(summary="fix"),
                     issue(description=None), issue(description="   ")):
            with self.subTest(summary=thin["summary"], description=thin["description"]):
                with self.assertRaises(ExecutionIntentUnresolved) as caught:
                    derive_objective("KAN-900", thin)
                self.assertEqual("objective-not-derivable", caught.exception.reason)
                self.assertEqual(CEO_INPUT_REQUIRED, caught.exception.classification)

    def test_jira_prose_that_instructs_orchestration_is_refused_at_derivation(self):
        leaking = issue(description=DESCRIPTION +
                        "\nWhen finished, transition the ticket to QA-Test.\n")
        with self.assertRaises(ExecutionIntentUnresolved) as caught:
            derive_objective("KAN-900", leaking)
        self.assertEqual("jira-objective-instructs-orchestration", caught.exception.reason)
        self.assertIn("KAN-900", caught.exception.detail)


class CanonicalDerivationTests(unittest.TestCase):
    def test_capability_surfaces_and_workspace_derive_from_canonical_state(self):
        brief = resolve()
        self.assertEqual("backend", brief["required_capability"])
        self.assertEqual("canonical-state", brief["brief_source"])
        self.assertTrue(brief["workspace"]["repository_root"].endswith("Dabbler/dabbler-code"))
        self.assertIn(os.path.join("product", "backend-1", "KAN-900"),
                      brief["workspace"]["working_directory"])
        self.assertEqual(brief["workspace"]["working_directory"],
                         brief["workspace"]["worktree_path"])
        self.assertEqual("repository_edit", brief["workspace"]["mutation_mode"])
        self.assertEqual(["CLAUDE.md"], brief["context_refs"])

    def test_validation_route_comes_from_policy_not_from_the_brief(self):
        brief = resolve()
        self.assertEqual("qa", brief["validation_route"])
        self.assertEqual("qa", brief["return_contract"]["return_to"])
        self.assertEqual([{"target_id": "qa", "kind": "review", "required": True}],
                         brief["validation_targets"])
        # The same characteristics through the canonical calculator.
        self.assertEqual(policy.validation_route(
            task()["execution_profile"]["characteristics"]), brief["validation_route"])

    def test_a_peer_characteristic_moves_the_route_without_any_new_policy(self):
        record = task()
        record["execution_profile"]["characteristics"]["schema_change"] = True
        record["execution_profile"]["validation_route"] = "peer"
        self.assertEqual("peer", resolve(record)["return_contract"]["return_to"])

    def test_unclassified_characteristics_block_rather_than_default_to_self(self):
        record = task()
        record["execution_profile"]["characteristics"] = None
        with self.assertRaises(ExecutionIntentUnresolved) as caught:
            resolve(record)
        self.assertEqual("validation-route-unresolved", caught.exception.reason)

    def test_a_stored_route_that_contradicts_its_characteristics_is_refused(self):
        record = task()
        record["execution_profile"]["validation_route"] = "self"
        with self.assertRaises(ExecutionIntentUnresolved) as caught:
            resolve(record)
        self.assertEqual("validation-route-incoherent", caught.exception.reason)
        self.assertEqual(DERIVABLE, caught.exception.classification)

    def test_environment_target_derives_from_the_recorded_authority(self):
        brief = resolve()
        self.assertEqual("local", brief["reported_environment"]["locality"])
        self.assertEqual("flutter run -d chrome", brief["primary_target"]["launch_command"])
        self.assertEqual("reported_environment", brief["primary_target"]["source"])

    def test_unresolved_environment_authority_is_a_bounded_governance_input(self):
        for record, reason in (
            (task(operational_context=None), "environment-authority-missing"),
            (task(operational_context={
                "intent": "observed_condition",
                "reported_environment": {"locality": "unknown", "runtime": None,
                                         "platform": None,
                                         "environment_ref": "CEO report; no runtime supplied"},
                "primary_target": {"locality": "unknown", "browser_automation": False,
                                   "source": "reported_environment"}}),
             "environment-authority-unresolved"),
        ):
            with self.subTest(reason=reason):
                with self.assertRaises(ExecutionIntentUnresolved) as caught:
                    resolve(record)
                self.assertEqual(reason, caught.exception.reason)
                self.assertEqual(CEO_INPUT_REQUIRED, caught.exception.classification)

    def test_execution_shape_follows_the_canonical_operational_intent(self):
        cases = {
            "implementation": ("implementation", "repository_edit"),
            "validation": ("validation", "read_only"),
            "reproduction_request": ("assessment", "read_only"),
            "observed_condition": ("assessment", "read_only"),
        }
        for intent, (kind, mutation) in cases.items():
            with self.subTest(intent=intent):
                record = task()
                record["operational_context"]["intent"] = intent
                brief = resolve(record)
                self.assertEqual(kind, brief["execution_kind"])
                self.assertEqual(mutation, brief["workspace"]["mutation_mode"])
                self.assertEqual("repository_edit" in brief["required_execution_features"],
                                 mutation == "repository_edit")

    def test_a_diagnosed_observed_condition_becomes_implementation(self):
        record = task()
        record["operational_context"]["intent"] = "observed_condition"
        record["operational_context"]["diagnosis"] = {"platform_specificity": "shared"}
        self.assertEqual("implementation", resolve(record)["execution_kind"])

    def test_a_canonical_validation_plan_is_consumed_not_recomputed(self):
        record = task()
        record["operational_context"]["validation_plan"] = {
            "required": [{"target_id": "shared-automated", "kind": "automated",
                          "surface": "shared"},
                         {"target_id": "primary-chrome", "kind": "runtime",
                          "platform": "chrome"}],
            "optional": [{"target_id": "confidence-android", "kind": "runtime",
                          "platform": "android"}],
            "evidence": {},
        }
        targets = resolve(record)["validation_targets"]
        self.assertEqual(["shared-automated", "primary-chrome", "confidence-android"],
                         [item["target_id"] for item in targets])
        self.assertEqual([True, True, False], [item["required"] for item in targets])

    def test_unassessed_surfaces_block_and_capability_gaps_block(self):
        with self.assertRaises(ExecutionIntentUnresolved) as caught:
            resolve(task(surfaces=None))
        self.assertEqual("surfaces-unassessed", caught.exception.reason)
        record = task()
        record["execution_profile"]["required_capability"] = None
        with self.assertRaises(ExecutionIntentUnresolved) as caught:
            resolve(record)
        self.assertEqual("required-capability-unresolved", caught.exception.reason)

    def test_safety_characteristics_are_never_inferred_from_jira_prose(self):
        alarming = issue(description=(
            "This touches the money path and is security sensitive; it needs a "
            "schema change and a migration on a shared contended surface.\n"
            "Acceptance criteria\n- the balance is correct\n"))
        record = task()
        record["execution_profile"]["characteristics"] = {}
        record["execution_profile"]["validation_route"] = "self"
        brief = resolve(record, alarming)
        # Prose says danger; typed canonical state says ordinary. State wins.
        self.assertEqual("self", brief["return_contract"]["return_to"])
        with open(os.path.join(ROOT, "agent", "controller", "intent.py"),
                  encoding="utf-8") as handle:
            source = handle.read()
        body = source[source.index("def derive_objective"):]
        for characteristic in NEVER_INFERRED:
            self.assertNotIn('"%s"' % characteristic, body, characteristic)


class ControllerCommandTests(unittest.TestCase):
    """The CEO supplies only the work-item key."""

    def _run(self, record=None, issue_record=None, brief=None, transport=None):
        # A workspace double: this suite proves derivation, and real worktree
        # allocation is proved against a synthetic repository in
        # `test_workspace_allocation.py`. Nothing here may touch the real
        # Product checkout.
        state, jira_double, workspace = State(record), Jira(issue_record), Workspace()
        wakes = []
        provider = ClaudeProvider(transport or (lambda wake: wakes.append(wake)
                                                or "fixture complete"))
        outcome = execute("KAN-900", brief, authorization=Authorization(),
                          state_store=state, jira_client=jira_double,
                          seat_registry=Registry(), providers=(provider,),
                          workspace_allocator=workspace.allocate,
                          workspace_concluder=workspace.conclude,
                          interventions=[])
        return outcome, state, jira_double, wakes

    def test_execute_needs_no_brief_file_and_completes_the_whole_flow(self):
        outcome, state, jira_double, wakes = self._run()
        self.assertEqual("canonical-state", outcome["brief_source"])
        self.assertEqual("backend", outcome["capability"])
        self.assertEqual("backend-1", outcome["seat_id"])
        self.assertEqual("claimed", outcome["claim_status"])
        self.assertEqual("claude-code", outcome["selected_provider"])
        self.assertEqual("completed", outcome["execution_status"])
        self.assertEqual("received", outcome["result_receipt_status"])
        self.assertEqual("closed", outcome["lease_closure_status"])
        # The trailing "mode" is the automatic integration tail gating itself.
        self.assertEqual(["mode", "observe", "claim", "continuation", "lease-open",
                          "receipt", "lease-close", "mode"], state.events)
        self.assertEqual(["KAN-900"], jira_double.reads)
        self.assertEqual([], jira_double.writes)
        self.assertEqual({"objective": "jira", "required_capability": "execution_profile",
                          "allowed_surfaces": "task.surfaces",
                          "validation_route": "system-policy",
                          "environment": "operational_context",
                          "workspace": "project-registry"}, outcome["derived_from"])

    def test_the_provider_receives_the_canonical_product_only_brief(self):
        outcome, _, _, wakes = self._run()
        prompt = wakes[0].prompt
        self.assertIn(SUMMARY, prompt)
        self.assertIn("## Acceptance criteria (Jira KAN-900)", prompt)
        self.assertIn("capped at 20 entries", prompt)
        self.assertIn("- Work item ID: KAN-900", prompt)
        self.assertIn("- Required capability: backend", prompt)
        self.assertIn("search_history_provider.dart", prompt)
        self.assertIn("- Return to: qa", prompt)
        self.assertIn("flutter run -d chrome", prompt)
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), prompt.lower())
        for withheld in (outcome["invocation_id"], "lease-900", "PRODUCT_EXECUTION",
                         "CEO fixture authorization KAN-900"):
            self.assertNotIn(withheld, prompt)

    def test_a_governance_input_stops_before_the_claim(self):
        outcome, state, jira_double, wakes = self._run(record=task(operational_context=None))
        self.assertEqual("unresolved", outcome["brief_source"])
        self.assertTrue(outcome["ceo_input_required"])
        self.assertEqual("environment-authority-missing",
                         outcome["governance_input"]["reason"])
        self.assertEqual("not-started", outcome["claim_status"])
        self.assertEqual("not-started", outcome["execution_status"])
        self.assertEqual(["mode", "observe"], state.events)
        self.assertEqual([], wakes)
        self.assertEqual([], jira_double.writes)

    def test_a_thin_ticket_stops_before_the_claim_too(self):
        outcome, state, _, wakes = self._run(issue_record=issue(description=None))
        self.assertEqual("objective-not-derivable", outcome["governance_input"]["reason"])
        self.assertTrue(outcome["ceo_input_required"])
        self.assertEqual("not-started", outcome["claim_status"])
        self.assertEqual([], wakes)

    def test_a_manual_brief_cannot_override_a_canonical_safety_fact(self):
        from agent.controller.tests.test_entry import brief as manual_brief
        derived = resolve()
        aligned = dict(manual_brief(), workspace=derived["workspace"],
                       reported_environment=derived["reported_environment"],
                       primary_target=derived["primary_target"],
                       validation_targets=derived["validation_targets"])
        aligned["return_contract"] = dict(aligned["return_contract"], return_to="qa")
        contradictions = {
            "return_contract.return_to": dict(
                aligned, return_contract=dict(aligned["return_contract"], return_to="self")),
            "workspace.repository_root": dict(
                aligned, workspace=dict(aligned["workspace"],
                                        repository_root="/somewhere/else")),
            "primary_target": dict(
                aligned, primary_target=dict(aligned["primary_target"],
                                             locality="deployed")),
            "validation_targets": dict(
                aligned, validation_targets=[{"target_id": "self", "kind": "review",
                                              "required": True}]),
        }
        for field, supplied in contradictions.items():
            with self.subTest(field=field):
                outcome, _, _, wakes = self._run(brief=supplied)
                self.assertIn("manual-brief-contradicts-canonical-state", outcome["blocker"])
                self.assertIn(field, outcome["blocker"])
                self.assertEqual("not-started", outcome["claim_status"])
                self.assertEqual([], wakes)

    def test_a_manual_brief_that_agrees_with_canonical_state_still_runs(self):
        from agent.controller.tests.test_entry import brief as manual_brief
        derived = resolve()
        supplied = manual_brief()
        supplied["return_contract"] = dict(supplied["return_contract"], return_to="qa")
        supplied["reported_environment"] = derived["reported_environment"]
        supplied["primary_target"] = derived["primary_target"]
        supplied["validation_targets"] = derived["validation_targets"]
        supplied["workspace"] = derived["workspace"]
        outcome, _, _, wakes = self._run(brief=supplied)
        self.assertEqual("supplied-brief", outcome["brief_source"])
        self.assertEqual("completed", outcome["execution_status"])
        self.assertIn(supplied["objective"], wakes[0].prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
