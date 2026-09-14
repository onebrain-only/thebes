"""Complete one validated, integrated work item: Jira Done, then cleanup.

Every act here already exists. `board.assert_transition_target` refuses a legacy
or unknown destination, `board.transition_for` names the exact Jira transition,
`jira.transition_issue` performs it, `store.observe_lifecycle` records what Jira
then says, `store.release` gives up ownership, and the workspace policy from the
allocation milestone decides the tree's fate. There is no second lifecycle
engine here.

What was missing is the ordering and the gate:

    evidence?   an integration receipt is ORCHESTRATION EVIDENCE, never lifecycle
                authority. It is validated against the work item it claims to
                belong to, and a failed, conflicted or foreign one proves nothing.
    completable? `queue.completion_reasons` already answers this and is consumed
                rather than re-derived. A provider status does not complete work,
                and neither does the mere existence of a commit.
    confirmed?  Jira is the lifecycle authority, so Persistent State is written
                from an authoritative RE-READ after the transition, never
                optimistically from the fact that a transition was accepted.

Ownership survives every failure. A Jira transition that does not land leaves
the owner exactly where it was, because the work is not finished — and a Jira
failure is never a reason to re-run a provider.
"""

from agent.state import board, queue


COMPLETED = "completed"
ALREADY_DONE = "already-done"
LIFECYCLE_NOT_COMPLETABLE = "lifecycle-not-completable"
INTEGRATION_EVIDENCE_INVALID = "integration-evidence-invalid"
JIRA_TRANSITION_FAILED = "jira-transition-failed"
JIRA_STATE_DIVERGED_AFTER_TRANSITION = "jira-state-diverged-after-transition"
OWNERSHIP_RELEASE_FAILED = "ownership-release-failed"
FINALIZATION_INCOMPLETE = "finalization-incomplete"

TERMINAL_SUCCESS = (COMPLETED, ALREADY_DONE)

# The integration outcomes that prove the Product side is finished. A conflict,
# an attribution failure or a commit failure prove the opposite.
COMPLETABLE_INTEGRATION_OUTCOMES = ("integrated", "already-present",
                                    "no-product-commit-required")
PROTECTED_BRANCHES = ("main", "master", "origin/main", "origin/master")


class CompletionRefused(Exception):
    """A bounded, named refusal. None of these is a provider or Product failure."""

    def __init__(self, outcome, detail):
        super().__init__("%s: %s" % (outcome, detail))
        self.outcome = outcome
        self.detail = detail


# ------------------------------------------------------- integration evidence

def valid_integration_receipt(work_item_id, task, receipts):
    """The one receipt that proves this work item's Product side is finished.

    A receipt is evidence of an orchestration act, not permission to complete.
    It is checked against the work item it claims, the project's integration
    branch, and its own outcome; anything foreign, failed or malformed is
    refused rather than interpreted generously.
    """
    if not receipts:
        raise CompletionRefused(
            INTEGRATION_EVIDENCE_INVALID,
            "%s has no integration receipt; nothing proves its Product work "
            "reached the integration branch" % work_item_id)
    owner = (task.get("ownership") or {}).get("seat_id")
    usable, refusals = [], []
    for receipt in receipts:
        problem = _receipt_problem(work_item_id, owner, receipt)
        if problem:
            refusals.append(problem)
        else:
            usable.append(receipt)
    if not usable:
        raise CompletionRefused(
            INTEGRATION_EVIDENCE_INVALID,
            "%s has no usable integration receipt: %s"
            % (work_item_id, "; ".join(refusals)))
    # The most recent usable receipt is the current truth; earlier refused
    # attempts stay on the record and are not erased by a later success.
    return sorted(usable, key=lambda r: r.get("created_at") or "")[-1]


def _receipt_problem(work_item_id, owner, receipt):
    if not isinstance(receipt, dict):
        return "a malformed receipt is not evidence"
    if receipt.get("work_item_id") != work_item_id:
        return ("receipt %s belongs to %s, not %s"
                % (receipt.get("integration_receipt_id"),
                   receipt.get("work_item_id"), work_item_id))
    if owner and receipt.get("seat_id") != owner:
        return ("receipt %s was produced by %s, which does not own %s"
                % (receipt.get("integration_receipt_id"), receipt.get("seat_id"),
                   work_item_id))
    outcome = receipt.get("outcome")
    if outcome not in COMPLETABLE_INTEGRATION_OUTCOMES:
        return "receipt outcome %r does not prove integration" % outcome
    if receipt.get("remediation_required"):
        return "receipt still requires Product remediation"
    branch = receipt.get("integration_branch")
    if outcome in ("integrated", "already-present"):
        if branch in PROTECTED_BRANCHES:
            return "receipt names protected integration branch %r" % branch
        for field in ("product_commit", "integrated_as"):
            if not receipt.get(field):
                return "receipt claims integration but records no %s" % field
    elif outcome == "no-product-commit-required":
        if receipt.get("product_commit"):
            return "a no-commit receipt cannot also carry a Product commit"
        if receipt.get("attributed_files"):
            return "a no-commit receipt cannot also carry attributed files"
    return None


# ------------------------------------------------------------ the gate

def completion_reasons(task, interventions=None):
    """Why this item may NOT be completed. Empty = canonical policy permits it.

    Straight through to `queue.completion_reasons`; completion is exactly the
    question that function exists to answer, and a second answer here would be a
    second authority.
    """
    return tuple(queue.completion_reasons(task, interventions))


def assert_completable(task, interventions=None):
    """Refuse unless canonical policy permits it, or it is already done."""
    reasons = completion_reasons(task, interventions)
    if not reasons:
        return False
    if tuple(reasons) == ("already-done",):
        # Not a refusal: the idempotent case. Everything else about the item is
        # complete and Jira has simply already been moved.
        return True
    raise CompletionRefused(
        LIFECYCLE_NOT_COMPLETABLE,
        "%s may not be completed: %s"
        % (task.get("work_item_id"), ", ".join(reasons)))


# ---------------------------------------------------------- Jira lifecycle

def complete_lifecycle(work_item_id, task, receipts, state_store, jira_client,
                       interventions=None, release_ref=None):
    """Transition to Done, confirm it from Jira, then reconcile and release.

    Returns the evidence of what happened. Raises `CompletionRefused` with an
    exact outcome for anything that stops it, having changed nothing it cannot
    justify: ownership in particular survives every failure below.
    """
    receipt = valid_integration_receipt(work_item_id, task, receipts)
    locally_done = assert_completable(task, interventions)
    seat_id = (task.get("ownership") or {}).get("seat_id")
    evidence = {
        "work_item_id": work_item_id, "seat_id": seat_id,
        "integration_receipt_id": receipt.get("integration_receipt_id"),
        "product_commit": receipt.get("product_commit"),
        "integrated_as": receipt.get("integrated_as"),
        "integration_branch": receipt.get("integration_branch"),
        "integration_outcome": receipt.get("outcome"),
        "validation_route": (task.get("execution_profile") or {}).get("validation_route"),
        "validation_result": (task.get("review_context") or {}).get("review_result"),
        "jira_transition_performed": False,
    }

    target = board.assert_transition_target(board.DONE_STATUS_ID)
    observed = jira_client.get_issue(work_item_id)
    before = str(observed.get("status_id"))
    evidence["jira_status_before"] = before

    if before == target:
        # Already Done in the authority. Idempotent: no second transition.
        evidence["jira_status_after"] = before
    else:
        if locally_done:
            # Local state says done, Jira does not. That is a reconciliation
            # question, not a transition to fire blindly.
            raise CompletionRefused(
                JIRA_STATE_DIVERGED_AFTER_TRANSITION,
                "%s is locally done but Jira reports %s; reconcile before "
                "completing" % (work_item_id, board.name_for(before) or before))
        transition_id = board.transition_for(target)
        try:
            jira_client.transition_issue(work_item_id, transition_id)
        except Exception as exc:                          # noqa: BLE001
            # Ownership is untouched: the work is not finished, and a Jira
            # failure is never a reason to re-run a provider.
            raise CompletionRefused(
                JIRA_TRANSITION_FAILED,
                "%s could not be transitioned to Done: %s" % (work_item_id, exc))
        evidence["jira_transition_performed"] = True
        evidence["jira_transition_id"] = transition_id

        # Jira is the lifecycle authority, so what it says AFTER the transition
        # is the only thing worth recording. An accepted transition is not proof.
        confirmed = jira_client.get_issue(work_item_id)
        after = str(confirmed.get("status_id"))
        evidence["jira_status_after"] = after
        if after != target:
            raise CompletionRefused(
                JIRA_STATE_DIVERGED_AFTER_TRANSITION,
                "%s accepted the transition but Jira now reports %s; ownership "
                "is preserved and no local Done is recorded"
                % (work_item_id, board.name_for(after) or after))

    reconciled = state_store.observe_lifecycle(
        work_item_id, task["revision"], evidence["jira_status_after"])
    evidence["lifecycle"] = (reconciled.get("lifecycle") or {}).get("canonical")
    if evidence["lifecycle"] != "done":
        raise CompletionRefused(
            FINALIZATION_INCOMPLETE,
            "%s observed %s after Jira Done; state was not reconciled"
            % (work_item_id, evidence["lifecycle"]))

    evidence["ownership_status"] = _release_ownership(
        work_item_id, seat_id, reconciled, state_store,
        release_ref or _release_ref(receipt))
    evidence["open_leases"] = _open_leases(work_item_id, state_store)
    evidence["outcome"] = ALREADY_DONE if before == target else COMPLETED
    return evidence


def _release_ref(receipt):
    landed = receipt.get("integrated_as")
    if landed:
        return "integration %s on %s" % (landed[:7], receipt.get("integration_branch"))
    return "integration %s" % receipt.get("outcome")


def _release_ownership(work_item_id, seat_id, task, state_store, release_ref):
    """Only after authoritative Done. Never before, and never silently skipped."""
    if (task.get("ownership") or {}).get("seat_id") is None:
        return "already-released"
    try:
        state_store.release(work_item_id, seat_id, task["revision"], release_ref,
                            authority="orchestrator")
    except Exception as exc:                              # noqa: BLE001
        raise CompletionRefused(
            OWNERSHIP_RELEASE_FAILED,
            "%s reached Done but ownership could not be released: %s"
            % (work_item_id, exc))
    return "released"


def _open_leases(work_item_id, state_store):
    """Leases still open for this item. Reported, never force-closed here."""
    try:
        leases = state_store.read_all("execution_lease")
    except Exception:                                     # noqa: BLE001
        return []
    return sorted(lease.get("execution_lease_id") for lease in leases
                  if lease.get("work_item_id") == work_item_id
                  and not lease.get("closed_at"))
