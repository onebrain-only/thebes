---
name: need-input-eligibility
description: "CEO 2026-10-21 — only two kinds of ticket may enter Need Input; never a board move, never work we can do ourselves"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-21T18:36:15.698Z
---

Only two kinds of ticket may enter Need Input:
1. Something only the CEO can type or do himself, such as a terminal command I am not allowed to run (e.g. /design-sync, /permissions, or saving a file only he can get).
2. An order the CEO must give a team, such as approving a cost or a migration. The team must be awake and waiting on that order. The moment he gives it, the team starts and the ticket goes back to its own column (Front-end or Back-end).

3. SUSPENDED 2026-10-21: the CEO opened the team conversation twice (KAN-621, KAN-624) and found no request; the prompt lives in the background session and is not visible there. Do NOT move tickets to Need Input on a `blocked-on-permission` alert until System Maintenance fixes the detector/visibility. Original rule: a team waiting on a permission prompt (blocked-on-permission). The ticket goes to Need Input with a comment naming the TEAM (e.g. "افتح فريق Memphis ووافق"). Never give the CEO `claude attach` commands or session IDs, in Jira or in chat.

**COLUMN REMOVED (CEO 2026-10-21, same evening): "needs-input column is useless now".** Never transition to Open (13) for Need Input again. CEO items stay in their own column with the `need-input` label + a numbered Arabic-steps comment, and are told to him in chat. Reopened/Returned column (Codex) is unaffected. Below is historical.

**Jira mechanics (CEO created the columns on 2026-10-21):**
- Needs Input column = status **Open** (status id 1, transition id 13).
- Returned column = status **Reopened** (status id 4, transition id 14). Codex moves returned work there. We never use it.
- Use Open and Reopened only for these purposes.
- When the CEO acts, move the ticket back to the status it came from.

Never put a ticket there for:
- a board move ("move X to Y"). The PM or PO does that.
- work a team or I can do without his real input.
- manual QA or hand-testing.

The list will grow later, but only when the CEO says so.

**Why:** the column is critical. If it is kept tidy it speeds the work up; if it is padded it becomes a bottleneck.

**Every Need Input comment carries numbered Arabic steps** (CEO 2026-10-21, after a one-line comment on KAN-621): what to open, where to click, what to choose, what happens after — never just one sentence.

**How to apply:** before the PM labels or moves a ticket into Need Input, test it against the two kinds. Its comment says exactly what the CEO types, or exactly which order he gives and to which team. Related: [[pm-runs-board-po-in-teams]], [[ceo-dont-hand-board-edits]].
