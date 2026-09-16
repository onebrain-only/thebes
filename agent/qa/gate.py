"""The deterministic gate — the ONE seam the validation route calls.

ORDER, AND WHY
    route -> run -> classify -> hand the reviewer structured evidence.

    The gate runs AFTER the review context is opened (so its evidence belongs to
    a named review cycle) and BEFORE the reviewer is dispatched (so the reviewer
    interprets results instead of producing them). It writes no verdict: the
    canonical writer still requires the recorded review owner, and this module
    is not one.

WHAT THE GATE DECIDES, AND WHAT IT DOES NOT
    infrastructure-failure  NOTHING was learned — every layer that ran was
                            broken. The validation act cannot proceed; the
                            caller refuses with a named outcome and NO review
                            cycle is spent.
    degraded                SOMETHING was learned, but a layer could not run.
                            Real evidence, incomplete coverage, and the hole is
                            named to the reviewer. Never decisive.
    anything else           evidence for the reviewer. A product-defect run is
                            strong evidence for FAIL; a clean run is strong
                            evidence for PASS; neither is the verdict.

    The reviewer's effort is derived from the gate: decisive deterministic
    evidence (pass / product-defect) warrants the cost-efficient dispatch —
    interpretation, not investigation. No applicable layer, or degraded
    coverage, keeps the reviewer's full effort, because then the reviewer IS
    the test.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from agent.execution.provider import ModelIntent, ReasoningEffort
from agent.qa.results import (
    GATE_DEGRADED, GATE_INFRA, GATE_NOT_RUN, GATE_PASS, GATE_PRODUCT, LayerRun,
    gate_outcome, render_for_validator, to_evidence_claims, to_test_claims,
    unavailable_layers,
)
from agent.qa.routing import ChangeProfile, RoutingDecision, select_layers
from agent.qa.runner import run_layers


@dataclass(frozen=True)
class DeterministicGate:
    decision: RoutingDecision
    runs: Tuple[LayerRun, ...]
    outcome: str
    workspace_path: Optional[str]

    @property
    def decisive(self):
        """Deterministic evidence that settles the question either way.

        GATE_DEGRADED is deliberately NOT decisive, however green the layers
        that did run. Some coverage is missing, so the reviewer keeps full
        effort and does the thinking the absent layer would have saved.
        """
        return bool(self.runs) and self.outcome in (GATE_PASS, GATE_PRODUCT)

    @property
    def unavailable(self):
        """(layer_id, reason) for every layer that could not run."""
        return unavailable_layers(self.runs)

    def reviewer_effort(self):
        """(ModelIntent, ReasoningEffort) for the dispatch this gate precedes."""
        if self.decisive:
            return ModelIntent.COST_EFFICIENT, ReasoningEffort.LOW
        return ModelIntent.BALANCED, ReasoningEffort.HIGH

    def test_claims(self):
        return to_test_claims(self.runs)

    def evidence_claims(self):
        return to_evidence_claims(self.runs)

    def render(self):
        return render_for_validator(self.runs, self.decision)

    def as_payload(self):
        return {"outcome": self.outcome, "decisive": self.decisive,
                "unavailable": [{"layer_id": lid, "reason": why}
                                for lid, why in self.unavailable],
                "workspace_path": self.workspace_path,
                "routing": self.decision.as_payload(),
                "runs": [run.as_payload() for run in self.runs]}


def run_deterministic_gate(work_item_id, task, realized, execution=None,
                           artifact_root=None, selector=select_layers,
                           runner=run_layers, **flags):
    """Route, run, classify. Pure composition of the three modules."""
    del work_item_id, execution            # named for the seam; the profile is the task
    profile = ChangeProfile.from_task(task, **flags)
    decision = selector(profile)
    workspace = (realized or {}).get("path")
    if not workspace or not decision.selected:
        return DeterministicGate(decision, (), GATE_NOT_RUN, workspace)
    runs = runner(decision, workspace, artifact_root)
    return DeterministicGate(decision, tuple(runs), gate_outcome(runs), workspace)


def no_gate(work_item_id, task, realized, execution=None, **_):
    """A gate that runs nothing — for callers that supply their own evidence."""
    profile = ChangeProfile.from_task(task)
    decision = select_layers(profile)
    return DeterministicGate(decision, (), GATE_NOT_RUN, (realized or {}).get("path"))


__all__ = ["DeterministicGate", "run_deterministic_gate", "no_gate",
           "GATE_DEGRADED", "GATE_INFRA", "GATE_PASS", "GATE_PRODUCT",
           "GATE_NOT_RUN", "unavailable_layers"]
