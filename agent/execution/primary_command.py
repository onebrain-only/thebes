"""The user's front door to the ACTIVE Primary: one command, one turn, one record.

Thebes is the runtime owner of the Primary session. A user talks to the Codex
Primary by submitting a PRIMARY_COMMAND intent to the existing Listener; the
Listener runs this module in its own Controller process, which:

  1. writes a durable primary_command record (the text goes to a text_ref
     file, never into the record);
  2. re-reads the canonical ACTIVE primary_binding;
  3. takes the Thebes-wide Primary writer lock WITHOUT waiting — a second
     concurrent command or a notification delivery already in flight is
     refused at once as `busy`, never queued;
  4. for a Codex Primary, runs exactly ONE turn on its bound thread through the
     existing codex_primary adapter (the same one worker-outcome notifications
     use) and waits for THAT turn's result only — never for any worker;
  5. settles the record: delivered (with the turn id and the Primary's reply),
     busy, failed or refused.

A Claude ACTIVE Primary is not commanded through here: it is a live Claude
session the user already talks to directly, so the command is refused with a
structured reason and nothing is sent. A worker actor may never command the
Primary (the Listener contract refuses it at intake).

    python3 -m agent.execution.primary_command status
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

EVENT_KIND = "user_command"
MAX_TEXT_BYTES = 16_000


def _text_dir(state_store):
    d = os.path.join(state_store.RUNTIME, "primary-command-texts")
    os.makedirs(d, exist_ok=True)
    return d


def run_primary_command(text, submitted_by, *, state_store=store, codex_waker=None,
                        command_id=None, timeout_seconds=600):
    """Deliver one user command to the ACTIVE Primary. Returns the settled record."""
    command_id = command_id or state_store.new_id("primary_command")
    text_ref = os.path.join(_text_dir(state_store), "%s.txt" % command_id)
    with open(text_ref, "w", encoding="utf-8") as fh:
        fh.write(text or "")
    rec = state_store.create("primary_command", {
        "primary_command_id": command_id, "status": "accepted",
        "submitted_by": submitted_by, "text_ref": text_ref, "provider": None,
        "session_ref": None, "generation": None, "turn_ref": None,
        "response_summary": None, "wake_record_id": None, "error": None,
        "started_at": state_store.now(), "completed_at": None}, rid=command_id)

    def settle(status, **fields):
        return state_store.update("primary_command", command_id, rec["revision"],
                                  dict(fields, status=status, completed_at=state_store.now()))

    if not (text or "").strip() or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        return settle("refused", error={"code": "primary-command-text-invalid",
                                        "message": "text must be 1..%d bytes" % MAX_TEXT_BYTES})
    active = state_store.active_primary()
    if active is None:
        return settle("refused", error={"code": "no-active-primary", "message": "no ACTIVE binding"})
    base = {"provider": active["provider"], "session_ref": active["session_ref"],
            "generation": active.get("generation")}
    if active["provider"] != "codex":
        return settle("refused", error={
            "code": "primary-command-claude-direct",
            "message": "the ACTIVE Primary is a live Claude session; talk to it directly"}, **base)
    try:
        with state_store.primary_writer():
            from agent.execution.codex_primary import wake_codex_primary
            waker = codex_waker or wake_codex_primary
            res = waker(EVENT_KIND, text, binding=active, state_store=state_store,
                        timeout_seconds=timeout_seconds)
    except state_store.PrimaryWriterBusy as exc:
        return settle("busy", error={"code": "PRIMARY_WRITER_BUSY", "message": str(exc)}, **base)
    status = {"delivered": "delivered", "busy": "busy"}.get(res.status, "failed")
    return settle(status, turn_ref=res.turn_id, response_summary=res.response_summary,
                  wake_record_id=res.wake_record_id,
                  error=None if status == "delivered" else {"code": res.code, "message": res.error},
                  **base)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.primary_command", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    ns = ap.parse_args(argv)
    rows = sorted(store.read_all("primary_command"), key=lambda r: r.get("created_at") or "")
    print(json.dumps({"commands": rows}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
