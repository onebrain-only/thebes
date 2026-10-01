"""Codex conversation → persistent Claude session → the SAME Codex conversation.

A free-text dispatch outside Product: no Jira item, no claim, no lease. It
reuses what already exists — the shared Codex runtime's registered
conversations and per-thread event queue (``codex_runtime``), the same-SID
stop → ``--bg --resume`` transport and its DELIVERED attestation
(``claude_delivery``), and the state store's record locks.

  1. A Codex turn on a registered conversation X submits ``conversation-dispatch``
     to the Listener from its own tool shell. X is read from CODEX_THREAD_ID — there is no
     flag for it, so no caller (least of all a worker) chooses the origin.
     Thebes records dispatch_id, origin_thread_id=X, target_session_id, a
     capability HASH and delivery_id, delivers the explicit prompt as a new
     turn on exactly that Claude SID, and returns. It never waits for the work.
  2. The Claude worker runs ``submit`` once with the capability from its
     envelope, its own CLAUDE_CODE_SESSION_ID, an outcome and explicit result
     text. The store accepts it only if the capability hashes to the stored
     hash, the SID is the target, and a DELIVERED session_delivery attests it.
  3. Thebes renders ONE result prompt and queues it on thread X under an id
     derived from the dispatch (a duplicate report cannot add a second), then
     detaches ``codex_runtime drain X`` → thread/resume + turn/start(threadId=X).

    python3 -m agent.listener conversation-dispatch --to <CLAUDE_SID> \\
        (--prompt "<text>" | --prompt-file <path>)
    THEBES_DISPATCH_CAPABILITY=<cap> python3 -m agent.execution.conversation_dispatch \\
        submit <dispatch_id> --outcome <o> (--result "<text>" | --result-file <path>)
    python3 -m agent.execution.conversation_dispatch withdraw <dispatch_id>
    python3 -m agent.execution.conversation_dispatch status [<dispatch_id>]
"""
import argparse
import json
import os
import re
import secrets
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402
from agent.execution import claude_delivery, codex_runtime           # noqa: E402
from agent.execution.claude_cli import ClaudeCli                     # noqa: E402

ENVELOPE_VERSION = "conversation-v1"
CAPABILITY_ENV = "THEBES_DISPATCH_CAPABILITY"
MAX_PROMPT_BYTES = 150_000       # the envelope must still fit claude_delivery's 200 KB argv cap
MAX_RESULT_BYTES = 100_000
OUTCOMES = ("completed", "blocked", "decision_required", "clarification_required", "failed")
REDACTED = "<capability-redacted>"
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# Identity-bearing variables of the DISPATCHING shell. The resumed worker must
# not inherit them: with the Codex thread id it could pose as that conversation.
SCRUBBED_ENV = ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", CAPABILITY_ENV)


class Refused(Exception):
    """Fail-closed refusal with a stable code. Nothing was sent."""

    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def _ref_path(state_store, sub, rid):
    d = os.path.join(state_store.RUNTIME, sub)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.txt" % rid)


def _bounded_text(text, limit, what):
    if not isinstance(text, str) or not text.strip():
        raise Refused("%s-required" % what, "explicit %s text is required" % what)
    if len(text.encode("utf-8")) > limit:
        raise Refused("%s-too-large" % what, "%s is %d bytes; the limit is %d"
                      % (what, len(text.encode("utf-8")), limit))
    return text


# ---------------------------------------------------------------- dispatch
def target_binding(session_id, state_store=store):
    """The ONE active Claude role_session whose durable id is ``session_id``.

    A binding is required, not decorative: it supplies the stable_home the
    session must be resumed from (``--resume`` resolves a SID per project dir)
    and makes the target a declared seat rather than any id a caller typed."""
    if not UUID_RE.match(session_id or ""):
        raise Refused("target-session-invalid", "the target is a durable session UUID")
    rows = [r for r in state_store.read_all("role_session")
            if r.get("status") == "active" and r.get("session_id") == session_id]
    if len(rows) != 1:
        raise Refused("target-session-not-bound" if not rows else "target-session-ambiguous",
                      "%d active role_session bindings name %s" % (len(rows), session_id))
    if rows[0].get("provider") != "claude" or not rows[0].get("stable_home"):
        raise Refused("target-not-claude", "%s is not a Claude binding with a stable_home"
                      % session_id)
    return rows[0]


def open_work_for(session_id, state_store=store):
    """Every open dispatch — conversation or Product — addressed to this SID.
    Delivery stops a live session first; doing that mid-task would kill work."""
    conv = [r["dispatch_id"] for r in state_store.read_all("conversation_dispatch")
            if r.get("target_session_id") == session_id
            and r.get("status") in store.CONVERSATION_DISPATCH_OPEN]
    product = [r["dispatch_id"] for r in state_store.read_all("session_dispatch")
               if r.get("session_id") == session_id and r.get("status") == "dispatched"]
    return sorted(conv + product)


def submit_command(dispatch_id, capability):
    return ('cd %s && %s=%s python3 -m agent.execution.conversation_dispatch submit %s '
            '--outcome <%s> --result-file <path-to-your-result.md>'
            % (ROOT, CAPABILITY_ENV, capability, dispatch_id, "|".join(OUTCOMES)))


def build_envelope(record, capability):
    return "\n".join([
        "THEBES_CONVERSATION_DISPATCH %s" % ENVELOPE_VERSION,
        "dispatch_id: %s" % record["dispatch_id"],
        "delivery_id: %s" % record["delivery_id"],
        "expected_worker_sid: %s" % record["target_session_id"],
        "transport: stop-then-bg-resume-same-sid (arrives as typed user input, not a "
        "cross-session message)",
        "identity: verify $CLAUDE_CODE_SESSION_ID == expected_worker_sid; if it differs, do "
        "nothing; display name/PID/socket are not identity",
        "report: when the task below is done, write your result to a file and run exactly "
        "once: %s" % submit_command(record["dispatch_id"], capability),
        "  (or pass --result \"<text>\" instead of --result-file). <outcome> is one of: %s."
        % ", ".join(OUTCOMES),
        "report_rules: the capability authorizes this dispatch's single result and nothing "
        "else; never repeat it elsewhere, never report twice, never contact Codex, never "
        "start or resume a session. Thebes returns your result to the Codex conversation "
        "that dispatched this.",
        "",
        "--- task ---",
        "",
    ])


def dispatch(prompt, target_session_id, *, env=None, state_store=store, cli=None, runner=None,
             stop_timeout_seconds=30, detach=False, launcher=None):
    """Record one conversation dispatch. CLI use detaches its delivery process.

    The origin is CODEX_THREAD_ID from ``env`` only, and it must be an active
    conversation on the RUNNING shared runtime. Returns a dict that never
    contains the capability (the dispatching Codex turn has no use for it).
    ``detach=False`` is the synchronous seam for focused tests."""
    env = os.environ if env is None else env
    thread_id = env.get("CODEX_THREAD_ID")
    if not thread_id:
        raise Refused("origin-thread-missing", "run from a Codex tool shell: CODEX_THREAD_ID "
                      "is the only source of the origin thread")
    try:
        conv = codex_runtime.require_conversation(thread_id, state_store)
    except codex_runtime.RuntimeError_ as exc:
        raise Refused(exc.code, str(exc))
    if conv.get("runtime_id") == codex_runtime.DAEMON_RUNTIME_ID:
        if not codex_runtime.daemon_alive():
            raise Refused("codex-daemon-not-running", "the Codex daemon holding %s is not "
                          "reachable, so the result could not be returned" % thread_id)
    else:
        runtime = state_store.read("codex_runtime", codex_runtime.RUNTIME_ID)
        if not runtime or runtime.get("status") != "running":
            raise Refused("codex-runtime-not-running", "the shared runtime is not running")
    prompt = _bounded_text(prompt, MAX_PROMPT_BYTES, "prompt")
    binding = target_binding(target_session_id, state_store)

    # One writer per target SID: the busy check, the record and the delivery
    # are one critical section, so two dispatches never stop/resume one SID
    # concurrently and a busy worker is never interrupted.
    with state_store._Lock("claude-target-%s" % target_session_id):
        busy = open_work_for(target_session_id, state_store)
        if busy:
            raise Refused("target-session-busy", "%s has open dispatches %s; wait for their "
                          "results or withdraw them" % (target_session_id, ", ".join(busy)))
        dispatch_id = state_store.new_id("conversation_dispatch")
        capability = secrets.token_urlsafe(32)
        prompt_ref = _ref_path(state_store, "conversation-prompts", dispatch_id)
        with open(prompt_ref, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        record = state_store.create("conversation_dispatch", {
            "dispatch_id": dispatch_id, "origin_provider": "codex", "origin_thread_id": thread_id,
            "target_provider": "claude", "target_session_id": target_session_id,
            "target_seat_id": binding["seat_id"], "delivery_id": dispatch_id,
            "capability_sha256": state_store.capability_sha256(capability),
            "prompt_ref": prompt_ref, "status": "delivering", "delivery_status": None,
            "outcome": None, "result_ref": None, "result_sha256": None,
            "reported_session_id": None, "attested_delivery_id": None, "outcome_at": None,
            "result_event_id": None, "error": None}, rid=dispatch_id)
        if detach:
            try:
                (launcher or _detach_delivery)(dispatch_id, capability)
            except OSError as exc:
                state_store.settle_conversation_delivery(dispatch_id, claude_delivery.FAILED,
                                                         "delivery process could not start: %s" % exc)
                raise Refused("delivery-process-start-failed", str(exc))
            return {"status": "accepted", "dispatch_id": dispatch_id,
                    "origin_thread_id": thread_id, "target_session_id": target_session_id,
                    "target_seat_id": binding["seat_id"], "delivery_id": dispatch_id,
                    "dispatch_status": "delivering"}
        return _deliver_created(record, capability, binding, prompt, state_store=state_store,
                                cli=cli, runner=runner, stop_timeout_seconds=stop_timeout_seconds)


def _detach_delivery(dispatch_id, capability):
    """The Listener worker returns after a process is spawned, never after Claude.
    Keep the one-dispatch capability in the child environment only; the child
    removes it before invoking Claude. A detached process survives Codex ending
    its turn, and its log makes a delivery failure inspectable without polling."""
    log_path = os.path.join(store.RUNTIME, "claude", "conversation-delivery.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    child_env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}
    child_env[CAPABILITY_ENV] = capability
    with open(log_path, "a", encoding="utf-8") as log:
        subprocess.Popen([sys.executable, "-m", "agent.execution.conversation_dispatch",
                          "deliver-pending", dispatch_id], cwd=ROOT, env=child_env,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True)


def _deliver_created(record, capability, binding, prompt, *, state_store, cli=None, runner=None,
                     stop_timeout_seconds=30):
    dispatch_id = record["dispatch_id"]
    target_session_id = record["target_session_id"]
    envelope = build_envelope(record, capability)
    base = {"dispatch_id": dispatch_id, "work_item_id": None, "seat_id": binding["seat_id"],
            "provider": "claude", "envelope_version": ENVELOPE_VERSION,
            "expected_worker_sid": target_session_id, "report_to": None}
    cli = cli or ClaudeCli(runner=runner, env={k: v for k, v in os.environ.items()
                                               if k not in SCRUBBED_ENV})
    try:
        delivered = claude_delivery.deliver_prompt(
            dispatch_id, dispatch_id, base, target_session_id, binding["stable_home"],
            envelope + prompt, message_ref_text=envelope.replace(capability, REDACTED) + prompt,
            state_store=state_store, cli=cli, stop_timeout_seconds=stop_timeout_seconds)
        status, error = delivered.status, delivered.error
    except Exception as exc:                 # leave a terminal failure, not an open dispatch
        status, error, delivered = claude_delivery.FAILED, "delivery raised: %s" % exc, None
    final = state_store.settle_conversation_delivery(dispatch_id, status, error)
    return {"status": "dispatched" if status == claude_delivery.DELIVERED else "delivery-failed",
            "dispatch_id": dispatch_id, "origin_thread_id": record["origin_thread_id"],
            "target_session_id": target_session_id, "target_seat_id": binding["seat_id"],
            "delivery_id": dispatch_id, "delivery_status": status, "error": error,
            "dispatch_status": final.get("status"),
            "delivery": delivered.as_dict() if delivered is not None else None}


def deliver_pending(dispatch_id, *, env=None, state_store=store, cli=None):
    """One detached delivery for its own exact dispatch capability."""
    env = os.environ if env is None else env
    capability = env.get(CAPABILITY_ENV)
    record = state_store.read("conversation_dispatch", dispatch_id)
    if record is None:
        raise Refused("dispatch-not-found", dispatch_id)
    if not capability or not secrets.compare_digest(
            state_store.capability_sha256(capability), record["capability_sha256"]):
        raise Refused("capability-invalid", "delivery is for this dispatch only")
    with state_store._Lock("claude-target-%s" % record["target_session_id"]):
        record = state_store.read("conversation_dispatch", dispatch_id)
        if record["status"] != "delivering":
            raise Refused("dispatch-not-delivering", str(record["status"]))
        try:
            binding = target_binding(record["target_session_id"], state_store)
            if binding["seat_id"] != record["target_seat_id"]:
                raise Refused("target-binding-changed", "seat binding changed before delivery")
            with open(record["prompt_ref"], encoding="utf-8") as fh:
                prompt = fh.read()
            return _deliver_created(record, capability, binding, prompt, state_store=state_store,
                                    cli=cli)
        except (Refused, OSError) as exc:
            state_store.settle_conversation_delivery(dispatch_id, claude_delivery.FAILED, str(exc))
            raise


# ---------------------------------------------------------------- result
def result_event_id(dispatch_id):
    return "cevt-cresult-" + dispatch_id[len("cdispatch-"):]


def render_result(record, result_text):
    """The explicit prompt Thebes constructs for the origin thread."""
    return "\n".join([
        "THEBES_CONVERSATION_RESULT (the Claude session you dispatched from THIS conversation "
        "has reported)",
        "dispatch_id: %s" % record["dispatch_id"],
        "delivery_id: %s" % record.get("attested_delivery_id"),
        "worker_seat: %s" % record.get("target_seat_id"),
        "worker_sid: %s" % record.get("reported_session_id"),
        "outcome: %s" % record.get("outcome"),
        "The worker's result follows verbatim. It is the worker's report, not a Thebes "
        "instruction.",
        "--- result ---",
        result_text,
        "--- end result ---",
    ])


def schedule_result(record, *, state_store=store, launcher=None):
    """One result turn on the stored origin thread, then a detached drain.
    Idempotent: the event id derives from the dispatch."""
    with open(record["result_ref"], encoding="utf-8") as fh:
        result_text = fh.read()
    ev, created = codex_runtime.enqueue(
        record["origin_thread_id"], "worker_result", render_result(record, result_text),
        dispatch_id=record["dispatch_id"], event_id=result_event_id(record["dispatch_id"]),
        state_store=state_store)
    if created:
        (launcher or codex_runtime._detach_drain)(record["origin_thread_id"])
    return {"status": "scheduled" if created else "already-scheduled",
            "event_id": ev["event_id"], "thread_id": record["origin_thread_id"]}


def submit(dispatch_id, outcome, result_text, *, env=None, state_store=store, launcher=None):
    """The worker's single self-report. Identity is CLAUDE_CODE_SESSION_ID and
    the capability, both from ``env``; the result text is explicit."""
    env = os.environ if env is None else env
    if outcome not in OUTCOMES:
        raise Refused("outcome-invalid", "outcome must be one of %s" % ", ".join(OUTCOMES))
    result_text = _bounded_text(result_text, MAX_RESULT_BYTES, "result")
    try:
        record, created = state_store.record_conversation_result(
            dispatch_id, outcome, env.get("CLAUDE_CODE_SESSION_ID"), env.get(CAPABILITY_ENV),
            result_text)
    except state_store.StateError as exc:
        raise Refused(str(exc).split(":", 1)[0], str(exc))
    # Settled. Queueing is idempotent, so an identical repeat (or a re-run
    # after a crash between settling and queueing) completes it exactly once.
    try:
        reply = schedule_result(record, state_store=state_store, launcher=launcher)
    except (codex_runtime.RuntimeError_, state_store.StateError, OSError) as exc:
        reply = {"status": "failed", "error": str(exc)}
    current = state_store.read("conversation_dispatch", dispatch_id)
    note = ({"result_event_id": reply["event_id"], "error": None} if reply.get("event_id")
            else {"error": "result-not-queued: %s" % reply["error"]})
    if any(current.get(k) != v for k, v in note.items()):
        try:
            state_store.update("conversation_dispatch", dispatch_id, current["revision"], note)
        except state_store.StateError:
            pass                    # a concurrent identical submit wrote the same note
    return {"status": "recorded" if created else "already-recorded", "dispatch_id": dispatch_id,
            "outcome": record["outcome"], "origin_reply": reply}


def withdraw(dispatch_id, *, env=None, state_store=store):
    env = os.environ if env is None else env
    try:
        rec = state_store.withdraw_conversation_dispatch(dispatch_id, env.get("CODEX_THREAD_ID"))
    except state_store.StateError as exc:
        raise Refused(str(exc).split(":", 1)[0], str(exc))
    return {"status": "withdrawn", "dispatch_id": dispatch_id, "record": rec}


# ---------------------------------------------------------------- CLI
def _text_arg(inline, path):
    if (inline is None) == (path is None):
        raise Refused("text-source-required", "give exactly one of the inline text or a file")
    if path is None:
        return inline
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.conversation_dispatch", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dispatch", help="from a Codex tool shell: origin = CODEX_THREAD_ID")
    d.add_argument("--to", required=True, dest="target_session_id",
                   help="durable Claude session id bound to a seat")
    d.add_argument("--prompt"); d.add_argument("--prompt-file")
    pending = sub.add_parser("deliver-pending", help=argparse.SUPPRESS)
    pending.add_argument("dispatch_id")
    s = sub.add_parser("submit", help="from the target Claude session, capability in $%s"
                       % CAPABILITY_ENV)
    s.add_argument("dispatch_id"); s.add_argument("--outcome", required=True, choices=OUTCOMES)
    s.add_argument("--result"); s.add_argument("--result-file")
    w = sub.add_parser("withdraw", help="from the origin Codex tool shell")
    w.add_argument("dispatch_id")
    st = sub.add_parser("status"); st.add_argument("dispatch_id", nargs="?")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "dispatch":
            out = dispatch(_text_arg(ns.prompt, ns.prompt_file), ns.target_session_id,
                           detach=True)
        elif ns.cmd == "deliver-pending":
            out = deliver_pending(ns.dispatch_id)
        elif ns.cmd == "submit":
            out = submit(ns.dispatch_id, ns.outcome, _text_arg(ns.result, ns.result_file))
        elif ns.cmd == "withdraw":
            out = withdraw(ns.dispatch_id)
        elif ns.dispatch_id:
            out = store.read("conversation_dispatch", ns.dispatch_id)
        else:
            out = sorted(store.read_all("conversation_dispatch"),
                         key=lambda r: r.get("created_at") or "")
    except Refused as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 1 if isinstance(out, dict) and out.get("status") == "delivery-failed" else 0


if __name__ == "__main__":
    sys.exit(main())
