"""The Ready dispatcher (D-042): a ticket in Jira `Ready` IS the order.

A background loop, no model and no tokens. Every INTERVAL seconds it reads project KAN's
Ready tickets and, for each one it can place:

    capability      the Thebes task record's, or a `cap:<capability>` label
    lane            code capabilities go to a free `code` team; everything else (and any
                    ticket labelled `ask`) goes to the `ops` team
    dependencies    a ticket blocked by an unfinished one waits
    brief           the description must pass the D-041 brief lint. `BRANCH: <base>-<team>`
                    (or the literal `<team>`) is filled in with the receiving team
    dispatch        conversation_dispatch with --ticket, origin = the orchestrator session,
                    so results reach the orchestrator's inbox exactly as before

Ownership (D-042): a code ticket whose component a team owns goes to that team first; a fresh
one waits up to 30 minutes for its busy owner, then any free team takes it. Owners take their
domain first, in the PM's rank order.

A ticket it cannot place is never retried in a loop: an incomplete brief gets ONE comment and
the label `needs-brief`. The board's needs are raised as one `priority_request` for the
orchestrator's inbox, which runs the project's PO (briefs) and the PM (re-ranking Backlog into
Ready). Labels are the state; removing `needs-brief` makes a ticket eligible again.

Stops dispatching (and says why) when the operating mode is not PRODUCT_EXECUTION, a
FREEZE is active, or MAX_PARALLEL code dispatches are already open.

    python3 -m agent.execution.ready_dispatcher tick       # one pass, prints what it did
    python3 -m agent.execution.ready_dispatcher serve      # loop forever (background)
"""
import argparse
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.state import store, teams                                   # noqa: E402

INTERVAL = 60
MAX_PARALLEL = 3
JQL = 'project = KAN AND status = "Ready" ORDER BY rank ASC'
FIELDS = ["summary", "status", "labels", "description", "issuelinks", "duedate", "components",
          "timeoriginalestimate"]
OWNER_WAIT = "-30m"
FRESH_JQL = ('project = KAN AND status = "Ready" AND status CHANGED TO "Ready" AFTER %s'
             % OWNER_WAIT)
CODE_CAPABILITIES = ("frontend", "backend", "ux-engineer", "product-designer")
CAP_LABEL = re.compile(r"^cap:([a-z-]+)$")
NEEDS_BRIEF = "needs-brief"
BRIEF_REQUESTED = "brief-requested"
ASK_LABEL = "ask"


def _jira():
    from agent.integrations import jira
    return jira


def capability_of(issue, state_store=store):
    task = state_store.read("task", issue["key"]) or {}
    cap = (task.get("execution_profile") or {}).get("required_capability")
    if cap:
        return cap
    for label in issue.get("labels") or []:
        m = CAP_LABEL.match(label)
        if m:
            return m.group(1)
    return None


def lane_of(issue, capability):
    if ASK_LABEL in (issue.get("labels") or []):
        return "ops"
    return "code" if capability in CODE_CAPABILITIES else "ops"


def blockers(raw_links, jira):
    """Keys of unfinished tickets that block this one."""
    out = []
    for link in raw_links or []:
        if (link.get("type") or {}).get("name") != "Blocks" or "inwardIssue" not in link:
            continue
        other = link["inwardIssue"]
        cat = (((other.get("fields") or {}).get("status") or {}).get("statusCategory") or {})
        if cat.get("key") != "done":
            out.append(other.get("key"))
    return out


BASES = ("alpha", "canary", "main")


def fill_branch(text, team_id):
    """A team branch is always `<base>-<team>` (D-041): `BRANCH: alpha-<team>`,
    `alpha-karnak` or a stray `alpha-frontend-1` all become `alpha-<this team>`, so a
    dispatch never works on another team's (or a seat's) branch. `none` stays `none`."""
    def repl(m):
        branch = m.group(2).strip().split()[0] if m.group(2).strip() else ""
        if not branch or branch.lower() == "none":
            return m.group(0)
        head = branch.split("-")[0]
        base = head if head.lower() in BASES else branch.replace("<team>", "").rstrip("-")
        return "%s%s-%s" % (m.group(1), base, team_id)
    return re.sub(r"(?im)^(BRANCH:\s*)(\S.*)$", repl, text)


def open_dispatches(state_store=store):
    return [r for r in state_store.read_all("conversation_dispatch")
            if r.get("status") in store.CONVERSATION_DISPATCH_OPEN]


def free_team(lane, state_store=store):
    from agent.execution import team_pool
    busy = {r["target_session_id"] for r in open_dispatches(state_store)}
    for tid in sorted(teams.lane_teams(lane), key=lambda t: teams.read()[t]["number"]):
        binding = state_store.active_role_session(tid)
        if binding and binding["session_id"] not in busy:
            return tid, binding["session_id"]
    return None, None


def effort_line(seconds):
    """The PM's Original estimate (D-042), as the team reads it."""
    if not seconds:
        return "Expected effort: not estimated."
    hours = seconds / 3600.0
    return "Expected effort (PM's Original estimate): %s." % (
        "%dh" % hours if hours == int(hours) else "%.1fh" % hours)


def prompt_for(issue, team_id):
    body = fill_branch(issue.get("description") or "", team_id)
    return "\n".join([
        "Jira %s: %s" % (issue["key"], issue.get("summary") or ""),
        effort_line(issue.get("estimate_seconds")),
        "Source: the ticket description, dispatched by the Thebes Ready dispatcher (D-042).",
        "Every commit message starts with `%s:`." % issue["key"],
        "",
        body,
    ])


def _label(jira, key, labels, add):
    if add in labels:
        return
    jira.update_issue(key, {"labels": list(labels) + [add]})


def _flag_brief(issue, problems, jira, comment=True):
    """One comment and the `needs-brief` label. The project's PO (run by the
    orchestrator, D-042) is asked through a priority request; the label is the state."""
    key = issue["key"]
    if comment:
        jira.add_comment(key, "Thebes Ready dispatcher: this ticket is in Ready but its brief "
                              "is incomplete, so it was not dispatched.\n\nMissing: %s\n\nThe "
                              "project's PO writes the brief into the description and removes "
                              "the `%s` label; the ticket is then picked up automatically."
                         % ("; ".join(problems), NEEDS_BRIEF))
    _label(jira, key, issue.get("labels") or [], NEEDS_BRIEF)
    return {"key": key, "action": "needs-brief", "problems": problems}


# ------------------------------------------------------------------ priority requests
PRIORITY_MIN_SECONDS = 3600      # the PM re-plans at most hourly unless a brief is needed
DONE_JQL = 'project = KAN AND status = "Done" ORDER BY updated DESC'
BACKLOG_JQL = 'project = KAN AND status = "To Do" ORDER BY rank ASC'


def _ts(stamp):
    import calendar
    try:
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


def raise_priority_request(reasons, signature, *, state_store=store, now=None):
    """One open request at a time: new reasons join the open one. Backlog reasons are
    rate-limited to one request per PRIORITY_MIN_SECONDS; brief reasons are not."""
    now = now or time.time()
    reqs = sorted(state_store.read_all("priority_request"), key=lambda r: r.get("created_at") or "")
    open_req = next((r for r in reqs if r.get("status") == "open"), None)
    last = reqs[-1] if reqs else None
    if last and last.get("backlog_signature") == signature:
        # Malfunction #28: an unchanged Backlog is not news, whatever the free-team count.
        reasons = [r for r in reasons if r.get("kind") not in ("backlog-changed", "ready-short")]
    if last and now - _ts(last.get("created_at")) < PRIORITY_MIN_SECONDS:
        # A NEW ticket in Backlog (live 2026-10-09: the desk's KAN-446 waited for the hourly
        # limit) is asked about at once; edits to tickets already seen stay rate-limited.
        seen = {k.split("@")[0] for r in reqs if now - _ts(r.get("created_at")) < PRIORITY_MIN_SECONDS
                for k in (r.get("backlog_signature") or "").split("|") if k}
        new_keys = sorted({k.split("@")[0] for k in signature.split("|") if k} - seen)
        reasons = [r for r in reasons if r.get("kind") == "needs-brief"] + (
            [{"kind": "new-in-backlog", "keys": new_keys}] if new_keys else [])
    if not reasons:
        return None
    if open_req:
        known = {json.dumps(r, sort_keys=True) for r in open_req["reasons"]}
        merged = open_req["reasons"] + [r for r in reasons
                                        if json.dumps(r, sort_keys=True) not in known]
        if len(merged) == len(open_req["reasons"]):
            return None
        return state_store.update("priority_request", open_req["priority_request_id"],
                                  open_req["revision"],
                                  {"reasons": merged, "backlog_signature": signature})
    return state_store.create("priority_request", {
        "reasons": reasons, "status": "open", "backlog_signature": signature,
        "collected_at": None})


def tick(*, state_store=store, jira=None, dispatch=None, now=None):
    """One pass. Returns a list of what happened, for the log."""
    from agent.execution import conversation_dispatch as cd, dispatch_brief
    jira = jira or _jira()
    mode = state_store.current_operating_mode()
    if mode != "PRODUCT_EXECUTION":
        return [{"skipped": "mode-%s" % mode}]
    if any(iv.get("kind") == "freeze" for iv in state_store.active_interventions()):
        return [{"skipped": "system-frozen"}]
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch:
        return [{"skipped": "orchestrator-unbound"}]

    def send(text, sid, ticket, lane_capability):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID")}
        env[cd.CLAUDE_ORIGIN_ENV] = orch
        return (dispatch or cd.dispatch)(text, sid, env=env, state_store=state_store,
                                         detach=True, ticket=ticket,
                                         lane_capability=lane_capability)

    done, brief_reasons = [], []
    opened = open_dispatches(state_store)
    open_keys = {r.get("jira_key") for r in opened}
    code_open = sum(1 for r in opened
                    if teams.read().get(r.get("target_seat_id"), {}).get("lane", "code") == "code")
    try:
        fresh = {i["key"] for i in jira.search_issues(FRESH_JQL, fields=["status"], limit=100)}
    except Exception:                                   # noqa: BLE001
        fresh = set()

    candidates = []
    for issue_raw in jira.search_issues(JQL, fields=FIELDS, limit=50, raw=True):
        issue = jira.normalize_issue(issue_raw)
        issue["components"] = [c.get("name") for c in
                               ((issue_raw.get("fields") or {}).get("components") or [])]
        issue["estimate_seconds"] = (issue_raw.get("fields") or {}).get("timeoriginalestimate")
        key = issue["key"]
        if key in open_keys:
            continue
        if NEEDS_BRIEF in issue["labels"]:
            if BRIEF_REQUESTED not in issue["labels"]:
                brief_reasons.append({"kind": "needs-brief", "key": key})
                _label(jira, key, issue["labels"], BRIEF_REQUESTED)
            continue
        waiting = blockers((issue_raw.get("fields") or {}).get("issuelinks"), jira)
        if waiting:
            done.append({"key": key, "action": "waiting", "blocked_by": waiting})
            continue
        cap = capability_of(issue, state_store)
        if not cap:
            done.append(_flag_brief(issue, ["capability: unknown — add label "
                                            "`cap:<capability>` or record it with "
                                            "agent.state.ready"], jira))
            continue
        task = state_store.read("task", key)
        if task:
            why = state_store.intervention_blocks_claim(key, cap)
            if why:
                done.append({"key": key, "action": "held", "reason": why})
                continue
        candidates.append((issue, cap))

    # Two passes (D-042): owners take their own domain first, in the PM's rank order;
    # then the rest. A fresh owned ticket waits for its busy owner up to 30 minutes.
    taken = set()
    for pass_no in (1, 2):
        for issue, cap in candidates:
            key = issue["key"]
            if key in taken:
                continue
            lane = lane_of(issue, cap)
            owner = teams.owner_of(issue["components"]) if lane == "code" else None
            if pass_no == 1 and not owner:
                continue
            if lane == "code" and code_open >= MAX_PARALLEL:
                if pass_no == 2:
                    done.append({"key": key, "action": "waiting", "reason": "max-parallel"})
                continue
            tid = sid = None
            if owner:
                sid_owner = (state_store.active_role_session(owner) or {}).get("session_id")
                busy = {r["target_session_id"] for r in open_dispatches(state_store)}
                if sid_owner and sid_owner not in busy:
                    tid, sid = owner, sid_owner
                elif pass_no == 1:
                    continue
                elif key in fresh:
                    done.append({"key": key, "action": "waiting",
                                 "reason": "owner-busy:%s" % owner})
                    continue
            if not tid:
                tid, sid = free_team(lane, state_store)
            if not tid:
                if pass_no == 2:
                    done.append({"key": key, "action": "waiting",
                                 "reason": "no-free-%s-team" % lane})
                continue
            text = prompt_for(issue, tid)
            try:
                dispatch_brief.lint(text, tid)
            except dispatch_brief.BriefError as exc:
                taken.add(key)
                done.append(_flag_brief(issue, exc.problems, jira))
                brief_reasons.append({"kind": "needs-brief", "key": key})
                continue
            try:
                out = send(text, sid, key, cap)
            except cd.Refused as exc:
                taken.add(key)
                done.append({"key": key, "action": "refused", "code": exc.code,
                             "error": str(exc)[:300]})
                continue
            taken.add(key)
            if lane == "code":
                code_open += 1
            done.append({"key": key, "action": "dispatched", "team": tid,
                         "owner": owner, "dispatch_id": out.get("dispatch_id")})

    # A Jira move that failed (a dropped connection) is retried while its work is still open.
    try:
        from agent.execution import jira_sync
        for r in opened:
            note = (r.get("jira_sync") or {}).get("start") or {}
            if r.get("jira_key") and note.get("status") == "failed" and not r.get("jira_retries", 0) >= 5:
                cur = state_store.read("conversation_dispatch", r["dispatch_id"])
                state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                                   {"jira_retries": (cur.get("jira_retries") or 0) + 1})
                out = jira_sync.on_start(state_store.read("conversation_dispatch",
                                                          r["dispatch_id"]),
                                         state_store=state_store, jira=jira)
                done.append({"key": r["jira_key"], "action": "jira-start-retried",
                             "status": (out or {}).get("status")})
    except Exception as exc:                            # noqa: BLE001
        done.append({"action": "jira-retry-failed", "error": str(exc)[:200]})

    # An ops dispatch that stopped on a permission denial is re-sent ONCE with the current
    # brief (which names the pre-approved push shapes), so the CEO is never the relay.
    try:
        for r in state_store.read_all("conversation_dispatch"):
            key = r.get("jira_key")
            if (not key or key in open_keys or r.get("permission_retried")
                    or r.get("status") not in ("decision_required", "blocked")
                    or teams.read().get(r.get("target_seat_id"), {}).get("lane") != "ops"):
                continue
            try:
                with open(r.get("result_ref") or "", errors="ignore") as fh:
                    result = fh.read()
            except OSError:
                continue
            if not re.search(r"(?i)denied by permission|permission system|push denied|"
                             r"permissions?\b[^.\n]{0,40}(denied|refus)", result):
                continue
            cur = state_store.read("conversation_dispatch", r["dispatch_id"])
            state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                               {"permission_retried": True})
            issue = jira.normalize_issue(jira.get_issue(key, fields=FIELDS, raw=True))
            if (issue.get("status") or "").lower() == "done":
                continue
            sid = (state_store.active_role_session(r["target_seat_id"]) or {}).get("session_id")
            if not sid or sid in {o["target_session_id"] for o in open_dispatches(state_store)}:
                continue
            note = ("RETRY: your last attempt stopped on a push permission denial. The dispatch "
                    "brief now names the only push shapes that are pre-approved; translate the "
                    "ticket's push command into one of them. Do not retry anything else.\n\n")
            out = send(note + prompt_for(issue, r["target_seat_id"]), sid, key,
                       capability_of(issue, state_store) or "devops")
            done.append({"key": key, "action": "permission-retry",
                         "dispatch_id": out.get("dispatch_id")})
    except Exception as exc:                            # noqa: BLE001
        done.append({"action": "permission-retry-failed", "error": str(exc)[:200]})

    # Verified work reaches Alpha by itself (D-042): settle finished integrations, then open the
    # next one. Never raises into the dispatch loop.
    try:
        from agent.execution import integrate
        done.extend(integrate.settle(state_store=state_store, jira=jira))
        done.extend(integrate.dispatch_for(state_store=state_store, dispatch=dispatch))
    except Exception as exc:                            # noqa: BLE001
        done.append({"action": "integrate-failed", "error": str(exc)[:200]})

    # Ask the PM (and the POs) when the board needs them (D-042).
    reasons = list(brief_reasons)
    try:
        backlog = jira.search_issues(BACKLOG_JQL, fields=["status", "updated"], limit=100)
        signature = "|".join("%s@%s" % (b["key"], b.get("updated")) for b in backlog)
        try:                    # a ticket finishing can unblock the Backlog (malfunction #1/#28)
            finished = jira.search_issues(DONE_JQL, fields=["status"], limit=5)
            signature += "|done@" + ",".join(f["key"] for f in finished)
        except Exception:                               # noqa: BLE001
            pass
        ready_left = len(candidates) - len(taken)
        free_code = sum(1 for t in teams.lane_teams("code")
                        if (state_store.active_role_session(t) or {}).get("session_id")
                        not in {r["target_session_id"] for r in open_dispatches(state_store)}
                        and state_store.active_role_session(t))
        if backlog:
            reasons.append({"kind": "backlog-changed", "count": len(backlog)})
            if ready_left < free_code:
                reasons.append({"kind": "ready-short", "ready": ready_left,
                                "free_code_teams": free_code})
        req = raise_priority_request(reasons, signature, state_store=state_store, now=now)
        if req:
            done.append({"action": "priority-request",
                         "priority_request_id": req["priority_request_id"],
                         "reasons": [r["kind"] for r in req["reasons"]]})
    except Exception as exc:                            # noqa: BLE001
        done.append({"action": "priority-request-failed", "error": str(exc)[:200]})
    return done


def serve(interval=INTERVAL):
    log = os.path.join(store.RUNTIME, "ready-dispatcher.log")
    last = None
    while True:
        try:
            done = tick()
            summary = json.dumps(done, sort_keys=True, default=str)
            if done and summary != last:          # log changes, not every idle minute
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"at": store.now(), "done": done}, default=str) + "\n")
            last = summary
        except Exception as exc:                  # the dispatcher never dies
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": store.now(), "error": str(exc)[:300]}) + "\n")
        time.sleep(interval)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.ready_dispatcher", description=__doc__,
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
