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
import fcntl, json, os, re, sys, uuid
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
}


class StateError(Exception):
    """Refused write. Never raised for a condition the caller could not check."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id(kind):
    prefix = KINDS[kind][1]
    if prefix is None:
        raise StateError("task ids are Jira keys, not generated")
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


def evidenced_executors(task):
    """The DISTINCT seats evidenced as having executed this work, sorted.

    One list, one meaning, read the same way everywhere: `queue.unclaimable_reasons`
    calls two of these `conflicting-evidence`, `policy.resolve_owner_or_wait` refuses
    to name a SELF owner unless there is exactly one, and this helper is what both
    of them are counting. Ownership is NOT evidence and never appears here — a seat
    that holds a claim has not yet executed anything.
    """
    return sorted({e.get("seat_id") for e in (task.get("executor_evidence") or [])
                   if isinstance(e, dict) and e.get("seat_id")})


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


def peer_fail_transfer(work_item_id, expected_revision, reviewer, evidence_ref):
    """PEER FAIL: the reviewer becomes the executor and self-reviews its own fix.

    Every field moves in ONE CAS'd write, because a half-applied transfer is exactly
    the state that would let someone reach an easier route: evidence replaced but
    review_type still peer, or review_type flipped with ownership left behind.

    executor_evidence is REPLACED, not appended. A list with two entries means
    CONFLICTING evidence and routing must refuse; here the workflow has explicitly
    transferred responsibility, so the original developer is no longer current
    evidence. Its ownership survives in Jira history and in previous_owner.

    The work returns to the SAME Development column: the reviewer shares the task's
    capability by construction, so required_capability does not change and neither
    does the column.
    """
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
        rc = dict(cur.get("review_context") or {})
        if rc.get("review_type") != "peer":
            raise StateError("peer_fail_transfer applies to the PEER route only")
        if rc.get("review_owner") != reviewer:
            raise StateError("only the recorded review owner may fail and take over")
        prev = [e.get("seat_id") for e in (cur.get("executor_evidence") or [])]
        merged = dict(cur)
        merged["executor_evidence"] = [{"seat_id": reviewer,
                                        "evidence_ref": evidence_ref,
                                        "evidenced_at": now()}]
        merged["review_context"] = {
            "review_type": "self",
            "review_owner": reviewer,
            "review_result": "pending",
            "review_cycle": int(rc.get("review_cycle") or 1) + 1,
            "started_at": now(),
            "previous_owner": prev[0] if len(prev) == 1 else None,
        }
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
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
            prof["provenance"] = prov
            merged["execution_profile"] = prof
        merged["revision"] = cur["revision"] + 1
        merged["updated_at"] = now()
        _validate_one("task", merged)
        _atomic_write(path_for("task", work_item_id), merged)
        return merged


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
    import queue as q                                   # noqa: E402
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
            "intervention": "intervention_id"}[kind]


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
