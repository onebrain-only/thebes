"""Make the derived Product workspace real, and decide when it may go away.

`agent/state/worktrees.py` is the canonical worktree manager and stays the only
one: it allocates, enforces the protected-branch refusal, refuses to write into
an occupied path, and refuses to delete a tree holding uncommitted work. This
module adds nothing to that. It does the two things the execution path was
missing:

    realize   allocate before dispatch, verify the identity of what came back,
              and bind ``expected_revision`` to what git actually says HEAD is
    conclude  decide from canonical lifecycle whether the workspace may be
              released, or must outlive this invocation

The second is the point of separating them. A worktree's lifetime follows the
Product lifecycle, not the function that created it: an execution that returns
`needs_input` will be continued in the same tree, work awaiting PEER/QA review
is not finished with its checkout, and a tree holding uncommitted Product work
is never deleted to make a flow tidy. Release is the exception, not the default.

An executor never allocates anything. It is handed a working directory that
already exists, on a branch that is already its own.
"""

import os
import subprocess

from agent.state import worktrees


class WorkspaceUnavailable(Exception):
    """Isolation could not be established. Not a reason to use a shared tree."""

    def __init__(self, reason, detail):
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def as_blocker(self, work_item_id, seat_id):
        return {"work_item_id": work_item_id, "seat_id": seat_id,
                "reason": self.reason, "detail": self.detail}


RELEASE = "release"
PRESERVE = "preserve"


def _head_revision(path):
    """Authoritative git truth for the tree we just allocated. Never invented."""
    result = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise WorkspaceUnavailable(
            "workspace-revision-unreadable",
            "git rev-parse HEAD failed in %s: %s"
            % (path, (result.stderr or result.stdout).strip()))
    revision = result.stdout.strip()
    if not revision:
        raise WorkspaceUnavailable("workspace-revision-unreadable",
                                   "%s reports no HEAD revision" % path)
    return revision


def _is_clean(path):
    result = subprocess.run(["git", "-C", path, "status", "--porcelain"],
                            capture_output=True, text=True)
    return result.returncode == 0 and not result.stdout.strip()


def realize_workspace(work_item_id, seat_id, workspace, repo=None, root=None,
                      base=None):
    """Allocate the isolated checkout this request names, then prove it is ours.

    ``workspace`` is the mapping the canonical intent resolver derived. The
    repository comes from the Product/Project registry through it, so allocation
    binds to the project the work item actually belongs to.
    """
    repository_root = (workspace or {}).get("repository_root")
    if not repository_root:
        raise WorkspaceUnavailable(
            "workspace-repository-unresolved",
            "%s has no derived repository root to allocate against" % work_item_id)
    repository = repo or repository_root
    if not os.path.isdir(os.path.join(repository, ".git")) and not os.path.isfile(
            os.path.join(repository, ".git")):
        raise WorkspaceUnavailable(
            "workspace-repository-unavailable",
            "%s is not a git repository, so no isolated worktree can be created "
            "from it" % repository)
    try:
        allocation = worktrees.allocate(seat_id, work_item_id, repo=repository,
                                        root=root, base=base)
    except worktrees.WorktreeError as exc:
        # Includes the protected-branch refusal and the occupied-path refusal.
        # Neither is a reason to fall back to the canonical Product checkout.
        raise WorkspaceUnavailable("workspace-allocation-refused", str(exc))
    except OSError as exc:
        raise WorkspaceUnavailable("workspace-allocation-failed", str(exc))

    path = allocation["path"]
    assert_isolated_identity(work_item_id, seat_id, allocation, repository, root)
    revision = _head_revision(path)
    realized = dict(workspace, working_directory=path, worktree_path=path,
                    expected_revision=revision)
    return {"workspace": realized, "branch": allocation["branch"],
            "base": allocation.get("base"), "base_commit": allocation.get("base_commit"),
            "reused": bool(allocation.get("reused")), "expected_revision": revision,
            "path": path, "repository_root": repository}


def assert_isolated_identity(work_item_id, seat_id, allocation, repository, root=None):
    """The tree we were given must be this seat's tree for this work item.

    `allocate` is idempotent and will reuse a registered worktree standing at the
    expected path. That is correct for a same-seat continuation and wrong for
    anything else, so the identity is checked rather than assumed: path ownership,
    branch name, registration, and that this is not the canonical checkout.
    """
    path = allocation["path"]
    if not os.path.isdir(path):
        raise WorkspaceUnavailable(
            "workspace-missing",
            "allocation reported %s but no directory exists there" % path)
    if os.path.realpath(path) == os.path.realpath(repository):
        raise WorkspaceUnavailable(
            "workspace-is-canonical-checkout",
            "%s resolved to the canonical Product checkout; executors never work "
            "there, and a failed isolation is not a reason to" % path)
    owner = worktrees.owner_of(path, root=root)
    if owner != (seat_id, work_item_id):
        raise WorkspaceUnavailable(
            "workspace-identity-mismatch",
            "%s belongs to %s, not to %s/%s"
            % (path, owner or "no managed seat", seat_id, work_item_id))
    expected_branch = worktrees.branch_name(seat_id, work_item_id)
    actual_branch = allocation.get("branch")
    if actual_branch != expected_branch:
        raise WorkspaceUnavailable(
            "workspace-branch-mismatch",
            "%s is checked out on %r; this work item's isolated branch is %r"
            % (path, actual_branch, expected_branch))
    if actual_branch in worktrees.PROTECTED_BRANCHES:
        raise WorkspaceUnavailable(
            "workspace-protected-branch",
            "%s is checked out on protected branch %r" % (path, actual_branch))
    registered = {entry["path"] for entry in worktrees.list_worktrees(repository)}
    if os.path.realpath(path) not in registered:
        raise WorkspaceUnavailable(
            "workspace-unregistered",
            "%s is not a registered worktree of %s" % (path, repository))
    return True


def release_decision(result, task, realized):
    """Workspace lifetime follows the Product lifecycle, not this function's scope.

    Preservation is the default and needs no justification. Release is the
    exception and must name the canonical fact that permits it.
    """
    status = getattr(getattr(result, "status", None), "value", None)
    lifecycle = ((task or {}).get("lifecycle") or {}).get("canonical")
    route = ((task or {}).get("execution_profile") or {}).get("validation_route")

    if status == "needs_input":
        return PRESERVE, "needs-input-continuation-uses-this-workspace"
    if status == "provider_failed":
        # Nothing executed, so nothing of the Product changed. A tree this
        # invocation freshly created and never dirtied can go; a reused one
        # belongs to work that predates this invocation.
        if realized.get("reused"):
            return PRESERVE, "reused-workspace-predates-this-invocation"
        if not _is_clean(realized["path"]):
            return PRESERVE, "workspace-holds-uncommitted-product-work"
        return RELEASE, "provider-failed-before-any-product-mutation"
    if status == "execution_failed":
        return PRESERVE, "execution-failure-evidence-remains-in-this-workspace"
    if lifecycle == "done":
        if not _is_clean(realized["path"]):
            return PRESERVE, "workspace-holds-uncommitted-product-work"
        return RELEASE, "work-item-is-canonically-done"
    if route in ("peer", "qa", "self"):
        return PRESERVE, "validation-route-%s-still-needs-this-workspace" % route
    return PRESERVE, "lifecycle-has-not-authorized-release"


def conclude_workspace(work_item_id, seat_id, result, task, realized, repo=None,
                       root=None):
    """Apply the lifecycle decision. A refused release is a fact, not a failure."""
    decision, reason = release_decision(result, task, realized)
    # The branch is durable identity and is never reported away here: a released
    # worktree keeps its branch, and a preserved one still is that branch.
    if decision == PRESERVE:
        return {"workspace_status": "preserved", "workspace_reason": reason,
                "workspace_path": realized["path"], "workspace_branch_kept": True}
    try:
        outcome = worktrees.release(seat_id, work_item_id,
                                    repo=repo or realized["repository_root"],
                                    root=root, keep_branch=True)
    except worktrees.WorktreeError as exc:
        # `release` refuses a dirty tree. That refusal protects unintegrated
        # Product work and must never turn into a deletion or an execution error.
        return {"workspace_status": "preserved", "workspace_reason": str(exc),
                "workspace_path": realized["path"], "workspace_branch_kept": True}
    return {"workspace_status": outcome.get("result", "released"),
            "workspace_reason": reason, "workspace_path": realized["path"],
            "workspace_branch_kept": bool(outcome.get("branch_kept"))}
