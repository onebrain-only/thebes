"""Read-only controller entry point for the canonical current-sprint plan."""
from agent.integrations import jira
from agent.state import capacity, queue, sprint, store, validate


def plan_current_sprint(*, jira_client=jira, state_store=store, when=None):
    """Resolve label-backed sprint scope and delegate all scheduling to state.

    This function performs no state or Jira writes and intentionally has no provider
    invocation path.  ``include_execution_gate=False`` makes the result a future
    plan while every other claim predicate remains authoritative.
    """
    sid = sprint.sprint_id(when)
    issues = jira_client.search_issues('project = KAN AND labels = "%s"' % sid,
                                       limit=200)
    return plan_issues(issues, sid, "canonical Dubai-time calendar plus Jira sprint label",
                       state_store=state_store)


def plan_issues(issues, scope_id, scope_source, *, state_store=store):
    """Shared read-only scope-to-batch-plan adapter for controller entry points."""
    keys = [row["key"] for row in issues]
    all_tasks = state_store.read_all("task")
    by_key = {row.get("work_item_id"): row for row in all_tasks}
    scoped = [by_key[key] for key in keys if key in by_key]
    facts = {row["key"]: {"status_id": row.get("status_id"),
                           "has_due_date": bool(row.get("due_date")),
                           "has_acceptance_criteria": bool(row.get("description"))}
             for row in issues}
    edges = [e for e in state_store.read_all("dependency") if not e.get("retired_at")]
    admissions = []
    for issue in issues:
        key, task = issue["key"], by_key.get(issue["key"])
        if task is None:
            admissions.append(_admission(key, issue, None, "OTHER_CANONICAL_BLOCKER",
                                         ["missing-canonical-task-record"]))
            continue
        reasons = queue.unclaimable_reasons(
            task, all_tasks=all_tasks, edges=edges, interventions=[], jira=facts[key],
            jira_status_id=facts[key]["status_id"], include_execution_gate=False)
        admissions.append(_admission(key, issue, task, _classify(task, reasons), reasons))

    seats = validate.seats_by_capability()
    waves, assigned = [], {}
    for cap in sorted({queue.capability_of(t) for t in scoped if queue.capability_of(t)}):
        plan = capacity.safe_parallel_plan(
            cap, all_tasks,
            seats, edges=edges, jira_by_key=facts, covers=lambda t, ks=set(keys): t.get("work_item_id") in ks,
            interventions=[], include_execution_gate=False)
        if plan["assignments"]:
            waves.append({"wave": 1, "capability": cap, "assignments": plan["assignments"]})
            assigned.update({a["work_item_id"]: a for a in plan["assignments"]})
    for row in admissions:
        assignment = assigned.get(row["key"])
        row["planned_executor"] = assignment and assignment["seat_id"]
        row["planned_provider"] = "claude-code" if assignment else None
        row["execution_wave"] = 1 if assignment else None
    return {"result_class": "EMPTY_SPRINT" if not issues else "PLANNED", "scope": scope_id,
            "scope_source": scope_source, "sprint": scope_id, "sprint_source": scope_source,
            "total_issues": len(issues), "issue_keys": keys, "admissions": admissions,
            "dependency_graph": [e for e in edges if e.get("source_work_item") in keys or e.get("target_work_item") in keys],
            "contention_graph": _contention(scoped, all_tasks),
            "existing_ownership": [{"key": t.get("work_item_id"), "owner": t.get("ownership")}
                                   for t in scoped if t.get("ownership")],
            "future_execution_waves": waves, "executable_count": len(assigned),
            "blocked_count": sum(1 for a in admissions if a["admission_class"] != "EXECUTABLE_NOW"),
            "deferred_count": 0, "execution_admitted": False,
            "operating_mode": state_store.current_operating_mode()}


def _admission(key, issue, task, classification, reasons):
    profile = (task or {}).get("execution_profile") or {}
    return {"key": key, "status": issue.get("status"), "status_id": issue.get("status_id"),
            "admission_class": classification, "block_reasons": reasons,
            "capability": profile.get("required_capability"), "work_effort": profile.get("work_effort"),
            "validation_route": queue.validation_route_for(task) if task else None,
            "current_owner": ((task or {}).get("ownership") or {}).get("seat_id")}


def _classify(task, reasons):
    if (task.get("ownership") or {}).get("seat_id"):
        return "ALREADY_OWNED"
    if "dependency-blocked" in reasons:
        return "WAITING_DEPENDENCY"
    if "surface-contention" in reasons:
        return "WAITING_CONTENTION"
    if any(r.startswith("missing-") or r == "not-ready" for r in reasons):
        return "MISSING_READY_FACT" if any(r.startswith("missing-") for r in reasons) else "NOT_READY"
    return "EXECUTABLE_NOW" if not reasons else "OTHER_CANONICAL_BLOCKER"


def _contention(scoped, all_tasks):
    out = []
    for task in scoped:
        for other in all_tasks:
            if task is other or task.get("work_item_id") == other.get("work_item_id"):
                continue
            if (other.get("ownership") or {}).get("seat_id") and queue.contends(task, other):
                out.append({"work_item_id": task.get("work_item_id"), "contends_with": other.get("work_item_id")})
    return out
