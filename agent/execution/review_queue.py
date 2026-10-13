"""The review queue the Codex reviewer works from (D-043 draft, agent/REVIEWER.md).

Claude teams hand over evidence and stop reviewing; ONE Codex conversation, "Reviewer", looks at
the finished work with its own eyes. Nothing wakes it from outside (a Desktop conversation cannot
be woken): it runs `wait` as one long command, gets an item, reviews, submits, and waits again.
This module is the zero-token side of that loop.

    python3 -m agent.execution.review_queue wait [--timeout 300]   # blocks; prints ONE item
    python3 -m agent.execution.review_queue next                   # one pass, no waiting
    python3 -m agent.execution.review_queue submit <item_id> --pass C2 --fail C3:"why" \\
        --skip C4:"needs-write" --evidence "<paths and steps>"      # a `judge` item
    python3 -m agent.execution.review_queue submit <item_id> --verdict pass|fail \\
        --reason "..." --evidence "..."                              # a `qa` item
    python3 -m agent.execution.review_queue status

Two kinds of item:
  judge  a verified-by-code dispatch whose only open checks are `judge` checks (an eye must
         settle them). A verdict goes through `verify.judge_verdict`, so a fail sends only
         that check back to the team and the round limit is Thebes's.
  qa     a Jira ticket in QA-Test / Peer-review. Pass -> Done. Fail -> comment, back to the
         lane status, and a priority request so the PM/orchestrator re-plans it.

An item is CLAIMED atomically for one Codex thread (O_EXCL file); a claim older than
CLAIM_SECONDS is offered again, so a reviewer that died never strands work. A verdict is only
accepted from the thread that holds the claim. `skip` (for example needs-write) is recorded as a
pass whose detail says SKIPPED, so the Jira comment shows what was not verified.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402

CLAIM_SECONDS = 20 * 60
POLL_SECONDS = 5
JIRA_POLL_SECONDS = 60
QA_JQL = 'project = KAN AND status in ("QA-Test", "Peer-review") ORDER BY updated ASC'
LANE_STATUS_ID = "10046"            # Front-end: where a failed qa ticket goes back to
DONE_STATUS_ID = "10007"
TEXT_LIMIT = 6000


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def _dir(sub):
    path = os.path.join(store.RUNTIME, "review", sub)
    os.makedirs(path, exist_ok=True)
    return path


def _safe(item_id):
    return "".join(c if c.isalnum() or c in "-_@." else "_" for c in item_id)


def _thread():
    """Who is asking: a Codex conversation, or (the fallback QA conversation) a Claude session."""
    if os.environ.get("CODEX_THREAD_ID"):
        return os.environ["CODEX_THREAD_ID"]
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    return "claude:%s" % sid if sid else ""


def reviewer_kind(thread=None):
    return "claude" if (thread if thread is not None else _thread()).startswith("claude:") else "codex"


# ------------------------------------------------------------------ which channel reviews
CHANNELS = ("codex", "claude")


def _channel_path():
    return os.path.join(store.RUNTIME, "review", "channel.json")


def get_channel():
    """`codex` (the default) or `claude`. Only the CEO's explicit order, through the orchestrator,
    ever changes it; the channel that is not active stands by and takes no work."""
    return (_read(_channel_path()) or {}).get("channel") or "codex"


def set_channel(channel, by, *, env=None, state_store=store, notify=True, dispatch=None):
    """Switch the review channel (CEO 2026-10-13: Codex is the default; when Codex has no tokens
    the CEO tells the orchestrator to run QA from Claude Code, and back). Orchestrator only.
    Claims held by the OTHER channel are released so nothing is stranded, and the fallback QA
    conversation (Edfu) is woken to start, or told to stop."""
    from agent.state import teams
    env = os.environ if env is None else env
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator switches the review channel, and "
                      "only on the CEO's explicit order")
    if channel not in CHANNELS:
        raise Refused("channel-invalid", "channel is codex or claude")
    if not (by or "").strip():
        raise Refused("order-required", "quote the CEO's words ordering the switch (--by)")
    before = get_channel()
    os.makedirs(os.path.dirname(_channel_path()), exist_ok=True)
    with open(_channel_path(), "w", encoding="utf-8") as fh:
        json.dump({"channel": channel, "by": by.strip()[:300], "at": time.time()}, fh)
    released = []
    for name in os.listdir(_dir("claims")):
        c = _read(os.path.join(_dir("claims"), name)) or {}
        if c.get("thread") and reviewer_kind(c["thread"]) != channel and not is_done(c.get("item_id", "")):
            os.unlink(os.path.join(_dir("claims"), name))
            released.append(c.get("item_id"))
    out = {"status": "switched", "from": before, "to": channel, "released_claims": released}
    if notify:
        out["edfu"] = _wake_edfu(channel, state_store, dispatch)
    return out


def _wake_edfu(channel, state_store, dispatch=None):
    from agent.state import teams
    edfu = next(iter(teams.lane_teams("qa")), None)
    sid = (state_store.active_role_session(edfu) or {}).get("session_id") if edfu else None
    if not sid:
        return {"status": "not-started",
                "next": "Edfu has no session: the CEO runs `bash agent/scripts/start-teams.sh edfu`"}
    if channel == "claude":
        text = ("THEBES REVIEW CHANNEL: CLAUDE. The CEO ordered QA to run from Claude Code. Follow "
                "agent/REVIEWER.md (Claude variant) now: start `python3 -m agent.execution."
                "review_queue wait --timeout 3600` with run_in_background, handle every item it "
                "returns, submit verdicts, and start the wait again each time. Report in one line "
                "that the loop is running, then end your turn.")
    else:
        text = ("THEBES REVIEW CHANNEL: CODEX. The CEO sent QA back to Codex. Stop your review "
                "loop now: do not start another `review_queue wait`, finish any item you have "
                "already submitted, report in one line that you stood down, and go idle.")
    from agent.execution import conversation_dispatch as cd
    env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID")}
    env[cd.CLAUDE_ORIGIN_ENV] = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    try:
        out = (dispatch or cd.dispatch)(text, sid, env=env, state_store=state_store, detach=True, ticket=None)
        return {"status": "notified", "dispatch_id": out.get("dispatch_id")}
    except Exception as exc:                                # noqa: BLE001
        return {"status": "notify-failed", "error": str(exc)[:200],
                "next": "dispatch the same text to Edfu by hand (conversation_dispatch dispatch --to %s)" % sid}


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _text(path, limit=TEXT_LIMIT):
    try:
        with open(path or "", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def is_done(item_id):
    return os.path.exists(os.path.join(_dir("done"), _safe(item_id)))


def claim(item_id, now=None):
    """Atomically claim for this thread. True if claimed (or this thread already holds it)."""
    now = now or time.time()
    path = os.path.join(_dir("claims"), _safe(item_id))
    body = {"item_id": item_id, "thread": _thread(), "at": now}
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            cur = _read(path) or {}
            if cur.get("thread") == body["thread"] and now - cur.get("at", 0) < CLAIM_SECONDS:
                return True
            if now - cur.get("at", 0) < CLAIM_SECONDS:
                return False
            try:                                  # stale: the reviewer that held it is gone
                os.unlink(path)
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(body, fh)
        return True
    return False


def holder(item_id):
    return (_read(os.path.join(_dir("claims"), _safe(item_id))) or {}).get("thread")


def finish(item_id, outcome):
    with open(os.path.join(_dir("done"), _safe(item_id)), "w", encoding="utf-8") as fh:
        json.dump({"item_id": item_id, "outcome": outcome, "at": time.time(),
                   "thread": _thread()}, fh)


# ------------------------------------------------------------------- finding work
def judge_items(state_store=store):
    from agent.execution import verify, conversation_dispatch as cd
    out = []
    for rec in state_store.read_all("conversation_dispatch"):
        if rec.get("root_dispatch_id") or not rec.get("jira_key") or not cd.is_product(rec):
            continue                       # text/ops deliverables stay with the orchestrator
        pending = verify.pending_judge(rec)
        if not pending:
            continue
        ver = rec.get("verification") or {}
        by_id = {c["id"]: c for c in rec.get("checks") or []}
        out.append({
            "item_id": "judge-%s-c%s" % (rec["dispatch_id"], ver.get("cycle") or 1),
            "kind": "judge", "dispatch_id": rec["dispatch_id"], "ticket": rec["jira_key"],
            "team": rec.get("target_seat_id"), "branch": ver.get("branch"), "sha": ver.get("sha"),
            "checks": [{"id": p["id"], "what": (by_id.get(p["id"]) or {}).get("what") or p.get("what"),
                        "evidence_named": (by_id.get(p["id"]) or {}).get("pass")}
                       for p in pending],
            "team_report": _text(rec.get("result_ref")),
            "brief": _text(rec.get("prompt_ref")),
            "at": rec.get("outcome_at") or rec.get("created_at") or ""})
    return out


def qa_items(jira=None):
    if jira is None:
        from agent.execution import jira_sync
        jira = jira_sync._client(None, store)
    if jira is None:
        return []
    out = []
    for raw in jira.search_issues(QA_JQL, fields=["summary", "status", "description", "updated"],
                                  limit=20, raw=True):
        issue = jira.normalize_issue(raw)
        key = issue["key"]
        out.append({"item_id": "qa-%s@%s" % (key, (raw.get("fields") or {}).get("updated")),
                    "kind": "qa", "ticket": key, "summary": issue.get("summary"),
                    "status": issue.get("status"), "description": (issue.get("description") or "")[:TEXT_LIMIT],
                    "at": (raw.get("fields") or {}).get("updated") or ""})
    return out


def _enrich_judges(items, jira=None):
    """A judge item whose ticket is already Done in Jira is stale (live 2026-10-13: a 5-day-old
    KAN-438 item the PO had closed with live-DB evidence was reviewed and failed). Drop those;
    for the rest add the ticket's status and latest comments so the reviewer sees the context."""
    if not items:
        return items
    if jira is None:
        from agent.execution import jira_sync
        jira = jira_sync._client(None, store)
    if jira is None:
        return items
    out = []
    for item in items:
        try:
            issue = jira.get_issue(item["ticket"])
            if (issue.get("status") or "").lower() == "done":
                finish(item["item_id"], {"skipped": "ticket-already-done"})
                continue
            item["ticket_status"] = issue.get("status")
            item["latest_comments"] = [
                {"at": c.get("created") or c.get("at"), "text": (c.get("body") or c.get("text") or "")[:500]}
                for c in (jira.get_comments(item["ticket"], limit=50) or [])[-3:]]
        except Exception:                                   # noqa: BLE001  Jira down: keep as is
            pass
        out.append(item)
    return out


def candidates(state_store=store, jira=None, with_qa=True):
    items = _enrich_judges(judge_items(state_store), jira)
    if with_qa:
        try:
            items += qa_items(jira)
        except Exception:                                   # noqa: BLE001  Jira down: judges only
            pass
    return sorted((i for i in items if not is_done(i["item_id"])), key=lambda i: i["at"])


def next_item(state_store=store, jira=None, with_qa=True):
    if reviewer_kind() != get_channel():
        return None                                         # this channel is standing by
    for item in candidates(state_store, jira, with_qa):
        if claim(item["item_id"]):
            return item
    return None


def wait(timeout, *, state_store=store, jira=None, sleep=time.sleep, clock=time.time):
    start, last_jira, with_qa = clock(), -JIRA_POLL_SECONDS, True
    if reviewer_kind() != get_channel():
        return {"standby": True, "channel": get_channel(),
                "next": "The review channel is %s, not yours: do not start another wait; go idle "
                        "until the orchestrator or the CEO tells you the channel is yours."
                        % get_channel()}
    while clock() - start < timeout:
        poll_qa = clock() - last_jira >= JIRA_POLL_SECONDS
        if poll_qa:
            last_jira = clock()
        item = next_answer(clock()) or next_item(state_store, jira, with_qa=poll_qa)
        if item:
            return item
        sleep(POLL_SECONDS)
    return None


# ------------------------------------------------------------------- the verdict
def _owner_check(item_id):
    held = holder(item_id)
    if held is None:
        raise Refused("not-claimed", "%s is not claimed; run `wait` or `next` first" % item_id)
    if held != _thread():
        raise Refused("not-your-claim", "%s is claimed by another reviewer thread" % item_id)


def _evidence_file(ticket, evidence):
    d = os.path.join(store.RUNTIME, "review-evidence", ticket)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "verdict-%d.txt" % int(time.time()))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(evidence)
    return path


def submit_judge(item_id, passed, failed, skipped, evidence, *, state_store=store, jira=None,
                 dispatcher=None, launcher=None):
    from agent.execution import verify
    _owner_check(item_id)
    if not (evidence or "").strip():
        raise Refused("evidence-required", "name what you looked at and the steps you took")
    dispatch_id = item_id.split("-", 1)[1].rsplit("-c", 1)[0]
    rec = state_store.read("conversation_dispatch", dispatch_id)
    if rec is None:
        raise Refused("dispatch-not-found", dispatch_id)
    ev_path = _evidence_file(rec.get("jira_key") or "unknown", evidence)
    notes = {c: "reviewer: %s (evidence %s)" % (evidence.strip()[:200], ev_path) for c in passed}
    for cid, why in skipped.items():
        notes[cid] = "SKIPPED, not verified: %s" % why
    out = verify.judge_verdict(dispatch_id, list(passed) + list(skipped), failed,
                               state_store=state_store, jira=jira, dispatcher=dispatcher,
                               launcher=launcher, reviewer=_thread() or "reviewer", notes=notes)
    finish(item_id, {"pass": sorted(passed), "fail": sorted(failed), "skip": sorted(skipped)})
    return {"status": "recorded", "item_id": item_id, "evidence": ev_path, "result": out}


def submit_qa(item_id, verdict, reason, evidence, *, state_store=store, jira=None):
    from agent.execution import jira_sync
    _owner_check(item_id)
    if verdict not in ("pass", "fail"):
        raise Refused("verdict-invalid", "--verdict pass|fail")
    if verdict == "fail" and not (reason or "").strip():
        raise Refused("reason-required", "a failing verdict needs a reason a developer can act on")
    if not (evidence or "").strip():
        raise Refused("evidence-required", "name what you looked at and the steps you took")
    ticket = item_id[len("qa-"):].split("@")[0]
    ev_path = _evidence_file(ticket, evidence)
    jira = jira_sync._client(jira, state_store)
    if jira is None:
        raise Refused("jira-unavailable", "cannot record a qa verdict without Jira")
    if verdict == "pass":
        jira_sync._move(ticket, DONE_STATUS_ID, jira, state_store)
        jira.add_comment(ticket, "Thebes reviewer (Codex): PASS. %s\nEvidence: %s"
                         % ((reason or "").strip()[:500], ev_path))
    else:
        jira_sync._move(ticket, LANE_STATUS_ID, jira, state_store)
        jira.add_comment(ticket, "Thebes reviewer (Codex): FAIL.\n%s\nEvidence: %s"
                         % (reason.strip()[:1500], ev_path))
        try:                                         # the PM / orchestrator re-plans the rework
            state_store.create("priority_request", {
                "reasons": [{"kind": "qa-failed", "key": ticket, "reason": reason.strip()[:300]}],
                "status": "open", "backlog_signature": "qa-failed|%s|%d" % (ticket, time.time()),
                "collected_at": None})
        except Exception:                            # noqa: BLE001
            pass
    finish(item_id, {"verdict": verdict})
    return {"status": "recorded", "item_id": item_id, "evidence": ev_path}


def reopen(dispatch_id, *, state_store=store):
    """Offer a verified-but-unverified product item to the reviewer again: every check that was
    SKIPPED goes back to pending, so the ticket can still close by itself."""
    rec = state_store.read("conversation_dispatch", dispatch_id)
    ver = dict((rec or {}).get("verification") or {})
    skipped = [i for i, r in (ver.get("results") or {}).items()
               if str(r.get("detail") or "").startswith("SKIPPED")]
    if not rec or not skipped:
        raise Refused("nothing-to-reopen", "no skipped check on %s" % dispatch_id)
    results = dict(ver["results"])
    for i in skipped:
        results[i] = dict(results[i], status="pending-judge", detail="")
    ver.update(results=results, verdict="needs_judge", unverified=[])
    state_store.update("conversation_dispatch", dispatch_id, rec["revision"], {"verification": ver})
    for name in os.listdir(_dir("done")):
        if dispatch_id in name:
            os.unlink(os.path.join(_dir("done"), name))
    for name in os.listdir(_dir("claims")):
        if dispatch_id in name:
            os.unlink(os.path.join(_dir("claims"), name))
    return {"status": "reopened", "dispatch_id": dispatch_id, "checks": skipped}


# ------------------------------------------------------------------ asking the orchestrator
QUESTION_TTL = 30 * 60
ANSWER_LIMIT = 4000


def _qdir():
    return _dir("questions")


def _qpath(qid):
    return os.path.join(_qdir(), "%s.json" % _safe(qid))


def _qsave(q):
    tmp = _qpath(q["qid"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(q, fh)
    os.replace(tmp, _qpath(q["qid"]))


def questions():
    out = []
    for name in sorted(os.listdir(_qdir())):
        if name.endswith(".json"):
            q = _read(os.path.join(_qdir(), name))
            if q:
                out.append(q)
    return out


def ask(item_id, question, *, now=None):
    """The reviewer is stuck on an item it holds: put ONE question to the orchestrator. The answer
    comes back through `wait` as an item of kind `answer` (a Desktop conversation cannot be woken,
    so the reviewer polls, as it already does for work). The claim on the item is kept alive."""
    _owner_check(item_id)
    if not (question or "").strip():
        raise Refused("question-required", "say exactly what you cannot decide and what you tried")
    if any(q["item_id"] == item_id and q["answered_at"] is None for q in questions()):
        raise Refused("question-open", "you already have an open question on %s; wait for its answer"
                      % item_id)
    now = now or time.time()
    ticket = (item_id[len("qa-"):].split("@")[0] if item_id.startswith("qa-")
              else _ticket_of_judge(item_id))
    qid = "q-%d-%s" % (now, os.urandom(3).hex())
    q = {"qid": qid, "item_id": item_id, "ticket": ticket, "thread": _thread(),
         "question": question.strip()[:ANSWER_LIMIT], "asked_at": now, "collected_at": None,
         "answered_at": None, "answer": None, "answered_by": None, "delivered_at": None}
    _qsave(q)
    return {"status": "asked", "question_id": qid,
            "next": "run `review_queue wait` as usual: the answer arrives as an item of kind "
                    "`answer`. If none comes in %d minutes you will get it as expired: then submit "
                    "your best verdict, or --skip with the reason needs-answer." % (QUESTION_TTL // 60)}


def _ticket_of_judge(item_id):
    did = item_id.split("-", 1)[1].rsplit("-c", 1)[0]
    rec = store.read("conversation_dispatch", did) or {}
    return rec.get("jira_key") or ""


def answer(qid, text, *, env=None, state_store=store):
    """The orchestrator's answer. Only the orchestrator session may give one."""
    from agent.state import teams
    env = os.environ if env is None else env
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator answers a reviewer question")
    q = _read(_qpath(qid))
    if not q:
        raise Refused("question-not-found", qid)
    if q["answered_at"] is not None:
        raise Refused("already-answered", qid)
    if not (text or "").strip():
        raise Refused("answer-required", "an empty answer helps nobody")
    q.update(answer=text.strip()[:ANSWER_LIMIT], answered_at=time.time(), answered_by="orchestrator")
    _qsave(q)
    return {"status": "answered", "question_id": qid, "ticket": q["ticket"]}


def questions_for_inbox():
    """Unanswered questions the orchestrator has not been shown yet."""
    return [q for q in questions() if q["answered_at"] is None and q["collected_at"] is None
            and time.time() - q["asked_at"] < QUESTION_TTL]


def mark_collected(qid):
    q = _read(_qpath(qid))
    if q and q["collected_at"] is None:
        q["collected_at"] = time.time()
        _qsave(q)


def next_answer(now=None):
    """An answer (or an expiry) for a question THIS thread asked, delivered once. While a question
    is open the claim on its item is kept alive so the work is not offered to someone else."""
    now = now or time.time()
    me = _thread()
    for q in questions():
        if q["thread"] != me or q["delivered_at"] is not None:
            continue
        expired = q["answered_at"] is None and now - q["asked_at"] >= QUESTION_TTL
        if q["answered_at"] is None and not expired:
            cpath = os.path.join(_dir("claims"), _safe(q["item_id"]))
            claim_rec = _read(cpath)
            if claim_rec and claim_rec.get("thread") == me:
                claim_rec["at"] = now
                with open(cpath, "w", encoding="utf-8") as fh:
                    json.dump(claim_rec, fh)
            continue
        q["delivered_at"] = now
        _qsave(q)
        return {"kind": "answer", "question_id": q["qid"], "item_id": q["item_id"],
                "ticket": q["ticket"], "question": q["question"], "answer": q["answer"],
                "expired": expired,
                "next": ("Continue the SAME item with this answer, then submit." if not expired else
                         "No answer arrived. Submit your best verdict on %s, or --skip the check with "
                         "the reason needs-answer; never guess a PASS." % q["item_id"]),
                "at": ""}
    return None


STALL_SECONDS = 30 * 60


def stalled(state_store=store, now=None):
    """Product items waiting for review longer than STALL_SECONDS with nobody holding them (the
    channel is probably out of tokens or closed). The orchestrator tells the CEO; it never
    switches the channel by itself."""
    import calendar
    now = now or time.time()
    out = []
    for item in judge_items(state_store):
        if is_done(item["item_id"]) or holder(item["item_id"]):
            continue
        try:
            age = now - calendar.timegm(time.strptime(item["at"], "%Y-%m-%dT%H:%M:%SZ"))
        except (TypeError, ValueError):
            continue
        if age >= STALL_SECONDS:
            out.append({"item_id": item["item_id"], "ticket": item["ticket"], "age_min": int(age / 60)})
    return out


def mark_stalled_alerted(item_id):
    with open(os.path.join(_dir("stalled-alerted"), _safe(item_id)), "w") as fh:
        fh.write("1")


def stalled_unalerted(state_store=store, now=None):
    return [i for i in stalled(state_store, now)
            if not os.path.exists(os.path.join(_dir("stalled-alerted"), _safe(i["item_id"])))]


def status(state_store=store):
    items = candidates(state_store, with_qa=False)
    claims = {}
    for name in os.listdir(_dir("claims")):
        c = _read(os.path.join(_dir("claims"), name)) or {}
        claims[c.get("item_id")] = c
    return {"channel": get_channel(), "waiting_judge_items": [i["item_id"] for i in items],
            "claimed": {k: {"thread": v.get("thread"), "age_s": int(time.time() - v.get("at", 0))}
                        for k, v in claims.items() if k and not is_done(k)}}


def _pairs(values):
    out = {}
    for v in values or []:
        cid, _, why = v.partition(":")
        out[cid.strip()] = why.strip() or "no reason given"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.review_queue", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait"); w.add_argument("--timeout", type=int, default=300)
    sub.add_parser("next")
    sub.add_parser("status")
    ro = sub.add_parser("reopen"); ro.add_argument("dispatch_id")
    aq = sub.add_parser("ask", help="the reviewer is stuck: put ONE question to the orchestrator")
    aq.add_argument("item_id"); aq.add_argument("--question", required=True)
    an = sub.add_parser("answer", help="orchestrator only: answer a reviewer question")
    an.add_argument("question_id"); an.add_argument("--text", required=True)
    sub.add_parser("questions")
    ch = sub.add_parser("channel", help="show the review channel, or (orchestrator, on the CEO's "
                        "explicit order) switch it to codex or claude")
    ch.add_argument("to", nargs="?", choices=CHANNELS)
    ch.add_argument("--by", default="", help="the CEO's words ordering the switch")
    s = sub.add_parser("submit"); s.add_argument("item_id")
    s.add_argument("--pass", dest="passed", action="append", default=[])
    s.add_argument("--fail", dest="failed", action="append", default=[])
    s.add_argument("--skip", dest="skipped", action="append", default=[])
    s.add_argument("--verdict"); s.add_argument("--reason", default="")
    s.add_argument("--evidence", default="")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "wait":
            item = wait(ns.timeout)
            print(json.dumps(item if item else {"status": "timeout", "waited_s": ns.timeout},
                             indent=2, ensure_ascii=False))
            return 0 if (item and not item.get("standby")) else 3
        if ns.cmd == "next":
            item = next_item()
            print(json.dumps(item if item else {"status": "empty"}, indent=2, ensure_ascii=False))
            return 0
        if ns.cmd == "status":
            print(json.dumps(status(), indent=2))
            return 0
        if ns.cmd == "channel":
            out = (set_channel(ns.to, ns.by) if ns.to else {"channel": get_channel()})
            print(json.dumps(out, indent=2))
            return 0
        if ns.cmd == "ask":
            print(json.dumps(ask(ns.item_id, ns.question), indent=2))
            return 0
        if ns.cmd == "answer":
            print(json.dumps(answer(ns.question_id, ns.text), indent=2))
            return 0
        if ns.cmd == "questions":
            print(json.dumps([{k: q[k] for k in ("qid", "ticket", "question", "answered_at")}
                              for q in questions()], indent=2))
            return 0
        if ns.cmd == "reopen":
            print(json.dumps(reopen(ns.dispatch_id), indent=2))
            return 0
        if ns.item_id.startswith("qa-"):
            out = submit_qa(ns.item_id, ns.verdict, ns.reason, ns.evidence)
        else:
            out = submit_judge(ns.item_id, [p.strip() for p in ns.passed], _pairs(ns.failed),
                               _pairs(ns.skipped), ns.evidence)
    except (Refused, __import__("agent.execution.verify", fromlist=["Refused"]).Refused) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
