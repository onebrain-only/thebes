#!/usr/bin/env python3
"""Validation-route construction and planning boundary regression suite.

No live Jira read and no runtime outside the temporary fixture are used here.
"""
import json
import inspect
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import fresh_seat_registry, ok, section, summary, state_path  # noqa: E402

sys.path.insert(0, state_path())
import board, capacity, policy, queue as q, store, validate  # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    os.makedirs(os.path.join(store.RUNTIME, "tasks"), exist_ok=True)
    return tmp


def task(key, characteristics, route=None, surfaces=None):
    return {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app", "surfaces": surfaces or [],
        "logical_surfaces": [], "ownership": None, "executor_evidence": [],
        "review_context": None,
        "lifecycle": {"canonical": "ready", "jira_column": "Ready",
                      "jira_status_id": "10008", "jira_status_name": "Ready",
                      "observed_at": store.now(), "source": "jira"},
        "execution_profile": {
            "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort"],
            "required_capability": "backend", "work_effort": 1,
            "characteristics": characteristics, "validation_route": route,
            "provenance": {},
        },
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }


def write(rec):
    with open(store.path_for("task", rec["work_item_id"]), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    return store.read("task", rec["work_item_id"])


fresh_runtime()
fresh_seat_registry(validate, {"backend-1": "backend", "backend-2": "backend"})
seats = {"backend": ["backend-1", "backend-2"]}
facts = {"status_id": "10008", "has_due_date": True, "has_acceptance_criteria": True}

section("one canonical policy function")
ok("ordinary -> SELF", policy.validation_route({}) == policy.SELF)
ok("user-visible -> QA", policy.validation_route({"user_visible_runtime": True}) == policy.QA)
ok("schema -> PEER", policy.validation_route({"schema_change": True}) == policy.PEER)
ok("money -> PEER", policy.validation_route({"money_path": True}) == policy.PEER)
ok("security -> PEER", policy.validation_route({"security_sensitive": True}) == policy.PEER)
ok("shared -> PEER", policy.validation_route({"shared_or_contended_surface": True}) == policy.PEER)
ok("strongest characteristic wins",
   policy.validation_route({"user_visible_runtime": True, "security_sensitive": True}) == policy.PEER)
ok("empty evidence is classified; absent evidence is not",
   policy.validation_route_for_profile({"characteristics": {}}) == policy.SELF
   and policy.validation_route_for_profile({}) is None)
ok("routing implementation contains no work-item key exception",
   all("KAN-" not in inspect.getsource(fn)
       for fn in (policy.validation_route, policy.validation_route_for_profile,
                  q.validation_route_for, capacity.safe_parallel_plan)))

section("construction and planning")
legacy = write(task("KAN-901", {"shared_or_contended_surface": True},
                    surfaces=["lib/core/config/supabase_config.dart"]))
unknown = write(task("KAN-902", None))
ordinary = write(task("KAN-903", {}))

ok("a missing materialised route derives from canonical characteristics",
   q.validation_route_for(legacy) == policy.PEER
   and "missing-validation-route" not in q.eligibility_reasons(legacy, facts))
ok("missing classification evidence stays distinguishable from route derivation",
   q.validation_route_for(unknown) is None
   and "missing-validation-route" not in q.eligibility_reasons(unknown, facts))
ok("ordinary legacy profile remains schedulable as SELF",
   q.eligibility_reasons(ordinary, facts) == [] and q.validation_route_for(ordinary) == policy.SELF)

plan = capacity.safe_parallel_plan("backend", [legacy, ordinary], seats,
                                  jira_by_key={"KAN-901": facts, "KAN-903": facts})
routes = {a["work_item_id"]: a["validation_route"] for a in plan["assignments"]}
ok("planner carries policy-derived routes, not task-key rules",
   routes == {"KAN-901": policy.PEER, "KAN-903": policy.SELF})

section("all construction paths materialise the route")
surface_only = write(task("KAN-904", {}, route=None, surfaces=[]))
updated = store.set_surfaces("KAN-904", surface_only["revision"],
                             ["lib/core/config/supabase_config.dart"], "worker:backend-1",
                             basis_ref="test")
ok("surface assessment atomically derives PEER",
   updated["execution_profile"]["validation_route"] == policy.PEER
   and updated["execution_profile"]["completion_route"] == "DONE")

repaired = store.reconcile_missing_validation_routes()
ok("generic backfill repairs classified legacy records only",
   set(repaired) == {"KAN-901", "KAN-903"}
   and store.read("task", "KAN-901")["execution_profile"]["validation_route"] == policy.PEER
   and store.read("task", "KAN-902")["execution_profile"]["validation_route"] is None)

section("maintenance does not hide a read-only future wave")
mode = store.set_operating_mode("SYSTEM_MAINTENANCE", "ceo", "test:future-plan")
future = task("KAN-905", {})
now_plan = capacity.safe_parallel_plan("backend", [future], seats,
                                       jira_by_key={"KAN-905": facts})
future_plan = capacity.safe_parallel_plan(
    "backend", [future], seats, jira_by_key={"KAN-905": facts},
    include_execution_gate=False)
ok("normal planning retains the maintenance execution gate",
   now_plan["selected"] == [])
ok("read-only future planning omits only the mode gate",
   future_plan["selected"] == ["KAN-905"]
   and future_plan["assignments"][0]["validation_route"] == policy.SELF)

sys.exit(summary())
