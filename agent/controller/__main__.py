"""Command line for the temporary Phase-2 controller entry point."""

import argparse
import json
import sys

from . import ControllerInputError, execute, load_brief


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m agent.controller")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("execute", help="submit one explicit bounded work item")
    run.add_argument("work_item_id")
    run.add_argument("--brief-file", required=True,
                     help="JSON bounded execution brief prepared by the controller")
    args = parser.parse_args(argv)
    try:
        outcome = execute(args.work_item_id, load_brief(args.brief_file))
    except ControllerInputError as exc:
        outcome = {"work_item_id": args.work_item_id, "blocker": str(exc)}
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0 if outcome.get("execution_status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
