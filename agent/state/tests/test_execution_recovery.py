#!/usr/bin/env python3
"""Recovering ORPHANED execution work to Ready.

Synthetic runtime and synthetic roster throughout. No live Jira call, no Product file.

THE STATE, AND HOW IT ARISES
  An executable item in a capability execution status with `ownership: null`. The
  validator accepts it and `claim` refuses it, so until now nothing could move it.
  It is not residue: `release` clears ownership without touching Jira, and release is
  deliberately permitted under STOP because a STOP must not trap ownership. Test 39
  reproduces that exact escape — the documented way out of a STOP produced a state
  with no documented way out of its own.

WHAT THESE TESTS DEFEND
  That recovery returns work to the QUEUE, never to a seat. `executor_evidence` is
  history, not assignment authority, and the largest group of assertions below checks
  that the previous executor gets no preference of any kind: it is not restored, not
  preferred, and another same-capability seat may take the work first. If recovery
  ever restored ownership from evidence, history would silently become authority.

Stdlib only.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

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
          "backend-1": "backend", "backend-2": "backend",
          "content-manager": "content", "ux-engineer-1": "ux-engineer",
          "devops": "devops", "qa": "qa", "po": "po"}


def fresh_roster():
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in ROSTER.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return validate.seats_by_capability()


REF = "po:recover-orphaned-execution"
FACTS = {"has_due_date": True, "has_acceptance_criteria": True}


def mk(key, *, capability="backend", sid="10043", canonical="development",
       owner=None, evidence=(), rc=None, route=None, ch=None, effort=1,
       surfaces=None, deps=None):
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app",
        "surfaces": ["supabase/%s.sql" % key.lower()] if surfaces is None else surfaces,
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
                                 "completion_route"],
            "provenance": {"required_capability": {"by": "po", "at": store.now()}},
        },
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }
    with open(store.path_for("task", key), "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


fresh_runtime()
SBC = fresh_roster()


def unchanged(key, before):
    cur = store.read("task", key)
    return (cur["revision"] == before["revision"]
            and cur["ownership"] == before["ownership"]
            and cur["executor_evidence"] == before["executor_evidence"]
            and cur["execution_profile"] == before["execution_profile"]
            and cur["lifecycle"] == before["lifecycle"])


# ---------------------------------------------------------------- 1-6 lanes

section("every capability execution lane is recoverable")

LANES = [("frontend", "10046", "Front-end"), ("backend", "10043", "Back-end"),
         ("content", "10048", "Content"), ("ux-engineer", "10047", "Design"),
         ("devops", "10049", "Operations")]
for n, (cap, sid, name) in enumerate(LANES, start=2):
    t = mk("KAN-50%d" % n, capability=cap, sid=sid, evidence=("backend-1",))
    r = store.recover_execution_to_ready("KAN-50%d" % n, t["revision"], REF, "po")
    ok("%d. %s orphaned in %s (%s) recovers" % (n, cap, name, sid),
       r["execution_recovery"]["from_status"] == sid)
ok("1. an orphaned execution item is recoverable at all",
   store.read("task", "KAN-502")["revision"] == 2)
ok("   the lane list came from board.py, not from a constant here",
   sorted({board.execution_status_for(c) for c, _, _ in LANES}) ==
   ["10043", "10046", "10047", "10048", "10049"])


# ---------------------------------------------------------------- 7-14 refusals

section("every refusal leaves the record untouched")

t = mk("KAN-510", owner="backend-1", evidence=("backend-1",))
raises("7. an OWNED item refuses — recovery never takes work from a current owner",
       lambda: store.recover_execution_to_ready("KAN-510", t["revision"], REF, "po"),
       "already-owned")
ok("   ... unchanged", unchanged("KAN-510", t))

t = mk("KAN-511", sid="10008", canonical="ready")
raises("8. an item already in Ready refuses",
       lambda: store.recover_execution_to_ready("KAN-511", t["revision"], REF, "po"),
       "not-orphaned-execution")

t = mk("KAN-512", sid="10004", canonical="ready")
raises("9. an item in Backlog refuses",
       lambda: store.recover_execution_to_ready("KAN-512", t["revision"], REF, "po"),
       "not-orphaned-execution")

t = mk("KAN-513", sid="10045", canonical="review")
raises("10. an item in a review status refuses",
       lambda: store.recover_execution_to_ready("KAN-513", t["revision"], REF, "po"),
       "not-orphaned-execution")

t = mk("KAN-514", sid="10007", canonical="done")
raises("11. a Done item refuses",
       lambda: store.recover_execution_to_ready("KAN-514", t["revision"], REF, "po"),
       "not-orphaned-execution")

t = mk("KAN-515", rc={"review_type": "self", "review_owner": "backend-1",
                      "review_result": "pending", "review_cycle": 1},
       route="self", evidence=("backend-1",))
raises("12. an active review context refuses — its route decides, not recovery",
       lambda: store.recover_execution_to_ready("KAN-515", t["revision"], REF, "po"),
       "review-in-progress")
ok("    ... unchanged", unchanged("KAN-515", t))

t = mk("KAN-516", evidence=("backend-1",))
raises("13. a stale CAS refuses",
       lambda: store.recover_execution_to_ready("KAN-516", 99, REF, "po"),
       "stale write refused")
ok("    ... unchanged", unchanged("KAN-516", t))

for bad in ("backend-1", "frontend-1", "cto", "orchestrator", "qa", ""):
    raises("14. actor %r may not recover lifecycle" % (bad or "<empty>"),
           lambda b=bad: store.recover_execution_to_ready("KAN-516", t["revision"],
                                                          REF, b),
           "unauthorised-recovery-actor")
ok("    an executor cannot reset its own work", unchanged("KAN-516", t))
raises("    a missing recovery_ref refuses",
       lambda: store.recover_execution_to_ready("KAN-516", t["revision"], "", "po"),
       "recovery_ref is required")
ok("    ceo is also an authority",
   store.recover_execution_to_ready("KAN-516", t["revision"], REF,
                                    "ceo")["revision"] == 2)


# ---------------------------------------------------------------- 15-24 preservation

section("recovery preserves everything and assigns nobody")

t = mk("KAN-520", capability="backend", evidence=("backend-1", "backend-2"),
       route="peer", ch={"schema_change": True}, effort=3,
       surfaces=["supabase/a.sql", "supabase/b.sql"])
store.create_dependency({"source_work_item": "KAN-521", "target_work_item": "KAN-520",
                         "relation": "BLOCKS", "completion_condition": "DONE",
                         "product_id": "dabbler", "created_by": "po", "reason_ref": "r"})
r = store.recover_execution_to_ready("KAN-520", t["revision"], REF, "po")
ok("15. the revision increments exactly once", r["revision"] == t["revision"] + 1)
ok("16. ownership remains null — recovery creates none", r["ownership"] is None)
ok("17. executor_evidence is preserved exactly",
   r["executor_evidence"] == t["executor_evidence"])
ok("18. the previous executor is NOT restored as owner", r["ownership"] is None)
ok("    both evidenced seats survive, neither is promoted",
   store.evidenced_executors(r) == ["backend-1", "backend-2"])
ok("19. a present validation_route is preserved",
   r["execution_profile"]["validation_route"] == "peer")
ok("21. characteristics preserved",
   r["execution_profile"]["characteristics"] == {"schema_change": True})
ok("22. surfaces preserved", r["surfaces"] == ["supabase/a.sql", "supabase/b.sql"])
ok("23. dependencies preserved",
   len([e for e in store.read_all("dependency") if not e.get("retired_at")]) == 1)
ok("24. Work Effort preserved", r["execution_profile"]["work_effort"] == 3)
ok("    the recovery is auditable — who, when, from where",
   set(r["execution_recovery"]) == {"by", "at", "recovery_ref", "from_status"})

t = mk("KAN-522", evidence=("backend-1",), route=None)
r = store.recover_execution_to_ready("KAN-522", t["revision"], REF, "po")
ok("20. a null validation_route stays null — nothing is fabricated",
   r["execution_profile"]["validation_route"] is None)


# ---------------------------------------------------------------- 25-27 interventions

section("interventions")

t = mk("KAN-530", evidence=("backend-1",))
iv = store.create_intervention("stop", "KAN-530", "ceo", "reason:safety")
raises("25. STOP blocks recovery",
       lambda: store.recover_execution_to_ready("KAN-530", t["revision"], REF, "po"),
       "task-stopped")
ok("    ... unchanged", unchanged("KAN-530", t))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
r = store.recover_execution_to_ready("KAN-530", t["revision"], REF, "po")
ok("    ... and permits it once cleared", r["revision"] == 2)

t = mk("KAN-531", evidence=("backend-1",))
iv = store.create_intervention("hold", "backend", "ceo", "reason:safety")
r = store.recover_execution_to_ready("KAN-531", t["revision"], REF, "po")
ok("26. HOLD does NOT block recovery — it gates claims, not reconciliation",
   r["revision"] == 2)
rd = store.observe_lifecycle("KAN-531", r["revision"], "10008")
ok("    but the recovered item is still unclaimable under HOLD",
   "capability-held" in q.unclaimable_reasons(rd, all_tasks=[rd], jira=dict(FACTS)))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")

t = mk("KAN-532", evidence=("backend-1",))
iv = store.create_intervention("freeze", None, "ceo", "reason:incident")
r = store.recover_execution_to_ready("KAN-532", t["revision"], REF, "po")
rd = store.observe_lifecycle("KAN-532", r["revision"], "10008")
ok("27. FREEZE does not block recovery, and does not fabricate claimability",
   "system-frozen" in q.unclaimable_reasons(rd, all_tasks=[rd], jira=dict(FACTS)))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")


# ---------------------------------------------------------------- 28-34 after recovery

section("after recovery: Ready is earned, not granted")

t = mk("KAN-540", evidence=("backend-1",), route="self")
r = store.recover_execution_to_ready("KAN-540", t["revision"], REF, "po")
ok("28. before the Jira observation the item is still NOT Ready",
   "not-ready" in q.unclaimable_reasons(r, all_tasks=[r], jira=dict(FACTS)))
rd = store.observe_lifecycle("KAN-540", r["revision"], "10008")
ok("    only the observed Jira Ready makes it ready",
   rd["lifecycle"]["canonical"] == "ready")
ok("32. a normal atomic claim works once genuinely ready",
   store.claim("KAN-540", "backend-2", "ref", rd["revision"],
               capability_of_seat="backend",
               jira_status_id="10008")["ownership"]["seat_id"] == "backend-2")
ok("33/34. the PREVIOUS executor had no preference — another seat took it",
   store.read("task", "KAN-540")["ownership"]["seat_id"] == "backend-2"
   and "backend-1" in store.evidenced_executors(store.read("task", "KAN-540")))

t = mk("KAN-541", evidence=("backend-1",))
r = store.recover_execution_to_ready("KAN-541", t["revision"], REF, "po")
rd = store.observe_lifecycle("KAN-541", r["revision"], "10008")
ok("29. recovered but missing due date -> still unclaimable",
   "missing-due-date" in q.unclaimable_reasons(
       rd, all_tasks=[rd], jira={"has_due_date": False,
                                 "has_acceptance_criteria": True}))
ok("30. recovered but missing acceptance criteria -> still unclaimable",
   "missing-acceptance-criteria" in q.unclaimable_reasons(
       rd, all_tasks=[rd], jira={"has_due_date": True,
                                 "has_acceptance_criteria": False}))
ok("31. a null validation profile cannot falsely complete",
   q.completion_reasons(rd, interventions=[]) != [])
ok("40. the recovered Ready record validates",
   [x for x in validate.validate_record("task", rd) if " WARN " not in x] == [])


# ---------------------------------------------------------------- 35-38 non-regression

section("the other routes are untouched")

t = mk("KAN-550", capability="frontend", sid="10046", evidence=("frontend-1",),
       route="self", canonical="review")
t2 = mk("KAN-551", capability="frontend", sid="10044", canonical="review",
        evidence=("frontend-1",), route="self")
so = store.open_review_context("KAN-551", t2["revision"])
sp = store.record_review_result("KAN-551", so["revision"], "frontend-1", "fail", "ref:x")
sr = store.self_fail_reentry("KAN-551", sp["revision"], "frontend-1", "ref:re")
ok("35. SELF FAIL re-entry is unchanged and still returns the SAME seat",
   sr["ownership"]["seat_id"] == "frontend-1")
raises("    recovery refuses it while Jira still shows the review status",
       lambda: store.recover_execution_to_ready("KAN-551", sr["revision"], REF, "po"),
       "not-orphaned-execution")
sd = store.observe_lifecycle("KAN-551", sr["revision"], "10046")
raises("    and refuses it in execution too — it is OWNED by the re-entered seat",
       lambda: store.recover_execution_to_ready("KAN-551", sd["revision"], REF, "po"),
       "already-owned")

t3 = mk("KAN-552", capability="frontend", sid="10045", canonical="review",
        evidence=("frontend-1",), route="peer", ch={"schema_change": True})
po_ = store.open_review_context("KAN-552", t3["revision"],
                                evidenced_reviewer="frontend-2")
pf = store.record_review_result("KAN-552", po_["revision"], "frontend-2", "fail", "r")
tr = store.peer_fail_transfer("KAN-552", pf["revision"], "frontend-2", "ref:t")
ok("36. PEER FAIL transfer unchanged", store.evidenced_executors(tr) == ["frontend-2"])

t4 = mk("KAN-553", capability="frontend", sid="10009", canonical="review",
        evidence=("frontend-1",), route="qa", ch={"user_visible_runtime": True})
qo = store.open_review_context("KAN-553", t4["revision"])
ok("37. QA path unchanged", qo["review_context"]["review_owner"] == "qa")

t5 = mk("KAN-554", capability="frontend", sid="10045", canonical="review",
        evidence=("frontend-1",), route="peer", ch={"schema_change": True})
w = store.open_review_context("KAN-554", t5["revision"])
res = store.resolve_review_owner("KAN-554", w["revision"], "frontend-2", "ceo:r")
ok("38. reviewer resolution unchanged",
   res["review_context"]["review_owner"] == "frontend-2")


# ---------------------------------------------------------------- 39 the STOP escape

section("39. the STOP escape, reproduced end to end")

fresh_runtime(); SBC = fresh_roster()
t = mk("KAN-560", capability="backend", evidence=(), owner="backend-1")
ok("  a. owned, executing in Back-end", t["ownership"]["seat_id"] == "backend-1")
iv = store.create_intervention("stop", "KAN-560", "ceo", "reason:collision-found")
raises("  b. STOP blocks continuation",
       lambda: store.assert_execution_permitted("KAN-560", "backend-1"), "task-stopped")
rel = store.release("KAN-560", "backend-1", t["revision"], "ref:released-under-stop")
ok("  c. release IS permitted under STOP — a STOP must not trap ownership",
   rel["ownership"] is None and store.evidenced_executors(rel) == ["backend-1"])
ok("  d. the item is now the orphaned shape the validator accepts",
   rel["lifecycle"]["canonical"] == "development"
   and [x for x in validate.validate_record("task", rel) if " WARN " not in x] == [])
ok("  e. and it is unclaimable — this was the trap",
   "not-ready" in q.unclaimable_reasons(rel, all_tasks=[rel], jira=dict(FACTS)))
raises("  f. recovery refuses while the STOP stands",
       lambda: store.recover_execution_to_ready("KAN-560", rel["revision"], REF, "po"),
       "task-stopped")
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
rec = store.recover_execution_to_ready("KAN-560", rel["revision"], REF, "po")
ok("  g. once RESUMEd, recovery is authorised", rec["ownership"] is None)
rdy = store.observe_lifecycle("KAN-560", rec["revision"], "10008")
ok("  h. Jira Ready observed -> canonical ready", rdy["lifecycle"]["canonical"] == "ready")
ok("  i. normal claimability restored",
   q.unclaimable_reasons(rdy, all_tasks=[rdy], jira=dict(FACTS)) == [])
c = store.claim("KAN-560", "backend-2", "ref", rdy["revision"],
                capability_of_seat="backend", jira_status_id="10008")
ok("  j. a normal atomic claim succeeds, and history did not pick the seat",
   c["ownership"]["seat_id"] == "backend-2"
   and store.evidenced_executors(c) == ["backend-1"])

src = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
fn = src.split("def recover_execution_to_ready")[1].split("\ndef ")[0]
code = "\n".join(l for l in fn.split("\n")
                 if not l.strip().startswith("#")).split('"""')[-1]
ok("  the operation CALLS no Jira machinery at store level",
   not any(w in code for w in ("transition_issue(", "observe_lifecycle(", "get_issue(")))
ok("  and never writes ownership",
   'merged["ownership"]' not in fn)

sys.exit(summary())
