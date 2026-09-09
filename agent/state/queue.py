#!/usr/bin/env python3
"""Capability queues, eligibility and claimability — all DERIVED, never stored.

WHY NOTHING HERE IS PERSISTED

  A stored queue is a second authority that drifts from Jira the moment anything
  moves. A stored `claimable` flag is worse: it is true only for the instant it was
  computed, and every reader after that is trusting a stale boolean. So queue
  membership, eligibility, claimability and blocked-ness are all recomputed on read,
  exactly as Wave 4 refused to store dependency satisfaction and Wave 5 refused to
  store blocked-ness.

QUEUE IDENTITY IS THE CAPABILITY

  Not the hierarchy, not a Team Lead, not the frontend/backend pair, not a project
  manager's routing. One executable work item has one `required_capability`, and that
  is the queue it sits in.

READY IS NOT CLAIMABLE

  Ready means selected and prepared. Claimable means every execution prerequisite
  holds right now — no owner, nothing blocking it, no intervention, no collision with
  work already in flight. An item can sit in Ready for days and never be claimable,
  and that is a correct state, not a stall.

Stdlib only.
"""
import os, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import board                                            # noqa: E402
import policy                                           # noqa: E402

# How old a lifecycle observation may be and still back a claim commit. Matches the
# horizon documented in README; a claim is the one operation where a stale read
# would hand work to a seat the board has already moved on from.
CLAIM_FRESHNESS_SECONDS = 900

READY_STATUS_ID = "10008"


# ---------------------------------------------------------------- helpers

def _parse(ts):
    if not ts:
        return None
    t = str(ts).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def capability_of(task):
    return (task.get("execution_profile") or {}).get("required_capability")


def is_executable(task):
    return task.get("record_type") == "executable"


# ---------------------------------------------------------------- eligibility

def eligibility_reasons(task, jira=None):
    """Why this item is NOT queue-eligible. Empty list means it is.

    `jira` carries the facts only a live read can establish — the status id, whether
    a due_date exists, whether acceptance criteria exist. They are parameters rather
    than lookups because this module is stdlib-only and must stay testable without a
    network. Omitting them is not treated as a pass: it yields `unverified-jira`.
    """
    out = []
    if not is_executable(task):
        out.append("not-executable")
        return out

    lc = task.get("lifecycle") or {}
    status = str((jira or {}).get("status_id") or lc.get("jira_status_id") or "")
    if board.canonical_for(status) != board.READY or status != READY_STATUS_ID:
        out.append("not-ready")

    prof = task.get("execution_profile") or {}
    if not task.get("project_id"):
        out.append("missing-project")
    if not prof.get("required_capability"):
        out.append("missing-capability")
    if prof.get("work_effort") is None:
        out.append("missing-work-effort")

    if jira is None:
        out.append("unverified-jira")
    else:
        if not jira.get("has_due_date"):
            out.append("missing-due-date")
        if not jira.get("has_acceptance_criteria"):
            out.append("missing-acceptance-criteria")
    return out


def queue(tasks, capability, jira_by_key=None):
    """Every queue-eligible item for one capability. Backlog is NOT a queue."""
    jira_by_key = jira_by_key or {}
    return sorted(
        (t for t in tasks
         if capability_of(t) == capability
         and not eligibility_reasons(t, jira_by_key.get(t.get("work_item_id")))),
        key=lambda t: t.get("work_item_id", ""))


def queues(tasks, jira_by_key=None):
    caps = {capability_of(t) for t in tasks if capability_of(t)}
    return {c: queue(tasks, c, jira_by_key) for c in sorted(caps)}


# ---------------------------------------------------------------- contention

def surfaces_collide(a_surfaces, b_surfaces):
    """Do two declared path sets actually collide under the system-owned rules?

    NOT "are both booleans true". Two items can each touch a shared surface and never
    meet — collapsing that into one boolean is what made the old flag useless for
    scheduling and is why the Team Lead had to sequence by hand.

    A collision is an exact path match, or a shared-prefix overlap where BOTH paths
    sit under the same governed shared prefix (lib/core/**, lib/data/**), or a
    directory containment where one path is an ancestor of the other.
    """
    A = {policy.normalise_path(p) for p in (a_surfaces or [])}
    B = {policy.normalise_path(p) for p in (b_surfaces or [])}
    if A & B:
        return True
    for a in A:
        for b in B:
            if a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/"):
                return True
            for pre in policy.SHARED_PREFIXES:
                if a.startswith(pre) and b.startswith(pre):
                    # Same governed shared surface. CONTRACT.md §4's discipline is
                    # one agent inside at a time.
                    return True
    return False


# --------------------------------------------------- logical-object compatibility
#
# A NARROW COMPATIBILITY MECHANISM, NOT A MODEL OF THE DATABASE.
#
# File surfaces are the canonical contention model and are unchanged. They cannot see
# a collision that exists only in the database: two migrations touching one PostgreSQL
# function collide with no shared path. `settle_game` and `trgfn_payment_to_ledger`
# are the cases actually encountered, and they are EXAMPLES, not the architecture.
#
# So this reads an OPTIONAL, declared `logical_surfaces` list off the task. It is
# deliberately separate from `surfaces`, trivial to extend and trivial to delete when
# a real model replaces it.
#
# THE CONSERVATIVE RULE, and the whole point of keeping it separate:
#   declared overlap  -> the tasks SERIALIZE.
#   nothing declared  -> file-surface rules still apply, and NOTHING here licenses a
#                        claim that no logical contention exists. Absence of evidence
#                        is not evidence of safety — the same rule `surfaces: null`
#                        already enforces for paths.

def logical_objects(task):
    """Declared logical objects, normalised. Absence is UNKNOWN, never 'none'."""
    return {str(o).strip().lower()
            for o in ((task or {}).get("logical_surfaces") or []) if str(o).strip()}


def logical_collide(a, b):
    """Do two tasks declare a factual overlap on the same logical object?"""
    return bool(logical_objects(a) & logical_objects(b))


def contends(a, b):
    """The full contention question: file surfaces OR declared logical objects.

    Callers should use this rather than `surfaces_collide` alone wherever they are
    deciding whether two items may run concurrently.
    """
    return surfaces_collide(a.get("surfaces"), b.get("surfaces")) or logical_collide(a, b)


def surfaces_assessed(task):
    """Has this item's surface scope been assessed at all?

    `null` means nobody has looked. `[]` means somebody looked and found nothing to
    declare. Collapsing the two is what made contention protection inert.
    """
    return task.get("surfaces") is not None


def contending_owner(task, all_tasks):
    """The work_item_id of an OWNED task whose surfaces collide with this one.

    Defensive: an UNASSESSED task must never reach a "no collision" conclusion here.
    Claimability rejects it first (`surfaces-unassessed`); if one arrives anyway that
    is a caller bug, and answering "None" would be the exact silent failure this
    function was rewritten to prevent.
    """
    if not surfaces_assessed(task):
        raise ValueError(
            "surfaces are UNASSESSED for %s — contention cannot conclude 'no collision' "
            "from an absence. Claimability must reject this before contention is "
            "evaluated." % task.get("work_item_id"))
    mine = task.get("surfaces") or []
    if not mine and not logical_objects(task):
        # Assessed and empty, with no declared logical object either: a real answer.
        return None
    for other in all_tasks:
        if other.get("work_item_id") == task.get("work_item_id"):
            continue
        if not (other.get("ownership") or {}).get("seat_id"):
            continue
        # File surfaces are canonical; a declared logical overlap serializes as well,
        # so an empty path set does not make a database collision invisible.
        if contends(task, other):
            return other.get("work_item_id")
    return None


# ---------------------------------------------------------------- claimability

def unclaimable_reasons(task, all_tasks=None, edges=None, lifecycles=None,
                        interventions=None, jira=None, jira_status_id=None, now=None):
    """Structured reasons this item cannot be claimed right now. Empty = claimable.

    Reasons are codes, not prose, so the Orchestrator can report *why* work is
    waiting instead of reporting that nothing happened.
    """
    import store                                        # noqa: E402
    import validate                                     # noqa: E402

    all_tasks = store.read_all("task") if all_tasks is None else all_tasks
    edges = ([e for e in store.read_all("dependency") if not e.get("retired_at")]
             if edges is None else edges)
    interventions = (store.active_interventions()
                     if interventions is None else interventions)
    key = task.get("work_item_id")
    cap = capability_of(task)
    out = []

    if jira is None and jira_status_id is not None:
        jira = {"status_id": jira_status_id, "has_due_date": True,
                "has_acceptance_criteria": True}
    out += eligibility_reasons(task, jira)

    if task.get("ownership") is not None:
        out.append("already-owned")

    if lifecycles is None:
        lifecycles = {t.get("work_item_id"): (t.get("lifecycle") or {}).get("canonical")
                      for t in all_tasks}
    if validate.is_blocked(key, edges, lifecycles):
        out.append("dependency-blocked")

    iv = store.intervention_blocks_claim(key, cap, interventions)
    if iv:
        out.append(iv)

    # Order matters: UNKNOWN scope is rejected BEFORE contention is consulted, so a
    # missing assessment can never be mistaken for a clean one.
    if not surfaces_assessed(task):
        out.append("surfaces-unassessed")
    elif contending_owner(task, all_tasks):
        out.append("surface-contention")

    ev = task.get("executor_evidence") or []
    # Assessment entries are excluded: a Preflight sizing report is not a competing
    # executor, and counting it as one made completed work unclaimable and
    # unreviewable (KAN-136, KAN-138, 2026-09-09).
    if len({e.get("seat_id") for e in ev if isinstance(e, dict)
            and e.get("classification", "execution") == "execution"}) > 1:
        # Two or more evidenced seats is CONFLICTING evidence. It blocks and requires
        # reconciliation — it does not fall back to anyone choosing.
        out.append("conflicting-evidence")

    obs = _parse((task.get("lifecycle") or {}).get("observed_at"))
    ref = now or datetime.now(timezone.utc)
    if jira_status_id is None:
        if obs is None or (ref - obs) > timedelta(seconds=CLAIM_FRESHNESS_SECONDS):
            out.append("stale-jira")

    seen, uniq = set(), []
    for r in out:
        if r not in seen:
            seen.add(r); uniq.append(r)
    return uniq


# ---------------------------------------------------------------- continuation
#
# CLAIM GATE vs CONTINUATION GATE — two different questions, deliberately not merged.
#
#   claimability      "may this UNOWNED work obtain an owner?"
#   execution gate    "may this ALREADY-OWNED seat be orchestrated to continue now?"
#
# Overloading claimability to answer both is how STOP became inert: for an owned task
# claimability already returns `already-owned`, so `task-stopped` alongside it changed
# nothing, and nothing was consulted before waking the existing owner again.

def execution_reasons(task, seat_id, interventions=None):
    """Why this seat may NOT be orchestrated to continue this task. Empty = permitted.

    Run this before EVERY execution wake — the initial one after a claim, a same-seat
    continuation, and a resumed invocation.

    HOLD and FREEZE deliberately do NOT appear here. They block *new claims*; a
    current owner continues. Only a task-scoped STOP stops the work in flight.
    """
    import store                                        # noqa: E402
    out = []
    own = task.get("ownership")
    if not own:
        out.append("not-owned")
    elif own.get("seat_id") != seat_id:
        out.append("not-owner")

    ivs = store.active_interventions() if interventions is None else interventions
    key = task.get("work_item_id")
    for iv in ivs:
        if iv.get("kind") == "stop" and iv.get("target") == key:
            out.append("task-stopped")
            break
    return out


# ---------------------------------------------------------------- review work
#
# DERIVED, and it reuses the review semantics that already exist rather than adding a
# second authority over who reviews what. The owner was decided by policy and recorded
# by store.open_review_context; this only reports what is outstanding.

def review_work(tasks, capability=None):
    """Open reviews with an exact owner — schedulable review work.

    A PEER item whose `review_owner` is null is DELIBERATELY excluded. It is waiting
    for an authorised reviewer, and acceleration must not treat waiting as a problem
    to solve by picking one.
    """
    out = []
    for t in tasks or []:
        rc = t.get("review_context")
        if not isinstance(rc, dict) or rc.get("review_result") != "pending":
            continue
        if not rc.get("review_owner"):
            continue
        if capability is not None and capability_of(t) != capability:
            continue
        out.append(t)
    return sorted(out, key=lambda t: t.get("work_item_id") or "")


def review_waiting(tasks):
    """Open reviews with NO owner — reported, never filled by inference."""
    return sorted((t for t in tasks or []
                   if isinstance(t.get("review_context"), dict)
                   and t["review_context"].get("review_result") == "pending"
                   and not t["review_context"].get("review_owner")),
                  key=lambda t: t.get("work_item_id") or "")


# ---------------------------------------------------------------- completion
#
# A THIRD reason namespace, kept apart from the other two on purpose:
#
#   claimability      "may this UNOWNED work obtain an owner?"
#   execution gate    "may this ALREADY-OWNED seat continue now?"
#   completion        "has this work actually passed its validation route?"
#
# Completion is DERIVED, never stored. A second stored lifecycle would be a second
# authority that drifts from the review context the moment anyone wrote to one and
# not the other — which is precisely how an item ends up marked complete having
# passed nothing.

def completion_reasons(task, interventions=None):
    """Why this item may NOT be transitioned to Done. Empty = eligible.

    The rule this enforces is `WORKFLOWS.md` §2.3: a task reaches Done only through
    its validation route, and only its review owner puts it there. Everything below
    is that sentence made checkable.

    What deliberately CANNOT make an item eligible: a Jira status of Done, a seat
    saying it validated the work, an `agent/status` entry, executor evidence on its
    own. None of them can produce a `pass` in the review context, and nothing else
    is consulted here.
    """
    import store                                        # noqa: E402
    out = []
    if not is_executable(task):
        return ["not-executable"]

    lc = (task.get("lifecycle") or {}).get("canonical")
    if lc == "done":
        out.append("already-done")
    elif lc != "review":
        # There is no path from an execution status straight to Done.
        out.append("not-in-review")

    prof = task.get("execution_profile") or {}
    if prof.get("completion_route") != "DONE":
        out.append("no-completion-route")

    rc = task.get("review_context")
    if not isinstance(rc, dict):
        # The unreconciled state: in review, with no record of a review.
        out.append("no-review-context")
    else:
        result = rc.get("review_result")
        if result != "pass":
            out.append("review-not-passed" if result != "fail" else "review-failed")
        if not rc.get("review_owner"):
            out.append("review-owner-unresolved")
        route = prof.get("validation_route")
        # The one legal divergence is the PEER-fail transfer, which sets previous_owner.
        if route and rc.get("review_type") != route and not rc.get("previous_owner"):
            out.append("review-route-mismatch")

    interventions = (store.active_interventions()
                     if interventions is None else interventions)
    key = task.get("work_item_id")
    for iv in interventions or []:
        if iv.get("kind") == "stop" and iv.get("target") == key:
            # STOP exists for a detected safety condition. Transitioning past one to
            # Done would complete exactly the work somebody stopped.
            out.append("task-stopped")
            break

    seen, uniq = set(), []
    for r in out:
        if r not in seen:
            seen.add(r); uniq.append(r)
    return uniq


def completion_eligible(task, **kw):
    return not completion_reasons(task, **kw)


def execution_permitted(task, seat_id, **kw):
    return not execution_reasons(task, seat_id, **kw)


def claimable(task, **kw):
    return not unclaimable_reasons(task, **kw)


if __name__ == "__main__":
    import store
    tasks = store.read_all("task")
    print("tasks: %d   active interventions: %d"
          % (len(tasks), len(store.active_interventions())))
    for cap, items in queues(tasks).items():
        print("  queue %-10s eligible=%d" % (cap, len(items)))
    for t in tasks:
        print("  %-8s %-10s owner=%-10s reasons=%s"
              % (t.get("work_item_id"), capability_of(t),
                 str((t.get("ownership") or {}).get("seat_id")),
                 ",".join(unclaimable_reasons(t)) or "CLAIMABLE"))
