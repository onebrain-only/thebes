---
name: cleanup-after-integration
description: CEO rule — all work lives only on the Alpha repo and the local Dabbler/dabbler-code folder; temporary branches/worktrees are removed once pushed/integrated
metadata:
  type: feedback
---

CEO 2026-10-11: everything must end up ONLY on the Alpha branch of the main repo (dabblersport/webapp) and in the local folder Dabbler/dabbler-code. Any temporary folder (worktree, scratch copy) or branch used for work must be cleaned and removed after its work is pushed and integrated into Alpha.

**Why:** the CEO runs the app from Dabbler/dabbler-code and wants one place, no leftover branches or folders from team work.
**How to apply:** every integration brief to Memphis ends with a cleanup step (delete the merged team branch on origin and locally, remove the integration worktree); teams delete their scratch/backup branches and scratch worktrees after reporting; only branches proven merged into origin/Alpha (ancestor check) or explicitly abandoned duplicates are deleted; never delete main, Canary, Alpha, alpha-ds or anything in flight; ops guard blocks are reported, never bypassed. Related: [[orchestrator-delegate-not-execute]], [[orchestrator-runs-only-pm-po]].
