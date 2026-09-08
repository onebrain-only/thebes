#!/usr/bin/env python3
"""The minimum capacity model — five questions, no forecasting.

WHAT THIS REPLACED

  Until Wave 6 the sitting count came from a Team Lead and `po` turned it into a
  `due_date`. That was the last thing those seats did that nothing else could, and it
  is why they survived Wave 5. This module makes the number derivable, so the seats
  can go.

WHAT THIS IS NOT

  Not a prediction engine, not utilisation scoring, not analytics. It answers five
  operational questions and stops. Anything that looks like forecasting is Wave 8's
  and does not belong here.

  Work Effort is the existing sitting/ceiling concept. It is NOT reasoning effort,
  and nothing here converts one into the other.

Stdlib only.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import queue as q                                       # noqa: E402

TOPOLOGY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "registry", "topology.json")


def topology():
    with open(TOPOLOGY, encoding="utf-8") as fh:
        return json.load(fh)["capabilities"]


def seats_for(capability, seats_by_capability):
    return list(seats_by_capability.get(capability, ()))


# ---- A. does a seat already own work? ---------------------------------------

def owned_by(seat_id, tasks):
    for t in tasks:
        if (t.get("ownership") or {}).get("seat_id") == seat_id:
            return t.get("work_item_id")
    return None


def busy_seats(capability, tasks, seats_by_capability):
    return {s for s in seats_for(capability, seats_by_capability)
            if owned_by(s, tasks)}


def free_seats(capability, tasks, seats_by_capability):
    """A DEFINED seat with no current ownership. A dormant seat is not unavailable —
    it simply owns nothing."""
    return sorted(set(seats_for(capability, seats_by_capability))
                  - busy_seats(capability, tasks, seats_by_capability))


# ---- B/C. queue depth vs available seats ------------------------------------

def claimable_items(capability, tasks, **kw):
    return [t for t in tasks
            if q.capability_of(t) == capability and q.claimable(t, all_tasks=tasks, **kw)]


# ---- D. is another seat justified? ------------------------------------------

def expansion_justified(capability, tasks, seats_by_capability, **kw):
    """Proven parallel demand only. Returns (bool, reason).

    The bar is deliberately high, and the second clause is the important one: a queue
    with two items does NOT justify a new seat while a defined seat sits dormant. Use
    the seats that exist first.
    """
    cfg = topology().get(capability)
    if cfg is None:
        return False, "unknown-capability"
    if not cfg.get("expandable"):
        return False, "capability-not-expandable"
    defined = seats_for(capability, seats_by_capability)
    if len(defined) >= cfg["ceiling"]:
        return False, "at-ceiling"
    free = free_seats(capability, tasks, seats_by_capability)
    if free:
        return False, "existing-seat-dormant"
    items = claimable_items(capability, tasks, **kw)
    if len(items) < 2:
        return False, "no-parallel-demand"
    # Mutually contended work cannot run in parallel, so a second seat would not help.
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if not q.surfaces_collide(a.get("surfaces"), b.get("surfaces")):
                return True, "parallel-demand"
    return False, "queued-work-mutually-contended"


def next_seat_id(capability, seats_by_capability, historical_ids=()):
    """<role-id>-<next unused positive integer>. Never recycles an id that carries
    durable historical evidence — a reused id would attach one seat's history to
    another, and status files are the executor evidence the whole model rests on."""
    used = set(seats_by_capability.get(capability, ())) | set(historical_ids)
    n = 1
    while "%s-%d" % (capability, n) in used:
        n += 1
    return "%s-%d" % (capability, n)


# ---- E. does the work visibly not fit? --------------------------------------

def overflow(capability, tasks, seats_by_capability, **kw):
    """Work that cannot fit the seats that exist. Exposed, never silently absorbed."""
    items = claimable_items(capability, tasks, **kw)
    effort = sum((t.get("execution_profile") or {}).get("work_effort") or 0
                 for t in items)
    seats = len(seats_for(capability, seats_by_capability)) or 1
    return {"capability": capability, "claimable": len(items),
            "total_work_effort": effort, "defined_seats": seats,
            "free_seats": len(free_seats(capability, tasks, seats_by_capability)),
            "sittings_per_seat": round(effort / seats, 2)}


if __name__ == "__main__":
    import store, validate
    tasks = store.read_all("task")
    sbc = validate.seats_by_capability()
    for cap in sorted(topology()):
        if cap in sbc or topology()[cap]["defined_seats"]:
            ok_, why = expansion_justified(cap, tasks, sbc)
            print("  %-17s seats=%-2d free=%-2d expand=%-5s (%s)"
                  % (cap, len(seats_for(cap, sbc)),
                     len(free_seats(cap, tasks, sbc)), ok_, why))
