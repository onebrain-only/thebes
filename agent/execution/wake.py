"""Core-owned ordering around one already-authorized Product execution wake."""


class WakeOrderError(ValueError):
    pass


def execute_product_wake(provider, work_item_id, seat_id, reason_ref,
                         request_factory, state_store=None,
                         closed_by="orchestrator"):
    """Gate, lease, build the request, execute once, and close the lease.

    ``request_factory`` runs only after the execution lease exists and receives
    ``(authoritative_task, lease)``. Selection, claim, Product authorization,
    routing, and lifecycle decisions happen before this helper and remain outside
    both the provider and this ordering seam.
    """
    if state_store is None:
        from agent.state import store as state_store

    task = state_store.assert_execution_permitted(work_item_id, seat_id)
    lease = state_store.open_execution_lease(work_item_id, seat_id, reason_ref)
    try:
        request = request_factory(task, lease)
        _validate_request_order(request, task, lease, work_item_id, seat_id)
        return provider.execute(request)
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
