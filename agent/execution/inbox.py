"""The orchestrator's inbox (D-039): Claude-only Thebes, no Codex, no Listener turn.

The CEO talks to the orchestrator session directly (Remote Control). That session
is never stopped and resumed — it is a live conversation. Everything that must
reach it waits here instead, and ONE background command hands it over:

  result     a team it dispatched has reported (completed / failed / escalated)
  decision   a team asked a question the decision gate routed to the orchestrator
  alert      the watchdog flagged that a dispatch stopped or failed

    python3 -m agent.execution.inbox wait [--timeout 6900]   # run_in_background
    python3 -m agent.execution.inbox peek                     # what is waiting, no collect

    python3 -m agent.execution.inbox take                     # collect now (foreground)

CEO 2026-11-11 ("no wake-ups at all"): the zero-token loop `agent.execution.inbox_push`
watches this inbox and drops one short message into the orchestrator's conversation when
items wait, the way the CEO's own messages arrive. The orchestrator runs `take` and handles
what it prints; it runs no waiter. While the pusher runs, `wait` refuses ("pushed").

`wait` (the old way) blocks until at least one item is waiting, prints all of them, marks
them collected and exits; Claude Code wakes the orchestrator when a background command
exits. Only the bound orchestrator session may collect: the identity is
CLAUDE_CODE_SESSION_ID.
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
# CEO 2026-11-11: every wake used to end with a line to him ("restarting the waiter", "I'm
# back"). A wake that brings him nothing new ends with the single mark · (an empty turn draws a
# forced "no visible output" call from Claude Code).
# CEO 2026-11-11: 40 messages in 30 minutes, most of them "KAN-89x passed review" for tickets
# that wait on their branch for the patch (TH-075). A pass or a hold needs nothing from the
# orchestrator: integration and Jira follow by themselves. These are marked seen and never wake it.
QUIET_VERDICTS = ("pass", "held")
QUIET_ALERTS = ("review-held",)
# CEO 2026-11-11 ("it consumes my tokens"): every wake re-reads the orchestrator's whole context
# four to eight times. Items that land a minute apart (a result, then its decision, then its
# verification) used to cost one wake each. After the first item the waiter keeps collecting
# until nothing new has come for BATCH_QUIET_POLLS polls, at most BATCH_MAX_POLLS.
BATCH_QUIET_POLLS = 30          # 90 s of quiet
BATCH_MAX_POLLS = 100           # 5 min at most
SILENT = " Start the waiter and end the turn with the single character · and nothing else."
SPEAK_ONLY_BY_NOTICE = (" Speak to the CEO only after ceo_notice prints SEND (ORCHESTRATOR.md "
                        "5a); otherwise end the turn with the single character · and nothing else.")
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
        elif kind == "review_stalled":
            if item["waited_min"] * 60 > best[0]:
                best = (item["waited_min"] * 60, "review_stalled %s" % ",".join(item["tickets"]))
            continue
        elif kind == "reviewer_question":
            from agent.execution import review_queue
            asked = next((q["asked_at"] for q in review_queue.questions()
                          if q["qid"] == item["question_id"]), now)
            if now - asked > best[0]:
                best = (now - asked, "reviewer_question %s" % item["question_id"])
            continue
        elif kind == "liveness":
            if item["waited_min"] * 60 > best[0]:
                best = (item["waited_min"] * 60, "liveness %s %s" % (item["team"], item["status"]))
            continue
        elif kind == "ceo_retired":
            stamp = item["at"]
        elif kind == "orphan":
            continue                       # raised once per rescue count; not a stalled listener
        elif kind == "not_live":
            continue                       # flagged by the dispatcher sweep; not a stalled listener

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
    if verdict in ("pass", "exhausted", "held") and "verified:%s" % verdict not in seen:
        return [dict(base, kind="verification", verdict=verdict, _quiet=verdict in QUIET_VERDICTS,
                     jira=(rec.get("jira_sync") or {}).get("verified")
                     or (rec.get("jira_sync") or {}).get("exhausted"),
                     report=(_read(rec.get("result_ref")) or "")[:3000],
                     _key="verified:%s" % verdict)]
    if verdict == "needs_judge" and "judge:%s" % ver.get("cycle") not in seen:
        from agent.execution import conversation_dispatch as cd
        if cd.is_product(rec):
            return []           # D-043: product work is reviewed by Codex, never by the orchestrator
        pend = [dict(r, id=i) for i, r in sorted((ver.get("results") or {}).items())
                if r.get("status") == "pending-judge"]
        return [dict(base, kind="judge", cycle=ver.get("cycle"),
                     pending=[{"id": r["id"], "what": r.get("what"),
                               "team_evidence": r.get("detail")} for r in pend],
                     how=("a text/report/answer deliverable (ask or ops lane): run ONE reviewer as a "
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
                        "_quiet": alert.get("kind") in QUIET_ALERTS,
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
            if req is not None and req.get("status") not in ("escalated", "stuck"):
                continue                       # decided inside Thebes; the continuation reports
        asked = rec.get("status") in ("decision_required", "blocked", "clarification_required")
        out.append({"kind": "result", "dispatch_id": rec["dispatch_id"],
                    "ticket": rec.get("jira_key"),
                    "how": (("The team asked a question and is idle. YOU answer it (CEO 2026-10-14: "
                             "decisions are the orchestrator's; only money, main and sending "
                             "outside the company are the CEO's — constitution 2026-10-27). Answer with: "
                             "python3 -m agent.execution.ticket_ruling %s --text-file <file> "
                             "(it adds your ruling to the ticket and sends it back to a team)."
                             % rec.get("jira_key")) if asked and rec.get("jira_key") else None),
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
                                "Original estimate and a domain component on each. D-049: "
                                "ready-below-target: cut Epics the CEO already approved into "
                                "tickets of one screen or one function plus its test (30-50 "
                                "minutes) until Ready holds 10 startable; never new scope. "
                                "serial-chain: on each waiting ticket keep a Blocks link only "
                                "for a real code or data dependency (same Epic is not one) and "
                                "remove the rest; split by file surfaces so one Epic runs on "
                                "several teams at once. too-big: an Original estimate over an hour; "
                                "real team time is a median 25 minutes, so cut it with epic-cut.")})
    try:
        from agent.execution import review_queue
        late = review_queue.stalled_unalerted(state_store, now)
        if late:
            out.append({"kind": "review_stalled", "tickets": [i["ticket"] for i in late],
                        "items": [i["item_id"] for i in late], "channel": review_queue.get_channel(),
                        "waited_min": max(i["age_min"] for i in late),
                        "wake_prompt": review_queue.wake_prompt([i["ticket"] for i in late]),
                        "how": ("Review of %s has waited %d+ minutes and nobody holds it (channel %s). "
                                "YOU fix it; never the CEO (constitution 2026-10-27). Claude "
                                "channel: the watchdog already re-woke Edfu — if Edfu has no "
                                "session, start it (bash agent/scripts/start-teams.sh edfu). Codex "
                                "channel: a Desktop conversation cannot be woken from outside, so "
                                "switch review to Claude: python3 -m agent.execution.review_queue "
                                "channel claude --by \"constitution 2026-10-27: CEO out of the "
                                "cycle; Codex reviewer stalled\". Say nothing to the CEO."
                                % (", ".join(i["ticket"] for i in late),
                                   max(i["age_min"] for i in late),
                                   review_queue.get_channel()))})
        for r in review_queue.not_live_for_inbox():
            out.append({"kind": "not_live", "ticket": r["ticket"], "sha": r.get("sha"),
                        "branch": r.get("branch"), "on_alpha": bool(r.get("on_alpha_at")),
                        "how": (("%s passed review and its commit %s is on staging, but "
                                 "staging.dabbler.pro has not served it for 15+ minutes. Dispatch ONE "
                                 "ops item to Memphis: check the Cloudflare Pages build for staging "
                                 "and redeploy it. Never the CEO (D-043).")
                                if r.get("on_alpha_at") else
                                ("%s passed review 24+ hours ago and %s is still not on staging. "
                                 "Check `python3 -m agent.execution.integrate` state for it and "
                                 "have Memphis integrate the branch. Never the CEO (D-043)."))
                               % (r["ticket"], (r.get("sha") or "?")[:12])})
        for q in review_queue.questions_for_inbox():
            out.append({"kind": "reviewer_question", "question_id": q["qid"], "ticket": q["ticket"],
                        "question": q["question"],
                        "how": ("The Codex reviewer is stuck on %s and is WAITING. Answer from the "
                                "ticket, the PM ledger and the board; for scope or acceptance run "
                                "that ticket's PO (po = app, po-2 = design system) in the "
                                "background; for a design-standard ruling dispatch ONE question to "
                                "Memphis. Then: python3 -m agent.execution.review_queue answer %s "
                                "--text \"<the answer>\". Answer within 15 minutes even if the "
                                "answer is 'undecided: verify X only and skip Y'. You answer; you "
                                "never tell the reviewer to pass something." % (q["ticket"], q["qid"]))})
    except Exception:                                       # noqa: BLE001  never blocks the inbox
        pass
    try:
        from agent.execution import liveness
        out.extend(liveness.inbox_items(now))
        out.extend(liveness.orphan_items())
        from agent.execution import orders
        seen = set(liveness._load("collected", []))
        for m in orders.messages(state_store=state_store, now=now,
                                 since=(now or time.time()) - 6 * 3600):
            if m.get("retired_session") and "retired:%s" % m["id"] not in seen:
                out.append({"kind": "ceo_retired", "key": "retired:%s" % m["id"], "message_id": m["id"],
                            "at": m["at"], "text": m["text"],
                            "how": ("The CEO typed this into a retired orchestrator session; it never "
                                    "reached you. Treat it exactly as if he had typed it here now.")})
    except Exception:                                       # noqa: BLE001  never blocks the inbox
        pass
    for req in requests:
        if (req.get("status") == "open" and req.get("delivery") == "inbox"
                and req.get("owner_session_id") in (session_id, None)
                and not req.get("inbox_collected_at")):
            # None: held while no orchestrator was bound (constitution 2026-10-27) — the next
            # orchestrator session takes it instead of the request reaching the CEO.
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


def collect(session_id, *, state_store=store, now=None, quiet_only=False):
    """Take everything waiting. An item another waiter took first is skipped. quiet_only marks
    the quiet items seen and takes nothing else (the pusher, which never takes work)."""
    taken = []
    for item in pending(session_id, state_store=state_store, now=now):
        if quiet_only and not item.get("_quiet"):
            continue
        try:
            if item["kind"] == "decision":
                taken.append(_collect_decision(item, state_store))
                continue
            if item["kind"] == "review_stalled":
                from agent.execution import review_queue
                for iid in item["items"]:
                    review_queue.mark_stalled_alerted(iid)
                taken.append(item)
                continue
            if item["kind"] == "reviewer_question":
                from agent.execution import review_queue
                review_queue.mark_collected(item["question_id"])
                taken.append(item)
                continue
            if item["kind"] in ("liveness", "orphan", "ceo_retired"):
                from agent.execution import liveness
                liveness.mark_collected(item["key"])
                taken.append(item)
                continue
            if item["kind"] == "not_live":
                from agent.execution import review_queue
                review_queue.mark_not_live_collected(item["ticket"])
                taken.append(item)
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
            if item.get("_quiet"):
                continue                       # recorded as seen; nothing to act on, no wake
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


def wait(timeout=DEFAULT_TIMEOUT, *, env=None, state_store=store, sleep=None, reexec=None):
    env = os.environ if env is None else env
    session_id = env.get("CLAUDE_CODE_SESSION_ID")
    orch = orchestrator_session(state_store)
    if not orch:
        raise Refused("orchestrator-unbound", "no orchestrator session is bound")
    if session_id != orch:
        raise Refused("not-orchestrator", "only the orchestrator session (%s) reads its inbox"
                      % orch)
    sleep = sleep or time.sleep
    if push_running(state_store):
        return {"status": "pushed", "items": [], "next": PUSHED}
    # B4: one waiter at a time. Several after a restart split the items and lost wakes.
    import fcntl
    os.makedirs(state_store.RUNTIME, exist_ok=True)
    lock = open(os.path.join(state_store.RUNTIME, "inbox-wait.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return {"status": "already-waiting", "items": [],
                "next": "another inbox waiter is already running; do not start a second one. "
                        "End the turn with the single character · and nothing else."}
    try:
        return _wait_loop(session_id, timeout, state_store, sleep, reexec)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _reexec(timeout):
    """Replace this process with a fresh waiter on the new code. Same PID, so the
    orchestrator's background command keeps running and nothing wakes it. The lock file
    is opened close-on-exec, so the new waiter takes it again."""
    sys.stdout.flush()
    os.chdir(ROOT)
    os.execv(sys.executable, [sys.executable, "-m", "agent.execution.inbox", "wait",
                              "--timeout", str(timeout)])


def _wait_loop(session_id, timeout, state_store, sleep, reexec=None):
    deadline = time.time() + timeout
    code_stamp = _code_stamp()
    while True:
        if _code_stamp() != code_stamp:
            # Live 2026-10-09: a waiter started before the `priority` item existed never
            # saw one, and the board waited. A changed Thebes collects nothing stale.
            # CEO 2026-11-11: the waiter reloads itself in place instead of waking the
            # orchestrator to start a new one; the orchestrator never sees a restart.
            if reexec:
                reexec(max(1, int(deadline - time.time())))
            return {"status": "restart", "items": [],
                    "next": "Thebes code changed; start the inbox waiter again now." + SILENT}
        if orchestrator_session(state_store) != session_id:
            # D-044 rotation: a waiter of the old session would hold the lock for two hours
            return {"status": "rebound", "items": [],
                    "next": "this session is no longer the orchestrator; stop"}
        if push_running(state_store):
            return {"status": "pushed", "items": [], "next": PUSHED}
        items = collect(session_id, state_store=state_store)
        if items:
            quiet = polls = 0
            while quiet < BATCH_QUIET_POLLS and polls < BATCH_MAX_POLLS:
                sleep(POLL_SECONDS)
                more = collect(session_id, state_store=state_store)
                items += more
                quiet = 0 if more else quiet + 1
                polls += 1
            if push_running(state_store):
                return {"status": "items", "count": len(items), "items": items,
                        "next": TAKE_NEXT + " " + PUSHED.split(";")[0] + "."}
            return {"status": "items", "count": len(items), "items": items,
                    "next": "SAY NOTHING to the CEO unless ceo_notice prints SEND. Handle "
                            "every item (see agent/ORCHESTRATOR.md), then start the inbox "
                            "waiter again." + SPEAK_ONLY_BY_NOTICE}
        if time.time() >= deadline:
            return {"status": "idle", "items": [],
                    "next": "nothing arrived; start the inbox waiter again." + SILENT}
        sleep(POLL_SECONDS)


PUSH_LOCK = "inbox-push.lock"
PUSHED = ("Thebes pushes your inbox to you as a message now (inbox_push); never start the "
          "inbox waiter again. End the turn with the single character · and nothing else.")
TAKE_NEXT = ("Handle every item (agent/ORCHESTRATOR.md), then end the turn. Start no inbox "
             "waiter." + SPEAK_ONLY_BY_NOTICE)


def push_running(state_store=store):
    """Is the inbox pusher alive? It holds PUSH_LOCK for as long as it runs."""
    import fcntl
    path = os.path.join(state_store.RUNTIME, PUSH_LOCK)
    if not os.path.exists(path):
        return False
    with open(path, "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
    return False


def take(*, env=None, state_store=store):
    """What the orchestrator runs when the pusher's message arrives: collect now, in the
    foreground, and print it. Same identity rule as `wait`."""
    env = os.environ if env is None else env
    orch = orchestrator_session(state_store)
    if not orch:
        raise Refused("orchestrator-unbound", "no orchestrator session is bound")
    if env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator session (%s) reads its inbox"
                      % orch)
    items = collect(orch, state_store=state_store)
    if not items:
        return {"status": "empty", "items": [],
                "next": "nothing is waiting (already taken). End the turn with the single character · and "
                        "nothing else."}
    return {"status": "items", "count": len(items), "items": items, "next": TAKE_NEXT}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.inbox", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait"); w.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    sub.add_parser("take")
    sub.add_parser("peek")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "wait":
            out = wait(ns.timeout, reexec=_reexec)
        elif ns.cmd == "take":
            out = take()
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
