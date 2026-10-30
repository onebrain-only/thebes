"""Order gate (D-044) — PreToolUse / PostToolUse for Thebes-bound sessions.

Two acts need an explicit CEO order lifted with `python3 -m agent.execution.orders grant`:

    create        a Jira ticket or Epic: the Atlassian createJiraIssue tool (any MCP server name),
                  or a shell call into agent.integrations.jira's create_issue
    merge-alpha   a push to Alpha / alpha-ds. Allowed when a merge-alpha grant is open, or while an
                  integration dispatch is open (integrate.dispatch_for already required the grant)

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
READ_ONLY = re.compile(r"^\s*(cat|tail|head|grep|wc|jq|less)\b")
KAN = re.compile(r"\bKAN-\d+\b")


def _order_files():
    from agent.execution import orders
    return tuple(orders.FILES.values())


def _deny(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def _integration_open(state_store):
    return any(r.get("integrates_base") and r.get("status") in state_store.CONVERSATION_DISPATCH_OPEN
               for r in state_store.read_all("conversation_dispatch"))


def _alpha_targets(command):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "branch_guard", os.path.join(ROOT, "agent", "state", "branch_guard.py"))
    bg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bg)
    return [t for t in bg.push_targets(command) if t in ALPHA_REFS]


def pre(payload, seat, state_store, now=None):
    from agent.execution import orders
    tool = payload.get("tool_name") or ""
    args = payload.get("tool_input") or {}
    sid = payload.get("session_id")

    if CREATE_TOOL.match(tool) or (tool == "Bash" and SHELL_CREATE.search(args.get("command") or "")):
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
    hit = _alpha_targets(cmd)
    if hit:
        g = orders.covering("merge-alpha", state_store=state_store, now=now)
        if g is None and not _integration_open(state_store):
            orders.log("refused-merge", seat, sid=sid, rule="D-044", detail=cmd[:200],
                       state_store=state_store, now=now)
            return _deny(orders.refusal("merge-alpha"))
    return None


def post(payload, seat, state_store, now=None):
    from agent.execution import orders
    tool = payload.get("tool_name") or ""
    resp = payload.get("tool_response")
    text = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    if CREATE_TOOL.match(tool):
        keys = KAN.findall(text or "")
        args = payload.get("tool_input") or {}
        orders.log("created", seat, key=keys[0] if keys else None, sid=payload.get("session_id"),
                   order_ref=(orders.recent(1, state_store=state_store) or [{}])[-1].get("order_ref"),
                   detail=(args.get("issueTypeName") or "") + ": " + (args.get("summary") or ""),
                   state_store=state_store, now=now)
    elif tool == "Bash":
        cmd = (payload.get("tool_input") or {}).get("command") or ""
        hit = _alpha_targets(cmd)
        if hit:
            g = orders.covering("merge-alpha", state_store=state_store, now=now)
            orders.log("pushed-alpha", seat, sid=payload.get("session_id"),
                       order_ref=g["id"] if g else None,
                       rule=None if g else "integration-dispatch", detail=cmd[:200],
                       state_store=state_store, now=now)
    return None


def handle(payload, state_store=None, now=None):
    import policy_hook
    if state_store is None:
        from agent.state import store as state_store
    who = policy_hook.bound(payload.get("session_id"), state_store)
    if not who:
        return None
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
