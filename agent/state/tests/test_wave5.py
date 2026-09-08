"""Wave 5 behavioural suite — board model, lifecycle, policy, review, sprint, store.

Migrated verbatim from the Wave 5 external fixtures on 2026-09-08 so the canonical
repository verifies itself from a fresh clone with no external file. The assertions
are unchanged; only the harness and the root resolution moved.
"""
import os, sys, tempfile, shutil
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path

ROOT = repo_root()
sys.path.insert(0, state_path())
import policy, sprint, validate, store, board

TZ = ZoneInfo("Asia/Dubai")

section("LIVE BOARD MODEL")
ok("Backlog column holds To Do 10004", board.statuses_in_column("Backlog") == ("10004",))
ok("Ready column holds Ready 10008",   board.statuses_in_column("Ready") == ("10008",))
ok("OPERATIONS column holds THREE statuses",
   set(board.statuses_in_column("Operations")) == {"10047","10048","10049"})
ok("REVIEW column holds THREE statuses",
   set(board.statuses_in_column("Review")) == {"10009","10044","10045"})
ok("Frontend Development holds Front-end 10046",
   board.statuses_in_column("Frontend Development") == ("10046",))
ok("Backend Development holds Back-end 10043",
   board.statuses_in_column("Backend Development") == ("10043",))
ok("live spelling Self-review (lowercase r)", board.name_for("10044") == "Self-review")
ok("live spelling Peer-review (lowercase r)", board.name_for("10045") == "Peer-review")
ok("10004 is named 'To Do', NOT 'Backlog'",  board.name_for("10004") == "To Do")
ok("column(10044)=Review, name=Self-review — column != status",
   board.column_for("10044") == "Review" and board.name_for("10044") != "Review")

section("CANONICAL MAPPING")
for sid in ("10047","10048","10049","10046","10043"):
    ok("execution status %s (%s) -> DEVELOPMENT" % (sid, board.name_for(sid)),
       board.canonical_for(sid) == "development")
for sid in ("10009","10044","10045"):
    ok("review status %s (%s) -> REVIEW" % (sid, board.name_for(sid)),
       board.canonical_for(sid) == "review")
ok("10004 -> READY", board.canonical_for("10004") == "ready")
ok("10008 -> READY", board.canonical_for("10008") == "ready")
ok("10007 -> DONE",  board.canonical_for("10007") == "done")
ok("exactly 4 canonical states", set(board.CANONICAL_STATES) == {"ready","development","review","done"})
print("  -- legacy statuses still mapped for history --")
ok("10005 In Progress legacy -> development",
   board.is_legacy("10005") and board.canonical_for("10005") == "development")
ok("10010 Development legacy -> development",
   board.is_legacy("10010") and board.canonical_for("10010") == "development")
ok("10006 In Review legacy -> review",
   board.is_legacy("10006") and board.canonical_for("10006") == "review")
ok("legacy statuses have NO column",
   all(board.column_for(s) is None for s in board.LEGACY_STATUS_IDS))

section("LEGACY TRANSITION GUARD (historical read != current transition authority)")
for sid in ("10005", "10010", "10006"):
    raises("REJECT legacy target %s (%s)" % (sid, board.name_for(sid)),
           lambda sid=sid: board.assert_transition_target(sid), "LEGACY status")
    ok("is_valid_transition_target(%s) is False" % sid,
       board.is_valid_transition_target(sid) is False)
    ok("...but %s is STILL readable historically -> %s" % (sid, board.canonical_for(sid)),
       board.canonical_for(sid) is not None)
raises("REJECT unknown target 99999",
       lambda: board.assert_transition_target("99999"), "unknown Jira status id")
for sid in board.LIVE_STATUS_IDS:
    ok("ACCEPT live target %s (%s)" % (sid, board.name_for(sid)),
       board.assert_transition_target(sid) == sid)
ok("no capability maps to a legacy status",
   all(not board.is_legacy(board.execution_status_for(c))
       for c in ("frontend","backend","content","product-designer","ux-engineer","devops","analyst")))
ok("no route maps to a legacy status",
   all(not board.is_legacy(board.review_status_for(r)) for r in ("self","peer","qa")))
# a historical observation naming a legacy id is ACCEPTED (WARN), not rejected
_h = {"total":1,"histories":[{"created":"2026-09-07T09:43:11.435+0400",
      "items":[{"field":"status","from":"10010","to":"10009","fromString":"Development","toString":"QA-Test"}]}]}
ok("historical replay still returns a legacy id",
   sprint.status_id_at("10009", _h, datetime(2026,9,7,9,35,tzinfo=TZ)) == "10010")

section("CAPABILITY -> ONE EXECUTION STATUS (alternatives, not a sequence)")
exp = {"frontend":"10046","backend":"10043","content":"10048",
       "product-designer":"10047","ux-engineer":"10047","devops":"10049","analyst":"10049"}
for cap, sid in exp.items():
    ok("%-17s -> %s (%s)" % (cap, sid, board.name_for(sid)),
       board.execution_status_for(cap) == sid)
ok("unknown specialist -> Operations 10049", board.execution_status_for("whatever") == "10049")
ok("qa has NO execution status", board.execution_status_for("qa") is None)
ok("content NOT collapsed into Operations", board.execution_status_for("content") != "10049")
ok("design NOT collapsed into Operations",
   board.execution_status_for("product-designer") != "10049")
ok("Design/Content/Operations are 3 DISTINCT ids",
   len({board.execution_status_for(c) for c in ("product-designer","content","devops")}) == 3)
ok("frontend and backend are DISTINCT ids",
   board.execution_status_for("frontend") != board.execution_status_for("backend"))

section("ROUTE -> REVIEW STATUS")
ok("SELF -> Self-review 10044", board.review_status_for("self") == "10044")
ok("PEER -> Peer-review 10045", board.review_status_for("peer") == "10045")
ok("QA   -> QA-Test 10009",     board.review_status_for("qa")   == "10009")
ok("10044 -> route self", board.route_for_status("10044") == "self")
ok("10045 -> route peer", board.route_for_status("10045") == "peer")
ok("10009 -> route qa",   board.route_for_status("10009") == "qa")
ok("execution status is NOT a review status", board.route_for_status("10043") is None)

section("SPRINT")
d = lambda *a: datetime(*a, tzinfo=TZ)
ok("sprint_id Monday",    sprint.sprint_id(d(2026,9,7,10,0), TZ) == "sprint-2026-09-07")
ok("Monday 00:00 OPEN",   sprint.is_open(d(2026,9,7,0,0), TZ) is True)
ok("Friday 18:59 OPEN",   sprint.is_open(d(2026,9,11,18,59), TZ) is True)
ok("Friday 19:00 CLOSED", sprint.is_open(d(2026,9,11,19,0), TZ) is False)
ok("Saturday CLOSED",     sprint.is_open(d(2026,9,12,10,0), TZ) is False)
raises("non-Monday sprint id refused", lambda: sprint.window("sprint-2026-09-08", TZ), "not a Monday")
kan141 = {"total": 5, "histories": [
 {"created":"2026-09-07T09:43:11.435+0400","items":[{"field":"status","from":"10010","to":"10009","fromString":"Development","toString":"QA-Test"}]},
 {"created":"2026-09-07T09:30:11.720+0400","items":[{"field":"status","from":"10006","to":"10010","fromString":"In Review","toString":"Development"}]},
 {"created":"2026-09-07T09:30:07.638+0400","items":[{"field":"status","from":"10005","to":"10006","fromString":"In Progress","toString":"In Review"}]},
 {"created":"2026-09-07T09:29:14.193+0400","items":[{"field":"status","from":"10004","to":"10005","fromString":"To Do","toString":"In Progress"}]},
 {"created":"2026-09-06T20:09:17.345+0400","items":[{"field":"IssueParentAssociation","from":None,"to":"10164","fromString":None,"toString":"KAN-127"}]}]}
ok("history replay still works across LEGACY ids",
   sprint.status_id_at("10009", kan141, d(2026,9,7,9,35)) == "10010")
ok("legacy id from history is canonically mapped",
   board.canonical_for(sprint.status_id_at("10009", kan141, d(2026,9,7,9,35))) == "development")
after = {"total":1,"histories":[{"created":"2026-09-12T10:00:00.000+0400",
        "items":[{"field":"status","from":"10045","to":"10007","fromString":"Peer-review","toString":"Done"}]}]}
ok("Sat Done does NOT appear at Fri 19:00 cutoff",
   sprint.status_id_at("10007", after, sprint.cutoff_of("sprint-2026-09-07", TZ)) == "10045")
ok("carried_over TRUE for that item",
   sprint.carried_over({"sprint-2026-09-07"}, "10007", after, "sprint-2026-09-07",
                       board.DONE_STATUS_ID, TZ) is True)
raises("truncated changelog REFUSES",
       lambda: sprint.status_id_at("10009", {"total":9,"histories":kan141["histories"]}, d(2026,9,7,12,0)),
       "truncated")

section("POLICY")
ok("empty -> SELF",        policy.validation_route({}) == "self")
ok("user_visible -> QA",   policy.validation_route({"user_visible_runtime":True}) == "qa")
ok("schema -> PEER",       policy.validation_route({"schema_change":True}) == "peer")
ok("money -> PEER",        policy.validation_route({"money_path":True}) == "peer")
ok("contended -> PEER",    policy.validation_route({"shared_or_contended_surface":True}) == "peer")
raises("unknown characteristic refused", lambda: policy.validation_route({"risk":True}), "unknown")
ok("escalate SELF->PEER",         policy.escalate("self","peer",True) == "peer")
ok("NO downgrade PEER->SELF",     policy.escalate("peer","self",True) == "peer")
ok("NO downgrade PEER->QA",       policy.escalate("peer","qa",True) == "peer")
topo = {"frontend":["frontend-%d"%i for i in range(1,9)],
        "backend":["backend-%d"%i for i in range(1,9)],
        "content":["content-manager"],"devops":["devops"],"analyst":["analyst"],"qa":["qa"]}
ok("content PEER impossible", policy.peer_possible("content", topo) is False)
o,r = policy.resolve_owner_or_wait("peer","content",topo,None,[])
ok("content PEER waits, route STAYS peer", o is None and r == "peer")
o,r = policy.resolve_owner_or_wait("peer","frontend",topo,"backend-4",["frontend-3"])
ok("cross-capability reviewer INVALID", o is None and r == "peer")
o,r = policy.resolve_owner_or_wait("peer","frontend",topo,"frontend-6",["frontend-3"])
ok("same-capability reviewer valid", o == "frontend-6")

section("VALIDATOR (live board)")
def rec(cap="backend", sid=None, canonical="development", route="peer",
        ch=None, rc=None, rtype="executable"):
    sid = sid or board.execution_status_for(cap)
    prof = None
    if rtype == "executable":
        prof = {"profile_status":"partial",
                "effective_fields":["project_id","required_capability","work_effort",
                                    "characteristics","validation_route","completion_route"],
                "required_capability":cap,"work_effort":2,
                "characteristics":{"schema_change":True} if ch is None else ch,
                "validation_route":route,"completion_route":"DONE",
                "provenance":{"validation_route":{"by":"system-policy"},
                              "completion_route":{"by":"system-policy"}}}
    return {"work_item_id":"KAN-999","product_id":"dabbler","project_id":"app",
            "schema_version":3,"revision":1,"created_at":"2026-09-08T00:00:00Z",
            "updated_at":"2026-09-08T00:00:00Z","record_type":rtype,
            "lifecycle":{"canonical":canonical,"jira_column":board.column_for(sid),
                         "jira_status_id":sid,"jira_status_name":board.name_for(sid),
                         "source":"jira","observed_at":"2026-09-08T00:00:00Z"},
            "executor_evidence":[],"execution_profile":prof,"review_context":rc}
hard = lambda r: [x for x in validate.validate_record("task", r) if " WARN " not in x]
warns = lambda r: [x for x in validate.validate_record("task", r) if " WARN " in x]

ok("valid backend item in Back-end 10043", hard(rec("backend")) == [])
ok("valid frontend item in Front-end 10046", hard(rec("frontend")) == [])
ok("valid content item in Content 10048", hard(rec("content", ch={}, route="self")) == [])
ok("valid design item in Design 10047",
   hard(rec("product-designer", ch={}, route="self")) == [])
ok("valid devops item in Operations 10049", hard(rec("devops", ch={}, route="self")) == [])
b = rec("frontend", sid="10043")
ok("frontend in BACKEND lane REJECTED", any("ALTERNATIVES" in x for x in hard(b)))
b = rec("content", sid="10049", ch={}, route="self")
ok("content in Operations lane REJECTED (dedicated status exists)",
   any("ALTERNATIVES" in x for x in hard(b)))
b = rec("backend"); b["lifecycle"]["jira_column"] = "Operations"
ok("wrong jira_column REJECTED", any("contradicts" in x and "column" in x for x in hard(b)))
b = rec("backend"); b["lifecycle"]["jira_status_name"] = "Backend Development"
ok("wrong jira_status_name REJECTED", any("does not match status id" in x for x in hard(b)))
b = rec("backend", sid="10010")
ok("LEGACY status is a WARN, not a hard failure", hard(b) == [] and len(warns(b)) >= 1)

section("REVIEW COHERENCE")
rc_peer = {"review_type":"peer","review_owner":"backend-6","review_result":"pending","review_cycle":1}
ok("PEER route in Peer-review 10045 coherent",
   hard(rec("backend", sid="10045", canonical="review", route="peer", rc=rc_peer)) == [])
rc_qa = {"review_type":"qa","review_owner":"qa","review_result":"pending","review_cycle":1}
ok("QA route in QA-Test 10009 coherent",
   hard(rec("backend", sid="10009", canonical="review", route="qa", ch={"user_visible_runtime":True}, rc=rc_qa)) == [])
rc_self = {"review_type":"self","review_owner":"frontend-3","review_result":"pending","review_cycle":1}
ok("SELF route in Self-review 10044 coherent",
   hard(rec("frontend", sid="10044", canonical="review", route="self", ch={}, rc=rc_self)) == [])
# Jira stricter than local -> repairable WARN
b = rec("backend", sid="10045", canonical="review", route="qa",
        ch={"user_visible_runtime":True}, rc=rc_qa)
ok("Jira STRICTER than local -> WARN (repairable), not fatal",
   hard(b) == [] and any("Jira wins" in x for x in warns(b)))
# Jira weaker than the policy floor -> hard error (the downgrade hole)
b = rec("backend", sid="10044", canonical="review", route="self",
        ch={"schema_change":True}, rc=rc_self)
ok("Jira WEAKER than policy floor -> HARD ERROR (no laundered downgrade)",
   any("unauthorised downgrade" in x for x in hard(b)))
b = rec("backend", sid="10043", canonical="review", route="peer", rc=rc_peer)
b["lifecycle"]["canonical"] = "review"
ok("canonical review on a non-review status REJECTED",
   any("contradicts status id" in x for x in hard(b)))

section("CONTAINERS")
c = rec(rtype="container", sid="10006", canonical="review")
c["execution_profile"] = None; c["review_context"] = None
ok("container in legacy In Review is VALID (KAN-39 shape)", hard(c) == [])
c2 = dict(c); c2["execution_profile"] = rec("backend")["execution_profile"]
ok("container WITH profile REJECTED", any("container records carry no" in x for x in hard(c2)))

section("STORE (temp runtime)")
tmp = tempfile.mkdtemp()
store.RUNTIME = os.path.join(tmp,"runtime"); store.LOCKS = os.path.join(store.RUNTIME,".locks")
validate.RUNTIME = store.RUNTIME
r = store.create("task", {"work_item_id":"KAN-990","product_id":"dabbler","project_id":"app",
    "record_type":"executable","executor_evidence":[],
    "lifecycle":{"canonical":"ready","jira_column":"Ready","jira_status_id":"10008",
                 "jira_status_name":"Ready","source":"jira","observed_at":"2026-09-08T00:00:00Z"},
    "execution_profile":{"profile_status":"partial","effective_fields":["required_capability"],
                         "required_capability":"frontend","provenance":{}},
    "review_context":None}, rid="KAN-990")
ok("created at current schema_version (3 since Wave 6)", r["schema_version"] == 3)
r2 = store.set_characteristics("KAN-990", r["revision"], {"user_visible_runtime":True}, "po")
ok("po asserts user_visible -> QA route", r2["execution_profile"]["validation_route"] == "qa")
# Ready invariant: a frontend seat sizes it before it can enter an execution status.
raises("cannot enter an execution status with work_effort null",
       lambda: store.observe_lifecycle("KAN-990", r2["revision"], "10046"),
       "work_effort is required")
rs = store.update("task","KAN-990",r2["revision"],
    {"execution_profile": dict(r2["execution_profile"], work_effort=1)})
r3 = store.observe_lifecycle("KAN-990", rs["revision"], board.execution_status_for("frontend"))
ok("observe_lifecycle derives column Frontend Development",
   r3["lifecycle"]["jira_column"] == "Frontend Development")
ok("observe_lifecycle derives name Front-end", r3["lifecycle"]["jira_status_name"] == "Front-end")
ok("observe_lifecycle derives canonical development", r3["lifecycle"]["canonical"] == "development")
raises("observe_lifecycle refuses unknown status",
       lambda: store.observe_lifecycle("KAN-990", r3["revision"], "99999"), "not on the live")
r4 = store.set_characteristics("KAN-990", r3["revision"], {"schema_change":True}, "worker:frontend-3")
ok("worker escalates QA -> PEER", r4["execution_profile"]["validation_route"] == "peer")
raises("worker CANNOT withdraw schema_change",
       lambda: store.set_characteristics("KAN-990", r4["revision"], {"schema_change":False}, "worker:frontend-3"),
       "may not withdraw")
# enter Peer-review
r5 = store.update("task","KAN-990",r4["revision"],{
    "lifecycle":{"canonical":"review","jira_column":"Review","jira_status_id":"10045",
                 "jira_status_name":"Peer-review","source":"jira","observed_at":"2026-09-08T00:00:00Z"},
    "review_context":{"review_type":"peer","review_owner":"frontend-6",
                      "review_result":"pending","review_cycle":1},
    "executor_evidence":[{"seat_id":"frontend-3","evidence_ref":"x","evidenced_at":"2026-09-08T00:00:00Z"}]})
ok("item sits in Peer-review 10045", r5["lifecycle"]["jira_status_id"] == "10045")
raises("reconcile REFUSES a weaker Jira status (Self-review on schema work)",
       lambda: store.reconcile_review_from_jira("KAN-990", r5["revision"], "10044"),
       "Move the issue back in Jira")
raises("reconcile refuses a non-review status",
       lambda: store.reconcile_review_from_jira("KAN-990", r5["revision"], "10043"),
       "not one of the three review statuses")
# PEER FAIL -> reviewer becomes executor, SELF-reviews, SAME execution status
r6 = store.peer_fail_transfer("KAN-990", r5["revision"], "frontend-6",
                              "peer-review-transfer:KAN-990:cycle-1")
ok("PEER FAIL: evidence REPLACED by reviewer",
   len(r6["executor_evidence"]) == 1 and r6["executor_evidence"][0]["seat_id"] == "frontend-6")
ok("PEER FAIL: review_type becomes SELF (not back to Peer-review)",
   r6["review_context"]["review_type"] == "self")
ok("PEER FAIL: cycle incremented", r6["review_context"]["review_cycle"] == 2)
ok("PEER FAIL: previous_owner kept", r6["review_context"]["previous_owner"] == "frontend-3")
ok("PEER FAIL: capability UNCHANGED -> returns to the SAME execution status (Front-end)",
   board.execution_status_for(r6["execution_profile"]["required_capability"]) == "10046")
r7 = store.observe_lifecycle("KAN-990", r6["revision"], "10046")
ok("PEER FAIL: item back in Front-end 10046", r7["lifecycle"]["jira_status_id"] == "10046")
r8 = store.observe_lifecycle("KAN-990", r7["revision"], "10044")
ok("PEER FAIL: reviewer's fix goes to Self-review 10044",
   r8["lifecycle"]["jira_status_id"] == "10044" and r8["lifecycle"]["jira_column"] == "Review")
# QA FAIL -> same execution status -> back to QA-Test, same owner
q = store.create("task", {"work_item_id":"KAN-991","product_id":"dabbler","project_id":"app",
    "record_type":"executable","executor_evidence":[{"seat_id":"frontend-3","evidence_ref":"y","evidenced_at":"2026-09-08T00:00:00Z"}],
    "lifecycle":{"canonical":"review","jira_column":"Review","jira_status_id":"10009",
                 "jira_status_name":"QA-Test","source":"jira","observed_at":"2026-09-08T00:00:00Z"},
    "execution_profile":{"profile_status":"partial",
        "effective_fields":["project_id","required_capability","work_effort","characteristics","validation_route","completion_route"],
        "required_capability":"frontend","work_effort":1,
        "characteristics":{"user_visible_runtime":True},"validation_route":"qa","completion_route":"DONE",
        "provenance":{"validation_route":{"by":"system-policy"},"completion_route":{"by":"system-policy"}}},
    "review_context":{"review_type":"qa","review_owner":"qa","review_result":"pending","review_cycle":1}}, rid="KAN-991")
q2 = store.update("task","KAN-991",q["revision"],{"review_context":dict(q["review_context"], review_result="fail")})
q3 = store.observe_lifecycle("KAN-991", q2["revision"], "10046")
ok("QA FAIL: returns to the SAME execution status Front-end 10046",
   q3["lifecycle"]["jira_status_id"] == "10046")
q4 = store.update("task","KAN-991",q3["revision"],{"review_context":{
    "review_type":"qa","review_owner":"qa","review_result":"pending","review_cycle":2}})
q5 = store.observe_lifecycle("KAN-991", q4["revision"], "10009")
ok("QA FAIL: comes back to QA-Test 10009, same route",
   q5["lifecycle"]["jira_status_id"] == "10009")
ok("QA FAIL: owner stays qa", q5["review_context"]["review_owner"] == "qa")
ok("QA FAIL: cycle incremented", q5["review_context"]["review_cycle"] == 2)
section("STORE TRANSITION TARGET GUARD")
ok("transition_target(capability='backend') -> 10043", store.transition_target(capability="backend") == "10043")
ok("transition_target(capability='content')  -> 10048", store.transition_target(capability="content") == "10048")
ok("transition_target(route='peer')          -> 10045", store.transition_target(route="peer") == "10045")
raises("transition_target refuses qa capability (no execution lane)",
       lambda: store.transition_target(capability="qa"), "no execution status")
raises("transition_target refuses both args",
       lambda: store.transition_target(capability="backend", route="peer"), "exactly one")
# observe_lifecycle still ACCEPTS a legacy id: it records what Jira says
lg = store.create("task", {"work_item_id":"KAN-992","product_id":"dabbler","project_id":"app",
    "record_type":"container","executor_evidence":[],
    "lifecycle":{"canonical":"review","jira_column":None,"jira_status_id":"10006",
                 "jira_status_name":"In Review","source":"jira","observed_at":"2026-09-08T00:00:00Z"},
    "execution_profile":None,"review_context":None}, rid="KAN-992")
ok("legacy observation is WRITABLE (migration state must be repairable)",
   lg["lifecycle"]["jira_status_id"] == "10006")
ok("...and the validator marks it WARN, not FAIL",
   any(" WARN " in x and "LEGACY" in x for x in validate.validate_record("task", lg)))

shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(summary())
