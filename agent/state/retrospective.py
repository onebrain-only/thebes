#!/usr/bin/env python3
"""Wave 8 — derived retrospective analysis.

A retrospective is a DERIVED SNAPSHOT over factual work. It is not stored, not
authoritative, and not a meeting simulation. Nothing here writes state.

THREE LAYERS, SEPARATED STRUCTURALLY
  FACT            must carry evidence_refs. A fact without a reference cannot be
                  constructed — `fact()` raises rather than returning an unsupported
                  claim, because an unevidenced fact is just prose.
  PATTERN         requires >= 2 DISTINCT factual occurrences. Distinctness is by
                  evidence reference, not by how many times something was read: if
                  polling could raise the count, the system would be learning from
                  its own observation frequency rather than from the work.
  RECOMMENDATION  must cite the pattern it derives from.

STRENGTH IS A LADDER, NOT A NUMBER
  single-observation (1) · repeated (2-3) · strong-repeated (>= 4 occurrences across
  >= 2 distinct evidence sources). Deterministic from counts alone. There is no
  confidence percentage, because a model's certainty is not a statistic and dressing
  it as one would invite exactly the false precision this layer must avoid.

WAVE-8 EVENT vs HISTORICAL-DERIVED
  Every finding declares its origin. A fact reconstructed from Persistent State, Git
  or the Jira changelog is `historical-derived`; only a recorded domain event is
  `wave8-event`. Backfilling history as events is forbidden, so anything older than
  Wave 8 is honestly labelled rather than silently promoted.

Stdlib only.
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store                                            # noqa: E402
import telemetry                                        # noqa: E402
import queue as q                                       # noqa: E402

WAVE8_EVENT = "wave8-event"
HISTORICAL = "historical-derived"

SINGLE, REPEATED, STRONG = "single-observation", "repeated", "strong-repeated"
PATTERN_MIN_OCCURRENCES = 2      # below this it is one observation, never a pattern
STRONG_MIN_OCCURRENCES = 4
STRONG_MIN_SOURCES = 2


def strength(occurrences, distinct_sources):
    """Deterministic from counts. No statistical language, no model certainty."""
    if occurrences < PATTERN_MIN_OCCURRENCES:
        return SINGLE
    if occurrences >= STRONG_MIN_OCCURRENCES and distinct_sources >= STRONG_MIN_SOURCES:
        return STRONG
    return REPEATED


def fact(statement, evidence_refs, origin=HISTORICAL, **extra):
    """A factual finding. REFUSES to exist without evidence."""
    refs = [r for r in (evidence_refs or []) if r]
    if not refs:
        raise ValueError("a FACT requires evidence_refs — an unevidenced statement is "
                         "prose, and this layer does not produce prose: %r" % statement)
    return dict({"kind": "FACT", "statement": statement, "evidence_refs": refs,
                 "origin": origin}, **extra)


def pattern(statement, facts, **extra):
    """A pattern. REFUSES below two DISTINCT factual occurrences.

    Distinctness is by evidence reference: re-reading one fact ten times yields one
    occurrence, so observation frequency can never become evidence of recurrence.
    """
    refs = []
    for f in facts or []:
        refs.extend(f.get("evidence_refs") or [])
    distinct = sorted(set(refs))
    if len(facts or []) < PATTERN_MIN_OCCURRENCES or len(distinct) < PATTERN_MIN_OCCURRENCES:
        raise ValueError("a PATTERN requires >= %d distinct factual occurrences; got "
                         "%d fact(s) over %d distinct evidence ref(s). One observation "
                         "is not a pattern." % (PATTERN_MIN_OCCURRENCES,
                                                len(facts or []), len(distinct)))
    sources = {r.split(":", 1)[0] for r in distinct}
    return dict({"kind": "PATTERN", "statement": statement,
                 "occurrences": len(facts), "evidence_refs": distinct,
                 "distinct_sources": sorted(sources),
                 "strength": strength(len(facts), len(sources)),
                 "origin": sorted({f.get("origin") for f in facts})}, **extra)


def recommendation(statement, patterns, **extra):
    """A recommendation. ADVISORY, and refuses to exist without a pattern."""
    if not patterns:
        raise ValueError("a RECOMMENDATION must cite the pattern it derives from")
    refs = []
    for p in patterns:
        refs.extend(p.get("evidence_refs") or [])
    return dict({"kind": "RECOMMENDATION", "statement": statement,
                 "derived_from": [p.get("statement") for p in patterns],
                 "evidence_refs": sorted(set(refs)), "advisory": True,
                 "authority": "NONE — requires an explicit authorised decision"}, **extra)


# ---------------------------------------------------------------- gathering

def _review_facts(tasks, events):
    out = []
    for e in events:
        if e.get("event_type") != "review_decided":
            continue
        out.append(fact("%s %s review cycle %s: %s"
                        % (e.get("work_item_id"), (e.get("review_type") or "").upper(),
                           e.get("review_cycle"), (e.get("review_result") or "").upper()),
                        [e.get("evidence_ref") or ("event:" + str(e.get("event_id")))],
                        origin=WAVE8_EVENT, work_item_id=e.get("work_item_id"),
                        capability=e.get("required_capability"),
                        review_result=e.get("review_result")))
    return out


def _blocker_facts(tasks, jira_by_key=None):
    """Blockers as they stand NOW, derived from canonical reason codes.

    Reason codes are reused verbatim — never re-labelled by a model — because the
    codes are the system's own vocabulary and a generated synonym would break every
    comparison across time.
    """
    out = []
    for t in tasks:
        key = t.get("work_item_id")
        facts = (jira_by_key or {}).get(key)
        try:
            reasons = q.unclaimable_reasons(t, all_tasks=tasks, jira=facts)
        except Exception:                                # noqa: BLE001
            continue
        for code in reasons:
            out.append(fact("%s blocked: %s" % (key, code),
                            ["state:%s@rev%s" % (key, t.get("revision"))],
                            origin=HISTORICAL, work_item_id=key, reason_code=code,
                            capability=(t.get("execution_profile") or {}).get("required_capability")))
    return out


def _group_patterns(facts, keyfn, phrase):
    out = []
    groups = collections.defaultdict(list)
    for f in facts:
        k = keyfn(f)
        if k:
            groups[k].append(f)
    for k, fs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        try:
            out.append(pattern(phrase(k, fs), fs, group=k))
        except ValueError:
            continue                                     # one observation is not a pattern
    return out


# ---------------------------------------------------------------- scopes

def build(scope_type="product", scope_id="dabbler", tasks=None, jira_by_key=None,
          changelog=None):
    """A derived retrospective. Reads only; writes nothing.

    SPRINT reuses `sprint.py` and inherits its refusal: an incomplete Jira changelog
    raises rather than being analysed, because a truncated history silently
    under-reports and a quiet under-report is worse than no report.
    """
    if scope_type not in ("task", "sprint", "capability", "product"):
        raise ValueError("scope_type must be task/sprint/capability/product — SYSTEM "
                         "is deferred")
    tasks = store.read_all("task") if tasks is None else tasks
    # Corrected events are excluded: a retrospective reasons about what happened,
    # and an invalidated advisory record is precisely a fact withdrawn.
    events = store.read_events(include_invalidated=False)

    if scope_type == "task":
        tasks = [t for t in tasks if t.get("work_item_id") == scope_id]
        events = [e for e in events if e.get("work_item_id") == scope_id]
    elif scope_type == "capability":
        tasks = [t for t in tasks
                 if (t.get("execution_profile") or {}).get("required_capability") == scope_id]
        keys = {t.get("work_item_id") for t in tasks}
        events = [e for e in events if e.get("work_item_id") in keys
                  or e.get("required_capability") == scope_id]
    elif scope_type == "product":
        tasks = [t for t in tasks if t.get("product_id") == scope_id]
        keys = {t.get("work_item_id") for t in tasks}
        events = [e for e in events if e.get("work_item_id") in keys
                  or e.get("event_type") == "acceleration_outcome"]
    elif scope_type == "sprint":
        import sprint                                    # noqa: E402
        if changelog is None:
            raise ValueError("a sprint retrospective needs the Jira changelog it is "
                             "reconstructed from; it is never inferred")
        sprint.require_complete_changelog(changelog)     # fails closed, by design

    # COVERAGE GATES THE CLAIM. Blocker facts derived here describe the CURRENT
    # moment; blocker HISTORY comes from observed edges. Where coverage is unknown,
    # the absence of a blocker pattern is not evidence of absence, so the retrospective
    # must decline to say so rather than report a false negative.
    coverage = telemetry.completeness(tasks)
    blocker_status = coverage["blocker_coverage"]["status"]
    facts = _review_facts(tasks, events) + _blocker_facts(tasks, jira_by_key)
    pats = []
    pats += _group_patterns([f for f in facts if f.get("reason_code")],
                            lambda f: f.get("reason_code"),
                            lambda k, fs: "recurring blocker %r across %d items" % (k, len(fs)))
    pats += _group_patterns([f for f in facts if f.get("review_result") == "fail"],
                            lambda f: f.get("capability"),
                            lambda k, fs: "recurring review failure in capability %r" % k)
    recs = []
    for p in pats:
        if p.get("group") in ("missing-due-date", "missing-acceptance-criteria",
                              "surfaces-unassessed", "missing-work-effort"):
            recs.append(recommendation(
                "PO readiness checklist should catch %r before selection into Ready"
                % p.get("group"), [p], target_scope="po"))
        elif p.get("group") == "review-owner-unresolved":
            recs.append(recommendation(
                "Prepare an exact reviewer earlier for this capability; the route is "
                "correct and must not be downgraded", [p], target_scope="orchestrator"))

    accel = [e for e in events if e.get("event_type") == "acceleration_outcome"]
    accel_status = coverage["acceleration_history"]["status"]

    # A NEGATIVE claim requires coverage. "No recurring blockers" and "ACCELERATE
    # produced no outcomes" are only sayable once observation has actually happened.
    claims = {
        "may_claim_no_blocker_patterns": blocker_status == "complete",
        "may_claim_no_acceleration_outcomes": (
            accel_status == "complete"
            and not coverage["acceleration_history"]["historical_derived"]),
        "blocker_coverage": blocker_status,
        "acceleration_coverage": accel_status,
    }
    if not pats and blocker_status != "complete":
        claims["blocker_evidence"] = (
            "BLOCKER EVIDENCE INCOMPLETE — no pattern is reported because blocker "
            "coverage is %r, not because none exists" % blocker_status)
    if not accel and accel_status != "complete":
        claims["acceleration_evidence"] = (
            "ACCELERATION EVIDENCE INCOMPLETE — coverage is %r; historical runs "
            "predate Wave 8 and were never recorded as events" % accel_status)
    return {
        "coverage_claims": claims,
        "scope_type": scope_type, "scope_id": scope_id,
        "generated_at": store.now(), "read_only": True, "advisory": True,
        "facts": facts, "patterns": pats, "recommendations": recs,
        "acceleration_outcomes": accel,
        "blocker_episodes": telemetry.blocker_episodes(),
        "telemetry_completeness": coverage,
        "origins_present": sorted({f.get("origin") for f in facts}) or [],
        "authority": "NONE — a retrospective is derived analysis and mutates nothing",
    }
