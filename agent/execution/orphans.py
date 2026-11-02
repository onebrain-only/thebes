"""Tickets in a working column with no team on them (D-047, CEO 2026-11-02).

The liveness sweep (D-045) probes sessions. A ticket can sit in Development / Back-end / Front-end /
Operations / a review column while every session is `free`, because the dispatch that carried it
ended `blocked`, `failed`, `delivery_failed` or `withdrawn` and nothing moves Jira when a dispatch
dies. Nobody holds it and nothing was looking. This module joins one read-only Jira query with the
dispatch records and the review queue and says, per ticket, which of these it is:

    ok             an open dispatch, a held or fresh review item, or Jira moved it in the last GRACE
    dead-end       the last dispatch ended without finishing (blocked/failed/delivery_failed/withdrawn)
    orphan         no dispatch holds it and the last one (if any) completed
    waiting-human  the last dispatch asked a question; decision_gate owns the answer
    waiting-judge  a review item exists and nobody has claimed it

Pure reading: it claims nothing, wakes nothing, writes nothing. The dispatcher re-sends dead-ends
and orphans through its normal claim path (ready_dispatcher.rescue), at most MAX_RESCUES times.
"""
import calendar
import time

from agent.state import store

GRACE_SECONDS = 10 * 60
DEAD = ("blocked", "failed", "delivery_failed", "withdrawn")
ASKING = ("decision_required", "clarification_required")   # decision_gate owns these
NEEDS_TEAM = ("orphan", "dead-end")
MAX_RESCUES = 2
RESCUE_GAP = 30 * 60
REVIEW_COLUMNS = ("QA-Test", "Self-review", "Peer-review")
JQL = 'project = KAN AND statusCategory = "In Progress" ORDER BY updated ASC'


def _epoch(stamp):
    """Epoch of an ISO stamp, Jira's `+0400` form or the store's `Z` form; None if unreadable."""
    if not stamp:
        return None
    try:
        if stamp.endswith("Z"):
            return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
        body, sign, zone = stamp[:19], stamp[-5], stamp[-4:]
        offset = (int(zone[:2]) * 3600 + int(zone[2:]) * 60) * (1 if sign == "+" else -1)
        return calendar.timegm(time.strptime(body, "%Y-%m-%dT%H:%M:%S")) - offset
    except (ValueError, IndexError):
        return None


def classify(issue, dispatches, review_items, now):
    """One ticket -> {key, status, state, why, team?}. `issue` is jira.normalize_issue output."""
    key = issue["key"]
    mine = sorted((d for d in dispatches if d.get("jira_key") == key),
                  key=lambda d: d.get("created_at") or "")
    out = {"key": key, "jira": issue.get("status"), "state": "ok", "why": ""}
    held = [d for d in mine if d.get("status") in store.CONVERSATION_DISPATCH_OPEN]
    if held:
        out.update(why="open dispatch", team=held[0].get("target_seat_id"))
        return out
    items = [i for i in review_items if i.get("ticket") == key]
    if items:
        from agent.execution import review_queue
        if any(review_queue.holder(i["item_id"]) for i in items):
            out["why"] = "review held"
            return out
        out.update(state="waiting-judge", why="review item waits for a judge")
        return out
    moved = _epoch(issue.get("updated"))
    if moved and now - moved < GRACE_SECONDS:
        out["why"] = "Jira moved %d min ago" % ((now - moved) // 60)
        return out
    last = mine[-1] if mine else None
    if last and last.get("status") in ASKING:
        out.update(state="waiting-human", team=last.get("target_seat_id"),
                   why="last dispatch %s" % last["status"])
        return out
    if last and last.get("status") in DEAD:
        out.update(state="dead-end", team=last.get("target_seat_id"),
                   why="last dispatch %s%s" % (last["status"],
                        (": %s" % last["outcome"]) if last.get("outcome") else ""))
        return out
    out.update(state="orphan", why=("last dispatch %s, ticket still in %s" % (last["status"], issue.get("status"))
                                    if last else "no dispatch ever, ticket in %s" % issue.get("status")))
    if last:
        out["team"] = last.get("target_seat_id")
    return out


def scan(*, state_store=store, jira=None, now=None):
    """Classify every working-column ticket. Raises if Jira cannot be read; callers swallow it."""
    if jira is None:
        from agent.integrations import jira as jira_mod
        jira = jira_mod
    now = now or time.time()
    issues = jira.search_issues(JQL, fields=["status", "updated"], limit=100)
    dispatches = state_store.read_all("conversation_dispatch")
    try:
        from agent.execution import review_queue
        review_items = [i for i in review_queue.judge_items(state_store)
                        if not review_queue.is_done(i["item_id"])]
    except Exception:                                   # noqa: BLE001  the queue may be absent
        review_items = []
    return [classify(i, dispatches, review_items, now) for i in issues]


def needs_team(rows):
    return [r for r in rows if r["state"] in NEEDS_TEAM]


def _rescues():
    import json
    import os
    try:
        with open(os.path.join(store.RUNTIME, "rescues.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def rescue_state(key):
    """{"n": attempts so far, "at": epoch of the last one}."""
    return _rescues().get(key) or {"n": 0, "at": 0}


def note_rescue(key, now=None):
    import json
    import os
    data = _rescues()
    data[key] = {"n": rescue_state(key)["n"] + 1, "at": now or time.time()}
    path = os.path.join(store.RUNTIME, "rescues.json")
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    os.replace(path + ".tmp", path)


def exhausted(row):
    """Needs a team, and automatic re-sends are used up (or impossible: it sits in a review column)."""
    return (row["state"] in NEEDS_TEAM
            and (rescue_state(row["key"])["n"] >= MAX_RESCUES or row.get("jira") in REVIEW_COLUMNS))
