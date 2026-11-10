---
name: identity-columns-profile-vs-auth-uid
description: In Dabbler's Supabase schema profiles.id is NOT an auth uid — the auth-comparable identity is <table>.*_user_id; picking *_profile_id for an auth.uid() check is a silent 100% miss
metadata:
  type: project
---

`public.profiles` has its own surrogate `id` **plus** a separate `user_id` column. `profiles.id` is
never an `auth.users.id`. Any table carrying both a `*_profile_id` and a `*_user_id` (e.g.
`games.creator_profile_id` / `games.creator_user_id`, `game_roster`, `posts`, `game_rating_events`)
must use the **`*_user_id`** column for anything compared to `auth.uid()` or written to a column
FK'd to `auth.users(id)` — `wallet_ledger.user_id`, `game_settlements.organiser_user_id`.

Measured 2026-09-10 on production `wtncuzcskpigqpmnxwws`:

```sql
select (select count(*) from public.profiles p join auth.users u on u.id=p.id)          -- 0 of 165
     , (select count(*) from public.games where creator_user_id is distinct from creator_profile_id) -- 218 of 218
     , (select count(*) from public.games g join auth.users u on u.id=g.creator_user_id)             -- 218 of 218
```

**Why:** the two columns are *never* equal in any live row, so choosing the profile id fails 100% of
the time rather than intermittently — it will not show up as a flaky bug, it will show up as a
permanent authorization or crediting defect. This is the trap called out in `[[settle-game-boundary-t069]]`.

**How to apply:** whenever ruling on or reviewing a definer function, RLS policy, or repository query
that establishes "is this caller the owner", check which of the pair is being read. Also note
`games.creator_user_id` has **no foreign key** to `auth.users` — the match is convention, not a
constraint.
