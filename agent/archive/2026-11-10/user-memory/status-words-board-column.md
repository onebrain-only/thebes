---
name: status-words-board-column
description: "CEO 2026-10-27: \"working\"/\"finished\" mean the Jira column only; never say \"work is done but ticket still in X\""
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-27T09:39:20.755Z
---

For the CEO, a ticket is "شغال" only if it sits in Front-end, Back-end or Operations (not Ready). It is "خلصت" only if it sits in Review (QA-Test/Self-review/Peer-review) or Done. The board column is the only truth.

**Why:** On KAN-650 I said "the work finished but the ticket is still in Front-end". He does not want to hear it: a ticket in Front-end is working, not finished.

**How to apply:** Report status by column only. Never say "the work is finished but the ticket is still in X" or "stuck". If the column looks wrong against the evidence (merged, checks passed), fix the column (transition + comment) and report the new column. Do not explain the gap to him. See [[status-from-jira]], [[keep-jira-status-current]].
