"""Dispatch the canonical validation route, and record the verdict it produces.

Validation is orchestration, not something an executor decides about itself.
Every rule here already exists and is reused unchanged:

    policy.validation_route_for_profile   derives SELF / QA / PEER
    policy.peer_eligible                  who may own a PEER review
    policy.resolve_owner_or_wait          who owns it, or that it waits
    store.transition_target(route=...)    the one legal review status
    store.open_review_context             records the route and its owner
    store.record_review_result            the only place a verdict becomes true
    store.peer_fail_transfer              PEER FAIL moves execution to the reviewer
    store.self_fail_reentry               SELF FAIL returns it to the same seat
    agent.execution.brief                 the one brief builder and its firewall

This module adds the ordering and the dispatch, and nothing else. It never
chooses a route, never picks a reviewer policy would refuse, and never writes a
verdict of its own: `record_review_result` requires the exact recorded review
owner, so a controller that wanted to pass its own work could not.

ORDERING, AND WHY IT IS THIS WAY

    release ownership   executor evidence is created by `store.release` and by
                        nothing else. SELF's owner IS the evidenced executor,
                        and PEER eligibility EXCLUDES the evidenced executors,
                        so both routes need that evidence to exist first.
    transition          `open_review_context` refuses unless the item is
                        canonically in review, so Jira moves before the context.
    open context        policy resolves the owner; a PEER with no eligible peer
                        waits with a null owner rather than being downgraded.
    dispatch            the reviewer runs as a read-only validation act.
    record              the verdict, through the canonical writer.

WHY THIS DOES NOT USE `execute_product_wake`

That wake is gated on OWNERSHIP, correctly: a Product implementation wake must
be owned. A reviewer is not the owner — that is the point of review, and `qa`
never owns anything. So validation composes the same provider seam
(`select_provider`, `provider.execute`, `receive_execution_result`, the same
brief and the same firewall) without the ownership gate that does not apply to
it. It opens no claim and no lease, and it cannot write: the request contract
refuses a validation request that is not read-only.
"""

import uuid

from agent.execution.brief import render_executor_brief  # noqa: F401  (firewall)
from agent.execution.provider import (
    ExecutionFeature, ExecutionKind, ExecutionRequest, ExecutionStatus,
    ExecutionTarget, ModelIntent, MutationMode, ReasoningEffort,
    ReportedEnvironment, ReturnContract, ValidationTarget, Workspace,
)
from agent.execution.receipt import normalized_result_payload
from agent.execution.result import receive_execution_result
from agent.execution.selection import select_provider
from agent.state import policy


PASS = "pass"
FAIL = "fail"

VALIDATION_NOT_REQUIRED = "validation-not-required"
VALIDATION_PASSED = "validation-passed"
VALIDATION_FAILED = "validation-failed"
VALIDATION_WAITING_FOR_REVIEWER = "validation-waiting-for-reviewer"
VALIDATION_ROUTE_UNRESOLVED = "validation-route-unresolved"
VALIDATION_CONTEXT_REFUSED = "validation-context-refused"
VALIDATION_DISPATCH_FAILED = "validation-dispatch-failed"
VALIDATION_RESULT_MALFORMED = "validation-result-malformed"
VALIDATION_ALREADY_SETTLED = "validation-already-settled"

VERDICT_EVIDENCE_KIND = "verdict"
DEFAULT_TIMEOUT_SECONDS = 900
REQUIRED_EVIDENCE = ("verdict", "checks performed", "evidence for the verdict")
REQUIRED_SECTIONS = ("VERDICT", "EVIDENCE")

# A validator inspects and reports. It does not implement, and it does not get
# to decide what happens next — that is the same boundary the executor has.
VALIDATOR_PROHIBITIONS = (
    "implement Product changes",
    "edit any file in this workspace",
    "widen the scope beyond this work item",
    "select next work item",
    "transition Jira lifecycle",
    "launch another executor",
)


class ValidationRefused(Exception):
    """A bounded, named refusal. None of these is a provider or Product failure."""

    def __init__(self, outcome, detail):
        super().__init__("%s: %s" % (outcome, detail))
        self.outcome = outcome
        self.detail = detail


# ------------------------------------------------------------------- the route

def route_for(task):
    """The canonical route, from the canonical calculator. Nothing else."""
    route = policy.validation_route_for_profile(task.get("execution_profile") or {})
    if route is None:
        raise ValidationRefused(
            VALIDATION_ROUTE_UNRESOLVED,
            "%s has no recorded characteristics, so policy has produced no "
            "validation route" % task.get("work_item_id"))
    return route


def propose_peer_reviewer(task, seats_by_capability, executors):
    """Name a candidate PEER. Policy decides whether it is one.

    `open_review_context` re-checks this against `policy.peer_eligible` with the
    evidenced executors excluded, so a wrong proposal is refused there rather
    than accepted here. Deterministic order: no scoring, no preference.
    """
    capability = (task.get("execution_profile") or {}).get("required_capability")
    eligible = policy.peer_eligible(capability, seats_by_capability,
                                    exclude=tuple(executors))
    return eligible[0] if eligible else None


# ------------------------------------------------------- entering the review

def enter_review(work_item_id, task, state_store, jira_client, release_ref):
    """Release ownership, move the issue into its review status, observe it.

    Ownership is released FIRST because that is the only act that creates
    executor evidence, and both SELF ownership and PEER eligibility are derived
    from it. Jira moves next because a review context may only be opened on an
    item that is canonically in review.
    """
    route = route_for(task)
    if (task.get("ownership") or {}).get("seat_id"):
        task = state_store.release(work_item_id, task["ownership"]["seat_id"],
                                   task["revision"], release_ref,
                                   authority="orchestrator")
    target = state_store.transition_target(route=route)
    issue = jira_client.get_issue(work_item_id)
    if str(issue.get("status_id")) != str(target):
        jira_client.transition_issue(work_item_id, _transition_id(target))
        issue = jira_client.get_issue(work_item_id)
        if str(issue.get("status_id")) != str(target):
            raise ValidationRefused(
                VALIDATION_CONTEXT_REFUSED,
                "%s did not reach its %s review status; Jira reports %s"
                % (work_item_id, route, issue.get("status_id")))
    return state_store.observe_lifecycle(work_item_id, task["revision"],
                                         str(target)), route


def _transition_id(status_id):
    from agent.state import board
    return board.transition_for(board.assert_transition_target(status_id))


def open_context(work_item_id, task, state_store, seats_by_capability, route):
    """Open the canonical review context; policy resolves its owner."""
    evidenced_reviewer = None
    if route == policy.PEER:
        executors = state_store.evidenced_executors(task)
        evidenced_reviewer = propose_peer_reviewer(task, seats_by_capability, executors)
    try:
        opened = state_store.open_review_context(
            work_item_id, task["revision"], opened_by="orchestrator",
            evidenced_reviewer=evidenced_reviewer)
    except Exception as exc:                              # noqa: BLE001
        raise ValidationRefused(VALIDATION_CONTEXT_REFUSED, str(exc))
    review = opened.get("review_context") or {}
    if not review.get("review_owner"):
        # The doctrine's waiting state: a route with no available validator waits
        # visibly rather than being downgraded to an easier one.
        raise ValidationRefused(
            VALIDATION_WAITING_FOR_REVIEWER,
            "%s is on the %s route with no eligible reviewer; it waits in its "
            "review status rather than being downgraded"
            % (work_item_id, review.get("review_type") or route))
    return opened


# ------------------------------------------------------------ the validator

def validation_objective(work_item_id, task, issue, execution, receipt_ref):
    """Bounded Product evidence for a validator. No control-plane mechanics.

    The executor's own brief is not reused verbatim: a validator needs what was
    asked for and what came back, not instructions to build it.
    """
    profile = task.get("execution_profile") or {}
    review = task.get("review_context") or {}
    lines = [
        "Validate %s against what it was asked to deliver." % work_item_id,
        "",
        "## What was asked (Jira %s)" % work_item_id,
        (issue or {}).get("summary") or "no summary recorded",
    ]
    description = ((issue or {}).get("description") or "").strip()
    if description:
        lines += ["", "## Acceptance criteria and requirement",
                  description[:2000].rstrip()]
    lines += ["", "## What the executor reported"]
    summary = getattr(execution, "summary", None) or "no executor summary recorded"
    lines.append(summary[:1500].rstrip())
    changed = [item.path for item in getattr(execution, "changed_files", ()) or ()]
    lines += ["", "## Changed surfaces", *(["- %s" % path for path in changed]
                                           or ["- none reported"])]
    tests = getattr(execution, "tests", ()) or ()
    lines += ["", "## Test evidence the executor returned"]
    lines += (["- %s -> %s" % (item.command, item.status.value) for item in tests]
              or ["- none reported"])
    lines += [
        "", "## Checks to perform",
        "- Confirm every acceptance criterion above is actually met by the work.",
        "- Confirm the change is confined to the declared surfaces.",
        "- Re-run the Product tests that cover this change and report what happened.",
        "- Report defects you find; do not fix them.",
        "", "## Your verdict",
        "Return exactly one verdict, pass or fail, as evidence of kind "
        "'%s' whose reference is the word pass or the word fail, with the "
        "evidence that supports it." % VERDICT_EVIDENCE_KIND,
        "", "Review reference: %s cycle %s; executor evidence: %s."
        % (review.get("review_type"), review.get("review_cycle"), receipt_ref),
        "Review only this work item. Report what you find and stop.",
    ]
    return "\n".join(lines).strip()


def build_validation_request(work_item_id, task, issue, execution, realized,
                             reviewer, review_ref, receipt_ref):
    """One read-only validation request, through the same contract and firewall."""
    review = task.get("review_context") or {}
    capability = _reviewer_capability(reviewer, task)
    workspace = Workspace(
        repository_root=realized["repository_root"],
        working_directory=realized["path"],
        mutation_mode=MutationMode.READ_ONLY,
        worktree_path=realized["path"],
        expected_revision=realized.get("expected_revision"),
    )
    context = task.get("operational_context") or {}
    reported = context.get("reported_environment") or {"locality": "unknown"}
    target = context.get("primary_target") or {"locality": "unknown"}
    return ExecutionRequest(
        invocation_id="validation-" + str(uuid.uuid4()),
        work_item_id=work_item_id, seat_id=reviewer,
        required_capability=capability,
        execution_kind=ExecutionKind.VALIDATION,
        objective=validation_objective(work_item_id, task, issue, execution,
                                       receipt_ref),
        role_contract_ref="agent/roles/%s.md" % capability,
        context_refs=("CLAUDE.md",),
        workspace=workspace,
        allowed_surfaces=tuple(task.get("surfaces") or ()),
        prohibited_actions=VALIDATOR_PROHIBITIONS,
        operating_mode="PRODUCT_EXECUTION",
        operating_mode_revision=0,
        claim_ref=None, execution_lease_id=None,
        review_context_ref=review_ref,
        reported_environment=ReportedEnvironment(
            reported.get("locality", "unknown"), reported.get("runtime"),
            reported.get("platform"), reported.get("environment_ref")),
        primary_target=ExecutionTarget(
            target.get("locality", "unknown"), target.get("runtime"),
            target.get("platform"), target.get("environment_ref"),
            bool(target.get("browser_automation", False)),
            target.get("launch_method"), target.get("launch_command"),
            target.get("source", "reported_environment")),
        validation_targets=(ValidationTarget(review.get("review_type") or "review",
                                             "review", True),),
        model_intent=ModelIntent.BALANCED,
        reasoning_effort=ReasoningEffort.HIGH,
        required_execution_features=frozenset({ExecutionFeature.REPOSITORY_READ,
                                               ExecutionFeature.SHELL}),
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        return_contract=ReturnContract(
            review.get("review_type") or "review", REQUIRED_EVIDENCE,
            REQUIRED_SECTIONS),
    )


def _reviewer_capability(reviewer, task):
    from agent.state import roster
    try:
        seats = roster.read()
    except Exception:                                     # noqa: BLE001
        seats = {}
    entry = seats.get(reviewer) or {}
    return (entry.get("role") or entry.get("capability")
            or (task.get("execution_profile") or {}).get("required_capability"))


def dispatch(request, providers, provider_override=None):
    """Select one compatible provider and invoke it once. No retry, no fallback."""
    selection = select_provider(request, providers, override=provider_override)
    if selection.provider is None:
        result = selection.failure_result(request)
    else:
        result = selection.provider.execute(request)
    return receive_execution_result(result), selection


def verdict_from(result):
    """Read the validator's verdict. Never inferred from a status.

    A provider that returned `completed` has reported that the validation ACT
    ran, not that the Product work passed. The verdict is an explicit claim or
    it does not exist.
    """
    if result.status is ExecutionStatus.PROVIDER_FAILED:
        raise ValidationRefused(
            VALIDATION_DISPATCH_FAILED,
            "the validator could not be invoked: %s" % result.summary)
    if result.status is ExecutionStatus.NEEDS_INPUT:
        raise ValidationRefused(
            VALIDATION_DISPATCH_FAILED,
            "the validator needs input before it can judge: %s"
            % (result.escalation.reason if result.escalation else result.summary))
    if result.status is ExecutionStatus.EXECUTION_FAILED:
        # The validation act failed. That is not the Product failing review.
        raise ValidationRefused(
            VALIDATION_DISPATCH_FAILED,
            "the validation act failed: %s" % result.summary)
    verdicts = {item.reference.strip().lower()
                for item in (result.evidence or ())
                if item.kind == VERDICT_EVIDENCE_KIND}
    if verdicts == {PASS}:
        return PASS
    if verdicts == {FAIL}:
        return FAIL
    raise ValidationRefused(
        VALIDATION_RESULT_MALFORMED,
        "the validator returned no single %r verdict (%s); a verdict is claimed "
        "explicitly or it does not exist"
        % (VERDICT_EVIDENCE_KIND, ", ".join(sorted(verdicts)) or "none"))


# ------------------------------------------------------------- the verdict

def record_verdict(work_item_id, task, state_store, reviewer, verdict, evidence_ref):
    """Through the canonical writer, which only the recorded owner may reach."""
    try:
        return state_store.record_review_result(work_item_id, task["revision"],
                                                reviewer, verdict, evidence_ref)
    except Exception as exc:                              # noqa: BLE001
        raise ValidationRefused(VALIDATION_CONTEXT_REFUSED, str(exc))


def remediate(work_item_id, task, state_store, jira_client, route, reviewer,
              evidence_ref):
    """Each FAIL has its own canonical semantics; none of them is generalised."""
    profile = task.get("execution_profile") or {}
    capability = profile.get("required_capability")
    if route == policy.PEER:
        # Execution authority moves to the reviewer, whose fix is SELF-reviewed.
        # There is no second PEER loop: the route itself becomes SELF.
        task = state_store.peer_fail_transfer(work_item_id, task["revision"],
                                              reviewer, evidence_ref)
        next_owner, next_route = reviewer, policy.SELF
    elif route == policy.SELF:
        task = state_store.self_fail_reentry(work_item_id, task["revision"],
                                             reviewer, evidence_ref)
        next_owner, next_route = reviewer, policy.SELF
    else:
        # QA FAIL returns the work to its executor; `qa` never executes and never
        # owns. Ownership is re-established by the ordinary claim on the next
        # execution, exactly as an unowned Ready item is.
        executors = state_store.evidenced_executors(task)
        next_owner = executors[0] if len(executors) == 1 else None
        next_route = policy.QA
    target = state_store.transition_target(capability=capability)
    issue = jira_client.get_issue(work_item_id)
    if str(issue.get("status_id")) != str(target):
        jira_client.transition_issue(work_item_id, _transition_id(target))
        issue = jira_client.get_issue(work_item_id)
    task = state_store.observe_lifecycle(work_item_id, task["revision"],
                                         str(issue.get("status_id")))
    return {"remediation_owner": next_owner, "remediation_route": next_route,
            "remediation_status": str(issue.get("status_id")), "task": task}


# --------------------------------------------------------------- the whole act

def run_validation(work_item_id, task, execution, realized, state_store,
                   jira_client, providers, issue=None, seats_by_capability=None,
                   provider_override=None, receipt_ref=None):
    """Enter review, dispatch the validator, record the verdict, remediate on fail."""
    if seats_by_capability is None:
        from agent.state import validate
        seats_by_capability = validate.seats_by_capability()
    release_ref = receipt_ref or ("execution of %s" % work_item_id)
    task, route = enter_review(work_item_id, task, state_store, jira_client,
                               release_ref)
    opened = open_context(work_item_id, task, state_store, seats_by_capability, route)
    review = opened.get("review_context") or {}
    reviewer = review["review_owner"]
    resolved_route = review.get("review_type") or route
    review_ref = "review:%s:%s:%s" % (work_item_id, resolved_route,
                                      review.get("review_cycle") or 1)
    evidence = {"validation_route": resolved_route, "reviewer": reviewer,
                "review_cycle": review.get("review_cycle") or 1,
                "review_context_ref": review_ref}

    # Read the issue only once a reviewer actually exists: a route that refuses
    # or waits should not spend a Jira read it will not use.
    issue = issue if issue is not None else jira_client.get_issue(work_item_id)
    request = build_validation_request(work_item_id, opened, issue, execution,
                                       realized, reviewer, review_ref, release_ref)
    result, selection = dispatch(request, providers, provider_override)
    evidence.update({"validation_invocation_id": request.invocation_id,
                     "validation_provider": result.provider_id,
                     "validation_summary": result.summary,
                     "validation_result_payload": normalized_result_payload(result)})

    verdict = verdict_from(result)
    evidence["verdict"] = verdict
    evidence_ref = "%s verdict %s by %s: %s" % (
        resolved_route, verdict, reviewer, (result.summary or "")[:200])
    settled = record_verdict(work_item_id, opened, state_store, reviewer, verdict,
                             evidence_ref)
    evidence["task"] = settled
    if verdict == PASS:
        evidence["outcome"] = VALIDATION_PASSED
        return evidence
    evidence["outcome"] = VALIDATION_FAILED
    evidence.update(remediate(work_item_id, settled, state_store, jira_client,
                              resolved_route, reviewer, evidence_ref))
    return evidence
