# backend-8 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-8.md`. This file is a work log, not a rule source.

  Part B, so out of scope here — but `KAN-191` selects it by name.
- Cascade-delete triggers on two of the 12: `comments.trg_comment_counter`, and three on
  `reactions`. All AFTER, none BEFORE, none able to abort a delete — so the cascade is safe.
  Relevant to AC3's eventual demonstration.

Both recorded on KAN-186 itself. Nothing written to `discovery-ledger.md` — every finding belongs
to an open ticket. **Ownership retained, ticket not released, not moved to `Peer-review`.**

### 2026-09-11, later — second `apply_migration` attempt on KAN-186: DENIED again

`team-lead` corrected itself twice (authorized → closed → open again, citing `kan168` and
`kan170_..._setnull` landing minutes earlier) and instructed: attempt, report the outcome, do not
theorise. Attempted. **Denied by the Claude Code auto-mode classifier for the second time.**

Stopped on the first denial of this attempt: no retry, and **no `execute_sql` fallback** — that
path returns no version string and writes no migration-ledger row, so AC6 would become
unsatisfiable *by construction* rather than merely unmet.

**Pre-state re-verified immediately before the attempt**, not carried over from the earlier one —
`kan170_games_creator_user_id_fk_setnull` had landed in between and touches `games`, so the
question was live rather than rhetorical. All 20 blocking constraints identical in name,
`confdeltype` and `confupdtype`; KAN-170 added an FK to `auth.users`, which never enters a
`confrelid = 'public.profiles'` census.

**Production confirmed untouched after the denial**, read back rather than assumed:

```
blocking FKs to profiles   20   (unchanged)
CASCADE FKs to profiles    26   (unchanged)
posts_author_user_profile_fkey
  FOREIGN KEY (author_user_id, author_profile_id) REFERENCES profiles(user_id, id)
    ON UPDATE RESTRICT ON DELETE RESTRICT      (unchanged — landmine intact)
posts 503 · profiles 165
```

**One factual observation, offered without a theory attached** (`backend-1` was right that
statement class does not predict this, and I am not restating a theory that has now been wrong
twice in both directions): the two migrations that landed today were each a **single short
statement**; mine is ~10 KB — 13 `DROP`+`ADD` pairs and two `DO` blocks. That is a difference in
the calls, not an explanation of the outcomes. If `team-lead` wants it tested rather than
assumed, the cheap experiment is to authorize applying **one** of the 13 constraints alone and
observe. **I did not run that experiment** — it would have been a retry, which I was told not to
do, and a partial apply is a worse state than a clean block.

Migration held at `supabase/migrations/kan186_profile_fk_cascade_part_a.sql`, unchanged and
apply-ready. Its pre-check makes the held work self-verifying: it aborts unless the live set is
still exactly what it was authored against, so the delay cannot silently invalidate it.
**Ownership retained, not released, not transitioned.**

### 2026-09-11 — KAN-186 assert-blindness check (prompted by `backend-2`'s KAN-188 finding)

`team-lead` relayed `backend-2`'s trap: an assert matching on
`pg_get_function_identity_arguments(oid) = 'uuid, uuid'` never matched, because that function
emits parameter *names*; every `IF` tested NULL, nothing raised, and the assert **passed while
the exposure was still open**. My held file's entire safety argument is that its two `DO` blocks
cannot pass by being read — so that argument had to be tested, not asserted. **Neither block had
ever executed**: the apply was refused before Postgres saw them.

**Six guards, each demonstrated failing against the live catalogue:**

| Test | Result |
|---|---|
| post-check vs the unconverted schema | **raises, "found 0"** |
| pre-check vs the unconverted schema | **passes, matches 13** |
| one constraint name perturbed | 12, not 13 |
| **LANDMINE**: `posts_author_user_profile_fkey` claimed `ON UPDATE 'a'` (real `'r'`) | **0** — and the same row with the true `'r'` → **1** |
| Part-B list with one bogus name | 6, not 7 |
| unique-index guard, index absent | reaches its own message |

The first two are one test, not two. `found 0` alone is ambiguous — a blind predicate also
returns 0. It is the **pair** — 0 and 13 from the same join against the same schema — that proves
the 0 comes from `confdeltype='c'` discriminating. Same logic for the landmine row: 0 on a false
`confupdtype` and 1 on the true one, so `confupdtype` is genuinely compared and the one attribute
this migration could silently destroy is actually guarded. That comparison is `"char" = text`
through an implicit cast, which was the thing most likely to be quietly wrong; it is not.

**Found and fixed one real defect in my own check.** The unique-index guard used
`'public.uq_profiles_user_id_id'::regclass` inside `NOT EXISTS`. If the index were absent the
**cast** raises `undefined_table` before `NOT EXISTS` is evaluated — the migration still aborts,
so it was fail-closed and never a safety hole, but it aborts with a generic catalogue error
instead of the sentence explaining what to do. Rewritten to match by name through
`pg_class`/`pg_namespace`; both branches then verified live. Only found by running it.

**The structural lesson, recorded because it generalises past both tickets:** every guard here is
*count, then RAISE IF n <> expected*. A blind predicate yields 0, and 0 <> expected, so it aborts.
`backend-2`'s was *RAISE IF <boolean>* — a NULL boolean is not true, nothing raises, silence reads
as success. **The shape is the safety property, not the care taken writing it.** Both the
demonstrations and this reasoning are now in the held file's header, so the next reader inherits
the evidence rather than the claim.

Held file unchanged in its DDL; header and index guard updated. Still unapplied, still owned.

### 2026-09-11 — shape audit of my own file: it violated my own rule once

`team-lead` propagated the fail-closed/fail-open shape rule board-wide and suggested I run it
against my own file. **I did, and my file broke the rule in exactly one place.**

Six guards, classified by form:

| | Guard | Shape |
|---|---|---|
| pre #1 | `IF n <> 13` | count |
| pre #2 | `IF n <> 20` | count |
| **pre #3** | **`IF NOT EXISTS (...)`** | **boolean — the one shape I had just warned everyone about** |
| post #4 | `IF n <> 13` | count |
| post #5 | `IF n <> 7` | count |
| post #6 | `IF n <> 7` | count |

**Guard #3 was not fail-open in `backend-2`'s sense** — `EXISTS` never returns NULL, so it could
not silently test NULL and pass. **But it was weak in a way the count form would not have
permitted:** it asserted that a unique index of that name existed, and never asserted *which
columns it covered*. An index of the right name over the wrong columns satisfies it, and the real
failure then surfaces as a confusing `ADD CONSTRAINT` error instead of the sentence I wrote for
precisely that moment. It also ignored `indpred` — and `profiles` carries **exactly one partial
unique index today** (`idx_one_active_profile_per_user`, `(user_id) WHERE is_active`), counted
live, which cannot back a foreign key at all. Not a hypothetical object.

Rewritten count-shaped, asserting the column **set** and excluding partial and exclusion indexes.
Demonstrated live: **1** against the real catalogue, **0** with the column expectation perturbed.
Then re-ran the whole rewritten pre-check **extracted verbatim from the held file** — all three
guards now count-shaped, passes clean.

**The honest lesson, and it is about me, not `backend-2`.** I derived the shape rule, wrote it up
as generally applicable, sent it on — and my own file had a boolean guard in it the whole time.
The rule is cheap to state and cheap to check, which is exactly why it survived my own review of
a file I had just finished defending. **Audit the form, not the author's confidence.**

Held file: DDL still untouched across all three revisions; only guard #3 and the header changed.
Unapplied, owned, not released.

## 2026-09-11 — PEER review of KAN-190 (repo-vs-live RLS policy census): **PASS**

Reviewing is not claiming; KAN-186 ownership undisturbed. `backend-4` executed; verdict posted to
KAN-190 as comment `10986`.

**Why this needed re-running rather than reading.** Its headline is **zero divergence**, and zero
is the one result a blind method and a clean estate produce identically — the same trap I spent
this morning on. So I re-derived it with my own regex, my own parser, my own set difference, and
re-measured every load-bearing number live.

| | policies | tables |
|---|---|---|
| live `pg_policies` (`public`) | **353** | **159** |
| repo, my independent parse | **353** | **159** |
| LIVE_ONLY / REPO_ONLY | **0 / 0** | |

Diffed as an exact **set difference** on `(tablename, policyname)`, not count equality — equal
counts can hide a live-only and a repo-only cancelling out.

### The estate moved during my own review, and that became the best control available

- first read **351**/159 → minutes later **353**/159, because **KAN-178 applied mid-review**
  (`role_grants` 2 → 4);
- `charges` (+3, new table) had already arrived from `kan171` after the census ran.

Three migrations landed on three different tables after `backend-4` measured, and repo-vs-live is
**still exactly 0 in both directions**. A predicate that silently matched nothing could not track
that. This is a stronger positive control than `backend-4` could have run for itself, and it
arrived by accident.

### AC2 reproduced, with a control added

`ran_as=anon | games=0 | roles=3 | role_grants=0 | v_game_card=217`. I captured `current_user`
**inside the same block**, so a silently-failed `SET ROLE` is excluded *directly* rather than
inferred from a sibling table being non-zero — `backend-4`'s control was sound but indirect.
`role_grants=0` where it measured 1 is KAN-178 landing between us: the number changed **because
the exposure was real and is now closed**.

### What I confirmed rather than accepted

All three self-reported method bugs (spaced names, drop-pairing, case-insensitivity), the
`34`→`28` correction (re-derived live: 28, identical list), the `wallets_self_read` divergence
(live `user_id`, repo `owner_id`, `20260910090000` absent from the ledger — confirmed `false`),
and that KAN-190's `validation_route: peer` really is `by: system-policy`, so declining
`Self-review` was correct rather than merely modest.

### The finding I rate highest in its report

**It stated the limit of its own method.** A name-keyed census *structurally cannot* see
`wallets_self_read` — my independent diff returns 0 and would have missed it — and it worded AC5's
answer as *"not behind live at all, **by name**"* rather than claiming more. It then found that
divergence anyway, by a different route.

### Three non-blocking notes

1. A census figure should be stamped with the **migration-ledger head** it was taken at, not just
   a date — mine drifted twice in fifteen minutes and only the ledger distinguishes stale from wrong.
2. The other **27** zero-policy tables are correctly marked unexamined, but `games` was caught only
   because the ticket pointed at it. That class deserves its own disposition from `po`, not this
   census's clean result by inheritance.
3. **My own parser artefact**, disclosed: 13 `storage.objects` policies mis-attributed to a table
   named `storage` because my pattern only anticipated a `public.` qualifier — same class of trap
   as the bug I was checking. Excluded before diffing.

Nothing fixed, nothing created, no ledger entry.

**Outcome:** `team-lead` closed KAN-190 **Done** on this PASS (closure #4, 2026-09-11). Notes 1
and 3 routed to the discovery ledger as method notes; note 2 (the other 27 zero-policy tables)
routed to `po` as a disposition question, not as work. No ticket created — the freeze holds.
