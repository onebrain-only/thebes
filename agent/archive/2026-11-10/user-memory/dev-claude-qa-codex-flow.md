---
name: dev-claude-qa-codex-flow
description: "CEO's target flow (2026-10-13): Claude Code does the work and hands it to review; Codex runs QA in review and continues; defects go back to development and Claude Code restarts from there"
metadata:
  node_type: memory
  type: project
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-13T11:20:14.019Z
---

CEO message 2026-10-13: Claude Code now owns the work and delivers it into review. In review, **Codex burns the QA** (runs QA and carries the review through). If Codex finds anything, it **returns the ticket to Development** and **Claude Code starts the rework from there**.

**Why:** the CEO wants a clean split: Claude Code = build, Codex = QA/review, with a bounce back to Development on any defect. It also removes the orchestrator's habit of running judge subagents itself.

**How to apply:** this is a Thebes workflow change (SYSTEM_MAINTENANCE), not something to improvise per ticket. Until it is wired, keep the current verify route (`python3 -m agent.execution.verify verdict`, one judge pass), but do not describe Claude Code teams as reviewers of their own work, and log it as a maintenance item: Codex QA stage in review, "fail" returns the ticket to Development for the same Claude Code team. Related: [[orchestrator-runs-only-pm-po]], [[orchestrator-delegate-not-execute]].

**Correction (CEO 2026-10-13, supersedes my first reading):** the two kinds of review are different.
- **Text, report, plan, spec and answer deliverables (ask/ops lane):** they still go through review and **I judge them normally** (one judge pass, then `verify verdict`). They are not exempt from judging.
- **Anything that STOPS in the Review status waiting for QA (work that changes the product: code, DS, migrations):** **Codex picks it up and carries QA.** I do NOT run a sub-agent on it and I do NOT start a judge for it. If I find a ticket waiting in Review, I leave it alone.
- QA is now Codex's job; a defect goes back to Development for the same Claude Code team.

**Tools from maintenance (2026-10-13):** `python3 -m agent.execution.intake order KAN-a KAN-b ...` sets the Ready order (Jira rank); `intake mark-integrated <dispatch_id> --base Alpha|alpha-ds --sha <sha> --evidence "..."` records work merged by hand (git must agree); `intake unlink <link_id> --approved "..."` removes a wrong Blocks link. Use them myself, do not ask the CEO. The CEO also said: leave review (and stuck-in-review items) to Codex; my job is to keep the tasks running, using idle teams on non-conflicting work in parallel.

**Review channel (D-043):** default is Codex. Only on the CEO's explicit order run `python3 -m agent.execution.review_queue channel claude --by "<his words>"` (wakes Edfu, the Claude QA conversation) or `channel codex --by "<his words>"` to go back. A `review_stalled` inbox item (product work waited 30+ min) = tell the CEO in ONE line, never switch myself. A `reviewer_question` item must be answered within 15 minutes. I never review product work on either channel.
