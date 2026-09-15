#!/usr/bin/env python3
"""THE FAILURE CONTRACT — four things a red run can mean, kept apart.

The invariant: A BROKEN OR FLAKY TEST MUST NOT MASQUERADE AS A PRODUCT DEFECT,
and an infrastructure failure must not spend a review or route to a developer.
Every signature here was observed on this machine or is the tool's documented
text; the conservative default is pinned so it cannot drift.

Stdlib only.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution.provider import TestStatus                       # noqa: E402
from agent.qa.layers import LAYERS                                     # noqa: E402
from agent.qa.results import (                                         # noqa: E402
    Classification, GATE_EXTERNAL, GATE_INFRA, GATE_NOT_RUN, GATE_PASS,
    GATE_PRODUCT, GATE_TEST, LayerRun, QADefect, TIMEOUT_EXIT, classify,
    gate_outcome, render_for_validator, to_evidence_claims, to_test_claims,
)

UNIT = LAYERS["flutter_unit"]
E2E = LAYERS["playwright_e2e"]
EXT = LAYERS["testsprite_exploratory"]


def run(layer_id, classification, exit_code=1, tail=(), artifact="art.log"):
    return LayerRun(layer_id, "cmd", exit_code, classification, 1.0, artifact,
                    tuple(tail))


class Classify(unittest.TestCase):
    def test_exit_zero_is_pass_whatever_the_output_says(self):
        self.assertIs(classify(UNIT, 0, ["Some tests failed"]), Classification.PASS)

    def test_observed_toolchain_failure_is_infrastructure(self):
        # Reproduced 2026-09-15: flutter test on this machine.
        tail = ["clang: error: linker command failed with exit code 1",
                "Building native assets failed. See the logs for more details."]
        self.assertIs(classify(UNIT, 1, tail),
                      Classification.TEST_INFRASTRUCTURE_FAILURE)

    def test_xcode_licence_is_infrastructure(self):
        self.assertIs(classify(UNIT, 69, ["You have not agreed to the Xcode license"]),
                      Classification.TEST_INFRASTRUCTURE_FAILURE)

    def test_timeout_exit_is_infrastructure(self):
        self.assertIs(classify(E2E, TIMEOUT_EXIT, ["✘ 1 something"]),
                      Classification.TEST_INFRASTRUCTURE_FAILURE)

    def test_assertion_failure_is_product_defect(self):
        self.assertIs(classify(E2E, 1, ["Error: expect(page).toHaveURL(expected) failed",
                                        "  1 failed"]),
                      Classification.PRODUCT_DEFECT)
        self.assertIs(classify(UNIT, 1, ["00:03 +2 -1: Some tests failed."]),
                      Classification.PRODUCT_DEFECT)

    def test_failure_inside_test_support_is_a_test_defect(self):
        tail = ["Error at tests/e2e/support/semantics.ts:12", "  1 failed"]
        self.assertIs(classify(E2E, 1, tail), Classification.TEST_DEFECT)

    def test_synthetic_failure_is_a_test_defect_not_a_product_one(self):
        tail = ["✘ synthetic-failure.synthetic.spec.ts › asserts a nonexistent element"]
        self.assertIs(classify(E2E, 1, tail), Classification.TEST_DEFECT)

    def test_nonzero_with_no_evidence_tests_ran_is_infrastructure(self):
        # The conservative default: the harness never reached the tests.
        self.assertIs(classify(UNIT, 1, [""]), Classification.TEST_INFRASTRUCTURE_FAILURE)
        self.assertIs(classify(UNIT, 2, ["usage: something"]),
                      Classification.TEST_INFRASTRUCTURE_FAILURE)

    def test_external_layer_nonzero_is_external_failure(self):
        self.assertIs(classify(EXT, 1, ["anything"]), Classification.EXTERNAL_QA_FAILURE)


class GateOutcome(unittest.TestCase):
    def test_empty_or_all_not_run_is_not_run(self):
        self.assertEqual(gate_outcome(()), GATE_NOT_RUN)
        self.assertEqual(gate_outcome((run("flutter_unit", Classification.NOT_RUN, None),)),
                         GATE_NOT_RUN)

    def test_infrastructure_outranks_everything(self):
        runs = (run("flutter_analyze", Classification.PASS, 0),
                run("flutter_unit", Classification.PRODUCT_DEFECT),
                run("playwright_e2e", Classification.TEST_INFRASTRUCTURE_FAILURE))
        self.assertEqual(gate_outcome(runs), GATE_INFRA)

    def test_product_defect_outranks_test_defect(self):
        runs = (run("a", Classification.TEST_DEFECT), run("b", Classification.PRODUCT_DEFECT))
        self.assertEqual(gate_outcome(runs), GATE_PRODUCT)
        self.assertEqual(gate_outcome((run("a", Classification.TEST_DEFECT),)), GATE_TEST)

    def test_external_failure_named(self):
        self.assertEqual(gate_outcome((run("x", Classification.EXTERNAL_QA_FAILURE),)),
                         GATE_EXTERNAL)

    def test_all_pass_is_pass(self):
        self.assertEqual(gate_outcome((run("a", Classification.PASS, 0),
                                       run("b", Classification.NOT_RUN, None))), GATE_PASS)


class FoldIntoCanonicalEvidence(unittest.TestCase):
    def test_test_claims_map_classification_to_status(self):
        claims = to_test_claims((run("a", Classification.PASS, 0),
                                 run("b", Classification.PRODUCT_DEFECT),
                                 run("c", Classification.TEST_DEFECT),
                                 run("d", Classification.TEST_INFRASTRUCTURE_FAILURE),
                                 run("e", Classification.NOT_RUN, None)))
        self.assertEqual([c.status for c in claims],
                         [TestStatus.PASSED, TestStatus.FAILED, TestStatus.FAILED,
                          TestStatus.NOT_RUN, TestStatus.NOT_RUN])
        self.assertEqual(claims[0].evidence_ref, "art.log")

    def test_evidence_claims_carry_reference_not_logs(self):
        claim = to_evidence_claims((run("flutter_unit", Classification.PRODUCT_DEFECT,
                                        tail=["x"] * 500),))[0]
        self.assertEqual(claim.kind, "deterministic-test")
        self.assertEqual(claim.reference, "art.log")
        self.assertLess(len(claim.summary), 120)

    def test_render_is_bounded(self):
        r = run("flutter_unit", Classification.PRODUCT_DEFECT, tail=["line %d" % i
                                                                    for i in range(400)])
        text = render_for_validator((r,))
        self.assertLessEqual(text.count("\n"), 25)
        self.assertIn("art.log", text)
        self.assertIn("product_defect", text)

    def test_render_says_so_when_nothing_applied(self):
        self.assertIn("no deterministic layer applied", render_for_validator(()))


class DefectRecord(unittest.TestCase):
    def test_product_defect_routes_to_the_product_capability(self):
        d = QADefect.from_run(run("playwright_e2e", Classification.PRODUCT_DEFECT),
                              "KAN-1", "local chrome", "frontend")
        self.assertEqual(d.recommended_owner, "frontend")
        self.assertEqual(d.severity, "HIGH")
        self.assertTrue(d.deterministic_regression_exists)
        self.assertEqual(d.classification, Classification.PRODUCT_DEFECT)

    def test_infrastructure_failure_routes_to_devops_not_a_developer(self):
        d = QADefect.from_run(run("flutter_unit", Classification.TEST_INFRASTRUCTURE_FAILURE),
                              "KAN-1", "local", "frontend")
        self.assertEqual(d.recommended_owner, "devops")
        self.assertEqual(d.likely_domain, "test-infrastructure")

    def test_payload_carries_every_contract_field(self):
        d = QADefect.from_run(run("api_postman", Classification.PRODUCT_DEFECT),
                              "KAN-2", "supabase rest", "backend").as_payload()
        for key in ("test", "environment", "work_item_id", "expected", "actual",
                    "reproduction", "evidence_refs", "severity", "likely_domain",
                    "classification", "deterministic_regression_exists",
                    "recommended_owner", "artifact_refs"):
            self.assertIn(key, d, key)


if __name__ == "__main__":
    unittest.main()
