"""Read-only composition of Seat, Role, employee profile, and authority registries."""

import json
import os
import re


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = os.path.join(ROOT, "agent", "state", "registry")
SEATS = os.path.join(REGISTRY, "seats.json")
ROLES = os.path.join(REGISTRY, "roles.json")
PROFILES = os.path.join(REGISTRY, "employee_profiles.json")
AUTHORITY = os.path.join(REGISTRY, "authority.json")
CORE_CAPABILITIES = (
    "understand_and_plan", "perform_role_work", "self_review_and_audit",
    "learn_and_adapt",
)
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganizationError(ValueError):
    pass


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise OrganizationError("cannot read %s: %s" % (path, exc))


def documents():
    return {
        "seats": _read(SEATS),
        "roles": _read(ROLES),
        "profiles": _read(PROFILES),
        "authority": _read(AUTHORITY),
    }


def validate_registries():
    errors = []
    try:
        docs = documents()
    except OrganizationError as exc:
        return [str(exc)]
    expected = {
        "seats": "seat_registry", "roles": "role_registry",
        "profiles": "employee_profile_registry", "authority": "authority_registry",
    }
    for name, record_type in expected.items():
        doc = docs[name]
        if doc.get("record_type") != record_type:
            errors.append("%s record_type must be %r" % (name, record_type))
        if doc.get("schema_version") != 1:
            errors.append("%s schema_version must be 1" % name)
    roles = docs["roles"].get("roles") or {}
    required = tuple(docs["roles"].get("required_capabilities") or ())
    if required != CORE_CAPABILITIES:
        errors.append("role registry must declare the four core employee capabilities in order")
    seats = docs["seats"].get("seats") or {}
    profiles = docs["profiles"].get("profiles") or {}
    if set(seats) != set(profiles):
        errors.append("employee profiles must cover exactly the declared seats")
    for seat_id, seat in sorted(seats.items()):
        role_id = (seat or {}).get("role")
        if role_id not in roles:
            errors.append("seat %r names unknown role %r" % (seat_id, role_id))
        if not _ID.match(str(seat_id)):
            errors.append("invalid seat id %r" % seat_id)
        if not str((profiles.get(seat_id) or {}).get("primary_scope") or "").strip():
            errors.append("employee %r needs a primary_scope" % seat_id)
    for role_id, role in sorted(roles.items()):
        outputs = (role or {}).get("work_outputs") or []
        if not isinstance(outputs, list) or not outputs:
            errors.append("role %r needs at least one work_output" % role_id)
    decisions = docs["authority"].get("decision_classes") or {}
    for decision_class, rule in sorted(decisions.items()):
        owner = (rule or {}).get("accountable_role")
        if owner not in roles and owner not in ("ceo", "task_owner"):
            errors.append("decision %r names unknown accountable role %r"
                          % (decision_class, owner))
        for role_id in (rule or {}).get("consulted_roles") or []:
            if role_id not in roles:
                errors.append("decision %r consults unknown role %r"
                              % (decision_class, role_id))
    return errors


def employees():
    errors = validate_registries()
    if errors:
        raise OrganizationError("; ".join(errors))
    docs = documents()
    roles = docs["roles"]["roles"]
    profiles = docs["profiles"]["profiles"]
    out = {}
    for seat_id, seat in sorted(docs["seats"]["seats"].items()):
        role_id = seat["role"]
        role = roles[role_id]
        out[seat_id] = {
            "employee_id": seat_id,
            "role": role_id,
            "role_family": role["family"],
            "primary_scope": profiles[seat_id]["primary_scope"],
            "core_capabilities": list(CORE_CAPABILITIES),
            "accountability": role["accountability"],
            "routine_scope": list(role.get("routine_scope") or []),
            "work_outputs": list(role.get("work_outputs") or []),
            "decision_classes": list(role.get("decision_classes") or []),
            "conflicts": list(role.get("conflicts") or []),
        }
    return out


def employee_profile(employee_id):
    try:
        return employees()[employee_id]
    except KeyError:
        raise OrganizationError("unknown employee %r" % employee_id)


def authority_document():
    errors = validate_registries()
    if errors:
        raise OrganizationError("; ".join(errors))
    return documents()["authority"]


def actor_role(actor):
    if actor == "ceo":
        return "ceo"
    profile = employee_profile(actor)
    return profile["role"]
