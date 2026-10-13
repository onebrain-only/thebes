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
    return os.environ.get("CODEX_THREAD_ID") or ""


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
    for item in candidates(state_store, jira, with_qa):
        if claim(item["item_id"]):
            return item
    return None


def wait(timeout, *, state_store=store, jira=None, sleep=time.sleep, clock=time.time):
    start, last_jira, with_qa = clock(), -JIRA_POLL_SECONDS, True
    while clock() - start < timeout:
        poll_qa = clock() - last_jira >= JIRA_POLL_SECONDS
        if poll_qa:
            last_jira = clock()
        item = next_item(state_store, jira, with_qa=poll_qa)
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


def status(state_store=store):
    items = candidates(state_store, with_qa=False)
    claims = {}
    for name in os.listdir(_dir("claims")):
        c = _read(os.path.join(_dir("claims"), name)) or {}
        claims[c.get("item_id")] = c
    return {"waiting_judge_items": [i["item_id"] for i in items],
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
            return 0 if item else 3
        if ns.cmd == "next":
            item = next_item()
            print(json.dumps(item if item else {"status": "empty"}, indent=2, ensure_ascii=False))
            return 0
        if ns.cmd == "status":
            print(json.dumps(status(), indent=2))
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
