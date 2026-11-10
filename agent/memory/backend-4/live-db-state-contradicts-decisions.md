---
name: live-db-state-contradicts-decisions
description: Two production facts in wtncuzcskpigqpmnxwws that contradict DECISIONS.md T-068 and T-063 as written — verify both before quoting either ruling
metadata:
  type: project
---

Measured 2026-09-10 against production `wtncuzcskpigqpmnxwws`, both contradicting rulings written the same day:

1. **MCP `execute_sql` works.** `T-068` records it as denied and calls that an ops blocker for `devops` that "materially limited step 2". It is not denied. T-068 step 2 (`kan78`/`kan93` by row count) is unblocked.
2. **`public.can_manage_venue` and `can_manage_venue_members` raise `42P01`** — they join `public.organiser_profiles`, which does not exist (the live table is `organiser`). All four `venue_members` RLS policies call one or the other, so `venue_members` **errors** for every client rather than returning empty. `venue_members` also holds 0 rows against 389 venues. `T-063`'s addendum ruled the venue read policy expressible "via membership" on the strength of the table existing in the catalogue — it never called the function.

Also: `wallets` is mid-migration — `user_id` still PRIMARY KEY, `owner_type` nullable, `wallets_self_read` still `auth.uid() = user_id`. Its repo migration `20260910090000_kan130_kan131_…` is **absent from the remote ledger**, so it landed partially and outside it.

**Why:** T-063 tells backend seats to copy "the wallets pattern exactly" and to route venue reads through membership. Both instructions rest on live state that is not what the ruling assumed, so following them literally ships a raising read path or an inconsistent identity model.

**How to apply:** on any money-table or venue-authorization work, call the authorization function and count the rows before quoting T-063 or T-068. Copy `wallets`' *policy shape* (`_block_dml` + a read policy), never its identity columns. Write venue read predicates inline against `venue_members`, never via `can_manage_venue`. Re-verify — `backend-3` holds KAN-130 and the wallets half may have moved. See [[t068-forward-only-landing-route]].
