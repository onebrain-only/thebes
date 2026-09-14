"""Core-owned ordering around one already-authorized Product execution wake."""

from dataclasses import replace
import hashlib

from agent.execution.provider import (
    ExecutionFeature, ExecutionKind, ExecutionRequest, ExecutionTarget, ModelIntent,
    MutationMode, ReasoningEffort, ReportedEnvironment, ReturnContract, ValidationTarget,
    Workspace,
)
from agent.execution.result import receive_execution_result
from agent.execution.receipt import normalized_result_payload
from agent.execution.selection import select_provider


class WakeOrderError(ValueError):
    pass


def build_prepared_continuation_request(preparation, task, lease):
    """Build the minimal new context expressly authorized for a historical resume."""
    if not preparation or preparation.get("historical_request_persisted") is not False:
        raise WakeOrderError("continuation preparation is absent or rewrites historical truth")
    return ExecutionRequest(
        invocation_id="prepared-" + preparation["execution_continuation_id"],
        work_item_id=preparation["work_item_id"], seat_id=preparation["seat_id"],
        required_capability=preparation["required_capability"],
        execution_kind=ExecutionKind.IMPLEMENTATION,
        objective=("Continue the same preserved work item from canonical durable state and only "
                   "declared surfaces. Do not run Thebes/controller bootstrap code, launch Claude, "
                   "or invoke execute_approved_claude_continuation."),
        role_contract_ref="agent/roles/%s.md" % preparation["required_capability"],
        context_refs=("CLAUDE.md", "agent/CONTRACT.md"),
        workspace=Workspace(preparation["repository_root"], preparation["working_directory"],
                            MutationMode.REPOSITORY_EDIT, preparation["worktree_path"],
                            preparation["expected_revision"]),
        allowed_surfaces=tuple(task.get("surfaces") or ()),
        prohibited_actions=("select another Jira task", "change provider", "bypass permissions",
                            "execute_approved_claude_continuation", "build_prepared_continuation_request",
                            "launch another Claude session"),
        operating_mode="PRODUCT_EXECUTION", operating_mode_revision=lease["mode_revision"],
        claim_ref=(task.get("ownership") or {}).get("claim_ref"),
        execution_lease_id=lease["execution_lease_id"],
        reported_environment=ReportedEnvironment("local", environment_ref=preparation["repository_root"]),
        primary_target=ExecutionTarget("local", environment_ref=preparation["repository_root"]),
        validation_targets=(ValidationTarget(preparation["validation_route"], "review", True),),
        model_intent=ModelIntent.BALANCED, reasoning_effort=ReasoningEffort.HIGH,
        required_execution_features=frozenset({ExecutionFeature.REPOSITORY_READ,
                                               ExecutionFeature.REPOSITORY_EDIT,
                                               ExecutionFeature.SHELL,
                                               ExecutionFeature.RESUMABLE_SESSIONS}),
        timeout_seconds=900,
        return_contract=ReturnContract("qa", ("changed files", "test output"), ("RESULT", "EVIDENCE")),
    )


def execute_product_wake(work_item_id, seat_id, reason_ref, request_factory, providers,
                         provider_override=None, state_store=None,
                         closed_by="orchestrator"):
    """Gate, lease, build, select, execute, receive, and close one request.

    ``request_factory`` runs only after the execution lease exists and receives
    ``(authoritative_task, lease)``. ``providers`` is an explicit controller
    registry, not a caller-selected executor. The existing selection policy
    chooses one compatible provider (or creates its normalized failure), and
    the existing core receipt boundary observes the normalized result. Claim,
    Product authorization, routing, and lifecycle decisions remain outside this
    ordering seam.
    """
    if state_store is None:
        from agent.state import store as state_store

    task = state_store.assert_execution_permitted(work_item_id, seat_id)
    lease = state_store.open_execution_lease(work_item_id, seat_id, reason_ref)
    try:
        request = request_factory(task, lease)
        _validate_request_order(request, task, lease, work_item_id, seat_id)
        selection = select_provider(request, providers, override=provider_override)
        if selection.provider is None:
            result = selection.failure_result(request)
        else:
            result = selection.provider.execute(request)
        normalized = receive_execution_result(result)
        # This must precede lease closure.  A caller may stop observing this wake
        # while the provider process continues; the terminal evidence remains
        # recoverable without another provider invocation.
        state_store.record_execution_receipt(
            request.invocation_id, work_item_id, seat_id,
            lease["execution_lease_id"], normalized_result_payload(normalized),
            provider_selection=selection.receipt_evidence(),
        )
        return normalized
    finally:
        state_store.close_execution_lease(
            lease["execution_lease_id"], lease["revision"], closed_by
        )


def _validate_request_order(request, task, lease, work_item_id, seat_id):
    ownership = task.get("ownership") or {}
    expected = {
        "work_item_id": work_item_id,
        "seat_id": seat_id,
        "operating_mode": "PRODUCT_EXECUTION",
        "execution_lease_id": lease["execution_lease_id"],
        "operating_mode_revision": lease["mode_revision"],
        "claim_ref": ownership.get("claim_ref"),
    }
    for field, value in expected.items():
        if getattr(request, field, None) != value:
            raise WakeOrderError(
                "prepared request %s must preserve %r" % (field, value)
            )


def _continuation_invocation_id(approval_ids):
    if len(approval_ids) == 1:
        return "continuation-" + approval_ids[0]
    digest = hashlib.sha256("\0".join(approval_ids).encode("utf-8")).hexdigest()
    return "continuation-approval-set-" + digest


def execute_approved_claude_continuation(approval_ids, request_factory, provider,
                                         *, state_store=None,
                                         closed_by="orchestrator", replacement_session=False):
    """Resume exactly one Claude session after one immutable CEO approval.

    This is deliberately not provider selection or a new claim.  The original
    receipt, owner, provider, and Claude session are the authority; a fresh
    short-lived lease only protects the resumed process lifecycle.
    """
    if state_store is None:
        from agent.state import store as state_store
    requested_ids = (approval_ids,) if isinstance(approval_ids, str) else tuple(approval_ids)
    if not requested_ids:
        raise WakeOrderError("continuation approval does not exist")
    first_approval = state_store.read_execution_approval(requested_ids[0])
    if first_approval is None:
        raise WakeOrderError("continuation approval does not exist")
    approvals = state_store.compose_execution_approvals(
        first_approval["original_invocation_id"], requested_ids)
    approval = approvals[0]
    original = state_store.read_execution_receipt(approval["original_invocation_id"])
    preparation = state_store.read_execution_continuation_preparation(
        approval["original_invocation_id"])
    if original is None or original.get("status") != "needs_input":
        raise WakeOrderError("continuation original receipt is not awaiting input")
    if preparation is None:
        raise WakeOrderError("continuation preparation does not exist")
    if original.get("provider_id") != "claude-code" or any(
            rec.get("provider_id") != "claude-code" for rec in approvals):
        raise WakeOrderError("continuation provider must remain Claude Code")
    if provider.capabilities().provider_id != "claude-code":
        raise WakeOrderError("continuation provider switch is refused")
    permissions = tuple(
        rec["permission"] if rec.get("allowed_operation") is None
        else "%s(%s)" % (rec["permission"], rec["allowed_operation"])
        for rec in approvals
    )
    if tuple(getattr(provider, "approved_permissions", ())) != permissions:
        raise WakeOrderError("continuation provider permissions do not match exact grants")
    invocation_id = _continuation_invocation_id(tuple(rec["execution_approval_id"] for rec in approvals))
    if replacement_session:
        invocation_id = "replacement-" + invocation_id
    if state_store.read_execution_receipt(invocation_id) is not None:
        raise WakeOrderError("continuation was already executed")
    task = state_store.assert_execution_permitted(approval["work_item_id"], approval["seat_id"])
    lease = state_store.open_execution_lease(
        approval["work_item_id"], approval["seat_id"],
        _continuation_invocation_id(tuple(rec["execution_approval_id"] for rec in approvals)))
    try:
        request = request_factory(task, lease, approval, original)
        request = replace(request, invocation_id=invocation_id,
                          work_item_id=approval["work_item_id"], seat_id=approval["seat_id"],
                          claim_ref=(task.get("ownership") or {}).get("claim_ref"),
                          execution_lease_id=lease["execution_lease_id"],
                          operating_mode_revision=lease["mode_revision"])
        _validate_request_order(request, task, lease, approval["work_item_id"], approval["seat_id"])
        result = receive_execution_result(provider.execute(request))
        state_store.record_execution_receipt(
            request.invocation_id, request.work_item_id, request.seat_id,
            lease["execution_lease_id"], normalized_result_payload(result),
            provider_selection={"primary_provider_id": "claude-code",
                                "selected_provider_id": "claude-code"},
            continuation_of=approval["original_invocation_id"],
            approval_id=approval["execution_approval_id"],
            approval_ids=tuple(rec["execution_approval_id"] for rec in approvals),
        )
        return result
    finally:
        state_store.close_execution_lease(lease["execution_lease_id"], lease["revision"], closed_by)
