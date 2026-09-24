"""Concurrent dispatch must not bypass the claim-time safety rules.

With bounded concurrent Listener dispatch (2026-09-25), two Controller processes
may claim and lease at the same instant. Every rule below is re-checked inside
the global `execution-domain` lock, so racing threads must still produce exactly
the outcomes sequential execution would. Real threads, released together.

Stdlib only.
"""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import fresh_seat_registry, ok, section, summary, state_path  # noqa: E402

sys.path.insert(0, state_path())
import store, validate, board                              # noqa: E402

OBS = store.now()


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    fresh_seat_registry(validate, {"ux-engineer-%d" % i: "ux-engineer"
                                   for i in range(1, 10)})
    store.set_operating_mode("PRODUCT_EXECUTION", "orchestrator", "concurrency suite")
    return tmp


def lc(sid):
    return {"canonical": board.canonical_for(sid), "jira_column": board.column_for(sid),
            "jira_status_id": sid, "jira_status_name": board.name_for(sid),
            "observed_at": OBS, "source": "jira"}


def task(key, cap="ux-engineer", surfaces=None):
    prof = {"profile_status": "partial", "required_capability": cap,
            "completion_route": "DONE", "work_effort": 1,
            "provenance": {"required_capability": {"by": "system-maintenance"},
                           "completion_route": {"by": "system-policy"}},
            "effective_fields": ["project_id", "required_capability",
                                 "completion_route", "work_effort"]}
    return store.create("task", {
        "work_item_id": key, "product_id": "dabbler", "project_id": "app",
        "record_type": "executable", "lifecycle": lc("10008"),
        "executor_evidence": [], "execution_profile": prof, "review_context": None,
        "ownership": None, "surfaces": surfaces if surfaces is not None else []},
        rid=key)


def race(*calls):
    """Run each callable in its own thread, released together. -> (wins, errors)."""
    barrier = threading.Barrier(len(calls))
    wins, errors = [], []

    def run(fn):
        barrier.wait()
        try:
            wins.append(fn())
        except store.StateError as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=run, args=(fn,)) for fn in calls]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    return wins, errors


def claimer(key, seat):
    rev = store.read("task", key)["revision"]
    return lambda: store.claim(key, seat, "race:" + key, rev,
                               capability_of_seat="ux-engineer", jira_status_id="10008")


fresh_runtime()

# ------------------------------------------------------------------ seats
section("SEAT — one seat never owns two tasks, even when claimed concurrently")
task("KAN-970")
task("KAN-971")
wins, errors = race(claimer("KAN-970", "ux-engineer-1"),
                    claimer("KAN-971", "ux-engineer-1"))
ok("[5] same seat, two tasks at once -> exactly one claim wins",
   len(wins) == 1 and len(errors) == 1)
ok("[5] the loser is refused as seat-already-owns",
   errors and "seat-already-owns" in errors[0])

task("KAN-972")
task("KAN-973")
wins, errors = race(claimer("KAN-972", "ux-engineer-2"),
                    claimer("KAN-973", "ux-engineer-3"))
ok("[1] two independent tasks on two free seats both claim concurrently",
   len(wins) == 2 and not errors)

task("KAN-974")
wins, errors = race(claimer("KAN-974", "ux-engineer-4"),
                    claimer("KAN-974", "ux-engineer-5"))
ok("[5] one task, two seats at once -> exactly one owner",
   len(wins) == 1 and len(errors) == 1)

# ------------------------------------------------------------------ dependencies
section("DEPENDENCY — blocked work is refused under concurrency")
task("KAN-975")
task("KAN-976")
store.create_dependency({"product_id": "dabbler", "source_work_item": "KAN-975",
                         "target_work_item": "KAN-976", "relation": "BLOCKS",
                         "completion_condition": "DONE"})
wins, errors = race(claimer("KAN-975", "ux-engineer-6"),
                    claimer("KAN-976", "ux-engineer-7"))
ok("[4] the source claims; the dependency-blocked target is refused",
   [w["work_item_id"] for w in wins] == ["KAN-975"]
   and any("dependency-blocked" in e for e in errors))

# ------------------------------------------------------------------ surfaces
section("SURFACE — contended paths are refused under concurrency")
task("KAN-977", surfaces=["lib/src/controls/button.dart"])
task("KAN-978", surfaces=["lib/src/controls/button.dart"])
wins, errors = race(claimer("KAN-977", "ux-engineer-8"),
                    claimer("KAN-978", "ux-engineer-9"))
ok("[6] two tasks on the same surface -> exactly one claim wins",
   len(wins) == 1 and len(errors) == 1)
ok("[6] the loser is refused for surface contention",
   errors and "surface-contention" in errors[0])

# ------------------------------------------------------------------ leases
section("LEASE — only the owner may open one, concurrently or not")
owned = store.read("task", "KAN-972")
wins, errors = race(
    lambda: store.open_execution_lease("KAN-972", "ux-engineer-2", "wake:owner"),
    lambda: store.open_execution_lease("KAN-972", "ux-engineer-3", "wake:intruder"))
ok("[6] the owner's lease opens; a non-owner's is refused",
   [w["seat_id"] for w in wins] == ["ux-engineer-2"]
   and any("not-owner" in e for e in errors))

try:
    store.set_operating_mode("SYSTEM_MAINTENANCE", "orchestrator", "mode race",
                             expected_revision=store.read_all("operating_mode")[0]["revision"])
    refused = False
except store.StateError as exc:
    refused = "active execution leases" in str(exc)
ok("[6] maintenance cannot begin while a lease is open",
   refused and store.current_operating_mode() == "PRODUCT_EXECUTION")

sys.exit(summary())
