# agent/status/senior-backend.md

**Owner:** `senior-backend` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

_No entries yet._

## 2026-09-06 — KAN-128 AUTHORED, both sittings (`team-lead` dispatch)

**Did.** Authored the migration and the AC-3 probe pack. **Nothing applied to
`wtncuzcskpigqpmnxwws`; nothing pushed.** Live Supabase access was read-only throughout
(`pg_get_functiondef`, `pg_proc`, `pg_default_acl`, `information_schema`, row counts).

**Touched.** `Dabbler/dabbler-code/supabase/migrations/20260909090000_kan128_ledger_unique_keys_and_on_conflict.sql`
(new), `Dabbler/dabbler-code/supabase/tests/kan128/` (new: harness prelude, fixtures, probe
pack, `run.sh`), this file. Local commit `93d6619`. Committed by explicit path — another agent
had `lib/app/` changes staged in that repo's index and they are untouched.

**Sitting 1 — the migration.** `ALTER COLUMN ref_id SET NOT NULL`; `UNIQUE (ref_type, ref_id,
direction)` on `wallet_ledger`; partial `UNIQUE (payment_intent_id, entity_type, entry_type)
WHERE payment_intent_id IS NOT NULL` on `financial_ledger`; `T-049`'s table-comment correction
("append-only" → amount-immutable); seven `ON CONFLICT DO NOTHING` clauses across five
functions. `admin_wallet_adjust` is `DROP` + `CREATE` + `REVOKE` + re-`GRANT`. One transaction.

**Live catalogue vs baseline: NO DRIFT.** All five definitions match the baseline text exactly,
and the attributes match the corrected table in KAN-128 — four `SECURITY DEFINER` with
`search_path` `'public'`, `trgfn_payment_to_ledger` neither. Every body authored from
`pg_get_functiondef` regardless.

**Sitting 2 — probes, executed pre and post.** Built a throwaway local harness
(`supabase/postgres:15.8.1.060`, which ships the supabase roles, `auth.users` and `auth.uid()`);
the baseline loads into it with **zero errors**. Every probe demonstrated failing pre-index and
passing post-index. `P1a` 2 rows → `23505`; `P1b` 2 → 1 absorbed through the writer; `P2`
reversal still 2 on both sides (no regression); `P4` arity 5 → 6, distinct keys not collapsed,
null `ref_id` rejected; `P5` 2 → 1, and NULL-`payment_intent` rows still 2 (the partial index
does not over-collapse). `P3` blocked — see below.

**One defect the probes caught in my own first draft.** `REVOKE ... FROM PUBLIC` is **not
sufficient** on this project. `pg_default_acl` carries two function entries for schema `public`
(grantors `supabase_admin` and `postgres`) and **both include `anon=X`**, so a freshly created
function is granted to `anon` **by name**, not only via `PUBLIC`. Measured live. My first draft
followed the ticket exactly and left `anon=X/postgres` standing on the new
`admin_wallet_adjust` — the precise outcome `cto` ruled against. Added an explicit
`REVOKE ... FROM anon`; `proacl` now reads `{postgres=X/postgres,authenticated=X/postgres,
service_role=X/postgres}`. **The ticket's grant trap is incomplete as written** and needs this
correction, or the same mistake recurs in `KAN-130`/`KAN-131`.

**Three dead money paths, not one. None changes the migration; all change what AC 3 can claim.**

1. **`settle_game` cannot execute — a `T-055`-shaped defect nobody had found.** Its
   `game_settlements` insert passes `case when p_finalize then 'settled' else 'pending' end`
   into `status`, which is `settlement_status`. Two unknown literals in a `CASE` resolve to
   `text`, and there is **no cast from `text` to `settlement_status`** — confirmed live:
   `pg_typeof(...)` = `text`, `pg_cast` count = 0, `status` is `settlement_status`. It raises
   `42804` before reaching the credit insert. **AC 3 says this probe "is genuinely live, not
   dormant." It is not.** Falsifiability condition 3 — the one I added — is what caught it.
2. **`_wallet_recalc` blocks every `wallet_ledger` write, and no fixture works around it.**
   `trg_wallet_ledger_recalc` fires on every insert/update/delete; `_wallet_recalc` upserts
   `wallets(user_id, balance_aed, held_aed)` and omits `owner_id`, which is `NOT NULL` with no
   default (all confirmed live). Postgres enforces `NOT NULL` at tuple formation, **before** the
   `ON CONFLICT` arbiter is consulted, so it fails `23502` **even when a `wallets` row already
   exists**. `wallets` holds 0 rows. So today **no row can be written to `wallet_ledger` at
   all**, by any of its four writers. This is `KAN-130`/`T-051` territory, not mine to fix.
3. **`trgfn_payment_to_ledger`** — already known (`T-055`), unchanged.

**Consequence for AC 3, stated plainly.** Probes `P1`–`P4` all write `wallet_ledger` and
therefore **cannot run against the schema as deployed**. I ran them under a **declared harness
deviation** — `trg_wallet_ledger_recalc` disabled — which is a departure from falsifiability
condition 2 ("the schema as deployed"). It is sound for what is under test (a recalc trigger has
no bearing on whether a `UNIQUE` index holds) but it is **weaker than an unqualified pass**, and
the probe pack says so in its own output rather than hiding it. `P5` needs no deviation. `P3`
fails condition 3 on **both** sides and is reported blocked, not passing.

**Decided.** Left `idx_wallet_ledger_ref` and `idx_ledger_payment` in place (unrelated cleanup).
Added an explicit `ref_id_required` guard in `admin_wallet_adjust` so the failure names its
cause. Placed `p_ref_id` **fourth**, not last — it carries no `DEFAULT` (a per-call mint is the
guarantee `T-049` refuses) and a non-defaulted parameter cannot follow defaulted ones.

**Did not verify.** That the migration applies to `wtncuzcskpigqpmnxwws` — that is `cto`'s slot
and this seat may not. The harness is not the deployed database: it differs in the extensions
the `--schema-only` dump omits and in platform tables no probe touches.

**Blocked.** Nothing on this ticket. Owed to `po`/`cto`: the `anon` grant correction, and a
ruling on whether AC 3 is satisfiable as written given findings 1 and 2.

## 2026-09-06 — Skills audit of this seat (survey, `team-lead` dispatch)

**Did.** Read-only survey. No SQL run, no migration touched, no Supabase call of any kind.
Read `agent/roles/senior-backend.md` (98 lines), `ls agent/skills/` (74), `agent/skills/AVAILABLE.md`,
`Dabbler/dabbler-docs/CONTRACT.md` §3, and opened the bodies of nine candidate `SKILL.md` files.

**Touched.** This file only.

**Decided.**
- Two skills claimed as core to this seat: `supabase` (repo, 112 lines + `references/`) and
  `supabase-postgres-best-practices` (repo, 64 lines + **34** reference files, wired to zero seats today).
- One repo skill claimed with a carve-out: `diagnosing-bugs`, for the feedback-loop discipline
  applied to a SQL probe rather than a test.
- Rejected after opening: `backend-patterns` (Node/Express/Next.js REST, not Postgres),
  `security-review` (`process.env` / TS web-app checklist), `verification-quality`
  (`npx ruflo` CI catalogue for the claude-flow repo, not this product), `system-design`,
  `tdd`, `domain-modeling` for this seat. `ddia-systems` accepted as reference-only, not a routine.
- The six mobile-security skills `cto` claims are all client-side; only `network-security-check`
  even mentions Postgres/RLS. **None of them is mine.** The database-security gap is real and unfilled.
- **Conflict found and flagged, not resolved:** the repo `supabase` skill's "Making and Committing
  Schema Changes" section instructs the reader to change schema with `execute_sql` and to iterate
  live. For this seat that is a `CONTRACT.md` §3 / decision `019` violation — `cto` is the only seat
  that may apply. The skill is safe for this seat only with that section carved out. Raised to
  `team-lead`; not amended (skills are not this seat's write surface).

**Blocked.** Nothing. Survey answered in full; no follow-up owed by this seat.

## 2026-09-06 — KAN-128 capacity: this seat sizes its own authoring (`team-lead` dispatch)

**Did.** Read-only. No SQL run, no migration authored, no Supabase call of any kind — every
figure below comes from `grep`/`sed` over
`Dabbler/dabbler-code/supabase/migrations/20260829080500_baseline_schema.sql` (39,291 lines),
plus `Dabbler/dabbler-docs/DECISIONS.md` `T-049`, KAN-128 and its three comments (10554/10555/10558),
`agent/skills/capacity-to-date/SKILL.md` and `agent/skills/money-write-invariants/SKILL.md`.

**Touched.** This file only.

**Number.** **2 sittings on this seat**, plus **2 gates on other seats** (`po`'s AC-3 review;
`cto`'s apply under `G-002`). Ceiling **3 sittings** — 2 plus one rework cycle, because AC 3's
probes run against `cto`'s applied database and a failure there returns the work here. **No date
set** — the calendar mapping is `po`'s (`capacity-to-date` §2 input 4). I agree with
`team-lead-4`'s count and with where it put the checkpoint.

- **Sitting 1 — mechanical.** Read the five live definitions via
  `pg_get_functiondef(...::regproc)`; DDL (`ALTER COLUMN ref_id SET NOT NULL`, `UNIQUE
  (ref_type, ref_id, direction)` on `wallet_ledger`, partial `UNIQUE (payment_intent_id,
  entity_type, entry_type)` on `financial_ledger`, `T-049`'s table-comment correction);
  `CREATE OR REPLACE` on the four signature-stable functions covering **6 of 7** insert sites —
  `admin_cancel_payout:2211`, `request_payout:10200`, `settle_game:17154`,
  `trgfn_payment_to_ledger:19215/:19226/:19237`.
- **Checkpoint.** Migration file holds the constraints and 6 of 7 conflict clauses;
  `admin_wallet_adjust` untouched. Reviewable and abandonable — and **not applicable**, because
  `ref_id NOT NULL` breaks `admin_wallet_adjust:2982` until sitting 2 lands. That un-appliability
  is what makes it a checkpoint rather than a partial finish.
- **Sitting 2 — the judgement.** `admin_wallet_adjust` is **not** a `CREATE OR REPLACE`:
  adding `p_ref_id uuid` changes the argument list, which produces an **overload**, not a
  replacement. It needs `DROP FUNCTION public.admin_wallet_adjust(uuid, ledger_direction,
  numeric, text, jsonb)` — dropping the NULL-writing path rather than leaving it callable —
  then `CREATE`, then re-`GRANT` to `anon`/`authenticated`/`service_role` (baseline
  `:34693`–`:34695`), which the `DROP` removes silently. The judgement inside it: the new
  parameter carries **no** `DEFAULT gen_random_uuid()`, because a per-call mint is exactly the
  guarantee `T-049` refuses. Then AC-3's four probes and the `G-002` ticket comment.

**Decided / found — three corrections to the measured scope, each re-read at the line:**

1. **KAN-128 AC 1 is wrong about `SECURITY DEFINER`.** It says *"None of the five is
   `SECURITY DEFINER`"*, generalising from the one function it checked
   (`trgfn_payment_to_ledger:19163`, correctly `LANGUAGE plpgsql` only). **Four of five are:**
   `admin_cancel_payout:2183`, `admin_wallet_adjust:2975`, `request_payout:10168`,
   `settle_game:17080`. `CREATE OR REPLACE` drops it. Following the AC literally would demote
   four money RPCs to `SECURITY INVOKER` — a privilege regression on the only paths that write
   `payouts` and `wallet_ledger`, whose table comment (`:26940`) states *"Only SECURITY DEFINER
   engine functions insert rows."*
2. **AC 1's `search_path` string is wrong for the same four.** They carry
   `SET search_path TO 'public'` — **no `pg_temp`**. Only `trgfn_payment_to_ledger:19166`
   carries `'public', 'pg_temp'`. `T-044`/`CONVENTIONS.md` §6c says *restate what is there*;
   restating the AC's string would silently change four functions' resolution scope.
   **Mitigation, and why neither corrections adds a sitting:** I author from
   `pg_get_functiondef` on the live catalogue, which is immune to both errors. The AC still
   needs correcting so review does not fail correct work.
3. **`admin_wallet_adjust`'s signature change breaks zero callers.**
   `grep -rnEi "admin_wallet_adjust|settle_game|request_payout|admin_cancel_payout|admin_approve_payout" lib supabase/functions`
   returns **nothing**. No client coordination is owed.

**Confirmed as measured.** All five `CREATE OR REPLACE` lines and all seven insert lines match
the brief exactly. `admin_approve_payout:2138` is `UPDATE`-only (`:2155`–`:2157`) — not an insert
site. `payment_intents` has **zero** SQL writers; the only Dart use is a `.select()` read at
`lib/features/profile/services/data_export_service.dart:932`. `wallet_ledger.ref_id` is nullable
(`:26929`) with only a non-unique btree on `(ref_type, ref_id)` (`:29421`); `financial_ledger`
has only a plain btree on `payment_intent_id` (`:28701`) — both constraints are genuinely absent.

**`payment_intents` half — declared unsizeable.** Its sitting count depends on the shape of a
writer that does not exist, so per `capacity-to-date` §4: *cannot size until a `payment_intents`
writer is designed, and `cto`/`po` hold that.* The DDL alone is two index statements, well under
one sitting, and **must not ship alone** — `cto`'s `T-052` ruling.

**Blocked.** Nothing. Two corrections owed to `po` as ticket edits (AC 1's `SECURITY DEFINER`
and `search_path` claims); neither blocks authoring. Number sent to `po`, copied to `pm` and
`team-lead-4`.

### Addendum, same day — four messages crossed my report; count holds at 2, checkpoint relocated

Briefs from `team-lead` (×2) and `team-lead-4` (×2) arrived after I had reported. Reconciled:

- **`financial_ledger` IN.** No change to my number — I had already sized both indexes and all
  three `trgfn_payment_to_ledger` inserts into sitting 1. `team-lead`'s original "size the
  `wallet_ledger` half only" was self-contradictory and I had not applied it.
- **7 vs 6 insert sites — no conflict, and I had already split it that way:** seven sites exist,
  six take a mechanical `ON CONFLICT DO NOTHING`, `admin_wallet_adjust:2982` is the seventh.
- **Zero callers** — found independently before the messages arrived. Newly checked:
  `supabase/schema/archive/fix_admin_functions_missing_auth_check.sql` names `admin_wallet_adjust`
  **only in a comment at `:9`**; it redefines `admin_force_delete_auth_user` and
  `admin_cleanup_user_data`, not any of my five. No competing definition exists in the repo.
- **`_wallet_recalc` AED-only** — noted, out of scope, will not touch.

**Checkpoint relocated — I now disagree with `team-lead-4` about where it falls, and with my own
first answer.** Both of us put it at the `admin_wallet_adjust` signature. On re-reading
`capacity-to-date` §1, the test for a second sitting is *a judgement whose output the next part of
the same ticket consumes* — and that signature is **ruled** by `T-049` (caller-generated uuid,
`NULLS NOT DISTINCT` rejected), has zero callers to migrate, and its output is consumed by a
single `ALTER COLUMN` statement in the same file. It is a decision taken inside a pass, not a
boundary between two. My first checkpoint — "a migration holding 6 of 7 clauses, not applicable" —
was a partial finish dressed as a checkpoint, which is the thing §1 warns against.

**The real boundary is migration-body-complete → AC-3 probe pack.** Sitting 1 is the whole
migration including `admin_wallet_adjust`, ending posted to the ticket in `G-002` format —
reviewable by `cto`, abandonable, complete in itself. Sitting 2 is AC 3's four probes, which need
fixtures (`settle_game`'s re-settle needs a game, an organiser and a commission rule) and a
**concurrent** replay demonstration for `financial_ledger`, since Invariant 5 is precisely about
the concurrent case a sequential probe cannot show.

**The one question that would take this to 1 sitting, named with its owner:** the ticket does not
say who authors AC 3's probes. **If `cto` owns them, KAN-128 is 1 sitting for this seat**; if they
come with the migration, it is 2. `po`/`cto` hold that. Ceiling stays 2 either way — one rework
cycle on a money migration that has never executed against rows anywhere.

**Re-flagged to `team-lead`, which reasserted it after my report:** *"restate `SET search_path TO
'public','pg_temp'` in every replaced function, do not add `SECURITY DEFINER`"* is wrong for four
of the five. They are `SECURITY DEFINER` and carry `SET search_path TO 'public'` with no `pg_temp`.
Unchanged from my report; the instruction has now been given twice.

## 2026-09-06 — KAN-130+131 capacity, and a skill quotation verified (`team-lead-4` / `team-lead-3`)

**Did.** Read-only. Read `DECISIONS.md` `T-051` (`:6362`) and `T-052` (`:6475`) in full, and every
line they cite: `wallets` (`:26677`), `wallets_pkey` (`:28296`), `wallets_user_id_fkey` (`:31858`),
`wallets_id_unique` (`:29605`), `wallets_unique_idx` (`:29609`), `wallets_self_read` (`:34003`),
`wallets_block_dml` (`:33999`), `financial_ledger_wallet_fkey` (`:30583`), `fn_get_wallet`
(`:6088`–`:6102`), `_wallet_recalc` (`:1794`–`:1819`), `_wallet_after_ledger` (`:1780`),
`request_payout:10190`, `delete_my_account` (`:5257`–`:5306`), `v_wallet_balance`,
`v_wallet_admin_overview`.

**Touched.** This file only.

**Number — KAN-130+131 as one migration: 2 sittings, ceiling 3.** Same shape as KAN-128, and the
same probe branch: sitting 1 is the whole migration ending posted in `G-002` format; sitting 2 is
the probe pack. **3 if the erasure question below resolves "yes".** No date.

**I disagree with `team-lead-4`'s "materially larger than KAN-128" read.** It is larger in
*volume* — 6 DDL statements on `wallets`, a policy swap, four function bodies rewritten, one new
function — but volume shifts the start, not the cost. That is `team-lead-4`'s own argument about
the `payment_intents` cut, applied symmetrically: lighter mechanical work buys back no sitting, and
heavier mechanical work adds none, unless it adds a **boundary**. I could not find a second
boundary. The DDL ordering looks like a judgement and is not one — `T-051`'s six-item list fixes
the end state, and the sequencing (dropping `user_id` takes `wallets_pkey` and
`wallets_user_id_fkey` with it as dependents, so the new PK must be added in the same statement
block) is craft inside a pass.

**The exhaustiveness check `T-051` invites.** SQL references to `public.wallets` outside DDL are
**exactly four**: `_wallet_recalc:1813`, `fn_get_wallet:6090`/`:6096`, `request_payout:10190`.
Plus the policy, the PK, the FK, and two views. `v_wallet_balance` already keys on
`owner_type`/`owner_id`/`id` and needs no change; `v_wallet_admin_overview` reads only
`balance_aed`. **`fn_get_wallet` itself needs no edit** — its `INSERT` already omits `user_id`,
which is precisely what the drop makes legal. `T-051`'s six dependents are complete for the SQL
half.

**Under-specified, with its holder — the answer to what `team-lead-4` asked for.**
`T-051` item 3 makes `delete_my_account` delete the wallet before `delete from auth.users`, calling
it "an erasure obligation, not tidiness". But **`financial_ledger` has no FK to `auth.users`** and
`trgfn_payment_to_ledger:19219` writes `entity_type='user', entity_id=NEW.user_id`. So after
erasure the user's uuid remains in `financial_ledger` indefinitely, and
`financial_ledger_wallet_fkey`'s `ON DELETE SET NULL` (`:30583`) only clears `wallet_id`, not
`entity_id`. This predates KAN-130 and is not caused by it, but KAN-130 is the ticket that opens
`delete_my_account` and states an erasure obligation. **Cannot size that slice until it is ruled,
and `cto` holds it** (a retention/erasure call, possibly `cpo`). If it resolves "also scrub
`financial_ledger`", that is a judgement the rest of the migration consumes and the count goes to 3.

**Two I can settle myself, noted rather than escalated.** `request_payout:10190`'s replacement
lookup needs a `currency` predicate, which `T-051` omits — I will mirror `_wallet_recalc`'s ruled
AED-only design rather than leave a `select … into` that takes an arbitrary row once multi-currency
exists. And `wallets_id_unique` (`:29605`) becomes redundant once `id` is the PK — I will leave it
rather than drop it, since dropping it is unrelated cleanup.

**A third `search_path` string, which sharpens the standing correction.** `delete_my_account:5259`
is `SECURITY DEFINER` with `SET search_path TO 'public', 'auth', 'extensions'` — not `'public'`,
not `'public','pg_temp'`. Three distinct strings now across the functions in play. **The rule is
restate each function's own header, read from `pg_get_functiondef`; there is no shared string.**

**Confirmed for `team-lead-3`** the five points of my KAN-128 checkpoint reasoning quoted in
`capacity-to-date`, with one wording correction and the probe branch flagged as still open.

**Blocked.** Nothing. Cannot start KAN-130/131 authoring until `cto` applies KAN-128
(`T-052` requires rebasing on live post-128 definitions). The erasure question is with `cto`.

### Addendum — my own "concurrent replay" framing is not executable here, and does not need to be

**Measured live** (read-only, `list_extensions` on `wtncuzcskpigqpmnxwws`): **`dblink` is available but
NOT installed** (`installed_version: null`), `pg_background` is absent entirely, and **`pgtap` 1.2.0
IS installed** in `extensions`.

**Consequence.** A genuinely concurrent probe needs two sessions interleaved. Nothing in this
database provides that without `CREATE EXTENSION dblink`, which is a DDL change to production,
`cto`'s to apply, and outside KAN-128's scope. Adding an extension to production to run one test is
not worth it and I am not proposing it.

**And it is not needed — the probe should target the constraint, not the trigger path.** My original
point stands where it was aimed: a sequential retry through `trgfn_payment_to_ledger` proves nothing,
because the `EXISTS` guard at `:19183`–`:19189` absorbs it before reaching the insert. But the fix
under test is the **unique index**, not the trigger. Two **direct** inserts into `financial_ledger`
with the same `(payment_intent_id, entity_type, entry_type)` demonstrate it exactly, and
sequentially: pre-index both succeed (2 rows), post-index the second is absorbed (1 row). That
satisfies `cto`'s failing-first condition cleanly. Concurrency-safety is then a property **inherited
from the unique index** — Postgres serialises on it — not something the probe reproduces. That is
the whole reason `T-049` ruled a constraint over the `EXISTS` guard.

**Owed as a correction, because it is my phrasing that propagated.** "Concurrent replay
demonstration" is now in KAN-128's AC 3 and in `capacity-to-date`'s worked example, in my words.
As literally written it is not executable on this database. It should read: *a direct two-insert
probe against the constraint, demonstrated failing pre-index* — with the note that the trigger path
cannot be used to show the failure because its `EXISTS` guard hides it. Raised to `team-lead` for
routing to `po` (AC 3) and `team-lead-3` (the skill).

**No change to the count.** KAN-128 stays **2 sittings** — `cto` has ruled I author the probes, so
the branch is closed at 2, not 1. This changes what sitting 2 contains, not its size; arguably it
shrinks it, since the direct-insert probe is simpler than what I had imagined.

**Also noted from `cto`'s corrected AC 1:** the `admin_wallet_adjust` re-grant is `authenticated`
and `service_role` **only** — `anon` is deliberately dropped from the baseline's `GRANT ALL`
(`:34693`). That is a privilege reduction, and I will not "restore" it while restating.

### Close — erasure branch resolved downward; my pseudonymisation proposal was wrong

`cto` ruled the `financial_ledger` erasure slice **out of KAN-130's scope** (`T-054`, commit
`c3a2930`). **KAN-130+131 is therefore 2 sittings firm; the third does not fire.** The distinction
is worth keeping: `T-051`'s wallet delete *restores* a guarantee the `auth.users` cascade gave until
`T-051` itself removed it — a repair. A `financial_ledger` scrub would *create* a guarantee that
never existed — a policy call, not a repair.

**My pseudonymise-`entity_id` proposal is ruled illusory, and I should not have made it.**
`booking_id` and `payment_intent_id` still trace to the user, so severing one identifier severs
nothing — and `financial_ledger.entity_id` is `NOT NULL` (`:22706`), which I had **read myself**
while sizing KAN-130 and failed to apply. `cto` also found the stronger objection: the three rows
per payment are a balanced double-entry set, so deleting one side leaves `v_wallet_balance`
unreconciled for counterparties who never asked to be erased. Recommendation to `cpo` is documented
retention — zero SQL.

Not an exposure: `relrowsecurity` on `financial_ledger` is `true` with one policy
(`financial_ledger_admin_read`, qual `is_admin()`), and `is_admin(null)` is `false`.

**Owed to this seat later, logged so it is not rediscovered:** whatever `cpo` rules on retention,
`delete_my_account`'s comment block should state it. `cto` is barred from `dabbler-code`; a function
body is this seat's surface. One-liner, folds into whichever migration is live when the ruling lands.

**KAN-130 AC 2 item 3** now states all three `search_path` values explicitly, with the reason that
beats mine: `delete_my_account` needs `auth` on its path to run `delete from auth.users`, so
restating any other string **fails at runtime on account deletion, not at apply time.**

### `T-055` stop signal verified — and it does not block the revised probe

**Verified independently** against the baseline: `public.bookings` **does not exist** (no
`CREATE TABLE`), and `:19195` is its **only** reference in the whole 39,291-line schema.
`trg_payment_to_ledger` confirmed at `:30007` as `AFTER UPDATE OF status ON payment_intents`.
`cto` is right: `trgfn_payment_to_ledger` raises at `:19195` before reaching any
`financial_ledger` insert, and the trigger's exception aborts the status update. The function has
never run.

**The stop applies to the probe I already retracted, not to the one I replaced it with.** The
blocked design was the *concurrent replay through the trigger* — which needs the function to run,
hence the `bookings` fixture `cto` rightly forbids. My replacement is **two direct inserts into
`financial_ledger`**. It never calls `trgfn_payment_to_ledger`, never touches `public.bookings`,
and needs no fixture at all.

**Measured, and this is what makes it fixture-free:** `financial_ledger` has exactly **one** FK —
`financial_ledger_wallet_fkey` (`wallet_id` → `wallets(id)`, nullable, `:30583`). **`booking_id`
and `payment_intent_id` have no FK**, so both take arbitrary uuids. The only other constraints are
two CHECKs (`entry_type ∈ {debit,credit}`, `reason ∈ {booking_payment,refund,commission,payout,
adjustment}`, `:22713`–`:22714`). Two `INSERT`s of literals satisfy everything.

**So AC 3 need not narrow to `wallet_ledger` only**, and the `financial_ledger` unique index should
stay in KAN-128: it is **not** a bare constraint — its three `ON CONFLICT DO NOTHING` clauses land
in the same migration, which is what `T-049` Decision 2 requires — and it is free only while the
table is empty. That is a recommendation to `po`, not my call.

**The real consequence, which should not be lost in the unblocking:** KAN-128's three `ON CONFLICT`
clauses on `trgfn_payment_to_ledger` are correct and **unexercisable in production**. Nobody should
read a green KAN-128 as evidence that webhook replay is handled. **`T-049` Invariant 4 stays open**
until the `venue_bookings`/`venue_spaces` ticket lands. Worth stating on the ticket so a future
reader does not treat the invariant as closed.

**Also flagged:** `T-051`'s "both writers are dead" now has a third sense — `fn_get_wallet`'s
`venue`/`platform` call sites are inside this dead function. `T-051`'s reasoning is unaffected
(that `user_id` cannot represent a venue is a design fact, not a runtime one), but `KAN-131`'s
`:19211`/`:19231` fix lands in code that cannot execute until the same ticket lands.

**No change to either count.** KAN-128 stays 2, KAN-130+131 stays 2.

### Correction to my own entry above — the pseudonymisation error was narrower than I logged

I logged *"my pseudonymise-`entity_id` proposal is ruled illusory, and I should not have made it."*
`cto` has since measured further (`T-055`): **`payment_intents` holds `user_id` directly and has
zero foreign keys**, so no deletion path reaches it. The surviving link is
**`payment_intents.user_id`**, not the `booking_id`/`payment_intent_id` columns originally named.
**Pseudonymisation is viable and technically sound; its scope is two tables, not one column.**

**The honest split: the idea survived, my analysis did not.** I named the wrong column
(`financial_ledger.entity_id`, which is `NOT NULL` and severs nothing) and reasoned from a
tracing argument that was itself wrong. Being directionally right by accident is not the same as
being right, and the original entry's self-criticism stands on the analysis even though the
conclusion has partly turned. `cto`'s objection to *deleting* rows is unchanged and correct —
a double-entry set cannot lose one side. Still `cpo`'s call, now a narrower one.

**New falsifiability condition, from `T-055`:** *the probe runs against the schema as deployed, and
anything it creates is a row, never a relation.* My direct-insert probe satisfies it by
construction — it writes rows to `financial_ledger` only, creates no relation, and needs no rows in
any other table, because `booking_id` and `payment_intent_id` carry no FK.

**Waiting, not choosing.** AC 3's scope (wait on the `:19195` fix vs narrow to `wallet_ledger`) is
`po`'s. I sent `pm` a measured third option — keep the `financial_ledger` index and probe it
directly — explicitly as a recommendation, and I am not acting on it.

---

## 2026-09-07 — KAN-128 restated under `G-028`, posted, awaiting `cto`'s confirmation

**Not applied.** The migration is posted as **KAN-128 comment `10721`** and is waiting on `cto`'s
posted confirmation. Under `G-028` (2026-09-07, amending `G-002`) I author **and** apply; `cto`
confirms only. I apply nothing until that confirmation is on the ticket.

### Why the ticket was stuck

Nothing was wrong with the work. The ticket text still described the old `G-002` model
("applied by `cto`"), so it sat waiting for a seat that under `G-028` no longer performs the
apply. I corrected the migration file's own header, which repeated the same stale claim
(`-- Applied by cto (CONTRACT.md G-002)`), and recorded today's re-measurement in it.

### I re-measured live myself rather than trusting the handover

`cto` had re-verified this on 2026-09-06 and the brief passed those figures to me. I re-derived
every one of them today against `wtncuzcskpigqpmnxwws`. **`G-002` condition 2 is that the
*applying* seat measures immediately before applying — not that someone measured recently**, and
two migrations had applied since my authoring.

| Precondition | Result |
|---|---|
| `wallet_ledger` / `financial_ledger` rows | **0** / **0** |
| `wallet_ledger.ref_id` NULLs | **0** |
| Duplicates on `(ref_type, ref_id, direction)` | **0** |
| Duplicates on `(payment_intent_id, entity_type, entry_type)` where not null | **0** |
| `wallet_ledger.ref_id` already NOT NULL? | **false** — the `ALTER` is a real transition |
| Unique constraints/indexes on either table | **only the two PKs** |

No catalogue drift on the five functions: four `SECURITY DEFINER` / `search_path=public`,
`trgfn_payment_to_ledger` neither, `search_path='public, pg_temp'` — matching the file's
per-function headers exactly. `list_migrations` puts the remote at `20260907061206 kan145`;
`kan141` and `kan145` are the only two applied since authoring and neither touches the five
functions or either ledger table, so **`T-052`'s revert hazard has not fired**. `KAN-128` is not
in the applied list.

### The finding that would have misled a count

`settle_game`'s live body **does** contain an `ON CONFLICT`. A grep hit alone would have read as
"partially applied" and been wrong: it is the **pre-existing `game_settlements (game_id)` upsert**,
unrelated to either ledger. I checked what the hit *was* rather than counting it (`020` — a
population is counted, never inferred from a finding count). Post-apply, `settle_game` should show
**2** occurrences, not 1.

### `cto`'s two pre-answered handover points

1. **The `anon` grant.** Already in the file since authoring (lines 273–276) — I did **not** add it
   in response, and I said so plainly on the ticket rather than presenting it as a fix. I
   re-derived the reason live: **two** `pg_default_acl` rows for functions in schema `public`,
   grantors `postgres` and `supabase_admin`, **both** granting `anon=X` **by name** on top of the
   `PUBLIC` default. `REVOKE … FROM PUBLIC` alone leaves the named grant standing. Post-apply I
   assert the resulting `proacl`, not that the revoke ran.
2. **`settle_game`'s `42804`.** Confirmed independently, not accepted on report:
   `pg_typeof(case when true then 'settled' else 'pending' end)` = **`text`**; `pg_cast`
   text→`settlement_status` returns **0** rows; `game_settlements.status` is
   `settlement_status NOT NULL`. It raises before reaching the credit insert.

### Ticket-text defect flagged, separately from the apply

`KAN-128`'s **AC3 is false as written** — it asserts something about a path that cannot execute.
A second instance of the `T-055` shape. This is `po`'s to reword, not mine; I proposed nothing
beyond naming the two honest options (narrow AC3 to executable paths, as `T-058` already did once;
or split the `settle_game` assertion onto a fix ticket the way `KAN-136` carries the trgfn defect).
**The `po` seat was not reachable as a live agent**, so I routed it to the running `po-ac-fix`
session with an explicit instruction to hand it on if that is the wrong holder — flagging here
because a message to a seat that does not answer is a message that was not delivered.

### Incidental, flagged not acted on

`kan155`, `kan150` and this migration exist locally but are unapplied, and the applied
`kan141`/`kan145` carry **different timestamps than the local filenames** (`20260907052826` vs
`20260906210000`). That is `devops`' territory.

### What is still open after this lands

`T-049` **Invariant 4 stays OPEN**. This migration installs the index that makes the guarantee, but
the trigger path that would exercise it cannot run until `KAN-136` fixes the `public.bookings`
reference. **Mechanism-verified is not observation-verified** — Invariant 4 must not be closed on
this file's green status.

### Correction to the entry above — the AC3 defect I flagged does not exist

I logged that `KAN-128`'s **AC3 is false as written** and routed it to `po`. **Wrong, withdrawn**
on the ticket as comment `10722`. `po` corrected me and I verified the correction against the
ticket's own text rather than accepting it: `T-058` narrowed AC3 on 2026-09-06 and the numbered
Acceptance Criteria section already reads *"This AC does not require P3 to pass."* The narrowing
I "proposed" had been ruled and written in a day before I raised it. Second error in the same
breath: I implied `settle_game`'s cast defect had no ticket — it has **`KAN-138`**. `KAN-136` is
`trgfn_payment_to_ledger`'s `bookings` defect, which I cited correctly; I never checked whether
`settle_game` was already covered.

**The measurement survives; the conclusion does not.** `pg_typeof(...) = text`, `pg_cast` count 0,
`status` typed `settlement_status NOT NULL` — all correct and independently derived, but that is
**re-confirmation of `T-058`**, not a new finding and not a ticket defect. Being right about the
database while wrong about the ticket is still wrong about the ticket.

**Root cause, which is the transferable part:** I read the discussion narrative and treated it as
the criteria. **The numbered AC section is the criterion; the prose above it is history**, and on
a ticket this long the history predates the ruling that changed it. Saved to memory. Nothing about
the migration or the live re-measurement is affected — all of that was measured directly, not read.

### Routing note on the two concurrent `cto` comments

`10718` and `10719` were posted six seconds apart by two `cto` instances that could not see each
other; `10719` read as "approved to apply" and would have let me skip the re-measurement.
**`10720` subordinates it: `10718`'s sequence governs and `10719` is review content, not an open
gate.** I had already re-measured and posted before seeing any of this, so nothing changed — but
the near-miss is worth recording: a concurrent approval that skips a verification step is exactly
the kind of green light that looks authoritative. Still holding for confirmation on `10721`.

## 2026-09-07 — KAN-128 APPLIED. Catalogue green, one verification item NOT run.

`cto` confirmed on comment `10723`; applied as migration `kan128_ledger_unique_keys_and_on_conflict`.
Results posted as comment `10730`. Ticket moved to **In Review** (my transition).

**Preconditions re-checked immediately before applying**, not inherited from `cto`'s minutes-old
reading: 0/0 rows, 0 `ref_id` NULLs, 0 duplicates on either key, `attnotnull` false, 2 unique
indexes, `admin_wallet_adjust` 1 overload. I re-ran `cto`'s condition-3 inventory independently by
stripping the five `$function$` bodies before counting — 1 alter, 2 create unique index,
4 comment on, 1 drop function, 5 create or replace, 2 revoke, 2 grant, **zero top-level DML**.
Matched exactly. Both tables still read 0 rows after the apply.

### All six verification items PASS — and item 5 as the ACL, not as "the revoke ran"

`admin_wallet_adjust` proacl reads back `{postgres=X/postgres,authenticated=X/postgres,
service_role=X/postgres}` — **no `=X/` PUBLIC entry, no `anon`**. The other four functions' grants
are untouched and still carry `anon`, as ruled; the change did not generalise.

`ON CONFLICT` counts: 1 / 1 / 1 / **2** / 3 = 8 occurrences, minus `settle_game`'s pre-existing
`game_settlements` upsert = **7 ledger clauses**, exactly AC 1's set. The pre-apply catch paid off
here: an assertion written as "settle_game = 1" would have failed on correct work.

Also asserted: all five `provolatile='v'`, `proisstrict=false`, `proparallel='u'` (all PostgreSQL
defaults, so the omitted keywords reproduced them), and both new indexes `indisvalid`/`indisready`/
`indislive`/`indisunique` all true — live and enforcing, not merely present.

### `cto` corrected my `10721` wording and is right

I wrote *"pg_constraint + pg_index: only the two PKs."* Correct is **eight indexes across the two
tables, of which two were unique**. `idx_wallet_ledger_ref` is a **non-unique** btree on
`(ref_type, ref_id)` — my key minus `direction`. Re-confirmed post-apply as `indisunique=false`.
Had it been unique it would already have broken `admin_cancel_payout`'s reversing credit, the exact
path `T-049` put `direction` in the key to protect. **Substance was right, wording would have
misled the next reader** — which is the whole cost of a loose count.

### NOT DONE: the §12h probe re-run

**`docker` is not running on this host**, and `supabase/tests/kan128/run.sh` builds a throwaway
container. **I did not run it and did not report it as passed.** The pre-apply probe evidence from
authoring stands (each probe demonstrated failing pre-migration); what is missing is the re-run
against the schema **as deployed**, with §12h evidence that each probe reached the modified
statements. **I did not route around it by probing production** — the probes write rows to live
money tables, and writing to them to make a checkbox green is the opposite of what the check is
for. To close: start Docker, then `bash supabase/tests/kan128/run.sh`.

### Still open

`T-049` **Invariant 4 stays OPEN** — index installed, path dead until `KAN-136`. `KAN-130`/`KAN-131`
must now source `trgfn_payment_to_ledger` from `pg_get_functiondef` read **after** this apply, or
they silently drop the three clauses. The migration file's header edit is **uncommitted**; commits
are `devops`'.

### Gap closed — §12h probe re-run executed (comment `10733`)

Started Docker, ran `supabase/tests/kan128/run.sh` end to end. `baseline load errors: 0`. Nothing
touched `wtncuzcskpigqpmnxwws` — the pack builds a throwaway container.

**Every runnable probe demonstrated failing pre-migration and passing post.** P1a `2 -> 1` with the
second insert rejected on **`23505`**; P1b `2 -> 1` absorbed; P2 reversal still **2** (no
regression); P4 arity **5 -> 6 and 6 only**, distinct keys `1, 1` not collapsed, null `ref_id`
rejected on **`P0001`**; P5 `2 -> 1` with NULL-`payment_intent` rows still **2**.

**§12h evidence is the error codes, not the row counts.** `23505` is the new index firing, not "the
function ran". `P0001` is the named `ref_id_required` RAISE this migration added — a generic NOT
NULL would have been `23502`, so the code proves the new guard line was reached rather than the
column constraint. That distinction is the whole point of the KAN-145 named-RAISE model.

**Reported at reduced strength, per `T-058` Decision 3.** P0 observes `23502` on `wallets.owner_id`
on both runs, so P1/P2/P4 ran with `trg_wallet_ledger_recalc` disabled and read as *"the constraint
holds in the absence of the recalc trigger"* — never unqualified. P5/P5b need no caveat. P3 stays
BLOCKED both sides on `42804`, as ruled; `KAN-138` owns it.

**Harness ACL matched production exactly** — `{postgres=X/postgres,authenticated=X/postgres,
service_role=X/postgres}`. Two independent derivations of the same assertion, one against the
deployed database and one against a clean container.

**AC 3 satisfied for P1, P2, P4, P5.** With `10730`'s six catalogue assertions, the verification
`cto` specified is complete. `T-049` Invariant 4 still OPEN — unchanged by a green pack.

### Two corrections landed on me this session, and one I caused in `cto`

`po` was right that AC3 needed no edit; `cto` was right that "only the two PKs" was loose. Both
accepted and confirmed. **And `cto` reports it repeated my withdrawn AC3 claim in its own
confirmation (`10723`), corrected in `10727`** — it had carried an assertion forward from comment
`10590`'s prose without re-reading the description that comment described. Same failure as mine,
one seat up. **A comment describing a document is not the document.** That is now twice in one
ticket, which is why I saved it rather than treating it as a one-off.

`cto` also answered my incidental flag: the local-filename vs ledger-version divergence is
**documented in `SCHEMA.md` §8a and by design** — `apply_migration` stamps its own version. Withdrawn.

### `cto` withdrew the §12h gate — and one line of my `10733` was overstated (comment `10734`)

`cto` posted `10732` withdrawing the probe re-run as a gate; my `10733` reporting the pack green
crossed it. **`10732` governs.** Reconciled on the ticket so the sequence doesn't read as me closing
a gate that had already been removed.

**`cto` measured what settles it**, and it is not Docker: `wallets.owner_id` `NOT NULL` no default,
`trg_wallet_ledger_recalc` enabled (`tgenabled='O'`), `wallets` 0 rows — so `_wallet_recalc` still
raises `23502` on every `wallet_ledger` write (my own `10590` finding, still true post-apply).
**P1/P2/P4 cannot execute against the deployed schema at all.** A container re-run could never have
closed that, because the container loads the baseline and applies this same file.

**I overstated one line and have corrected it.** `10733` said *"the verification `cto` specified is
complete."* Correct: the six catalogue assertions are complete; the pack adds **container-level
confirmation, not evidence**. I had reported the recalc-trigger caveat under `T-058` Decision 3, so
the caveat was there — but "complete" undercut it in the same comment. **A qualification stated in
one paragraph does not survive an unqualified claim in another.** Worth remembering: I have now
twice made a correct measurement and wrapped it in a conclusion stronger than it supported.

**The right framing, from `cto`, adopted:** the constraint half is proven by the **catalogue** —
both indexes `unique`/`valid`/`ready`/`live`, and Postgres has no state where such an index fails to
reject a duplicate. What is NOT proven is the **runtime behaviour of the seven clauses on the
deployed schema**: present and readable, never executed there, unexecutable while the paths are
dead. The real follow-up is **`KAN-146`** (end-to-end liveness, all triggers enabled) once
`KAN-130`/`KAN-131`/`KAN-136` land — not a re-run of my pack.

**Released to `po`.** Stays In Review; that gate's transition is `po`'s. No hold, nothing
outstanding from me. `cto` explicitly endorsed two calls: refusing to probe production, and naming
the gap rather than letting the catalogue checks stand in for it.

### `cto` narrowed its own "adds nothing new" — the container run DID add evidence

Correcting my entry above, which recorded the pack as *"container-level confirmation, not
evidence."* `cto` withdrew that framing as overstated: the authoring run reported **row counts**;
this run reported **error codes**, and those are a different class of evidence. **`23505`** shows
`wallet_ledger_ref_key_unique` fired rather than "the function ran"; **`P0001`** shows the named
`ref_id_required` RAISE was reached, where a generic NOT NULL would have surfaced **`23502`**.
That is the §12h discrimination, and row counts could not have produced it. Same harness, strictly
better evidence.

**The accurate statement is narrower:** a container re-run could not close the gap **for P1/P2/P4
against the deployed schema**, because those paths are dead there regardless. It was never
worthless. Recorded so I don't over-learn this into "container runs prove nothing" — and memory
amended accordingly.

`cto` also reports matching my own failure twice today (an AC3 claim carried from a comment rather
than the description field; an instruction made a gate without checking it was satisfiable) and
frames it as **a property of the work, not of either seat** — asserting from a secondary artifact
instead of the primary one. Its added tell for the caveat-vs-summary failure: **the summary line is
written last, when the caveat is already three paragraphs behind you.**

**Both loose ends routed by `cto`, not mine:** the migration header edit and a new `CONVENTIONS.md`
§12i are with `devops-push2`, staged by explicit path — §12i now requires that, since every Dabbler
repo is a single shared tree, verified across all five.

**Stood down.** AC 3 satisfied for P1/P2/P4/P5 at `T-058` Decision 3's strength. `T-049` Invariant 4
open. `KAN-146` is the follow-up. KAN-128 sits in In Review for `po`'s gate.
