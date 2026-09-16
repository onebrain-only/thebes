#!/usr/bin/env python3
"""THE RUNNER AND THE GATE — commands in, structured evidence out, no model.

Defended here:
  - external layers are NEVER invoked by the runner, however they were selected;
  - a workspace without the layer's marker is NOT_RUN, not a failure;
  - a missing tool is an infrastructure failure, named;
  - full output goes to disk, a bounded tail comes back, and the artifact is
    referenced by path;
  - the runner stops at the first infrastructure failure;
  - the gate never raises, never writes state, and derives reviewer effort from
    decisive evidence only.

The subprocess is a double. No real flutter, npm, maestro or network.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution.provider import ModelIntent, ReasoningEffort   # noqa: E402
from agent.qa.gate import (                                          # noqa: E402
    GATE_INFRA, GATE_NOT_RUN, GATE_PASS, GATE_PRODUCT, DeterministicGate,
    no_gate, run_deterministic_gate,
)
from agent.qa.results import Classification, TAIL_LINES              # noqa: E402
from agent.qa.routing import ChangeProfile, LayerSelection, RoutingDecision, select_layers  # noqa: E402
from agent.qa.runner import run_layer, run_layers                    # noqa: E402


class Completed:
    def __init__(self, code, out):
        self.returncode, self.stdout = code, out.encode("utf-8")


def fake_run_factory(script):
    """script: argv[0] -> (exit_code, output) or an exception instance."""
    calls = []

    def run(argv, cwd, env, stdout, stderr, timeout, check):
        calls.append((tuple(argv), cwd, timeout, env.get("DEVELOPER_DIR")))
        outcome = script.get(argv[0], (0, "ok"))
        if isinstance(outcome, Exception):
            raise outcome
        return Completed(*outcome)
    run.calls = calls
    return run


def markers(path, *names):
    for name in names:
        full = os.path.join(path, name)
        os.makedirs(os.path.dirname(full) or path, exist_ok=True)
        with open(full, "w") as handle:
            handle.write("x")


class RunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        self.art = os.path.join(self.ws, "artifacts")
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)


class ExternalAndMissing(RunnerTestCase):
    def test_external_layer_is_never_invoked(self):
        run = fake_run_factory({})
        r = run_layer("testsprite_exploratory", self.ws, self.art, run=run,
                      which=lambda t: "/bin/x", environ={})
        self.assertIs(r.classification, Classification.NOT_RUN)
        self.assertEqual(r.reason, "external-not-invoked")
        self.assertEqual(run.calls, [])

    def test_missing_marker_is_not_run_not_a_failure(self):
        run = fake_run_factory({})
        r = run_layer("flutter_unit", self.ws, self.art, run=run,
                      which=lambda t: "/bin/x", environ={})
        self.assertIs(r.classification, Classification.NOT_RUN)
        self.assertIn("pubspec.yaml", r.reason)
        self.assertEqual(run.calls, [])

    def test_missing_tool_is_a_named_infrastructure_failure(self):
        markers(self.ws, "pubspec.yaml")
        run = fake_run_factory({})
        r = run_layer("flutter_unit", self.ws, self.art, run=run,
                      which=lambda t: None, environ={})
        self.assertIs(r.classification, Classification.TEST_INFRASTRUCTURE_FAILURE)
        self.assertIn("flutter", r.reason)
        self.assertEqual(run.calls, [])


class Execution(RunnerTestCase):
    def test_pass_writes_artifact_and_bounded_tail(self):
        markers(self.ws, "pubspec.yaml")
        long = "\n".join("line %d" % i for i in range(300)) + "\nAll tests passed!"
        run = fake_run_factory({"flutter": (0, long)})
        r = run_layer("flutter_unit", self.ws, self.art, run=run,
                      which=lambda t: "/bin/x", environ={"DEVELOPER_DIR": "/dev/x"})
        self.assertIs(r.classification, Classification.PASS)
        self.assertLessEqual(len(r.tail), TAIL_LINES)
        self.assertTrue(os.path.exists(r.artifact_ref))
        with open(r.artifact_ref) as handle:
            body = handle.read()
        self.assertIn("line 0", body)                 # full output on disk
        self.assertIn("exit=0", body)
        self.assertEqual(run.calls[0][1], self.ws)     # ran in the workspace
        self.assertEqual(run.calls[0][3], "/dev/x")    # pinned toolchain passed through

    def test_observed_toolchain_failure_classifies_as_infrastructure(self):
        markers(self.ws, "pubspec.yaml")
        run = fake_run_factory({"flutter": (1, "clang: error: linker command failed\n"
                                              "Building native assets failed.")})
        r = run_layer("flutter_unit", self.ws, self.art, run=run,
                      which=lambda t: "/bin/x", environ={})
        self.assertIs(r.classification, Classification.TEST_INFRASTRUCTURE_FAILURE)

    def test_timeout_is_infrastructure_with_partial_output_kept(self):
        markers(self.ws, "playwright.config.ts")
        run = fake_run_factory({"npm": subprocess.TimeoutExpired(["npm"], 1, output=b"partial")})
        r = run_layer("playwright_e2e", self.ws, self.art, run=run,
                      which=lambda t: "/bin/x", environ={})
        self.assertEqual(r.exit_code, 124)
        self.assertIs(r.classification, Classification.TEST_INFRASTRUCTURE_FAILURE)
        self.assertIn("TIMEOUT", "\n".join(r.tail))

    def test_runner_continues_past_an_infrastructure_failure(self):
        # AMENDED 2026-09-16. This asserted the runner STOPPED at the first
        # infrastructure failure, on the reasoning that later layers could add
        # nothing a broken toolchain had not already said. That assumed the
        # failure was toolchain-WIDE. `flutter test` alone is broken on this
        # machine, and stopping meant KAN-212 and KAN-208 never reached
        # `flutter analyze` — the one gate that sees the barrel export lines
        # they change. The runner now runs every selected layer; `gate_outcome`
        # reports the hole instead of the runner hiding it.
        markers(self.ws, "pubspec.yaml", "playwright.config.ts")
        decision = RoutingDecision(
            (LayerSelection("flutter_analyze", "t"), LayerSelection("flutter_unit", "t"),
             LayerSelection("playwright_e2e", "t")), (), ("dart",), "test")
        run = fake_run_factory({"flutter": (69, "You have not agreed to the Xcode license"),
                                "npm": (0, "Running 3 tests\n3 passed")})
        runs = run_layers(decision, self.ws, self.art, run=run,
                          which=lambda t: "/bin/x", environ={})
        self.assertEqual([r.layer_id for r in runs],
                         ["flutter_analyze", "flutter_unit", "playwright_e2e"])
        self.assertEqual(len(run.calls), 3)
        # The broken layer is still classified honestly, not swallowed.
        self.assertIs(runs[0].classification,
                      Classification.TEST_INFRASTRUCTURE_FAILURE)
        self.assertIs(runs[2].classification, Classification.PASS)

    def test_never_raises_on_os_error(self):
        markers(self.ws, "pubspec.yaml")
        run = fake_run_factory({"flutter": OSError("boom")})
        r = run_layer("flutter_unit", self.ws, self.art, run=run,
                      which=lambda t: "/bin/x", environ={})
        self.assertEqual(r.exit_code, 127)
        self.assertIs(r.classification, Classification.TEST_INFRASTRUCTURE_FAILURE)


class Gate(RunnerTestCase):
    def task(self, surfaces=("lib/a.dart",), chars=None):
        return {"execution_profile": {"required_capability": "frontend",
                                      "characteristics": chars or {}},
                "surfaces": list(surfaces),
                "operational_context": {"primary_target": {"runtime": "flutter_web",
                                                           "platform": "chrome"}}}

    def test_fixture_workspace_without_markers_is_not_run_and_full_effort(self):
        g = run_deterministic_gate("KAN-1", self.task(), {"path": self.ws},
                                   artifact_root=self.art)
        self.assertEqual(g.outcome, GATE_NOT_RUN)
        self.assertFalse(g.decisive)
        self.assertEqual(g.reviewer_effort(), (ModelIntent.BALANCED, ReasoningEffort.HIGH))
        self.assertIn("no deterministic layer applied", g.render()) if not g.runs else None

    def test_docs_only_selects_nothing_and_runs_nothing(self):
        called = []
        g = run_deterministic_gate("KAN-1", self.task(("docs/x.md",)), {"path": self.ws},
                                   runner=lambda *a, **k: called.append(a) or ())
        self.assertEqual(called, [])
        self.assertEqual(g.outcome, GATE_NOT_RUN)

    def test_decisive_pass_lowers_reviewer_effort(self):
        def runner(decision, ws, art):
            from agent.qa.results import LayerRun
            return tuple(LayerRun(s.layer_id, "cmd", 0, Classification.PASS, 1.0, "a.log")
                         for s in decision.selected)
        g = run_deterministic_gate("KAN-1", self.task(), {"path": self.ws}, runner=runner)
        self.assertEqual(g.outcome, GATE_PASS)
        self.assertTrue(g.decisive)
        self.assertEqual(g.reviewer_effort(), (ModelIntent.COST_EFFICIENT, ReasoningEffort.LOW))

    def test_product_defect_is_decisive_infrastructure_is_not(self):
        from agent.qa.results import LayerRun
        prod = DeterministicGate(select_layers(ChangeProfile("frontend", ("lib/a.dart",))),
                                 (LayerRun("flutter_unit", "c", 1, Classification.PRODUCT_DEFECT,
                                           1.0, "a"),), GATE_PRODUCT, self.ws)
        infra = DeterministicGate(prod.decision,
                                  (LayerRun("flutter_unit", "c", 1,
                                            Classification.TEST_INFRASTRUCTURE_FAILURE, 1.0, "a"),),
                                  GATE_INFRA, self.ws)
        self.assertTrue(prod.decisive)
        self.assertFalse(infra.decisive)
        self.assertEqual(infra.reviewer_effort(), (ModelIntent.BALANCED, ReasoningEffort.HIGH))

    def test_payload_is_json_shaped_and_bounded(self):
        import json
        g = no_gate("KAN-1", self.task(), {"path": self.ws})
        payload = g.as_payload()
        json.dumps(payload)
        self.assertEqual(payload["outcome"], GATE_NOT_RUN)
        self.assertIn("routing", payload)


if __name__ == "__main__":
    unittest.main()
