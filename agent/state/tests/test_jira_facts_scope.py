#!/usr/bin/env python3
"""Per-item Jira facts at the batched planning boundary.

Synthetic runtime and synthetic roster throughout. NO live Jira call is made — the
fact maps here are fixtures, and no Jira cache is created or consulted.

THE DEFECT THIS PINS
  `eligibility_reasons(task, jira=...)` describes ONE item: its due date, its
  acceptance criteria, its status. Batched planning used to take a single `jira=`
  dict and hand it to every task, so a task with no due date could be judged against
  a neighbour's. It failed CLOSED in the run that found it — absent facts yield
  `unverified-jira`, never a pass — but a shared object is unsafe in the other
  direction and is now refused outright rather than reinterpreted.

  So these tests assert two things: each item is judged on its OWN facts, and the
  unsafe call shape can no longer be made at all.

Stdlib only.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, queue as q, capacity as cap, board                 # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


def fresh_roster():
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in {"frontend-1": "frontend", "frontend-2": "frontend",
                       "backend-1": "backend", "backend-2": "backend"}.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return validate.seats_by_capability()


FULL = {"has_due_date": True, "has_acceptance_criteria": True}
NO_DUE = {"has_due_date": False, "has_acceptance_criteria": True}
NO_AC = {"has_due_date": True, "has_acceptance_criteria": False}


def mk(key, *, capability="frontend", surfaces=None, sid="10008", canonical="ready",
       product="dabbler", owner=None):
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": product, "project_id": "app",
        "surfaces": ["lib/%s.dart" % key.lower()] if surfaces is None else surfaces,
        "executor_evidence": [],
        "ownership": ({"seat_id": owner, "claim_ref": "r", "claimed_at": store.now()}
                      if owner else None),
        "review_context": None,
        "lifecycle": {"canonical": canonical, "jira_column": board.column_for(sid),
                      "jira_status_id": sid, "jira_status_name": board.name_for(sid),
                      "observed_at": store.now(), "source": "jira"},
        "execution_profile": {
            "required_capability": capability, "work_effort": 1,
            "validation_route": "self", "completion_route": "DONE",
            "characteristics": {}, "profile_status": "partial",
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


# ---------------------------------------------------------------- 1-6 isolation

section("each item is judged on its OWN facts")

A = mk("KAN-201", surfaces=["lib/a.dart"])
B = mk("KAN-202", surfaces=["lib/b.dart"])
tasks = store.read_all("task")

sel = cap.claimable_items("frontend", tasks,
                          jira_by_key={"KAN-201": dict(FULL), "KAN-202": dict(NO_DUE)})
keys = [t["work_item_id"] for t in sel]
ok("1. two tasks receive different fact objects", keys == ["KAN-201"])
ok("2. A's due date does NOT satisfy B",
   "missing-due-date" in q.unclaimable_reasons(B, all_tasks=tasks, jira=dict(NO_DUE)))
ok("   ... and B is excluded from the batch while A is admitted",
   "KAN-202" not in keys and "KAN-201" in keys)

sel = cap.claimable_items("frontend", tasks,
                          jira_by_key={"KAN-201": dict(FULL), "KAN-202": dict(NO_AC)})
ok("3. A's acceptance criteria do NOT satisfy B",
   [t["work_item_id"] for t in sel] == ["KAN-201"])

sel = cap.claimable_items("frontend", tasks, jira_by_key={"KAN-201": dict(FULL)})
ok("4. an item MISSING from the map stays fail-closed",
   [t["work_item_id"] for t in sel] == ["KAN-201"])
ok("   the missing item reports unverified-jira, not a pass",
   "unverified-jira" in q.unclaimable_reasons(B, all_tasks=tasks, jira=None))

hist = cap.blocked_reasons(tasks, ["frontend"],
                           jira_by_key={"KAN-201": dict(FULL), "KAN-202": dict(NO_DUE)})
ok("5. a VERIFIED task is not reported unverified-jira",
   hist.get("unverified-jira") is None)
ok("6. a mixed batch reports each item independently",
   hist.get("missing-due-date") == 1)

hist2 = cap.blocked_reasons(tasks, ["frontend"], jira_by_key={"KAN-201": dict(FULL)})
ok("   only the genuinely unmapped item counts as unverified",
   hist2.get("unverified-jira") == 1)
ok("   ... and the mapped one still does not", hist2.get("unverified-jira") != 2)


# ---------------------------------------------------------------- 7-13 boundary

section("the unsafe shared-fact call is REFUSED, not reinterpreted")

for name, fn in (
        ("claimable_items", lambda: cap.claimable_items("frontend", tasks, jira=dict(FULL))),
        ("safe_parallel_plan", lambda: cap.safe_parallel_plan("frontend", tasks, SBC,
                                                              jira=dict(FULL))),
        ("expansion_justified", lambda: cap.expansion_justified("frontend", tasks, SBC,
                                                                jira=dict(FULL))),
        ("blocked_reasons", lambda: cap.blocked_reasons(tasks, ["frontend"],
                                                        jira=dict(FULL)))):
    raises("13. %s refuses a shared `jira=` object" % name, fn,
           "does not accept a shared")

try:
    cap.claimable_items("frontend", tasks, jira=dict(FULL))
except TypeError as e:
    ok("   the message tells the caller exactly what to pass instead",
       "jira_by_key" in str(e) and "unverified-jira" in str(e))

ok("14. single-item eligibility is UNCHANGED and still takes `jira=`",
   q.eligibility_reasons(A, dict(FULL)) == []
   and "missing-due-date" in q.eligibility_reasons(A, dict(NO_DUE)))
ok("    single-item unclaimable_reasons is unchanged",
   q.unclaimable_reasons(A, all_tasks=tasks, jira=dict(FULL)) == [])
ok("    queue.queue's existing per-item map still works",
   [t["work_item_id"] for t in q.queue(tasks, "frontend",
                                       {"KAN-201": dict(FULL), "KAN-202": dict(NO_DUE)})]
   == ["KAN-201"])


# ---------------------------------------------------------------- 15-19 plumbed

section("the per-item map reaches every planning entry point")

plan = cap.safe_parallel_plan("frontend", tasks, SBC,
                              jira_by_key={"KAN-201": dict(FULL), "KAN-202": dict(NO_DUE)})
ok("15. safe_parallel_plan uses per-item facts",
   plan["claimable"] == ["KAN-201"] and plan["selected"] == ["KAN-201"])

store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "r")
whole = cap.accelerate_plan(tasks, store.active_execution_policies(), SBC,
                            jira_by_key={"KAN-201": dict(FULL), "KAN-202": dict(NO_DUE)})
ok("16. accelerate_plan uses per-item facts",
   whole["plans"][0]["selected"] == ["KAN-201"])
ok("    and its blocked_reasons are per-item too",
   whole["blocked_reasons"].get("unverified-jira") is None
   and whole["blocked_reasons"].get("missing-due-date") == 1)

src = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
claimfn = src.split("def claim(")[1].split("\ndef ")[0]
ok("17. store.claim is unchanged — still takes ONE task's status id",
   "jira_status_id" in claimfn and "jira_by_key" not in claimfn)

ok("18. fail-closed preserved: no facts at all -> nothing claimable",
   cap.claimable_items("frontend", tasks) == [])

capsrc = open(os.path.join(repo_root(), "agent", "state", "capacity.py")).read()
ok("19. no Jira cache added — facts are parameters and are never written",
   "_atomic_write" not in capsrc and "open(" not in capsrc.split("ACCELERATE")[-1])
ok("    and capacity still makes no network call",
   not any(w in capsrc for w in ("urllib", "requests", "jira.get_issue", "import jira")))


# ---------------------------------------------------------------- ordering leak

section("ordering facts cannot leak between items either")

edges = []
jb = {"KAN-201": {"priority_rank": 9, "due_date": "2026-12-31"},
      "KAN-202": {"priority_rank": 1, "due_date": "2026-01-01"}}
ka = cap.ordering_key(A, edges, jb)
kb = cap.ordering_key(B, edges, jb)
ok("10. A's priority does not leak to B", kb < ka)
ok("11. A's due date does not alter B's ordering",
   ka[1] == 9 and kb[1] == 1 and ka[3] == "2026-12-31" and kb[3] == "2026-01-01")
solo = cap.ordering_key(A, edges, {"KAN-202": {"priority_rank": 1}})
ok("    an unmapped item gets NO borrowed priority", solo[0] == 1)


# ---------------------------------------------------------------- live shape

section("reproduction of the shape found in the real acceptance run")

fresh_runtime(); SBC = fresh_roster()
X = mk("KAN-301", surfaces=["lib/x.dart"])                       # Ready, full facts
Y = mk("KAN-302", surfaces=["lib/y.dart"])                       # Ready, no due date
Z = mk("KAN-303", capability="backend", surfaces=["supabase/z.sql"],
       sid="10043", canonical="development")                     # Back-end
tasks = store.read_all("task")
jb = {"KAN-301": dict(FULL), "KAN-302": dict(NO_DUE), "KAN-303": dict(FULL)}

rx = q.unclaimable_reasons(X, all_tasks=tasks, jira=jb["KAN-301"])
ry = q.unclaimable_reasons(Y, all_tasks=tasks, jira=jb["KAN-302"])
rz = q.unclaimable_reasons(Z, all_tasks=tasks, jira=jb["KAN-303"])
ok("KAN-X (Ready, due date, AC) is CLAIMABLE", rx == [])
ok("KAN-Y reports exactly missing-due-date", ry == ["missing-due-date"])
ok("KAN-Z reports exactly not-ready", rz == ["not-ready"])
ok("Y did NOT inherit X's due date", "missing-due-date" in ry)
ok("Z did NOT inherit X's Ready status", "not-ready" in rz)

plan = cap.safe_parallel_plan("frontend", tasks, SBC, jira_by_key=jb)
ok("the frontend plan admits X alone", plan["selected"] == ["KAN-301"])
hist = cap.blocked_reasons(tasks, ["frontend", "backend"], jira_by_key=jb)
ok("blocked_reasons reports each item's own blocker",
   hist.get("missing-due-date") == 1 and hist.get("not-ready") == 1)
ok("and reports NO unverified-jira, because every item was mapped",
   "unverified-jira" not in hist)

sys.exit(summary())
