"""The PO's Ready command (D-040): make a ticket claimable through the normal path.

    python3 -m agent.state.ready show KAN-123
    python3 -m agent.state.ready set KAN-123 --capability frontend --effort 2 \\
        --basis "<what the effort was sized from>" [--project app] [--move-ready]

`set` records the two facts only the PO states, the required capability and the Work
Effort in sittings, each with its basis. A ticket Thebes has never seen gets its record
first (`--project` is then required). `--move-ready` also moves the Jira ticket to Ready
and records what Jira then says. It prints the ticket's remaining claimability reasons,
so the PO sees what still stands between it and a claim. A common one is
`surfaces-unassessed`: the executing seat states the touched paths at Preflight, and
the PO never invents them.

Run it from a PO seat (`po`, `po-2`) or from the orchestrator executing a CEO order
for the PO. Provenance records `po` (the seat class); the basis should name the seat.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.state import store                                      # noqa: E402
import board                                                       # noqa: E402
import queue as tqueue                                             # noqa: E402

READY_STATUS_ID = "10008"


def _jira():
    from agent.integrations import jira
    return jira


def show(key, *, state_store=store):
    task = state_store.read("task", key)
    if task is None:
        return {"work_item_id": key, "known": False}
    prof = task.get("execution_profile") or {}
    return {"work_item_id": key, "known": True, "project_id": task.get("project_id"),
            "lifecycle": (task.get("lifecycle") or {}).get("jira_status_name"),
            "required_capability": prof.get("required_capability"),
            "work_effort": prof.get("work_effort"),
            "surfaces": task.get("surfaces"),
            "validation_route": prof.get("validation_route"),
            "ownership": task.get("ownership"),
            "unclaimable_reasons": tqueue.unclaimable_reasons(task)}


def set_ready(key, capability, effort, basis, *, project=None, move_ready=False,
              state_store=store, jira=None):
    jira = jira or _jira()
    issue = jira.get_issue(key)                          # proves the ticket exists
    task = state_store.read("task", key)
    admitted = False
    if task is None:
        if not project:
            raise store.StateError("%s is new to Thebes: pass --project (app, admin, "
                                   "design-system)" % key)
        task = state_store.admit_task(key, project, issue["status_id"], capability, "po",
                                      basis)
        admitted = True
    task = state_store.set_work_profile(key, task["revision"], "po", basis,
                                        required_capability=capability, work_effort=effort)
    moved = None
    if move_ready and str(issue.get("status_id")) != READY_STATUS_ID:
        offered = {t["to_status_id"]: t["id"] for t in jira.get_transitions(key)}
        if READY_STATUS_ID not in offered:
            raise store.StateError("Jira offers no transition to Ready from %s"
                                   % issue.get("status"))
        jira.transition_issue(key, offered[READY_STATUS_ID])
        moved = READY_STATUS_ID
    after = jira.get_issue(key).get("status_id")
    task = state_store.read("task", key)
    if str((task.get("lifecycle") or {}).get("jira_status_id")) != str(after):
        state_store.observe_lifecycle(key, task["revision"], after)
    return dict(show(key, state_store=state_store), admitted=admitted,
                moved_to=board.name_for(moved) if moved else None)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.state.ready", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("show"); sh.add_argument("key")
    st = sub.add_parser("set"); st.add_argument("key")
    st.add_argument("--capability", required=True)
    st.add_argument("--effort", required=True, type=int, help="Work Effort in sittings")
    st.add_argument("--basis", required=True)
    st.add_argument("--project")
    st.add_argument("--move-ready", action="store_true")
    ns = ap.parse_args(argv)
    try:
        out = (show(ns.key) if ns.cmd == "show" else
               set_ready(ns.key, ns.capability, ns.effort, ns.basis, project=ns.project,
                         move_ready=ns.move_ready))
    except Exception as exc:                                 # noqa: BLE001
        print(json.dumps({"status": "refused", "error": str(exc)[:500]}, indent=2))
        return 2
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
