"""Single-owner decision routing and risk-based independent review."""

from .registry import OrganizationError, actor_role, authority_document, employees


def decision_class_for_permission(permission, allowed_operation=None):
    """Classify an exact provider permission without consulting a model.

    Native production, secret, deployment and migration operations belong to the
    platform owner. Security/architecture operations belong to the CTO. Everything
    else remains task-local and is covered by the assigned employee's authority.
    """
    text = (str(permission or "") + " " + str(allowed_operation or "")).lower()
    if any(token in text for token in (
            "apply_migration", "production", "deploy", "secret", "credential",
            "dns", "release")):
        return "production_operation"
    if any(token in text for token in (
            "security", "rls", "policy", "schema", "architecture")):
        return "technical_architecture"
    return "task_local_technical"


def decision_owner(decision_class, task_owner=None):
    rules = authority_document()["decision_classes"]
    try:
        rule = dict(rules[decision_class])
    except KeyError:
        raise OrganizationError("unknown decision class %r" % decision_class)
    accountable = rule["accountable_role"]
    if accountable == "task_owner":
        if not task_owner:
            raise OrganizationError("decision %r requires task_owner" % decision_class)
        rule["accountable_employee"] = task_owner
    else:
        rule["eligible_employees"] = [
            employee_id for employee_id, profile in employees().items()
            if profile["role"] == accountable
        ]
        if accountable == "ceo":
            rule["eligible_employees"] = ["ceo"]
    rule["decision_class"] = decision_class
    return rule


def assert_decision_authority(decision_class, actor, task_owner=None):
    owner = decision_owner(decision_class, task_owner=task_owner)
    if owner["accountable_role"] == "task_owner":
        allowed = actor == owner["accountable_employee"]
    else:
        try:
            allowed = actor_role(actor) == owner["accountable_role"]
        except OrganizationError:
            allowed = False
    if not allowed:
        raise OrganizationError(
            "%r is not the decision owner for %r; accountable role is %r"
            % (actor, decision_class, owner["accountable_role"]))
    return owner


def independent_review_required(risks=(), explicit_policy=False,
                                evidence_conflict=False, actor_conflict=False):
    """Return the reasons for an independent review; empty means self-review."""
    configured = set(authority_document()["independent_review_risks"])
    reasons = set(risks or ()) & configured
    if explicit_policy:
        reasons.add("explicit_policy")
    if evidence_conflict:
        reasons.add("evidence_conflict")
    if actor_conflict:
        reasons.add("actor_conflict")
    return tuple(sorted(reasons))
