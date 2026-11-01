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
            "THEBES_ALERT %s (Thebes watchdog — work stopped; the orchestrator handles it)" % kind,
            "dispatch_id: %s" % dispatch["dispatch_id"],
            "team: %s" % dispatch.get("target_seat_id"),
            text,
            "Handle it yourself: resume, re-brief, or send it to another team. It reaches the "
            "CEO only if it is money, merging into main or sending outside the company "
            "(agent/state/registry/autonomy.json) — never a technical question or a step "
            "for him to run."])
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


WAKE_AFTER_SECONDS = 300       # something waited this long for an orchestrator that is not listening
WAKE_EVERY_SECONDS = 900       # and the orchestrator is woken at most this often
WAKE_MESSAGE = ("THEBES_WAKE: your inbox waiter was not running and %s has waited %d minutes "
                "uncollected (your last turn probably ended on an error while the Mac slept). "
                "Re-read agent/ORCHESTRATOR.md section 1, start your inbox waiter now (background), "
                "handle what it hands you. The CEO hears only money, main and outside sending.")


def pending_tool(session_id, projects=None):
    """The tool call a session is waiting on (its last tool_use without a result), read from its
    transcript, or None. This is what a `blocked` session is waiting for."""
    import glob
    root = projects or os.path.expanduser("~/.claude/projects")
    files = glob.glob(os.path.join(root, "*", "%s.jsonl" % session_id))
    if not files:
        return None
    open_calls = {}
    with open(files[0], encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
            content = msg.get("content")
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    open_calls[block["id"]] = (block.get("name"),
                                               json.dumps(block.get("input"))[:160])
                elif block.get("type") == "tool_result":
                    open_calls.pop(block.get("tool_use_id"), None)
    return list(open_calls.values())[-1] if open_calls else None


def wake_orchestrator(*, state_store=store, cli=None, now=None, waiter=None, projects=None):
    """Wake the orchestrator when work waits for it and nobody is listening (D-042).

    Only when it is IDLE (a turn in progress is never touched), no `inbox wait` process exists,
    and the oldest waiting item is older than WAKE_AFTER_SECONDS. Stop then same-SID resume with
    a short message: the only wake there is for an idle live session. At most once per
    WAKE_EVERY_SECONDS. Returns what it did, or None."""
    import time as _time
    from agent.execution import inbox
    from agent.execution.claude_cli import ClaudeCli
    from agent.state import teams
    now = now or _time.time()
    binding = state_store.active_role_session(teams.ORCHESTRATOR_ID)
    if not binding:
        return None
    sid = binding["session_id"]
    age, what = inbox.oldest_waiting(sid, state_store=state_store, now=now)
    if age < WAKE_AFTER_SECONDS or (waiter or inbox.waiter_running)():
        return None
    marker = os.path.join(state_store.RUNTIME, "orchestrator-wake.json")
    try:
        with open(marker, encoding="utf-8") as fh:
            last = json.load(fh).get("at", 0)
    except (OSError, ValueError):
        last = 0
    if now - last < WAKE_EVERY_SECONDS:
        return None
    cli = cli or ClaudeCli()
    row = cli.find_by_sid(cli.agents(), sid)
    if row is None or row.get("state") == "working":
        return None                     # not running (thebes-up's job) or mid-turn: leave it
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump({"at": now, "what": what, "waited": int(age)}, fh)
    try:
        cli.stop(sid[:8])
        if not cli.wait_stopped(sid, 30, pid=row.get("pid")):
            return {"action": "wake-failed", "error": "session did not stop in 30s"}
        cli.bg_resume(sid, WAKE_MESSAGE % (what, int(age // 60)), binding["stable_home"])
    except Exception as exc:            # noqa: BLE001
        return {"action": "wake-failed", "error": str(exc)[:200]}
    return {"action": "woke-orchestrator", "waiting": what, "minutes": int(age // 60)}


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
        if s["session_state"] == "blocked":
            # Waiting on a permission or a question, not idle: resuming cannot answer it and
            # "usage limit" would be the wrong diagnosis. Say what it waits for, once.
            waiting = pending_tool(s["target_session_id"])
            what = ("%s %s" % waiting) if waiting else "a permission or a question"
            if _alert(rec, "blocked-on-permission",
                      "%s is stuck on a permission prompt, not idle: %s. The policy hook should "
                      "have answered it (agent/scripts/policy_hook.py): withdraw the dispatch and "
                      "re-dispatch the work with the allowed path, or fix the rule in "
                      "autonomy.json. Never send the CEO to approve it (session %s). Nothing "
                      "was resumed." % (s["target"], what, s["target_session_id"][:8]),
                      state_store=state_store, launcher=launcher):
                done.append({"dispatch_id": s["dispatch_id"], "action": "alerted-blocked",
                             "waiting_for": what})
            continue
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
    woke = None
    try:
        woke = wake_orchestrator(state_store=state_store, cli=cli, now=now)
    except Exception as exc:               # noqa: BLE001
        done.append({"check": "wake", "error": str(exc)[:200]})
    if woke:
        done.append(woke)
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


def ensure_dispatcher(*, running=None, start=None):
    """B3: the Ready dispatcher died silently and KAN-495 sat in Ready. The watchdog brings
    it back (detached, its own session, so a closed terminal or a background timeout cannot
    kill it). Returns what it did, or None."""
    import subprocess
    running = running or (lambda: subprocess.run(
        ["pgrep", "-f", "agent.execution.ready_dispatcher serve"], capture_output=True).returncode == 0)
    if running():
        return None
    def _start():
        with open(os.path.join(store.RUNTIME, "ready-dispatcher.out"), "a") as out:
            subprocess.Popen([sys.executable, "-m", "agent.execution.ready_dispatcher", "serve"],
                             cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                             start_new_session=True)
    (start or _start)()
    return {"action": "restarted-ready-dispatcher"}


COMPACT_CHECK_EVERY = 300


def maybe_compact(*, state_store=store, now=None):
    """Run the session-weight policy at most every COMPACT_CHECK_EVERY seconds."""
    import time as _time
    now = now or _time.time()
    marker = os.path.join(state_store.RUNTIME, "compaction", "checked")
    try:
        if now - float(open(marker).read()) < COMPACT_CHECK_EVERY:
            return []
    except (OSError, ValueError):
        pass
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w") as fh:
        fh.write(str(now))
    from agent.execution import session_weight
    return session_weight.compact_idle(state_store=state_store, now=now)


ROTATE_AFTER_COMPACTIONS = 4   # D-044: CEO 2026-10-30, "كل يوم + بعد 4 compactions"
ROTATE_QUIET_SECONDS = 600     # never while the CEO is mid-conversation
ROTATE_MESSAGES_HOURS = 24
ORCHESTRATOR_NAME = "thebes-orchestrator"
ORCHESTRATOR_MODEL = "claude-sonnet-5-5"
HANDOFF = ("You are the Thebes orchestrator, in a FRESH session (D-044 rotation; the previous one "
           "was %s). Nothing from that conversation is carried over except what is below. Read "
           "CLAUDE.md and agent/ORCHESTRATOR.md now, start the inbox waiter as section 1 says, and "
           "then go idle. Answer the CEO only from the <thebes-facts> block every turn brings, or a "
           "command you run; what is not there you do not know. The CEO's own words from the last "
           "%dh, verbatim and oldest first, are the only record of what he asked:\n\n%s\n\n%s")


def _local_day(stamp):
    import calendar
    try:
        return time.strftime("%Y-%m-%d", time.localtime(
            calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))))
    except (TypeError, ValueError):
        return None


def rotation_due(binding, *, state_store=store, now=None):
    """Why the orchestrator should move to a fresh session, or None (D-044)."""
    sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))
    import ceo_prompt_hook
    now = now or time.time()
    count = ceo_prompt_hook.read_count(state_store)
    if (count.get("session_id") == binding["session_id"]
            and int(count.get("count") or 0) >= ROTATE_AFTER_COMPACTIONS):
        return "compactions"
    day = _local_day(binding.get("updated_at"))
    if day and day < time.strftime("%Y-%m-%d", time.localtime(now)):
        return "new-day"
    return None


def rotation_blockers(sid, *, state_store=store, now=None):
    """What makes rotating now unsafe. Empty means it is safe."""
    from agent.execution import inbox, orders
    now = now or time.time()
    out = []
    if any(not lease.get("closed_at") for lease in state_store.read_all("execution_lease")):
        out.append("execution-lease-open")
    last = (orders.messages(state_store=state_store, now=now) or [{}])[-1]
    if now - orders._epoch(last.get("at")) < ROTATE_QUIET_SECONDS:
        out.append("ceo-talking")
    # the inbox routes by origin_thread_id: a dispatch from the old session reports to it only
    if any(r.get("origin_thread_id") == sid
           and r.get("status") in state_store.CONVERSATION_DISPATCH_OPEN
           for r in state_store.read_all("conversation_dispatch")):
        out.append("dispatches-open")
    if inbox.pending(sid, state_store=state_store, now=now):
        out.append("inbox-not-empty")
    return out


def handoff_prompt(old_sid, *, state_store=store, now=None):
    from agent.execution import orders
    from agent.state import facts
    now = now or time.time()
    since = now - ROTATE_MESSAGES_HOURS * 3600
    said = orders.messages(state_store=state_store, since=since, now=now)[-30:]
    words = "\n".join("- [%s %s] %s" % (m["id"], time.strftime(
        "%m-%d %H:%M", time.localtime(orders._epoch(m["at"]))), m["text"][:1500])
        for m in said) or "- (none)"
    return HANDOFF % (old_sid[:8], ROTATE_MESSAGES_HOURS, words, facts.build(now))


def _launch(cli, prompt, home):
    """Start the fresh session and return its session id, read back by name."""
    done = cli._exec(["--bg", "--name", ORCHESTRATOR_NAME, "--model", ORCHESTRATOR_MODEL,
                      "--permission-mode", "auto", prompt], cwd=home)
    if done.returncode:
        raise RuntimeError("claude --bg exited %d: %s" % (done.returncode,
                                                          (done.stderr or "").strip()[:200]))
    return done


def rotate_orchestrator(*, state_store=store, cli=None, now=None, launch=None, sleep=None):
    """Move the orchestrator to a fresh session when it has been compacted
    ROTATE_AFTER_COMPACTIONS times or the day has changed (D-044), and only when it is
    idle, no execution lease is open, the CEO has not written for ROTATE_QUIET_SECONDS,
    and nothing open still reports to the old session. Returns what it did, or None."""
    from agent.execution.claude_cli import ClaudeCli
    from agent.state import teams
    sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))
    import ceo_prompt_hook
    now = now or time.time()
    binding = state_store.active_role_session(teams.ORCHESTRATOR_ID)
    if not binding:
        return None
    old = binding["session_id"]
    why = rotation_due(binding, state_store=state_store, now=now)
    if not why:
        return None
    blocked = rotation_blockers(old, state_store=state_store, now=now)
    cli = cli or ClaudeCli()
    before = cli.agents()
    row = cli.find_by_sid(before, old)
    if row is None:
        blocked.append("not-running")            # thebes-up resumes it; rotation does not start one
    elif row.get("state") == "working":
        blocked.append("mid-turn")
    if blocked:
        return {"action": "rotation-waiting", "reason": why, "blocked_by": blocked}
    known = {r.get("sessionId") for r in before}
    (launch or _launch)(cli, handoff_prompt(old, state_store=state_store, now=now),
                        binding["stable_home"])
    new = None
    for _ in range(30):
        new = next((r["sessionId"] for r in cli.agents() if r.get("name") == ORCHESTRATOR_NAME
                    and r.get("sessionId") not in known), None)
        if new:
            break
        (sleep or time.sleep)(2)
    if not new:
        return {"action": "rotation-failed", "reason": why,
                "error": "the new session did not appear in claude agents"}
    state_store.bind_role_session(teams.ORCHESTRATOR_ID, "claude", new, binding["stable_home"],
                                  "orchestrator", session_name=ORCHESTRATOR_NAME,
                                  expected_revision=binding["revision"])
    os.makedirs(os.path.dirname(ceo_prompt_hook.count_path(state_store)), exist_ok=True)
    with open(ceo_prompt_hook.count_path(state_store), "w", encoding="utf-8") as fh:
        json.dump({"session_id": new, "count": 0, "since": state_store.now()}, fh)
    try:
        cli.stop(old[:8])
    except Exception as exc:                      # noqa: BLE001
        return {"action": "rotated-orchestrator", "reason": why, "from": old, "to": new,
                "warning": "old session did not stop: %s" % str(exc)[:200]}
    from agent.execution import orders
    orders.log("rotated-orchestrator", "watchdog", rule="D-044", sid=new,
               detail="%s -> %s (%s)" % (old[:8], new[:8], why), state_store=state_store, now=now)
    return {"action": "rotated-orchestrator", "reason": why, "from": old, "to": new}


ROTATE_CHECK_EVERY = 300


def maybe_rotate(*, state_store=store, now=None):
    now = now or time.time()
    marker = os.path.join(state_store.RUNTIME, "compaction", "rotation-checked")
    try:
        if now - float(open(marker).read()) < ROTATE_CHECK_EVERY:
            return []
    except (OSError, ValueError):
        pass
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    with open(marker, "w") as fh:
        fh.write(str(now))
    done = rotate_orchestrator(state_store=state_store, now=now)
    return [done] if done else []


def serve(interval=INTERVAL):
    log = os.path.join(store.RUNTIME, "watchdog.log")
    while True:
        try:
            done = tick()
            done = list(done or []) + maybe_compact()
            try:
                from agent.execution import liveness
                done += liveness.maybe_sweep()
            except Exception as exc:                       # noqa: BLE001
                done.append({"action": "liveness-error", "error": str(exc)[:200]})
            try:
                done += maybe_rotate()
            except Exception as exc:                       # noqa: BLE001
                done.append({"action": "rotation-error", "error": str(exc)[:200]})
            try:
                from agent.execution import review_queue
                done += review_queue.notify_stalled()
            except Exception:                              # noqa: BLE001
                pass
            restarted = ensure_dispatcher()
            if restarted:
                done = list(done or []) + [restarted]
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
