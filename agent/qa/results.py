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
# Some layer could not run, and some other layer did produce a result. Evidence
# exists but its coverage is INCOMPLETE, and the reviewer is told exactly which
# layer is missing. (2026-09-16 — see gate_outcome.)
GATE_DEGRADED = "degraded"

# Classifications that answer something about the Product.
_VERDICT_BEARING = (Classification.PASS, Classification.PRODUCT_DEFECT,
                    Classification.TEST_DEFECT)


def gate_outcome(runs):
    """One word for the whole gate.

    INFRASTRUCTURE STILL OUTRANKS A RESULT, BUT ONLY OVER ITS OWN LAYER.
    Until 2026-09-16 a single layer that could not run condemned the entire act:
    one `TEST_INFRASTRUCTURE_FAILURE` anywhere returned `GATE_INFRA`, the
    validation route refused, and nothing could be validated at all. Found by
    real Product work — `flutter test` is broken on this machine by a
    native-asset link fault, routing selects it for every Dart change, and
    KAN-212 and KAN-208 were both refused although `flutter analyze` and the web
    E2E layer were perfectly capable of answering.

    So the question became: did we learn ANYTHING?

      no layer ran at all            -> GATE_NOT_RUN
      every layer that ran was broken -> GATE_INFRA. Nothing was learned; the act
                                         refuses and spends no review cycle.
      some broken, some answered      -> GATE_DEGRADED. Real evidence exists and
                                         is reported WITH the hole in it named.
      nothing broken                  -> the strongest result stands, as before.

    DEGRADED IS NOT A PASS AND MUST NEVER READ AS ONE. It is never `decisive`,
    so the reviewer keeps full effort, and `render_for_validator` states which
    layer could not run and what coverage went missing with it. A layer silently
    skipped would be the worst outcome available here — worse than refusing —
    because the reviewer would weigh partial evidence as whole.
    """
    kinds = {run.classification for run in runs}
    if not runs or kinds <= {Classification.NOT_RUN}:
        return GATE_NOT_RUN
    broken = kinds & {Classification.TEST_INFRASTRUCTURE_FAILURE,
                      Classification.EXTERNAL_QA_FAILURE}
    answered = kinds & set(_VERDICT_BEARING)
    if broken and not answered:
        return (GATE_INFRA if Classification.TEST_INFRASTRUCTURE_FAILURE in broken
                else GATE_EXTERNAL)
    if broken:
        return GATE_DEGRADED
    if Classification.PRODUCT_DEFECT in kinds:
        return GATE_PRODUCT
    if Classification.TEST_DEFECT in kinds:
        return GATE_TEST
    return GATE_PASS


def unavailable_layers(runs):
    """The layers that could not run, with the reason. Never silently dropped."""
    return tuple((run.layer_id,
                  run.reason or (run.tail[-1] if run.tail else "exit %s" % run.exit_code))
                 for run in runs
                 if run.classification in (Classification.TEST_INFRASTRUCTURE_FAILURE,
                                           Classification.EXTERNAL_QA_FAILURE))


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
    # State the hole FIRST and in the reviewer's own terms. Partial evidence
    # read as complete is the failure this paragraph exists to prevent.
    missing = unavailable_layers(runs)
    if missing and gate_outcome(runs) == GATE_DEGRADED:
        lines.append("INCOMPLETE COVERAGE — %d of %d selected layer(s) could not run: %s"
                     % (len(missing), len(runs),
                        "; ".join("%s (%s)" % (lid, why[:90]) for lid, why in missing)))
        lines.append("The results below are real but do NOT cover what those layers "
                     "test. Weigh them accordingly; a pass here is narrower than a "
                     "full pass, and this is a test-infrastructure fault, not a "
                     "Product one.")
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
