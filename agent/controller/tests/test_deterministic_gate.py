#!/usr/bin/env python3
"""THE DETERMINISTIC GATE INSIDE THE VALIDATION ROUTE.

The REAL `agent/state/store.py` runs here (temp runtime), the real
`run_validation`, a synthetic git repository, a Jira double and provider doubles
— the established pattern from test_validation_dispatch. The gate is injected.

WHAT THIS SUITE DEFENDS
  - an infrastructure failure REFUSES the act: no dispatch, no verdict, the
    review stays pending at the same cycle with its owner — it is not a Product
    failure and it spends nothing;
  - decisive deterministic evidence (pass / product-defect) reaches the
    reviewer as bounded text and lowers the dispatch to cost-efficient / low
    effort; the reviewer still writes the verdict;
  - no applicable layer (the fixture workspace) leaves today's behaviour intact:
    full effort, the old "re-run the tests" instruction, identical flow;
  - the gate's payload lands in the validation evidence for the receipt.
"""

import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                       # noqa: E402

from agent.controller.validation import (                          # noqa: E402
    FAIL, PASS, VALIDATION_FAILED, VALIDATION_INFRASTRUCTURE_FAILED,
    VALIDATION_PASSED, ValidationRefused, run_validation,
)
from agent.controller.tests.test_validation_dispatch import (      # noqa: E402
    Jira, SEATS, ValidationTestCase, Validator, make_task,
)
from agent.execution.provider import ModelIntent, ReasoningEffort  # noqa: E402
from agent.qa.gate import DeterministicGate                         # noqa: E402
from agent.qa.results import (                                      # noqa: E402
    Classification, GATE_INFRA, GATE_NOT_RUN, GATE_PASS, GATE_PRODUCT, LayerRun,
)
from agent.qa.routing import ChangeProfile, select_layers           # noqa: E402


def gate_double(outcome, runs):
    """A gate function that returns a fixed DeterministicGate."""
    calls = []

    def gate(work_item_id, task, realized, execution=None, **_):
        calls.append((work_item_id, realized["path"]))
        decision = select_layers(ChangeProfile.from_task(task))
        return DeterministicGate(decision, tuple(runs), outcome, realized["path"])
    gate.calls = calls
    return gate


def run_(layer_id, classification, code):
    return LayerRun(layer_id, "npm run test:e2e", code, classification, 3.2,
                    "/tmp/artifacts/%s.log" % layer_id,
                    tail=("Running 3 tests", "1 failed" if code else "3 passed"))


class GateInsideValidation(ValidationTestCase):
    def self_task(self):
        # {} characteristics -> SELF; enter_review releases ownership and creates
        # the executor evidence the SELF owner is derived from.
        return make_task(characteristics={})

    def run_with_gate(self, task, validator, gate):
        work_item_id = task["work_item_id"]
        return run_validation(work_item_id, task, self.execution_result(),
                              self.realize(work_item_id=work_item_id), store, Jira(),
                              (validator,), seats_by_capability=SEATS,
                              receipt_ref="execution receipt for %s" % work_item_id,
                              deterministic=gate)

    # ---------------------------------------------------- infrastructure

    def test_infrastructure_failure_refuses_without_dispatch_or_verdict(self):
        task = self.self_task()
        validator = Validator(PASS)
        gate = gate_double(GATE_INFRA, [run_("playwright_e2e",
                                             Classification.TEST_INFRASTRUCTURE_FAILURE, 124)])
        with self.assertRaises(ValidationRefused) as ctx:
            self.run_with_gate(task, validator, gate)
        self.assertEqual(ctx.exception.outcome, VALIDATION_INFRASTRUCTURE_FAILED)
        self.assertIn("not a Product failure", str(ctx.exception))
        self.assertEqual(validator.requests, [])                 # never dispatched
        after = store.read("task", task["work_item_id"])
        review = after["review_context"]
        self.assertEqual(review["review_result"], "pending")     # no verdict
        self.assertEqual(review["review_cycle"], 1)              # nothing spent
        self.assertEqual(review["review_owner"], "backend-1")    # owner kept
        self.assertEqual(gate.calls[0][0], task["work_item_id"])

    def test_after_repair_the_same_review_resumes_and_passes(self):
        task = self.self_task()
        infra = gate_double(GATE_INFRA, [run_("flutter_unit",
                                             Classification.TEST_INFRASTRUCTURE_FAILURE, 1)])
        with self.assertRaises(ValidationRefused):
            self.run_with_gate(task, Validator(PASS), infra)
        task = store.read("task", task["work_item_id"])
        ok = gate_double(GATE_PASS, [run_("flutter_unit", Classification.PASS, 0)])
        evidence = self.run_with_gate(task, Validator(PASS), ok)
        self.assertEqual(evidence["outcome"], VALIDATION_PASSED)
        self.assertEqual(evidence["review_cycle"], 1)            # same cycle, resumed

    # ---------------------------------------------------- decisive evidence

    def test_product_defect_evidence_reaches_reviewer_at_low_effort(self):
        task = self.self_task()
        validator = Validator(FAIL)
        gate = gate_double(GATE_PRODUCT, [run_("playwright_e2e",
                                               Classification.PRODUCT_DEFECT, 1)])
        evidence = self.run_with_gate(task, validator, gate)
        self.assertEqual(evidence["outcome"], VALIDATION_FAILED)
        request = validator.requests[0]
        self.assertIs(request.reasoning_effort, ReasoningEffort.LOW)
        self.assertIs(request.model_intent, ModelIntent.COST_EFFICIENT)
        self.assertIn("Deterministic test evidence", request.objective)
        self.assertIn("product_defect", request.objective)
        self.assertIn("/tmp/artifacts/playwright_e2e.log", request.objective)
        self.assertIn("Do NOT re-run them", request.objective)
        self.assertNotIn("Re-run the Product tests that cover this change",
                         request.objective)
        self.assertEqual(evidence["deterministic_gate"]["outcome"], GATE_PRODUCT)

    def test_pass_evidence_lowers_effort_but_reviewer_still_writes_the_verdict(self):
        task = self.self_task()
        validator = Validator(PASS)
        gate = gate_double(GATE_PASS, [run_("flutter_analyze", Classification.PASS, 0),
                                      run_("flutter_unit", Classification.PASS, 0)])
        evidence = self.run_with_gate(task, validator, gate)
        self.assertEqual(evidence["outcome"], VALIDATION_PASSED)
        self.assertIs(validator.requests[0].reasoning_effort, ReasoningEffort.LOW)
        after = store.read("task", task["work_item_id"])
        self.assertEqual(after["review_context"]["review_result"], "pass")
        self.assertEqual(after["review_context"]["review_owner"], "backend-1")

    def test_a_reviewer_may_still_fail_a_green_gate(self):
        # The gate is evidence, not the verdict: a reviewer who finds an
        # unmet acceptance criterion fails the review regardless.
        task = self.self_task()
        gate = gate_double(GATE_PASS, [run_("flutter_unit", Classification.PASS, 0)])
        evidence = self.run_with_gate(task, Validator(FAIL), gate)
        self.assertEqual(evidence["outcome"], VALIDATION_FAILED)

    # ---------------------------------------------------- nothing applied

    def test_no_applicable_layer_keeps_full_effort_and_todays_instruction(self):
        task = self.self_task()
        validator = Validator(PASS)
        gate = gate_double(GATE_NOT_RUN, [])
        evidence = self.run_with_gate(task, validator, gate)
        self.assertEqual(evidence["outcome"], VALIDATION_PASSED)
        request = validator.requests[0]
        self.assertIs(request.reasoning_effort, ReasoningEffort.HIGH)
        self.assertIs(request.model_intent, ModelIntent.BALANCED)
        self.assertIn("no deterministic layer applied", request.objective)
        self.assertIn("Re-run the Product tests that cover this change", request.objective)

    def test_default_gate_on_the_fixture_workspace_is_not_run(self):
        # No injection: the real gate routes the fixture's `alpha.dart` surfaces
        # to the cheap floor, finds no pubspec.yaml, and runs nothing.
        task = self.self_task()
        validator = Validator(PASS)
        evidence = self.run_route(task, Jira(), validator)
        self.assertEqual(evidence["outcome"], VALIDATION_PASSED)
        self.assertEqual(evidence["deterministic_gate"]["outcome"], GATE_NOT_RUN)
        self.assertEqual([r["classification"] for r in
                          evidence["deterministic_gate"]["runs"]],
                         ["not_run", "not_run"])
        self.assertIs(validator.requests[0].reasoning_effort, ReasoningEffort.HIGH)


if __name__ == "__main__":
    unittest.main()
