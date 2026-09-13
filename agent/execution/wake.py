"""Core-owned ordering around one already-authorized Product execution wake."""

from dataclasses import replace

from agent.execution.result import receive_execution_result
from agent.execution.receipt import normalized_result_payload
from agent.execution.selection import select_provider


class WakeOrderError(ValueError):
    pass


def execute_product_wake(work_item_id, seat_id, reason_ref, request_factory, providers,
                         provider_override=None, state_store=None,
                         closed_by="orchestrator"):
    """Gate, lease, build, select, execute, receive, and close one request.

    ``request_factory`` runs only after the execution lease exists and receives
    ``(authoritative_task, lease)``. ``providers`` is an explicit controller
    registry, not a caller-selected executor. The existing selection policy
    chooses one compatible provider (or creates its normalized failure), and
    the existing core receipt boundary observes the normalized result. Claim,
    Product authorization, routing, and lifecycle decisions remain outside this
    ordering seam.
    """
    if state_store is None:
        from agent.state import store as state_store

    task = state_store.assert_execution_permitted(work_item_id, seat_id)
    lease = state_store.open_execution_lease(work_item_id, seat_id, reason_ref)
    try:
        request = request_factory(task, lease)
        _validate_request_order(request, task, lease, work_item_id, seat_id)
        selection = select_provider(request, providers, override=provider_override)
        if selection.provider is None:
            result = selection.failure_result(request)
        else:
            result = selection.provider.execute(request)
        normalized = receive_execution_result(result)
        # This must precede lease closure.  A caller may stop observing this wake
        # while the provider process continues; the terminal evidence remains
        # recoverable without another provider invocation.
        state_store.record_execution_receipt(
            request.invocation_id, work_item_id, seat_id,
            lease["execution_lease_id"], normalized_result_payload(normalized),
            provider_selection=selection.receipt_evidence(),
        )
        return normalized
    finally:
        state_store.close_execution_lease(
            lease["execution_lease_id"], lease["revision"], closed_by
        )


def _validate_request_order(request, task, lease, work_item_id, seat_id):
    ownership = task.get("ownership") or {}
    expected = {
        "work_item_id": work_item_id,
        "seat_id": seat_id,
        "operating_mode": "PRODUCT_EXECUTION",
        "execution_lease_id": lease["execution_lease_id"],
        "operating_mode_revision": lease["mode_revision"],
        "claim_ref": ownership.get("claim_ref"),
    }
    for field, value in expected.items():
        if getattr(request, field, None) != value:
            raise WakeOrderError(
                "prepared request %s must preserve %r" % (field, value)
            )


def execute_approved_claude_continuation(approval_id, request_factory, provider,
                                         *, state_store=None,
                                         closed_by="orchestrator"):
    """Resume exactly one Claude session after one immutable CEO approval.

    This is deliberately not provider selection or a new claim.  The original
    receipt, owner, provider, and Claude session are the authority; a fresh
    short-lived lease only protects the resumed process lifecycle.
    """
    if state_store is None:
        from agent.state import store as state_store
    approval = state_store.read_execution_approval(approval_id)
    if approval is None:
        raise WakeOrderError("continuation approval does not exist")
    original = state_store.read_execution_receipt(approval["original_invocation_id"])
    if original is None or original.get("status") != "needs_input":
        raise WakeOrderError("continuation original receipt is not awaiting input")
    if original.get("provider_id") != "claude-code" or approval.get("provider_id") != "claude-code":
        raise WakeOrderError("continuation provider must remain Claude Code")
    if provider.capabilities().provider_id != "claude-code":
        raise WakeOrderError("continuation provider switch is refused")
    invocation_id = "continuation-" + approval_id
    if state_store.read_execution_receipt(invocation_id) is not None:
        raise WakeOrderError("continuation was already executed")
    task = state_store.assert_execution_permitted(approval["work_item_id"], approval["seat_id"])
    lease = state_store.open_execution_lease(approval["work_item_id"], approval["seat_id"], approval_id)
    try:
        request = request_factory(task, lease, approval, original)
        request = replace(request, invocation_id=invocation_id,
                          work_item_id=approval["work_item_id"], seat_id=approval["seat_id"],
                          claim_ref=(task.get("ownership") or {}).get("claim_ref"),
                          execution_lease_id=lease["execution_lease_id"],
                          operating_mode_revision=lease["mode_revision"])
        _validate_request_order(request, task, lease, approval["work_item_id"], approval["seat_id"])
        result = receive_execution_result(provider.execute(request))
        state_store.record_execution_receipt(
            request.invocation_id, request.work_item_id, request.seat_id,
            lease["execution_lease_id"], normalized_result_payload(result),
            provider_selection={"primary_provider_id": "claude-code",
                                "selected_provider_id": "claude-code"},
            continuation_of=approval["original_invocation_id"], approval_id=approval_id,
        )
        return result
    finally:
        state_store.close_execution_lease(lease["execution_lease_id"], lease["revision"], closed_by)
