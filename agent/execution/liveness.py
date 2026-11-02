"""Liveness check of EVERY team, every 5 minutes (D-045, CEO 2026-11-01).

"Not just give the task and wait for the answer: every 5 minutes see what is stuck where, so it
has a 360 view of all the teams, even the ones that are not working." A team the orchestrator
believes is idle can be stuck, and a team it believes is busy can have stopped; asking only the
teams that hold work misses both. So the watchdog probes all of them, whatever the orchestrator
thinks, and writes one snapshot that the fact block shows in every orchestrator turn.

The probe reads the session, never talks to it: the CLI's agent row (working / idle / blocked),
the time its transcript last moved, the tool call it is waiting on, and its open dispatches.
Typing into a team every 5 minutes would interrupt the work it is checking.

    status      meaning
    busy        working on an open dispatch, transcript moving
    free        idle, no open dispatch
    silent      says `working`, transcript still for SILENT_SECONDS: a hung tool call
                (Memphis 2026-10-30: one execute_sql never returned and it looked busy for 10h)
    blocked     waiting on a permission or a question
    untracked   working with NO open dispatch: work Thebes did not send, or a dispatch closed
                while the team still works. Neither free nor holding anything
    stalled     open dispatch but the session is not working (the watchdog tick resumes it)
    no-session  no bound session at all

silent, untracked, no-session, and blocked without a dispatch reach the orchestrator's inbox
once each (stalled and blocked-with-a-dispatch already raise a watchdog alert there).

    python3 -m agent.execution.liveness sweep          # probe now, print the snapshot
    python3 -m agent.execution.liveness show           # print the last snapshot
    python3 -m agent.execution.liveness revive <team>  # stop + same-session resume a silent team
"""
import argparse
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                  # noqa: E402

CHECK_EVERY = 300
SILENT_SECONDS = 20 * 60
STALE_SECONDS = 15 * 60          # a snapshot older than this means the watchdog is not running
INBOX = ("silent", "untracked", "no-session", "blocked")
REVIVE = ("THEBES_LIVENESS %s: your session showed `working` but nothing moved for %d minutes; "
          "your last tool call (%s) never returned and was cut off. Do not repeat it as one long "
          "call: if it touched the database, first check pg_stat_activity for a backend it left "
          "open and cancel it (ops lane only). Then continue the open dispatch from where you are "
          "and report as its envelope says.")


def path(name="snapshot"):
    return os.path.join(store.RUNTIME, {"snapshot": "liveness.json",
                                        "collected": "liveness-collected.json"}[name])


def _load(name, default):
    try:
        with open(path(name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _save(name, data):
    tmp = path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path(name))


def last_activity(session_id, projects=None):
    """Epoch of the last write to the session's transcript or its subagents' transcripts."""
    root = projects or os.path.expanduser("~/.claude/projects")
    files = glob.glob(os.path.join(root, "*", "%s.jsonl" % session_id))
    files += glob.glob(os.path.join(root, "*", session_id, "subagents", "*"))
    stamps = []
    for f in files:
        try:
            stamps.append(os.path.getmtime(f))
        except OSError:
            pass
    return max(stamps) if stamps else None


def review_held(session_id, now):
    """Review items this session claimed in the last hour and has not finished: the review
    team's work arrives through review_queue claims, not conversation dispatches."""
    from agent.execution import review_queue
    held = []
    try:
        names = os.listdir(review_queue._dir("claims"))
    except OSError:
        return held
    for name in names:
        c = review_queue._read(os.path.join(review_queue._dir("claims"), name)) or {}
        if (c.get("thread") == "claude:%s" % session_id and c.get("item_id")
                and now - c.get("at", 0) < 3600 and not review_queue.is_done(c["item_id"])):
            held.append(c["item_id"])
    return held


FINISH_GRACE = 10 * 60
IDLE_WAIT = "review_queue wait"      # the review team idles inside this call; it is not hung


def finished_recently(team, now, state_store=store):
    """A team keeps `working` for a while after it submits; that is not untracked work."""
    import calendar
    for r in state_store.read_all("conversation_dispatch"):
        if r.get("target_seat_id") == team and r.get("outcome_at"):
            try:
                at = calendar.timegm(time.strptime(r["outcome_at"], "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                continue
            if now - at < FINISH_GRACE:
                return True
    return False


def _probe(tid, t, rows, open_by_seat, now, state_store, projects):
    from agent.execution import watchdog
    entry = {"team": tid, "lane": t.get("lane", "code"), "status": None, "detail": "",
             "dispatch": None, "key": None}
    open_ = open_by_seat.get(tid, [])
    if open_:
        entry["dispatch"] = open_[0]["dispatch_id"]
        entry["ticket"] = open_[0].get("jira_key")
    binding = state_store.active_role_session(tid)
    if not binding:
        entry.update(status="no-session", key="%s:no-session" % tid,
                     detail="no bound session")
        return entry
    sid = binding["session_id"]
    entry["session"] = sid[:8]
    row = rows.get(sid) or {}
    state = row.get("state")
    last = last_activity(sid, projects)
    quiet = int(now - last) if last else None
    entry["quiet_min"] = quiet // 60 if quiet is not None else None
    waiting_on = watchdog.pending_tool(sid, projects) if state == "working" else None
    if waiting_on and IDLE_WAIT in (waiting_on[1] or "") and not open_:
        entry.update(status="free", detail="waiting for review work")
    elif state == "blocked":
        waiting = watchdog.pending_tool(sid, projects)
        entry.update(status="blocked", detail="waits on %s" % (
            ("%s %s" % waiting) if waiting else "a permission or a question"),
            key="%s:blocked:%d" % (tid, int(last or 0)))
    elif state == "working" and quiet is not None and quiet >= SILENT_SECONDS:
        waiting = watchdog.pending_tool(sid, projects)
        entry.update(status="silent", detail="`working` but still for %d min; open call: %s" % (
            quiet // 60, ("%s %s" % waiting) if waiting else "none found"),
            key="%s:silent:%d" % (tid, int(last)))
    elif state == "working":
        reviews = review_held(sid, now)
        if open_ or reviews:
            entry.update(status="busy", detail=", ".join(
                [r.get("jira_key") or ("merge %s" % r["integrates_base"] if r.get("integrates_base")
                                       else "task") for r in open_]
                + ["review %s" % i for i in reviews]))
        elif finished_recently(tid, now, state_store):
            entry.update(status="busy", detail="finishing its turn after submitting")
        else:
            entry.update(status="untracked", detail="working with no open dispatch",
                         key="%s:untracked:%s" % (tid, row.get("startedAt") or int(last or 0)))
    elif open_:
        entry.update(status="stalled", detail="dispatch open, session %s" % (state or "not running"))
    else:
        entry.update(status="free", detail=state or "not running")
    return entry


def sweep(*, state_store=store, cli=None, now=None, projects=None):
    """Probe every team and write the snapshot. Returns the snapshot."""
    from agent.execution.claude_cli import ClaudeCli
    now = now or time.time()
    cli = cli or ClaudeCli()
    rows = {r.get("sessionId"): r for r in cli.agents(include_completed=True)}
    open_by_seat = {}
    for r in state_store.read_all("conversation_dispatch"):
        if r.get("status") in store.CONVERSATION_DISPATCH_OPEN:
            open_by_seat.setdefault(r.get("target_seat_id"), []).append(r)
    entries = []
    for tid, t in sorted(teams.read().items(), key=lambda kv: kv[1].get("number", 99)):
        if t.get("kind", "team") != "team":
            continue
        try:
            entries.append(_probe(tid, t, rows, open_by_seat, now, state_store, projects))
        except Exception as exc:                          # noqa: BLE001  one team never hides the rest
            entries.append({"team": tid, "status": "unknown", "detail": str(exc)[:160]})
    snap = {"at": now, "teams": entries}
    try:
        from agent.execution import orphans
        snap["tickets"] = orphans.scan(state_store=state_store, now=now)
        wanting = orphans.needs_team(snap["tickets"])
        for e in entries:
            if e.get("status") == "free":
                work = [t["key"] for t in wanting if t.get("team") in (None, e["team"])]
                e["why"] = "idle-work-waiting" if work else "idle-nothing-to-do"
                if work:
                    e["work"] = work
    except Exception as exc:                              # noqa: BLE001  Jira down never hides the teams
        snap["tickets_error"] = str(exc)[:160]
        snap["tickets"] = (_load("snapshot", {}) or {}).get("tickets") or []
    try:
        from agent.execution import team_pool
        snap["duplicates"] = team_pool.sweep_duplicates(state_store=state_store, cli=cli,
                                                        now=now, projects=projects)
    except Exception as exc:                              # noqa: BLE001  cleanup never hides the teams
        snap["duplicates_error"] = str(exc)[:160]
    _save("snapshot", snap)
    return snap


def problems(snap=None):
    """Snapshot entries the orchestrator must hear about."""
    snap = snap if snap is not None else _load("snapshot", {})
    return [e for e in snap.get("teams") or [] if e.get("key") and e.get("status") in INBOX
            and not (e["status"] == "blocked" and e.get("dispatch"))]


def uncollected():
    seen = set(_load("collected", []))
    return [e for e in problems() if e["key"] not in seen]


def mark_collected(key):
    seen = _load("collected", [])
    if key not in seen:
        _save("collected", (seen + [key])[-500:])


HOW = {
    "silent": ("%(team)s looks busy but has not moved for %(quiet_min)s min (%(detail)s). Its work "
               "has stopped. Revive it in the SAME session: python3 -m agent.execution.liveness "
               "revive %(team)s. Do not re-dispatch the work and do not count it as progressing."),
    "untracked": ("%(team)s is working with no open dispatch: a dispatch closed while it still "
                  "works, or work Thebes never sent. Read what it is doing (claude logs "
                  "%(session)s). It is neither free nor holding a ticket until that is settled."),
    "blocked": ("%(team)s holds no dispatch and %(detail)s. Nothing will answer it. Stop that "
                "session (claude stop %(session)s) unless that call belongs to work you sent."),
    "no-session": ("%(team)s has no session, so nothing can be sent to it. Start it: bash "
                   "agent/scripts/start-teams.sh %(team)s"),
}


def orphan_items():
    """One inbox item per ticket that needs a team once automatic re-sends are used up."""
    from agent.execution import orphans
    seen = set(_load("collected", []))
    out = []
    for t in (_load("snapshot", {}).get("tickets") or []):
        key = "orphan:%s:%d" % (t["key"], orphans.rescue_state(t["key"])["n"])
        if orphans.exhausted(t) and key not in seen:
            out.append({"kind": "orphan", "ticket": t["key"], "state": t["state"], "key": key,
                        "team": t.get("team"), "waited_min": 0,
                        "why": t.get("why"), "jira": t.get("jira"),
                        "how": ("%s sits in %s with no team on it (%s) and the automatic re-sends "
                                "are used up or it is in a review column. Decide: dispatch it to a "
                                "free same-capability team yourself, route its review, or move it "
                                "back to Ready. The CEO hears none of this (D-043)."
                                % (t["key"], t.get("jira"), t.get("why")))})
    return out


def inbox_items(now=None):
    out = []
    for e in uncollected():
        fields = dict({"quiet_min": "?", "session": "?", "detail": ""}, **e)
        out.append({"kind": "liveness", "team": e["team"], "status": e["status"],
                    "detail": e.get("detail"), "ticket": e.get("ticket"), "key": e["key"],
                    "waited_min": e.get("quiet_min") or 0,
                    "how": HOW[e["status"]] % fields + " The CEO hears none of this (D-043)."})
    return out


def fact_rows(now=None):
    now = now or time.time()
    snap = _load("snapshot", {})
    if not snap:
        return ["  no liveness snapshot yet (watchdog not running?)"]
    age = int(now - snap.get("at", 0))
    rows = ["  checked %s (%dm ago)%s" % (
        time.strftime("%H:%M", time.localtime(snap.get("at", 0))), age // 60,
        " — STALE: the watchdog is not probing; run bash agent/scripts/thebes-up.sh"
        if age > STALE_SECONDS else "")]
    for e in snap.get("teams") or []:
        mark = "!" if e.get("status") in INBOX + ("stalled",) or e.get("work") else " "
        detail = e.get("detail") or ""
        if e.get("why"):
            detail = ("%s %s" % (e["why"], ",".join(e.get("work") or []))).strip()
        rows.append(" %s%-18s %-10s %s" % (mark, e.get("team"), e.get("status"), detail[:110]))
    dups = snap.get("duplicates") or []
    if dups:
        refused = [d for d in dups if d.get("result") == "refused"]
        rows.append("  retired %d duplicate sessions (D-050)%s" % (
            len(dups) - len(refused),
            "; refused: " + ", ".join("%s %s" % (d["team"], d["id"]) for d in refused)
            if refused else ""))
    return rows


def ticket_rows():
    """TICKETS WITH NO TEAM: working-column tickets nobody holds (D-047)."""
    snap = _load("snapshot", {})
    rows = []
    if snap.get("tickets_error"):
        rows.append("  Jira unreadable at the last sweep: %s" % snap["tickets_error"])
    bad = [t for t in snap.get("tickets") or [] if t.get("state") != "ok"]
    for t in bad:
        rows.append(" !%-8s %-14s %-14s %s" % (t["key"], t["state"], t.get("jira") or "", t.get("why", "")[:90]))
    if not bad and not snap.get("tickets_error"):
        rows.append("  none: every working-column ticket has a team, a review or a recent Jira move")
    return rows


def revive(team, *, state_store=store, cli=None):
    """Stop a silent team's session and resume the same session with a short explanation."""
    from agent.execution import watchdog
    from agent.execution.claude_cli import ClaudeCli
    binding = state_store.active_role_session(team)
    if not binding:
        return {"action": "revive-refused", "reason": "no-session"}
    sid = binding["session_id"]
    cli = cli or ClaudeCli()
    row = cli.find_by_sid(cli.agents(include_completed=True), sid) or {}
    last = last_activity(sid)
    quiet = int(time.time() - last) if last else 0
    if row.get("state") != "working" or quiet < SILENT_SECONDS:
        return {"action": "revive-refused", "reason": "not-silent", "state": row.get("state"),
                "quiet_min": quiet // 60}
    waiting = watchdog.pending_tool(sid)
    cli.stop(sid[:8])
    if not cli.wait_stopped(sid, 30, pid=row.get("pid")):
        return {"action": "revive-failed", "error": "session did not stop in 30s"}
    cli.bg_resume(sid, REVIVE % (team, quiet // 60, waiting[0] if waiting else "unknown"),
                  binding["stable_home"])
    from agent.execution import orders
    orders.log("revived-team", "orchestrator", sid=sid, rule="D-045",
               detail="%s silent %d min on %s" % (team, quiet // 60,
                                                   waiting[0] if waiting else "?"))
    return {"action": "revived", "team": team, "quiet_min": quiet // 60}


def maybe_sweep(*, state_store=store, now=None):
    """The watchdog's 5-minute call. Returns the new inbox problems, for the log."""
    now = now or time.time()
    if now - _load("snapshot", {}).get("at", 0) < CHECK_EVERY:
        return []
    sweep(state_store=state_store, now=now)
    return [{"action": "liveness-problem", "team": e["team"], "status": e["status"],
             "detail": e.get("detail")} for e in uncollected()]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.liveness", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sweep")
    sub.add_parser("show")
    r = sub.add_parser("revive")
    r.add_argument("team")
    ns = ap.parse_args(argv)
    if ns.cmd == "sweep":
        sweep()
        print("\n".join(fact_rows()))
    elif ns.cmd == "show":
        print("\n".join(fact_rows()))
    else:
        print(json.dumps(revive(ns.team), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
