#!/usr/bin/env python3
"""BOUNDED RETEST — the review cycle has a ceiling, enforced in the writer.

Synthetic runtime and synthetic roster throughout. The live `agent/state/runtime/**`
is never read for assertions and never written.

WHAT THIS SUITE DEFENDS
  developer -> QA -> developer -> QA -> ... must END. `policy.MAX_REVIEW_CYCLES`
  is the ceiling and `store.open_review_context` is the one writer that creates a
  cycle, so the bound is enforced where it cannot be routed around:

    - cycle 1 is the first review; reopening after FAIL gives 2, then 3;
    - the reopen that would create cycle MAX+1 is REFUSED with
      `retest-limit-reached`, and the record is left EXACTLY as it was — same
      owner, same status, the last FAIL still on it;
    - the read-only explanation in `agent/qa/retest.py` agrees with the writer
      on every cycle, so nothing can predict "permitted" and then be refused;
    - a PEER FAIL is still not a reopen (that is the transfer's job), so the
      bound does not change PEER semantics;
    - a pending review, a passed review and a task with no review are not
      affected: the bound is about REPEATED FAILURE only.

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
import store, validate, policy, board                                       # noqa: E402
sys.path.insert(0, repo_root())
from agent.qa import retest                                                 # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend",
          "backend-1": "backend", "backend-2": "backend", "qa": "qa"}


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


def fail_once(key, seat="frontend-1"):
    """Open (or reopen) the SELF review and record FAIL. Returns the task."""
    t = store.read("task", key)
    o = store.open_review_context(key, t["revision"])
    return store.record_review_result(key, o["revision"], seat, "fail", "ref:defect")


fresh_runtime()
fresh_seat_registry(validate, ROSTER)
LIMIT = policy.MAX_REVIEW_CYCLES


# ---------------------------------------------------------------- the ceiling

section("the ceiling exists and is three")

ok("1. MAX_REVIEW_CYCLES is a positive integer", isinstance(LIMIT, int) and LIMIT >= 1)
ok("   and it is 3: one review plus two retests", LIMIT == 3)

section("cycles advance up to the ceiling, then refuse")

mk("KAN-901", evidence=("frontend-1",))
t = fail_once("KAN-901")
ok("2. cycle 1 records FAIL", t["review_context"]["review_cycle"] == 1
   and t["review_context"]["review_result"] == "fail")
permitted, why = retest.retest_permitted(t["review_context"])
ok("   read-only: cycle 2 is permitted", permitted and "cycle 2 of 3" in why)

t = fail_once("KAN-901")
ok("3. reopen after FAIL is cycle 2", t["review_context"]["review_cycle"] == 2)
t = fail_once("KAN-901")
ok("4. reopen after FAIL is cycle 3 — the last permitted",
   t["review_context"]["review_cycle"] == 3)

permitted, why = retest.retest_permitted(t["review_context"])
ok("5. read-only explanation now refuses", not permitted
   and why.startswith(retest.RETEST_LIMIT_REACHED))

before = store.read("task", "KAN-901")
raises("6. the writer refuses cycle 4 with retest-limit-reached",
       lambda: store.open_review_context("KAN-901", before["revision"]),
       "retest-limit-reached")
after = store.read("task", "KAN-901")
ok("   the record is byte-identical after the refusal", before == after)
ok("   the last FAIL is still on it", after["review_context"]["review_result"] == "fail"
   and after["review_context"]["review_cycle"] == LIMIT)
ok("   no owner was invented", after["ownership"] is None)
ok("   the route was not downgraded", after["review_context"]["review_type"] == "self")

section("read-only and writer agree on every cycle")

mk("KAN-902", evidence=("frontend-1",))
t = fail_once("KAN-902")                      # cycle 1 failed
predictions = []
for _ in range(LIMIT):                        # attempts for cycles 2, 3, 4
    permitted, _why = retest.retest_permitted(t["review_context"])
    try:
        opened = store.open_review_context("KAN-902", t["revision"])
        wrote = True
        t = store.record_review_result("KAN-902", opened["revision"], "frontend-1",
                                       "fail", "ref:d")
    except store.StateError as exc:
        wrote = False
        ok("   the refusal names the rule", "retest-limit-reached" in str(exc))
    predictions.append(permitted == wrote)
ok("7. retest_permitted() predicted the writer on every cycle",
   predictions == [True, True, True])
ok("   two reopens succeeded and the third was refused",
   t["review_context"]["review_cycle"] == LIMIT)

section("the bound is about repeated FAILURE only")

mk("KAN-903", evidence=("frontend-1",))
t = store.open_review_context("KAN-903", store.read("task", "KAN-903")["revision"])
raises("8. a PENDING review is refused as already-open, not as a retest",
       lambda: store.open_review_context("KAN-903", t["revision"]), "review-already-open")

mk("KAN-904", evidence=("frontend-1",))
t = store.open_review_context("KAN-904", store.read("task", "KAN-904")["revision"])
p = store.record_review_result("KAN-904", t["revision"], "frontend-1", "pass", "ref:ok")
raises("9. a PASSED review is not reopened either",
       lambda: store.open_review_context("KAN-904", p["revision"]), "review-already-open")

ok("10. no review context -> permitted, no cycle implied",
   retest.retest_permitted(None) == (True, "no review context yet")
   and retest.next_cycle(None) == 1)

section("PEER semantics are untouched")

mk("KAN-905", route="peer", sid="10045", evidence=("frontend-1",),
   ch={"schema_change": True})
t = store.open_review_context("KAN-905", store.read("task", "KAN-905")["revision"],
                              evidenced_reviewer="frontend-2")
f = store.record_review_result("KAN-905", t["revision"],
                               t["review_context"]["review_owner"], "fail", "ref:d")
raises("11. a failed PEER review is still not reopened here",
       lambda: store.open_review_context("KAN-905", f["revision"]),
       "peer_fail_transfer")

section("infrastructure refusals spend nothing (by construction)")

mk("KAN-906", evidence=("frontend-1",))
t = store.open_review_context("KAN-906", store.read("task", "KAN-906")["revision"])
ok("12. an opened, pending review sits at cycle 1 until a verdict exists",
   t["review_context"]["review_cycle"] == 1
   and t["review_context"]["review_result"] == "pending")
ok("    and the read-only rule says nothing to retest yet",
   retest.retest_permitted(t["review_context"])[1] == "no failed review to retest")

section("T-095(B) — a review opens on RELEASED work")

# The legacy shape KAN-219 was stuck in: an owner that was never released, a
# recorded FAIL, and no way forward — `self_fail_reentry` correctly refuses to
# re-establish an ownership nobody gave up, so the loop dead-ends.
mk("KAN-907", owner="frontend-1", evidence=("frontend-1",))
raises("13. an item that still has an owner cannot open a review",
       lambda: store.open_review_context("KAN-907",
                                         store.read("task", "KAN-907")["revision"]),
       "owner-not-released")
before = store.read("task", "KAN-907")
released = store.release("KAN-907", "frontend-1", before["revision"],
                         "ref: the owner releases, which records the evidence")
opened = store.open_review_context("KAN-907", released["revision"])
ok("    and once released it opens for the evidenced executor",
   opened["review_context"]["review_owner"] == "frontend-1"
   and opened["review_context"]["review_result"] == "pending")

summary()
