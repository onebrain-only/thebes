"""The employee work cycle and implied completion obligations."""

from .registry import employee_profile


WORK_KINDS = (
    "plan", "implement", "investigate", "decide", "direct", "delegate",
    "review", "remediate", "learn",
)
TEMPORAL_SCOPES = (
    "invocation", "task", "session", "project", "product", "organization",
    "until_condition",
)


def completion_actions(work_kind, repository_change=False, product_work=False):
    """Actions implied by accepting the work, not fresh approval requests."""
    if work_kind not in WORK_KINDS:
        raise ValueError("unknown work kind %r" % work_kind)
    actions = ["produce_evidence", "self_review", "record_learning_or_no_learning"]
    if repository_change:
        actions.extend(("run_relevant_tests", "create_scoped_commit"))
    if product_work:
        actions.extend(("integrate_validated_change", "update_product_lifecycle"))
    return tuple(actions)


def new_work_cycle(employee_id, work_item_id, work_kind, objective,
                   repository_change=False, product_work=False):
    employee_profile(employee_id)
    if work_kind not in WORK_KINDS:
        raise ValueError("unknown work kind %r" % work_kind)
    if not work_item_id or not objective:
        raise ValueError("work_item_id and objective are required")
    return {
        "employee_id": employee_id,
        "work_item_id": work_item_id,
        "work_kind": work_kind,
        "objective": objective,
        "status": "planned",
        "plan": {"status": "required", "steps": [], "risks": [], "authority_refs": []},
        "execution": {"status": "pending", "evidence_refs": []},
        "self_review": {"status": "pending", "findings": [], "evidence_refs": []},
        "learning": {"status": "pending", "learning_refs": []},
        "definition_of_done": list(completion_actions(
            work_kind, repository_change=repository_change, product_work=product_work)),
    }
