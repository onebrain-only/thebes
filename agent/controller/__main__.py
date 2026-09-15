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

from . import ControllerInputError, decide, execute, integrate, load_brief, resume
from .entry import ORCHESTRATING_COMMANDS, caller as classify_caller
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
    # A decision is the CEO's answer to a boundary Thebes already reported. The
    # seat and provider session are derived from canonical state, never supplied
    # here: a caller may answer a question, not choose who it was asked of.
    call = sub.add_parser("decide",
                          help="record one exact CEO approval and resume that workflow")
    call.add_argument("work_item_id")
    call.add_argument("--invocation", required=True,
                      help="the original needs_input invocation this answers")
    call.add_argument("--permission", required=True,
                      help="the exact native permission that was denied")
    call.add_argument("--scope", required=True, help="what this approval permits")
    call.add_argument("--operation", default=None,
                      help="the exact allowed operation, when the permission is scoped")
    land = sub.add_parser("integrate",
                          help="land one work item's validated Product work on Canary")
    land.add_argument("work_item_id")
    sub.add_parser("plan-sprint", help="read-only plan for the current canonical sprint")
    sub.add_parser("plan-backlog", help="read-only plan for the canonical Jira Product backlog")
    manifest = sub.add_parser("authority-manifest", help="read-only execution authority discovery")
    manifest.add_argument("work_item_id")
    for orchestrating in (run, again, call):
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
        outcome = (integrate(args.work_item_id) if args.command == "integrate"
                   else resume(args.work_item_id) if args.command == "resume"
                   else decide(args.work_item_id, args.invocation, args.permission,
                               args.scope, args.operation)
                   if args.command == "decide"
                   else plan_current_sprint() if args.command == "plan-sprint" else plan_backlog()
                   if args.command == "plan-backlog"
                   else discover_execution_authority(args.work_item_id, store)
                   if args.command == "authority-manifest"
                   else execute(args.work_item_id,
                                load_brief(args.brief_file) if args.brief_file else None))
    except ControllerInputError as exc:
        outcome = {"work_item_id": args.work_item_id, "blocker": str(exc)}
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
    if args.command == "integrate":
        return 0 if outcome.get("integration_status") in (
            "integrated", "already-present", "no-product-commit-required") else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
