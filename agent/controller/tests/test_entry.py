#!/usr/bin/env python3
"""Deterministic coverage for the temporary controller entry point."""

import copy
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.controller import execute  # noqa: E402
from agent.controller.allocation import SeatAllocationError, select_claim_seat  # noqa: E402
from agent.execution.codex import CodexProvider, CodexUnavailable  # noqa: E402


class Authorization:
    def __init__(self, authorized=True):
        self.authorized = authorized

    def for_work_item(self, work_item_id):
        return {"authorized": self.authorized,
                "reason": "authorized" if self.authorized else "product-execution-not-authorized",
                "reference": "CEO fixture authorization %s" % work_item_id}


class Registry:
    def read(self):
        return {"backend-1": {"seat_id": "backend-1", "role": "backend",
                              "capability": "backend"},
                "backend-2": {"seat_id": "backend-2", "role": "backend",
                              "capability": "backend"},
                "frontend-1": {"seat_id": "frontend-1", "role": "frontend",
                               "capability": "frontend"}}


class Jira:
    def __init__(self):
        self.calls = []

    def get_issue(self, key):
        self.calls.append(key)
        return {"key": key, "status_id": "10008"}


class State:
    def __init__(self):
        self.events = []
        self.task = {
            "work_item_id": "KAN-900", "revision": 1, "record_type": "executable",
            "ownership": None, "surfaces": ["supabase/migrations/kan900.sql"],
            "execution_profile": {"required_capability": "backend", "work_effort": 1},
        }
        self.lease = None

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
        return [copy.deepcopy(self.task)] if kind == "task" else []

    def observe_lifecycle(self, work_item_id, revision, status_id):
        self.events.append("observe")
        assert revision == self.task["revision"] and status_id == "10008"
        self.task["revision"] += 1
        self.task["lifecycle"] = {"jira_status_id": status_id, "canonical": "ready"}
        return copy.deepcopy(self.task)

    def claim(self, work_item_id, seat_id, claim_ref, revision, **kwargs):
        self.events.append("claim")
        assert work_item_id == "KAN-900" and seat_id == "backend-1"
        assert revision == self.task["revision"] and kwargs["capability_of_seat"] == "backend"
        self.task["ownership"] = {"seat_id": seat_id, "claim_ref": claim_ref}
        self.task["revision"] += 1
        return copy.deepcopy(self.task)

    def assert_execution_permitted(self, work_item_id, seat_id):
        self.events.append("continuation")
        assert self.task["ownership"]["seat_id"] == seat_id
        return copy.deepcopy(self.task)

    def open_execution_lease(self, work_item_id, seat_id, reason_ref):
        self.events.append("lease-open")
        self.lease = {"execution_lease_id": "lease-900", "mode_revision": 1,
                      "revision": 1, "closed_at": None}
        return copy.deepcopy(self.lease)

    def close_execution_lease(self, lease_id, revision, closed_by):
        self.events.append("lease-close")
        assert lease_id == "lease-900" and revision == 1
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


def brief(**changes):
    value = {
        "execution_kind": "implementation",
        "objective": "Implement exactly the selected bounded fixture work item.",
        "context_refs": ["CLAUDE.md", "agent/roles/backend.md"],
        "workspace": {"repository_root": "/fixture", "working_directory": "/fixture",
                      "mutation_mode": "repository_edit", "expected_revision": "fixture"},
        "reported_environment": {"locality": "local", "runtime": "python",
                                 "environment_ref": "fixture"},
        "primary_target": {"locality": "local", "runtime": "python",
                           "environment_ref": "fixture"},
        "validation_targets": [{"target_id": "fixture-test", "kind": "automated",
                                "required": True}],
        "model_intent": "cost_efficient", "reasoning_effort": "high",
        "required_execution_features": ["repository_read", "repository_edit", "shell"],
        "timeout_seconds": 60,
        "return_contract": {"return_to": "controller", "required_evidence": ["test output"],
                            "required_sections": ["RESULT"]},
    }
    value.update(changes)
    return value


class ControllerEntryTests(unittest.TestCase):
    def test_unauthorized_fails_before_state_jira_or_provider(self):
        state, jira, calls = State(), Jira(), []
        provider = CodexProvider(lambda invocation: calls.append(invocation))
        outcome = execute("KAN-900", brief(), authorization=Authorization(False),
                          state_store=state, jira_client=jira, seat_registry=Registry(),
                          providers=(provider,))
        self.assertEqual("product-execution-not-authorized", outcome["authorization_status"])
        self.assertEqual(["mode"], state.events)
        self.assertEqual([], jira.calls)
        self.assertEqual([], calls)
        self.assertEqual("not-started", outcome["claim_status"])

    def test_authorized_uses_claim_wake_receipt_and_closes_exact_lease(self):
        state, jira, calls = State(), Jira(), []
        provider = CodexProvider(lambda invocation: calls.append(invocation) or "completed fixture")
        outcome = execute("KAN-900", brief(), authorization=Authorization(), state_store=state,
                          jira_client=jira, seat_registry=Registry(), providers=(provider,))
        self.assertEqual(["mode", "observe", "claim", "continuation", "lease-open", "receipt", "lease-close"],
                         state.events)
        self.assertEqual(["KAN-900"], jira.calls)
        self.assertEqual(1, len(calls))
        self.assertEqual("backend", outcome["capability"])
        self.assertEqual("backend-1", outcome["seat_id"])
        self.assertEqual("claimed", outcome["claim_status"])
        self.assertEqual("codex-cli", outcome["selected_provider"])
        self.assertEqual("selected", outcome["provider_selection_status"])
        self.assertEqual("completed", outcome["execution_status"])
        self.assertEqual("received", outcome["result_receipt_status"])
        self.assertEqual("closed", outcome["lease_closure_status"])
        self.assertEqual("completed fixture", outcome["summary"])
        self.assertEqual("claude-code", state.receipt["provider_selection"]["primary_provider_id"])
        self.assertEqual("codex-cli", state.receipt["provider_selection"]["selected_provider_id"])
        self.assertEqual("controller", calls[0].request.return_contract.return_to)
        self.assertEqual(("supabase/migrations/kan900.sql",), calls[0].request.allowed_surfaces)

    def test_authorized_continuation_preserves_existing_owner_without_reclaiming(self):
        state, calls = State(), []
        state.task["ownership"] = {"seat_id": "backend-2", "claim_ref": "CEO prior grant"}
        provider = CodexProvider(lambda invocation: calls.append(invocation) or "continued fixture")
        outcome = execute("KAN-900", brief(), authorization=Authorization(), state_store=state,
                          jira_client=Jira(), seat_registry=Registry(), providers=(provider,))
        self.assertNotIn("claim", state.events)
        self.assertEqual(["mode", "observe", "continuation", "lease-open", "receipt", "lease-close"],
                         state.events)
        self.assertEqual("backend-2", outcome["seat_id"])
        self.assertEqual("preserved", outcome["claim_status"])
        self.assertEqual("CEO prior grant", calls[0].request.claim_ref)

    def test_available_claude_transport_is_reported_without_selecting_it_by_test_override(self):
        state = State()
        provider = CodexProvider(lambda invocation: "completed fixture")
        outcome = execute("KAN-900", brief(), authorization=Authorization(), state_store=state,
                          jira_client=Jira(), seat_registry=Registry(), providers=(provider,))
        self.assertEqual("available-via-local-claude-cli",
                         outcome["claude_transport_from_codex"])
        self.assertIn("native prompts are denied", outcome["claude_transport_limitation"])
        self.assertEqual("codex-cli", outcome["selected_provider"])

    def test_provider_failure_is_received_once_without_fallback_or_retry(self):
        state, primary_calls, fallback_calls = State(), [], []
        primary = CodexProvider(lambda invocation: primary_calls.append(invocation) or {
            "status": "execution_failed", "summary": "native permission blocked",
            "failure_message": "permission required",
        })
        fallback = CodexProvider(lambda invocation: fallback_calls.append(invocation) or "must not run",
                                 model_map={})
        outcome = execute("KAN-900", brief(), authorization=Authorization(), state_store=state,
                          jira_client=Jira(), seat_registry=Registry(), providers=(primary,))
        self.assertEqual(1, len(primary_calls))
        self.assertEqual([], fallback_calls)
        self.assertEqual("execution_failed", outcome["execution_status"])
        self.assertEqual("execution_failure", outcome["execution_failure_code"])
        self.assertEqual("permission required", outcome["blocker"])
        self.assertEqual("closed", outcome["lease_closure_status"])

    def test_provider_unavailability_is_normalized_and_the_lease_still_closes(self):
        state, calls = State(), []

        def unavailable(invocation):
            calls.append(invocation)
            raise CodexUnavailable("Codex executor unavailable")

        outcome = execute("KAN-900", brief(), authorization=Authorization(), state_store=state,
                          jira_client=Jira(), seat_registry=Registry(),
                          providers=(CodexProvider(unavailable),))
        self.assertEqual(1, len(calls))
        self.assertEqual("provider_failed", outcome["execution_status"])
        self.assertEqual("unavailable", outcome["provider_failure_code"])
        self.assertEqual("closed", outcome["lease_closure_status"])

    def test_busy_backend_selects_free_backend(self):
        task = copy.deepcopy(State().task)
        busy = copy.deepcopy(task)
        busy["work_item_id"] = "KAN-901"
        busy["ownership"] = {"seat_id": "backend-1"}
        self.assertEqual("backend-2", select_claim_seat(task, Registry().read(), (task, busy)))

    def test_multiple_free_seats_are_deterministic(self):
        task = copy.deepcopy(State().task)
        seats = {"backend-2": {"capability": "backend"},
                 "backend-1": {"capability": "backend"}}
        self.assertEqual("backend-1", select_claim_seat(task, seats, (task,)))

    def test_all_busy_is_a_factual_allocation_failure(self):
        task = copy.deepcopy(State().task)
        one, two = copy.deepcopy(task), copy.deepcopy(task)
        one["work_item_id"], one["ownership"] = "KAN-901", {"seat_id": "backend-1"}
        two["work_item_id"], two["ownership"] = "KAN-902", {"seat_id": "backend-2"}
        with self.assertRaisesRegex(SeatAllocationError, "no free active seats"):
            select_claim_seat(task, Registry().read(), (task, one, two))

    def test_explicit_pin_is_the_only_candidate(self):
        task = copy.deepcopy(State().task)
        task["execution_profile"]["pinned_seat_id"] = "backend-2"
        self.assertEqual("backend-2", select_claim_seat(task, Registry().read(), (task,)))
        task["execution_profile"]["pinned_seat_id"] = "frontend-1"
        with self.assertRaisesRegex(SeatAllocationError, "not an active backend seat"):
            select_claim_seat(task, Registry().read(), (task,))

    def test_active_claim_excludes_seat_and_claim_stays_atomic(self):
        task = copy.deepcopy(State().task)
        busy = copy.deepcopy(task)
        busy["work_item_id"], busy["ownership"] = "KAN-901", {"seat_id": "backend-1"}
        self.assertEqual("backend-2", select_claim_seat(task, Registry().read(), (task, busy)))
        state = State()
        outcome = execute("KAN-900", brief(), authorization=Authorization(), state_store=state,
                          jira_client=Jira(), seat_registry=Registry(), providers=())
        self.assertEqual("backend-1", outcome["seat_id"])
        self.assertEqual(["mode", "observe", "claim", "continuation", "lease-open",
                          "receipt", "lease-close"], state.events)


if __name__ == "__main__":
    unittest.main(verbosity=2)
