# agent/status/backend-6.md

**Owner:** `backend-6` (Shai) (write) · all agents (read)

> Header corrected 2026-09-10 by `backend-6`. This file carried a stale
> `junior-frontend-4b` header and ownership line — a template copy from a retired seat.
> Only the header was changed; no log content existed to alter.

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

## 2026-09-10 — KAN-138 — AC-2 canonical probe run against production; AC-2 substance PROVEN, literal criterion NOT met, new blocking defect found in `_wallet_recalc`
**Agent:** `backend-6` (Shai), CEO-authorised narrow scope, production `wtncuzcskpigqpmnxwws`

**Outcome:** Ran the canonical AC-2 probe verbatim from
`Dabbler/dabbler-code/supabase/migrations/20260907130000_kan138_settle_game_settlement_status_cast.sql:53-67`.
The KAN-138 cast fix **works**: the `42804` at the `game_settlements` insert is gone and
execution passed it. Execution then **reached and completed the `wallet_ledger` credit
insert** — which is exactly what AC-2 asks. But the probe did **not** return
`PROBE_RESULT=SETTLE_GAME_SUCCEEDED`. It aborted one level *past* the credit insert, inside
the `AFTER` trigger chain, on a previously unknown defect:

    23502: null value in column "owner_id" of relation "wallets" violates not-null constraint
    CONTEXT: _wallet_recalc(uuid) line 17
          <- _wallet_after_ledger() line 3
          <- settle_game(...) line 80   [the wallet_ledger credit insert]
          <- inline_code_block line 13  [the probe]

`public._wallet_recalc` inserts `public.wallets(user_id, balance_aed, held_aed)` and never
supplies `owner_id`, but `wallets.owner_id` is `uuid NOT NULL` with **no default**
(`information_schema.columns` ordinal 9). So the wallet-recalc chain cannot complete for any
user without a pre-existing `wallets` row — and `public.wallets` holds **0 rows**. The money
path is blocked one step beyond where KAN-138 unblocked it. **Not a KAN-138 regression**:
KAN-138 did not touch `_wallet_recalc`, `_wallet_after_ledger` or `wallets`.

**Evidence (all measured, verbatim):**
- Project ref confirmed `wtncuzcskpigqpmnxwws` ("Dabbler", ACTIVE_HEALTHY) before anything ran.
- Live `settle_game` `prosrc` md5 = `d3c6238ea2b04ecd06f87cdb832cda37` — matches the briefed
  reviewed body, so the probed function is the fix `backend-1` peer-reviewed.
- Pre-probe: `game_settlements` **0**, `wallet_ledger` **0**.
- Post-probe: `game_settlements` **0**, `wallet_ledger` **0**, `wallets` **0**. Nothing committed.
- **Credit insert provably completed**, two independent ways: (1) `trg_wallet_ledger_recalc`
  has `pg_trigger.tgtype = 29` = ROW+INSERT+DELETE+UPDATE with the BEFORE bit **unset** →
  `AFTER ROW`, so the ledger row existed before the trigger fired; (2) `_wallet_recalc`
  computed `balance_aed = 90.00` for the probe user (visible in the 23502 DETAIL row), and
  90.00 = 100.00 gross − 10% commission = `gs.organiser_earnings_aed`. From an empty
  `wallet_ledger`, that sum is only reachable if the probe's own credit row was visible.
- AC-1 cast present: `prosrc like '%::public.settlement_status%'` → **true**.
- AC-4: `prosecdef=true`, `provolatile='v'`, `proconfig=search_path=public` ('public' alone).
- AC-5 / T-069: `proacl` = `postgres=X/postgres | service_role=X/postgres`. The T-069
  containment revoke is intact. **Nothing re-granted.**
- KAN-128 survived: `on conflict (game_id) do update` → **true**;
  `on conflict do nothing` → **true**. No regression.

**Rollback, verified before running rather than assumed:** the probe `DO` block has no
`EXCEPTION WHEN` clause, so the `RAISE` cannot be caught; `settle_game` is `prokind='f'` (a
FUNCTION, not a PROCEDURE) so it cannot `COMMIT` even in principle, and measured to contain no
`commit`, no `rollback` and no `exception when` handler; `set_config(..., true)` is
transaction-local. Both probe paths terminate in an exception. Post-probe counts confirm it.

**Not verified:** whether `_wallet_recalc`'s `owner_id` omission also breaks the payment/refund
paths that call it (only the settlement path was exercised — one probe, as authorised). The
intended semantics of `wallets.owner_id` vs `wallets.user_id`, and of the nullable
`owner_type`, are undetermined — I did not read `_wallet_recalc`'s full source (the MCP
permission classifier blocked `pg_get_functiondef` and `prosrc` text reads; the quoted
statement above comes from Postgres' own error CONTEXT). AC-3 (KAN-128's re-settle
double-credit probe) was not run — not authorised and now blocked by this same defect.

**Next:** KAN-138 AC-2's *substance* is satisfied and I recommend it be recorded as such with
the literal `PROBE_RESULT` line explicitly noted as unreachable until the `wallets.owner_id`
defect is fixed. `backend-1` reviews. The `_wallet_recalc` defect needs a **new ticket from
`po`** — I did not create one (`backend-N` does not create or edit tickets) and did not fix it
(outside this authorisation; the T-068 freeze is ACTIVE). No Jira transition performed.

## 2026-09-10 — KAN-170 PREFLIGHT (assess only; no claim, no DDL applied)

**Scope of this pass:** Preflight assessment only, as briefed by `team-lead`. Read-only against
`wtncuzcskpigqpmnxwws`. **No DDL, no DML, no grant change, no `db push`, no migration applied.**
No claim taken, no Jira transition performed, no reviewer selected.

**Could not read the ticket at source.** `mcp__atlassian__getAccessibleAtlassianResources`
returned "We are having trouble completing this action" on three attempts, so no `cloudId` and
no `getJiraIssue`. The ACs below are as restated in the brief, **not** verified against Jira.
Anyone acting on this should re-read KAN-170 once the Atlassian MCP recovers.

**Precondition re-measured live (not carried from the 218/218 figure cited in the ticket):**
218 games, **0 NULL** `creator_user_id`, **0 orphans**, 26 distinct creators. Types match —
`games.creator_user_id uuid NOT NULL`, `auth.users.id uuid NOT NULL` (PK). The `ADD CONSTRAINT`
will validate clean. Also measured: all 218 rows have `creator_profile_id` resolving to a
profile whose `user_id` **equals** `creator_user_id` — 0 disagreements, 0 orphaned profile refs.

**Index:** `idx_games_host ON games (creator_user_id, creator_profile_id)` already exists, and
`creator_user_id` is the leading column, so the RESTRICT delete-side check is indexed. No index
added — AC "touch nothing else" is met with no trade-off (same situation as KAN-145).

**Recommended action: `ON DELETE RESTRICT`.** It is the zero-behaviour-change option. The
sibling on the *same table* is `games_creator_profile_id_fkey ... ON DELETE RESTRICT`, and
`profiles.user_id -> auth.users ON DELETE CASCADE` already means deleting a game creator's auth
row is blocked today by that RESTRICT. RESTRICT records the posture that already exists rather
than introducing one. `SET NULL` is impossible (`NOT NULL`). **`CASCADE` is affirmatively
rejected**: it would destroy game history and could change user deletion from "blocked" to
"deletes rows", and the interleaving of two cascade paths is not something to rest on.

**Lock, stated plainly:** `ADD CONSTRAINT ... FOREIGN KEY` takes `SHARE ROW EXCLUSIVE` on
**both** `public.games` and **`auth.users`**. The `auth.users` lock blocks logins/signups for
its duration. At 218 rows validation is sub-millisecond, so the window is trivial — but it is a
lock on the auth table and should be named, not glossed. **`NOT VALID` + `VALIDATE CONSTRAINT`
is ceremony here and I recommend against it**: it takes the same locks and only defers the scan.

**Authority: within role, not CEO-reserved.** `CONTRACT.md:399` — schema/structure changes are
authored and applied by the owning `backend-N` under `G-002`, PEER-reviewed by another
`backend-N`. `019`'s CEO reservation is **user-data mutation**; `ADD CONSTRAINT` reads existing
rows to validate and modifies none. Route is `peer`, system-derived from `schema_change`.

**Recorded through `agent/state/store.py`** (never by hand):
- `surfaces` -> `["supabase/migrations/20260910100000_kan170_games_creator_user_id_fk.sql"]`,
  superseding `po`'s assessed-empty `[]`. `shared_or_contended_surface` recomputes **false**.
- `work_effort` -> **1** (ceiling 2), with the ceiling condition written into the basis_ref.
- Record now at revision 7; `effective_fields` recomputed to include `work_effort`.

**DEFECT FOUND, PRE-EXISTING, NOT CAUSED BY THIS TICKET — needs a ticket from `po`.**
`public.delete_my_account()` deletes rows that block account deletion (`meetup_invites`,
`game_link_tokens`, `user_freezes`, `venue_bookings`, ...) but **`games` is not in that list**.
Because `games.creator_profile_id -> profiles` is RESTRICT and `profiles.user_id -> auth.users`
is CASCADE, the final `delete from auth.users` raises 23503 for anyone who has created a game.
**All 26 distinct game creators cannot delete their accounts today** — an erasure/GDPR problem.
The Dart comment at `account_management_screen.dart:1139-1141` asserts the opposite ("cascades
to all related public/auth data") and is wrong. This ticket does not make it better or worse:
whatever `ON DELETE` action is chosen, the `creator_profile_id` RESTRICT still blocks. **I did
not fix it and did not create a ticket** — `backend-N` does not create or edit tickets.

**Blockers to claiming, reported not routed around:** `queue.eligibility_reasons` returns
`['not-ready', 'unverified-jira']`. KAN-170 sits at Jira status **10004 (To Do, Backlog
column)**, not **10008 (Ready)** — `po` must select it into Ready (transition "2"). The
`unverified-jira` reason is live, not an artefact: the Atlassian MCP is erroring, so
`has_due_date` and `has_acceptance_criteria` cannot be checked from here.

**Also flagged:** KAN-169 declares the whole `supabase/migrations/` directory as its surface,
which overlaps my file-level declaration. `derive_contended` does not flag it (that prefix is
not in `SHARED_PREFIXES`), so it needs an Orchestrator judgement, not an automatic one. And
there is **no `KAN-170 BLOCKS KAN-169` dependency edge** — only `KAN-171 BLOCKS KAN-169`
exists. Whether one is wanted is a `po` question; I did not create one.

**Next:** stand by. On execution: post the `G-006` claim comment first, re-measure preconditions
immediately before applying, demonstrate the probe failing pre-apply, apply, then post
verification asserting `confdeltype='r'` (not merely that a row appeared). Reviewer is another
`backend-N`, not `frontend-6`, and not chosen by me.

## 2026-09-10 — KAN-170 EXECUTION ATTEMPT — **APPLY DENIED, NOTHING APPLIED**

**Outcome: blocked, not done.** Migration authored, preconditions measured, `apply_migration`
**denied by the Claude Code permission classifier**. The behavioural probe was denied too. I did
**not** route around either denial — running the same DDL through `execute_sql` would have
bypassed the intent of the block. Ticket **stays in Back-end (10043)**; I did **not** transition
to Peer-review, because claiming review-readiness on unapplied work would be a false state.

**Ticket read at source this time.** Primary Atlassian MCP still failing; **Rovo works**
(cloudId `18c8e9f5-d139-4e03-b5d8-89122cc14937`). `po` had tightened AC1 and AC2 since Preflight.
Transitioned Ready (10008) → Back-end (10043) myself (transition `5`). G-006 claim comment
posted **before** any DDL (comment 10887); blocked-apply correction posted after (comment 10894).

**AC2 — apply-time preconditions, measured live 2026-09-10 12:41:30Z** (explicitly not the
ticket's 218/218, not Preflight's): 218 games, **0 NULL**, **0 orphans**, 26 distinct creators.
Types match, `auth.users.id` is PK. Clean → plain validated `ADD CONSTRAINT`; AC2's `NOT VALID`
branch not needed.

**Production verified untouched after the denial:** `games_creator_user_id_fkey` absent (0),
constraints 20, FKs 7, indexes 13, games 218, auth.users 259, profiles 165 — all identical to
baseline. **Probe residue 0/0**: the aborted `DO` block rolled back in full.

**AC1's convention clause, confronted rather than skipped.** AC1 defers to
`game_settlements.organiser_user_id` / `wallet_ledger.user_id` "if they fix a repo convention".
**I measured both — both are `ON DELETE CASCADE` (`confdeltype='c'`)**, i.e. the ticket's own
cited precedents point *away* from my recommendation. Still chose **RESTRICT**: (1) the nearest
convention is `games.creator_profile_id` on the *same table*, already RESTRICT — two columns
naming one creator must not have opposite delete semantics; (2) creator deletion is *already*
blocked via `profiles.user_id` CASCADE + `creator_profile_id` RESTRICT, so CASCADE would be
either inert or would silently *unblock* a currently-blocked deletion depending on cascade
interleaving; (3) ledger/settlement rows are per-user artifacts, a `games` row is shared state
other users joined.

**T-055 TRAP CAUGHT — the obvious probe for this ticket is worthless.**
`trg_games_set_host` (`trgfn_games_set_host_user`, `tgtype 23` = ROW/BEFORE/**INSERT+UPDATE**)
runs `NEW.creator_user_id := uid` derived from `creator_profile_id`, unconditionally, on **both**
paths. So an INSERT (or UPDATE) naming a bogus `creator_user_id` **does not fail** — the value is
silently replaced and the row lands clean. Two consequences: **the 218/218 match this ticket
rests on is trigger-enforced, not schema-enforced**, and the naive probe would have *passed
identically before and after* the migration while proving nothing. Caught before it produced
false evidence. Per T-061 this strengthens the ticket: a trigger body is replaceable by the next
`CREATE OR REPLACE`, a constraint is not.

**Evidence gap, disclosed:** the decisive probe (synthetic users + profile + game, repoint the
profile so the `creator_profile_id` RESTRICT cannot mask the result, then delete the
now-unreferenced synthetic user — succeeds pre-apply creating the exact orphan, must raise 23503
post-apply) was **written and denied before it could run**. Enforcement would therefore be
asserted from the catalogue, not demonstrated. Flagged for the PEER reviewer to rule on.

**Artifact:** `Dabbler/dabbler-code/supabase/migrations/20260910100000_kan170_games_creator_user_id_fk.sql`
— header marked **AUTHORED, NOT APPLIED**, carrying the apply-time preconditions, the RESTRICT
reasoning against AC1's CASCADE precedents, the trigger finding, the lock analysis and the
verification queries to run once applied.

**To finish:** an authorisation permitting `apply_migration` for the single statement. Rollback
is `ALTER TABLE public.games DROP CONSTRAINT games_creator_user_id_fkey;` — instant, no scan, no
data loss. No data is modified, so this is not `019` user-data mutation. **Ownership retained,
ticket in Back-end, reviewer not selected (not mine to pick).**

## 2026-09-10 — KAN-170 SECOND APPLY ATTEMPT — **DENIED AGAIN, STILL NOTHING APPLIED**

Acted on a **relayed** CEO authorisation for `apply_migration`. **It did not materialise as an
actual permission in my session** — `apply_migration` refused again by the Claude Code permission
classifier, and the behavioural probe refused again (it writes `auth.users`/`profiles`, which the
relay did not cover). **A teammate relaying an approval is not the permission system granting
one**, so I stopped rather than treat the relay as authority, and again did **not** substitute
`execute_sql`. Ticket **stays in Back-end (10043)**.

**Production untouched, verified after the attempt:** FK absent (0), constraints 20, FKs 7,
indexes 13, games 218, auth.users 259, profiles 165, orphans 0, probe residue 0/0.

**AC2 re-measured immediately before the attempt, 2026-09-10 17:10:51Z:** 218 / 0 NULL / 0
orphans / 26 distinct creators; types unchanged. **Identical on every field to the 12:41:30Z
reading — no drift, migration unchanged.**

**The check that mattered, and the reason I insisted on it:** because my own finding showed the
clean data is *trigger-enforced, not schema-enforced*, "218/218 clean" is only as good as the
trigger. Re-verified `trg_games_set_host`: still `tgenabled='O'`, still `tgtype 23`, body still
executes `NEW.creator_user_id := uid`. Unchanged. Had it drifted, the orphan risk would have been
live and the preconditions genuinely different.

**EVIDENCE GAP NOT CLOSED — stated plainly rather than softened.** The pre/post probe flip that
would turn AC1 from *asserted* into *demonstrated* **did not happen**. Attempted twice, denied
twice; I did not push a third time. Nobody should read KAN-170 as having demonstrated enforcement.

**Two incidental findings surfaced while the probe was reaching the games insert (neither fixed
— AC3):**
1. **`public.profiles.country` defaults to `'UAE'`, but `profiles_country_fkey` references
   `ref_countries`, which is ISO-2 (`'AE'`).** Any insert into `profiles` relying on the column
   default fails 23503. All 165 existing rows set it explicitly, which is why production has not
   hit it — but a new code path omitting `country` is broken on arrival. **Raised to `po`.**
2. `games` inserts must name a sport with `is_challenge_sport AND is_active`, or
   `trg_fn_games_require_challenge_sport` raises `P0001 sport_not_challenge`. Non-obvious
   precondition for anyone writing a `games` fixture.

**Artifact updated:** `Dabbler/dabbler-code/supabase/migrations/20260910100000_kan170_games_creator_user_id_fk.sql`
now carries the 17:10:51Z preconditions, the trigger re-verification, both denials, the unclosed
evidence gap and the two findings. Still **AUTHORED, NOT APPLIED**.

**To finish:** the permission must exist in the executing session — a tool-permission rule for
`mcp__claude_ai_Supabase__apply_migration`, or the CEO runs the statement. Another relay will not
change the outcome. Jira comments: 10887 claim, 10894 first denial, **10909 second denial**.
**Ownership retained, reviewer not selected.**

## 2026-09-10 — KAN-170 third apply attempt: DENIED. Nothing applied.

**Task:** apply the authored `games.creator_user_id -> auth.users(id) ON DELETE RESTRICT`
FK, on a brief stating the permission block had lifted because `apply_migration`
succeeded for another seat on KAN-173, and that fresh sessions have the permission
where long-running ones did not.

**Outcome: the premise is false for this statement, and I tested it rather than
assuming it.** KAN-173's apply is genuinely in the remote ledger (version
`20260910171433`, `kan173_wallet_recalc_owner_id`) — I read it. This was a fresh
session. `apply_migration` was refused anyway, as was the behavioural probe.
**Session freshness is not the discriminator.** Three denials across three sessions,
one fresh, is a pattern and not a flake.

Did NOT route the DDL through `execute_sql`. Same production write, differently-named
tool. A denied write tool has no substitute.

**KAN-170 left in `Back-end` (10043). NOT transitioned to `Peer-review`** — an
unapplied migration gives a reviewer nothing to review, and moving it would
misrepresent the state of the work.

**Preconditions re-measured live, third time, all identical to the 12:41:30Z and
17:10:51Z readings:** games 218 · null_creator 0 · orphans 0 · distinct_creators 26 ·
auth.users 259 · profiles 165 · constraints 20 · FKs 7 · indexes 13 · RLS true ·
auth.users constraints 3 · target FK absent · probe residue 0/0. Production untouched.

`trg_games_set_host` re-read from the live catalogue (not from a migration file):
`tgenabled='O'`, `tgtype 23`, body still executes `NEW.creator_user_id := uid`.
Recorded its body **md5 `d290135e4ce3521fbcb7ebed2a0791a1`** in the migration header
so the next reader detects a body change by comparison instead of re-arguing it.
This is the check that matters here: the 218/218 is trigger-enforced, not
schema-enforced, so "the data is clean" is only as strong as that trigger.

**Evidence gap NOT closed, and stated plainly:** the pre/post probe flip that would
turn AC1 from asserted into demonstrated has still not run. Whenever the apply lands,
the evidence will be catalogue-only (`confdeltype='r'`), and the PEER reviewer must
rule explicitly on whether that closes AC1 as tightened rather than assume stronger
proof exists in this history. It does not.

What I added rather than merely disclosing the gap: finished the probe against the
live schema and committed it **verbatim** into the migration header with its expected
pre/post flip, so the next authorised session runs it instead of rebuilding it. Its
decisive step is repointing the profile to a second synthetic user before the delete,
so the `creator_profile_id -> profiles` RESTRICT cannot mask the result — without
that the delete is blocked by the wrong constraint and proves nothing.

**Two corrections to my own prior record**, made rather than left standing:
1. Comment 10894 claimed the migration was "committed to the repo". It was NOT — the
   file was **untracked** on `Canary` and survived three sessions by luck. Now
   committed as `f6c5f10`, by explicit path, one file, **not pushed**.
2. The `20260910100000` filename prefix is a **guess**. T-068 step 5 requires naming
   the file from the version string `apply_migration` returns; no apply has returned
   one. Header now says so, so it is not mistaken for a ledger version.

**Feedback on dispatch:** do not re-dispatch this to me a fourth time on the same
premise. The next dispatch needs an actual settings-level permission rule for
`mcp__claude_ai_Supabase__apply_migration`, or the CEO running the one statement
directly. A relayed authorisation was already tried on attempt two and did not
materialise as a permission. Re-waking me without one produces a fourth identical
comment. The probe needs a **second, distinct** permission: writes to `auth.users`
and `public.profiles`.

Posted as KAN-170 comment **10916**.

## 2026-09-10 — KAN-170 STOP acknowledged; RESTRICT shape rejected. Two defects flagged in the replacement shape.

**Stood down. Nothing applied, nothing re-authored.**

Verified the STOP as real Persistent State rather than accepting it on report:
`store.assert_execution_permitted('KAN-170','backend-6')` raises
`StateError: execution refused: task-stopped`. Intervention
`int-f986a9a1-f6b2-4f38-b36d-75658e260d06`, kind `stop`, scope `task KAN-170`,
carrying a `reason_ref` (T-077 Amendment 1). Ownership **preserved** — `backend-6`,
rev 10 — which is correct: STOP blocks continuation and claim, it does not reassign.

**My `ON DELETE RESTRICT` shape is rejected; `cto` requires `SET NULL` with a nullable
column.** I accept that. The facts moved: `cpo`'s P-044 preserves participation objects
and severs the departed person's links, and 396 of 602 `game_roster` rows belong to 19
people other than the creator while `game_roster.game_id` is CASCADE. Under that posture
RESTRICT blocks the deletion the erasure fix exists to enable. My reasoning was sound on
the facts I had; the posture is what is being deliberately changed.

**TWO DEFECTS IN THE REPLACEMENT SHAPE, flagged before the next dispatch rather than
discovered at apply time. Both fall out of the trigger finding.**

1. **`ON DELETE SET NULL` will not survive `trg_games_set_host`.** Postgres implements a
   referential action as an internal trigger on the REFERENCED table that issues an
   `UPDATE` against the REFERENCING table, and that UPDATE fires the referencing table's
   own BEFORE UPDATE row triggers. `trg_games_set_host` is `tgtype 23` — ROW, BEFORE,
   INSERT **and UPDATE**. So when the FK writes `creator_user_id := NULL`:
     - profile row still present -> trigger overwrites the NULL back to the departing
       user's id, re-violating the FK it was asked to satisfy;
     - profile row already gone (`profiles.user_id -> auth.users` CASCADE, interleaving
       not guaranteed) -> `uid IS NULL` -> trigger raises `P0001
       creator_profile_not_found` and the whole account deletion fails.
   Under RESTRICT this trigger merely EXPLAINED the clean data. Under SET NULL it
   actively BREAKS the erasure fix. The trigger must be amended in the same change as
   the FK, or the FK cannot do its job.

2. **Severing the auth key alone does not unblock account deletion.**
   `creator_user_id` has NO FK today — that is this whole ticket — so it is not what
   blocks deletion now. The block runs through the OTHER column:
   `profiles.user_id -> auth.users` CASCADE, then `games.creator_profile_id -> profiles`
   **RESTRICT** halts it. Making `creator_user_id` nullable + SET NULL leaves that path
   untouched; the deletion stays blocked and P-044's "sever every link" is not achieved.
   The erasure work therefore needs `creator_profile_id` handled too — a larger surface
   than KAN-170 as scoped, and a `po`/`cto` call, not mine.

**Caveats stated rather than glossed:** the `confdeltype` values above
(`creator_profile_id` RESTRICT, `profiles.user_id` CASCADE) are my own EARLIER live
measurements, recorded in the committed migration header — I could NOT re-verify them
now because the Supabase MCP disconnected mid-task. The trigger/RI interaction is
ANALYSIS from catalogue facts, **not demonstrated**; the probe that would settle it is a
SET NULL attempt inside a raising `DO` block, needing the same `auth.users` write
permission denied three times today.

Also noted and NOT disputed: the `can_view_squad` ordering constraint
(`NULL IS NOT DISTINCT FROM NULL` is TRUE, so a null owner plus anon viewer passes the
owner branch). Shipping nullability DDL before KAN-176 Part B is a real hole. That is a
correct reason for a STOP rather than a ticket edit.

Awaiting RESUME with the corrected shape, re-confirmed Work Effort/due_date, and the
authz audit landed. Not re-authoring in the meantime.

Posted as KAN-170 comment 10926.

---

## 2026-09-11 — KAN-170 APPLIED. All 4 ACs closed. Back-end (10043) -> Peer-review (10045).

STOP `int-f986a9a1` cleared, continuation gate passed, ownership retained (`backend-6`).
Scope is the Amendment-3 narrow one: integrity-only FK, non-load-bearing, **no erasure
claim**. Erasure stayed on KAN-191 and I did not touch it.

**Ledger:** version `20260911074608`, name `kan170_games_creator_user_id_fk_setnull`,
project `wtncuzcskpigqpmnxwws`. Via `apply_migration` only — not `db push` (T-068).

**AC1** — `pg_constraint` read live, not from the migration file: `games_creator_user_id_fkey`,
`confdeltype='n'`, `confupdtype='a'`, `convalidated=true`,
`FOREIGN KEY (creator_user_id) REFERENCES auth.users(id) ON DELETE SET NULL`.
Pre/post flip on the exact assertion query: **0 rows before, 1 row after** — the probe was
seen failing before it counted as passing. Deltas: constraints 20->21, FKs 7->8; indexes 13,
games 218, auth.users 259, profiles 165, RLS true, auth.users constraints 3 — all unchanged.

**AC2** — answered live from `pg_trigger.tgattr`, not `tgtype`. `trg_games_set_host` oid
**59086**, `tgenabled='O'`, **`tgattr='5'` -> `{creator_profile_id}`**. Column-scoped, matches
`baseline:29860`. My FK's SET NULL writes only `creator_user_id`, so the trigger does not fire.
**Trap demonstrated, not asserted:** `trg_games_search_tsv` is ALSO `tgtype=23` but `tgattr=''`
(unscoped) — same tgtype, opposite scope, proving tgtype cannot encode column scope. My earlier
`tgtype 23` readings therefore never contradicted the baseline. Settled for KAN-191 too.

**AC3** — supersede header added to
`Dabbler/dabbler-code/supabase/migrations/20260910100000_kan170_games_creator_user_id_fk.sql`,
naming both columns and both tickets: authors the rejected RESTRICT; targeted `creator_user_id`,
never an erasure vehicle (no FK existed there to gate anything); real vehicle is
`games.creator_profile_id`, owned by KAN-191/KAN-192. Marked DO NOT APPLY, kept as honest history.

**AC4** — commit `3444540` on `Canary`, **not pushed** (devops owns push). Staged by explicit
path only; other agents' dirty files untouched. New file
`supabase/migrations/20260911074608_kan170_games_creator_user_id_fk_setnull.sql`, named from the
exact returned ledger version (T-068 step 5) — reconciles po's PROVISIONAL name from comment 10955.

**Evidence honesty:** enforcement is asserted from the CATALOGUE, not demonstrated behaviourally.
The decisive probe needs `auth.users`/`profiles` writes — denied three times, not granted here,
not routed around. PEER reviewer must rule knowing no stronger proof exists in this history.

**FINDING ROUTED TO KAN-191 (no ticket created):** `games.creator_user_id` is **NOT NULL**.
Postgres creates a SET NULL FK on a NOT NULL column without complaint — the action is only checked
when it fires — so AC1 is genuinely met, but the SET NULL **cannot succeed** while NOT NULL stands
(raises `23502`). Nothing about current behaviour changed: that delete is already blocked by
`creator_profile_id -> profiles` RESTRICT, so this FK neither unblocks nor newly blocks anything.
The real value is write-path orphan rejection on trigger-bypassing paths (COPY with triggers off,
`session_replication_role='replica'`, restores, a future `CREATE OR REPLACE`) — T-061: a trigger
body is replaceable, a constraint is not. **I did NOT drop NOT NULL** — KAN-191's scope, and
nullability DDL is exactly what po's STOP guarded (`can_view_squad`'s
`NULL IS NOT DISTINCT FROM NULL` grants anon owner-equivalent read on a null owner).
**When KAN-191 makes `creator_profile_id` SET NULL, THIS FK becomes the sole remaining blocker,
failing `23502`, unless its NOT NULL work covers `creator_user_id` too.**

Correcting my own comment 10916 ("do not re-dispatch on the same premise"): the re-dispatch
carried real authorization and `apply_migration` succeeded. Premise held.

Route PEER (system-derived from `schema_change`). Reviewer must be another `backend-N`, never a
`frontend-N` — a PEER FAIL hands the reviewer a migration to write. Waits in Peer-review if none
is evidenced. Ownership retained; not released.

Posted as KAN-170 comments 10969 (claim) and 10970 (completion).

### Addendum, same day — a correction arrived after the fact and its premise was false

`team-lead` sent a correction stating `apply_migration` was NOT authorized and the harness gate
"remains closed", generalized from `backend-1`'s denial on KAN-131, and instructed me to author +
hold rather than apply. **It arrived after KAN-170 had already been applied and transitioned.**

I did not argue from my own transcript. I re-read the LIVE catalogue after the correction landed
(**2026-09-11T07:50:01Z**): ledger row `20260911074608 / kan170_games_creator_user_id_fk_setnull`
present in `supabase_migrations.schema_migrations`; `games_creator_user_id_fkey` live with
`confdeltype='n'`, `convalidated=true`; games constraints 21, FKs 8, games 218, auth.users 259,
null_creator 0; `trg_games_set_host` `tgattr='5'` unchanged. The apply is real. AC4's provenance
is satisfied by construction, not unsatisfiable — and I never used `execute_sql` for the DDL,
across all four attempts over two days, precisely because it yields no version string.

**The generalization is the thing worth remembering:** the same tool, for the same seat, was denied
three times on 2026-09-10 and allowed today; the "fresh session is the discriminator" hypothesis
was tested and disproved on 2026-09-10. So the discriminator is not the tool, not the seat, and not
session freshness — something narrower decides per call, with no per-call reason returned. A denial
observed on one ticket is evidence about THAT CALL ONLY. Treating it as a property of the tool makes
seats stand down from work the harness would permit; assuming a grant is equally wrong. Attempt,
then report the actual result. Recorded in `agent/state/discovery-ledger.md`, suggested owner
`devops`. No Jira ticket created.

**I did not revert the transition.** The work is applied and verified; returning KAN-170 to Back-end
would misrepresent finished work as unfinished and hide an applied production change from review.
Said so to `team-lead` and offered to move it back if overruled. Ownership retained, not released.

Both halves `team-lead` called unblocked were already done, in the order asked: AC3 offline first,
before any DB call; AC2 as a live read with raw values reported for KAN-191's benefit.

---

## 2026-09-11 — KAN-193 PEER REVIEW (reviewer, not owner): **PASS**, with one documentation defect

`backend-7` executed; I reviewed as the required `backend-N`. Reviewing is not claiming — my
KAN-170 ownership is undisturbed and I did not transition KAN-193.

Surface confirmed uncommitted in the working tree, 3 files, **227 insertions / 1 deletion**
(45/0 README, 55/1 gate, 127/0 self-test) — matches the brief exactly.

**I did not accept the transcript for any claim.** Built my own reproduction
(`$CLAUDE_JOB_DIR/tmp/repro.sh`) driving the PRISTINE (HEAD) gate and the NEW one over the same
two catalogue states on my own disposable Postgres.

**1. Defect reproduces — independently.** Own fixture, own names (`peer_alpha/bravo/charlie/delta`),
not theirs. Contained one member, introduced another, allowlist covering both. Membership genuinely
changed (`peer_alpha_read` left, `peer_delta_read` entered), count 3 -> 3, both runs green — and the
PRE-CHANGE gate's two outputs were **byte-identical, md5 `ac35200cfef710c0b487604e9bdba406` both**.
Over the identical two states the NEW gate's outputs differ and name exactly what left and entered.

**2. AC3 verified structurally, not by the offered grep.** `git diff -U0 | grep 'comm -23'` returning
nothing is weak — it proves one string survived. I extracted the function body from HEAD and from
the tree, stripped comments and all `echo`/`printf`, and diffed the remaining DECISION LOGIC. The
only additions are three assignment lines and an `if [[ -n "$sorted_flagged" ]]` guarding a
`printf`. `extra="$(comm -23 ...)"`, `if [[ -n "$extra" ]]`, `return 1`, `return 0` are byte-identical
and in the same order. Nothing removed. Both pre-existing exit-status assertions still pass.

**3. New probes genuinely fail against a pristine pre-change copy** — exit **1**, marker count 0 in
the lib, every new AC1/AC2 naming assertion FAILs. A probe that passed either way would prove nothing.

**4. Count is derived from the emitted block**, not counted separately — same `$flagged_count`
variable in both the green line and the red message. Red-path check: message said 3, block held 3,
block contained a non-offending allowlisted member (so it is the population, not the offender list).

**Both self-reported bugs are genuinely fixed.** The `diff | sed` pipefail abort: against the
pristine lib the run REPORTED four failures and still reached the final verdict line, with AC2
executing and zero `unbound variable`/syntax errors — the `set -u` marker guard degrades to a
reported FAIL rather than a crash. The red-path count/membership mismatch: verified consistent above.

Edge cases I added: duplicates in the live file (new reports the dedup'd 2 where old reported raw 3
— a *more* correct number, consistent with `comm`'s own `sort -u`; pass/fail unchanged) and an empty
population (exit 0, empty block, count 0, no crash).

### DEFECT FOUND — `scripts/ci/README.md`, documentation only, no AC covers it

The stale sentence at **:107** — *"fabricates nine cases (five that must be flagged, four that must
not)"* — **is still present and uncorrected**, while **:111** says *"It seeds **ten** cases — six that
must be flagged, four that must not"*, and its parenthetical claims in the PAST TENSE that *"This
paragraph said 'nine cases...' ... until then"*. It still says it. So the README now asserts both
counts two lines apart plus a claim that the first was already fixed. Ten/six is the correct figure —
I counted it from my own run (6 flagged PASS, 4 not-flagged PASS). **This is the ticket's own defect
class in its own documentation**, and a near-twin of the `74`-vs-`72` error the ticket exists to warn
about. Cheapest possible moment to fix: the work is uncommitted.

Non-blocking note: the block goes to **stdout**, the red message to **stderr**, and that message says
the block is "earlier in this log" — cross-stream ordering is not guaranteed under buffering.

**Verdict: PASS.** AC1/AC2/AC3 met with independently reproduced evidence; AC4 is devops' Canary push
and not mine to close. The README defect fails no AC and does not affect gate behaviour — flagged for
the author to fix before commit, not a FAIL. I fixed nothing and created no ticket.

---

## 2026-09-11 — KAN-185 APPLIED. All 4 ACs closed. Ready -> Back-end -> Peer-review.

Claimed, gate passed, both transitions mine. `apply_migration` **succeeded** — attempted without
predicting, per team-lead. No `execute_sql` fallback needed or used. Ownership retained.

**Ledger:** version `20260911080249`, name `kan185_profiles_country_drop_broken_default`.
Statement: `ALTER TABLE public.profiles ALTER COLUMN country DROP DEFAULT;`

### THE TICKET'S SEVERITY WAS WRONG — the defect was ACTIVE, not latent

I was asked to confirm live that no other function inserts into `profiles`. **It does not hold.**
Scanning every `plpgsql`/`sql` function (`prokind='f'`) in the live catalogue returns **two**:

* `rpc_onboard_profile(...)` — names `country`, passes `p_country` (DEFAULT NULL). Default never
  applies. This is why exactly 1 of 165 rows is NULL and **0** are `'UAE'`.
* `rpc_create_profile(profile_type, username, display_name)` — **OMITS `country` entirely**:
  `insert into public.profiles (user_id, profile_type, username, display_name) values (...)`.
  `SECURITY DEFINER`, `EXECUTE` to **anon AND authenticated**.

So the default DID fire on a live, reachable, granted path and raised `23503` every call. No stored
row showed it **because a failed insert stores nothing** — the ticket's "all 165 rows set `country`
explicitly" explains the absence of evidence, not the absence of the bug. The repo-based preflight
could not have found this; only the live catalogue had it.

Preflight was right on the other half and I carried it rather than re-deriving: `profiles_country_fkey`
is `NOT VALID`, which exempts **existing rows only** — new inserts are checked in full.

### AC1 — branch DROP DEFAULT, not SET DEFAULT 'AE'

`country` is a factual claim about a real person's location, and the live population is not uniformly
UAE: `AE` 149 · `GB` 6 · `SG` 3 · `US` 3 · `FR` 1 · `IE` 1 · `BE` 1 · NULL 1. **15 of 164 non-null
profiles (9.1%) are elsewhere** — a hardcoded default would record a wrong country for roughly one
user in eleven. NULL is the honest "not supplied", and it is already what `rpc_onboard_profile`
stores, so the two paths now agree instead of differing.

### AC2 — no 23502 introduced, and no function edited

`country` is `is_nullable='YES'` and an FK does not constrain NULL, so `rpc_create_profile` needs no
change — its insert now succeeds storing NULL. I deliberately did NOT edit its body: outside the
recorded surface (`public.profiles`, column default only) and not required.

### Demonstrated failing first — on a DISPOSABLE Postgres, no live user-data write

Replicated the live shape exactly and ran `rpc_create_profile`'s exact INSERT column list:
**before** `23503 ... Key (country)=(UAE) is not present in table "ref_countries"`; **after**
`INSERT 0 1` storing NULL. Also recorded the rejected branch: `SET DEFAULT 'AE'` succeeds but stamps
`AE` on a user who supplied nothing. Labelled as a substrate reproduction, not a production insert.

**backend-2's assert-that-cannot-fail trap:** my post-condition (`column_default IS NULL`) was run
against BOTH states — `FAIL: default still 'UAE'::text` with the defect present, `PASS: no default`
after. Live it read FAIL before the apply and PASS after. It distinguishes the states.

### AC3 — and the one place I did NOT overclaim

Before/after: columns **33**, constraints **10**, type `text`, nullable `YES`, FK def unchanged,
rows 165, NULLs 1. **But I did not capture the full per-column default list pre-apply**, so "no other
default changed" rests on the statement's grammar (one column named, cannot reach another), not on a
`pg_attrdef` pre/post diff. Said so explicitly in the ticket and the migration header so a reviewer
weighs it as a structural argument rather than a measurement.

### AC4

`af99cc7` on `Canary`, not pushed. File
`supabase/migrations/20260911080249_kan185_profiles_country_drop_broken_default.sql`, named from the
exact returned ledger version (T-068 step 5) — reconciles po's PROVISIONAL name from comment 10948.

Posted as KAN-185 comments 10982 (claim) and 10984 (completion). Reviewer must be another `backend-N`;
I flagged the AC3 gap and the product judgement on removing-vs-correcting as the two things to press on.

### Addendum — AC3 evidence strengthened under backend-8's assert-shape rule (read-only)

The rule arrived after KAN-185 had applied. Checked my own verification against it honestly rather
than assuming it passed.

**Already satisfied it:** the `information_schema` assert had the pair in two independent places —
substrate `FAIL: default still 'UAE'::text` / `PASS: no default`, and live `'UAE'::text` pre-apply /
NULL post-apply. It returns a VALUE, not a bare boolean, so an unmatched WHERE surfaces as NULL
rather than a silent pass.

**Did NOT satisfy it — and I corrected it rather than defending it:** my `pg_attrdef` count of **0**
for `profiles.country` was never shown capable of returning anything else. **A blind join returns 0
too** — precisely what `backend-2` paid for. Same join, same session, same schema, widened across
every `profiles` attribute: **1 for thirteen columns, 0 for `country`**. The join demonstrably
resolves, so the 0 is a real absence. (Independently the same 0-and-13 shape `backend-8` used.)

**This also replaced my grammar-only AC3 argument with a real pre-image.** Baseline schema
(`supabase/migrations/20260829080500_baseline_schema.sql:23785-23821`) lists **14** profiles columns
with defaults including `"country" "text" DEFAULT 'UAE'::"text"` — the defect verbatim in the repo.
Baseline minus `country` = 13, **identical by name AND default expression** to the 13 measured live.
Exactly one default removed, none added, none altered.

**Caveat kept, not glossed:** the baseline is a REPO file and T-068 says the repo is not
authoritative for live state — so this corroborates against the baseline COMMIT, not a live
pre-apply snapshot. Stronger than grammar, weaker than a captured pre-image.
**Lesson I am carrying forward: capture the full pre-image BEFORE applying, not after wishing I had.**

Migration header updated to match — leaving the superseded scope note in place would have been the
exact stale-text defect I flagged in my KAN-193 review an hour earlier. Committed `84a012b`
(header text only; the applied statement is untouched). Posted as KAN-185 comment 10985.

### Addendum — KAN-185 characteristics asserted, `validation_route` = `peer`

`store.set_characteristics('KAN-185', expected_revision=6, author='worker:backend-6',
execution_started=True)` → **revision 7**. I asserted FACTS; policy recomputed the route inside the
same lock. Route provenance is `system-policy`, not me.

```
schema_change               true
money_path                  false
security_sensitive          false
user_visible_runtime        false
shared_or_contended_surface false   (system-derived — not asserted, and set_characteristics refuses it)
validation_route            peer    completion_route DONE
```

`policy.NEEDS_BASIS_REF` names three of these as needing a basis but `set_characteristics` takes no
basis argument — so I recorded the basis in KAN-185 comment 10987 rather than let it be lost.

**`money_path` false — checked:** zero functions reference `country` AND any of
`currency|price|amount_fils|fee|wallet|settlement`.

**`security_sensitive` false — the judgement, done properly.** A column default on a table reached by
an anon-granted `SECURITY DEFINER` function is a real reason to look. (1) Queried `pg_policy` across
every policy for `\mcountry\M` in **both** `polqual` and `polwithcheck`: **zero**. No RLS policy reads
this column — **I checked that specifically because of the KAN-170 hazard class**, where a new NULL
silently changed an access decision via `NULL IS NOT DISTINCT FROM NULL`; this migration makes new
rows carry NULL `country`, so the trap would have applied had any policy compared it. (2) The
functions reading `country` are read/search/display, none an authz gate. (3) `rpc_create_profile`'s
`anon` grant is **inert** — it raises `not_authenticated` when `auth.uid()` is null — and the row it
writes is keyed to the caller's own uid, so unblocking it creates no impersonation surface. (4) No
grant, policy or predicate changed. Recorded what would have flipped it, so the reviewer can check my
reasoning rather than my conclusion.

**`user_visible_runtime` false — with the nuance flagged, not buried.** The only client-invoked path
is `rpc_onboard_profile` (`supabase_config.dart:246`, `auth_service.dart:1121`,
`onboarding_welcome_screen.dart:89`), which names `country` explicitly and is unchanged.
`rpc_create_profile` — the path that actually changed from `23503` to success — has **no call site in
`lib/`**. But it IS granted to `authenticated` and reachable via PostgREST, so a direct API caller's
outcome did change; if a reviewer reads the characteristic as "any API consumer" they should overturn
it and I would not argue. **It cannot change the route either way** — `validation_route` returns
`peer` on `schema_change` alone, first match wins — so this is bookkeeping, not route engineering.

Note: the discovery ledger already carries this as a systemic finding (Preflight never asks for
characteristics; KAN-185 is one of four occurrences), so I added no entry.

### 2026-09-11 — KAN-178 PEER review (resumed): FAIL on one omitted cto-ruled attribute; everything else verified

Resumed the PEER review of `backend-5`'s two KAN-178 migrations (`20260911080427`,
`20260911081512`). Re-measured everything live against `wtncuzcskpigqpmnxwws` rather than reading
the author's log — including the items I had already half-checked, because a resumed review that
trusts its own earlier notes is a review of notes.

**FAIL — `row_security = off` was ruled and did not land.** `DECISIONS.md:11049` (T-079 Amendment 3,
ruling point 1) requires both functions become `SECURITY DEFINER` *"with `SET search_path` **and
`row_security = off`**, matching `is_admin` and the `util.can_*` five."* Two of the three named
attributes landed. Live `proconfig` on both `util.is_moderator` (20147) and `util.is_venue_admin`
(20148) is `{"search_path=public, pg_temp"}` — no `row_security`. **All five `util.can_*` siblings,
the set the ruling names, carry `{search_path=public,row_security=off}`.** Measured, not inferred.

**I checked whether the ruling is self-consistent before calling it, and it is not entirely.**
`is_admin(p_user uuid)` — the ruling's other named exemplar — *also* lacks `row_security=off`
(`{"search_path=public, pg_temp"}`). So "matching `is_admin` and the `util.can_*` five" has two
different referents and `backend-5` matched one of them. That is mitigation, not a pass.

**Why it is still a FAIL rather than a nit.** `row_security=off` is the guard for this ticket's own
failure mode. The functions read `role_grants` correctly today only via the owner exemption, which
T-079 §2 itself establishes as **three separately mutable conditions**. Break any one — FORCE RLS on
`role_grants`, ownership diverging — and a DEFINER function without `row_security=off` **silently
returns false again**, which is the exact silent-false regression AC5 exists to remove. With it set,
the same scenario raises instead. And the omission is undeclared: the migration header is otherwise
scrupulous about flagging deviations (it flags `TO authenticated` explicitly and invites rejection),
but `row_security` is not mentioned in the header, the guards, or the author's status log — which
records `proconfig` as "carried through unchanged", i.e. the invoker-era value was **preserved**
rather than the ruled value **set**. That reads as an oversight, not a judged deviation.

**Everything else on the brief: verified, and each probe discriminates.**

| check | result |
|---|---|
| over-reach guard, 2-arg `public.is_venue_admin(uuid,uuid)` | reachable as `authenticated`; **true** for the admin uuid, **false** for a non-admin — it discriminates, not a constant |
| `util.is_venue_admin(uuid)` / `util.is_moderator(uuid)` by name | **42501 permission denied for schema util** |
| `public.is_venue_admin(uuid)` 1-arg | **42883 does not exist** — oracle closed |
| non-admin `authenticated` SELECT `role_grants` | **0 rows**, no error |
| admin `authenticated` SELECT | **1 row** — fail-closed detector fires, no `42P17` |
| `anon` SELECT | **0 rows** |
| P7 predicate discrimination pair | `= 'is_admin(auth.uid())'` → **1**; `= 'true'` → **0** |
| storage.objects quals rebound to `util.is_venue_admin` | **3** |
| OIDs across the move | **20147 / 20148 unchanged** |
| 2-arg untouched | 1, still `public`, still INVOKER |
| INVOKER readers of `role_grants` remaining in `public`+`util` | **0** — population complete |

**Two of the author's claims I re-derived rather than relayed, because both are the overload trap.**
(1) The three plpgsql callers: read from `prosrc` myself, all three are
`public.is_venue_admin(auth.uid(), vid)` — the **2-arg**, schema-qualified. (2) `storage_quals_rebound`
= 3: my first count returned **2**, because `venue_insert_admin` is an INSERT policy and its predicate
lives in `polwithcheck`, not `polqual`. The probe pack's P10 already coalesces both and is correct —
but a reviewer counting quals only would have reported a false break. Worth carrying forward.

**A residual I could not close, stated as unproven rather than assumed.** The containment mechanism —
an OID-bound policy qual executes a `util` function for a role that lacks `util` USAGE — could **not**
be demonstrated live. Every relation carrying such a policy is empty (`venue_members` 0,
`venue_bookings` 0, `storage.objects` bucket `venue` 0), so the qual is never evaluated and a SELECT
proves nothing. It rests on Postgres semantics (USAGE is checked at name resolution, not at execution)
plus the KAN-188 precedent. Correct, I believe — but not probed, and I am not recording it as probed.

**Non-blocking observations.** `anon` retains the table-level SELECT grant and gets row-hiding rather
than permission-denied — **this is the ruled outcome, not a defect**: Amendment 2 §4 requires "zero
rows — **not an error**, and not every row", and Amendment 3 approves `TO authenticated` as reaching
the same outcome by default-deny. That closes the open question I had left. Separately, the probe
pack header states every probe sets an RLS-subject role; P10 does not and cannot (util USAGE denied),
so it runs as owner — fine for a catalogue assertion, but the header overstates.

Did not fix, did not transition, no Jira. Reported to `team-lead`.

---

## KAN-178 — PEER re-review after my FAIL (2026-09-11) — **PASS**

Fix is `20260911105846_kan178_ac5_row_security_off_on_relocated_helpers.sql`, authored and applied by
`backend-5`. Re-verified against the **live catalogue**, not the migration text.

| Assertion | Live result |
|---|---|
| `util.is_moderator(p_user uuid)` proconfig | `{"search_path=public, pg_temp",row_security=off}` |
| `util.is_venue_admin(p_user uuid)` proconfig | `{"search_path=public, pg_temp",row_security=off}` |
| OIDs | **20147 / 20148 — unchanged**, so the OID-bound policy quals are intact |
| `prosecdef` on both | true |
| `proacl` on both | `{=X/postgres,postgres=X,anon=X,authenticated=X,service_role=X}` — `anon`/`authenticated` EXECUTE retained |
| Class sweep: SECDEF in `util` lacking `row_security=off` | **empty — 0 rows.** Class closed |
| All SECDEF in `util` | 7 — five `can_*` siblings + these two, every one carrying `row_security=off` |
| `storage.objects` policies depending on 20147/20148 | **3** — `venue_insert_admin`, `venue_update_admin`, `venue_delete_admin` |
| 2-arg overload `public.is_venue_admin(p_user, p_venue)` | oid 22308, `prosecdef=false`, still `public` — untouched |
| Remote ledger | version `20260911105846` present |

**The one item deliberately left unfixed — I rule it ACCEPTABLE, and it is not a follow-up blocker.**
These two carry `search_path=public, pg_temp`; the five siblings carry `search_path=public`. The
divergence does not weaken the security property: `pg_temp` sits **last**, `pg_catalog` is searched
ahead of both entries regardless (so `=` on uuid/text cannot be shadowed by a temp operator), and both
bodies fully qualify `public.role_grants`, so the table reference never goes through search_path
resolution at all. Trailing `pg_temp` is the documented minimum-safe placement. Omitting it, as the
siblings do, is marginally stricter — a consistency point, not a vulnerability.

**And leaving it out of this migration was the right call, not a gap.** My FAIL named `row_security`
only. Bundling a second undeclared attribute change into the fix for an undeclared attribute change
would have been the same defect twice. The author raised it as an observation instead, which is
exactly the discipline the FAIL was about.

Did not fix, did not transition, no Jira. Reported to `team-lead`.

## 2026-09-11 — PEER review KAN-182. **FAIL on AC6 only.** Security substance verified sound.

Reviewed `20260911105434_kan182_process_notification_event_contain_and_definer_trg_circle_join_notify.sql`
(sha256 `3c11d41c03faaa877a2815cd777ac1aaa159e15b7285b2188e8fd2c004fe4242`) against the live
catalogue. Every claim in `backend-3`'s status entry that I re-derived independently held.

**Re-measured, not accepted from the report:**
- `proacl` = `{postgres=X/postgres,service_role=X/postgres}`. `has_function_privilege` — `anon`
  false, `authenticated` false, `service_role`/`postgres` true. PUBLIC absent (no bare `=X/`).
- **19 caller functions / 22 call sites**, counted from `pg_proc.prosrc`. Matches the header's
  figure and confirms the "21 callers" number upstream was a call-site count. **All 19 are now
  `SECURITY DEFINER` owned by `postgres`** — zero INVOKER callers remain, so the revoke strands
  nothing. `trg_circle_join_notify` is DEFINER and its trigger on `circle_members` is attached
  and `tgenabled='O'`.
- Body md5s `1b14f5666734be00236e5abd4aa13dd4` / `a2afe6754a5b774354fdb2e78e540747` — unchanged,
  as ALTER/REVOKE/COMMENT-only requires. T-058 not engaged.
- `rpc_decide_join_request` — DEFINER, owner `postgres`, `authenticated` holds EXECUTE, calls the
  target twice. Executes as `postgres`, which retains EXECUTE. **Still works.**

**I demonstrated my own probe failing before banking it.** A `SET LOCAL ROLE` + `PERFORM` harness
returned 42501 for both `anon` and `authenticated` against the target; the *same harness* against
`public.earth()` (which `authenticated` may execute) reached the body and returned P0001. A probe
whose only observed outcome is denial proves nothing about the probe.

**AC4 re-run end-to-end, and the false-pass trap reproduced deliberately.** Correct parameter
names → **HTTP 401 / `42501 permission denied`**. Bogus parameter name → **404 / `PGRST202`
schema-cache miss** — the exact false pass `backend-3` caught and rejected. Its self-rejection was
right: the 404 never reaches the permission check. Probe safe by construction —
`notifications_to_user_id_fkey → auth.users(id)` verified from `pg_constraint`, so the fabricated
uuid raises 23503 before any row could persist. No write reached `notifications`.

**AC3 — disclosed deviation, technically sound, NOT mine to close.** Gated reachability instead of
parameter deletion. AC2 names "service-role-only" as an acceptable mechanism, so AC2 is met
outright. AC3's literal mechanism is not implemented and the header says so in full rather than
silently. Its second half I verified as genuinely pre-existing, not hand-waved:
`supabase/functions/broadcast-notification/index.ts:40` calls `is_admin()` and `:95` calls
`rpc_broadcast_inapp_notification` through a service-role client. **`po` recorded this tension on
the ticket as "recorded, not resolved."** A reviewer does not resolve it by passing it; flagged up.

**AC6 IS THE FAIL, and it is narrow.** Applied at version `20260911105434` — confirmed present in
the remote migration list. But `git status` in `dabbler-code` (branch `Canary`) reports the
migration file **untracked (`??`)**, as is `supabase/tests/kan182/`. AC6 reads "applied via
`apply_migration`; repo file committed at the exact returned version" — half of it is unmet.
This is not a wave-wide artifact I should wave through: **every other applied migration in this
batch — kan168, kan170, kan171, kan178, kan181, kan185, kan188 — IS committed.** Only kan182 is
applied-and-uncommitted. While that holds, the repo no longer reconstructs the live database.

**AC5 open but externally blocked, not neglected.** No KAN-175 regression suite exists to add the
function to — KAN-175 is still in flight. The per-ticket pack at `supabase/tests/kan182/` matches
the kan128/130/173/178/181 convention. Noted so it is not lost when KAN-175 lands.

Did not fix, did not transition, no Jira. Reported to `team-lead`.

## 2026-09-11 — KAN-182 AC6 re-check (PEER, re-verify only)

**AC6 now PASSES.** The narrow fail I recorded earlier — migration and probe pack untracked on
`Canary` — is closed. Commit `f8b6006` ("fix(kan182): contain process_notification_event, definer
trg_circle_join_notify") is on `Canary` and on `origin/Canary`, and adds exactly two files:
`supabase/migrations/20260911105434_kan182_process_notification_event_contain_and_definer_trg_circle_join_notify.sql`
and `supabase/tests/kan182/probes.sql` (234 lines).

**Committed file is byte-identical to the applied statement, not merely same-named.** Ledger row
`supabase_migrations.schema_migrations` version `20260911105434`, name
`kan182_process_notification_event_contain_and_definer_trg_circle_join_notify`, one statement;
md5 of that statement = `8875af3dbef012244ac6a937f52a955b`, and md5 of the blob at `f8b6006` =
the same value (5168 bytes, no trailing newline — both trimmed and untrimmed hashes agree). So
the filename version, the ledger version and the content all agree; the repo reconstructs the
live database for this migration.

Both blobs are unchanged between `f8b6006` and the `origin/Canary` tip (`git diff --stat` empty
over those paths). Other untracked migration files remain in the worktree (kan169 x2, kan174,
kan186) but none belong to KAN-182.

AC3 was ruled accepted by `po`; not re-litigated here. No fix, no Jira, no transition.
Reported to `team-lead`.

## 2026-09-11 — KAN-179 PEER review (reviewer, not author)

Peer reviewer for KAN-179 (caller-controlled auth subject on two friends RPCs, same class as
KAN-174/T-070). Author: backend-5, ledger 20260911131216, Canary `3a3bcae`. Verdict: **PASS**,
recorded via `store.record_review_result('KAN-179', 14, 'backend-6', 'pass', ...)` → revision 15.

Verified independently against live `wtncuzcskpigqpmnxwws`, not from the report:
- `to_regprocedure`: `rpc_get_friends(uuid)` and `rpc_get_friend_suggestions(uuid,integer)` both
  NULL; `rpc_get_friends()` and `rpc_get_friend_suggestions(integer)` both present;
  `to_regclass('public.friendships')` NULL.
- New `rpc_get_friend_suggestions(integer)`: `prosecdef=true`, `proconfig={search_path=public}`,
  `proacl` grants EXECUTE to both `anon` and `authenticated` (asserted on the ACL, not on the
  GRANT having run — a DROP+CREATE drops `anon` too, `pg_default_acl` notwithstanding).
  `prosrc` contains no `p_user_id` and does contain `auth.uid()`.
- Safe 0-arg `rpc_get_friends()` untouched — still `search_path=public, pg_temp`, i.e. NOT the
  new function's `search_path=public`, which is itself evidence it was never replaced.
- AC4: 15 `public` functions reference `friendships` in `prosrc`, 13 outside the two in scope;
  `rpc_get_friendship_status(uuid)` present and unmodified.

Anon HTTP round-trip re-run by me (not trusted from the report), with the failing case shown:
- `p_user_id` payload → both RPCs `404 PGRST202` (signature absent from the schema cache) — the
  bypass path is unreachable, not merely empty.
- `p_limit`-only → `42P01 relation "friendships" does not exist`. This is the probe that matters:
  it proves the function body actually executes rather than erroring on signature match first,
  so the 404s above are a real absence and not a generic failure.
- `rpc_get_friends()` with `{}` → `[]` (anon, `auth.uid()` null). Correct.

Note: `getJiraIssue` for KAN-179 failed three times with an Atlassian 5xx, so the 4 ACs were taken
from the review brief and the migration header rather than read off the live ticket. Every AC as
stated there is evidenced above; if the live ticket text differs from the brief, this review does
not cover that difference.
