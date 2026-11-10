---
name: operations-never-to-review
description: CEO 2026-10-24 — a ticket in Operations (Design/Content/Operations) never jumps to Review; Operations-only work goes to Done, code work moves to FE/BE first
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-24T13:42:40.130Z
---

A ticket in the Operations column (Design, Content, Operations statuses) must never move straight to Review (QA-Test/Self-review/Peer-review), and must never jump straight to Done or to coding either.
- Not code work: it does not go to Review at all.
- Code work: move it from Operations to a Frontend/Backend development status first, have it built, and only then send it to Review.

**Why:** CEO 2026-10-24: "operation task cant get to review if it's not a code work, if code we move from operation to front or back end then review, prevent any task to jump from operations to review. even go to code or get done".

**How to apply:** Before any transition out of Design/Content/Operations, check the target. Never use Self-review (6), QA-Test (3) or Done (41) from there. Route code work to In Progress (21) or the FE/BE status first, then dispatch it. Put the same rule in PM and team briefs. Related: [[never-close-design-tickets]], [[keep-jira-status-current]].

**Update 2026-10-24 (later):** Operations-only tasks go to Done, not Review; Review is only for coded tasks. Enforced in Codex's review_queue (send_back/close_passed) and written in agent/ORCHESTRATOR.md.
