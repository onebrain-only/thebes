"""Operator command line for the Thebes Listener.

    python3 -m agent.listener serve                  # run the Listener
    python3 -m agent.listener health                 # probe a running Listener
    python3 -m agent.listener submit KAN-183         # send one EXECUTE_WORK_ITEM
    python3 -m agent.listener decide <intent-id> ... # answer one waiting intent
    python3 -m agent.listener session-dispatch KAN-183   # prepare for a bound session
    python3 -m agent.listener session-outcome KAN-183 --dispatch <id> --outcome <o> ...
    python3 -m agent.listener show <intent-id>       # durable intent + result
    python3 -m agent.listener status                 # every intent's delivery state

`submit`, `decide`, `health` and `show` speak to a RUNNING Listener over
loopback HTTP. Since Phase 4 this is the normal operational front door for a
CEO or a controller conversation — but it is still only a client: it builds
exactly the same envelope any caller would POST, and it has no access to
Persistent State, Jira or a provider.

`--wait` blocks until the intent settles, so a controller can ask a question and
read its answer instead of busy-polling. It is the CLIENT'S patience and nothing
more: it adds no server surface, holds no authority, and a caller that gives up
waiting loses nothing, because the answer is durable and `show` returns it.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

from agent.core import lifecycle
from agent.listener import contract, server, store


# Slow enough to be free when idle, fast enough that a short refusal feels
# immediate. A settled intent is durable either way.
POLL_SECONDS = 0.5


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
    send.add_argument("--wait", type=float, nargs="?", const=1800.0, default=None,
                      metavar="SECONDS",
                      help="block until the intent settles, then print its result")
    check = sub.add_parser("validate",
                           help="submit one VALIDATE_WORK_ITEM intent: dispatch an "
                                "already-open review context to its recorded owner")
    check.add_argument("work_item_id")
    check.add_argument("--idempotency-key", default=None,
                       help="resubmitting with the same key is harmless by design")
    check.add_argument("--actor", default="ceo")
    check.add_argument("--source", default="listener-cli")
    check.add_argument("--wait", type=float, nargs="?", const=1800.0, default=None,
                       metavar="SECONDS",
                       help="block until the intent settles, then print its result")
    answer = sub.add_parser("decide", help="answer one WAITING_INPUT intent")
    answer.add_argument("responds_to", help="the waiting intent's id")
    answer.add_argument("--invocation", required=True)
    answer.add_argument("--permission", required=True)
    answer.add_argument("--scope", required=True)
    answer.add_argument("--operation", default=None)
    answer.add_argument("--idempotency-key", default=None)
    answer.add_argument("--actor", default="ceo")
    answer.add_argument("--source", default="listener-cli")
    answer.add_argument("--wait", type=float, nargs="?", const=1800.0, default=None,
                        metavar="SECONDS",
                        help="block until the decision settles, then print its result")
    prep = sub.add_parser("session-dispatch",
                          help="submit one PREPARE_SESSION_DISPATCH intent: prepare a "
                               "work item for its bound persistent session")
    prep.add_argument("work_item_id")
    prep.add_argument("--deliver", action="store_true",
                      help="also hand the packet to the bound session and return at once")
    prep.add_argument("--idempotency-key", default=None,
                      help="resubmitting with the same key is harmless by design")
    prep.add_argument("--actor", default="ceo")
    prep.add_argument("--source", default="listener-cli")
    prep.add_argument("--wait", type=float, nargs="?", const=1800.0, default=None,
                      metavar="SECONDS",
                      help="block until the intent settles, then print its result")
    report = sub.add_parser("session-outcome",
                            help="submit one RECORD_SESSION_OUTCOME intent")
    report.add_argument("work_item_id")
    report.add_argument("--dispatch", required=True)
    report.add_argument("--outcome", required=True)
    report.add_argument("--summary", required=True)
    report.add_argument("--session-id", default=None)
    report.add_argument("--reference", default=None)
    report.add_argument("--delivery-id", default=None)
    report.add_argument("--idempotency-key", default=None)
    report.add_argument("--actor", default="ceo")
    report.add_argument("--source", default="listener-cli")
    report.add_argument("--wait", type=float, nargs="?", const=1800.0, default=None,
                        metavar="SECONDS",
                        help="block until the intent settles, then print its result")
    ask = sub.add_parser("primary-command",
                         help="send one command to the ACTIVE Primary; --wait returns its "
                              "reply (that one turn only, never a worker)")
    ask.add_argument("text")
    ask.add_argument("--idempotency-key", default=None)
    ask.add_argument("--actor", default="ceo")
    ask.add_argument("--source", default="listener-cli")
    ask.add_argument("--wait", type=float, nargs="?", const=900.0, default=None,
                     metavar="SECONDS",
                     help="block until the Primary's turn settles, then print its result")
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
    elif args.command in ("submit", "validate"):
        key = args.idempotency_key or "%s-%s-%s" % (args.command, args.work_item_id,
                                                    uuid.uuid4())
        status, body = _post(args.port, "/intents", {
            "schema_version": contract.SCHEMA_VERSION,
            "intent_type": (contract.EXECUTE_WORK_ITEM if args.command == "submit"
                            else contract.VALIDATE_WORK_ITEM),
            "source": args.source, "actor": args.actor,
            "idempotency_key": key, "correlation_id": key,
            "payload": {"work_item_id": args.work_item_id}})
    elif args.command == "session-dispatch":
        key = args.idempotency_key or "session-dispatch-%s-%s" % (args.work_item_id,
                                                                  uuid.uuid4())
        payload = {"work_item_id": args.work_item_id}
        if args.deliver:
            payload["deliver"] = True
        # A Codex conversation dispatching from its own tool shell carries its
        # thread id in the environment Codex set; it is read here, never typed,
        # so the reply goes back to the conversation that actually dispatched.
        if os.environ.get("CODEX_THREAD_ID"):
            payload["origin_thread_id"] = os.environ["CODEX_THREAD_ID"]
        status, body = _post(args.port, "/intents", {
            "schema_version": contract.SCHEMA_VERSION,
            "intent_type": contract.PREPARE_SESSION_DISPATCH,
            "source": args.source, "actor": args.actor,
            "idempotency_key": key, "correlation_id": key,
            "payload": payload})
    elif args.command == "primary-command":
        key = args.idempotency_key or "primary-command-%s" % uuid.uuid4()
        status, body = _post(args.port, "/intents", {
            "schema_version": contract.SCHEMA_VERSION,
            "intent_type": contract.PRIMARY_COMMAND,
            "source": args.source, "actor": args.actor,
            "idempotency_key": key, "correlation_id": key,
            "payload": {"text": args.text}})
    elif args.command == "session-outcome":
        # The dispatch id makes a repeated report of the same outcome the same
        # intent; a different outcome for one dispatch is refused by the store.
        key = args.idempotency_key or "session-outcome-%s-%s" % (args.dispatch, args.outcome)
        payload = {"work_item_id": args.work_item_id, "dispatch_id": args.dispatch,
                   "outcome": args.outcome, "summary": args.summary}
        if args.session_id:
            payload["session_id"] = args.session_id
        if args.reference:
            payload["reference"] = args.reference
        if args.delivery_id:
            payload["delivery_id"] = args.delivery_id
        status, body = _post(args.port, "/intents", {
            "schema_version": contract.SCHEMA_VERSION,
            "intent_type": contract.RECORD_SESSION_OUTCOME,
            "source": args.source, "actor": args.actor,
            "idempotency_key": key, "correlation_id": key, "payload": payload})
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
    if (getattr(args, "wait", None) and status and 200 <= status < 300
            and body.get("intent_id")):
        status, body = _await_settlement(args.port, body["intent_id"], args.wait)
    print(json.dumps({"http_status": status, "body": body}, indent=2, sort_keys=True))
    return 0 if status and 200 <= status < 300 else 1


def _await_settlement(port, intent_id, timeout):
    """Poll one intent until it settles, or until the caller's patience runs out.

    A timeout is not a failure of the work — the intent is durable and still
    being dispatched. It says only that this client stopped watching, and it
    says so in those words rather than inventing an outcome.
    """
    deadline = time.time() + timeout
    while True:
        status, body = _get(port, "/intents/%s" % intent_id)
        if status != 200:
            return status, body
        if body.get("intent", {}).get("lifecycle_state") in lifecycle.TERMINAL_STATES:
            return status, body
        if body.get("intent", {}).get("lifecycle_state") == lifecycle.INDETERMINATE:
            # Nothing is progressing and nothing will retry it. Waiting longer
            # would only be a longer silence, and the answer already carries the
            # canonical state a human needs to settle it.
            return status, body
        if time.time() >= deadline:
            return status, {"intent_id": intent_id, "waited_seconds": timeout,
                            "lifecycle_state": body.get("intent", {}).get("lifecycle_state"),
                            "detail": "still in flight; this client stopped waiting. "
                                      "The intent is durable — read it with `show`."}
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
