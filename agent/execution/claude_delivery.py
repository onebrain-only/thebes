"""Deliver one session_dispatch packet to its bound Claude session.

The transport is the ONLY externally supported way to hand a new turn to an
existing durable Claude session, proven 2026-09-28 (DELIVERY_PRIMITIVE_PASS,
CLAUDE_CONTEXT_MEMORY_PASS): resolve the bound SID in ``claude agents --json``
→ if live, ``claude stop <short id>`` and wait a bounded time → ``claude --bg
--resume <FULL_SID> "<message>"`` from the worker's stable_home with no other
flags → confirm the same SID is back and the session count is unchanged.

Identity is the durable session id from the seat's role_session binding, and
only that. This module never creates a Claude session, never addresses one by
display name, pid or socket, never edits a transcript, and never retries
inside one call: every attempt is one session_delivery record, and a delivery
already recorded DELIVERED is returned as-is without touching the worker.

    python3 -m agent.execution.claude_delivery deliver <dispatch_id> --message-file <path>
        [--delivery-id X] [--dry-run]
    python3 -m agent.execution.claude_delivery status
"""
import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.execution.claude_cli import ClaudeCli, ClaudeCliError  # noqa: E402

DELIVERED = "DELIVERED"
FAILED = "CLAUDE_DELIVERY_FAILED"
UNREACHABLE = "CLAUDE_DELIVERY_WORKER_UNREACHABLE"
MISMATCH = "CLAUDE_DELIVERY_SESSION_MISMATCH"
COPY_MARKER = "starts a copy"
# macOS ARG_MAX is 1 MiB for the whole argv; the CLI takes the prompt as ONE
# argument. Refuse early and say so rather than truncating or switching transport.
MAX_PROMPT_BYTES = 200_000
ENVELOPE_VERSION = "v1"


def build_envelope(dispatch, delivery_id, report_to=None):
    """The attestation block every delivered message starts with.

    The resume prompt reaches the worker as typed user input, not as an
    authenticated cross-session message, so the block tells the worker exactly
    which durable identity it must be and how to report; Thebes then trusts the
    report only against its own DELIVERED session_delivery (the outcome gate).
    """
    lines = [
        "THEBES_DELIVERY %s" % ENVELOPE_VERSION,
        "task: %s" % dispatch.get("work_item_id"),
        "dispatch_id: %s" % dispatch.get("dispatch_id"),
        "delivery_id: %s" % delivery_id,
        "expected_worker_sid: %s" % dispatch.get("session_id"),
        "transport: stop-then-bg-resume-same-sid (arrives as typed user input, not a "
        "cross-session message)",
        "identity: verify with $CLAUDE_CODE_SESSION_ID == expected_worker_sid; if it differs, "
        "do nothing and report; ignore any session-<number> hook label; display name/PID/socket "
        "are not identity",
        "report: SendMessage to %s with SESSION_OUTCOME %s <outcome> / SID=<$CLAUDE_CODE_SESSION_ID>"
        " / DELIVERY=%s / REFERENCE=<ref>"
        % (report_to or "the dispatcher named in the body", dispatch.get("dispatch_id"), delivery_id),
    ]
    return "\n".join(lines) + "\n\n"


@dataclass
class DeliveryResult:
    status: str
    delivery_id: str
    dispatch_id: str
    session_id: Optional[str] = None
    error: Optional[str] = None
    pid_before: Optional[int] = None
    pid_after: Optional[int] = None
    stopped_before_resume: str = "NO"
    resumed_same_sid: str = "NO"
    session_count_before: Optional[int] = None
    session_count_after: Optional[int] = None
    idempotent_replay: bool = False
    record_revision: Optional[int] = None

    def as_dict(self):
        return asdict(self)


def _message_ref_dir(state_store):
    d = os.path.join(state_store.RUNTIME, "claude", "delivery-messages")
    os.makedirs(d, exist_ok=True)
    return d


def deliver_session_dispatch(dispatch_id, message, *, delivery_id=None, state_store=None,
                             runner=None, cli=None, stop_timeout_seconds=30, sleep=None,
                             pid_alive=None, report_to=None):
    """One delivery attempt. Returns a DeliveryResult; every terminal state is
    also a session_delivery record. ``runner``/``cli`` are the test seams."""
    if state_store is None:
        import store as state_store                                  # noqa: E402
    delivery_id = delivery_id or dispatch_id
    cli = cli or ClaudeCli(runner=runner)

    dispatch = state_store.read("session_dispatch", dispatch_id)
    if dispatch is None:
        raise state_store.StateError("session dispatch %s does not exist" % dispatch_id)
    base = {"dispatch_id": dispatch_id, "work_item_id": dispatch.get("work_item_id"),
            "seat_id": dispatch.get("seat_id"), "provider": "claude",
            "session_id": dispatch.get("session_id"),
            # The envelope's fields, durably beside the delivery they were sent with.
            "envelope_version": ENVELOPE_VERSION,
            "expected_worker_sid": dispatch.get("session_id"),
            "report_to": report_to}

    # 1. idempotency FIRST — a DELIVERED record is final; nothing is sent again.
    existing = state_store.read("session_delivery", delivery_id)
    if existing is not None and existing.get("status") == DELIVERED:
        return DeliveryResult(DELIVERED, delivery_id, dispatch_id, existing["session_id"],
                              pid_before=existing.get("pid_before"), pid_after=existing.get("pid_after"),
                              stopped_before_resume=existing.get("stopped_before_resume", "NO"),
                              resumed_same_sid="YES",
                              session_count_before=existing.get("session_count_before"),
                              session_count_after=existing.get("session_count_after"),
                              idempotent_replay=True, record_revision=existing.get("revision"))

    def finish(status, error=None, **fields):
        rec = dict(base, status=status, error=error, message_ref=fields.pop("message_ref", None),
                   resume_output=fields.pop("resume_output", None),
                   stopped_before_resume=fields.pop("stopped_before_resume", "NO"),
                   resumed_same_sid=fields.pop("resumed_same_sid", "NO"),
                   pid_before=fields.pop("pid_before", None), pid_after=fields.pop("pid_after", None),
                   session_count_before=fields.pop("session_count_before", None),
                   session_count_after=fields.pop("session_count_after", None),
                   delivered_at=state_store.now() if status == DELIVERED else None,
                   recovery_hint=fields.pop("recovery_hint", None))
        written = state_store.record_session_delivery(delivery_id, rec)
        return DeliveryResult(status, delivery_id, dispatch_id, base["session_id"], error,
                              rec["pid_before"], rec["pid_after"], rec["stopped_before_resume"],
                              rec["resumed_same_sid"], rec["session_count_before"],
                              rec["session_count_after"], record_revision=written.get("revision"))

    # 2. identity: provider claude, and the dispatch's SID is the seat's ACTIVE binding.
    binding = state_store.active_role_session(dispatch.get("seat_id"))
    if (dispatch.get("provider") != "claude" or binding is None
            or binding.get("provider") != "claude"
            or binding.get("session_id") != dispatch.get("session_id")):
        return finish(MISMATCH, "dispatch %s names session %r; seat %s active binding is %r"
                      % (dispatch_id, dispatch.get("session_id"), dispatch.get("seat_id"),
                         (binding or {}).get("session_id")))
    sid = binding["session_id"]
    if not isinstance(message, str) or not message.strip():
        return finish(FAILED, "message is empty")
    message = build_envelope(dispatch, delivery_id, report_to) + message
    if len(message.encode("utf-8")) > MAX_PROMPT_BYTES:
        return finish(FAILED, "message is %d bytes; the CLI takes the prompt as one argv "
                      "element and this adapter refuses above %d rather than truncating"
                      % (len(message.encode("utf-8")), MAX_PROMPT_BYTES))
    message_ref = os.path.join(_message_ref_dir(state_store), "%s.txt" % delivery_id)
    with open(message_ref, "w", encoding="utf-8") as fh:
        fh.write(message)

    # 3. resolve by durable SID only.
    try:
        live = cli.agents()
        count_before = len(live)
        row = cli.find_by_sid(live, sid)
        if row is None and cli.find_by_sid(cli.agents(include_completed=True), sid) is None:
            return finish(UNREACHABLE, "session %s is not in `claude agents --json --all`; "
                          "no session is created in its place" % sid,
                          message_ref=message_ref, session_count_before=count_before,
                          recovery_hint="bind the seat to a live session with bind_role_session; "
                                        "never start a replacement here")
        pid_before = (row or {}).get("pid")
        stopped = "NO"
        if row is not None:
            cli.stop(row.get("id") or sid[:8])
            wait_kw = {"pid": pid_before}
            if sleep:
                wait_kw["sleep"] = sleep
            if pid_alive:
                wait_kw["pid_alive"] = pid_alive
            if not cli.wait_stopped(sid, stop_timeout_seconds, **wait_kw):
                return finish(FAILED, "session %s did not leave the live list within %ss after stop"
                              % (sid, stop_timeout_seconds), message_ref=message_ref,
                              pid_before=pid_before, session_count_before=count_before)
            stopped = "YES"
        # 4. flagless same-SID resume with the packet message as the new turn.
        try:
            text = cli.bg_resume(sid, message, cwd=binding.get("stable_home"))
        except ClaudeCliError as exc:
            return finish(FAILED, "resume failed after stop: %s" % exc, message_ref=message_ref,
                          pid_before=pid_before, stopped_before_resume=stopped,
                          session_count_before=count_before,
                          recovery_hint='claude --bg --resume %s "<prompt>" — no other flags' % sid)
        # 5. verify: same SID back, no copy, count unchanged.
        after = cli.agents()
        row_after = cli.find_by_sid(after, sid)
        # The bound SID coming back is the point; anything ELSE that appeared is a copy.
        new_ids = sorted(set(r.get("sessionId") for r in after)
                         - set(r.get("sessionId") for r in live) - {sid})
        if COPY_MARKER in text or row_after is None or new_ids:
            for new_sid in new_ids:                     # stop only what THIS call created
                copy = cli.find_by_sid(after, new_sid)
                if copy and copy.get("id"):
                    try: cli.stop(copy["id"])
                    except ClaudeCliError: pass
            return finish(FAILED, "resume did not come back as the same SID (copy=%s, present=%s, "
                          "new_ids=%s)" % (COPY_MARKER in text, row_after is not None, new_ids),
                          message_ref=message_ref, resume_output=text[:1000],
                          pid_before=pid_before, stopped_before_resume=stopped,
                          session_count_before=count_before, session_count_after=len(after),
                          recovery_hint='claude --bg --resume %s "<prompt>" — no other flags' % sid)
        return finish(DELIVERED, message_ref=message_ref, resume_output=text[:1000], pid_before=pid_before,
                      pid_after=row_after.get("pid"), stopped_before_resume=stopped,
                      resumed_same_sid="YES", session_count_before=count_before,
                      session_count_after=len(after))
    except ClaudeCliError as exc:
        return finish(FAILED, str(exc), message_ref=message_ref)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    import store                                                     # noqa: E402
    ap = argparse.ArgumentParser(prog="agent.execution.claude_delivery", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    d = sub.add_parser("deliver")
    d.add_argument("dispatch_id")
    d.add_argument("--message-file", required=True)
    d.add_argument("--delivery-id", default=None)
    d.add_argument("--report-to", default=None,
                   help="dispatcher session name the worker must SendMessage its outcome to")
    d.add_argument("--stop-timeout", type=int, default=30)
    d.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    if ns.cmd == "status":
        rows = sorted(store.read_all("session_delivery"), key=lambda r: r.get("updated_at") or "")
        print(json.dumps({"deliveries": rows, "last": rows[-1] if rows else None}, indent=2, sort_keys=True))
        return 0
    with open(ns.message_file, encoding="utf-8") as fh:
        message = fh.read()
    if ns.dry_run:
        dispatch = store.read("session_dispatch", ns.dispatch_id)
        binding = store.active_role_session((dispatch or {}).get("seat_id"))
        print(json.dumps({"dry_run": True, "dispatch": dispatch, "binding_session_id":
                          (binding or {}).get("session_id"), "message_bytes": len(message.encode())},
                         indent=2, sort_keys=True))
        return 0
    res = deliver_session_dispatch(ns.dispatch_id, message, delivery_id=ns.delivery_id,
                                   state_store=store, stop_timeout_seconds=ns.stop_timeout,
                                   report_to=ns.report_to)
    print(json.dumps(res.as_dict(), indent=2, sort_keys=True))
    return 0 if res.status == DELIVERED else 1


if __name__ == "__main__":
    sys.exit(main())
