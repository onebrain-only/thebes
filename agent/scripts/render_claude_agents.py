#!/usr/bin/env python3
"""Render Claude agent definitions from neutral Seats and Claude configuration."""
import argparse
import os
import sys
import tempfile


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, "agent", "state")
if STATE not in sys.path:
    sys.path.insert(0, STATE)

import roster  # noqa: E402


SEATS_JSON = os.path.join(ROOT, "agent", "state", "registry", "seats.json")
BINDINGS_DIR = os.path.join(ROOT, ".claude", "bindings")
ROLES_DIR = os.path.join(ROOT, "agent", "roles")
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")


class RenderError(ValueError):
    pass


def _configuration_files(bindings_dir):
    if not os.path.isdir(bindings_dir):
        return {}
    return {
        filename[:-4]: os.path.join(bindings_dir, filename)
        for filename in os.listdir(bindings_dir)
        if filename.endswith(".yml")
    }


def _field_values(data, key):
    prefix = (key + ":").encode("ascii")
    values = []
    for line in data.splitlines():
        if line.startswith(prefix):
            value = line.split(b":", 1)[1].strip().strip(b'"').strip(b"'")
            values.append(value.decode("utf-8", errors="replace"))
    return values


def validation_errors(registry_path=SEATS_JSON, bindings_dir=BINDINGS_DIR,
                      roles_dir=ROLES_DIR):
    """Return Claude-renderer migration errors without changing neutral invariants."""
    try:
        neutral = roster.read(registry_path)
    except roster.RegistryError as exc:
        return [str(exc)]

    configurations = _configuration_files(bindings_dir)
    expected = set(neutral)
    configured = set(configurations)
    errors = [
        "missing Claude configuration for neutral seat %r" % seat
        for seat in sorted(expected - configured)
    ]
    errors += [
        "Claude configuration has no neutral seat %r" % seat
        for seat in sorted(configured - expected)
    ]

    for seat in sorted(expected & configured):
        with open(configurations[seat], "rb") as fh:
            data = fh.read()
        names = _field_values(data, "name")
        roles = _field_values(data, "role")
        if len(names) > 1:
            errors.append("Claude configuration %r declares duplicate name metadata" % seat)
        elif names and names[0] != seat:
            errors.append(
                "Claude configuration %r declares incompatible seat identifier %r"
                % (seat, names[0])
            )
        if len(roles) != 1:
            errors.append(
                "Claude configuration %r must retain exactly one legacy role metadata field"
                % seat
            )
        elif roles[0] != neutral[seat]["role"]:
            errors.append(
                "Claude configuration %r declares legacy role %r; neutral registry requires %r"
                % (seat, roles[0], neutral[seat]["role"])
            )
        if any(line.startswith(b"seat_context:") for line in data.splitlines()):
            errors.append(
                "Claude configuration %r declares seat_context, retired in Wave 6" % seat
            )

        role_path = os.path.join(roles_dir, neutral[seat]["role"] + ".md")
        if not os.path.isfile(role_path):
            errors.append(
                "neutral seat %r requires missing Role contract %s"
                % (seat, role_path)
            )
    return errors


def render_content(seat, role_id, configuration, role_contract):
    """Combine a neutral Seat/Role with opaque Claude-only configuration bytes."""
    provider_lines = [
        line for line in configuration.splitlines(keepends=True)
        if not line.startswith(b"role:")
    ]
    return b"".join([
        b"---\n",
        b"".join(provider_lines),
        b"---\n",
        b"<!-- GENERATED FILE \xe2\x80\x94 do not edit. -->\n",
        ("<!-- Seat:    .claude/bindings/%s.yml -->\n" % seat).encode("utf-8"),
        ("<!-- Role:    agent/roles/%s.md -->\n" % role_id).encode("utf-8"),
        b"<!-- Rebuild: agent/scripts/build-agents.sh -->\n",
        b"\n",
        role_contract,
    ])


def expected_outputs(registry_path=SEATS_JSON, bindings_dir=BINDINGS_DIR,
                     roles_dir=ROLES_DIR):
    errors = validation_errors(registry_path, bindings_dir, roles_dir)
    if errors:
        raise RenderError("; ".join(errors))
    neutral = roster.read(registry_path)
    outputs = {}
    for seat, entry in sorted(neutral.items()):
        with open(os.path.join(bindings_dir, seat + ".yml"), "rb") as fh:
            configuration = fh.read()
        with open(os.path.join(roles_dir, entry["role"] + ".md"), "rb") as fh:
            role_contract = fh.read()
        outputs[seat] = render_content(
            seat, entry["role"], configuration, role_contract
        )
    return outputs


def run(check=False, registry_path=SEATS_JSON, bindings_dir=BINDINGS_DIR,
        roles_dir=ROLES_DIR, agents_dir=AGENTS_DIR):
    try:
        outputs = expected_outputs(registry_path, bindings_dir, roles_dir)
    except RenderError as exc:
        for error in str(exc).split("; "):
            print("ERROR: " + error)
        return 1

    os.makedirs(agents_dir, exist_ok=True)
    status = 0
    if check:
        actual = {
            filename[:-3] for filename in os.listdir(agents_dir)
            if filename.endswith(".md")
        }
        for seat in sorted(actual - set(outputs)):
            print("EXTRA   %s  (no neutral Seat owns this generated output)" % seat)
            status = 1
    for seat, content in sorted(outputs.items()):
        output_path = os.path.join(agents_dir, seat + ".md")
        if check:
            try:
                with open(output_path, "rb") as fh:
                    current = fh.read()
            except OSError:
                current = None
            if current == content:
                print("ok      " + seat)
            else:
                print("STALE   %s  (%s differs from generated output)" %
                      (seat, output_path))
                status = 1
            continue

        descriptor, temporary = tempfile.mkstemp(dir=agents_dir)
        try:
            with os.fdopen(descriptor, "wb") as fh:
                fh.write(content)
            os.replace(temporary, output_path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        print("built   " + seat)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return run(check=args.check)


if __name__ == "__main__":
    sys.exit(main())
