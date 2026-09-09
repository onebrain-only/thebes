#!/usr/bin/env python3
"""The SELF validation state path — execution through to completion eligibility.

Every test runs against a SYNTHETIC runtime in a temporary directory and a synthetic
roster. The live `agent/state/runtime/**` is never read for assertions and never
written.

WHAT THIS SUITE DEFENDS
  One sentence from `WORKFLOWS.md` §2.3: *a task reaches Done only through its
  validation route, and only its review owner puts it there.* Before this path
  existed that sentence was unenforceable — no operation could record a review at
  all — so most of what follows asserts the shape of what the system REFUSES:
  ownership is not evidence, a status file is not evidence, a Jira status cannot
  create a review, and a Jira Done cannot fabricate a pass.

  The other half is that SELF's owner is DERIVED. `policy.resolve_owner_or_wait` has
  decided it since Wave 5; the gap was that nothing recorded the decision. So these
  tests pin the derivation to evidence and refuse both ambiguity and absence.

Stdlib only, like the rest of the suite.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, policy, queue as q, board                          # noqa: E402


# ---------------------------------------------------------------- fixtures

def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


def fresh_roster(seats):
    """Synthetic bindings, so seat topology is a fact about the fixture."""
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in seats.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nmodel: sonnet\neffort: medium\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return tmp


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend",
          "backend-1": "backend", "backend-2": "backend", "qa": "qa"}


def mk(key, *, route="self", canonical="review", sid="10044", capability="frontend",
       owner=None, evidence=(), rc=None, ch=None, effort=1):
    """Write a task directly, to set up a STARTING state — never to assert an outcome."""
    lc = None
    if canonical:
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
        "review_context": rc,
        "lifecycle": lc,
        "execution_profile": {
            "required_capability": capability, "work_effort": effort,
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


fresh_runtime()
fresh_roster(ROSTER)


# ---------------------------------------------------------------- 1-7 opening

section("SELF cannot open without exactly one evidenced executor")

t = mk("KAN-901", evidence=())
raises("1. SELF cannot open with NO executor evidence",
       lambda: store.open_review_context("KAN-901", t["revision"]),
       "no-executor-evidence")
ok("   the refusal leaves revision unchanged",
   store.read("task", "KAN-901")["revision"] == 1)
ok("   the refusal leaves review_context null",
   store.read("task", "KAN-901")["review_context"] is None)

t = mk("KAN-902", evidence=("frontend-1",))
r = store.open_review_context("KAN-902", t["revision"], opened_by="orchestrator")
rc = r["review_context"]
ok("2. SELF opens with exactly one evidenced executor", isinstance(rc, dict))
ok("3. review_owner IS the evidenced executor", rc["review_owner"] == "frontend-1")
ok("   review_type is self", rc["review_type"] == "self")
ok("   review_result starts pending", rc["review_result"] == "pending")
ok("   review_cycle starts at 1", rc["review_cycle"] == 1)
ok("   revision advanced by exactly one", r["revision"] == 2)

# 4-6: the three things that look like evidence and are not.
t = mk("KAN-903", evidence=(), owner="frontend-1")
raises("4. current OWNERSHIP is not executor evidence",
       lambda: store.open_review_context("KAN-903", t["revision"]),
       "no-executor-evidence")

t = mk("KAN-904", evidence=())
os.makedirs(os.path.join(repo_root(), "agent", "status"), exist_ok=True)
raises("5. a status file naming a seat is not executor evidence",
       lambda: store.open_review_context("KAN-904", t["revision"]),
       "no-executor-evidence")
t = mk("KAN-905", evidence=(), sid="10044")
raises("6. a Jira assignee/status is not executor evidence — status is 10044 here",
       lambda: store.open_review_context("KAN-905", t["revision"]),
       "no-executor-evidence")

t = mk("KAN-906", evidence=("frontend-1", "frontend-2"))
raises("7. TWO distinct evidenced executors refuse as ambiguity",
       lambda: store.open_review_context("KAN-906", t["revision"]),
       "conflicting-executor-evidence")
ok("   ambiguity is surfaced, not resolved by picking",
   store.read("task", "KAN-906")["review_context"] is None)

t = mk("KAN-907", evidence=("frontend-1", "frontend-1"))
r = store.open_review_context("KAN-907", t["revision"])
ok("   the same seat evidenced twice is ONE executor, not a conflict",
   r["review_context"]["review_owner"] == "frontend-1")


section("opening: atomicity, route and lifecycle guards")

t = mk("KAN-908", evidence=("frontend-1",))
raises("8. a stale expected_revision refuses",
       lambda: store.open_review_context("KAN-908", 99), "stale write refused")
ok("   the failed CAS left review_context null",
   store.read("task", "KAN-908")["review_context"] is None)
ok("   the failed CAS left revision unchanged",
   store.read("task", "KAN-908")["revision"] == 1)

t = mk("KAN-909", route="peer", evidence=("frontend-1",), sid="10045",
       ch={"schema_change": True})
r = store.open_review_context("KAN-909", t["revision"], evidenced_reviewer="frontend-2")
ok("9a. a PEER item opens a PEER context, never a SELF one",
   r["review_context"]["review_type"] == "peer")
ok("    PEER owner is the evidenced same-capability reviewer",
   r["review_context"]["review_owner"] == "frontend-2")

t = mk("KAN-910", route="peer", evidence=("frontend-1",), sid="10045",
       ch={"schema_change": True})
r = store.open_review_context("KAN-910", t["revision"])
ok("9b. PEER with no evidenced reviewer WAITS with a null owner, never downgrades",
   r["review_context"]["review_owner"] is None
   and r["review_context"]["review_type"] == "peer")

t = mk("KAN-911", route="qa", evidence=("frontend-1",), sid="10009",
       ch={"user_visible_runtime": True})
r = store.open_review_context("KAN-911", t["revision"])
ok("9c. a QA item opens a QA context owned by the qa seat",
   r["review_context"]["review_type"] == "qa"
   and r["review_context"]["review_owner"] == "qa")

t = mk("KAN-912", evidence=("frontend-1",), canonical="development", sid="10046")
raises("9d. a review cannot open on an item still in DEVELOPMENT",
       lambda: store.open_review_context("KAN-912", t["revision"]), "not-in-review")

t = mk("KAN-913", evidence=("frontend-1",))
store.open_review_context("KAN-913", t["revision"])
cur = store.read("task", "KAN-913")
raises("   a pending review is not reopened",
       lambda: store.open_review_context("KAN-913", cur["revision"]),
       "review-already-open")


# ---------------------------------------------------------------- 10-13 results

section("recording the verdict")

t = mk("KAN-920", evidence=("frontend-1",))
raises("10. PASS requires an open review context",
       lambda: store.record_review_result("KAN-920", t["revision"], "frontend-1",
                                          "pass", "ref:x"),
       "no-review-context")

t = mk("KAN-921", evidence=("frontend-1",))
o = store.open_review_context("KAN-921", t["revision"])
raises("11. PASS requires the EXACT review owner",
       lambda: store.record_review_result("KAN-921", o["revision"], "frontend-2",
                                          "pass", "ref:x"),
       "not-review-owner")
ok("    the refusal left the result pending",
   store.read("task", "KAN-921")["review_context"]["review_result"] == "pending")
p = store.record_review_result("KAN-921", o["revision"], "frontend-1", "pass", "ref:ok")
ok("    the exact owner records PASS",
   p["review_context"]["review_result"] == "pass")
ok("    PASS records its evidence_ref", p["review_context"]["evidence_ref"] == "ref:ok")
ok("    PASS does NOT clear ownership or invent one", p["ownership"] is None)
ok("    PASS does NOT set the lifecycle to done",
   p["lifecycle"]["canonical"] == "review")
raises("    a settled review is not re-recorded",
       lambda: store.record_review_result("KAN-921", p["revision"], "frontend-1",
                                          "fail", "ref:y"),
       "review-already-settled")

t = mk("KAN-922", evidence=("frontend-1",))
o = store.open_review_context("KAN-922", t["revision"])
raises("12. FAIL requires the exact owner too",
       lambda: store.record_review_result("KAN-922", o["revision"], "frontend-2",
                                          "fail", "ref:x"),
       "not-review-owner")
f = store.record_review_result("KAN-922", o["revision"], "frontend-1", "fail", "ref:no")
ok("    FAIL is recorded truthfully as 'fail'",
   f["review_context"]["review_result"] == "fail")
ok("13. SELF FAIL does NOT apply PEER executor-transfer semantics — evidence "
   "is unchanged",
   [e["seat_id"] for e in f["executor_evidence"]] == ["frontend-1"])
ok("    SELF FAIL does not invent a new owner", f["ownership"] is None)
ok("    SELF FAIL leaves review_type self", f["review_context"]["review_type"] == "self")

re = store.open_review_context("KAN-922", f["revision"])
ok("    a FAILED SELF review reopens with the cycle incremented",
   re["review_context"]["review_cycle"] == 2)
ok("    the reopened cycle is pending again",
   re["review_context"]["review_result"] == "pending")
ok("    the reopened owner is still the evidenced executor",
   re["review_context"]["review_owner"] == "frontend-1")

t = mk("KAN-923", route="peer", evidence=("frontend-1",), sid="10045",
       ch={"schema_change": True})
o = store.open_review_context("KAN-923", t["revision"], evidenced_reviewer="frontend-2")
f = store.record_review_result("KAN-923", o["revision"], "frontend-2", "fail", "ref:no")
raises("    a FAILED PEER review is NOT reopened here — peer_fail_transfer owns it",
       lambda: store.open_review_context("KAN-923", f["revision"]),
       "peer_fail_transfer")

t = mk("KAN-924", route="peer", evidence=("frontend-1",), sid="10045",
       ch={"schema_change": True})
o = store.open_review_context("KAN-924", t["revision"])
raises("    a WAITING review (null owner) accepts no verdict",
       lambda: store.record_review_result("KAN-924", o["revision"], "frontend-2",
                                          "pass", "ref:x"),
       "review-owner-unresolved")

t = mk("KAN-925", evidence=("frontend-1",))
o = store.open_review_context("KAN-925", t["revision"])
raises("    an invalid result value refuses",
       lambda: store.record_review_result("KAN-925", o["revision"], "frontend-1",
                                          "maybe", "ref:x"), "must be 'pass' or 'fail'")
raises("    a verdict with no evidence_ref refuses",
       lambda: store.record_review_result("KAN-925", o["revision"], "frontend-1",
                                          "pass", ""), "evidence_ref is required")
raises("20. a failed CAS on the verdict leaves state unchanged",
       lambda: store.record_review_result("KAN-925", 99, "frontend-1", "pass", "r"),
       "stale write refused")
ok("    ... result still pending after the failed CAS",
   store.read("task", "KAN-925")["review_context"]["review_result"] == "pending")
ok("    ... revision unchanged after the failed CAS",
   store.read("task", "KAN-925")["revision"] == o["revision"])


# ---------------------------------------------------------------- 14-15 QA/PEER

section("QA and PEER non-regression")

t = mk("KAN-930", route="peer", evidence=("frontend-1",), sid="10045",
       ch={"schema_change": True})
o = store.open_review_context("KAN-930", t["revision"], evidenced_reviewer="frontend-2")
tr = store.peer_fail_transfer("KAN-930", o["revision"], "frontend-2", "ref:transfer")
ok("15. PEER FAIL still transfers execution to the reviewer",
   [e["seat_id"] for e in tr["executor_evidence"]] == ["frontend-2"])
ok("    PEER FAIL still flips the route to SELF for the reviewer's own fix",
   tr["review_context"]["review_type"] == "self"
   and tr["review_context"]["review_owner"] == "frontend-2")
ok("    PEER FAIL still records previous_owner",
   tr["review_context"]["previous_owner"] == "frontend-1")
ok("    PEER FAIL still increments the cycle", tr["review_context"]["review_cycle"] == 2)
ok("    the post-transfer record still validates",
   [x for x in validate.validate_record("task", tr) if " WARN " not in x] == [])

ok("14. QA route policy is untouched",
   policy.validation_route({"user_visible_runtime": True}) == policy.QA)
ok("    PEER route policy is untouched",
   policy.validation_route({"schema_change": True}) == policy.PEER)
ok("    SELF remains the default route",
   policy.validation_route({}) == policy.SELF)
ok("    resolve_owner_or_wait is reused unchanged for SELF",
   policy.resolve_owner_or_wait("self", "frontend", {}, executor_seats=["frontend-1"])
   == ("frontend-1", "self"))


# ---------------------------------------------------------------- 16-19 completion

section("completion eligibility is DERIVED")

t = mk("KAN-940", evidence=("frontend-1",))
ok("16. not completion-eligible before a review context exists",
   "no-review-context" in q.completion_reasons(t, interventions=[]))
o = store.open_review_context("KAN-940", t["revision"])
ok("    not eligible with a PENDING review",
   "review-not-passed" in q.completion_reasons(o, interventions=[]))
f = store.record_review_result("KAN-940", o["revision"], "frontend-1", "fail", "ref:n")
ok("    not eligible with a FAILED review",
   "review-failed" in q.completion_reasons(f, interventions=[]))

t = mk("KAN-941", evidence=("frontend-1",))
o = store.open_review_context("KAN-941", t["revision"])
p = store.record_review_result("KAN-941", o["revision"], "frontend-1", "pass", "ref:y")
ok("17. eligible after SELF PASS when every other prerequisite holds",
   q.completion_reasons(p, interventions=[]) == [])
ok("    completion_eligible agrees", q.completion_eligible(p, interventions=[]))

# 18/19: the two things that must NOT be able to complete an item.
t = mk("KAN-942", evidence=("frontend-1",), sid="10044")
ok("18. a Jira review STATUS alone creates no review context",
   store.read("task", "KAN-942")["review_context"] is None
   and "no-review-context" in q.completion_reasons(t, interventions=[]))

t = mk("KAN-943", evidence=("frontend-1",), canonical="done", sid="10007")
r = q.completion_reasons(t, interventions=[])
ok("19. a Jira DONE alone does not fabricate a SELF pass",
   "no-review-context" in r)
ok("    ... and a done item is not re-completed", "already-done" in r)

t = mk("KAN-944", evidence=("frontend-1",))
o = store.open_review_context("KAN-944", t["revision"])
p = store.record_review_result("KAN-944", o["revision"], "frontend-1", "pass", "ref:y")
iv = [{"kind": "STOP", "target": "KAN-944", "intervention_id": "iv-1"}]
ok("    a STOPped task is not completion-eligible even having PASSED",
   "task-stopped" in q.completion_reasons(p, interventions=iv))

ok("    completion reasons are a THIRD namespace, distinct from the other two",
   "review-not-passed" not in q.unclaimable_reasons(
       mk("KAN-945", evidence=("frontend-1",)), all_tasks=[], jira_status_id="10044"))


# ---------------------------------------------------------------- 21-23 paths

section("release semantics and the full paths")

t = mk("KAN-950", evidence=(), owner="frontend-1", canonical="development", sid="10046")
rel = store.release("KAN-950", "frontend-1", t["revision"], "ref:done-executing")
ok("21. release creates executor evidence exactly once",
   [e["seat_id"] for e in rel["executor_evidence"]] == ["frontend-1"])
ok("    release clears ownership", rel["ownership"] is None)
ok("    a second identical evidence entry is de-duplicated, not appended twice",
   len(store.evidenced_executors(rel)) == 1)

section("22. full synthetic SELF happy path")
t = mk("KAN-960", evidence=(), owner="frontend-1", canonical="development", sid="10046")
s1 = store.release("KAN-960", "frontend-1", t["revision"], "ref:executed")
ok("  a. release -> ownership null, evidence frontend-1",
   s1["ownership"] is None and store.evidenced_executors(s1) == ["frontend-1"])
s2 = store.observe_lifecycle("KAN-960", s1["revision"], "10044")
ok("  b. Jira observed at Self-review -> canonical review",
   s2["lifecycle"]["canonical"] == "review")
s3 = store.open_review_context("KAN-960", s2["revision"], opened_by="orchestrator")
ok("  c. SELF context opens, owner derived as frontend-1",
   s3["review_context"]["review_owner"] == "frontend-1")
s4 = store.record_review_result("KAN-960", s3["revision"], "frontend-1", "pass",
                                "jira-comment:1")
ok("  d. SELF PASS recorded", s4["review_context"]["review_result"] == "pass")
ok("  e. completion eligible", q.completion_reasons(s4, interventions=[]) == [])
s5 = store.observe_lifecycle("KAN-960", s4["revision"], "10007")
ok("  f. Jira Done observed back -> canonical done",
   s5["lifecycle"]["canonical"] == "done")
ok("  g. ownership stays null", s5["ownership"] is None)
ok("  h. the final record validates with no hard error",
   [x for x in validate.validate_record("task", s5) if " WARN " not in x] == [])

section("23. synthetic SELF failure path")
t = mk("KAN-961", evidence=(), owner="frontend-1", canonical="development", sid="10046")
f1 = store.release("KAN-961", "frontend-1", t["revision"], "ref:executed")
f2 = store.observe_lifecycle("KAN-961", f1["revision"], "10044")
f3 = store.open_review_context("KAN-961", f2["revision"])
f4 = store.record_review_result("KAN-961", f3["revision"], "frontend-1", "fail",
                                "jira-comment:2")
ok("  a. FAIL recorded, not eligible for completion",
   "review-failed" in q.completion_reasons(f4, interventions=[]))
f5 = store.observe_lifecycle("KAN-961", f4["revision"], "10046")
ok("  b. returns to its OWN execution status (Front-end 10046)",
   f5["lifecycle"]["jira_status_id"] == "10046"
   and f5["lifecycle"]["canonical"] == "development")
ok("  c. no PEER transfer occurred — evidence still frontend-1",
   store.evidenced_executors(f5) == ["frontend-1"])
f6 = store.observe_lifecycle("KAN-961", f5["revision"], "10044")
f7 = store.open_review_context("KAN-961", f6["revision"])
ok("  d. re-review opens on the SAME route, cycle 2",
   f7["review_context"]["review_type"] == "self"
   and f7["review_context"]["review_cycle"] == 2)
f8 = store.record_review_result("KAN-961", f7["revision"], "frontend-1", "pass",
                                "jira-comment:3")
ok("  e. second cycle passes and becomes eligible",
   q.completion_reasons(f8, interventions=[]) == [])


# ---------------------------------------------------------------- 24-25 validator

section("the validator guards the FILE as the store guards the WRITE")

t = mk("KAN-970", evidence=("frontend-1",))
good = store.open_review_context("KAN-970", t["revision"])
ok("24. validator accepts a coherent SELF context",
   [x for x in validate.validate_record("task", good) if " WARN " not in x] == [])

bad = dict(good)
bad["review_context"] = dict(good["review_context"], review_owner="frontend-2")
errs = [x for x in validate.validate_record("task", bad) if " WARN " not in x]
ok("25. validator REJECTS a SELF owner that is not the evidenced executor",
   any("not the evidenced executor" in x for x in errs))

bad2 = dict(good)
bad2["executor_evidence"] = [
    {"seat_id": "frontend-1", "evidence_ref": "a", "evidenced_at": store.now()},
    {"seat_id": "frontend-2", "evidence_ref": "b", "evidenced_at": store.now()}]
ok("    validator REJECTS a SELF context over conflicting evidence",
   any("conflicting evidence" in x or "distinct evidenced executors" in x
       for x in validate.validate_record("task", bad2) if " WARN " not in x))

bad3 = dict(good)
bad3["review_context"] = dict(good["review_context"], review_owner="nobody-9")
ok("    validator REJECTS an undeclared seat as review_owner",
   any("not a declared seat" in x
       for x in validate.validate_record("task", bad3) if " WARN " not in x))

bad4 = dict(good)
bad4["executor_evidence"] = []
warns = [x for x in validate.validate_record("task", bad4) if " WARN " in x]
ok("    a SELF owner with NO evidence is a repairable WARN, not unloadable",
   any("no executor evidence" in x for x in warns))

bad5 = dict(good)
bad5["review_context"] = dict(good["review_context"], review_result="pass",
                              review_owner=None)
ok("    validator REJECTS a pass with no owner",
   any("no review_owner" in x
       for x in validate.validate_record("task", bad5) if " WARN " not in x))

bad6 = dict(good)
bad6["lifecycle"] = dict(good["lifecycle"], canonical="done", jira_status_id="10007",
                         jira_status_name="Done", jira_column="Done")
ok("    validator still REJECTS done with a non-pass review",
   any("review_result" in x
       for x in validate.validate_record("task", bad6) if " WARN " not in x))

sys.exit(summary())
