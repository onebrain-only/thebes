"""The orchestrator's fact block (D-044): what is true NOW, from Persistent State, in every turn.

The orchestrator's conversation is compacted many times a day, and a compacted memory answered
"KAN-693 is with Luxor" an hour after Luxor finished. This block is injected into every
orchestrator prompt by agent/scripts/ceo_prompt_hook.py so that answers about who holds what come
from state, not memory. Read-only, local files only (no Jira, no network, no CLI), and it never
raises: a broken section says so and the rest is still printed.

    python3 -m agent.state.facts            # print the block
"""
import calendar
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                  # noqa: E402

RECENT_HOURS = 8
RULE = ("RULE (D-044/D-046): every claim about who holds a ticket, what a team is doing, or a "
        "ticket's state comes from THIS block or a command you run now — never from memory or an "
        "earlier turn. If it is not here, say ما أعرفش and check. Review-passed work merges into "
        "Alpha on its own, and a ticket that supports existing work (parent or KAN key in its "
        "summary) needs no order. Only an Epic or new scope nobody asked for needs a CEO order "
        "lifted from his own words (python3 -m agent.execution.orders grant). Never poll: no "
        "cron, no wakeup — the watchdog wakes you through the inbox.")


def _epoch(stamp):
    try:
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


def _hm(stamp):
    e = _epoch(stamp)
    return time.strftime("%H:%M", time.localtime(e)) if e else "?"


def _ago(stamp, now):
    e = _epoch(stamp)
    if not e:
        return "?"
    m = int((now - e) // 60)
    return "%dm" % m if m < 120 else "%dh" % (m // 60)


def _section(title, fn):
    try:
        return [title] + (fn() or ["  (none)"])
    except Exception as exc:                              # noqa: BLE001
        return [title, "  (unreadable: %s)" % str(exc)[:120]]


def _teams(dispatches, now):
    rows = []
    by_seat = {}
    for r in dispatches:
        by_seat.setdefault(r.get("target_seat_id"), []).append(r)
    for tid, t in sorted(teams.read().items(), key=lambda kv: kv[1].get("number", 99)):
        if t.get("kind", "team") != "team":
            continue
        name = "%s(%s)" % (tid, t.get("lane", "code"))
        mine = sorted(by_seat.get(tid, []), key=lambda r: r.get("created_at") or "")
        open_ = [r for r in mine if r.get("status") in store.CONVERSATION_DISPATCH_OPEN]
        binding = store.active_role_session(tid)
        if not binding:
            rows.append("  %-26s NO SESSION" % name)
            continue
        if open_:
            what = ", ".join("%s since %s" % (r.get("jira_key") or r.get("integrates_base")
                                              and "merge %s" % r["integrates_base"] or "task",
                                              _hm(r.get("created_at"))) for r in open_)
            rows.append("  %-26s BUSY  %s" % (name, what))
            continue
        last = mine[-1] if mine else None
        tail = ("last: %s %s %s (%s ago)" % (last.get("jira_key") or "task", last.get("outcome")
                                            or last.get("status"), _hm(last.get("outcome_at")),
                                            _ago(last.get("outcome_at"), now))) if last else ""
        rows.append("  %-26s FREE  %s" % (name, tail))
    return rows


def _recent(dispatches, now):
    rows = []
    since = now - RECENT_HOURS * 3600
    on_alpha = {r["jira_key"] for r in dispatches if r.get("jira_key") and r.get("integrated_at")}
    done = [r for r in dispatches if r.get("jira_key") and _epoch(r.get("outcome_at")) >= since]
    for r in sorted(done, key=lambda r: r.get("outcome_at"))[-12:]:
        v = r.get("verification") or {}
        review = v.get("verdict") or ("needs-judge" if r.get("needs_judge") else "-")
        live = "on-Alpha" if r["jira_key"] in on_alpha else "not-on-Alpha"
        rows.append("  %s %-8s %-9s by %-14s review:%-11s %s" % (
            _hm(r.get("outcome_at")), r["jira_key"], r.get("outcome"), r.get("target_seat_id"),
            review, live))
    return rows


def _awaiting_merge(dispatches, now):
    """Passed review, not integrated. Older than 3 days is counted, not listed: those predate
    the integration record and may already be on Alpha by another path."""
    since = now - 3 * 86400
    fresh, old = set(), set()
    on_alpha = {r["jira_key"] for r in dispatches if r.get("jira_key") and r.get("integrated_at")}
    for r in dispatches:
        if (r.get("jira_key") and not r.get("root_dispatch_id") and r["jira_key"] not in on_alpha
                and (r.get("verification") or {}).get("verdict") == "pass"
                and not r.get("integrated_at") and not r.get("integration_dispatch_id")):
            stamp = r.get("verified_at") or r.get("outcome_at")
            (fresh if _epoch(stamp) >= since else old).add(r["jira_key"])
    rows = []
    if fresh:
        rows.append("  " + ", ".join(sorted(fresh, key=lambda k: int(k.split("-")[1]))))
    if old - fresh:
        rows.append("  + %d older than 3 days (not tracked by integration; check git before "
                    "claiming they are or are not on Alpha)" % len(old - fresh))
    return rows


def _orders(now):
    from agent.execution import orders
    rows = []
    for g in orders.open_grants(now=now):
        left = g.get("remaining") if g["what"] == "create" else g.get("keys")
        rows.append("  %s %s left=%s until %s «%s»" % (g["id"], g["what"], left,
                                                       _hm(g["expires_at"]), g["quote"][:120]))
    return rows


def _actions():
    from agent.execution import orders
    return ["  " + orders.fmt_action(r)[:200] for r in orders.recent(8)]


def _dispatcher(now):
    p = os.path.join(store.RUNTIME, "ready-dispatcher.log")
    try:
        with open(p, "rb") as fh:
            fh.seek(max(0, os.path.getsize(p) - 20000))
            last = fh.read().decode("utf-8", "ignore").strip().splitlines()[-1]
        rec = json.loads(last)
    except (OSError, ValueError, IndexError):
        return ["  no log"]
    waiting = [d for d in rec.get("done") or [] if d.get("action") == "waiting" and d.get("key")]
    head = "  last run %s (%s ago)" % (_hm(rec.get("at")), _ago(rec.get("at"), now))
    rows = [head]
    for d in waiting[:8]:
        why = d.get("blocked_by") or d.get("reason") or ""
        rows.append("  %s waits: %s" % (d["key"], ", ".join(why) if isinstance(why, list) else why))
    if len(waiting) > 8:
        rows.append("  … %d more waiting" % (len(waiting) - 8))
    return rows


def _retired_messages():
    from agent.execution import orders
    try:
        found = [m for m in orders.messages() if m.get("retired_session")]
    except Exception:                                     # noqa: BLE001
        return []
    return ["  %s [%s] %s" % (m["at"][11:16], m["id"], " ".join(m["text"].split())[:300])
            for m in found]


def build(now=None):
    now = now or time.time()
    out = ["<thebes-facts at=%s>" % time.strftime("%Y-%m-%d %H:%M", time.localtime(now)), RULE]
    try:
        mode = store.current_operating_mode()
        mode = mode.get("mode", "?") if isinstance(mode, dict) else (mode or "?")
    except Exception:                                     # noqa: BLE001
        mode = "?"
    try:
        ints = ["%s %s" % (i.get("kind"), i.get("target")) for i in store.active_interventions()]
    except Exception:                                     # noqa: BLE001
        ints = ["unreadable"]
    out.append("mode: %s · interventions: %s" % (mode, ", ".join(ints) or "none"))
    try:
        from agent.execution import review_queue
        out.append("review channel: %s" % review_queue.get_channel())
    except Exception:                                     # noqa: BLE001
        pass
    try:
        dispatches = store.read_all("conversation_dispatch")
    except Exception:                                     # noqa: BLE001
        dispatches = []
    out += _section("TEAMS (BUSY = an open dispatch right now; nothing else counts as holding):",
                    lambda: _teams(dispatches, now))
    retired = _retired_messages()
    if retired:
        out += ["CEO MESSAGES TYPED INTO A RETIRED SESSION, last 24h — you never saw them, act on them:"]
        out += retired
    out += _section("LIVENESS — every team probed every 5 min, busy or not (D-045; ! = needs you):",
                    lambda: __import__("agent.execution.liveness", fromlist=["x"]).fact_rows(now))
    out += _section("FINISHED, last %dh (time ticket outcome by-team review Alpha):" % RECENT_HOURS,
                    lambda: _recent(dispatches, now))
    out += _section("REVIEW PASSED, NOT ON ALPHA (integrates on its own, D-046):",
                    lambda: _awaiting_merge(dispatches, now))
    out += _section("OPEN CEO ORDERS:", lambda: _orders(now))
    out += _section("RECENT ACTIONS (agent/state/runtime/action-ledger.jsonl):", _actions)
    out += _section("READY DISPATCHER:", lambda: _dispatcher(now))
    out.append("</thebes-facts>")
    return "\n".join(out)


if __name__ == "__main__":
    print(build())
