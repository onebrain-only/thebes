"""Carry one Listener intent across the process boundary to the Controller.

This module is the entire coupling between the two processes, and it is
deliberately thin. It builds an argv ARRAY for the existing controller entry
point, runs it, and keeps whatever JSON that process printed. It does not
interpret the result, grade it, retry it, or decide anything about the work.

What it must never become is a second controller. There is no seat here, no
provider, no workspace, no claim, no lease, no Jira call, no validation route
and no lifecycle. The Listener hands over a work-item key — the same thing a
human typed at `python -m agent.controller execute KAN-XXX` — and the Controller
re-derives everything else from canonical sources, exactly as it did before a
Listener existed.

Classification note, because the word is easy to misread: COMPLETED here means
the Controller RETURNED AN AUTHORITATIVE ANSWER. It does not mean the Product
work succeeded. A refusal — unauthorized, maintenance-active, unclaimable — is a
COMPLETED delivery carrying a refusal. FAILED is reserved for the case where the
Controller produced no authoritative answer at all.
"""

import json
import os
import subprocess
import sys

from agent.controller.entry import INTENT_ENV
from agent.listener import contract, store


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Generous, but not unbounded: a provider wake can legitimately run for a long
# time, and a hung subprocess must not pin a Listener worker forever.
DEFAULT_TIMEOUT_SECONDS = 60 * 60


def argv_for(intent):
    """The exact controller command line for one intent.

    Always a list, never a string, and never passed to a shell. Every element
    is either a fixed literal or a contract-validated token, so there is no
    path by which intake text becomes an executable instruction.
    """
    payload = intent["payload"]
    work_item_id = payload["work_item_id"]
    if not contract.WORK_ITEM_ID.match(work_item_id):
        raise ValueError("work item id was not contract-validated")
    if intent["intent_type"] == contract.EXECUTE_WORK_ITEM:
        return [sys.executable, "-m", "agent.controller", "execute", work_item_id]
    if intent["intent_type"] == contract.VALIDATE_WORK_ITEM:
        return [sys.executable, "-m", "agent.controller", "validate", work_item_id]
    if intent["intent_type"] == contract.DECISION_RESPONSE:
        command = [sys.executable, "-m", "agent.controller", "decide", work_item_id,
                   "--invocation", payload["original_invocation_id"],
                   "--permission", payload["permission"],
                   "--scope", payload["approval_scope"],
                   "--authority", intent["actor"]]
        if payload.get("allowed_operation"):
            command += ["--operation", payload["allowed_operation"]]
        return command
    if intent["intent_type"] == contract.PREPARE_SESSION_DISPATCH:
        return [sys.executable, "-m", "agent.controller", "dispatch-session", work_item_id]
    if intent["intent_type"] == contract.RECORD_SESSION_OUTCOME:
        command = [sys.executable, "-m", "agent.controller", "session-outcome", work_item_id,
                   "--dispatch", payload["dispatch_id"],
                   "--outcome", payload["outcome"],
                   "--summary", payload["summary"]]
        if payload.get("session_id"):
            command += ["--session-id", payload["session_id"]]
        if payload.get("reference"):
            command += ["--reference", payload["reference"]]
        if payload.get("delivery_id"):
            command += ["--delivery-id", payload["delivery_id"]]
        return command
    raise ValueError("no controller transport for %r" % intent["intent_type"])


def controller_environment(intent, environ=None):
    """The subprocess environment, carrying which intent authorized this run.

    Since Phase 4 the Controller's orchestrating commands expect to be launched
    here rather than typed, so the intent id travels with the invocation and
    comes back on the result. It is provenance, not a credential: it says WHICH
    intake caused this run, and the Controller still re-derives every
    authorization, claim and lifecycle fact from canonical sources regardless.
    """
    return dict(environ if environ is not None else os.environ,
                **{INTENT_ENV: intent["intent_id"]})


def run_controller(intent, timeout=DEFAULT_TIMEOUT_SECONDS, root=ROOT):
    """Invoke the Controller once, in its own process, and return what it said."""
    command = argv_for(intent)
    try:
        completed = subprocess.run(command, cwd=root, capture_output=True,
                                   text=True, timeout=timeout, shell=False,
                                   env=controller_environment(intent))
    except subprocess.TimeoutExpired:
        return {"transport": "timeout",
                "detail": "controller did not return within %ss" % timeout}
    except OSError as exc:
        return {"transport": "unavailable", "detail": str(exc)}
    try:
        result = json.loads(completed.stdout)
    except ValueError:
        return {"transport": "unreadable",
                "detail": "controller produced no JSON result",
                "exit_code": completed.returncode,
                "stderr": (completed.stderr or "")[-2000:]}
    if not isinstance(result, dict):
        return {"transport": "unreadable", "detail": "controller result is not an object",
                "exit_code": completed.returncode}
    return {"transport": "returned", "exit_code": completed.returncode,
            "controller_exit_status": completed.returncode, "result": result}


def classify(transport_outcome):
    """Map one controller invocation onto a Listener DELIVERY state."""
    if transport_outcome.get("transport") != "returned":
        return store.FAILED, transport_outcome.get("transport")
    result = transport_outcome["result"]
    if result.get("ceo_input_required") or result.get("execution_status") == "needs_input":
        return store.WAITING_INPUT, "ceo-input-required"
    return store.COMPLETED, "controller-answered"


def dispatch(intent_id, runner=run_controller, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Dispatch one intent exactly once, and settle it durably.

    Returns None when the intent was not eligible — already dispatched, already
    settled, or taken by another worker in the same instant. That is the normal
    answer to a duplicate, not an error.
    """
    claimed = store.begin_dispatch(intent_id)
    if claimed is None:
        return None
    outcome = runner(claimed, timeout=timeout)
    delivery_state, reason = classify(outcome)
    record, result, settled = store.settle(intent_id, delivery_state, outcome, reason)
    return {"intent_id": intent_id, "delivery_state": record["delivery_state"],
            "delivery_reason": record.get("delivery_reason"), "settled": settled,
            "result": result}
