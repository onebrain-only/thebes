"""The QA failure contract, and its fold into the canonical evidence model.

FOUR THINGS A RED RUN CAN MEAN — deliberately not one
    PRODUCT_DEFECT               the tests ran and an assertion about the
                                 Product failed. Routes to the Product capability.
    TEST_DEFECT                  the tests ran and the TEST is wrong: a synthetic
                                 failure, a broken selector in test support, a
                                 quarantined spec. Routes to whoever owns the test.
    TEST_INFRASTRUCTURE_FAILURE  the harness never reached the tests: toolchain,
                                 device, missing tool, timeout, build of native
                                 assets. NOT a Product failure; consumes no review
                                 cycle.
    EXTERNAL_QA_FAILURE          an external service (TestSprite, BrowserStack)
                                 failed to run or answer. Deferred, not Product.

A broken or flaky test must not masquerade as a Product defect, and the reverse
is just as costly: a genuine Product failure hidden under "infrastructure" would
ship. So classification is by explicit signature tables that a test can pin,
with a conservative default: a nonzero exit with NO evidence any test executed
is an infrastructure failure, and a nonzero exit WITH such evidence is a Product
defect unless a test-defect signature says otherwise.

ARTIFACT POLICY. Full stdout/stderr lives on disk under an artifact reference.
What crosses into long-lived context is the tail (bounded) and the reference —
never a screenshot, never a trace, never the whole log.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from agent.execution.provider import EvidenceClaim, TestClaim, TestStatus


class Classification(str, Enum):
    PASS = "pass"
    PRODUCT_DEFECT = "product_defect"
    TEST_DEFECT = "test_defect"
    TEST_INFRASTRUCTURE_FAILURE = "test_infrastructure_failure"
    EXTERNAL_QA_FAILURE = "external_qa_failure"
    NOT_RUN = "not_run"


DETERMINISTIC_EVIDENCE_KIND = "deterministic-test"
TAIL_LINES = 40                 # what the runner keeps
VALIDATOR_TAIL_LINES = 20       # what a reviewer is shown per layer

# The harness never reached the tests. Every entry here was either observed on
# this machine or is the documented failure text of the tool named.
INFRASTRUCTURE_SIGNATURES = (
    "Building native assets failed",
    "You have not agreed to the Xcode license",
    "linker command failed",
    "No devices found",
    "No connected devices",
    "No emulators",
    "Unable to connect to device",
    "device offline",
    "command not found",
    "ENOENT",
    "Cannot find module",
    "npm ERR! missing script",
    "chromedriver is not on PATH",
    "browserType.launch",
    "Executable doesn't exist",
    "Timed out waiting",
    "Error: Timed out",
    "Could not find a file named \"pubspec.yaml\"",
    "Error: missing required env var",
    "ECONNREFUSED",
    "getaddrinfo ENOTFOUND",
    "Killed",
)

# The tests ran and the TEST is the defect. Deliberately narrow.
TEST_DEFECT_SIGNATURES = (
    ".synthetic.spec",
    "tests/e2e/support/",
    "strict mode violation",
    "quarantined",
    "known-issue",
)

# Evidence that tests actually executed. Needed to tell "assertion failed" from
# "never started".
TESTS_RAN_SIGNATURES = (
    "Some tests failed",
    "All tests passed",
    "tests passed",
    "passed (",
    " failed",
    "✘",
    "✓",
    "Error: expect(",
    "assertVisible",
    "Flow Failed",
    "Flow Passed",
    "Ran ",
    "iterations",
    "checks",
    "requests",
    "executed",
)

TIMEOUT_EXIT = 124


def classify(layer, exit_code, tail):
    """One classification per run. Signature tables, then the conservative default."""
    text = "\n".join(tail or ())
    if exit_code == 0:
        return Classification.PASS
    if layer.external:
        return Classification.EXTERNAL_QA_FAILURE
    if exit_code == TIMEOUT_EXIT:
        return Classification.TEST_INFRASTRUCTURE_FAILURE
    if any(sig in text for sig in INFRASTRUCTURE_SIGNATURES):
        return Classification.TEST_INFRASTRUCTURE_FAILURE
    if any(sig in text for sig in TEST_DEFECT_SIGNATURES):
        return Classification.TEST_DEFECT
    if any(sig in text for sig in TESTS_RAN_SIGNATURES):
        return Classification.PRODUCT_DEFECT
    return Classification.TEST_INFRASTRUCTURE_FAILURE


@dataclass(frozen=True)
class LayerRun:
    layer_id: str
    command: str
    exit_code: Optional[int]
    classification: Classification
    duration_seconds: float
    artifact_ref: Optional[str]
    tail: Tuple[str, ...] = ()
    reason: Optional[str] = None            # why NOT_RUN / infra, when known
    started_at: Optional[str] = None

    def as_payload(self):
        return {
            "layer_id": self.layer_id, "command": self.command,
            "exit_code": self.exit_code, "classification": self.classification.value,
            "duration_seconds": round(self.duration_seconds, 3),
            "artifact_ref": self.artifact_ref, "reason": self.reason,
            "started_at": self.started_at,
            "tail": list(self.tail[-VALIDATOR_TAIL_LINES:]),
        }


@dataclass(frozen=True)
class QADefect:
    """The durable failure record. Every field the brief names, nothing raw."""
    work_item_id: str
    test: str
    environment: str
    expected: str
    actual: str
    reproduction: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    severity: str
    likely_domain: str
    classification: Classification
    deterministic_regression_exists: bool
    recommended_owner: str
    artifact_refs: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_run(cls, run, work_item_id, environment, required_capability):
        layer_domain = {
            "flutter_analyze": "frontend", "flutter_unit": "frontend",
            "playwright_e2e": "frontend", "maestro_smoke": "frontend",
            "api_postman": "backend", "k6_perf": "backend",
        }
        if run.classification in (Classification.TEST_DEFECT,):
            owner = required_capability or layer_domain.get(run.layer_id, "unknown")
            domain = "tests"
        elif run.classification is Classification.TEST_INFRASTRUCTURE_FAILURE:
            owner, domain = "devops", "test-infrastructure"
        elif run.classification is Classification.EXTERNAL_QA_FAILURE:
            owner, domain = "devops", "external-qa"
        else:
            domain = layer_domain.get(run.layer_id, required_capability or "unknown")
            owner = required_capability or domain
        return cls(
            work_item_id=work_item_id, test=run.command, environment=environment,
            expected="exit 0 from %s" % run.layer_id,
            actual="exit %s (%s)" % (run.exit_code, run.classification.value),
            reproduction=(("cd <workspace>", run.command)),
            evidence_refs=tuple(x for x in (run.artifact_ref,) if x),
            severity=("HIGH" if run.classification is Classification.PRODUCT_DEFECT
                      else "MEDIUM"),
            likely_domain=domain, classification=run.classification,
            deterministic_regression_exists=run.classification in (
                Classification.PRODUCT_DEFECT, Classification.TEST_DEFECT),
            recommended_owner=owner,
            artifact_refs=tuple(x for x in (run.artifact_ref,) if x),
        )

    def as_payload(self):
        d = dict(self.__dict__)
        d["classification"] = self.classification.value
        d["reproduction"] = list(self.reproduction)
        d["evidence_refs"] = list(self.evidence_refs)
        d["artifact_refs"] = list(self.artifact_refs)
        return d


# ------------------------------------------------------------ the fold

def to_test_claims(runs):
    """Deterministic runs as the canonical `TestClaim` the evidence model already has."""
    out = []
    for run in runs:
        if run.classification is Classification.PASS:
            status = TestStatus.PASSED
        elif run.classification in (Classification.PRODUCT_DEFECT,
                                    Classification.TEST_DEFECT):
            status = TestStatus.FAILED
        else:
            status = TestStatus.NOT_RUN
        out.append(TestClaim(run.command, status, run.artifact_ref, run.exit_code))
    return tuple(out)


def to_evidence_claims(runs):
    return tuple(
        EvidenceClaim(DETERMINISTIC_EVIDENCE_KIND,
                      run.artifact_ref or run.command,
                      "%s %s exit=%s" % (run.layer_id, run.classification.value,
                                         run.exit_code))
        for run in runs)


GATE_PASS, GATE_PRODUCT, GATE_TEST, GATE_INFRA, GATE_EXTERNAL, GATE_NOT_RUN = (
    "pass", "product-defect", "test-defect", "infrastructure-failure",
    "external-failure", "not-run")


def gate_outcome(runs):
    """One word for the whole gate. Infrastructure outranks everything: a run that
    could not execute says nothing about the Product either way."""
    kinds = {run.classification for run in runs}
    if not runs or kinds <= {Classification.NOT_RUN}:
        return GATE_NOT_RUN
    if Classification.TEST_INFRASTRUCTURE_FAILURE in kinds:
        return GATE_INFRA
    if Classification.EXTERNAL_QA_FAILURE in kinds:
        return GATE_EXTERNAL
    if Classification.PRODUCT_DEFECT in kinds:
        return GATE_PRODUCT
    if Classification.TEST_DEFECT in kinds:
        return GATE_TEST
    return GATE_PASS


def render_for_validator(runs, decision=None):
    """Bounded text for a reviewer: status, reference, short tail. No raw logs."""
    lines = []
    if decision is not None:
        lines.append("Routing basis: %s" % decision.basis)
        if decision.skipped:
            lines.append("Not selected: " + "; ".join(
                "%s (%s)" % (lid, why) for lid, why in decision.skipped
                if not why.startswith("no applicable")))
    if not runs:
        lines.append("- no deterministic layer applied to this change")
        return "\n".join(lines)
    for run in runs:
        lines.append("- %s -> %s (exit %s, %.1fs)%s" % (
            run.layer_id, run.classification.value, run.exit_code,
            run.duration_seconds,
            (" artifact: %s" % run.artifact_ref) if run.artifact_ref else ""))
        if run.reason:
            lines.append("  reason: %s" % run.reason)
        for row in run.tail[-VALIDATOR_TAIL_LINES:]:
            if row.strip():
                lines.append("    %s" % row.rstrip()[:200])
    return "\n".join(lines)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
