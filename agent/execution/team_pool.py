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
"""
import argparse
import json
import os
import sys

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
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "reserve":
            out = reserve(ns.seat_id, ns.dispatch)
        elif ns.cmd == "release":
            out = release(ns.seat_id, ns.dispatch)
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
