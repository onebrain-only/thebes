---
name: returned-column-removed
description: "CEO 2026-10-24 — Reopened/Returned column is gone; returned work goes back to its own working column with a \"returned\" label"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-24T13:43:39.125Z
---

There is no Reopened/Returned column on the board any more. When work comes back, move it to the column it belongs in (Design or Content for Operations work, In Progress or the FE/BE status for code) and add a `returned` label so it can be told apart.

**Why:** CEO 2026-10-24: "returned column removed now the returned tasks will go back to it's column with a tag".

**How to apply:** On any returned or failed ticket, transition it to its working status, add the `returned` label, and comment the reason. Never look for a Reopened transition. Remove the label once the ticket passes. Put the same rule in PM briefs. Related: [[operations-never-to-review]], [[keep-jira-status-current]].
