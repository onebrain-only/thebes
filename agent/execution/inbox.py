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
# A completed dispatch with checks is reported once it is verified. If verification never
# ran (the detached process failed), the plain result still reaches the orchestrator after this.
VERIFY_GRACE_SECONDS = 1800
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


def oldest_waiting(session_id, *, state_store=store, now=None):
    """(seconds, what) for the OLDEST item waiting uncollected for this orchestrator, or
    (0, None). The watchdog uses it to tell 'nothing to do' from 'nobody is listening'."""
    now = now or time.time()
    best = (0, None)
    stamps = {}
    for rec in state_store.read_all("conversation_dispatch"):
        stamps[rec["dispatch_id"]] = rec.get("outcome_at") or (rec.get("watchdog_alert") or {}).get("at")
    for item in pending(session_id, state_store=state_store, now=now):
        kind = item["kind"]
        if kind == "priority":
            stamp = (state_store.read("priority_request", item["priority_request_id"]) or {}).get(
                "created_at")
        elif kind == "decision":
            stamp = (state_store.read("decision_request", item["decision_request_id"]) or {}).get(
                "created_at")
        else:
            stamp = stamps.get(item.get("dispatch_id"))
        age = _age(stamp, now) if stamp else 0
        if age > best[0]:
            best = (age, "%s %s" % (kind, item.get("priority_request_id")
                                    or item.get("decision_request_id")
                                    or item.get("dispatch_id")))
    return best


def waiter_running():
    """Is an `inbox wait` process alive on this machine?"""
    import subprocess
    done = subprocess.run(["pgrep", "-f", "agent.execution.inbox wait"], capture_output=True,
                          text=True)
    return done.returncode == 0 and bool(done.stdout.strip())


def _verification_items(rec, seen, now):
    """The verified / exhausted / needs-a-reviewer outcome of a ROOT dispatch (D-041)."""
    ver = rec.get("verification")
    if rec.get("root_dispatch_id") or not ver:
        return []
    verdict = ver.get("verdict")
    base = {"dispatch_id": rec["dispatch_id"], "team": rec.get("target_seat_id"),
            "ticket": rec.get("jira_key"), "branch": ver.get("branch"), "sha": ver.get("sha"),
            "checks": {i: {"status": r.get("status"), "what": r.get("what"),
                           "detail": r.get("detail")}
                       for i, r in sorted((ver.get("results") or {}).items())}}
    if verdict in ("pass", "exhausted") and "verified:%s" % verdict not in seen:
        return [dict(base, kind="verification", verdict=verdict,
                     jira=(rec.get("jira_sync") or {}).get("verified")
                     or (rec.get("jira_sync") or {}).get("exhausted"),
                     report=(_read(rec.get("result_ref")) or "")[:3000],
                     _key="verified:%s" % verdict)]
    if verdict == "needs_judge" and "judge:%s" % ver.get("cycle") not in seen:
        pend = [dict(r, id=i) for i, r in sorted((ver.get("results") or {}).items())
                if r.get("status") == "pending-judge"]
        return [dict(base, kind="judge", cycle=ver.get("cycle"),
                     pending=[{"id": r["id"], "what": r.get("what"),
                               "team_evidence": r.get("detail")} for r in pend],
                     how=("run ONE reviewer (cxo for design fidelity, qa for behaviour) as a "
                          "subagent over exactly these checks and their named evidence. One "
                          "pass, a PASS/FAIL line per check, no rework and no new scenarios. "
                          "Then: python3 -m agent.execution.verify verdict %s --pass C1 "
                          "--fail C2:\"reason\"" % rec["dispatch_id"]),
                     _key="judge:%s" % ver.get("cycle"))]
    return []


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
        out.extend(_verification_items(rec, seen, now))
        if rec.get("status") not in SETTLED or "result" in seen:
            continue
        if (rec.get("outcome") == "completed" and rec.get("checks")
                and not rec.get("verified_at")
                and _age(rec.get("outcome_at"), now) < VERIFY_GRACE_SECONDS):
            continue                           # reported through the verification item (D-041)
        if rec.get("outcome") == "completed" and rec.get("checks") and rec.get("verified_at"):
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
    for pr in state_store.read_all("priority_request"):
        if pr.get("status") == "open":
            briefs = [r["key"] for r in pr["reasons"] if r.get("kind") == "needs-brief"]
            board = [r for r in pr["reasons"] if r.get("kind") != "needs-brief"]
            out.append({"kind": "priority", "priority_request_id": pr["priority_request_id"],
                        "needs_brief": briefs, "board": board,
                        "how": ("D-042, run in the background. needs_brief: run the PO of each "
                                "ticket's project (po = app, po-2 = design system) to write "
                                "its brief and remove the needs-brief and brief-requested "
                                "labels. board: run the PM to re-prioritise the Backlog "
                                "(including returned work and new sub-tasks) and move what the "
                                "free teams can take into Ready, in rank order, with an "
                                "Original estimate and a domain component on each.")})
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
            if item["kind"] == "priority":
                pr = state_store.read("priority_request", item["priority_request_id"])
                state_store.update("priority_request", pr["priority_request_id"],
                                   pr["revision"], {"status": "collected",
                                                    "collected_at": state_store.now()})
                taken.append(item)
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


CODE_FILES = ("agent/execution/inbox.py", "agent/execution/ready_dispatcher.py",
              "agent/execution/verify.py", "agent/execution/conversation_dispatch.py",
              "agent/state/store.py")


def _code_stamp():
    out = []
    for rel in CODE_FILES:
        try:
            out.append(os.path.getmtime(os.path.join(ROOT, rel)))
        except OSError:
            out.append(None)
    return tuple(out)


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
    code_stamp = _code_stamp()
    while True:
        if _code_stamp() != code_stamp:
            # Live 2026-10-09: a waiter started before the `priority` item existed never
            # saw one, and the board waited. A changed Thebes collects nothing stale.
            return {"status": "restart", "items": [],
                    "next": "Thebes code changed; start the inbox waiter again now"}
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
