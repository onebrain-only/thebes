"""Operating-mode switch as one fixed command, so a permission rule can name it.

    python3 -m agent.state.mode show
    python3 -m agent.state.mode set PRODUCT_EXECUTION --by ceo --reason "<why>"
    python3 -m agent.state.mode set SYSTEM_MAINTENANCE --by orchestrator --reason "<why>"

A thin wrapper over `store.set_operating_mode`: the same revision CAS, the same
refusal to enter maintenance while an execution lease is open. It exists only so
the transition is a stable, auditable command line instead of ad-hoc Python.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                      # noqa: E402

MODES = ("SYSTEM_MAINTENANCE", "PRODUCT_EXECUTION")
ACTORS = ("ceo", "orchestrator")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.state.mode", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("mode", choices=MODES)
    s.add_argument("--by", choices=ACTORS, required=True)
    s.add_argument("--reason", required=True)
    ns = ap.parse_args(argv)
    cur = store.read("operating_mode", "current")
    if ns.cmd == "show":
        print(json.dumps({"mode": cur["mode"], "revision": cur["revision"],
                          "changed_by": cur.get("changed_by"),
                          "reason_ref": cur.get("reason_ref")}, indent=2))
        return 0
    if cur["mode"] == ns.mode:
        print(json.dumps({"mode": cur["mode"], "revision": cur["revision"],
                          "status": "unchanged"}, indent=2))
        return 0
    try:
        rec = store.set_operating_mode(ns.mode, ns.by, ns.reason,
                                       expected_revision=cur["revision"])
    except store.StateError as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"mode": rec["mode"], "revision": rec["revision"], "status": "changed"},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
