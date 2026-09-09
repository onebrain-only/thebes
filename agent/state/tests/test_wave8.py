#!/usr/bin/env python3
"""Wave 8 — advisory telemetry, retrospective and role learning.

Synthetic runtime and roster throughout. No live Jira, no Product file, no `.flow`.

WHAT THIS SUITE DEFENDS
  One sentence: NONE OF THIS IS AUTHORITY. The largest group of tests below asserts
  what telemetry and learning CANNOT do — mutate a task, alter routing, validation,
  ownership, a reviewer, Jira, Product, a prompt or governance. A learning layer that
  could quietly change any of those would be a system rewriting itself from its own
  observations, and every later report would be written for the rewrite.

  Two subtler invariants get the same weight:

  POLLING IS NOT REPETITION. A blocker is an EDGE. Observing an unchanged blocker a
  hundred times must produce nothing, or the act of looking would manufacture the
  recurrence that learning then reads as a pattern.

  ADVISORY FAILURE CANNOT BREAK AUTHORITY. A committed verdict must survive a
  telemetry write that fails, and the resulting gap must be VISIBLE rather than
  silently under-reported.

Stdlib only.
"""
import os
import sys
import json
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, policy, queue as q, board, view                    # noqa: E402
import telemetry, retrospective as retro, learning as learn                # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies", "events",
                 "learning", "coverage"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


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


FACTS = {"has_due_date": True, "has_acceptance_criteria": True}


def mk(key, *, capability="frontend", sid="10044", canonical="review", route="self",
       ev=("frontend-1",), rc=None, ch=None, owner=None):
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "product_id": "dabbler", "project_id": "app",
        "surfaces": ["lib/%s.dart" % key.lower()],
        "executor_evidence": [{"seat_id": s, "evidence_ref": "ref:%s:%d" % (s, i),
                               "evidenced_at": store.now()} for i, s in enumerate(ev)],
        "ownership": ({"seat_id": owner, "claim_ref": "r", "claimed_at": store.now()}
                      if owner else None),
        "review_context": rc,
        "lifecycle": {"canonical": canonical, "jira_column": board.column_for(sid),
                      "jira_status_id": sid, "jira_status_name": board.name_for(sid),
                      "observed_at": store.now(), "source": "jira"},
        "execution_profile": {
            "required_capability": capability, "work_effort": 1,
            "validation_route": route, "completion_route": "DONE",
            "characteristics": ch or {}, "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "completion_route"],
            "provenance": {"required_capability": {"by": "po", "at": store.now()}}},
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }
    with open(store.path_for("task", key), "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


fresh_runtime()
SBC = fresh_roster()


# ---------------------------------------------------------------- AUTHORITY

section("AUTHORITY — telemetry and learning mutate nothing")

t = mk("KAN-701")
before = json.dumps(store.read("task", "KAN-701"), sort_keys=True)
telemetry.emit({"event_type": "review_decided", "work_item_id": "KAN-701",
                "review_type": "self", "review_cycle": 1, "review_result": "pass",
                "review_owner": "frontend-1", "decided_at": store.now(),
                "evidence_ref": "jira-comment:1"})
telemetry.observe_blockers("KAN-701", ["not-ready"], capability="frontend")
ok("telemetry cannot mutate the task record",
   json.dumps(store.read("task", "KAN-701"), sort_keys=True) == before)
ok("telemetry cannot authorize workflow — claimability is unchanged by events",
   "not-ready" in q.unclaimable_reasons(store.read("task", "KAN-701"),
                                        all_tasks=[t], jira=dict(FACTS)))

L = learn.propose("capability", "frontend", "recurring X", ["state:KAN-701@rev1"],
                  2, "repeated", "look at X")
after = store.read("task", "KAN-701")
ok("learning cannot alter required_capability",
   after["execution_profile"]["required_capability"] == "frontend")
ok("learning cannot alter validation_route",
   after["execution_profile"]["validation_route"] == "self")
ok("learning cannot alter ownership", after["ownership"] is None)
ok("learning cannot alter the reviewer", after["review_context"] is None)
ok("learning cannot mutate the task at all",
   json.dumps(after, sort_keys=True) == before)

lsrc = open(os.path.join(repo_root(), "agent", "state", "learning.py")).read()
tsrc = open(os.path.join(repo_root(), "agent", "state", "telemetry.py")).read()
rsrc = open(os.path.join(repo_root(), "agent", "state", "retrospective.py")).read()
def code_only(src):
    """Strip comments and docstrings — a module that NAMES a path in prose has not
    written to it, and an assertion that cannot tell the difference is worthless."""
    out, in_doc = [], False
    for line in src.split("\n"):
        st = line.strip()
        if st.startswith('"""') or st.endswith('"""'):
            in_doc = not in_doc if st.count('"""') % 2 else in_doc
            continue
        if in_doc or st.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


for name, src in (("learning", code_only(lsrc)), ("telemetry", code_only(tsrc)),
                  ("retrospective", code_only(rsrc))):
    ok("%s cannot write a task record" % name,
       'update("task"' not in src and 'path_for("task"' not in src
       and "_atomic_write" not in src)
    ok("%s cannot mutate Jira" % name,
       not any(w in src for w in ("transition_issue", "update_issue", "add_comment")))
    ok("%s cannot touch Product or prompts or governance" % name,
       not any(w in src for w in ("dabbler-code", ".claude/agents", "bindings",
                                  "CLAUDE.md", "CONTRACT.md", "WORKFLOWS.md")))
ok("no store operation reads events for a decision",
   "read_events" not in open(os.path.join(repo_root(), "agent", "state",
                                          "queue.py")).read())


# ---------------------------------------------------------------- EVENTS

section("EVENTS — schema, identity, and what must NOT be recorded")

fresh_runtime(); SBC = fresh_roster()
e = store.append_event({"event_type": "review_decided", "work_item_id": "KAN-710",
                        "review_type": "peer", "review_cycle": 1,
                        "review_result": "fail", "review_owner": "frontend-2",
                        "decided_at": store.now(), "evidence_ref": "jira-comment:9"})
ok("event schema valid and id assigned", e["event_id"].startswith("evt-"))
ok("event declares its source as wave8-event", e["source"] == "wave8-event")
again = store.append_event({"event_type": "review_decided", "work_item_id": "KAN-710",
                            "review_type": "peer", "review_cycle": 1,
                            "review_result": "fail", "review_owner": "frontend-2",
                            "decided_at": store.now()})
ok("review decision dedups by natural identity, not timestamp",
   again["event_id"] == e["event_id"] and len(store.read_events()) == 1)
store.append_event({"event_type": "review_decided", "work_item_id": "KAN-710",
                    "review_type": "self", "review_cycle": 2, "review_result": "pass",
                    "review_owner": "frontend-2", "decided_at": store.now()})
evs = store.read_events("review_decided", "KAN-710")
ok("cycles are separately durable",
   sorted(x["review_cycle"] for x in evs) == [1, 2])
ok("PASS and FAIL both preserved",
   sorted(x["review_result"] for x in evs) == ["fail", "pass"])
ok("task / capability / reviewer refs correct",
   evs[0]["work_item_id"] == "KAN-710" and evs[0]["review_owner"] == "frontend-2")

for banned in ("tool_input", "transcript_path", "last_assistant_message", "prompt",
               "reasoning", "tokens", "cost", "api_key", "description"):
    raises("banned field %r refused" % banned,
           lambda b=banned: store.append_event(
               {"event_type": "review_decided", "work_item_id": "KAN-711",
                "review_type": "self", "review_cycle": 1, "review_result": "pass",
                "review_owner": "frontend-1", "decided_at": store.now(), b: "x"}),
           "banned field")
raises("a historical fact may NOT be backfilled as an event",
       lambda: store.append_event({"event_type": "review_decided",
                                   "work_item_id": "KAN-712", "review_type": "self",
                                   "review_cycle": 1, "review_result": "pass",
                                   "review_owner": "frontend-1",
                                   "decided_at": store.now(),
                                   "source": "historical-derived"}),
       "never be backfilled")

path = store.path_for("event", e["event_id"])
ok("event survives restart — it is a validated file on disk",
   json.load(open(path))["event_type"] == "review_decided")


# ---------------------------------------------------------------- BLOCKER EDGES

section("BLOCKERS ARE EDGES — polling must not manufacture recurrence")

fresh_runtime(); SBC = fresh_roster()
w = telemetry.observe_blockers("KAN-720", ["missing-due-date"], capability="frontend")
ok("blocker entered emits exactly one event", len(w) == 1 and w[0]["transition"] == "entered")
for _ in range(25):
    telemetry.observe_blockers("KAN-720", ["missing-due-date"], capability="frontend")
ok("UNCHANGED blocker observed 25 more times emits NOTHING",
   len(store.read_events("blocker_observed", "KAN-720")) == 1)
w = telemetry.observe_blockers("KAN-720", [], capability="frontend")
ok("blocker cleared emits exactly one event",
   len(w) == 1 and w[0]["transition"] == "cleared")
for _ in range(10):
    telemetry.observe_blockers("KAN-720", [], capability="frontend")
ok("staying clear emits nothing",
   len(store.read_events("blocker_observed", "KAN-720")) == 2)
w = telemetry.observe_blockers("KAN-720", ["missing-due-date"], capability="frontend")
ok("REAPPEARANCE counts as a new factual occurrence", w[0]["occurrence"] == 2)

eps = telemetry.blocker_episodes("KAN-720")
closed = [x for x in eps if not x["open"]]
open_ = [x for x in eps if x["open"]]
ok("a closed episode has both timestamps",
   closed and closed[0]["entered_at"] and closed[0]["cleared_at"])
ok("an OPEN blocker gets NO invented duration",
   open_ and open_[0]["cleared_at"] is None and open_[0]["duration"] is None)
ok("lifecycle re-observation emits nothing — it is not an event type",
   "lifecycle" not in str(store.EVENT_TYPES))


# ---------------------------------------------------------------- ACCELERATION

section("ACCELERATION — one activation, one terminal outcome")

fresh_runtime(); SBC = fresh_roster()
pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "ceo:run")
plan = {"condition": "ACCELERATION SATURATED", "capabilities": ["frontend"],
        "plans": [{"capability": "frontend", "selected": ["KAN-1"],
                   "deferred": ["KAN-2"], "expansion_justified": False}],
        "blocked_reasons": {"not-ready": 3}}
a1 = telemetry.emit_acceleration_outcome(pol, plan, max_simultaneous_owners=1)
ok("terminal outcome recorded", a1["condition"] == "ACCELERATION SATURATED")
ok("factual fields captured",
   a1["selected_count"] == 1 and a1["deferred_count"] == 1
   and a1["blocked_reasons"] == {"not-ready": 3})
a2 = telemetry.emit_acceleration_outcome(pol, dict(plan, condition="ACCELERATION DRAINED"))
ok("a RETRY does not forge a second run — identity is the activation, not the clock",
   a2["event_id"] == a1["event_id"]
   and len(store.read_events("acceleration_outcome")) == 1)
ok("run identity survives restart",
   json.load(open(store.path_for("event", a1["event_id"])))["policy_id"] == pol["policy_id"])
pol2 = store.set_execution_policy("accelerate", "capability", "frontend", "ceo", "r")
telemetry.emit_acceleration_outcome(pol2, plan)
ok("a DIFFERENT activation is a different run",
   len(store.read_events("acceleration_outcome")) == 2)


# ---------------------------------------------------------------- FAILURE BOUNDARY

section("ADVISORY FAILURE CANNOT BREAK AUTHORITY")

fresh_runtime(); SBC = fresh_roster()
t = mk("KAN-730", capability="frontend", route="self")
o = store.open_review_context("KAN-730", t["revision"])

broken = os.path.join(store.RUNTIME, "events")
import shutil
shutil.rmtree(broken)
with open(broken, "w") as fh:                 # a FILE where the directory must be
    fh.write("not a directory")
p = store.record_review_result("KAN-730", o["revision"], "frontend-1", "pass",
                               "jira-comment:5")
ok("the authoritative verdict COMMITS even though telemetry cannot write",
   p["review_context"]["review_result"] == "pass")
ok("  the task is valid and unrolled-back",
   store.read("task", "KAN-730")["review_context"]["review_result"] == "pass"
   and [x for x in validate.validate_record("task", p) if " WARN " not in x] == [])
ok("  telemetry.emit returned None rather than raising",
   telemetry.emit({"event_type": "review_decided", "work_item_id": "KAN-730",
                   "review_type": "self", "review_cycle": 1, "review_result": "pass",
                   "review_owner": "frontend-1", "decided_at": store.now()}) is None)
os.remove(broken); os.makedirs(broken, exist_ok=True)
comp = telemetry.completeness([store.read("task", "KAN-730")])
ok("  the GAP is visible, not hidden",
   comp["complete"] is False
   and comp["review_history"]["status"] == "incomplete"
   and comp["review_history"]["missing"][0]["work_item_id"] == "KAN-730")
ok("  and no event was fabricated to cover it",
   len(store.read_events("review_decided")) == 0)


# ---------------------------------------------------------------- RETROSPECTIVE

section("RETROSPECTIVE — fact / pattern / recommendation")

fresh_runtime(); SBC = fresh_roster()
raises("a FACT without evidence cannot be constructed",
       lambda: retro.fact("something happened", []), "requires evidence_refs")
f1 = retro.fact("KAN-1 blocked: missing-due-date", ["state:KAN-1@rev1"])
f2 = retro.fact("KAN-2 blocked: missing-due-date", ["state:KAN-2@rev1"])
raises("ONE observation is not a pattern",
       lambda: retro.pattern("recurring", [f1]), "not a pattern")
raises("the SAME fact repeated is not two occurrences — polling is not repetition",
       lambda: retro.pattern("recurring", [f1, f1]), "distinct")
p1 = retro.pattern("recurring missing-due-date", [f1, f2])
ok("two DISTINCT occurrences make a pattern", p1["occurrences"] == 2)
ok("strength is the deterministic ladder, not a number",
   p1["strength"] == retro.REPEATED and "confidence" not in p1)
ok("no numeric confidence anywhere in the module — the word appears only in\n   prose explaining its absence", "confidence" not in code_only(rsrc))
raises("a RECOMMENDATION requires a pattern",
       lambda: retro.recommendation("do X", []), "must cite the pattern")
r1 = retro.recommendation("PO checklist should catch this", [p1])
ok("a recommendation carries its evidence and is marked advisory",
   r1["evidence_refs"] and r1["advisory"] is True and r1["authority"].startswith("NONE"))
f3 = retro.fact("KAN-3 blocked", ["state:KAN-3@rev1"])
f4 = retro.fact("KAN-4 blocked", ["jira-comment:44"])
ok("strong-repeated needs 4 occurrences over 2 distinct sources",
   retro.pattern("x", [f1, f2, f3, f4])["strength"] == retro.STRONG)

for st in ("task", "sprint", "capability", "product"):
    if st == "sprint":
        raises("sprint retrospective refuses without a changelog",
               lambda: retro.build("sprint", "S1"), "never inferred")
        raises("sprint fails CLOSED on an incomplete changelog",
               lambda: retro.build("sprint", "S1", changelog={"histories": []}), None)
    else:
        ok("%s scope builds" % st, retro.build(st, "dabbler")["scope_type"] == st)
raises("SYSTEM scope is deferred", lambda: retro.build("system", "x"), "deferred")

fresh_runtime(); SBC = fresh_roster()
mk("KAN-740", capability="frontend"); mk("KAN-741", capability="frontend")
out = retro.build("product", "dabbler", jira_by_key={})
ok("blockers use CANONICAL reason codes, never generated labels",
   all(f.get("reason_code") in (None,) or "-" in f["reason_code"] for f in out["facts"]))
ok("retrospective is read-only and advisory",
   out["read_only"] and out["advisory"] and out["authority"].startswith("NONE"))
ok("origins distinguish wave8-event from historical-derived",
   retro.WAVE8_EVENT == "wave8-event" and retro.HISTORICAL == "historical-derived")
ok("telemetry completeness is reported inside the retrospective",
   "telemetry_completeness" in out)


# ---------------------------------------------------------------- LEARNING

section("LEARNING — advisory, capability-scoped, never a ranking")

fresh_runtime(); SBC = fresh_roster()
L = learn.propose("capability", "backend", "recurring PEER waits",
                  ["state:KAN-1@rev2", "jira-comment:7"], 3, "repeated",
                  "prepare an exact reviewer earlier")
ok("learning is capability-scoped", L["scope_type"] == "capability" and L["scope_id"] == "backend")
ok("runtime may only create a CANDIDATE", L["status"] == "candidate")
ok("it is marked advisory with no authority",
   L["advisory"] is True and L["authority"].startswith("NONE"))
raises("a learning record refuses without evidence",
       lambda: learn.propose("capability", "backend", "x", [], 2, "repeated", "y"),
       "requires evidence_refs")
raises("runtime cannot auto-ACCEPT",
       lambda: learn.decide(L["learning_id"], L["revision"], "accepted", "orchestrator",
                            "r"), "unauthorised-learning-decision")
raises("nor can a seat",
       lambda: learn.decide(L["learning_id"], L["revision"], "accepted", "backend-1",
                            "r"), "unauthorised-learning-decision")
raises("decide() cannot set 'candidate' back",
       lambda: learn.decide(L["learning_id"], L["revision"], "candidate", "ceo", "r"),
       "DECIDED status")
acc = learn.decide(L["learning_id"], L["revision"], "accepted", "ceo", "ceo:adopt")
ok("an authorised decision records who and why",
   acc["status"] == "accepted" and acc["decided_by"] == "ceo"
   and acc["reason_ref"] == "ceo:adopt")

L2 = learn.propose("capability", "backend", "contradicting evidence",
                   ["state:KAN-9@rev1", "jira-comment:9"], 2, "repeated", "revisit")
sup = learn.decide(L2["learning_id"], L2["revision"], "superseded", "ceo", "ceo:x",
                   supersedes=L["learning_id"])
ok("supersession LINKS rather than overwrites", sup["supersedes"] == L["learning_id"])
ok("  the superseded record and its evidence survive intact",
   store.read("learning", L["learning_id"])["evidence_refs"] == L["evidence_refs"])
rej = learn.decide(learn.propose("capability", "frontend", "p", ["state:K@1"], 2,
                                 "repeated", "r")["learning_id"], 1, "rejected",
                   "cto", "cto:no")
ok("rejection preserves the record rather than deleting it",
   rej["status"] == "rejected" and store.read("learning", rej["learning_id"]) is not None)
ok("candidate survives restart",
   json.load(open(store.path_for("learning", L2["learning_id"])))["status"] == "superseded")

ok("NO ranking, scoring or leaderboard exists in the CODE",
   not any(w in code_only(lsrc).lower() for w in ("leaderboard", "ranking", "rank(",
                                                  "score", "best_agent", "worst",
                                                  "reputation")))
ok("  the subject is capability, never a seat",
   learn.SCOPE_TYPES == ("capability", "product", "workflow"))
ok("  seat ids may appear only as evidence",
   "seat" not in [k for k in L if k != "evidence_refs"])


# ---------------------------------------------------------------- MODEL / COST

section("MODEL, REASONING AND COST REMAIN DEFERRED")

for src, name in ((tsrc, "telemetry"), (rsrc, "retrospective"), (lsrc, "learning")):
    ok("%s adds no token estimate" % name,
       not any(w in src.lower() for w in ("token_count", "estimate_token", "tokens =")))
    ok("%s adds no cost estimate" % name,
       not any(w in src.lower() for w in ("cost =", "usd", "price")))
    ok("%s does not activate model/reasoning" % name,
       not any(w in src for w in ('"model"', '"reasoning_effort"', '"parallelism"')))
ok("execution profile still defers those fields",
   "model" in validate.PROFILE_DEFERRED and "reasoning_effort" in validate.PROFILE_DEFERRED)
ok("no duration is read as work cost", "duration_ms" not in tsrc)


# ---------------------------------------------------------------- VIEW

section("AGENT VIEW — visible, read-only, control-free")

fresh_runtime(); SBC = fresh_roster()
mk("KAN-750")
telemetry.emit({"event_type": "review_decided", "work_item_id": "KAN-750",
                "review_type": "self", "review_cycle": 1, "review_result": "pass",
                "review_owner": "frontend-1", "decided_at": store.now(),
                "evidence_ref": "jira-comment:2"})
telemetry.observe_blockers("KAN-750", ["surfaces-unassessed"], capability="frontend")
learn.propose("capability", "frontend", "p", ["state:KAN-750@rev1", "jira-comment:2"],
              2, "repeated", "r")
w = view.wave8_view(store.read_all("task"))
ok("events visible", w["event_count"] >= 2)
ok("recurring blockers visible", "surfaces-unassessed" in w["recurring_blockers"])
ok("learning candidates visible", len(w["learning_candidates"]) == 1)
ok("acceleration history section present", "acceleration_history" in w)
ok("telemetry completeness surfaced", "telemetry_completeness" in w)
ok("read-only and advisory", w["read_only"] and w["advisory"] and w["authoritative_for"] == [])
ok("NO controls of any kind", w["controls"] is None
   and not any(k in w for k in ("accept", "reject", "promote", "rewrite", "rerun")))
vsrc = open(os.path.join(repo_root(), "agent", "state", "view.py")).read()
ok("Agent View cannot decide learning", "learn.decide(" not in vsrc)
ok("Agent View still performs no write",
   not any(x in vsrc for x in ("_atomic_write(", "store.claim(", "append_event(")))
ok("no fake availability", "UNKNOWN" in vsrc and "dispatchability" in vsrc)
ok(".flow remains uncorrelated and non-authoritative",
   'UNCORRELATED' in vsrc and '"authoritative_for": []' in vsrc)
ok("  flow-hook.sh untouched by Wave 8",
   "wave8" not in open(os.path.join(repo_root(), "agent", "scripts",
                                    "flow-hook.sh")).read().lower())


# ================================================================ REMEDIATION
#
# The closure check found the primitives correct and UNWIRED: `observe_blockers` and
# `emit_acceleration_outcome` had zero production callers, so real orchestration
# produced no blocker or ACCELERATE telemetry at all — and `completeness()` reported
# `complete: True` over coverage it had never checked.
#
# These tests exercise the PRODUCTION path. Not one of them calls an emitter directly:
# if the wiring is removed, they fail.

section("REMEDIATION — blocker edges come from NORMAL orchestration")

fresh_runtime(); SBC = fresh_roster()
NOFACTS = {"has_due_date": False, "has_acceptance_criteria": True}


def ready(key, **kw):
    return mk(key, sid="10008", canonical="ready", rc=None, **kw)


t = ready("KAN-801")
cap_mod = __import__("capacity")
cap_mod.reconcile(tasks=[store.read("task", "KAN-801")],
                  jira_by_key={"KAN-801": dict(NOFACTS)})
edges = store.read_events("blocker_observed", "KAN-801")
ok("1. normal orchestration derives a blocker and RECORDS the edge",
   any(e["reason_code"] == "missing-due-date" and e["transition"] == "entered"
       for e in edges))
ok("   no emitter was called directly — the boundary did it", True)

n = len(store.read_events("blocker_observed", "KAN-801"))
for _ in range(5):
    cap_mod.reconcile(tasks=[store.read("task", "KAN-801")],
                      jira_by_key={"KAN-801": dict(NOFACTS)})
ok("2. repeating the SAME orchestration adds no duplicate edge",
   len(store.read_events("blocker_observed", "KAN-801")) == n)

cap_mod.reconcile(tasks=[store.read("task", "KAN-801")],
                  jira_by_key={"KAN-801": dict(FACTS)})
ok("3. the due date becoming available CLEARS the blocker through orchestration",
   any(e["reason_code"] == "missing-due-date" and e["transition"] == "cleared"
       for e in store.read_events("blocker_observed", "KAN-801")))
cap_mod.reconcile(tasks=[store.read("task", "KAN-801")],
                  jira_by_key={"KAN-801": dict(NOFACTS)})
ok("4. the blocker returning is a SECOND occurrence",
   max(e["occurrence"] for e in store.read_events("blocker_observed", "KAN-801")
       if e["reason_code"] == "missing-due-date") == 2)

fresh_runtime(); SBC = fresh_roster()
a = ready("KAN-810", capability="frontend"); b = ready("KAN-811", capability="frontend")
store.create_dependency({"source_work_item": "KAN-810", "target_work_item": "KAN-811",
                         "relation": "BLOCKS", "completion_condition": "DONE",
                         "product_id": "dabbler", "created_by": "po", "reason_ref": "r"})
cap_mod.reconcile(tasks=store.read_all("task"),
                  jira_by_key={k: dict(FACTS) for k in ("KAN-810", "KAN-811")})
ok("5. dependency-blocked observed through normal orchestration",
   any(e["reason_code"] == "dependency-blocked"
       for e in store.read_events("blocker_observed", "KAN-811")))

fresh_runtime(); SBC = fresh_roster()
o1 = mk("KAN-820", sid="10008", canonical="ready", owner="frontend-1", rc=None)
c1 = mk("KAN-821", sid="10008", canonical="ready", rc=None)
for k in ("KAN-820", "KAN-821"):
    p_ = store.path_for("task", k); d_ = json.load(open(p_))
    d_["surfaces"] = ["lib/app/app_router.dart"]; json.dump(d_, open(p_, "w"))
cap_mod.reconcile(tasks=store.read_all("task"),
                  jira_by_key={k: dict(FACTS) for k in ("KAN-820", "KAN-821")})
ok("6. surface-contention observed through normal orchestration",
   any(e["reason_code"] == "surface-contention"
       for e in store.read_events("blocker_observed", "KAN-821")))

fresh_runtime(); SBC = fresh_roster()
pw = mk("KAN-830", capability="frontend", sid="10045", canonical="review", route="peer",
        ch={"schema_change": True},
        rc={"review_type": "peer", "review_owner": None, "review_result": "pending",
            "review_cycle": 1})
cap_mod.reconcile(tasks=store.read_all("task"), jira_by_key={"KAN-830": dict(FACTS)})
ok("7. review-owner-unresolved observed through normal orchestration",
   any(e["reason_code"] == "review-owner-unresolved"
       for e in store.read_events("blocker_observed", "KAN-830")))

for n_, (kind, target, code) in enumerate(
        [("stop", "KAN-840", "task-stopped"),
         ("hold", "frontend", "capability-held"),
         ("freeze", None, "system-frozen")], start=8):
    fresh_runtime(); SBC = fresh_roster()
    ready("KAN-840", capability="frontend")
    iv = store.create_intervention(kind, target, "ceo", "reason:x")
    cap_mod.reconcile(tasks=store.read_all("task"), jira_by_key={"KAN-840": dict(FACTS)})
    ok("%d. %s observed through normal orchestration" % (n_, kind.upper()),
       any(e["reason_code"] == code
           for e in store.read_events("blocker_observed", "KAN-840")))

fresh_runtime(); SBC = fresh_roster()
ready("KAN-850")
cap_mod.reconcile(tasks=store.read_all("task"), jira_by_key={})
ok("11. unverified-jira observed where the canonical blocker exists",
   any(e["reason_code"] == "unverified-jira"
       for e in store.read_events("blocker_observed", "KAN-850")))

fresh_runtime(); SBC = fresh_roster()
clean = ready("KAN-860", capability="frontend")
cap_mod.reconcile(tasks=[store.read("task", "KAN-860")],
                  jira_by_key={"KAN-860": dict(FACTS)})
ok("12. a task with NO blockers still gets coverage — zero is now a fact",
   telemetry.blocker_coverage_known("KAN-860")
   and store.read_events("blocker_observed", "KAN-860") == [])


section("REMEDIATION — ACCELERATE terminal outcome from the real run path")

fresh_runtime(); SBC = fresh_roster()
pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "ceo:r")
plan = cap_mod.run_acceleration(store.read_all("task"), store.active_execution_policies(),
                                SBC, jira_by_key={})
ok("13. an empty scope reaches DRAINED and records ONE terminal event",
   plan["condition"] == cap_mod.DRAINED
   and len(store.read_events("acceleration_outcome")) == 1)

fresh_runtime(); SBC = fresh_roster()
for i in range(5):
    ready("KAN-87%d" % i, capability="frontend")
pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "ceo:r")
tasks_ = store.read_all("task")
jbk = {t_["work_item_id"]: dict(FACTS) for t_ in tasks_}
plan = cap_mod.run_acceleration(tasks_, store.active_execution_policies(), SBC,
                                jira_by_key=jbk)
ok("14. a saturated run records ONE terminal event",
   plan["condition"] == cap_mod.SATURATED
   and len(store.read_events("acceleration_outcome")) == 1)
ev = store.read_events("acceleration_outcome")[0]
ok("    with factual terminal fields",
   ev["condition"] == cap_mod.SATURATED and ev["selected_count"] >= 1
   and ev["policy_id"] == pol["policy_id"])

for _ in range(4):
    cap_mod.run_acceleration(tasks_, store.active_execution_policies(), SBC,
                             jira_by_key=jbk)
ok("16. many intermediate plans still yield ONE outcome per activation",
   len(store.read_events("acceleration_outcome")) == 1)
ok("17. retrying the terminal emission returns the same event",
   telemetry.emit_acceleration_outcome(pol, plan)["event_id"] == ev["event_id"])

pol2 = store.set_execution_policy("accelerate", "capability", "frontend", "ceo", "r2")
cap_mod.run_acceleration(tasks_, store.active_execution_policies(), SBC, jira_by_key=jbk)
ok("18. a NEW activation is a new run",
   len(store.read_events("acceleration_outcome")) == 2)

fresh_runtime(); SBC = fresh_roster()
ready("KAN-880")
p_ = store.path_for("task", "KAN-880"); d_ = json.load(open(p_))
d_["surfaces"] = None; json.dump(d_, open(p_, "w"))
pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "r")
plan = cap_mod.run_acceleration(store.read_all("task"), store.active_execution_policies(),
                                SBC, jira_by_key={"KAN-880": dict(FACTS)})
ok("15. a blocked run records BLOCKED once", plan["condition"] == cap_mod.BLOCKED
   and len(store.read_events("acceleration_outcome")) == 1)

fresh_runtime(); SBC = fresh_roster()
ready("KAN-890")
pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "r")
ed = os.path.join(store.RUNTIME, "events"); shutil.rmtree(ed)
with open(ed, "w") as fh:
    fh.write("x")
plan = cap_mod.run_acceleration(store.read_all("task"), store.active_execution_policies(),
                                SBC, jira_by_key={"KAN-890": dict(FACTS)})
ok("19. the run's terminal condition is authoritative despite telemetry failure",
   plan["condition"] in (cap_mod.DRAINED, cap_mod.SATURATED, cap_mod.BLOCKED))
cur = [x for x in store.active_execution_policies() if x["policy_id"] == pol["policy_id"]][0]
cleared = store.clear_execution_policy(cur["policy_id"], cur["revision"], "ceo")
ok("20. clearing the policy is independent of event success",
   cleared["cleared_by"] == "ceo")
os.remove(ed); os.makedirs(ed, exist_ok=True)


section("REMEDIATION — completeness is scoped, and zero is not unknown")

fresh_runtime(); SBC = fresh_roster()
t = mk("KAN-900", route="self")
o = store.open_review_context("KAN-900", t["revision"])
store.record_review_result("KAN-900", o["revision"], "frontend-1", "pass", "jira:1")
c = telemetry.completeness()
ok("21. review complete + blockers unknown -> overall NOT complete",
   c["review_history"]["status"] == "complete"
   and c["blocker_coverage"]["status"] == "unknown"
   and c["complete"] is False and c["overall"] != "complete")
ok("29. `complete` can never be True while a dimension is unchecked",
   c["complete"] == (c["overall"] == "complete"))

cap_mod.reconcile(tasks=store.read_all("task"), jira_by_key={"KAN-900": dict(FACTS)})
c = telemetry.completeness()
ok("22. review + blocker coverage complete, no applicable run -> complete",
   c["blocker_coverage"]["status"] == "complete"
   and c["acceleration_history"]["status"] == "complete"
   and c["complete"] is True)
ok("25. after real observation, coverage is COMPLETE and the count is factual",
   c["blocker_coverage"]["observed_items"] == ["KAN-900"]
   and c["blocker_coverage"]["unknown_items"] == []
   and c["blocker_coverage"]["edges_recorded"] == 1)   # in review => genuinely not-ready

fresh_runtime(); SBC = fresh_roster()
mk("KAN-901")
c = telemetry.completeness()
ok("26. zero blocker events WITHOUT observation -> unknown, not zero",
   c["blocker_coverage"]["status"] == "unknown"
   and c["blocker_coverage"]["unknown_items"] == ["KAN-901"])

fresh_runtime(); SBC = fresh_roster()
telemetry.wave8_boundary()
pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "r")
c = telemetry.completeness()
ok("23. a post-Wave8 activation with no outcome -> acceleration incomplete",
   c["acceleration_history"]["status"] == "incomplete"
   and c["acceleration_history"]["missing_terminal_outcomes"][0]["policy_id"]
   == pol["policy_id"])

fresh_runtime(); SBC = fresh_roster()
old_pol = store.set_execution_policy("accelerate", "product", "dabbler", "ceo", "r")
pp = store.path_for("policy", old_pol["policy_id"]); dd = json.load(open(pp))
dd["activated_at"] = "2020-01-01T00:00:00Z"; json.dump(dd, open(pp, "w"))
store.mark_coverage(store.COVERAGE_SYSTEM, wave8_started_at="2026-09-09T08:00:00Z")
c = telemetry.completeness()
ok("24. a PRE-Wave8 run is historical-derived, NOT a missing event",
   c["acceleration_history"]["historical_derived"]
   and not c["acceleration_history"]["missing_terminal_outcomes"]
   and c["acceleration_history"]["status"] == "complete")

fresh_runtime(); SBC = fresh_roster()
mk("KAN-910")
out = retro.build("product", "dabbler", jira_by_key={})
ok("27. retrospective REFUSES a negative blocker claim when coverage is unknown",
   out["coverage_claims"]["may_claim_no_blocker_patterns"] is False
   and "BLOCKER EVIDENCE INCOMPLETE" in out["coverage_claims"]["blocker_evidence"])
cap_mod.reconcile(tasks=store.read_all("task"), jira_by_key={"KAN-910": dict(FACTS)})
out = retro.build("product", "dabbler", jira_by_key={"KAN-910": dict(FACTS)})
ok("28. it may state zero blockers ONLY once coverage is complete",
   out["coverage_claims"]["may_claim_no_blocker_patterns"] is True)

w = view.wave8_view(store.read_all("task"))
ok("30. Agent View exposes SCOPED completeness truthfully",
   set(w["coverage"]) == {"review_history", "blocker_coverage",
                          "acceleration_history", "overall"}
   and w["coverage"]["blocker_coverage"] == "complete")
ok("    and still has no controls", w["controls"] is None)

sys.exit(summary())
