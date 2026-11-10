---
name: project-db-writes-blocked-2026-09-10
description: As of 2026-09-10 the permission classifier blocks apply_migration against the Dabbler Supabase project for some statements but NOT all — KAN-173 landed while KAN-170 was denied three times, and a fresh session does not lift it
metadata:
  type: project
---
> **Note 2026-11-10 (Thebes System).** History from 2026-09-10. Today a team seat does not apply migrations; Memphis does, as ordered `execute_sql` steps (`agent/DECISIONS.md` TH-054). `team-lead` no longer exists; a blocker goes to the orchestrator as one `decision_required` question.

As of **2026-09-10**, the Claude Code permission classifier denies `apply_migration` (and
write-shaped probe DDL/DML) against production `wtncuzcskpigqpmnxwws`. KAN-170 and KAN-171 both
stalled on it the same day, with migrations fully authored and preconditions measured but nothing
applied. `team-lead` escalated the permission itself to the CEO as the blocker on **all** remaining
database work.

**Why:** it is a harness permission decision, not a governance gate — `CONTRACT.md:399` already puts
schema changes with the owning `backend-N` under `G-002`, so the authority exists and only the
tool permission is missing. Nobody routed around it; see [[feedback-denied-tool-no-substitute]].

**Updated 2026-09-10, third attempt — the block is NOT uniform, and two plausible theories are
now DISPROVEN:**

1. *"No apply works."* False. KAN-173 landed for another seat and is in the remote ledger as
   version `20260910171433` (`kan173_wallet_recalc_owner_id`) — verified via `list_migrations`,
   not taken on report.
2. *"Fresh sessions have the permission; long-running ones don't."* False. KAN-170's one-statement
   `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY` was denied in a **fresh** session, the third
   denial across three sessions. Session freshness is not the discriminator.

What distinguishes a permitted apply from a denied one is **not visible from inside the denial** —
the classifier returns only "blocked", with no per-call reason. So it cannot be predicted, only
attempted. The probe surface is **separate again**: writes to `auth.users`/`profiles` are denied
independently of `apply_migration`, so one being granted says nothing about the other.

**How to apply:** attempt the apply rather than assuming either outcome — a report that "the block
is gone" is a claim to test, and evidence of some other ticket applying is not evidence yours will.
Preflight, authoring and live measurement still deliver full value, so do those and stop cleanly at
the apply. Do NOT substitute `execute_sql` for a denied `apply_migration`; see
[[feedback-denied-tool-no-substitute]]. Reads are unaffected — `execute_sql` SELECTs, `list_tables`,
`list_migrations` and catalogue queries all work, and they are how both the preconditions and the
"was this actually applied" question get answered. If denied, say so plainly and leave the ticket in
`Back-end`: an unapplied migration in `Peer-review` misrepresents the work.
