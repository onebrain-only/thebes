#!/usr/bin/env python3
"""A scripted stand-in for ``codex app-server`` over stdio, for tests only.

Answers initialize/account/config/model/resume/start with canned results,
emits one approval request (which the client must decline), one agentMessage
for the started turn, one for a DIFFERENT turn (which must be ignored), and
turn/completed. Exits on stdin EOF like the real thing.
"""
import json
import sys

THREAD = "01a0e382-98e9-70b2-84df-c757e3c6c517"
TURN = "01a0e738-7d60-71e2-b052-a4bfa80000a0"


def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    msg = json.loads(line)
    method, rid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if method == "initialize":
        out({"id": rid, "result": {"userAgent": "fake"}})
    elif method == "initialized":
        continue
    elif method == "account/read":
        out({"id": rid, "result": {"account": {"type": "chatgpt", "planType": "plus"}}})
    elif method == "config/read":
        out({"id": rid, "result": {"config": {
            "openai_base_url": "https://chatgpt.com/backend-api/codex",
            "model_catalog_json": sys.argv[1] if len(sys.argv) > 1 else None}}})
    elif method == "model/list":
        out({"id": rid, "result": {"data": [{"id": "gpt-6-astra", "isDefault": True, "hidden": False}]}})
    elif method == "thread/resume":
        out({"id": rid, "result": {"thread": {"id": params.get("threadId")}}})
    elif method == "turn/start":
        out({"id": rid, "result": {"turn": {"id": TURN, "status": "inProgress"}}})
        out({"method": "turn/started", "params": {"threadId": THREAD, "turn": {"id": TURN}}})
        out({"id": 900, "method": "item/commandExecution/requestApproval",
             "params": {"threadId": THREAD, "turnId": TURN, "itemId": "cmd-1"}})
    elif rid == 900:
        # The client's answer to the approval request: must be a decline.
        out({"method": "item/completed", "params": {"threadId": THREAD, "turnId": "other-turn",
             "item": {"type": "agentMessage", "id": "m0", "text": "NOT THIS TURN"}}})
        out({"method": "item/completed", "params": {"threadId": THREAD, "turnId": TURN,
             "item": {"type": "agentMessage", "id": "m1",
                      "text": "decision=%s" % (msg.get("result") or {}).get("decision")}}})
        out({"method": "turn/completed", "params": {"threadId": THREAD, "turn": {
            "id": TURN, "status": "completed", "error": None}}})
    else:
        out({"id": rid, "error": {"code": -32601, "message": "fake: unknown %s" % method}})
