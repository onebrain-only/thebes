"""Route one accepted worker outcome to whichever Primary is ACTIVE — once.

The Listener records a worker's outcome synchronously (identity + delivery
gate). Everything after that is this module, and it is deliberately dumb:

  * ``schedule()`` creates the ONE durable primary_notification a dispatch may
    ever have and hands it to a detached process. The caller returns at once.
    A duplicate outcome, a replay, or a rerun finds the record already there
    and schedules nothing — the record IS the duplicate-wake prevention.
  * ``deliver()`` (the detached process) re-reads the canonical ACTIVE
    primary_binding at send time and wakes only that Primary: Codex through
    the existing codex_primary adapter on its bound thread; Claude through the
    same stop-then-resume transport as a worker delivery, and only if that
    session is idle. A busy Primary keeps the notification durable as ``busy``
    for a later attempt. There is no retry loop and no polling anywhere.

A wake carries the event; it authorizes nothing. The Primary handles it and
waits for the user unless the task itself requires continuation.

    python3 -m agent.execution.primary_notify deliver <dispatch_id>
    python3 -m agent.execution.primary_notify status
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

EVENT_KIND = "worker_outcome"
# What the Primary is told to do with each outcome. None of these creates work:
# the Primary routes, resumes the SAME worker on the SAME ticket, or reports.
NEXT_STEP = {
    "completed": "Record completion for this ticket. Do not invent or dispatch further work; "
                 "wait for the user unless this task's own brief requires a continuation.",
    "failed": "Report the failure to the user with the worker's summary. Do not re-dispatch "
              "on your own authority.",
    "blocked": "Route the blocker to the persistent authority that owns it, then resume the "
               "SAME worker session on the SAME ticket with the answer. No follow-up ticket.",
    "decision_required": "Route the decision to the persistent authority that owns it (cto/po/"
                         "cpo/cxo/ceo as the question dictates), then resume the SAME worker on "
                         "the SAME ticket with the decision. No follow-up ticket.",
    "clarification_required": "Obtain the clarification from the authority that owns the "
                              "question, then resume the SAME worker on the SAME ticket. "
                              "No follow-up ticket.",
}


def render(notification):
    n = notification
    return "\n".join([
        "WORKER_OUTCOME (Thebes event; handle it, do not generate new tasks)",
        "task: %s" % n.get("work_item_id"),
        "dispatch_id: %s" % n.get("dispatch_id"),
        "delivery_id: %s" % n.get("delivery_id"),
        "seat: %s" % n.get("seat_id"),
        "worker_sid: %s" % n.get("worker_session_id"),
        "outcome: %s" % n.get("outcome"),
        "reference: %s" % (n.get("reference") or "none"),
        "summary: %s" % (n.get("summary_ref") or "none"),
        "next: %s" % NEXT_STEP.get(n.get("outcome"), "handle and wait for the user"),
    ])


def schedule(dispatch_id, settled, *, state_store=store, launcher=None):
    """Create the dispatch's one notification and start its detached delivery.

    ``settled`` is the settled session_dispatch record. Returns
    {"status": "scheduled"|"already-scheduled", "dispatch_id": ...}. Never
    waits on the delivery; never raises for a delivery problem.
    """
    rec, created = state_store.create_primary_notification(dispatch_id, {
        "work_item_id": settled.get("work_item_id"), "seat_id": settled.get("seat_id"),
        "worker_session_id": settled.get("reported_session_id"),
        "delivery_id": settled.get("attested_delivery_id"),
        "outcome": settled.get("outcome"), "reference": settled.get("reference"),
        "summary_ref": (settled.get("summary") or "")[:200]})
    if not created:
        return {"status": "already-scheduled", "dispatch_id": dispatch_id,
                "notification_status": rec.get("status")}
    (launcher or _detach)(dispatch_id)
    return {"status": "scheduled", "dispatch_id": dispatch_id, "notification_status": "scheduled"}


def _detach(dispatch_id):
    """One detached delivery process. Nothing here waits for it."""
    subprocess.Popen([sys.executable, "-m", "agent.execution.primary_notify", "deliver",
                      dispatch_id], cwd=ROOT, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def deliver(dispatch_id, *, state_store=store, codex_waker=None, claude_cli=None):
    """Wake the ACTIVE Primary with this dispatch's notification, once."""
    n = state_store.read("primary_notification", dispatch_id)
    if n is None:
        return {"status": "failed", "error": "no primary_notification for %s" % dispatch_id}
    if n.get("status") == "delivered":
        return {"status": "delivered", "already": True, "wake_record_id": n.get("wake_record_id")}
    active = state_store.active_primary()
    if active is None:
        settled = state_store.settle_primary_notification(
            dispatch_id, "failed", error={"code": "no-active-primary", "message": "no ACTIVE binding"})
        return {"status": settled["status"], "error": settled["error"]}
    text = render(n)
    provider = active["provider"]
    if provider == "codex":
        from agent.execution.codex_primary import wake_codex_primary
        waker = codex_waker or wake_codex_primary
        # The same Thebes-wide single writer a user command takes: a
        # notification never races a command onto the Primary thread.
        try:
            with state_store.primary_writer():
                res = waker(EVENT_KIND, text, binding=active, state_store=state_store)
        except state_store.PrimaryWriterBusy as exc:
            settled = state_store.settle_primary_notification(
                dispatch_id, "busy", provider="codex",
                error={"code": "PRIMARY_WRITER_BUSY", "message": str(exc)})
            return {"status": "busy", "provider": "codex", "wake_record_id": None,
                    "error": settled["error"]}
        status = {"delivered": "delivered", "busy": "busy"}.get(res.status, "failed")
        settled = state_store.settle_primary_notification(
            dispatch_id, status, provider="codex", wake_record_id=res.wake_record_id,
            error=None if status == "delivered" else {"code": res.code, "message": res.error})
    elif provider == "claude":
        status, error = _wake_claude(active, text, claude_cli)
        settled = state_store.settle_primary_notification(
            dispatch_id, status, provider="claude", error=error)
    else:
        settled = state_store.settle_primary_notification(
            dispatch_id, "failed", provider=None,
            error={"code": "unknown-primary-provider", "message": provider})
    return {"status": settled["status"], "provider": provider,
            "wake_record_id": settled.get("wake_record_id"), "error": settled.get("error")}


def _wake_claude(binding, text, cli=None):
    """The Claude Primary gets the same typed-input turn a worker does, and
    only when idle: stopping a Primary mid-conversation is not a wake."""
    from agent.execution.claude_cli import ClaudeCli, ClaudeCliError
    cli = cli or ClaudeCli()
    sid = binding["session_ref"]
    try:
        live = cli.agents()
        row = cli.find_by_sid(live, sid)
        if row is None and cli.find_by_sid(cli.agents(include_completed=True), sid) is None:
            return "failed", {"code": "claude-primary-unreachable", "message": sid}
        if row is not None and row.get("status") != "idle":
            return "busy", {"code": "CLAUDE_PRIMARY_BUSY", "message": "session %s is %s"
                            % (sid, row.get("status"))}
        if row is not None:
            cli.stop(row.get("id") or sid[:8])
            if not cli.wait_stopped(sid, 30, pid=row.get("pid")):
                return "failed", {"code": "claude-primary-stop-timeout", "message": sid}
        out = cli.bg_resume(sid, text, cwd=binding.get("stable_home"))
        if cli.find_by_sid(cli.agents(), sid) is None:
            return "failed", {"code": "claude-primary-resume-lost", "message": out[:300]}
        return "delivered", None
    except ClaudeCliError as exc:
        return "failed", {"code": "claude-cli-error", "message": str(exc)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.primary_notify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    d = sub.add_parser("deliver")
    d.add_argument("dispatch_id")
    ns = ap.parse_args(argv)
    if ns.cmd == "status":
        rows = sorted(store.read_all("primary_notification"), key=lambda r: r.get("updated_at") or "")
        print(json.dumps({"notifications": rows}, indent=2, sort_keys=True))
        return 0
    res = deliver(ns.dispatch_id)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res.get("status") == "delivered" else 1


if __name__ == "__main__":
    sys.exit(main())
