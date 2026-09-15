"""The one canonical lifecycle of a submitted intent.

THE DEFECT THIS CLOSES. After Phase 4 an intent had two state machines. The
Listener's transport record said RECEIVED / DISPATCHING / COMPLETED; Persistent
State separately knew whether a claim existed, whether a lease was open, whether
a receipt landed, and where the work item's lifecycle stood. Nothing reconciled
them, so they could disagree indefinitely and no caller could tell. Phase 5's
"one canonical intent lifecycle" is exactly that reconciliation.

THE RULE. The transport record is EVIDENCE OF DELIVERY and nothing more — it is
authority for whether a message arrived, never for what happened to the work.
Canonical state is authority for the work. Where they disagree, canonical state
wins and the disagreement is REPORTED rather than smoothed over; a reconciler
that quietly picks a winner is how a fourth source of truth is born.

THE DANGEROUS CASE, and why it is deliberately not clever. A dispatch that was
interrupted leaves an intent whose outcome nobody observed. Phase 3 refused to
retry it, because the Listener could not prove the Controller had not already
run. That rule is unchanged and must stay unchanged — but Phase 4 left it
unhelpful: "interrupted, a human decides" with no statement of what canonical
state actually holds. Core now answers INDETERMINATE *and* reports the claim,
the open lease, the receipts and the lifecycle for that work item. Strictly more
information; identical conservatism. It still never guesses that an ambiguous
Product mutation did not occur.

This module reads. It has no write path into Persistent State, Jira, a provider
or a task record, and that is asserted by tests rather than promised here.
"""

from agent.listener import store as transport
from agent.state import store as persistent_state


# The ONE external vocabulary. A caller reasons in these words; the Listener's
# delivery states and Persistent State's records are the inputs that produce
# them, not parallel answers a caller has to reconcile themselves.
ACCEPTED = "ACCEPTED"                    # durable, not yet dispatched
ORCHESTRATING = "ORCHESTRATING"          # with the Controller, no answer yet
AWAITING_AUTHORITY = "AWAITING_AUTHORITY"  # stopped at an authority boundary
COMPLETED = "COMPLETED"                  # the Controller gave an authoritative answer
REFUSED = "REFUSED"                      # refused at intake; never orchestrated
UNDELIVERED = "UNDELIVERED"              # no authoritative answer was produced
INDETERMINATE = "INDETERMINATE"          # dispatch interrupted; outcome unobserved

LIFECYCLE_STATES = (ACCEPTED, ORCHESTRATING, AWAITING_AUTHORITY, COMPLETED,
                    REFUSED, UNDELIVERED, INDETERMINATE)

# COMPLETED means the Controller ANSWERED. It does not mean Product work
# succeeded — a governance refusal is a completed delivery carrying a refusal,
# and the answer itself says which.
TERMINAL_STATES = (COMPLETED, REFUSED, UNDELIVERED)

_FROM_TRANSPORT = {
    transport.RECEIVED: ACCEPTED,
    transport.DISPATCHING: ORCHESTRATING,
    transport.WAITING_INPUT: AWAITING_AUTHORITY,
    transport.COMPLETED: COMPLETED,
    transport.REJECTED: REFUSED,
    transport.FAILED: UNDELIVERED,
}

AGREES = "agrees"
NO_CANONICAL_SUBJECT = "no-canonical-subject"
UNOBSERVED_EXECUTION = "unobserved-execution"
TRANSPORT_CLAIMS_MORE = "transport-claims-more-than-canonical-state-shows"


def _canonical_evidence(work_item_id, state_store):
    """What Persistent State actually holds about this work item, read-only."""
    if not work_item_id:
        return None
    task = state_store.read("task", work_item_id)
    if task is None:
        return None
    receipts = [record for record in state_store.read_all("execution_receipt")
                if record.get("work_item_id") == work_item_id]
    leases = [record for record in state_store.read_all("execution_lease")
              if record.get("work_item_id") == work_item_id
              and not record.get("closed_at")]
    return {
        "work_item_id": work_item_id,
        "lifecycle": (task.get("lifecycle") or {}).get("canonical"),
        "owner_seat_id": (task.get("ownership") or {}).get("seat_id"),
        "open_execution_leases": [record["execution_lease_id"] for record in leases],
        "execution_receipts": [
            {"invocation_id": record.get("invocation_id"),
             "status": record.get("status"),
             "provider_id": record.get("provider_id")}
            for record in sorted(receipts, key=lambda r: r.get("created_at") or "")],
        "integration_receipts": [
            record.get("integration_receipt_id")
            for record in state_store.read_all("integration_receipt")
            if record.get("work_item_id") == work_item_id],
    }


def _controller_result(result):
    outcome = (result or {}).get("controller_result") or {}
    return outcome.get("result") if isinstance(outcome.get("result"), dict) else None


def _reconcile(lifecycle_state, canonical, controller):
    """Name any disagreement between delivery evidence and canonical truth.

    Deliberately not a repair. Reconciliation here means SAYING what each source
    holds when they differ; acting on it is a decision made against canonical
    state by someone who can weigh it.
    """
    if canonical is None:
        # Ordinary for a refused intake, or for a key Thebes has no task for —
        # which is itself the Controller's answer, not a Core inconsistency.
        return NO_CANONICAL_SUBJECT
    if lifecycle_state == INDETERMINATE:
        return UNOBSERVED_EXECUTION
    if lifecycle_state in (COMPLETED, AWAITING_AUTHORITY) and controller is not None:
        # An answer that reports an invocation must have left a receipt behind.
        # If it did not, the delivery record is claiming more than canonical
        # state can show, and a caller needs to know that before trusting it.
        invocation = controller.get("invocation_id")
        if invocation and not any(
                receipt["invocation_id"] == invocation
                for receipt in canonical["execution_receipts"]):
            return TRANSPORT_CLAIMS_MORE
    return AGREES


def _lifecycle_state(intent):
    state = _FROM_TRANSPORT.get(intent.get("delivery_state"))
    if state == ORCHESTRATING and intent.get("recovery") == "dispatch-interrupted":
        # The honest word. It is not "in progress" — nothing is progressing —
        # and it is emphatically not "failed", which would assert that nothing
        # happened when that is the one thing nobody can prove.
        return INDETERMINATE
    return state


def resolve(intent_id, state_store=persistent_state, transport_store=transport):
    """One intent's canonical answer, derived rather than reported.

    Returns None when no such intent was ever accepted — which is different from
    an intent that was accepted and refused, and the caller can tell.
    """
    intent = transport_store.read_intent(intent_id)
    if intent is None:
        return None
    result = transport_store.read_result(intent_id)
    controller = _controller_result(result)
    work_item_id = (intent.get("payload") or {}).get("work_item_id")
    canonical = _canonical_evidence(work_item_id, state_store)
    lifecycle_state = _lifecycle_state(intent)
    return {
        "intent_id": intent_id,
        "correlation_id": intent.get("correlation_id"),
        "intent_type": intent.get("intent_type"),
        "work_item_id": work_item_id,
        "submitted_by": {"source": intent.get("source"), "actor": intent.get("actor")},
        "received_at": intent.get("received_at"),
        # The one external state. Everything below it is the evidence it came from.
        "lifecycle_state": lifecycle_state,
        "terminal": lifecycle_state in TERMINAL_STATES,
        "reconciliation": _reconcile(lifecycle_state, canonical, controller),
        "delivery": {
            "transport_state": intent.get("delivery_state"),
            "reason": intent.get("delivery_reason"),
            "dispatch_attempts": intent.get("dispatch_attempts"),
            "recovery": intent.get("recovery"),
        },
        # Read-only projection of Persistent State. Present so an INDETERMINATE
        # answer arrives with the facts a human needs to settle it, instead of
        # sending them to go and look.
        "canonical_state": canonical,
        "controller_result": controller,
    }


def resolve_all(state_store=persistent_state, transport_store=transport):
    """Every accepted intent's canonical answer, oldest intake first."""
    return [resolve(record["intent_id"], state_store, transport_store)
            for record in sorted(transport_store.read_intents(),
                                 key=lambda rec: (rec.get("received_at") or "",
                                                  rec["intent_id"]))]
