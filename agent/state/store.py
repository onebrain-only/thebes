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
SCHEMA_VERSION = 2

KINDS = {
    "task":       ("tasks",        None),
    "routing":    ("routing",      "rr"),
    "exception":  ("exceptions",   "exc"),
    "dependency": ("dependencies", "dep"),
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


def _id_field(kind):
    return {"task": "work_item_id", "routing": "request_id",
            "exception": "exception_id", "dependency": "dependency_id"}[kind]


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
