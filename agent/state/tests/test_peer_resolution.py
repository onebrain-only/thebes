#!/usr/bin/env python3
"""Resolving an EXACT reviewer onto an already-open, unresolved PEER review.

Synthetic runtime and synthetic roster throughout. No live Jira call, no Product file.

THE GAP
  A PEER review may legitimately wait with `review_owner: null` — that is doctrine,
  and it is why `open_review_context` writes the waiting state instead of picking
  someone. But nothing could then fill the owner in: the opener reopens only after a
  recorded FAIL, and `peer_fail_transfer` needs a FAIL to exist. A review that
  started waiting stayed waiting even once a reviewer was named.

WHAT THESE TESTS DEFEND
  That this is RESOLUTION and never REASSIGNMENT. Most of what follows asserts a
  refusal: a settled review, an already-owned one, a SELF or QA context, a reviewer
  who does not hold the work's capability, the executor reviewing itself. An
  operation that could swap a reviewer mid-review would let anyone choose their own,
  which is the entire thing the PEER route exists to prevent.

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


ROSTER = {"frontend-1": "frontend", "frontend-2": "frontend", "frontend-3": "frontend",
          "backend-1": "backend", "backend-2": "backend", "qa": "qa", "cto": "cto"}


def fresh_roster():
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    os.makedirs(b, exist_ok=True)
    for seat, role in ROSTER.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nrole: %s\n' % (seat, role))
    validate.BINDINGS = b
    return validate.seats_by_capability()


def mk(key, *, route="peer", capability="frontend", evidence=("frontend-1",),
       sid="10045", canonical="review", ch=None):
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app",
        "surfaces": ["lib/%s.dart" % key.lower()],
        "executor_evidence": [{"seat_id": s, "evidence_ref": "ref:%s:%d" % (s, i),
                               "evidenced_at": store.now()}
                              for i, s in enumerate(evidence)],
        "ownership": None, "review_context": None,
        "lifecycle": {"canonical": canonical, "jira_column": board.column_for(sid),
                      "jira_status_id": sid, "jira_status_name": board.name_for(sid),
                      "observed_at": store.now(), "source": "jira"},
        "execution_profile": {
            "required_capability": capability, "work_effort": 1,
            "validation_route": route, "completion_route": "DONE",
            "characteristics": ch or ({"schema_change": True} if route == "peer" else {}),
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


def waiting_peer(key, **kw):
    """A PEER review open and WAITING — exactly the state KAN-129 was stuck in."""
    t = mk(key, **kw)
    return store.open_review_context(key, t["revision"], opened_by="orchestrator")


fresh_runtime()
SBC = fresh_roster()
REF = "ceo:authorised-reviewer"


# ---------------------------------------------------------------- 1-5 the happy path

section("resolving an exact reviewer onto a waiting PEER review")

w = waiting_peer("KAN-401")
ok("   the starting state really is WAITING (owner null, pending)",
   w["review_context"]["review_owner"] is None
   and w["review_context"]["review_result"] == "pending")
r = store.resolve_review_owner("KAN-401", w["revision"], "frontend-2", REF)
rc = r["review_context"]
ok("1. an open PEER review with a null owner resolves", rc["review_owner"] == "frontend-2")
ok("2. the cycle is UNCHANGED — this is not a new review", rc["review_cycle"] == 1)
ok("3. the result remains pending — resolution is not a verdict",
   rc["review_result"] == "pending")
ok("4. the exact named reviewer is stored", rc["review_owner"] == "frontend-2")
ok("5. the revision increments exactly once", r["revision"] == w["revision"] + 1)
ok("   the review type is untouched", rc["review_type"] == "peer")
ok("   started_at is preserved", rc["started_at"] == w["review_context"]["started_at"])
ok("   the authorising evidence is recorded", rc["owner_evidence_ref"] == REF)
ok("30. resolution creates NO task ownership", r["ownership"] is None)
ok("    and does not alter executor evidence",
   store.evidenced_executors(r) == ["frontend-1"])
ok("    and does not touch Jira lifecycle",
   r["lifecycle"]["jira_status_id"] == w["lifecycle"]["jira_status_id"])


# ---------------------------------------------------------------- 6-16 refusals

section("every refusal leaves the record untouched")


def unchanged(key, before):
    cur = store.read("task", key)
    return (cur["revision"] == before["revision"]
            and cur["review_context"] == before["review_context"]
            and cur["ownership"] == before["ownership"]
            and cur["executor_evidence"] == before["executor_evidence"])


w = waiting_peer("KAN-402")
raises("6. a stale expected_revision refuses",
       lambda: store.resolve_review_owner("KAN-402", 99, "frontend-2", REF),
       "stale write refused")
ok("   ... state unchanged", unchanged("KAN-402", w))

s_ = mk("KAN-403", route="self", sid="10044", ch={})
so = store.open_review_context("KAN-403", s_["revision"])
raises("7. a SELF context refuses",
       lambda: store.resolve_review_owner("KAN-403", so["revision"], "frontend-2", REF),
       "PEER route only")
ok("   ... state unchanged", unchanged("KAN-403", so))

qa_ = mk("KAN-404", route="qa", sid="10009", ch={"user_visible_runtime": True})
qo = store.open_review_context("KAN-404", qa_["revision"])
raises("8. a QA context refuses",
       lambda: store.resolve_review_owner("KAN-404", qo["revision"], "qa", REF),
       "PEER route only")
ok("   ... QA owner is untouched", store.read("task", "KAN-404")["review_context"]["review_owner"] == "qa")

wrong = mk("KAN-405", route="self", sid="10044", ch={})
raises("9. a wrong validation route refuses before anything else",
       lambda: store.resolve_review_owner("KAN-405", wrong["revision"], "frontend-2", REF),
       "PEER route only")

nc = mk("KAN-406")
raises("10. a missing review context refuses",
       lambda: store.resolve_review_owner("KAN-406", nc["revision"], "frontend-2", REF),
       "no-review-context")

w = waiting_peer("KAN-407")
res = store.resolve_review_owner("KAN-407", w["revision"], "frontend-2", REF)
raises("11. an already-owned context refuses",
       lambda: store.resolve_review_owner("KAN-407", res["revision"], "frontend-2", REF),
       "already-resolved")
raises("12. a REPLACEMENT reviewer refuses — write-once, never reassignment",
       lambda: store.resolve_review_owner("KAN-407", res["revision"], "frontend-3", REF),
       "already-resolved")
ok("    the original reviewer survives the replacement attempt",
   store.read("task", "KAN-407")["review_context"]["review_owner"] == "frontend-2")

w = waiting_peer("KAN-408")
res = store.resolve_review_owner("KAN-408", w["revision"], "frontend-2", REF)
p = store.record_review_result("KAN-408", res["revision"], "frontend-2", "pass", "ref:ok")
raises("13. a PASSED context refuses",
       lambda: store.resolve_review_owner("KAN-408", p["revision"], "frontend-3", REF),
       "already-settled")

w = waiting_peer("KAN-409")
res = store.resolve_review_owner("KAN-409", w["revision"], "frontend-2", REF)
f = store.record_review_result("KAN-409", res["revision"], "frontend-2", "fail", "ref:no")
raises("14. a FAILED context refuses — peer_fail_transfer owns that path",
       lambda: store.resolve_review_owner("KAN-409", f["revision"], "frontend-3", REF),
       "already-settled")

w = waiting_peer("KAN-410")
raises("15. an undeclared seat refuses",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "nobody-9", REF),
       "invalid-peer-reviewer")
ok("    ... state unchanged", unchanged("KAN-410", w))
raises("16. a reviewer of the WRONG capability refuses",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "backend-1", REF),
       "invalid-peer-reviewer")
raises("    the EXECUTOR cannot review its own work under PEER",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "frontend-1", REF),
       "invalid-peer-reviewer")
raises("19. a management seat is not eligible on a frontend item",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "cto", REF),
       "invalid-peer-reviewer")
raises("    the Orchestrator is not a seat and cannot review",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "orchestrator", REF),
       "invalid-peer-reviewer")
raises("    a missing evidence_ref refuses",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "frontend-2", ""),
       "evidence_ref is required")
raises("    an empty reviewer refuses — a reviewer is NAMED, never inferred",
       lambda: store.resolve_review_owner("KAN-410", w["revision"], "", REF),
       "exact reviewer is required")
ok("20. after every refusal above, the record is byte-identical", unchanged("KAN-410", w))

ok("17. an explicitly valid PEER reviewer IS accepted",
   store.resolve_review_owner("KAN-410", w["revision"], "frontend-2",
                              REF)["review_context"]["review_owner"] == "frontend-2")

src = open(os.path.join(repo_root(), "agent", "state", "store.py")).read()
fn = src.split("def resolve_review_owner")[1].split("\ndef ")[0]
ok("18. availability is never consulted or inferred",
   not any(w_ in fn for w_ in ("available", "dispatch", "online", "awake", "idle")))
ok("    eligibility REUSES policy.peer_eligible, not a second model",
   "policy.peer_eligible(" in fn)
ok("    the reviewer is never chosen here — only validated",
   "resolve_owner_or_wait" not in fn and "[0]" not in fn)
ok("29. the cycle is never incremented by resolution", "review_cycle" not in fn)
ok("    Jira is not touched at operation level",
   not any(w_ in fn for w_ in ("jira", "transition", "observe_lifecycle")))


# ---------------------------------------------------------------- 21-25 interplay

section("the explicit path, and non-regression")

w = waiting_peer("KAN-420")
raises("22. record_review_result still REFUSES before resolution",
       lambda: store.record_review_result("KAN-420", w["revision"], "frontend-2",
                                          "pass", "ref:x"),
       "review-owner-unresolved")
res = store.resolve_review_owner("KAN-420", w["revision"], "frontend-2", REF)
p = store.record_review_result("KAN-420", res["revision"], "frontend-2", "pass", "ref:ok")
ok("21. record_review_result works normally AFTER resolution, unmodified",
   p["review_context"]["review_result"] == "pass")
w2 = waiting_peer("KAN-421")
r2 = store.resolve_review_owner("KAN-421", w2["revision"], "frontend-2", REF)
raises("    a non-owner cannot record even after resolution",
       lambda: store.record_review_result("KAN-421", r2["revision"], "frontend-3",
                                          "pass", "ref:x"),
       "not-review-owner")
ok("    ... and the review is still pending after that refusal",
   store.read("task", "KAN-421")["review_context"]["review_result"] == "pending")

w = waiting_peer("KAN-422")
res = store.resolve_review_owner("KAN-422", w["revision"], "frontend-2", REF)
f = store.record_review_result("KAN-422", res["revision"], "frontend-2", "fail", "ref:no")
tr = store.peer_fail_transfer("KAN-422", f["revision"], "frontend-2", "ref:transfer")
ok("23. PEER FAIL transfer is UNCHANGED — reviewer becomes executor",
   store.evidenced_executors(tr) == ["frontend-2"]
   and tr["review_context"]["review_type"] == "self"
   and tr["review_context"]["previous_owner"] == "frontend-1"
   and tr["review_context"]["review_cycle"] == 2)

s_ = mk("KAN-423", route="self", sid="10044", ch={})
so = store.open_review_context("KAN-423", s_["revision"])
sp = store.record_review_result("KAN-423", so["revision"], "frontend-1", "pass", "ref:ok")
ok("24. the SELF path is unchanged end to end",
   so["review_context"]["review_owner"] == "frontend-1"
   and sp["review_context"]["review_result"] == "pass"
   and q.completion_reasons(sp, interventions=[]) == [])

qa_ = mk("KAN-424", route="qa", sid="10009", ch={"user_visible_runtime": True})
qo = store.open_review_context("KAN-424", qa_["revision"])
qp = store.record_review_result("KAN-424", qo["revision"], "qa", "pass", "ref:ok")
ok("25. the QA path is unchanged end to end",
   qo["review_context"]["review_owner"] == "qa"
   and qp["review_context"]["review_result"] == "pass")
ok("    SELF FAIL re-entry is unchanged", hasattr(store, "self_fail_reentry"))


# ---------------------------------------------------------------- 26-28 view & Jira

section("Agent View, and what Jira still cannot do")

w = waiting_peer("KAN-430")
ok("26a. Agent View reads WAITING before resolution",
   view.review_view(w)["display_state"] == "WAITING FOR EXACT REVIEWER")
res = store.resolve_review_owner("KAN-430", w["revision"], "frontend-2", REF)
ok("26b. Agent View reads the resolved reviewer after",
   view.review_view(res)["display_state"] == "REVIEW OWNER: frontend-2")
vsrc = open(os.path.join(repo_root(), "agent", "state", "view.py")).read()
ok("    Agent View still performs no write",
   "resolve_review_owner(" not in vsrc)

w = waiting_peer("KAN-431")
raises("28. a Jira Done alone cannot fabricate a reviewer or a pass",
       lambda: store.observe_lifecycle("KAN-431", w["revision"], "10007"),
       "review_result")
ok("    the review is still waiting, unowned",
   store.read("task", "KAN-431")["review_context"]["review_owner"] is None)
ok("    and it is not completion-eligible",
   "review-owner-unresolved" in q.completion_reasons(store.read("task", "KAN-431"),
                                                     interventions=[]))

section("27. full synthetic: open unresolved -> resolve -> PASS -> eligible")
w = waiting_peer("KAN-440")
ok("  a. opens unresolved", w["review_context"]["review_owner"] is None)
ok("  b. not completion-eligible while unresolved",
   "review-owner-unresolved" in q.completion_reasons(w, interventions=[]))
res = store.resolve_review_owner("KAN-440", w["revision"], "frontend-2", REF)
ok("  c. reviewer resolved, cycle still 1",
   res["review_context"]["review_owner"] == "frontend-2"
   and res["review_context"]["review_cycle"] == 1)
p = store.record_review_result("KAN-440", res["revision"], "frontend-2", "pass", "ref:ok")
ok("  d. PEER PASS recorded", p["review_context"]["review_result"] == "pass")
ok("  e. completion eligible", q.completion_reasons(p, interventions=[]) == [])
d = store.observe_lifecycle("KAN-440", p["revision"], "10007")
ok("  f. Jira Done observed -> canonical done", d["lifecycle"]["canonical"] == "done")
ok("  g. ownership stays null", d["ownership"] is None)
ok("  h. the final record validates",
   [x for x in validate.validate_record("task", d) if " WARN " not in x] == [])

sys.exit(summary())
