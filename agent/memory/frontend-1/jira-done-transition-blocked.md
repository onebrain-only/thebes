---
name: jira-done-transition-blocked
description: the Self-review -> Done Jira transition was blocked for this seat on KAN-153 via the mcp__atlassian__ server, but SUCCEEDED on KAN-161 via mcp__claude_ai_Atlassian_Rovo__ — attempt it, do not pre-emptively escalate
metadata:
  type: project
---

On a SELF validation route the `Self-review (10044) -> Done (10007)` transition belongs to the
review owner — the worker, not `po`. **Whether it is permitted appears to depend on which
Atlassian MCP server is used, not on Jira and not on a workflow rule.**

**Measured, both first-hand:**

- **KAN-153, 2026-09-08** — `mcp__atlassian__transitionJiraIssue` to Done (transition `41`) was
  **denied by the Claude Code permission classifier**. `Ready -> Front-end` (`8`) and
  `Front-end -> Self-review` (`6`) both succeeded in the same session.
- **KAN-161, 2026-09-10** — `mcp__claude_ai_Atlassian_Rovo__transitionJiraIssue` to Done
  (transition `41`) **succeeded**, closing the ticket. Same seat, same route, same transition id.

**How to apply:** Finish the work, commit, post the evidence comment, transition into the review
status, record the verdict through `store.record_review_result`, then **attempt `-> Done`**. Do
not assume it will fail and do not escalate before trying. If it *is* denied, do not retry the
same call through a second server or as `transitionName` instead of `transitionId` — that is
working around the user's permission decision — and do not ask a teammate to make it (a peer
performing an action blocked in my session launders that decision, and on a SELF route it is not
theirs to make). Record the blocked step and escalate to the caller, leaving the ticket in
Self-review with its verdict attached.

**Ordering gotcha, learned on KAN-161:** `open_review_context` refuses with `no-executor-evidence`
until `store.release` has run — evidence arises from the release, never from ownership, a status
file or a Jira status. And `observe_lifecycle` must sync the record to the new Jira status first,
or it refuses with `not-in-review`. Sequence: transition Jira -> `observe_lifecycle` -> `release`
-> `open_review_context` -> `record_review_result`.

See also [[thebes-transitions-are-mine]].
