"""Land validated Product work on the integration branch, and nothing else.

Every git act here already exists in `agent/state/worktrees.py` and is used
unchanged: `assert_attribution` proves the changes belong to this task,
`commit` stages an explicit pathspec and never `-A`, and `integrate` takes the
cross-process integration lock, refuses a stale or dirty target, cherry-picks
with `-x`, detects an already-landed commit, and reports a conflict exactly
rather than resolving it. There is no second git subsystem here and no second
integration queue.

What was missing is the gate and the ordering around them:

    validated?   the canonical validation route must have PASSED. That question
                 already has one answer — `queue.completion_reasons` — and this
                 module consumes it rather than inventing a second validation
                 model. Nothing else makes work integrable: not a completed
                 provider result, not a Jira status, not a seat's say-so.
    attributed?  the changed files must be a subset of the surfaces the task
                 declared. Anything else is refused before a single file is
                 staged; unrelated dirt is left exactly where it is.
    landed?      git is asked what actually happened afterwards, rather than the
                 exit code being taken as proof.

A conflict is Product remediation. It is never permission to force, reset, or
resolve somebody else's code by guessing.
"""

import os
import subprocess

from agent.state import queue, worktrees


# Outcomes, mirroring `store.INTEGRATION_OUTCOMES`. Each stays its own fact: a
# git failure is not a provider failure and not a PEER failure.
INTEGRATED = "integrated"
ALREADY_PRESENT = "already-present"
NO_PRODUCT_COMMIT_REQUIRED = "no-product-commit-required"
ATTRIBUTION_FAILED = "attribution-failed"
COMMIT_FAILED = "commit-failed"
INTEGRATION_CONFLICT = "integration-conflict"
INTEGRATION_FAILED = "integration-failed"
VALIDATION_NOT_PASSED = "validation-not-passed"

TERMINAL_SUCCESS = (INTEGRATED, ALREADY_PRESENT, NO_PRODUCT_COMMIT_REQUIRED)
REMEDIATION_OUTCOMES = (ATTRIBUTION_FAILED, COMMIT_FAILED, INTEGRATION_CONFLICT,
                        INTEGRATION_FAILED)

# Jira issue type to the Product repository's existing conventional-commit type.
# Derived, declared and recorded on the receipt — never improvised per commit.
COMMIT_TYPES = {"Bug": "fix", "Story": "feat", "Epic": "feat", "Task": "fix",
                "Sub-task": "fix", "Subtask": "fix"}
DEFAULT_COMMIT_TYPE = "fix"
MAX_SUBJECT_CHARS = 100


class IntegrationRefused(Exception):
    """A bounded, named refusal. Always carries the outcome it should be filed as."""

    def __init__(self, outcome, detail, conflict_paths=()):
        super().__init__("%s: %s" % (outcome, detail))
        self.outcome = outcome
        self.detail = detail
        self.conflict_paths = tuple(conflict_paths)


# ------------------------------------------------------------------- the gate

def validation_reasons(task, interventions=None):
    """Why this work may NOT be integrated yet. Empty = the route has passed.

    This is `queue.completion_reasons` with exactly one reason dropped:
    `already-done`. Completion and integration ask the same question about the
    verdict, and differ only on where the card has since been moved — an item
    the Orchestrator has already transitioned to Done still needs its code to
    land. Every other reason is kept, including `not-in-review`, so a stale
    verdict on an item that has re-entered execution cannot integrate.
    """
    return tuple(reason for reason in queue.completion_reasons(task, interventions)
                 if reason != "already-done")


def integration_eligible(task, interventions=None):
    return not validation_reasons(task, interventions)


def assert_validated(task, interventions=None):
    reasons = validation_reasons(task, interventions)
    if reasons:
        raise IntegrationRefused(
            VALIDATION_NOT_PASSED,
            "%s has not passed its canonical validation route: %s"
            % (task.get("work_item_id"), ", ".join(reasons)))
    return True


# ------------------------------------------------------------- attribution

def attributed_changes(work_item_id, seat_id, task, root=None):
    """The changed files, proven to be inside the surfaces this task declared.

    Refuses BEFORE anything is staged. An undeclared change is reported, never
    cleaned up: restoring or resetting it is how the original incident nearly
    reverted finished work.
    """
    declared = tuple(task.get("surfaces") or ())
    try:
        actual = worktrees.changed_files(seat_id, work_item_id, root=root)
    except worktrees.WorktreeError as exc:
        raise IntegrationRefused(ATTRIBUTION_FAILED, str(exc))
    undeclared = sorted(set(actual) - set(declared))
    if undeclared:
        raise IntegrationRefused(
            ATTRIBUTION_FAILED,
            "%s changed files its task never declared: %s — commit refused, and "
            "they are left in place for a human to read"
            % (work_item_id, ", ".join(undeclared)))
    return tuple(actual)


def commit_message(work_item_id, issue):
    """The Product repository's existing convention: type(KEY): summary."""
    issue = issue or {}
    kind = COMMIT_TYPES.get(issue.get("issue_type"), DEFAULT_COMMIT_TYPE)
    summary = (issue.get("summary") or "").strip()
    if not summary:
        raise IntegrationRefused(
            COMMIT_FAILED,
            "%s has no Jira summary to describe its commit" % work_item_id)
    if len(summary) > MAX_SUBJECT_CHARS:
        summary = summary[:MAX_SUBJECT_CHARS].rstrip() + "…"
    return "%s(%s): %s" % (kind, work_item_id, summary)


# --------------------------------------------------------------- integration

def _git(path, *args):
    return subprocess.run(["git", "-C", path] + list(args),
                          capture_output=True, text=True)


def _revision(path, ref):
    result = _git(path, "rev-parse", ref)
    return result.stdout.strip() if result.returncode == 0 else None


def unintegrated_commit(worktree_path, branch):
    """The newest commit on this seat's branch that the target does not have yet."""
    result = _git(worktree_path, "rev-list", "--max-count=1", "%s..HEAD" % branch)
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def verify_integration(repo, landed, previous_head, expected_files, branch):
    """Ask git what happened. A zero exit code is not evidence on its own."""
    problems = []
    if _git(repo, "merge-base", "--is-ancestor", landed, branch).returncode != 0:
        problems.append("%s is not an ancestor of %s" % (landed[:7], branch))
    if previous_head and _git(repo, "merge-base", "--is-ancestor",
                              previous_head, branch).returncode != 0:
        problems.append("%s no longer contains its previous head %s — unrelated "
                        "work was discarded" % (branch, previous_head[:7]))
    landed_files = set(_git(repo, "show", "--name-only", "--format=", landed)
                       .stdout.split())
    missing = sorted(set(expected_files) - landed_files)
    if missing:
        problems.append("integrated commit is missing %s" % ", ".join(missing))
    if problems:
        raise IntegrationRefused(INTEGRATION_FAILED,
                                 "integration could not be verified: %s"
                                 % "; ".join(problems))
    return {"landed_files": sorted(landed_files)}


def integrate_validated_work(work_item_id, seat_id, task, issue, realized,
                             repo=None, root=None, integration_branch=None,
                             interventions=None, gates=None):
    """Attribute, commit, serialize, integrate, verify. Refuses at every gate.

    ``realized`` is the workspace mapping the allocation milestone produced, so
    the worktree this integrates from is the one the executor actually ran in.
    """
    assert_validated(task, interventions)
    repository = repo or realized["repository_root"]
    branch = integration_branch or worktrees.INTEGRATION_BRANCH
    profile = task.get("execution_profile") or {}
    review = task.get("review_context") or {}
    evidence = {
        "worktree_path": realized["path"],
        "source_branch": worktrees.branch_name(seat_id, work_item_id),
        "integration_branch": branch,
        "validation_route": profile.get("validation_route"),
        "validation_result": review.get("review_result"),
    }

    attributed = attributed_changes(work_item_id, seat_id, task, root=root)
    evidence["attributed_files"] = list(attributed)
    pending = unintegrated_commit(realized["path"], branch)
    if not attributed:
        if pending is None:
            # Verification-only work, an already-satisfied state, a readback.
            # Real completed work that legitimately changes no file. An empty
            # commit would be a lie told to make a pipeline green.
            return dict(evidence, outcome=NO_PRODUCT_COMMIT_REQUIRED,
                        detail="%s completed with no attributed Product change"
                               % work_item_id)
        # A clean tree does not prove there is nothing to land: an earlier
        # attempt may have committed and then failed to integrate. Retrying
        # must offer that commit, not declare the work change-free.
        product_commit = pending
        evidence["attributed_files"] = sorted(
            _git(realized["path"], "show", "--name-only", "--format=",
                 pending).stdout.split())
    else:
        message = commit_message(work_item_id, issue)
        evidence["commit_message"] = message
        try:
            product_commit = worktrees.commit(seat_id, work_item_id, message,
                                              list(attributed), root=root)
        except worktrees.WorktreeError as exc:
            # `commit` re-runs assert_attribution itself; a refusal there is
            # still an attribution fact, not a git malfunction.
            outcome = (ATTRIBUTION_FAILED if "unrelated-changes" in str(exc)
                       else COMMIT_FAILED)
            raise IntegrationRefused(outcome, str(exc))
    evidence["product_commit"] = product_commit
    attributed = tuple(evidence["attributed_files"])

    landed = _integrate_once(seat_id, work_item_id, product_commit, repository,
                             root, branch, gates, evidence)
    if landed["result"] == "already-present":
        return dict(evidence, outcome=ALREADY_PRESENT,
                    integrated_as=landed.get("integrated_as") or product_commit,
                    previous_head=landed.get("head"),
                    detail="%s is already on %s" % (product_commit[:7], branch))
    verify_integration(repository, landed["integrated_as"],
                       landed.get("previous_head"), attributed, branch)
    return dict(evidence, outcome=INTEGRATED,
                integrated_as=landed["integrated_as"],
                previous_head=landed.get("previous_head"),
                detail="%s landed on %s as %s"
                       % (product_commit[:7], branch, landed["integrated_as"][:7]))


def _integrate_once(seat_id, work_item_id, product_commit, repository, root,
                    branch, gates, evidence):
    """One serialized attempt, with one bounded retry for a lost head race.

    `integrate` re-reads the branch under its own lock, so a `stale-integration`
    means another task landed between our read and the lock. That is the lock
    working, not a conflict: refresh the expectation and try once more. A second
    stale answer is reported rather than looped.
    """
    for attempt in (1, 2):
        expected_head = _revision(repository, branch)
        if expected_head is None:
            raise IntegrationRefused(
                INTEGRATION_FAILED,
                "%s has no %s branch to integrate onto" % (repository, branch))
        try:
            return worktrees.integrate(seat_id, work_item_id, product_commit,
                                       expected_head, repo=repository, root=root,
                                       gates=gates, integration_branch=branch)
        except worktrees.WorktreeError as exc:
            detail = str(exc)
            if detail.startswith("stale-integration") and attempt == 1:
                continue
            if detail.startswith("integration-conflict"):
                after = detail.split("Conflicting paths:", 1)
                listed = after[1].split(". NOT resolved")[0] if len(after) > 1 else ""
                conflict = [p.strip() for p in listed.split(",")]
                raise IntegrationRefused(
                    INTEGRATION_CONFLICT,
                    "%s does not apply cleanly onto %s; the worktree is preserved "
                    "for Product remediation and %s is untouched. %s"
                    % (product_commit[:7], branch, branch, detail),
                    conflict_paths=[p for p in conflict if p])
            raise IntegrationRefused(INTEGRATION_FAILED, detail)
    raise IntegrationRefused(
        INTEGRATION_FAILED,
        "%s kept moving under two serialized attempts; re-verify and retry"
        % branch)


def record(state_store, work_item_id, seat_id, outcome, evidence):
    """Persist the orchestration evidence. Git stays the authority on the code."""
    payload = dict(evidence)
    payload["remediation_required"] = outcome in REMEDIATION_OUTCOMES
    return state_store.record_integration_receipt(work_item_id, seat_id, outcome,
                                                  payload)
