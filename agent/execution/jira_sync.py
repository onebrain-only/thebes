"""Jira follows a team dispatch that names one ticket (D-040).

A dispatch to a team skips claim → lease → execute, which is the only path that
moves Jira. Without this the board stays where the PO last left it while a team
works the ticket. Policy, decided by the CEO (2026-10-03):

  team receives the work   → ticket moves to its EXECUTION lane (from the task's
                             required capability, or the dispatch's --capability),
                             comment "<Team> started …"
  team reports completed   → ticket moves to its REVIEW status (the route Thebes
                             policy already derived for the task; Self-review for a
                             ticket Thebes has no record of), comment with the summary
  team reports failed /
  escalated to the CEO     → comment only, no move

Jira stays the lifecycle authority: after a move Persistent State OBSERVES what Jira
now says (`store.observe_lifecycle`). Nothing here decides ownership, claims, or
Done. A Jira failure never blocks or undoes the work; it is recorded on the dispatch
and raised to the origin as a watchdog alert, so the orchestrator hears it.

The ticket is the dispatch's `--ticket`, or the single KAN key in the prompt when
there is exactly one. A prompt that mentions several keys and names no ticket is not
synced — guessing which one is the work would move the wrong card.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.state import store                                        # noqa: E402

KEY_RE = re.compile(r"\bKAN-\d+\b")
DEFAULT_REVIEW_ROUTE = "self"
SUMMARY_CHARS = 1500


def ticket_for(prompt, explicit=None):
    """(ticket, reason). `ticket` is None when the dispatch is not synced."""
    if explicit:
        if not KEY_RE.fullmatch(explicit):
            raise ValueError("ticket must look like KAN-123, got %r" % explicit)
        return explicit, "explicit"
    keys = list(dict.fromkeys(KEY_RE.findall(prompt or "")))
    if len(keys) == 1:
        return keys[0], "only-key-in-prompt"
    return None, ("no-ticket-key" if not keys else
                  "several-keys-%s-name-one-with---ticket" % "+".join(keys[:4]))


CANONICAL_RUNTIME = os.path.join(ROOT, "agent", "state", "runtime")


def _client(jira, state_store):
    """The real board is written only from the canonical workspace's runtime. A
    runtime anywhere else (a test, a second clone) coordinates with nothing and
    must never move a real card; it syncs only through an injected client."""
    if jira is not None:
        return jira
    if os.path.realpath(state_store.RUNTIME) != os.path.realpath(CANONICAL_RUNTIME):
        return None
    from agent.integrations import jira as real
    return real


def _team_name(record):
    from agent.state import teams
    t = teams.read().get(record.get("target_seat_id")) if hasattr(teams, "read") else None
    return (t or {}).get("display_name") or record.get("target_seat_id") or "team"


def _task(ticket, state_store):
    return state_store.read("task", ticket)


def execution_target(record, state_store):
    import board
    cap = record.get("jira_capability")
    task = _task(record["jira_key"], state_store) or {}
    cap = cap or task.get("required_capability") or \
        (task.get("execution_profile") or {}).get("required_capability")
    if not cap or cap in board.NO_EXECUTION_CAPABILITIES:
        return None, cap
    return board.execution_status_for(cap), cap


def review_target(record, state_store):
    import board
    task = _task(record["jira_key"], state_store) or {}
    route = (task.get("execution_profile") or {}).get("validation_route") or DEFAULT_REVIEW_ROUTE
    return board.review_status_for(route) or board.review_status_for(DEFAULT_REVIEW_ROUTE), route


def _move(ticket, target, jira, state_store):
    """Transition unless already there; then let Persistent State observe Jira."""
    import board
    board.assert_transition_target(target)
    before = jira.get_issue(ticket).get("status_id")
    moved = False
    if str(before) != str(target):
        offered = {t["to_status_id"]: t["id"] for t in jira.get_transitions(ticket)}
        tid = offered.get(str(target))
        if tid is None:
            raise RuntimeError("Jira offers no transition from %s to %s"
                               % (board.name_for(before) or before, board.name_for(target)))
        jira.transition_issue(ticket, tid)
        moved = True
    after = jira.get_issue(ticket).get("status_id")
    task = _task(ticket, state_store)
    if task is not None and board.canonical_for(after) is not None:
        try:
            state_store.observe_lifecycle(ticket, task["revision"], after)
        except state_store.StateError:
            pass                       # a concurrent write; the next observation catches up
    return {"from": before, "to": after, "moved": moved}


def _note(record, phase, outcome, state_store, alert=True):
    """Record what happened on the dispatch; alert the origin on failure."""
    cur = state_store.read("conversation_dispatch", record["dispatch_id"])
    sync = dict(cur.get("jira_sync") or {})
    sync[phase] = dict(outcome, at=state_store.now())
    try:
        cur = state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                                 {"jira_sync": sync})
    except state_store.StateError:
        return
    if alert and outcome.get("status") == "failed":
        from agent.execution import watchdog
        watchdog._alert(cur, "jira-sync-failed",
                        "Jira was not updated for %s (%s): %s. The team's work is unaffected; "
                        "move the ticket by hand or fix the cause."
                        % (record["jira_key"], phase, outcome.get("error")),
                        state_store=state_store)


def on_start(record, *, state_store=store, jira=None):
    """Called once the team has the work (delivery DELIVERED)."""
    if not record.get("jira_key") or (record.get("jira_sync") or {}).get("start"):
        return None
    jira = _client(jira, state_store)
    if jira is None:
        return None
    team = _team_name(record)
    try:
        target, cap = execution_target(record, state_store)
        if target is None:
            moved = {"moved": False, "reason": "no execution lane (capability %r); pass "
                                               "--capability on dispatch" % cap}
        else:
            moved = _move(record["jira_key"], target, jira, state_store)
        if not record.get("jira_continuation"):
            jira.add_comment(record["jira_key"],
                             "Thebes: team %s started this (dispatch %s)."
                             % (team, record["dispatch_id"]))
        out = dict(moved, status="ok")
    except Exception as exc:                                 # noqa: BLE001
        out = {"status": "failed", "error": str(exc)[:300]}
    _note(record, "start", out, state_store)
    return out


def on_finish(record, result_text, *, state_store=store, jira=None, escalated=False):
    """Called once the team's result is settled and not routed for a decision."""
    if not record.get("jira_key") or (record.get("jira_sync") or {}).get("finish"):
        return None
    jira = _client(jira, state_store)
    if jira is None:
        return None
    team = _team_name(record)
    outcome = record.get("outcome")
    summary = (result_text or "").strip()
    if len(summary) > SUMMARY_CHARS:
        summary = summary[:SUMMARY_CHARS] + " …"
    try:
        if outcome == "completed":
            target, route = review_target(record, state_store)
            moved = _move(record["jira_key"], target, jira, state_store)
            head = "Thebes: team %s reported completed; ticket moved to review (%s)." % (
                team, route)
        else:
            moved = {"moved": False}
            head = ("Thebes: team %s stopped — %s%s. The ticket was not moved."
                    % (team, outcome, " (waiting on a CEO hard stop)" if escalated else ""))
        jira.add_comment(record["jira_key"], "%s\n\n%s" % (head, summary))
        out = dict(moved, status="ok")
    except Exception as exc:                                 # noqa: BLE001
        out = {"status": "failed", "error": str(exc)[:300]}
    _note(record, "finish", out, state_store)
    return out
