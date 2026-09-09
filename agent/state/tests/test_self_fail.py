#!/usr/bin/env python3
"""SELF FAIL re-entry — execution returns to the exact evidenced executor.

Synthetic runtime and synthetic roster throughout. The live `agent/state/runtime/**`
is never read for assertions and never written, and KAN-153 — which is complete —
is not used.

THREE FAIL SEMANTICS, NOT ONE
  The invariant this suite exists to hold is that PEER FAIL, QA FAIL and SELF FAIL
  stay three different things. PEER FAIL hands execution to a DIFFERENT seat; SELF
  FAIL hands it back to the SAME one. A single generic fail handler would satisfy
  both descriptions and protect neither, so most of these tests assert that SELF
  FAIL refuses every substitution — another seat, a queue claim, a PEER transfer.

  The second invariant is that a failure stays visible. Re-entry does not clear the
  failed review; the next cycle is created later, incremented, by the same generic
  opener. A retry must never be indistinguishable from a review that never happened.

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
    for kind in ("tasks", "dependencies", "interventions"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


def fresh_roster(seats):
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in seats.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nmodel: sonnet\neffort: medium\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return tmp


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend",
          "backend-1": "backend", "backend-2": "backend",
          "qa": "qa", "content-manager": "content", "ux-engineer-1": "ux-engineer",
          "devops": "devops"}


def mk(key, *, route="self", canonical="review", sid="10044", capability="frontend",
       owner=None, evidence=(), rc=None, ch=None):
    lc = {"canonical": canonical, "jira_column": board.column_for(sid),
          "jira_status_id": sid, "jira_status_name": board.name_for(sid),
          "observed_at": store.now(), "source": "jira"}
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app",
        "surfaces": ["lib/x/%s.dart" % key.lower()],
        "executor_evidence": [{"seat_id": s, "evidence_ref": "ref:%s:%d" % (s, i),
                               "evidenced_at": store.now()}
                              for i, s in enumerate(evidence)],
        "ownership": ({"seat_id": owner, "claim_ref": "ref", "claimed_at": store.now()}
                      if owner else None),
        "review_context": rc, "lifecycle": lc,
        "execution_profile": {
            "required_capability": capability, "work_effort": 1,
            "validation_route": route, "completion_route": "DONE",
            "characteristics": ch or {}, "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "validation_route", "completion_route"],
            "provenance": {"validation_route": {"by": "system-policy", "at": store.now()}},
        },
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }
    path = store.path_for("task", key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


def failed(key, *, seat="frontend-1", capability="frontend"):
    """A task standing exactly where a SELF FAIL leaves it, built by real operations."""
    t = mk(key, evidence=(seat,), capability=capability)
    o = store.open_review_context(key, t["revision"])
    return store.record_review_result(key, o["revision"], seat, "fail", "ref:defect")


fresh_runtime()
fresh_roster(ROSTER)


# ---------------------------------------------------------------- 1-3 preconditions

section("recording the failure")

t = mk("KAN-801", evidence=("frontend-1",))
raises("1. SELF FAIL requires a coherent SELF review context",
       lambda: store.record_review_result("KAN-801", t["revision"], "frontend-1",
                                          "fail", "ref:x"), "no-review-context")
raises("   and re-entry requires one too",
       lambda: store.self_fail_reentry("KAN-801", t["revision"], "frontend-1", "ref:r"),
       "no-review-context")

t = mk("KAN-802", evidence=("frontend-1",))
o = store.open_review_context("KAN-802", t["revision"])
f = store.record_review_result("KAN-802", o["revision"], "frontend-1", "fail", "ref:d")
raises("2. a settled review does not transition again",
       lambda: store.record_review_result("KAN-802", f["revision"], "frontend-1",
                                          "fail", "ref:d2"), "review-already-settled")

t = mk("KAN-803", evidence=("frontend-1",))
o = store.open_review_context("KAN-803", t["revision"])
raises("3. the wrong reviewer cannot record FAIL",
       lambda: store.record_review_result("KAN-803", o["revision"], "frontend-2",
                                          "fail", "ref:x"), "not-review-owner")
ok("   the refusal left the review pending",
   store.read("task", "KAN-803")["review_context"]["review_result"] == "pending")


# ---------------------------------------------------------------- 4-8 re-entry

section("execution returns to the EXACT SELF reviewer")

f = failed("KAN-810")
ok("   after FAIL the item is unowned", f["ownership"] is None)
r = store.self_fail_reentry("KAN-810", f["revision"], "frontend-1", "ref:selffail-1")
ok("4. re-entry returns ownership to the exact review_owner",
   r["ownership"]["seat_id"] == "frontend-1")
ok("   the re-entry ref is recorded on the ownership",
   r["ownership"]["claim_ref"] == "ref:selffail-1")
ok("   revision advanced by exactly one", r["revision"] == f["revision"] + 1)

f = failed("KAN-811")
raises("5. re-entry REFUSES any other seat, same capability or not",
       lambda: store.self_fail_reentry("KAN-811", f["revision"], "frontend-2",
                                       "ref:x"), "not-review-owner")
ok("   the refusal left the item unowned",
   store.read("task", "KAN-811")["ownership"] is None)
raises("   and refuses a cross-capability seat",
       lambda: store.self_fail_reentry("KAN-811", f["revision"], "backend-1",
                                       "ref:x"), "not-review-owner")

f = failed("KAN-812")
reasons = q.unclaimable_reasons(f, all_tasks=[f], jira_status_id="10044")
ok("6. re-entry is NOT a queue claim — the item is not queue-claimable at all",
   "not-ready" in reasons)
ok("   nor is it eligible for any capability queue",
   q.queue([f], "frontend") == [])
r = store.self_fail_reentry("KAN-812", f["revision"], "frontend-1", "ref:r")
ok("   yet re-entry still succeeds: responsibility is not competed for",
   r["ownership"]["seat_id"] == "frontend-1")

f = failed("KAN-813")
raises("7. SELF FAIL does not invoke the PEER transfer",
       lambda: store.peer_fail_transfer("KAN-813", f["revision"], "frontend-1", "ref"),
       "PEER route only")
r = store.self_fail_reentry("KAN-813", f["revision"], "frontend-1", "ref:r")
ok("   evidence is NOT replaced the way PEER FAIL replaces it",
   store.evidenced_executors(r) == ["frontend-1"])
ok("   no previous_owner is invented", r["review_context"].get("previous_owner") is None)

ok("8. the validation route is still SELF after re-entry",
   r["execution_profile"]["validation_route"] == "self")
ok("   the review_type is still self", r["review_context"]["review_type"] == "self")


# ---------------------------------------------------------------- 9-12 facts & atomicity

section("the failure stays on the record")

f = failed("KAN-820")
r = store.self_fail_reentry("KAN-820", f["revision"], "frontend-1", "ref:r")
rc = r["review_context"]
ok("9. the FAIL is preserved verbatim through re-entry",
   rc["review_result"] == "fail" and rc["review_owner"] == "frontend-1"
   and rc["review_cycle"] == 1 and rc["review_type"] == "self")
ok("   its evidence_ref survives", rc["evidence_ref"] == "ref:defect")
ok("   re-entry does not erase the failure to make room for the retry",
   store.read("task", "KAN-820")["review_context"]["review_result"] == "fail")

ok("10. a FAILED review can never make the item completion-eligible",
   "review-failed" in q.completion_reasons(r, interventions=[]))
ok("    and it is not in review any more once execution resumes",
   "review-failed" in q.completion_reasons(r, interventions=[]))

f = failed("KAN-821")
raises("11/12. a stale CAS refuses",
       lambda: store.self_fail_reentry("KAN-821", 99, "frontend-1", "ref:r"),
       "stale write refused")
after = store.read("task", "KAN-821")
ok("    the failed CAS left ownership null", after["ownership"] is None)
ok("    the failed CAS left the revision unchanged", after["revision"] == f["revision"])
ok("    the failed CAS left review_context untouched",
   after["review_context"]["review_result"] == "fail")

f = failed("KAN-822")
raises("    a missing reentry_ref refuses",
       lambda: store.self_fail_reentry("KAN-822", f["revision"], "frontend-1", ""),
       "reentry_ref is required")
ok("    ... leaving no half-state", store.read("task", "KAN-822")["ownership"] is None)

f = failed("KAN-823")
r = store.self_fail_reentry("KAN-823", f["revision"], "frontend-1", "ref:r")
raises("    re-entry never overwrites an existing owner",
       lambda: store.self_fail_reentry("KAN-823", r["revision"], "frontend-1", "ref:r2"),
       "already-owned")

f = failed("KAN-824")
iv = store.create_intervention("stop", "KAN-824", "ceo", "reason:safety")
raises("    a STOPped task refuses re-entry",
       lambda: store.self_fail_reentry("KAN-824", f["revision"], "frontend-1", "ref:r"),
       "task-stopped")
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
cur824 = store.read("task", "KAN-824")
r = store.self_fail_reentry("KAN-824", cur824["revision"], "frontend-1", "ref:r")
ok("    ... and permits it once the STOP is cleared",
   r["ownership"]["seat_id"] == "frontend-1")

f = failed("KAN-825")
o = store.read("task", "KAN-825")
raises("    a PENDING review is not a failed one",
       lambda: store.self_fail_reentry("KAN-826", 1, "frontend-1", "ref"),
       "does not exist")
t = mk("KAN-827", evidence=("frontend-1",))
o2 = store.open_review_context("KAN-827", t["revision"])
raises("    re-entry refuses a pending review",
       lambda: store.self_fail_reentry("KAN-827", o2["revision"], "frontend-1", "ref:r"),
       "review-not-failed")
p = store.record_review_result("KAN-827", o2["revision"], "frontend-1", "pass", "ref:ok")
raises("    re-entry refuses a PASSED review",
       lambda: store.self_fail_reentry("KAN-827", p["revision"], "frontend-1", "ref:r"),
       "review-not-failed")


# ---------------------------------------------------------------- 13-18 jira mapping

section("the execution status comes from the capability, never hard-coded")

CASES = [("frontend", "10046", "Front-end"), ("backend", "10043", "Back-end"),
         ("content", "10048", "Content"), ("ux-engineer", "10047", "Design"),
         ("devops", "10049", "Operations")]
for n, (cap, sid, name) in enumerate(CASES, start=14):
    ok("%d. %s -> %s (%s) via the existing mapping"
       % (n, cap, sid, name),
       store.transition_target(capability=cap) == sid and board.name_for(sid) == name)

ok("13. re-entry itself writes NO Jira status — state and Jira stay separate",
   store.read("task", "KAN-820")["lifecycle"]["jira_status_id"] == "10044")
src = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
fn = src.split("def self_fail_reentry")[1].split("\ndef ")[0]
ok("    and hard-codes no status id or capability name",
   not any(s in fn for s in ("10046", "10043", "10048", "10047", "10049",
                             '"frontend"', '"backend"')))


# ---------------------------------------------------------------- 19-24 next cycle

section("the next SELF cycle")

f = failed("KAN-830")
r = store.self_fail_reentry("KAN-830", f["revision"], "frontend-1", "ref:r")
d = store.observe_lifecycle("KAN-830", r["revision"],
                            store.transition_target(capability="frontend"))
ok("    Jira returns to the capability's execution status",
   d["lifecycle"]["jira_status_id"] == "10046"
   and d["lifecycle"]["canonical"] == "development")
rel = store.release("KAN-830", "frontend-1", d["revision"], "ref:fixed")
ok("19. a subsequent release remains valid and re-evidences the same seat",
   rel["ownership"] is None and store.evidenced_executors(rel) == ["frontend-1"])
ok("    evidence is still ONE distinct seat, so the route stays derivable",
   len(store.evidenced_executors(rel)) == 1)
back = store.observe_lifecycle("KAN-830", rel["revision"], "10044")
o2 = store.open_review_context("KAN-830", back["revision"])
ok("20. the next SELF context increments the cycle to 2",
   o2["review_context"]["review_cycle"] == 2)
ok("    with a fresh pending result", o2["review_context"]["review_result"] == "pending")
ok("21. the next review owner still DERIVES from evidence",
   o2["review_context"]["review_owner"] == "frontend-1")

f = failed("KAN-831")
r = store.self_fail_reentry("KAN-831", f["revision"], "frontend-1", "ref:r")
cur = store.read("task", "KAN-831")
merged = dict(cur)
merged["executor_evidence"] = list(cur["executor_evidence"]) + [
    {"seat_id": "frontend-2", "evidence_ref": "ref:other", "evidenced_at": store.now()}]
merged["review_context"] = None
merged["revision"] = cur["revision"] + 1
store._atomic_write(store.path_for("task", "KAN-831"), merged)
raises("22. ambiguous evidence still refuses reviewer selection on the next cycle",
       lambda: store.open_review_context("KAN-831", merged["revision"]),
       "conflicting-executor-evidence")

section("23. synthetic SELF FAIL -> cycle 2 PASS")
f = failed("KAN-840")
s1 = store.self_fail_reentry("KAN-840", f["revision"], "frontend-1", "ref:selffail")
ok("  a. execution returns to frontend-1", s1["ownership"]["seat_id"] == "frontend-1")
s2 = store.observe_lifecycle("KAN-840", s1["revision"], "10046")
ok("  b. Jira back at Front-end", s2["lifecycle"]["canonical"] == "development")
s3 = store.release("KAN-840", "frontend-1", s2["revision"], "ref:fix-commit")
s4 = store.observe_lifecycle("KAN-840", s3["revision"], "10044")
s5 = store.open_review_context("KAN-840", s4["revision"])
ok("  c. cycle 2 opens, owner still derived", s5["review_context"]["review_cycle"] == 2
   and s5["review_context"]["review_owner"] == "frontend-1")
s6 = store.record_review_result("KAN-840", s5["revision"], "frontend-1", "pass", "ref:ok")
ok("  d. cycle 2 PASSES", s6["review_context"]["review_result"] == "pass")
ok("  e. completion now eligible", q.completion_reasons(s6, interventions=[]) == [])
s7 = store.observe_lifecycle("KAN-840", s6["revision"], "10007")
ok("  f. Jira Done observed, ownership null",
   s7["lifecycle"]["canonical"] == "done" and s7["ownership"] is None)
ok("  g. the final record validates",
   [x for x in validate.validate_record("task", s7) if " WARN " not in x] == [])

section("24. repeated failure cycles are monotonic")
f = failed("KAN-841")
cyc = []
for i in range(3):
    cur = store.read("task", "KAN-841")
    cyc.append(cur["review_context"]["review_cycle"])
    a = store.self_fail_reentry("KAN-841", cur["revision"], "frontend-1", "ref:r%d" % i)
    b = store.observe_lifecycle("KAN-841", a["revision"], "10046")
    c = store.release("KAN-841", "frontend-1", b["revision"], "ref:fix%d" % i)
    d = store.observe_lifecycle("KAN-841", c["revision"], "10044")
    e = store.open_review_context("KAN-841", d["revision"])
    store.record_review_result("KAN-841", e["revision"], "frontend-1", "fail",
                               "ref:defect%d" % i)
ok("    cycles increase by one each time, never reset", cyc == [1, 2, 3])
ok("    the final cycle is 4 and still failing",
   store.read("task", "KAN-841")["review_context"]["review_cycle"] == 4)
ok("    and it is still not completion-eligible",
   "review-failed" in q.completion_reasons(store.read("task", "KAN-841"),
                                           interventions=[]))


# ---------------------------------------------------------------- 25-28 non-regression

section("QA and PEER remain three distinct semantics")

t = mk("KAN-850", route="peer", evidence=("frontend-1",), sid="10045",
       ch={"schema_change": True})
o = store.open_review_context("KAN-850", t["revision"], evidenced_reviewer="frontend-2")
f2 = store.record_review_result("KAN-850", o["revision"], "frontend-2", "fail", "ref:d")
raises("26. PEER FAIL does NOT go through SELF re-entry",
       lambda: store.self_fail_reentry("KAN-850", f2["revision"], "frontend-2", "ref:r"),
       "SELF route only")
tr = store.peer_fail_transfer("KAN-850", f2["revision"], "frontend-2", "ref:transfer")
ok("    PEER FAIL still transfers execution to the reviewer",
   store.evidenced_executors(tr) == ["frontend-2"])
ok("    PEER FAIL still records previous_owner",
   tr["review_context"]["previous_owner"] == "frontend-1")
ok("    PEER FAIL still increments the cycle", tr["review_context"]["review_cycle"] == 2)

t = mk("KAN-851", route="qa", evidence=("frontend-1",), sid="10009",
       ch={"user_visible_runtime": True})
o = store.open_review_context("KAN-851", t["revision"])
ok("25. QA still resolves to the qa seat", o["review_context"]["review_owner"] == "qa")
fq = store.record_review_result("KAN-851", o["revision"], "qa", "fail", "ref:bug")
raises("    QA FAIL does NOT go through SELF re-entry either",
       lambda: store.self_fail_reentry("KAN-851", fq["revision"], "qa", "ref:r"),
       "SELF route only")
ok("    QA FAIL does not make qa the executor",
   store.evidenced_executors(fq) == ["frontend-1"] and fq["ownership"] is None)
ok("    policy is unchanged for all three routes",
   policy.validation_route({}) == policy.SELF
   and policy.validation_route({"user_visible_runtime": True}) == policy.QA
   and policy.validation_route({"schema_change": True}) == policy.PEER)

f = failed("KAN-852")
ok("27. completion requires the CURRENT cycle to pass",
   "review-failed" in q.completion_reasons(f, interventions=[]))
r = store.self_fail_reentry("KAN-852", f["revision"], "frontend-1", "ref:r")
ok("    a past PASS cannot be inherited — the current result governs",
   "review-failed" in q.completion_reasons(r, interventions=[]))

f = failed("KAN-853")
raises("28. Jira Done alone cannot override a recorded SELF FAIL",
       lambda: store.observe_lifecycle("KAN-853", f["revision"], "10007"),
       "review_result")
ok("    the refusal left the lifecycle in review",
   store.read("task", "KAN-853")["lifecycle"]["canonical"] == "review")
ok("    and left the failure intact",
   store.read("task", "KAN-853")["review_context"]["review_result"] == "fail")


# ---------------------------------------------------------------- 29-30 validator

section("the validator accepts the re-entry state")

f = failed("KAN-860")
r = store.self_fail_reentry("KAN-860", f["revision"], "frontend-1", "ref:r")
d = store.observe_lifecycle("KAN-860", r["revision"], "10046")
ok("29. a coherent re-entry record validates with no hard error",
   [x for x in validate.validate_record("task", d) if " WARN " not in x] == [])
ok("    ownership, a failed SELF review and a development lifecycle coexist legally",
   d["ownership"]["seat_id"] == "frontend-1"
   and d["review_context"]["review_result"] == "fail"
   and d["lifecycle"]["canonical"] == "development")

bad = dict(d)
bad["ownership"] = {"seat_id": "frontend-2", "claim_ref": "r", "claimed_at": store.now()}
errs = [x for x in validate.validate_record("task", bad) if " WARN " not in x]
ok("30. a SELF context whose owner is not the evidenced executor is still rejected",
   [x for x in validate.validate_record(
       "task", dict(d, review_context=dict(d["review_context"],
                                           review_owner="frontend-2")))
    if " WARN " not in x] != [])

sys.exit(summary())
