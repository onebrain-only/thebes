"""Minimal JSON-RPC stdio client for the installed ``codex app-server``.

This is a transport, not a policy. It launches exactly one app-server child,
speaks the protocol documented by ``codex app-server generate-json-schema``
(codex-cli 0.154.0), and hands raw request/response/notification objects back
to the caller. It never starts a thread, never approves anything, and never
touches ``~/.codex`` beyond what the child process itself reads.

Every message in and out is appended to ``log_path`` as JSONL so a wake leaves
raw evidence behind. The wait for a turn is a process blocking on the JSON-RPC
stream, not a model loop and not a poll: the child pushes notifications and
this client reads them until ``turn/completed`` for the one turn it started.
"""
import collections
import json
import subprocess
import threading
import time

CLIENT_INFO = {"name": "thebes-codex-primary", "version": "0.1"}


class _Inbox:
    """A tiny blocking FIFO. Not the stdlib ``queue`` module on purpose:
    ``agent/state/queue.py`` (capability queues) shadows it whenever
    ``agent/state`` is first on ``sys.path``, which the state-aware callers
    of this client make true."""

    def __init__(self):
        self._items = collections.deque()
        self._cv = threading.Condition()

    def put(self, item):
        with self._cv:
            self._items.append(item)
            self._cv.notify()

    def get(self, timeout):
        """The next item, or None if nothing arrived within ``timeout``."""
        with self._cv:
            if not self._items:
                self._cv.wait(timeout)
            if not self._items:
                return _EMPTY
            return self._items.popleft()


_EMPTY = object()
_EOF = None


class AppServerError(Exception):
    """A JSON-RPC error response, carried with its code and message."""

    def __init__(self, method, error):
        super().__init__("%s: %s" % (method, (error or {}).get("message")))
        self.method = method
        self.error = error or {}


class AppServerTimeout(Exception):
    pass


class CodexAppServerClient:
    """One ``codex app-server`` child over stdio, with a raw JSONL log."""

    def __init__(self, args, log_path, stderr_path=None):
        self._args = list(args)
        self._log = open(log_path, "a", encoding="utf-8")
        stderr = open(stderr_path, "a", encoding="utf-8") if stderr_path else subprocess.DEVNULL
        self._proc = subprocess.Popen(self._args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=stderr, text=True, bufsize=1)
        self._inbox = _Inbox()
        self._next_id = 0
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # -- wire ---------------------------------------------------------------
    def _record(self, direction, obj):
        if self._log.closed:                  # a late frame after close() is not an error
            return
        self._log.write(json.dumps({"ts": time.time(), "dir": direction, "msg": obj}) + "\n")
        self._log.flush()

    def _read_loop(self):
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                obj = {"_raw": line}
            self._record("in", obj)
            self._inbox.put(obj)
        self._inbox.put(_EOF)                      # EOF sentinel

    def send(self, obj):
        self._record("out", obj)
        self._proc.stdin.write(json.dumps(obj) + "\n")
        self._proc.stdin.flush()

    def _decline(self, server_request):
        """Grant nothing. Every approval or input request from the server is
        declined; nothing the model asks for is ever authorized here."""
        method = server_request.get("method", "")
        if "Approval" in method or "requestApproval" in method:
            self.send({"id": server_request["id"], "result": {"decision": "decline"}})
        else:
            self.send({"id": server_request["id"],
                       "error": {"code": -32601, "message": "declined by thebes codex primary adapter"}})

    def request(self, method, params, timeout=60):
        self._next_id += 1
        rid = self._next_id
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._inbox.get(timeout=1)
            if msg is _EMPTY:
                continue
            if msg is _EOF:
                raise AppServerError(method, {"message": "app-server closed the stream"})
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                if "error" in msg:
                    raise AppServerError(method, msg["error"])
                return msg["result"]
            if "method" in msg and "id" in msg:
                self._decline(msg)
        raise AppServerTimeout(method)

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)

    # -- protocol -----------------------------------------------------------
    def initialize(self):
        result = self.request("initialize", {"clientInfo": CLIENT_INFO,
                                             "capabilities": {"experimentalApi": True}})
        self.notify("initialized")
        return result

    def await_turn(self, turn_id, timeout):
        """Consume notifications until ``turn/completed`` for ``turn_id``.

        Returns (completed_turn, agent_messages) where agent_messages are the
        ``agentMessage`` items whose ``turnId`` is exactly this turn. Items from
        earlier turns never count. Server requests are declined as they arrive.
        """
        deadline = time.time() + timeout
        messages = []
        while time.time() < deadline:
            msg = self._inbox.get(timeout=1)
            if msg is _EMPTY:
                continue
            if msg is _EOF:
                raise AppServerError("turn/completed", {"message": "app-server closed the stream"})
            method = msg.get("method")
            if method and "id" in msg:
                self._decline(msg)
                continue
            params = msg.get("params") or {}
            if method == "item/completed" and params.get("turnId") == turn_id:
                item = params.get("item") or {}
                if item.get("type") == "agentMessage":
                    messages.append(item)
            if method == "turn/completed" and (params.get("turn") or {}).get("id") == turn_id:
                return params["turn"], messages
        raise AppServerTimeout("turn/completed")

    def close(self):
        """Clean shutdown on stdin EOF, which releases the thread writer lock."""
        try:
            self._proc.stdin.close()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._log.close()
        return self._proc.returncode
