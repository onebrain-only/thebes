---
name: ceo-dont-hand-board-edits
description: Never hand Jira/board edits to the CEO; send them to the PO (retrying while the connector is flaky)
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-21T15:04:48.270Z
---

Jira edits (descriptions, labels, moves) go to the PO subagent, with retries if the connector times out. Do not ask the CEO to do them by hand.

**Why:** CEO 2026-10-21: "even if there's an edit you have the PO, why did you add requests". Every extra ask annoys him.
**How to apply:** ask the CEO only for what truly needs him: permission prompts, secrets, money, main. See [[ceo-delegates-decisions]].
