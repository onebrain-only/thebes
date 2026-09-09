#!/usr/bin/env python3
"""Assessment is not execution.

Synthetic runtime and roster throughout. No live Jira, no database, no Product file.

WHAT THIS SUITE DEFENDS

  `CLAUDE.md` settles it in four words — "assessing is not claiming". Preflight
  sizing, surface assessment, planning and capability evaluation are pre-execution
  factual acts, and they establish no executor identity. Nothing enforced that. A
  seat that sized an item at Preflight wrote one line to its status file, and that
  line landed in `executor_evidence` indistinguishable from having done the work.

  It broke two real items on 2026-09-09, in OPPOSITE directions, which is why one
  test would not have caught it:

    KAN-136 — a sizing entry plus a genuine execution entry made TWO seats appear
      evidenced. `open_review_context` refused to derive a SELF owner, and a
      completed, correct piece of work could not be reviewed at all.

    KAN-138 — a sizing entry made `backend-5` look like an executor, excluding it
      from the PEER reviewer pool for work it had never touched.

  So the property under test is not "sizing is harmless". It is that sizing must be
  INERT for executor derivation while remaining fully auditable — and that the rule
  holds in every place the derivation is written, because it is written in three:
  `store.evidenced_executors`, `validate`'s SELF-owner check, and `queue`'s
  conflicting-evidence predicate. The reconciliation was applied and STILL failed the
  first time, because the validator carried its own copy. That is test [14].

Stdlib only.
"""
import json
import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, board, queue as q                                  # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies", "events",
                 "learning", "coverage", "corrections"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


ROSTER = {"backend-1": "backend", "backend-2": "backend", "backend-3": "backend",
          "backend-4": "backend", "frontend-1": "frontend", "qa": "qa", "po": "po"}


def fresh_roster():
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in ROSTER.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return validate.seats_by_capability()


def mk(key, *, capability="backend", sid="10044", canonical="review", route="self",
       evidence=(), owner=None, rc=None):
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app", "surfaces": [],
        "executor_evidence": list(evidence),
        "ownership": ({"seat_id": owner, "claim_ref": "r", "claimed_at": store.now()}
                      if owner else None),
        "review_context": rc,
        "lifecycle": {"canonical": canonical, "jira_column": board.column_for(sid),
                      "jira_status_id": sid, "jira_status_name": board.name_for(sid),
                      "observed_at": store.now(), "source": "jira"},
        "execution_profile": {
            "required_capability": capability, "work_effort": 1,
            "validation_route": route, "completion_route": "DONE",
            "characteristics": {}, "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "completion_route"],
            "provenance": {"required_capability": {"by": "po", "at": store.now()}}},
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }
    with open(store.path_for("task", key), "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


def ev(seat, ref, at="2026-09-08T00:00:00Z"):
    return {"seat_id": seat, "evidence_ref": ref, "evidenced_at": at}


TMP = fresh_runtime()
SBC = fresh_roster()

# The two real entries, verbatim in shape: a sizing line and a delivery.
SIZING = ev("backend-3", "agent/status/backend-3.md:31 — 'KAN-136 part 1: sitting count'")
DELIVERY = ev("backend-1", "Jira comment 10839: pt.1 design delivered; read-only, no diff",
              "2026-09-09T19:24:34Z")

section("THE DEFECT, REPRODUCED — sizing counted as execution")

t = mk("KAN-901", evidence=[SIZING, DELIVERY])
ok("[reproduction] before reconciliation, BOTH seats read as executors",
   store.evidenced_executors(t) == ["backend-1", "backend-3"])
raises("[reproduction] and the SELF review cannot open — a completed item is stuck",
       lambda: store.open_review_context("KAN-901", t["revision"], opened_by="orchestrator"),
       "conflicting-executor-evidence")
ok("[reproduction] queue calls it conflicting-evidence too",
   "conflicting-evidence" in q.unclaimable_reasons(t))

section("1-3 — ASSESSMENT ESTABLISHES NO EXECUTOR IDENTITY")

r = store.classify_executor_evidence("KAN-901", t["revision"], "backend-3",
                                     "assessment", "ceo",
                                     "Preflight sizing act, not execution")
ok("[1] Preflight sizing does not establish executor evidence",
   "backend-3" not in store.evidenced_executors(r))
ok("[2] assessment without a claim leaves exactly the real executor",
   store.evidenced_executors(r) == ["backend-1"])
ok("[3] and the conflicting-evidence predicate clears",
   "conflicting-evidence" not in q.unclaimable_reasons(r))

section("4 — REAL EXECUTION STILL ESTABLISHES PROVENANCE")

ok("[4] the genuine execution entry is untouched and still counts",
   store.evidenced_executors(r) == ["backend-1"])
real = [e for e in r["executor_evidence"] if e["seat_id"] == "backend-1"][0]
ok("[4] it carries no classification marker at all — the default is execution",
   "classification" not in real)
t2 = mk("KAN-902", evidence=[DELIVERY])
ok("[4] an unclassified record behaves exactly as before the change",
   store.evidenced_executors(t2) == ["backend-1"])

section("5-6 — THE HISTORICAL RECORD SURVIVES")

kept = [e for e in r["executor_evidence"] if e["seat_id"] == "backend-3"][0]
ok("[5] the assessment entry is still present", kept is not None)
ok("[5] its seat_id is unchanged", kept["seat_id"] == SIZING["seat_id"])
ok("[5] its evidence_ref is byte-identical — the status line is still readable",
   kept["evidence_ref"] == SIZING["evidence_ref"])
ok("[5] its original evidenced_at is unchanged — history is not restamped",
   kept["evidenced_at"] == SIZING["evidenced_at"])
ok("[6] reconciliation DELETED nothing — both entries remain",
   len(r["executor_evidence"]) == 2)
ok("[6] and it records WHO reconciled and WHY",
   kept["classified_by"] == "ceo" and "Preflight sizing" in kept["classification_reason_ref"])

section("7 — EXECUTION DERIVATION IGNORES IT, EVERYWHERE IT IS WRITTEN")

ok("[7] store.evidenced_executors ignores it",
   "backend-3" not in store.evidenced_executors(r))
ok("[7] queue's conflicting-evidence predicate ignores it",
   "conflicting-evidence" not in q.unclaimable_reasons(r))
errs = validate.validate_record("task", dict(r, review_context={
    "review_type": "self", "review_result": "pending", "review_cycle": 1,
    "review_owner": "backend-1", "started_at": store.now()}))
ok("[14] AND the VALIDATOR ignores it — the rule lives in three places, and the "
   "reconciliation still failed the first time because this copy was missed",
   not [e for e in errs if "distinct evidenced executors" in e])

section("8-9 — AUTHORITY")

t3 = mk("KAN-903", evidence=[SIZING, DELIVERY])
for bad in ("backend-3", "backend-1", "po", "qa", "worker:backend-3"):
    raises("[8] %r cannot reclassify evidence" % bad,
           lambda b=bad: store.classify_executor_evidence(
               "KAN-903", t3["revision"], "backend-3", "assessment", b, "why"),
           "not-an-evidence-authority")
ok("[9] the CEO can", store.classify_executor_evidence(
    "KAN-903", t3["revision"], "backend-3", "assessment", "ceo", "sizing")
   ["executor_evidence"][0]["classification"] == "assessment")
t4 = mk("KAN-904", evidence=[SIZING, DELIVERY])
ok("[9] and the orchestrator can — verifying ownership coherence is its duty",
   store.classify_executor_evidence("KAN-904", t4["revision"], "backend-3",
                                    "assessment", "orchestrator", "sizing")
   ["executor_evidence"][0]["classification"] == "assessment")

section("10-11 — IT REACHES NOTHING ELSE")

t5 = mk("KAN-905", evidence=[SIZING, DELIVERY], owner=None,
        rc={"review_type": "self", "review_result": "pending", "review_cycle": 1,
            "review_owner": None, "started_at": store.now()})
before = json.dumps({k: v for k, v in t5.items()
                     if k not in ("executor_evidence", "revision", "updated_at")},
                    sort_keys=True)
r5 = store.classify_executor_evidence("KAN-905", t5["revision"], "backend-3",
                                      "assessment", "ceo", "sizing")
after = json.dumps({k: v for k, v in r5.items()
                    if k not in ("executor_evidence", "revision", "updated_at")},
                   sort_keys=True)
ok("[10] no Jira field is touched — lifecycle is byte-identical", before == after)
ok("[11] no review result is fabricated",
   r5["review_context"]["review_result"] == "pending")
ok("[11] no ownership is created", r5["ownership"] is None)
ok("[10] the record carries no Jira-mutating field", "jira_status_id" not in r5)

section("12 — A KAN-136-SHAPED RECORD BECOMES REVIEWABLE, BUT ONLY GENUINELY")

t6 = mk("KAN-906", evidence=[SIZING, DELIVERY])
r6 = store.classify_executor_evidence("KAN-906", t6["revision"], "backend-3",
                                      "assessment", "ceo", "sizing")
opened = store.open_review_context("KAN-906", r6["revision"], opened_by="orchestrator")
ok("[12] SELF opens once the false executor is reconciled",
   opened["review_context"]["review_type"] == "self")
ok("[12] and its owner is the REAL executor, derived not chosen",
   opened["review_context"]["review_owner"] == "backend-1")

# The other direction: reconcile away the only genuine executor and SELF must NOT open.
t7 = mk("KAN-907", evidence=[SIZING])
r7 = store.classify_executor_evidence("KAN-907", t7["revision"], "backend-3",
                                      "assessment", "ceo", "sizing")
ok("[12] with ONLY an assessment entry, no executor is evidenced",
   store.evidenced_executors(r7) == [])
raises("[12] and SELF must NOT open — reconciliation never manufactures an executor",
       lambda: store.open_review_context("KAN-907", r7["revision"], opened_by="orchestrator"),
       "")

section("PROMOTION IS IMPOSSIBLE — the direction that would recreate the defect")

t8 = mk("KAN-908", evidence=[SIZING])
raises("[8] evidence cannot be reclassified INTO execution",
       lambda: store.classify_executor_evidence("KAN-908", t8["revision"], "backend-3",
                                                "execution", "ceo", "promote"),
       "promote-refused")
raises("[8] an unknown classification is refused",
       lambda: store.classify_executor_evidence("KAN-908", t8["revision"], "backend-3",
                                                "verified", "ceo", "x"),
       "unknown classification")
raises("[8] a reclassification with no reason is refused",
       lambda: store.classify_executor_evidence("KAN-908", t8["revision"], "backend-3",
                                                "assessment", "ceo", ""),
       "reason_ref is required")
raises("[8] naming an entry that does not exist is refused",
       lambda: store.classify_executor_evidence("KAN-908", t8["revision"], "backend-4",
                                                "assessment", "ceo", "x"),
       "no-such-evidence")
t9 = mk("KAN-909", evidence=[ev("backend-3", "first", "2026-09-08T00:00:00Z"),
                             ev("backend-3", "second", "2026-09-08T01:00:00Z")])
raises("[8] two entries for one seat is AMBIGUOUS — reclassifying the wrong one is "
       "not recoverable, so it refuses rather than guessing",
       lambda: store.classify_executor_evidence("KAN-909", t9["revision"], "backend-3",
                                                "assessment", "ceo", "x"),
       "ambiguous-evidence")
ok("[8] naming the exact entry resolves the ambiguity",
   store.classify_executor_evidence("KAN-909", t9["revision"], "backend-3",
                                    "assessment", "ceo", "x",
                                    evidenced_at="2026-09-08T01:00:00Z")
   is not None)

section("THE FILE IS GUARDED TOO — a hand-edited record reaches only the validator")

bad = mk("KAN-910", evidence=[dict(SIZING, classification="assessment")])
errs = validate.validate_record("task", bad)
ok("[8] a classification with no authority is refused by the validator",
   any("not an evidence authority" in e for e in errs))
bad2 = mk("KAN-911", evidence=[dict(SIZING, classification="assessment",
                                    classified_by="ceo")])
ok("[8] a classification with no reason is refused by the validator",
   any("no classification_reason_ref" in e for e in validate.validate_record("task", bad2)))
bad3 = mk("KAN-912", evidence=[dict(SIZING, classification="invented",
                                    classified_by="ceo",
                                    classification_reason_ref="x")])
ok("[8] an unknown classification is refused by the validator",
   any("unknown evidence classification" in e for e in validate.validate_record("task", bad3)))

section("13 — PEER ELIGIBILITY: the other direction the defect broke")

t10 = mk("KAN-913", route="peer", sid="10045",
         evidence=[ev("backend-5" if "backend-5" in SBC.get("backend", []) else "backend-4",
                      "status:57 — 'sized: 2 sittings, ceiling 3'"),
                   ev("backend-2", "Jira: delivered", "2026-09-09T20:09:32Z")])
sizer = t10["executor_evidence"][0]["seat_id"]
ok("[13] before reconciliation the SIZING seat is treated as an executor",
   sizer in store.evidenced_executors(t10))
r10 = store.classify_executor_evidence("KAN-913", t10["revision"], sizer,
                                       "assessment", "ceo", "sizing act")
ok("[13] after it, only the real executor is evidenced — the sizer is eligible to "
   "review work it never touched",
   store.evidenced_executors(r10) == ["backend-2"])
ok("[13] and the real executor is still correctly excluded from reviewing itself",
   "backend-2" in store.evidenced_executors(r10))

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(summary())
