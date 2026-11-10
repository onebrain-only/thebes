---
name: feedback-denied-jira-transition-no-workaround
description: Jira transitionJiraIssue is blocked by the Claude Code permission classifier for this seat; report the transition as owed rather than routing around it
metadata:
  type: feedback
---

`mcp__atlassian__transitionJiraIssue` is refused by the Claude Code auto-mode
permission classifier even when the org contract says the seat owns the
transition. `getAccessibleAtlassianResources` also fails intermittently with
"We are having trouble completing this action" — the site URL
`https://dabbler.atlassian.net` works in place of a cloudId when it does.

When this happens: finish and verify the actual work, then report the transition
as **owed and blocked**, naming the exact status and transition ids from
`agent/state/board.py`.

**Why:** org authority is not harness permission — the two are separate systems and
the harness wins. A denied tool has no substitute. Asking another seat to run the
transition is cross-session permission laundering and is explicitly forbidden;
fabricating the transition in a status log or report would be worse, because the
board would then disagree with the record. The work being complete does not entitle
me to record a lifecycle event I could not perform.

**How to apply:** on any ticket where I own a transition — `Ready` → `Back-end`
(10043, transition `5`) and `Back-end` → `Peer-review` (10045, transition `7`) —
attempt it once, and on denial put it in the report as an explicit owed item for
`team-lead`. Never retry verbatim, never delegate it, never claim it happened.

Related: [[project-supabase-apply-migration-ledger-version]]
