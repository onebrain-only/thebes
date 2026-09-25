#!/usr/bin/env python3
"""Persistent-session bindings and dispatch outcomes, against a real store.

Covers: a binding persists and reloads; a rebind is CAS'd and keeps its
history; an outcome is accepted only from the bound session; every outcome in
the vocabulary is durably representable; each dispatch settles exactly once;
and settling never touches ownership. Runs in a temporary runtime — never the
real one.
"""
import os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _harness import ok, raises, section, summary, state_path, repo_root  # noqa: E402

sys.path.insert(0, repo_root())
sys.path.insert(0, state_path())
import store      # noqa: E402
import validate   # noqa: E402

SEAT = "frontend-1"                       # declared in the real neutral registry
OTHER_SEAT = "backend-1"
SID_A = "11111111-1111-4111-8111-111111111111"
SID_B = "22222222-2222-4222-8222-222222222222"
HOME = "/stable/home"

TMP = tempfile.mkdtemp()
OLD = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
store.RUNTIME = os.path.join(TMP, "runtime")
store.LOCKS = os.path.join(store.RUNTIME, ".locks")
validate.RUNTIME = store.RUNTIME


def lease(work_item_id="KAN-901", seat=SEAT):
    return store.create("execution_lease", {
        "work_item_id": work_item_id, "seat_id": seat, "mode_revision": 1,
        "reason_ref": "authz:fixture", "closed_at": None, "closed_by": None})


def dispatch(lease_rec, session_id=SID_A, seat=SEAT, work_item_id="KAN-901"):
    return store.create("session_dispatch", {
        "work_item_id": work_item_id, "seat_id": seat, "provider": "claude",
        "session_id": session_id, "worktree_path": "/wt/%s" % work_item_id,
        "branch": "exec/%s/%s" % (seat, work_item_id),
        "execution_lease_id": lease_rec["execution_lease_id"],
        "invocation_id": "controller-fixture", "authorization_ref": "authz:fixture",
        "status": "dispatched", "outcome": None, "summary": None, "reference": None,
        "reported_session_id": None, "outcome_at": None, "recorded_by": None})


try:
    section("1. binding persists, reloads, and rebinds by CAS")
    first = store.bind_role_session(SEAT, "claude", SID_A, HOME, "ceo", session_name="dev")
    ok("created at revision 1 and active", first["revision"] == 1 and first["status"] == "active")
    on_disk = store.read("role_session", SEAT)
    ok("reloads from disk with the same session id", on_disk["session_id"] == SID_A)
    ok("active_role_session returns it", (store.active_role_session(SEAT) or {}).get("session_id") == SID_A)
    ok("an unbound seat has no active binding", store.active_role_session(OTHER_SEAT) is None)
    raises("rebind without expected_revision refused",
           lambda: store.bind_role_session(SEAT, "claude", SID_B, HOME, "ceo"),
           "expected_revision")
    raises("stale rebind refused",
           lambda: store.bind_role_session(SEAT, "claude", SID_B, HOME, "ceo",
                                           expected_revision=7), "stale write")
    second = store.bind_role_session(SEAT, "claude", SID_B, HOME, "ceo",
                                     expected_revision=first["revision"])
    ok("rebind moves to revision 2", second["revision"] == 2)
    ok("rebind keeps the old id in previous_session_ids",
       second["previous_session_ids"] == [SID_A] and second["session_id"] == SID_B)
    raises("unknown seat refused",
           lambda: store.bind_role_session("no-such-seat", "claude", SID_A, HOME, "ceo"),
           "not declared")
    raises("unknown provider refused",
           lambda: store.bind_role_session(OTHER_SEAT, "gpt", SID_A, HOME, "ceo"),
           "unknown provider")
    raises("a session name is not an identity",
           lambda: store.bind_role_session(OTHER_SEAT, "claude", "my-dev-session", HOME, "ceo"),
           "UUID")
    raises("a relative stable_home is refused",
           lambda: store.bind_role_session(OTHER_SEAT, "claude", SID_A, "relative/home", "ceo"),
           "absolute")
    ok("codex is a representable provider",
       store.bind_role_session(OTHER_SEAT, "codex", SID_A, HOME, "ceo")["provider"] == "codex")

    section("5/6. outcome identity is the bound session id")
    L = lease()
    D = dispatch(L, session_id=SID_B)
    raises("a different session id is refused",
           lambda: store.record_session_outcome(D["dispatch_id"], "completed", "done", "orchestrator",
                                                session_id=SID_A), "session-identity-mismatch")
    ok("the refused report recorded nothing",
       store.read("session_dispatch", D["dispatch_id"])["status"] == "dispatched"
       and store.read("session_dispatch", D["dispatch_id"])["revision"] == D["revision"])
    ok("the refused report left the lease open",
       store.read("execution_lease", L["execution_lease_id"])["closed_at"] is None)
    raises("a missing session id is refused for a worker outcome",
           lambda: store.record_session_outcome(D["dispatch_id"], "completed", "done",
                                                "orchestrator"), "session_id is required")
    done = store.record_session_outcome(D["dispatch_id"], "completed", "done", "orchestrator",
                                        session_id=SID_B, reference="abc1234")
    ok("the bound session's report is recorded",
       done["status"] == "completed" and done["reported_session_id"] == SID_B
       and done["reference"] == "abc1234")
    ok("recording closed the dispatch's lease",
       bool(store.read("execution_lease", L["execution_lease_id"])["closed_at"]))
    ok("no task record was written by settling (ownership untouched)",
       store.read_all("task") == [])

    section("5b. a rebind after dispatch invalidates the old session's report")
    L2 = lease("KAN-902")
    D2 = dispatch(L2, session_id=SID_B, work_item_id="KAN-902")
    cur = store.read("role_session", SEAT)
    store.bind_role_session(SEAT, "claude", SID_A, HOME, "ceo", expected_revision=cur["revision"])
    raises("dispatch session no longer the active binding -> refused",
           lambda: store.record_session_outcome(D2["dispatch_id"], "completed", "late",
                                                "orchestrator", session_id=SID_B),
           "session-identity-mismatch")
    ok("its lease is still open", store.read("execution_lease", L2["execution_lease_id"])["closed_at"] is None)

    section("FIX 1. write order: dispatch settles before its lease closes")
    active_sid_for_fix1 = store.active_role_session(SEAT)["session_id"]
    L3 = lease("KAN-903")
    D3 = dispatch(L3, session_id=active_sid_for_fix1, work_item_id="KAN-903")
    before = store.read("session_dispatch", D3["dispatch_id"])
    real_validate_one = store._validate_one

    def _fail_validate(kind, record):
        if kind == "session_dispatch":
            raise store.StateError("fixture: refuse validation of the settled dispatch")
        return real_validate_one(kind, record)

    store._validate_one = _fail_validate
    try:
        raises("a validation failure at step (b) records nothing",
               lambda: store.record_session_outcome(D3["dispatch_id"], "completed", "x",
                                                    "orchestrator", session_id=active_sid_for_fix1),
               "fixture: refuse validation")
    finally:
        store._validate_one = real_validate_one
    after_validate_failure = store.read("session_dispatch", D3["dispatch_id"])
    ok("the dispatch record is byte-for-byte unchanged after a validation failure",
       after_validate_failure == before)
    ok("its status is still dispatched", after_validate_failure["status"] == "dispatched")
    ok("its lease is still open (closed_at null)",
       store.read("execution_lease", L3["execution_lease_id"])["closed_at"] is None)
    ok("its lease revision is unchanged",
       store.read("execution_lease", L3["execution_lease_id"])["revision"] == L3["revision"])

    real_atomic_write = store._atomic_write

    def _fail_write(path, obj):
        if path == store.path_for("session_dispatch", D3["dispatch_id"]):
            raise OSError("fixture: refuse the atomic write of the settled dispatch")
        return real_atomic_write(path, obj)

    store._atomic_write = _fail_write
    try:
        raises("an atomic-write failure at step (c) records nothing",
               lambda: store.record_session_outcome(D3["dispatch_id"], "completed", "x",
                                                    "orchestrator", session_id=active_sid_for_fix1),
               "refuse the atomic write")
    finally:
        store._atomic_write = real_atomic_write
    after_write_failure = store.read("session_dispatch", D3["dispatch_id"])
    ok("the dispatch record is byte-for-byte unchanged after a write failure",
       after_write_failure == before)
    ok("its lease is STILL open after the write failure too",
       store.read("execution_lease", L3["execution_lease_id"])["closed_at"] is None)
    # Now let it succeed for real, proving the fixtures above changed nothing
    # about ordinary success.
    settled = store.record_session_outcome(D3["dispatch_id"], "completed", "x", "orchestrator",
                                           session_id=active_sid_for_fix1)
    ok("an unpatched call still settles and closes the lease",
       settled["status"] == "completed"
       and bool(store.read("execution_lease", L3["execution_lease_id"])["closed_at"]))

    section("7. every outcome is durably representable, once")
    active_sid = store.active_role_session(SEAT)["session_id"]
    for index, outcome in enumerate(sorted(store.SESSION_DISPATCH_OUTCOMES)):
        work_item_id = "KAN-%d" % (910 + index)
        rec = dispatch(lease(work_item_id), session_id=active_sid, work_item_id=work_item_id)
        kwargs = {} if outcome == "worker_unreachable" else {"session_id": active_sid}
        store.record_session_outcome(rec["dispatch_id"], outcome, "summary for %s" % outcome,
                                     "orchestrator", **kwargs)
        back = store.read("session_dispatch", rec["dispatch_id"])
        ok("%s persists and reloads" % outcome, back["status"] == outcome == back["outcome"])
        if outcome == "worker_unreachable":
            ok("worker_unreachable carries the exact recovery hint",
               back["recovery_hint"] == 'claude --bg --resume %s "<prompt>" — no other flags; '
                                        'extra flags create a copy' % active_sid)
            ok("worker_unreachable needs no reporting session", back["reported_session_id"] is None)
        raises("a second outcome on the %s dispatch is refused" % outcome,
               lambda: store.record_session_outcome(rec["dispatch_id"], "failed", "again",
                                                    "orchestrator", session_id=active_sid),
               "not open")
    raises("an outcome outside the vocabulary is refused",
           lambda: store.record_session_outcome(D["dispatch_id"], "done-ish", "x", "orchestrator",
                                                session_id=SID_B), "unknown session dispatch outcome")

    section("validator sweep covers the new record kinds")
    mine = [e for e in validate.check(store.RUNTIME)
            if "role_session" in e or "session_dispatch" in e
            or "role-sessions" in e or "session-dispatches" in e]
    ok("no validation errors on role-sessions or session-dispatches", mine == [])
    bad = dict(store.read("session_dispatch", D["dispatch_id"]), reported_session_id=SID_A)
    ok("the file-level rule rejects an outcome reported by another session",
       any("bound session" in e for e in validate.validate_record("session_dispatch", bad)))
finally:
    store.RUNTIME, store.LOCKS, validate.RUNTIME = OLD
    shutil.rmtree(TMP, ignore_errors=True)

sys.exit(summary())
