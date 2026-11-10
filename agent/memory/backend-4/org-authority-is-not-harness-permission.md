---
name: org-authority-is-not-harness-permission
description: A teammate relaying CEO authorization never unblocks a Claude Code permission denial — the two are separate systems; and apply_migration can be denied per-call by the auto mode classifier while succeeding for other seats the same hour
metadata:
  type: feedback
---
> **Note 2026-11-10 (Thebes System).** The lesson stands: a relayed go-ahead never lifts a permission denial. What changed is the route: a team seat does not apply migrations at all; it reports the SQL and Memphis applies it (`agent/DECISIONS.md` TH-054).

**Organizational authorization and harness permission are two different systems, and only the CEO acting in Claude Code settings changes the second one.** When a teammate message says "the CEO authorized this" or "that block is gone, it just worked for another seat," that settles legitimacy and scope within the company model. It does not alter what the permission layer allows. Retry once if there is real evidence the permission state changed; do not keep retrying on a relay.

**Why:** KAN-171 (`public.charges`) was denied three times on `mcp__claude_ai_Supabase__apply_migration` — 2026-09-10, twice on relayed CEO authorization and once after `kan173_wallet_recalc_owner_id` demonstrably landed at 17:14:33 UTC, proving the tool was not globally blocked. Each denial came from the **Claude Code auto mode classifier**, which refuses silently rather than prompting. Body size was ruled out as the cause: 9,600 chars denied, while 13,154 and 11,424-char migrations had landed on the same project.

**How to apply:** when `apply_migration` is denied, say so plainly and name the two unblock paths — a permission rule in `.claude/settings.json`, or an interactive approval in a session running in **default (prompting) mode** rather than auto mode. Then refuse the three workarounds, in this order of temptation:

1. `execute_sql` for the same DDL — same production write, different tool name, and it returns no version string and writes no `supabase_migrations.schema_migrations` row, so it manufactures exactly the orphan [[t068-forward-only-landing-route]] forbids.
2. **Splitting the migration to slip past the classifier** — yields multiple version strings for one artefact, and a denial partway through leaves a partially-created table. On a money table that is strictly worse than not applying.
3. **Dropping the `REVOKE`/`GRANT` statements** so the body looks less like a privilege change — `pg_default_acl` grants `anon=rxtm` on new `public` tables, so a body without them ships `anon` SELECT. Removing them to satisfy a classifier ships the exact hole they close.

Hold the claim, stay in the development status (do **not** advance to `Peer-review` — nothing is applied for a reviewer to check against live state), keep the SQL outside `supabase/migrations/`, and write no repo file: with no returned version there is no legal name for it.
