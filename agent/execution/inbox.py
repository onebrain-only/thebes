"""The orchestrator's inbox (D-039): Claude-only Thebes, no Codex, no Listener turn.

The CEO talks to the orchestrator session directly (Remote Control). That session
is never stopped and resumed — it is a live conversation. Everything that must
reach it waits here instead, and ONE background command hands it over:

  result     a team it dispatched has reported (completed / failed / escalated)
  decision   a team asked a question the decision gate routed to the orchestrator
  alert      the watchdog flagged that a dispatch stopped or failed

    python3 -m agent.execution.inbox wait [--timeout 6900]   # run_in_background
    python3 -m agent.execution.inbox peek                     # what is waiting, no collect

`wait` blocks until at least one item is waiting, prints all of them, marks them
collected and exits; Claude Code wakes the orchestrator when a background command
exits. The orchestrator handles the items and starts `wait` again. Only the bound
orchestrator session may collect: the identity is CLAUDE_CODE_SESSION_ID.
"""
import argparse
import calendar
import json
import os
import secrets
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                  # noqa: E402

DEFAULT_TIMEOUT = 6900          # just under a 2-hour background-command limit
POLL_SECONDS = 3
# A decision outcome is routed by the gate right after it is recorded; give the
# router this long to file its request before treating the result as final.
ROUTING_GRACE_SECONDS = 30
SETTLED = tuple(store.CONVERSATION_RESULT_OUTCOMES) + ("delivery_failed",)


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def orchestrator_session(state_store=store):
    return (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")


def _age(stamp, now):
    try:
        return now - calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, TypeError):
        return None


def pending(session_id, *, state_store=store, now=None):
    """What is waiting for this orchestrator session, without collecting it."""
    now = now or time.time()
    requests = state_store.read_all("decision_request")
    routed = {r.get("origin_dispatch_id"): r for r in requests}
    out = []
    for rec in state_store.read_all("conversation_dispatch"):
        if rec.get("origin_provider") != "claude" or rec.get("origin_thread_id") != session_id:
            continue
        seen = rec.get("inbox_seen") or []
        alert = rec.get("watchdog_alert") or {}
        if alert and "alert:%s" % alert.get("kind") not in seen:
            out.append({"kind": "alert", "dispatch_id": rec["dispatch_id"],
                        "team": rec.get("target_seat_id"), "alert": alert.get("kind"),
                        "text": alert.get("text"), "_key": "alert:%s" % alert.get("kind")})
        if rec.get("status") not in SETTLED or "result" in seen:
            continue
        req = routed.get(rec["dispatch_id"])
        if rec.get("status") in ("decision_required", "blocked", "clarification_required"):
            if req is None and _age(rec.get("outcome_at"), now) < ROUTING_GRACE_SECONDS:
                continue                       # the gate is still routing it
            if req is not None and req.get("status") != "escalated":
                continue                       # decided inside Thebes; the continuation reports
        out.append({"kind": "result", "dispatch_id": rec["dispatch_id"],
                    "team": rec.get("target_seat_id"), "outcome": rec.get("status"),
                    "escalated": (req or {}).get("escalation_reason") if req else None,
                    "error": rec.get("error") if rec.get("status") == "delivery_failed" else None,
                    "result": _read(rec.get("result_ref")), "_key": "result"})
    for req in requests:
        if (req.get("status") == "open" and req.get("delivery") == "inbox"
                and req.get("owner_session_id") == session_id
                and not req.get("inbox_collected_at")):
            out.append({"kind": "decision", "decision_request_id": req["decision_request_id"],
                        "asked_by": req.get("asker_seat_id"),
                        "decision_class": req.get("decision_class"),
                        "owner_seat": req.get("owner_seat")})
    return out


def _collect_decision(item, state_store):
    """Issue a fresh capability for the request and render its envelope. The
    capability exists only in this process's output; its hash is the record's."""
    from agent.execution import decision_gate as dg
    req = state_store.read("decision_request", item["decision_request_id"])
    capability = secrets.token_urlsafe(32)
    req = state_store.update("decision_request", req["decision_request_id"], req["revision"], {
        "capability_sha256": state_store.capability_sha256(capability),
        "inbox_collected_at": state_store.now()})
    return dict(item, envelope=dg.request_envelope(req, capability, _read(req["question_ref"])))


def collect(session_id, *, state_store=store, now=None):
    """Take everything waiting. An item another waiter took first is skipped."""
    taken = []
    for item in pending(session_id, state_store=state_store, now=now):
        try:
            if item["kind"] == "decision":
                taken.append(_collect_decision(item, state_store))
                continue
            rec = state_store.read("conversation_dispatch", item["dispatch_id"])
            seen = list(rec.get("inbox_seen") or [])
            if item["_key"] in seen:
                continue
            state_store.update("conversation_dispatch", rec["dispatch_id"], rec["revision"],
                               {"inbox_seen": seen + [item["_key"]]})
            taken.append({k: v for k, v in item.items() if not k.startswith("_")})
        except state_store.StateError:
            continue                           # changed under us: the next pass decides
    return taken


def wait(timeout=DEFAULT_TIMEOUT, *, env=None, state_store=store, sleep=None):
    env = os.environ if env is None else env
    session_id = env.get("CLAUDE_CODE_SESSION_ID")
    orch = orchestrator_session(state_store)
    if not orch:
        raise Refused("orchestrator-unbound", "no orchestrator session is bound")
    if session_id != orch:
        raise Refused("not-orchestrator", "only the orchestrator session (%s) reads its inbox"
                      % orch)
    sleep = sleep or time.sleep
    deadline = time.time() + timeout
    while True:
        items = collect(session_id, state_store=state_store)
        if items:
            return {"status": "items", "count": len(items), "items": items,
                    "next": "handle every item (see agent/ORCHESTRATOR.md), then start the "
                            "inbox waiter again"}
        if time.time() >= deadline:
            return {"status": "idle", "items": [],
                    "next": "nothing arrived; start the inbox waiter again"}
        sleep(POLL_SECONDS)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.inbox", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait"); w.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    sub.add_parser("peek")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "wait":
            out = wait(ns.timeout)
        else:
            sid = os.environ.get("CLAUDE_CODE_SESSION_ID") or orchestrator_session()
            out = [{k: v for k, v in i.items() if not k.startswith("_") and k != "result"}
                   for i in pending(sid)]
    except Refused as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
