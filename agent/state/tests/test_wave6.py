"""Wave 6 behavioural suite — v3 state, queues, claim/release, contention, interventions.

Every test here exists because the corresponding rule is one somebody could break by
accident and nothing else would notice: a claim that races, an intervention with the
wrong scope, a contention check that blocks on a boolean instead of a path, a seat
created while a defined one sits dormant.
"""
import os, sys, shutil, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path

ROOT = repo_root()
sys.path.insert(0, state_path())
import board, policy, store, validate, queue as q, capacity          # noqa: E402

OBS = "2026-09-08T00:00:00Z"


def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    return tmp


def lc(sid, observed=None):
    return {"canonical": board.canonical_for(sid), "jira_column": board.column_for(sid),
            "jira_status_id": sid, "jira_status_name": board.name_for(sid),
            "observed_at": observed or OBS, "source": "jira"}


def task(key, cap="backend", sid="10008", effort=1, surfaces=None, owner=None,
         evidence=None, route=None, rtype="executable"):
    prof = None
    if rtype == "executable":
        eff = ["project_id", "required_capability", "completion_route"]
        prof = {"profile_status": "partial", "required_capability": cap,
                "completion_route": "DONE",
                "provenance": {"required_capability": {"by": "system-maintenance"},
                               "completion_route": {"by": "system-policy"}}}
        if effort is not None:
            prof["work_effort"] = effort; eff.append("work_effort")
        if route:
            prof["validation_route"] = route; eff.append("validation_route")
            prof["provenance"]["validation_route"] = {"by": "system-policy"}
        prof["effective_fields"] = eff
    return {"work_item_id": key, "product_id": "dabbler", "project_id": "app",
            "record_type": rtype, "lifecycle": lc(sid),
            "executor_evidence": evidence or [], "execution_profile": prof,
            "review_context": None, "ownership": owner, "surfaces": surfaces or []}


JIRA_OK = {"status_id": "10008", "has_due_date": True, "has_acceptance_criteria": True}
FRESH = {"jira_status_id": "10008"}

# ---------------------------------------------------------------- STATE V3
section("STATE V3 — MIGRATION")
tmp = fresh_runtime()
legacy = task("KAN-900")
del legacy["ownership"]; del legacy["surfaces"]
legacy["schema_version"] = 2
os.makedirs(os.path.join(store.RUNTIME, "tasks"), exist_ok=True)
legacy.update({"revision": 1, "created_at": OBS, "updated_at": OBS})
store._atomic_write(store.path_for("task", "KAN-900"), legacy)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "mig", os.path.join(ROOT, "agent", "scripts", "migrate-v2-v3.py"))
mig = importlib.util.module_from_spec(spec); spec.loader.exec_module(mig)
ch, sk, er = mig.migrate()
r = store.read("task", "KAN-900")
ok("v2 record migrates to v3", r["schema_version"] == 3)
ok("migration adds ownership = null", r["ownership"] is None)
ok("migration adds surfaces = NULL (unassessed, not assessed-empty)",
   r["surfaces"] is None)
ok("migration preserves work_effort", r["execution_profile"]["work_effort"] == 1)
ok("migration preserves capability", r["execution_profile"]["required_capability"] == "backend")
ok("migration reports no errors", er == [])
ch2, sk2, er2 = mig.migrate()
ok("migration is IDEMPOTENT (second run changes nothing)", ch2 == [] and len(sk2) >= 1)
# evidence must NOT become ownership
ev = task("KAN-901", evidence=[{"seat_id": "backend-1", "evidence_ref": "x",
                                "evidenced_at": OBS}])
del ev["ownership"]; ev["schema_version"] = 2
ev.update({"revision": 1, "created_at": OBS, "updated_at": OBS})
store._atomic_write(store.path_for("task", "KAN-901"), ev)
mig.migrate()
ok("Wave 5 executor_evidence does NOT become Wave 6 ownership",
   store.read("task", "KAN-901")["ownership"] is None)
shutil.rmtree(tmp, ignore_errors=True)

section("STATE V3 — VALIDATION")
e = lambda r: [x for x in validate.validate_record("task", r) if " WARN " not in x]
ok("valid v3 task", e(dict(task("KAN-902"), schema_version=3, revision=1,
                           created_at=OBS, updated_at=OBS)) == [])
bad = dict(task("KAN-903", owner={"seat_id": "backend-1", "claimed_at": OBS,
                                  "claim_ref": "r", "released_at": OBS}),
           schema_version=3, revision=1, created_at=OBS, updated_at=OBS)
ok("ownership carrying released_at REJECTED",
   any("released_at" in x for x in e(bad)))
bad = dict(task("KAN-904", owner={"seat_id": "nobody-9", "claimed_at": OBS,
                                  "claim_ref": "r"}),
           schema_version=3, revision=1, created_at=OBS, updated_at=OBS)
ok("ownership by an undeclared seat REJECTED", any("not a declared seat" in x for x in e(bad)))
for bad_path, why in (("/etc/passwd", "absolute"), ("../secrets", "traversal"),
                      ("lib\\core\\x.dart", "backslash")):
    b = dict(task("KAN-905", surfaces=[bad_path]), schema_version=3, revision=1,
             created_at=OBS, updated_at=OBS)
    ok("surface rejected (%s): %s" % (why, bad_path), e(b) != [])
b = dict(task("KAN-906", surfaces=["lib/a.dart", "lib/a.dart"]), schema_version=3,
         revision=1, created_at=OBS, updated_at=OBS)
ok("duplicate surface REJECTED", any("duplicate surface" in x for x in e(b)))
b = task("KAN-907", surfaces=["lib/providers.dart"])
b["execution_profile"]["characteristics"] = {"shared_or_contended_surface": False}
b.update(schema_version=3, revision=1, created_at=OBS, updated_at=OBS)
ok("contended boolean contradicting declared surfaces REJECTED",
   any("system-derived from" in x for x in e(b)))

# ---------------------------------------------------------------- QUEUES
section("CAPABILITY QUEUES")
ready = task("KAN-910", cap="backend", sid="10008")
ok("Ready + all five facts is queue-eligible", q.eligibility_reasons(ready, JIRA_OK) == [])
# The live Jira read is authoritative, so a status id in `jira` overrides the stored
# observation. These pass a read that MATCHES the record, which is the real case.
backlog = task("KAN-911", sid="10004")
ok("Backlog is NOT a queue",
   "not-ready" in q.eligibility_reasons(backlog, dict(JIRA_OK, status_id="10004")))
indev = task("KAN-912", sid="10043")
ok("an execution status is not queue-eligible",
   "not-ready" in q.eligibility_reasons(indev, dict(JIRA_OK, status_id="10043")))
ok("a live Jira read OVERRIDES a stale stored observation (Jira wins)",
   q.eligibility_reasons(task("KAN-917", sid="10004"), JIRA_OK) == [])
ok("missing work_effort -> missing-work-effort",
   "missing-work-effort" in q.eligibility_reasons(task("KAN-913", effort=None), JIRA_OK))
noproj = task("KAN-914"); noproj["project_id"] = None
ok("missing project -> missing-project", "missing-project" in q.eligibility_reasons(noproj, JIRA_OK))
ok("missing due_date -> missing-due-date",
   "missing-due-date" in q.eligibility_reasons(ready, dict(JIRA_OK, has_due_date=False)))
ok("missing acceptance criteria -> missing-acceptance-criteria",
   "missing-acceptance-criteria" in q.eligibility_reasons(
       ready, dict(JIRA_OK, has_acceptance_criteria=False)))
ok("no Jira evidence is NOT a silent pass -> unverified-jira",
   "unverified-jira" in q.eligibility_reasons(ready, None))
ok("container is not queue-eligible",
   "not-executable" in q.eligibility_reasons(task("KAN-915", rtype="container"), JIRA_OK))
qs = q.queues([ready, backlog, task("KAN-916", cap="frontend")], {"KAN-910": JIRA_OK,
                                                                 "KAN-916": JIRA_OK})
ok("queue key IS the capability", set(qs) == {"backend", "frontend"})
ok("backend queue holds only the eligible item",
   [t["work_item_id"] for t in qs["backend"]] == ["KAN-910"])

# ---------------------------------------------------------------- CLAIMABILITY
section("CLAIMABILITY — READY IS NOT CLAIMABLE")
tmp = fresh_runtime()
base = store.create("task", task("KAN-920", surfaces=["lib/features/a/x.dart"]), rid="KAN-920")
ok("eligible + nothing blocking = CLAIMABLE",
   q.unclaimable_reasons(base, jira=JIRA_OK, **FRESH) == [])
owned = store.create("task", dict(task("KAN-921"),
                                  ownership={"seat_id": "backend-2", "claimed_at": OBS,
                                             "claim_ref": "r"}), rid="KAN-921")
ok("already owned -> already-owned",
   "already-owned" in q.unclaimable_reasons(owned, jira=JIRA_OK, **FRESH))
conf = store.create("task", dict(task("KAN-922"), executor_evidence=[
    {"seat_id": "backend-1", "evidence_ref": "a", "evidenced_at": OBS},
    {"seat_id": "backend-3", "evidence_ref": "b", "evidenced_at": OBS}]), rid="KAN-922")
ok("conflicting evidence BLOCKS (no MODEL C fallback)",
   "conflicting-evidence" in q.unclaimable_reasons(conf, jira=JIRA_OK, **FRESH))
stale = dict(base); stale["lifecycle"] = lc("10008", "2020-01-01T00:00:00Z")
ok("no fresh Jira read -> stale-jira",
   "stale-jira" in q.unclaimable_reasons(stale, jira=JIRA_OK))
ok("reasons are structured codes, not prose",
   all(" " not in r for r in q.unclaimable_reasons(owned, jira=JIRA_OK, **FRESH)))

# ---------------------------------------------------------------- DEPENDENCY
section("DEPENDENCY ENFORCEMENT")
store.create("task", task("KAN-930", surfaces=[]), rid="KAN-930")
store.create("task", task("KAN-931", surfaces=[]), rid="KAN-931")
dep = store.create_dependency({"product_id": "dabbler", "source_work_item": "KAN-930",
                               "target_work_item": "KAN-931", "relation": "BLOCKS",
                               "completion_condition": "DONE"})
tgt = store.read("task", "KAN-931")
ok("source in READY blocks the target",
   "dependency-blocked" in q.unclaimable_reasons(tgt, jira=JIRA_OK, **FRESH))
edges = [dep]
ok("source in REVIEW still blocks — review does NOT unblock",
   validate.is_blocked("KAN-931", edges, {"KAN-930": "review"}) is True)
ok("only DONE satisfies", validate.is_blocked("KAN-931", edges, {"KAN-930": "done"}) is False)
ok("no stored blocked/satisfied flag on the edge",
   not any(k in dep for k in ("blocked", "state", "satisfied", "active", "resolved")))
ok("completion_condition is DONE", dep["completion_condition"] == "DONE")

# ---------------------------------------------------------------- CONTENTION
section("CONTENTION — PATHS, NOT BOOLEANS")
ok("exact file collision", q.surfaces_collide(["lib/x.dart"], ["lib/x.dart"]) is True)
ok("directory containment collision",
   q.surfaces_collide(["lib/features/a"], ["lib/features/a/b.dart"]) is True)
ok("same governed shared prefix collides",
   q.surfaces_collide(["lib/core/a.dart"], ["lib/core/b.dart"]) is True)
ok("BOTH contended but DIFFERENT files -> NO false block",
   q.surfaces_collide(["lib/providers.dart"], ["lib/app/app_router.dart"]) is False)
ok("disjoint feature files do not collide",
   q.surfaces_collide(["lib/features/a/x.dart"], ["lib/features/b/y.dart"]) is False)
ok("empty surfaces never collide", q.surfaces_collide([], ["lib/x.dart"]) is False)
store.create("task", dict(task("KAN-940", surfaces=["lib/features/z/z.dart"]),
                          ownership={"seat_id": "backend-5", "claimed_at": OBS,
                                     "claim_ref": "r"}), rid="KAN-940")
rival = store.create("task", task("KAN-941", surfaces=["lib/features/z/z.dart"]), rid="KAN-941")
ok("collision with an OWNED task -> surface-contention",
   "surface-contention" in q.unclaimable_reasons(rival, jira=JIRA_OK, **FRESH))
o = store.read("task", "KAN-940")
store.release("KAN-940", "backend-5", o["revision"], "released")
ok("release CLEARS the collision by derivation",
   "surface-contention" not in q.unclaimable_reasons(store.read("task", "KAN-941"),
                                                     jira=JIRA_OK, **FRESH))

# ---------------------------------------------------------------- INTERVENTIONS
section("INTERVENTIONS")
iv_stop = store.create_intervention("stop", "KAN-920", "ceo", "safety: reconciliation failure")
ok("STOP is scope task", iv_stop["scope"] == "task")
ok("STOP blocks that task",
   "task-stopped" in q.unclaimable_reasons(store.read("task", "KAN-920"), jira=JIRA_OK, **FRESH))
ok("STOP does not touch another task",
   "task-stopped" not in q.unclaimable_reasons(store.read("task", "KAN-941"),
                                               jira=JIRA_OK, **FRESH))
raises("duplicate ACTIVE intervention refused",
       lambda: store.create_intervention("stop", "KAN-920", "ceo", "again"),
       "already exists")
store.clear_intervention(iv_stop["intervention_id"], iv_stop["revision"], "ceo")
ok("RESUME clears it",
   "task-stopped" not in q.unclaimable_reasons(store.read("task", "KAN-920"),
                                               jira=JIRA_OK, **FRESH))
ok("cleared record is KEPT, not deleted",
   store.read("intervention", iv_stop["intervention_id"])["cleared_at"] is not None)
ok("a duplicate is allowed once the first is cleared",
   store.create_intervention("stop", "KAN-920", "ceo", "second") is not None)

iv_hold = store.create_intervention("hold", "backend", "orchestrator", "safety: collision storm")
ok("HOLD is scope capability", iv_hold["scope"] == "capability")
ok("HOLD blocks NEW claims for that capability",
   "capability-held" in q.unclaimable_reasons(store.read("task", "KAN-941"),
                                              jira=JIRA_OK, **FRESH))
ok("HOLD does not block another capability",
   "capability-held" not in q.unclaimable_reasons(task("KAN-950", cap="frontend"),
                                                  jira=JIRA_OK, **FRESH))
held_owner = store.read("task", "KAN-921")
ok("HOLD lets a CURRENT OWNER continue (it is not a stop)",
   (held_owner.get("ownership") or {}).get("seat_id") == "backend-2")
store.clear_intervention(iv_hold["intervention_id"], iv_hold["revision"], "ceo")

iv_fr = store.create_intervention("freeze", None, "ceo", "safety: system reconciliation")
ok("FREEZE is scope system with no target",
   iv_fr["scope"] == "system" and iv_fr["target"] is None)
ok("FREEZE blocks every capability",
   "system-frozen" in q.unclaimable_reasons(task("KAN-951", cap="frontend"),
                                            jira=JIRA_OK, **FRESH))
store.clear_intervention(iv_fr["intervention_id"], iv_fr["revision"], "ceo")
raises("unknown kind refused", lambda: store.create_intervention("pause", None, "ceo", "r"),
       "unknown intervention kind")
bad_iv = {"intervention_id": "int-x", "kind": "hold", "scope": "task", "target": "KAN-1",
          "created_by": "ceo", "reason_ref": "r", "schema_version": 3, "revision": 1,
          "created_at": OBS, "updated_at": OBS}
ok("wrong scope for kind REJECTED",
   any("is always scope" in x for x in validate.validate_record("intervention", bad_iv)))
bad_iv2 = dict(bad_iv, kind="resume", scope="task")
ok("'resume' is not a stored kind",
   any("not a stored intervention" in x for x in validate.validate_record("intervention", bad_iv2)))

# ---------------------------------------------------------------- CLAIM / RELEASE
section("ATOMIC OWNERSHIP")
c = store.create("task", task("KAN-960", cap="backend",
                              surfaces=["lib/features/q/q.dart"]), rid="KAN-960")
got = store.claim("KAN-960", "backend-6", "claim:KAN-960", c["revision"],
                  capability_of_seat="backend", jira_status_id="10008")
ok("claim sets exactly one owner", got["ownership"]["seat_id"] == "backend-6")
ok("claim records claimed_at and claim_ref",
   got["ownership"].get("claimed_at") and got["ownership"].get("claim_ref"))
ok("claim does NOT add released_at", "released_at" not in got["ownership"])
raises("DOUBLE CLAIM refused (already owned)",
       lambda: store.claim("KAN-960", "backend-7", "x", got["revision"],
                           capability_of_seat="backend", jira_status_id="10008"),
       "already-owned")
raises("stale revision refused (CAS)",
       lambda: store.claim("KAN-960", "backend-7", "x", 1,
                           capability_of_seat="backend", jira_status_id="10008"),
       "stale write refused")
c2 = store.create("task", task("KAN-961", cap="frontend"), rid="KAN-961")
raises("wrong-capability claim refused",
       lambda: store.claim("KAN-961", "backend-6", "x", c2["revision"],
                           capability_of_seat="backend", jira_status_id="10008"),
       "wrong-capability")
c3 = store.create("task", task("KAN-962", cap="backend"), rid="KAN-962")
raises("seat already owning another task refused",
       lambda: store.claim("KAN-962", "backend-6", "x", c3["revision"],
                           capability_of_seat="backend", jira_status_id="10008"),
       "seat-already-owns")
cur = store.read("task", "KAN-960")
raises("release by the WRONG seat refused",
       lambda: store.release("KAN-960", "backend-7", cur["revision"], "r"), "not-owner")
rel = store.release("KAN-960", "backend-6", cur["revision"], "released:done")
ok("release sets ownership to NULL (never a released object)", rel["ownership"] is None)
ok("release leaves durable evidence behind",
   any(e["seat_id"] == "backend-6" for e in rel["executor_evidence"]))
ok("release does NOT reassign", rel["ownership"] is None)

section("CONCURRENCY — exactly one winner")
c4 = store.create("task", task("KAN-963", cap="backend"), rid="KAN-963")
rev = c4["revision"]
wins, losses = 0, 0
for seat in ("backend-1", "backend-2", "backend-3"):
    try:
        store.claim("KAN-963", seat, "race", rev, capability_of_seat="backend",
                    jira_status_id="10008"); wins += 1
    except store.StateError:
        losses += 1
ok("three claimants on the same revision -> exactly 1 win, 2 refused",
   wins == 1 and losses == 2)

# ---------------------------------------------------------------- CAPACITY / SEATS
section("CAPACITY AND DYNAMIC SEATS")
sbc = {"backend": ["backend-%d" % i for i in range(1, 9)],
       "frontend": ["frontend-%d" % i for i in range(1, 9)],
       "content": ["content-manager"], "ux-engineer": ["ux-engineer-1"]}
tasks = store.read_all("task")
ok("a dormant defined seat is FREE, not unavailable",
   len(capacity.free_seats("backend", tasks, sbc)) > 0)
just, why = capacity.expansion_justified("backend", tasks, sbc, jira=JIRA_OK, **FRESH)
ok("no new seat while a defined seat is dormant", just is False and why == "existing-seat-dormant")
busy = [dict(t, ownership={"seat_id": s, "claimed_at": OBS, "claim_ref": "r"})
        for t, s in zip([task("B%d" % i) for i in range(8)], sbc["backend"])]
j2, w2 = capacity.expansion_justified("backend", busy, sbc, jira=JIRA_OK, **FRESH)
ok("all seats busy but no claimable demand -> still no expansion",
   j2 is False and w2 == "no-parallel-demand")
ok("ceiling respected: content at ceiling refuses",
   capacity.expansion_justified("content", [], {"content": ["content-manager", "content-2"]},
                                jira=JIRA_OK, **FRESH)[1] == "at-ceiling")
ok("non-expandable capability refuses",
   capacity.expansion_justified("po", [], {"po": ["po"]}, jira=JIRA_OK, **FRESH)[1]
   == "capability-not-expandable")
ok("deterministic next id", capacity.next_seat_id("backend", sbc) == "backend-9")
ok("historical id is NEVER recycled",
   capacity.next_seat_id("content", {"content": []},
                         historical_ids=["content-1"]) == "content-2")
ok("topology ceilings are inspectable and token-free",
   capacity.topology()["backend"]["ceiling"] == 9)
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- ROSTER
section("ROSTER — TEAM LEADS REMOVED, UX ENGINEER ACTIVE")
B = os.path.join(ROOT, ".claude", "bindings")
A = os.path.join(ROOT, ".claude", "agents")
R = os.path.join(ROOT, "agent", "roles")
S = os.path.join(ROOT, "agent", "status")
binds = sorted(f[:-4] for f in os.listdir(B) if f.endswith(".yml"))
agents = sorted(f[:-3] for f in os.listdir(A) if f.endswith(".md"))
ok("zero live Team Lead bindings", not any(b.startswith("team-lead") for b in binds))
ok("zero generated Team Lead agents", not any(a.startswith("team-lead") for a in agents))
ok("zero Team Lead Role files",
   not any(f.startswith("team-lead") for f in os.listdir(R)))
ok("Team Lead STATUS history PRESERVED (5 files)",
   len([f for f in os.listdir(S) if f.startswith("team-lead")]) == 5)
ok("ux-engineer-1 binding exists", "ux-engineer-1" in binds)
ok("ux-engineer-1 generated agent exists", "ux-engineer-1" in agents)
ok("bindings and generated agents are 1:1", binds == agents)
ok("roster is 26 bindings", len(binds) == 26)
ok("roster is 26 generated agents", len(agents) == 26)
ok("agent/seats/ is gone", not os.path.isdir(os.path.join(ROOT, "agent", "seats")))
ok("no binding declares seat_context",
   not any("seat_context" in open(os.path.join(B, f), encoding="utf-8").read()
           for f in os.listdir(B) if f.endswith(".yml")))
uxb = open(os.path.join(B, "ux-engineer-1.yml"), encoding="utf-8").read()
ok("ux-engineer-1 binds the ux-engineer Role", "role: ux-engineer" in uxb)
ok("ux-engineer-1 has a real dispatch hint, not a generic one",
   len(uxb.split("description:")[1].split("\n")[0]) > 200)
ok("ux-engineer executes in Design 10047", board.execution_status_for("ux-engineer") == "10047")
ok("product-designer still has NO seat", "product-designer" not in binds)

section("MODEL C — THREE SURVIVING USES ONLY")
claude = open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
ok("doctrine states MODEL C survives in exactly three places",
   "MODEL C survives in exactly three places" in claude)
ok("no generic 'ask the CEO who owns this' fallback remains",
   "ask the CEO** which concrete seat" not in claude)
ok("claim-before-wake is stated", "claim already succeeded" in claude
   or "CLAIM and WAKE are different acts" in claude)
ok("Orchestrator may not own ordinary work",
   "Claim a normal Product task for yourself" in claude)


# ================================================================ REMEDIATION
# Wave 6 closure found two hard blockers. These are the tests for both fixes.

section("BLOCKER A — SURFACE ASSESSMENT: null vs []")
tmp = fresh_runtime()
J = {"status_id": "10008", "has_due_date": True, "has_acceptance_criteria": True}
F = {"jira_status_id": "10008"}

unassessed = dict(task("KAN-811"), surfaces=None)
a1 = store.create("task", unassessed, rid="KAN-811")
ok("1. surfaces=null on an otherwise-claimable Ready task -> surfaces-unassessed",
   "surfaces-unassessed" in q.unclaimable_reasons(a1, jira=J, **F))
ok("1b. ...and it is therefore NOT CLAIMABLE",
   not q.claimable(a1, jira=J, **F))
a2 = store.create("task", task("KAN-812", surfaces=[]), rid="KAN-812")
ok("2. surfaces=[] with everything else satisfied -> no surfaces-unassessed",
   "surfaces-unassessed" not in q.unclaimable_reasons(a2, jira=J, **F))
ok("2b. ...and it IS claimable", q.claimable(a2, jira=J, **F))
cur = store.read("task", "KAN-811")
a3 = store.set_surfaces("KAN-811", cur["revision"], [], "worker:backend-4",
                        basis_ref="preflight: no governed paths touched")
ok("3. set_surfaces([]) makes it assessed-empty", a3["surfaces"] == [])
ok("3b. ...surfaces-unassessed disappears",
   "surfaces-unassessed" not in q.unclaimable_reasons(a3, jira=J, **F))
ok("3c. ...assessment provenance is recorded",
   (a3["execution_profile"]["provenance"].get("surfaces") or {}).get("by") == "worker:backend-4")
raises("4. set_surfaces(null) by a normal actor REJECTED",
       lambda: store.set_surfaces("KAN-812", store.read("task","KAN-812")["revision"],
                                  None, "worker:backend-4"),
       "cannot write null")
# 5/6 covered by the migration section above (surfaces = NULL, idempotent)
ok("5. v2->v3 migration yields surfaces=null (asserted above)", True)
ok("6. migration idempotence (asserted above)", True)
ok("8. shared_or_contended_surface is NOT false-derived from null",
   policy.validation_route({}) == "self" and
   any("unassessed scope has no derivable answer" in x
       for x in validate.validate_record("task", dict(
           store.read("task","KAN-812"), surfaces=None,
           execution_profile=dict(store.read("task","KAN-812")["execution_profile"],
               characteristics={"shared_or_contended_surface": False})))))
a4 = store.set_surfaces("KAN-812", store.read("task","KAN-812")["revision"], [],
                        "worker:backend-4")
ok("9. assessed empty [] derives shared_or_contended_surface = false",
   a4["execution_profile"]["characteristics"]["shared_or_contended_surface"] is False)
a5 = store.set_surfaces("KAN-812", a4["revision"], ["lib/core/x.dart"], "worker:backend-4")
ok("10. non-empty governed paths derive true; contention behaviour unchanged",
   a5["execution_profile"]["characteristics"]["shared_or_contended_surface"] is True
   and q.surfaces_collide(["lib/core/x.dart"], ["lib/core/y.dart"]) is True)
raises("contention evaluator REFUSES an unassessed task defensively",
       lambda: q.contending_owner(dict(task("KAN-813"), surfaces=None), []),
       "UNASSESSED")
shutil.rmtree(tmp, ignore_errors=True)

section("BLOCKER B — STOP CONTINUATION ENFORCEMENT")
tmp = fresh_runtime()
b = store.create("task", task("KAN-821", surfaces=["lib/features/b/b.dart"]), rid="KAN-821")
owned = store.claim("KAN-821", "backend-1", "c", b["revision"],
                    capability_of_seat="backend", jira_status_id="10008")
ok("1. owned, no STOP, correct owner -> continuation PERMITTED",
   q.execution_permitted(owned, "backend-1"))
ok("1b. store gate agrees",
   store.assert_execution_permitted("KAN-821", "backend-1")["work_item_id"] == "KAN-821")
iv = store.create_intervention("stop", "KAN-821", "ceo", "safety: reconciliation failure")
cur = store.read("task", "KAN-821")
ok("2. owned, active STOP, correct owner -> continuation DENIED with task-stopped",
   q.execution_reasons(cur, "backend-1") == ["task-stopped"])
raises("2b. store gate refuses",
       lambda: store.assert_execution_permitted("KAN-821", "backend-1"), "task-stopped")
ok("3. owned, active STOP, WRONG seat -> denied",
   set(q.execution_reasons(cur, "backend-9")) == {"not-owner", "task-stopped"})
ok("4. STOP PRESERVES ownership", cur["ownership"]["seat_id"] == "backend-1")
rel = store.release("KAN-821", "backend-1", cur["revision"], "released under STOP")
ok("5. release by the owner WHILE STOP active -> permitted, ownership null",
   rel["ownership"] is None)
ok("6. STOP does not mutate Jira lifecycle",
   rel["lifecycle"]["jira_status_id"] == cur["lifecycle"]["jira_status_id"])
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")

h = store.create("task", task("KAN-822", surfaces=[]), rid="KAN-822")
h_owned = store.claim("KAN-822", "backend-2", "c", h["revision"],
                      capability_of_seat="backend", jira_status_id="10008")
ivh = store.create_intervention("hold", "backend", "orchestrator", "safety: collision storm")
ok("7. HOLD + existing owner -> continuation PERMITTED (HOLD is not STOP)",
   q.execution_permitted(store.read("task","KAN-822"), "backend-2"))
ok("7b. ...but HOLD still blocks a NEW claim",
   "capability-held" in q.unclaimable_reasons(dict(task("KAN-823"), surfaces=[]),
                                              jira=J, **F))
store.clear_intervention(ivh["intervention_id"], ivh["revision"], "ceo")
ivf = store.create_intervention("freeze", None, "ceo", "safety: system reconciliation")
ok("8. FREEZE + existing owner -> continuation PERMITTED",
   q.execution_permitted(store.read("task","KAN-822"), "backend-2"))
ok("8b. ...but FREEZE still blocks a NEW claim",
   "system-frozen" in q.unclaimable_reasons(dict(task("KAN-824"), surfaces=[]),
                                            jira=J, **F))
store.clear_intervention(ivf["intervention_id"], ivf["revision"], "ceo")

b9 = store.create("task", task("KAN-825", surfaces=[]), rid="KAN-825")
o9 = store.claim("KAN-825", "backend-3", "c", b9["revision"],
                 capability_of_seat="backend", jira_status_id="10008")
iv9 = store.create_intervention("stop", "KAN-825", "ceo", "safety")
ok("9a. stopped -> denied", q.execution_reasons(store.read("task","KAN-825"),
                                                "backend-3") == ["task-stopped"])
store.clear_intervention(iv9["intervention_id"], iv9["revision"], "ceo")
ok("9b. STOP cleared, ownership still legitimate -> continuation PERMITTED again",
   q.execution_permitted(store.read("task","KAN-825"), "backend-3"))
ok("9c. RESUME did not recreate or alter ownership",
   store.read("task","KAN-825")["ownership"]["seat_id"] == "backend-3")
shutil.rmtree(tmp, ignore_errors=True)

section("BLOCKER B — DOCTRINE IS OPERATIVE, NOT DESCRIPTIVE")
claude = open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
ok("10. Orchestrator MUST run the continuation gate before every wake",
   "RUN THE CONTINUATION GATE BEFORE EVERY EXECUTION WAKE" in claude
   and "assert_execution_permitted" in claude)
ok("10b. it is a MUST NOT, not a table row",
   "Wake a seat for execution without valid ownership AND a passing continuation gate" in claude)
skill = open(os.path.join(ROOT, "agent/skills/route-to-seat/SKILL.md"), encoding="utf-8").read()
ok("11. the active wake skill requires ownership + continuation gate",
   "assert_execution_permitted" in skill and "DO NOT WAKE" in skill)
ok("11b. the skill names all three refusal reasons",
   all(r in skill for r in ("task-stopped", "not-owner", "not-owned")))
ok("surfaces rule is operative in doctrine too",
   "never means \"no collision\"" in claude or "surfaces-unassessed" in claude)


if __name__ == "__main__":
    sys.exit(summary())
