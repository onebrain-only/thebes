#!/usr/bin/env python3
"""CANONICAL TEST ROUTING — one deterministic function, lowest-cost sufficient.

What this suite defends, in one sentence: NOT EVERY TASK INVOKES QA, AND NOT
EVERY QA TASK INVOKES EVERY TOOL. Documentation changes select nothing;
config changes select the static gate only; intentional and release layers are
unreachable from paths alone; the same profile always yields the same decision.

Stdlib only. No workspace, no subprocess, no state.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.qa.layers import INTENTIONAL, LAYERS, RELEASE, ROUTINE, availability  # noqa: E402
from agent.qa.routing import (                                       # noqa: E402
    BACKEND, CONFIG, DART, DOCS, TESTS, UNKNOWN, WEB, ChangeProfile,
    classify_change, classify_path, select_layers,
)


def ids(decision):
    return decision.selected_ids


class ChangeClassification(unittest.TestCase):
    def test_paths_classify_by_kind(self):
        self.assertEqual(classify_path("docs/ARCHITECTURE.md"), DOCS)
        self.assertEqual(classify_path("README.md"), DOCS)
        self.assertEqual(classify_path("pubspec.yaml"), CONFIG)
        self.assertEqual(classify_path("lib/main.dart"), DART)
        self.assertEqual(classify_path("Dabbler/dabbler-code/lib/x.dart"), DART)
        self.assertEqual(classify_path("supabase/migrations/1.sql"), BACKEND)
        self.assertEqual(classify_path("web/index.html"), WEB)
        self.assertEqual(classify_path("tests/e2e/smoke.spec.ts"), TESTS)
        self.assertEqual(classify_path("test/foo_test.dart"), TESTS)
        self.assertEqual(classify_path("alpha.dart"), UNKNOWN)

    def test_empty_surfaces_are_unknown_not_docs(self):
        self.assertEqual(classify_change(()), frozenset({UNKNOWN}))


class LowestCostSufficient(unittest.TestCase):
    def test_docs_only_selects_nothing(self):
        d = select_layers(ChangeProfile("content", ("docs/CONVENTIONS.md", "README.md")))
        self.assertEqual(ids(d), ())
        self.assertIn("documentation-only", d.basis)

    def test_config_only_selects_static_gate_only(self):
        d = select_layers(ChangeProfile("devops", ("pubspec.yaml", "pubspec.lock")))
        self.assertEqual(ids(d), ("flutter_analyze",))

    def test_dart_change_selects_ci_gates(self):
        d = select_layers(ChangeProfile("frontend", ("lib/core/x.dart",)))
        self.assertEqual(ids(d), ("flutter_analyze", "flutter_unit"))

    def test_user_visible_dart_change_adds_web_e2e(self):
        d = select_layers(ChangeProfile(
            "frontend", ("lib/features/a/screen.dart",),
            (("user_visible_runtime", True),), "flutter_web", "chrome"))
        self.assertEqual(ids(d), ("flutter_analyze", "flutter_unit", "playwright_e2e"))

    def test_mobile_platform_adds_maestro(self):
        d = select_layers(ChangeProfile("frontend", ("lib/main.dart",),
                                        platform="android"))
        self.assertIn("maestro_smoke", ids(d))
        self.assertNotIn("playwright_e2e", ids(d))

    def test_backend_change_selects_api_layer(self):
        d = select_layers(ChangeProfile("backend", ("supabase/migrations/x.sql",)))
        self.assertEqual(ids(d), ("api_postman",))

    def test_backend_risk_characteristics_pull_api_layer_regardless_of_paths(self):
        for name in ("schema_change", "money_path", "security_sensitive"):
            d = select_layers(ChangeProfile("backend", ("lib/data/repo.dart",),
                                            ((name, True),)))
            self.assertIn("api_postman", ids(d), name)

    def test_test_only_change_runs_the_owning_layer(self):
        self.assertEqual(ids(select_layers(ChangeProfile("frontend", ("tests/e2e/x.spec.ts",)))),
                         ("playwright_e2e",))
        self.assertEqual(ids(select_layers(ChangeProfile("backend", ("tests/api/c.json",)))),
                         ("api_postman",))
        self.assertEqual(ids(select_layers(ChangeProfile("frontend", ("test/a_test.dart",)))),
                         ("flutter_unit",))

    def test_editing_a_k6_script_does_not_make_perf_routine(self):
        d = select_layers(ChangeProfile("backend", ("tests/perf/k6/smoke.js",)))
        self.assertNotIn("k6_perf", ids(d))

    def test_unknown_surfaces_get_the_cheap_honest_floor(self):
        d = select_layers(ChangeProfile("backend", ("alpha.dart", "beta.dart")))
        self.assertEqual(ids(d), ("flutter_analyze", "flutter_unit"))

    def test_selection_is_cheapest_first(self):
        d = select_layers(ChangeProfile("frontend", ("lib/a.dart", "supabase/x.sql"),
                                        (("user_visible_runtime", True),), "flutter_web"))
        costs = [LAYERS[i].cost for i in ids(d)]
        self.assertEqual(costs, sorted(costs))


class IntentionalAndReleaseLayersNeedFlags(unittest.TestCase):
    def test_no_path_reaches_testsprite_k6_or_browserstack(self):
        every_kind = ("docs/x.md", "pubspec.yaml", "lib/a.dart", "web/i.html",
                      "supabase/x.sql", "android/b.gradle", "tests/e2e/s.spec.ts", "z")
        d = select_layers(ChangeProfile("frontend", every_kind,
                                        (("user_visible_runtime", True),)))
        for lid in ("testsprite_exploratory", "k6_perf", "browserstack_devices"):
            self.assertNotIn(lid, ids(d), lid)
        skipped = dict(d.skipped)
        self.assertIn("intentional", skipped["testsprite_exploratory"])
        self.assertIn("intentional", skipped["k6_perf"])
        self.assertIn("release", skipped["browserstack_devices"])

    def test_performance_scope_selects_k6(self):
        d = select_layers(ChangeProfile("backend", ("supabase/f/i.ts",),
                                        performance_scope=True))
        self.assertIn("k6_perf", ids(d))
        self.assertIn("performance_scope", d.flags)

    def test_exploratory_request_needs_a_user_visible_change(self):
        visible = select_layers(ChangeProfile("frontend", ("lib/s.dart",),
                                              (("user_visible_runtime", True),),
                                              exploratory_requested=True))
        self.assertIn("testsprite_exploratory", ids(visible))
        docs = select_layers(ChangeProfile("content", ("docs/x.md",),
                                           exploratory_requested=True))
        self.assertNotIn("testsprite_exploratory", ids(docs))

    def test_release_candidate_adds_devices_and_mobile_smoke(self):
        d = select_layers(ChangeProfile("frontend", ("lib/main.dart",),
                                        release_candidate=True))
        self.assertIn("browserstack_devices", ids(d))
        self.assertIn("maestro_smoke", ids(d))


class Determinism(unittest.TestCase):
    def test_same_profile_same_decision(self):
        p = ChangeProfile("frontend", ("lib/a.dart", "supabase/x.sql"),
                          (("user_visible_runtime", True),), "flutter_web", "chrome")
        self.assertEqual(select_layers(p), select_layers(p))

    def test_from_task_reads_the_canonical_fields(self):
        task = {"execution_profile": {"required_capability": "frontend",
                                      "characteristics": {"user_visible_runtime": True}},
                "surfaces": ["lib/x.dart"],
                "operational_context": {"primary_target": {"runtime": "flutter_web",
                                                           "platform": "chrome"}}}
        p = ChangeProfile.from_task(task)
        self.assertEqual((p.required_capability, p.runtime, p.platform),
                         ("frontend", "flutter_web", "chrome"))
        self.assertTrue(p.characteristic("user_visible_runtime"))


class RegistryShape(unittest.TestCase):
    def test_external_layers_have_no_argv_and_are_never_routine(self):
        for lid, layer in LAYERS.items():
            if layer.external:
                self.assertEqual(layer.argv, (), lid)
                self.assertNotEqual(layer.trigger, ROUTINE, lid)

    def test_availability_reports_without_deciding(self):
        report = availability(which=lambda tool: tool == "flutter")
        self.assertTrue(report["flutter_analyze"]["available"])
        self.assertFalse(report["maestro_smoke"]["available"])
        self.assertTrue(report["testsprite_exploratory"]["external"])
        self.assertIsNone(report["testsprite_exploratory"]["available"])

    def test_triggers_are_the_three_named_policies(self):
        self.assertEqual({LAYERS[l].trigger for l in LAYERS},
                         {ROUTINE, INTENTIONAL, RELEASE})


if __name__ == "__main__":
    unittest.main()
