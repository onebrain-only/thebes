"""The separate Listener process: a loopback intake boundary and its worker.

Phase 3's whole claim is that a CEO instruction can enter Thebes without anyone
invoking the Controller by hand. This is the thing that receives it.

It is a COMMUNICATION boundary and nothing else. It binds 127.0.0.1 only, it
accepts an allow-listed intent, it writes that intent down durably before it
answers, and a worker hands it to the Controller in a separate process. It owns
no Product decision of any kind, and the endpoints below are the complete
surface: there is no endpoint that runs a command, names a seat, selects a
provider, transitions Jira, or grants an authorization.

Since Phase 5 this is Thebes Core's intake subsystem rather than a separate
conceptual product (`MASTER_ROADMAP.md` §37). Nothing about its authority
changed — it still decides nothing — but the answers it gives are now Core's
canonical ones, derived from Persistent State and reconciled against this
process's own delivery records, rather than the delivery record alone.

Endpoints:
    GET  /health           liveness and how much is queued
    POST /intents          submit one intent; durable before it answers
    GET  /intents          canonical lifecycle of every intent, oldest first
    GET  /intents/<id>     one intent's canonical answer and its evidence

Idle cost is a condition wait, not a poll: intake signals the worker directly,
and the timeout below exists only so a restarted or recovered queue still drains
without anyone poking it.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent.core import lifecycle
from agent.listener import contract, dispatch, store


HOST = "127.0.0.1"
DEFAULT_PORT = 8787
# Safety heartbeat only. Every ordinary wake-up comes from intake signalling the
# condition, so an idle Listener does this a handful of times an hour.
IDLE_WAIT_SECONDS = 30.0
LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")


class Worker(threading.Thread):
    """Drains the durable inbox. One intent, one Controller process, once."""

    daemon = True

    def __init__(self, dispatcher=dispatch.dispatch, idle_wait=IDLE_WAIT_SECONDS):
        super().__init__(name="thebes-listener-worker")
        self._dispatch = dispatcher
        self._idle_wait = idle_wait
        self._wake = threading.Condition()
        self._stopping = False
        self.dispatched = []

    def signal(self):
        with self._wake:
            self._wake.notify_all()

    def stop(self):
        with self._wake:
            self._stopping = True
            self._wake.notify_all()

    def drain_once(self):
        """Dispatch everything currently eligible. Returns what it settled."""
        settled = []
        for record in store.pending():
            outcome = self._dispatch(record["intent_id"])
            if outcome is not None:
                settled.append(outcome)
                self.dispatched.append(outcome["intent_id"])
        return settled

    def run(self):
        while True:
            with self._wake:
                if self._stopping:
                    return
            try:
                self.drain_once()
            except Exception as exc:                      # never kill the worker
                print("listener worker error: %s" % exc, flush=True)
            with self._wake:
                if self._stopping:
                    return
                self._wake.wait(self._idle_wait)


class Handler(BaseHTTPRequestHandler):
    server_version = "ThebesListener/1"
    worker = None

    def log_message(self, fmt, *args):                    # quiet by default
        pass

    def _reply(self, code, body):
        payload = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _loopback(self):
        """Defence in depth. The socket is already bound to loopback."""
        if (self.client_address[0] if self.client_address else None) in LOOPBACK:
            return True
        self._reply(403, {"reason": "loopback-only",
                          "detail": "the Thebes Listener accepts local requests only"})
        return False

    def do_GET(self):
        if not self._loopback():
            return
        if self.path == "/health":
            return self._reply(200, {
                "status": "ok", "listener": "thebes-listener",
                "schema_version": contract.SCHEMA_VERSION,
                "intent_types": list(contract.INTENT_TYPES),
                "pending": len(store.pending())})
        if self.path == "/intents":
            return self._reply(200, {"intents": [
                {"intent_id": answer["intent_id"],
                 "intent_type": answer["intent_type"],
                 "correlation_id": answer["correlation_id"],
                 "work_item_id": answer["work_item_id"],
                 "lifecycle_state": answer["lifecycle_state"],
                 "reconciliation": answer["reconciliation"],
                 "received_at": answer["received_at"]}
                for answer in lifecycle.resolve_all()]})
        if self.path.startswith("/intents/"):
            intent_id = self.path[len("/intents/"):]
            answer = lifecycle.resolve(intent_id)
            if answer is None:
                return self._reply(404, {"reason": "unknown-intent", "intent_id": intent_id})
            # The durable replay path: a caller that never saw its answer, or a
            # caller asking again after this process died, gets the recorded
            # result rather than a re-run. Since Phase 5 it also gets the
            # canonical state behind that result, so an unobserved outcome
            # arrives with the facts needed to settle it.
            return self._reply(200, {
                "intent": answer,
                # Kept for callers written against Phase 3/4 and for the audit
                # trail. `intent.lifecycle_state` is the canonical answer; these
                # are the delivery records it was derived from.
                "transport_record": store.read_intent(intent_id),
                "result": store.read_result(intent_id)})
        return self._reply(404, {"reason": "unknown-path"})

    def do_POST(self):
        if not self._loopback():
            return
        if self.path != "/intents":
            return self._reply(404, {"reason": "unknown-path"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._reply(400, {"reason": "malformed-body",
                                     "detail": "Content-Length is not an integer"})
        if length > contract.MAX_BODY_BYTES:
            return self._reply(413, {"reason": "body-too-large",
                                     "detail": "intake body exceeds %d bytes"
                                               % contract.MAX_BODY_BYTES})
        try:
            envelope = contract.normalize(contract.parse_body(self.rfile.read(length)))
        except contract.IntentRejected as exc:
            # No identity yet, so nothing durable to write: the caller is told
            # plainly that this never became an intent.
            return self._reply(400, {"reason": exc.reason, "detail": exc.detail})
        code, body = intake(envelope, worker=type(self).worker)
        return self._reply(code, body)


def intake(envelope, worker=None):
    """Durably record one well-formed envelope and answer the caller.

    Order matters and is the acknowledgement invariant: the record is written
    and fsynced FIRST, the worker is signalled second, and only then does the
    caller hear anything. There is no window in which a caller has been told
    'accepted' about something that is not on disk.
    """
    if envelope["intent_type"] == contract.DECISION_RESPONSE:
        try:
            store.assert_decision_reference(envelope)
        except contract.IntentRejected as exc:
            record, _ = store.reject(envelope, exc.reason, exc.detail)
            return 400, {"intent_id": record["intent_id"], "reason": exc.reason,
                         "detail": exc.detail,
                         "delivery_state": record["delivery_state"]}
    try:
        record, created = store.accept(envelope)
    except store.ListenerStoreError as exc:
        return 409, {"reason": "idempotency-conflict", "detail": str(exc)}
    if created and worker is not None:
        worker.signal()
    return (202 if created else 200), {
        "intent_id": record["intent_id"],
        "correlation_id": record.get("correlation_id"),
        "delivery_state": record["delivery_state"],
        "duplicate": not created,
        "received_at": record.get("received_at")}


def build(port=DEFAULT_PORT, worker=None):
    """A bound, not-yet-serving Listener. Loopback by construction."""
    handler = type("BoundHandler", (Handler,), {"worker": worker})
    httpd = ThreadingHTTPServer((HOST, port), handler)
    return httpd


def serve(port=DEFAULT_PORT, idle_wait=IDLE_WAIT_SECONDS):
    """Run the Listener until interrupted."""
    interrupted = store.recover()
    if interrupted:
        print("listener: %d intent(s) left mid-dispatch by an earlier process; "
              "they are marked dispatch-interrupted and will NOT be re-dispatched: %s"
              % (len(interrupted), ", ".join(interrupted)), flush=True)
    worker = Worker(idle_wait=idle_wait)
    worker.start()
    httpd = build(port, worker)
    print("thebes listener on http://%s:%d (loopback only)" % (HOST, port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop()
        httpd.shutdown()
        httpd.server_close()
        print("thebes listener stopped", flush=True)
    return 0
