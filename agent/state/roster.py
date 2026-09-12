"""Provider-neutral Seat registry and current-Claude migration compatibility.

The public interface is deliberately small:

  read()                    Seat identity and Role mapping owned by Thebes.
  seats_by_capability()     The topology shape consumed by state policy.
  claude_compatibility()    A temporary check for the active Claude adapter data.

Claude bindings are never a fallback source for Seat identity or Role mapping.
"""
import json
import os
import re


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEATS_JSON = os.path.join(ROOT, "agent", "state", "registry", "seats.json")
CLAUDE_BINDINGS_DIR = os.path.join(ROOT, ".claude", "bindings")

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


def _binding_fields(path):
    fields = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for key in ("name", "role"):
                    if line.startswith(key + ":"):
                        fields.setdefault(
                            key, line.split(":", 1)[1].strip().strip('"').strip("'"))
    except OSError:
        pass
    return fields


def claude_compatibility(registry_path=SEATS_JSON,
                         bindings_dir=CLAUDE_BINDINGS_DIR):
    """Migration-only parity errors for the currently present Claude configuration.

    A checkout with no Claude binding directory is valid provider-neutral architecture.
    When the directory exists, it represents an active compatibility surface and must
    cover the neutral roster exactly until the Claude renderer owns that translation.
    """
    if not os.path.isdir(bindings_dir):
        return []
    neutral = read(registry_path)
    provider = {f[:-4] for f in os.listdir(bindings_dir) if f.endswith(".yml")}
    expected = set(neutral)
    errors = ["missing Claude binding for neutral seat %r" % seat
              for seat in sorted(expected - provider)]
    errors += ["extra Claude binding has no neutral seat %r" % seat
               for seat in sorted(provider - expected)]
    for seat in sorted(expected & provider):
        fields = _binding_fields(os.path.join(bindings_dir, seat + ".yml"))
        if fields.get("name") not in (None, seat):
            errors.append("Claude binding %r declares incompatible seat identifier %r"
                          % (seat, fields["name"]))
        if fields.get("role") != neutral[seat]["role"]:
            errors.append("Claude binding %r declares role %r; neutral registry requires %r"
                          % (seat, fields.get("role"), neutral[seat]["role"]))
    return errors
