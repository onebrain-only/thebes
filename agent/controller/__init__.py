"""Temporary Phase-2 controller entry point.

This module is intentionally composition glue, not a Listener.  The routine path
takes only a work-item key: ``agent.controller.intent`` derives the bounded
execution brief from canonical sources (Jira for the Product definition,
Persistent State for capability, surfaces, route and environment authority, the
registry for the repository), and Thebes supplies the authorization gate, runtime
checks, claim, immutable request, provider selection, receipt and lease lifecycle
through the existing modules.

A hand-authored brief remains available for exceptional and debug use only. It
fills gaps; it never overrules a canonical safety fact, and it never bypasses the
executor-brief firewall, because it still travels the same request path.
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
from agent.controller.intent import (
    ExecutionIntentUnresolved,
    assert_manual_brief_cannot_override_canonical,
    resolve_execution_intent,
)
from agent.controller.integration import (
    IntegrationRefused,
    integrate_validated_work,
)
from agent.controller import completion as completion_policy
from agent.controller import continuation as continuation_policy
from agent.controller import validation as validation_policy
from agent.controller.validation import ValidationRefused, run_validation
from agent.controller import integration as integration_policy
from agent.controller.completion import CompletionRefused, complete_lifecycle
from agent.controller.workspace import (
    WorkspaceUnavailable,
    conclude_workspace,
    realize_workspace,
)


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


class ProductAuthorization:
    """Exact-ticket authorization first, then a bounded CEO standing grant.

    Two sources, deliberately kept apart, because the whole risk here is one
    actor doing both halves:

      AUTHORITY comes from the CEO — either the roadmap's exact-ticket record,
      or a durable `product_authorization` the CEO granted. Thebes can create
      neither; `store.record_product_authorization` refuses any authority but
      `ceo`, and the roadmap is a governance document.

      SELECTION comes from canonical planning. Under a standing grant the caller
      supplies no key, so this class will not authorize a work item until the
      canonical admission rules have independently proven it admissible. That
      proof is `queue.unclaimable_reasons` — the same predicates the claim gate
      uses — passed in as a prover rather than trusted from the caller.

    That is why this does not weaken D-003. D-003 forbids INFERRING permission
    from queue availability; here the queue decides only WHICH admissible item
    fills an envelope a human already sized. With no grant on record, an empty
    queue authorizes exactly nothing.
    """

    def __init__(self, roadmap=None, state_store=store, admissibility=None):
        self.roadmap = roadmap or RoadmapAuthorization()
        self.state_store = state_store
        self.admissibility = admissibility

    def for_work_item(self, work_item_id):
        exact = self.roadmap.for_work_item(work_item_id)
        if exact["authorized"]:
            return exact
        reader = getattr(self.state_store, "active_product_authorization", None)
        if reader is None:
            return exact              # a store with no standing-grant support
        try:
            grant = reader()
        except store.StateError as exc:
            return dict(exact, reason="authorization-record-unavailable: %s" % exc)
        if grant is None:
            return exact                      # no standing grant: the exact answer stands
        if self.state_store.authorization_remaining(grant) <= 0:
            return {"authorized": False, "reason": "bounded-authorization-exhausted",
                    "reference": grant["authorization_ref"],
                    "authorization_id": grant["product_authorization_id"]}
        if self.admissibility is None:
            # Refuse rather than assume. A standing grant without a way to prove
            # admissibility is exactly the shape that would let selection and
            # authorization collapse into one act.
            return {"authorized": False,
                    "reason": "bounded-authorization-requires-admissibility-proof",
                    "reference": grant["authorization_ref"],
                    "authorization_id": grant["product_authorization_id"]}
        reasons = self.admissibility(work_item_id)
        if reasons:
            return {"authorized": False,
                    "reason": "bounded-authorization-selection-not-admissible: %s"
                              % ", ".join(reasons),
                    "reference": grant["authorization_ref"],
                    "authorization_id": grant["product_authorization_id"]}
        # The reference must be an IDENTIFIER, not the grant's prose. It becomes
        # `claim_ref` on the task record and the wake's reason_ref, and Persistent
        # State caps reference fields at 300 chars precisely so a ticket body
        # cannot be pasted into one. A bounded grant quotes the CEO decision that
        # created it — that text belongs on the authorization record, and the id
        # is how a reader gets to it. The first grant written this way was 295
        # chars and passed only by luck; the second was 440 and refused the claim.
        return {"authorized": True, "reason": "bounded-authorization",
                "reference": grant["product_authorization_id"],
                "authorization_detail": grant["authorization_ref"],
                "authorization_id": grant["product_authorization_id"],
                "authorization_remaining": self.state_store.authorization_remaining(grant)}


def canonical_admissibility(state_store=store, jira_client=jira):
    """Prove admissibility with the canonical predicates and nothing else."""
    def prove(work_item_id):
        from agent.state import queue
        task = state_store.read("task", work_item_id)
        if task is None:
            return ["work-item-not-found"]
        try:
            issue = jira_client.get_issue(work_item_id)
        except jira.JiraError as exc:
            return ["jira-unavailable: %s" % exc]
        facts = {"status_id": issue["status_id"],
                 "has_due_date": bool(issue.get("due_date")),
                 "has_acceptance_criteria": bool(issue.get("description"))}
        return list(queue.unclaimable_reasons(
            task, all_tasks=state_store.read_all("task"),
            edges=[e for e in state_store.read_all("dependency") if not e.get("retired_at")],
            interventions=state_store.active_interventions(),
            jira=facts, jira_status_id=issue["status_id"],
            include_execution_gate=False))
    return prove


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


def execute(work_item_id, brief=None, *, authorization=None, state_store=store,
            jira_client=jira, seat_registry=roster, providers=None,
            intent_resolver=resolve_execution_intent,
            workspace_allocator=realize_workspace,
            workspace_concluder=conclude_workspace,
            run_tail=True, interventions=None, worktree_root=None,
            integration_branch=None, validation_providers=None,
            seats_by_capability=None, validator=run_validation):
    """Submit exactly one already-selected work item through the existing wake.

    ``brief`` is optional and exceptional. With it omitted, Thebes derives the
    execution brief from canonical state. This interface never accepts mode,
    authorization, capability, lifecycle, claim, lease, allowed-surface, or
    provider-selection overrides.
    """
    result = _result_shell(work_item_id)
    result["operating_mode"] = state_store.current_operating_mode()
    authorization = authorization or ProductAuthorization(
        state_store=state_store,
        admissibility=canonical_admissibility(state_store, jira_client))
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
        seat_id, capability, already_owned = _resolve_seat(task, seat_registry, state_store)
        result.update({"capability": capability, "seat_id": seat_id,
                       "seat_resolution_status": "capability-verified"})

        issue = jira_client.get_issue(work_item_id)
        observed = state_store.observe_lifecycle(
            work_item_id, task["revision"], issue["status_id"]
        )
        result["readiness_status"] = "jira-observed"

        # Derivation happens before the claim: work Thebes cannot brief is work
        # it must not take ownership of.
        try:
            derived = intent_resolver(work_item_id, observed, issue, seat_id, state_store)
        except ExecutionIntentUnresolved as exc:
            if brief is None:
                result.update({"blocker": str(exc), "brief_source": "unresolved",
                               "needs_input": exc.detail,
                               "ceo_input_required": exc.classification == "CEO_INPUT_REQUIRED",
                               "governance_input": exc.as_governance_input(work_item_id)})
                return result
            derived = None
        if brief is None:
            brief = derived
            result["brief_source"] = "canonical-state"
        else:
            assert_manual_brief_cannot_override_canonical(brief, derived)
            result["brief_source"] = "supplied-brief"
        result["derived_from"] = (derived or {}).get("derived_from")
        if already_owned:
            # A continuation preserves the canonical owner.  Re-claiming would
            # either fail as already-owned or silently turn a resume into a new
            # allocation decision.
            result["claim_status"] = "preserved"
        else:
            state_store.claim(
                work_item_id, seat_id, auth["reference"], observed["revision"],
                capability_of_seat=capability, jira_status_id=issue["status_id"],
            )
            result["claim_status"] = "claimed"

        # The workspace becomes real here: after ownership exists, before any
        # lease, request or provider. A provider is never pointed at a directory
        # that has not been allocated and proven to be this seat's own.
        realized = workspace_allocator(work_item_id, seat_id, brief["workspace"])
        brief = dict(brief, workspace=realized["workspace"])
        result.update({"workspace_status": "allocated",
                       "workspace_path": realized["path"],
                       "workspace_branch": realized["branch"],
                       "workspace_reused": realized["reused"],
                       "expected_revision": realized["expected_revision"]})

        registry = tuple(providers) if providers is not None else available_provider_registry()
        captured = {}

        def request_factory(authoritative_task, lease):
            request = _build_request(authoritative_task, seat_id, brief, lease)
            captured["invocation_id"] = request.invocation_id
            captured["lease_id"] = lease["execution_lease_id"]
            captured["lease_revision"] = lease["revision"]
            captured["task"] = authoritative_task
            return request

        execution = execute_product_wake(
            work_item_id, seat_id, auth["reference"], request_factory, registry,
            state_store=state_store,
        )
        result.update(_execution_result(execution))
        result["invocation_id"] = captured.get("invocation_id")
        result["result_receipt_status"] = "received"
        result["lease_closure_status"] = _lease_status(state_store, captured)

        # The tail: integration and lifecycle completion are not separate human
        # commands. Both gate themselves on canonical truth, so an execution
        # whose validation route has not yet passed simply refuses here and
        # changes nothing — which is the ordinary case, because a review happens
        # after the wake that produced the work.
        # A needs-input result is durably recorded by now and its workspace is
        # about to be preserved. Deriving the continuation context here is what
        # makes an approved resume possible at all; without it the receipt is a
        # dead end. It grants nothing — the approval is a separate CEO act.
        if run_tail and execution.status.value == "needs_input":
            result["continuation_prepared"] = _prepare_continuation(
                work_item_id, seat_id, captured.get("invocation_id"),
                realized, auth["reference"], state_store)

        integration_evidence = None
        if run_tail and execution.status.value == "completed":
            integration_evidence = _run_completion_tail(
                result, work_item_id, execution, realized, state_store, jira_client,
                validation_providers if validation_providers is not None else registry,
                interventions, seats_by_capability, validator,
                workspace_allocator, workspace_concluder, worktree_root,
                integration_branch)

        # Lifecycle decides the workspace's fate, not the end of this function.
        result.update(workspace_concluder(
            work_item_id, seat_id, execution,
            state_store.read("task", work_item_id) or captured.get("task") or observed,
            realized, integration=integration_evidence))
        return result
    except WorkspaceUnavailable as exc:
        # Isolation failed. That is a bounded orchestration failure; it is never
        # a reason to execute against the canonical Product checkout.
        result.update({"blocker": str(exc), "workspace_status": exc.reason,
                       "workspace_blocker": exc.as_blocker(work_item_id,
                                                           result.get("seat_id"))})
        return result
    except ExecutionIntentUnresolved as exc:
        result.update({"blocker": str(exc), "needs_input": exc.detail,
                       "ceo_input_required": exc.classification == "CEO_INPUT_REQUIRED",
                       "governance_input": exc.as_governance_input(work_item_id)})
        return result
    except (ControllerInputError, store.StateError, jira.JiraError, ValueError) as exc:
        result["blocker"] = str(exc)
        return result


def _integration_shell(work_item_id):
    return {
        "work_item_id": work_item_id,
        "operating_mode": None,
        "seat_id": None,
        "integration_status": "not-started",
        "validation_route": None,
        "validation_result": None,
        "attributed_files": [],
        "product_commit": None,
        "integrated_as": None,
        "integration_branch": None,
        "previous_head": None,
        "conflict_paths": [],
        "remediation_required": False,
        "integration_evidence": None,
        "receipt_status": "not-recorded",
        "completion_status": "not-attempted",
        "jira_transition_performed": False,
        "lifecycle": None,
        "ownership_status": None,
        "open_leases": None,
        "completion_blocker": None,
        "workspace_status": "not-allocated",
        "workspace_path": None,
        "workspace_reason": None,
        "blocker": None,
    }


def integrate(work_item_id, *, state_store=store, jira_client=jira,
              workspace_allocator=realize_workspace,
              workspace_concluder=conclude_workspace,
              integrator=integrate_validated_work, interventions=None,
              integration_branch=None, gates=None, worktree_root=None,
              complete=True, completer=complete_lifecycle,
              conclude_workspace_after=True, record_refusals=True):
    """Land one work item's validated Product work on the integration branch.

    Deliberately a separate act from `execute`: validation happens after an
    execution returns, often in another session, so integration cannot be the
    tail of the wake that produced the work.

    The gate is the canonical validation route and nothing else. Roadmap
    execution authorization is not re-checked here: it names the ticket selected
    for EXECUTION, and refusing to land KAN-A's passed review because the
    roadmap has since moved to KAN-B would strand finished work. What may not be
    skipped is the review verdict, and that is exactly what is checked.
    """
    result = _integration_shell(work_item_id)
    result["operating_mode"] = state_store.current_operating_mode()
    if result["operating_mode"] != "PRODUCT_EXECUTION":
        result["blocker"] = "system-maintenance-active"
        return result
    try:
        task = state_store.read("task", work_item_id)
        if task is None:
            result["blocker"] = "work-item-not-found"
            return result
        seat_id = _integration_seat(task, state_store)
        if not seat_id:
            result["blocker"] = "not-owned"
            return result
        result["seat_id"] = seat_id
        profile = task.get("execution_profile") or {}
        review = task.get("review_context") or {}
        result.update({"validation_route": profile.get("validation_route"),
                       "validation_result": review.get("review_result")})

        # The gate runs before the workspace is touched: work that may not be
        # integrated should not even have its tree re-verified for the purpose.
        integration_policy.assert_validated(task, interventions)

        realized = workspace_allocator(work_item_id, seat_id,
                                       _integration_workspace(task, seat_id, state_store))
        result.update({"workspace_status": "allocated",
                       "workspace_path": realized["path"]})
        issue = jira_client.get_issue(work_item_id)
        evidence = integrator(work_item_id, seat_id, task, issue, realized,
                              root=worktree_root,
                              integration_branch=integration_branch,
                              interventions=interventions, gates=gates)
        outcome = evidence["outcome"]
    except IntegrationRefused as exc:
        # A refusal is evidence: file it with whatever the attempt established.
        evidence = dict(_refusal_evidence(task, seat_id, work_item_id,
                                          result.get("workspace_path"),
                                          integration_branch),
                        detail=exc.detail, conflict_paths=list(exc.conflict_paths))
        outcome = exc.outcome
        result["blocker"] = str(exc)
    except (store.StateError, jira.JiraError, WorkspaceUnavailable, ValueError) as exc:
        result["blocker"] = str(exc)
        return result

    result.update({"integration_status": outcome,
                   "attributed_files": list(evidence.get("attributed_files") or []),
                   "product_commit": evidence.get("product_commit"),
                   "integrated_as": evidence.get("integrated_as"),
                   "integration_branch": evidence.get("integration_branch"),
                   "previous_head": evidence.get("previous_head"),
                   "conflict_paths": list(evidence.get("conflict_paths") or []),
                   "remediation_required": outcome in integration_policy.REMEDIATION_OUTCOMES})
    # A refusal a human asked for is evidence worth keeping. The automatic tail
    # of an execution asks on every run, and filing a receipt each time that a
    # review has simply not happened yet would bury the real ones.
    if outcome in integration_policy.TERMINAL_SUCCESS or record_refusals:
        try:
            receipt = integration_policy.record(state_store, work_item_id, seat_id,
                                                outcome, evidence)
            result["receipt_status"] = "recorded"
        except store.StateError as exc:
            receipt = None
            result["receipt_status"] = "refused: %s" % exc
    else:
        receipt = None
        result["receipt_status"] = "not-recorded"

    # Completion is the tail of integration, not a second human command. It
    # gates itself, so an integration that did not finish simply does not
    # complete anything.
    if complete and outcome in integration_policy.TERMINAL_SUCCESS:
        result.update(_complete_after_integration(
            work_item_id, state_store, jira_client, receipt, interventions,
            completer))
    result["integration_evidence"] = evidence
    if conclude_workspace_after and result["workspace_status"] == "allocated":
        result.update(workspace_concluder(work_item_id, seat_id, None, task,
                                          realized, integration=evidence))
    return result


def _run_completion_tail(result, work_item_id, execution, realized, state_store,
                         jira_client, providers, interventions, seats_by_capability,
                         validator, workspace_allocator, workspace_concluder,
                         worktree_root, integration_branch):
    """Validation, integration and lifecycle completion, in canonical order.

    Shared by the first wake and by an approved continuation: a resumed
    execution that completes the Product work is finished work, and it earns the
    same tail. Both gate themselves, so a route that has not passed simply
    changes nothing.
    """
    result.update(_validate_after_execution(
        work_item_id, state_store, jira_client, execution, realized, providers,
        interventions, seats_by_capability, validator))
    if result.get("validation_status") != validation_policy.VALIDATION_PASSED:
        return None
    tail = integrate(
        work_item_id, state_store=state_store, jira_client=jira_client,
        workspace_allocator=workspace_allocator,
        workspace_concluder=workspace_concluder,
        interventions=interventions, worktree_root=worktree_root,
        integration_branch=integration_branch,
        conclude_workspace_after=False, record_refusals=False)
    result.update({key: tail[key] for key in (
        "integration_status", "attributed_files", "product_commit",
        "integrated_as", "integration_branch", "previous_head",
        "conflict_paths", "remediation_required", "receipt_status",
        "completion_status", "completion_blocker",
        "jira_transition_performed", "lifecycle", "ownership_status",
        "open_leases") if key in tail})
    return tail.get("integration_evidence")


def decide(work_item_id, original_invocation_id, permission, approval_scope,
           allowed_operation=None, *, approving_authority="ceo", state_store=store,
           resumer=None, **resume_kwargs):
    """Record one exact CEO decision, then resume the workflow that asked for it.

    This is the missing process-callable half of the Phase-2 authority loop.
    `store.record_execution_approval` and `resume` both already existed, and both
    were reachable only from inside a Python session that already held the
    controller's imports — so a decision arriving over any boundary at all had
    nowhere to land.

    It creates no approval architecture. The seat and the provider session are
    re-derived from the canonical continuation preparation rather than accepted
    from the caller, so a caller cannot redirect a decision at another seat or
    another session; the approval writer then re-verifies identity, session and
    the exact permission boundary against the durable receipt and refuses
    anything that does not match. Idempotence is the writer's, not this
    function's: the approval id is content-addressed, so the same decision twice
    is the same record, and `resume` detects an already-executed continuation
    before composing grants.
    """
    result = _result_shell(work_item_id)
    result.update({"operating_mode": state_store.current_operating_mode(),
                   "decision_status": "not-recorded",
                   "execution_approval_id": None})
    if result["operating_mode"] != "PRODUCT_EXECUTION":
        result["blocker"] = "system-maintenance-active"
        return result
    try:
        preparation = state_store.read_execution_continuation_preparation(
            original_invocation_id)
        if preparation is None:
            result["blocker"] = "no-prepared-continuation"
            return result
        if preparation.get("work_item_id") != work_item_id:
            result["blocker"] = "decision-work-item-mismatch"
            return result
        approval = state_store.record_execution_approval(
            original_invocation_id=original_invocation_id,
            work_item_id=work_item_id,
            seat_id=preparation["seat_id"],
            claude_session_id=preparation["claude_session_id"],
            permission=permission,
            approving_authority=approving_authority,
            approval_scope=approval_scope,
            allowed_operation=allowed_operation)
        result.update({"decision_status": "recorded",
                       "execution_approval_id": approval["execution_approval_id"]})
    except (store.StateError, ValueError) as exc:
        result["blocker"] = str(exc)
        return result
    resumed = (resumer or resume)(work_item_id, state_store=state_store, **resume_kwargs)
    resumed.update({"decision_status": result["decision_status"],
                    "execution_approval_id": result["execution_approval_id"]})
    return resumed


def resume(work_item_id, *, state_store=store, jira_client=jira, providers=None,
           workspace_allocator=realize_workspace,
           workspace_concluder=conclude_workspace, validator=run_validation,
           interventions=None, worktree_root=None, integration_branch=None,
           seats_by_capability=None, continuation_driver=None, transport=None):
    """Resume one approved continuation, then run the same completion tail.

    `execute_approved_claude_continuation` resumes the provider session and
    records its receipt; it deliberately owns nothing beyond that. Without this
    entry the resumed work stopped there — finished Product work with no
    validation, no integration and no lifecycle completion. This is that gap
    closed, reusing the ordering `execute` already has rather than a second one.
    """
    from agent.execution.claude import ClaudeCliTransport, ClaudeProvider
    from agent.execution.wake import (
        build_prepared_continuation_request, execute_approved_claude_continuation,
        granted_permissions,
    )
    driver = continuation_driver or execute_approved_claude_continuation
    result = _result_shell(work_item_id)
    result["operating_mode"] = state_store.current_operating_mode()
    if result["operating_mode"] != "PRODUCT_EXECUTION":
        result["blocker"] = "system-maintenance-active"
        return result
    try:
        task = state_store.read("task", work_item_id)
        if task is None:
            result["blocker"] = "work-item-not-found"
            return result
        seat_id = (task.get("ownership") or {}).get("seat_id")
        result.update({"seat_id": seat_id,
                       "capability": (task.get("execution_profile") or {}).get(
                           "required_capability")})
        original = _continuable_invocation(work_item_id, seat_id, state_store)
        if original is None:
            result["blocker"] = "no-prepared-continuation"
            return result
        preparation = state_store.read_execution_continuation_preparation(original)
        result["continuation_prepared"] = preparation["execution_continuation_id"]

        # Idempotent, and the order matters: a completed continuation is a
        # terminal outcome for its whole grant set, so composing the approvals
        # is itself refused afterwards. The already-executed case is therefore
        # detected FIRST, and the tail resumes from durable evidence rather than
        # re-waking the provider over finished Product work.
        already = _existing_continuation_receipt(original, state_store)
        if already is not None:
            from agent.execution.receipt import execution_result_from_payload
            execution = execution_result_from_payload(already["normalized_result"])
            result["continuation_status"] = "already-executed"
        else:
            approvals = state_store.compose_execution_approvals(original)
            # Rendered by the wake's own renderer, not rebuilt here. Building it
            # twice is what made a scoped grant unresumable.
            permissions = granted_permissions(approvals)
            result["approved_permissions"] = list(permissions)
            provider = ClaudeProvider(transport or ClaudeCliTransport(),
                                      session_ref=preparation["claude_session_id"],
                                      approved_permissions=permissions)
            execution = driver(
                tuple(record["execution_approval_id"] for record in approvals),
                lambda task_record, lease, approval, prior:
                    build_prepared_continuation_request(preparation, task_record, lease),
                provider, state_store=state_store)
            result["continuation_status"] = "executed"
        result.update(_execution_result(execution))
        result["invocation_id"] = execution.invocation_id
        result["result_receipt_status"] = "received"

        realized = workspace_allocator(work_item_id, seat_id, {
            "repository_root": preparation["repository_root"],
            "working_directory": None, "worktree_path": None,
            "expected_revision": None, "mutation_mode": "repository_edit"})
        result.update({"workspace_status": "allocated",
                       "workspace_path": realized["path"],
                       "workspace_branch": realized["branch"],
                       "workspace_reused": realized["reused"],
                       "expected_revision": realized["expected_revision"]})
        integration_evidence = None
        if execution.status.value == "completed":
            integration_evidence = _run_completion_tail(
                result, work_item_id, execution, realized, state_store, jira_client,
                tuple(providers) if providers is not None else available_provider_registry(),
                interventions, seats_by_capability, validator,
                workspace_allocator, workspace_concluder, worktree_root,
                integration_branch)
        elif execution.status.value == "needs_input":
            result["continuation_prepared"] = _prepare_continuation(
                work_item_id, seat_id, execution.invocation_id, realized,
                preparation["authorization_ref"], state_store)
        result.update(workspace_concluder(
            work_item_id, seat_id, execution,
            state_store.read("task", work_item_id) or task, realized,
            integration=integration_evidence))
        return result
    except (WorkspaceUnavailable, store.StateError, jira.JiraError, ValueError) as exc:
        result["blocker"] = str(exc)
        return result


def _existing_continuation_receipt(original_invocation_id, state_store):
    """The terminal receipt of a continuation already driven for this lineage."""
    return next((receipt for receipt in state_store.read_all("execution_receipt")
                 if receipt.get("continuation_of_invocation_id") == original_invocation_id
                 and receipt.get("status") != "needs_input"), None)


def resume_validation(work_item_id, *, state_store=store, jira_client=jira,
                      workspace_allocator=realize_workspace,
                      workspace_concluder=conclude_workspace, interventions=None,
                      worktree_root=None, integration_branch=None, transport=None):
    """Resume an approved validator, then run the rest of the lifecycle.

    The verdict a resumed validator returns is the same verdict any validator
    returns, so it earns the same tail: integration and lifecycle completion,
    both gating themselves on canonical truth.
    """
    result = _result_shell(work_item_id)
    result["operating_mode"] = state_store.current_operating_mode()
    if result["operating_mode"] != "PRODUCT_EXECUTION":
        result["blocker"] = "system-maintenance-active"
        return result
    try:
        evidence = validation_policy.resume_validation(
            work_item_id, state_store, jira_client, transport=transport,
            interventions=interventions)
    except ValidationRefused as exc:
        result.update({"validation_status": exc.outcome, "validation_blocker": str(exc)})
        return result
    except (store.StateError, jira.JiraError, ValueError) as exc:
        result.update({"validation_status": validation_policy.VALIDATION_DISPATCH_FAILED,
                       "validation_blocker": str(exc)})
        return result

    result.update({"validation_status": evidence["outcome"],
                   "validation_route": evidence.get("validation_route"),
                   "reviewer": evidence.get("reviewer"),
                   "review_cycle": evidence.get("review_cycle"),
                   "verdict": evidence.get("verdict"),
                   "approved_permissions": list(evidence.get("approved_permissions") or []),
                   "remediation_owner": evidence.get("remediation_owner"),
                   "remediation_route": evidence.get("remediation_route")})
    task = state_store.read("task", work_item_id)
    seat_id = _integration_seat(task, state_store)
    result["seat_id"] = seat_id
    if evidence["outcome"] != validation_policy.VALIDATION_PASSED:
        return result
    tail = integrate(work_item_id, state_store=state_store, jira_client=jira_client,
                     workspace_allocator=workspace_allocator,
                     workspace_concluder=workspace_concluder,
                     interventions=interventions, worktree_root=worktree_root,
                     integration_branch=integration_branch,
                     conclude_workspace_after=True, record_refusals=True)
    result.update({key: tail[key] for key in (
        "integration_status", "attributed_files", "product_commit", "integrated_as",
        "integration_branch", "previous_head", "conflict_paths",
        "remediation_required", "receipt_status", "completion_status",
        "completion_blocker", "jira_transition_performed", "lifecycle",
        "ownership_status", "open_leases", "workspace_status", "workspace_reason",
        "workspace_path") if key in tail})
    return result


def _continuable_invocation(work_item_id, seat_id, state_store):
    """The one prepared, still-open continuation for this work item."""
    candidates = [
        record for record in state_store.read_all("execution_continuation_preparation")
        if record.get("work_item_id") == work_item_id
        and record.get("seat_id") == seat_id]
    if not candidates:
        return None
    newest = sorted(candidates, key=lambda record: record.get("created_at") or "")[-1]
    return newest["original_invocation_id"]


def _prepare_continuation(work_item_id, seat_id, invocation_id, realized,
                          authorization_ref, state_store):
    """Derive the resume context from the needs-input receipt just written."""
    if not invocation_id:
        return None
    try:
        receipt = state_store.read_execution_receipt(invocation_id)
        prepared = continuation_policy.prepare(
            work_item_id, seat_id, receipt, realized, authorization_ref, state_store)
    except (store.StateError, ValueError, KeyError) as exc:
        # A preparation that cannot be derived is reported, never invented: the
        # execution evidence itself is already durable and unaffected.
        return "refused: %s" % exc
    if prepared is None:
        return "not-continuable"
    return prepared["execution_continuation_id"]


def _validate_after_execution(work_item_id, state_store, jira_client, execution,
                              realized, providers, interventions,
                              seats_by_capability, validator):
    """Run the canonical validation route. A refusal is named, never a guess."""
    outcome = {"validation_status": "not-attempted", "validation_blocker": None}
    task = state_store.read("task", work_item_id)
    if task is None:
        return dict(outcome, validation_status="work-item-not-found")
    review = task.get("review_context") or {}
    if review.get("review_result") == "pass":
        # Already validated in an earlier pass of this flow. Not a second review.
        return {"validation_status": validation_policy.VALIDATION_PASSED,
                "validation_route": review.get("review_type"),
                "reviewer": review.get("review_owner"),
                "review_cycle": review.get("review_cycle"),
                "verdict": "pass", "validation_blocker": None}
    try:
        evidence = validator(work_item_id, task, execution, realized, state_store,
                             jira_client, providers,
                             seats_by_capability=seats_by_capability,
                             receipt_ref="execution receipt for %s" % work_item_id)
    except ValidationRefused as exc:
        return dict(outcome, validation_status=exc.outcome,
                    validation_blocker=str(exc))
    except (store.StateError, jira.JiraError, ValueError) as exc:
        return dict(outcome,
                    validation_status=validation_policy.VALIDATION_DISPATCH_FAILED,
                    validation_blocker=str(exc))
    return {"validation_status": evidence["outcome"],
            "validation_route": evidence.get("validation_route"),
            "reviewer": evidence.get("reviewer"),
            "review_cycle": evidence.get("review_cycle"),
            "verdict": evidence.get("verdict"),
            "validation_blocker": None,
            "remediation_owner": evidence.get("remediation_owner"),
            "remediation_route": evidence.get("remediation_route")}


def _complete_after_integration(work_item_id, state_store, jira_client, receipt,
                                interventions, completer):
    """Run the lifecycle tail against the task as it now stands."""
    outcome = {"completion_status": "not-attempted", "completion_blocker": None}
    task = state_store.read("task", work_item_id)
    if task is None:
        return dict(outcome, completion_status="work-item-not-found")
    receipts = ([receipt] if receipt is not None
                else state_store.read_integration_receipts(work_item_id))
    try:
        evidence = completer(work_item_id, task, receipts, state_store, jira_client,
                             interventions=interventions)
    except CompletionRefused as exc:
        return dict(outcome, completion_status=exc.outcome,
                    completion_blocker=str(exc))
    except (store.StateError, jira.JiraError, ValueError) as exc:
        return dict(outcome, completion_status=completion_policy.FINALIZATION_INCOMPLETE,
                    completion_blocker=str(exc))
    outcome = {"completion_status": evidence["outcome"],
               "completion_blocker": None,
               "jira_transition_performed": evidence["jira_transition_performed"],
               "lifecycle": evidence["lifecycle"],
               "ownership_status": evidence["ownership_status"],
               "open_leases": evidence["open_leases"]}
    outcome.update(_consume_authorization(work_item_id, evidence, state_store))
    return outcome


def _consume_authorization(work_item_id, evidence, state_store):
    """Spend one allowance of a standing grant, and only for a real completion.

    The single place this happens, and it happens HERE rather than at dispatch on
    purpose: an attempt is not a completion. A refusal, a failure, a block or an
    interrupted run must leave the quota exactly where it was, or a grant quietly
    expires against work that never landed.

    Consumption is keyed on the work item, so a re-entered or retried completion
    tail returns the same record instead of counting twice.
    """
    if evidence["outcome"] not in completion_policy.TERMINAL_SUCCESS:
        return {}
    if evidence.get("lifecycle") != "done":
        return {}
    # A store that does not implement standing grants simply has none. This is
    # not defensive padding: the exact-ticket path predates this feature and must
    # keep working against a store that never heard of it.
    reader = getattr(state_store, "active_product_authorization", None)
    if reader is None:
        return {}
    try:
        grant = reader()
        if grant is None:
            return {}
        before = state_store.authorization_remaining(grant)
        updated = state_store.consume_product_authorization(
            grant["product_authorization_id"], work_item_id, grant["revision"],
            evidence_ref="lifecycle %s, jira transition %s" % (
                evidence["outcome"], evidence["jira_transition_performed"]))
        return {"authorization_id": updated["product_authorization_id"],
                "authorization_remaining_before": before,
                "authorization_remaining_after":
                    state_store.authorization_remaining(updated),
                "authorization_status": updated["status"]}
    except store.StateError as exc:
        # A quota that cannot be spent never turns a real completion into a
        # failure — the Product work IS done and Jira says so. It is reported.
        return {"authorization_consumption_blocker": str(exc)}


def _integration_seat(task, state_store):
    """Whose worktree holds this work.

    Ownership while the item is still owned; once validation has released it,
    the evidenced executor — which is the same seat, and after a PEER FAIL
    transfer is correctly the reviewer who took the work over. Two distinct
    evidenced seats is conflicting evidence and integration refuses rather than
    picking one.
    """
    owner = (task.get("ownership") or {}).get("seat_id")
    if owner:
        return owner
    try:
        evidenced = state_store.evidenced_executors(task)
    except Exception:                                     # noqa: BLE001
        return None
    return evidenced[0] if len(evidenced) == 1 else None


def _refusal_evidence(task, seat_id, work_item_id, workspace_path, integration_branch):
    from agent.state import worktrees
    profile = task.get("execution_profile") or {}
    review = task.get("review_context") or {}
    return {"worktree_path": workspace_path,
            "source_branch": worktrees.branch_name(seat_id, work_item_id),
            "integration_branch": integration_branch or worktrees.INTEGRATION_BRANCH,
            "validation_route": profile.get("validation_route"),
            "validation_result": review.get("review_result"),
            "attributed_files": []}


def _integration_workspace(task, seat_id, state_store):
    """Name the same isolated workspace this work item already has.

    Allocation is idempotent and derives the path from (seat, work item), so
    this re-verifies and reuses the executor's tree rather than making a new one.
    """
    from agent.controller.intent import ROOT as INTENT_ROOT, read_project_repository
    repository = read_project_repository(task.get("product_id"), task.get("project_id"))
    return {"repository_root": os.path.join(INTENT_ROOT, repository),
            "working_directory": None, "worktree_path": None,
            "expected_revision": None, "mutation_mode": "repository_edit"}


def _resolve_seat(task, seat_registry, state_store):
    capability = (task.get("execution_profile") or {}).get("required_capability")
    if not capability:
        raise ControllerInputError("work item has no required capability")
    seats = seat_registry.read()
    ownership = task.get("ownership") or {}
    existing_owner = ownership.get("seat_id")
    if existing_owner:
        entry = seats.get(existing_owner)
        if not isinstance(entry, dict) or entry.get("capability") != capability:
            raise ControllerInputError(
                "current owner %s is not an active %s seat" % (existing_owner, capability)
            )
        return existing_owner, capability, True
    try:
        seat_id = select_claim_seat(task, seats, state_store.read_all("task"))
    except SeatAllocationError as exc:
        raise ControllerInputError(str(exc))
    return seat_id, capability, False


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
        "brief_source": "not-resolved",
        "derived_from": None,
        "workspace_status": "not-allocated",
        "workspace_path": None,
        "workspace_branch": None,
        "workspace_reused": False,
        "workspace_reason": None,
        "workspace_branch_kept": None,
        "workspace_blocker": None,
        "expected_revision": None,
        # The automatic tail: integration and lifecycle completion. Both gate
        # themselves, so "not-attempted" is the ordinary answer for an execution
        # whose review has not happened yet.
        "validation_status": "not-attempted",
        "validation_route": None,
        "reviewer": None,
        "review_cycle": None,
        "verdict": None,
        "validation_blocker": None,
        "remediation_owner": None,
        "remediation_route": None,
        "integration_status": "not-attempted",
        "attributed_files": [],
        "product_commit": None,
        "integrated_as": None,
        "integration_branch": None,
        "previous_head": None,
        "conflict_paths": [],
        "remediation_required": False,
        "receipt_status": "not-recorded",
        "completion_status": "not-attempted",
        "completion_blocker": None,
        "jira_transition_performed": False,
        "lifecycle": None,
        "ownership_status": None,
        "open_leases": None,
        "continuation_prepared": None,
        "approved_permissions": [],
        "continuation_status": "not-attempted",
        "ceo_input_required": False,
        "governance_input": None,
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
