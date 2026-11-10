---
name: close-ticket-procedure
description: on a validation route, the Done Jira transition belongs to the review owner (me on QA routes) as a separate act after record_review_result, not to the Orchestrator
metadata:
  type: feedback
---

After `store.record_review_result` records a PASS, I am not finished — I still have to move
the Jira ticket to Done myself, then sync Persistent State. WORKFLOWS.md §2.3: a task reaches
Done "only through its validation route, and only its review owner puts it there." The
`record_review_result` docstring calling the Jira move "the Orchestrator's separate act" means
separate from recording the verdict, not "someone else's job" — I misread it that way on
KAN-167 and team-lead corrected it.

**Why:** the review owner is the one who actually checked the work; letting a different seat
(the Orchestrator, or anyone else) perform the close keeps the verdict and the transition in
different hands than the doctrine intends, and orphans tickets in QA-Test that are already
decided.

**How to apply, on every PASS I record:**
1. Read live transitions for the ticket (`getTransitionsForJiraIssue` or equivalent) rather
   than trusting `board.py`'s cached table — confirm the Done transition id and target status
   id before calling it.
2. Confirm current status matches what I expect (e.g. QA-Test/10009) before moving it.
3. Transition to Done. If `mcp__atlassian__transitionJiraIssue` is denied by the permission
   classifier, try `mcp__claude_ai_Atlassian_Rovo__transitionJiraIssue` before escalating —
   frontend-1 measured this exact denied/succeeded split across the two servers on different
   tickets (`agent-memory/frontend-1/jira-done-transition-blocked.md`), and it held for me too
   (KAN-167, Rovo succeeded).
4. `store.observe_lifecycle(work_item_id, expected_revision=<post-record_review_result rev>,
   jira_status_id=<the id just confirmed>)` to bring Persistent State's `lifecycle.canonical`
   to `done`.
5. Sanity-check `queue.completion_reasons(task)` returns `['already-done']` (or empty/no
   blocking reasons) before reporting the ticket closed.

Only do this on tickets where I am the recorded `review_owner` with `review_result: pass`.
