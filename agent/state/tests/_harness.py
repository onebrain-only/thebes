"""Tiny assertion harness for the Thebes state suite.

Deliberately not pytest: the state layer is stdlib-only by constitution, and a test
runner that needs an install would make a fresh clone unable to verify itself.
"""
import os, sys

PASSED, FAILED = [], []


def repo_root():
    """The canonical checkout, derived from this file — never an env var or a
    hard-coded path, so a fresh clone at any location verifies itself."""
    return os.environ.get("THEBES_ROOT") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def state_path():
    return os.path.join(repo_root(), "agent", "state")


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
