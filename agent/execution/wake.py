"""Core-owned ordering around one already-authorized Product execution wake."""

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
