"""Durable Listener inbox and outbox.

THIS IS NOT PERSISTENT STATE. These records are COMMUNICATION EVIDENCE: what
arrived, whether it was dispatched, and what the Controller said. They are
authority for nothing. If a listener record says DISPATCHING and Persistent
State says the work is unowned, Persistent State is right; if it says COMPLETED
and Jira says otherwise, Jira is right. Nothing here is ever consulted to decide
a lifecycle, an ownership, a dependency, a validation verdict or an
authorization — the Controller re-derives every one of those from canonical
sources on each invocation.

It deliberately lives outside `agent/state/runtime/` for that reason, and
`agent/state/validate.py` does not know it exists. What it borrows from
Persistent State is the two mechanical primitives it would otherwise duplicate
badly: the same-directory atomic write and the same `flock` discipline.

The invariant this module exists to hold: ONCE AN INTENT IS ACKNOWLEDGED IT
DOES NOT DISAPPEAR. The durable record is written and fsynced before the caller
is told anything at all.
"""

import json
import os

from agent.listener import contract
from agent.state.store import _Lock as _StateLock          # same flock discipline
from agent.state.store import _atomic_write as _atomic_write  # same atomic replace
from agent.state.store import now


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# One canonical location, with an override used only to give a test (or a second
# operator experiment) its own throwaway inbox. It is deliberately NOT a way to
# point the Listener at Persistent State: nothing it writes belongs there.
RUNTIME = os.environ.get("THEBES_LISTENER_RUNTIME") or os.path.join(
    ROOT, "agent", "listener", "runtime")

# Listener DELIVERY states. They describe the fate of a message, never the fate
# of Product work: there is deliberately no state here that means "done",
# "passed", "claimed" or "ready".
RECEIVED = "RECEIVED"
DISPATCHING = "DISPATCHING"
WAITING_INPUT = "WAITING_INPUT"
COMPLETED = "COMPLETED"
REJECTED = "REJECTED"
FAILED = "FAILED"

DELIVERY_STATES = (RECEIVED, DISPATCHING, WAITING_INPUT, COMPLETED, REJECTED, FAILED)
# A terminal intent is never re-dispatched. WAITING_INPUT is terminal for THIS
# intent: the workflow continues through a correlated DECISION_RESPONSE, which
# is its own intent, so resuming never means re-running this one.
TERMINAL = (WAITING_INPUT, COMPLETED, REJECTED, FAILED)
DISPATCHABLE = (RECEIVED,)


class ListenerStoreError(Exception):
    pass


def _dir(name):
    path = os.path.join(RUNTIME, name)
    os.makedirs(path, exist_ok=True)
    return path


def _path(name, rid):
    return os.path.join(_dir(name), rid + ".json")


def _read(name, rid):
    path = _path(name, rid)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_all(name):
    out = []
    for filename in sorted(os.listdir(_dir(name))):
        if filename.endswith(".json"):
            with open(os.path.join(_dir(name), filename), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out


def _lock(intent_id):
    return _StateLock("listener-intent-%s" % intent_id)


def read_intent(intent_id):
    return _read("intents", intent_id)


def read_result(intent_id):
    return _read("results", intent_id)


def read_intents():
    return _read_all("intents")


def accept(envelope, received_at=None):
    """Durably record one intake, and say whether it was new.

    Returns ``(record, created)``. A second submission under the same
    idempotency key returns the FIRST record untouched and ``created=False`` —
    that, not a lookup before the write, is what makes duplicate delivery
    harmless: identity is derived from the caller's own key, so the duplicate
    is literally the same file.
    """
    intent_id = envelope["intent_id"]
    with _lock(intent_id):
        existing = read_intent(intent_id)
        if existing is not None:
            changed = contract.conflicts(existing, envelope)
            if changed:
                raise ListenerStoreError(
                    "idempotency key reused with different content: %s"
                    % ", ".join(changed))
            return existing, False
        record = dict(envelope,
                      record_type="listener_intent",
                      received_at=received_at or now(),
                      delivery_state=RECEIVED,
                      delivery_reason=None,
                      dispatch_attempts=0,
                      dispatched_at=None,
                      settled_at=None,
                      recovery=None)
        _atomic_write(_path("intents", intent_id), record)
        return record, True


def reject(envelope, reason, detail, received_at=None):
    """Durably record an intake that was understood and refused.

    A refusal the caller can read back later is worth keeping; a refusal that
    vanishes leaves them unable to tell 'refused' from 'lost'.
    """
    intent_id = envelope["intent_id"]
    with _lock(intent_id):
        existing = read_intent(intent_id)
        if existing is not None:
            return existing, False
        record = dict(envelope,
                      record_type="listener_intent",
                      received_at=received_at or now(),
                      delivery_state=REJECTED,
                      delivery_reason=reason,
                      dispatch_attempts=0,
                      dispatched_at=None,
                      settled_at=now(),
                      recovery=None)
        _atomic_write(_path("intents", intent_id), record)
        _write_result(intent_id, record, REJECTED,
                      {"rejected": reason, "detail": detail})
        return record, True


def pending():
    """Every intent still eligible for dispatch, oldest intake first."""
    return sorted((record for record in read_intents()
                   if record.get("delivery_state") in DISPATCHABLE),
                  key=lambda record: (record.get("received_at") or "",
                                      record["intent_id"]))


def begin_dispatch(intent_id):
    """Take exclusive responsibility for dispatching one intent, or return None.

    The RECEIVED -> DISPATCHING move happens under the intent's own lock and is
    checked, not assumed. Two workers racing the same intent therefore produce
    exactly one dispatch; the loser is told 'not eligible' and moves on.
    """
    with _lock(intent_id):
        record = read_intent(intent_id)
        if record is None:
            raise ListenerStoreError("unknown intent %r" % intent_id)
        if record.get("delivery_state") not in DISPATCHABLE:
            return None
        record = dict(record,
                      delivery_state=DISPATCHING,
                      dispatched_at=now(),
                      dispatch_attempts=(record.get("dispatch_attempts") or 0) + 1)
        _atomic_write(_path("intents", intent_id), record)
        return record


def settle(intent_id, delivery_state, result, reason=None):
    """Record the Controller's answer durably, THEN mark the intent settled.

    The order is the whole point of CASE C: if this process dies between the
    two writes, the result is already on disk and the intent is still
    DISPATCHING — recoverable and truthful. It can never die leaving an intent
    marked COMPLETED with no result behind it.
    """
    if delivery_state not in TERMINAL:
        raise ListenerStoreError("%r is not a terminal delivery state" % delivery_state)
    with _lock(intent_id):
        record = read_intent(intent_id)
        if record is None:
            raise ListenerStoreError("unknown intent %r" % intent_id)
        if record.get("delivery_state") in TERMINAL:
            # Already settled. Never re-settle: a terminal intent whose result
            # is overwritten is exactly the silent duplicate this boundary exists
            # to prevent.
            return read_intent(intent_id), read_result(intent_id), False
        _write_result(intent_id, record, delivery_state, result)
        record = dict(record, delivery_state=delivery_state,
                      delivery_reason=reason, settled_at=now())
        _atomic_write(_path("intents", intent_id), record)
        return record, read_result(intent_id), True


def _write_result(intent_id, intent, delivery_state, result):
    _atomic_write(_path("results", intent_id), {
        "record_type": "listener_result",
        "schema_version": contract.SCHEMA_VERSION,
        "intent_id": intent_id,
        "correlation_id": intent.get("correlation_id"),
        "intent_type": intent.get("intent_type"),
        "work_item_id": (intent.get("payload") or {}).get("work_item_id"),
        "delivery_state": delivery_state,
        "recorded_at": now(),
        # Whatever the Controller said, verbatim and unreinterpreted. The
        # Listener does not summarise, grade or re-decide a controller result.
        "controller_result": result,
    })


def recover():
    """Reconcile intents left mid-dispatch by a Listener that died.

    A DISPATCHING intent is NOT re-dispatched. The Listener cannot prove the
    Controller did not already run — and a Product execution it cannot prove
    did not happen is precisely what must not be repeated on a hunch. It is
    marked interrupted, left non-eligible, and surfaced. Deciding what to do
    about it is a human act with canonical state in front of them.
    """
    interrupted = []
    for record in read_intents():
        if record.get("delivery_state") != DISPATCHING:
            continue
        with _lock(record["intent_id"]):
            current = read_intent(record["intent_id"])
            if current.get("delivery_state") != DISPATCHING:
                continue
            current = dict(current, recovery="dispatch-interrupted")
            _atomic_write(_path("intents", current["intent_id"]), current)
            interrupted.append(current["intent_id"])
    return interrupted


def assert_decision_reference(envelope):
    """Bind a DECISION_RESPONSE to the exact workflow that asked for it.

    Four independent facts must line up: the referenced intent exists, it is
    still waiting on this decision, it concerns the same work item, and it
    names the same provider invocation. A decision that misses any of them is
    refused here and never reaches the Controller — which would refuse it
    again, because `store.record_execution_approval` re-verifies the boundary
    from Persistent State. Two gates, and the canonical one is the second.
    """
    payload = envelope["payload"]
    referenced = read_intent(envelope["responds_to"])
    if referenced is None:
        raise contract.IntentRejected(
            "unknown-decision-reference",
            "responds_to names no intent this Listener has seen")
    if referenced.get("delivery_state") != WAITING_INPUT:
        raise contract.IntentRejected(
            "decision-target-not-waiting",
            "intent %s is %s, not %s" % (envelope["responds_to"],
                                         referenced.get("delivery_state"), WAITING_INPUT))
    if (referenced.get("payload") or {}).get("work_item_id") != payload["work_item_id"]:
        raise contract.IntentRejected(
            "decision-work-item-mismatch",
            "decision names a different work item than the waiting intent")
    result = read_result(envelope["responds_to"]) or {}
    # The controller result sits inside the transport outcome the dispatcher
    # recorded verbatim; the invocation the workflow actually stopped at is the
    # Controller's own field, not one the Listener invented.
    controller = ((result.get("controller_result") or {}).get("result")) or {}
    awaited = controller.get("invocation_id")
    if awaited != payload["original_invocation_id"]:
        raise contract.IntentRejected(
            "decision-invocation-mismatch",
            "decision names invocation %r; the waiting intent stopped at %r"
            % (payload["original_invocation_id"], awaited))
    return referenced
