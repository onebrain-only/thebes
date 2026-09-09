#!/usr/bin/env python3
"""Moving ALREADY-COMPLETE orphaned execution forward to its derived review.

Synthetic runtime and synthetic roster throughout. No live Jira call, no Product file.

TWO ORPHANS, TWO PATHS
  `recover_execution_to_ready` is right for work that still needs executing. Ready is
  a PRE-execution queue, so sending COMPLETED work there would imply execution is
  outstanding, invite a duplicate implementation, and risk handing finished work to a
  new executor. KAN-155 was exactly that: applied to production, every criterion
  verified, sitting in `Back-end` because nobody transitioned it.

WHAT THESE TESTS DEFEND
  Two lines that are easy to erase and expensive to lose.

  First, `executor_evidence` alone is NOT proof of completion — it proves who executed
  something, and every stranded item in this family carries it, including the merely
  stalled ones. So completion must be evidenced explicitly.

  Second, completion evidence is NOT validation evidence. Forward reconciliation moves
  an item to its REVIEW route and never to Done, and the route is DERIVED — there is
  no route argument, so no caller can reach an easier review by asking for one.

Stdlib only.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, policy, queue as q, board, view                    # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend",
          "backend-1": "backend", "backend-2": "backend", "qa": "qa", "po": "po"}


def fresh_roster():
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in ROSTER.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return validate.seats_by_capability()


REF = "jira-comment:10750 APPLIED and verified"
FACTS = {"has_due_date": True, "has_acceptance_criteria": True}


_UNSET = object()


def mk(key, *, capability="backend", sid=None, canonical="development", owner=None,
       evidence=("backend-1",), rc=None, route="self", ch=_UNSET):
    sid = sid or board.execution_status_for(capability)
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app",
        "surfaces": ["supabase/%s.sql" % key.lower()],
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
            "required_capability": capability, "work_effort": 1,
            "validation_route": route, "completion_route": "DONE",
            "characteristics": ({} if ch is _UNSET else ch),
            "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "validation_route", "completion_route"],
            "provenance": {"validation_route": {"by": "system-policy", "at": store.now()}},
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
            and cur.get("completion_reconciliation") is None
            and cur["ownership"] == before["ownership"]
            and cur["executor_evidence"] == before["executor_evidence"]
            and cur["review_context"] == before["review_context"])


# ---------------------------------------------------------------- 1-3 the core rule

section("completion must be EVIDENCED, never inferred")

t = mk("KAN-601", evidence=("backend-1",))
r = store.reconcile_completed_execution("KAN-601", t["revision"], "po", REF)
ok("1. an orphaned execution item with explicit completion evidence reconciles",
   r["completion_reconciliation"]["completion_ref"] == REF)
ok("   the record names where it came from and where it goes",
   r["completion_reconciliation"]["from_status"] == "10043"
   and r["completion_reconciliation"]["to_review_status"] == "10044")

t = mk("KAN-602", evidence=("backend-1",))
raises("2. NO completion evidence -> refused",
       lambda: store.reconcile_completed_execution("KAN-602", t["revision"], "po", ""),
       "completion_ref is required")
ok("   ... unchanged", unchanged("KAN-602", t))
ok("3. executor_evidence ALONE is not proof of completion — the item carries it and "
   "was still refused",
   store.evidenced_executors(store.read("task", "KAN-602")) == ["backend-1"])
try:
    store.reconcile_completed_execution("KAN-602", t["revision"], "po", "")
except store.StateError as e:
    ok("   ... it distinguishes 'who executed' from 'finished'",
       "who" in str(e) and "FINISHED" in str(e))


# ---------------------------------------------------------------- 4-12 refusals

section("every refusal leaves the record untouched")

t = mk("KAN-610", owner="backend-1")
raises("4. an OWNED item refuses",
       lambda: store.reconcile_completed_execution("KAN-610", t["revision"], "po", REF),
       "already-owned")
ok("   ... unchanged", unchanged("KAN-610", t))

for n, (key, sid, canon, frag) in enumerate([
        ("KAN-611", "10008", "ready", "not-orphaned-execution"),
        ("KAN-612", "10004", "ready", "not-orphaned-execution"),
        ("KAN-613", "10045", "review", "not-orphaned-execution"),
        ("KAN-614", "10007", "done", "not-orphaned-execution")], start=5):
    t = mk(key, sid=sid, canonical=canon)
    raises("%d. status %s (%s) refuses" % (n, sid, board.name_for(sid)),
           lambda k=key, tt=t: store.reconcile_completed_execution(k, tt["revision"],
                                                                   "po", REF), frag)

t = mk("KAN-615", rc={"review_type": "self", "review_owner": "backend-1",
                      "review_result": "pending", "review_cycle": 1})
raises("9. an active review context refuses",
       lambda: store.reconcile_completed_execution("KAN-615", t["revision"], "po", REF),
       "review-in-progress")

t = mk("KAN-616", ch=None)
raises("10/11. a profile with NO characteristics refuses — no route can be derived",
       lambda: store.reconcile_completed_execution("KAN-616", t["revision"], "po", REF),
       "incomplete-profile")
ok("    ... unchanged", unchanged("KAN-616", t))

t = mk("KAN-617", route=None)
raises("12. a null validation_route refuses — reconciliation never guesses one",
       lambda: store.reconcile_completed_execution("KAN-617", t["revision"], "po", REF),
       "no-validation-route")

t = mk("KAN-618")
raises("25. a stale CAS refuses",
       lambda: store.reconcile_completed_execution("KAN-618", 99, "po", REF),
       "stale write refused")
ok("    ... unchanged", unchanged("KAN-618", t))
for bad in ("backend-1", "cto", "qa", "orchestrator", ""):
    raises("26. actor %r refused" % (bad or "<empty>"),
           lambda b=bad: store.reconcile_completed_execution("KAN-618", t["revision"],
                                                             "po" if False else b, REF),
           "unauthorised-recovery-actor")
ok("    ceo is also an authority",
   store.reconcile_completed_execution("KAN-618", t["revision"], "ceo",
                                       REF)["completion_reconciliation"]["by"] == "ceo")


# ---------------------------------------------------------------- 13-17 route

section("the route is DERIVED, and cannot be asked for")

CASES = [(13, "self", {}, "10044"),
         (14, "qa", {"user_visible_runtime": True}, "10009"),
         (15, "peer", {"schema_change": True}, "10045")]
for n, route, ch, want in CASES:
    t = mk("KAN-62%d" % n, route=route, ch=ch)
    r = store.reconcile_completed_execution("KAN-62%d" % n, t["revision"], "po", REF)
    ok("%d. characteristics %s derive the %s target %s"
       % (n, ch or "{}", route.upper(), want),
       r["completion_reconciliation"]["to_review_status"] == want
       and r["completion_reconciliation"]["route"] == route)

import inspect
sig = str(inspect.signature(store.reconcile_completed_execution))
ok("16/17. there is NO route argument to override or weaken",
   "route" not in sig and "target" not in sig)
t = mk("KAN-630", route="self", ch={"schema_change": True})
raises("    a stored route WEAKER than the characteristics derive is refused",
       lambda: store.reconcile_completed_execution("KAN-630", t["revision"], "po", REF),
       "route-incoherent")
ok("    ... unchanged", unchanged("KAN-630", t))


# ---------------------------------------------------------------- 18-24 effects

section("what reconciliation must NOT do")

t = mk("KAN-640", evidence=("backend-1", "backend-2"), route="peer",
       ch={"schema_change": True})
r = store.reconcile_completed_execution("KAN-640", t["revision"], "po", REF)
ok("18. no ownership is created", r["ownership"] is None)
ok("19. executor_evidence preserved exactly",
   r["executor_evidence"] == t["executor_evidence"])
ok("20. the previous executor is not restored",
   r["ownership"] is None and store.evidenced_executors(r) == ["backend-1", "backend-2"])
ok("21. the task does NOT enter Ready — lifecycle is untouched here",
   r["lifecycle"]["jira_status_id"] == "10043")
ok("22. no review cycle is fabricated", r["review_context"] is None)
ok("23. no review PASS is fabricated", r["review_context"] is None)
ok("24. completion is not fabricated — it is still not Done",
   r["lifecycle"]["canonical"] != "done"
   and q.completion_reasons(r, interventions=[]) != [])
fn = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
body = fn.split("def reconcile_completed_execution")[1].split("\ndef ")[0]
code = "\n".join(l for l in body.split("\n")
                 if not l.strip().startswith("#")).split('"""')[-1]
ok("    Jira is not mutated at store level",
   not any(w in code for w in ("transition_issue(", "get_issue(", "observe_lifecycle(")))
ok("    no review_owner is chosen", "review_owner" not in code)


# ---------------------------------------------------------------- 27-29 interventions

section("interventions")

t = mk("KAN-650")
iv = store.create_intervention("stop", "KAN-650", "ceo", "reason:safety")
raises("27. STOP refuses — lifecycle progression waits",
       lambda: store.reconcile_completed_execution("KAN-650", t["revision"], "po", REF),
       "task-stopped")
ok("    ... unchanged", unchanged("KAN-650", t))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
ok("    ... permitted once cleared",
   store.reconcile_completed_execution("KAN-650", t["revision"], "po",
                                       REF)["revision"] == 2)

t = mk("KAN-651")
iv = store.create_intervention("hold", "backend", "ceo", "reason:safety")
ok("28. HOLD does not block forward reconciliation — it gates new execution claims",
   store.reconcile_completed_execution("KAN-651", t["revision"], "po", REF)["revision"] == 2)
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")

t = mk("KAN-652")
iv = store.create_intervention("freeze", None, "ceo", "reason:incident")
ok("29. FREEZE likewise does not block it, and fabricates no ownership",
   store.reconcile_completed_execution("KAN-652", t["revision"], "po",
                                       REF)["ownership"] is None)
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")


# ---------------------------------------------------------------- 30-36 onward

section("the forward path, end to end")

t = mk("KAN-660", route="self", ch={})
r = store.reconcile_completed_execution("KAN-660", t["revision"], "po", REF)
raises("30. the review context cannot open before the Jira review status is observed",
       lambda: store.open_review_context("KAN-660", r["revision"]), "not-in-review")
d = store.observe_lifecycle("KAN-660", r["revision"],
                            r["completion_reconciliation"]["to_review_status"])
o = store.open_review_context("KAN-660", d["revision"])
ok("31. the SELF opener works after the forward transition",
   o["review_context"]["review_type"] == "self"
   and o["review_context"]["review_owner"] == "backend-1")
p = store.record_review_result("KAN-660", o["revision"], "backend-1", "pass", "ref:ok")
ok("36. PASS -> Done still uses the normal completion path",
   q.completion_reasons(p, interventions=[]) == [])
dn = store.observe_lifecycle("KAN-660", p["revision"], "10007")
ok("    and the final record validates",
   [x for x in validate.validate_record("task", dn) if " WARN " not in x] == [])

t = mk("KAN-661", route="qa", ch={"user_visible_runtime": True})
r = store.reconcile_completed_execution("KAN-661", t["revision"], "po", REF)
d = store.observe_lifecycle("KAN-661", r["revision"], "10009")
o = store.open_review_context("KAN-661", d["revision"])
ok("32. the QA opener works after the forward transition",
   o["review_context"]["review_owner"] == "qa")

t = mk("KAN-662", route="peer", ch={"schema_change": True})
r = store.reconcile_completed_execution("KAN-662", t["revision"], "po", REF)
d = store.observe_lifecycle("KAN-662", r["revision"], "10045")
o = store.open_review_context("KAN-662", d["revision"])
ok("33. the PEER opener works after the forward transition",
   o["review_context"]["review_type"] == "peer")
ok("34. an unresolved PEER reviewer remains supported and waits",
   o["review_context"]["review_owner"] is None
   and view.review_view(o)["display_state"] == "WAITING FOR EXACT REVIEWER")
res = store.resolve_review_owner("KAN-662", o["revision"], "backend-2", "ceo:named")
ok("35. reviewer resolution still works", res["review_context"]["review_owner"] == "backend-2")


# ---------------------------------------------------------------- 37-40 separation

section("the two orphan paths stay separate")

t = mk("KAN-670", route="self", ch={})
rec = store.recover_execution_to_ready("KAN-670", t["revision"], "po:still-incomplete",
                                        "po")
ok("37. recovery-to-Ready is unchanged for INCOMPLETE work",
   rec["execution_recovery"]["from_status"] == "10043")

t = mk("KAN-671", route="self", ch={})
rc_ = store.reconcile_completed_execution("KAN-671", t["revision"], "po", REF)
raises("38. work marked factually COMPLETE can no longer be sent backward to Ready",
       lambda: store.recover_execution_to_ready("KAN-671", rc_["revision"],
                                                "po:oops", "po"),
       "already-reconciled-complete")
ok("    ... and the completion record survives the attempt",
   store.read("task", "KAN-671")["completion_reconciliation"]["completion_ref"] == REF)

ok("39. a coherent forward-reconciled record validates",
   [x for x in validate.validate_record("task", rc_) if " WARN " not in x] == [])
bad = dict(rc_)
bad["completion_reconciliation"] = dict(rc_["completion_reconciliation"], by="backend-1")
ok("    the validator rejects an unauthorised reconciliation author",
   any("not a reconciliation authority" in x
       for x in validate.validate_record("task", bad) if " WARN " not in x))
bad2 = dict(rc_)
bad2["completion_reconciliation"] = dict(rc_["completion_reconciliation"],
                                         completion_ref="")
ok("    and rejects a missing completion_ref on disk",
   any("completion_ref is required" in x
       for x in validate.validate_record("task", bad2) if " WARN " not in x))

ok("40. no runtime shortcut exists — both paths are store operations under lock",
   "flock" in open(os.path.join(repo_root(), "agent", "state", "store.py")).read())

sys.exit(summary())
