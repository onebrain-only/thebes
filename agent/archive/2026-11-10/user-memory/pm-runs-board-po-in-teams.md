---
name: pm-runs-board-po-in-teams
description: "CEO 2026-10-21 — orchestrator runs the PM, not the PO; PO lives inside teams; new tickets only for cross-team blockers; Need Input column for CEO-blocked tickets"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-21T18:00:40.336Z
---

- The orchestrator does NOT run the PO in its own conversation. The PO works at team level: teams run it and it moves their tickets itself. Board work, ordering and ticket creation go to the **PM**, which the orchestrator runs.
- The PM must be active: it picks the order, says what goes first and what waits, and keeps every team busy.
- A new ticket is allowed only when the blocker needs a DIFFERENT team. If the same team can do it, they do both inside the one ticket and leave a comment ("need A to reach B"). Never spin a ticket off a ticket to finish it.
- A ticket waiting on a CEO decision goes to a **Need Input** column (placed after Back-end, before Review/Done). Its comment carries the exact step-by-step instructions the CEO must follow, so he sees it on the board without opening the chat.

**Why:** CEO 2026-10-21: running the PO here blocked the PO's work in the teams, and spinning off KAN-624 from KAN-589 was the wrong pattern. He wants to see what waits on him from the board.

**How to apply:** route Jira writes and ordering to the `pm` subagent. Put CEO-blocked tickets in Need Input with an instructions comment. Supersedes the PO-dispatch parts of [[po-no-followup-tickets]]. See also [[ceo-dont-hand-board-edits]].
