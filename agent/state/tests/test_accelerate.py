#!/usr/bin/env python3
"""ACCELERATE — maximum SAFE parallel throughput.

Synthetic runtime and synthetic roster throughout. The live `agent/state/runtime/**`
is never read for assertions and never written; no Jira call is made; no Product file
is touched.

THE ONE SENTENCE THIS SUITE DEFENDS
  ACCELERATE changes HOW AGGRESSIVELY SAFE CAPACITY IS FILLED. It does not change
  WHAT WORK IS VALID. So the largest group of tests below simply re-asserts, with a
  policy active, every rule that held without one: Ready, fresh Jira, dependencies,
  contention, STOP/HOLD/FREEZE, SELF/QA/PEER, exact reviewers, ownership uniqueness.
  If any of those can be observed to weaken under acceleration, ACCELERATE is wrong.

  The second thing it defends is that the selector is ADVISORY. `store.claim` re-runs
  every predicate inside its lock, so a stale plan fails at the claim rather than
  producing an unsafe ownership. Tests assert the claim refuses what the plan could
  not have known.

Stdlib only.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, policy, queue as q, board, capacity as cap, view   # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend", "frontend-3": "frontend",
          "backend-1": "backend", "backend-2": "backend",
          "content-manager": "content", "qa": "qa", "cto": "cto", "po": "po"}


def fresh_roster(seats=None):
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in (seats or ROSTER).items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nmodel: sonnet\neffort: medium\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return validate.seats_by_capability()


READY = "10008"


def mk(key, *, capability="frontend", surfaces=None, owner=None, sid=READY,
       canonical="ready", product="dabbler", effort=1, logical=None, route="self",
       rc=None, ch=None):
    lc = {"canonical": canonical, "jira_column": board.column_for(sid),
          "jira_status_id": sid, "jira_status_name": board.name_for(sid),
          "observed_at": store.now(), "source": "jira"}
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": product, "project_id": "app",
        "surfaces": ["lib/f/%s.dart" % key.lower()] if surfaces is None else surfaces,
        "executor_evidence": [], "ownership": (
            {"seat_id": owner, "claim_ref": "r", "claimed_at": store.now()}
            if owner else None),
        "review_context": rc, "lifecycle": lc,
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
    if logical is not None:
        rec["logical_surfaces"] = logical
    path = store.path_for("task", key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


JIRA_OK = {"has_due_date": True, "has_acceptance_criteria": True}


def kw(tasks):
    """The Jira facts a live read supplies, passed as parameters — never cached."""
    return {"jira": dict(JIRA_OK)}


def plan_for(cap_name, tasks, sbc, **extra):
    return cap.safe_parallel_plan(cap_name, tasks, sbc, jira=dict(JIRA_OK), **extra)


fresh_runtime()
SBC = fresh_roster()


# ---------------------------------------------------------------- 1-8 policy record

section("the execution policy record")

t1 = mk("KAN-701"); t2 = mk("KAN-702")
tasks = store.read_all("task")
ok("1. with NO policy, nothing is accelerated",
   store.accelerate_scopes_for(t1) == [] and not store.accelerated(t1))
ok("   and normal claimability is unchanged",
   q.unclaimable_reasons(t1, all_tasks=tasks, jira=dict(JIRA_OK)) == [])

ok("   ACCELERATE is NOT in the intervention vocabulary",
   "accelerate" not in validate.INTERVENTION_KINDS)
raises("   and cannot be created as one",
       lambda: store.create_intervention("accelerate", "KAN-701", "ceo", "r"),
       "unknown intervention kind")
ok("   policies are a separate record kind and directory",
   store.KINDS["policy"][0] == "policies")
ok("   intervention_blocks_claim never consults a policy",
   store.intervention_blocks_claim("KAN-701", "frontend", []) is None)

sysp = store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:accel-1")
ok("2. SYSTEM scope covers a task of any capability/product",
   store.accelerated(store.read("task", "KAN-701")))
ok("   a system policy takes no target", sysp["target"] is None)
ok("   the policy is auditable", sysp["activated_by"] == "ceo"
   and sysp["reason_ref"] == "ceo:accel-1" and sysp["activated_at"])
ok("   and revisioned", sysp["revision"] == 1)
raises("   a duplicate ACTIVE policy on the same scope/target refuses",
       lambda: store.set_execution_policy("accelerate", "system", None, "ceo", "r"),
       "already exists")
store.clear_execution_policy(sysp["policy_id"], sysp["revision"], "ceo")

other = mk("KAN-703", product="other-product")
pp = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "ceo:p")
ok("3. PRODUCT scope covers its own product",
   store.accelerated(store.read("task", "KAN-701")))
ok("   and does NOT cover another product", not store.accelerated(other))
store.clear_execution_policy(pp["policy_id"], pp["revision"], "ceo")

be = mk("KAN-704", capability="backend", surfaces=["supabase/x.sql"])
cp = store.set_execution_policy("accelerate", "capability", "frontend", "ceo", "ceo:c")
ok("4. CAPABILITY scope covers its own capability",
   store.accelerated(store.read("task", "KAN-701")))
ok("   and does NOT cover another capability", not store.accelerated(be))

cp2 = store.set_execution_policy("accelerate", "capability", "backend", "ceo", "ceo:c2")
ok("5. scopes UNION — two capability policies cover both",
   store.accelerated(store.read("task", "KAN-701")) and store.accelerated(be))
sysp2 = store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:s2")
ok("   a system policy unions with capability policies rather than fighting them",
   len(store.accelerate_scopes_for(store.read("task", "KAN-701"))) == 2)
ok("   there is no negative/NORMAL policy to express an override",
   store.POLICY_KINDS == ("accelerate",))

raises("6. TASK scope is REJECTED, not deferred",
       lambda: store.set_execution_policy("accelerate", "task", "KAN-701", "ceo", "r"),
       "unknown policy scope")
raises("   an unknown capability target refuses",
       lambda: store.set_execution_policy("accelerate", "capability", "nope", "ceo", "r"),
       None)
raises("   a policy with no reason_ref refuses",
       lambda: store.set_execution_policy("accelerate", "product", "dabbler", "ceo", ""),
       "reason_ref is required")

for p_ in list(store.active_execution_policies()):
    store.clear_execution_policy(p_["policy_id"], p_["revision"], "ceo")
ok("7. clear leaves no active policy", store.active_execution_policies() == [])
ok("   cleared records are RETAINED as history", len(store.read_all("policy")) >= 4)
ok("   a cleared policy records who and when",
   all(p_["cleared_by"] and p_["cleared_at"] for p_ in store.read_all("policy")))
first = store.read_all("policy")[0]
raises("   clearing twice refuses",
       lambda: store.clear_execution_policy(first["policy_id"], first["revision"], "ceo"),
       "already cleared")
raises("   a stale CAS on clear refuses",
       lambda: store.clear_execution_policy(first["policy_id"], 99, "ceo"),
       "stale write refused")

per = store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:persist")
ok("8. the policy PERSISTS on disk — a new process re-reads it",
   json.load(open(store.path_for("policy", per["policy_id"])))["scope"] == "system")
ok("   dispatchability is NOT persisted alongside it",
   "seats" not in per and "dispatchable" not in per)


# ---------------------------------------------------------------- 9-18 what is valid

section("ACCELERATE does not change what work is valid")

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")

a = mk("KAN-710", surfaces=["lib/a.dart"])
b = mk("KAN-711", surfaces=["lib/b.dart"])
owned = mk("KAN-712", surfaces=["lib/c.dart"], owner="frontend-3")
tasks = store.read_all("task")
p = plan_for("frontend", tasks, SBC)
ok("9. an existing owner is preserved and never re-planned",
   "KAN-712" not in p["selected"]
   and store.read("task", "KAN-712")["ownership"]["seat_id"] == "frontend-3")
ok("   its seat is not offered as free", "frontend-3" not in p["free_seats"])
ok("10. one item appears at most once in a plan",
   len(p["selected"]) == len(set(p["selected"])))
ok("    and each seat is assigned at most one item",
   len({x["seat_id"] for x in p["assignments"]}) == len(p["assignments"]))

stale = mk("KAN-713")
tasks = store.read_all("task")
ok("12/13. unverified Jira excludes an item (no jira facts supplied)",
   "KAN-713" not in [t.get("work_item_id")
                     for t in cap.claimable_items("frontend", tasks)])
ok("11. only claimable tasks are ever candidates",
   set(p["selected"]) <= set(p["claimable"]))

dev = mk("KAN-714", canonical="development", sid="10046")
tasks = store.read_all("task")
ok("    a non-Ready item is excluded",
   "KAN-714" not in plan_for("frontend", tasks, SBC)["claimable"])

src = mk("KAN-715"); tgt = mk("KAN-716")
store.create_dependency({"source_work_item": "KAN-715", "target_work_item": "KAN-716",
                         "relation": "BLOCKS", "completion_condition": "DONE",
                         "product_id": "dabbler", "created_by": "po", "reason_ref": "r"})
tasks = store.read_all("task")
ok("14. dependency-blocked work is excluded under ACCELERATE",
   "KAN-716" not in plan_for("frontend", tasks, SBC)["claimable"])

un = mk("KAN-717", surfaces=None)
un_rec = store.read("task", "KAN-717")
p2 = store.path_for("task", "KAN-717")
d = json.load(open(p2)); d["surfaces"] = None; json.dump(d, open(p2, "w"))
tasks = store.read_all("task")
ok("15. surfaces-unassessed work is excluded",
   "KAN-717" not in plan_for("frontend", tasks, SBC)["claimable"])

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
c1 = mk("KAN-720", surfaces=["lib/app/app_router.dart"])
c2 = mk("KAN-721", surfaces=["lib/app/app_router.dart"])
c3 = mk("KAN-722", surfaces=["lib/z.dart"])
tasks = store.read_all("task")
p = plan_for("frontend", tasks, SBC)
ok("16. two items on the SAME file are serialized, not parallelised",
   len([k for k in p["selected"] if k in ("KAN-720", "KAN-721")]) == 1)
ok("    the third, non-colliding item still runs in parallel", "KAN-722" in p["selected"])
ok("    the deferred one is REPORTED, not lost",
   len(p["deferred"]) == 1 and p["deferred"][0] in ("KAN-720", "KAN-721"))

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
L1 = mk("KAN-730", capability="backend", surfaces=["supabase/a.sql"],
        logical=["settle_game"])
L2 = mk("KAN-731", capability="backend", surfaces=["supabase/b.sql"],
        logical=["settle_game"])
L3 = mk("KAN-732", capability="backend", surfaces=["supabase/c.sql"],
        logical=["trgfn_payment_to_ledger"])
tasks = store.read_all("task")
p = plan_for("backend", tasks, SBC)
ok("17. declared logical overlap serializes despite NO file collision",
   not q.surfaces_collide(L1["surfaces"], L2["surfaces"])
   and q.logical_collide(L1, L2)
   and len([k for k in p["selected"] if k in ("KAN-730", "KAN-731")]) == 1)
ok("    a different logical object does not collide", "KAN-732" in p["selected"])
ok("18. an UNDECLARED logical surface is UNKNOWN, never proof of safety",
   q.logical_objects(mk("KAN-733", capability="backend")) == set()
   and not q.logical_collide(L1, store.read("task", "KAN-733")))
ok("    logical objects live in their own field, separate from file surfaces",
   "logical_surfaces" in L1 and L1["logical_surfaces"] != L1["surfaces"])


# ---------------------------------------------------------------- 19-25 safety wins

section("interventions and validation always outrank ACCELERATE")

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
s1 = mk("KAN-740"); s2 = mk("KAN-741")
iv = store.create_intervention("stop", "KAN-740", "ceo", "reason:safety")
tasks = store.read_all("task")
p = plan_for("frontend", tasks, SBC)
ok("19. STOP wins — the stopped task is not selected", "KAN-740" not in p["selected"])
ok("    while unrelated accelerated work continues", "KAN-741" in p["selected"])
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")

iv = store.create_intervention("hold", "frontend", "ceo", "reason:safety")
tasks = store.read_all("task")
ok("20. HOLD wins for that capability",
   plan_for("frontend", tasks, SBC)["selected"] == [])
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")

iv = store.create_intervention("freeze", None, "ceo", "reason:safety")
tasks = store.read_all("task")
ok("21. FREEZE wins system-wide",
   plan_for("frontend", tasks, SBC)["selected"] == [])
ok("    ACCELERATE never mutates or clears an intervention",
   not store.read("intervention", iv["intervention_id"]).get("cleared_at"))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
tasks = store.read_all("task")
ok("    once cleared, the next recomputation considers the work again",
   plan_for("frontend", tasks, SBC)["selected"] != [])

ok("22. SELF policy unchanged under ACCELERATE",
   policy.validation_route({}) == policy.SELF)
ok("23. QA policy unchanged",
   policy.validation_route({"user_visible_runtime": True}) == policy.QA)
ok("24. PEER policy unchanged",
   policy.validation_route({"schema_change": True}) == policy.PEER)

rc_wait = {"review_type": "peer", "review_owner": None,
           "review_result": "pending", "review_cycle": 1}
pw = mk("KAN-745", route="peer", sid="10045", canonical="review", rc=rc_wait,
        ch={"schema_change": True})
rc_own = {"review_type": "self", "review_owner": "frontend-1",
          "review_result": "pending", "review_cycle": 1}
po_ = mk("KAN-746", canonical="review", sid="10044", rc=rc_own)
tasks = store.read_all("task")
ok("25. a PEER item with NO reviewer keeps waiting — never filled by inference",
   "KAN-745" in [t["work_item_id"] for t in q.review_waiting(tasks)]
   and "KAN-745" not in [t["work_item_id"] for t in q.review_work(tasks)])
ok("    review work with an EXACT owner is schedulable",
   "KAN-746" in [t["work_item_id"] for t in q.review_work(tasks)])
ok("    ACCELERATE never downgrades the waiting PEER route",
   store.read("task", "KAN-745")["execution_profile"]["validation_route"] == "peer")


# ---------------------------------------------------------------- 26-31 capacity

section("capacity: existing seats first, expansion only when justified")

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
f1 = mk("KAN-750", surfaces=["lib/1.dart"]); f2 = mk("KAN-751", surfaces=["lib/2.dart"])
b1 = mk("KAN-752", capability="backend", surfaces=["supabase/1.sql"])
b2 = mk("KAN-753", capability="backend", surfaces=["supabase/2.sql"])
c1 = mk("KAN-754", capability="content", surfaces=["lib/l10n/en.arb"])
tasks = store.read_all("task")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira=dict(JIRA_OK))
by = {p_["capability"]: p_ for p_ in whole["plans"]}
ok("26. unrelated capabilities fill in PARALLEL, never serialized behind each other",
   len(by["frontend"]["selected"]) == 2 and len(by["backend"]["selected"]) == 2
   and len(by["content"]["selected"]) == 1)

ok("27/28. expansion is refused while a defined seat is dormant",
   by["frontend"]["expansion_justified"] is False
   and by["frontend"]["expansion_reason"] == "existing-seat-dormant")
busy = {"frontend-1": "KAN-760", "frontend-2": "KAN-761", "frontend-3": "KAN-762"}
fresh_runtime(); SBC = fresh_roster()
for seat, k in busy.items():
    mk(k, surfaces=["lib/%s.dart" % k], owner=seat)
d1 = mk("KAN-763", surfaces=["lib/d1.dart"]); d2 = mk("KAN-764", surfaces=["lib/d2.dart"])
tasks = store.read_all("task")
just, why = cap.expansion_justified("frontend", tasks, SBC, jira=dict(JIRA_OK))
ok("    with every seat busy and genuine parallel demand, expansion IS justified",
   just is True and why == "parallel-demand")
ok("29. the ceiling comes from topology, not from a constant here",
   cap.topology()["frontend"]["ceiling"] == 9)
ok("    a non-expandable capability is refused",
   cap.expansion_justified("po", tasks, SBC, jira=dict(JIRA_OK))[1]
   in ("capability-not-expandable", "at-ceiling", "unknown-capability"))
nid = cap.next_seat_id("frontend", SBC, historical_ids=("frontend-9",))
ok("    next_seat_id never recycles a historical id", nid != "frontend-9")

p = plan_for("frontend", tasks, SBC)
ok("30. a planned seat's dispatchability is UNKNOWN, never inferred",
   p["dispatchability"] == "UNKNOWN")
ok("31. free seat != available seat — the plan reports seats, not availability",
   "available" not in p and "dispatchable_seats" not in p)


# ---------------------------------------------------------------- 32-34 refill

section("refill, dependency unlock, and clearing")

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
held = mk("KAN-770", surfaces=["lib/app/app_router.dart"], owner="frontend-1")
wait = mk("KAN-771", surfaces=["lib/app/app_router.dart"])
tasks = store.read_all("task")
ok("32a. work colliding with OWNED work is not selected",
   "KAN-771" not in plan_for("frontend", tasks, SBC)["selected"])
store.release("KAN-770", "frontend-1", held["revision"], "ref:done")
tasks = store.read_all("task")
p32 = plan_for("frontend", tasks, SBC)
ok("32b. after release the OWNERSHIP collision clears and the freed capacity refills",
   len(p32["selected"]) == 1 and set(p32["claimable"]) == {"KAN-770", "KAN-771"})
ok("    the two router items are still serialized against each other",
   len(p32["deferred"]) == 1)

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
A = mk("KAN-780", surfaces=["lib/a.dart"]); B = mk("KAN-781", surfaces=["lib/b.dart"])
store.create_dependency({"source_work_item": "KAN-780", "target_work_item": "KAN-781",
                         "relation": "BLOCKS", "completion_condition": "DONE",
                         "product_id": "dabbler", "created_by": "po", "reason_ref": "r"})
tasks = store.read_all("task")
ok("33a. B is blocked while A is not done",
   "KAN-781" not in plan_for("frontend", tasks, SBC)["selected"])
pth = store.path_for("task", "KAN-780")
dd = json.load(open(pth)); dd["lifecycle"]["canonical"] = "done"
dd["lifecycle"]["jira_status_id"] = "10007"; json.dump(dd, open(pth, "w"))
tasks = store.read_all("task")
ok("33b. the instant A is observed DONE, B becomes selectable — derived, not stored",
   "KAN-781" in plan_for("frontend", tasks, SBC)["selected"])
ok("    dependency satisfaction is still never stored",
   "satisfied" not in store.read_all("dependency")[0])

fresh_runtime(); SBC = fresh_roster()
pol = store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
own = mk("KAN-790", surfaces=["lib/o.dart"], owner="frontend-1")
store.clear_execution_policy(pol["policy_id"], pol["revision"], "ceo")
ok("34. clearing ACCELERATE does NOT cancel current ownership",
   store.read("task", "KAN-790")["ownership"]["seat_id"] == "frontend-1")
ok("    and does not touch the task record at all",
   store.read("task", "KAN-790")["revision"] == own["revision"])


# ---------------------------------------------------------------- 35-41 scope/actors

section("scope isolation, excluded actors, failure isolation")

fresh_runtime(); SBC = fresh_roster()
d_ = mk("KAN-800", surfaces=["lib/d.dart"])
o_ = mk("KAN-801", surfaces=["lib/o.dart"], product="other-product")
pp = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "ceo:p")
tasks = store.read_all("task")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira=dict(JIRA_OK))
sel = sum((p_["selected"] for p_ in whole["plans"]), [])
ok("35. PRODUCT scope isolation — only the named product participates",
   "KAN-800" in sel and "KAN-801" not in sel)
store.clear_execution_policy(pp["policy_id"], pp["revision"], "ceo")

fresh_runtime(); SBC = fresh_roster()
fr = mk("KAN-810", surfaces=["lib/f.dart"])
bk = mk("KAN-811", capability="backend", surfaces=["supabase/f.sql"])
cpol = store.set_execution_policy("accelerate", "capability", "frontend", "ceo", "ceo:c")
tasks = store.read_all("task")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira=dict(JIRA_OK))
ok("36. CAPABILITY scope isolation — backend is not accelerated",
   whole["capabilities"] == ["frontend"])
store.clear_execution_policy(cpol["policy_id"], cpol["revision"], "ceo")

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
mk("KAN-820", surfaces=["lib/f.dart"])
mk("KAN-821", capability="cto", surfaces=["docs/ARCHITECTURE.md"])
mk("KAN-822", capability="po", surfaces=["docs/x.md"])
tasks = store.read_all("task")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira=dict(JIRA_OK))
ok("38. executives/management are NOT woken by generic acceleration",
   "cto" not in whole["capabilities"] and "po" not in whole["capabilities"])
ok("    they are excluded by name, and the list is explicit",
   {"cto", "cpo", "cxo", "pm", "po", "analyst"} == cap.EXCLUDED_FROM_ACCELERATION)
ok("37. the Orchestrator is never a capability and can never be selected",
   "orchestrator" not in whole["capabilities"]
   and "orchestrator" not in cap.topology())

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
x1 = mk("KAN-830", surfaces=["lib/1.dart"], canonical="review", sid="10044",
        rc={"review_type": "self", "review_owner": "frontend-1",
            "review_result": "fail", "review_cycle": 1})
x2 = mk("KAN-831", surfaces=["lib/2.dart"])
tasks = store.read_all("task")
ok("41. one task's FAILED review does not cancel unrelated accelerated work",
   "KAN-831" in plan_for("frontend", tasks, SBC)["selected"])
ok("    and the failed task keeps its own normal failure semantics",
   store.read("task", "KAN-830")["review_context"]["review_result"] == "fail")


# ---------------------------------------------------------------- 42-44 exit states

section("exit states are scheduler conditions, never Jira lifecycle")

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
whole = cap.accelerate_plan(store.read_all("task"), store.active_execution_policies(),
                            SBC, jira=dict(JIRA_OK))
ok("42. no work at all -> ACCELERATION DRAINED", whole["condition"] == cap.DRAINED)

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
for i in range(5):
    mk("KAN-84%d" % i, surfaces=["lib/%d.dart" % i])
tasks = store.read_all("task")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira=dict(JIRA_OK))
ok("43. 5 claimable items against 3 seats -> ACCELERATION SATURATED",
   whole["condition"] == cap.SATURATED)
ok("    exactly 3 selected, the rest deferred",
   len(whole["plans"][0]["selected"]) == 3 and len(whole["plans"][0]["deferred"]) == 2)

fresh_runtime(); SBC = fresh_roster()
store.set_execution_policy("accelerate", "system", None, "ceo", "ceo:a")
mk("KAN-850", surfaces=["lib/a.dart"], canonical="ready")
pth = store.path_for("task", "KAN-850")
dd = json.load(open(pth)); dd["surfaces"] = None; json.dump(dd, open(pth, "w"))
tasks = store.read_all("task")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira=dict(JIRA_OK))
ok("44. work remains but none is claimable -> ACCELERATION BLOCKED",
   whole["condition"] == cap.BLOCKED)
ok("    and the structured reasons are reported, not solved",
   "surfaces-unassessed" in whole["blocked_reasons"])
ok("    BLOCKED is not DRAINED — 'stuck' never reads as 'nothing to do'",
   cap.BLOCKED != cap.DRAINED and whole["condition"] != cap.DRAINED)
ok("    none of the three conditions is a Jira status",
   all(board.canonical_for(c) is None
       for c in (cap.DRAINED, cap.SATURATED, cap.BLOCKED)))
ok("    and none is written onto a task record",
   "condition" not in store.read("task", "KAN-850")
   and "acceleration" not in store.read("task", "KAN-850"))


# ---------------------------------------------------------------- 45-50 view/guards

section("Agent View, telemetry, and the remaining guards")

fresh_runtime(); SBC = fresh_roster()
av = view.acceleration_view([], [], {}, [], [], {})
ok("45. Agent View acceleration block declares itself read-only", av["read_only"] is True)
ok("    with no controls of any kind",
   not any(k in av for k in ("activate", "clear", "controls", "buttons", "animation")))
ok("    and reports inactive honestly when no policy exists", av["active"] is False)

pol = store.set_execution_policy("accelerate", "capability", "frontend", "ceo", "ceo:v")
mk("KAN-860", surfaces=["lib/v.dart"])
tasks = store.read_all("task")
av = view.acceleration_view(tasks, store.read_all("policy"), {}, [], [], {})
ok("46. active acceleration is VISIBLE with its scope, target and provenance",
   av["active"] and av["policies"][0]["scope"] == "capability"
   and av["policies"][0]["target"] == "frontend"
   and av["policies"][0]["activated_by"] == "ceo"
   and av["policies"][0]["reason_ref"] == "ceo:v"
   and av["policies"][0]["activated_at"])
ok("    the scheduler condition is surfaced", av["condition"] in
   (cap.DRAINED, cap.SATURATED, cap.BLOCKED))
ok("    dispatchability stays UNKNOWN in the view too",
   av.get("dispatchability") == "UNKNOWN")

src = open(os.path.join(repo_root(), "agent", "state", "view.py")).read()
ok("    Agent View still performs no write",
   not any(w in src for w in ("store.claim(", "store.release(", "set_execution_policy(",
                              "clear_execution_policy(", "_atomic_write(")))

hook = os.path.join(repo_root(), "agent", "scripts", "flow-hook.sh")
ok("47. telemetry is untouched — flow-hook.sh unmodified by ACCELERATE",
   os.path.exists(hook) and "accelerate" not in open(hook).read().lower())
capsrc = open(os.path.join(repo_root(), "agent", "state", "capacity.py")).read()
ok("    and ACCELERATE emits no telemetry event",
   "telemetry" not in capsrc.lower() and "jsonl" not in capsrc.lower())

ok("48. no hard-coded seat count anywhere in the selector",
   not any(str(n) in capsrc.split("ACCELERATE")[1] for n in (" 8,", " 9,", "== 8")))
ok("    seat counts come from bindings and topology",
   len(SBC.get("frontend", [])) == 3)

storesrc = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
# The policy operations, isolated exactly: from the first one to the next section.
accel = storesrc.split("def set_execution_policy")[1].split("\n# ---")[0]
ok("49. ACCELERATE performs no destructive action and bypasses no CEO gate",
   not any(w in accel for w in ("subprocess", "os.remove", "shutil", "rmtree",
                                "git ", "push")))
ok("    and cannot escalate authority — the policy operations write only policy records",
   'path_for("policy"' in accel and 'path_for("task"' not in accel)

ok("50. Jira lifecycle semantics unchanged — the board table is untouched",
   board.STATUSES["10008"][0] == "Ready" and board.STATUSES["10007"][0] == "Done"
   and len(board.STATUSES) == 14)
ok("    ACCELERATE writes no Jira status and holds no transition id",
   "transition" not in capsrc.lower())
ok("40. the selector opens no channel to any agent — no chatter is possible from it",
   not any(w in capsrc for w in ("SendMessage", "Agent(", "wake(")))
ok("39. factual coordination stays the Orchestrator's act, outside this layer",
   "SendMessage" not in storesrc)

sys.exit(summary())
