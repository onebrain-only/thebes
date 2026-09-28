#!/usr/bin/env python3
"""Outcome attestation gate (hardening 2026-09-28), against a real store.

A worker's outcome is accepted only when BOTH hold: the reporting SID is the
dispatch's bound SID and the seat's current active binding (the existing
identity check), AND Thebes holds a DELIVERED session_delivery for that exact
dispatch and that SID. Anything else is refused deterministically with
"outcome-delivery-unattested" and nothing changes: dispatch still open, lease
still open. worker_unreachable keeps its exemption (no SID, no delivery).
"""
import os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _harness import ok, raises, section, summary, state_path, repo_root  # noqa: E402

sys.path.insert(0, repo_root())
sys.path.insert(0, state_path())
import store      # noqa: E402
import validate   # noqa: E402

SEAT = "po"
SID = "4d417564-5e86-4808-aacf-7158dcb65d59"
OTHER = "11111111-1111-4111-8111-111111111111"
HOME = "/stable/home"

TMP = tempfile.mkdtemp()
OLD = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
store.RUNTIME = os.path.join(TMP, "runtime")
store.LOCKS = os.path.join(store.RUNTIME, ".locks")
validate.RUNTIME = store.RUNTIME

n = [0]


def dispatch(sid=SID):
    n[0] += 1
    item = "KAN-%d" % (950 + n[0])
    lease = store.create("execution_lease", {"work_item_id": item, "seat_id": SEAT,
                                             "mode_revision": 1, "reason_ref": "authz:fixture",
                                             "closed_at": None, "closed_by": None})
    return store.create("session_dispatch", {
        "work_item_id": item, "seat_id": SEAT, "provider": "claude", "session_id": sid,
        "worktree_path": "/wt", "branch": "exec/po/%s" % item,
        "execution_lease_id": lease["execution_lease_id"], "invocation_id": "fixture",
        "authorization_ref": "authz:fixture", "status": "dispatched", "outcome": None,
        "summary": None, "reference": None, "reported_session_id": None, "outcome_at": None,
        "recorded_by": None})


def delivery(d, status="DELIVERED", sid=None, delivery_id=None):
    return store.record_session_delivery(delivery_id or d["dispatch_id"], {
        "dispatch_id": d["dispatch_id"], "work_item_id": d["work_item_id"], "seat_id": SEAT,
        "provider": "claude", "session_id": sid or d["session_id"], "status": status,
        "stopped_before_resume": "YES", "resumed_same_sid": "YES" if status == "DELIVERED" else "NO",
        "session_count_before": 1, "session_count_after": 1,
        "delivered_at": store.now() if status == "DELIVERED" else None,
        "error": None if status == "DELIVERED" else {"code": status, "message": "fixture"}})


def untouched(d, label):
    cur = store.read("session_dispatch", d["dispatch_id"])
    lease = store.read("execution_lease", d["execution_lease_id"])
    ok(label + ": nothing recorded, dispatch open, lease open",
       cur["status"] == "dispatched" and cur["revision"] == d["revision"]
       and lease["closed_at"] is None)


try:
    store.bind_role_session(SEAT, "claude", SID, HOME, "ceo", session_name="thebes-po-c")

    section("1. valid SID + DELIVERED -> accepted")
    d = dispatch(); delivery(d)
    rec = store.record_session_outcome(d["dispatch_id"], "completed", "hash read", "orchestrator",
                                       session_id=SID, reference="b2f46e7", delivery_id=d["dispatch_id"])
    ok("settled and attested", rec["status"] == "completed"
       and rec["attested_delivery_id"] == d["dispatch_id"])
    ok("lease closed", bool(store.read("execution_lease", d["execution_lease_id"])["closed_at"]))
    raises("a replayed valid outcome is refused and changes nothing",
           lambda: store.record_session_outcome(d["dispatch_id"], "completed", "again", "orchestrator",
                                                session_id=SID, delivery_id=d["dispatch_id"]), "not open")
    ok("replay left the settled record at its revision",
       store.read("session_dispatch", d["dispatch_id"])["revision"] == rec["revision"])

    section("2. valid SID + no delivery record -> rejected")
    d = dispatch()
    raises("unattested", lambda: store.record_session_outcome(
        d["dispatch_id"], "completed", "x", "orchestrator", session_id=SID), "outcome-delivery-unattested")
    untouched(d, "no delivery")

    section("3. valid SID + FAILED / UNREACHABLE delivery -> rejected")
    for status in ("CLAUDE_DELIVERY_FAILED", "CLAUDE_DELIVERY_WORKER_UNREACHABLE"):
        d = dispatch(); delivery(d, status=status)
        raises("%s is not DELIVERED" % status, lambda: store.record_session_outcome(
            d["dispatch_id"], "completed", "x", "orchestrator", session_id=SID), "not DELIVERED")
        untouched(d, status)

    section("4. wrong SID + DELIVERED -> rejected (identity check first)")
    d = dispatch(); delivery(d)
    raises("wrong reporter", lambda: store.record_session_outcome(
        d["dispatch_id"], "completed", "x", "orchestrator", session_id=OTHER), "session-identity-mismatch")
    untouched(d, "wrong SID")
    d = dispatch(); delivery(d, sid=OTHER)
    raises("delivery went to another session", lambda: store.record_session_outcome(
        d["dispatch_id"], "completed", "x", "orchestrator", session_id=SID), "not the reporting session")
    untouched(d, "delivery to other SID")

    section("5. delivery belongs to a different dispatch -> rejected")
    a = dispatch(); b = dispatch(); delivery(a)
    raises("named delivery is another dispatch's", lambda: store.record_session_outcome(
        b["dispatch_id"], "completed", "x", "orchestrator", session_id=SID, delivery_id=a["dispatch_id"]),
        "belongs to dispatch")
    untouched(b, "foreign delivery")

    section("6. delivery_id mismatch -> rejected")
    d = dispatch(); delivery(d)
    raises("unknown delivery id", lambda: store.record_session_outcome(
        d["dispatch_id"], "completed", "x", "orchestrator", session_id=SID, delivery_id="delivery-nope"),
        "no session_delivery delivery-nope")
    untouched(d, "delivery_id mismatch")
    ok("without a delivery_id the dispatch's own DELIVERED record attests",
       store.record_session_outcome(d["dispatch_id"], "completed", "x", "orchestrator",
                                    session_id=SID)["attested_delivery_id"] == d["dispatch_id"])

    section("7. worker_unreachable keeps its exemption")
    d = dispatch()
    rec = store.record_session_outcome(d["dispatch_id"], "worker_unreachable", "no answer", "orchestrator")
    ok("recorded with no SID and no delivery", rec["status"] == "worker_unreachable"
       and rec["attested_delivery_id"] is None)

    ok("validator sweep clean", [e for e in validate.check(store.RUNTIME)
                                 if "session" in e.lower()] == [])
finally:
    store.RUNTIME, store.LOCKS, validate.RUNTIME = OLD
    shutil.rmtree(TMP, ignore_errors=True)

sys.exit(summary())
