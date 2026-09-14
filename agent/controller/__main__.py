"""Command line for the temporary Phase-2 controller entry point."""

import argparse
import json
import sys

from . import ControllerInputError, execute, load_brief
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
    sub.add_parser("plan-sprint", help="read-only plan for the current canonical sprint")
    sub.add_parser("plan-backlog", help="read-only plan for the canonical Jira Product backlog")
    manifest = sub.add_parser("authority-manifest", help="read-only execution authority discovery")
    manifest.add_argument("work_item_id")
    args = parser.parse_args(argv)
    try:
        outcome = (plan_current_sprint() if args.command == "plan-sprint" else plan_backlog()
                   if args.command == "plan-backlog"
                   else discover_execution_authority(args.work_item_id, store)
                   if args.command == "authority-manifest"
                   else execute(args.work_item_id,
                                load_brief(args.brief_file) if args.brief_file else None))
    except ControllerInputError as exc:
        outcome = {"work_item_id": args.work_item_id, "blocker": str(exc)}
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0 if args.command in ("plan-sprint", "plan-backlog", "authority-manifest") or outcome.get("execution_status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
