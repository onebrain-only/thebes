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

The ticket is the dispatch's `--ticket` and nothing else: a prompt that merely mentions
a KAN key is not assigning that ticket's work, so it is never inferred (D-041).
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
    """(ticket, reason). `ticket` is None when the dispatch is not synced.

    The ticket is ALWAYS named (`--ticket`). It used to be inferred from the only KAN key
    in the prompt (D-040), but a question that merely mentions a ticket ("summarize KAN-1")
    would then have moved it on the board and demanded a brief. A mention is a hint, not
    an assignment."""
    if explicit:
        if not KEY_RE.fullmatch(explicit):
            raise ValueError("ticket must look like KAN-123, got %r" % explicit)
        return explicit, "explicit"
    keys = list(dict.fromkeys(KEY_RE.findall(prompt or "")))
    return None, ("no-ticket" if not keys else
                  "not-synced: the prompt mentions %s; pass --ticket if this is that "
                  "ticket's work" % "+".join(keys[:4]))


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


def _done(record, phase):
    """A phase counts as done only if it SUCCEEDED; a failed note is retried (live 2026-10-09:
    one connection reset left KAN-447 in Ready while its team was working on it)."""
    return ((record.get("jira_sync") or {}).get(phase) or {}).get("status") == "ok"


def _retry(fn, attempts=3, pause=2.0, sleep=None):
    """Run a Jira call again on a transient failure (connection reset, timeout, 5xx)."""
    import time as _t
    sleep = sleep or _t.sleep
    for n in range(attempts):
        try:
            return fn()
        except Exception as exc:                          # noqa: BLE001
            transient = (isinstance(exc, (ConnectionError, TimeoutError, OSError))
                         or exc.__class__.__name__ in ("JiraUnavailable", "JiraRateLimited"))
            if not transient or n == attempts - 1:
                raise
            sleep(pause * (n + 1))


def _move(ticket, target, jira, state_store):
    """Transition unless already there; then let Persistent State observe Jira."""
    import board
    board.assert_transition_target(target)
    before = _retry(lambda: jira.get_issue(ticket)).get("status_id")
    moved = False
    if str(before) != str(target):
        offered = {t["to_status_id"]: t["id"] for t in _retry(lambda: jira.get_transitions(ticket))}
        tid = offered.get(str(target))
        if tid is None:
            raise RuntimeError("Jira offers no transition from %s to %s"
                               % (board.name_for(before) or before, board.name_for(target)))
        _retry(lambda: jira.transition_issue(ticket, tid))
        moved = True
    after = _retry(lambda: jira.get_issue(ticket)).get("status_id")
    task = _task(ticket, state_store)
    if task is not None and board.canonical_for(after) is not None:
        try:
            state_store.observe_lifecycle(ticket, task["revision"], after)
        except state_store.StateError:
            pass                       # a concurrent write; the next observation catches up
    return {"from": before, "to": after, "moved": moved}


def _note(record, phase, outcome, state_store, alert=True):
    """Record what happened on the dispatch; alert the origin on failure."""
    # Verification and the report write the same record within seconds of each other
    # (live 2026-10-09: the `finish` note was lost to that race), so retry the CAS.
    for _ in range(5):
        cur = state_store.read("conversation_dispatch", record["dispatch_id"])
        sync = dict(cur.get("jira_sync") or {})
        sync[phase] = dict(outcome, at=state_store.now())
        try:
            cur = state_store.update("conversation_dispatch", cur["dispatch_id"],
                                     cur["revision"], {"jira_sync": sync})
            break
        except state_store.StateError:
            continue
    else:
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
    if not record.get("jira_key") or _done(record, "start"):
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
    if not record.get("jira_key") or _done(record, "finish"):
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


# ---------------------------------------------------------------- verification (D-041)
DONE_STATUS_ID = "10007"


def _evidence_lines(ver):
    return "\n".join("%s %s — %s: %s" % (cid, (r.get("status") or "?").upper(),
                                        r.get("what", ""), r.get("detail", ""))
                     for cid, r in sorted((ver.get("results") or {}).items()))


def on_verified(root, ver, *, state_store=store, jira=None):
    """Every declared check passed. A SELF-route ticket (the policy default, and what an
    untracked ticket gets) is closed; a PEER or QA route keeps its review status, now with
    verified evidence for its reviewer. Never blocks, never raises."""
    if not root.get("jira_key"):
        return None
    jira = _client(jira, state_store)
    if jira is None:
        return None
    team = _team_name(root)
    try:
        _, route = review_target(root, state_store)
        where = ("branch %s at %s. " % (ver.get("branch"), (ver.get("sha") or "")[:12])
                 if ver.get("sha") else "")
        if route == "self":
            moved = _move(root["jira_key"], DONE_STATUS_ID, jira, state_store)
            head = ("Thebes verified team %s's work and closed this: every declared check "
                    "passed. %s" % (team, where))
        else:
            moved = {"moved": False}
            head = ("Thebes verified team %s's work: every declared check passed. %sThe %s "
                    "reviewer checks only what the checks do not cover." % (team, where, route))
        jira.add_comment(root["jira_key"], "%s\n\n%s" % (head, _evidence_lines(ver)))
        out = dict(moved, status="ok", route=route)
    except Exception as exc:                                 # noqa: BLE001
        out = {"status": "failed", "error": str(exc)[:300]}
    _note(root, "verified", out, state_store)
    return out


def on_exhausted(root, ver, *, state_store=store, jira=None):
    """Still failing after the allowed passes: say why on the ticket; do not move it."""
    if not root.get("jira_key"):
        return None
    jira = _client(jira, state_store)
    if jira is None:
        return None
    try:
        jira.add_comment(
            root["jira_key"],
            "Thebes: verification still fails after %d passes; the ticket stays in review and "
            "needs a decision, not another retry.\n\n%s"
            % (ver.get("cycle") or 0, _evidence_lines(ver)))
        out = {"status": "ok", "moved": False}
    except Exception as exc:                                 # noqa: BLE001
        out = {"status": "failed", "error": str(exc)[:300]}
    _note(root, "exhausted", out, state_store)
    return out


ACCEPTED_RE = __import__("re").compile(r"^\W*(accepted|accept|approved)\b", __import__("re").I)


def on_accepted(ticket, answer_text, *, state_store=store, jira=None):
    """A `work_acceptance` ruling whose FIRST word is ACCEPTED closes the ticket
    (malfunction #18: it stayed in Self-review and blocked the next ticket). Anything else,
    including REJECTED, leaves it alone. Never raises."""
    first = (answer_text or "").strip().splitlines()[0] if (answer_text or "").strip() else ""
    if not ticket or not ACCEPTED_RE.match(first):
        return None
    jira = _client(jira, state_store)
    if jira is None:
        return None
    try:
        moved = _move(ticket, DONE_STATUS_ID, jira, state_store)
        jira.add_comment(ticket, "Thebes: the acceptance ruling said ACCEPTED, so this ticket is "
                                 "closed.\n\n%s" % first[:300])
        return dict(moved, status="ok")
    except Exception as exc:                                 # noqa: BLE001
        return {"status": "failed", "error": str(exc)[:300]}
