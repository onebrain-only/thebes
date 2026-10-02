"""The watchdog: nothing stops silently (CEO, 2026-10-02).

"I want the conversation to be active, not passive: if they stop, they tell me." One
background loop, every INTERVAL seconds, looks for work that has stopped and either
recovers it or raises a flag in the conversation that asked for it:

  stalled dispatch   (session no longer working, result not submitted —
                      usage limit, crash, lost connection)
                     → resume the SAME session once; if it is still stalled after
                       that, or the resume fails → ALERT
  failed delivery    (Thebes could not hand the work to the team) → ALERT
  CEO escalation     (decision_request escalated to the CEO) → ALERT, so a phone
                       conversation in inline mode hears it too

An ALERT is (a) a turn pushed into the origin Codex conversation when Thebes can
write into it, and (b) a `watchdog_alert` field on the dispatch, which
`conversation_dispatch wait` reports immediately — so a phone conversation waiting
inline hears it in the same second instead of waiting out its timeout. Each alert is
sent once (its event id derives from the dispatch and the alert kind).

    python3 -m agent.execution.watchdog tick      # one pass, prints what it did
    python3 -m agent.execution.watchdog serve     # loop forever (start once, in background)
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                      # noqa: E402

INTERVAL = 60
# Only events this recent are alerted. The first live pass (2026-10-02) alerted on a
# day of historical test failures and escalations and flooded the CEO's conversations;
# a watchdog reports what is happening now, not the archive.
ALERT_WINDOW_SECONDS = 30 * 60


def _recent(rec, now):
    import calendar
    stamp = rec.get("updated_at") or rec.get("created_at")
    try:
        return now - calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")) <= ALERT_WINDOW_SECONDS
    except (TypeError, ValueError):
        return False


def _alert(dispatch, kind, text, *, state_store=store, launcher=None):
    """Raise one alert for one dispatch, once. Returns True if newly raised."""
    from agent.execution import codex_runtime as cr
    if (dispatch.get("watchdog_alert") or {}).get("kind") == kind:
        return False
    try:
        state_store.update("conversation_dispatch", dispatch["dispatch_id"], dispatch["revision"],
                           {"watchdog_alert": {"kind": kind, "text": text,
                                               "at": state_store.now()}})
    except state_store.StateError:
        return False                       # changed under us; the next tick decides again
    conv = state_store.read("codex_conversation", dispatch.get("origin_thread_id") or "none") or {}
    if conv.get("status") == "active" and conv.get("reply_mode") != "inline":
        body = "\n".join([
            "THEBES_ALERT %s (Thebes watchdog — work stopped; the CEO must hear this)" % kind,
            "dispatch_id: %s" % dispatch["dispatch_id"],
            "team: %s" % dispatch.get("target_seat_id"),
            text,
            "Tell the CEO in one or two plain sentences what stopped, what Thebes already "
            "tried, and the single thing that would unblock it. Do not ask them to check "
            "anything themselves."])
        eid = "cevt-alert-%s-%s" % (dispatch["dispatch_id"][len("cdispatch-"):], kind)
        try:
            ev, created = cr.enqueue(dispatch["origin_thread_id"], "alert", body,
                                     dispatch_id=dispatch["dispatch_id"], event_id=eid,
                                     state_store=state_store)
            if created:
                (launcher or cr._detach_drain)(dispatch["origin_thread_id"])
        except Exception:
            pass                           # the field above still reaches an inline `wait`
    return True


def tick(*, state_store=store, cli=None, launcher=None, resume=None, now=None):
    """One pass. Returns a list of what it did, for the log."""
    from agent.execution import conversation_dispatch as cd
    done = []
    try:
        stalled = cd.stalled(state_store=state_store, cli=cli, now=now)
    except Exception as exc:               # claude CLI unavailable: say so, keep going
        stalled = []
        done.append({"check": "stalled", "error": str(exc)[:200]})
    for s in stalled:
        rec = state_store.read("conversation_dispatch", s["dispatch_id"])
        attempts = sum(1 for d in state_store.read_all("session_delivery")
                       if str(d.get("delivery_id") or "").startswith(s["dispatch_id"] + "-resume"))
        if attempts == 0:
            try:
                out = (resume or cd.resume_stalled)(s["dispatch_id"], state_store=state_store)
            except Exception as exc:
                out = {"status": "resume-failed", "error": str(exc)[:200]}
            done.append({"dispatch_id": s["dispatch_id"], "action": "resumed", "result": out})
            if out.get("status") != "resumed":
                _alert(rec, "stalled-resume-failed",
                       "%s stopped working on this (session state %r, open %d min) and the "
                       "automatic resume failed: %s" % (s["target"], s["session_state"],
                                                        s["open_minutes"], out.get("error")),
                       state_store=state_store, launcher=launcher)
        elif _alert(rec, "stalled",
                    "%s stopped working on this again after an automatic resume (session state "
                    "%r, open %d min). Most likely its Claude usage limit; it will need to be "
                    "resumed once the limit resets, or the request sent to another team."
                    % (s["target"], s["session_state"], s["open_minutes"]),
                    state_store=state_store, launcher=launcher):
            done.append({"dispatch_id": s["dispatch_id"], "action": "alerted-stalled"})
    clock = now or time.time()
    for rec in state_store.read_all("conversation_dispatch"):
        if rec.get("status") == "delivery_failed" and _recent(rec, clock) and _alert(
                rec, "delivery-failed",
                "Thebes could not hand this request to %s: %s"
                % (rec.get("target_seat_id"), (rec.get("error") or "")[:300]),
                state_store=state_store, launcher=launcher):
            done.append({"dispatch_id": rec["dispatch_id"], "action": "alerted-delivery-failed"})
    for req in state_store.read_all("decision_request"):
        if req.get("status") != "escalated" or req.get("watchdog_alerted"):
            continue
        if not _recent(req, clock):
            continue
        origin = state_store.read("conversation_dispatch", req.get("origin_dispatch_id") or "")
        if origin and _alert(origin, "needs-ceo",
                             "A decision was escalated to the CEO (%s). Reason: %s."
                             % (req["decision_request_id"], req.get("escalation_reason")),
                             state_store=state_store, launcher=launcher):
            done.append({"decision_request_id": req["decision_request_id"],
                         "action": "alerted-needs-ceo"})
        try:
            state_store.update("decision_request", req["decision_request_id"], req["revision"],
                               {"watchdog_alerted": True})
        except state_store.StateError:
            pass
    return done


def serve(interval=INTERVAL):
    log = os.path.join(store.RUNTIME, "watchdog.log")
    while True:
        try:
            done = tick()
            if done:
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"at": store.now(), "done": done}, default=str) + "\n")
        except Exception as exc:                          # the watchdog never dies
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": store.now(), "error": str(exc)[:300]}) + "\n")
        time.sleep(interval)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.watchdog", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tick")
    s = sub.add_parser("serve"); s.add_argument("--interval", type=int, default=INTERVAL)
    ns = ap.parse_args(argv)
    if ns.cmd == "tick":
        print(json.dumps(tick(), indent=2, default=str))
        return 0
    return serve(ns.interval)


if __name__ == "__main__":
    sys.exit(main())
