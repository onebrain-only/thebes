#!/usr/bin/env python3
"""Token audit: which sessions called the model, and how many of those calls were a wake.

Every model call re-reads the whole context, so what a session costs is its number of calls times
its context, not what it writes. A call that follows a notification (a finished background command,
a message from another session, a subagent hand-back) is a wake; an idle wake that says "nothing
new" is waste (TH-078). Reads the Claude Code transcripts of this workspace; changes nothing.

    python3 agent/scripts/token_audit.py                 # the last 24 hours
    python3 agent/scripts/token_audit.py --hours 12 --hourly
    python3 agent/scripts/token_audit.py --from 00:00 --to 11:50     # today, local time (the night)
"""
import argparse
import datetime
import glob
import json
import os
from collections import Counter

PROJECTS = os.path.expanduser("~/.claude/projects")
WAKE_MARKERS = ("<task-notification>", "cross-session-message", "Subagent hand-back")


def project_dir():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(PROJECTS, root.replace("/", "-"))


def when(ts):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()


def audit(directory, lo, hi):
    """One row per transcript: calls, context tokens read, and the calls that followed a notification."""
    rows = []
    for path in glob.glob(os.path.join(directory, "*.jsonl")):
        calls = ctx = wakes = wake_ctx = 0
        hourly, after_wake = Counter(), False
        for line in open(path, errors="ignore"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not d.get("timestamp"):
                continue
            t = when(d["timestamp"])
            if not lo <= t <= hi:
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            if d.get("type") == "user" and isinstance(msg.get("content"), str):
                after_wake = any(m in msg["content"] for m in WAKE_MARKERS)
            usage = msg.get("usage")
            if d.get("type") == "assistant" and usage:
                n = (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                     + usage.get("cache_creation_input_tokens", 0))
                calls, ctx = calls + 1, ctx + n
                hourly[t.strftime("%H")] += 1
                if after_wake:
                    wakes, wake_ctx = wakes + 1, wake_ctx + n
        if calls:
            rows.append({"session": os.path.basename(path)[:8], "calls": calls, "ctx": ctx,
                         "wakes": wakes, "wake_ctx": wake_ctx, "hourly": dict(sorted(hourly.items()))})
    return sorted(rows, key=lambda r: -r["ctx"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--from", dest="start", help="HH:MM today, local time")
    ap.add_argument("--to", dest="end", help="HH:MM today, local time")
    ap.add_argument("--hourly", action="store_true", help="calls per local hour for each session")
    ns = ap.parse_args(argv)
    now = datetime.datetime.now().astimezone()
    lo, hi = now - datetime.timedelta(hours=ns.hours), now
    if ns.start or ns.end:
        def at(hhmm, default):
            if not hhmm:
                return default
            h, m = hhmm.split(":")
            return now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        lo, hi = at(ns.start, lo), at(ns.end, hi)
    rows = audit(project_dir(), lo, hi)
    total = sum(r["ctx"] for r in rows) or 1
    print("%s .. %s" % (lo.strftime("%d %H:%M"), hi.strftime("%d %H:%M")))
    print("%-9s %12s %6s %8s %12s   %s" % ("session", "context(M)", "calls", "wakes", "wake ctx(M)", "share"))
    for r in rows:
        print("%-9s %12.1f %6d %8d %12.1f   %3d%%" % (r["session"], r["ctx"] / 1e6, r["calls"], r["wakes"],
                                                     r["wake_ctx"] / 1e6, round(100 * r["ctx"] / total)))
        if ns.hourly:
            print("          calls per hour: %s" % r["hourly"])
    print("total context read: %.1fM tokens in %d calls" % (total / 1e6, sum(r["calls"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
