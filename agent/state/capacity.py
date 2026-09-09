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

def _reject_shared_jira(kw):
    """A BATCHED boundary must never take one `jira=` fact object.

    `eligibility_reasons(task, jira=...)` describes ONE item — its due date, its
    acceptance criteria, its status. Passing a single dict to a function that
    evaluates many tasks silently answers every item with some other item's facts,
    which is how a task with no due date inherits one. The unsafe call is refused
    rather than quietly reinterpreted: a caller that means "no live facts" already
    has a way to say so, which is to pass nothing and get `unverified-jira`.
    """
    if "jira" in kw:
        raise TypeError(
            "batched planning does not accept a shared `jira=` fact object — one "
            "item's due date and acceptance criteria are not another's. Pass "
            "`jira_by_key={work_item_id: facts}`; an item absent from the map is "
            "correctly reported unverified-jira.")


def _facts_for(task, jira_by_key):
    """This task's OWN Jira facts, or None. Never another task's, never invented."""
    if not jira_by_key:
        return None
    return jira_by_key.get(task.get("work_item_id"))


def claimable_items(capability, tasks, jira_by_key=None, **kw):
    """Claimable work of one capability, each item judged on ITS OWN Jira facts.

    An item with no entry in `jira_by_key` keeps the fail-closed answer
    (`unverified-jira`) — absent facts are never fabricated and never borrowed.
    """
    _reject_shared_jira(kw)
    return [t for t in tasks
            if q.capability_of(t) == capability
            and q.claimable(t, all_tasks=tasks, jira=_facts_for(t, jira_by_key), **kw)]


# ---- D. is another seat justified? ------------------------------------------

def expansion_justified(capability, tasks, seats_by_capability,
                        jira_by_key=None, **kw):
    """Proven parallel demand only. Returns (bool, reason).

    The bar is deliberately high, and the second clause is the important one: a queue
    with two items does NOT justify a new seat while a defined seat sits dormant. Use
    the seats that exist first.
    """
    _reject_shared_jira(kw)
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
    items = claimable_items(capability, tasks, jira_by_key=jira_by_key, **kw)
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

def overflow(capability, tasks, seats_by_capability, jira_by_key=None, **kw):
    """Work that cannot fit the seats that exist. Exposed, never silently absorbed."""
    _reject_shared_jira(kw)
    items = claimable_items(capability, tasks, jira_by_key=jira_by_key, **kw)
    effort = sum((t.get("execution_profile") or {}).get("work_effort") or 0
                 for t in items)
    seats = len(seats_for(capability, seats_by_capability)) or 1
    return {"capability": capability, "claimable": len(items),
            "total_work_effort": effort, "defined_seats": seats,
            "free_seats": len(free_seats(capability, tasks, seats_by_capability)),
            "sittings_per_seat": round(effort / seats, 2)}


# ---------------------------------------------------------------- ACCELERATE
#
# THE SELECTOR IS ADVISORY. `store.claim` REMAINS THE AUTHORITY.
#
# Everything below plans; nothing below writes. `store.claim` re-runs
# `unclaimable_reasons` inside the record lock immediately before its write, so a plan
# that has gone stale between planning and claiming fails there rather than producing
# an unsafe claim. That is why this module is allowed to be optimistic: it cannot be
# the thing that gets it wrong.
#
# ACCELERATE does not change WHAT IS VALID WORK. Every candidate here has already
# passed the same eligibility, claimability, dependency, contention and intervention
# predicates a normal-mode claim passes. What changes is only how many of them the
# Orchestrator fills in one pass.

DRAINED = "ACCELERATION DRAINED"
SATURATED = "ACCELERATION SATURATED"
BLOCKED = "ACCELERATION BLOCKED"


def stable_order(task):
    """The deterministic tiebreak: the work item id. Never a score."""
    return str(task.get("work_item_id") or "")


def unlock_impact(task, edges):
    """How many blocked items this task's completion would unblock. Derived."""
    key = task.get("work_item_id")
    return sum(1 for e in (edges or [])
               if not e.get("retired_at") and e.get("source_work_item") == key)


def ordering_key(task, edges=None, jira_by_key=None):
    """Deterministic factual ordering. NO invented importance score.

    1. live Jira priority, when a caller supplied it (lower rank first);
    2. due-date urgency, likewise;
    3. dependency-unlock impact, derived — most unblocking first;
    4. work_item_id, the stable tiebreak.

    A signal the caller could not supply is SKIPPED cleanly rather than guessed, and
    nothing here persists a second Jira cache: priority and due date arrive as
    parameters, exactly as `eligibility_reasons` takes its Jira facts.

    Work Effort is deliberately absent. It is a sitting count, not importance.
    """
    j = (jira_by_key or {}).get(task.get("work_item_id")) or {}
    rank = j.get("priority_rank")
    due = j.get("due_date")
    return (0 if rank is not None else 1, rank if rank is not None else 0,
            0 if due else 1, due or "",
            -unlock_impact(task, edges), stable_order(task))


def safe_parallel_plan(capability, tasks, seats_by_capability, edges=None,
                       jira_by_key=None, covers=None, **kw):
    """The most work of one capability that may safely be owned AT ONCE.

    Two independent limits, and the smaller wins:
      - free DEFINED seats (a seat owns at most one item — store.claim enforces it);
      - a mutually NON-CONTENDING subset of the claimable items.

    The second is why "8 tasks, 8 seats" does not mean eight claims. Candidates are
    walked in deterministic order and each is admitted only if it contends with
    nothing already admitted AND nothing already owned — so of two colliding items the
    higher-ordered one is planned and the other waits, which is serialisation, not loss.
    """
    free = free_seats(capability, tasks, seats_by_capability)
    _reject_shared_jira(kw)
    pool = claimable_items(capability, tasks, jira_by_key=jira_by_key, **kw)
    if covers is not None:
        # Scope is enforced HERE as well as when choosing capabilities: a
        # PRODUCT-scoped policy must not accelerate another product's work merely
        # because both share a capability.
        pool = [t for t in pool if covers(t)]
    candidates = sorted(pool, key=lambda t: ordering_key(t, edges, jira_by_key))
    owned = [t for t in tasks if (t.get("ownership") or {}).get("seat_id")]

    admitted = []
    deferred = []
    for t in candidates:
        if len(admitted) >= len(free):
            deferred.append(t.get("work_item_id"))
            continue
        if any(q.contends(t, o) for o in owned):
            deferred.append(t.get("work_item_id"))
            continue
        if any(q.contends(t, a) for a in admitted):
            deferred.append(t.get("work_item_id"))
            continue
        admitted.append(t)

    pairs = list(zip(free, [t.get("work_item_id") for t in admitted]))
    expand, why = expansion_justified(capability, tasks, seats_by_capability,
                                      jira_by_key=jira_by_key, **kw)
    return {
        "capability": capability,
        "free_seats": free,
        "claimable": [t.get("work_item_id") for t in candidates],
        "selected": [t.get("work_item_id") for t in admitted],
        "assignments": [{"seat_id": s, "work_item_id": k} for s, k in pairs],
        "deferred": deferred,
        "expansion_justified": expand,
        "expansion_reason": why,
        # A seat this planner could name is not a seat the harness can necessarily
        # wake. Dispatchability is not knowable here and is never asserted.
        "dispatchability": "UNKNOWN",
    }


def scheduler_condition(plans, tasks, capabilities, jira_by_key=None, **kw):
    """DRAINED / SATURATED / BLOCKED — derived, never stored.

    These are SCHEDULER conditions and not Jira lifecycle. None of them is DONE, and
    none is written to a task.

    BLOCKED exists because DRAINED and SATURATED cannot express the honest third case:
    work remains, none of it claimable, for structured reasons. Collapsing that into
    DRAINED would report "nothing to do" when the truth is "everything is stuck".
    """
    selected = sum(len(p["selected"]) for p in plans)
    claimable = sum(len(p["claimable"]) for p in plans)
    in_scope = [t for t in tasks if q.capability_of(t) in set(capabilities)]
    pending = [t for t in in_scope
               if not (t.get("ownership") or {}).get("seat_id")
               and (t.get("lifecycle") or {}).get("canonical") != "done"]
    if selected:
        return SATURATED if (claimable > selected or pending) else DRAINED
    if claimable:
        # Claimable work exists but no free seat could take it.
        return SATURATED
    if pending:
        return BLOCKED
    return DRAINED


def blocked_reasons(tasks, capabilities, jira_by_key=None, **kw):
    """The structured reasons in-scope work is not claimable. Reported, not solved.

    Each item is counted against its OWN facts, so a task whose Jira facts were
    supplied is never reported `unverified-jira` merely because a neighbour's were
    missing. That inaccuracy was real and is fixed at the source rather than
    patched in the reporting.
    """
    import collections
    _reject_shared_jira(kw)
    hist = collections.Counter()
    for t in tasks:
        if q.capability_of(t) not in set(capabilities):
            continue
        if (t.get("ownership") or {}).get("seat_id"):
            continue
        hist.update(q.unclaimable_reasons(t, all_tasks=tasks,
                                          jira=_facts_for(t, jira_by_key), **kw))
    return dict(sorted(hist.items()))


# ---------------------------------------------------------------- the canonical boundary

def reconcile(tasks=None, jira_by_key=None, edges=None, lifecycles=None,
              interventions=None, observe=True, now=None):
    """THE canonical orchestration reconciliation point.

    One place where the Orchestrator assembles the COMPLETE blocker truth for every
    work item — readiness, dependency, contention, interventions, Jira freshness, and
    the review blockers `completion_reasons` derives — and, having assembled it,
    records the edges.

    Why here and nowhere else: `unclaimable_reasons` is the function that combines
    those facts, but it is called from Agent View (which must never write) and from
    inside `store.claim`'s lock (where writing an advisory record would be reckless).
    Instrumenting it would put telemetry in both places. So observation belongs to the
    boundary that *plans*, not to the predicate that *answers*.

    Telemetry is emitted AFTER each item's truth is derived and never influences it.
    `observe=False` gives the same derivation with no writes, for read-only callers.
    """
    import telemetry                                     # noqa: E402
    tasks = store.read_all("task") if tasks is None else tasks
    if observe:
        telemetry.wave8_boundary()
    out = {}
    for t in tasks:
        key = t.get("work_item_id")
        cap = q.capability_of(t)
        reasons = list(q.unclaimable_reasons(
            t, all_tasks=tasks, edges=edges, lifecycles=lifecycles,
            interventions=interventions, jira=_facts_for(t, jira_by_key), now=now))
        # Review blockers are real blockers and belong in the same picture.
        for r in q.completion_reasons(t, interventions=interventions):
            if r in ("review-owner-unresolved",) and r not in reasons:
                reasons.append(r)
        out[key] = reasons
        if observe:
            telemetry.observe_blockers(key, reasons, capability=cap)
            telemetry.mark_blocker_coverage(key)
    return out


def run_acceleration(tasks, policies, seats_by_capability, edges=None,
                     jira_by_key=None, observe=True, **kw):
    """A whole ACCELERATE run: reconcile, plan, and record ONE terminal outcome.

    The terminal outcome belongs to the RUN, not to a plan. `accelerate_plan` is
    advisory and may be computed many times during a run — by the scheduler, by a
    recompute after a release, by Agent View rendering. Emitting there would turn one
    activation into many, so the event is written here, once, when the run finishes.

    Emission is idempotent on the activation, so a retry does not forge a second run,
    and it is advisory: if it fails, the run's terminal condition and the policy are
    both untouched. Clearing the policy stays a separate act — telemetry never
    controls lifecycle.
    """
    import telemetry                                     # noqa: E402
    reconcile(tasks=tasks, jira_by_key=jira_by_key, edges=edges,
              interventions=kw.get("interventions"), observe=observe)
    plan = accelerate_plan(tasks, policies, seats_by_capability, edges=edges,
                           jira_by_key=jira_by_key, **kw)
    owned = [t for t in tasks
             if (t.get("ownership") or {}).get("seat_id")
             and q.capability_of(t) in set(plan.get("capabilities") or [])]
    unused = None
    for p in plan.get("plans") or []:
        if p.get("claimable") and not p.get("free_seats"):
            unused = "no free seat for claimable work in %s" % p.get("capability")
            break
    if observe:
        for pol in policies or []:
            if pol.get("policy_kind") == "accelerate" and not pol.get("cleared_at"):
                telemetry.emit_acceleration_outcome(
                    pol, plan, max_simultaneous_owners=len(owned),
                    unused_capacity_reason=unused)
    return plan


def accelerate_plan(tasks, policies, seats_by_capability, edges=None,
                    jira_by_key=None, **kw):
    """`jira_by_key` maps work_item_id -> that item's live Jira facts.

    ONE map serves both eligibility (has_due_date, has_acceptance_criteria,
    status_id) and ordering (priority_rank, due_date), so there is no second map to
    drift and no way for one item's priority or due date to reach another's.
    Nothing is persisted: the facts arrive as a parameter and leave with the call.
    """
    """The whole accelerated schedule: every covered capability, planned independently.

    Capabilities are planned SEPARATELY and never serialised behind one another —
    unrelated frontend and backend work has no reason to wait on each other.

    Executive and management capabilities are excluded from generic acceleration:
    filling them by throughput pressure would wake `cto`/`cpo`/`pm` because a queue
    exists, and their involvement is an authority question, not a capacity one.
    """
    covered = sorted({q.capability_of(t) for t in tasks
                      if q.capability_of(t)
                      and accelerate_covers(t, policies)}
                     - EXCLUDED_FROM_ACCELERATION)
    covers = lambda t: accelerate_covers(t, policies)
    plans = [safe_parallel_plan(c, tasks, seats_by_capability, edges=edges,
                                jira_by_key=jira_by_key, covers=covers, **kw)
             for c in covered]
    return {
        "capabilities": covered,
        "plans": plans,
        "condition": scheduler_condition(plans, tasks, covered,
                                         jira_by_key=jira_by_key, **kw),
        "blocked_reasons": blocked_reasons(tasks, covered,
                                           jira_by_key=jira_by_key, **kw),
        "review_work": [t.get("work_item_id") for t in q.review_work(tasks)],
        "review_waiting": [t.get("work_item_id") for t in q.review_waiting(tasks)],
    }


# Management and executive capabilities are never filled by generic throughput
# pressure. They are woken when their exact authority is required, which is a routing
# decision and not a capacity one.
EXCLUDED_FROM_ACCELERATION = {"cto", "cpo", "cxo", "pm", "po", "analyst"}


def accelerate_covers(task, policies):
    import store                                        # noqa: E402
    return bool(store.accelerate_scopes_for(task, policies))


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
