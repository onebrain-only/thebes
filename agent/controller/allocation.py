"""Deterministic controller-side allocation for one unowned Product task.

The neutral registry is the active seat pool.  This module derives a candidate
from that pool; it neither claims work nor changes lifecycle.  ``store.claim``
remains the atomic final authority, so a candidate can become unavailable only
as a normal claim-time race that claim will refuse.
"""


class SeatAllocationError(ValueError):
    pass


def select_claim_seat(task, seats, all_tasks):
    """Return one free exact-capability seat, or raise a factual allocation error.

    ``execution_profile.pinned_seat_id`` is the sole optional active pin.  It is
    deliberately distinct from historical ``executor_evidence``: past assessment
    or execution is not an allocation decision.  Seats absent from the supplied
    neutral registry are inactive and therefore cannot be selected.
    """
    profile = (task or {}).get("execution_profile") or {}
    capability = profile.get("required_capability")
    if not capability:
        raise SeatAllocationError("work item has no required capability")

    declared = {
        seat_id: entry for seat_id, entry in (seats or {}).items()
        if isinstance(entry, dict) and entry.get("capability") == capability
    }
    pin = profile.get("pinned_seat_id")
    if pin is not None:
        if not isinstance(pin, str) or not pin.strip():
            raise SeatAllocationError("pinned seat id must be non-empty text")
        if pin not in declared:
            raise SeatAllocationError(
                "pinned seat %s is not an active %s seat" % (pin, capability)
            )
        candidates = [pin]
    else:
        candidates = sorted(declared)

    busy = {
        (row.get("ownership") or {}).get("seat_id")
        for row in (all_tasks or ())
        if isinstance(row, dict) and (row.get("ownership") or {}).get("seat_id")
    }
    free = [seat_id for seat_id in candidates if seat_id not in busy]
    if free:
        return free[0]
    if pin is not None:
        raise SeatAllocationError("pinned seat %s already owns active work" % pin)
    if not candidates:
        raise SeatAllocationError("no active seats declared for capability %s" % capability)
    raise SeatAllocationError("no free active seats for capability %s" % capability)
