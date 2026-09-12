"""Post-Wave-8 slice 1: operating-mode isolation."""
import copy, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root, state_path

ROOT = repo_root()
sys.path.insert(0, state_path())
import board, operations, queue as q, store, validate  # noqa: E402

OBS = "2026-09-12T00:00:00Z"
JIRA = {"status_id": "10008", "has_due_date": True, "has_acceptance_criteria": True}


def task(key, owner=None):
    return {"work_item_id": key, "product_id": "dabbler", "project_id": "app",
            "record_type": "executable",
            "lifecycle": {"canonical": "ready", "jira_column": board.column_for("10008"),
                          "jira_status_id": "10008", "jira_status_name": board.name_for("10008"),
                          "observed_at": OBS, "source": "jira"},
            "executor_evidence": [], "review_context": None, "ownership": owner, "surfaces": [],
            "execution_profile": {"profile_status": "partial", "required_capability": "backend",
                "work_effort": 1, "completion_route": "DONE",
                "effective_fields": ["project_id", "required_capability", "work_effort",
                                     "completion_route"],
                "provenance": {"required_capability": {"by": "system-maintenance"},
                               "completion_route": {"by": "system-policy"}}}}


section("OPERATING MODE RECORD")
tmp = tempfile.mkdtemp()
store.RUNTIME = os.path.join(tmp, "runtime")
store.LOCKS = os.path.join(store.RUNTIME, ".locks")
validate.RUNTIME = store.RUNTIME

ok("legacy runtime defaults to PRODUCT_EXECUTION", store.current_operating_mode() == operations.PRODUCT_EXECUTION)
raises("unknown mode refused", lambda: store.set_operating_mode("MAINTENANCE", "ceo", "r"), "unknown operating mode")
mode = store.set_operating_mode(operations.SYSTEM_MAINTENANCE, "ceo", "post-wave8:slice-1")
ok("exactly one current record exists", mode["operating_mode_id"] == "current" and len(store.read_all("operating_mode")) == 1)
raises("transition requires CAS", lambda: store.set_operating_mode(operations.PRODUCT_EXECUTION, "ceo", "r"), "expected_revision")
raises("stale transition refused", lambda: store.set_operating_mode(operations.PRODUCT_EXECUTION, "ceo", "r", 99), "stale write")

section("PRODUCT ISOLATION AND PRESERVATION")
owned = store.create("task", task("KAN-990", {"seat_id": "backend-1", "claimed_at": OBS,
                                               "claim_ref": "existing"}), rid="KAN-990")
waiting = store.create("task", task("KAN-991"), rid="KAN-991")
before = {kind: copy.deepcopy(store.read_all(kind))
          for kind in ("task", "dependency", "intervention", "policy")}
ok("maintenance appears in derived claimability",
   "system-maintenance-active" in q.unclaimable_reasons(waiting, jira=JIRA))
raises("maintenance refuses authoritative claim",
       lambda: store.claim("KAN-991", "backend-2", "c", waiting["revision"],
                           capability_of_seat="backend", jira_status_id="10008"),
       "system-maintenance-active")
raises("maintenance refuses existing-owner wake",
       lambda: store.assert_execution_permitted("KAN-990", "backend-1"),
       "system-maintenance-active")
ok("maintenance is visible before the wake attempt",
   q.execution_reasons(owned, "backend-1") == ["system-maintenance-active"])
after = {kind: store.read_all(kind) for kind in before}
ok("maintenance attempts preserve all Product records", before == after)

product = store.set_operating_mode(operations.PRODUCT_EXECUTION, "ceo", "resume:accepted",
                                   mode["revision"])
ok("Product continuation resumes through existing gates",
   store.assert_execution_permitted("KAN-990", "backend-1")["work_item_id"] == "KAN-990")
claimed = store.claim("KAN-991", "backend-2", "c", waiting["revision"],
                      capability_of_seat="backend", jira_status_id="10008")
ok("Product claims resume", claimed["ownership"]["seat_id"] == "backend-2")

iv = store.create_intervention("freeze", None, "ceo", "independence")
ok("FREEZE remains independent in Product mode",
   "system-frozen" in q.unclaimable_reasons(task("KAN-992"), jira=JIRA))
store.clear_intervention(iv["intervention_id"], iv["revision"], "ceo")
maintenance = store.set_operating_mode(operations.SYSTEM_MAINTENANCE, "ceo", "return:maintenance",
                                       product["revision"])
ok("mode transition changed only the singleton",
   maintenance["revision"] == 3 and store.read("task", "KAN-990") == owned)

section("OBSERVATION AND REPORTED ENVIRONMENT")
observed = store.set_operational_context(
    "KAN-990", owned["revision"], "observed_condition",
    {"locality": "local", "runtime": "flutter_web", "platform": "chrome",
     "environment_ref": "localhost"}, "ceo", "report:blank-localhost-chrome")
context = observed["operational_context"]
ok("observed condition starts investigation", context["initial_phase"] == "investigation")
ok("localhost Chrome derives terminal Flutter target",
   context["primary_target"]["launch_command"] == "flutter run -d chrome"
   and context["primary_target"]["browser_automation"] is False)
local_android = operations.derive_primary_target(
    {"locality": "local", "runtime": "flutter", "platform": "android",
     "environment_ref": "emulator-5554"})
ok("other local runtimes preserve reported locality",
   local_android["locality"] == "local" and local_android["platform"] == "android")
bad = copy.deepcopy(observed)
bad["operational_context"]["primary_target"] = {
    "locality": "deployed", "environment_ref": "canary", "source": "reported_environment"}
ok("validator rejects Canary replacing localhost",
   any("cannot be silently replaced" in error
       for error in validate.validate_record("task", bad)))
repro = store.set_operational_context(
    "KAN-990", observed["revision"], "reproduction_request",
    {"locality": "unknown", "runtime": None, "platform": None},
    "po", "jira:explicit-reproduction-request")
ok("explicit reproduction request starts reproduction",
   repro["operational_context"]["initial_phase"] == "reproduction")
raises("unknown locality refused",
       lambda: store.set_operational_context(
           "KAN-990", repro["revision"], "observed_condition",
           {"locality": "canary", "runtime": "flutter_web", "platform": "chrome"},
           "ceo", "report:x"), "unknown reported-environment locality")

section("CAUSAL VALIDATION SCOPE")
shared_task = store.create("task", task("KAN-993"), rid="KAN-993")
shared_context = store.set_operational_context(
    "KAN-993", shared_task["revision"], "observed_condition",
    {"locality": "local", "runtime": "flutter_web", "platform": "chrome",
     "environment_ref": "localhost"}, "ceo", "report:shared-bootstrap")
shared = store.set_diagnosis(
    "KAN-993", shared_context["revision"], "flutter-bootstrap",
    ["lib/bootstrap.dart"], "shared", ["chrome", "ios"],
    "worker:frontend-1", "diagnosis:bootstrap-init")
plan = shared["operational_context"]["validation_plan"]
ok("shared cause requires automation and primary runtime",
   [target["target_id"] for target in plan["required"]]
   == ["shared-automated", "primary-chrome"])
ok("other reported platform is optional confidence evidence",
   [target["target_id"] for target in plan["optional"]] == ["confidence-ios"])
ok("missing required evidence blocks completion", not operations.validation_complete(plan))
one = store.record_validation_evidence("KAN-993", shared["revision"],
                                       "shared-automated", "test:bootstrap")
two = store.record_validation_evidence("KAN-993", one["revision"],
                                       "primary-chrome", "runtime:localhost-chrome")
ok("all required evidence completes without optional iOS",
   operations.validation_complete(two["operational_context"]["validation_plan"]))

android_task = store.create("task", task("KAN-994"), rid="KAN-994")
android_context = store.set_operational_context(
    "KAN-994", android_task["revision"], "observed_condition",
    {"locality": "unknown", "runtime": "flutter", "platform": "android"},
    "ceo", "report:android-notification")
android = store.set_diagnosis(
    "KAN-994", android_context["revision"], "android-notification-channel",
    ["android/app/src/main/AndroidManifest.xml"], "platform_specific", ["android"],
    "worker:frontend-2", "diagnosis:manifest")
ok("platform-specific Android cause requires Android",
   [target["target_id"] for target in android["operational_context"]["validation_plan"]["required"]]
   == ["required-android"])
bad_plan = copy.deepcopy(android)
bad_plan["operational_context"]["validation_plan"]["required"] = []
ok("validator rejects a weakened derived plan",
   any("must derive" in error for error in validate.validate_record("task", bad_plan)))
raises("changed Android surface cannot be labelled shared",
       lambda: store.set_diagnosis(
           "KAN-994", android["revision"], "android-channel",
           ["android/app/src/main/AndroidManifest.xml"], "shared", ["android"],
           "worker:frontend-2", "diagnosis:wrong-scope"),
       "contradicts changed surfaces")
raises("re-diagnosis cannot silently remove required targets",
       lambda: store.set_diagnosis(
           "KAN-993", two["revision"], "android-wrapper",
           ["android/app/src/main/AndroidManifest.xml"], "platform_specific", ["android"],
           "worker:frontend-1", "diagnosis:revised-cause"),
       "supersedes_validation_ref is required")
recomputed = store.set_diagnosis(
    "KAN-993", two["revision"], "android-wrapper",
    ["android/app/src/main/AndroidManifest.xml"], "platform_specific", ["android"],
    "worker:frontend-1", "diagnosis:revised-cause", "review:corrected-cause")
required_ids = {target["target_id"]
                for target in recomputed["operational_context"]["validation_plan"]["required"]}
ok("corrected diagnosis derives only current required scope",
   required_ids == {"required-android"})
ok("superseded plan remains auditable",
   recomputed["operational_context"]["validation_history"][0]["superseded_by"]
   == "review:corrected-cause")

shutil.rmtree(tmp, ignore_errors=True)
sys.exit(summary())
