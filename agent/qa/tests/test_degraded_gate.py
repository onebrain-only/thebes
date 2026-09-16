#!/usr/bin/env python3
"""ONE BROKEN LAYER MUST NOT CONDEMN THE WHOLE ACT — and must never be hidden.

Found by real Product work on 2026-09-16. `flutter test` is broken on this
machine by a native-asset link fault; routing selects it for every Dart change;
so a single `TEST_INFRASTRUCTURE_FAILURE` returned `GATE_INFRA` and the
validation route refused KAN-212 and KAN-208 — without ever running
`flutter analyze`, the one gate that sees the barrel export lines those tickets
change. Nothing on the machine could be validated at all.

The invariant this suite defends has two halves, and the second matters more:

  1. If SOMETHING answered, the act proceeds on that evidence (`GATE_DEGRADED`).
  2. DEGRADED IS NOT A PASS. It is never `decisive`, the reviewer keeps full
     effort, and the missing layer is named in the reviewer's text. Partial
     evidence silently read as complete would be worse than refusing.

Stdlib only. No subprocess, no workspace, no state.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution.provider import ModelIntent, ReasoningEffort, TestStatus  # noqa: E402
from agent.qa.gate import DeterministicGate                          # noqa: E402
from agent.qa.results import (                                       # noqa: E402
    Classification, GATE_DEGRADED, GATE_EXTERNAL, GATE_INFRA, GATE_NOT_RUN,
    GATE_PASS, GATE_PRODUCT, GATE_TEST, LayerRun, gate_outcome,
    render_for_validator, to_test_claims, unavailable_layers,
)
from agent.qa.routing import (                                       # noqa: E402
    ChangeProfile, LayerSelection, RoutingDecision, select_layers,
)
from agent.qa.runner import run_layers                               # noqa: E402

INFRA = Classification.TEST_INFRASTRUCTURE_FAILURE
NATIVE_ASSETS = "Building native assets failed. See the logs for more details."


def run(layer_id, classification, exit_code=1, reason=None, tail=()):
    return LayerRun(layer_id, "cmd", exit_code, classification, 1.0, "a.log",
                    tuple(tail), reason)


class NothingLearnedStillRefuses(unittest.TestCase):
    """The original protection must survive: a gate that learned nothing refuses."""

    def test_the_only_layer_broke(self):
        self.assertEqual(gate_outcome([run("flutter_unit", INFRA, 1, NATIVE_ASSETS)]),
                         GATE_INFRA)

    def test_every_layer_that_ran_broke(self):
        self.assertEqual(gate_outcome([run("flutter_unit", INFRA),
                                       run("playwright_e2e", INFRA)]), GATE_INFRA)

    def test_broken_plus_not_run_is_still_infra(self):
        # NOT_RUN answers nothing about the Product, so it cannot rescue a gate.
        self.assertEqual(gate_outcome([run("flutter_unit", INFRA),
                                       run("playwright_e2e", Classification.NOT_RUN,
                                           None, "no playwright.config.ts")]),
                         GATE_INFRA)

    def test_external_only_failure_is_named_external_not_infra(self):
        self.assertEqual(gate_outcome([run("testsprite_exploratory",
                                           Classification.EXTERNAL_QA_FAILURE)]),
                         GATE_EXTERNAL)

    def test_nothing_ran_at_all(self):
        self.assertEqual(gate_outcome([]), GATE_NOT_RUN)
        self.assertEqual(gate_outcome([run("flutter_unit", Classification.NOT_RUN,
                                           None, "no pubspec.yaml")]), GATE_NOT_RUN)


class SomethingLearnedProceedsDegraded(unittest.TestCase):

    def test_the_exact_kan_212_shape(self):
        runs = [run("flutter_analyze", Classification.PASS, 0),
                run("flutter_unit", INFRA, 1, None, [NATIVE_ASSETS]),
                run("playwright_e2e", Classification.PASS, 0)]
        self.assertEqual(gate_outcome(runs), GATE_DEGRADED)

    def test_a_product_defect_still_surfaces_through_a_broken_sibling(self):
        runs = [run("flutter_unit", INFRA),
                run("playwright_e2e", Classification.PRODUCT_DEFECT)]
        self.assertEqual(gate_outcome(runs), GATE_DEGRADED)

    def test_clean_gates_are_unchanged(self):
        self.assertEqual(gate_outcome([run("flutter_analyze", Classification.PASS, 0),
                                       run("playwright_e2e", Classification.PASS, 0)]),
                         GATE_PASS)
        self.assertEqual(gate_outcome([run("playwright_e2e",
                                           Classification.PRODUCT_DEFECT)]),
                         GATE_PRODUCT)
        self.assertEqual(gate_outcome([run("playwright_e2e",
                                           Classification.TEST_DEFECT)]), GATE_TEST)


class DegradedIsNeverMistakenForAPass(unittest.TestCase):
    """The half that matters: incomplete evidence must not read as complete."""

    def gate(self, outcome, runs):
        decision = select_layers(ChangeProfile("frontend", ("lib/a.dart",)))
        return DeterministicGate(decision, tuple(runs), outcome, "/ws")

    def test_degraded_is_not_decisive_and_keeps_full_reviewer_effort(self):
        g = self.gate(GATE_DEGRADED, [run("flutter_analyze", Classification.PASS, 0),
                                      run("flutter_unit", INFRA, 1, NATIVE_ASSETS)])
        self.assertFalse(g.decisive)
        self.assertEqual(g.reviewer_effort(),
                         (ModelIntent.BALANCED, ReasoningEffort.HIGH))

    def test_a_fully_clean_gate_is_still_decisive_and_cheap(self):
        g = self.gate(GATE_PASS, [run("flutter_analyze", Classification.PASS, 0)])
        self.assertTrue(g.decisive)
        self.assertEqual(g.reviewer_effort(),
                         (ModelIntent.COST_EFFICIENT, ReasoningEffort.LOW))

    def test_the_reviewer_is_told_which_layer_is_missing_and_what_it_means(self):
        runs = [run("flutter_analyze", Classification.PASS, 0),
                run("flutter_unit", INFRA, 1, None, [NATIVE_ASSETS]),
                run("playwright_e2e", Classification.PASS, 0)]
        text = render_for_validator(runs)
        self.assertIn("INCOMPLETE COVERAGE", text)
        self.assertIn("flutter_unit", text)
        self.assertIn("1 of 3", text)
        self.assertIn("do NOT cover", text)
        self.assertIn("not a Product one", text)

    def test_a_clean_gate_carries_no_incomplete_coverage_warning(self):
        text = render_for_validator([run("flutter_analyze", Classification.PASS, 0)])
        self.assertNotIn("INCOMPLETE COVERAGE", text)

    def test_the_broken_layer_is_reported_not_run_never_passed(self):
        claims = to_test_claims([run("flutter_unit", INFRA, 1, NATIVE_ASSETS)])
        self.assertEqual(claims[0].status, TestStatus.NOT_RUN)

    def test_unavailable_names_every_broken_layer_with_a_reason(self):
        runs = [run("flutter_analyze", Classification.PASS, 0),
                run("flutter_unit", INFRA, 1, NATIVE_ASSETS),
                run("testsprite_exploratory", Classification.EXTERNAL_QA_FAILURE, 1,
                    "external-not-invoked")]
        self.assertEqual([lid for lid, _ in unavailable_layers(runs)],
                         ["flutter_unit", "testsprite_exploratory"])
        self.assertIn("native assets", dict(unavailable_layers(runs))["flutter_unit"])

    def test_the_payload_carries_the_hole_for_the_receipt(self):
        g = self.gate(GATE_DEGRADED, [run("flutter_analyze", Classification.PASS, 0),
                                      run("flutter_unit", INFRA, 1, NATIVE_ASSETS)])
        payload = g.as_payload()
        self.assertEqual(payload["outcome"], GATE_DEGRADED)
        self.assertFalse(payload["decisive"])
        self.assertEqual(payload["unavailable"],
                         [{"layer_id": "flutter_unit", "reason": NATIVE_ASSETS}])


class TheRunnerNoLongerStopsEarly(unittest.TestCase):
    """The change that makes the rest reachable: a broken layer is not the end."""

    def test_every_selected_layer_runs_even_after_an_infrastructure_failure(self):
        attempted = []

        def fake_run_layer(layer_id, workspace_path, artifact_root=None, **kw):
            attempted.append(layer_id)
            if layer_id == "flutter_unit":
                return run("flutter_unit", INFRA, 1, NATIVE_ASSETS)
            return run(layer_id, Classification.PASS, 0)

        import agent.qa.runner as runner_module
        original = runner_module.run_layer
        runner_module.run_layer = fake_run_layer
        try:
            decision = RoutingDecision(
                (LayerSelection("flutter_analyze", "t"),
                 LayerSelection("flutter_unit", "t"),
                 LayerSelection("playwright_e2e", "t")), (), ("dart",), "test")
            runs = run_layers(decision, "/ws")
        finally:
            runner_module.run_layer = original

        self.assertEqual(attempted,
                         ["flutter_analyze", "flutter_unit", "playwright_e2e"])
        self.assertEqual(gate_outcome(runs), GATE_DEGRADED)


if __name__ == "__main__":
    unittest.main()
