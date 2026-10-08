"""The PM's decision ledger (D-042): the PM knows every ruling, so a stuck PO asks the PM first.

A subagent starts every run from nothing, so the PM's knowledge has to live in a file it reads
first. This is that file: one line per ruling (who decided, what, the reference), appended by
code where a decision is answered (`decision_gate.answer`) and by the orchestrator after any
cpo / cto / cxo / CEO ruling it obtains. Append-only, local to this workspace (runtime is
gitignored); durable rulings still go into `agent/DECISIONS.md` as D-entries.

    python3 -m agent.execution.pm_ledger add --by cto --ref KAN-437 --text "<one line>"
    python3 -m agent.execution.pm_ledger show [--last 50]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

MAX_TEXT = 400


def path(state_store=store):
    return os.path.join(state_store.RUNTIME, "pm-ledger.md")


def add(decided_by, ref, text, *, state_store=store):
    one_line = " ".join((text or "").split())
    if not decided_by or not one_line:
        raise ValueError("a ledger line needs who decided and what")
    if len(one_line) > MAX_TEXT:
        one_line = one_line[:MAX_TEXT] + " …"
    line = "- %s · %s · %s · %s\n" % (state_store.now(), decided_by, ref or "-", one_line)
    os.makedirs(os.path.dirname(path(state_store)), exist_ok=True)
    with open(path(state_store), "a", encoding="utf-8") as fh:
        fh.write(line)
    return line


def show(last=50, *, state_store=store):
    try:
        with open(path(state_store), encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return ""
    return "".join(lines[-last:])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.pm_ledger", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--by", required=True); a.add_argument("--ref"); a.add_argument("--text", required=True)
    s = sub.add_parser("show"); s.add_argument("--last", type=int, default=50)
    ns = ap.parse_args(argv)
    if ns.cmd == "add":
        sys.stdout.write(add(ns.by, ns.ref, ns.text))
    else:
        sys.stdout.write(show(ns.last) or "(empty)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
