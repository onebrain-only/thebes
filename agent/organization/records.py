"""Auditable organization writes through the canonical Persistent State store."""

import os
import sys

STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
sys.path.insert(0, STATE)
import store  # noqa: E402

from .authority import assert_decision_authority, decision_owner
from .registry import employee_profile
from .work import TEMPORAL_SCOPES, new_work_cycle


def start_work(employee_id, work_item_id, work_kind, objective,
               repository_change=False, product_work=False):
    return store.create("work_cycle", new_work_cycle(
        employee_id, work_item_id, work_kind, objective,
        repository_change=repository_change, product_work=product_work))


def record_plan(work_cycle_id, expected_revision, employee_id, steps, risks=(),
                authority_refs=()):
    return _advance(work_cycle_id, expected_revision, employee_id, "plan", {
        "status": "completed", "steps": list(steps or ()), "risks": list(risks or ()),
        "authority_refs": list(authority_refs or ()),
    })


def record_execution(work_cycle_id, expected_revision, employee_id, evidence_refs):
    refs = list(evidence_refs or ())
    if not refs:
        raise store.StateError("execution requires evidence_refs")
    return _advance(work_cycle_id, expected_revision, employee_id, "execution", {
        "status": "completed", "evidence_refs": refs,
    })


def record_self_review(work_cycle_id, expected_revision, employee_id, passed,
                       findings=(), evidence_refs=()):
    return _advance(work_cycle_id, expected_revision, employee_id, "self_review", {
        "status": "passed" if passed else "failed",
        "findings": list(findings or ()), "evidence_refs": list(evidence_refs or ()),
    })


def record_learning(work_cycle_id, expected_revision, employee_id, learning_refs=()):
    refs = list(learning_refs or ())
    return _advance(work_cycle_id, expected_revision, employee_id, "learning", {
        "status": "recorded" if refs else "none", "learning_refs": refs,
    })


def _advance(work_cycle_id, expected_revision, employee_id, phase, value):
    current = store.read("work_cycle", work_cycle_id)
    if current is None:
        raise store.StateError("work cycle %s does not exist" % work_cycle_id)
    if current.get("employee_id") != employee_id:
        raise store.StateError("only the assigned employee may advance its work cycle")
    if phase == "execution" and (current.get("plan") or {}).get("status") != "completed":
        raise store.StateError("execution cannot be recorded before planning")
    if phase == "self_review" and (current.get("execution") or {}).get("status") != "completed":
        raise store.StateError("self-review cannot be recorded before execution")
    if phase == "learning" and (current.get("self_review") or {}).get("status") != "passed":
        raise store.StateError("learning cannot close a cycle before self-review passes")
    changes = {phase: value, "status": "in_progress"}
    projected = dict(current)
    projected.update(changes)
    if all((projected.get(name) or {}).get("status") in allowed for name, allowed in (
            ("plan", ("completed",)), ("execution", ("completed",)),
            ("self_review", ("passed",)), ("learning", ("recorded", "none")))):
        changes["status"] = "completed"
    return store.update("work_cycle", work_cycle_id, expected_revision, changes)


def record_decision(decision_class, decided_by, decision, rationale_ref,
                    temporal_scope, scope_ref=None, task_owner=None,
                    consulted=()):
    assert_decision_authority(decision_class, decided_by, task_owner=task_owner)
    if temporal_scope not in TEMPORAL_SCOPES:
        raise store.StateError("unknown temporal scope %r" % temporal_scope)
    if temporal_scope != "organization" and not scope_ref:
        raise store.StateError("a bounded decision requires scope_ref")
    return store.create("decision", {
        "decision_class": decision_class,
        "decided_by": decided_by,
        "decision": decision,
        "rationale_ref": rationale_ref,
        "temporal_scope": temporal_scope,
        "scope_ref": scope_ref,
        "task_owner": task_owner,
        "consulted": sorted(set(consulted or ())),
    })


def record_delegation(delegated_by, delegated_to, work_ref, outcome,
                      decision_class, authority_ref, temporal_scope="task"):
    employee_profile(delegated_to)
    owner = assert_decision_authority(decision_class, delegated_by,
                                      task_owner=delegated_by)
    return store.create("delegation", {
        "delegated_by": delegated_by,
        "delegated_to": delegated_to,
        "work_ref": work_ref,
        "outcome": outcome,
        "decision_class": decision_class,
        "accountable_role": owner["accountable_role"],
        "authority_ref": authority_ref,
        "temporal_scope": temporal_scope,
        "status": "active",
        "completed_at": None,
        "evidence_refs": [],
    })


def employee_ledger(employee_id):
    employee_profile(employee_id)
    entries = []
    for kind, fields in (
        ("work_cycle", ("employee_id",)),
        ("decision", ("decided_by",)),
        ("delegation", ("delegated_by", "delegated_to")),
        ("learning", ("decided_by",)),
    ):
        for record in store.read_all(kind):
            if any(record.get(field) == employee_id for field in fields):
                entries.append({"kind": kind, "record": record})
    return sorted(entries, key=lambda entry: entry["record"].get("created_at", ""))
