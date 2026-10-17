#!/usr/bin/env python3
"""The orchestrator's ruling for a team that asked a question (maintenance 2026-10-16, change 10).

A team that returns `decision_required` as a plain result has no open decision request, so the
`decision_gate answer` path cannot resume it. The orchestrator had NO sanctioned way to send the
answer back: a description edit is refused by the permission classifier (a whole-description
rewrite), `conversation-dispatch` needs a Codex thread, and the Ready dispatcher reads only the
description and only from status Ready, so the idle ticket never restarted.

One narrow, audited command:

    python3 -m agent.execution.ticket_ruling KAN-123 --text-file ruling.txt
    python3 -m agent.execution.ticket_ruling KAN-123 --text "the ruling"

It (a) appends the text to the ticket description under a dated `ORCHESTRATOR RULING` heading,
adding nothing else and touching nothing already written, (b) moves the ticket to Ready when it
is in a team's working status (Front-end, Back-end, Operations, Design) so the dispatcher sends it
back to a free team with the ruling in its brief, and (c) writes an audit comment. Any other
status (Backlog, Done, a review column) is refused: this is not a general editor. Only the
orchestrator session may run it.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                    # noqa: E402

READY_ID = "10008"
TEAM_STATUS_IDS = {"10046": "Front-end", "10043": "Back-end", "10049": "Operations", "10047": "Design"}
MAX_TEXT = 6000


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def rule(key, text, *, env=None, state_store=store, jira=None, today=None):
    env = os.environ if env is None else env
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator sends a ruling")
    text = (text or "").strip()
    if not text:
        raise Refused("text-required", "the ruling is empty")
    if len(text) > MAX_TEXT:
        raise Refused("text-too-long", "a ruling is at most %d characters; the rest belongs in a "
                      "new ticket" % MAX_TEXT)
    if jira is None:
        from agent.integrations import jira as jira_mod
        jira = jira_mod
    issue = jira.get_issue(key)
    status_id = str(issue.get("status_id"))
    if status_id not in TEAM_STATUS_IDS and status_id != READY_ID:
        raise Refused("status-not-allowed", "%s is in %r: a ruling goes only to a ticket a team is "
                      "working on (%s) or one already in Ready" % (
                          key, issue.get("status"), ", ".join(sorted(TEAM_STATUS_IDS.values()))))
    heading = "ORCHESTRATOR RULING (%s)" % (today or time.strftime("%Y-%m-%d %H:%M", time.localtime()))
    desc = (issue.get("description") or "").rstrip("\n")
    jira.update_issue(key, {"description": jira.to_adf("%s\n\n%s\n%s" % (desc, heading, text))})
    moved = False
    if status_id in TEAM_STATUS_IDS:
        from agent.execution import jira_sync
        jira_sync._move(key, READY_ID, jira, state_store)
        moved = True
    try:
        jira.add_comment(key, "Thebes: the orchestrator ruled on this ticket (see the ORCHESTRATOR "
                              "RULING at the end of the description)%s." % (
                                  "; moved from %s to Ready so a team picks it up with the ruling"
                                  % TEAM_STATUS_IDS[status_id] if moved else ""))
    except Exception:                                      # noqa: BLE001  the audit note never blocks
        pass
    return {"status": "ruled", "key": key, "moved_to_ready": moved, "from": issue.get("status")}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.ticket_ruling", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text"); g.add_argument("--text-file")
    ns = ap.parse_args(argv)
    text = ns.text
    if ns.text_file:
        with open(ns.text_file, encoding="utf-8") as fh:
            text = fh.read()
    try:
        out = rule(ns.key, text)
    except Refused as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
