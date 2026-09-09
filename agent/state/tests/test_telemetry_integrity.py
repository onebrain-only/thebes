#!/usr/bin/env python3
"""Review-telemetry integrity, advisory correction, and task supersession.

Synthetic runtime and roster throughout. No live Jira, no Product file.

WHAT THIS SUITE DEFENDS

  EVENT LOSS WAS SILENT. `record_review_result` committed the verdict and then
  emitted the advisory `review_decided` event through `telemetry.emit`, which never
  raises. The event validator applied the 300-char identifier bound to
  `evidence_ref` while the authoritative review record applied NO bound at all — so
  every scoped verdict, which is exactly the kind this system asks reviewers to
  write, committed and then vanished. Six of seven review decisions on 2026-09-09
  were lost that way and nothing said so.

  The fix is not a bigger number. It is that ONE bound now gates both layers, so the
  advisory layer can never again reject what the authoritative layer accepted.

  ADVISORY FAILURE STILL MUST NOT REACH AUTHORITY. The tests below therefore also
  prove the opposite direction: when telemetry genuinely fails, the verdict still
  commits, completion still derives, and the gap is VISIBLE rather than papered over.

  A FALSE FACT IS WITHDRAWN, NEVER ERASED. Events are append-only. A correction
  record references the original; the original stays byte-identical and auditable;
  the read side stops counting it; and completeness reports the underlying history
  as still MISSING, because withdrawing a lie is not the same as telling the truth.

  REPLACEMENT IS NOT COMPLETION. `supersede_task` records that Product definition
  replaced an item, without inventing a verdict nobody reached.

Stdlib only.
"""
import os
import sys
import json
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, state_path       # noqa: E402

sys.path.insert(0, state_path())
import store, validate, board, queue as q                           # noqa: E402
import telemetry, retrospective as retro, learning as learn         # noqa: E402


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions", "policies", "events",
                 "learning", "coverage", "corrections"):
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


def mk(key, *, capability="frontend", sid="10044", canonical="review", route="self",
       ev=("frontend-1",), rc=None, owner=None):
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
            "characteristics": {}, "profile_status": "partial",
            "effective_fields": ["project_id", "required_capability", "work_effort",
                                 "completion_route"],
            "provenance": {"required_capability": {"by": "po", "at": store.now()}}},
        "created_at": store.now(), "updated_at": store.now(), "revision": 1,
    }
    with open(store.path_for("task", key), "w") as fh:
        json.dump(rec, fh)
    return store.read("task", key)


def pending(kind="self", owner="frontend-1"):
    return {"review_type": kind, "review_result": "pending", "review_cycle": 1,
            "review_owner": owner, "started_at": store.now(),
            "opened_by": "orchestrator"}


TMP = fresh_runtime()
SBC = fresh_roster()

# A real scoped verdict from the 2026-09-09 run, at its real length. This is the
# shape that was silently dropped — not a synthetic pathological string.
LONG = ("Jira KAN-128 comment 10779 — backend-2 PEER PASS scoped to available "
        "evidence. AC1 PASS in source: seven ON CONFLICT DO NOTHING at "
        ":203/:247/:327/:445/:540/:552/:564 with :407 correctly excluded, both "
        "indexes plus ref_id SET NOT NULL in one transaction, DROP FUNCTION naming "
        "the baseline 5-arg signature, all five bodies normalised-diffed against "
        "baseline_schema.sql. Grant rule PASS in source (explicit revokes :277 "
        "PUBLIC, :278 anon ahead of the grants). AC3 PASS independently re-derived "
        "— the reviewer ran supabase/tests/kan128/run.sh itself in a throwaway "
        "container rather than accept the reported output. AC2 PARTIAL: authored, "
        "cto-confirmed and committed PASS; APPLIED NOT VERIFIABLE, resting solely "
        "on comment 10730 after a live read was attempted and denied.")

# ------------------------------------------------------- 13-16. long refs

section("EVIDENCE LENGTH — the advisory layer accepts what authority accepts")

ok("[13] the real dropped verdict is longer than the identifier bound",
   len(LONG) > validate.MAX_REF_LEN)
ok("[13] and within the shared verdict bound", len(LONG) <= validate.MAX_VERDICT_REF_LEN)

t = mk("KAN-801", rc=pending("self"), route="self")
r = store.record_review_result("KAN-801", t["revision"], "frontend-1", "pass", LONG)
evs = store.read_events("review_decided", "KAN-801")
ok("[13] a legitimate LONG evidence_ref records a review_decided event", len(evs) == 1)
ok("[13] the event carries the verdict reference intact, not truncated",
   evs[0].get("evidence_ref") == LONG)
ok("[13] the authoritative verdict is recorded too",
   r["review_context"]["review_result"] == "pass")

t = mk("KAN-802", rc=pending("self"), route="self")
store.record_review_result("KAN-802", t["revision"], "frontend-1", "pass", LONG)
ok("[14] SELF with a long evidence ref emits",
   len(store.read_events("review_decided", "KAN-802")) == 1)
ok("[14] and the event records the route", store.read_events(
    "review_decided", "KAN-802")[0].get("review_type") == "self")

t = mk("KAN-803", sid="10009", route="qa", rc=pending("qa", "qa"))
store.record_review_result("KAN-803", t["revision"], "qa", "pass", LONG)
ok("[15] QA with a long evidence ref emits",
   len(store.read_events("review_decided", "KAN-803")) == 1)

t = mk("KAN-804", sid="10045", route="peer", rc=pending("peer", "frontend-2"))
store.record_review_result("KAN-804", t["revision"], "frontend-2", "pass", LONG)
ok("[16] PEER with a long evidence ref emits",
   len(store.read_events("review_decided", "KAN-804")) == 1)
ok("[16] the event names the reviewer, not the executor", store.read_events(
    "review_decided", "KAN-804")[0].get("review_owner") == "frontend-2")

section("THE BOUND IS SHARED, NOT MERELY LARGER")

TOO_LONG = "x" * (validate.MAX_VERDICT_REF_LEN + 1)
errs = validate.validate_record("event", {
    "event_id": "evt-x", "event_type": "review_decided", "observed_at": store.now(),
    "source": "wave8-event", "seq": 1, "work_item_id": "KAN-805",
    "review_type": "self", "review_cycle": 1, "review_result": "pass",
    "review_owner": "frontend-1", "decided_at": store.now(),
    "evidence_ref": TOO_LONG})
ok("[18] the event schema still refuses a genuine report body",
   any("verdict reference" in e for e in errs))
ok("[18] validation was NOT simply removed",
   validate.MAX_VERDICT_REF_LEN < 10000 and hasattr(validate, "_verdict_reflen"))

t = mk("KAN-806", rc=pending("self"), route="self")
raises("[18] and the AUTHORITATIVE layer refuses the same value — the two bounds "
       "cannot diverge again",
       lambda: store.record_review_result("KAN-806", t["revision"], "frontend-1",
                                          "pass", TOO_LONG),
       "verdict reference")
ok("[18] a refused verdict wrote nothing",
   (store.read("task", "KAN-806").get("review_context") or {})
   .get("review_result") == "pending")

# ------------------------------------------------------- 17. no backpressure

section("NO TELEMETRY BACKPRESSURE — authority survives an advisory failure")

t = mk("KAN-807", rc=pending("self"), route="self")
real_emit = telemetry.emit_review_decided
telemetry.emit_review_decided = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError("event store on fire"))
try:
    r = store.record_review_result("KAN-807", t["revision"], "frontend-1", "pass",
                                   "jira-comment:1")
finally:
    telemetry.emit_review_decided = real_emit
ok("[17] the verdict still commits when telemetry raises",
   r["review_context"]["review_result"] == "pass")
ok("[17] completion still derives from authoritative state",
   q.completion_reasons(dict(r, lifecycle=dict(r["lifecycle"], canonical="review")))
   == [])
ok("[17] and the missing event is VISIBLE, not silently absent",
   any(m.get("work_item_id") == "KAN-807"
       for m in telemetry.completeness()["review_history"]["missing"]))

# ------------------------------------------------------- 19. immutability

section("LEGITIMATE EVENTS REMAIN IMMUTABLE")

before = json.dumps(store.read("event", store.read_events(
    "review_decided", "KAN-801")[0]["event_id"]), sort_keys=True)
store.record_review_result  # no-op reference; re-emitting must not rewrite
telemetry.emit({"event_type": "review_decided", "work_item_id": "KAN-801",
                "review_type": "self", "review_cycle": 1, "review_result": "fail",
                "review_owner": "frontend-2", "decided_at": store.now(),
                "evidence_ref": "an attempt to overwrite the verdict"})
after = json.dumps(store.read("event", store.read_events(
    "review_decided", "KAN-801")[0]["event_id"]), sort_keys=True)
ok("[19] re-emitting on the same natural key does NOT rewrite the event",
   before == after)
ok("[19] and does not create a second one",
   len(store.read_events("review_decided", "KAN-801")) == 1)

# ------------------------------------------------------- 20-30. correction

section("CORRECTION — a false advisory fact is withdrawn, never erased")

false_ev = telemetry.emit({
    "event_type": "review_decided", "work_item_id": "KAN-808", "review_type": "self",
    "review_cycle": 1, "review_result": "pass", "review_owner": "frontend-1",
    "decided_at": store.now(), "evidence_ref": "short-ref-test"})
mk("KAN-808", rc=dict(pending("self"), review_result="pass",
                      evidence_ref="short-ref-test", decided_at=store.now()))
ok("[20] the false event exists before correction", false_ev is not None)

cor = store.correct_event(false_ev["event_id"], "ceo",
                          "diagnostic mutation wrote a fabricated evidence_ref",
                          evidence_ref="orchestrator session 2026-09-09")
ok("[20] a false advisory event can be canonically invalidated",
   cor["correction_kind"] == "invalidate")
ok("[21] the ORIGINAL record still exists byte-identical",
   store.read("event", false_ev["event_id"]) == false_ev)
ok("[21] and is still visible in the audit view",
   any(e["event_id"] == false_ev["event_id"]
       for e in store.read_events("review_decided", "KAN-808")))
ok("[22] the correction references the original by id",
   cor["corrects_event_id"] == false_ev["event_id"])
ok("[22] and records who and why",
   cor["corrected_by"] == "ceo" and "fabricated" in cor["reason_ref"])

raises("[23] an executor cannot correct advisory history",
       lambda: store.correct_event(false_ev["event_id"], "frontend-1", "tidy"),
       "not-a-correction-authority")
raises("[23] nor the orchestrator",
       lambda: store.correct_event(false_ev["event_id"], "orchestrator", "tidy"),
       "not-a-correction-authority")
raises("[23] nor po",
       lambda: store.correct_event(false_ev["event_id"], "po", "tidy"),
       "not-a-correction-authority")
ok("[24] the CEO can", store.correct_event(false_ev["event_id"], "ceo", "again")
   ["correction_id"] == cor["correction_id"])
raises("[24] a correction naming no real event is refused",
       lambda: store.correct_event("evt-does-not-exist", "ceo", "why"),
       "no-such-event")
raises("[24] a correction with no stated reason is refused",
       lambda: store.correct_event(false_ev["event_id"], "ceo", ""),
       "reason_ref is required")

task_before = json.dumps(store.read("task", "KAN-808"), sort_keys=True)
store.correct_event(false_ev["event_id"], "ceo", "no-op re-correction")
ok("[25] correcting an event does NOT mutate the task",
   json.dumps(store.read("task", "KAN-808"), sort_keys=True) == task_before)
ok("[25] the verdict on the task is untouched",
   store.read("task", "KAN-808")["review_context"]["review_result"] == "pass")
ok("[26] correction touches no Jira field — the record carries none",
   not (set(cor) & {"jira_status_id", "lifecycle", "status"}))

ok("[27] the retrospective's factual event view excludes it",
   all(e["event_id"] != false_ev["event_id"]
       for e in store.read_events(include_invalidated=False)))
ok("[27] while the audit view still contains it",
   any(e["event_id"] == false_ev["event_id"] for e in store.read_events()))
ok("[28] learning reads the same filtered view — no invalidated event reaches it",
   false_ev["event_id"] not in {e.get("event_id")
                                for e in telemetry._safe_read("review_decided")})
ok("[29] completeness does NOT count an invalidated event",
   any(m.get("work_item_id") == "KAN-808"
       for m in telemetry.completeness()["review_history"]["missing"]))
ok("[29] withdrawing a lie is not the same as telling the truth — the history stays "
   "MISSING rather than becoming complete",
   telemetry.completeness()["review_history"]["status"] == "incomplete")
ok("[30] the correction itself is auditable",
   len(store.read_corrections(false_ev["event_id"])) == 1)
ok("[30] and invalidated_event_ids reports it",
   false_ev["event_id"] in store.invalidated_event_ids())
ok("[30] a legitimate event is NOT invalidated by another event's correction",
   store.read_events("review_decided", "KAN-801")[0]["event_id"]
   not in store.invalidated_event_ids())

# ------------------------------------------------------- 22. supersession

section("SUPERSESSION — replaced is not validated, and never Done")

mk("KAN-900", sid="10009", route="qa", rc=pending("qa", "qa"), canonical="review")
mk("KAN-901", sid="10004", canonical="ready", route="peer", ev=())
old = store.read("task", "KAN-900")

raises("[22] an executor cannot supersede work out of review",
       lambda: store.supersede_task("KAN-900", old["revision"], "KAN-901",
                                    "frontend-1", "ruling"),
       "not-a-supersession-authority")
raises("[22] a replacement that does not exist is refused",
       lambda: store.supersede_task("KAN-900", old["revision"], "KAN-999", "po",
                                    "ruling"),
       "no-such-replacement")
raises("[22] an item cannot supersede itself",
       lambda: store.supersede_task("KAN-900", old["revision"], "KAN-900", "po",
                                    "ruling"),
       "cannot supersede itself")
raises("[22] a replacement with no reason is refused",
       lambda: store.supersede_task("KAN-900", old["revision"], "KAN-901", "po", ""),
       "reason_ref is required")

s = store.supersede_task("KAN-900", old["revision"], "KAN-901", "po",
                         "CEO ruling: routing defect, re-scoped", jira_status_id="10004")
ok("[22] po may supersede", s["superseded"]["replaced_by"] == "KAN-901")
ok("[22] the open review context is CLEARED, not decided",
   s["review_context"] is None)
ok("[22] no verdict was invented",
   s["superseded"]["review_state_at_supersession"] == "pending")
ok("[22] the item is NOT done", s["lifecycle"]["canonical"] != "done")
ok("[22] lifecycle now matches the observed Jira status", s["lifecycle"]["canonical"]
   == board.canonical_for("10004"))
ok("[22] the reason is recorded", "re-scoped" in s["superseded"]["reason_ref"])
ok("[22] ownership is released", s["ownership"] is None)
ok("[22] the replacement is untouched",
   store.read("task", "KAN-901").get("superseded") is None)
ok("[22] Persistent State and Jira now agree",
   s["lifecycle"]["jira_status_id"] == "10004")

mk("KAN-902", sid="10007", canonical="done",
   rc=dict(pending("self"), review_result="pass", evidence_ref="x",
           decided_at=store.now()))
raises("[22] completed work cannot be superseded",
       lambda: store.supersede_task("KAN-902", store.read("task", "KAN-902")["revision"],
                                    "KAN-901", "po", "why"),
       "already-done")
mk("KAN-903", sid="10044", canonical="review",
   rc=dict(pending("self"), review_result="pass", evidence_ref="x",
           decided_at=store.now()))
raises("[22] nor may a PASS verdict be discarded by superseding",
       lambda: store.supersede_task("KAN-903", store.read("task", "KAN-903")["revision"],
                                    "KAN-901", "po", "why"),
       "already-validated")

_errs = [e for e in validate.check(store.RUNTIME) if " WARN " not in e]
if _errs:
    print("  validator errors: " + " | ".join(_errs[:4]))
ok("validator accepts every record this suite wrote", not _errs)

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(summary())
