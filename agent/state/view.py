#!/usr/bin/env python3
"""Agent View — the READ-ONLY derivation seam between orchestration state and the page.

AGENT VIEW IS OBSERVABILITY. IT IS NOT AUTHORITY.

This module reads Persistent State, bindings, roles, topology, derived queues,
capacity, historical status and flow telemetry, and returns one payload describing
what Thebes knows right now. It writes nothing and holds no authority over routing,
claim, ownership, release, lifecycle, validation route, reviewer selection,
dependency satisfaction, interventions, seat creation or capacity decisions.

WHAT THIS MODULE REFUSES TO DO, AND WHY

  No writes. Every store mutation entry point (claim, release, create_intervention,
  clear_intervention, set_surfaces, observe_lifecycle, ...) is absent by
  construction. A view that can write is a second state machine.

  No Jira client. Lifecycle reaches Persistent State through the Orchestrator's own
  observation; this module reads `task.lifecycle` and says how old it is. A cache
  here would be a second Jira authority that drifts.

  No invented availability. "This seat owns nothing" is a fact. "This seat is
  available" is not: nothing observes whether a binding resolves to a real agent in
  the caller's session, so dispatchability is reported UNKNOWN and never inferred
  from an absence of ownership.

  No fabricated progress. There is no thinking/executing/percent-complete model,
  because no source proves any of them. Telemetry is advisory session activity and
  loses every conflict with Persistent State.

REASON NAMESPACES ARE SEPARATE ON PURPOSE

  eligibility_reasons   why an item is not queue-eligible
  claimability_reasons  why UNOWNED work may not obtain an owner
  execution_reasons     why an OWNING seat may not continue

  Three different questions, never merged into one list. `not-owned` / `not-owner`
  belong only to the continuation domain and must never inflate a queue's
  claimability histogram. Nothing here hard-codes a reason vocabulary: the codes are
  whatever the canonical queue functions return.

Stdlib only. No HTTP server. No build step.
"""
import os, sys, csv, json, time, collections
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import policy                                           # noqa: E402
import queue as q                                       # noqa: E402
import store                                            # noqa: E402
import capacity as cap_mod                              # noqa: E402
import validate                                         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Module-level paths rather than values baked into functions, so a test can point the
# roster at a synthetic directory without touching the live checkout — the same
# reason store.RUNTIME is reassignable.
BINDINGS_DIR = os.path.join(ROOT, ".claude", "bindings")
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")
NAMING_CSV = os.path.join(ROOT, "agent", "NAMING.csv")
STATUS_DIR = os.path.join(ROOT, "agent", "status")
TOPOLOGY_JSON = os.path.join(ROOT, "agent", "state", "registry", "topology.json")
TELEMETRY_JSONL = os.path.join(ROOT, "agent", ".flow", "events.jsonl")

# Jira freshness reuses the ONE canonical Wave 6 horizon. A second threshold here
# would be a second opinion about what "current" means.
FRESHNESS_SECONDS = q.CLAIM_FRESHNESS_SECONDS

LIVE, STALE, UNAVAILABLE = "LIVE", "STALE", "UNAVAILABLE"
OWNING, UNOWNED = "OWNING", "UNOWNED"
UNKNOWN = "UNKNOWN"

SURFACES_UNASSESSED = "UNASSESSED"
SURFACES_ASSESSED_EMPTY = "ASSESSED_EMPTY"
SURFACES_ASSESSED_PATHS = "ASSESSED_PATHS"

# Shown wherever contention is presented. File-surface contention is the only
# mechanism Wave 6 implements; the absence of a path collision is not proof that two
# items cannot meet inside the database. Carried as compatibility debt, deliberately
# NOT modelled here as a second contention engine.
CONTENTION_MECHANISM = "FILE-SURFACE CONTENTION"
CONTENTION_COMPATIBILITY_NOTE = (
    "File-surface contention only. NO FILE COLLISION does not prove NO LOGICAL "
    "DATABASE-OBJECT COLLISION — shared functions and triggers are not representable "
    "as repository paths.")

ORCHESTRATOR_ROLE = "Dispatcher + Coordinator + Verifier"

REVIEW_WAITING = "WAITING FOR EXACT REVIEWER"
REVIEW_UNRECONCILED = "REVIEW STATE UNRECONCILED"
REVIEW_NOT_IN_REVIEW = "NOT IN REVIEW"

NOT_OBSERVED = "NOT OBSERVED"


# ---------------------------------------------------------------- helpers

def _now(now=None):
    return now or datetime.now(timezone.utc)


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def freshness(lifecycle, now=None):
    """LIVE / STALE / UNAVAILABLE from `lifecycle.observed_at` and nothing else.

    UNAVAILABLE is the honest answer when no observation exists: an absent Jira read
    must never render as a live one.
    """
    obs = q._parse((lifecycle or {}).get("observed_at"))
    if obs is None:
        return UNAVAILABLE, None
    age = (_now(now) - obs).total_seconds()
    return (LIVE if age <= FRESHNESS_SECONDS else STALE), age


def surfaces_state(task):
    """Tri-state. `null` = nobody looked; `[]` = looked and declared nothing."""
    s = task.get("surfaces")
    if s is None:
        return SURFACES_UNASSESSED
    return SURFACES_ASSESSED_EMPTY if not s else SURFACES_ASSESSED_PATHS


# ---------------------------------------------------------------- roster

def _naming():
    out = {}
    try:
        with open(NAMING_CSV, encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                seat = (row.get("Seat") or "").strip()
                if not seat or seat == "—":
                    continue
                out[seat] = {"deity": (row.get("Given Name (Arabic)") or "").strip(),
                             "glyph": (row.get("Hieroglyphs") or "").strip()}
    except (OSError, csv.Error):
        return {}
    return out


def _binding(path):
    """name/model/effort/role from one binding.

    `role:` IS the capability identity. Capability is never parsed out of the seat
    slug: `ux-engineer-1` is capability `ux-engineer` because its binding says so,
    and a future `payments-3` works for the same reason with no edit here.
    """
    out = {}
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            for key in ("name", "model", "effort", "role"):
                if line.startswith(key + ":"):
                    out.setdefault(key, line.split(":", 1)[1].strip().strip('"').strip("'"))
    except OSError:
        return {}
    return out


def bindings():
    """The live roster. The binding directory IS the roster — no fixed list, no count.

    A seat added to `.claude/bindings/` appears on the next read; a retired one
    disappears. Its `agent/status/` file survives as history, which is a different
    question from whether the seat is live.
    """
    out = {}
    if not os.path.isdir(BINDINGS_DIR):
        return out
    for fn in sorted(os.listdir(BINDINGS_DIR)):
        if not fn.endswith(".yml"):
            continue
        seat = fn[:-4]
        b = _binding(os.path.join(BINDINGS_DIR, fn))
        out[seat] = {"seat_id": b.get("name") or seat,
                     "capability": b.get("role") or None,
                     "model": b.get("model") or None,
                     "effort": b.get("effort") or None}
    return out


def seats_by_capability(binds=None):
    binds = bindings() if binds is None else binds
    out = collections.defaultdict(list)
    for seat, b in sorted(binds.items()):
        if b.get("capability"):
            out[b["capability"]].append(seat)
    return dict(out)


def topology():
    return (_read_json(TOPOLOGY_JSON, {}) or {}).get("capabilities", {}) or {}


def _generated_present(seat):
    return os.path.exists(os.path.join(AGENTS_DIR, seat + ".md"))


def _history(seat):
    """Durable evidence this seat has worked before — NEVER current activity.

    Deliberately named `history_present`, not `logged`. The old name read as "is
    working", and a seat that finished a ticket last week is not working now.
    """
    path = os.path.join(STATUS_DIR, seat + ".md")
    if not os.path.exists(path):
        return False, 0
    try:
        body = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False, 0
    if "_No entries yet._" in body:
        return False, 0
    return True, body.count("\n### ")


def historical_status_seats():
    """Every seat with a status file, live or retired. History outlives the roster:
    retired Team Lead files stay queryable and must never re-enter the roster."""
    if not os.path.isdir(STATUS_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(STATUS_DIR) if f.endswith(".md"))


# ---------------------------------------------------------------- validation

def review_view(task):
    """SELF / QA / PEER are ALTERNATIVES, never a pipeline.

    Two states this must not blur:
      review_owner null under PEER -> waiting for an exact reviewer, NOT "no review
                                      required";
      lifecycle review with no review_context -> unreconciled, which is neither
                                      passing nor absent.
    """
    lc = (task.get("lifecycle") or {}).get("canonical")
    rc = task.get("review_context")
    prof = task.get("execution_profile") or {}
    base = {"validation_route": prof.get("validation_route"),
            "routes_are_alternatives": True,
            "available_routes": sorted(policy.STRICTNESS.keys()),
            "review_type": None, "review_owner": None, "review_result": None,
            "review_cycle": None, "started_at": None}

    if not isinstance(rc, dict):
        base["display_state"] = (REVIEW_UNRECONCILED if lc == "review"
                                 else REVIEW_NOT_IN_REVIEW)
        return base

    base.update({"review_type": rc.get("review_type"),
                 "review_owner": rc.get("review_owner"),
                 "review_result": rc.get("review_result"),
                 "review_cycle": rc.get("review_cycle"),
                 "started_at": rc.get("started_at")})
    base["display_state"] = ("REVIEW OWNER: %s" % rc["review_owner"]
                             if rc.get("review_owner") else REVIEW_WAITING)
    return base


# ---------------------------------------------------------------- work items

def work_item(task, all_tasks, edges, interventions, lifecycles, now=None):
    prof = task.get("execution_profile") or {}
    lc = task.get("lifecycle") or {}
    own = task.get("ownership") or None
    key = task.get("work_item_id")
    fresh, age = freshness(lc, now)

    claim_reasons = q.unclaimable_reasons(
        task, all_tasks=all_tasks, edges=edges, lifecycles=lifecycles,
        interventions=interventions, now=_now(now))

    # Continuation is a DIFFERENT question, and it only exists for an owned item.
    exec_reasons = None
    if own and own.get("seat_id"):
        exec_reasons = q.execution_reasons(task, own["seat_id"],
                                           interventions=interventions)

    stop = next((i for i in interventions
                 if i.get("kind") == "stop" and i.get("target") == key), None)

    return {
        "work_item_id": key,
        "product_id": task.get("product_id"),
        "project_id": task.get("project_id"),
        "record_type": task.get("record_type"),
        # Title, due date and acceptance criteria live ONLY in Jira. Named here as
        # NOT OBSERVED rather than omitted, so the page cannot render a blank that
        # reads like an empty value. Filling them would mean building a Jira cache.
        "jira_only_fields": {"title": NOT_OBSERVED, "due_date": NOT_OBSERVED,
                             "acceptance_criteria": NOT_OBSERVED},
        "lifecycle": {
            "canonical": lc.get("canonical"),
            "jira_status_id": lc.get("jira_status_id"),
            "jira_status_name": lc.get("jira_status_name"),
            "jira_column": lc.get("jira_column"),
            "observed_at": lc.get("observed_at"),
            "observed_age_seconds": age,
            "freshness": fresh,
            "source": lc.get("source"),
        },
        "execution_profile": {
            "required_capability": prof.get("required_capability"),
            "work_effort": prof.get("work_effort"),
            "validation_route": prof.get("validation_route"),
            "completion_route": prof.get("completion_route"),
            "profile_status": prof.get("profile_status"),
            "characteristics": prof.get("characteristics") or {},
            "effective_fields": prof.get("effective_fields") or [],
        },
        "surfaces": {"state": surfaces_state(task),
                     "paths": task.get("surfaces") or [],
                     "mechanism": CONTENTION_MECHANISM,
                     "compatibility_note": CONTENTION_COMPATIBILITY_NOTE},
        "ownership": ({"state": OWNING, "seat_id": own.get("seat_id"),
                       "claimed_at": own.get("claimed_at"),
                       "claim_ref": own.get("claim_ref")}
                      if own and own.get("seat_id") else {"state": UNOWNED}),
        # History. Never current execution — an evidenced seat on an unowned item is
        # a seat that worked on it once, not one working on it now.
        "executor_evidence": [
            {"seat_id": e.get("seat_id"), "evidence_ref": e.get("evidence_ref"),
             "evidenced_at": e.get("evidenced_at")}
            for e in (task.get("executor_evidence") or []) if isinstance(e, dict)],
        "review": review_view(task),
        "eligibility_reasons": q.eligibility_reasons(task),
        "claimability_reasons": claim_reasons,
        "claimable": not claim_reasons,
        "execution_reasons": exec_reasons,
        "blocked_by": [e.get("source_work_item") for e in edges
                       if e.get("target_work_item") == key],
        "blocks": [e.get("target_work_item") for e in edges
                   if e.get("source_work_item") == key],
        "dependency_blocked": validate.is_blocked(key, edges, lifecycles),
        "active_stop": ({"intervention_id": stop.get("intervention_id"),
                         "reason_ref": stop.get("reason_ref"),
                         "created_by": stop.get("created_by")} if stop else None),
        "revision": task.get("revision"),
        "updated_at": task.get("updated_at"),
    }


# ---------------------------------------------------------------- seats

def seat_view(seat, b, tasks, interventions, now=None):
    """One seat. Primary state is DEFINED plus exactly one ownership condition.

    HOLD and FREEZE are deliberately absent here: they are capability- and
    system-scoped and do NOT make a seat unavailable — under Wave 6 an existing owner
    continues through both. Rendering them on a seat would say the opposite. Only a
    task-scoped STOP touches a seat, and only because it blocks that seat's
    continuation on that one item.
    """
    owned = [t for t in tasks if (t.get("ownership") or {}).get("seat_id") == seat]
    hist, hist_n = _history(seat)
    out = {
        "seat_id": seat,
        "capability": b.get("capability"),
        "model": b.get("model"),
        "effort": b.get("effort"),
        "defined": True,
        "generated_registry_present": _generated_present(seat),
        # Not observable: a binding can exist while the Agent tool silently falls back
        # to a generic agent in the caller's session. Never inferred from "owns
        # nothing", which is a different fact entirely.
        "dispatchability": UNKNOWN,
        "dispatchability_note": "NOT OBSERVABLE",
        "history_present": hist,
        "history_entry_count": hist_n,
        "recent_session_activity": None,
        "state_inconsistency": None,
    }
    if not owned:
        out.update({"ownership_state": UNOWNED, "current_work_item": None,
                    "ownership_claimed_at": None, "ownership_claim_ref": None,
                    "stop_overlay": None, "owned_item_lifecycle": None,
                    "is_review_owner_of": None})
        return out

    if len(owned) > 1:
        # One owner maximum is the invariant. Surface the breach; never pick one, and
        # never repair the data — this view has no authority to do either.
        out["state_inconsistency"] = (
            "STATE INCONSISTENCY: seat owns %d work items (%s) — one owner maximum"
            % (len(owned), ", ".join(sorted(t.get("work_item_id") for t in owned))))

    t = owned[0]
    key = t.get("work_item_id")
    own = t.get("ownership") or {}
    stop = next((i for i in interventions
                 if i.get("kind") == "stop" and i.get("target") == key), None)
    out.update({
        "ownership_state": OWNING,
        "current_work_item": key,
        "ownership_claimed_at": own.get("claimed_at"),
        "ownership_claim_ref": own.get("claim_ref"),
        # The ITEM's lifecycle, reported as the item's. An owned item sitting in
        # Review does not make its owner the reviewer — only review_owner names that.
        "owned_item_lifecycle": (t.get("lifecycle") or {}).get("canonical"),
        "stop_overlay": ({"intervention_id": stop.get("intervention_id"),
                          "work_item_id": key,
                          "reason_ref": stop.get("reason_ref")} if stop else None),
    })
    return out


def review_owner_map(tasks):
    """seat -> work items where review_context.review_owner EXACTLY names that seat.

    The only fact that makes a seat a reviewer. Never derived from lifecycle.
    """
    out = collections.defaultdict(list)
    for t in tasks:
        rc = t.get("review_context")
        if isinstance(rc, dict) and rc.get("review_owner"):
            out[rc["review_owner"]].append(t.get("work_item_id"))
    return dict(out)


# ---------------------------------------------------------------- queues

def capability_universe(tasks, binds, topo):
    """Every capability that should render a queue.

    The union matters: `queue.queues()` derives capabilities from the tasks present,
    so a capability with no work would silently vanish rather than showing an honest
    empty queue.
    """
    caps = set(topo) | set(seats_by_capability(binds))
    caps |= {q.capability_of(t) for t in tasks if q.capability_of(t)}
    return sorted(c for c in caps if c)


def _expansion(capability, tasks, sbc, topo):
    if not (topo.get(capability) or {}).get("expandable"):
        return False
    try:
        return bool(cap_mod.expansion_justified(capability, tasks, sbc))
    except Exception:
        return False


def queue_view(capability, tasks, binds, topo, interventions, edges, lifecycles,
               now=None):
    mine = [t for t in tasks if q.capability_of(t) == capability]
    eligible = q.queue(tasks, capability)

    hist = collections.Counter()
    claimable, blocked = [], []
    for t in mine:
        reasons = q.unclaimable_reasons(
            t, all_tasks=tasks, edges=edges, lifecycles=lifecycles,
            interventions=interventions, now=_now(now))
        if reasons:
            blocked.append(t.get("work_item_id"))
            # CLAIMABILITY codes only. Continuation codes (`not-owned`, `not-owner`)
            # come from a different function and never reach this histogram.
            hist.update(reasons)
        else:
            claimable.append(t.get("work_item_id"))

    sbc = seats_by_capability(binds)
    defined = sorted(sbc.get(capability, []))
    busy = sorted(cap_mod.busy_seats(capability, tasks, sbc))
    hold = next((i for i in interventions
                 if i.get("kind") == "hold" and i.get("target") == capability), None)
    tp = topo.get(capability) or {}
    return {
        "capability": capability,
        "eligible_depth": len(eligible),
        "eligible": [t.get("work_item_id") for t in eligible],
        "claimable_count": len(claimable),
        "claimable": sorted(claimable),
        "blocked_count": len(blocked),
        "blocked": sorted(blocked),
        "claimability_reason_histogram": dict(sorted(hist.items())),
        "current_owners": {(t.get("ownership") or {}).get("seat_id"): t.get("work_item_id")
                           for t in mine if (t.get("ownership") or {}).get("seat_id")},
        "defined_seats": defined,
        "defined_seat_count": len(defined),
        "busy_seats": busy,
        # NEVER "available". A seat owning nothing is a fact; availability is not.
        "unowned_seats": sorted(set(defined) - set(busy)),
        "unowned_seat_label": "SEATS WITHOUT CURRENT OWNERSHIP",
        "ceiling": tp.get("ceiling"),
        "expandable": tp.get("expandable"),
        "expansion_eligible": _expansion(capability, tasks, sbc, topo),
        # Capability scope lives on the QUEUE, not on any seat.
        "hold": ({"intervention_id": hold.get("intervention_id"),
                  "reason_ref": hold.get("reason_ref"), "scope": "capability"}
                 if hold else None),
        "work_effort_total": sum((t.get("execution_profile") or {}).get("work_effort") or 0
                                 for t in mine),
        "empty_state": None if mine else "NOTHING CLAIMABLE",
    }


# ---------------------------------------------------------------- capacity

def capacity_view(capability, tasks, binds, topo):
    """Minimal Wave 6 facts. No utilisation, no scores, no forecasting, no tokens."""
    sbc = seats_by_capability(binds)
    defined = sorted(sbc.get(capability, []))
    busy = sorted(cap_mod.busy_seats(capability, tasks, sbc))
    mine = [t for t in tasks if q.capability_of(t) == capability]
    tp = topo.get(capability) or {}
    return {
        "capability": capability,
        "defined_seats": len(defined),
        "busy_seats": len(busy),
        "seats_without_current_ownership": len(defined) - len(busy),
        "claimable_items": len(cap_mod.claimable_items(capability, tasks)),
        "blocked_items": len([t for t in mine if q.unclaimable_reasons(t, all_tasks=tasks)]),
        "work_effort_total": sum((t.get("execution_profile") or {}).get("work_effort") or 0
                                 for t in mine),
        "ceiling": tp.get("ceiling"),
        "ceiling_note": "A ceiling is a safety bound, not a forecast.",
        "expandable": tp.get("expandable"),
        "expansion_eligible": _expansion(capability, tasks, sbc, topo),
        # due_date lives only in Jira; computing pressure would need a Jira cache.
        "due_date_pressure": NOT_OBSERVED,
    }


# ---------------------------------------------------------------- dependencies

def dependency_view(edges, lifecycles):
    out = []
    for e in sorted(edges, key=lambda x: (x.get("source_work_item") or "")):
        src, tgt = e.get("source_work_item"), e.get("target_work_item")
        out.append({
            "dependency_id": e.get("dependency_id"),
            "product_id": e.get("product_id"),
            "source_work_item": src,
            "target_work_item": tgt,
            "source_project_id": e.get("source_project_id"),
            "target_project_id": e.get("target_project_id"),
            "relation": e.get("relation"),
            "completion_condition": e.get("completion_condition"),
            "reason_ref": e.get("reason_ref"),
            "source_lifecycle": lifecycles.get(src),
            # DERIVED on every read. Satisfaction is never stored, so it is never
            # displayed as a stored truth — only DONE on the source clears the edge.
            "target_blocked": validate.is_blocked(tgt, edges, lifecycles),
            "satisfied_is_derived": True,
            "cross_project": e.get("source_project_id") != e.get("target_project_id"),
        })
    return out


# ---------------------------------------------------------------- interventions

def intervention_view(all_interventions):
    active, cleared = [], []
    for i in sorted(all_interventions, key=lambda x: x.get("created_at") or ""):
        row = {"intervention_id": i.get("intervention_id"), "kind": i.get("kind"),
               "scope": i.get("scope"), "target": i.get("target"),
               "created_by": i.get("created_by"), "reason_ref": i.get("reason_ref"),
               "created_at": i.get("created_at"), "cleared_by": i.get("cleared_by"),
               "cleared_at": i.get("cleared_at")}
        (cleared if i.get("cleared_at") else active).append(row)
    return {
        "active": active,
        "cleared": cleared,
        "empty_state": None if active else "NO ACTIVE INTERVENTIONS",
        # RESUME is the clearing operation, never a fourth stored kind.
        "scopes": dict(validate.KIND_SCOPE),
        "controls": False,
        "note": "STOP is task scope, HOLD is capability scope, FREEZE is system "
                "scope. RESUME clears; it is not a kind. Read-only: no controls.",
    }


# ---------------------------------------------------------------- telemetry

def telemetry(limit=40):
    """Advisory session activity. NEVER ownership, lifecycle, progress or availability.

    `agent_type` in the hook payload is the free-form instance label passed at
    dispatch (`backend-4-surfaces`, `exec-kan153`, `po-gate`), not a canonical seat
    id. Correlating it to a seat by prefix would be a guess dressed as a fact, so it
    is reported UNCORRELATED and left that way.
    """
    empty = {"present": False, "state": "NO SESSION ACTIVITY OBSERVED", "count": 0,
             "labels": [], "recent": [], "advisory": True,
             "authoritative_for": []}
    if not os.path.exists(TELEMETRY_JSONL):
        return empty
    rows, labels = [], collections.Counter()
    try:
        with open(TELEMETRY_JSONL, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                rows.append(d)
                if d.get("agent_type"):
                    labels[d["agent_type"]] += 1
    except OSError:
        pass
    if not rows:
        return empty
    return {
        "present": True, "state": "RECENT SESSION ACTIVITY", "advisory": True,
        "authoritative_for": [],
        "count": len(rows), "last_at": rows[-1].get("at"),
        "labels": [{"label": k, "count": v, "seat_correlation": "UNCORRELATED"}
                   for k, v in labels.most_common(12)],
        "recent": [{"event": d.get("event"), "at": d.get("at"),
                    "tool": d.get("tool_name"), "duration_ms": d.get("duration_ms"),
                    "label": d.get("agent_type"), "seat_correlation": "UNCORRELATED"}
                   for d in rows[-limit:]],
        "note": "Advisory only. Free-form agent_type is not a canonical seat id. "
                "Persistent State wins every conflict.",
    }


# ---------------------------------------------------------------- payload

def _meta(tasks, edges, interventions, binds, topo, now=None):
    generated = 0
    if os.path.isdir(AGENTS_DIR):
        generated = len([f for f in os.listdir(AGENTS_DIR) if f.endswith(".md")])
    fresh = collections.Counter(freshness(t.get("lifecycle"), now)[0] for t in tasks)
    return {
        "runtime_present": bool(tasks or edges or interventions),
        "task_count": len(tasks),
        "dependency_count": len(edges),
        "intervention_count": len(interventions),
        "roster_count": len(binds),
        "generated_agent_count": generated,
        "registry_consistent": generated == len(binds),
        "capability_count": len(topo),
        "state_schema": store.SCHEMA_VERSION,
        "freshness_window_seconds": FRESHNESS_SECONDS,
        "lifecycle_freshness": dict(sorted(fresh.items())),
        "view_generated_at": datetime.fromtimestamp(
            time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "read_only": True,
        "empty_state": None if tasks else "NO WORK RECORDED",
    }


def acceleration_view(tasks, policies, binds, edges, interventions, lifecycles):
    """Active ACCELERATE, as FACT. Read-only, like everything else here.

    Agent View observes and never invents, so this reports what the policy records and
    the derivation say and nothing more. There are no controls: no activate, no clear,
    and nothing that animates to imply speed. `capacity_unavailable` is stated only
    where it is factual — a capability with claimable work and no free seat — and
    dispatchability stays UNKNOWN because it is not knowable from state.
    """
    active = [p for p in (policies or []) if not p.get("cleared_at")
              and p.get("policy_kind") == "accelerate"]
    base = {"active": False, "policies": [], "condition": None,
            "accelerated_owned": 0, "remaining_claimable": 0,
            "capacity_unavailable": [], "blocked_reasons": {},
            "review_work": [], "review_waiting": [], "read_only": True}
    if not active:
        return base

    sbc = seats_by_capability(binds)
    kw = {"lifecycles": lifecycles, "interventions": interventions}
    try:
        plan = cap_mod.accelerate_plan(tasks, active, sbc, edges=edges, **kw)
    except Exception:
        # Observability must never be the thing that breaks. An underivable plan is
        # reported as unknown, not as an empty one that would read like "no work".
        return dict(base, active=True, condition=NOT_OBSERVED,
                    policies=[_policy_row(p) for p in active])

    covered = set(plan["capabilities"])
    owned = [t for t in tasks
             if (t.get("ownership") or {}).get("seat_id")
             and q.capability_of(t) in covered]
    unavailable = [pl["capability"] for pl in plan["plans"]
                   if pl["claimable"] and not pl["free_seats"]]
    return {
        "active": True,
        "policies": [_policy_row(p) for p in active],
        "condition": plan["condition"],
        "capabilities": plan["capabilities"],
        "accelerated_owned": len(owned),
        "remaining_claimable": sum(len(pl["claimable"]) for pl in plan["plans"]),
        "selected": {pl["capability"]: pl["selected"] for pl in plan["plans"]},
        "capacity_unavailable": unavailable,
        "blocked_reasons": plan["blocked_reasons"],
        "review_work": plan["review_work"],
        "review_waiting": plan["review_waiting"],
        "dispatchability": "UNKNOWN",
        "read_only": True,
    }


def _policy_row(p):
    return {"policy_id": p.get("policy_id"), "scope": p.get("scope"),
            "target": p.get("target"), "activated_at": p.get("activated_at"),
            "activated_by": p.get("activated_by"), "reason_ref": p.get("reason_ref")}


def build(now=None):
    """The whole read-only payload. Reads; never writes."""
    tasks = store.read_all("task")
    edges = [e for e in store.read_all("dependency") if not e.get("retired_at")]
    interventions = store.active_interventions()
    all_interventions = store.read_all("intervention")
    binds = bindings()
    topo = topology()
    lifecycles = {t.get("work_item_id"): (t.get("lifecycle") or {}).get("canonical")
                  for t in tasks}
    ident = _naming()
    reviewers = review_owner_map(tasks)
    policies = store.read_all("policy")

    items = sorted(
        (work_item(t, tasks, edges, interventions, lifecycles, now) for t in tasks),
        key=lambda x: x["work_item_id"] or "")

    seats = []
    for seat in sorted(binds):
        s = seat_view(seat, binds[seat], tasks, interventions, now)
        s["is_review_owner_of"] = reviewers.get(seat) or None
        s.update({"deity": (ident.get(seat) or {}).get("deity"),
                  "glyph": (ident.get(seat) or {}).get("glyph")})
        seats.append(s)

    caps = capability_universe(tasks, binds, topo)
    owners = collections.Counter(
        (t.get("ownership") or {}).get("seat_id") for t in tasks
        if (t.get("ownership") or {}).get("seat_id"))
    freeze = next((i for i in interventions if i.get("kind") == "freeze"), None)
    live = set(binds)

    return {
        "meta": _meta(tasks, edges, interventions, binds, topo, now),
        "acceleration": acceleration_view(tasks, policies, binds, edges,
                                          interventions, lifecycles),
        "orchestrator": {
            "name": "Main Session",
            "role": ORCHESTRATOR_ROLE,
            "is_seat": False,
            "owns_work": False,
            "excluded_from_roster": True,
            "note": "Coordination only. Never a task owner, Product executor, CTO or "
                    "Team Lead. Excluded from roster, seat counts, queues, capacity "
                    "and ownership.",
            # System scope belongs here, not on any seat.
            "system_freeze": ({"intervention_id": freeze.get("intervention_id"),
                               "reason_ref": freeze.get("reason_ref"),
                               "scope": "system"} if freeze else None),
        },
        "seats": seats,
        "work_items": items,
        "queues": [queue_view(c, tasks, binds, topo, interventions, edges, lifecycles, now)
                   for c in caps],
        "dependencies": dependency_view(edges, lifecycles),
        "interventions": intervention_view(all_interventions),
        "capacity": [capacity_view(c, tasks, binds, topo) for c in caps],
        "ownership": {
            "by_work_item": {i["work_item_id"]: i["ownership"].get("seat_id")
                             for i in items if i["ownership"]["state"] == OWNING},
            "by_seat": {s["seat_id"]: s["current_work_item"] for s in seats
                        if s.get("current_work_item")},
            "active_count": sum(1 for i in items if i["ownership"]["state"] == OWNING),
            "review_owners": reviewers,
            "inconsistencies": ["STATE INCONSISTENCY: %s owns %d work items" % (s, n)
                                for s, n in sorted(owners.items()) if n > 1],
            "empty_state": None if owners else "NO ACTIVE OWNERSHIP",
        },
        "history": {
            "status_seats": historical_status_seats(),
            "retired_status_seats": sorted(set(historical_status_seats()) - live),
            "note": "History only. Never current ownership or activity.",
        },
        "telemetry": telemetry(),
        "contention": {"mechanism": CONTENTION_MECHANISM,
                       "compatibility_note": CONTENTION_COMPATIBILITY_NOTE},
    }


if __name__ == "__main__":
    p = build()
    m = p["meta"]
    print("Agent View — read-only derivation")
    print("  runtime      : %s tasks, %s deps, %s active interventions%s"
          % (m["task_count"], m["dependency_count"], m["intervention_count"],
             "  [%s]" % m["empty_state"] if m["empty_state"] else ""))
    print("  roster       : %s bindings, %s generated (consistent=%s)"
          % (m["roster_count"], m["generated_agent_count"], m["registry_consistent"]))
    print("  freshness    : %s" % (m["lifecycle_freshness"] or "—"))
    print("  ownership    : %s active %s"
          % (p["ownership"]["active_count"], p["ownership"]["by_work_item"] or "—"))
    print("  interventions: %s" % (p["interventions"]["empty_state"]
                                   or p["interventions"]["active"]))
    a = p["acceleration"]
    if a["active"]:
        print("  ACCELERATE   : %s  scope=%s"
              % (a["condition"], ", ".join("%s%s" % (x["scope"],
                 ":" + x["target"] if x["target"] else "") for x in a["policies"])))
        print("                 owned=%d remaining_claimable=%d%s"
              % (a["accelerated_owned"], a["remaining_claimable"],
                 "  capacity_unavailable=" + ",".join(a["capacity_unavailable"])
                 if a.get("capacity_unavailable") else ""))
    else:
        print("  ACCELERATE   : not active (normal mode)")
    for qv in p["queues"]:
        if qv["defined_seat_count"] or qv["blocked_count"]:
            print("  queue %-16s eligible=%d claimable=%d blocked=%d seats=%d unowned=%d"
                  % (qv["capability"], qv["eligible_depth"], qv["claimable_count"],
                     qv["blocked_count"], qv["defined_seat_count"],
                     len(qv["unowned_seats"])))
