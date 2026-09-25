"""Command line for the Controller.

Since Phase 4 this is NOT the operational front door. `execute`, `resume` and
`decide` orchestrate Product execution and now expect to be launched by the
Listener, which runs them in its own process; invoked directly they refuse and
say where the front door is. A maintenance override remains, because recovery
and debugging genuinely need it — it just has to state its reason.

Everything else here is unchanged and deliberately still direct: `integrate` is
the recovery path, and `plan-sprint`, `plan-backlog` and `authority-manifest`
are read-only and orchestrate nothing.
"""

import argparse
import json
import sys

from . import (ControllerInputError, decide, execute, integrate, load_brief, resume,
               validate)
from .entry import ORCHESTRATING_COMMANDS, caller as classify_caller
from .session_dispatch import bind_session, dispatch_session, session_outcome
from .sprint_plan import plan_current_sprint
from .backlog_plan import plan_backlog
from agent.execution.authority import discover_execution_authority
from agent.state import store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m agent.controller")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("execute", help="submit one explicit bounded work item")
    run.add_argument("work_item_id")
    run.add_argument("--brief-file", default=None,
                     help="EXCEPTIONAL/DEBUG ONLY. Thebes derives the routine brief from "
                          "canonical state; a supplied brief fills gaps and may not "
                          "contradict a canonical safety fact")
    again = sub.add_parser("resume",
                           help="resume one already-approved continuation and run its tail")
    again.add_argument("work_item_id")
    # A decision is the accountable employee's answer to a boundary Thebes reported. The
    # seat and provider session are derived from canonical state, never supplied
    # here: a caller may answer a question, not choose who it was asked of.
    call = sub.add_parser("decide",
                          help="record one exact accountable-role approval and resume")
    call.add_argument("work_item_id")
    call.add_argument("--invocation", required=True,
                      help="the original needs_input invocation this answers")
    call.add_argument("--permission", required=True,
                      help="the exact native permission that was denied")
    call.add_argument("--scope", required=True, help="what this approval permits")
    call.add_argument("--authority", default=None,
                      help="the employee/owner answering the decision boundary")
    call.add_argument("--operation", default=None,
                      help="the exact allowed operation, when the permission is scoped")
    # A review that is already open — context recorded, owner resolved — has no
    # execution to run first. `validate` dispatches exactly that context to its
    # recorded owner and runs the same tail a passed validation always earns.
    check = sub.add_parser("validate",
                           help="dispatch one already-open review context to its "
                                "recorded owner, then run integration and completion")
    check.add_argument("work_item_id")
    land = sub.add_parser("integrate",
                          help="land one work item's validated Product work on Canary")
    land.add_argument("work_item_id")
    sub.add_parser("plan-sprint", help="read-only plan for the current canonical sprint")
    sub.add_parser("plan-backlog", help="read-only plan for the canonical Jira Product backlog")
    manifest = sub.add_parser("authority-manifest", help="read-only execution authority discovery")
    manifest.add_argument("work_item_id")
    # The persistent-session path: prepare exactly as `execute` does, stop before
    # any provider, and return a packet the controller conversation delivers.
    prep = sub.add_parser("dispatch-session",
                          help="prepare one work item for a bound persistent session "
                               "and return its dispatch packet; launches nothing")
    prep.add_argument("work_item_id")
    report = sub.add_parser("session-outcome",
                            help="record what a bound session reported for one dispatch")
    report.add_argument("work_item_id")
    report.add_argument("--dispatch", required=True)
    report.add_argument("--outcome", required=True)
    report.add_argument("--summary", required=True)
    report.add_argument("--session-id", default=None)
    report.add_argument("--reference", default=None)
    # Maintenance/internal: binds identity, orchestrates nothing.
    bind = sub.add_parser("bind-session",
                          help="bind or rebind one seat to a persistent provider session")
    bind.add_argument("seat_id")
    bind.add_argument("--provider", required=True)
    bind.add_argument("--session-id", required=True)
    bind.add_argument("--stable-home", required=True)
    bind.add_argument("--session-name", default=None)
    bind.add_argument("--bound-by", default="ceo")
    for orchestrating in (run, again, call, check, prep, report):
        orchestrating.add_argument(
            "--maintenance-reason", default=None,
            help="bypass the Listener front door for recovery, debugging or a "
                 "test, stating why; the reason is recorded in the result")
    args = parser.parse_args(argv)

    permitted, classification, detail = classify_caller(
        args.command, getattr(args, "maintenance_reason", None))
    if not permitted:
        print(json.dumps({"work_item_id": getattr(args, "work_item_id", None),
                          "blocker": classification, "entry_path": "direct",
                          "detail": detail}, indent=2, sort_keys=True))
        return 2
    try:
        outcome = (dispatch_session(args.work_item_id) if args.command == "dispatch-session"
                   else session_outcome(args.work_item_id, args.dispatch, args.outcome,
                                        args.session_id, args.summary, args.reference)
                   if args.command == "session-outcome"
                   else bind_session(args.seat_id, args.provider, args.session_id,
                                     args.stable_home, session_name=args.session_name,
                                     bound_by=args.bound_by)
                   if args.command == "bind-session"
                   else integrate(args.work_item_id) if args.command == "integrate"
                   else validate(args.work_item_id) if args.command == "validate"
                   else resume(args.work_item_id) if args.command == "resume"
                   else decide(args.work_item_id, args.invocation, args.permission,
                               args.scope, args.operation,
                               approving_authority=args.authority)
                   if args.command == "decide"
                   else plan_current_sprint() if args.command == "plan-sprint" else plan_backlog()
                   if args.command == "plan-backlog"
                   else discover_execution_authority(args.work_item_id, store)
                   if args.command == "authority-manifest"
                   else execute(args.work_item_id,
                                load_brief(args.brief_file) if args.brief_file else None))
    except ControllerInputError as exc:
        outcome = {"work_item_id": getattr(args, "work_item_id", None), "blocker": str(exc)}
    if args.command in ORCHESTRATING_COMMANDS:
        # How this invocation was authorized travels with its result, so an
        # operational run can be traced back to the intent that caused it and a
        # bypass is visible in the record rather than only in a shell history.
        outcome["entry_path"] = classification
        outcome["entry_reference"] = detail
    print(json.dumps(outcome, indent=2, sort_keys=True))
    if args.command in ("plan-sprint", "plan-backlog", "authority-manifest"):
        return 0
    if args.command in ("execute", "resume", "decide"):
        return 0 if outcome.get("execution_status") == "completed" else 1
    if args.command == "validate":
        return 0 if outcome.get("validation_status") in (
            "validation-passed", "validation-failed") else 1
    if args.command == "integrate":
        return 0 if outcome.get("integration_status") in (
            "integrated", "already-present", "no-product-commit-required") else 1
    if args.command == "dispatch-session":
        return 0 if outcome.get("dispatch_status") == "dispatched" else 1
    if args.command == "session-outcome":
        return 0 if outcome.get("outcome_status") == "recorded" else 1
    if args.command == "bind-session":
        return 0 if outcome.get("binding_status") in ("bound", "rebound") else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
