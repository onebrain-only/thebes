---
name: keep-jira-status-current
description: "CEO 2026-10-23: he tracks work from Jira — move status + add a comment on every dispatch, finish and wait"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-23T18:54:46.896Z
---

On every dispatch, completion or wait, update the Jira ticket myself: transition the status (parent too) and add a short comment saying who, which branch, and what is next.

**Why:** CEO tracks work from the board; on 2026-10-23 he asked "why work not started" when KAN-630 sat in To Do and KAN-631 stayed in Front-end after it had finished.

**How to apply:** Right after `conversation_dispatch` returns accepted, check the ticket status and fix it. When a team reports finished, move the ticket to Self-review. Keep the parent in In Progress while any child is running.
