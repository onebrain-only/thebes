#!/usr/bin/env python3
"""Thebes Persistent State — the mandatory write path for runtime records.

Every operational mutation under agent/state/runtime/ goes through here.
Nothing technically prevents an agent editing the JSON directly; the rule is
constitutional, exactly like the no-delegation rule. What this module gives you
is the only implementation where the guarantees actually hold.

WHY A UTILITY AND NOT "JUST WRITE THE FILE"
  Read-modify-check-write across four syscalls is not compare-and-swap. Two
  writers can both read revision 5, both re-check 5, and both write 6 — the
  second silently destroying the first. os.replace() makes a write atomic for
  *readers*; it does nothing to serialise *writers*. So the revision check and
  the write happen inside one fcntl.flock region, and that is the whole point.

SCOPE
  Same working copy: flock serialises every process sharing this filesystem.
  Different clone / worktree / cloud checkout: NO COORDINATION. Runtime state is
  workspace-local by design (it is git-ignored), so there is nothing shared to
  corrupt — but it is also not global truth. Wave 6 revisits this.

Stdlib only. No DELETE: records are retired or withdrawn, never removed.
"""
import fcntl, hashlib, json, os, re, sys, uuid
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE = os.path.join(ROOT, "agent", "state")
RUNTIME = os.path.join(STATE, "runtime")
REGISTRY = os.path.join(STATE, "registry")
LOCKS = os.path.join(RUNTIME, ".locks")
SCHEMA_VERSION = 3

KINDS = {
    "task":       ("tasks",        None),
    "routing":    ("routing",      "rr"),
    "exception":  ("exceptions",   "exc"),
    "dependency": ("dependencies", "dep"),
    "intervention": ("interventions", "int"),
    "policy":       ("policies",      "pol"),
    "event":        ("events",        "evt"),
    "learning":     ("learning",      "lrn"),
    # Human-organization records. These are not provider transcripts: they are
    # the durable professional ledger of work, decisions, and delegations.
    "work_cycle":   ("work-cycles",   "cycle"),
    "decision":     ("decisions",     "decision"),
    "delegation":   ("delegations",   "delegation"),
    # Coverage is NOT an event. It records that observation HAPPENED, which is the
    # only way "no blockers" can be told apart from "nobody looked".
    "coverage":     ("coverage",      None),
    # A correction does not amend or delete the event it names. It is a separate
    # append that the READ side honours; the original stays byte-identical and
    # auditable forever.
    "correction":   ("corrections",   "cor"),
    "operating_mode": ("operating-mode", None),
    "execution_lease": ("execution-leases", "lease"),
    # A receipt is inert, immutable evidence that a dispatched invocation reached
    # a normalized terminal result.  It is deliberately separate from leases:
    # closing a lease proves ordering cleanup, not what the provider returned.
    "execution_receipt": ("execution-receipts", "receipt"),
    # An approval is immutable, exact evidence for one native permission boundary.
    # It is deliberately not a general permission or provider configuration.
    "execution_approval": ("execution-approvals", "approval"),
    "execution_continuation_preparation": ("execution-continuations", "continuation"),
    # A retirement is immutable evidence that a provider session is historical
    # only.  It never deletes the receipt/session it names.
    "execution_session_retirement": ("execution-session-retirements", "session-retirement"),
    # One replacement is permitted for a retired execution lineage.  It is not
    # a new task or a second claim.
    "execution_replacement": ("execution-replacements", "replacement"),
    # Immutable evidence that validated Product work was attributed, committed
    # and offered to the integration branch, and what git said happened. It
    # records the orchestration act; git remains the authority on the code.
    "integration_receipt": ("integration-receipts", "integration"),
    # Evidence of a bounded Product grant. A company investment envelope belongs
    # to CEO; execution inside an approved roadmap belongs to PM. Selection stays
    # with the canonical planner and every grant references the actual decision.
    "product_authorization": ("product-authorizations", "authz"),
    # The durable identity binding a persistent provider session to a seat.
    # Natural key = seat_id: a seat has at most one ACTIVE binding, and rebinding
    # is a CAS update that keeps history rather than a second record.
    "role_session": ("role-sessions", None),
    # One prepared-but-not-yet-woken persistent-session dispatch. It exists
    # beside the one-shot execute path, not instead of it: preparation runs the
    # same authorization/claim/workspace machinery and stops before any provider
    # wake, so a durably-bound worker session can be told to do the work itself.
    "session_dispatch": ("session-dispatches", "dispatch"),
}

# Providers a role_session may be bound to. The persistent-session dispatch
# path is Claude-only in this slice (see agent/controller/session_dispatch.py);
# this vocabulary is not hardwired to that restriction — it just names the two
# providers Thebes knows how to wake at all.
ROLE_SESSION_PROVIDERS = frozenset({"claude", "codex"})

# The complete outcome vocabulary a session_dispatch may settle to. Exactly one
# of these ends a dispatch; a follow-up (an answer to a decision, an unblock) is
# a NEW prepare for the same item, not a second outcome on this one.
SESSION_DISPATCH_OUTCOMES = frozenset({
    "completed", "blocked", "decision_required", "clarification_required",
    "failed", "worker_unreachable",
})


# The complete integration vocabulary. A git failure is not a provider failure
# and not a Product-implementation failure; each stays its own fact.
INTEGRATION_OUTCOMES = frozenset({
    "integrated", "already-present", "no-product-commit-required",
    "attribution-failed", "commit-failed", "integration-conflict",
    "integration-failed", "validation-not-passed",
})


class StateError(Exception):
    """Refused write. Never raised for a condition the caller could not check."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id(kind):
    prefix = KINDS[kind][1]
    if prefix is None:
        raise StateError("%s ids are natural keys, not generated" % kind)
    return "%s-%s" % (prefix, uuid.uuid4())


def _dir(kind):
    d = os.path.join(RUNTIME, KINDS[kind][0])
    os.makedirs(d, exist_ok=True)          # created on demand; never committed
    return d


def path_for(kind, rid):
    return os.path.join(_dir(kind), rid + ".json")


class _Lock:
    """Exclusive advisory lock. Released by the kernel if the process dies, so
    there is no stale-lock reaper and no timeout to tune."""

    def __init__(self, name):
        os.makedirs(LOCKS, exist_ok=True)
        self.path = os.path.join(LOCKS, name + ".lock")

    def __enter__(self):
        self.fh = open(self.path, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()
        return False


def record_lock(kind, rid):
    return _Lock("%s-%s" % (kind, rid))


def graph_lock(product_id):
    """Product-wide dependency lock.

    Per-edge locks cannot protect a graph invariant: two sessions adding X→Y and
    Y→X under different edge locks each pass a cycle check alone and together
    make a cycle. Every graph mutation — read, integrity check, write — happens
    under this one lock. Dependency writes are rare; serialising them is cheap.
    """
    return _Lock("graph-%s" % product_id)


def _atomic_write(path, obj):
    """Temp file in the SAME directory — os.replace is only atomic within one
    filesystem — then fsync, then replace."""
    tmp = path + ".tmp.%d" % os.getpid()
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try: os.unlink(tmp)
            except OSError: pass
        raise


def read(kind, rid):
    p = path_for(kind, rid)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def read_all(kind):
    d = _dir(kind)
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            with open(os.path.join(d, fn), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out


def current_operating_mode():
    """Return the current execution domain without changing Product state.

    A pre-hardening runtime has no record, so it keeps its historical Product
    behavior until its first explicit transition. New sessions set a mode before
    orchestration and thereafter use the singleton record.
    """
    import operations                                  # noqa: E402
    rec = read("operating_mode", operations.CURRENT_MODE_ID)
    return (rec or {}).get("mode", operations.PRODUCT_EXECUTION)


def set_operating_mode(mode, changed_by, reason_ref, expected_revision=None):
    """Create or CAS-transition the singleton operating-mode record."""
    import operations                                  # noqa: E402
    if mode not in operations.OPERATING_MODES:
        raise StateError("unknown operating mode %r" % mode)
    if not changed_by or not reason_ref:
        raise StateError("changed_by and reason_ref are required")
    rid = operations.CURRENT_MODE_ID
    with _Lock("execution-domain"):
        if mode == operations.SYSTEM_MAINTENANCE:
            active = [lease for lease in read_all("execution_lease")
                      if not lease.get("closed_at")]
            if active:
                raise StateError("cannot enter SYSTEM_MAINTENANCE with active execution leases: %s"
                                 % ", ".join(lease["execution_lease_id"] for lease in active))
        with record_lock("operating_mode", rid):
            cur = read("operating_mode", rid)
            if cur is None:
                if expected_revision is not None:
                    raise StateError("operating mode does not exist; expected_revision must be null")
                rec = {"operating_mode_id": rid, "mode": mode, "changed_by": changed_by,
                       "reason_ref": reason_ref, "schema_version": SCHEMA_VERSION,
                       "revision": 1, "created_at": now(), "updated_at": now()}
            else:
                if expected_revision is None:
                    raise StateError("expected_revision is required; there is no force update")
                if cur["revision"] != expected_revision:
                    raise StateError("stale write refused: operating mode is at revision %d, "
                                     "caller expected %d" % (cur["revision"], expected_revision))
                rec = dict(cur, mode=mode, changed_by=changed_by, reason_ref=reason_ref,
                           revision=cur["revision"] + 1, updated_at=now())
            _validate_one("operating_mode", rec)
            _atomic_write(path_for("operating_mode", rid), rec)
            return rec


def create(kind, record, rid=None):
    """Create exactly once. Concurrent creates of the same id: one wins, the
    other is refused — the check happens under the lock."""
    if kind not in KINDS:
        raise StateError("unknown kind %r" % kind)
    rid = rid or record.get(_id_field(kind)) or new_id(kind)
    record = dict(record)
    record[_id_field(kind)] = rid
    record["schema_version"] = SCHEMA_VERSION
    record["revision"] = 1
    record["created_at"] = record.get("created_at") or now()
    record["updated_at"] = record["created_at"]
    with record_lock(kind, rid):
        if os.path.exists(path_for(kind, rid)):
            raise StateError("%s %s already exists" % (kind, rid))
        _validate_one(kind, record)
        _atomic_write(path_for(kind, rid), record)
    return record


def update(kind, rid, expected_revision, changes):
    """Compare-and-swap. expected_revision is mandatory: there is no force mode,
    because an optional safety check is an absent one."""
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    with record_lock(kind, rid):
        cur = read(kind, rid)
        if cur is None:
            raise StateError("%s %s does not exist" % (kind, rid))
        if cur["revision"] != expected_revision:
            raise StateError(
                "stale write refused: %s %s is at revision %d, caller expected %d"
                % (kind, rid, cur["revision"], expected_revision))
        merged = dict(cur)
        merged.update(changes)
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one(kind, merged)
        _atomic_write(path_for(kind, rid), merged)
        return merged


def create_dependency(record):
    """Dependency creation under the PRODUCT GRAPH LOCK — see graph_lock()."""
    from validate import check_graph_addition          # noqa: E402
    product = record.get("product_id")
    if not product:
        raise StateError("dependency requires product_id")
    with graph_lock(product):
        edges = [e for e in read_all("dependency") if not e.get("retired_at")]
        problem = check_graph_addition(edges, record)
        if problem:
            raise StateError("dependency refused: " + problem)
        rid = new_id("dependency")
        rec = dict(record)
        rec["dependency_id"] = rid
        rec["schema_version"] = SCHEMA_VERSION
        rec["revision"] = 1
        rec["created_at"] = rec.get("created_at") or now()
        rec["updated_at"] = rec["created_at"]
        _validate_one("dependency", rec)
        _atomic_write(path_for("dependency", rid), rec)
        return rec


def transition_target(capability=None, route=None):
    """The one legal CURRENT destination for a capability or a route. Guarded.

    This is the only place workflow logic should obtain a transition target, and it
    can never return a legacy status: the capability and route tables name live ids
    only, and the guard re-checks anyway.
    """
    import board                                        # noqa: E402
    if (capability is None) == (route is None):
        raise StateError("give exactly one of capability or route")
    sid = (board.execution_status_for(capability) if capability is not None
           else board.review_status_for(route))
    if sid is None:
        raise StateError("no execution status for capability %r" % capability
                         if capability is not None else "unknown route %r" % route)
    try:
        return board.assert_transition_target(sid)
    except ValueError as e:
        raise StateError(str(e))


def observe_lifecycle(work_item_id, expected_revision, jira_status_id, observed_at=None):
    """Record a lifecycle OBSERVATION of Jira. CAS'd.

    Column, status name and canonical state are all derived from the live board
    model — the caller supplies only the status id it just read from Jira, so a
    stale or invented column name cannot enter the record.

    A LEGACY status is accepted here on purpose. This function records what Jira
    says, and an unreconciled or historical item legitimately sits on one; the
    validator marks it WARN. Rejecting it would make the migration state unwritable.
    Use transition_target() to choose where to MOVE something — that guard is where
    legacy ids are refused.
    """
    import board                                        # noqa: E402
    sid = str(jira_status_id)
    if board.canonical_for(sid) is None:
        raise StateError("unknown Jira status id %r — not on the live KAN board" % sid)
    lc = {
        "canonical": board.canonical_for(sid),
        "jira_column": board.column_for(sid),
        "jira_status_id": sid,
        "jira_status_name": board.name_for(sid),
        "observed_at": observed_at or now(),
        "source": "jira",
    }
    return update("task", work_item_id, expected_revision, {"lifecycle": lc})


def reconcile_review_from_jira(work_item_id, expected_revision, jira_status_id):
    """Adopt the review route Jira is showing. CAS'd.

    Jira is authoritative for WHICH REVIEW ROUTE IS ACTIVE once the transition has
    succeeded, so this is the repair path for the state a successful Jira transition
    plus a failed local write leaves behind.

    It refuses exactly one thing: adopting a route WEAKER than the policy computes
    from the item's own characteristics. Every transition on this board is global
    and unconditional, so anyone can drag an item from Peer-review to Self-review;
    letting "Jira wins" absorb that would turn the no-downgrade rule into a
    suggestion. The repair for a weaker Jira status is to move the issue back in
    Jira — not to lower the route here.
    """
    import board, policy                                # noqa: E402
    sid = str(jira_status_id)
    route = board.route_for_status(sid)
    if route is None:
        raise StateError("status %r is not one of the three review statuses" % sid)
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        prof = dict(cur.get("execution_profile") or {})
        ch = prof.get("characteristics")
        rc_cur = cur.get("review_context") or {}
        # Same authorised carve-out as the validator: after a PEER-fail transfer the
        # reviewer SELF-reviews its own fix, so a peer-floor item may legally show
        # Self-review. previous_owner is the record that the transfer happened.
        transferred = (bool(rc_cur.get("previous_owner"))
                       and rc_cur.get("review_type") == "self" and route == "self")
        if ch is not None and not transferred:
            floor = policy.validation_route(ch)
            if policy.STRICTNESS[route] < policy.STRICTNESS[floor]:
                raise StateError(
                    "refusing to reconcile: Jira shows %s (%s) = route %r, weaker than "
                    "the %r this item's characteristics require. Move the issue back in "
                    "Jira." % (sid, board.name_for(sid), route, floor))
        prov = dict(prof.get("provenance") or {})
        prof["validation_route"] = route
        prov["validation_route"] = {"by": "system-policy", "at": now(),
                                    "reconciled_from_jira": sid}
        prof["provenance"] = prov
        rc = dict(cur.get("review_context") or {})
        if rc and not rc.get("previous_owner"):
            # Keep review_type in step with the route, except after a PEER-fail
            # transfer, where SELF on a peer-routed item is the intended end state.
            rc["review_type"] = route
        merged = dict(cur)
        merged["execution_profile"] = prof
        if rc:
            merged["review_context"] = rc
        merged["lifecycle"] = {
            "canonical": board.canonical_for(sid),
            "jira_column": board.column_for(sid),
            "jira_status_id": sid,
            "jira_status_name": board.name_for(sid),
            "observed_at": now(),
            "source": "jira",
        }
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def set_characteristics(work_item_id, expected_revision, changes, author,
                        paths=None, execution_started=None):
    """Record task characteristics and let POLICY recompute the route. CAS'd.

    This is the only supported way a route changes. An actor states facts about the
    work; the route follows. Nobody hands in a `validation_route` — and because the
    recompute happens inside the same lock as the write, no two writers can race a
    characteristic in and a route out of step with it.

    Escalation only, once development has started: a worker who finds an RLS
    migration mid-execution raises `schema_change` and the route moves SELF -> PEER;
    removing the characteristic afterwards does not move it back.
    """
    import policy                                       # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") == "container":
            raise StateError("container records carry no characteristics or route")
        prof = dict(cur.get("execution_profile") or {})
        ch = dict(prof.get("characteristics") or {})
        prov = dict(prof.get("provenance") or {})
        chprov = dict((prov.get("characteristics") or {}).get("fields") or {})

        # Authority is by ACTOR CLASS: a seat authors as "worker:<seat>", and every
        # worker holds the same assert/withdraw rights. Matching the literal string
        # against the authority table would silently deny every real caller.
        actor = "worker" if str(author).startswith("worker:") else str(author)

        started = (execution_started if execution_started is not None
                   else (cur.get("lifecycle") or {}).get("canonical") in
                        ("development", "review", "done"))

        for name, value in (changes or {}).items():
            if name not in policy.CHARACTERISTICS:
                raise StateError("unknown task characteristic %r" % name)
            if name in policy.SYSTEM_DERIVED:
                raise StateError("%s is system-derived; it is computed from paths, "
                                 "not asserted" % name)
            rule = policy.AUTHORITY[name]
            was, now_ = bool(ch.get(name)), bool(value)
            if now_ and not was and actor not in rule["assert_true"]:
                raise StateError("%s may not assert %s" % (author, name))
            if was and not now_:
                if actor not in rule["downgrade"]:
                    raise StateError("%s may not withdraw %s — escalation is available "
                                     "to whoever finds the danger, de-escalation is not "
                                     "available to whoever benefits from it"
                                     % (author, name))
                if cur.get("review_context") is not None:
                    raise StateError("%s cannot be withdrawn once review has begun" % name)
            ch[name] = now_
            chprov[name] = {"by": author, "at": now()}

        # The one characteristic nobody asserts.
        if paths is not None:
            ch["shared_or_contended_surface"] = policy.derive_contended(paths)
            chprov["shared_or_contended_surface"] = {"by": "system-derived", "at": now()}

        recomputed = policy.validation_route(ch)
        route = policy.escalate(prof.get("validation_route"), recomputed, started)

        prof["characteristics"] = ch
        prof["validation_route"] = route
        prof["completion_route"] = "DONE"
        prov["characteristics"] = {"by": "system-derived", "at": now(), "fields": chprov}
        prov["validation_route"] = {"by": "system-policy", "at": now()}
        prov["completion_route"] = {"by": "system-policy", "at": now()}
        prof["provenance"] = prov
        prof.setdefault("profile_status", "partial")
        eff = [f for f in ("project_id", "required_capability", "work_effort",
                           "characteristics", "validation_route", "completion_route")
               if (cur.get(f) if f == "project_id" else prof.get(f)) is not None]
        prof["effective_fields"] = eff

        merged = dict(cur)
        merged["execution_profile"] = prof
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def set_operational_context(work_item_id, expected_revision, intent,
                            reported_environment, author, evidence_ref,
                            supersedes_validation_ref=None, supersedes_context_ref=None):
    """Persist reported intent and derive its authoritative primary target atomically."""
    import operations                                  # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if intent not in operations.TASK_INTENTS:
        raise StateError("unknown task intent %r" % intent)
    if not author or not evidence_ref:
        raise StateError("author and evidence_ref are required")
    try:
        target = operations.derive_primary_target(reported_environment)
    except ValueError as exc:
        raise StateError(str(exc))
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") != "executable":
            raise StateError("container records carry no operational context")
        context = dict(cur.get("operational_context") or {})
        prior_context = dict(context)
        prior_plan = context.get("validation_plan")
        changed_report = bool(context) and (
            context.get("intent") != intent
            or context.get("reported_environment") != dict(reported_environment or {}))
        if changed_report:
            if not supersedes_context_ref:
                raise StateError("operational-context correction requires supersedes_context_ref")
            history = list(context.get("context_history") or [])
            history.append({"intent": prior_context.get("intent"),
                            "reported_environment": prior_context.get("reported_environment"),
                            "primary_target": prior_context.get("primary_target"),
                            "provenance": prior_context.get("provenance"),
                            "superseded_at": now(), "superseded_by": supersedes_context_ref})
            context["context_history"] = history
        context.update({"intent": intent, "initial_phase": operations.initial_phase(intent),
                        "reported_environment": dict(reported_environment or {}),
                        "primary_target": target,
                        "comparative_targets": context.get("comparative_targets") or [],
                        "provenance": {"by": author, "at": now(),
                                       "evidence_ref": evidence_ref}})
        if context.get("diagnosis"):
            new_plan = operations.derive_validation_plan(context["diagnosis"], target)
            prior_required = {item.get("target_id")
                              for item in (prior_plan or {}).get("required") or []}
            new_required = {item.get("target_id") for item in new_plan["required"]}
            if prior_required - new_required:
                if not supersedes_validation_ref:
                    raise StateError("operational-context change would remove required validation "
                                     "targets; supersedes_validation_ref is required")
                history = list(context.get("validation_history") or [])
                history.append({"plan": prior_plan, "superseded_at": now(),
                                "superseded_by": supersedes_validation_ref})
                context["validation_history"] = history
                context["diagnosis"] = dict(
                    context["diagnosis"],
                    supersedes_validation_ref=supersedes_validation_ref)
            prior_evidence = (prior_plan or {}).get("evidence") or {}
            known = {item.get("target_id")
                     for item in new_plan["required"] + new_plan["optional"]}
            new_plan["evidence"] = {target_id: evidence
                                    for target_id, evidence in prior_evidence.items()
                                    if target_id in known}
            context["validation_plan"] = new_plan
        merged = dict(cur, operational_context=context,
                      revision=cur["revision"] + 1, updated_at=now())
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def set_diagnosis(work_item_id, expected_revision, causal_surface, changed_surfaces,
                  platform_specificity, affected_platforms, author, evidence_ref,
                  supersedes_validation_ref=None, causal_platforms=None):
    """Record causal findings and derive validation scope in the same CAS write."""
    import operations                                  # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    diagnosis = {"causal_surface": causal_surface,
                 "changed_surfaces": sorted(set(changed_surfaces or [])),
                 "platform_specificity": platform_specificity,
                 "affected_platforms": sorted(set(affected_platforms or [])),
                 "causal_platforms": sorted(set(causal_platforms or [])),
                 "provenance": {"by": author, "at": now(), "evidence_ref": evidence_ref}}
    if not causal_surface or not diagnosis["changed_surfaces"] or not author or not evidence_ref:
        raise StateError("causal_surface, changed_surfaces, author and evidence_ref are required")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller expected %d"
                             % (work_item_id, cur["revision"], expected_revision))
        context = dict(cur.get("operational_context") or {})
        if not context:
            raise StateError("operational_context is required before diagnosis")
        try:
            plan = operations.derive_validation_plan(diagnosis, context.get("primary_target"))
        except ValueError as exc:
            raise StateError(str(exc))
        prior_plan = context.get("validation_plan")
        prior_diagnosis = context.get("diagnosis")
        diagnosis_changed = prior_diagnosis is not None and any(
            prior_diagnosis.get(field) != diagnosis.get(field)
            for field in ("causal_surface", "changed_surfaces", "platform_specificity",
                          "affected_platforms", "causal_platforms"))
        prior_required = {target.get("target_id")
                          for target in (prior_plan or {}).get("required") or []}
        new_required = {target.get("target_id") for target in plan.get("required") or []}
        if diagnosis_changed and not supersedes_validation_ref:
            raise StateError("re-diagnosis requires supersedes_validation_ref")
        if prior_required - new_required:
            if not supersedes_validation_ref:
                raise StateError("re-diagnosis would remove required validation targets; "
                                 "supersedes_validation_ref is required")
            diagnosis["supersedes_validation_ref"] = supersedes_validation_ref
        if diagnosis_changed:
            diagnosis["supersedes_validation_ref"] = supersedes_validation_ref
            history = list(context.get("validation_history") or [])
            history.append({"diagnosis": prior_diagnosis, "plan": prior_plan,
                            "superseded_at": now(),
                            "superseded_by": supersedes_validation_ref})
            context["validation_history"] = history
        context["diagnosis"] = diagnosis
        context["validation_plan"] = plan
        merged = dict(cur, operational_context=context,
                      revision=cur["revision"] + 1, updated_at=now())
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def record_validation_evidence(work_item_id, expected_revision, target_id, evidence_ref):
    """Attach evidence to one derived target; optional evidence never gates closure."""
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not target_id or not evidence_ref:
        raise StateError("target_id and evidence_ref are required")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller expected %d"
                             % (work_item_id, cur["revision"], expected_revision))
        context = dict(cur.get("operational_context") or {})
        plan = dict(context.get("validation_plan") or {})
        known = {target.get("target_id")
                 for target in (plan.get("required") or []) + (plan.get("optional") or [])}
        if target_id not in known:
            raise StateError("unknown validation target %r" % target_id)
        evidence = dict(plan.get("evidence") or {})
        evidence[target_id] = evidence_ref
        plan["evidence"] = evidence
        context["validation_plan"] = plan
        merged = dict(cur, operational_context=context,
                      revision=cur["revision"] + 1, updated_at=now())
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def evidenced_executors(task):
    """The DISTINCT seats evidenced as having executed this work, sorted.

    One list, one meaning, read the same way everywhere: `queue.unclaimable_reasons`
    calls two of these `conflicting-evidence`, `policy.resolve_owner_or_wait` refuses
    to name a SELF owner unless there is exactly one, and this helper is what both
    of them are counting. Ownership is NOT evidence and never appears here — a seat
    that holds a claim has not yet executed anything.

    ASSESSMENT IS NOT EXECUTION. An entry carrying a `classification` other than
    `execution` is excluded here — it stays in the record, auditable, but it does not
    establish executor identity. That distinction is doctrine (`CLAUDE.md`: "assessing
    is not claiming"), and it was not enforced until 2026-09-10: a Preflight sizing
    report written to a status file had been landing in this list as though the seat
    had executed the work. Two consequences, both observed on real items: a SELF review
    could not open because two seats appeared evidenced when only one had executed
    (KAN-136), and a seat that had only sized an item was excluded from reviewing it
    (KAN-138, backend-5).
    """
    return sorted({e.get("seat_id") for e in (task.get("executor_evidence") or [])
                   if isinstance(e, dict) and e.get("seat_id")
                   and e.get("classification", "execution") == "execution"})


def open_review_context(work_item_id, expected_revision, opened_by=None,
                        evidenced_reviewer=None):
    """Open the validation route's review context. CAS'd.

    THE MISSING STEP. Until this existed a route could be *computed* — policy has
    derived the owner since Wave 5 — but never *recorded*, so a SELF item that passed
    its validation had no supported path to Done and sat in `Self-review` reading
    REVIEW STATE UNRECONCILED forever. This writes what policy already decides; it
    decides nothing itself.

    THE OWNER IS DERIVED, NEVER PASSED IN
    `policy.resolve_owner_or_wait` is the authority for all three routes and is
    reused unchanged. For SELF it returns the single evidenced executor, or None
    where evidence is absent or conflicting — and here that None becomes a REFUSAL,
    because SELF doctrine says the route cannot start rather than starting ownerless.
    For PEER and QA a None owner is the legitimate WAITING state the doctrine
    requires: the item sits in its review status with `review_owner` null rather than
    being downgraded to an easier route, and this function writes exactly that.

    REOPENING AFTER A FAIL
    A context whose result is `fail` may be reopened on the SAME route with the cycle
    incremented — that is the SELF and QA rework loop verbatim. PEER is excluded:
    its failure path is `peer_fail_transfer`, which moves execution authority to the
    reviewer, and letting a plain reopen stand in for it would drop that transfer.

    Jira is never touched here. Persistent State owns the review context; Jira owns
    the lifecycle status.
    """
    import policy, validate                             # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") != "executable":
            raise StateError("container records carry no review context")

        canonical = (cur.get("lifecycle") or {}).get("canonical")
        if canonical != "review":
            raise StateError("not-in-review: %s is in %r, and a review context is "
                             "opened only once the item is in its review status"
                             % (work_item_id, canonical))

        # T-095(B): a review opens on RELEASED work. `release` is the only act
        # that mints executor evidence, and SELF's owner is derived from that
        # evidence — so an item that still has an owner has not finished the act
        # the review is about to judge. Nothing checked this, which is how a
        # legacy record (KAN-219: owner never released, cycle-1 FAIL still on
        # the record) could be dispatched for review and then dead-end, because
        # `self_fail_reentry` correctly refuses to re-establish an ownership that
        # was never given up.
        owner = (cur.get("ownership") or {}).get("seat_id")
        if owner:
            raise StateError(
                "owner-not-released: %s is still owned by %s. A review opens on "
                "released work — the owner releases, which is also what records "
                "the executor evidence a SELF review's owner is derived from."
                % (work_item_id, owner))

        prof = dict(cur.get("execution_profile") or {})
        route = prof.get("validation_route")
        if route not in policy.STRICTNESS:
            raise StateError("no validation_route on %s — policy derives the route "
                             "from characteristics before a review can open"
                             % work_item_id)

        prev = cur.get("review_context")
        cycle = 1
        if prev is not None:
            if not isinstance(prev, dict):
                raise StateError("review_context on %s is malformed" % work_item_id)
            result = prev.get("review_result")
            if result != "fail":
                raise StateError("review-already-open: %s already has a %r review "
                                 "context with result %r; a settled or pending review "
                                 "is not reopened"
                                 % (work_item_id, prev.get("review_type"), result))
            if prev.get("review_type") == "peer":
                raise StateError("a failed PEER review is not reopened here — "
                                 "peer_fail_transfer moves execution to the reviewer")
            cycle = int(prev.get("review_cycle") or 1) + 1
            # Bounded retest (policy.MAX_REVIEW_CYCLES). Enforced HERE, in the one
            # writer that creates a cycle, so a caller cannot loop developer -> QA
            # -> developer forever by simply asking again. The item keeps its
            # owner, its status and its last FAIL on the record; what it needs now
            # is a human decision, which no retry can supply.
            if cycle > policy.MAX_REVIEW_CYCLES:
                raise StateError(
                    "retest-limit-reached: %s failed its %s review at cycle %d and "
                    "reopening would be cycle %d, above MAX_REVIEW_CYCLES=%d. A "
                    "bounded intervention or a CEO decision is required; the route "
                    "is not downgraded and the review is not retried automatically."
                    % (work_item_id, prev.get("review_type"), cycle - 1, cycle,
                       policy.MAX_REVIEW_CYCLES))

        executors = evidenced_executors(cur)
        owner, resolved = policy.resolve_owner_or_wait(
            route, prof.get("required_capability"), validate.seats_by_capability(),
            evidenced_reviewer=evidenced_reviewer, executor_seats=executors)

        if resolved == policy.SELF and owner is None:
            # Deliberately two distinct reasons: nobody has executed this yet, and
            # two seats claim to have, are different findings needing different repairs.
            if not executors:
                raise StateError(
                    "no-executor-evidence: SELF review of %s cannot start — its owner "
                    "is the evidenced executor, and nothing has evidenced one. Evidence "
                    "arises from store.release, not from ownership, a status file or a "
                    "Jira status." % work_item_id)
            raise StateError(
                "conflicting-executor-evidence: SELF review of %s cannot start — %d "
                "distinct seats are evidenced (%s). Ambiguity is surfaced, never "
                "resolved by picking one."
                % (work_item_id, len(executors), ", ".join(executors)))

        rc = {"review_type": resolved,
              "review_owner": owner,
              "review_result": "pending",
              "review_cycle": cycle,
              "started_at": now()}
        if opened_by:
            rc["opened_by"] = opened_by
        if prev is not None and prev.get("previous_owner"):
            rc["previous_owner"] = prev["previous_owner"]

        merged = dict(cur)
        merged["review_context"] = rc
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


RECOVERY_AUTHORITIES = ("po", "ceo")


def recover_execution_to_ready(work_item_id, expected_revision, recovery_ref, actor):
    """Authorise returning an ORPHANED execution item to Ready. CAS'd.

    THE STATE THIS RECOVERS
      An executable item sitting in a capability execution status with `ownership:
      null`. The validator accepts it, `claim` refuses it (`not-ready`), and until
      now nothing could move it: the transition table had no execution-status ->
      Ready row and no seat was authorised to perform one. It is not historical
      residue — `release` clears ownership without touching Jira, and release is
      deliberately permitted under STOP because a STOP must not trap ownership. So
      the documented escape from a STOP produced a state with no documented exit.

    EVIDENCE IS HISTORY, NOT ASSIGNMENT
      Recovery does NOT restore the previous evidenced executor. That seat may be
      from an earlier session, no longer dispatchable, or simply no longer the right
      one; it is only the last seat that legitimately held execution. Ownership after
      recovery is won the way every other item wins it — through Ready, eligibility,
      claimability and an atomic claim. If the former executor claims it again, that
      is capacity deciding, not history asserting. Preserving that line is the whole
      point of the doctrine.

    WHAT THIS WRITES, AND WHAT IT DOES NOT
      Jira owns lifecycle, so this does not move the issue and does not pretend the
      item is Ready while Jira still shows an execution status. It records the
      AUTHORISATION — who recovered it, when, and against what reference — and the
      lifecycle follows from the real Jira transition through observe_lifecycle. The
      recovery is complete only when Jira reads Ready (10008) and the observation has
      landed.

      Everything else is preserved untouched: executor evidence, characteristics,
      validation route, surfaces, Work Effort, dependencies and the profile. Nothing
      is fabricated — an item whose route was never derived comes back with it still
      null, and stays unclaimable until the ordinary readiness path runs.
    """
    import board                                        # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not recovery_ref:
        raise StateError("recovery_ref is required — recovery is a lifecycle act and "
                         "every lifecycle act names its reason")
    if actor not in RECOVERY_AUTHORITIES:
        raise StateError("unauthorised-recovery-actor: %r may not recover execution "
                         "state. Ready is the Product-selected execution queue, so "
                         "recovery into it is a Product lifecycle act (%s) — never an "
                         "executor resetting its own work."
                         % (actor, "/".join(RECOVERY_AUTHORITIES)))
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") != "executable":
            raise StateError("container records hold no execution state to recover")

        lc = cur.get("lifecycle") or {}
        sid = str(lc.get("jira_status_id") or "")
        canonical = lc.get("canonical")
        if canonical != "development" or board.column_for(sid) is None:
            raise StateError(
                "not-orphaned-execution: %s is %r at status %s. Recovery applies only "
                "to an item in a capability EXECUTION status — not Backlog, not Ready, "
                "not a review status, not Done."
                % (work_item_id, canonical, sid or "none"))
        exec_ids = set(board.CAPABILITY_TO_STATUS_ID.values()) | {
            board.DEFAULT_EXECUTION_STATUS_ID}
        if sid not in exec_ids:
            raise StateError("not-execution-status: %s is at %s (%s), which is not one "
                             "of the capability execution lanes"
                             % (work_item_id, sid, board.name_for(sid)))
        if cur.get("ownership") is not None:
            raise StateError("already-owned: %s is owned by %s — recovery is for "
                             "ORPHANED execution, and never takes work from a current "
                             "owner" % (work_item_id,
                                        (cur["ownership"] or {}).get("seat_id")))
        if cur.get("review_context") is not None:
            raise StateError("review-in-progress: %s carries a review context; its "
                             "route decides what happens next, not recovery"
                             % work_item_id)
        if cur.get("completion_reconciliation") is not None:
            raise StateError("already-reconciled-complete: %s is recorded as factually "
                             "complete and moving forward to review. Completed work is "
                             "never sent backward to Ready merely to regain lifecycle "
                             "reachability." % work_item_id)
        # STOP is task-scoped safety and blocks the recovery itself. HOLD and FREEZE
        # deliberately do NOT: they gate new CLAIMS, and recovery creates no
        # ownership. A recovered item under HOLD or FREEZE simply sits in Ready
        # unclaimable, which is truthful rather than hidden.
        for iv in active_interventions():
            if iv.get("kind") == "stop" and iv.get("target") == work_item_id:
                raise StateError("task-stopped: a STOP is active on %s; recovery waits "
                                 "until it is cleared" % work_item_id)

        # Its own field, not `provenance` — provenance is strictly per execution-profile
        # FIELD, and recovery authorises a lifecycle move rather than setting one.
        merged = dict(cur)
        merged["execution_recovery"] = {"by": actor, "at": now(),
                                        "recovery_ref": recovery_ref,
                                        "from_status": sid}
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def recover_failed_review_to_ready(work_item_id, expected_revision, recovery_ref, actor,
                                   jira_status_id):
    """Return a PEER-FAILED item that has NO evidenced executor to Ready. CAS'd. (T-092)

    THE STATE THIS RECOVERS
      A PEER review recorded `fail` on an item whose `executor_evidence` is empty —
      work that reached the branch outside the wake seam and was routed UP to PEER
      under T-090. The canonical PEER-fail transfer cannot apply: it hands
      execution to the reviewer and records `previous_owner` from the one
      evidenced executor, and here there is none; writing a transfer anyway would
      fabricate executor evidence for work nobody did (T-089(f), T-090(b)).
      `recover_execution_to_ready` refuses a review status and a review context by
      design, `open_review_context` never reopens a failed PEER context, and the
      validator refuses a context in Ready — so nothing could move the item.

    WHAT IT WRITES, ATOMICALLY
      * `review_context` -> null. The failed verdict is preserved verbatim under
        `execution_recovery.closed_review`, so the record still says the review
        happened and what it found; it is brief input for the remediation, never
        a verdict on the next cycle, which starts fresh at cycle 1.
      * `execution_recovery` — the same field `recover_execution_to_ready` writes,
        with `from_status` the review status it left (10045).
      * `lifecycle` observed at the Ready status the caller read back from Jira
        (po transitions Jira FIRST; this records that fact, it does not cause it).
      * `validation_route` recomputed to the POLICY FLOOR from the item's own
        characteristics. The stored PEER was T-090(d)'s evidence-absence raise,
        not a characteristic; left in place it would make the next review
        unopenable (route_for derives from characteristics, open_review_context
        reads the stored route). A floor is not a downgrade.

    Refuses, with a structured reason, everything that is NOT exactly this state.
    It creates no ownership: the item goes back to the QUEUE and is won by an
    ordinary claim.
    """
    import board, policy                                # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not recovery_ref:
        raise StateError("recovery_ref is required — recovery is a lifecycle act and "
                         "every lifecycle act names its reason")
    if actor not in RECOVERY_AUTHORITIES:
        raise StateError("unauthorised-recovery-actor: %r may not recover review "
                         "state; this is a Product lifecycle act (%s)"
                         % (actor, "/".join(RECOVERY_AUTHORITIES)))
    sid_to = str(jira_status_id)
    if board.canonical_for(sid_to) != "ready":
        raise StateError("jira-not-ready: %s read back from Jira is %s (%s), not the "
                         "Ready status; po transitions Jira first and passes the "
                         "status it read back" % (work_item_id, sid_to,
                                                   board.name_for(sid_to) or "unknown"))
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") != "executable":
            raise StateError("container records hold no review state to recover")
        lc = cur.get("lifecycle") or {}
        sid_from = str(lc.get("jira_status_id") or "")
        if lc.get("canonical") != "review":
            raise StateError("not-in-review: %s is %r at status %s; this recovery "
                             "applies only to an item in a review status"
                             % (work_item_id, lc.get("canonical"), sid_from or "none"))
        rc = cur.get("review_context")
        if not isinstance(rc, dict):
            raise StateError("no-review-context: %s carries no review context; "
                             "there is no failed review to close" % work_item_id)
        if rc.get("review_type") != "peer":
            raise StateError("not-a-peer-review: %s's review is %r; SELF and QA fails "
                             "have their own canonical handlers"
                             % (work_item_id, rc.get("review_type")))
        if rc.get("review_result") != "fail":
            raise StateError("review-not-failed: %s's PEER review is %r; only a "
                             "recorded FAIL is recovered" % (work_item_id,
                                                             rc.get("review_result")))
        if cur.get("ownership") is not None:
            raise StateError("already-owned: %s is owned by %s — recovery never takes "
                             "work from a current owner"
                             % (work_item_id, (cur["ownership"] or {}).get("seat_id")))
        if evidenced_executors(cur):
            raise StateError("executor-evidenced: %s has evidenced executor(s) %s; the "
                             "PEER-fail TRANSFER is the path when evidence exists"
                             % (work_item_id, ", ".join(evidenced_executors(cur))))
        if cur.get("completion_reconciliation") is not None:
            raise StateError("already-reconciled-complete: %s is recorded as factually "
                             "complete; it is never sent backward to Ready" % work_item_id)
        for iv in active_interventions():
            if iv.get("kind") == "stop" and iv.get("target") == work_item_id:
                raise StateError("task-stopped: a STOP is active on %s; recovery waits "
                                 "until it is cleared" % work_item_id)

        prof = dict(cur.get("execution_profile") or {})
        floor = policy.validation_route(prof.get("characteristics") or {})
        prov = dict(prof.get("provenance") or {})
        if prof.get("validation_route") != floor:
            prof["validation_route"] = floor
            prov["validation_route"] = {"by": "system-policy", "at": now(),
                                        "basis_ref": "T-092 recovery: route "
                                                     "recomputed to the policy floor "
                                                     "after a PEER FAIL with no "
                                                     "evidenced executor"}
            prof["provenance"] = prov

        merged = dict(cur)
        merged["execution_profile"] = prof
        merged["review_context"] = None
        merged["execution_recovery"] = {"by": actor, "at": now(),
                                        "recovery_ref": recovery_ref,
                                        "from_status": sid_from,
                                        "closed_review": dict(rc)}
        merged["lifecycle"] = {
            "canonical": board.canonical_for(sid_to),
            "jira_column": board.column_for(sid_to),
            "jira_status_id": sid_to,
            "jira_status_name": board.name_for(sid_to),
            "observed_at": now(),
            "source": "jira",
        }
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def recover_remediation_required_to_ready(work_item_id, expected_revision,
                                          recovery_ref, actor, jira_status_id):
    """Return a SETTLED-PASS item whose integration DEMANDS REMEDIATION to Ready. CAS'd.

    THE STATE THIS RECOVERS
      An executable item whose SELF (or QA) review settled PASS, sitting in a review
      status with `ownership: null`, whose latest integration receipt recorded
      `remediation_required: true` — an integration conflict, not a verdict. The
      review is over and cannot be reopened; the Product work is not over. Every
      existing door refuses it, each of them correctly:
        * EXECUTE refuses `not-ready` — the item is not in Ready.
        * EXECUTE-in-Ready cannot be reached by moving Jira alone: the validator
          refuses a review context in Ready (`validate.py:392-393`).
        * VALIDATE refuses `validation-already-settled` — a settled review is settled.
        * `recover_execution_to_ready` refuses a review status and, at
          `store.py:918-921`, any review context at all — by design.
        * `recover_failed_review_to_ready` refuses at `store.py:1019-1022`
          (`not-a-peer-review`) and, were the type peer, again at the FAIL check —
          T-092 is strictly the PEER-fail-with-no-evidence case.
        * completion refuses at `completion.py:104-105` — "receipt still requires
          Product remediation".
      So the item is reachable by nothing. This is its one exit.

    SELF AND QA ONLY — NEVER PEER
      A PEER context carries transfer semantics (`previous_owner`,
      `validate.py:406-410`) that this transition does not reason about, and the
      PEER paths have their own handlers. PASS means `review_result == "pass"`;
      a FAIL has its own handlers too and is refused here.

    WHAT IT WRITES, ATOMICALLY
      * `review_context` -> null. The settled PASS is preserved verbatim under
        `execution_recovery.closed_review` — the record still says the review
        happened and what it found.
      * `execution_recovery` — the same field the neighbouring recoveries write,
        with `from_status` the review status it left, plus
        `remediation_receipt_id` naming the receipt that demanded the remediation.
      * `lifecycle` observed at the Ready status the caller read back from Jira
        (po transitions Jira FIRST; this records that fact, it does not cause it).

    WHY `validation_route` IS NOT RECOMPUTED HERE
      This is the deliberate divergence from `recover_failed_review_to_ready`
      (`store.py:1043-1053`), and it is a decision rather than an omission. That
      transition recomputes because the route it found was T-090(d)'s
      evidence-absence RAISE to PEER — an artefact of missing evidence, not a
      characteristic of the work — and leaving it in place would make the next
      review unopenable (`store.py:972-977`). Here the route was derived from the
      item's own characteristics in the ordinary way, and a review actually opened
      and settled on it, which proves it is openable. There is nothing to repair,
      so `execution_profile` is left byte-identical.

    It creates no ownership: the item goes back to the QUEUE and is won by an
    ordinary claim. Refuses, with a structured reason, everything that is NOT
    exactly this state.
    """
    import board                                         # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not recovery_ref:
        raise StateError("recovery_ref is required — recovery is a lifecycle act and "
                         "every lifecycle act names its reason")
    if actor not in RECOVERY_AUTHORITIES:
        raise StateError("unauthorised-recovery-actor: %r may not recover review "
                         "state; this is a Product lifecycle act (%s)"
                         % (actor, "/".join(RECOVERY_AUTHORITIES)))
    sid_to = str(jira_status_id)
    if board.canonical_for(sid_to) != "ready":
        raise StateError("jira-not-ready: %s read back from Jira is %s (%s), not the "
                         "Ready status; po transitions Jira first and passes the "
                         "status it read back" % (work_item_id, sid_to,
                                                  board.name_for(sid_to) or "unknown"))
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") != "executable":
            raise StateError("container records hold no review state to recover")
        lc = cur.get("lifecycle") or {}
        sid_from = str(lc.get("jira_status_id") or "")
        # A Done item needs no separate branch: it is not canonically `review`, so
        # this same check refuses it. A dead branch would only invite belief.
        if lc.get("canonical") != "review":
            raise StateError("not-in-review: %s is %r at status %s; this recovery "
                             "applies only to an item in a review status"
                             % (work_item_id, lc.get("canonical"), sid_from or "none"))
        rc = cur.get("review_context")
        if not isinstance(rc, dict):
            raise StateError("no-review-context: %s carries no review context; there "
                             "is no settled review to close" % work_item_id)
        if rc.get("review_type") not in ("self", "qa"):
            raise StateError("not-a-self-or-qa-review: %s's review is %r; only a "
                             "settled SELF or QA review reaches this recovery, and a "
                             "PEER context carries transfer semantics this transition "
                             "does not reason about"
                             % (work_item_id, rc.get("review_type")))
        if rc.get("review_result") != "pass":
            raise StateError("review-not-passed: %s's review is %r; only a settled "
                             "PASS is recovered — a FAIL has its own handlers"
                             % (work_item_id, rc.get("review_result")))
        if cur.get("ownership") is not None:
            raise StateError("already-owned: %s is owned by %s — recovery never takes "
                             "work from a current owner"
                             % (work_item_id, (cur["ownership"] or {}).get("seat_id")))
        if cur.get("completion_reconciliation") is not None:
            raise StateError("already-reconciled-complete: %s is recorded as factually "
                             "complete; it is never sent backward to Ready" % work_item_id)

        # NOT `valid_integration_receipt`: that helper filters OUT receipts requiring
        # remediation, so it would refuse every legitimate input to this transition.
        # Latest-wins, mirroring completion.py:87 — a later clean integration means
        # the remediation already happened, and any-matching would recover it anyway.
        receipts = read_integration_receipts(work_item_id)
        usable = [r for r in receipts if isinstance(r, dict)]
        if not usable:
            if receipts:
                raise StateError("malformed-integration-receipt: %s's latest receipt "
                                 "is not an object" % work_item_id)
            raise StateError("no-integration-receipt: %s has no integration receipt; "
                             "nothing records a remediation to perform" % work_item_id)
        latest = sorted(usable, key=lambda r: r.get("created_at") or "")[-1]
        if not latest.get("remediation_required"):
            raise StateError("no-remediation-required: %s's latest integration receipt "
                             "%s (%r) does not require Product remediation; a settled "
                             "PASS with a clean receipt completes, it is not recovered"
                             % (work_item_id, latest.get("integration_receipt_id"),
                                latest.get("outcome")))
        # STOP is task-scoped safety and blocks the recovery itself. HOLD and FREEZE
        # deliberately do NOT: they gate new CLAIMS, and recovery creates no
        # ownership. A recovered item under HOLD or FREEZE simply sits in Ready
        # unclaimable, which is truthful rather than hidden.
        for iv in active_interventions():
            if iv.get("kind") == "stop" and iv.get("target") == work_item_id:
                raise StateError("task-stopped: a STOP is active on %s; recovery waits "
                                 "until it is cleared" % work_item_id)

        merged = dict(cur)
        merged["review_context"] = None
        merged["execution_recovery"] = {"by": actor, "at": now(),
                                        "recovery_ref": recovery_ref,
                                        "from_status": sid_from,
                                        "closed_review": dict(rc),
                                        "remediation_receipt_id":
                                            latest.get("integration_receipt_id")}
        merged["lifecycle"] = {
            "canonical": board.canonical_for(sid_to),
            "jira_column": board.column_for(sid_to),
            "jira_status_id": sid_to,
            "jira_status_name": board.name_for(sid_to),
            "observed_at": now(),
            "source": "jira",
        }
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def reconcile_completed_execution(work_item_id, expected_revision, actor,
                                  completion_ref):
    """Move ALREADY-COMPLETE orphaned execution FORWARD to its derived review. CAS'd.

    TWO ORPHANS, TWO PATHS
      `recover_execution_to_ready` is right for work that still needs executing. It
      is wrong for work already finished: Ready is a PRE-execution queue, so sending
      completed work there would imply execution is outstanding, invite a duplicate
      implementation, create a pointless claim, risk handing finished work to a new
      executor, and distort the item's history. KAN-155 was exactly that — applied to
      production and every criterion verified, sitting in `Back-end` because nobody
      transitioned it.

    COMPLETION EVIDENCE IS NOT VALIDATION EVIDENCE
      So this moves the item to its review route and NEVER to Done. That the executor
      verified its own acceptance criteria during execution is not a validation
      verdict; execution verification and canonical review are different authorities,
      and the item still has to pass its route.

    `executor_evidence` ALONE IS NOT PROOF OF COMPLETION
      It proves who executed something, not that the ticket finished — every stranded
      item in this family carries it, including the ones that were merely stalled. So
      an explicit `completion_ref` is required, naming the factual record (an applied
      migration, a verification comment, a commit). Completion is asserted by an
      authority and evidenced, never inferred from state shape.

    THE ROUTE IS DERIVED, NOT PASSED
      There is no route argument. The target comes from `policy.validation_route`
      over the item's own characteristics and must agree with the stored route, so a
      caller cannot reach an easier review by asking for one. An item whose profile
      was never completed is refused rather than guessed at.

    Jira is not touched here, no ownership is created, no review owner is chosen and
    no verdict is recorded. It authorises the forward move and names the target; the
    transition, the observation and `open_review_context` follow separately.
    """
    import board, policy                                # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not completion_ref:
        raise StateError("completion_ref is required — executor evidence proves who "
                         "executed, not that the work FINISHED, so completion must be "
                         "evidenced explicitly and never inferred")
    if actor not in RECOVERY_AUTHORITIES:
        raise StateError("unauthorised-recovery-actor: %r may not reconcile completed "
                         "execution. Deciding that work is factually finished is a "
                         "Product lifecycle judgement (%s)."
                         % (actor, "/".join(RECOVERY_AUTHORITIES)))
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("record_type") != "executable":
            raise StateError("container records hold no execution to reconcile")

        lc = cur.get("lifecycle") or {}
        sid = str(lc.get("jira_status_id") or "")
        prof = dict(cur.get("execution_profile") or {})
        cap = prof.get("required_capability")
        if lc.get("canonical") != "development":
            raise StateError(
                "not-orphaned-execution: %s is %r. Forward reconciliation applies only "
                "to an item still sitting in a capability EXECUTION status."
                % (work_item_id, lc.get("canonical")))
        if not cap or sid != board.execution_status_for(cap):
            raise StateError("wrong-execution-status: %s is at %s but capability %r "
                             "executes in %s" % (work_item_id, sid or "none", cap,
                                                 board.execution_status_for(cap)))
        if cur.get("ownership") is not None:
            raise StateError("already-owned: %s is owned by %s — reconciliation is for "
                             "ORPHANED completed work"
                             % (work_item_id, (cur["ownership"] or {}).get("seat_id")))
        if cur.get("review_context") is not None:
            raise StateError("review-in-progress: %s already carries a review context"
                             % work_item_id)

        ch = prof.get("characteristics")
        if ch is None:
            raise StateError("incomplete-profile: %s has no characteristics, so no "
                             "review route can be derived. Complete the profile through "
                             "the ordinary readiness path first." % work_item_id)
        stored = prof.get("validation_route")
        if stored not in policy.STRICTNESS:
            raise StateError("no-validation-route: %s has no derived route; forward "
                             "reconciliation never guesses one" % work_item_id)
        derived = policy.validation_route(ch)
        if policy.STRICTNESS[stored] < policy.STRICTNESS[derived]:
            raise StateError("route-incoherent: %s stores %r but its characteristics "
                             "derive %r. Reconciliation will not carry a route weaker "
                             "than the work requires." % (work_item_id, stored, derived))
        target = board.review_status_for(stored)
        if target is None:
            raise StateError("no review status for route %r" % stored)

        for iv in active_interventions():
            if iv.get("kind") == "stop" and iv.get("target") == work_item_id:
                raise StateError("task-stopped: a STOP is active on %s; lifecycle "
                                 "progression waits until it is cleared" % work_item_id)

        merged = dict(cur)
        merged["completion_reconciliation"] = {
            "by": actor, "at": now(), "completion_ref": completion_ref,
            "from_status": sid, "to_review_status": target, "route": stored}
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def resolve_review_owner(work_item_id, expected_revision, reviewer_seat_id,
                         evidence_ref):
    """Resolve the EXACT reviewer onto an already-open, unresolved PEER review. CAS'd.

    THE GAP THIS CLOSES
      A PEER review may legitimately wait with `review_owner: null` until an exact
      reviewer is established — that is doctrine, not a defect, and it is why
      `open_review_context` writes the waiting state rather than picking someone.
      But nothing could then fill the owner in: `open_review_context` reopens only
      after a recorded FAIL, and `peer_fail_transfer` needs a FAIL to exist. So a
      review that started waiting stayed waiting even once the CEO named a reviewer.

    THIS IS RESOLUTION, NOT REASSIGNMENT
      Write-once. Once an owner is recorded, a later call with a different seat is
      REFUSED. Reviewer replacement is a separate authority decision and is
      deliberately not implemented here — an operation that could silently swap a
      reviewer mid-review would let anyone choose their own.

    It does not reopen the review, does not touch the cycle, the route, the result,
    Jira, ownership or executor evidence. The intended path stays explicit:
    resolve -> record_review_result -> completion eligibility -> Jira.
    """
    import policy, validate                             # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not reviewer_seat_id:
        raise StateError("an exact reviewer is required — this operation exists so a "
                         "reviewer can be NAMED, never inferred")
    if not evidence_ref:
        raise StateError("evidence_ref is required — it records what authorised this "
                         "exact reviewer")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        prof = cur.get("execution_profile") or {}
        if prof.get("validation_route") != policy.PEER:
            raise StateError("resolve_review_owner applies to the PEER route only — "
                             "%s is on the %r route" % (work_item_id,
                                                        prof.get("validation_route")))
        rc = cur.get("review_context")
        if not isinstance(rc, dict):
            raise StateError("no-review-context: %s has no open review to resolve a "
                             "reviewer onto" % work_item_id)
        if rc.get("review_type") != policy.PEER:
            raise StateError("review-not-peer: %s carries a %r review context; "
                             "reviewer resolution does not generalise across review "
                             "types" % (work_item_id, rc.get("review_type")))
        if rc.get("review_result") != "pending":
            raise StateError("review-already-settled: %s is %r; a reviewer is resolved "
                             "before a verdict, never after"
                             % (work_item_id, rc.get("review_result")))
        if rc.get("review_owner"):
            raise StateError("review-owner-already-resolved: %s is owned for review by "
                             "%s. This operation is write-once; replacing a reviewer is "
                             "a separate authority decision."
                             % (work_item_id, rc.get("review_owner")))

        # SAME eligibility doctrine as everywhere else — not a second model.
        sbc = validate.seats_by_capability()
        cap = prof.get("required_capability")
        executors = evidenced_executors(cur)
        eligible = policy.peer_eligible(cap, sbc, exclude=executors)
        if reviewer_seat_id not in eligible:
            raise StateError(
                "invalid-peer-reviewer: %s is not an eligible PEER reviewer for %s "
                "(capability %r, executor(s) %s excluded). A PEER reviewer must hold "
                "the work's own capability, because PEER FAIL transfers execution to "
                "it. Eligible: %s"
                % (reviewer_seat_id, work_item_id, cap, executors or "none",
                   ", ".join(eligible) or "none"))

        merged = dict(cur)
        merged["review_context"] = dict(rc, review_owner=reviewer_seat_id,
                                        owner_resolved_at=now(),
                                        owner_evidence_ref=evidence_ref)
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def record_review_result(work_item_id, expected_revision, reviewer, result,
                         evidence_ref):
    """Record the validation VERDICT. CAS'd.

    Only the exact recorded `review_owner` may record it. That is the whole point of
    deriving the owner rather than accepting one: if any actor could write `pass`
    here, the route would be decorative. A conversation, a status file and a Jira
    status are all incapable of reaching this function, which is why none of them can
    make a task complete.

    PASS records the verdict and nothing else. It does not transition Jira, does not
    clear ownership and does not set the lifecycle to done — completion is DERIVED
    from this state by `queue.completion_reasons`, and the Jira move is the
    Orchestrator's separate act.

    FAIL is recorded truthfully as `fail`. It does NOT invoke the PEER transfer, does
    not invent a new owner, and does not restore ownership: SELF and QA doctrine
    returns the item to its own execution status with the same owner and the cycle
    incremented, and the cycle increments when the review is REOPENED, not when it
    fails. Recording the failure and re-entering execution are two acts.
    """
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if result not in ("pass", "fail"):
        raise StateError("review_result must be 'pass' or 'fail', got %r" % result)
    if not evidence_ref:
        raise StateError("evidence_ref is required — a verdict with no evidence is "
                         "an assertion, and the review exists to test assertions")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        rc = cur.get("review_context")
        if not isinstance(rc, dict):
            raise StateError("no-review-context: %s has no open review context. Jira "
                             "showing a review status does not create one."
                             % work_item_id)
        if rc.get("review_result") != "pending":
            raise StateError("review-already-settled: %s is already %r; reopen the "
                             "review to record another verdict"
                             % (work_item_id, rc.get("review_result")))
        owner = rc.get("review_owner")
        if owner is None:
            raise StateError("review-owner-unresolved: %s is waiting for an exact "
                             "reviewer; no verdict may be recorded until one is "
                             "resolved" % work_item_id)
        if reviewer != owner:
            raise StateError("not-review-owner: %s is owned for review by %s, not %s"
                             % (work_item_id, owner, reviewer))

        merged = dict(cur)
        merged["review_context"] = dict(rc, review_result=result,
                                        decided_at=now(), evidence_ref=evidence_ref)
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)

    # AUTHORITATIVE WRITE IS COMMITTED AND THE LOCK IS RELEASED.
    #
    # The verdict is now durable. What follows is ADVISORY: it records the fact that
    # reopening a failed review would otherwise destroy. `telemetry.emit` never
    # raises, so a failure here cannot roll back, retry or invalidate the verdict —
    # there is deliberately no transaction spanning task state and event files, and
    # claiming one would misdescribe what the filesystem guarantees. A missing event
    # surfaces through `telemetry.completeness()` instead of corrupting the workflow.
    try:
        import telemetry                                 # noqa: E402
        telemetry.emit_review_decided(merged)
    except Exception:                                    # noqa: BLE001 - deliberate
        pass
    return merged


def self_fail_reentry(work_item_id, expected_revision, seat_id, reentry_ref):
    """SELF FAIL: execution responsibility returns to the SAME exact reviewer. CAS'd.

    THREE FAIL SEMANTICS, DELIBERATELY NOT ONE HANDLER
      PEER FAIL  transfers execution to the REVIEWER, who is a different seat and
                 whose taking over is the whole point (`peer_fail_transfer`).
      QA FAIL    returns the item to the current executor; `qa` never executes.
      SELF FAIL  returns it to the exact seat that is BOTH executor and reviewer.

    Generalising them would cost each one its own invariant, so this is its own
    operation and it asserts what only it can assert: the returning owner is
    `review_context.review_owner` and nothing else may be substituted for it.

    NOT A CLAIM, AND NOT QUEUE COMPETITION
      Ownership returns to an executor the work already established through SELF
      evidence, so no seat competes for it, no capability queue is consulted and
      claimability is not evaluated. It is also NOT gated on dispatchability: whether
      the session can currently wake that seat is unknowable here, and persistent
      responsibility returning to a seat that cannot be woken is work waiting
      truthfully. The alternative — substituting a reachable seat — is exactly the
      fabricated selection the SELF route exists to prevent.

    THE FAILURE STAYS ON THE RECORD
      `review_context` is left exactly as it is, still reading fail at cycle N. The
      next cycle is created later by `open_review_context`, which increments to N+1
      when the fixed work is released and re-enters review. Erasing the failure here
      to make room for the retry would make a failed review indistinguishable from
      one that never happened.

    JIRA IS NOT TOUCHED. This decides state; returning the issue to its capability's
    execution status is the Orchestrator's separate act, and the status itself comes
    from `transition_target(capability=...)` — never hard-coded per capability here.
    """
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not reentry_ref:
        raise StateError("reentry_ref is required — re-entry is an ownership event "
                         "and every ownership event names its authorising reason")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        rc = cur.get("review_context")
        if not isinstance(rc, dict):
            raise StateError("no-review-context: %s has no review to have failed"
                             % work_item_id)
        if rc.get("review_type") != "self":
            raise StateError("self_fail_reentry applies to the SELF route only — "
                             "%s is on the %r route, whose failure path is different"
                             % (work_item_id, rc.get("review_type")))
        if rc.get("review_result") != "fail":
            raise StateError("review-not-failed: %s is %r; re-entry follows a recorded "
                             "FAIL, and is not a way to reopen a passing or pending "
                             "review" % (work_item_id, rc.get("review_result")))
        owner = rc.get("review_owner")
        if not owner:
            raise StateError("review-owner-unresolved: %s has no recorded SELF owner "
                             "to return execution to" % work_item_id)
        if seat_id != owner:
            raise StateError("not-review-owner: SELF FAIL on %s returns execution to "
                             "%s, the exact evidenced executor — not to %s. No other "
                             "seat may take it." % (work_item_id, owner, seat_id))
        if cur.get("ownership") is not None:
            raise StateError("already-owned: %s is owned by %s; re-entry establishes "
                             "ownership and never overwrites one"
                             % (work_item_id, (cur["ownership"] or {}).get("seat_id")))
        # STOP is task-scoped safety and blocks establishing ownership, exactly as it
        # blocks a claim. HOLD and FREEZE deliberately do NOT apply: they gate NEW
        # claims from a queue, and this is the return of responsibility the item
        # already carries.
        for iv in active_interventions():
            if iv.get("kind") == "stop" and iv.get("target") == work_item_id:
                raise StateError("task-stopped: a STOP is active on %s; execution may "
                                 "not resume until it is cleared" % work_item_id)

        merged = dict(cur)
        merged["ownership"] = {"seat_id": owner, "claim_ref": reentry_ref,
                               "claimed_at": now()}
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def peer_fail_transfer(work_item_id, expected_revision, reviewer, evidence_ref,
                       expected_cycle=None):
    """PEER FAIL: the reviewer becomes the executor and self-reviews its own fix.

    Every field moves in ONE CAS'd write, because a half-applied transfer is exactly
    the state that would let someone reach an easier route: evidence replaced but
    review_type still peer, or review_type flipped with ownership left behind.

    OWNERSHIP MOVES HERE, AND THAT IS THE WHOLE POINT
    Until 2026-09-14 this wrote every field of the transfer EXCEPT ownership, which
    left the doctrine unreachable: the reviewer became the evidenced executor on a
    SELF route with `ownership` null, on an item sitting in Development that
    `claim` refuses as `not-ready`. Nothing could then continue the remediation and
    a human had to intervene — the exact "ownership left behind" state the paragraph
    above names as the thing to avoid. This is a TRANSFER of execution authority the
    PEER failure already authorised, not a fresh claim, so it deliberately does not
    go through queue claimability: the work is not being handed to whoever is free,
    it is being handed to the one seat the review context already records.

    executor_evidence is REPLACED, not appended. A list with two entries means
    CONFLICTING evidence and routing must refuse; here the workflow has explicitly
    transferred responsibility, so the original developer is no longer current
    evidence. Its ownership survives in Jira history and in previous_owner.

    The work returns to the SAME Development column: the reviewer shares the task's
    capability by construction, so required_capability does not change and neither
    does the column.

    REPLAY IS REFUSED BY CONSTRUCTION. A completed transfer leaves `review_type` on
    `self`, so a second call fails the PEER-route check rather than advancing the
    cycle twice or re-taking ownership from whoever holds it now.
    """
    import validate as _validate                        # noqa: E402
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if not evidence_ref:
        raise StateError("evidence_ref is required — a transfer of execution "
                         "authority names the failure that caused it")
    # Ownership is written here, so the same lock ordering `claim` uses applies:
    # the execution domain first, then the record. Without it the seat-exclusivity
    # check below could race a concurrent claim elsewhere.
    with _Lock("execution-domain"):
      with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        rc = dict(cur.get("review_context") or {})
        if rc.get("review_type") != "peer":
            raise StateError("peer_fail_transfer applies to the PEER route only")
        if rc.get("review_owner") != reviewer:
            raise StateError("only the recorded review owner may fail and take over")
        # A transfer follows a RECORDED failure. Without this a reviewer could take
        # the work over without ever having failed it.
        if rc.get("review_result") != "fail":
            raise StateError("review-not-failed: %s is %r; the transfer follows a "
                             "recorded PEER FAIL and is not a way to take over a "
                             "pending or passing review"
                             % (work_item_id, rc.get("review_result")))
        cycle = int(rc.get("review_cycle") or 1)
        if expected_cycle is not None and int(expected_cycle) != cycle:
            raise StateError("stale-review-cycle: %s is on cycle %d, caller expected %s"
                             % (work_item_id, cycle, expected_cycle))
        capability = (cur.get("execution_profile") or {}).get("required_capability")
        if reviewer not in _validate.seats_by_capability().get(capability, ()):
            # PEER FAIL hands over EXECUTION, so the reviewer must be able to execute
            # this capability. This is re-checked here and not merely trusted from
            # the review context, because that context may predate a roster change.
            raise StateError("wrong-capability: %s is not a declared %s seat and may "
                             "not take over execution of %s"
                             % (reviewer, capability, work_item_id))
        held = [t for t in read_all("task")
                if t.get("work_item_id") != work_item_id
                and (t.get("ownership") or {}).get("seat_id") == reviewer]
        if held:
            raise StateError("seat-already-owns: %s already owns %s and cannot also "
                             "take over %s" % (reviewer, held[0]["work_item_id"],
                                               work_item_id))
        prev = [e.get("seat_id") for e in (cur.get("executor_evidence") or [])]
        merged = dict(cur)
        merged["ownership"] = {"seat_id": reviewer, "claimed_at": now(),
                               "claim_ref": evidence_ref}
        merged["executor_evidence"] = [{"seat_id": reviewer,
                                        "evidence_ref": evidence_ref,
                                        "evidenced_at": now()}]
        merged["review_context"] = {
            "review_type": "self",
            "review_owner": reviewer,
            "review_result": "pending",
            "review_cycle": cycle + 1,
            "started_at": now(),
            "previous_owner": prev[0] if len(prev) == 1 else None,
        }
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        # Nothing has been written yet: every refusal above leaves the record
        # byte-identical, and this single atomic replace is the only mutation.
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


# ---------------------------------------------------------------- interventions
#
# Independent records, not a field on a task. A task-level object cannot represent a
# capability-scoped HOLD or a system-scoped FREEZE — there is no single task to hang
# them on. Claimability queries these records instead.

def create_intervention(kind, target, created_by, reason_ref):
    """STOP / HOLD / FREEZE. Refuses a duplicate ACTIVE one.

    A second active intervention with the same (kind, scope, target) would make
    clearing ambiguous — RESUME would not know which one it cleared.
    """
    import validate                                     # noqa: E402
    scope = validate.KIND_SCOPE.get(kind)
    if scope is None:
        raise StateError("unknown intervention kind %r — stop/hold/freeze only" % kind)
    if kind == "freeze":
        target = None
    with _Lock("interventions"):
        for iv in read_all("intervention"):
            if (not iv.get("cleared_at") and iv.get("kind") == kind
                    and iv.get("target") == target):
                raise StateError("an active %s already exists on target %r (%s)"
                                 % (kind, target, iv["intervention_id"]))
        rid = new_id("intervention")
        rec = {"intervention_id": rid, "kind": kind, "scope": scope, "target": target,
               "created_by": created_by, "reason_ref": reason_ref,
               "cleared_by": None, "cleared_at": None,
               "schema_version": SCHEMA_VERSION, "revision": 1,
               "created_at": now(), "updated_at": now()}
        _validate_one("intervention", rec)
        _atomic_write(path_for("intervention", rid), rec)
        return rec


def clear_intervention(intervention_id, expected_revision, cleared_by):
    """RESUME. The clearing OPERATION — never a fourth stored kind, and never a
    delete: the record stays as evidence that the condition existed."""
    with record_lock("intervention", intervention_id):
        cur = read("intervention", intervention_id)
        if cur is None:
            raise StateError("intervention %s does not exist" % intervention_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: intervention %s is at revision %d, "
                             "caller expected %d"
                             % (intervention_id, cur["revision"], expected_revision))
        if cur.get("cleared_at"):
            raise StateError("intervention %s is already cleared" % intervention_id)
        merged = dict(cur)
        merged["cleared_by"] = cleared_by
        merged["cleared_at"] = now()
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("intervention", merged)
        _atomic_write(path_for("intervention", intervention_id), merged)
        return merged


def active_interventions():
    return [i for i in read_all("intervention") if not i.get("cleared_at")]


def intervention_blocks_claim(work_item_id, capability, interventions=None):
    """Which active intervention, if any, forbids a NEW claim. Returns a reason code.

    HOLD deliberately does not stop a current owner: it stops new claims on that
    capability. FREEZE is the same rule system-wide. Neither reassigns ownership.
    """
    for iv in (active_interventions() if interventions is None else interventions):
        k = iv.get("kind")
        if k == "freeze":
            return "system-frozen"
        if k == "hold" and iv.get("target") == capability:
            return "capability-held"
        if k == "stop" and iv.get("target") == work_item_id:
            return "task-stopped"
    return None


# ---------------------------------------------------------------- coverage
#
# ZERO IS NOT UNKNOWN.
#
# A work item with no blocker events might have had no blockers, or might never have
# been looked at. Those are different claims and the read side must never merge them,
# so observation itself is recorded: a coverage record says "this item's blocker
# truth WAS reconciled at this time". Absence of the record means unknown.
#
# This is deliberately NOT a fourth event type. It is a small mutable marker, not a
# fact about the work, and it carries no history.

COVERAGE_SYSTEM = "system"


def mark_coverage(coverage_id, **fields):
    """Upsert a coverage marker. Advisory, like everything else in Wave 8."""
    with _Lock("coverage"):
        cur = read("coverage", coverage_id)
        if cur is None:
            rec = dict({"coverage_id": coverage_id, "schema_version": SCHEMA_VERSION,
                        "revision": 1, "created_at": now(), "updated_at": now()},
                       **fields)
            _validate_one("coverage", rec)
            _atomic_write(path_for("coverage", coverage_id), rec)
            return rec
        merged = dict(cur, **fields)
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("coverage", merged)
        _atomic_write(path_for("coverage", coverage_id), merged)
        return merged


def read_coverage(coverage_id=None):
    if coverage_id is not None:
        return read("coverage", coverage_id)
    return read_all("coverage")


# ---------------------------------------------------------------- domain events
#
# ADVISORY. A DOMAIN EVENT IS NEVER WORKFLOW AUTHORITY.
#
# Nothing in claimability, ownership, validation or lifecycle reads these records.
# Deleting the whole `events` directory would change no decision the system makes —
# it would only make the read side honestly poorer. That is the test of advisory.
#
# THREE TYPES, NOT THIRTY
# Most workflow facts are already durable: executor_evidence appends, policies and
# interventions retain their cleared records, dependencies are records, and Jira's
# changelog reconstructs lifecycle. Emitting events for those would create a second
# copy of an authority that already exists, and a second copy drifts. So events are
# written ONLY where a fact is otherwise destroyed or never stored:
#
#   review_decided        review_context is CURRENT state — reopening a failed
#                         review overwrites the previous cycle's result and its
#                         evidence_ref, so WHY a review failed is lost today.
#   blocker_observed      unclaimable_reasons is derived per call and kept nowhere,
#                         so nothing records that an item WAS blocked, or for how long.
#   acceleration_outcome  a plan and its terminal condition are derived and discarded;
#                         the policy record says a run happened, never what it did.
#
# IMMUTABLE. There is no update operation for an event, only append.

EVENT_TYPES = ("review_decided", "blocker_observed", "acceleration_outcome")
EVENT_SOURCE = "wave8-event"


def _event_identity(rec):
    """The natural key that makes an event factually unique.

    Not a uuid and not a timestamp: a retry must not become a second fact. A review
    decision is identified by its cycle, an acceleration outcome by its activation,
    a blocker transition by the edge it records.
    """
    t = rec.get("event_type")
    if t == "review_decided":
        return (t, rec.get("work_item_id"), rec.get("review_type"),
                rec.get("review_cycle"))
    if t == "acceleration_outcome":
        # ONE activation, ONE terminal outcome. Deliberately NOT keyed on
        # observed_at — a retry gets a new timestamp and would forge a second run.
        return (t, rec.get("policy_id"))
    if t == "blocker_observed":
        return (t, rec.get("work_item_id"), rec.get("reason_code"),
                rec.get("transition"), rec.get("occurrence"))
    return (t, rec.get("event_id"))


EVIDENCE_CLASSIFICATIONS = ("execution", "assessment")
# Reclassifying evidence is a governance act, not an execution one. A seat able to
# reclassify its own entry could erase the record of what it did, which is the whole
# thing evidence exists to prevent. `orchestrator` is included because verifying
# ownership and lifecycle coherence is its stated duty; no `worker:` seat is.
EVIDENCE_AUTHORITIES = ("ceo", "orchestrator")


def classify_executor_evidence(work_item_id, expected_revision, seat_id,
                               classification, authority, reason_ref,
                               evidenced_at=None):
    """Mark a stored evidence entry as ASSESSMENT rather than EXECUTION. CAS'd.

    THE DEFECT THIS CLOSES. `CLAUDE.md` settles that "assessing is not claiming" —
    Preflight sizing, surface assessment, planning and capability evaluation are
    pre-execution factual acts that establish no executor identity. Nothing enforced
    it. A seat that sized an item at Preflight and wrote a status line got that line
    recorded as `executor_evidence`, indistinguishable from having done the work.

    It surfaced twice on real items on 2026-09-09, in opposite directions:
      * KAN-136 — a sizing entry plus a real execution entry made TWO seats appear
        evidenced, so `open_review_context` refused to derive a SELF owner and a
        completed item could not be reviewed at all.
      * KAN-138 — a sizing entry made `backend-5` look like an executor, excluding it
        from the PEER reviewer pool for work it had never touched.

    WHAT IT DOES NOT DO. It does not delete, edit or overwrite the entry: `seat_id`,
    `evidence_ref` and `evidenced_at` are left exactly as written, so the historical
    record of who assessed what stays auditable. It adds a classification, the actor
    and the reason. It touches no task lifecycle, no ownership, no review verdict, no
    Jira field and no Product file — a reconciliation that could reach any of those
    would be a way to rewrite a review by relabelling its evidence.

    It is also not a general evidence editor. The only reclassification is
    execution -> assessment; there is deliberately no way to promote an assessment
    INTO execution evidence, because that would let a sizing report become a claim.
    """
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if classification not in EVIDENCE_CLASSIFICATIONS:
        raise StateError("unknown classification %r — expected one of %s"
                         % (classification, "/".join(EVIDENCE_CLASSIFICATIONS)))
    if classification == "execution":
        raise StateError("promote-refused: evidence may be reclassified as assessment, "
                         "never INTO execution. An assessment that could become "
                         "execution evidence would be a sizing report turned into a "
                         "claim, which is the defect this operation exists to close")
    if authority not in EVIDENCE_AUTHORITIES:
        raise StateError("not-an-evidence-authority: %r may not reclassify executor "
                         "evidence; only %s may. A seat able to reclassify its own "
                         "entry could erase the record of what it did"
                         % (authority, "/".join(EVIDENCE_AUTHORITIES)))
    if not reason_ref:
        raise StateError("reason_ref is required — evidence reclassified without a "
                         "stated reason is indistinguishable from evidence quietly "
                         "disowned")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        ev = list(cur.get("executor_evidence") or [])
        hits = [e for e in ev if isinstance(e, dict) and e.get("seat_id") == seat_id
                and (evidenced_at is None or e.get("evidenced_at") == evidenced_at)]
        if not hits:
            raise StateError("no-such-evidence: %s has no executor_evidence entry for "
                             "%s%s" % (work_item_id, seat_id,
                                       " at %s" % evidenced_at if evidenced_at else ""))
        if len(hits) > 1:
            raise StateError("ambiguous-evidence: %s has %d entries for %s; pass "
                             "evidenced_at to name exactly one. Reclassifying the "
                             "wrong entry is not recoverable by another reclassify"
                             % (work_item_id, len(hits), seat_id))
        target = hits[0]
        if target.get("classification", "execution") != "execution":
            return cur                                   # already reconciled; idempotent
        merged = dict(cur)
        merged["executor_evidence"] = [
            dict(e, classification=classification, classified_by=authority,
                 classified_at=now(), classification_reason_ref=reason_ref)
            if e is target else e for e in ev]
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


SUPERSESSION_AUTHORITIES = ("po", "ceo")


def supersede_task(work_item_id, expected_revision, replaced_by, authority,
                   reason_ref, jira_status_id=None):
    """Record that a work item was REPLACED, not completed. CAS'd.

    THE GAP THIS CLOSES. A task that Product definition replaces has no
    representable end state. `record_review_result` needs a verdict nobody reached;
    `reconcile_completed_execution` describes work that finished; and leaving the
    record alone leaves an open review context pointing at a reviewer who will never
    review it, permanently disagreeing with Jira. KAN-141 sat in exactly that shape:
    To Do in Jira, `lifecycle: review` with an open QA context in Persistent State,
    after `po` correctly re-scoped it into KAN-162 under a CEO ruling.

    WHAT IT REFUSES TO PRETEND. It never writes a verdict, never sets `done`, and
    never touches the replacement. The open review context is CLEARED rather than
    resolved, because no review happened — a `pass` here would be the fabrication
    the whole validation model exists to prevent, and a `fail` would libel work that
    was never judged. The replacement link and the reason are recorded so the
    history reads truthfully in both directions.

    Authority is Product-definition authority (`po`) or the CEO. An executor cannot
    supersede its own work out of review.
    """
    if expected_revision is None:
        raise StateError("expected_revision is required; there is no force update")
    if authority not in SUPERSESSION_AUTHORITIES:
        raise StateError("not-a-supersession-authority: %r may not replace a work "
                         "item; only %s may — replacing work is Product definition, "
                         "not execution"
                         % (authority, "/".join(SUPERSESSION_AUTHORITIES)))
    if not replaced_by:
        raise StateError("replaced_by is required — an item superseded by nothing is "
                         "an item cancelled, and that is a different act")
    if replaced_by == work_item_id:
        raise StateError("an item cannot supersede itself")
    if not reason_ref:
        raise StateError("reason_ref is required — a replacement with no recorded "
                         "reason is indistinguishable from quietly dropping the work")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if (cur.get("lifecycle") or {}).get("canonical") == "done":
            raise StateError("already-done: %s is complete; completed work is not "
                             "superseded, it is superseded work that was never "
                             "completed" % work_item_id)
        rc = cur.get("review_context") or {}
        if rc.get("review_result") == "pass":
            raise StateError("already-validated: %s carries a PASS verdict; "
                             "superseding it would discard a real review"
                             % work_item_id)
        if read("task", replaced_by) is None:
            raise StateError("no-such-replacement: %s does not exist in Persistent "
                             "State — a replacement link must point at a real record"
                             % replaced_by)
        merged = dict(cur)
        # The review is CLEARED, not decided. Nothing here asserts an outcome.
        merged["review_context"] = None
        merged["ownership"] = None
        merged["superseded"] = {"replaced_by": replaced_by, "by": authority,
                                "reason_ref": reason_ref, "at": now(),
                                "review_state_at_supersession": rc.get("review_result")
                                or "none"}
        if jira_status_id:
            import board                                  # noqa: E402
            merged["lifecycle"] = {
                "canonical": board.canonical_for(jira_status_id),
                "jira_column": board.column_for(jira_status_id),
                "jira_status_id": jira_status_id,
                "jira_status_name": board.name_for(jira_status_id),
                "observed_at": now(), "source": "jira"}
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def cancel_task(work_item_id, expected_revision, authority, reason_ref):
    """Record that a work item was CANCELLED — withdrawn with no replacement. CAS'd.

    The act `supersede_task` refuses by design. A Jira issue the CEO deleted
    (KAN-292, KAN-346, 2026-09-24) left records reading `ready` with no issue behind
    them: never claimable (`unverified-jira`), yet still counted as pending work and
    shown as Ready anywhere that does not re-verify Jira.

    WHAT IT KEEPS. Everything: revisions, lifecycle as last observed, executor
    evidence, execution history and landed-commit references stay exactly as they
    were. Cancellation is a marker added to the record, never an erasure of it.

    WHAT IT REFUSES. Completed work, a PASS verdict, owned work (the owner releases
    first) and work under an open execution lease — cancelling any of those would
    discard or strand something real. Any open review context is CLEARED, not decided.
    """
    if authority not in SUPERSESSION_AUTHORITIES:
        raise StateError("not-a-cancellation-authority: %r may not cancel a work item; "
                         "only %s may — withdrawing work is Product definition"
                         % (authority, "/".join(SUPERSESSION_AUTHORITIES)))
    if not reason_ref:
        raise StateError("reason_ref is required — a cancellation with no recorded "
                         "reason is indistinguishable from quietly dropping the work")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("cancelled"):
            raise StateError("already-cancelled: %s" % work_item_id)
        if (cur.get("lifecycle") or {}).get("canonical") == "done":
            raise StateError("already-done: %s is complete; completed work is not "
                             "cancelled" % work_item_id)
        rc = cur.get("review_context") or {}
        if rc.get("review_result") == "pass":
            raise StateError("already-validated: %s carries a PASS verdict; "
                             "cancelling it would discard a real review" % work_item_id)
        if (cur.get("ownership") or {}).get("seat_id"):
            raise StateError("owned: %s is owned by %s; the owner releases first"
                             % (work_item_id, cur["ownership"]["seat_id"]))
        open_leases = [lease for lease in read_all("execution_lease")
                       if lease.get("work_item_id") == work_item_id
                       and not lease.get("closed_at")]
        if open_leases:
            raise StateError("active-lease: %s has an open execution lease" % work_item_id)
        merged = dict(cur)
        merged["review_context"] = None
        merged["cancelled"] = {"by": authority, "reason_ref": reason_ref, "at": now(),
                               "lifecycle_at_cancellation":
                                   (cur.get("lifecycle") or {}).get("canonical"),
                               "review_state_at_cancellation":
                                   rc.get("review_result") or "none"}
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def read_corrections(corrects_event_id=None):
    """Advisory correction records, oldest first. Read-only."""
    out = [c for c in read_all("correction")
           if (corrects_event_id is None
               or c.get("corrects_event_id") == corrects_event_id)]
    return sorted(out, key=lambda c: (c.get("corrected_at") or "",
                                      c.get("correction_id") or ""))


def invalidated_event_ids():
    """Event ids the read side must stop treating as factual evidence.

    A set, not a filter over events, because every advisory reader needs the same
    answer and none of them should have to know how a correction is shaped.
    """
    return {c.get("corrects_event_id") for c in read_all("correction")
            if c.get("correction_kind") == "invalidate"}


def correct_event(corrects_event_id, corrected_by, reason_ref, evidence_ref=None,
                  correction_kind="invalidate"):
    """Stop an advisory event counting as evidence. It is NOT edited or deleted.

    THE SHAPE OF THE PROBLEM. Wave 8 events are append-only historical facts, and
    `append_event` dedups on a natural key — so a false event cannot be repaired by
    re-emitting the true one: the re-emit returns the existing record. There was
    previously no way at all to stop a wrong advisory fact from being read as right,
    and the only alternatives were hand-editing runtime or leaving it standing.

    WHY CORRECTION RATHER THAN DELETION. Deleting the record would destroy the
    audit: nobody could later see that the fact was ever asserted, by whom, or that
    it was withdrawn. The original append stays byte-identical; this record
    references it and the read side excludes it. `telemetry.completeness()` then
    correctly reports the underlying history as MISSING rather than satisfied,
    because an invalidated event is not a replacement for the event that never
    happened.

    WHAT IT DELIBERATELY CANNOT DO. It does not touch the task, ownership, the
    review verdict, the lifecycle, Jira, or any authoritative state — an advisory
    correction that could reach authority would be a way to rewrite a review by
    complaining about its telemetry. It cannot amend an event's content, and there
    is no general event-edit API. Authority is restricted to the CEO by
    `validate.CORRECTION_AUTHORITIES`: an executor able to invalidate its own
    telemetry could edit the record of its own reviews.
    """
    if not corrects_event_id:
        raise StateError("corrects_event_id is required — a correction with no "
                         "target is an assertion about nothing")
    if not reason_ref:
        raise StateError("reason_ref is required — a correction with no stated "
                         "reason is indistinguishable from tidying away a fact")
    from validate import CORRECTION_AUTHORITIES        # noqa: E402
    if corrected_by not in CORRECTION_AUTHORITIES:
        raise StateError("not-a-correction-authority: %r may not correct advisory "
                         "history; only %s may"
                         % (corrected_by, "/".join(sorted(CORRECTION_AUTHORITIES))))
    with _Lock("events"):
        target = read("event", corrects_event_id)
        if target is None:
            raise StateError("no-such-event: %s does not exist — a correction names "
                             "a real record or it is fiction" % corrects_event_id)
        for existing in read_all("correction"):
            if (existing.get("corrects_event_id") == corrects_event_id
                    and existing.get("correction_kind") == correction_kind):
                # Write-once per (event, kind). Re-correcting is not a second fact.
                return existing
        rid = new_id("correction")
        rec = {"correction_id": rid, "corrects_event_id": corrects_event_id,
               "correction_kind": correction_kind, "corrected_by": corrected_by,
               "reason_ref": reason_ref, "corrected_at": now(),
               "created_at": now(), "updated_at": now(), "revision": 1,
               "schema_version": SCHEMA_VERSION}
        if evidence_ref:
            rec["evidence_ref"] = evidence_ref
        _validate_one("correction", rec)
        _atomic_write(path_for("correction", rid), rec)
        return rec


def read_events(event_type=None, work_item_id=None, include_invalidated=True):
    """All recorded events, oldest first. Read-only; nothing consumes them for policy.

    `include_invalidated` defaults TRUE because this is the audit view: a corrected
    event still happened and must remain visible. Advisory readers that reason about
    facts pass False, or use `telemetry.active_events()`.
    """
    dead = set() if include_invalidated else invalidated_event_ids()
    out = [e for e in read_all("event")
           if (event_type is None or e.get("event_type") == event_type)
           and (work_item_id is None or e.get("work_item_id") == work_item_id)
           and e.get("event_id") not in dead]
    # Ordered by SEQ, not by timestamp. `observed_at` is second-resolution, so two
    # events in the same second would otherwise tie and fall back to a random uuid —
    # which silently loses append order, and the blocker edge model reads "latest"
    # to decide whether a blocker is still open. A monotonic seq makes order a fact.
    return sorted(out, key=lambda e: (e.get("seq") or 0, e.get("event_id") or ""))


def append_event(record):
    """Append one immutable domain event. Returns the record, or the EXISTING one.

    Idempotent by natural identity, so re-observing a fact is not a second fact —
    which is what stops polling from manufacturing repetition that learning would
    then read as a pattern.

    Raises on a malformed event. Callers that are advisory must not let that reach an
    authoritative operation; see `telemetry.emit`.
    """
    rec = dict(record)
    if rec.get("event_type") not in EVENT_TYPES:
        raise StateError("unknown event_type %r — the Wave 8 set is fixed at %s"
                         % (rec.get("event_type"), "/".join(EVENT_TYPES)))
    rec.setdefault("observed_at", now())
    rec.setdefault("source", EVENT_SOURCE)
    rec.setdefault("schema_version", SCHEMA_VERSION)
    ident = _event_identity(rec)
    with _Lock("events"):
        for existing in read_all("event"):
            if _event_identity(existing) == ident:
                return existing
        rid = new_id("event")
        rec["event_id"] = rid
        rec["seq"] = 1 + max([e.get("seq") or 0 for e in read_all("event")] or [0])
        rec.setdefault("created_at", now())
        rec.setdefault("updated_at", rec["created_at"])
        rec.setdefault("revision", 1)
        _validate_one("event", rec)
        _atomic_write(path_for("event", rid), rec)
        return rec


# ---------------------------------------------------------------- execution policy
#
# ACCELERATE IS NOT AN INTERVENTION, AND THIS IS NOT A STYLISTIC CHOICE.
#
# CONTRACT.md §3 permits an intervention "only for a concrete detected safety
# condition" and "never for priority, ordinary scheduling, routine approval or
# performance management". ACCELERATE *is* ordinary scheduling, so putting it in the
# intervention namespace would place a scheduling record inside one the contract
# defines as safety-only. It would also break three live invariants at once:
# KIND_SCOPE binds each kind to exactly one scope (ACCELERATE needs three),
# intervention_blocks_claim returns a BLOCKING reason for every kind, and every
# caller of active_interventions() reads that list as "things that restrict".
#
# So policies live in their own record kind, their own directory and their own
# reader. Nothing here is consulted by claimability, ownership or Jira lifecycle:
# a policy changes only how aggressively the Orchestrator fills SAFE capacity, and
# removing every policy record would leave behaviour identical to today's.

POLICY_KINDS = ("accelerate",)
POLICY_SCOPES = ("system", "product", "capability")


def set_execution_policy(policy_kind, scope, target, activated_by, reason_ref):
    """Activate an execution policy. Atomic under the policies lock.

    Refuses a duplicate ACTIVE policy on the same (kind, scope, target) for the same
    reason `create_intervention` does: a second one would make clearing ambiguous.
    """
    import validate                                     # noqa: E402
    if policy_kind not in POLICY_KINDS:
        raise StateError("unknown execution policy kind %r — the set is %s"
                         % (policy_kind, "/".join(POLICY_KINDS)))
    if scope not in POLICY_SCOPES:
        raise StateError("unknown policy scope %r — system/product/capability only. "
                         "There is deliberately no TASK scope: 'maximum parallelism' "
                         "on one item is meaningless, and a task-scoped accelerator "
                         "would be priority by another name." % scope)
    if scope == "system":
        target = None
    elif not target:
        raise StateError("a %s-scoped policy needs a target" % scope)
    if not reason_ref:
        raise StateError("reason_ref is required — a policy is an auditable act")
    with _Lock("policies"):
        for pol in active_execution_policies():
            if (pol.get("policy_kind") == policy_kind and pol.get("scope") == scope
                    and pol.get("target") == target):
                raise StateError("an active %s policy already exists on %s target %r "
                                 "(%s)" % (policy_kind, scope, target,
                                           pol["policy_id"]))
        rid = new_id("policy")
        rec = {"policy_id": rid, "policy_kind": policy_kind, "scope": scope,
               "target": target, "activated_by": activated_by,
               "reason_ref": reason_ref, "cleared_by": None, "cleared_at": None,
               "schema_version": SCHEMA_VERSION, "revision": 1,
               "activated_at": now(), "created_at": now(), "updated_at": now()}
        _validate_one("policy", rec)
        _atomic_write(path_for("policy", rid), rec)
        return rec


def clear_execution_policy(policy_id, expected_revision, cleared_by):
    """CLEAR ACCELERATE. CAS'd, and the cleared record is KEPT as history.

    Clearing changes future scheduling pressure and NOTHING else. It does not cancel
    ownership, does not stop a current owner and does not touch a single task record —
    a policy that could revoke ownership on the way out would be an intervention, and
    it deliberately is not one.
    """
    with _Lock("policies"):
        cur = read("policy", policy_id)
        if cur is None:
            raise StateError("policy %s does not exist" % policy_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: policy %s is at revision %d, caller "
                             "expected %d" % (policy_id, cur["revision"],
                                              expected_revision))
        if cur.get("cleared_at"):
            raise StateError("policy %s is already cleared" % policy_id)
        merged = dict(cur, cleared_by=cleared_by, cleared_at=now(),
                      revision=cur["revision"] + 1, updated_at=now())
        _validate_one("policy", merged)
        _atomic_write(path_for("policy", policy_id), merged)
        return merged


def active_execution_policies(policy_kind=None):
    out = [p for p in read_all("policy") if not p.get("cleared_at")]
    if policy_kind is not None:
        out = [p for p in out if p.get("policy_kind") == policy_kind]
    return sorted(out, key=lambda p: p.get("policy_id") or "")


def accelerate_scopes_for(task, policies=None):
    """Which active ACCELERATE policies cover this task. Empty = normal mode.

    UNION, never override. A task is accelerated if ANY active policy covers it, and
    there is no negative policy to express "normal" — absence already means normal.
    One composable rule, no policy language, and nothing that can contradict itself.
    """
    pols = (active_execution_policies("accelerate") if policies is None
            else [p for p in policies
                  if p.get("policy_kind") == "accelerate" and not p.get("cleared_at")])
    cap = (task.get("execution_profile") or {}).get("required_capability")
    out = []
    for p in pols:
        sc, tgt = p.get("scope"), p.get("target")
        if (sc == "system"
                or (sc == "product" and tgt == task.get("product_id"))
                or (sc == "capability" and tgt == cap)):
            out.append(p)
    return out


def accelerated(task, policies=None):
    return bool(accelerate_scopes_for(task, policies))


# ---------------------------------------------------------------- ownership

def set_surfaces(work_item_id, expected_revision, surfaces, author, basis_ref=None):
    """Record a SURFACE ASSESSMENT: the paths this work touches, possibly none.

    This is an assessment ACT, so `None` is refused. `null` is reserved for the
    unassessed state — new work, a migrated record, or an explicitly authorised system
    repair — and letting an ordinary actor write it back would re-open exactly the
    hole this closed: work that looks assessed-empty because nobody looked.

    Passing `[]` is a real answer and is accepted: assessed, nothing to declare.

    Assessment is a pre-execution factual act, like Work Effort sizing. **Assessing is
    not claiming**, and the assessing seat does not thereby become the executor.
    """
    import policy                                       # noqa: E402
    if surfaces is None:
        raise StateError(
            "set_surfaces records an assessment and cannot write null. Pass [] for "
            "'assessed, nothing declared'; null is the unassessed state and is only "
            "set by migration or an authorised system repair.")
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        clean = sorted({policy.normalise_path(p) for p in surfaces})
        merged = dict(cur)
        merged["surfaces"] = clean
        prof = dict(merged.get("execution_profile") or {})
        if prof:
            ch = dict(prof.get("characteristics") or {})
            ch["shared_or_contended_surface"] = policy.derive_contended(clean)
            prof["characteristics"] = ch
            prov = dict(prof.get("provenance") or {})
            chprov = dict((prov.get("characteristics") or {}).get("fields") or {})
            chprov["shared_or_contended_surface"] = {"by": "system-derived", "at": now()}
            prov["characteristics"] = {"by": "system-derived", "at": now(),
                                       "fields": chprov}
            # Who assessed the paths, when, and against what — recorded on the existing
            # per-field provenance mechanism rather than in a second source of truth.
            prov["surfaces"] = {"by": author, "at": now(), "basis_ref": basis_ref}
            # Surface assessment changes a policy characteristic.  Materialise the
            # corresponding policy result atomically so a fully assessed profile
            # cannot reach planning without a validation route.
            started = (cur.get("lifecycle") or {}).get("canonical") in (
                "development", "review", "done")
            route = policy.escalate(prof.get("validation_route"),
                                    policy.validation_route(ch), started)
            prof["validation_route"] = route
            prof["completion_route"] = "DONE"
            prov["validation_route"] = {"by": "system-policy", "at": now()}
            prov["completion_route"] = {"by": "system-policy", "at": now()}
            prof["provenance"] = prov
            prof.setdefault("profile_status", "partial")
            prof["effective_fields"] = [
                f for f in ("project_id", "required_capability", "work_effort",
                            "characteristics", "validation_route", "completion_route")
                if (merged.get(f) if f == "project_id" else prof.get(f)) is not None]
            merged["execution_profile"] = prof
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def reconcile_missing_validation_routes():
    """Materialise routes for every classified legacy execution profile.

    This is a generic Persistent State maintenance repair, never a Jira update or
    task-key exception.  Profiles whose characteristics are absent remain unchanged
    so callers can distinguish unavailable classification evidence from a missing
    materialised route.
    """
    import policy                                       # noqa: E402
    repaired = []
    for row in read_all("task"):
        if row.get("record_type") != "executable":
            continue
        key = row.get("work_item_id")
        with record_lock("task", key):
            cur = read("task", key)
            prof = dict((cur or {}).get("execution_profile") or {})
            if (not prof or prof.get("characteristics") is None
                    or prof.get("validation_route") is not None):
                continue
            route = policy.validation_route_for_profile(prof)
            if route is None:
                continue
            started = (cur.get("lifecycle") or {}).get("canonical") in (
                "development", "review", "done")
            prof["validation_route"] = policy.escalate(None, route, started)
            prof["completion_route"] = "DONE"
            prov = dict(prof.get("provenance") or {})
            prov["validation_route"] = {"by": "system-policy", "at": now(),
                                         "reconciled_from": "characteristics"}
            prov["completion_route"] = {"by": "system-policy", "at": now()}
            prof["provenance"] = prov
            prof.setdefault("profile_status", "partial")
            prof["effective_fields"] = [
                f for f in ("project_id", "required_capability", "work_effort",
                            "characteristics", "validation_route", "completion_route")
                if (cur.get(f) if f == "project_id" else prof.get(f)) is not None]
            merged = dict(cur)
            merged["execution_profile"] = prof
            merged["revision"] = cur["revision"] + 1
            merged["updated_at"] = now()
            _validate_one("task", merged)
            _atomic_write(path_for("task", key), merged)
            repaired.append(key)
    return repaired


def assert_execution_permitted(work_item_id, seat_id):
    """THE CONTINUATION GATE. Raises unless this seat may be woken to continue now.

    The Orchestrator must call this before every ordinary execution wake, every
    same-seat continuation and every resumed invocation. It is separate from
    claimability on purpose: claimability governs acquiring an owner, this governs
    whether an owner may keep going.

    An active STOP on the task denies it. HOLD and FREEZE do not — they block new
    claims while current owners continue, and conflating them with STOP would turn a
    capability-wide pause into a system-wide halt.

    RELEASE IS NOT BLOCKED BY THIS GATE. A STOP must not trap ownership: the owner
    stays able to release, which is how a stopped task gets out of its owner's hands
    without anyone silently reassigning it.
    """
    import queue as q                                   # noqa: E402
    cur = read("task", work_item_id)
    if cur is None:
        raise StateError("task %s does not exist" % work_item_id)
    reasons = q.execution_reasons(cur, seat_id)
    if reasons:
        raise StateError("execution refused: " + ", ".join(reasons))
    return cur


def open_execution_lease(work_item_id, seat_id, reason_ref):
    """Atomically authorize one Product wake against the current mode revision."""
    import operations, queue as q                       # noqa: E402
    if not reason_ref:
        raise StateError("reason_ref is required")
    with _Lock("execution-domain"):
        mode = read("operating_mode", operations.CURRENT_MODE_ID)
        if current_operating_mode() != operations.PRODUCT_EXECUTION:
            raise StateError("execution refused: system-maintenance-active")
        task = read("task", work_item_id)
        if task is None:
            raise StateError("task %s does not exist" % work_item_id)
        reasons = q.execution_reasons(task, seat_id)
        if reasons:
            raise StateError("execution refused: " + ", ".join(reasons))
        rid = new_id("execution_lease")
        rec = {"execution_lease_id": rid, "work_item_id": work_item_id,
               "seat_id": seat_id, "mode_revision": (mode or {}).get("revision", 0),
               "reason_ref": reason_ref, "closed_at": None, "closed_by": None,
               "schema_version": SCHEMA_VERSION, "revision": 1,
               "created_at": now(), "updated_at": now()}
        _validate_one("execution_lease", rec)
        _atomic_write(path_for("execution_lease", rid), rec)
        return rec


def close_execution_lease(execution_lease_id, expected_revision, closed_by):
    with _Lock("execution-domain"):
        with record_lock("execution_lease", execution_lease_id):
            cur = read("execution_lease", execution_lease_id)
            if cur is None:
                raise StateError("execution lease %s does not exist" % execution_lease_id)
            if cur["revision"] != expected_revision:
                raise StateError("stale write refused: execution lease is at revision %d, "
                                 "caller expected %d" % (cur["revision"], expected_revision))
            if cur.get("closed_at"):
                raise StateError("execution lease is already closed")
            rec = dict(cur, closed_at=now(), closed_by=closed_by,
                       revision=cur["revision"] + 1, updated_at=now())
            _validate_one("execution_lease", rec)
            _atomic_write(path_for("execution_lease", execution_lease_id), rec)
            return rec


def bind_role_session(seat_id, provider, session_id, stable_home, bound_by,
                      session_name=None, expected_revision=None):
    """Create or CAS-rebind the durable session identity backing one seat.

    Identity is the session_id, never the name, PID, socket or bridge address —
    none of those survive a restart. A rebind is not a new identity: the
    previous session_id is appended to previous_session_ids and kept, exactly
    like an execution replacement keeps the lineage it replaces.
    """
    import roster                                       # noqa: E402
    if provider not in ROLE_SESSION_PROVIDERS:
        raise StateError("unknown provider %r — expected one of %s"
                         % (provider, "/".join(sorted(ROLE_SESSION_PROVIDERS))))
    if not isinstance(session_id, str) or not session_id:
        raise StateError("session_id is required")
    if not stable_home:
        raise StateError("stable_home is required")
    if not bound_by:
        raise StateError("bound_by is required")
    if seat_id not in roster.read():
        raise StateError("seat %r is not declared in the neutral registry" % seat_id)
    with record_lock("role_session", seat_id):
        cur = read("role_session", seat_id)
        if cur is None:
            if expected_revision is not None:
                raise StateError("role session for %s does not exist; expected_revision "
                                 "must be null" % seat_id)
            rec = {"seat_id": seat_id, "provider": provider, "session_id": session_id,
                   "session_name": session_name, "stable_home": stable_home,
                   "status": "active", "previous_session_ids": [], "bound_by": bound_by,
                   "schema_version": SCHEMA_VERSION, "revision": 1,
                   "created_at": now(), "updated_at": now()}
            _validate_one("role_session", rec)
            _atomic_write(path_for("role_session", seat_id), rec)
            return rec
        if expected_revision is None:
            raise StateError("expected_revision is required; there is no force update")
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: role session %s is at revision %d, "
                             "caller expected %d" % (seat_id, cur["revision"], expected_revision))
        previous = list(cur.get("previous_session_ids") or [])
        if cur.get("session_id") and cur["session_id"] != session_id:
            previous.append(cur["session_id"])
        merged = dict(cur, provider=provider, session_id=session_id,
                     session_name=session_name, stable_home=stable_home,
                     status="active", previous_session_ids=previous, bound_by=bound_by,
                     revision=cur["revision"] + 1, updated_at=now())
        _validate_one("role_session", merged)
        _atomic_write(path_for("role_session", seat_id), merged)
        return merged


def active_role_session(seat_id):
    """The seat's current ACTIVE session binding, or None.

    A dormant or never-bound seat legitimately has none; that is an ordinary
    answer, not an error.
    """
    rec = read("role_session", seat_id)
    if rec is None or rec.get("status") != "active":
        return None
    return rec


def record_session_outcome(dispatch_id, outcome, summary, recorded_by,
                           session_id=None, reference=None):
    """Settle one persistent-session dispatch. Every outcome ends the dispatch.

    Identity, not politeness, is the gate: for every outcome except
    worker_unreachable, the caller must name the exact session_id this dispatch
    was bound to, AND that session must still be the seat's current active
    binding. Anything else is refused and nothing is recorded — a stale or
    impersonating report must not close a lease it did not earn. Ownership
    (the claim) is never touched here; a follow-up is a new prepare for the
    same item, not a second outcome on this one.
    """
    if outcome not in SESSION_DISPATCH_OUTCOMES:
        raise StateError("unknown session dispatch outcome %r — expected one of %s"
                         % (outcome, "/".join(sorted(SESSION_DISPATCH_OUTCOMES))))
    if not summary:
        raise StateError("summary is required")
    if not recorded_by:
        raise StateError("recorded_by is required")
    if outcome != "worker_unreachable" and not session_id:
        raise StateError("session_id is required for outcome %r" % outcome)
    with record_lock("session_dispatch", dispatch_id):
        cur = read("session_dispatch", dispatch_id)
        if cur is None:
            raise StateError("session dispatch %s does not exist" % dispatch_id)
        if cur.get("status") != "dispatched":
            raise StateError("session dispatch %s is not open (status %r) — every "
                             "outcome is terminal for that dispatch"
                             % (dispatch_id, cur.get("status")))
        if outcome != "worker_unreachable":
            active = active_role_session(cur.get("seat_id"))
            if (session_id != cur.get("session_id") or active is None
                    or active.get("session_id") != session_id):
                raise StateError(
                    "session-identity-mismatch: dispatch %s is bound to a different "
                    "session than the one reporting this outcome" % dispatch_id)
        recovery_hint = None
        if outcome == "worker_unreachable":
            recovery_hint = ('claude --bg --resume %s "<prompt>" — no other flags; '
                             'extra flags create a copy' % cur.get("session_id"))
        merged = dict(cur, status=outcome, outcome=outcome, summary=summary,
                     reference=reference, reported_session_id=session_id,
                     outcome_at=now(), recorded_by=recorded_by,
                     recovery_hint=recovery_hint,
                     revision=cur["revision"] + 1, updated_at=now())
        # Validate and write the settled dispatch BEFORE touching the lease. If
        # either fails, nothing has happened: the dispatch is still open and its
        # lease is still open with it. The conservative failure direction is the
        # other one — a settled dispatch whose lease did not close — and that is
        # exactly what a failure AFTER this point below leaves: recoverable from
        # the lease id already on the written record, not silently lost.
        _validate_one("session_dispatch", merged)
        _atomic_write(path_for("session_dispatch", dispatch_id), merged)
        lease_id = cur.get("execution_lease_id")
        if lease_id:
            lease = read("execution_lease", lease_id)
            if lease is not None and not lease.get("closed_at"):
                close_execution_lease(lease_id, lease["revision"], recorded_by)
        return merged


def review_context_ref(work_item_id, review_context):
    """The canonical reference for one open review context."""
    review = review_context or {}
    return "review:%s:%s:%s" % (work_item_id, review.get("review_type"),
                                review.get("review_cycle") or 1)


def assert_review_authority(work_item_id, seat_id, ref):
    """A validation invocation's authority is its review context, not a claim.

    A reviewer legitimately does not own the work it reviews — that is the whole
    point of review, and `qa` never owns anything — so a validation receipt is
    authorized by the exact open review context naming this seat as its owner,
    exactly as a validation ExecutionRequest is. Everything else about the
    record is unchanged.
    """
    task = read("task", work_item_id)
    if task is None:
        raise StateError("task %s does not exist" % work_item_id)
    review = task.get("review_context")
    if not isinstance(review, dict):
        raise StateError("no-review-context: %s has no open review" % work_item_id)
    if review.get("review_owner") != seat_id:
        raise StateError("not-review-owner: %s is reviewed by %s, not %s"
                         % (work_item_id, review.get("review_owner"), seat_id))
    expected = review_context_ref(work_item_id, review)
    if ref != expected:
        raise StateError("stale-review-context: %s is on %r, caller named %r"
                         % (work_item_id, expected, ref))
    return review


def _receipt_id(invocation_id):
    """Stable natural identity without placing arbitrary invocation text in a path."""
    digest = hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()
    return "receipt-" + digest


def record_execution_receipt(invocation_id, work_item_id, seat_id,
                             execution_lease_id, normalized_result,
                             provider_selection=None, continuation_of=None,
                             approval_id=None, approval_ids=None,
                             review_context_ref=None):
    """Persist one normalized terminal result before its lease is closed.

    The operation is idempotent only for byte-identical evidence from the same
    invocation.  A second, different result is refused rather than overwriting
    the first terminal record or making a duplicate execution look legitimate.
    """
    if not isinstance(normalized_result, dict):
        raise StateError("normalized_result must be a JSON object")
    if normalized_result.get("invocation_id") != invocation_id:
        raise StateError("receipt invocation_id must match its normalized result")
    if normalized_result.get("status") not in {
            "completed", "needs_input", "execution_failed", "provider_failed"}:
        raise StateError("receipt has no normalized terminal status")
    if provider_selection is not None and not isinstance(provider_selection, dict):
        raise StateError("provider_selection must be a JSON object")
    rid = _receipt_id(invocation_id)
    if approval_ids is not None:
        if (not isinstance(approval_ids, (tuple, list)) or not approval_ids
                or any(not isinstance(item, str) or not item.startswith("approval-")
                       for item in approval_ids)):
            raise StateError("continuation receipt approval_ids must be non-empty approval ids")
        approval_ids = list(approval_ids)
    rec = {"execution_receipt_id": rid, "invocation_id": invocation_id,
           "work_item_id": work_item_id, "seat_id": seat_id,
           "execution_lease_id": execution_lease_id,
           "provider_id": normalized_result.get("provider_id"),
           "status": normalized_result["status"],
           "normalized_result": normalized_result,
           "provider_selection": provider_selection,
           "continuation_of_invocation_id": continuation_of,
           "approval_id": approval_id, "approval_ids": approval_ids,
           "review_context_ref": review_context_ref}
    if (execution_lease_id is None) == (review_context_ref is None):
        raise StateError("an execution receipt is authorized by exactly one of an "
                         "execution lease or an open review context")
    with _Lock("execution-domain"):
        if review_context_ref is not None:
            # A validation invocation holds no claim and opens no lease; its
            # authority is the review context that named this reviewer.
            assert_review_authority(work_item_id, seat_id, review_context_ref)
        else:
            lease = read("execution_lease", execution_lease_id)
            if lease is None:
                raise StateError("execution receipt needs an existing execution lease")
            if (lease.get("work_item_id"), lease.get("seat_id")) != (work_item_id, seat_id):
                raise StateError("execution receipt does not match its execution lease")
        with record_lock("execution_receipt", rid):
            existing = read("execution_receipt", rid)
            if existing is not None:
                if (existing.get("normalized_result") != normalized_result
                        or existing.get("provider_selection") != provider_selection):
                    raise StateError("conflicting terminal receipt for invocation %s"
                                     % invocation_id)
                return existing
            rec["schema_version"] = SCHEMA_VERSION
            rec["revision"] = 1
            rec["created_at"] = now()
            rec["updated_at"] = rec["created_at"]
            _validate_one("execution_receipt", rec)
            _atomic_write(path_for("execution_receipt", rid), rec)
            return rec


def _integration_id(work_item_id, product_commit, outcome):
    digest = hashlib.sha256(
        "\0".join((work_item_id, product_commit or "none", outcome)).encode("utf-8")
    ).hexdigest()[:16]
    return "integration-%s" % digest


def record_integration_receipt(work_item_id, seat_id, outcome, evidence):
    """Persist what integration did, including what it refused to do.

    Idempotent for byte-identical evidence; a second, different result for the
    same (work item, commit, outcome) is refused rather than overwriting the
    first record. A refusal is evidence too: an attribution failure or an
    integration conflict is exactly the state somebody later needs to read.
    """
    if not isinstance(evidence, dict):
        raise StateError("integration evidence must be a JSON object")
    if outcome not in INTEGRATION_OUTCOMES:
        raise StateError("unknown integration outcome %r" % outcome)
    rid = _integration_id(work_item_id, evidence.get("product_commit"), outcome)
    rec = {"integration_receipt_id": rid, "work_item_id": work_item_id,
           "seat_id": seat_id, "outcome": outcome,
           "product_commit": evidence.get("product_commit"),
           "integrated_as": evidence.get("integrated_as"),
           "integration_branch": evidence.get("integration_branch"),
           "previous_head": evidence.get("previous_head"),
           "source_branch": evidence.get("source_branch"),
           "worktree_path": evidence.get("worktree_path"),
           "validation_route": evidence.get("validation_route"),
           "validation_result": evidence.get("validation_result"),
           "attributed_files": list(evidence.get("attributed_files") or []),
           "conflict_paths": list(evidence.get("conflict_paths") or []),
           "remediation_required": bool(evidence.get("remediation_required")),
           "detail": evidence.get("detail")}
    with record_lock("integration_receipt", rid):
        existing = read("integration_receipt", rid)
        if existing is not None:
            comparable = {k: v for k, v in rec.items()
                          if k not in ("schema_version", "revision",
                                       "created_at", "updated_at")}
            if {k: existing.get(k) for k in comparable} != comparable:
                raise StateError("conflicting integration receipt %s" % rid)
            return existing
        rec["schema_version"] = SCHEMA_VERSION
        rec["revision"] = 1
        rec["created_at"] = now()
        rec["updated_at"] = rec["created_at"]
        _validate_one("integration_receipt", rec)
        _atomic_write(path_for("integration_receipt", rid), rec)
        return rec


def read_integration_receipts(work_item_id=None):
    """Every integration act, or only those for one work item."""
    return [r for r in read_all("integration_receipt")
            if work_item_id is None or r.get("work_item_id") == work_item_id]


def read_execution_receipt(invocation_id):
    """Recover durable normalized evidence without re-waking a provider."""
    if not invocation_id:
        raise StateError("invocation_id is required")
    return read("execution_receipt", _receipt_id(invocation_id))


# A CLI tool specifier is a COMMAND — `git diff`, `npm test`,
# `python3 -c 'resume()'`. The realistic failure is a sentence, and the reliable
# difference is length: a command is short and a scope explanation is not.
#
# This is a misuse guard, not a proof. Someone determined could write 100
# characters of prose and it would pass. What it stops is the accident that
# actually happened — a careful, well-meant explanation typed into a field that
# is handed to a command line — and it stops it at the write rather than three
# invocations later when a tool is mysteriously still denied.
_CLI_TOOL_SPECIFIER_MAX = 120


def _looks_like_cli_specifier(value):
    return ("\n" not in value and "\r" not in value
            and len(value) <= _CLI_TOOL_SPECIFIER_MAX)


def _approval_id(invocation_id, permission, allowed_operation=None):
    identity = invocation_id + "\0" + permission
    if allowed_operation is not None:
        identity += "\0" + allowed_operation
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return "approval-" + digest


def record_execution_approval(original_invocation_id, work_item_id, seat_id,
                              claude_session_id, permission, approving_authority,
                              approval_scope, allowed_operation=None,
                              decision_class=None):
    """Persist one exact denied-tool decision, immutably.

    The decision class is either explicit or deterministically derived from the
    exact permission. New writes can never use the legacy CEO-only shape;
    validation alone keeps historical records readable during migration.
    """
    required = (original_invocation_id, work_item_id, seat_id, claude_session_id,
                permission, approving_authority, approval_scope)
    if any(not isinstance(value, str) or not value.strip() for value in required):
        raise StateError("execution approval fields must be non-empty strings")
    try:
        from agent.organization.authority import (assert_decision_authority,
                                                  decision_class_for_permission)
        decision_class = decision_class or decision_class_for_permission(
            permission, allowed_operation)
        assert_decision_authority(decision_class, approving_authority,
                                  task_owner=seat_id)
    except ValueError as exc:
        raise StateError("execution approval authority refused: %s" % exc)
    if "*" in permission or (allowed_operation is not None and
                              (not isinstance(allowed_operation, str)
                               or not allowed_operation.strip()
                               or "*" in allowed_operation)):
        raise StateError("execution approval cannot be wildcarded")
    # The controller can never grant its own bootstrap back to a Product
    # executor.  This is deliberately a write-time guard as well as the wake
    # guard: malformed historical evidence remains readable, but new recursive
    # grants cannot be persisted.
    if permission == "Bash" and allowed_operation:
        control_tokens = ("execute_approved_claude_continuation",
                          "build_prepared_continuation_request",
                          "prepare_replacement_execution", "retire_execution_session",
                          "claudeclitransport", "claudeprovider(", "claude --resume",
                          "claude -p", "agent.execution.wake")
        if any(token in allowed_operation.lower() for token in control_tokens):
            raise StateError("execution approval cannot grant Product executor control-plane continuation")

    # `allowed_operation` is MACHINE-READABLE. It is rendered as
    # `permission(allowed_operation)` and handed to the Claude CLI's
    # `--allowedTools`, which matches it against tool rules. Prose there matches
    # nothing, so the tool stays denied while Persistent State records a grant
    # that looks perfectly good — a silent, durable lie about what was
    # authorized. The human-readable scope belongs in `approval_scope`, which is
    # evidence and never reaches a command line.
    if allowed_operation is not None and not _looks_like_cli_specifier(allowed_operation):
        raise StateError(
            "execution approval allowed_operation must be a CLI tool specifier — a "
            "bounded command of at most %d characters on one line, such as "
            "\"python3 -c 'resume()'\" — not prose. It is handed to the provider's "
            "--allowedTools, where a sentence matches no rule and the tool stays "
            "denied. Put the human-readable scope in approval_scope."
            % _CLI_TOOL_SPECIFIER_MAX)
    original = read_execution_receipt(original_invocation_id)
    if original is None or original.get("status") != "needs_input":
        raise StateError("execution approval needs an original needs_input receipt")
    if (original.get("work_item_id"), original.get("seat_id")) != (work_item_id, seat_id):
        raise StateError("execution approval does not match original execution identity")
    if original.get("provider_id") != "claude-code":
        raise StateError("execution approval is only valid for Claude Code")
    boundaries = [original] + [
        receipt for receipt in read_all("execution_receipt")
        if receipt.get("continuation_of_invocation_id") == original_invocation_id
    ]
    matches_boundary = False
    for boundary in boundaries:
        result = boundary.get("normalized_result") or {}
        escalation = result.get("escalation") or {}
        if (boundary.get("work_item_id"), boundary.get("seat_id"),
                boundary.get("provider_id"), result.get("continuation_ref")) == (
                    work_item_id, seat_id, "claude-code", claude_session_id) and \
                permission in str(escalation.get("reason") or ""):
            matches_boundary = True
            break
    if not matches_boundary:
        raise StateError("execution approval permission does not match original boundary")
    rid = _approval_id(original_invocation_id, permission, allowed_operation)
    rec = {"execution_approval_id": rid, "original_invocation_id": original_invocation_id,
           "work_item_id": work_item_id, "seat_id": seat_id, "provider_id": "claude-code",
           "claude_session_id": claude_session_id, "permission": permission,
           "allowed_operation": allowed_operation,
           "approving_authority": approving_authority, "approval_scope": approval_scope}
    rec["decision_class"] = decision_class
    with _Lock("execution-domain"):
        with record_lock("execution_approval", rid):
            existing = read("execution_approval", rid)
            if existing is not None:
                if any(existing.get(key) != value for key, value in rec.items()):
                    raise StateError("conflicting approval for original execution")
                return existing
            rec.update(schema_version=SCHEMA_VERSION, revision=1, created_at=now(), updated_at=now())
            _validate_one("execution_approval", rec)
            _atomic_write(path_for("execution_approval", rid), rec)
            return rec


def read_execution_approval(approval_id):
    if not approval_id:
        raise StateError("execution approval id is required")
    return read("execution_approval", approval_id)


def compose_execution_approvals(original_invocation_id, approval_ids=None):
    """Return every independently approved exact grant for one Claude resume.

    A continuation never selects a convenient subset: when a second native boundary
    has been approved, the next wake receives the complete immutable set.  This is
    intentionally read-only; composing approvals cannot wake a provider or change a
    claim, lifecycle, workspace, or Product state.
    """
    original = read_execution_receipt(original_invocation_id)
    if original is None or original.get("status") != "needs_input":
        raise StateError("approval composition needs an original needs_input receipt")
    # A completed/failed continuation is a terminal outcome for every grant in
    # this lineage.  A later needs-input boundary is deliberately not terminal:
    # it is the same preserved provider session asking for its next exact grant.
    terminal = [rec for rec in read_all("execution_receipt")
                if rec.get("continuation_of_invocation_id") == original_invocation_id
                and rec.get("status") != "needs_input"]
    if terminal:
        raise StateError("approval composition expired after terminal continuation outcome")
    approvals = sorted(
        (rec for rec in read_all("execution_approval")
         if rec.get("original_invocation_id") == original_invocation_id),
        key=lambda rec: (rec["permission"], rec.get("allowed_operation") or "",
                         rec["execution_approval_id"]),
    )
    if not approvals:
        raise StateError("approval composition needs at least one exact grant")
    all_ids = tuple(rec["execution_approval_id"] for rec in approvals)
    requested = all_ids if approval_ids is None else tuple(approval_ids)
    if (not requested or len(set(requested)) != len(requested)
            or set(requested) != set(all_ids)):
        raise StateError("approval composition must use every exact grant once")
    expected = (original.get("work_item_id"), original.get("seat_id"), "claude-code")
    session = None
    for rec in approvals:
        if (rec.get("work_item_id"), rec.get("seat_id"), rec.get("provider_id")) != expected:
            raise StateError("approval composition has a mismatched work item, seat, or provider")
        if session is None:
            session = rec.get("claude_session_id")
        elif rec.get("claude_session_id") != session:
            raise StateError("approval composition has a mismatched Claude session")
    return tuple(approvals)


def _continuation_id(invocation_id):
    return "continuation-" + hashlib.sha256(invocation_id.encode("utf-8")).hexdigest()


def record_execution_continuation_preparation(
        original_invocation_id, work_item_id, seat_id, claude_session_id, permission,
        repository_root, working_directory, worktree_path, branch, expected_revision,
        authorization_ref, authorization_scope, prepared_by="system-policy",
        review_context_ref=None):
    """Record system-derived continuation context without granting authority."""
    required = (original_invocation_id, work_item_id, seat_id, claude_session_id, permission,
                repository_root, working_directory, branch, expected_revision,
                authorization_ref, authorization_scope, prepared_by)
    if any(not isinstance(value, str) or not value.strip() for value in required):
        raise StateError("continuation preparation fields must be non-empty strings")
    if prepared_by not in ("system-policy", "orchestrator", "ceo") or "*" in permission:
        raise StateError("continuation preparation requires a system actor and one exact permission")
    original = read_execution_receipt(original_invocation_id)
    task = read("task", work_item_id)
    if original is None or original.get("status") != "needs_input":
        raise StateError("continuation preparation needs original needs_input receipt")
    if review_context_ref is not None:
        # A validation continuation resumes a reviewer, which never held the
        # claim. Its authority is the same open review context the invocation
        # ran under, so a stale or foreign one is refused here.
        assert_review_authority(work_item_id, seat_id, review_context_ref)
    elif task is None or (task.get("ownership") or {}).get("seat_id") != seat_id:
        raise StateError("continuation preparation needs the original active claim")
    result = original.get("normalized_result") or {}
    if (original.get("work_item_id"), original.get("seat_id"), original.get("provider_id")) != (
            work_item_id, seat_id, "claude-code"):
        raise StateError("continuation preparation does not match original execution")
    if result.get("continuation_ref") != claude_session_id:
        raise StateError("continuation preparation session does not match original receipt")
    if permission not in str((result.get("escalation") or {}).get("reason") or ""):
        raise StateError("continuation preparation permission does not match original boundary")
    profile = task.get("execution_profile") or {}
    capability, route = profile.get("required_capability"), profile.get("validation_route")
    if not capability or not route:
        raise StateError("continuation preparation needs canonical capability and validation route")
    rid = _continuation_id(original_invocation_id)
    rec = {
        "execution_continuation_id": rid, "original_invocation_id": original_invocation_id,
        "original_receipt_id": original["execution_receipt_id"], "work_item_id": work_item_id,
        "seat_id": seat_id, "provider_id": "claude-code", "claude_session_id": claude_session_id,
        "permission": permission, "required_capability": capability, "validation_route": route,
        "repository_root": repository_root, "working_directory": working_directory,
        "worktree_path": worktree_path, "branch": branch, "expected_revision": expected_revision,
        "authorization_ref": authorization_ref, "authorization_scope": authorization_scope,
        "prepared_by": prepared_by, "review_context_ref": review_context_ref,
        "preparation_purpose": "resume existing execution after permission gate",
        "historical_request_persisted": False,
    }
    with _Lock("execution-domain"):
        with record_lock("execution_continuation_preparation", rid):
            existing = read("execution_continuation_preparation", rid)
            if existing is not None:
                if any(existing.get(key) != value for key, value in rec.items()):
                    raise StateError("conflicting continuation preparation")
                return existing
            rec.update(schema_version=SCHEMA_VERSION, revision=1, created_at=now(), updated_at=now())
            _validate_one("execution_continuation_preparation", rec)
            _atomic_write(path_for("execution_continuation_preparation", rid), rec)
            return rec


def read_execution_continuation_preparation(original_invocation_id):
    if not original_invocation_id:
        raise StateError("original invocation id is required")
    return read("execution_continuation_preparation", _continuation_id(original_invocation_id))


def _session_retirement_id(original_invocation_id):
    return "session-retirement-" + hashlib.sha256(original_invocation_id.encode("utf-8")).hexdigest()


def retire_execution_session(original_invocation_id, reason, retired_by="orchestrator"):
    """Retire one unsafe provider session without altering its historical receipt."""
    original = read_execution_receipt(original_invocation_id)
    if original is None or original.get("provider_id") != "claude-code":
        raise StateError("session retirement needs a Claude execution receipt")
    if (not isinstance(reason, str) or not reason.strip()
            or retired_by not in ("orchestrator", "system-policy", "ceo", original.get("seat_id"))):
        raise StateError("session retirement needs an accountable system or task actor and reason")
    session = (original.get("normalized_result") or {}).get("continuation_ref")
    if not isinstance(session, str) or not session:
        raise StateError("session retirement needs the original Claude session")
    rid = _session_retirement_id(original_invocation_id)
    rec = {"execution_session_retirement_id": rid,
           "original_invocation_id": original_invocation_id,
           "work_item_id": original["work_item_id"], "seat_id": original["seat_id"],
           "provider_id": "claude-code", "claude_session_id": session,
           "reason": reason, "retired_by": retired_by}
    with _Lock("execution-domain"):
        with record_lock("execution_session_retirement", rid):
            existing = read("execution_session_retirement", rid)
            if existing is not None:
                if any(existing.get(key) != value for key, value in rec.items()):
                    raise StateError("conflicting session retirement")
                return existing
            rec.update(schema_version=SCHEMA_VERSION, revision=1, created_at=now(), updated_at=now())
            _validate_one("execution_session_retirement", rec)
            _atomic_write(path_for("execution_session_retirement", rid), rec)
            return rec


def read_execution_session_retirement(original_invocation_id):
    return read("execution_session_retirement", _session_retirement_id(original_invocation_id))


def prepare_replacement_execution(original_invocation_id, replacement_session_id,
                                  authorization_ref, authorization_scope,
                                  prepared_by="orchestrator"):
    """Create exactly one linked replacement for a retired provider session.

    This is intentionally preparation only: it acquires no lease, invokes no
    provider, and replays no Product action.
    """
    original = read_execution_receipt(original_invocation_id)
    retired = read_execution_session_retirement(original_invocation_id)
    if original is None or retired is None:
        raise StateError("replacement needs a retired historical execution")
    required = (replacement_session_id, authorization_ref, authorization_scope)
    if (any(not isinstance(value, str) or not value.strip() for value in required)
            or prepared_by not in ("orchestrator", "system-policy", "ceo", original.get("seat_id"))):
        raise StateError("replacement needs an accountable system or task actor and one session")
    if replacement_session_id == retired["claude_session_id"]:
        raise StateError("replacement must use a new Claude session")
    rid = "replacement-" + hashlib.sha256(original_invocation_id.encode("utf-8")).hexdigest()
    rec = {"execution_replacement_id": rid, "original_invocation_id": original_invocation_id,
           "retirement_id": retired["execution_session_retirement_id"],
           "work_item_id": original["work_item_id"], "seat_id": original["seat_id"],
           "provider_id": "claude-code", "replacement_session_id": replacement_session_id,
           "authorization_ref": authorization_ref, "authorization_scope": authorization_scope,
           "prepared_by": prepared_by, "replay_product_actions": False}
    with _Lock("execution-domain"):
        with record_lock("execution_replacement", rid):
            existing = read("execution_replacement", rid)
            if existing is not None:
                if any(existing.get(key) != value for key, value in rec.items()):
                    raise StateError("exactly one replacement execution is permitted")
                return existing
            rec.update(schema_version=SCHEMA_VERSION, revision=1, created_at=now(), updated_at=now())
            _validate_one("execution_replacement", rec)
            _atomic_write(path_for("execution_replacement", rid), rec)
            return rec


def read_execution_replacement(original_invocation_id):
    rid = "replacement-" + hashlib.sha256(original_invocation_id.encode("utf-8")).hexdigest()
    return read("execution_replacement", rid)


BOUNDED_PRODUCT_BATCH = "BOUNDED_PRODUCT_BATCH"
APPROVED_ROADMAP_BATCH = "APPROVED_ROADMAP_BATCH"
AUTHORIZATION_KINDS = (BOUNDED_PRODUCT_BATCH, APPROVED_ROADMAP_BATCH)
AUTHORIZATION_STATUSES = ("active", "exhausted", "revoked", "suspended")
CANONICAL_PLANNER = "canonical-thebes-planner"


def record_product_authorization(authorization_ref, maximum_completed_items,
                                 scope, approving_authority="ceo",
                                 authorization_kind=BOUNDED_PRODUCT_BATCH,
                                 selection_authority=CANONICAL_PLANNER):
    """Persist one accountable-role grant of bounded Product execution.

    This does NOT weaken D-003. D-003 forbids a controller INFERRING permission
    from queue availability, green tests or a finished ticket. Here permission is
    an explicit human act and only its representation is new: CEO decides a new
    investment envelope; PM decides a batch inside an approved roadmap; the
    canonical planner decides which admissible item fills it.

    Authority is contractual rather than cryptographic — `validate.py` says so
    of the whole store. Every grant names the human act it came from.
    """
    if authorization_kind not in AUTHORIZATION_KINDS:
        raise StateError("unknown product authorization kind %r" % authorization_kind)
    required_authority = "ceo" if authorization_kind == BOUNDED_PRODUCT_BATCH else "pm"
    if approving_authority != required_authority:
        raise StateError("%s product authorization requires %s authority"
                         % (authorization_kind, required_authority))
    if selection_authority != CANONICAL_PLANNER:
        raise StateError("product authorization selection authority must be the "
                         "canonical planner")
    if not isinstance(authorization_ref, str) or not authorization_ref.strip():
        raise StateError("product authorization requires a reference to the CEO grant")
    if not isinstance(scope, str) or not scope.strip():
        raise StateError("product authorization requires a scope")
    if not isinstance(maximum_completed_items, int) or maximum_completed_items < 1:
        raise StateError("product authorization maximum must be a positive integer")
    with _Lock("product-authorization"):
        for record in read_all("product_authorization"):
            if record.get("status") == "active":
                raise StateError("an active product authorization already exists: %s"
                                 % record["product_authorization_id"])
        rid = new_id("product_authorization")
        rec = {"product_authorization_id": rid,
               "authorization_kind": authorization_kind,
               "approving_authority": approving_authority,
               "authorization_ref": authorization_ref.strip(),
               "selection_authority": selection_authority,
               "maximum_completed_items": maximum_completed_items,
               # A LIST, not a counter. Duplicate consumption becomes structurally
               # impossible rather than something a check has to remember, and the
               # record stays auditable after the grant is spent.
               "completed_items": [],
               "scope": scope.strip(),
               "status": "active",
               "revoked_at": None, "revoked_by": None, "revocation_ref": None,
               "schema_version": SCHEMA_VERSION, "revision": 1,
               "created_at": now(), "updated_at": now()}
        _validate_one("product_authorization", rec)
        _atomic_write(path_for("product_authorization", rid), rec)
        return rec


def read_product_authorization(authorization_id):
    if not authorization_id:
        raise StateError("product authorization id is required")
    return read("product_authorization", authorization_id)


def active_product_authorization():
    """The one active bounded grant, or None. Never more than one by construction."""
    active = [record for record in read_all("product_authorization")
              if record.get("status") == "active"]
    return active[0] if len(active) == 1 else None


def authorization_remaining(record):
    if not record or record.get("status") != "active":
        return 0
    return max(0, record["maximum_completed_items"] - len(record.get("completed_items") or []))


def consume_product_authorization(authorization_id, work_item_id, expected_revision,
                                  evidence_ref, completed_at=None):
    """Record that one work item reached canonical completion under this grant.

    Called ONLY from the canonical completion path, and only for a canonically
    successful completion. Starting work consumes nothing: a refusal, a failure,
    a block or an interruption must leave the quota exactly where it was, because
    a grant that shrinks on attempts is a grant that silently expires while the
    work it was for never happened.

    Idempotent by identity — an item already recorded is returned unchanged
    rather than counted twice — so a retried or re-entered completion tail
    cannot spend the same allowance again.
    """
    if not work_item_id:
        raise StateError("product authorization consumption requires a work item")
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise StateError("product authorization consumption requires evidence")
    with _Lock("product-authorization"):
        with record_lock("product_authorization", authorization_id):
            rec = read("product_authorization", authorization_id)
            if rec is None:
                raise StateError("no such product authorization")
            if rec["revision"] != expected_revision:
                raise StateError("product authorization changed under us")
            if rec["status"] != "active":
                raise StateError("product authorization is %s" % rec["status"])
            completed = list(rec.get("completed_items") or [])
            if any(item["work_item_id"] == work_item_id for item in completed):
                return rec                     # already counted; never twice
            if len(completed) >= rec["maximum_completed_items"]:
                raise StateError("product authorization quota is exhausted")
            completed.append({"work_item_id": work_item_id,
                              "completed_at": completed_at or now(),
                              "evidence_ref": evidence_ref.strip()})
            rec = dict(rec, completed_items=completed, revision=rec["revision"] + 1,
                       updated_at=now())
            if len(completed) >= rec["maximum_completed_items"]:
                rec["status"] = "exhausted"
            _validate_one("product_authorization", rec)
            _atomic_write(path_for("product_authorization", authorization_id), rec)
            return rec


def revoke_product_authorization(authorization_id, expected_revision, revoked_by,
                                 revocation_ref, status="revoked"):
    """End a grant early. Only the CEO may revoke; suspension is for safety."""
    if status not in ("revoked", "suspended"):
        raise StateError("a product authorization ends as revoked or suspended")
    if status == "revoked" and revoked_by != "ceo":
        raise StateError("only the CEO may revoke a product authorization")
    if not isinstance(revocation_ref, str) or not revocation_ref.strip():
        raise StateError("ending a product authorization requires a reason reference")
    with _Lock("product-authorization"):
        with record_lock("product_authorization", authorization_id):
            rec = read("product_authorization", authorization_id)
            if rec is None:
                raise StateError("no such product authorization")
            if rec["revision"] != expected_revision:
                raise StateError("product authorization changed under us")
            rec = dict(rec, status=status, revoked_at=now(), revoked_by=revoked_by,
                       revocation_ref=revocation_ref.strip(),
                       revision=rec["revision"] + 1, updated_at=now())
            _validate_one("product_authorization", rec)
            _atomic_write(path_for("product_authorization", authorization_id), rec)
            return rec


def claim(work_item_id, seat_id, claim_ref, expected_revision, capability_of_seat=None,
          jira_status_id=None):
    """Atomically take execution ownership. CAS'd inside the record lock.

    Everything claimability asserts is re-checked HERE, inside the lock, immediately
    before the write. Checking outside and writing after is the read-modify-write
    race Wave 4 was built to refuse: two sessions could both see 'claimable' and both
    write. The lock plus the revision check is what makes exactly one succeed.

    A claim is NOT a wake. Nothing here invokes a seat; a seat is woken only after a
    claim has succeeded, and a wake never creates ownership.
    """
    import operations, queue as q                       # noqa: E402
    with _Lock("execution-domain"):
      with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        if cur.get("ownership") is not None:
            raise StateError("already-owned: %s is owned by %s"
                             % (work_item_id, cur["ownership"].get("seat_id")))
        mode_reason = operations.product_execution_reason(current_operating_mode())
        if mode_reason:
            raise StateError("not-claimable: " + mode_reason)
        cap = (cur.get("execution_profile") or {}).get("required_capability")
        if capability_of_seat is not None and capability_of_seat != cap:
            raise StateError("wrong-capability: seat %s is %r, task requires %r"
                             % (seat_id, capability_of_seat, cap))
        held = [t for t in read_all("task")
                if (t.get("ownership") or {}).get("seat_id") == seat_id]
        if held:
            raise StateError("seat-already-owns: %s already owns %s"
                             % (seat_id, held[0]["work_item_id"]))
        reasons = q.unclaimable_reasons(cur, jira_status_id=jira_status_id)
        if reasons:
            raise StateError("not-claimable: " + ", ".join(reasons))
        merged = dict(cur)
        merged["ownership"] = {"seat_id": seat_id, "claimed_at": now(),
                               "claim_ref": claim_ref}
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def release(work_item_id, seat_id, expected_revision, release_ref, authority=None):
    """Give up ownership. ownership -> null, never reassigned in the same act.

    Only the current owner releases, unless an explicit CEO/system safety authority
    is named. Release never hands the slot to someone else: a reassignment that
    happens inside a release is a silent steal, and the next claim should have to win
    the lock like everyone else.

    **Release is deliberately NOT gated by an active STOP.** A STOP that blocked
    release would trap ownership permanently, and the defined way out of a stopped
    task is for its owner to release it.
    """
    with record_lock("task", work_item_id):
        cur = read("task", work_item_id)
        if cur is None:
            raise StateError("task %s does not exist" % work_item_id)
        if cur["revision"] != expected_revision:
            raise StateError("stale write refused: task %s is at revision %d, caller "
                             "expected %d" % (work_item_id, cur["revision"],
                                              expected_revision))
        own = cur.get("ownership")
        if own is None:
            raise StateError("not-owned: %s has no current owner" % work_item_id)
        if own.get("seat_id") != seat_id and authority not in ("ceo", "orchestrator"):
            raise StateError("not-owner: %s is owned by %s, not %s"
                             % (work_item_id, own.get("seat_id"), seat_id))
        ev = list(cur.get("executor_evidence") or [])
        ev.append({"seat_id": own.get("seat_id"), "evidence_ref": release_ref,
                   "evidenced_at": now()})
        seen, uniq = set(), []
        for e in ev:
            k = (e.get("seat_id"), e.get("evidence_ref"), e.get("evidenced_at"))
            if k not in seen:
                seen.add(k); uniq.append(e)
        merged = dict(cur)
        merged["ownership"] = None
        merged["executor_evidence"] = uniq
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


def _id_field(kind):
    return {"task": "work_item_id", "routing": "request_id",
            "exception": "exception_id", "dependency": "dependency_id",
            "intervention": "intervention_id", "policy": "policy_id",
            "event": "event_id", "learning": "learning_id",
            "work_cycle": "work_cycle_id", "decision": "decision_id",
            "delegation": "delegation_id",
            "coverage": "coverage_id", "correction": "correction_id",
            "operating_mode": "operating_mode_id",
            "execution_lease": "execution_lease_id",
            "execution_receipt": "execution_receipt_id",
            "role_session": "seat_id",
            "session_dispatch": "dispatch_id"}[kind]


def _validate_one(kind, record):
    """Refuse on errors; carry warnings without blocking.

    A WARN marks a state that is legitimate but wants a human eye — a legacy item
    observed in review before its route has been reconciled, say. Treating it as
    fatal would make the honest migration path unwritable and push callers toward
    inventing a route to satisfy the validator, which is the opposite of the point.
    """
    from validate import validate_record               # noqa: E402
    errs = validate_record(kind, record)
    hard = [e for e in errs if " WARN " not in e]
    if hard:
        raise StateError("; ".join(hard))


sys.path.insert(0, STATE)

if __name__ == "__main__":
    print(__doc__.strip().split("\n")[0])
    print("runtime:", RUNTIME)
    print("this module is a library; use validate.py --check to verify state")
