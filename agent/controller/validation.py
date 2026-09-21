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

import re
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
from agent.qa import gate as deterministic_gate
from agent.qa.results import GATE_INFRA
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
# A validator on this very cycle stopped at a native permission boundary and a
# continuation is prepared; the answer is a DECISION_RESPONSE, not a new wake.
VALIDATION_CONTINUATION_PENDING = "validation-continuation-pending"
# The deterministic gate could not RUN — toolchain, device, missing tool,
# timeout. Not a Product failure, not a verdict, no review cycle spent: the
# context stays pending with its owner and the act is re-run once the
# infrastructure is repaired. (2026-09-15, QA layer integration.)
VALIDATION_INFRASTRUCTURE_FAILED = "validation-infrastructure-failed"

VERDICT_EVIDENCE_KIND = "verdict"
# The Claude CLI transport carries result TEXT and cannot emit structured
# evidence claims, so a verdict expressed only as an evidence claim is
# unsatisfiable over the one provider that exists. The declaration below is the
# transport-compatible equivalent: the marker, then the verdict word with
# nothing but markup between them. Prose before the word does not match, so a
# hedged answer is refused rather than read generously.
_VERDICT_DECLARATION = re.compile(
    r"\bVERDICT\b[\s:*_#>.\-]*\b(pass|fail)\b", re.IGNORECASE)
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
    """Open the canonical review context; policy resolves its owner.

    A PEER FAIL transfer already opens the reviewer's SELF review as part of its
    one atomic write, so an existing PENDING context with a resolved owner is
    that review — not a second one to create. `open_review_context` would
    refuse it as `review-already-open`, which is correct for it and wrong here.
    """
    existing = task.get("review_context")
    if (isinstance(existing, dict) and existing.get("review_result") == "pending"
            and existing.get("review_owner")):
        return task
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

def validation_objective(work_item_id, task, issue, execution, receipt_ref,
                         deterministic=None):
    """Bounded Product evidence for a validator. No control-plane mechanics.

    The executor's own brief is not reused verbatim: a validator needs what was
    asked for and what came back, not instructions to build it.

    `deterministic` is the gate that already ran (`agent.qa.gate`). Its results
    are rendered as evidence the reviewer INTERPRETS — status, reference, a
    bounded tail — never as logs to wade through and never as layers to re-run.
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
    if execution is None:
        # An already-open review (T-091): the work reached the branch outside
        # the wake seam, so there is no execution receipt to summarise. Say so;
        # a synthesised report would be the fabricated evidence T-090 refuses.
        lines.append("No execution receipt exists for this work: it reached the "
                     "integration branch outside the Thebes wake seam, so there is "
                     "no executor summary, no changed-file claim and no test claim "
                     "to interpret. Judge the work itself, in the tree you are "
                     "given, against the acceptance criteria above.")
    else:
        summary = getattr(execution, "summary", None) or "no executor summary recorded"
        lines.append(summary[:1500].rstrip())
    changed = [item.path for item in getattr(execution, "changed_files", ()) or ()]
    lines += ["", "## Changed surfaces", *(["- %s" % path for path in changed]
                                           or ["- none reported"])]
    declared = task.get("surfaces")
    lines += ["", "## Declared surfaces (assessed before execution)",
              *(["- %s" % path for path in declared] if declared
                else ["- none declared" if declared == [] else "- not assessed"])]
    tests = getattr(execution, "tests", ()) or ()
    lines += ["", "## Test evidence the executor returned"]
    lines += (["- %s -> %s" % (item.command, item.status.value) for item in tests]
              or ["- none reported"])
    gate_ran = bool(deterministic is not None and deterministic.runs)
    if deterministic is not None:
        lines += ["", "## Deterministic test evidence (run by Thebes before this review)",
                  deterministic.render()]
        if gate_ran:
            lines += ["",
                      "These layers already ran by command; their full output is at "
                      "the artifact reference beside each. Do NOT re-run them. "
                      "Interpret them: a product_defect result is evidence for fail "
                      "unless you can show the assertion itself is wrong; a pass "
                      "result covers what that layer tests and nothing more."]
    lines += [
        "", "## Checks to perform",
        "- Confirm every acceptance criterion above is actually met by the work.",
        "- Confirm the change is confined to the declared surfaces.",
        ("- Run only the Product tests NOT already covered by the deterministic "
         "evidence above, if any criterion needs them, and report what happened."
         if gate_ran else
         "- Re-run the Product tests that cover this change and report what happened."),
        "- Report defects you find; do not fix them.",
        "", "## Your verdict",
        "Open your reply with a VERDICT section whose very first word is pass or "
        "fail, like this and nothing else before it:",
        "", "## VERDICT", "pass", "",
        "Then give the evidence that supports it. Exactly one verdict: a hedged "
        "or absent one is read as no verdict at all.",
        "", "Review reference: %s cycle %s; executor evidence: %s."
        % (review.get("review_type"), review.get("review_cycle"), receipt_ref),
        "Review only this work item. Report what you find and stop.",
    ]
    return "\n".join(lines).strip()


def build_validation_request(work_item_id, task, issue, execution, realized,
                             reviewer, review_ref, receipt_ref, deterministic=None):
    """One read-only validation request, through the same contract and firewall.

    Effort follows the evidence: when the deterministic gate is decisive the
    reviewer interprets (cost-efficient, low effort); when no layer applied the
    reviewer is the test and keeps full effort. The gate never sets the verdict.
    """
    review = task.get("review_context") or {}
    capability = _reviewer_capability(reviewer, task)
    if deterministic is not None:
        model_intent, reasoning_effort = deterministic.reviewer_effort()
    else:
        model_intent, reasoning_effort = ModelIntent.BALANCED, ReasoningEffort.HIGH
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
                                       receipt_ref, deterministic=deterministic),
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
        model_intent=model_intent,
        reasoning_effort=reasoning_effort,
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
    if not verdicts:
        # No structured claim: read the declaration the brief asks for instead.
        verdicts = {match.group(1).lower()
                    for match in _VERDICT_DECLARATION.finditer(result.summary or "")}
    if verdicts == {PASS}:
        return PASS
    if verdicts == {FAIL}:
        return FAIL
    raise ValidationRefused(
        VALIDATION_RESULT_MALFORMED,
        "the validator declared no single verdict (%s); a verdict is claimed "
        "explicitly or it does not exist"
        % (", ".join(sorted(verdicts)) or "none"))


# ------------------------------------------------------------- the verdict

def _record_validation_receipt(request, result, review_ref, selection, state_store,
                               continuation_of=None, approval_ids=None):
    """Durable evidence of one validation act. Never a verdict by itself."""
    try:
        record = state_store.record_execution_receipt(
            request.invocation_id, request.work_item_id, request.seat_id, None,
            normalized_result_payload(result),
            provider_selection=selection.receipt_evidence(),
            continuation_of=continuation_of,
            approval_id=(approval_ids[0] if approval_ids else None),
            approval_ids=list(approval_ids) if approval_ids else None,
            review_context_ref=review_ref)
    except Exception as exc:                              # noqa: BLE001
        return "refused: %s" % exc
    return record["execution_receipt_id"]


def _prepare_validation_continuation(request, result, review_ref, realized,
                                     state_store):
    """Make an approved validator resume possible, on the same review context."""
    from agent.controller.continuation import denied_permissions
    receipt = {"status": "needs_input", "provider_id": result.provider_id,
               "invocation_id": request.invocation_id,
               "normalized_result": normalized_result_payload(result)}
    permissions = denied_permissions(receipt)
    if not permissions or not result.continuation_ref:
        return "not-continuable"
    try:
        record = state_store.record_execution_continuation_preparation(
            original_invocation_id=request.invocation_id,
            work_item_id=request.work_item_id, seat_id=request.seat_id,
            claude_session_id=result.continuation_ref, permission=permissions[0],
            repository_root=realized["repository_root"],
            working_directory=request.workspace.working_directory,
            worktree_path=realized["path"], branch=realized["branch"],
            expected_revision=realized["expected_revision"],
            authorization_ref=review_ref,
            authorization_scope=(
                "resume the same validation invocation on the same review context "
                "after the native permission boundary: %s" % ", ".join(permissions)),
            review_context_ref=review_ref)
    except Exception as exc:                              # noqa: BLE001
        return "refused: %s" % exc
    return record["execution_continuation_id"]


def build_prepared_validation_request(preparation, task, issue):
    """The same validation act, resumed. Same review context, same workspace.

    Deliberately short: the provider session is resumed, so the validator still
    holds everything it already read. Replaying the original brief would invite
    it to start the review over.
    """
    review = task.get("review_context") or {}
    reviewer = preparation["seat_id"]
    capability = _reviewer_capability(reviewer, task)
    workspace = Workspace(
        repository_root=preparation["repository_root"],
        working_directory=preparation["working_directory"],
        mutation_mode=MutationMode.READ_ONLY,
        worktree_path=preparation["worktree_path"],
        expected_revision=preparation["expected_revision"])
    context = task.get("operational_context") or {}
    reported = context.get("reported_environment") or {"locality": "unknown"}
    target = context.get("primary_target") or {"locality": "unknown"}
    return ExecutionRequest(
        invocation_id="validation-continuation-" + preparation["execution_continuation_id"][-24:],
        work_item_id=preparation["work_item_id"], seat_id=reviewer,
        required_capability=capability,
        execution_kind=ExecutionKind.VALIDATION,
        objective=("Continue the same validation of %s you already began, on the "
                   "same Product evidence. Finish the checks you were making and "
                   "return your verdict; do not restart the review or widen it.\n\n"
                   "Open your reply with a VERDICT section whose very first word "
                   "is pass or fail, then the evidence that supports it. Exactly "
                   "one verdict: a hedged or absent one is read as no verdict."
                   % preparation["work_item_id"]),
        role_contract_ref="agent/roles/%s.md" % capability,
        context_refs=("CLAUDE.md",),
        workspace=workspace,
        allowed_surfaces=tuple(task.get("surfaces") or ()),
        prohibited_actions=VALIDATOR_PROHIBITIONS,
        operating_mode="PRODUCT_EXECUTION", operating_mode_revision=0,
        claim_ref=None, execution_lease_id=None,
        review_context_ref=preparation["review_context_ref"],
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
        model_intent=ModelIntent.BALANCED, reasoning_effort=ReasoningEffort.HIGH,
        required_execution_features=frozenset({ExecutionFeature.REPOSITORY_READ,
                                               ExecutionFeature.SHELL}),
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        return_contract=ReturnContract(review.get("review_type") or "review",
                                       REQUIRED_EVIDENCE, REQUIRED_SECTIONS))


def resume_validation(work_item_id, state_store, jira_client, transport=None,
                      interventions=None):
    """Resume an approved validator, take its verdict, and settle the review.

    Reuses the Product-execution continuation mechanism wholesale: the same
    approval records, the same exact-grant composition with its replay and
    terminal protection, the same provider/session binding, and the same
    receipt lineage. What differs is only the authority — a review context
    rather than a claim and lease — because a reviewer holds neither.
    """
    from agent.execution.claude import ClaudeCliTransport, ClaudeProvider
    task = state_store.read("task", work_item_id)
    review = (task or {}).get("review_context") or {}
    if review.get("review_result") != "pending":
        raise ValidationRefused(VALIDATION_ALREADY_SETTLED,
                                "%s has no pending review to resume" % work_item_id)
    preparation = _pending_validation_preparation(work_item_id, review, state_store)
    if preparation is None:
        raise ValidationRefused(VALIDATION_CONTEXT_REFUSED,
                                "%s has no prepared validation continuation"
                                % work_item_id)
    original = preparation["original_invocation_id"]
    prior = next((r for r in state_store.read_all("execution_receipt")
                  if r.get("continuation_of_invocation_id") == original
                  and r.get("status") != "needs_input"), None)
    if prior is not None:
        # The validator already answered. Its verdict is durable evidence, so
        # the review settles from that receipt rather than re-waking a reviewer
        # over a judgement it has already made.
        return _settle_from_receipt(work_item_id, task, review, preparation, prior,
                                    state_store, jira_client)
    approvals = state_store.compose_execution_approvals(original)
    permissions = tuple(record["permission"] for record in approvals)
    provider = ClaudeProvider(transport or ClaudeCliTransport(),
                              session_ref=preparation["claude_session_id"],
                              approved_permissions=permissions)
    request = build_prepared_validation_request(preparation, task,
                                                jira_client.get_issue(work_item_id))
    result = receive_execution_result(provider.execute(request))
    reviewer = preparation["seat_id"]
    review_ref = preparation["review_context_ref"]
    evidence = {"validation_route": review.get("review_type"), "reviewer": reviewer,
                "review_cycle": review.get("review_cycle") or 1,
                "review_context_ref": review_ref, "approved_permissions": list(permissions),
                "validation_invocation_id": request.invocation_id,
                "validation_provider": result.provider_id,
                "validation_summary": result.summary,
                "validation_receipt": _record_validation_receipt(
                    request, result, review_ref, _ResumedSelection(), state_store,
                    continuation_of=original,
                    approval_ids=tuple(r["execution_approval_id"] for r in approvals))}
    verdict = verdict_from(result)
    evidence["verdict"] = verdict
    evidence_ref = "%s verdict %s by %s: %s" % (
        review.get("review_type"), verdict, reviewer, (result.summary or "")[:200])
    settled = record_verdict(work_item_id, task, state_store, reviewer, verdict,
                             evidence_ref)
    evidence["task"] = settled
    if verdict == PASS:
        evidence["outcome"] = VALIDATION_PASSED
        return evidence
    evidence["outcome"] = VALIDATION_FAILED
    evidence.update(remediate(work_item_id, settled, state_store, jira_client,
                              review.get("review_type"), reviewer, evidence_ref))
    return evidence


def _settle_from_receipt(work_item_id, task, review, preparation, receipt,
                         state_store, jira_client):
    """Take the verdict a recorded validation result already carries."""
    from agent.execution.receipt import execution_result_from_payload
    result = execution_result_from_payload(receipt["normalized_result"])
    reviewer = preparation["seat_id"]
    verdict = verdict_from(result)
    evidence = {"validation_route": review.get("review_type"), "reviewer": reviewer,
                "review_cycle": review.get("review_cycle") or 1,
                "review_context_ref": preparation["review_context_ref"],
                "approved_permissions": [],
                "validation_invocation_id": receipt["invocation_id"],
                "validation_provider": receipt.get("provider_id"),
                "validation_summary": result.summary,
                "validation_receipt": receipt["execution_receipt_id"],
                "validation_source": "recorded-receipt", "verdict": verdict}
    evidence_ref = "%s verdict %s by %s: %s" % (
        review.get("review_type"), verdict, reviewer, (result.summary or "")[:200])
    settled = record_verdict(work_item_id, task, state_store, reviewer, verdict,
                             evidence_ref)
    evidence["task"] = settled
    if verdict == PASS:
        evidence["outcome"] = VALIDATION_PASSED
        return evidence
    evidence["outcome"] = VALIDATION_FAILED
    evidence.update(remediate(work_item_id, settled, state_store, jira_client,
                              review.get("review_type"), reviewer, evidence_ref))
    return evidence


class _ResumedSelection:
    """The provider was fixed by the approval, not chosen again."""

    def receipt_evidence(self):
        return {"primary_provider_id": "claude-code", "selected_provider_id": "claude-code"}


def _pending_validation_preparation(work_item_id, review, state_store):
    """The preparation for the review cycle currently open, and no other."""
    ref = "review:%s:%s:%s" % (work_item_id, review.get("review_type"),
                               review.get("review_cycle") or 1)
    matches = [record for record
               in state_store.read_all("execution_continuation_preparation")
               if record.get("work_item_id") == work_item_id
               and record.get("review_context_ref") == ref]
    if not matches:
        return None
    return sorted(matches, key=lambda record: record.get("created_at") or "")[-1]


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
        # There is no second PEER loop: the route itself becomes SELF. The cycle
        # is pinned so a replayed transfer cannot advance it twice.
        review = task.get("review_context") or {}
        task = state_store.peer_fail_transfer(
            work_item_id, task["revision"], reviewer, evidence_ref,
            expected_cycle=review.get("review_cycle"))
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
                   provider_override=None, receipt_ref=None, deterministic=None):
    """Enter review, run the deterministic gate, dispatch the validator, record
    the verdict, remediate on fail.

    `deterministic` is the gate function (default `agent.qa.gate.
    run_deterministic_gate`); tests inject a double. It runs after the review
    context exists and before the reviewer is dispatched, and an
    infrastructure failure refuses the whole act with
    `VALIDATION_INFRASTRUCTURE_FAILED` — no dispatch, no verdict, no cycle spent.
    """
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

    # The deterministic gate: commands, not a model. It runs inside the named
    # review cycle and before any reviewer exists as a process. An
    # infrastructure failure is refused here — before the Jira read it would
    # not use and before a dispatch it must not make — and spends nothing.
    gate_fn = deterministic or deterministic_gate.run_deterministic_gate
    gate = gate_fn(work_item_id, opened, realized, execution)
    evidence["deterministic_gate"] = gate.as_payload()
    # Only a gate that learned NOTHING refuses the act. A gate where one layer
    # broke and another answered is DEGRADED: it proceeds, carrying real
    # evidence and an explicit statement of what is missing, and it is never
    # decisive — so the reviewer keeps full effort rather than reading partial
    # coverage as whole. (2026-09-16: before this, one broken local layer
    # refused every validation on the machine.)
    if gate.outcome == GATE_INFRA:
        raise ValidationRefused(
            VALIDATION_INFRASTRUCTURE_FAILED,
            "the deterministic gate could not run for %s (%s); this is a test-"
            "infrastructure failure, not a Product failure — the %s review stays "
            "pending at cycle %s with its owner, no verdict was recorded, and the "
            "act is re-run once the infrastructure is repaired"
            % (work_item_id,
               "; ".join("%s: %s" % (lid, why) for lid, why in gate.unavailable)
               or "no layer executed",
               resolved_route, review.get("review_cycle") or 1))
    if gate.unavailable:
        evidence["deterministic_gate_unavailable"] = [
            {"layer_id": lid, "reason": why} for lid, why in gate.unavailable]

    return _dispatch_and_settle(work_item_id, opened, execution, realized, state_store,
                                jira_client, providers, issue, provider_override,
                                release_ref, gate, evidence)


def run_open_review(work_item_id, task, realized, state_store, jira_client, providers,
                    issue=None, seats_by_capability=None, provider_override=None,
                    deterministic=None, receipt_ref=None):
    """Dispatch a review context that is ALREADY open and owned. (T-091)

    The complement of `run_validation` for work whose execution Thebes did not
    witness in this process: the item is canonically in review, `po` opened the
    context, and the owner was resolved — by policy or by a CEO-named
    `resolve_review_owner`. There is no ownership to release, no Jira transition
    to make and no executor result to summarise, so this skips `enter_review`
    and `open_context` entirely and REFUSES rather than repairs when the context
    is not in the state it expects:

        no context, or a settled one   -> VALIDATION_ALREADY_SETTLED /
                                          VALIDATION_CONTEXT_REFUSED
        pending with no owner          -> VALIDATION_WAITING_FOR_REVIEWER
                                          (doctrine: work is allowed to wait)

    Everything after that point is the same tail `run_validation` runs: the
    deterministic gate, the read-only validation request, the receipt, the
    verdict through `record_review_result`, and the canonical remediation on
    FAIL. Nothing here chooses a route, a reviewer or a verdict.
    """
    del seats_by_capability                          # owner is already recorded
    review = task.get("review_context") or {}
    if not review:
        raise ValidationRefused(
            VALIDATION_CONTEXT_REFUSED,
            "%s has no open review context; a review is opened by the canonical "
            "validation path or by po, never by this act" % work_item_id)
    if review.get("review_result") != "pending":
        raise ValidationRefused(
            VALIDATION_ALREADY_SETTLED,
            "%s's %s review is already %r at cycle %s; a settled review is not "
            "re-dispatched" % (work_item_id, review.get("review_type"),
                               review.get("review_result"), review.get("review_cycle")))
    reviewer = review.get("review_owner")
    resolved_route = review.get("review_type")
    if not reviewer:
        raise ValidationRefused(
            VALIDATION_WAITING_FOR_REVIEWER,
            "%s's %s review is waiting with no owner; name one through "
            "store.resolve_review_owner — this act never picks a reviewer"
            % (work_item_id, resolved_route))
    review_ref = "review:%s:%s:%s" % (work_item_id, resolved_route,
                                      review.get("review_cycle") or 1)
    # The verdict cites the review context and the tree the reviewer read
    # (`integration:<branch>@<revision>`, supplied by the caller): there is no
    # execution receipt for work Thebes did not wake, and inventing one would
    # be a second kind of fabricated evidence.
    release_ref = "open review context %s; tree %s; executor evidence: %s" % (
        review_ref, receipt_ref or "not stated",
        ", ".join(sorted({e.get("seat_id") for e in
                          (task.get("executor_evidence") or [])
                          if e.get("seat_id")})) or "none recorded")
    evidence = {"validation_route": resolved_route, "reviewer": reviewer,
                "review_cycle": review.get("review_cycle") or 1,
                "review_context_ref": review_ref}
    # Idempotency: a validation act on this exact cycle that already returned a
    # terminal result is settled from its receipt, never re-woken. A second
    # VALIDATE after a crash between receipt and verdict costs no invocation.
    recorded = _terminal_validation_receipt(work_item_id, review_ref, state_store)
    if recorded is not None:
        return _settle_from_receipt(work_item_id, task, review,
                                    {"seat_id": reviewer, "review_context_ref": review_ref},
                                    recorded, state_store, jira_client)
    gate_fn = deterministic or deterministic_gate.run_deterministic_gate
    gate = gate_fn(work_item_id, task, realized, None)
    evidence["deterministic_gate"] = gate.as_payload()
    if gate.outcome == GATE_INFRA:
        raise ValidationRefused(
            VALIDATION_INFRASTRUCTURE_FAILED,
            "the deterministic gate could not run for %s (%s); the %s review stays "
            "pending at cycle %s with its owner and no verdict was recorded"
            % (work_item_id,
               "; ".join("%s: %s" % (lid, why) for lid, why in gate.unavailable)
               or "no layer executed",
               resolved_route, review.get("review_cycle") or 1))
    if gate.unavailable:
        evidence["deterministic_gate_unavailable"] = [
            {"layer_id": lid, "reason": why} for lid, why in gate.unavailable]
    return _dispatch_and_settle(work_item_id, task, None, realized, state_store,
                                jira_client, providers, issue, provider_override,
                                release_ref, gate, evidence)


def _terminal_validation_receipt(work_item_id, review_ref, state_store):
    """The recorded terminal result of a validation act on this exact review
    cycle, if one exists. A needs_input result is not terminal and is handled
    by the prepared-continuation precondition instead."""
    reader = getattr(state_store, "read_all", None)
    if reader is None:
        return None
    matches = []
    for record in reader("execution_receipt"):
        if record.get("work_item_id") != work_item_id:
            continue
        if record.get("review_context_ref") != review_ref:
            continue
        payload = record.get("normalized_result") or {}
        # Only a COMPLETED validation act can carry a verdict. A needs_input
        # result is handled by the prepared-continuation precondition, and a
        # provider failure (api_error, timeout, execution_failed) is not a
        # settled review: re-dispatching it is exactly the right thing to do.
        # (2026-09-21: KAN-290's review was refused as "settled" by its own
        # 429-failed receipt until this line existed.)
        if payload.get("status") != ExecutionStatus.COMPLETED.value:
            continue
        matches.append(record)
    if not matches:
        return None
    return sorted(matches, key=lambda record: record.get("created_at") or "")[-1]


def _dispatch_and_settle(work_item_id, opened, execution, realized, state_store,
                         jira_client, providers, issue, provider_override,
                         release_ref, gate, evidence):
    """The shared tail: request, dispatch, receipt, verdict, remediation.

    `opened` is the task carrying the review context to dispatch; `execution`
    is the executor's normalized result when this process witnessed one, or
    None for an already-open review (`run_open_review`).
    """
    review = opened.get("review_context") or {}
    reviewer = review["review_owner"]
    resolved_route = evidence["validation_route"]
    review_ref = evidence["review_context_ref"]
    # Read the issue only once a reviewer actually exists: a route that refuses
    # or waits should not spend a Jira read it will not use.
    issue = issue if issue is not None else jira_client.get_issue(work_item_id)
    request = build_validation_request(work_item_id, opened, issue, execution,
                                       realized, reviewer, review_ref, release_ref,
                                       deterministic=gate)
    result, selection = dispatch(request, providers, provider_override)
    payload = normalized_result_payload(result)
    evidence.update({"validation_invocation_id": request.invocation_id,
                     "validation_provider": result.provider_id,
                     "validation_summary": result.summary,
                     "validation_result_payload": payload})
    # The validation invocation gets a receipt of its own, authorized by the
    # review context rather than a lease. Without it nothing could bind an
    # approval or a continuation to a validator that stopped at a native
    # permission boundary — which is exactly what happened on KAN-183.
    evidence["validation_receipt"] = _record_validation_receipt(
        request, result, review_ref, selection, state_store)
    if result.status is ExecutionStatus.NEEDS_INPUT:
        evidence["validation_continuation_prepared"] = _prepare_validation_continuation(
            request, result, review_ref, realized, state_store)

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
