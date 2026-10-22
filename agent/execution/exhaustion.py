"""An exhausted review decides itself when the only thing left is a coverage limit.

CEO 2026-10-22: "this kind of message should go and get approved directly". After MAX_CYCLES a
ticket whose every `run` and `judge` check passes and whose ONLY failing check is the Codex `QA`
check, failed because the reviewer could not execute part of the scope (a locale/theme it cannot
switch without writing live data, a device it does not have), is accepted here, with that gap written
on the ticket. A reviewer that saw a defect, a second failing check, or an unsure gate leaves the
ticket in review and the orchestrator decides it (D-035): the CEO is not the approver of this.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402

QA_CHECK = "QA"


def eligible(results):
    """The QA reason when QA is the only failing check and everything else passed, else None."""
    failing = [i for i, r in results.items() if r.get("status") == "fail"]
    if failing != [QA_CHECK]:
        return None
    if any(r.get("status") != "pass" for i, r in results.items() if i != QA_CHECK):
        return None                                   # a pending, skipped-as-error or unknown check
    return str(results[QA_CHECK].get("detail") or "").strip() or None


def decide(root, results, *, state_store=store, jira=None, gate=None):
    """Returns {"accepted": True, ...} after closing the ticket, or {"accepted": False, "why": ...}.
    Never raises: the caller then alerts the orchestrator as before."""
    try:
        reason = eligible(results)
        key = root.get("jira_key")
        if not reason or not key:
            return {"accepted": False, "why": "not-eligible"}
        from agent.execution import decision_gate, jira_sync, pm_ledger
        verdict = (gate or decision_gate.exhaustion_verdict)(reason)
        if verdict.get("verdict") != "accept":
            return {"accepted": False, "why": verdict.get("reason")}
        text = ("ACCEPTED by Thebes under the CEO's delegation (D-035). Every run and judge check "
                "passes. The Codex QA check failed only on part of the scope it could not execute, "
                "which is NOT verified: %s" % " ".join(reason.split())[:600])
        client = jira_sync._client(jira, state_store)
        closed = jira_sync.on_accepted(key, text, state_store=state_store, jira=client)
        if not closed or closed.get("status") != "ok":
            return {"accepted": False, "why": "jira-unavailable"}
        client.add_comment(key, "Thebes: %s" % text)          # on_accepted keeps only the first 300 chars
        pm_ledger.add("thebes-gate", key, "accepted after exhausted review: coverage limit, "
                      "unverified part: %s" % reason[:200], state_store=state_store)
        jira_sync._note(root, "auto-accepted", {"status": "ok", "gate": verdict.get("gate")},
                        state_store, alert=False)
        return {"accepted": True, "ticket": key, "gate": verdict.get("gate")}
    except Exception as exc:                                  # noqa: BLE001
        return {"accepted": False, "why": "error: %s" % str(exc)[:200]}
