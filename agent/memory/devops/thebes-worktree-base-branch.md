---
name: thebes-worktree-base-branch
description: Thebes controller's worktree allocator hardcodes "Canary" as the base branch for every Project, not just dabbler-code — bootstrapping a new Project repo needs a Canary branch, not main.
metadata:
  type: project
---
> **Note 2026-11-10 (Thebes System).** Still true of `agent/state/worktrees.py` (`INTEGRATION_BRANCH = "Canary"`), which belongs to the kept Controller path. Live team checkouts come from the conversation-dispatch path and use `staging-<team>` (D-052).

`agent/state/worktrees.py` in the Thebes-Canonical repo (not `agent/controller/worktrees.py`,
which doesn't exist) is what `agent.controller.workspace.realize_workspace()` calls to allocate
an isolated worktree before dispatching a claimed work item to an executor. Its `allocate()`
defaults `base` to the module constant `INTEGRATION_BRANCH = "Canary"` (`worktrees.py:63,127`)
when no caller passes one — and **no caller currently does**, for any Product/Project, not just
Dabbler's app repo. `PROTECTED_BRANCHES` includes `"main"`, so a fresh repo whose only branch is
`main` will not just risk a protected-branch refusal — it fails allocation outright with a plain
`git rev-parse Canary` error, because nothing overrides `base` per project today.

**How to apply:** when bootstrapping ANY new registered Project's repository from scratch (the
first commit is unwritten, `.git` doesn't exist yet) so that Thebes can allocate a worktree
against it, initialize the repository with `Canary` as the branch holding the first commit —
not `main`. Verify with `agent.controller.workspace.realize_workspace(...)` (or
`agent.state.worktrees.allocate(...)` directly) using no `base` override, the same way the
controller's three real call sites in `agent/controller/__init__.py` invoke it, before reporting
the bootstrap done. Confirmed empirically 2026-09-17 while bootstrapping
`Dabbler/dabbler-design-system` for KAN-214 — see `agent/status/devops.md` for the full proof
(allocate, verify via `git worktree list`, then `release(..., keep_branch=False)` to clean up).

This is a structural gap, not a one-off: it will recur for `web` and `admin` (and any other
Project registered without an activated repo yet), since the base branch is one hardcoded
constant rather than something read from `agent/state/registry/products/*/projects/*.json`.
Not something devops should silently patch — it's a Thebes controller change, `cto`'s call.
