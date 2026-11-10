---
name: where-things-live
description: "CEO 2026-11-05 — all plans in dabbler-docs; no PNGs/screenshot folders; live test before screenshot; one branch per team, not per story; never delete docs on an agent's judgment"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0a2fe358-3c7d-441e-b22d-9153cd1adc00
  modified: 2026-11-05T06:03:05.822Z
---

All plans/briefs/reports live in `Dabbler/dabbler-docs/` (archive: `alpha-plan-archive/`). No scattered Desktop or Dabbler/ folders.
Designs are read from the Claude Design link, never saved PNGs; delete all images. Live test first, screenshot last (not a hard ban — a ban becomes a bottleneck), delete after the task.
One branch per team (`<base>-<team>`), no folder/worktree per story. Merge unmerged work into Alpha first.

**Why:** the CEO found orphan worktrees (7.5G+7.8G), duplicated plans and thousands of PNGs, and distrusts agents deciding what is "not helpful" to delete ("sorry I removed it").
**How to apply:** move docs, never delete them on my own judgment; only images are removable on his standing order; the per-seat worktree change in `agent/state/worktrees.py` follows the Alpha merge. See [[ceo-delegates-decisions]].
