"""Order gate (D-044) — PreToolUse / PostToolUse for Thebes-bound sessions.

Two acts need an explicit CEO order lifted with `python3 -m agent.execution.orders grant`:

    create        an Epic, or a ticket that serves no existing one: the Atlassian createJiraIssue
                  tool (any MCP server name), or a shell call into agent.integrations.jira's
                  create_issue. D-046: a non-Epic whose parent or summary names the KAN ticket it
                  supports goes through without an order, ledgered as `supports-KAN-N`.
    promote-alpha a push to Alpha / alpha-ds (D-052: Alpha is the customer trial, moved only as a
                  promotion of staging the CEO chose). Allowed only while a promote-alpha grant
                  is open; each push spends one unit. An open integration dispatch does NOT allow it.

A push to `staging` (the internal integrate-and-test branch, both repos) needs no CEO order but
needs an open integration dispatch (D-046: review-passed work integrates on its own); outside
one it is refused, so staging only ever receives verified, integrated work.

D-046 also refuses CronCreate / ScheduleWakeup from the orchestrator: it is woken by its inbox
(the watchdog probes for free), never by a poll it schedules for itself.

and the order records themselves (ceo-messages.jsonl, order-grants.json, action-ledger.jsonl) are
written only by code: a Write/Edit to them, or a shell command that names them and is not a plain
read, is refused, so an order cannot be forged.

Only sessions bound to the orchestrator or a team are gated (policy_hook.bound). An unbound
session is the CEO at his own keyboard. Any failure here is silent: exit 0, no opinion — the
same fail-open rule as branch-guard.sh, because a gate that crashes must not freeze the company.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

CREATE_TOOL = re.compile(r"^mcp__.*atlassian.*__createJiraIssue$", re.I)
SHELL_CREATE = re.compile(r"\bcreate_issue\s*\(")
ALPHA_REFS = ("Alpha", "alpha-ds")
STAGING_REFS = ("staging",)
READ_ONLY = re.compile(r"^\s*(cat|tail|head|grep|wc|jq|less)\b")
KAN = re.compile(r"\bKAN-\d+\b")
POLL_TOOLS = ("CronCreate", "ScheduleWakeup")


def _order_files():
    from agent.execution import orders
    return tuple(orders.FILES.values())


def _deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def _integration_open(state_store):
    return any(r.get("integrates_base") and r.get("status") in state_store.CONVERSATION_DISPATCH_OPEN
               for r in state_store.read_all("conversation_dispatch"))


def _push_targets(command):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "branch_guard", os.path.join(ROOT, "agent", "state", "branch_guard.py"))
    bg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bg)
    return bg.push_targets(command)


def _alpha_targets(command):
    return [t for t in _push_targets(command) if t in ALPHA_REFS]


def _staging_targets(command):
    return [t for t in _push_targets(command) if t in STAGING_REFS]


def pre(payload, seat, state_store, now=None):
    from agent.execution import orders
    tool = payload.get("tool_name") or ""
    args = payload.get("tool_input") or {}
    sid = payload.get("session_id")

    if tool in POLL_TOOLS and seat == "orchestrator":
        orders.log("refused-poll", seat, sid=sid, rule="D-046", detail=tool,
                   state_store=state_store, now=now)
        return _deny("The orchestrator does not poll (D-046). The watchdog probes every team "
                     "for free and wakes you through your inbox when something changes; with "
                     "nothing in the inbox, stop and wait. Delete any cron you already made "
                     "(CronList, CronDelete).")

    if CREATE_TOOL.match(tool) or (tool == "Bash" and SHELL_CREATE.search(args.get("command") or "")):
        extra = (args.get("additional_fields") or {}).get("parent")
        parent = args.get("parent") or (extra.get("key") if isinstance(extra, dict) else extra)
        served = orders.supports(issue_type=args.get("issueTypeName"), parent=parent,
                                 summary=args.get("summary") or "") if tool != "Bash" else None
        if served:
            orders.log("create-allowed", seat, sid=sid, rule="supports-%s" % served,
                       detail=(args.get("summary") or "")[:200], state_store=state_store, now=now)
            return None
        g = orders.consume("create", state_store=state_store, now=now)
        if g is None:
            orders.log("refused-create", seat, sid=sid, rule="D-044",
                       detail=(args.get("summary") or args.get("command") or "")[:200],
                       state_store=state_store, now=now)
            return _deny(orders.refusal("create"))
        orders.log("create-allowed", seat, order_ref=g["id"], sid=sid,
                   detail=(args.get("summary") or "")[:200], state_store=state_store, now=now)
        return None

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        p = args.get("file_path") or args.get("notebook_path") or ""
        if os.path.basename(p) in _order_files():
            return _deny("%s is written only by Thebes code (D-044); an order cannot be edited "
                         "by hand." % os.path.basename(p))
        return None

    if tool != "Bash":
        return None
    cmd = args.get("command") or ""
    if any(f in cmd for f in _order_files()) and (not READ_ONLY.match(cmd) or ">" in cmd):
        return _deny("The CEO order records are written only by Thebes code (D-044). Read them "
                     "with `python3 -m agent.execution.orders open|log|messages`.")
    if _alpha_targets(cmd):
        g = orders.consume("promote-alpha", state_store=state_store, now=now)
        if g is None:
            orders.log("refused-promote", seat, sid=sid, rule="D-052", detail=cmd[:200],
                       state_store=state_store, now=now)
            return _deny(orders.refusal("promote-alpha"))
        orders.log("promote-allowed", seat, order_ref=g["id"], sid=sid, detail=cmd[:200],
                   state_store=state_store, now=now)
    if _staging_targets(cmd) and not _integration_open(state_store):
        orders.log("refused-staging", seat, sid=sid, rule="D-052", detail=cmd[:200],
                   state_store=state_store, now=now)
        return _deny("A push to staging needs an open integration dispatch (D-052): staging only "
                     "receives verified work that Thebes sent to integrate. Push your own team "
                     "branch (staging-<team>) instead; Thebes integrates it once it passes review.")
    return None


def post(payload, seat, state_store, now=None):
    from agent.execution import orders
    tool = payload.get("tool_name") or ""
    resp = payload.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    if CREATE_TOOL.match(tool):
        keys = KAN.findall(text or "")
        args = payload.get("tool_input") or {}
        last = (orders.recent(1, state_store=state_store) or [{}])[-1]
        orders.log("created", seat, key=keys[0] if keys else None, sid=payload.get("session_id"),
                   order_ref=last.get("order_ref"), rule=last.get("rule"),
                   detail=(args.get("issueTypeName") or "") + ": " + (args.get("summary") or ""),
                   state_store=state_store, now=now)
    elif tool == "Bash":
        cmd = (payload.get("tool_input") or {}).get("command") or ""
        if _alpha_targets(cmd):
            orders.log("pushed-alpha", seat, sid=payload.get("session_id"), rule="promote-alpha",
                       detail=cmd[:200], state_store=state_store, now=now)
        if _staging_targets(cmd):
            orders.log("pushed-staging", seat, sid=payload.get("session_id"),
                       rule="integration-dispatch", detail=cmd[:200],
                       state_store=state_store, now=now)
    return None


def retired(payload, state_store):
    """A retired orchestrator session acts on nothing: the live one owns every decision now."""
    from agent.execution import orders
    if payload.get("hook_event_name") != "PreToolUse":
        return None
    live = orders.retired_orchestrator(payload.get("session_id"), state_store)
    if not live:
        return None
    tool = payload.get("tool_name") or ""
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if tool == "Bash" and READ_ONLY.match(cmd) and ">" not in cmd:
        return None
    if tool in ("Read", "Grep", "Glob"):
        return None
    return _deny("This orchestrator session is retired; the live one is %s and owns every "
                 "dispatch, edit and Jira or git act (D-044). Tell the CEO to continue in "
                 "thebes-orchestrator (%s); his message here is already recorded for it."
                 % (live[:8], live[:8]))


def handle(payload, state_store=None, now=None):
    import policy_hook
    if state_store is None:
        from agent.state import store as state_store
    who = policy_hook.bound(payload.get("session_id"), state_store)
    if not who:
        return retired(payload, state_store)
    fn = pre if payload.get("hook_event_name") == "PreToolUse" else post
    return fn(payload, who[0], state_store, now)


def main():
    try:
        out = handle(json.load(sys.stdin))
    except Exception:                                     # noqa: BLE001
        return 0
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
