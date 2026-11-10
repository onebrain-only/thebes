---
name: feedback-denied-tool-no-substitute
description: When apply_migration is denied by the permission classifier, do NOT fall back to execute_sql for the same DDL — confirmed correct by team-lead and independently by backend-4
metadata:
  type: feedback
---
> **Note 2026-11-10 (Thebes System).** The lesson stands: a denied tool has no substitute inside the same session. The route today: a team seat does not apply migrations; it hands the SQL to Memphis (`agent/DECISIONS.md` TH-054).

When the permission system denies `apply_migration`, do **not** reach for `execute_sql` (or any
other tool) to run the same production write. Stop, preserve the authored work, report the
blocker, and let the user decide.

**Why:** a denial from the user's permission system is a decision to respect, not an obstacle to
route around — the same production write through a differently-named tool is the same write.
Confirmed on 2026-09-10 (KAN-170): `team-lead` explicitly endorsed the refusal, said it holds
`execute_sql` permission itself and declined to use it for the same reason, and noted `backend-4`
reached the identical judgment independently on KAN-171. The permission block was escalated to the
CEO as the blocker on all remaining database work rather than worked around by anyone.

**How to apply:** on any denied write, (1) verify production is untouched and say so with counts,
(2) write the artifact to the repo marked clearly as NOT APPLIED, (3) post a correction to any
claim comment so it cannot be read as "applied", (4) do **not** advance the Jira status — claiming
review-readiness on unapplied work is a false state, (5) hand back the exact statement, affected
objects and rollback so someone with the permission can finish it. Keep ownership; blocked is not
released. See [[project-db-writes-blocked-2026-09-10]].
