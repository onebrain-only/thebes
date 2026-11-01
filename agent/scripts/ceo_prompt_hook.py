"""CEO prompt hook (D-044) — UserPromptSubmit and PreCompact, orchestrator session only.

UserPromptSubmit: keeps the CEO's message verbatim (agent/execution/orders.py) and returns the
fact block (agent/state/facts.py) as additionalContext, so every turn answers from state, not
from a memory that has been compacted a hundred times. Wakes, task notifications and messages
from other sessions are not recorded (orders.NOT_CEO) but still get the fact block.

PreCompact: counts compactions of the orchestrator (runtime/compaction/orchestrator-count) so the
watchdog can rotate it to a fresh session (watchdog.rotate_orchestrator).

Any other session, or any failure: silent exit 0. This hook never blocks a prompt.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))


def count_path(state_store):
    return os.path.join(state_store.RUNTIME, "compaction", "orchestrator-count")


def read_count(state_store):
    """{"session_id", "count", "since"} for the bound orchestrator session; count 0 when unknown."""
    try:
        with open(count_path(state_store), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"session_id": None, "count": 0}


def bump_count(session_id, state_store, now=None):
    cur = read_count(state_store)
    if cur.get("session_id") != session_id:
        cur = {"session_id": session_id, "count": 0,
               "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time()))}
    cur["count"] = int(cur.get("count") or 0) + 1
    os.makedirs(os.path.dirname(count_path(state_store)), exist_ok=True)
    with open(count_path(state_store), "w", encoding="utf-8") as fh:
        json.dump(cur, fh)
    return cur


RETIRED = ("THIS SESSION IS RETIRED (D-044 rotation). The live orchestrator is %s; this message "
           "has been recorded for it as CEO message %s and it will act on it. Do not act here: no "
           "dispatch, no edit, no Jira, no git. Reply to the CEO only with this line, verbatim:\n"
           "الجلسة دي اتقفلت. رسالتك وصلت للأوركستريتور الجديد وهو هيتصرف فيها. "
           "كمّل الكلام معاه في جلسة thebes-orchestrator (%s).")


def _retired(payload, sid, state_store, now):
    """The CEO typed into an orchestrator session that was rotated away: keep his words for the
    live one, and tell this session to stand down."""
    from agent.execution import orders
    live = orders.retired_orchestrator(sid, state_store)
    if not live or payload.get("hook_event_name") != "UserPromptSubmit":
        return None
    mid = orders.record_message(sid, payload.get("prompt") or "", state_store=state_store,
                                now=now, retired=True)
    if not mid:
        return None
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                   "additionalContext": RETIRED % (live[:8], mid, live[:8])}}


def handle(payload, state_store=None, now=None):
    """The hook's stdout object, or None to say nothing."""
    import policy_hook
    if state_store is None:
        from agent.state import store as state_store
    sid = payload.get("session_id")
    who = policy_hook.bound(sid, state_store)
    if not who or who[2] != "orchestrator":
        return _retired(payload, sid, state_store, now)
    event = payload.get("hook_event_name")
    if event == "PreCompact":
        bump_count(sid, state_store, now)
        return None
    if event != "UserPromptSubmit":
        return None
    from agent.execution import orders
    from agent.state import facts
    mid = orders.record_message(sid, payload.get("prompt") or "", state_store=state_store, now=now)
    block = facts.build(now)
    if mid:
        block += ("\nThis message is recorded as CEO message %s. If it orders a ticket/Epic to be "
                  "created or work to be merged into Alpha, lift his exact words with "
                  "`python3 -m agent.execution.orders grant` before acting." % mid)
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                   "additionalContext": block}}


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
