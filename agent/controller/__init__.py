"""Temporary Phase-2 controller entry point.

This module is intentionally composition glue, not a Listener.  A controller
supplies one bounded execution brief; Thebes supplies the authorization gate,
runtime checks, claim, immutable request, provider selection, receipt, and
lease lifecycle through the existing modules.
"""

import json
import os
import uuid

from agent.execution.codex import CodexCliTransport, CodexProvider
from agent.execution.claude import ClaudeCliTransport, ClaudeProvider
from agent.execution.provider import (
    ExecutionFeature, ExecutionKind, ExecutionRequest, ExecutionTarget,
    ModelIntent, MutationMode, ReasoningEffort, ReportedEnvironment,
    ReturnContract, ValidationTarget, Workspace,
)
from agent.execution.wake import execute_product_wake
from agent.integrations import jira
from agent.state import roster, store
from agent.controller.allocation import SeatAllocationError, select_claim_seat


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROADMAP = os.path.join(ROOT, "agent", "ROADMAP.md")


class ControllerInputError(ValueError):
    pass


class RoadmapAuthorization:
    """Read the existing canonical Product-authorization record.

    Authorization remains a governance fact: this adapter does not create,
    change, or infer it.  The acceptance protocol records the selected ticket
    and reference in ROADMAP.md, so both must be present before the runtime
    path is touched.
    """

    def __init__(self, path=ROADMAP):
        self.path = path

    def for_work_item(self, work_item_id):
        try:
            with open(self.path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return {"authorized": False, "reason": "authorization-record-unavailable: %s" % exc,
                    "reference": None}
        enabled = "PRODUCT_EXECUTION_AUTHORIZED: YES" in text
        selected = _last_value(text, "Selected ticket:")
        reference = _last_value(text, "Authorization reference:")
        if not enabled:
            return {"authorized": False, "reason": "product-execution-not-authorized",
                    "reference": None}
        if _none_value(reference):
            return {"authorized": False, "reason": "authorization-reference-missing",
                    "reference": None}
        if selected != work_item_id:
            return {"authorized": False, "reason": "work-item-not-authorized",
                    "reference": reference}
        return {"authorized": True, "reason": "authorized", "reference": reference}


def _last_value(text, prefix):
    values = []
    for line in text.splitlines():
        if line.startswith(prefix):
            values.append(line[len(prefix):].strip().strip("*"))
    return values[-1] if values else None


def _none_value(value):
    if not value:
        return True
    clean = value.replace("*", "").strip().lower()
    return clean == "none" or clean.startswith("none ") or clean.startswith("none(")


def load_brief(path):
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ControllerInputError("cannot read controller brief: %s" % exc)
    if not isinstance(payload, dict):
        raise ControllerInputError("controller brief must be a JSON object")
    return payload


def available_provider_registry():
    """Compose only transports that this Codex environment can actually launch.

    Claude's supported local CLI is invoked through the existing ClaudeProvider
    seam.  Native permission prompts are denied and returned as needs-input
    evidence rather than approved by this controller.
    """
    return (ClaudeProvider(ClaudeCliTransport()), CodexProvider(CodexCliTransport()))


def execute(work_item_id, brief, *, authorization=None, state_store=store,
            jira_client=jira, seat_registry=roster, providers=None):
    """Submit exactly one already-selected work item through the existing wake.

    This interface never accepts mode, authorization, capability, lifecycle,
    claim, lease, allowed-surface, or provider-selection overrides.
    """
    result = _result_shell(work_item_id)
    result["operating_mode"] = state_store.current_operating_mode()
    authorization = authorization or RoadmapAuthorization()
    auth = authorization.for_work_item(work_item_id)
    result.update({"authorization_status": auth["reason"],
                   "authorization_reference": auth.get("reference")})
    if not auth["authorized"]:
        return result

    try:
        if result["operating_mode"] != "PRODUCT_EXECUTION":
            result["blocker"] = "system-maintenance-active"
            return result

        task = state_store.read("task", work_item_id)
        if task is None:
            result["blocker"] = "work-item-not-found"
            return result
        seat_id, capability = _resolve_seat(task, seat_registry, state_store)
        result.update({"capability": capability, "seat_id": seat_id,
                       "seat_resolution_status": "capability-verified"})

        issue = jira_client.get_issue(work_item_id)
        observed = state_store.observe_lifecycle(
            work_item_id, task["revision"], issue["status_id"]
        )
        result["readiness_status"] = "jira-observed"
        claimed = state_store.claim(
            work_item_id, seat_id, auth["reference"], observed["revision"],
            capability_of_seat=capability, jira_status_id=issue["status_id"],
        )
        result["claim_status"] = "claimed"
        registry = tuple(providers) if providers is not None else available_provider_registry()
        captured = {}

        def request_factory(authoritative_task, lease):
            request = _build_request(authoritative_task, seat_id, brief, lease)
            captured["invocation_id"] = request.invocation_id
            captured["lease_id"] = lease["execution_lease_id"]
            captured["lease_revision"] = lease["revision"]
            return request

        execution = execute_product_wake(
            work_item_id, seat_id, auth["reference"], request_factory, registry,
            state_store=state_store,
        )
        result.update(_execution_result(execution))
        result["invocation_id"] = captured.get("invocation_id")
        result["result_receipt_status"] = "received"
        result["lease_closure_status"] = _lease_status(state_store, captured)
        return result
    except (ControllerInputError, store.StateError, jira.JiraError, ValueError) as exc:
        result["blocker"] = str(exc)
        return result


def _resolve_seat(task, seat_registry, state_store):
    capability = (task.get("execution_profile") or {}).get("required_capability")
    if not capability:
        raise ControllerInputError("work item has no required capability")
    seats = seat_registry.read()
    try:
        seat_id = select_claim_seat(task, seats, state_store.read_all("task"))
    except SeatAllocationError as exc:
        raise ControllerInputError(str(exc))
    return seat_id, capability


def _build_request(task, seat_id, brief, lease):
    capability = (task.get("execution_profile") or {}).get("required_capability")
    surfaces = task.get("surfaces")
    if not isinstance(surfaces, list):
        raise ControllerInputError("work item has no assessed declared surfaces")
    workspace_data = _object(brief, "workspace")
    workspace = Workspace(
        repository_root=_required_text(workspace_data, "repository_root"),
        working_directory=_required_text(workspace_data, "working_directory"),
        mutation_mode=MutationMode(_required_text(workspace_data, "mutation_mode")),
        worktree_path=workspace_data.get("worktree_path"),
        expected_revision=workspace_data.get("expected_revision"),
    )
    return ExecutionRequest(
        invocation_id="controller-" + str(uuid.uuid4()),
        work_item_id=task["work_item_id"], seat_id=seat_id,
        required_capability=capability,
        execution_kind=ExecutionKind(_required_text(brief, "execution_kind")),
        objective=_required_text(brief, "objective"),
        role_contract_ref="agent/roles/%s.md" % capability,
        context_refs=_text_list(brief, "context_refs"), workspace=workspace,
        allowed_surfaces=tuple(surfaces),
        prohibited_actions=("select next work item", "transition Jira lifecycle",
                            "launch another executor"),
        operating_mode="PRODUCT_EXECUTION",
        operating_mode_revision=lease["mode_revision"],
        claim_ref=(task.get("ownership") or {}).get("claim_ref"),
        execution_lease_id=lease["execution_lease_id"],
        reported_environment=_reported_environment(_object(brief, "reported_environment")),
        primary_target=_target(_object(brief, "primary_target")),
        validation_targets=tuple(_validation_target(row) for row in
                                 _list(brief, "validation_targets")),
        model_intent=ModelIntent(_required_text(brief, "model_intent")),
        reasoning_effort=ReasoningEffort(_required_text(brief, "reasoning_effort")),
        required_execution_features=frozenset(
            ExecutionFeature(value) for value in _text_list(brief, "required_execution_features")
        ),
        timeout_seconds=_positive_int(brief, "timeout_seconds"),
        return_contract=_return_contract(_object(brief, "return_contract")),
    )


def _reported_environment(data):
    return ReportedEnvironment(_required_text(data, "locality"), data.get("runtime"),
                               data.get("platform"), data.get("environment_ref"))


def _target(data):
    return ExecutionTarget(_required_text(data, "locality"), data.get("runtime"),
                           data.get("platform"), data.get("environment_ref"),
                           bool(data.get("browser_automation", False)),
                           data.get("launch_method"), data.get("launch_command"),
                           data.get("source", "reported_environment"))


def _validation_target(data):
    if not isinstance(data, dict):
        raise ControllerInputError("validation target must be an object")
    return ValidationTarget(_required_text(data, "target_id"), _required_text(data, "kind"),
                            data.get("required") is True, data.get("platform"), data.get("surface"))


def _return_contract(data):
    return ReturnContract(_required_text(data, "return_to"),
                          _text_list(data, "required_evidence"),
                          _text_list(data, "required_sections"))


def _required_text(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ControllerInputError("%s is required" % key)
    return value.strip()


def _object(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if not isinstance(value, dict):
        raise ControllerInputError("%s must be an object" % key)
    return value


def _list(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if not isinstance(value, list):
        raise ControllerInputError("%s must be a list" % key)
    return value


def _text_list(data, key):
    values = _list(data, key)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ControllerInputError("%s must contain non-empty text" % key)
    return tuple(values)


def _positive_int(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ControllerInputError("%s must be a positive integer" % key)
    return value


def _result_shell(work_item_id):
    return {
        "work_item_id": work_item_id,
        "authorization_status": "not-checked",
        "operating_mode": None,
        "capability": None,
        "seat_id": None,
        "seat_resolution_status": "not-started",
        "readiness_status": "not-started",
        "claim_status": "not-started",
        "invocation_id": None,
        "selected_provider": None,
        "provider_selection_status": "not-started",
        "execution_status": "not-started",
        "provider_failure_code": None,
        "execution_failure_code": None,
        "needs_input": None,
        "blocker": None,
        "result_receipt_status": "not-started",
        "lease_closure_status": "not-opened",
        "claude_transport_from_codex": "available-via-local-claude-cli",
        "claude_transport_limitation": (
            "native prompts are denied in non-interactive controller execution and "
            "returned as needs_input"
        ),
        "codex_transport_status": "available-via-codex-exec",
    }


def _execution_result(execution):
    failure = execution.failure
    return {
        "selected_provider": execution.provider_id,
        "provider_selection_status": ("failed" if execution.provider_id == "thebes-provider-selection"
                                      else "selected"),
        "execution_status": execution.status.value,
        "provider_failure_code": (failure.code.value if failure and execution.status.value == "provider_failed"
                                  else None),
        "execution_failure_code": (failure.code.value if failure and execution.status.value == "execution_failed"
                                   else None),
        "needs_input": (execution.escalation.reason if execution.escalation else None),
        "blocker": (failure.message if failure else None),
        "summary": execution.summary,
        "evidence": [{"kind": item.kind, "reference": item.reference,
                      "summary": item.summary} for item in execution.evidence],
        "changed_files": [{"path": item.path, "change_kind": item.change_kind}
                          for item in execution.changed_files],
        "tests": [{"command": item.command, "status": item.status.value,
                   "evidence_ref": item.evidence_ref, "exit_code": item.exit_code}
                  for item in execution.tests],
        "continuation_ref": execution.continuation_ref,
        "raw_artifact_ref": execution.raw_artifact_ref,
    }


def _lease_status(state_store, captured):
    lease_id = captured.get("lease_id")
    if not lease_id:
        return "not-opened"
    try:
        lease = state_store.read("execution_lease", lease_id)
    except Exception:
        return "closed-by-wake"
    return "closed" if lease and lease.get("closed_at") else "closure-unverified"
