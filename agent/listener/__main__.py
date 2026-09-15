"""Operator command line for the Thebes Listener.

    python3 -m agent.listener serve                  # run the Listener
    python3 -m agent.listener health                 # probe a running Listener
    python3 -m agent.listener submit KAN-183         # send one EXECUTE_WORK_ITEM
    python3 -m agent.listener decide <intent-id> ... # answer one waiting intent
    python3 -m agent.listener show <intent-id>       # durable intent + result
    python3 -m agent.listener status                 # every intent's delivery state

`submit`, `decide`, `health` and `show` speak to a RUNNING Listener over
loopback HTTP. They are a convenience for a human at a terminal, not a second
entry point: they build exactly the same envelope any caller would POST, and
they have no access to Persistent State, Jira or a provider.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

from agent.listener import contract, server, store


def _url(port, path):
    return "http://%s:%d%s" % (server.HOST, port, path)


def _get(port, path):
    try:
        with urllib.request.urlopen(_url(port, path), timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except OSError as exc:
        return None, {"reason": "listener-unreachable", "detail": str(exc)}


def _post(port, path, body):
    request = urllib.request.Request(
        _url(port, path), data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except OSError as exc:
        return None, {"reason": "listener-unreachable", "detail": str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m agent.listener")
    parser.add_argument("--port", type=int, default=server.DEFAULT_PORT)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("serve", help="run the Listener process (loopback only)")
    run.add_argument("--idle-wait", type=float, default=server.IDLE_WAIT_SECONDS)
    sub.add_parser("health", help="probe a running Listener")
    sub.add_parser("status", help="delivery state of every recorded intent")
    send = sub.add_parser("submit", help="submit one EXECUTE_WORK_ITEM intent")
    send.add_argument("work_item_id")
    send.add_argument("--idempotency-key", default=None,
                      help="resubmitting with the same key is harmless by design")
    send.add_argument("--actor", default="ceo")
    send.add_argument("--source", default="listener-cli")
    answer = sub.add_parser("decide", help="answer one WAITING_INPUT intent")
    answer.add_argument("responds_to", help="the waiting intent's id")
    answer.add_argument("--invocation", required=True)
    answer.add_argument("--permission", required=True)
    answer.add_argument("--scope", required=True)
    answer.add_argument("--operation", default=None)
    answer.add_argument("--idempotency-key", default=None)
    answer.add_argument("--actor", default="ceo")
    answer.add_argument("--source", default="listener-cli")
    show = sub.add_parser("show", help="one intent and its durable result")
    show.add_argument("intent_id")
    args = parser.parse_args(argv)

    if args.command == "serve":
        return server.serve(args.port, args.idle_wait)
    if args.command == "health":
        status, body = _get(args.port, "/health")
    elif args.command == "status":
        status, body = _get(args.port, "/intents")
    elif args.command == "show":
        status, body = _get(args.port, "/intents/%s" % args.intent_id)
    elif args.command == "submit":
        key = args.idempotency_key or "submit-%s-%s" % (args.work_item_id, uuid.uuid4())
        status, body = _post(args.port, "/intents", {
            "schema_version": contract.SCHEMA_VERSION,
            "intent_type": contract.EXECUTE_WORK_ITEM,
            "source": args.source, "actor": args.actor,
            "idempotency_key": key, "correlation_id": key,
            "payload": {"work_item_id": args.work_item_id}})
    else:
        waiting = store.read_intent(args.responds_to) or {}
        work_item_id = (waiting.get("payload") or {}).get("work_item_id")
        if not work_item_id:
            print(json.dumps({"reason": "unknown-decision-reference",
                              "responds_to": args.responds_to}, indent=2))
            return 1
        key = args.idempotency_key or "decide-%s-%s" % (args.invocation, args.permission)
        status, body = _post(args.port, "/intents", {
            "schema_version": contract.SCHEMA_VERSION,
            "intent_type": contract.DECISION_RESPONSE,
            "source": args.source, "actor": args.actor,
            "idempotency_key": key,
            "correlation_id": waiting.get("correlation_id") or key,
            "responds_to": args.responds_to,
            "payload": {"work_item_id": work_item_id, "decision": "approve",
                        "original_invocation_id": args.invocation,
                        "permission": args.permission,
                        "approval_scope": args.scope,
                        **({"allowed_operation": args.operation} if args.operation else {})}})
    print(json.dumps({"http_status": status, "body": body}, indent=2, sort_keys=True))
    return 0 if status and 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
