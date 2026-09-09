#!/usr/bin/env python3
"""Thebes Persistent State validator.

THIS IS NOT JSON SCHEMA. There is no jsonschema package installed and none is
added; these are executable Thebes rules. Record shapes are documented in
agent/state/README.md. Do not describe this as JSON Schema compliance.

WHAT IT CANNOT DO
  It cannot prove a valid-looking record went through store.py. Runtime files
  carry no external write ledger, so a careful manual edit is indistinguishable
  from a store.py write. The no-direct-edit rule is contractual, like the
  no-delegation rule. Stated here so nobody mistakes a green check for proof of
  provenance.

  It also cannot tell you a stored lifecycle observation is still true. It checks
  the observation's SHAPE and that its canonical state matches the Jira status id
  it names. Freshness is the reader's problem, and `observed_at` is there so the
  reader can have it.

    python3 agent/state/validate.py --check
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, "agent", "state")
RUNTIME = os.path.join(STATE, "runtime")
REGISTRY = os.path.join(STATE, "registry")
BINDINGS = os.path.join(ROOT, ".claude", "bindings")
SCHEMA_VERSIONS = {1, 2, 3}

sys.path.insert(0, STATE)
import policy                                          # noqa: E402
import board                                           # noqa: E402

CAPABILITIES = {"frontend", "backend", "qa", "content", "devops", "analyst",
                "ux-engineer", "product-designer", "po", "pm", "cto", "cpo", "cxo"}
ROUTING_STATUS = {"open", "routed", "resolved", "withdrawn"}
EXCEPTION_STATUS = {"open", "redirected", "resolved", "withdrawn"}
EXCEPTION_TYPES = {"scope", "acceptance", "work_definition", "technical_domain",
                   "product", "experience", "blocker"}
PROVENANCE_ACTORS = re.compile(r"^(po|pm|qa|cto|analyst|system-policy|system-derived|"
                               r"system-maintenance|worker:[a-z0-9-]+)$")
JIRA_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")

# ---- Wave 5 lifecycle -------------------------------------------------------
#
# The board model lives in ONE place: agent/state/board.py. Canonical state is
# DERIVED from the Jira status ID, never authored beside it, and ids are the key
# rather than names — names change, and every historical changelog entry keeps
# saying whatever the status was called at the time.
#
# A COLUMN IS NOT A STATUS. `Operations` groups three execution lanes and
# `Review` groups three validation routes, so an observation carries column,
# status id and canonical separately: none of the three derives the other two.

CANONICAL_STATES = set(board.CANONICAL_STATES)

# ---- Wave 6 orchestration ---------------------------------------------------
#
# Interventions are INDEPENDENT records, not a field on a task. A task-level object
# could not represent a capability-scoped HOLD or a system-scoped FREEZE at all —
# there is no single task to hang them on. Claimability queries the records.

INTERVENTION_KINDS = {"stop", "hold", "freeze"}
# Execution policies are a SEPARATE namespace from interventions on purpose:
# interventions restrict execution for a safety condition, policies change how
# aggressively safe capacity is filled. CONTRACT.md §3 forbids using the first for
# the second, so they never share a vocabulary, a scope table or a reader.
POLICY_KINDS = {"accelerate"}
POLICY_SCOPES = {"system", "product", "capability"}
POLICY_AUTHORITIES = {"ceo", "orchestrator"}
INTERVENTION_SCOPES = {"task", "capability", "system"}
# kind determines scope exactly. A stop is always a task, a freeze is always system.
KIND_SCOPE = {"stop": "task", "hold": "capability", "freeze": "system"}
INTERVENTION_AUTHORITIES = {"ceo", "orchestrator"}

REVIEW_TYPES = {"self", "peer", "qa"}
REVIEW_RESULTS = {"pending", "pass", "fail"}
RECORD_TYPES = {"executable", "container"}

# ---- Execution Profile ------------------------------------------------------
#
# Wave 5 makes six fields operational. A single status word cannot say that
# truthfully while five others stay deferred, so `partial` carries an explicit
# effective_fields list and the validator checks the list against reality.

PROFILE_DEFERRED = ["execution_complexity", "risk", "model", "reasoning_effort",
                    "parallelism"]
PROFILE_OPERATIONAL_W5 = ["project_id", "required_capability", "work_effort",
                          "characteristics", "validation_route", "completion_route"]
PROFILE_SYSTEM_DERIVED = ["validation_route", "completion_route"]
PROFILE_NEVER_BY_PO_OR_WORKER = ["model", "reasoning_effort", "validation_route"]

# Wave 4 gates, retained for v1 records only. Wave 5 records carry `lifecycle`
# and `review_context` instead of these two flat nulls.
NULL_IN_WAVE_4 = ["canonical_lifecycle", "jira_operational_column", "review_context"]
PROFILE_NULL_IN_WAVE_4 = ["execution_complexity", "risk", "model", "reasoning_effort",
                          "validation_route", "parallelism", "completion_route"]

MAX_REF_LEN = 300      # identifier/reference fields; catches a pasted ticket body


def seats():
    if not os.path.isdir(BINDINGS):
        return set()
    return {f[:-4] for f in os.listdir(BINDINGS) if f.endswith(".yml")}


def seats_by_capability():
    """Seat topology, read from the bindings' declared roles.

    Needed because a PEER route is only ownable where a second same-capability seat
    exists — and that is a fact about the repository, not a constant.
    """
    out = {}
    if not os.path.isdir(BINDINGS):
        return out
    for fn in sorted(os.listdir(BINDINGS)):
        if not fn.endswith(".yml"):
            continue
        role = None
        with open(os.path.join(BINDINGS, fn), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("role:"):
                    role = line.split(":", 1)[1].strip()
                    break
        if role:
            out.setdefault(role, []).append(fn[:-4])
    return out


def registry():
    prods, projs = {}, {}
    pdir = os.path.join(REGISTRY, "products")
    if not os.path.isdir(pdir):
        return prods, projs
    for pid in sorted(os.listdir(pdir)):
        pf = os.path.join(pdir, pid, "product.json")
        if os.path.exists(pf):
            prods[pid] = json.load(open(pf, encoding="utf-8"))
        jdir = os.path.join(pdir, pid, "projects")
        if os.path.isdir(jdir):
            for fn in sorted(os.listdir(jdir)):
                if fn.endswith(".json"):
                    r = json.load(open(os.path.join(jdir, fn), encoding="utf-8"))
                    projs[(pid, r.get("project_id"))] = r
    return prods, projs


def _req(rec, fields, errs, where):
    for f in fields:
        if f not in rec:
            errs.append("%s: missing required field %r" % (where, f))


def _reflen(rec, fields, errs, where):
    for f in fields:
        v = rec.get(f)
        if isinstance(v, str) and len(v) > MAX_REF_LEN:
            errs.append("%s: %r is %d chars — reference fields hold identifiers, "
                        "not ticket bodies, acceptance criteria or governance text"
                        % (where, f, len(v)))


# ---------------------------------------------------------------- lifecycle

def validate_lifecycle(lc, errs, where):
    """Shape, and that canonical really follows from the status id.

    Jira is the authority. This record is an OBSERVATION of it, and it says so:
    source, observed_at and a staleness horizon are required, so a reader can never
    mistake a stored value for a live one.
    """
    if lc is None:
        return None
    if not isinstance(lc, dict):
        errs.append("%s: lifecycle must be an object" % where); return None
    _req(lc, ["canonical", "jira_column", "jira_status_id", "jira_status_name",
              "observed_at", "source"], errs, where)
    if lc.get("source") != "jira":
        errs.append("%s: lifecycle.source must be 'jira' — Jira is the lifecycle "
                    "authority and state only observes it" % where)
    sid = str(lc.get("jira_status_id") or "")
    expect = board.canonical_for(sid)
    if expect is None:
        errs.append("%s: unknown jira_status_id %r — not a status on the live KAN board"
                    % (where, sid))
        return lc.get("canonical")
    if lc.get("canonical") != expect:
        errs.append("%s: lifecycle.canonical %r contradicts status id %s (%s), which maps "
                    "to %r — canonical is derived, never authored beside the id"
                    % (where, lc.get("canonical"), sid, board.name_for(sid), expect))
    if lc.get("jira_status_name") != board.name_for(sid):
        errs.append("%s: jira_status_name %r does not match status id %s, which is %r "
                    "on the live board" % (where, lc.get("jira_status_name"), sid,
                                           board.name_for(sid)))
    col = board.column_for(sid)
    if board.is_legacy(sid):
        # Not an error: historical records and mid-migration items legitimately
        # name a retired status. It is simply not a target for new work.
        errs.append("%s: WARN status %s (%s) is a LEGACY status with no board column — "
                    "valid for history, not a target for new work"
                    % (where, sid, board.name_for(sid)))
    elif lc.get("jira_column") != col:
        errs.append("%s: jira_column %r contradicts status id %s, which sits in column "
                    "%r — a column groups several statuses, so both are recorded and "
                    "neither is guessed" % (where, lc.get("jira_column"), sid, col))
    if lc.get("canonical") not in CANONICAL_STATES:
        errs.append("%s: unknown canonical lifecycle %r" % (where, lc.get("canonical")))
    return lc.get("canonical")


# ---------------------------------------------------------------- ownership

def validate_ownership(own, errs, where, seatset):
    """Current ownership, or null. There is no third state.

    `released_at` is REJECTED inside the object. An ownership record that exists but
    says it is already released is ambiguous — two readers would disagree about
    whether the slot is free. Release sets ownership to null; the history of who
    executed what lives in executor_evidence and provenance, which already carry it.
    """
    if own is None:
        return
    if not isinstance(own, dict):
        errs.append("%s: ownership must be an object or null" % where); return
    if "released_at" in own:
        errs.append("%s: ownership must not carry 'released_at' — release sets "
                    "ownership to null. An object that exists but is already released "
                    "is ambiguous about whether the slot is free" % where)
    _req(own, ["seat_id", "claimed_at", "claim_ref"], errs, where)
    seat = own.get("seat_id")
    if seat and seat not in seatset:
        errs.append("%s: ownership.seat_id %r is not a declared seat" % (where, seat))
    _reflen(own, ["claim_ref"], errs, where)


# ---------------------------------------------------------------- surfaces

def validate_surfaces(surfaces, errs, where):
    """Declared repository-relative paths the work touches. Returns (assessed, paths).

    These exist because a boolean cannot detect a collision: two items can both be
    `shared_or_contended_surface: true` and touch entirely different files. The path
    set is what makes contention decidable, and it is what replaced the Team Lead.

    NULL AND EMPTY-LIST ARE DIFFERENT STATES, and conflating them was a real defect:

        surfaces = null       -> SURFACE ASSESSMENT HAS NOT OCCURRED
        surfaces = []         -> assessed, and it touches no declared path
        surfaces = ["..."]    -> assessed, these paths

    `null` must NEVER be read as false, "no collision", "not shared" or
    "assessed-empty". Until Wave 6 closure both meanings shared `[]`, so an item whose
    scope nobody had looked at was treated as colliding with nothing — contention
    protection was silently inert for every unassessed item.
    """
    if surfaces is None:
        return False, []
    if not isinstance(surfaces, list):
        errs.append("%s: surfaces must be null (unassessed) or a list of "
                    "repository-relative paths" % where)
        return False, []
    seen, clean = set(), []
    for raw in surfaces:
        if not isinstance(raw, str) or not raw.strip():
            errs.append("%s: surface entries must be non-empty strings" % where); continue
        p = raw.strip()
        if len(p) > MAX_REF_LEN:
            errs.append("%s: surface %r is too long" % (where, p[:40])); continue
        if p.startswith("/") or (len(p) > 1 and p[1] == ":"):
            errs.append("%s: surface %r is absolute — paths are repository-relative"
                        % (where, p)); continue
        if "\\" in p:
            errs.append("%s: surface %r uses backslashes — use '/'" % (where, p)); continue
        if ".." in p.split("/"):
            errs.append("%s: surface %r escapes the repository with '..'" % (where, p))
            continue
        if p != policy.normalise_path(p):
            errs.append("%s: surface %r is not normalised (expected %r)"
                        % (where, p, policy.normalise_path(p))); continue
        if p in seen:
            errs.append("%s: duplicate surface %r" % (where, p)); continue
        seen.add(p); clean.append(p)
    return True, clean


# ---------------------------------------------------------------- review

def validate_review_context(rc, canonical, profile, errs, where, rec=None):
    """Current review state — not a history. Jira's changelog and the ticket's own
    comments already hold the cycles; duplicating them here would create a second
    authority that drifts."""
    if rc is None:
        if canonical == "review":
            # A reconciliation warning in the CEO's migration, not a hard failure:
            # legacy items arrive in Review without a route already decided.
            errs.append("%s: WARN lifecycle is 'review' with no review_context — "
                        "legitimate only for an unreconciled legacy item" % where)
        return
    if not isinstance(rc, dict):
        errs.append("%s: review_context must be an object" % where); return
    if canonical == "ready":
        errs.append("%s: review_context must be null in 'ready'" % where)
    _req(rc, ["review_type", "review_result", "review_cycle"], errs, where)
    rt = rc.get("review_type")
    if rt not in REVIEW_TYPES:
        errs.append("%s: unknown review_type %r" % (where, rt))
    if rc.get("review_result") not in REVIEW_RESULTS:
        errs.append("%s: unknown review_result %r" % (where, rc.get("review_result")))
    cyc = rc.get("review_cycle")
    if not isinstance(cyc, int) or cyc < 1:
        errs.append("%s: review_cycle must be an integer >= 1" % where)
    # review_type is initialised FROM the policy output and never edited afterwards.
    # This is the hole that would otherwise let a worker reach an easier route by
    # editing a field rather than by transitioning.
    route = (profile or {}).get("validation_route")
    if route and rt and rt != route and not rc.get("previous_owner"):
        errs.append("%s: review_type %r does not match validation_route %r — the only "
                    "legal divergence is after a PEER-fail transfer, which sets "
                    "previous_owner" % (where, rt, route))
    owner = rc.get("review_owner")
    if owner is not None and owner not in seats():
        errs.append("%s: review_owner %r is not a declared seat" % (where, owner))
    if rc.get("review_result") == "pass" and owner is None:
        errs.append("%s: review_result 'pass' with no review_owner — a verdict with "
                    "no owner is a verdict nobody is accountable for" % where)
    # SELF's owner IS the evidenced executor. Checked here as well as in
    # open_review_context because the store guards the WRITE and the validator guards
    # the FILE, and a hand-edited record reaches only the second.
    if rt == "self" and owner is not None and rec is not None:
        ev = sorted({e.get("seat_id") for e in (rec.get("executor_evidence") or [])
                     if isinstance(e, dict) and e.get("seat_id")})
        if len(ev) > 1:
            errs.append("%s: SELF review_owner %r with %d distinct evidenced "
                        "executors (%s) — SELF's owner is derived from exactly one, "
                        "and conflicting evidence is surfaced, never resolved by "
                        "picking" % (where, owner, len(ev), ", ".join(ev)))
        elif not ev:
            # WARN, not a hard failure, for the same reason a legacy status is: a
            # record written before this invariant existed is repairable, and making
            # it unloadable would make the migration state unwritable. The WRITE path
            # (store.open_review_context) refuses outright, so nothing new lands here.
            errs.append("%s: WARN SELF review_owner %r with no executor evidence — "
                        "legitimate only for a record predating the SELF state path"
                        % (where, owner))
        elif ev[0] != owner:
            errs.append("%s: SELF review_owner %r is not the evidenced executor %r"
                        % (where, owner, ev[0]))
    if rt == "qa" and rc.get("review_owner") not in (None, "qa"):
        errs.append("%s: the QA route's owner is the qa seat, got %r"
                    % (where, rc.get("review_owner")))
    if canonical == "done" and rc.get("review_result") != "pass":
        errs.append("%s: lifecycle is 'done' but review_result is %r"
                    % (where, rc.get("review_result")))


# ---------------------------------------------------------------- profile

def validate_characteristics(ch, errs, where):
    if ch is None:
        return None
    if not isinstance(ch, dict):
        errs.append("%s: characteristics must be an object" % where); return None
    unknown = set(ch) - set(policy.CHARACTERISTICS)
    if unknown:
        errs.append("%s: unknown task characteristic(s) %s — the Wave 5 set is fixed; "
                    "risk/complexity are Wave 6"
                    % (where, ", ".join(sorted(unknown))))
    for k, v in ch.items():
        if not isinstance(v, bool):
            errs.append("%s: characteristics.%s must be a boolean, got %r" % (where, k, v))
    return ch


def validate_profile_v2(prof, errs, where, topology=None, rec=None):
    def _effective_value(f):
        # project_id and surfaces are operational FACTS that live on the record, not
        # inside the profile — one Project and one path set per work item, so a copy in
        # the profile would be a second value to drift. Provenance for them is still
        # recorded on the profile's per-field mechanism, so resolve them from the record.
        if f in ("project_id", "surfaces"):
            return (rec or {}).get(f)
        return prof.get(f)

    if prof is None:
        return
    for f in PROFILE_DEFERRED:
        if prof.get(f) is not None:
            errs.append("%s: execution_profile.%s must be null in Wave 5 "
                        "(policy that derives it becomes effective in Wave 6)" % (where, f))
    st = prof.get("profile_status")
    if st == "effective":
        errs.append("%s: profile_status 'effective' is forbidden until Wave 6 — five "
                    "fields are still deferred, so 'effective' would be untrue" % where)
    elif st not in ("draft", "partial"):
        errs.append("%s: profile_status must be 'draft' or 'partial', got %r" % (where, st))

    eff = prof.get("effective_fields")
    if st == "partial":
        if not isinstance(eff, list):
            errs.append("%s: profile_status 'partial' requires effective_fields" % where)
        else:
            for f in eff:
                if f in PROFILE_DEFERRED:
                    errs.append("%s: effective_fields names deferred field %r" % (where, f))
                elif f not in PROFILE_OPERATIONAL_W5:
                    errs.append("%s: effective_fields names unknown field %r" % (where, f))
                elif _effective_value(f) is None:
                    errs.append("%s: effective_fields claims %r is operational but it is "
                                "null — the list must be truthful" % (where, f))
    elif eff:
        errs.append("%s: effective_fields is only meaningful with profile_status "
                    "'partial'" % where)

    cap = prof.get("required_capability")
    if cap is not None and cap not in CAPABILITIES:
        errs.append("%s: unknown required_capability %r" % (where, cap))
    we = prof.get("work_effort")
    if we is not None and (not isinstance(we, int) or we < 0):
        errs.append("%s: work_effort must be a non-negative integer (sittings)" % where)
    cr = prof.get("completion_route")
    if cr is not None and cr != "DONE":
        errs.append("%s: completion_route must be DONE" % where)

    ch = validate_characteristics(prof.get("characteristics"), errs, where)

    # The route is a CONSEQUENCE. If characteristics are present, the stored route
    # must be exactly what the policy computes from them — which is what makes
    # "no seat chooses its own reviewer" checkable rather than merely stated.
    route = prof.get("validation_route")
    if route is not None:
        if route not in (policy.SELF, policy.PEER, policy.QA):
            errs.append("%s: unknown validation_route %r" % (where, route))
        elif ch is not None:
            try:
                expect = policy.validation_route(ch)
            except ValueError as e:
                expect = None
                errs.append("%s: %s" % (where, e))
            if expect and route != expect:
                # Escalation above the computed route is legitimate; below it is not.
                if policy.STRICTNESS[route] < policy.STRICTNESS[expect]:
                    errs.append("%s: validation_route %r is weaker than the policy's %r "
                                "for these characteristics — routes escalate, never "
                                "downgrade" % (where, route, expect))
        if route == policy.PEER and topology is not None and cap:
            if not policy.peer_possible(cap, topology):
                # Not an error: the item waits. Recorded so it is visible rather than
                # quietly rerouted for throughput.
                errs.append("%s: WARN PEER route on capability %r which has fewer than "
                            "two seats — the item waits in review; do NOT downgrade"
                            % (where, cap))

    prov = prof.get("provenance") or {}
    if not isinstance(prov, dict):
        errs.append("%s: provenance must be an object keyed by field name" % where)
        return
    for field, entry in prov.items():
        if not isinstance(entry, dict) or "by" not in entry:
            errs.append("%s: provenance.%s needs an object with 'by'" % (where, field))
            continue
        by = str(entry["by"])
        if not PROVENANCE_ACTORS.match(by):
            errs.append("%s: provenance.%s.by %r is not a recognised actor" % (where, field, by))
        if field in PROFILE_NEVER_BY_PO_OR_WORKER and (
                by in ("po", "pm") or by.startswith("worker:")):
            errs.append("%s: %s may not be authored by %s — system policy derives it"
                        % (where, field, by))
        if field in PROFILE_SYSTEM_DERIVED and by != "system-policy":
            errs.append("%s: %s must carry provenance by 'system-policy', got %r"
                        % (where, field, by))
    for field in prov:
        if field not in ("characteristics",) and _effective_value(field) is None:
            errs.append("%s: provenance.%s present but the field is unset" % (where, field))
    # A characteristic nobody may assert must not arrive with an author.
    chprov = (prov.get("characteristics") or {}).get("fields") or {}
    for name, entry in chprov.items():
        if name in policy.SYSTEM_DERIVED and (entry or {}).get("by") != "system-derived":
            errs.append("%s: characteristic %r is system-derived; it cannot be asserted "
                        "by %r" % (where, name, (entry or {}).get("by")))


def validate_profile(prof, errs, where):
    """Wave 4 (v1) profile rules, retained unchanged for v1 records."""
    if prof is None:
        return
    for f in PROFILE_NULL_IN_WAVE_4:
        if prof.get(f) is not None:
            errs.append("%s: execution_profile.%s must be null in Wave 4 "
                        "(policy that derives it becomes effective in Wave 6)" % (where, f))
    st = prof.get("profile_status")
    if st != "draft":
        errs.append("%s: profile_status must be 'draft' in Wave 4, got %r" % (where, st))
    cap = prof.get("required_capability")
    if cap is not None and cap not in CAPABILITIES:
        errs.append("%s: unknown required_capability %r" % (where, cap))
    we = prof.get("work_effort")
    if we is not None and (not isinstance(we, int) or we < 0):
        errs.append("%s: work_effort must be a non-negative integer (sittings)" % where)
    prov = prof.get("provenance") or {}
    if not isinstance(prov, dict):
        errs.append("%s: provenance must be an object keyed by field name" % where)
        return
    for field, entry in prov.items():
        if not isinstance(entry, dict) or "by" not in entry:
            errs.append("%s: provenance.%s needs an object with 'by'" % (where, field))
            continue
        by = entry["by"]
        if not PROVENANCE_ACTORS.match(str(by)):
            errs.append("%s: provenance.%s.by %r is not a recognised actor" % (where, field, by))
        if field in PROFILE_NEVER_BY_PO_OR_WORKER and (
                by == "po" or by == "pm" or str(by).startswith("worker:")):
            errs.append("%s: %s may not be authored by %s — system policy derives it"
                        % (where, field, by))
    for field in prov:
        if prof.get(field) is None:
            errs.append("%s: provenance.%s present but the field is unset" % (where, field))


# ---------------------------------------------------------------- records

def _review_coherence(rec, prof, canonical, status_id, errs, where):
    """Jira review status vs Persistent State validation_route — ONE authority.

    The board now expresses the route directly (QA-Test / Self-review / Peer-review),
    so the two must not drift. Three outcomes, and the distinction matters:

      equal                      -> coherent.
      Jira stricter than local   -> WARN, repairable. Jira wins and local is
                                    reconciled up to it. This is the state a
                                    successful Jira transition followed by a failed
                                    local write leaves behind, and it MUST stay
                                    repairable — hard-failing it would strand the
                                    record with no legal way back.
      Jira WEAKER than policy    -> ERROR. Every transition on this board is global
                                    and unconditional, so anyone can drag an item
                                    from Peer-review to Self-review. "Jira wins"
                                    must never launder that into a downgrade: the
                                    repair is to move the issue back in Jira, not to
                                    lower the route here.
    """
    if canonical != "review" or not status_id:
        return
    jira_route = board.route_for_status(status_id)
    if jira_route is None:
        if not board.is_legacy(status_id):
            errs.append("%s: lifecycle is 'review' but status %s (%s) is not one of the "
                        "three review statuses" % (where, status_id,
                                                   board.name_for(status_id)))
        return
    local = (prof or {}).get("validation_route")
    ch = (prof or {}).get("characteristics")
    floor = None
    if ch is not None:
        try:
            floor = policy.validation_route(ch)
        except ValueError:
            floor = None

    # THE ONE AUTHORISED WAY BELOW THE FLOOR.
    # A PEER failure transfers execution ownership to the reviewer, and the settled
    # rule is that the reviewer SELF-reviews its own fix rather than going back to
    # Peer-review. So a peer-floor item legitimately sits in Self-review afterwards.
    # The transfer is what makes it legal, and `previous_owner` is the record of the
    # transfer having happened — set atomically by peer_fail_transfer() and by
    # nothing else. Without this carve-out the settled PEER-fail path would be
    # unreachable; with it, an ordinary drag from Peer-review to Self-review is
    # still refused, because no transfer ever occurred.
    rc = rec.get("review_context") or {}
    transferred = bool(rc.get("previous_owner")) and rc.get("review_type") == "self"
    if transferred and jira_route == "self":
        return

    if floor and policy.STRICTNESS[jira_route] < policy.STRICTNESS[floor]:
        errs.append("%s: Jira status %s (%s) expresses route %r, weaker than the %r the "
                    "policy computes from this item's characteristics — an unauthorised "
                    "downgrade. Move the issue back in Jira; do NOT lower the route here"
                    % (where, status_id, board.name_for(status_id), jira_route, floor))
        return
    if local and local != jira_route:
        errs.append("%s: WARN Jira status %s (%s) says route %r but validation_route is "
                    "%r — Jira wins for the active review status; reconcile local state "
                    "to it" % (where, status_id, board.name_for(status_id), jira_route,
                               local))


def validate_record(kind, rec, prods=None, projs=None, seatset=None, topology=None):
    errs = []
    where = "%s/%s" % (kind, rec.get("work_item_id") or rec.get("request_id")
                       or rec.get("exception_id") or rec.get("dependency_id") or "?")
    ver = rec.get("schema_version")
    if ver not in SCHEMA_VERSIONS:
        errs.append("%s: unsupported schema_version %r" % (where, ver))
    if not isinstance(rec.get("revision"), int) or rec["revision"] < 1:
        errs.append("%s: revision must be a positive integer" % where)
    _req(rec, ["created_at", "updated_at"], errs, where)

    prods = prods if prods is not None else registry()[0]
    projs = projs if projs is not None else registry()[1]
    seatset = seatset if seatset is not None else seats()
    topology = topology if topology is not None else seats_by_capability()

    pid = rec.get("product_id")
    if pid and pid not in prods:
        errs.append("%s: product_id %r is not in the registry" % (where, pid))
    jid = rec.get("project_id")
    if jid and (pid, jid) not in projs:
        errs.append("%s: project_id %r is not a registered Project of %r" % (where, jid, pid))

    # Interventions are authored by an AUTHORITY (ceo / orchestrator), not only by a
    # seat, so their created_by/cleared_by are checked in the intervention branch.
    generic_seat_fields = ("raised_by", "return_to", "selected_seat")
    if kind != "intervention":
        generic_seat_fields += ("created_by",)
    for f in generic_seat_fields:
        v = rec.get(f)
        if v and v not in seatset:
            errs.append("%s: %s %r is not a declared seat in .claude/bindings/" % (where, f, v))

    if kind == "task":
        _req(rec, ["work_item_id", "product_id", "project_id"], errs, where)
        if rec.get("work_item_id") and not JIRA_KEY.match(rec["work_item_id"]):
            errs.append("%s: work_item_id must be a Jira key" % where)

        ev = rec.get("executor_evidence")
        if ev is None:
            ev = []
        if not isinstance(ev, list):
            errs.append("%s: executor_evidence must be a list — it represents evidence, "
                        "not a claim, and may be empty or conflicting" % where)
            ev = []
        else:
            seen = set()
            for o in ev:
                if not isinstance(o, dict) or "seat_id" not in o:
                    errs.append("%s: executor_evidence entry needs seat_id" % where); continue
                if o["seat_id"] not in seatset:
                    errs.append("%s: executor_evidence seat %r is not declared" % (where, o["seat_id"]))
                key = (o.get("seat_id"), o.get("evidence_ref"), o.get("evidenced_at"))
                if key in seen:
                    errs.append("%s: duplicate identical executor_evidence entry" % where)
                seen.add(key)
                _reflen(o, ["evidence_ref"], errs, where)

        if ver == 1:
            for f in NULL_IN_WAVE_4:
                if rec.get(f) is not None:
                    errs.append("%s: %s must be null in a v1 record" % (where, f))
            validate_profile(rec.get("execution_profile"), errs, where)
            return errs

        # ---- v2 ----
        rt = rec.get("record_type")
        if rt not in RECORD_TYPES:
            errs.append("%s: record_type must be one of %s — an Epic or coordination "
                        "parent is not executable merely because its children are"
                        % (where, "/".join(sorted(RECORD_TYPES))))
        canonical = validate_lifecycle(rec.get("lifecycle"), errs, where)
        prof = rec.get("execution_profile")

        if ver >= 3:
            validate_ownership(rec.get("ownership"), errs, where, seatset)
            assessed, surfaces = validate_surfaces(rec.get("surfaces"), errs, where)
            # shared_or_contended_surface stays SYSTEM-DERIVED, and it is derived from
            # something checkable: the declared paths. An actor cannot assert it, and it
            # cannot be silently wrong.
            #
            # UNKNOWN STAYS UNKNOWN. When surfaces is null nothing has been assessed, so
            # the boolean must not be derived at all — deriving `false` from an absence
            # is exactly how unassessed work would look safe.
            prof0 = rec.get("execution_profile") or {}
            ch0 = prof0.get("characteristics")
            if isinstance(ch0, dict) and "shared_or_contended_surface" in ch0:
                if not assessed:
                    errs.append("%s: shared_or_contended_surface is present while surfaces "
                                "is null — the boolean is derived from the declared paths, "
                                "and unassessed scope has no derivable answer" % where)
                else:
                    want = policy.derive_contended(surfaces)
                    if bool(ch0["shared_or_contended_surface"]) != want:
                        errs.append("%s: shared_or_contended_surface is %r but the declared "
                                    "surfaces derive %r — the boolean is system-derived "
                                    "from the paths, never asserted beside them"
                                    % (where, ch0["shared_or_contended_surface"], want))

        if rt == "container":
            # ONE EXECUTABLE WORK ITEM = ONE required_capability. A container spans
            # capabilities by design, so the executable invariants must not be
            # applied to it — and it must not carry the fields that imply execution.
            for f in ("execution_profile", "review_context", "ownership"):
                if rec.get(f) is not None:
                    errs.append("%s: container records carry no %s — no capability, no "
                                "Work Effort, no validation route, no review, no owner"
                                % (where, f))
            if ev:
                errs.append("%s: container records carry no executor_evidence" % where)
            return errs

        if prof is None:
            errs.append("%s: an executable v2 task requires an execution_profile" % where)
        else:
            validate_profile_v2(prof, errs, where, topology, rec)
            cap = prof.get("required_capability")
            if cap is None:
                errs.append("%s: an executable work item has exactly ONE "
                            "required_capability; it determines the Development column, "
                            "the valid PEER reviewer and the Wave 6 queue" % where)
            # Ready invariant: enforced at the Ready -> Development transition, which
            # is where the reason for it actually bites. An item may sit in Ready
            # pending classification; it may not start.
            got = str((rec.get("lifecycle") or {}).get("jira_status_id") or "")
            if canonical == "development":
                for f in ("project_id", "required_capability", "work_effort"):
                    if (prof.get(f) if f != "project_id" else rec.get("project_id")) is None:
                        errs.append("%s: %s is required before an execution status"
                                    % (where, f))
                want = board.execution_status_for(cap) if cap else None
                if cap in board.NO_EXECUTION_CAPABILITIES:
                    errs.append("%s: capability %r has no execution status — QA is a "
                                "validation route, not an execution lane" % (where, cap))
                elif want and got and not board.is_legacy(got) and want != got:
                    errs.append("%s: capability %r executes in status %s (%s) but the item "
                                "is in %s (%s) — Design/Content/Operations and the two "
                                "developer lanes are ALTERNATIVES chosen by capability, "
                                "never a sequence"
                                % (where, cap, want, board.name_for(want), got,
                                   board.name_for(got)))
            _review_coherence(rec, prof, canonical, got, errs, where)
        validate_review_context(rec.get("review_context"), canonical, prof, errs,
                                where, rec=rec)
        cr = rec.get("completion_reconciliation")
        if cr is not None:
            if not isinstance(cr, dict):
                errs.append("%s: completion_reconciliation must be an object" % where)
            else:
                for f in ("by", "at", "completion_ref", "from_status",
                          "to_review_status", "route"):
                    if not cr.get(f):
                        errs.append("%s: completion_reconciliation.%s is required"
                                    % (where, f))
                if cr.get("by") and cr["by"] not in ("po", "ceo"):
                    errs.append("%s: completion_reconciliation.by %r is not a "
                                "reconciliation authority" % (where, cr.get("by")))
                if cr.get("route") and cr["route"] not in REVIEW_TYPES:
                    errs.append("%s: completion_reconciliation.route %r is unknown"
                                % (where, cr.get("route")))
                _reflen(cr, ["completion_ref"], errs, where)
        er = rec.get("execution_recovery")
        if er is not None:
            if not isinstance(er, dict):
                errs.append("%s: execution_recovery must be an object" % where)
            else:
                for f in ("by", "at", "recovery_ref", "from_status"):
                    if not er.get(f):
                        errs.append("%s: execution_recovery.%s is required" % (where, f))
                if er.get("by") and er["by"] not in ("po", "ceo"):
                    errs.append("%s: execution_recovery.by %r is not a recovery "
                                "authority — Ready is the Product-selected queue"
                                % (where, er.get("by")))
                _reflen(er, ["recovery_ref"], errs, where)
        ls = rec.get("logical_surfaces")
        if ls is not None:
            if not isinstance(ls, list) or not all(isinstance(o, str) and o.strip()
                                                   for o in ls):
                errs.append("%s: logical_surfaces is an optional list of non-empty "
                            "object names — a compatibility declaration, not a model "
                            "of the database" % where)
            elif len(ls) > 20:
                errs.append("%s: logical_surfaces names %d objects; it declares known "
                            "overlap, not an inventory" % (where, len(ls)))

    elif kind == "routing":
        _req(rec, ["request_id", "originating_work_item", "required_capability",
                   "raised_by", "return_to", "status"], errs, where)
        if rec.get("required_capability") not in CAPABILITIES:
            errs.append("%s: unknown required_capability %r" % (where, rec.get("required_capability")))
        if rec.get("status") not in ROUTING_STATUS:
            errs.append("%s: unknown status %r" % (where, rec.get("status")))
        # A discoverer records what it found; it does not size another capability's
        # work. Work Effort arrives at the executing capability's own Preflight.
        if rec.get("work_effort") is not None:
            errs.append("%s: a routing request carries no work_effort — the discoverer "
                        "may not estimate another capability's work" % where)
        _reflen(rec, ["discovered_scope", "dependency_ref", "selection_evidence"], errs, where)

    elif kind == "exception":
        _req(rec, ["exception_id", "originating_work_item", "raised_by", "return_to",
                   "exception_type", "status"], errs, where)
        if rec.get("exception_type") not in EXCEPTION_TYPES:
            errs.append("%s: unknown exception_type %r" % (where, rec.get("exception_type")))
        if rec.get("status") not in EXCEPTION_STATUS:
            errs.append("%s: unknown status %r" % (where, rec.get("status")))
        rc = rec.get("redirect_count", 0)
        if not isinstance(rc, int) or rc < 0 or rc > 1:
            errs.append("%s: redirect_count must be 0 or 1 — the Dispatcher redirects once "
                        "and exits; a second redirect is a relay chain" % where)
        auth = rec.get("decision_authority")
        if auth and auth not in seatset:
            errs.append("%s: decision_authority %r is not a declared seat" % (where, auth))
        _reflen(rec, ["question", "resolution_ref"], errs, where)

    elif kind == "policy":
        _req(rec, ["policy_id", "policy_kind", "scope", "activated_by", "reason_ref"],
             errs, where)
        k, sc, tgt = rec.get("policy_kind"), rec.get("scope"), rec.get("target")
        if k not in POLICY_KINDS:
            errs.append("%s: unknown execution policy kind %r" % (where, k))
        if sc not in POLICY_SCOPES:
            errs.append("%s: unknown policy scope %r — system/product/capability only; "
                        "there is no TASK scope" % (where, sc))
        if sc == "system":
            if tgt is not None:
                errs.append("%s: a system-scoped policy takes no target, got %r"
                            % (where, tgt))
        elif sc == "product":
            if not tgt or (prods and tgt not in prods):
                errs.append("%s: a product-scoped policy needs a known product target, "
                            "got %r" % (where, tgt))
        elif sc == "capability":
            if tgt not in CAPABILITIES:
                errs.append("%s: a capability-scoped policy needs a known capability "
                            "target, got %r" % (where, tgt))
        for f in ("activated_by", "cleared_by"):
            v = rec.get(f)
            if v and v not in POLICY_AUTHORITIES and v not in seatset:
                errs.append("%s: %s %r is not a policy authority (%s) or a declared "
                            "seat" % (where, f, v, "/".join(sorted(POLICY_AUTHORITIES))))
        if rec.get("cleared_at") and not rec.get("cleared_by"):
            errs.append("%s: a cleared policy records who cleared it" % where)
        if rec.get("cleared_by") and not rec.get("cleared_at"):
            errs.append("%s: a policy with cleared_by records when" % where)
        _reflen(rec, ["reason_ref"], errs, where)

    elif kind == "intervention":
        _req(rec, ["intervention_id", "kind", "scope", "created_by", "reason_ref"],
             errs, where)
        k, sc = rec.get("kind"), rec.get("scope")
        if k not in INTERVENTION_KINDS:
            errs.append("%s: unknown intervention kind %r — the set is fixed at "
                        "stop/hold/freeze; these are safety primitives, not a growing "
                        "vocabulary" % (where, k))
        if sc not in INTERVENTION_SCOPES:
            errs.append("%s: unknown scope %r" % (where, sc))
        if k in KIND_SCOPE and sc != KIND_SCOPE[k]:
            errs.append("%s: kind %r is always scope %r, got %r — a STOP is a task, a "
                        "HOLD is a capability, a FREEZE is the system"
                        % (where, k, KIND_SCOPE[k], sc))
        tgt = rec.get("target")
        if sc == "task":
            if not tgt or not JIRA_KEY.match(str(tgt)):
                errs.append("%s: a task-scoped intervention needs a Jira key target" % where)
        elif sc == "capability":
            if tgt not in CAPABILITIES:
                errs.append("%s: a capability-scoped intervention needs a known "
                            "capability target, got %r" % (where, tgt))
        elif sc == "system":
            if tgt is not None:
                errs.append("%s: a system-scoped intervention takes no target, got %r"
                            % (where, tgt))
        for f in ("created_by", "cleared_by"):
            v = rec.get(f)
            if v and v not in INTERVENTION_AUTHORITIES and v not in seatset:
                errs.append("%s: %s %r is not an intervention authority (%s) or a "
                            "declared seat" % (where, f, v,
                                               "/".join(sorted(INTERVENTION_AUTHORITIES))))
        if rec.get("cleared_at") and not rec.get("cleared_by"):
            errs.append("%s: a cleared intervention records who cleared it" % where)
        if rec.get("cleared_by") and not rec.get("cleared_at"):
            errs.append("%s: cleared_by set without cleared_at" % where)
        # RESUME is the clearing OPERATION, never a fourth stored kind.
        if k == "resume" or rec.get("kind") == "resume":
            errs.append("%s: 'resume' is not a stored intervention — it is the operation "
                        "that clears one" % where)
        _reflen(rec, ["reason_ref"], errs, where)

    elif kind == "dependency":
        _req(rec, ["dependency_id", "product_id", "source_work_item", "target_work_item",
                   "relation", "completion_condition"], errs, where)
        if rec.get("relation") != "BLOCKS":
            errs.append("%s: relation must be BLOCKS — IS_BLOCKED_BY is a derived query, "
                        "never a second record" % where)
        if rec.get("completion_condition") != "DONE":
            errs.append("%s: completion_condition must be DONE" % where)
        for f in ("state", "satisfied", "active", "resolved"):
            if f in rec:
                errs.append("%s: %r is not stored — satisfaction is derived from canonical "
                            "lifecycle, never mirrored here" % (where, f))
        for f in ("source_work_item", "target_work_item"):
            if rec.get(f) and not JIRA_KEY.match(rec[f]):
                errs.append("%s: %s must be a Jira key" % (where, f))
        for f, p in (("source_project_id", rec.get("product_id")),
                     ("target_project_id", rec.get("product_id"))):
            v = rec.get(f)
            if v and (p, v) not in projs:
                errs.append("%s: %s %r is not a registered Project of %r" % (where, f, v, p))
    return errs


# ---------------------------------------------------------------- derived reads

def is_blocked(work_item_id, edges, lifecycles):
    """Dependency blocking — DERIVED, never stored.

    An item is blocked if any non-retired edge targets it whose source has not
    reached canonical DONE. A prerequisite sitting in REVIEW does NOT satisfy the
    edge: completion_condition is DONE, and that is enforced by the condition rather
    than by special-casing review.

    blocked != not claimable. Claimability additionally needs capacity, contention
    and a queue — all Wave 6. Wave 5 computes blocked/unblocked and nothing more.
    """
    for e in edges:
        if e.get("retired_at") or e.get("target_work_item") != work_item_id:
            continue
        if lifecycles.get(e.get("source_work_item")) != "done":
            return True
    return False


def check_graph_addition(edges, new):
    """Integrity of the whole graph, checked under the Product graph lock."""
    s, t = new.get("source_work_item"), new.get("target_work_item")
    if s == t:
        return "self-edge %s BLOCKS itself" % s
    for e in edges:
        if e.get("source_work_item") == s and e.get("target_work_item") == t:
            return "duplicate active edge %s BLOCKS %s (%s)" % (s, t, e.get("dependency_id"))
    adj = {}
    for e in edges:
        adj.setdefault(e["source_work_item"], []).append(e["target_work_item"])
    adj.setdefault(s, []).append(t)
    colour = {}
    def cyclic(n):
        colour[n] = 1
        for m in adj.get(n, []):
            if colour.get(m) == 1:
                return True
            if colour.get(m) is None and cyclic(m):
                return True
        colour[n] = 2
        return False
    for n in list(adj):
        if colour.get(n) is None and cyclic(n):
            return "would create a dependency cycle involving %s" % s
    return None


def check(runtime=None):
    runtime = runtime or RUNTIME
    errs = []
    prods, projs = registry()
    if "dabbler" not in prods:
        errs.append("registry: product 'dabbler' is missing")
    try:
        import sprint
        sprint.canonical_tz()
    except Exception as e:
        errs.append("registry: %s" % e)
    seatset = seats()
    topology = seats_by_capability()
    for pid, jid in projs:
        po = projs[(pid, jid)].get("current_po_seat_id")
        if po and po not in seatset:
            errs.append("registry: project %s/%s binds PO seat %r which is not declared"
                        % (pid, jid, po))
    kinds = {"task": "tasks", "routing": "routing", "exception": "exceptions",
             "dependency": "dependencies", "intervention": "interventions",
             "policy": "policies"}
    seen_ids = {}
    edges = []
    active_iv = []
    active_pol = []
    for kind, sub in kinds.items():
        d = os.path.join(runtime, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(d, fn)
            try:
                rec = json.load(open(p, encoding="utf-8"))
            except Exception as e:
                errs.append("%s: invalid JSON (%s)" % (p, e)); continue
            if isinstance(rec, list):
                errs.append("%s: a record file holds ONE record, never an array — "
                            "a single aggregate file would serialise every write" % p); continue
            idf = {"task": "work_item_id", "routing": "request_id",
                   "exception": "exception_id", "dependency": "dependency_id",
                   "intervention": "intervention_id", "policy": "policy_id"}[kind]
            rid = rec.get(idf)
            if rid != fn[:-5]:
                errs.append("%s: filename does not match %s %r" % (p, idf, rid))
            if (kind, rid) in seen_ids:
                errs.append("%s: duplicate id %r" % (p, rid))
            seen_ids[(kind, rid)] = p
            errs += validate_record(kind, rec, prods, projs, seatset, topology)
            if kind == "dependency" and not rec.get("retired_at"):
                edges.append(rec)
            if kind == "intervention" and not rec.get("cleared_at"):
                active_iv.append(rec)
            if kind == "policy" and not rec.get("cleared_at"):
                active_pol.append(rec)
    # At most one ACTIVE intervention per (kind, scope, target): a second would make
    # clearing ambiguous — which one did RESUME clear?
    seen_iv = {}
    for iv in active_iv:
        key = (iv.get("kind"), iv.get("scope"), iv.get("target"))
        if key in seen_iv:
            errs.append("intervention %s: duplicate ACTIVE %s/%s on target %r (already "
                        "%s) — clear the first before creating another"
                        % (iv.get("intervention_id"), key[0], key[1], key[2], seen_iv[key]))
        seen_iv[key] = iv.get("intervention_id")

    built = []
    for e in edges:
        problem = check_graph_addition(built, e)
        if problem:
            errs.append("dependency graph: %s" % problem)
        else:
            built.append(e)
    return errs


if __name__ == "__main__":
    if "--check" not in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    errs = check()
    hard = [e for e in errs if " WARN " not in e]
    for e in errs:
        print(("WARN  " if " WARN " in e else "FAIL  ") + e)
    if hard:
        print("\n%d problem(s)" % len(hard)); sys.exit(1)
    print("ok      persistent state valid")
    sys.exit(0)
