"""The shared seat pool, as a team island sees it.

A team is one persistent Claude session. Inside it, seats run as subagents.
Seats are shared across teams but exclusive in time: before a team spawns a
seat it RESERVES it for the dispatch it is working, and Thebes refuses if
another team holds that seat — naming the holder, so the team picks a free
seat of the same capability instead of waiting. Every reservation a dispatch
holds is released when the team submits its result (or the dispatch is
withdrawn); an explicit release exists for a seat finished early.

Identity is never typed: the team is resolved from this session's own
CLAUDE_CODE_SESSION_ID through its role_session binding, so a team cannot
reserve on another team's behalf, and a seat session cannot reserve at all.

    python3 -m agent.execution.team_pool reserve <seat> --dispatch <cdispatch-id>
    python3 -m agent.execution.team_pool release <seat> --dispatch <cdispatch-id>
    python3 -m agent.execution.team_pool free [--capability frontend]
    python3 -m agent.execution.team_pool status
    python3 -m agent.execution.team_pool sweep-duplicates [--dry-run] [team]
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import roster, store, teams                       # noqa: E402


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def team_for_session(session_id, state_store=store):
    """The team whose ACTIVE binding is this session, or a refusal."""
    if not session_id:
        raise Refused("team-identity-missing", "CLAUDE_CODE_SESSION_ID is the only identity")
    for rec in state_store.read_all("role_session"):
        if (rec.get("status") == "active" and rec.get("session_id") == session_id
                and teams.is_team(rec.get("seat_id"))):
            return rec["seat_id"]
    raise Refused("not-a-team-session", "session %s is not bound to a team" % session_id)


def open_dispatches_for(session_id, state_store=store):
    return [r["dispatch_id"] for r in state_store.read_all("conversation_dispatch")
            if r.get("target_session_id") == session_id
            and r.get("status") in store.CONVERSATION_DISPATCH_OPEN]


def orchestrator_binding(state_store=store):
    """The orchestrator's ACTIVE binding with busy state, or None (D-034)."""
    binding = state_store.active_role_session(teams.ORCHESTRATOR_ID)
    if binding is None or binding.get("provider") != "claude":
        return None
    busy = open_dispatches_for(binding["session_id"], state_store)
    return {"team_id": teams.ORCHESTRATOR_ID, "session_id": binding["session_id"],
            "stable_home": binding.get("stable_home"), "busy": bool(busy),
            "open_dispatches": busy}


def team_bindings(state_store=store):
    """Every DELIVERY team's binding plus whether it has an open dispatch.
    The orchestrator is not a delivery team; see orchestrator_binding()."""
    out = []
    for team_id, entry in sorted(teams.delivery_teams().items(), key=lambda kv: kv[1]["number"]):
        binding = state_store.active_role_session(team_id)
        busy = []
        if binding:
            busy = [r["dispatch_id"] for r in state_store.read_all("conversation_dispatch")
                    if r.get("target_session_id") == binding["session_id"]
                    and r.get("status") in store.CONVERSATION_DISPATCH_OPEN]
        out.append({"team_id": team_id, "number": entry["number"],
                    "display_name": entry["display_name"],
                    "session_id": binding["session_id"] if binding else None,
                    "busy": bool(busy), "open_dispatches": busy})
    return out


def free_teams(state_store=store):
    return [t for t in team_bindings(state_store) if t["session_id"] and not t["busy"]]


def free_seats(capability=None, state_store=store):
    """Seats with no ACTIVE reservation, optionally of one capability."""
    held = {r["seat_id"] for r in state_store.read_all("seat_reservation")
            if r.get("status") == "active"}
    out = []
    for seat_id, entry in sorted(roster.read().items()):
        cap = (entry or {}).get("capability") or (entry or {}).get("role")
        if capability and cap != capability:
            continue
        if seat_id not in held:
            out.append({"seat_id": seat_id, "capability": cap})
    return out


def reserve(seat_id, dispatch_id, *, env=None, state_store=store):
    env = os.environ if env is None else env
    team_id = team_for_session(env.get("CLAUDE_CODE_SESSION_ID"), state_store)
    try:
        rec, created = state_store.reserve_seat(seat_id, team_id, dispatch_id)
    except state_store.StateError as exc:
        code = str(exc).split(":", 1)[0]
        detail = {"code": code, "error": str(exc)}
        if code == "seat-held":
            cap = (roster.read().get(seat_id) or {}).get("capability") or \
                  (roster.read().get(seat_id) or {}).get("role")
            detail["free_alternatives"] = [s["seat_id"] for s in free_seats(cap, state_store)]
        raise Refused(code, json.dumps(detail, sort_keys=True))
    return {"status": "reserved" if created else "already-reserved", "seat_id": seat_id,
            "team_id": team_id, "dispatch_id": dispatch_id,
            "seat_reservation_id": rec["seat_reservation_id"]}


def release(seat_id, dispatch_id, *, env=None, state_store=store):
    env = os.environ if env is None else env
    team_id = team_for_session(env.get("CLAUDE_CODE_SESSION_ID"), state_store)
    held = state_store.active_seat_reservation(seat_id)
    if held is None:
        return {"status": "not-held", "seat_id": seat_id}
    if held.get("team_id") != team_id or held.get("dispatch_id") != dispatch_id:
        raise Refused("not-your-reservation", "%s is held by team %s for %s"
                      % (seat_id, held.get("team_id"), held.get("dispatch_id")))
    released = state_store.release_seat_reservations(dispatch_id, "team-released", seat_id)
    return {"status": "released" if released else "not-held", "seat_id": seat_id,
            "team_id": team_id, "dispatch_id": dispatch_id}


def direct_seats(state_store=store):
    """Seats with their OWN bound session, for direct CEO orders (AGENTS.md:
    'move KAN-348 to Ready' goes to po's session, not a team or the orchestrator)."""
    out = []
    for rec in state_store.read_all("role_session"):
        if (rec.get("status") == "active" and rec.get("provider") == "claude"
                and not teams.is_team(rec.get("seat_id"))):
            out.append({"seat_id": rec["seat_id"], "session_id": rec["session_id"],
                        "busy": bool(open_dispatches_for(rec["session_id"], state_store))})
    return sorted(out, key=lambda r: r["seat_id"])


# ---------------------------------------------------------------- duplicates (D-050)
#
# Restarts, rotations and resume copies leave old sessions under the same
# `thebes-team-<id>` name. Only the BOUND session ever receives work; the rest are
# leftovers. Live ones are stopped (reversible: --resume brings them back); exited
# ones older than RM_AFTER are removed after their transcript is archived.

SESSION_PREFIXES = ("thebes-team-", "thebes-orchestrator", "conversation-dispatch-")
LIVE_STATES = ("working", "blocked", "idle", "busy")
RM_AFTER = 6 * 3600
ARCHIVE = os.path.join(ROOT, "agent", "state", "runtime", "session-archive")


def _protected_sids(state_store):
    """Every sid that is bound to a seat or that an open dispatch targets or reports to."""
    out = {r.get("session_id") for r in state_store.read_all("role_session")
           if r.get("status") == "active"}
    for r in state_store.read_all("conversation_dispatch"):
        if r.get("status") in store.CONVERSATION_DISPATCH_OPEN:
            out.add(r.get("target_session_id"))
            origin = r.get("origin_thread_id") or ""
            if origin.startswith("claude:"):
                out.add(origin.split(":", 1)[1])
    out.discard(None)
    return out


def _team_of(name):
    if name == "thebes-orchestrator":
        return teams.ORCHESTRATOR_ID
    if name.startswith("conversation-dispatch-"):
        return "dispatch-copy"                            # a resume copy; never a bound session
    return name[len("thebes-team-"):]


def duplicates(rows, *, state_store=store, team=None, now=None):
    """Same-named thebes sessions that are not the bound one and nothing depends on."""
    now = now or time.time()
    protected = _protected_sids(state_store)
    out = []
    for r in rows:
        name, sid = r.get("name") or "", r.get("sessionId")
        if not sid or not name.startswith(SESSION_PREFIXES) or sid in protected:
            continue
        tid = _team_of(name)
        if team and tid != team:
            continue
        started = (r.get("startedAt") or 0) / 1000.0
        live = r.get("state") in LIVE_STATES
        if not live and now - started < RM_AFTER:
            continue
        out.append({"team": tid, "session_id": sid, "id": r.get("id") or sid[:8],
                    "state": r.get("state"), "action": "stop" if live else "rm"})
    return out


def _archive(sid, projects=None):
    root = projects or os.path.expanduser("~/.claude/projects")
    os.makedirs(ARCHIVE, exist_ok=True)
    copied = 0
    for f in glob.glob(os.path.join(root, "*", "%s.jsonl" % sid)):
        shutil.copy2(f, os.path.join(ARCHIVE, os.path.basename(f)))
        copied += 1
    return copied


def sweep_duplicates(*, state_store=store, cli=None, team=None, dry_run=False, now=None,
                     projects=None):
    from agent.execution.claude_cli import ClaudeCli, ClaudeCliError
    from agent.execution import orders
    cli = cli or ClaudeCli()
    found = duplicates(cli.agents(include_completed=True), state_store=state_store,
                       team=team, now=now)
    if dry_run:
        return found
    for d in found:
        try:
            if d["action"] == "stop":
                cli.stop(d["id"])
            else:
                _archive(d["session_id"], projects)
                cli.rm(d["id"])
            d["result"] = "done"
        except (ClaudeCliError, OSError) as exc:
            d["result"] = "refused"
            d["error"] = str(exc)[:200]
        try:
            orders.log("retired-duplicate-session", "orchestrator", sid=d["session_id"], state_store=state_store,
                       rule="D-050", detail="%s %s %s: %s" % (d["team"], d["action"], d["state"],
                                                              d["result"]))
        except Exception:                                 # noqa: BLE001  the log never blocks cleanup
            pass
    return found


def status(state_store=store):
    return {"teams": team_bindings(state_store),
            "orchestrator": orchestrator_binding(state_store),
            "direct_seats": direct_seats(state_store),
            "reservations": [r for r in state_store.read_all("seat_reservation")
                             if r.get("status") == "active"]}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.team_pool", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reserve"); r.add_argument("seat_id"); r.add_argument("--dispatch", required=True)
    l = sub.add_parser("release"); l.add_argument("seat_id"); l.add_argument("--dispatch", required=True)
    f = sub.add_parser("free"); f.add_argument("--capability", default=None)
    sub.add_parser("status")
    d = sub.add_parser("sweep-duplicates")
    d.add_argument("team", nargs="?", default=None)
    d.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "reserve":
            out = reserve(ns.seat_id, ns.dispatch)
        elif ns.cmd == "release":
            out = release(ns.seat_id, ns.dispatch)
        elif ns.cmd == "sweep-duplicates":
            out = sweep_duplicates(team=ns.team, dry_run=ns.dry_run)
        elif ns.cmd == "free":
            out = {"free_seats": free_seats(ns.capability), "free_teams": free_teams()}
        else:
            out = status()
    except Refused as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
