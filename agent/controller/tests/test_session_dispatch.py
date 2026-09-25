#!/usr/bin/env python3
"""The persistent-session path: prepare like `execute`, stop before any provider.

Preparation is exercised with the same kind of doubles `test_entry.py` uses, so
the seat, claim, gate, lease and packet ordering are visible as events. Outcome
recording is exercised against a real store in a temporary runtime, because the
identity check lives there.
"""

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

import agent.controller as controller  # noqa: E402
from agent.controller import session_dispatch as sd  # noqa: E402
from agent.execution.brief import CONTROL_PLANE_TOKENS  # noqa: E402
from agent.state import store as real_store  # noqa: E402


SID = "33333333-3333-4333-8333-333333333333"
OTHER_SID = "44444444-4444-4444-8444-444444444444"


def binding(seat_id, provider="claude", session_id=SID):
    return {"seat_id": seat_id, "provider": provider, "session_id": session_id,
            "session_name": "developer", "stable_home": "/stable/home", "status": "active",
            "previous_session_ids": [], "revision": 1}


class Authorization:
    def for_work_item(self, work_item_id):
        return {"authorized": True, "reason": "authorized",
                "reference": "authz:fixture-%s" % work_item_id}


class Registry:
    def read(self):
        return {"backend-1": {"seat_id": "backend-1", "role": "backend", "capability": "backend"},
                "backend-2": {"seat_id": "backend-2", "role": "backend", "capability": "backend"},
                "frontend-1": {"seat_id": "frontend-1", "role": "frontend",
                               "capability": "frontend"}}


class Jira:
    def get_issue(self, key):
        return {"key": key, "status_id": "10008"}


class State:
    """Persistent State double that records the order of every act."""

    def __init__(self, owner=None, bindings=None, fail_create=False):
        self.events = []
        self.bindings = dict(bindings or {})
        self.fail_create = fail_create
        self.lease = None
        self.dispatches = {}
        self.task = {
            "work_item_id": "KAN-900", "revision": 1, "record_type": "executable",
            "ownership": ({"seat_id": owner, "claim_ref": "authz:earlier"} if owner else None),
            "surfaces": ["supabase/migrations/kan900.sql"],
            "execution_profile": {"required_capability": "backend", "work_effort": 1},
        }

    def current_operating_mode(self):
        return "PRODUCT_EXECUTION"

    def read(self, kind, rid):
        if kind == "task" and rid == self.task["work_item_id"]:
            return copy.deepcopy(self.task)
        if kind == "execution_lease" and self.lease and rid == self.lease["execution_lease_id"]:
            return copy.deepcopy(self.lease)
        if kind == "session_dispatch":
            return copy.deepcopy(self.dispatches.get(rid))
        return None

    def read_all(self, kind):
        return [copy.deepcopy(self.task)] if kind == "task" else []

    def active_role_session(self, seat_id):
        return copy.deepcopy(self.bindings.get(seat_id))

    def observe_lifecycle(self, work_item_id, revision, status_id):
        self.events.append("observe")
        self.task["revision"] += 1
        self.task["lifecycle"] = {"jira_status_id": status_id, "canonical": "ready"}
        return copy.deepcopy(self.task)

    def claim(self, work_item_id, seat_id, claim_ref, revision, **kwargs):
        self.events.append("claim:%s" % seat_id)
        self.task["ownership"] = {"seat_id": seat_id, "claim_ref": claim_ref}
        self.task["revision"] += 1
        return copy.deepcopy(self.task)

    def release(self, *args, **kwargs):
        self.events.append("release")
        raise AssertionError("the persistent-session path never releases ownership")

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
        self.lease["closed_at"] = "fixture-time"
        self.lease["revision"] += 1
        return copy.deepcopy(self.lease)

    def create(self, kind, record, rid=None):
        self.events.append("create:%s" % kind)
        if self.fail_create:
            raise real_store.StateError("fixture refuses the dispatch record")
        record = dict(record, dispatch_id="dispatch-fixture", revision=1)
        self.dispatches[record["dispatch_id"]] = record
        return copy.deepcopy(record)


def brief():
    return {
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
        "derived_from": ["fixture"],
    }


def allocate(work_item_id, seat_id, workspace):
    path = "/fixture/worktrees/%s/%s" % (seat_id, work_item_id)
    return {"workspace": dict(workspace, working_directory=path, worktree_path=path,
                              expected_revision="fixturesha"),
            "branch": "exec/%s/%s" % (seat_id, work_item_id), "base": "Canary",
            "base_commit": "fixturesha", "reused": False, "expected_revision": "fixturesha",
            "path": path, "repository_root": workspace["repository_root"]}


def prepare(state, **kwargs):
    kwargs.setdefault("authorization", Authorization())
    kwargs.setdefault("jira_client", Jira())
    kwargs.setdefault("seat_registry", Registry())
    kwargs.setdefault("intent_resolver", lambda *args: brief())
    kwargs.setdefault("workspace_allocator", allocate)
    return sd.dispatch_session("KAN-900", state_store=state, **kwargs)


def _refuse(*args, **kwargs):
    raise AssertionError("preparation must not reach a provider or a subprocess")


class SeatResolutionTests(unittest.TestCase):
    def test_owned_task_uses_its_bound_owner_and_preserves_the_claim(self):
        state = State(owner="backend-2", bindings={"backend-2": binding("backend-2")})
        result = prepare(state)
        self.assertEqual("dispatched", result["dispatch_status"], result.get("blocker"))
        self.assertEqual("backend-2", result["seat_id"])
        self.assertEqual("preserved", result["claim_status"])
        self.assertEqual(SID, result["dispatch_packet"]["session_id"])
        self.assertFalse([e for e in state.events if e.startswith("claim")])

    def test_owned_task_whose_owner_has_no_binding_is_refused_before_anything(self):
        state = State(owner="backend-2", bindings={"backend-1": binding("backend-1")})
        result = prepare(state)
        self.assertEqual("no-bound-session", result["blocker"])
        self.assertEqual([], state.events)

    def test_unowned_task_is_allocated_only_among_bound_seats(self):
        # backend-1 would be the allocator's first choice; only backend-2 is bound.
        state = State(bindings={"backend-2": binding("backend-2")})
        result = prepare(state)
        self.assertEqual("dispatched", result["dispatch_status"], result.get("blocker"))
        self.assertEqual("backend-2", result["seat_id"])
        self.assertIn("claim:backend-2", state.events)

    def test_unowned_task_with_no_bound_seat_is_refused_before_any_claim(self):
        state = State(bindings={"frontend-1": binding("frontend-1")})
        result = prepare(state)
        self.assertEqual("no-bound-session-for-capability", result["blocker"])
        self.assertEqual([], state.events)
        self.assertEqual("not-started", result["claim_status"])

    def test_a_codex_binding_is_refused_not_rerouted(self):
        state = State(bindings={"backend-1": binding("backend-1", provider="codex")})
        result = prepare(state)
        self.assertEqual("persistent-session-unsupported-provider", result["blocker"])
        self.assertEqual([], state.events)


class PreparationTests(unittest.TestCase):
    def test_order_is_claim_gate_lease_record_and_nothing_is_closed(self):
        state = State(bindings={"backend-1": binding("backend-1")})
        prepare(state)
        self.assertEqual(["observe", "claim:backend-1", "continuation", "lease-open",
                          "create:session_dispatch"], state.events)

    def test_packet_carries_the_realized_worktree_and_the_rendered_brief(self):
        state = State(bindings={"backend-1": binding("backend-1")})
        packet = prepare(state)["dispatch_packet"]
        self.assertEqual("/fixture/worktrees/backend-1/KAN-900", packet["worktree_path"])
        self.assertEqual("exec/backend-1/KAN-900", packet["branch"])
        self.assertEqual("/stable/home", packet["stable_home"])
        self.assertEqual("lease-900", packet["execution_lease_id"])
        self.assertEqual("dispatch-fixture", packet["dispatch_id"])
        record = state.dispatches["dispatch-fixture"]
        self.assertEqual((packet["worktree_path"], packet["branch"], "dispatched"),
                         (record["worktree_path"], record["branch"], record["status"]))
        message = packet["message"]
        self.assertTrue(message.startswith("DISPATCH dispatch-fixture KAN-900\n"))
        self.assertIn("cd /fixture/worktrees/backend-1/KAN-900", message)
        self.assertIn("git branch --show-current      must print exec/backend-1/KAN-900",
                      message)
        self.assertIn("SESSION_OUTCOME dispatch-fixture <outcome>", message)
        self.assertIn("# Thebes Product Execution Brief", message)
        self.assertEqual(["select next work item", "transition Jira lifecycle",
                          "launch another executor"],
                         packet["restrictions"]["prohibited_actions"])
        self.assertEqual(["supabase/migrations/kan900.sql"],
                         packet["restrictions"]["allowed_surfaces"])

    def test_packet_message_carries_no_control_plane_token(self):
        state = State(bindings={"backend-1": binding("backend-1")})
        message = prepare(state)["dispatch_packet"]["message"].lower()
        for token in CONTROL_PLANE_TOKENS:
            self.assertNotIn(token.lower(), message, token)

    def test_preparation_never_reaches_a_provider_or_a_subprocess(self):
        state = State(bindings={"backend-1": binding("backend-1")})
        patches = [mock.patch.object(controller, name, _refuse) for name in (
            "execute_product_wake", "available_provider_registry", "ClaudeCliTransport",
            "CodexCliTransport", "ClaudeProvider", "CodexProvider")]
        patches += [mock.patch("agent.execution.wake.execute_product_wake", _refuse),
                    mock.patch("agent.execution.claude.ClaudeCliTransport", _refuse),
                    mock.patch("agent.execution.codex.CodexCliTransport", _refuse)]
        patches += [mock.patch.object(subprocess, name, _refuse)
                    for name in ("run", "Popen", "call", "check_call", "check_output")]
        for patch in patches:
            patch.start()
        try:
            result = prepare(state)
        finally:
            for patch in patches:
                patch.stop()
        self.assertEqual("dispatched", result["dispatch_status"], result.get("blocker"))
        for name in ("execute_product_wake", "available_provider_registry",
                     "ClaudeCliTransport", "CodexCliTransport", "subprocess"):
            self.assertNotIn(name, vars(sd))

    def test_a_failure_after_the_lease_opened_closes_it(self):
        state = State(bindings={"backend-1": binding("backend-1")}, fail_create=True)
        result = prepare(state)
        self.assertIn("fixture refuses the dispatch record", result["blocker"])
        self.assertEqual("lease-close", state.events[-1])
        self.assertEqual("closed-after-preparation-failure", result["lease_closure_status"])
        self.assertIsNone(result["dispatch_packet"])


class OutcomeTests(unittest.TestCase):
    """Against a real store: identity is checked where it is recorded."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = (real_store.RUNTIME, real_store.LOCKS)
        real_store.RUNTIME = os.path.join(self.tmp, "runtime")
        real_store.LOCKS = os.path.join(real_store.RUNTIME, ".locks")
        import validate
        self.validate, self.saved_validate = validate, validate.RUNTIME
        validate.RUNTIME = real_store.RUNTIME
        real_store.bind_role_session("frontend-1", "claude", SID, "/stable/home", "ceo")
        self.lease = real_store.create("execution_lease", {
            "work_item_id": "KAN-900", "seat_id": "frontend-1", "mode_revision": 1,
            "reason_ref": "authz:fixture", "closed_at": None, "closed_by": None})
        self.dispatch = real_store.create("session_dispatch", {
            "work_item_id": "KAN-900", "seat_id": "frontend-1", "provider": "claude",
            "session_id": SID, "worktree_path": "/wt", "branch": "exec/frontend-1/KAN-900",
            "execution_lease_id": self.lease["execution_lease_id"],
            "invocation_id": "controller-fixture", "authorization_ref": "authz:fixture",
            "status": "dispatched"})

    def tearDown(self):
        real_store.RUNTIME, real_store.LOCKS = self.saved
        self.validate.RUNTIME = self.saved_validate
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _lease_open(self):
        return real_store.read("execution_lease", self.lease["execution_lease_id"])["closed_at"] is None

    def test_matching_session_is_recorded_lease_closed_and_ownership_untouched(self):
        with mock.patch.object(real_store, "release", _refuse), \
                mock.patch.object(real_store, "claim", _refuse):
            result = sd.session_outcome("KAN-900", self.dispatch["dispatch_id"], "completed",
                                        SID, "implemented and committed", "abc1234")
        self.assertEqual("recorded", result["outcome_status"], result["blocker"])
        self.assertEqual("completed", result["status"])
        self.assertEqual("preserved", result["claim_status"])
        self.assertFalse(self._lease_open())

    def test_a_different_session_is_refused_and_nothing_changes(self):
        result = sd.session_outcome("KAN-900", self.dispatch["dispatch_id"], "completed",
                                    OTHER_SID, "not me", None)
        self.assertEqual("not-recorded", result["outcome_status"])
        self.assertIn("session-identity-mismatch", result["blocker"])
        self.assertTrue(self._lease_open())
        self.assertEqual("dispatched",
                         real_store.read("session_dispatch", self.dispatch["dispatch_id"])["status"])

    def test_the_work_item_must_match_the_dispatch(self):
        result = sd.session_outcome("KAN-901", self.dispatch["dispatch_id"], "completed",
                                    SID, "wrong item", None)
        self.assertEqual("dispatch-work-item-mismatch", result["blocker"])
        self.assertTrue(self._lease_open())

    def test_worker_unreachable_needs_no_session_and_carries_the_recovery_hint(self):
        result = sd.session_outcome("KAN-900", self.dispatch["dispatch_id"],
                                    "worker_unreachable", None, "SendMessage: no such session")
        self.assertEqual("recorded", result["outcome_status"], result["blocker"])
        self.assertTrue(result["recovery_hint"].startswith("claude --bg --resume %s " % SID))
        self.assertFalse(self._lease_open())

    def test_bind_session_refuses_a_name_and_rebinds_by_cas(self):
        self.assertEqual("session-id-must-be-a-uuid",
                         sd.bind_session("frontend-1", "claude", "developer",
                                         "/stable/home")["blocker"])
        rebound = sd.bind_session("frontend-1", "claude", OTHER_SID, "/stable/home")
        self.assertEqual("rebound", rebound["binding_status"], rebound["blocker"])
        self.assertEqual([SID], rebound["binding"]["previous_session_ids"])


if __name__ == "__main__":
    unittest.main()
