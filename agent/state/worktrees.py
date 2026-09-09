#!/usr/bin/env python3
"""Isolated Product working trees for concurrent executors, and ONE serialized
integration path back to Canary.

WHY THIS EXISTS — a structural failure, not a careless agent.

On 2026-09-09 six frontend seats executed in parallel against ONE Product working
tree. Three things followed, and none of them was a mistake any individual seat
could have avoided:

  * `frontend-5` staged four file deletions for KAN-148. `frontend-6` then ran
    `git commit` for KAN-156 and swept them in, because a shared index has no idea
    whose changes it holds. The resulting commit says KAN-156 and contains KAN-148.
  * `frontend-6` correctly read those deletions as contamination and tried three
    times to restore them — which would have REVERTED a ticket that had already
    passed review. Only an external permission block stopped it.
  * Undoing its own commit with `reset --soft HEAD~1` transiently orphaned a commit
    `frontend-4` had made on top of it in the meantime. Shared branch history was
    rewritten underneath a seat that had no part in it.

Every one of those is the same root cause: a mutable working tree and index shared
between concurrent writers. Care does not fix it. Isolation does.

THE MODEL

    canonical repository / integration branch (Canary)
        |
        +-- .claude/worktrees/product/<seat>/<work-item>/   [exec/<seat>/<item>]
        +-- .claude/worktrees/product/<seat>/<work-item>/   [exec/<seat>/<item>]

Native `git worktree`, not clones: a clone would need fetching to integrate and
would let a seat's history diverge invisibly. Worktrees share the object database
and nothing else — separate checkout, separate index, separate HEAD. Git itself
then enforces most of what follows, which is the point: a rule the tool refuses is
worth more than a rule an agent is asked to remember.

WHAT IS PARALLEL AND WHAT IS NOT

    execution      PARALLEL   — many seats, many worktrees, at once
    integration    SERIAL     — one lock, one commit onto Canary at a time

Parallel writes to integration history are exactly the failure above; parallel
execution is the throughput the system exists for. They are separable, so they are
separated.

`main` is never a target of anything here. Stdlib only.
"""
import os
import subprocess

STATE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(STATE))

# The canonical Product checkout. It is the INTEGRATION AND REFERENCE workspace and
# must stop being a six-agent scratchpad: executors get worktrees, not this.
PRODUCT_REPO = os.path.join(ROOT, "Dabbler", "dabbler-code")

# Under the existing `.claude/worktrees/` location, which already holds a Thebes
# worktree (`wave7-agentview`). Product worktrees are namespaced beneath `product/`
# so the two can never collide and neither cleanup can reach the other.
WORKTREE_ROOT = os.path.join(ROOT, ".claude", "worktrees", "product")

INTEGRATION_BRANCH = "Canary"
# Not a warning. Every entry point below refuses these outright.
PROTECTED_BRANCHES = ("main", "master", "origin/main", "origin/master")

BRANCH_PREFIX = "exec"


class WorktreeError(Exception):
    """Refused. Never raised for a condition the caller could not have checked."""


# ---------------------------------------------------------------- git plumbing

def _git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise WorktreeError("git %s failed in %s: %s"
                            % (" ".join(args), repo, (p.stderr or p.stdout).strip()))
    return p.stdout.strip()


def _rc(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args),
                          capture_output=True, text=True).returncode


# ---------------------------------------------------------------- identity

def _slug(s):
    return "".join(c if (c.isalnum() or c in "-_.") else "-" for c in str(s))


def worktree_path(seat_id, work_item_id, root=None):
    """Deterministic, derived from (seat, work item) and nothing else.

    Deterministic matters: a resumed invocation of the same seat on the same item
    must land in the same tree rather than allocate a second one, and a path that
    encoded a timestamp or a counter would quietly give it a fresh empty checkout.
    """
    if not seat_id or not work_item_id:
        raise WorktreeError("a worktree identity needs both a seat and a work item")
    return os.path.join(root or WORKTREE_ROOT, _slug(seat_id), _slug(work_item_id))


def branch_name(seat_id, work_item_id):
    return "%s/%s/%s" % (BRANCH_PREFIX, _slug(seat_id), _slug(work_item_id))


def _assert_not_protected(name):
    if name in PROTECTED_BRANCHES or _slug(name) in PROTECTED_BRANCHES:
        raise WorktreeError("protected-branch: %r is never a target of execution or "
                            "integration; it deploys to production" % name)


# ---------------------------------------------------------------- allocation

def allocate(seat_id, work_item_id, repo=None, root=None, base=None):
    """Give this seat its own checkout and its own branch. Idempotent.

    The branch is created FROM the integration branch, so the executor starts from
    what Canary actually is rather than from whatever another seat left behind.
    """
    repo = repo or PRODUCT_REPO
    base = base or INTEGRATION_BRANCH
    _assert_not_protected(base)
    path = worktree_path(seat_id, work_item_id, root)
    br = branch_name(seat_id, work_item_id)
    _assert_not_protected(br)

    # Compared by realpath: `git worktree list` resolves symlinks, and on macOS a
    # temp path under /var resolves to /private/var. A literal string compare would
    # decide an existing worktree was unregistered and refuse to reuse it.
    existing = {w["path"]: w for w in list_worktrees(repo)}
    if os.path.isdir(path) and os.path.realpath(path) in existing:
        found = existing[os.path.realpath(path)]
        return {"path": path, "branch": found.get("branch", br), "seat_id": seat_id,
                "work_item_id": work_item_id, "base": base,
                "base_commit": found.get("head"), "reused": True}
    if os.path.isdir(path) and os.listdir(path):
        raise WorktreeError("occupied: %s already exists and is not a registered "
                            "worktree — refusing to write into it blind" % path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    base_sha = _git(repo, "rev-parse", base)
    if _rc(repo, "rev-parse", "--verify", br) == 0:
        _git(repo, "worktree", "add", path, br)
    else:
        _git(repo, "worktree", "add", "-b", br, path, base)
    return {"path": path, "branch": br, "seat_id": seat_id,
            "work_item_id": work_item_id, "base": base, "base_commit": base_sha,
            "reused": False}


def list_worktrees(repo=None):
    """Every registered worktree, including the canonical checkout itself."""
    repo = repo or PRODUCT_REPO
    out, cur = [], {}
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines():
        if not line.strip():
            if cur:
                out.append(cur); cur = {}
            continue
        k, _, v = line.partition(" ")
        if k == "worktree":
            cur["path"] = os.path.realpath(v)
        elif k == "HEAD":
            cur["head"] = v
        elif k == "branch":
            cur["branch"] = v.replace("refs/heads/", "")
    if cur:
        out.append(cur)
    return out


def owner_of(path, repo=None, root=None):
    """(seat_id, work_item_id) for a registered Product worktree, else None.

    Derived from the path layout rather than stored, so there is no second record
    to drift from the filesystem.
    """
    root = os.path.realpath(root or WORKTREE_ROOT)
    real = os.path.realpath(path)
    if not real.startswith(root + os.sep):
        return None
    rel = os.path.relpath(real, root).split(os.sep)
    return (rel[0], rel[1]) if len(rel) >= 2 else None


# ---------------------------------------------------------------- the boundary

def assert_mutation_allowed(seat_id, work_item_id, path, root=None):
    """THE rule the shared tree could not express: a seat mutates its own worktree
    and nothing else.

    Refuses the canonical integration checkout and every other seat's worktree. This
    is what makes `git add`, `restore`, `reset`, `checkout` and `commit` against
    somebody else's files a refusal rather than a race.
    """
    own = os.path.realpath(worktree_path(seat_id, work_item_id, root))
    real = os.path.realpath(path)
    if real == own or real.startswith(own + os.sep):
        return True
    other = owner_of(real, root=root)
    if other:
        raise WorktreeError(
            "cross-worktree-mutation: %s may not mutate %s/%s's worktree at %s — "
            "this is the exact failure that put KAN-148's deletions inside the "
            "KAN-156 commit" % (seat_id, other[0], other[1], real))
    raise WorktreeError(
        "outside-worktree: %s may only mutate its own worktree for %s (%s); %s is "
        "the canonical integration workspace or is unmanaged, and executors do not "
        "write there" % (seat_id, work_item_id, own, real))


def changed_files(seat_id, work_item_id, root=None):
    """Paths changed in this seat's worktree, staged or not."""
    path = worktree_path(seat_id, work_item_id, root)
    # NOT via `_git`: it strips the output, and porcelain v1 encodes status in the
    # first two columns — " M beta.dart" stripped becomes "M beta.dart" and the
    # fixed-offset slice then eats the first character of the filename.
    p = subprocess.run(["git", "-C", path, "status", "--porcelain"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise WorktreeError("git status failed in %s: %s" % (path, p.stderr.strip()))
    out = []
    for line in p.stdout.splitlines():
        if line.strip():
            out.append(line[3:].strip().split(" -> ")[-1])
    return sorted(set(out))


def assert_attribution(seat_id, work_item_id, expected=None, root=None):
    """A task commit contains only that task's changes.

    Isolation makes contamination from ANOTHER seat impossible; this catches the
    other half — a seat that edited files its own ticket never named. The answer is
    to REFUSE THE COMMIT, never to "clean up" with restore or reset, because a
    cleanup is how the previous incident nearly reverted finished work.
    """
    actual = changed_files(seat_id, work_item_id, root)
    if expected is None:
        return actual
    unexpected = sorted(set(actual) - set(expected))
    if unexpected:
        raise WorktreeError(
            "unrelated-changes: %s carries changes its task did not declare: %s — "
            "commit REFUSED. Do not restore or reset them; report them"
            % (work_item_id, ", ".join(unexpected)))
    return actual


def commit(seat_id, work_item_id, message, paths, root=None, allow_empty=False):
    """Stage exactly `paths` in this seat's worktree and commit them.

    Explicit pathspec, always. `git commit` with no pathspec is what swept another
    task's staged deletions into a commit that named neither of them.
    """
    path = worktree_path(seat_id, work_item_id, root)
    if not os.path.isdir(path):
        raise WorktreeError("no-worktree: %s has none for %s" % (seat_id, work_item_id))
    for p in paths:
        assert_mutation_allowed(seat_id, work_item_id, os.path.join(path, p), root)
    assert_attribution(seat_id, work_item_id, expected=list(paths), root=root)
    _git(path, "add", "--", *paths)
    args = ["commit", "-m", message, "--"] + list(paths)
    if allow_empty:
        args.insert(1, "--allow-empty")
    _git(path, *args)
    return _git(path, "rev-parse", "HEAD")


# ---------------------------------------------------------------- integration

class _IntegrationLock:
    """ONE integration at a time, across processes.

    Parallel execution is the goal; parallel writes to integration history are the
    defect. `flock` on the canonical repo is what separates them.
    """

    def __init__(self, repo):
        self.p = os.path.join(repo, ".git", "thebes-integration.lock")
        self.fh = None

    def __enter__(self):
        import fcntl
        self.fh = open(self.p, "a+")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        import fcntl
        try:
            fcntl.flock(self.fh, fcntl.LOCK_UN)
        finally:
            self.fh.close()
        return False


def integrate(seat_id, work_item_id, expected_commit, expected_head,
              repo=None, root=None, gates=None, integration_branch=None,
              source_repo=None):
    """Land ONE task's commit onto the integration branch, under one lock.

    Fails CLOSED. Every precondition is verified against the repository rather than
    trusted from the caller, and a conflict is reported exactly rather than
    resolved by guessing — a guessed merge in a shared history is how the original
    incident would have been made permanent.

    `gates` is a list of (name, argv) run in the canonical checkout AFTER the commit
    lands and BEFORE the result is accepted; a failing gate rolls the branch back to
    where it started.
    """
    repo = repo or PRODUCT_REPO
    branch = integration_branch or INTEGRATION_BRANCH
    _assert_not_protected(branch)
    # `source_repo` is for RECOVERY: a commit that exists in another checkout with
    # no executing seat behind it — an orphaned author's worktree, a second clone.
    # It changes where the commit is READ from and nothing else; every precondition,
    # the lock, the conflict check and the gates are identical, because a recovered
    # commit is not entitled to an easier path than an ordinary one.
    wt = source_repo or worktree_path(seat_id, work_item_id, root)

    with _IntegrationLock(repo):
        head = _git(repo, "rev-parse", branch)
        if expected_head and not head.startswith(expected_head.strip()):
            raise WorktreeError(
                "stale-integration: %s is at %s, caller expected %s — another "
                "integration landed first; re-verify and retry"
                % (branch, head[:7], expected_head))
        if _rc(wt, "cat-file", "-e", expected_commit + "^{commit}") != 0:
            raise WorktreeError("no-such-commit: %s is not in %s's worktree"
                                % (expected_commit, work_item_id))
        sha = _git(wt, "rev-parse", expected_commit)
        touched = _git(repo, "show", "--name-only", "--format=", sha).split()

        # Two ways a commit can already be on the branch, and both must be detected
        # or a retry would land the change twice. Direct ancestry covers the trivial
        # case; the `-x` trailer covers the normal one, because cherry-pick rewrites
        # the sha and an integrated commit therefore never IS its source commit.
        if _rc(repo, "merge-base", "--is-ancestor", sha, branch) == 0:
            return {"result": "already-present", "commit": sha, "branch": branch,
                    "head": head, "files": touched}
        prior = _git(repo, "log", branch, "--format=%H",
                     "--grep=cherry picked from commit %s" % sha, "--fixed-strings")
        if prior:
            return {"result": "already-present", "commit": sha,
                    "integrated_as": prior.splitlines()[0], "branch": branch,
                    "head": head, "files": touched}

        cur = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        if cur != branch:
            raise WorktreeError("canonical checkout is on %r, not %r — integration "
                                "does not switch branches under a running run"
                                % (cur, branch))
        if _git(repo, "status", "--porcelain"):
            raise WorktreeError("dirty-integration-tree: the canonical checkout has "
                                "uncommitted changes; integration refuses to commit "
                                "on top of work nobody has claimed")

        if _rc(repo, "cherry-pick", "-x", sha) != 0:
            conflict = _git(repo, "diff", "--name-only", "--diff-filter=U", check=False)
            _git(repo, "cherry-pick", "--abort", check=False)
            raise WorktreeError(
                "integration-conflict: %s does not apply cleanly onto %s at %s. "
                "Conflicting paths: %s. NOT resolved by guessing — re-author against "
                "current %s." % (sha[:7], branch, head[:7],
                                 conflict.replace("\n", ", ") or "unknown", branch))
        landed = _git(repo, "rev-parse", "HEAD")

        for name, argv in (gates or []):
            p = subprocess.run(argv, cwd=repo, capture_output=True, text=True)
            if p.returncode != 0:
                _git(repo, "reset", "--hard", head)
                raise WorktreeError(
                    "gate-failed: %r exited %d after integrating %s; %s rolled back "
                    "to %s. Output: %s" % (name, p.returncode, sha[:7], branch,
                                           head[:7], (p.stdout + p.stderr)[-400:]))
        return {"result": "integrated", "commit": sha, "integrated_as": landed,
                "branch": branch, "previous_head": head, "files": touched}


def adopt_reconstructed(new_head, expected_head, repo=None, branch=None,
                        allow_tree_change=False):
    """Replace unpublished integration history with a re-attributed rebuild.

    THE ONLY LEGITIMATE USE. Local-only commits whose ATTRIBUTION is wrong — a
    task's changes sitting inside a commit that names a different ticket, which is
    what a shared index produces — can be rebuilt into correctly attributed commits
    before anything is published. Once history is on the remote this is no longer
    available and the record stands as it is.

    THE SAFETY PROPERTY IS TREE IDENTITY. The rebuilt head must produce a
    byte-identical tree to the head it replaces. That is what makes this an
    attribution rewrite rather than a content change, and it is what stops the
    operation being used to smuggle a diff past review under the word "normalize".
    `allow_tree_change` exists only so the refusal has a name; nothing in Thebes
    passes it.

    Everything else is verified rather than trusted: the branch is not protected,
    the current head is exactly what the caller expects, the new head already
    contains the remote's tip so nothing published is dropped, no other worktree has
    the branch checked out, and the canonical tree is clean. Serialized under the
    same integration lock as an ordinary landing, because it writes the same ref.
    """
    repo = repo or PRODUCT_REPO
    branch = branch or INTEGRATION_BRANCH
    _assert_not_protected(branch)
    with _IntegrationLock(repo):
        head = _git(repo, "rev-parse", branch)
        if not head.startswith(expected_head.strip()):
            raise WorktreeError("stale-adoption: %s is at %s, caller expected %s"
                                % (branch, head[:7], expected_head))
        new = _git(repo, "rev-parse", new_head)
        old_tree = _git(repo, "rev-parse", head + "^{tree}")
        new_tree = _git(repo, "rev-parse", new + "^{tree}")
        if old_tree != new_tree and not allow_tree_change:
            raise WorktreeError(
                "content-change-refused: the reconstructed head produces tree %s but "
                "the head it replaces produces %s. Re-attribution must not change "
                "content — if the diff is genuinely different this is a new commit, "
                "not a normalization" % (new_tree[:7], old_tree[:7]))
        upstream = "origin/%s" % branch
        if _rc(repo, "rev-parse", "--verify", upstream) == 0:
            pub = _git(repo, "rev-parse", upstream)
            if _rc(repo, "merge-base", "--is-ancestor", pub, new) != 0:
                raise WorktreeError(
                    "would-drop-published-history: %s (%s) is not an ancestor of the "
                    "reconstructed head; refusing" % (upstream, pub[:7]))
        for w in list_worktrees(repo):
            if (w.get("branch") == branch
                    and os.path.realpath(w["path"]) != os.path.realpath(repo)):
                raise WorktreeError("branch-checked-out-elsewhere: %s is held by the "
                                    "worktree at %s" % (branch, w["path"]))
        if _git(repo, "status", "--porcelain"):
            raise WorktreeError("dirty-integration-tree: refusing to move %s under "
                                "uncommitted changes" % branch)
        cur = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        if cur != branch:
            raise WorktreeError("canonical checkout is on %r, not %r" % (cur, branch))
        _git(repo, "reset", "--hard", new)
        return {"result": "adopted", "branch": branch, "previous_head": head,
                "new_head": new, "tree": new_tree,
                "replaced": _git(repo, "log", "--format=%H",
                                 "%s..%s" % (_git(repo, "merge-base", head, new),
                                             head)).split()}


# ---------------------------------------------------------------- cleanup

def release(seat_id, work_item_id, repo=None, root=None, keep_branch=True):
    """Remove ONE seat's worktree, and only that one.

    Refuses a tree with uncommitted work, and cannot reach another seat's worktree
    or the canonical checkout — the identity is recomputed here rather than taken
    from the caller, so a wrong path cannot be passed in.
    """
    repo = repo or PRODUCT_REPO
    path = worktree_path(seat_id, work_item_id, root)
    reg = {w["path"] for w in list_worktrees(repo)}
    if os.path.realpath(path) not in reg:
        return {"result": "not-allocated", "path": path}
    if os.path.realpath(path) == os.path.realpath(repo):
        raise WorktreeError("refusing to remove the canonical integration checkout")
    if _git(path, "status", "--porcelain"):
        raise WorktreeError("dirty-worktree: %s has uncommitted changes; refusing to "
                            "delete unintegrated work" % path)
    _git(repo, "worktree", "remove", path)
    if not keep_branch:
        _git(repo, "branch", "-D", branch_name(seat_id, work_item_id), check=False)
    return {"result": "released", "path": path,
            "branch_kept": keep_branch and branch_name(seat_id, work_item_id)}
