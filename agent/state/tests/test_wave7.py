#!/usr/bin/env python3
"""Wave 7 — Agent View observability.

Every test runs against a SYNTHETIC runtime in a temporary directory and a synthetic
roster. The live `agent/state/runtime/**` is never read for assertions and never
written: a test that depended on real Product records would fail the moment real work
moved, and one that wrote to them would be exactly the mutation Wave 7 forbids.

What these tests are really defending is a single line: Agent View observes, and
never invents. So they assert the shape of what it refuses to say — no availability,
no fabricated progress, no merged reason namespaces, no history rendered as live
work — as much as the shape of what it reports.

Stdlib only, like the rest of the suite.
"""
import os, sys, json, shutil, tempfile, inspect
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, section, summary, repo_root, state_path   # noqa: E402

sys.path.insert(0, state_path())
import store, validate, queue as q, view                            # noqa: E402


# ---------------------------------------------------------------- fixtures

def fresh_runtime():
    tmp = tempfile.mkdtemp()
    store.RUNTIME = os.path.join(tmp, "runtime")
    store.LOCKS = os.path.join(store.RUNTIME, ".locks")
    validate.RUNTIME = store.RUNTIME
    for kind in ("tasks", "dependencies", "interventions"):
        os.makedirs(os.path.join(store.RUNTIME, kind), exist_ok=True)
    return tmp


def fresh_roster(seats):
    """A synthetic binding directory. `seats` is {seat_id: role}.

    Pointing view at this proves the roster is read from bindings rather than from
    any list inside the code — the whole point of the dynamic-roster requirement.
    """
    tmp = tempfile.mkdtemp()
    b = os.path.join(tmp, "bindings")
    a = os.path.join(tmp, "agents")
    s = os.path.join(tmp, "status")
    for d in (b, a, s):
        os.makedirs(d, exist_ok=True)
    for seat, role in seats.items():
        with open(os.path.join(b, seat + ".yml"), "w") as fh:
            fh.write('name: "%s"\nmodel: sonnet\neffort: medium\nrole: %s\n' % (seat, role))
        with open(os.path.join(a, seat + ".md"), "w") as fh:
            fh.write("---\nname: %s\n---\n" % seat)
    view.BINDINGS_DIR, view.AGENTS_DIR, view.STATUS_DIR = b, a, s
    view.NAMING_CSV = os.path.join(tmp, "naming.csv")
    view.TELEMETRY_JSONL = os.path.join(tmp, "events.jsonl")
    return tmp


def topo(caps):
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "topology.json")
    with open(p, "w") as fh:
        json.dump({"record_type": "topology", "schema_version": 3,
                   "capabilities": caps}, fh)
    view.TOPOLOGY_JSON = p
    return tmp


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def task(key, capability="frontend", *, owner=None, canonical="ready",
         status_id="10008", observed=None, surfaces=(), review=None,
         evidence=(), route="self", effort=2, project="app"):
    """One synthetic task record written straight to the temp runtime.

    Written directly rather than through store.create so a test can express states the
    normal path would refuse to construct — an unreconciled review, conflicting
    evidence — which are exactly the states the view must render honestly.
    """
    rec = {
        "work_item_id": key, "record_type": "executable", "schema_version": 3,
        "revision": 1, "product_id": "dabbler", "project_id": project,
        "created_at": "2026-09-08T00:00:00Z", "updated_at": "2026-09-08T00:00:00Z",
        "lifecycle": {"canonical": canonical, "jira_status_id": status_id,
                      "jira_status_name": "Ready", "jira_column": "Ready",
                      "source": "jira"},
        "execution_profile": {"required_capability": capability, "work_effort": effort,
                              "validation_route": route, "completion_route": "DONE",
                              "profile_status": "complete", "characteristics": {},
                              "effective_fields": [], "provenance": {}},
        "surfaces": None if surfaces is None else list(surfaces),
        "ownership": ({"seat_id": owner, "claimed_at": "2026-09-08T10:00:00Z",
                       "claim_ref": "test"} if owner else None),
        "executor_evidence": [{"seat_id": s, "evidence_ref": "ref",
                               "evidenced_at": "2026-09-08T00:00:00Z"}
                              for s in evidence],
        "review_context": review,
    }
    if observed is not None:
        rec["lifecycle"]["observed_at"] = observed
    with open(os.path.join(store.RUNTIME, "tasks", key + ".json"), "w") as fh:
        json.dump(rec, fh)
    return rec


def dep(src, tgt, did="dep-1"):
    rec = {"dependency_id": did, "schema_version": 3, "revision": 1,
           "product_id": "dabbler", "relation": "BLOCKS",
           "completion_condition": "DONE", "source_work_item": src,
           "target_work_item": tgt, "source_project_id": "app",
           "target_project_id": "app", "created_by": "po", "reason_ref": "test",
           "created_at": "2026-09-08T00:00:00Z", "updated_at": "2026-09-08T00:00:00Z"}
    with open(os.path.join(store.RUNTIME, "dependencies", did + ".json"), "w") as fh:
        json.dump(rec, fh)
    return rec


def intervention(kind, target, iid="int-1"):
    rec = {"intervention_id": iid, "kind": kind,
           "scope": validate.KIND_SCOPE[kind], "target": target,
           "created_by": "orchestrator", "reason_ref": "test",
           "cleared_by": None, "cleared_at": None, "schema_version": 3,
           "revision": 1, "created_at": "2026-09-08T00:00:00Z",
           "updated_at": "2026-09-08T00:00:00Z"}
    with open(os.path.join(store.RUNTIME, "interventions", iid + ".json"), "w") as fh:
        json.dump(rec, fh)
    return rec


NOW = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
FRESH = iso(NOW - timedelta(seconds=60))
OLD = iso(NOW - timedelta(seconds=view.FRESHNESS_SECONDS + 600))

STD = {"frontend-1": "frontend", "frontend-2": "frontend",
       "backend-1": "backend", "ux-engineer-1": "ux-engineer", "qa": "qa"}
STD_TOPO = {"frontend": {"defined_seats": 2, "ceiling": 3, "expandable": True},
            "backend": {"defined_seats": 1, "ceiling": 2, "expandable": True},
            "ux-engineer": {"defined_seats": 1, "ceiling": 2, "expandable": True},
            "qa": {"defined_seats": 1, "ceiling": 2, "expandable": True},
            "product-designer": {"defined_seats": 0, "ceiling": 0, "expandable": False}}

TMP = []


def setup(seats=None, caps=None):
    t1 = fresh_runtime(); t2 = fresh_roster(seats or STD); t3 = topo(caps or STD_TOPO)
    TMP.extend([t1, t2, t3])
    return t1


# ---------------------------------------------------------------- roster

section("Wave 7 — dynamic roster")
setup()
p = view.build(now=NOW)
ok("roster derives from bindings, not a fixed list",
   sorted(s["seat_id"] for s in p["seats"]) == sorted(STD))
ok("roster count follows the binding directory",
   p["meta"]["roster_count"] == len(STD))

# A brand-new seat nobody has ever heard of must appear with no code change.
setup(seats=dict(STD, **{"payments-3": "payments"}))
p2 = view.build(now=NOW)
ok("a synthetic new binding appears with no flow.py/view.py edit",
   any(s["seat_id"] == "payments-3" for s in p2["seats"]))
ok("its capability comes from binding role:, not the slug",
   [s for s in p2["seats"] if s["seat_id"] == "payments-3"][0]["capability"] == "payments")

setup()
p = view.build(now=NOW)
ok("ux-engineer-1 capability is ux-engineer, derived from role:",
   [s for s in p["seats"] if s["seat_id"] == "ux-engineer-1"][0]["capability"] == "ux-engineer")

# A slug that flatly contradicts its role. If capability were parsed from the name
# this would come back "frontend"; role: is the only source, so it comes back backend.
setup(seats=dict(STD, **{"frontend-9": "backend"}))
p3 = view.build(now=NOW)
ok("capability is never inferred from the seat slug",
   [s for s in p3["seats"] if s["seat_id"] == "frontend-9"][0]["capability"] == "backend")
ok("a contradicting slug lands in its role's queue, not its slug's",
   "frontend-9" in [x for x in p3["queues"]
                    if x["capability"] == "backend"][0]["defined_seats"])

def code_only(src):
    """Source with the module docstring removed.

    Both files describe, in prose, the fabrications Wave 7 deleted — `30 - awake`,
    `p < 0.24 ? thinking : exec`. That prose is the record of why they went, so these
    checks read the CODE and let the explanation stand.
    """
    i = src.find('"""')
    j = src.find('"""', i + 3)
    return src[:i] + src[j + 3:] if i != -1 and j != -1 else src


flow_src = code_only(open(os.path.join(repo_root(), "agent", "scripts", "flow.py")).read())
view_src = open(os.path.join(state_path(), "view.py")).read()

ok("no hard-coded 26-seat assumption in view.py", "26" not in view_src)
ok("no `30 - awake` idle-count assumption in flow.py", "30 - awake" not in flow_src)
ok("no Team Lead legend/tier in flow.py",
   "Team leads" not in flow_src and "team-lead" not in flow_src.lower().replace(
       "the retired team lead files", ""))
ok("no elapsed-fraction thinking/exec fabrication in flow.py",
   'p < 0.24' not in flow_src and 'st: "thinking"' not in flow_src)
ok("no level_of() seat-name hierarchy parsing in flow.py", "def level_of" not in flow_src)

# Team Leads: gone from the live roster, still present as history.
setup(seats=dict(STD))
open(os.path.join(view.STATUS_DIR, "team-lead-1.md"), "w").write("### entry\n")
p = view.build(now=NOW)
ok("Team Leads absent from the live roster",
   not any("team-lead" in s["seat_id"] for s in p["seats"]))
ok("Team Lead status file remains queryable as history",
   "team-lead-1" in p["history"]["status_seats"])
ok("retired seat is listed as retired, not live",
   "team-lead-1" in p["history"]["retired_status_seats"])


# ---------------------------------------------------------------- orchestrator

section("Wave 7 — orchestrator")
setup()
p = view.build(now=NOW)
o = p["orchestrator"]
ok("orchestrator is not a seat", o["is_seat"] is False and o["owns_work"] is False)
ok("orchestrator excluded from the seat roster",
   not any(s["seat_id"] in ("orchestrator", "Main Session") for s in p["seats"]))
ok("orchestrator excluded from seat counts", p["meta"]["roster_count"] == len(STD))
ok("orchestrator excluded from queues and capacity",
   not any(qq["capability"] == "orchestrator" for qq in p["queues"] + p["capacity"]))


# ---------------------------------------------------------------- seat state

section("Wave 7 — seat state")
setup()
task("KAN-1", "frontend", owner="frontend-1", observed=FRESH)
p = view.build(now=NOW)
s1 = [s for s in p["seats"] if s["seat_id"] == "frontend-1"][0]
s2 = [s for s in p["seats"] if s["seat_id"] == "frontend-2"][0]
ok("owning seat reports OWNING with its work item",
   s1["ownership_state"] == "OWNING" and s1["current_work_item"] == "KAN-1")
ok("non-owning seat reports UNOWNED", s2["ownership_state"] == "UNOWNED")
ok("dispatchability is UNKNOWN, never inferred from ownership",
   s1["dispatchability"] == "UNKNOWN" and s2["dispatchability"] == "UNKNOWN")
ok("no seat is ever labelled AVAILABLE / ONLINE / AWAKE",
   not any(k in json.dumps(p["seats"]).upper()
           for k in ('"AVAILABLE"', '"ONLINE"', '"AWAKE"', '"EXECUTING"', '"THINKING"')))
ok("ownership==null does not produce an availability claim",
   "available" not in json.dumps(s2).lower())

# History must never become current state.
setup()
task("KAN-2", "backend", evidence=["backend-1"], observed=FRESH)
p = view.build(now=NOW)
sb = [s for s in p["seats"] if s["seat_id"] == "backend-1"][0]
w = p["work_items"][0]
ok("executor_evidence never becomes ownership",
   w["ownership"]["state"] == "UNOWNED" and w["executor_evidence"][0]["seat_id"] == "backend-1")
ok("evidenced seat is not shown as owning", sb["ownership_state"] == "UNOWNED")

setup()
open(os.path.join(view.STATUS_DIR, "frontend-1.md"), "w").write("### did a thing\n")
p = view.build(now=NOW)
s1 = [s for s in p["seats"] if s["seat_id"] == "frontend-1"][0]
ok("status history never becomes ownership",
   s1["history_present"] is True and s1["ownership_state"] == "UNOWNED")
ok("history flag is named history_present, not `logged`", "logged" not in s1)

# One owner maximum: surface the breach, never choose.
setup()
task("KAN-3", "frontend", owner="frontend-1", observed=FRESH)
task("KAN-4", "frontend", owner="frontend-1", observed=FRESH)
p = view.build(now=NOW)
s1 = [s for s in p["seats"] if s["seat_id"] == "frontend-1"][0]
ok("duplicate ownership surfaces STATE INCONSISTENCY",
   s1["state_inconsistency"] and "STATE INCONSISTENCY" in s1["state_inconsistency"])
ok("payload reports the inconsistency rather than picking an owner",
   any("STATE INCONSISTENCY" in m for m in p["ownership"]["inconsistencies"]))


# ---------------------------------------------------------------- reason namespaces

section("Wave 7 — reason namespaces")
setup()
task("KAN-5", "frontend", owner="frontend-1", observed=FRESH)
p = view.build(now=NOW)
w = [x for x in p["work_items"] if x["work_item_id"] == "KAN-5"][0]
qf = [x for x in p["queues"] if x["capability"] == "frontend"][0]
ok("claimability and execution reasons are separate fields",
   "claimability_reasons" in w and "execution_reasons" in w
   and w["claimability_reasons"] is not w["execution_reasons"])
ok("eligibility reasons are their own field", "eligibility_reasons" in w)
ok("owned item reports execution_reasons (continuation domain)",
   isinstance(w["execution_reasons"], list))
ok("not-owned / not-owner never appear in the queue claimability histogram",
   "not-owned" not in qf["claimability_reason_histogram"]
   and "not-owner" not in qf["claimability_reason_histogram"])
ok("claimability histogram carries only codes the canonical queue fn returned",
   set(qf["claimability_reason_histogram"]) <= set(
       q.unclaimable_reasons(store.read("task", "KAN-5"), all_tasks=[], now=NOW)) | {"already-owned"})

setup()
task("KAN-6", "frontend", observed=FRESH)
p = view.build(now=NOW)
w = [x for x in p["work_items"] if x["work_item_id"] == "KAN-6"][0]
ok("unowned item has no execution_reasons (question does not apply)",
   w["execution_reasons"] is None)


# ---------------------------------------------------------------- interventions

section("Wave 7 — interventions")
setup()
task("KAN-7", "frontend", owner="frontend-1", observed=FRESH)
intervention("stop", "KAN-7")
p = view.build(now=NOW)
s1 = [s for s in p["seats"] if s["seat_id"] == "frontend-1"][0]
w = [x for x in p["work_items"] if x["work_item_id"] == "KAN-7"][0]
ok("STOP overlays the owning seat", s1["stop_overlay"] is not None)
ok("STOP blocks continuation for that item", "task-stopped" in (w["execution_reasons"] or []))
ok("STOP renders task scope", p["interventions"]["active"][0]["scope"] == "task")

setup()
task("KAN-8", "frontend", observed=FRESH)
intervention("hold", "frontend", iid="int-h")
p = view.build(now=NOW)
qf = [x for x in p["queues"] if x["capability"] == "frontend"][0]
ok("HOLD renders on the capability queue", qf["hold"] is not None
   and qf["hold"]["scope"] == "capability")
ok("HOLD is NOT rendered as seat state",
   all(s.get("stop_overlay") is None and "HELD" not in json.dumps(s).upper()
       for s in p["seats"]))

setup()
task("KAN-9", "frontend", owner="frontend-1", observed=FRESH)
intervention("freeze", None, iid="int-f")
p = view.build(now=NOW)
ok("FREEZE renders at system scope on the Orchestrator",
   p["orchestrator"]["system_freeze"] is not None)
ok("FREEZE is NOT rendered as seat state",
   "FROZEN" not in json.dumps(p["seats"]).upper())
ok("FREEZE does not block an existing owner's continuation",
   [x for x in p["work_items"] if x["work_item_id"] == "KAN-9"][0]["execution_reasons"] == [])

setup()
p = view.build(now=NOW)
ok("no interventions renders NO ACTIVE INTERVENTIONS",
   p["interventions"]["empty_state"] == "NO ACTIVE INTERVENTIONS")
ok("RESUME is not a fourth kind", set(p["interventions"]["scopes"]) == {"stop", "hold", "freeze"})
ok("intervention panel exposes no controls", p["interventions"]["controls"] is False)


# ---------------------------------------------------------------- review

section("Wave 7 — validation / review")
setup()
task("KAN-10", "frontend", owner="frontend-1", canonical="review",
     status_id="10045", observed=FRESH, review=None)
p = view.build(now=NOW)
w = [x for x in p["work_items"] if x["work_item_id"] == "KAN-10"][0]
s1 = [s for s in p["seats"] if s["seat_id"] == "frontend-1"][0]
ok("review lifecycle with null review_context is UNRECONCILED",
   w["review"]["display_state"] == view.REVIEW_UNRECONCILED)
ok("owning an item in Review does NOT make the owner the reviewer",
   s1["is_review_owner_of"] is None and s1["owned_item_lifecycle"] == "review")
ok("seat reports the ITEM's lifecycle, not a REVIEWING seat state",
   "REVIEWING" not in json.dumps(s1).upper())

setup()
task("KAN-11", "frontend", canonical="review", status_id="10045", observed=FRESH,
     route="peer", review={"review_type": "peer", "review_owner": None,
                           "review_result": "pending", "review_cycle": 1,
                           "started_at": "2026-09-08T00:00:00Z"})
p = view.build(now=NOW)
w = p["work_items"][0]
ok("PEER with null review_owner waits for an exact reviewer",
   w["review"]["display_state"] == view.REVIEW_WAITING)
ok("null review_owner never reads as 'no review required'",
   "no review" not in json.dumps(w["review"]).lower())

setup()
task("KAN-12", "frontend", canonical="review", status_id="10045", observed=FRESH,
     route="peer", review={"review_type": "peer", "review_owner": "frontend-2",
                           "review_result": "pending", "review_cycle": 1,
                           "started_at": "2026-09-08T00:00:00Z"})
p = view.build(now=NOW)
s2 = [s for s in p["seats"] if s["seat_id"] == "frontend-2"][0]
ok("an exact review_owner renders that seat as reviewer",
   s2["is_review_owner_of"] == ["KAN-12"])
ok("reviewer identity is separate from execution ownership",
   s2["ownership_state"] == "UNOWNED")
ok("SELF/QA/PEER are alternatives, not stages",
   p["work_items"][0]["review"]["routes_are_alternatives"] is True
   and sorted(p["work_items"][0]["review"]["available_routes"]) == ["peer", "qa", "self"])


# ---------------------------------------------------------------- queues

section("Wave 7 — queues")
setup()
task("KAN-13", "frontend", observed=FRESH)
task("KAN-14", "backend", observed=FRESH)
p = view.build(now=NOW)
caps = [x["capability"] for x in p["queues"]]
ok("queue union includes topology capabilities with zero work",
   "product-designer" in caps and "qa" in caps)
ok("every capability with seats renders a queue",
   set(["frontend", "backend", "ux-engineer", "qa"]) <= set(caps))
qf = [x for x in p["queues"] if x["capability"] == "frontend"][0]
ok("queue reports eligible / claimable / blocked counts",
   all(k in qf for k in ("eligible_depth", "claimable_count", "blocked_count")))
ok("queue never labels unowned seats as available",
   qf["unowned_seat_label"] == "SEATS WITHOUT CURRENT OWNERSHIP"
   and "available" not in json.dumps(qf).lower())
ok("empty capability queue renders honestly rather than vanishing",
   [x for x in p["queues"] if x["capability"] == "product-designer"][0]["defined_seat_count"] == 0)


# ---------------------------------------------------------------- dependencies

section("Wave 7 — dependencies")
setup()
task("KAN-15", "frontend", canonical="review", observed=FRESH)
task("KAN-16", "frontend", observed=FRESH)
dep("KAN-15", "KAN-16")
p = view.build(now=NOW)
d = p["dependencies"][0]
ok("dependency renders source BLOCKS target",
   d["source_work_item"] == "KAN-15" and d["relation"] == "BLOCKS"
   and d["target_work_item"] == "KAN-16")
ok("target blocked while source is not DONE", d["target_blocked"] is True)
ok("satisfaction is derived, never stored", d["satisfied_is_derived"] is True
   and "satisfied" not in store.read("dependency", "dep-1"))
ok("blocked target carries dependency-blocked in claimability",
   "dependency-blocked" in [x for x in p["work_items"]
                            if x["work_item_id"] == "KAN-16"][0]["claimability_reasons"])

setup()
task("KAN-17", "frontend", canonical="done", observed=FRESH)
task("KAN-18", "frontend", observed=FRESH)
dep("KAN-17", "KAN-18")
p = view.build(now=NOW)
ok("only canonical DONE clears a BLOCKS edge",
   p["dependencies"][0]["target_blocked"] is False)
ok("completion condition is DONE", p["dependencies"][0]["completion_condition"] == "DONE")


# ---------------------------------------------------------------- surfaces

section("Wave 7 — surfaces / contention")
setup()
task("KAN-19", "frontend", surfaces=None, observed=FRESH)
task("KAN-20", "frontend", surfaces=[], observed=FRESH)
task("KAN-21", "frontend", surfaces=["lib/x.dart"], observed=FRESH)
p = view.build(now=NOW)
by = {x["work_item_id"]: x["surfaces"]["state"] for x in p["work_items"]}
ok("surfaces null renders UNASSESSED", by["KAN-19"] == "UNASSESSED")
ok("surfaces [] renders ASSESSED_EMPTY", by["KAN-20"] == "ASSESSED_EMPTY")
ok("surfaces populated renders ASSESSED_PATHS", by["KAN-21"] == "ASSESSED_PATHS")
ok("unassessed surfaces block a claim",
   "surfaces-unassessed" in [x for x in p["work_items"]
                             if x["work_item_id"] == "KAN-19"][0]["claimability_reasons"])
ok("contention is labelled file-surface only",
   p["contention"]["mechanism"] == "FILE-SURFACE CONTENTION")
ok("compatibility note warns no-file-collision is not no-logical-collision",
   "DATABASE-OBJECT" in p["contention"]["compatibility_note"])


# ---------------------------------------------------------------- freshness

section("Wave 7 — Jira freshness")
setup()
task("KAN-22", "frontend", observed=FRESH)
p = view.build(now=NOW)
ok("recent observation renders LIVE", p["work_items"][0]["lifecycle"]["freshness"] == "LIVE")

setup()
task("KAN-23", "frontend", observed=OLD)
p = view.build(now=NOW)
ok("old observation renders STALE", p["work_items"][0]["lifecycle"]["freshness"] == "STALE")
ok("stale lifecycle never renders as live",
   p["work_items"][0]["lifecycle"]["freshness"] != "LIVE")

setup()
task("KAN-24", "frontend", observed=None)
p = view.build(now=NOW)
ok("absent observation renders UNAVAILABLE",
   p["work_items"][0]["lifecycle"]["freshness"] == "UNAVAILABLE")
ok("freshness reuses the canonical Wave 6 constant",
   view.FRESHNESS_SECONDS == q.CLAIM_FRESHNESS_SECONDS)
ok("Jira-only fields are declared NOT OBSERVED, never invented",
   p["work_items"][0]["jira_only_fields"]["title"] == "NOT OBSERVED"
   and p["work_items"][0]["jira_only_fields"]["due_date"] == "NOT OBSERVED")
ok("view.py contains no Jira/HTTP client",
   not any(t in view_src for t in ("urllib", "http.client", "requests", "atlassian")))


# ---------------------------------------------------------------- degraded

section("Wave 7 — degraded / empty states")
setup()
p = view.build(now=NOW)
ok("fresh-clone empty runtime renders NO WORK RECORDED",
   p["meta"]["empty_state"] == "NO WORK RECORDED" and p["meta"]["task_count"] == 0)
ok("empty runtime still renders the full roster", len(p["seats"]) == len(STD))
ok("empty runtime reports no active ownership",
   p["ownership"]["empty_state"] == "NO ACTIVE OWNERSHIP")
ok("no telemetry renders NO SESSION ACTIVITY OBSERVED",
   p["telemetry"]["state"] == "NO SESSION ACTIVITY OBSERVED")

setup()
task("KAN-25", "frontend", observed=FRESH)
p = view.build(now=NOW)
ok("runtime with no ownership reports NO ACTIVE OWNERSHIP",
   p["ownership"]["active_count"] == 0
   and p["ownership"]["empty_state"] == "NO ACTIVE OWNERSHIP")


# ---------------------------------------------------------------- telemetry

section("Wave 7 — telemetry is advisory")
setup()
with open(view.TELEMETRY_JSONL, "w") as fh:
    # A free-form dispatch label that is NOT a canonical seat id, next to a claim
    # that Persistent State flatly contradicts.
    fh.write(json.dumps({"event": "PreToolUse", "at": FRESH,
                         "agent_type": "frontend-1-surfaces", "tool_name": "Bash"}) + "\n")
task("KAN-26", "frontend", observed=FRESH)          # frontend-1 owns nothing
p = view.build(now=NOW)
t = p["telemetry"]
s1 = [s for s in p["seats"] if s["seat_id"] == "frontend-1"][0]
ok("telemetry is marked advisory", t["advisory"] is True)
ok("telemetry is authoritative for nothing", t["authoritative_for"] == [])
ok("free-form agent_type is not treated as a canonical seat id",
   all(l["seat_correlation"] == "UNCORRELATED" for l in t["labels"]))
ok("telemetry conflict loses: Persistent State says UNOWNED",
   s1["ownership_state"] == "UNOWNED" and s1["recent_session_activity"] is None)
ok("telemetry never sets ownership/lifecycle/progress",
   not any(k in json.dumps(t).lower()
           for k in ("progress", "percent", "executing", "thinking")))
ok("no token or cost analytics in the payload",
   not any(k in json.dumps(p).lower() for k in ('"cost"', '"tokens"', "output_tokens")))
ok("capacity exposes no utilisation / score / forecast field",
   not any(bad in k.lower() for row in p["capacity"] for k in row
           for bad in ("utilisation", "utilization", "score", "forecast", "percent",
                       "token", "cost")))


# ---------------------------------------------------------------- read-only

section("Wave 7 — read-only enforcement")
ok("view.py never calls a store mutation",
   not any(("store." + fn + "(") in view_src
           for fn in ("claim", "release", "create", "update", "create_intervention",
                      "clear_intervention", "set_surfaces", "observe_lifecycle",
                      "peer_fail_transfer", "set_characteristics", "create_dependency")))
ok("view.py opens no file for writing",
   ', "w"' not in view_src and "'w'" not in view_src)
ok("flow.py exposes GET only",
   "def do_GET" in flow_src and not any(("def do_" + v) in flow_src
                                        for v in ("POST", "PUT", "PATCH", "DELETE")))
ok("flow.py page issues no state-changing request",
   "method:" not in flow_src and "XMLHttpRequest" not in flow_src)
ok("flow.py never imports a mutation path",
   "store.claim" not in flow_src and "create_intervention" not in flow_src)
ok("no claim/wake/stop/resume control in the page",
   not any(('id="' + c + '"') in flow_src
           for c in ("claim", "wake", "stop", "resume", "assign")))
ok("payload declares itself read-only", view.build(now=NOW)["meta"]["read_only"] is True)


# ---------------------------------------------------------------- cleanup

for t in TMP:
    shutil.rmtree(t, ignore_errors=True)

summary()
sys.exit(1 if __import__("_harness").FAILED else 0)
