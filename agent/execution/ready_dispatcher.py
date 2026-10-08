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

A ticket it cannot place is never retried in a loop: an incomplete brief gets ONE comment
and the label `needs-brief`; when an ops team exists, one brief request is sent to it,
whose po writes the brief and removes the label. The label is the state; removing it
makes the ticket eligible again.

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
FIELDS = ["summary", "status", "labels", "description", "issuelinks", "duedate"]
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


def fill_branch(text, team_id):
    """`BRANCH: alpha-<team>` → `BRANCH: alpha-karnak`. A branch already naming a team
    keeps its base and takes this team, so a re-dispatch never reuses another team's branch."""
    def repl(m):
        branch = m.group(2).strip().split()[0] if m.group(2).strip() else ""
        if not branch or branch.lower() == "none":
            return m.group(0)
        base = branch.replace("<team>", "").rstrip("-")
        for t in teams.delivery_teams():
            if base.endswith("-" + t):
                base = base[:-(len(t) + 1)]
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


def prompt_for(issue, team_id):
    body = fill_branch(issue.get("description") or "", team_id)
    return "\n".join([
        "Jira %s: %s" % (issue["key"], issue.get("summary") or ""),
        "Source: the ticket description, dispatched by the Thebes Ready dispatcher (D-042).",
        "Every commit message starts with `%s:`." % issue["key"],
        "",
        body,
    ])


def _label(jira, key, labels, add):
    if add in labels:
        return
    jira.update_issue(key, {"labels": list(labels) + [add]})


def _request_brief(issue, problems, jira, state_store, dispatch, now, comment=True):
    """One comment + label; one brief request to ops if an ops team is free. Labels are
    the state: `needs-brief` (incomplete) and `brief-requested` (a PO has been asked)."""
    key = issue["key"]
    if comment:
        jira.add_comment(key, "Thebes Ready dispatcher: this ticket is in Ready but its brief "
                              "is incomplete, so it was not dispatched.\n\nMissing: %s\n\nA "
                              "PO writes the brief into the description and removes the `%s` "
                              "label; the ticket is then picked up automatically."
                         % ("; ".join(problems), NEEDS_BRIEF))
    labels = list(issue.get("labels") or [])
    _label(jira, key, labels, NEEDS_BRIEF)
    labels = labels if NEEDS_BRIEF in labels else labels + [NEEDS_BRIEF]
    tid, sid = free_team("ops", state_store)
    if not tid:
        return {"key": key, "action": "needs-brief", "problems": problems, "ops": "none-free"}
    text = "\n".join([
        "THEBES_BRIEF_REQUEST %s" % key,
        "Ticket %s is in Ready without a complete brief. Run po as a subagent to write it." % key,
        "Read the ticket and the code it concerns. Rewrite the Jira description so it carries, "
        "one per line: GOAL, BRANCH (`<base>-<team>`, e.g. alpha-<team>), ALLOWED PATHS, "
        "FORBIDDEN, DECISIONS MADE, IF BLOCKED, CHECKS (`C1 | run | <flutter/dart test or "
        "analyze command> | exit 0`, or `| judge |` only where an eye must decide). Keep the "
        "acceptance criteria. Check every path and command exists on the base branch.",
        "Validate before saving: python3 -m agent.execution.dispatch_brief lint --file <draft> "
        "--team <any team id>",
        "Then remove the label `%s`. Do not change the status; do not implement anything."
        % NEEDS_BRIEF,
        "Missing now: %s" % "; ".join(problems),
    ])
    out = dispatch(text, sid, ticket=None, lane_capability=None)
    _label(jira, key, labels, BRIEF_REQUESTED)
    return {"key": key, "action": "needs-brief", "problems": problems,
            "ops": tid, "dispatch_id": out.get("dispatch_id")}


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

    done = []
    open_keys = {r.get("jira_key") for r in open_dispatches(state_store)}
    code_open = sum(1 for r in open_dispatches(state_store)
                    if teams.read().get(r.get("target_seat_id"), {}).get("lane", "code") == "code")
    for issue_raw in jira.search_issues(JQL, fields=FIELDS, limit=50, raw=True):
        issue = jira.normalize_issue(issue_raw)
        key = issue["key"]
        if key in open_keys:
            continue
        if NEEDS_BRIEF in issue["labels"]:
            # Waiting for a PO; the labels are the state. Ask once an ops team exists.
            if BRIEF_REQUESTED not in issue["labels"] and free_team("ops", state_store)[0]:
                done.append(_request_brief(issue, ["see the earlier Thebes comment"], jira,
                                           state_store, send, now, comment=False))
            continue
        waiting = blockers((issue_raw.get("fields") or {}).get("issuelinks"), jira)
        if waiting:
            done.append({"key": key, "action": "waiting", "blocked_by": waiting})
            continue
        cap = capability_of(issue, state_store)
        if not cap:
            done.append(dict(_request_brief(issue, ["capability: unknown — add label "
                                                    "`cap:<capability>` or record it with "
                                                    "agent.state.ready"], jira, state_store,
                                            send, now)))
            continue
        task = state_store.read("task", key)
        if task:
            why = state_store.intervention_blocks_claim(key, cap)
            if why:
                done.append({"key": key, "action": "held", "reason": why})
                continue
        lane = lane_of(issue, cap)
        if lane == "code" and code_open >= MAX_PARALLEL:
            done.append({"key": key, "action": "waiting", "reason": "max-parallel"})
            continue
        tid, sid = free_team(lane, state_store)
        if not tid:
            done.append({"key": key, "action": "waiting", "reason": "no-free-%s-team" % lane})
            continue
        text = prompt_for(issue, tid)
        try:
            dispatch_brief.lint(text, tid)
        except dispatch_brief.BriefError as exc:
            done.append(_request_brief(issue, exc.problems, jira, state_store, send, now))
            continue
        try:
            out = send(text, sid, key, cap)
        except cd.Refused as exc:
            done.append({"key": key, "action": "refused", "code": exc.code,
                         "error": str(exc)[:300]})
            continue
        open_keys.add(key)
        if lane == "code":
            code_open += 1
        done.append({"key": key, "action": "dispatched", "team": tid,
                     "dispatch_id": out.get("dispatch_id")})
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
