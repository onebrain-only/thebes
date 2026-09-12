"""Provider-neutral Seat registry.

The public interface is deliberately small:

  read()                    Seat identity and Role mapping owned by Thebes.
  seats_by_capability()     The topology shape consumed by state policy.

Provider renderers may consume this registry, but provider configuration is not
validated here and is never a fallback source for Seat identity or Role mapping.
"""
import json
import os
import re


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEATS_JSON = os.path.join(ROOT, "agent", "state", "registry", "seats.json")

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RegistryError(ValueError):
    pass


def _document(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise RegistryError("cannot read %s: %s" % (path, exc))


def validation_errors(path=SEATS_JSON):
    """Return structural errors without making any provider a prerequisite."""
    try:
        doc = _document(path)
    except RegistryError as exc:
        return [str(exc)]
    errors = []
    if doc.get("record_type") != "seat_registry":
        errors.append("record_type must be 'seat_registry'")
    if doc.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    entries = doc.get("seats")
    if not isinstance(entries, dict) or not entries:
        return errors + ["seats must be a non-empty object"]
    for seat, entry in sorted(entries.items()):
        where = "seat %r" % seat
        if not isinstance(seat, str) or not _ID.match(seat):
            errors.append("%s has an invalid identifier" % where)
        if not isinstance(entry, dict):
            errors.append("%s must be an object" % where)
            continue
        if set(entry) != {"role"}:
            errors.append("%s may contain only provider-neutral field 'role'" % where)
        role = entry.get("role")
        if not isinstance(role, str) or not _ID.match(role):
            errors.append("%s has an invalid role" % where)
    return errors


def read(path=SEATS_JSON):
    """Return {seat_id: {seat_id, role, capability}} from the neutral registry."""
    errors = validation_errors(path)
    if errors:
        raise RegistryError("; ".join(errors))
    entries = _document(path)["seats"]
    return {
        seat: {"seat_id": seat, "role": entry["role"],
               "capability": entry["role"]}
        for seat, entry in sorted(entries.items())
    }


def seats_by_capability(path=SEATS_JSON):
    out = {}
    for seat, entry in read(path).items():
        out.setdefault(entry["capability"], []).append(seat)
    return out
