#!/usr/bin/env python3
"""Wave 8 — advisory domain telemetry.

ADVISORY. NOTHING HERE IS WORKFLOW AUTHORITY.

No function in this module is consulted by claimability, ownership, validation,
lifecycle or ACCELERATE. Deleting every event record would change no decision the
system makes; it would only make the read side honestly poorer. That is the whole
test of "advisory", and it is asserted by tests rather than promised here.

WHY SO FEW EVENT TYPES
  Most workflow facts are already durable — executor_evidence appends, policies and
  interventions keep their cleared records, dependencies are records, and Jira's
  changelog reconstructs lifecycle. Emitting events for those would create a second
  copy of an authority that already exists, and a second copy drifts. Events are
  written ONLY where a fact is otherwise destroyed or never stored at all.

THE THREE
  review_decided        `review_context` is CURRENT state: reopening a failed review
                        overwrites the previous cycle's result and evidence_ref, so
                        WHY a review failed does not survive today.
  blocker_observed      `unclaimable_reasons` is derived per call and kept nowhere,
                        so nothing records that an item WAS blocked, or how long for.
  acceleration_outcome  a plan and its terminal condition are derived then discarded;
                        the policy record says a run happened, never what it did.

BLOCKERS ARE EDGES, NOT SAMPLES
  A blocker event is written only when the blocker SET CHANGES. Polling the same
  unchanged blocker a hundred times must produce nothing — otherwise the act of
  looking would manufacture the repetition that learning later reads as a pattern,
  and the system would learn from its own observation frequency.

TELEMETRY MUST NOT BE ABLE TO BREAK WORKFLOW
  `emit` never raises. An authoritative operation that has already committed must
  never be undone, retried or reported invalid because an advisory write failed
  afterwards. There is deliberately NO transaction spanning task state and events —
  claiming one would be a lie about what the filesystem guarantees. Instead the gap
  becomes VISIBLE: `completeness()` reports facts whose event is missing, so a
  retrospective can say "telemetry is incomplete" rather than quietly under-reporting.

Stdlib only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store                                            # noqa: E402


# ---------------------------------------------------------------- emit

def emit(record):
    """Append a domain event, best-effort. NEVER raises. Returns the event or None.

    The swallowed exception is the point: this is called after an authoritative write
    has already succeeded, and an advisory failure must not propagate into it.
    """
    try:
        return store.append_event(record)
    except Exception:                                    # noqa: BLE001 - deliberate
        return None


def emit_review_decided(task, evidence_ref=None):
    """Record a review verdict — the fact `review_context` destroys on reopen."""
    rc = (task or {}).get("review_context") or {}
    if rc.get("review_result") not in ("pass", "fail"):
        return None
    prof = task.get("execution_profile") or {}
    return emit({
        "event_type": "review_decided",
        "work_item_id": task.get("work_item_id"),
        # No project_id/product_id: an event REFERENCES the work item, and the
        # project is derivable from it. Carrying it would couple an advisory record
        # to the Project registry for no analytical gain.
        "required_capability": prof.get("required_capability"),
        "review_type": rc.get("review_type"),
        "review_cycle": rc.get("review_cycle"),
        "review_result": rc.get("review_result"),
        "review_owner": rc.get("review_owner"),
        "evidence_ref": rc.get("evidence_ref") or evidence_ref,
        "decided_at": rc.get("decided_at") or store.now(),
    })


# ---------------------------------------------------------------- blockers

def _safe_read(event_type=None, work_item_id=None):
    """Advisory READS must not raise into orchestration either.

    `emit` already refuses to break an authoritative write. This closes the other
    half: the canonical reconciliation boundary calls telemetry to work out which
    edges changed, and a broken or unreadable event store must degrade to "no
    history" rather than propagate an exception into planning.
    """
    try:
        return store.read_events(event_type, work_item_id)
    except Exception:                                    # noqa: BLE001 - deliberate
        return []


def open_blockers(work_item_id, events=None):
    """Reason codes whose LATEST recorded edge is `entered`. Derived, never stored.

    Deriving the open set from the event log itself is what keeps the edge model
    honest — there is no separate "current blockers" field to fall out of step with
    the transitions that produced it.
    """
    evs = events if events is not None else _safe_read("blocker_observed", work_item_id)
    latest = {}
    for e in evs:
        if e.get("work_item_id") != work_item_id:
            continue
        latest[e.get("reason_code")] = e
    return {code for code, e in latest.items() if e.get("transition") == "entered"}


def _occurrence(work_item_id, reason_code, events):
    """How many times this blocker has ENTERED before. A reappearance is a new fact."""
    return 1 + sum(1 for e in events
                   if e.get("work_item_id") == work_item_id
                   and e.get("reason_code") == reason_code
                   and e.get("transition") == "entered")


def observe_blockers(work_item_id, reason_codes, capability=None):
    """Record only the CHANGES between the last observed blocker set and this one.

    Unchanged -> nothing is written. That is the difference between a factual record
    of being blocked and a record of how often somebody looked.
    """
    evs = _safe_read("blocker_observed", work_item_id)
    current = set(reason_codes or [])
    open_now = open_blockers(work_item_id, evs)
    written = []
    for code in sorted(current - open_now):
        ev = emit({"event_type": "blocker_observed", "work_item_id": work_item_id,
                   "required_capability": capability,
                   "reason_code": code, "transition": "entered",
                   "occurrence": _occurrence(work_item_id, code, evs),
                   "entered_at": store.now()})
        if ev:
            written.append(ev); evs = evs + [ev]
    for code in sorted(open_now - current):
        prior = [e for e in evs if e.get("reason_code") == code
                 and e.get("transition") == "entered"]
        occ = prior[-1].get("occurrence") if prior else 1
        ev = emit({"event_type": "blocker_observed", "work_item_id": work_item_id,
                   "required_capability": capability,
                   "reason_code": code, "transition": "cleared", "occurrence": occ,
                   "entered_at": prior[-1].get("entered_at") if prior else None,
                   "cleared_at": store.now()})
        if ev:
            written.append(ev); evs = evs + [ev]
    return written


def blocker_episodes(work_item_id=None):
    """Paired entered/cleared edges. An OPEN blocker gets NO duration — not zero,
    not "so far": a duration needs two trustworthy timestamps and it has one."""
    evs = _safe_read("blocker_observed", work_item_id)
    out, open_ = [], {}
    for e in evs:
        key = (e.get("work_item_id"), e.get("reason_code"), e.get("occurrence"))
        if e.get("transition") == "entered":
            open_[key] = e
        else:
            start = open_.pop(key, None)
            out.append({"work_item_id": e.get("work_item_id"),
                        "reason_code": e.get("reason_code"),
                        "occurrence": e.get("occurrence"),
                        "entered_at": (start or {}).get("entered_at") or e.get("entered_at"),
                        "cleared_at": e.get("cleared_at"), "open": False})
    for key, e in open_.items():
        out.append({"work_item_id": key[0], "reason_code": key[1], "occurrence": key[2],
                    "entered_at": e.get("entered_at"), "cleared_at": None,
                    "duration": None, "open": True})
    return out


# ---------------------------------------------------------------- acceleration

def emit_acceleration_outcome(policy, plan, max_simultaneous_owners=None,
                              unused_capacity_reason=None):
    """One ACTIVATION, one terminal outcome.

    Identity is the policy_id, deliberately not a timestamp: a retried write must not
    forge a second run. Re-emitting for the same activation returns the first record.
    """
    plans = (plan or {}).get("plans") or []
    return emit({
        "event_type": "acceleration_outcome",
        "policy_id": (policy or {}).get("policy_id"),
        "scope": (policy or {}).get("scope"),
        "target": (policy or {}).get("target"),
        "condition": (plan or {}).get("condition"),
        "capabilities": (plan or {}).get("capabilities"),
        "selected_count": sum(len(p.get("selected") or []) for p in plans),
        "deferred_count": sum(len(p.get("deferred") or []) for p in plans),
        "max_simultaneous_owners": max_simultaneous_owners,
        "blocked_reasons": (plan or {}).get("blocked_reasons"),
        "unused_capacity_reason": unused_capacity_reason,
        "expansion_justified": any(p.get("expansion_justified") for p in plans),
    })


# ---------------------------------------------------------------- coverage markers

def wave8_boundary():
    """When Wave 8 began observing. Established once, on first reconciliation.

    Everything factual that happened BEFORE this instant is `historical-derived`, and
    its absence from the event log is not a defect — the system could not have
    recorded what it had no code to record. Without this line every pre-Wave-8 review
    and ACCELERATE run would be reported as missing telemetry, which would be false.
    """
    rec = store.read_coverage(store.COVERAGE_SYSTEM)
    if rec and rec.get("wave8_started_at"):
        return rec["wave8_started_at"]
    started = store.now()
    try:
        store.mark_coverage(store.COVERAGE_SYSTEM, wave8_started_at=started)
    except Exception:                                    # noqa: BLE001 - advisory
        return started
    return started


def mark_blocker_coverage(work_item_id):
    """Record that this item's blocker truth WAS reconciled. Zero != unknown."""
    try:
        return store.mark_coverage(work_item_id, blocker_observed_at=store.now())
    except Exception:                                    # noqa: BLE001 - advisory
        return None


def blocker_coverage_known(work_item_id):
    rec = store.read_coverage(work_item_id)
    return bool(rec and rec.get("blocker_observed_at"))


# ---------------------------------------------------------------- completeness

def completeness(tasks=None, policies=None):
    """Coverage per DIMENSION. `overall` is complete only if every dimension is.

    The previous shape exposed a single `complete` flag computed from review history
    alone, so a runtime with one review event and no blocker or acceleration coverage
    reported `complete: True`. That was not a partial answer, it was a wrong one: a
    retrospective reading it would present unobserved blockers as observed absence.

    Each dimension now answers separately, and each distinguishes ZERO from UNKNOWN.
    """
    tasks = store.read_all("task") if tasks is None else tasks
    boundary = (store.read_coverage(store.COVERAGE_SYSTEM) or {}).get("wave8_started_at")

    # ---- review history -------------------------------------------------
    decided = {(e.get("work_item_id"), e.get("review_type"), e.get("review_cycle"))
               for e in _safe_read("review_decided")}
    missing_reviews, historical_reviews = [], []
    for t in tasks:
        rc = t.get("review_context") or {}
        if rc.get("review_result") not in ("pass", "fail"):
            continue
        key = (t.get("work_item_id"), rc.get("review_type"), rc.get("review_cycle"))
        if key in decided:
            continue
        row = {"work_item_id": t.get("work_item_id"),
               "review_type": rc.get("review_type"),
               "review_cycle": rc.get("review_cycle")}
        # Decided BEFORE Wave 8 existed: historical-derived, not a missing event.
        if boundary and (rc.get("decided_at") or "") < boundary:
            historical_reviews.append(dict(row, why="decided before Wave 8 began"))
        else:
            missing_reviews.append(dict(row, why="settled review with no wave8-event"))
    review = {"status": "complete" if not missing_reviews else "incomplete",
              "missing": missing_reviews, "historical_derived": historical_reviews,
              "recorded": len(decided)}

    # ---- blocker coverage -----------------------------------------------
    observed, unknown = [], []
    for t in tasks:
        (observed if blocker_coverage_known(t.get("work_item_id")) else unknown)\
            .append(t.get("work_item_id"))
    edges = _safe_read("blocker_observed")
    blocker = {
        "status": ("complete" if tasks and not unknown else
                   "unknown" if not observed else "partial"),
        "observed_items": sorted(observed), "unknown_items": sorted(unknown),
        "edges_recorded": len(edges),
        "note": ("An item with no edges AND no coverage marker is UNKNOWN, not zero. "
                 "Zero blockers is only a fact once observation has happened."),
    }

    # ---- acceleration history -------------------------------------------
    pols = store.read_all("policy") if policies is None else policies
    covered = {e.get("policy_id") for e in _safe_read("acceleration_outcome")}
    missing_runs, historical_runs = [], []
    for p in pols:
        if p.get("policy_kind") != "accelerate" or p["policy_id"] in covered:
            continue
        row = {"policy_id": p["policy_id"], "scope": p.get("scope"),
               "target": p.get("target")}
        if boundary and (p.get("activated_at") or "") < boundary:
            historical_runs.append(dict(row, why="activated before Wave 8 began"))
        else:
            missing_runs.append(dict(row, why="activation with no terminal outcome"))
    accel = {"status": "complete" if not missing_runs else "incomplete",
             "covered_runs": sorted(covered), "missing_terminal_outcomes": missing_runs,
             "historical_derived": historical_runs}

    dims = (review["status"], blocker["status"], accel["status"])
    if all(d == "complete" for d in dims):
        overall = "complete"
    elif any(d in ("incomplete", "unknown") for d in dims) and \
            any(d == "complete" for d in dims):
        overall = "partial"
    else:
        overall = "incomplete"

    return {
        "review_history": review,
        "blocker_coverage": blocker,
        "acceleration_history": accel,
        "historical_boundary": {
            "wave8_started_at": boundary,
            "note": ("Wave 8 events begin at this instant. Facts older than it are "
                     "historical-derived and are NEVER backfilled as events."),
        },
        "overall": overall,
        "wave8_events": len(_safe_read()),
        # `complete` is kept as a strict alias so no caller can read a partial
        # answer as a whole one: it is true only when EVERY dimension is complete.
        "complete": overall == "complete",
    }
