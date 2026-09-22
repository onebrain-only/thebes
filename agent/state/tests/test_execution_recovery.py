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
from _harness import (fresh_seat_registry, ok, raises, section, summary, repo_root,
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
          "backend-1": "backend", "backend-2": "backend",
          "content-manager": "content", "ux-engineer-1": "ux-engineer",
          "devops": "devops", "qa": "qa", "po": "po"}


def fresh_roster():
    fresh_seat_registry(validate, ROSTER)
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

# ------------------------------------------- settled PASS + remediation_required
#
# KAN-292's deadlock: a SELF review settled PASS, ownership released, and the only
# integration receipt says `remediation_required`. Every door refuses — EXECUTE
# (`not-ready`), EXECUTE-in-Ready (the validator refuses a review context in Ready),
# VALIDATE (`validation-already-settled`), completion ("receipt still requires
# Product remediation") — and each refusal is correct. These tests pin the one exit.

section("a settled PASS whose integration demands remediation")

RREF = "po:recover-remediation-required"
READY = "10008"
SELF_RC = {"review_type": "self", "review_owner": "frontend-2",
           "review_result": "pass", "review_cycle": 3}


def rmk(key, *, rc=None, route="self", **kw):
    """Baseline S: frontend, Self-review (10044), settled PASS, unowned."""
    if rc is None:
        rc = dict(SELF_RC)
    return mk(key, capability="frontend", sid="10044", canonical="review",
              route=route, evidence=("frontend-2",), rc=rc, **kw)


def rcpt(key, *, outcome="integration-conflict", remediation=True, commit=None,
         created_at=None, seat_id="frontend-2",
         conflict_paths=("lib/src/navigation/tab_bar.dart",)):
    """One integration receipt. `created_at` is forced where a test needs an order:
    now() is second-precision, so two receipts written back to back would tie."""
    ev = {"product_commit": commit or ("commit:%s:%s" % (key, outcome)),
          "remediation_required": remediation,
          "conflict_paths": list(conflict_paths)}
    if outcome == "integrated":
        # A clean receipt has to be a REAL clean receipt or the validator refuses it.
        ev.update({"integrated_as": ev["product_commit"],
                   "integration_branch": "integration/%s" % key,
                   "previous_head": "head:%s" % key})
    r = store.record_integration_receipt(key, seat_id, outcome, ev)
    if created_at:
        r = dict(r)
        r["created_at"] = created_at
        store._atomic_write(
            store.path_for("integration_receipt", r["integration_receipt_id"]), r)
        r = store.read("integration_receipt", r["integration_receipt_id"])
    return r


def patch(key, **kw):
    """Write a shape the public API would refuse to construct."""
    rec = store.read("task", key)
    rec.update(kw)
    with open(store.path_for("task", key), "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


def rec_to_ready(key, rev, *, ref=RREF, actor="po", sid=READY):
    return store.recover_remediation_required_to_ready(key, rev, ref, actor, sid)


# --- 71-77. the happy path
t = rmk("KAN-600")
r0 = rcpt("KAN-600")
before = store.read("task", "KAN-600")
r = rec_to_ready("KAN-600", t["revision"])
ok("71. a settled SELF PASS with a remediation-required receipt recovers",
   r["review_context"] is None)
ok("72. lifecycle is the Ready status the caller read back from Jira",
   r["lifecycle"]["jira_status_id"] == READY
   and r["lifecycle"]["canonical"] == "ready"
   and r["lifecycle"]["source"] == "jira")
ok("73. the settled verdict is preserved VERBATIM, not summarised",
   r["execution_recovery"]["closed_review"] == SELF_RC
   and r["execution_recovery"]["from_status"] == "10044"
   and r["execution_recovery"]["by"] == "po"
   and r["execution_recovery"]["recovery_ref"] == RREF)
ok("74. the receipt that demanded the remediation is named",
   r["execution_recovery"]["remediation_receipt_id"] == r0["integration_receipt_id"])
ok("75. recovery creates no ownership — the item goes back to the QUEUE",
   r["ownership"] is None)
ok("76. execution_profile is byte-identical — the route is NOT recomputed",
   r["execution_profile"] == before["execution_profile"]
   and r["execution_profile"]["validation_route"] == "self")
ok("77. the revision advances by exactly one",
   r["revision"] == before["revision"] + 1)
ok("78. and the WRITTEN record validates — validate.py:392-393 refuses a review "
   "context in Ready, so this is the assertion that guards the whole transition",
   [x for x in validate.validate_record("task", store.read("task", "KAN-600"))
    if " WARN " not in x] == [])

t = rmk("KAN-601", rc={"review_type": "qa", "review_owner": "qa",
                       "review_result": "pass", "review_cycle": 1}, route="qa")
rcpt("KAN-601")
ok("79. a settled QA PASS reaches the same exit",
   rec_to_ready("KAN-601", t["revision"])["review_context"] is None)

# --- 80-84. the four pre-lock preconditions, and the record it never read
section("preconditions refuse everything that is not exactly this state")

t = rmk("KAN-602")
rcpt("KAN-602")
b = store.read("task", "KAN-602")
raises("80. expected_revision=None is refused — there is no force update",
       lambda: rec_to_ready("KAN-602", None), "expected_revision is required")
raises("81. an unnamed reason is refused",
       lambda: rec_to_ready("KAN-602", t["revision"], ref=""),
       "recovery_ref is required")
raises("82. an executor may not recover its own review state",
       lambda: rec_to_ready("KAN-602", t["revision"], actor="frontend-2"),
       "unauthorised-recovery-actor")
ok("   and nothing was written", unchanged("KAN-602", b))
raises("83. a status that is not Ready is refused — po transitions Jira FIRST",
       lambda: rec_to_ready("KAN-602", t["revision"], sid="10043"), "jira-not-ready")
ok("   still nothing was written", unchanged("KAN-602", b))
raises("84. an unknown work item is refused",
       lambda: rec_to_ready("KAN-NOPE", 1), "does not exist")
raises("85. a stale revision is refused",
       lambda: rec_to_ready("KAN-602", t["revision"] + 1), "stale write refused")
ok("   and the CAS failure wrote nothing", unchanged("KAN-602", b))

t = rmk("KAN-603")
rcpt("KAN-603")
patch("KAN-603", record_type="container")
raises("86. a container holds no review state to recover",
       lambda: rec_to_ready("KAN-603", t["revision"]),
       "container records hold no review state to recover")

# --- 87-89. it is a REVIEW recovery
t = mk("KAN-604", capability="frontend", sid="10043", canonical="development",
       route="self", rc=dict(SELF_RC))
rcpt("KAN-604")
b = store.read("task", "KAN-604")
raises("87. an item still in a development status is refused",
       lambda: rec_to_ready("KAN-604", t["revision"]), "not-in-review")
ok("   unchanged", unchanged("KAN-604", b))

t = mk("KAN-605", capability="frontend", sid="10011", canonical="done",
       route="self", rc=dict(SELF_RC))
rcpt("KAN-605")
b = store.read("task", "KAN-605")
raises("88. a DONE item is refused by the same check — no separate branch exists, "
       "because a dead branch only invites belief",
       lambda: rec_to_ready("KAN-605", t["revision"]), "not-in-review")
ok("   unchanged", unchanged("KAN-605", b))

# --- 89-93. the review context itself
t = mk("KAN-606", capability="frontend", sid="10044", canonical="review",
       route="self", evidence=("frontend-2",), rc=None)
rcpt("KAN-606")
b = store.read("task", "KAN-606")
raises("89. no review context — there is no settled review to close",
       lambda: rec_to_ready("KAN-606", t["revision"]), "no-review-context")
ok("   unchanged", unchanged("KAN-606", b))

t = rmk("KAN-607", rc="settled, honest")
rcpt("KAN-607")
raises("90. a review context that is not an object is refused the same way",
       lambda: rec_to_ready("KAN-607", t["revision"]), "no-review-context")

t = rmk("KAN-608", rc=dict(SELF_RC, review_type="peer"), route="peer")
rcpt("KAN-608")
b = store.read("task", "KAN-608")
raises("91. a PEER context is refused — it carries transfer semantics this "
       "transition does not reason about",
       lambda: rec_to_ready("KAN-608", t["revision"]), "not-a-self-or-qa-review")
ok("   unchanged", unchanged("KAN-608", b))

t = rmk("KAN-609", rc=dict(SELF_RC, review_result="fail"))
rcpt("KAN-609")
b = store.read("task", "KAN-609")
raises("92. a settled FAIL is refused — a FAIL has its own handlers",
       lambda: rec_to_ready("KAN-609", t["revision"]), "review-not-passed")
ok("   unchanged", unchanged("KAN-609", b))

t = rmk("KAN-610", rc=dict(SELF_RC, review_result="pending"))
rcpt("KAN-610")
raises("93. an UNSETTLED review is refused by the same check — only PASS recovers",
       lambda: rec_to_ready("KAN-610", t["revision"]), "review-not-passed")

# --- 94-95. ownership and completion
t = rmk("KAN-611", owner="frontend-2")
rcpt("KAN-611")
b = store.read("task", "KAN-611")
raises("94. recovery never takes work from a current owner",
       lambda: rec_to_ready("KAN-611", t["revision"]), "already-owned")
ok("   unchanged", unchanged("KAN-611", b))

t = rmk("KAN-612")
rcpt("KAN-612")
patch("KAN-612", completion_reconciliation={"by": "po", "at": store.now(),
                                            "completion_ref": "ref:done"})
b = store.read("task", "KAN-612")
raises("95. work recorded factually complete is never sent backward to Ready",
       lambda: rec_to_ready("KAN-612", b["revision"]), "already-reconciled-complete")
ok("   unchanged", unchanged("KAN-612", b))

# --- 96-99. the receipt is the whole reason this transition exists
section("the integration receipt decides, and LATEST wins")

t = rmk("KAN-613")
b = store.read("task", "KAN-613")
raises("96. no integration receipt — nothing records a remediation to perform",
       lambda: rec_to_ready("KAN-613", t["revision"]), "no-integration-receipt")
ok("   unchanged", unchanged("KAN-613", b))

t = rmk("KAN-614")
rcpt("KAN-614", outcome="integrated", remediation=False, conflict_paths=())
b = store.read("task", "KAN-614")
raises("97. a CLEAN receipt is refused — a settled PASS with a clean receipt "
       "completes, it is not recovered",
       lambda: rec_to_ready("KAN-614", t["revision"]), "no-remediation-required")
ok("   unchanged", unchanged("KAN-614", b))

t = rmk("KAN-615")
rcpt("KAN-615", created_at="2026-09-20T10:00:00Z")
rcpt("KAN-615", outcome="integrated", remediation=False, conflict_paths=(),
     created_at="2026-09-21T10:00:00Z")
b = store.read("task", "KAN-615")
raises("98. an OLD conflict under a NEW clean integration is refused — the "
       "remediation already happened; this is latest-wins, not any-matching",
       lambda: rec_to_ready("KAN-615", t["revision"]), "no-remediation-required")
ok("   unchanged", unchanged("KAN-615", b))

t = rmk("KAN-616")
rcpt("KAN-616", outcome="integrated", remediation=False, conflict_paths=(),
     created_at="2026-09-20T10:00:00Z")
newest = rcpt("KAN-616", created_at="2026-09-21T10:00:00Z")
r = rec_to_ready("KAN-616", t["revision"])
ok("99. and the inverse recovers, naming the NEWEST receipt",
   r["review_context"] is None
   and r["execution_recovery"]["remediation_receipt_id"]
   == newest["integration_receipt_id"])

# --- 100-102. interventions, and replay
section("STOP blocks; HOLD and FREEZE deliberately do not; replay is refused")

t = rmk("KAN-617")
rcpt("KAN-617")
iv = store.create_intervention("stop", "KAN-617", "ceo", "reason:collision-found")
b = store.read("task", "KAN-617")
raises("100. a STOP on the item blocks the recovery itself",
       lambda: rec_to_ready("KAN-617", t["revision"]), "task-stopped")
ok("   unchanged", unchanged("KAN-617", b))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
ok("   once RESUMEd it is authorised",
   rec_to_ready("KAN-617", t["revision"])["review_context"] is None)

t = rmk("KAN-618")
rcpt("KAN-618")
h = store.create_intervention("hold", "frontend", "ceo", "reason:safety")
f = store.create_intervention("freeze", None, "ceo", "reason:incident")
ok("101. HOLD and FREEZE do NOT block — they gate new CLAIMS, and recovery "
   "creates no ownership; the item simply sits in Ready unclaimable",
   rec_to_ready("KAN-618", t["revision"])["review_context"] is None)
store.clear_intervention(h["intervention_id"], h["revision"], "ceo")
store.clear_intervention(f["intervention_id"], f["revision"], "ceo")

raises("102. a replay against the new revision is refused — the item is in Ready "
       "now, and Ready is not a review status",
       lambda: rec_to_ready("KAN-600", store.read("task", "KAN-600")["revision"]),
       "not-in-review")

# --- 103. what the source text must never contain
rsrc = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
rfn = rsrc.split("def recover_remediation_required_to_ready")[1].split("\ndef ")[0]
rcode = "\n".join(l for l in rfn.split("\n")
                  if not l.strip().startswith("#")).split('"""')[-1]
ok("103. it never writes ownership — none is created, and none is restored",
   'merged["ownership"]' not in rcode)
ok("   and it never recomputes the validation route — the divergence from "
   "recover_failed_review_to_ready is deliberate and documented",
   "policy.validation_route" not in rcode)
ok("   nor does it call Jira machinery at store level",
   not any(w in rcode for w in ("transition_issue(", "observe_lifecycle(",
                                "get_issue(")))

sys.exit(summary())
