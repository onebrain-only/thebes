"""Tiny assertion harness for the Thebes state suite.

Deliberately not pytest: the state layer is stdlib-only by constitution, and a test
runner that needs an install would make a fresh clone unable to verify itself.
"""
import json, os, sys, tempfile

PASSED, FAILED = [], []


def repo_root():
    """The canonical checkout, derived from this file — never an env var or a
    hard-coded path, so a fresh clone at any location verifies itself."""
    return os.environ.get("THEBES_ROOT") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def state_path():
    return os.path.join(repo_root(), "agent", "state")


def fresh_seat_registry(validate_module, seats):
    """Point validation at a provider-neutral synthetic {seat_id: role} registry."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "seats.json")
    with open(path, "w") as fh:
        json.dump({"record_type": "seat_registry", "schema_version": 1,
                   "seats": {seat: {"role": role}
                             for seat, role in seats.items()}}, fh)
    validate_module.SEATS_JSON = path
    validate_module.CLAUDE_BINDINGS_DIR = os.path.join(tmp, "no-claude-bindings")
    counts = {}
    for role in seats.values():
        counts[role] = counts.get(role, 0) + 1
    topology = os.path.join(tmp, "topology.json")
    with open(topology, "w") as fh:
        json.dump({"record_type": "topology", "schema_version": 3,
                   "capabilities": {role: {"defined_seats": count}
                                    for role, count in counts.items()}}, fh)
    validate_module.TOPOLOGY_JSON = topology
    return tmp


def ok(name, cond):
    (PASSED if cond else FAILED).append(name)
    print(("  ok   " if cond else "  FAIL ") + name)


def raises(name, fn, frag=None):
    try:
        fn()
        ok(name + " [should raise]", False)
    except Exception as e:
        ok(name + (" (%s)" % str(e)[:55]), (frag in str(e)) if frag else True)


def section(title):
    print("== %s ==" % title)


def summary():
    print("\n%d passed, %d FAILED" % (len(PASSED), len(FAILED)))
    for f in FAILED:
        print("  FAILED: " + f)
    return 1 if FAILED else 0
