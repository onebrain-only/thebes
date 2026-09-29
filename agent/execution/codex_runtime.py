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
    python3 -m agent.execution.codex_runtime new-conversation --label <label>
    python3 -m agent.execution.codex_runtime prompt <thread_id> "<text>"
    python3 -m agent.execution.codex_runtime drain <thread_id>
    python3 -m agent.execution.codex_runtime events <thread_id>
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

RUNTIME_ID = "shared"
TURN_TIMEOUT_SECONDS = 900


class RuntimeError_(Exception):
    """Fail-closed refusal with a stable code."""

    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def socket_path(state_store=store):
    d = os.path.join(state_store.RUNTIME, "codex")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "shared.sock")


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
               "catalog_path": catalog, "launch_args": args, "started_at": state_store.now()}
        if cur is None:
            return state_store.create("codex_runtime", rec, rid=RUNTIME_ID)
        return state_store.update("codex_runtime", RUNTIME_ID, cur["revision"], rec)


def _spawn(args):
    log = open(os.path.join(os.path.dirname(args[3][len("unix://"):]), "shared.log"), "a")
    proc = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                            start_new_session=True)
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
def create_conversation(label, created_by, *, state_store=store, factory=None):
    """thread/start on the shared runtime, then register the new thread."""
    if str(created_by).startswith("worker:"):
        raise RuntimeError_("actor-not-permitted", "a worker may not create a conversation")
    client, model = connect(state_store=state_store, factory=factory)
    try:
        started = client.request("thread/start", {"model": model, "cwd": ROOT})
    finally:
        client.close()
    thread_id = (started.get("thread") or {}).get("id")
    return state_store.create("codex_conversation", {
        "thread_id": thread_id, "runtime_id": RUNTIME_ID, "label": label,
        "registered_by": created_by, "status": "active"}, rid=thread_id)


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
    event_id = event_id or state_store.new_id("codex_turn_event")
    existing = state_store.read("codex_turn_event", event_id)
    if existing is not None:
        return existing, False
    path = _text_path(state_store, event_id)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    try:
        rec = state_store.create("codex_turn_event", {
            "event_id": event_id, "thread_id": thread_id, "event_kind": event_kind,
            "dispatch_id": dispatch_id, "status": "queued", "text_ref": path,
            "turn_ref": None, "response_summary": None, "error": None,
            "completed_at": None}, rid=event_id)
    except store.StateError:
        return state_store.read("codex_turn_event", event_id), False
    return rec, True


def _queued(thread_id, state_store):
    return sorted((r for r in state_store.read_all("codex_turn_event")
                   if r.get("thread_id") == thread_id and r.get("status") == "queued"),
                  key=lambda r: r.get("created_at") or "")


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


NO_ROLLOUT = "no rollout found"


def _resume_if_needed(client, thread_id):
    """Load the thread on this shared server if it is not already loaded.

    A thread started on the shared server but with no turn yet has no rollout
    on disk, so thread/resume answers "no rollout found" — it is already live
    in this same server process (registered conversations are only ever
    started here), and turn/start addresses it directly. Any other resume
    error still fails closed."""
    from agent.execution.codex_appserver import AppServerError
    try:
        client.request("thread/resume", {"threadId": thread_id, "excludeTurns": True}, timeout=120)
    except AppServerError as exc:
        if NO_ROLLOUT not in str(exc.error.get("message") or ""):
            raise


def _run_one(client, ev, state_store, turn_timeout):
    from agent.execution.codex_appserver import AppServerError, AppServerTimeout
    cur = state_store.update("codex_turn_event", ev["event_id"], ev["revision"],
                             {"status": "running"})
    with open(ev["text_ref"], encoding="utf-8") as fh:
        text = fh.read()
    try:
        started = client.request("turn/start", {"threadId": ev["thread_id"],
                                                "input": [{"type": "text", "text": text}]},
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
    subprocess.Popen([sys.executable, "-m", "agent.execution.codex_runtime", "drain", thread_id],
                     cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.codex_runtime", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start"); sub.add_parser("status")
    nc = sub.add_parser("new-conversation"); nc.add_argument("--label", required=True)
    nc.add_argument("--created-by", default="ceo")
    pr = sub.add_parser("prompt"); pr.add_argument("thread_id"); pr.add_argument("text")
    dr = sub.add_parser("drain"); dr.add_argument("thread_id")
    ev = sub.add_parser("events"); ev.add_argument("thread_id")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "start":
            out = ensure_runtime()
        elif ns.cmd == "status":
            out = {"runtime": store.read("codex_runtime", RUNTIME_ID),
                   "conversations": store.read_all("codex_conversation")}
        elif ns.cmd == "new-conversation":
            out = create_conversation(ns.label, ns.created_by)
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
