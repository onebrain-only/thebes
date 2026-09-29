"""A narrow, bearer-authenticated, loopback-only gateway to PRIMARY_COMMAND.

The Listener (127.0.0.1:8787) accepts every allow-listed intent and trusts
loopback. This gateway exists so ONE of those intents can be reached from a
remote device through a tunnel pointed at the gateway — never at the Listener.
Its entire surface:

    POST /primary-command   {"message": "<text>"}   Authorization: Bearer <token>

Nothing else: no other path, no other method, no other intent, no shell, no
Jira, no Product, no worker or session endpoint. A valid request becomes one
PRIMARY_COMMAND intent posted to the local Listener (the same durable record,
the same Primary serialization); the gateway returns the intent id and, after
a short bounded wait, the Listener's canonical answer for it.

Security properties, each tested:
  * binds 127.0.0.1 only;
  * token: 256-bit random, generated once into a 0600 file under the gitignored
    Listener runtime dir, compared with hmac.compare_digest, never logged,
    never echoed;
  * no Authorization header -> 401; wrong token -> 403 (same body either way);
  * body > 8 KiB -> 413; non-JSON / wrong shape / empty or control-char
    message -> 400;
  * simple fixed-window rate limit -> 429;
  * the access log is silenced so no request line or header is ever printed.

    python3 -m agent.listener.gateway serve [--port 8788]
    python3 -m agent.listener.gateway token-path
"""
import argparse
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNTIME = os.path.join(ROOT, "agent", "listener", "runtime")
TOKEN_PATH = os.path.join(RUNTIME, "gateway.token")
HOST = "127.0.0.1"
DEFAULT_PORT = 8788
LISTENER_URL = "http://127.0.0.1:8787"
MAX_BODY = 8 * 1024
MAX_MESSAGE = 4000
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS = 6
ANSWER_WAIT_SECONDS = 20
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
ACTOR = "ceo-remote"
SOURCE = "primary-gateway"


def load_or_create_token(path=TOKEN_PATH):
    """Read the gateway token, creating it (0600) on first use. Never printed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        token = secrets.token_urlsafe(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(token)
    os.chmod(path, 0o600)
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


class RateLimit:
    def __init__(self, limit=RATE_MAX_REQUESTS, window=RATE_WINDOW_SECONDS, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.stamps, self.lock = [], threading.Lock()

    def allow(self):
        now = self.clock()
        with self.lock:
            self.stamps = [t for t in self.stamps if now - t < self.window]
            if len(self.stamps) >= self.limit:
                return False
            self.stamps.append(now)
            return True


def listener_submit(message, listener_url=LISTENER_URL, wait=ANSWER_WAIT_SECONDS):
    """Post ONE PRIMARY_COMMAND to the local Listener; bounded wait for its answer."""
    key = "primary-gateway-%s" % uuid.uuid4()
    body = json.dumps({"schema_version": 1, "intent_type": "PRIMARY_COMMAND",
                       "source": SOURCE, "actor": ACTOR, "idempotency_key": key,
                       "correlation_id": key, "payload": {"text": message}}).encode()
    req = urllib.request.Request(listener_url + "/intents", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            accepted = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, {"reason": "listener-refused", "detail": json.loads(exc.read() or b"{}")}
    except OSError:
        return 503, {"reason": "listener-unreachable"}
    intent_id = accepted.get("intent_id")
    answer = None
    if intent_id:
        try:
            with urllib.request.urlopen(listener_url + "/intents/%s/wait?timeout=%s"
                                        % (intent_id, wait), timeout=wait + 10) as resp:
                answer = json.loads(resp.read().decode())
        except OSError:
            pass
    result = (answer or {}).get("result") or {}
    controller = (result.get("outcome") or {}).get("result") or {}
    return 202, {"intent_id": intent_id,
                 "lifecycle_state": ((answer or {}).get("intent") or {}).get("lifecycle_state"),
                 "primary_command_id": controller.get("primary_command_id"),
                 "status": controller.get("status"), "turn_ref": controller.get("turn_ref"),
                 "response_summary": controller.get("response_summary"),
                 "error": controller.get("error")}


def make_handler(token, submit=listener_submit, limiter=None):
    limiter = limiter or RateLimit()
    expected = ("Bearer " + token).encode()

    class Handler(BaseHTTPRequestHandler):
        server_version = "ThebesPrimaryGateway/1"
        sys_version = ""

        def log_message(self, *args):                     # never print request lines/headers
            pass

        def _reply(self, code, body):
            data = json.dumps(body, sort_keys=True).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _refuse_method(self):
            self._reply(405 if self.path == "/primary-command" else 404, {"reason": "not-found"})

        do_GET = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _refuse_method

        def do_POST(self):
            if self.path != "/primary-command":
                return self._reply(404, {"reason": "not-found"})
            header = self.headers.get("Authorization")
            if not header:
                return self._reply(401, {"reason": "unauthorized"})
            if not hmac.compare_digest(header.encode(), expected):
                return self._reply(403, {"reason": "unauthorized"})
            if not limiter.allow():
                return self._reply(429, {"reason": "rate-limited"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._reply(400, {"reason": "bad-request"})
            if length <= 0 or length > MAX_BODY:
                return self._reply(413 if length > MAX_BODY else 400, {"reason": "bad-size"})
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._reply(400, {"reason": "bad-json"})
            if not isinstance(payload, dict) or set(payload) != {"message"}:
                return self._reply(400, {"reason": "body-must-be-exactly-message"})
            message = payload["message"]
            if (not isinstance(message, str) or not message.strip()
                    or len(message) > MAX_MESSAGE or CONTROL.search(message)):
                return self._reply(400, {"reason": "bad-message"})
            code, body = submit(message)
            return self._reply(code, body)

    return Handler


def build(port=DEFAULT_PORT, token=None, submit=listener_submit, limiter=None):
    return ThreadingHTTPServer((HOST, port), make_handler(token or load_or_create_token(),
                                                          submit, limiter))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.listener.gateway", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub.add_parser("token-path")
    ns = ap.parse_args(argv)
    if ns.cmd == "token-path":
        load_or_create_token()
        print(TOKEN_PATH)
        return 0
    httpd = build(ns.port)
    print("thebes primary gateway on http://%s:%d (loopback only; POST /primary-command)"
          % (HOST, ns.port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
