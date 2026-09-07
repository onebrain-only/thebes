# junior-frontend-3a — status log

## 2026-09-06 — Skills audit of this seat (survey, from `team-lead`)

**What it was.** A read-only survey, not work: four questions about which skills the
junior-frontend seat needs. First entry in this file — this seat has never run a task.

**What I did.** Read `agent/roles/junior-frontend-3a.md`, listed `agent/skills/` (75 entries
including `AVAILABLE.md`, so **74 skills**), read `agent/skills/AVAILABLE.md`, opened the
frontmatter of 12 repo skills and the bodies of 7 `dart-flutter` plugin skills, and checked
`Dabbler/dabbler-code/docs/CONVENTIONS.md` for whether it answers "which example do I copy".

**What I touched.** This file only. No `lib/`, no `test/`, no git, no Jira, no `flutter`
command. `CONTRACT.md` §4.1 bars this seat from Phase 0 and Phase 0 is live.

**What I decided.**
- The seat's reflex table is nearly right and needs **removals, not additions**. Of the five
  `dart-flutter` candidates offered, I would take **none** as a standing reflex.
- `flutter-fix-layout-issues` — cited in my role file — is the one plugin skill worth keeping,
  and it is already there.
- `flutter-apply-architecture-best-practices` is actively dangerous for this seat: it prescribes
  MVVM/`ChangeNotifier` and a `lib/data/services/` tree, both of which contradict this repo
  (Riverpod 2.x three-layer stack; `lib/data/**` is not a junior's). It is not on my list and
  should not reach any junior.
- The one real gap is **finding the canonical example** — the thing my whole seat is defined by.
  There is no tool for it and no index. `docs/CONVENTIONS.md` gives naming rules, not
  `file:line` exemplars.

**What is blocked.** Nothing. Survey answered; no follow-up requested.

## 2026-09-06 — KAN-136 part 1: sitting count (no migration authored)

Dispatched by `team-lead-4` via `team-lead` to size KAN-136 part 1 — establishing the
venue resolution join path for `trgfn_payment_to_ledger` (`T-055`). Read-only; no writes
to the live project, no SQL authored, no `duedate` set.

**Count: 1 sitting, ceiling 2.**

Sitting 1 — enumerate the path, name every column, decide the NULL policy, hand the
design to whoever authors the body after KAN-131 lands. Checkpoint: design written,
nothing in the function touched. Ceiling 2 covers one rework cycle if the missing FK
below has to go to `cto` and the ruling changes the design.

**The join path resolves.** Verified against the live catalogue
(`information_schema.columns`, `pg_constraint`):

  payment_intents.booking_id (uuid, NOT NULL, **no FK**)
    -> venue_bookings.id (uuid PK)
    -> venue_bookings.venue_space_id (uuid, NOT NULL, FK venue_spaces(id) ON DELETE CASCADE)
    -> venue_spaces.venue_id (uuid, NOT NULL, FK venues(id) ON DELETE CASCADE)

Both hops that matter are NOT NULL with real FKs, so once a `booking_id` matches a
`venue_bookings` row the venue is guaranteed to resolve.

**Finding — `payment_intents.booking_id` carries no foreign key at all.** No FK exists on
`payment_intents` in `pg_constraint`. Nothing in the database asserts that `booking_id`
names a `venue_bookings` row, so the join can return zero rows and `v_venue_id` stays
NULL, which then reaches `fn_get_wallet('venue', NULL, ...)`. Whether part 1 adds the FK,
or the function raises on a NULL, is a decision I did not take — it is `cto`'s.

**Counted, not inferred:** `payment_intents` 0 rows, `venue_bookings` 0 rows,
`venue_spaces` 693 rows, 0 joinable pairs. The path cannot be exercised against real data
today; it is verified structurally only.

Not verified: `fn_get_wallet`'s behaviour on a NULL owner id, and whether KAN-131's
replacement body keeps the same variable shape. Both are post-KAN-131 authoring concerns.

**Update, same day —** `po` carried the count unchanged (earliest 2026-09-07, ceiling
2026-09-08) and split the ticket to match the scope it was sized against: `KAN-136` is now
pt.1 only (the design/enumeration pass), and the authoring work moved to `KAN-140`, unsized
and blocked on pt.1's output plus `cto`'s NULL-policy ruling. The FK-less `booking_id`
finding is carried on `KAN-136` as the question for `cto`. No re-size needed — the number
still describes the scope now on the ticket.

**Second update, same day —** `team-lead-4` briefly told `po` not to date `KAN-136` on my
count, on the grounds that `backend-3` was not a seat, having validated against the
pre-restructure roster loaded at its session start rather than `agent/roles/` on disk. It
retracted in full to `po` and `pm` and asked for the ticket to be dated from the count as
given. It had independently re-verified my findings before doubting the seat and confirmed
all of them: zero foreign keys on `payment_intents`, and both join hops real
(`venue_bookings_venue_space_id_fkey`, `venue_spaces_venue_id_fkey`). No change to the
count and nothing for me to redo.

It also added a consequence I had not: the NULL-venue path collides with `T-051` making
`wallets.owner_id` NOT NULL, so `fn_get_wallet('venue', NULL, …)` would fail on the column
constraint and not only on the lookup. That sharpens the question already carried to `cto`.

**Third update, same day —** `po` hit the same stale-roster failure independently of
`team-lead-4`, briefly treating `backend-3` as not a real seat, then verified
`agent/roles/backend-3.md` on disk and restored `KAN-136`'s `due_date` to 2026-09-08 off
the original count, carried unchanged. Two seats, the same cached-roster error, one ticket.
Recorded in agent memory so the next dispatch from this seat does not re-argue it.

**Net: the count was never disturbed.** 1 sitting, ceiling 2; `KAN-136` dated 2026-09-08.
