"""The shared Thebes-owned Codex app-server and its conversation router.

ONE long-lived `codex app-server --listen unix://<runtime>/codex/shared.sock`
is started once and shared by every Thebes-managed Codex conversation. Nothing
here starts an app-server per message, and nothing touches a Desktop-owned
thread: only threads this runtime created (`new-conversation`) are registered,
and every turn goes to a registered thread on this runtime or is refused.

Routing, end to end:

  Codex conversation X (on the shared runtime) runs, in its own tool shell,
      python3 -m agent.listener session-dispatch KAN-1 --deliver
  The Listener CLI reads CODEX_THREAD_ID from that shell's environment (the
  worker never chooses it) and the Controller records on the dispatch:
      origin_provider=codex, origin_thread_id=X, reply_to_thread_id=X,
      target_provider=claude, target_session_id=<bound SID>, delivery_id.
  The bound Claude worker reports through the Listener; the existing gate
  (exact SID + DELIVERED delivery) accepts it once. `session_outcome` then
  enqueues ONE worker_result event for thread X (its id derives from the
  dispatch, so a duplicate can never create a second) and detaches a drain.
  The drain resumes X on the shared runtime and runs one turn/start(threadId=X,
  input=<explicit result prompt>) — a real turn, not a state-only note.

Serialization is per thread: a non-blocking `thread_writer(X)` lock. Thread A
and thread B run concurrently; a second writer on X is refused at once, its
event stays queued, and the current writer drains it right after its own turn
completes (and re-checks after releasing, so none is stranded). No polling, no
global Primary lock, no primary_binding.

    python3 -m agent.execution.codex_runtime start | status
    python3 -m agent.execution.codex_runtime new-conversation --label <label> --prompt "<first turn>"
    python3 -m agent.execution.codex_runtime prompt <thread_id> "<text>"
    python3 -m agent.execution.codex_runtime drain <thread_id>
    python3 -m agent.execution.codex_runtime events <thread_id>
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

# The Desktop app and its app-server use the default ~/.codex home. Keep the
# Thebes-owned threads in a separate Codex home so Desktop cannot acquire
# their single-writer ownership. The old "shared" runtime/threads remain
# historical state but are not accepted by this runtime.
RUNTIME_ID = "thebes"
TURN_TIMEOUT_SECONDS = 900
BOOTSTRAP_VERSION = "thebes-conversation-v1"
THREAD_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class RuntimeError_(Exception):
    """Fail-closed refusal with a stable code."""

    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def socket_path(state_store=store):
    d = os.path.join(state_store.RUNTIME, "codex")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "thebes.sock")


def isolated_codex_home():
    """A separate persistent thread store with the existing ChatGPT login.

    The auth symlink keeps token refresh in the user's normal credential store;
    no credential is copied into the repository or placed in a model prompt.
    Refuse an unexpected pre-existing auth path instead of overwriting it.
    """
    home = os.path.join(os.path.expanduser("~"), ".thebes-codex")
    os.makedirs(home, mode=0o700, exist_ok=True)
    source = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")
    target = os.path.join(home, "auth.json")
    if not os.path.isfile(source):
        raise RuntimeError_("codex-auth-unavailable", "ChatGPT auth file is unavailable")
    if os.path.lexists(target):
        if not os.path.islink(target) or os.path.realpath(target) != os.path.realpath(source):
            raise RuntimeError_("codex-auth-conflict", "isolated home has another auth path")
    else:
        os.symlink(source, target)
    return home


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


# ---------------------------------------------------------------- lifecycle
def ensure_runtime(*, state_store=store, spawn=None, alive=None, wait=None):
    """Start the shared app-server once; return its record. Reuse when healthy.

    Healthy = recorded pid alive AND its socket accepts. A live pid whose
    socket does not accept is inconsistent and refused (fail closed) rather
    than replaced, so two runtimes can never share one record.
    """
    from agent.execution import codex_ws, codex_primary
    alive = alive or codex_ws.socket_alive
    wait = wait or codex_ws.wait_for_socket
    path = socket_path(state_store)
    # A lifecycle lock distinct from the record's own lock: create()/update()
    # below take record_lock themselves, and flock does not nest across fds.
    with state_store._Lock("codex-runtime-lifecycle"):
        cur = state_store.read("codex_runtime", RUNTIME_ID)
        if cur and cur.get("status") == "running" and _pid_alive(cur.get("pid")):
            if cur.get("socket_path") == path and alive(path):
                return cur
            raise RuntimeError_("codex-runtime-inconsistent",
                                "pid %s is alive but %s does not accept" % (cur.get("pid"), path))
        if os.path.exists(path):
            os.unlink(path)                          # stale socket of a dead runtime
        catalog = codex_primary.bundled_catalog_path(state_store)
        args = codex_primary.launch_args(catalog)
        args[2:2] = ["--listen", "unix://" + path]  # codex app-server --listen … -c … -c …
        pid = (spawn or _spawn)(args)
        if not wait(path):
            raise RuntimeError_("codex-runtime-start-failed", "socket never accepted: %s" % path)
        rec = {"runtime_id": RUNTIME_ID, "socket_path": path, "pid": pid, "status": "running",
               "codex_home": os.path.join(os.path.expanduser("~"), ".thebes-codex"),
               "catalog_path": catalog, "launch_args": args, "started_at": state_store.now()}
        if cur is None:
            return state_store.create("codex_runtime", rec, rid=RUNTIME_ID)
        return state_store.update("codex_runtime", RUNTIME_ID, cur["revision"], rec)


def _spawn(args):
    home = isolated_codex_home()
    log = open(os.path.join(os.path.dirname(args[3][len("unix://"):]), "shared.log"), "a")
    env = dict(os.environ, CODEX_HOME=home)
    proc = subprocess.Popen(args, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=log, start_new_session=True)
    return proc.pid


def connect(*, state_store=store, factory=None):
    """A preflighted client on the RUNNING shared runtime, or a refusal."""
    from agent.execution import codex_ws, codex_primary
    rec = state_store.read("codex_runtime", RUNTIME_ID)
    if not rec or rec.get("status") != "running" or rec.get("socket_path") != socket_path(state_store):
        raise RuntimeError_("codex-runtime-not-running", "start it with `codex_runtime start`")
    log = os.path.join(os.path.dirname(rec["socket_path"]), "shared-clients.jsonl")
    client = (factory or codex_ws.CodexWsClient)(rec["socket_path"], log)
    client.initialize()
    try:
        model = codex_primary.preflight(client, rec["catalog_path"])
    except codex_primary.PreflightError as exc:
        client.close()
        raise RuntimeError_(exc.code, str(exc))
    return client, model


# ---------------------------------------------------------------- registry
def bootstrap_prompt(thread_id, state_store=store):
    """The first, private turn on a new thread. It names the real local route."""
    workers = sorted((r["seat_id"], r["session_id"])
                     for r in state_store.read_all("role_session")
                     if r.get("provider") == "claude" and r.get("status") == "active")
    choices = "\n".join("- %s: %s" % pair for pair in workers) or "- none"
    return "\n".join([
        "THEBES_CONVERSATION_BOOTSTRAP %s" % BOOTSTRAP_VERSION,
        "Your exact Codex thread_id is %s on the shared Thebes-owned runtime %s."
        % (thread_id, RUNTIME_ID),
        "You are a persistent managed conversation. To delegate, write an explicit, "
        "self-contained prompt and select the appropriate persistent Claude session below:",
        choices,
        "Run: python3 -m agent.listener conversation-dispatch --to <CLAUDE_SESSION_ID> "
        "--prompt '<YOUR_COMPLETE_PROMPT>'",
        "Read the accepted intake response, finish your own turn immediately, and go idle. "
        "Claude works independently and submits its own result. Thebes resolves the dispatch "
        "to this exact origin_thread_id and sends the result as a new prompt turn here.",
        "Do not poll, relay through another worker, ask the user to copy text, or ask what "
        "channel to use for Claude. Use the Listener command above.",
        "For a self-check run: python3 -m agent.execution.codex_runtime conversation-status "
        "%s" % thread_id,
        "This is a bootstrap acknowledgement turn. Reply with exactly: THEBES_BOOTSTRAP_READY %s"
        % thread_id,
    ])


def listener_ready():
    """The local dispatch front door must be available before a thread is exposed."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=2) as response:
            body = json.load(response)
            return (response.status == 200 and body.get("status") == "ok"
                    and "CONVERSATION_DISPATCH" in body.get("intent_types", []))
    except (OSError, ValueError):
        return False


def conversation_status(thread_id, *, state_store=store, route_ready=None):
    """Read the actual registration, bootstrap event and current runtime binding."""
    conv = state_store.read("codex_conversation", thread_id or "none")
    runtime = state_store.read("codex_runtime", RUNTIME_ID)
    registered = bool(conv and conv.get("thread_id") == thread_id)
    bound = bool(registered and runtime and runtime.get("status") == "running"
                 and conv.get("runtime_id") == runtime.get("runtime_id") == RUNTIME_ID
                 and conv.get("runtime_socket_path") == runtime.get("socket_path"))
    bootstrap = False
    if registered and conv.get("bootstrap_event_id"):
        ev = state_store.read("codex_turn_event", conv["bootstrap_event_id"])
        if ev and ev.get("thread_id") == thread_id and ev.get("event_kind") == "bootstrap" \
                and ev.get("status") == "delivered" and ev.get("turn_ref"):
            try:
                with open(ev["text_ref"], "rb") as fh:
                    digest = hashlib.sha256(fh.read()).hexdigest()
                bootstrap = (digest == conv.get("bootstrap_sha256") and
                             "THEBES_BOOTSTRAP_READY %s" % thread_id in
                             (ev.get("response_summary") or ""))
            except OSError:
                bootstrap = False
    route = bool(bound and bootstrap and (listener_ready() if route_ready is None else route_ready))
    managed = bool(registered and conv.get("status") == "active" and route)
    return {"THREAD_ID": thread_id, "MANAGED": managed,
            "THREAD_CREATED": registered, "THREAD_REGISTERED": registered,
            "RUNTIME_ID": conv.get("runtime_id") if conv else None,
            "RUNTIME_BOUND": bound, "BOOTSTRAP_LOADED": bootstrap,
            "RETURN_ROUTING_READY": route}


def _retire_initializing(thread_id, state_store):
    """Never leave a failed creation eligible for dispatch or opening."""
    if not thread_id:
        return
    conv = state_store.read("codex_conversation", thread_id)
    if conv and conv.get("status") == "initializing":
        state_store.update("codex_conversation", thread_id, conv["revision"],
                           {"status": "retired"})


def create_conversation(label, created_by, first_prompt, *, state_store=store, factory=None,
                        turn_timeout=TURN_TIMEOUT_SECONDS, route_ready=None):
    """thread/start on the shared runtime, register it, and run its FIRST turn
    on that same connection.

    Live finding 2026-09-29: the app-server drops a thread that has no turn
    yet when the connection that started it closes — there is no rollout on
    disk, so a later connection gets "no rollout found" / "thread not found".
    Running the first turn before closing persists the thread; from then on
    any connection can resume it.
    """
    if str(created_by).startswith("worker:"):
        raise RuntimeError_("actor-not-permitted", "a worker may not create a conversation")
    if not (first_prompt or "").strip():
        raise RuntimeError_("first-prompt-required", "a conversation starts with its first turn")
    runtime = state_store.read("codex_runtime", RUNTIME_ID)
    client, model = connect(state_store=state_store, factory=factory)
    thread_id = None
    conv = None
    try:
        started = client.request("thread/start", {"model": model, "cwd": ROOT,
                                                  "sandbox": "workspace-write",
                                                  "approvalPolicy": "never"})
        thread_id = (started.get("thread") or {}).get("id")
        if not THREAD_ID.fullmatch(str(thread_id or "")):
            raise RuntimeError_("thread-id-invalid", "app-server returned no valid thread_id")
        current_runtime = state_store.read("codex_runtime", RUNTIME_ID)
        if not runtime or not current_runtime or current_runtime.get("socket_path") != runtime.get("socket_path"):
            raise RuntimeError_("runtime-changed", "shared runtime changed during thread creation")
        conv = state_store.create("codex_conversation", {
            "thread_id": thread_id, "runtime_id": RUNTIME_ID, "label": label,
            "runtime_socket_path": runtime["socket_path"],
            "registered_by": created_by, "status": "initializing",
            "bootstrap_event_id": None, "bootstrap_sha256": None}, rid=thread_id)
        bootstrap_text = bootstrap_prompt(thread_id, state_store)
        bootstrap_ev, _ = _create_event(thread_id, "bootstrap", bootstrap_text,
                                         state_store=state_store)
        conv = state_store.update("codex_conversation", thread_id, conv["revision"], {
            "bootstrap_event_id": bootstrap_ev["event_id"],
            "bootstrap_sha256": hashlib.sha256(bootstrap_text.encode("utf-8")).hexdigest()})
        with state_store.thread_writer(thread_id):
            if not _run_one(client, bootstrap_ev, state_store, turn_timeout):
                raise RuntimeError_("bootstrap-turn-failed", "bootstrap turn did not complete")
    except Exception as exc:
        _retire_initializing(thread_id, state_store)
        if isinstance(exc, RuntimeError_):
            raise
        raise RuntimeError_("conversation-create-failed", str(exc)) from exc
    finally:
        client.close()
    # A new connection must be able to resume the persisted exact thread.
    try:
        check_client, _ = connect(state_store=state_store, factory=factory)
        try:
            _resume_if_needed(check_client, thread_id)
        finally:
            check_client.close()
        state = conversation_status(thread_id, state_store=state_store, route_ready=route_ready)
        if not all(state[k] for k in ("THREAD_CREATED", "THREAD_REGISTERED", "RUNTIME_BOUND",
                                        "BOOTSTRAP_LOADED", "RETURN_ROUTING_READY")):
            raise RuntimeError_("conversation-not-ready", json.dumps(state, sort_keys=True))
    except Exception as exc:
        _retire_initializing(thread_id, state_store)
        if isinstance(exc, RuntimeError_):
            raise
        raise RuntimeError_("conversation-create-failed", str(exc)) from exc
    conv = state_store.update("codex_conversation", thread_id, conv["revision"], {"status": "active"})
    ev, _ = enqueue(thread_id, "user_prompt", first_prompt, state_store=state_store)
    first = drain(thread_id, state_store=state_store, factory=factory, turn_timeout=turn_timeout)
    if ev["event_id"] not in first["delivered"]:
        raise RuntimeError_("first-turn-failed", "first user turn did not complete")
    # A Claude result can arrive while this first turn still owns the thread
    # lock. Its detached drain then sees "held" and exits. Drain once after
    # releasing the lock so that such a result cannot be stranded.
    return {"conversation": conv, "first_event": state_store.read("codex_turn_event", ev["event_id"]),
            "status": conversation_status(thread_id, state_store=state_store, route_ready=route_ready)}


def require_conversation(thread_id, state_store=store):
    conv = state_store.read("codex_conversation", thread_id or "none")
    if conv is None or conv.get("status") != "active" or conv.get("runtime_id") != RUNTIME_ID:
        raise RuntimeError_("thread-not-in-shared-runtime",
                            "%s is not an active conversation on the shared runtime" % thread_id)
    return conv


# ---------------------------------------------------------------- per-thread queue
def _text_path(state_store, event_id):
    d = os.path.join(state_store.RUNTIME, "codex-turn-texts")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.txt" % event_id)


def enqueue(thread_id, event_kind, text, *, dispatch_id=None, event_id=None, state_store=store):
    """Durably queue one turn for a registered thread. Returns (record, created).
    An existing event with the same id is returned untouched (idempotent)."""
    require_conversation(thread_id, state_store)
    return _create_event(thread_id, event_kind, text, dispatch_id=dispatch_id,
                         event_id=event_id, state_store=state_store)


def _create_event(thread_id, event_kind, text, *, dispatch_id=None, event_id=None,
                  state_store=store):
    event_id = event_id or state_store.new_id("codex_turn_event")
    # Check, text write and create are ONE critical section. Without it two
    # concurrent enqueues of the same derived id both pass the existence check
    # and the loser's text overwrites the winner's text_ref after the winner's
    # record exists. (A lock distinct from create()'s own record lock: flock
    # does not nest across file descriptors.)
    with state_store._Lock("codex-turn-event-enqueue-%s" % event_id):
        existing = state_store.read("codex_turn_event", event_id)
        if existing is not None:
            return existing, False
        path = _text_path(state_store, event_id)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        rec = state_store.create("codex_turn_event", {
            "event_id": event_id, "thread_id": thread_id, "event_kind": event_kind,
            "dispatch_id": dispatch_id, "status": "queued", "text_ref": path,
            # created_at has one-second resolution; seq keeps FIFO inside a second.
            "seq": time.time_ns(), "turn_ref": None, "response_summary": None,
            "error": None, "completed_at": None}, rid=event_id)
    return rec, True


def _queued(thread_id, state_store):
    return sorted((r for r in state_store.read_all("codex_turn_event")
                   if r.get("thread_id") == thread_id and r.get("status") == "queued"),
                  key=lambda r: (r.get("created_at") or "", r.get("seq") or 0))


def drain(thread_id, *, state_store=store, factory=None, turn_timeout=TURN_TIMEOUT_SECONDS):
    """Deliver this thread's queued events, oldest first, one turn each.

    Returns {"status": "drained"|"held", "delivered": [...], "failed": [...]}.
    `held` means another Thebes writer is on this thread and will drain these
    itself when its current turn completes.
    """
    require_conversation(thread_id, state_store)
    delivered, failed = [], []
    while True:
        try:
            with state_store.thread_writer(thread_id):
                pending = _queued(thread_id, state_store)
                if pending:
                    client, _ = connect(state_store=state_store, factory=factory)
                    try:
                        _resume_if_needed(client, thread_id)
                        for ev in pending:
                            (delivered if _run_one(client, ev, state_store, turn_timeout)
                             else failed).append(ev["event_id"])
                    finally:
                        client.close()
        except state_store.ThreadWriterBusy:
            return {"status": "held", "delivered": delivered, "failed": failed}
        # Released. Anything queued while we held the lock is ours to drain.
        if not _queued(thread_id, state_store):
            return {"status": "drained", "delivered": delivered, "failed": failed}


def _resume_if_needed(client, thread_id):
    """Load a persisted conversation on this connection. Every registered
    conversation had its first turn at creation, so a resume failure is real
    and fails closed (the event stays queued)."""
    client.request("thread/resume", {"threadId": thread_id, "excludeTurns": True,
                                     "sandbox": "workspace-write",
                                     "approvalPolicy": "never"}, timeout=120)


def _run_one(client, ev, state_store, turn_timeout):
    from agent.execution.codex_appserver import AppServerError, AppServerTimeout
    cur = state_store.update("codex_turn_event", ev["event_id"], ev["revision"],
                             {"status": "running"})
    with open(ev["text_ref"], encoding="utf-8") as fh:
        text = fh.read()
    try:
        started = client.request("turn/start", {"threadId": ev["thread_id"],
                                                "input": [{"type": "text", "text": text}],
                                                "sandboxPolicy": {"type": "workspaceWrite",
                                                                  "networkAccess": True},
                                                "approvalPolicy": "never"},
                                 timeout=120)
        turn_id = (started.get("turn") or {}).get("id")
        done, messages = client.await_turn(turn_id, turn_timeout)
        ok = done.get("status") == "completed"
        texts = [m.get("text") or "" for m in messages]
        state_store.update("codex_turn_event", ev["event_id"], cur["revision"], {
            "status": "delivered" if ok else "failed", "turn_ref": turn_id,
            "response_summary": (texts[-1][:500] if texts else None),
            "error": None if ok else {"code": "codex-turn-%s" % done.get("status"),
                                      "message": json.dumps(done.get("error"))[:500]},
            "completed_at": state_store.now()})
        return ok
    except (AppServerError, AppServerTimeout) as exc:
        state_store.update("codex_turn_event", ev["event_id"], cur["revision"], {
            "status": "failed", "error": {"code": "codex-app-server-error", "message": str(exc)[:500]},
            "completed_at": state_store.now()})
        return False


# ---------------------------------------------------------------- worker results
def result_event_id(dispatch_id):
    return "cevt-result-" + dispatch_id[len("dispatch-"):]


def render_result(dispatch):
    from agent.execution.primary_notify import NEXT_STEP
    d = dispatch
    return "\n".join([
        "THEBES_WORKER_RESULT (the worker you dispatched from THIS conversation has reported)",
        "task: %s" % d.get("work_item_id"),
        "dispatch_id: %s" % d.get("dispatch_id"),
        "delivery_id: %s" % d.get("attested_delivery_id"),
        "worker_seat: %s" % d.get("seat_id"),
        "worker_sid: %s" % d.get("reported_session_id"),
        "outcome: %s" % d.get("outcome"),
        "reference: %s" % (d.get("reference") or "none"),
        "summary: %s" % (d.get("summary") or "none"),
        "next: %s" % NEXT_STEP.get(d.get("outcome"), "handle and wait for the user"),
    ])


def schedule_worker_result(dispatch, *, state_store=store, launcher=None):
    """One result turn for the dispatch's origin thread, then a detached drain."""
    thread_id = dispatch.get("reply_to_thread_id")
    rec, created = enqueue(thread_id, "worker_result", render_result(dispatch),
                           dispatch_id=dispatch["dispatch_id"],
                           event_id=result_event_id(dispatch["dispatch_id"]),
                           state_store=state_store)
    if created:
        (launcher or _detach_drain)(thread_id)
    return {"status": "scheduled" if created else "already-scheduled",
            "event_id": rec["event_id"], "thread_id": thread_id}


def _detach_drain(thread_id):
    # Appended, not discarded: a drain that fails before any event status
    # changes (runtime down, resume refused) must leave a trace.
    with open(os.path.join(os.path.dirname(socket_path()), "drain.log"), "a") as log:
        subprocess.Popen([sys.executable, "-m", "agent.execution.codex_runtime", "drain",
                          thread_id], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                         stderr=log, start_new_session=True)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.codex_runtime", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start"); sub.add_parser("status")
    nc = sub.add_parser("new-conversation"); nc.add_argument("--label", required=True)
    nc.add_argument("--created-by", default="ceo")
    nc.add_argument("--prompt", required=True,
                    help="the conversation's first turn, run on the creating connection")
    pr = sub.add_parser("prompt"); pr.add_argument("thread_id"); pr.add_argument("text")
    dr = sub.add_parser("drain"); dr.add_argument("thread_id")
    ev = sub.add_parser("events"); ev.add_argument("thread_id")
    cs = sub.add_parser("conversation-status"); cs.add_argument("thread_id")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "start":
            out = ensure_runtime()
        elif ns.cmd == "status":
            out = {"runtime": store.read("codex_runtime", RUNTIME_ID),
                   "conversations": store.read_all("codex_conversation")}
        elif ns.cmd == "new-conversation":
            out = create_conversation(ns.label, ns.created_by, ns.prompt)
        elif ns.cmd == "conversation-status":
            out = conversation_status(ns.thread_id)
        elif ns.cmd == "prompt":
            rec, _ = enqueue(ns.thread_id, "user_prompt", ns.text)
            result = drain(ns.thread_id)
            out = {"drain": result, "event": store.read("codex_turn_event", rec["event_id"])}
        elif ns.cmd == "drain":
            out = drain(ns.thread_id)
        else:
            out = sorted((r for r in store.read_all("codex_turn_event")
                          if r.get("thread_id") == ns.thread_id),
                         key=lambda r: r.get("created_at") or "")
    except RuntimeError_ as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
