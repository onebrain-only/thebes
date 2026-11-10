---
name: batch-alpha-merges
description: CEO 2026-11-04 — defer Alpha integration/migration merges; batch them when necessary or once at end of day
metadata:
  node_type: memory
  type: feedback
  originSessionId: b9b99f0a-421b-44b0-ba8d-923d3efd43c5
  modified: 2026-11-04T08:03:26.865Z
---

Do not integrate every finished ticket into Alpha right away. Hold the Memphis integration and migration work and run it only when something depends on it, or as a single batch at the end of the day when no other work would be blocked.

**Why:** every Memphis migration or merge on Alpha makes the CEO answer accept/decline prompts in the terminal, which interrupts him. He wants no work to stall waiting on him.

**How to apply:** Code Done stays at review PASS ([[code-dod-review-pass-done]]). Queue the Operations integration tickets and dispatch them in one batch. Dispatch one early only when a dependent ticket needs the change live, such as the serial prod chain KAN-843→844.
