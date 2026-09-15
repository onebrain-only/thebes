"""Command line for the temporary Phase-2 controller entry point."""

import argparse
import json
import sys

from . import ControllerInputError, decide, execute, integrate, load_brief, resume
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
    args = parser.parse_args(argv)
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
