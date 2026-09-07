#!/usr/bin/env python3
"""Thebes Sprint — a derived calendar window, and historical truth from Jira.

THE WINDOW IS A FUNCTION, NOT A RECORD

    sprint_id(now)   -> "sprint-YYYY-MM-DD", the Monday of now's week
    is_open(now)     -> Monday 00:00 <= now < Friday 19:00, canonical timezone

Nothing opens or closes a Sprint. Monday's arrival opens it and Friday 19:00 closes
it, with no actor, no scheduler and no stored mutable flag. That is stronger than an
automation rule: it cannot fail to fire, cannot double-fire, and needs no process to
be running — which matters here because nothing in Thebes wakes autonomously, so a
Sprint record would only open or close when a session happened to run.

STATE AT CLOSE IS NOT A LATER READ

  Friday 19:00  KAN-137 is in Review
  Saturday 10:00  someone transitions it to Done
  Saturday 12:00  a current-state read reports "Done at close"        <- FALSE

  So state_at_close is reconstructed from the Jira changelog at the cutoff, never
  observed afterwards. A Saturday current-state read is not "state at close" and
  must never be labelled one.

REPLAY DIRECTION
  Backwards, from the value we know for certain. The current field value is a fact
  in hand; an issue's initial value is not always in the changelog (Jira records the
  creation status implicitly). So we take today's value and undo every change made
  after the cutoff. This also makes the truncation guard meaningful: a partial
  history can only ever be detected, never silently tolerated.

Stdlib only. Requires zoneinfo (Python 3.9+).
"""
import json, os, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

STATE = os.path.dirname(os.path.abspath(__file__))
COMPANY = os.path.join(STATE, "registry", "company.json")

CLOSE_HOUR = 19          # Friday 19:00
CLOSE_MINUTE = 0
SPRINT_LABEL = re.compile(r"^sprint-(\d{4})-(\d{2})-(\d{2})$")
DEFAULT_TZ = "Asia/Dubai"


class SprintError(Exception):
    """Refused computation. Raised where a plausible answer would be a wrong one."""


def canonical_tz():
    """The Sprint boundary's timezone, from the Company registry.

    Stored as an IANA id, never as a fixed offset: 'UTC+4' names an offset, not a
    zone, and cannot express a DST rule. Dubai has none today, which is exactly why
    writing the offset would look correct until the day it isn't.
    """
    try:
        with open(COMPANY, encoding="utf-8") as fh:
            tz = json.load(fh).get("timezone")
    except (OSError, ValueError):
        tz = None
    if not tz:
        raise SprintError(
            "company registry declares no timezone; the Friday cutoff is undefined. "
            "Set 'timezone' in agent/state/registry/company.json to an IANA id.")
    return ZoneInfo(tz)


# ---------------------------------------------------------------- time parsing

_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")


def parse_jira_ts(s):
    """Jira renders '2026-09-06T19:47:06.509+0400'.

    Python 3.9's fromisoformat rejects an offset without a colon, so normalise it
    rather than requiring 3.11.
    """
    if isinstance(s, datetime):
        return s
    t = str(s).strip().replace("Z", "+00:00")
    t = _OFFSET.sub(r"\1:\2", t)
    return datetime.fromisoformat(t)


# ---------------------------------------------------------------- the window

def sprint_id(when=None, tz=None):
    tz = tz or canonical_tz()
    d = (when or datetime.now(tz)).astimezone(tz)
    monday = d.date() - timedelta(days=d.weekday())
    return "sprint-%s" % monday.isoformat()


def window(sid, tz=None):
    """(opens_at, closes_at) for a sprint id. Half-open: opens <= t < closes."""
    tz = tz or canonical_tz()
    m = SPRINT_LABEL.match(str(sid))
    if not m:
        raise SprintError("not a sprint id: %r (expected sprint-YYYY-MM-DD)" % sid)
    y, mo, dd = (int(g) for g in m.groups())
    start = datetime(y, mo, dd, 0, 0, tzinfo=tz)
    if start.weekday() != 0:
        raise SprintError("%s is not a Monday; sprint ids are keyed to the Monday" % sid)
    return start, start + timedelta(days=4, hours=CLOSE_HOUR, minutes=CLOSE_MINUTE)


def is_open(when=None, tz=None):
    tz = tz or canonical_tz()
    d = (when or datetime.now(tz)).astimezone(tz)
    opens, closes = window(sprint_id(d, tz), tz)
    return opens <= d < closes


def cutoff_of(sid, tz=None):
    return window(sid, tz)[1]


# ---------------------------------------------------------------- changelog

def require_complete_changelog(changelog):
    """Refuse an exact answer from a partial history.

    Jira caps the embedded changelog; beyond that cap `histories` is a page, not the
    record. A replay over a page produces a confident wrong answer, so this raises
    instead. Both issues tested in the Wave 5 preflight returned total == len.
    """
    if not isinstance(changelog, dict):
        raise SprintError("changelog missing")
    hist = changelog.get("histories")
    total = changelog.get("total")
    if hist is None or total is None:
        raise SprintError("changelog has no histories/total; completeness unknowable")
    if int(total) != len(hist):
        raise SprintError(
            "changelog truncated (total=%s, retrieved=%d); exact cutoff reconstruction "
            "refused — do NOT substitute the current Jira status" % (total, len(hist)))
    return True


def value_at(current_value, changelog, field, cutoff, use_id=False):
    """The value of `field` at `cutoff`, by undoing every change made after it.

    `use_id` picks the status id ('from'/'to') over the display name
    ('fromString'/'toString'). Ids are the right key across a rename: Wave 5 renames
    five statuses and every historical name in the changelog keeps saying the old one.
    """
    require_complete_changelog(changelog)
    src, _dst = ("from", "to") if use_id else ("fromString", "toString")
    v = current_value
    for h in sorted(changelog["histories"], key=lambda x: parse_jira_ts(x["created"]),
                    reverse=True):
        if parse_jira_ts(h["created"]) <= cutoff:
            break
        for item in h.get("items", ()):
            if item.get("field") == field:
                v = item.get(src)
    return v


def status_id_at(current_status_id, changelog, cutoff):
    return value_at(current_status_id, changelog, "status", cutoff, use_id=True)


def labels_at(current_labels, changelog, cutoff):
    """Jira stores a labels change as space-separated strings."""
    raw = value_at(" ".join(sorted(current_labels or ())), changelog, "labels", cutoff)
    return set((raw or "").split())


# ---------------------------------------------------------------- membership

def was_member(current_labels, changelog, sid, tz=None):
    """Membership AT THE CUTOFF, not membership as it stands now.

    Carry-over adds next Monday's label and keeps the old one, so a later read of the
    label set answers a different question than the one the retrospective asks.
    """
    return sid in labels_at(current_labels, changelog, cutoff_of(sid, tz))


def carried_over(current_labels, current_status_id, changelog, sid, done_status_id,
                 tz=None):
    """A member at the cutoff whose status at the cutoff was not Done.

    Carry-over is a signal, not a defect. Wave 8's retrospective interprets it; Wave 5
    only has to compute it honestly.
    """
    cut = cutoff_of(sid, tz)
    if sid not in labels_at(current_labels, changelog, cut):
        return False
    return status_id_at(current_status_id, changelog, cut) != done_status_id


def scope_changes(changelog, sid, tz=None, fields=("labels", "priority", "Rank",
                                                   "status", "IssueParentAssociation")):
    """Every in-window change to membership, order, position or parent.

    Returns what/when/who, which is the four-field record a retrospective needs to
    tell estimation failure from capacity failure from a blocker from a deliberate
    change. Reason is not derivable from Jira and is recorded in Persistent State.
    """
    require_complete_changelog(changelog)
    opens, closes = window(sid, tz)
    out = []
    for h in sorted(changelog["histories"], key=lambda x: parse_jira_ts(x["created"])):
        t = parse_jira_ts(h["created"])
        if not (opens <= t < closes):
            continue
        for item in h.get("items", ()):
            if item.get("field") in fields:
                out.append({
                    "at": t.isoformat(),
                    "field": item.get("field"),
                    "from": item.get("fromString"),
                    "to": item.get("toString"),
                    "by": (h.get("author") or {}).get("displayName"),
                })
    return out


if __name__ == "__main__":
    tz = canonical_tz()
    now = datetime.now(tz)
    sid = sprint_id(now, tz)
    opens, closes = window(sid, tz)
    print("timezone :", tz)
    print("sprint   :", sid)
    print("window   :", opens.isoformat(), "->", closes.isoformat())
    print("open now :", is_open(now, tz))
