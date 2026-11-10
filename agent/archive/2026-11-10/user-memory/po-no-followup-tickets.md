---
name: po-no-followup-tickets
description: CEO 2026-10-21 — PO never creates follow-up tickets from an existing ticket; it finishes the ticket or sends it back to the orchestrator
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-21T17:55:26.983Z
---

The PO (po / po-2) keeps its Jira write permission, but it never creates a follow-up or spin-off ticket from an existing one. A gap found during a ticket is either finished inside that ticket or sent back to the orchestrator. The orchestrator then either runs the PM (to create or re-prioritise) or asks the CEO to create the ticket through Codex.

**Why:** CEO 2026-10-21: "i didn't allow PO to make you create infinity tasks". KAN-624 was spun off KAN-589 this way.

**How to apply:** every PO brief must say "do not create tickets; finish or return". New tickets go through the PM or the CEO via Codex only. Never dispatch a PO to create a ticket because a PO decision named one. Related: [[messaging-no-po-tickets]], [[ceo-dont-hand-board-edits]].
