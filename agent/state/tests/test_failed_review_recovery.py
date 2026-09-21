#!/usr/bin/env python3
"""Recovering a PEER-FAILED item with NO evidenced executor to Ready. (T-092)

Synthetic runtime and roster. No live Jira call, no Product file.

THE STATE, AND HOW IT ARISES
  Work that reached the branch outside the wake seam was routed UP to PEER under
  T-090 (executor_evidence empty). Its PEER review recorded FAIL. The canonical
  PEER-fail transfer needs one evidenced executor to record as `previous_owner`
  and there is none, so the transfer is refused — and nothing else could move the
  item: execution recovery refuses review statuses, open_review_context never
  reopens a failed PEER context, and the validator refuses a context in Ready.

WHAT THESE TESTS DEFEND
  That recovery returns the work to the QUEUE with its findings preserved and its
  route back at the policy floor, creates no ownership and no evidence, and refuses
  every state that is not exactly "PEER, fail, unowned, unevidenced, in review".

Stdlib only.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import (fresh_seat_registry, ok, raises, section, summary,
                      state_path)   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, policy, queue as q, board                          # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend",
          "content-manager": "content", "content-2": "content", "po": "po"}
fresh_runtime()
fresh_seat_registry(validate, ROSTER)

PEER, READY = "10045", "10008"
REF = "T-092; jira comment 1"


def failed_peer(result="fail", owner_seat="frontend-2"):
    return {"review_type": "peer", "review_owner": owner_seat, "review_result": result,
            "review_cycle": 1, "started_at": store.now()}


def mk(key, *, capability="frontend", sid=PEER, canonical="review", owner=None,
       evidence=(), rc=None, route="peer", ch=None, effort=2):
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "design-system",
        "surfaces": ["lib/src/cards/"],
        "executor_evidence": [{"seat_id": s, "evidence_ref": "ref:%s:%d" % (s, i),
                               "evidenced_at": store.now()}
                              for i, s in enumerate(evidence)],
        "ownership": ({"seat_id": owner, "claim_ref": "r", "claimed_at": store.now()}
                      if owner else None),
        "review_context": rc,
        "lifecycle": {"canonical": canonical, "jira_column": board.column_for(sid),
                      "jira_status_id": sid, "jira_status_name": board.name_for(sid),
                      "observed_at": store.now(), "source": "jira"},
        "execution_profile": {
            "required_capability": capability, "work_effort": effort,
            "validation_route": route, "completion_route": "DONE",
            "characteristics": ch or {}, "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "characteristics", "validation_route",
                                 "completion_route"],
            "provenance": {"required_capability": {"by": "po", "at": store.now()},
                           "validation_route": {"by": "system-policy",
                                                "at": store.now()}},
        },
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }
    with open(store.path_for("task", key), "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


def recover(key, rev, actor="po", ref=REF, sid=READY):
    return store.recover_failed_review_to_ready(key, rev, ref, actor, sid)


section("1. the exact state is recovered: context closed, findings kept, route at floor")
t = mk("KAN-288", rc=failed_peer())
r = recover("KAN-288", t["revision"])
ok("review_context is null", r["review_context"] is None)
ok("lifecycle observed at Ready",
   r["lifecycle"]["canonical"] == "ready" and r["lifecycle"]["jira_status_id"] == READY)
ok("from_status is the review status left", r["execution_recovery"]["from_status"] == PEER)
ok("the failed verdict and its reviewer are preserved verbatim",
   r["execution_recovery"]["closed_review"]["review_result"] == "fail"
   and r["execution_recovery"]["closed_review"]["review_owner"] == "frontend-2")
ok("route recomputed to the policy floor (SELF for no characteristics)",
   r["execution_profile"]["validation_route"] == policy.SELF)
ok("route provenance is system-policy",
   r["execution_profile"]["provenance"]["validation_route"]["by"] == "system-policy")
ok("no ownership and no evidence were created",
   r["ownership"] is None and r["executor_evidence"] == [])
ok("one revision", r["revision"] == t["revision"] + 1)

section("2. it is claimable by an ordinary claim; the previous reviewer gets no preference")
reasons = q.unclaimable_reasons(r, [])
ok("no readiness fact was lost: %r" % reasons,
   "surfaces-unassessed" not in reasons and "missing-work-effort" not in reasons)
c = store.claim("KAN-288", "frontend-1", "claim:test", r["revision"],
                capability_of_seat="frontend", jira_status_id=READY)
ok("another same-capability seat may claim first", c["ownership"]["seat_id"] == "frontend-1")

section("3. a second recovery on the recovered item refuses")
raises("second recovery refuses", lambda: recover("KAN-288", c["revision"]), "not-in-review")

section("4. every other state refuses, and leaves the record untouched")
cases = {
    "review-not-failed": mk("KAN-301", rc=failed_peer(result="pending")),
    "not-a-peer-review": mk("KAN-302", route="self",
                            rc={"review_type": "self", "review_owner": "frontend-1",
                                "review_result": "fail", "review_cycle": 1,
                                "started_at": store.now()}),
    "no-review-context": mk("KAN-303", rc=None),
    "already-owned": mk("KAN-304", rc=failed_peer(), owner="frontend-1"),
    "executor-evidenced": mk("KAN-305", rc=failed_peer(), evidence=("frontend-1",)),
    "not-in-review": mk("KAN-306", rc=None, sid=READY, canonical="ready", route=None),
}
for reason, rec in cases.items():
    before = store.read("task", rec["work_item_id"])
    raises(reason, lambda rec=rec: recover(rec["work_item_id"], rec["revision"]), reason)
    ok("%s: record untouched" % reason,
       store.read("task", rec["work_item_id"]) == before)

section("5. authority, reference, Jira read-back, staleness and STOP")
t = mk("KAN-307", rc=failed_peer())
raises("executor may not recover", lambda: recover("KAN-307", t["revision"], actor="frontend-1"),
       "unauthorised-recovery-actor")
raises("a reason is required", lambda: recover("KAN-307", t["revision"], ref=""),
       "recovery_ref is required")
raises("Jira must already read Ready", lambda: recover("KAN-307", t["revision"], sid=PEER),
       "jira-not-ready")
raises("stale revision refused", lambda: recover("KAN-307", t["revision"] + 5),
       "stale write refused")
store.create("intervention", {"kind": "stop", "target": "KAN-307", "scope": "task",
                              "created_by": "ceo", "reason_ref": "test", "cleared_at": None})
raises("STOP blocks recovery", lambda: recover("KAN-307", t["revision"]), "task-stopped")

section("6. a PEER route that IS a characteristic stays PEER at the floor")
t = mk("KAN-308", rc=failed_peer(), ch={"schema_change": True})
r = recover("KAN-308", t["revision"])
ok("a characteristic-derived PEER floor is kept, not lowered",
   r["execution_profile"]["validation_route"] == policy.PEER)

sys.exit(summary())
