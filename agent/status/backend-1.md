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

## 2026-09-08 — KAN-128 surface assessment recorded (Preflight, not execution)

**Did.** Read `agent/state/store.py:546` (`set_surfaces`), `queue.py:118/:145`, `policy.py`, the
KAN-128 runtime record and my own entry at `:15`. Read the record's `revision` immediately before
writing: **2**. Wrote two paths, `author=worker:backend-1`, `basis_ref` naming `:21-24` and
`:583-584`. Record now at **revision 3**.

**Surfaces declared** (post-`normalise_path`):
`supabase/migrations/20260909090000_kan128_ledger_unique_keys_and_on_conflict.sql`,
`supabase/tests/kan128/`.

`shared_or_contended_surface` recomputed **false** by the system — neither path is a
`CONTENDED_FILES` entry nor under `lib/core/`/`lib/data/`. I did not set it.

**Not claiming.** No ownership taken, no transition, no Jira contact (no Atlassian tool exists in
this session). `work_effort` 2, `validation_route` peer, `money_path`/`schema_change` untouched.

**Excluded, deliberately.** `agent/status/backend-1.md` — the status file is this seat's own log,
not a work surface, and declaring it would manufacture contention with every future KAN-* item this
seat touches. **`dabbler-code` is not checked out in this workspace**, so both declared paths rest on
my authoring record, not on `ls`. The record names them explicitly with a commit hash; I did not
guess or widen either.

**Contention.** `trgfn_payment_to_ledger` is a database object, not a repo path. KAN-131 has **no
runtime record** — it does not exist under `agent/state/runtime/tasks/`, so no path-level collision
can be computed against it. The overlap is real at the SQL-object level and `surfaces_collide` cannot
see it. Flagged, not resolved.

`python3 agent/state/validate.py --check` → `ok      persistent state valid`.

**Blocked.** Nothing.

---

## 2026-09-09 — KAN-136 pt.1: venue-resolution join path design (T-055/T-061). Delivered.

**Owner:** `backend-1` (Shu), continuation on work already claimed. Route **SELF**, Work Effort 1.
**Deliverable:** Jira comment `10839` on `KAN-136`. **No diff** — the ticket's own scope is
*"No function body touched, nothing written to the database. Read-only throughout."* Nothing was
committed because nothing in a repo changed.

**Read-only, and the boundary held.** No DDL, no DML, no `apply_migration`, no `db push`, no
function replaced, no Jira transition, no write under `agent/state/runtime/**`. Writes made: this
entry, comment `10839`, and files in my own scratchpad.

**Project identity, confirmed three ways before citing anything** — `supabase projects list` marks
`wtncuzcskpigqpmnxwws` ("Dabbler") as LINKED and shows `ekmhrxdwgegxkdkdukgq` ("Dabbler-draft")
unlinked; the pooler URL greps 1 for the correct ref and 0 for both forbidden refs;
`supabase/.temp/project-ref` reads `wtncuzcskpigqpmnxwws`.

**Evidence route.** My own `supabase db dump --linked --schema public` (1,330,472 bytes), taken
today into my scratchpad — pg_dump renders `pg_catalog`, not migration text. I did not use the
team lead's dump. Every hop cited to a dump line and spot-checked line by line before posting.

**Two findings that were not in the brief.**

1. **T-061's FK is ALREADY LIVE.** `payment_intents_booking_id_fkey ... ON DELETE RESTRICT` exists
   in the catalogue (dump `:29516-29517`) — split to `KAN-145` (Done) and applied 2026-09-07 by
   `backend-4`. **`KAN-136`'s description is three days stale** where it reads *"no FK — the only
   hole"*. `KAN-140` must not re-issue the `ADD CONSTRAINT` (42710); its AC6 is now satisfied by
   construction. The ruling is unchanged; only its execution state moved.
2. **`psql` IS installed**, at `/opt/homebrew/opt/libpq/bin/psql`, contrary to the brief — just not
   on `PATH` and with no usable stored password. The Supabase MCP `execute_sql` exists but returns
   *"You do not have permission to perform this action"* for this seat. So arbitrary SQL was
   genuinely unavailable and the dump is the route I used.

**The stop-and-ask trigger I did NOT fire, and why.** `po`'s 2026-09-09 recovery comment says
AC-1's confirmation *"genuinely cannot be produced yet"* with `KAN-131` unapplied. **I disagree, on
evidence.** AC-1's deliverable is the join path — a property of four tables. `KAN-128` targets
`financial_ledger`/`wallet_ledger` writers; `KAN-131` replaces two expressions inside a function
body. **Neither touches a column, type, constraint or FK on the join path**, so the answer is
invariant under `KAN-131` landing. The `post-KAN-128/KAN-131` qualifier exists to protect the
*whole-body replacement* (T-044 / CONVENTIONS.md §6c) — that is `KAN-140`'s AC5 and it **is** still
blocked. I recorded the disagreement in the comment rather than working around it, and said plainly
that if `po` reads AC-1 as also requiring body-level confirmation, the ticket goes back to blocked.
**That reading is `po`'s to make, not mine.**

**Measured, and labelled at its real strength.** Row counts are `table-stats` planner *estimates*
(0 for `payment_intents`, `venue_bookings`, `financial_ledger`), **not counts** — no arbitrary-SQL
route existed. Per `020` I did not assert a counted zero. Nothing in the design depends on it.

**Declared not verified.** That the ruled query executes. The function still aborts at
`public.bookings` (live body, dump `:18683-18781`) before reaching venue resolution — `T-055`'s own
lesson is that a probe which cannot reach the code under test proves nothing. Demonstrating it is
`KAN-140` AC2.

**Also measured for `KAN-140`'s benefit:** `KAN-128` **is** applied into the live body (three
`ON CONFLICT DO NOTHING`); `KAN-131` is **not** (both platform sites still `gen_random_uuid()`);
attributes to preserve are `LANGUAGE plpgsql`, `SET search_path TO 'public', 'pg_temp'`, and **no**
`SECURITY DEFINER`.

**Blocked.** Nothing. **Transition:** none taken — `Back-end` → `Peer-review` is not mine to take
on a SELF route, and I did not touch the board.

## 2026-09-10 — KAN-138 PEER review (cycle 1), reviewer backend-1 (Shu)

CEO-authorised `review_owner` for KAN-138. Executor `backend-2`. Read-only under the
general migration freeze — no push, apply, replay, repair or schema mutation; no
commit, no push, no transition.

Evidence: my own fresh `supabase db dump --linked -s public` (project ref read back as
`wtncuzcskpigqpmnxwws`, 37681 lines). No earlier agent's dump reused; repo not accepted
as evidence of production state (T-068 §19).

Re-derived independently: live `settle_game` (dump :16589) still inserts the UNCAST
`case when p_finalize then 'settled' else 'pending' end` into
`game_settlements.status`, which is `public.settlement_status NOT NULL` (:16573, enum
at :280) — KAN-138 is NOT applied and 42804 is live. Mechanical body diff live vs the
migration at Canary `b978647` is ONE substantive hunk (the 28-char cast) plus four
comment lines across 102 body lines. Both KAN-128 `on conflict` clauses present live and
byte-identical. Attributes preserved exactly (SECURITY DEFINER, `search_path` 'public'
alone, VOLATILE, `RETURNS public.game_settlements`). No DROP/GRANT/REVOKE anywhere in the
file; live grants to anon/authenticated/service_role confirmed (:35340-35342).

Verdict: AC-1 PASS (artefact level), AC-2 PARKED (unchanged — CEO authority under 019;
not converted), AC-3 NOT SATISFIED (parked downstream of AC-2; recorded a labelling
mismatch — backend-2's "AC-3 PASS" describes AC-4's substance), AC-4 PASS, AC-5 NOT
ENGAGED. **The artefact passes everything verifiable; the ITEM does not pass — it is
INCOMPLETE with AC-2 parked.** Explicitly NOT a PEER FAIL: no defect found, so execution
ownership does not transfer to me and there is no rework brief. The block is an authority
the CEO holds, not work anyone can do.

Recorded without ruling: the migration exists on Canary only and `db push` is barred by
T-068, so application remains cto's to resolve.

Posted as Jira comment 10852 on KAN-138.

## 2026-09-10 — KAN-138 PEER review of the APPLIED settle_game hotfix (read-only)

CEO-named peer reviewer on the live production hotfix to
`public.settle_game(uuid,uuid,text,numeric,boolean)` in `wtncuzcskpigqpmnxwws`. Follows my
2026-09-09 pre-apply review of the same ticket; the migration is now applied live.

Read-only throughout. No DDL, no `apply_migration`, no `db push`, no probe. Production
mutations: 0. `game_settlements` = 0 rows, `wallet_ledger` = 0 rows, both before and after —
the only writes-adjacent statements I issued were `count(*)`.

**Verdict: PASS on the static/catalogue evidence.** Every point in the brief verified from my
own reads of `pg_proc`/`pg_cast`/`pg_constraint`, not from the executor's assertions.

- Cast present: `prosrc ILIKE '%::public.settlement_status%'` → true; `pg_cast` text →
  `settlement_status` count still **0**, so the cast is load-bearing, not cosmetic.
- KAN-128 SURVIVED — the regression that mattered most. Both `on conflict (game_id) do update`
  and `on conflict do nothing` → true.
- Attributes asserted, not assumed: `prosecdef` true, `provolatile` 'v', `proconfig`
  `search_path=public` — **'public' alone**, not `public, pg_temp`. Confirmed the body contains
  no `pg_temp` and no `stable` keyword.
- `proacl` unchanged and exactly as recorded. Signature and `RETURNS game_settlements`
  unchanged. Exactly one `settle_game` in the whole catalogue — no shadow overload.
- No unrelated body drift, proved byte-exactly rather than by eye: live `md5(prosrc)` =
  `d3c6238ea2b04ecd06f87cdb832cda37`, len 3136 — **identical** to the md5 of the body extracted
  from the canonical migration file.

Every ILIKE predicate was run against a deliberate near-miss control in the same statement
(`settlement_statuz`, `on conflict (booking_id)`, `on conflict do everything`) and each control
returned false — the probes were demonstrated capable of failing before I counted them as
passing.

Two checks beyond the brief, because a green catalogue does not mean a working function:
- The `on conflict (game_id)` arbiter exists — unique index `idx_game_settlement_unique` on
  `(game_id)`. Without it the function would raise 42P10 at runtime whatever the cast said.
- The cast mechanism type-checks as bare expressions: bare CASE → `text`, cast CASE →
  `settlement_status`, yielding 'settled'/'pending'; the untouched DO UPDATE literal coerces.

**AC-2 remains PARKED and I do NOT report it verified.** The only test establishing it is the
forbidden probe. My verdict covers static/catalogue evidence only.

**Raised, out of KAN-138's scope and NOT a PEER FAIL:** `settle_game` never checks that
`p_organiser_user_id` is the organiser of `p_game_id`. `games` carries `creator_user_id` and the
function reads it nowhere; the guard is only `is_admin(me) or me = p_organiser_user_id`, and the
caller supplies `p_organiser_user_id` and `p_gross_collected`. Any authenticated user can pass
their own uid and self-credit `wallet_ledger` for an arbitrary amount against any game. This
pre-dates the hotfix, but the 42804 was incidentally acting as a total block on the function, so
the fix makes it reachable for the first time. Escalated to `cto` as a serious security question
per role contract; it does not block this hotfix.

### Addendum, same day — caller analysis for the escalated `settle_game` auth hole

Asked by the peer-review requester whether the `authenticated` EXECUTE grant has a legitimate
caller. Established from the repo (no further production reads):

`settle_game` has NO caller in the application or in any edge function. 751 Dart files under
`lib/` and 5 edge functions under `supabase/functions/` searched; zero hits in either. Guarded
the negative — both directories exist, the search space is non-empty, and a control grep for
`rpc(` returned real files, so the empty result is absence, not a bad path. The only
non-migration references in the whole repo are `docs/CONVENTIONS.md` (prose) and
`supabase/tests/kan128/20_probes.sql` (a test probe). `supabase_config.dart` declares no
settlement RPC constant.

Consequence: revoking EXECUTE from `authenticated` (and PUBLIC/anon) on `settle_game` would
break no existing caller. Recommended as the immediate mitigation. NOT applied — CEO decision,
and it needs its own ticket from `po`.

On exploitability: the 42804 was a TOTAL block on the money path. The `game_settlements` insert
is unconditional and precedes the `if p_finalize` credit block, and the untyped CASE resolved to
text on BOTH branches, so every call that cleared the guards died there and none ever reached
`wallet_ledger`. The hotfix is correct and still the right change, but it does open a
previously-dead path. Both tables at 0 rows corroborate that no settlement ever completed.

### Addendum 2 — complete caller enumeration for `settle_game` (repo + catalogue)

Asked for the full search surface behind the "no caller" claim. Result is unchanged and now
covers the DB interior, which the first pass did not.

Searched, with every negative guarded by a control:
- `lib/` — 751 Dart files, 0 hits. Control: `rpc(` returns real files.
- `supabase/functions/` — 5 edge functions, 0 hits.
- `supabase_config.dart` — no settlement RPC constant.
- All DB functions — 2979 searched, **0** bodies mention `settle_game`. Control:
  `resolve_commission` returns 1 (settle_game itself), so the scan reaches real bodies.
- Triggers (non-internal), views, matviews, `pg_depend` edges — empty result set.
- `pg_cron` IS installed (so is `pg_net`); read `cron.job` in full rather than filtering:
  exactly ONE job, `flush_notifications_every_10_seconds` -> `flush_notification_aggregates()`,
  unrelated, and covered by the 0/2979 scan.

Only non-migration references anywhere: `docs/CONVENTIONS.md` (prose),
`supabase/tests/kan128/20_probes.sql` (test probe).

Grantees (expanded): PUBLIC, anon, authenticated, service_role EXECUTE; postgres EXECUTE
WITH GRANT OPTION. Revoking PUBLIC/anon/authenticated breaks NO known caller. service_role
should RETAIN EXECUTE — it is the tier a future server-side settlement flow belongs in, and
nothing calls it today. Still NOT applied; CEO decision, needs a `po` ticket and `cto` ruling.

## 2026-09-10 — `KAN-138` PEER re-review: ruling on AC-2 after the authorized probe

**Task:** rule PASS/FAIL on `KAN-138` AC-2, which I had previously PARKED. `backend-6` ran the
CEO-authorized probe and reported that AC-2's *substance* is proven but its literal token
`PROBE_RESULT=SETTLE_GAME_SUCCEEDED` did not occur. Read-only; **production mutations: 0.**

**Verdict: AC-2 PASS. `KAN-138` closable as scoped.** Reasoning below is not "intent over text" —
the written token itself does not survive measurement.

**Verified `backend-6`'s two proofs independently; both hold.**
- `trg_wallet_ledger_recalc` `tgtype = 29`. Bit arithmetic confirmed AND corroborated by a second
  route: `pg_get_triggerdef` emits `AFTER INSERT OR DELETE OR UPDATE ... FOR EACH ROW`. Control:
  the `(tgtype & 2)` expression discriminates — 115 BEFORE vs 62 AFTER across 177 non-internal
  public triggers, so it is not a constant-false probe. `wallet_ledger` carries **exactly one**
  non-internal trigger and it is AFTER — there is no BEFORE trigger that could have raised first.
- `settle_game` **line 80 IS `insert into public.wallet_ledger(`** — read from live `prosrc` with
  line numbers, not inferred. The cited CONTEXT frame therefore locates the abort *at* the credit
  insert, and an AFTER ROW trigger fires only once the row is in the heap.
- The `90.00` argument is sound but I did not need it: `_wallet_recalc` sums `amount_aed` over
  `wallet_ledger where user_id = p_user`, so with the table empty the only source of 90.00 is the
  probe's own posted credit row. Corroborating, not load-bearing.

**THE TOKEN IS DEFECTIVE, and that is the actual ruling.** `PROBE_RESULT=SETTLE_GAME_SUCCEEDED`
was substituted into AC-2 on 2026-09-07 by `cto` under `T-068`, which overrode `T-060`'s original
AC-2 addendum on this stated premise: *"Live `_wallet_after_ledger`/`_wallet_recalc` reference
neither [`owner_type`/`owner_id`] — those arrive with `KAN-130` ... No `23502` is reachable."*
**That premise is false, and was false when written:**
- `wallets.owner_id` is `uuid NOT NULL` **with no default**, and it comes from
  `20260829080500_baseline_schema.sql` — the baseline, present since 2026-08-29, not from KAN-130.
- `_wallet_recalc` line 17 inserts `wallets(user_id, balance_aed, held_aed)` and never supplies
  `owner_id`. No trigger on `wallets` fills it (zero non-internal triggers on that table).
- A NOT NULL column with no default that the insert never names is the *definition* of a reachable
  `23502`. `cto`'s check had the polarity inverted: it read "the function doesn't mention owner_id"
  as exoneration, when that absence is precisely the cause.

So `T-060`'s ORIGINAL AC-2 addendum — "the post-fix probe shows `_wallet_recalc` raising `23502` on
missing `owner_type`/`owner_id`" — was met **verbatim**. The probe produced exactly the observation
the criterion required before it was amended in error. AC-2 passes on the text as well as the
purpose; only the erroneously-substituted token fails, and a pass condition resting on a premise
the catalogue contradicts is not binding. `backend-6` was right to refuse to collapse substance and
token — the resolution is that the token, not the substance, is what fails scrutiny.

**No partial-migration alarm.** I tested the scarier hypothesis and disproved it: `owner_id` and
`wallets_unique_idx` are baseline artefacts, and `fn_platform_owner_id` does **not** exist live, so
`KAN-130` is cleanly unapplied rather than half-applied.

**All other `KAN-138` criteria re-measured live, every ILIKE run against a near-miss control:**
- AC-1 cast `::public.settlement_status` present (line 62). Control `settlement_statuz` → false.
- AC-4 `prosecdef=true`, `provolatile='v'`, `proconfig={search_path=public}` — **'public' alone**.
  Control: body contains no `pg_temp` → false.
- **KAN-128 SURVIVED** — `on conflict (game_id) do update` (line 65) and `on conflict do nothing`
  (line 103), both read from live `prosrc`. Controls `(booking_id)` and `do everything` → false.
- **T-069 containment intact and TIGHTER than at my first review:** `proacl` is now
  `{postgres=X/postgres,service_role=X/postgres}`. PUBLIC, `anon` and `authenticated` are all gone
  — the revoke I recommended landed and held. Nothing re-granted.
- Live `md5(prosrc)` = `d3c6238ea2b04ecd06f87cdb832cda37`, len 3136 — unchanged.
- `game_settlements`, `wallet_ledger`, `wallets` all **0 rows**. No persistent mutation.

**Agreed: the `_wallet_recalc` defect is OUT of `KAN-138`'s scope and is NOT a regression.**
`KAN-138` altered `settle_game` only; `_wallet_recalc` (md5 `513f7be69af61da5dcc56b9cfada1aed`),
`_wallet_after_ledger` (`94c6cec21f3e620c3c3a2981e0d63502`) and the `wallets` schema are untouched.

**But `KAN-138` closable ≠ settlement works, and that must not be misread.** The defect is
deterministic and total: `wallets` holds 0 rows, so *every* user is a first credit, and *every*
settlement still aborts — one level lower than before. `KAN-130` is the fix and sits unapplied in
`Ready`. `KAN-138` moved the blockage; it did not clear the money path.

**Raised beyond the brief — bookkeeping defect, not a `KAN-138` FAIL.** The cast is LIVE but
`KAN-138` has **0 rows** in `supabase_migrations.schema_migrations`; the ledger's latest entry is
`20260907071308 kan155_plan_key_migration`. Repo filenames also drift from applied versions
(`kan128` is `20260909090000_*` on disk, `20260907064216` in the ledger). The ledger no longer
describes production. Flagged to the requester for `devops`/rebaseline; `backend-2-rebaseline` is
already active on adjacent work. Not mine to fix and not a blocker on this ticket.

**Not done:** no Jira transition — reported to the requester, per brief.

### Closure, same day — `KAN-138` PEER review completed and ticket put to Done

Requester lifted the "do not transition" hold once I had ruled; as recorded `review_owner` the
close-out is mine, per `WORKFLOWS.md` §2.3 (only the review owner puts a task to Done through its
validation route). Sequence, each hop kept in lockstep:

1. `store.record_review_result("KAN-138", 25, "backend-1", "pass", <evidence_ref>)` — rev 25 → 26.
   CAS held; I am the exact recorded `review_owner`, so no authority was borrowed.
2. `queue.completion_reasons` → `[]` (eligible). Checked BEFORE transitioning, not after.
3. Jira comment **10875** — the full reasoning, led by *why the token failed scrutiny*.
4. Transition **41** → status **10007** `Done`. Target read back from the LIVE transition set
   (`getTransitionsForJiraIssue`) and cross-checked against `board.py`'s table per `G-018`; the
   response echoed `status.id = 10007`.
5. `store.observe_lifecycle("KAN-138", 26, "10007")` — rev 26 → 27. Final state: `lifecycle.canonical
   = done`, `review_result = pass`, `review_type = peer`, `review_cycle = 1`, `ownership = None`,
   `completion_reasons = ['already-done']`.

**Found while closing, and it strengthens the ruling — the TICKET's AC-2 contains no token at all.**
Its written text is: *"The acceptance criterion is that the path reaches the credit insert — not that
the function compiles … demonstrate `settle_game` actually executing through to its `wallet_ledger`
insert."* `PROBE_RESULT=SETTLE_GAME_SUCCEEDED` appears only in the migration file's verification
block and in `T-068` — **never in the acceptance criteria**. So even the strict "an AC is its written
text" position lands on PASS: the token was never part of AC-2's text, and the text's actual demand
is exactly what the AFTER-ROW evidence establishes. My earlier reasoning stands and now has a third
independent leg.

**AC-5 also satisfied on re-read:** it requires that IF a `DROP`+`CREATE` was used, `EXECUTE` is
revoked from `PUBLIC` and `anon` and the RESULTING `proacl` asserted — not that the revoke ran.
Asserted: `proacl = {postgres=X/postgres, service_role=X/postgres}`. Both gone.

**AC-3 — honest reading, and I will not overstate it.** It says KAN-128's P3 re-settle probe
"becomes demonstrable once this lands", explicitly "not re-specified here". The blocker AC-3 names —
*this ticket's* 42804 — is removed, so AC-3 is met as written. But P3 is still not runnable
end-to-end in practice, because a re-settle now aborts at `_wallet_recalc`'s 23502 (`KAN-173`).
AC-3 is satisfied; the probe it forward-references is not yet exercisable. Those are two different
statements and collapsing them would repeat exactly the error I ruled against.

**Confirmed by `po` while I was reviewing, and it widens my carry-forward:** `_wallet_after_ledger`
is the only caller of `_wallet_recalc`, but **four** functions write `wallet_ledger` — `settle_game`,
`request_payout`, `admin_cancel_payout`, `admin_wallet_adjust`. So `KAN-173` is not a settlement
defect, it is **every wallet-ledger-writing path in the schema**. Also noted: `KAN-130` is marked
Done in Jira while its migration is unapplied (internal APPLY GATE blocked on `KAN-131` Section B) —
a Done ticket describing an unshipped fix, now on `KAN-173` for `cto` to sequence. My own read
independently corroborates the unapplied half: `fn_platform_owner_id` does not exist live.

My bookkeeping flag is carried by **`T-068` Amendment 2** (`backend-2` rebaselined it). Not mine.

**Production mutations across this entire review: 0.** Every query was a SELECT; the probe was not
re-run.

---

## 2026-09-10 — KAN-173 PREFLIGHT (assessment only; no claim, no implementation)

**Did.** Sized `KAN-173` and designed its verification. **Read-only throughout against
`wtncuzcskpigqpmnxwws`: 0 DDL, 0 DML, 0 `apply_migration`, 0 `db push`.** Every claim below is from
`pg_proc` / `pg_get_functiondef` / `pg_indexes` / `pg_constraint` / `pg_policies` /
`information_schema` / `pg_trigger`, or from `DECISIONS.md` read directly. T-068 freeze respected.

**Work Effort: 2 sittings.** Sitting 1 — author from `pg_get_functiondef`, apply, post-verify
attributes and `proacl`. Sitting 2 — the probe pack, which is the bulk, because the pre/post flip
requires two runs bracketing the apply, plus the `ON CONFLICT` negative case and the `fn_get_wallet`
documentation probe.

**Surfaces.**
- `Dabbler/dabbler-code/supabase/migrations/20260910110000_kan173_wallet_recalc_owner_id.sql` (new;
  next free timestamp after `20260910100000_kan170_…`)
- `Dabbler/dabbler-code/supabase/tests/kan173/` (new; `kan128`/`kan130` are the precedent)
- `agent/status/backend-1.md`

No `lib/core/config/supabase_config.dart` change: `_wallet_recalc` is internal, adds no table,
bucket or app-called RPC name.

**Independently corroborated the two scoping facts, rather than inheriting them.** A catalogue sweep
for every `public` function referencing `_wallet_recalc` or writing `wallets` returns exactly three:
`_wallet_after_ledger` (sole caller of `_wallet_recalc`), `_wallet_recalc`, `fn_get_wallet`. And all
four money paths are `prosecdef = true`, all touch `wallet_ledger`, **none calls `_wallet_recalc`**.
So this is one change to one function, verified as consequences. `trg_wallet_ledger_recalc` is
`tgenabled = 'O'`.

**`settle_game` now reaches the defect.** The `KAN-138` cast is live in the catalogue, so the
`42804` that used to abort it first is gone and the very next thing it hits is this `23502`. That
retires my own `KAN-128` finding 1.

**`ON CONFLICT (user_id)` — verified, and cto's conclusion holds for a narrower reason than stated.**
Three unique indexes: `wallets_pkey (user_id)`, `wallets_unique_idx (owner_type, owner_id,
currency)`, `wallets_id_unique (id)`. The arbiter binds `wallets_pkey` only; a conflict on either
other index raises an unhandled `23505`. `wallets_id_unique` is unreachable (`id` defaults to
`gen_random_uuid()`, not named in the insert). `wallets_unique_idx` is safe **because the map
`p_user -> ('user', p_user, 'AED')` is injective and `_wallet_recalc` is the only writer that
produces it** — not because the two indexes identify the same row in general. **Nothing in the
schema enforces `owner_id = user_id`**; a row with `user_id = A, owner_id = B` would make
`_wallet_recalc(B)` miss the pkey arbiter and raise `23505` on `wallets_unique_idx`. Unreachable
today — `wallets` holds **0 rows** (measured) and no writer produces such a row — so the ruled
statement is correct as written. It is safe under an unenforced invariant, and that belongs on the
ticket because `KAN-130` touches exactly this.

**Checked whether the fix creates a write primitive. It does not.** `_wallet_recalc` carries
`anon=X, authenticated=X` in `proacl` and is `SECURITY INVOKER`, so post-fix it becomes a *working*
anon-reachable PostgREST RPC — worth checking rather than assuming, since making it work is the
whole point. `anon` and `authenticated` hold **SELECT only** on `wallets` (no INSERT/UPDATE grant),
and `wallets_block_dml` is `FOR ALL … USING false WITH CHECK false`. An anon caller fails `42501`
on the grant before RLS is consulted. **No new exposure.** Consequence for the probe pack: a probe
run as `authenticated` gets `42501`, not `23502` — a different error that would misreport where the
defect is. The running role is therefore a declared precondition of the pack, not an incidental.

**The `KAN-128` grant trap does NOT apply here.** That was `DROP`+`CREATE`, which re-derives the ACL
from `pg_default_acl` and silently re-grants `anon` by name. `KAN-173` is a pure `CREATE OR REPLACE`,
which preserves `proacl` verbatim. The author asserts `proacl` **unchanged** post-apply as a
regression check, and must not re-grant anything.

**`fn_get_wallet` — named, not fixed, and `T-071`'s word "unreachable" is imprecise.** It omits
`user_id` (`NOT NULL`, no default) and so raises the mirror `23502`. It is uncalled internally
except by `trgfn_payment_to_ledger()` (itself dead per `T-055`), but it carries `anon=X,
authenticated=X` and lives in `public`, so it **is externally invocable** as an RPC. It fails closed
today. That distinction matters for whoever fixes it under `KAN-130`.

**Also named, not fixed:** `owner_type` is nullable while participating in `wallets_unique_idx`
(`T-052`, `KAN-130`'s).

**Authority conclusion — stated, not asked: ordinary `backend-N`, not CEO-reserved.** The change is
`CREATE OR REPLACE FUNCTION` on one function; it mutates no row, so `019`'s user-data reservation is
not engaged, and both tables hold 0 rows. `CONTRACT.md`'s "Supabase project — writing" row: owning
`backend-N` authors and applies under `G-002`'s four conditions with `G-006` claim-comment
discipline, PEER-reviewed by another `backend-N`. `T-068`'s recovery step 1 authorises forward-only
`apply_migration` — read directly at `DECISIONS.md:9652`, not inherited. `T-071` independently
reaches the same conclusion ("No CEO authorization required"). Route is PEER by `schema_change`; I
neither author nor pick the reviewer.

**Jira NOT read.** `getJiraIssue` on `KAN-173` failed four times with the Atlassian MCP's generic
"trouble completing this action". **So "any AC not testable as written" is UNASSESSED**, not clear —
I will not infer acceptance criteria from the dispatch brief. Two AC-shaped hazards I can state
without the ticket, from the schema alone: (1) any AC asserting `settle_game`/`request_payout`/
`admin_cancel_payout`/`admin_wallet_adjust` "now work" is **not testable through their public entry
points** — all four are gated on `auth.uid()`, which is NULL in an MCP session, so they raise
`auth_required`/`forbidden` before reaching the ledger, the `T-055` trap exactly; (2) any AC reading
as "the wallet write path is fixed" is **false** and must be scoped to the ledger-recalc half.

**Production mutations: 0.**

## 2026-09-10 — KAN-173 Preflight ADDENDUM: ACs read via Rovo; sizing revised 2 → 3 sittings

**Did.** Closed the gap left open above. The **Rovo** connector succeeded where the primary Atlassian
MCP failed four times, so the six ACs are now assessed. Still read-only; still no claim. **Production
mutations: 0.**

**One of my own conclusions was too strong and I am correcting it.** I wrote "do NOT probe the four
callers through their entry points" because `auth.uid()` is NULL in an MCP session. That premise was
right; the conclusion was wrong. `auth.uid()` is `coalesce(nullif(current_setting(
'request.jwt.claim.sub', true),''), (nullif(current_setting('request.jwt.claims',true),'')::jsonb
->>'sub'))::uuid` — read live. So `SET LOCAL request.jwt.claims` **does** drive it, and the callers
**are** reachable through their real entry points inside an aborted transaction. AC-2 demands exactly
that, and it is achievable. My P5 becomes "probing the callers needs a JWT-claims harness", not
"don't".

**Checked a suspected third dead path and it is NOT one.** `settle_game` upserts `game_settlements`
`on conflict (game_id)` and `pg_constraint` shows no unique on `game_id` — which would be `42P10`.
`pg_indexes` shows `idx_game_settlement_unique` (a unique *index*, not a constraint), which satisfies
inference. Sound. Worth the query rather than the assertion.

**Fixtures measured live:** `games` 218, `commission_rules` active 1, `role_grants` admin 1,
`game_settlements` 0. Enough to drive AC-2.

**AC-2's real cost, per caller — this is what moves the estimate.**
- `admin_wallet_adjust` — **cheapest, and the right AC-2 anchor.** Needs only the admin as
  `auth.uid()` and a real `p_user_id`. **Zero fixtures.** Straight to the ledger insert.
- `settle_game` — a real game + its organiser; gross must exceed the fee so
  `organiser_earnings_aed > 0` (`wallet_ledger_amount_aed_check` is `amount_aed > 0`). Moderate.
- `request_payout` — **circular, and it breaks AC-2's flip.** It reads `balance_aed` from `wallets`
  and raises `insufficient_funds` when the balance is short. `wallets` is empty, so **pre-fix it
  fails on `insufficient_funds`, never on `23502`.** Post-fix it needs a wallet with a balance first,
  i.e. a chained `admin_wallet_adjust` credit, plus a `payout_beneficiaries` row.
- `admin_cancel_payout` — deeper on the same chain; needs a payout from the step above.

So AC-2 is one **chained** aborted transaction: `admin_wallet_adjust` → wallet exists →
`request_payout` → payout exists → `admin_cancel_payout`, with `settle_game` independent. **For two
of the four callers the pre/post flip is unavailable** — their pre-state failure is a different
error — so their evidence is post-only, as a consequence of the shared trigger.

**Work Effort revised: 2 → 3 sittings.** S1 author + apply + post-verify (`proacl` unchanged). S2
P0–P4/P6. **S3 the AC-2 harness** — JWT claims, four callers, chained state. That third sitting is
entirely AC-2's "end to end, not inspected only", which my first estimate underweighted because I had
not read the ticket.

**AC verdicts.**
- **AC-1** (cto records the sequencing decision) — satisfied in substance by `T-071` (separate
  forward-only fix), **but not recorded on the ticket**; the newest comment still calls it open.
  `po`'s bookkeeping.
- **AC-2** — testable but expensive, and **imprecise as written**. "No `23502`" is *trivially* true
  pre-fix for `request_payout`/`admin_cancel_payout`, which fail earlier for unrelated reasons.
  Recommend rewording to the mechanism: *all four complete a `wallet_ledger` write and the resulting
  `wallets` row carries a non-null `owner_id`* — that is what the fix actually guarantees.
- **AC-3** (T-049 Invariant 3, recompute never increment) — testable and **cheap**; my P2 already
  proves it (two ledger rows, assert balance = the sum, not a double-count).
- **AC-4** (no conflict/duplication with Section A) — testable but **not mine**; it is a `cto`
  confirmation. Concrete input: when `KAN-131` opens the gate, Section A's owner-keyed
  `_wallet_recalc` **overwrites** mine — a clean forward supersede, not a conflict, *if* Section A is
  correct. **Flagging a contradiction I did not resolve:** the ticket says Section A "implements this
  fix in full" (lines 217-264), while `T-071` says KAN-130's Section A **fails to restate**
  `_wallet_recalc` when it drops `user_id`. Both cannot hold. `cto`'s to settle under AC-4.
- **AC-5** (closing verdict states `fn_get_wallet` still open) — testable; my **P6 turns it from an
  assertion into evidence**.
- **AC-6** (applied via `apply_migration`, repo file at the exact returned version) — testable, and
  **precisely what is blocked** by the denied `apply_migration` permission.

**Second, independent blocker beyond the permission.** The ticket is Jira status **To Do** (10004),
with **`work_effort` and `due_date` unset** by design pending AC-1. It is not in `Ready`, so it fails
the Ready facts and **is not claimable even once `apply_migration` lands.** `po` must record AC-1,
set Work Effort (3) and surfaces, and move it to Ready first.

## 2026-09-10 — KAN-173 APPLIED AND VERIFIED. Version `20260910171433`. Now in Peer-review.

**Did.** Owned, applied and verified `KAN-173` — `_wallet_recalc` supplies `owner_id`. Ready →
Back-end (transition 5) on start, Back-end → Peer-review (transition 7) on finish; both ids read
back before calling (`G-018`). **I did not pick my reviewer.**

**Applied version `20260910171433`** (`kan173_wallet_recalc_owner_id`), confirmed in
`list_migrations`. Via `apply_migration`; **no `db push`, no replay, no blanket repair, nothing
pushed to a remote.** Repo file committed at that exact version per `T-068` step 5 — **the returned
version named the file, not my Preflight guess** (`20260910110000` was wrong and discarded).

**Touched.**
- `Dabbler/dabbler-code/supabase/migrations/20260910171433_kan173_wallet_recalc_owner_id.sql` (new)
- `Dabbler/dabbler-code/supabase/tests/kan173/probes.sql` (new)
- this file

Local commit `5d32afc` on `Canary`, **by explicit path** — `docs/CONVENTIONS.md`, the KAN-130/131
migration and an untracked KAN-170 file were dirty in that tree from other agents and are untouched.

**G-002 discipline.** Claim comment posted first (`10908`) carrying the P0 table and both PRE-side
failures. Live source re-read immediately before applying: md5
`88efbd7bcc0609f47f3f169c6547f071`, **byte-identical to the Preflight read — no drift.** Body
restated from `pg_get_functiondef`, never a repo file. Results posted back (`10911`).

**Post-apply catalogue: `prosecdef=false` (still INVOKER, not hardened), `proconfig` preserved,
`proacl` UNCHANGED (asserted `= true`, not eyeballed), trigger still `O`.** `CREATE OR REPLACE`
preserves the ACL, so `KAN-128`'s `pg_default_acl` trap — a DROP+CREATE re-granting `anon` **by
name**, where `REVOKE FROM PUBLIC` was insufficient — does not arise. Nothing re-granted.

**The proof was the flip, and every probe was demonstrated failing first.**

| Probe | PRE | POST |
|---|---|---|
| P1 the defect | `23502` on `owner_id` | **`P0001 PROBE_REACHED_END`** |
| P2/P3 DO-UPDATE + columns | unreachable | `balance=35.00 held=-4.00 rows=1` |
| P4 negative case | — | `23505` on `wallets_unique_idx` |
| P6 `fn_get_wallet` | `23502` on `user_id` | **identical** |

**AC-3 satisfied by P2:** `wallets` rowcount **1** after three ledger rows, so the `DO UPDATE`
branch fired rather than duplicating, and `35.00` is a full recompute, never an increment (`T-049`
Invariant 3).

**P4 converted my Preflight reasoning into evidence.** I constructed `user_id=A, owner_id=B` and
reproduced the predicted `23505` on `wallets_unique_idx` from `_wallet_recalc` line 20. So
`ON CONFLICT (user_id)` is safe **under an unenforced invariant**, not because both unique indexes
coincide. `cto` reached the right answer; the mechanism is narrower than the ruling stated, and
`KAN-130` changes the arbiter to exactly that key. Recorded on the ticket and in the migration
header.

**AC-2 — all four callers, end to end, real entry points.** My Preflight P5 said don't probe them;
**that was wrong and I corrected it before executing.** `auth.uid()` reads `request.jwt.claims`, so
`set_config` satisfies each function's own authorization gate rather than bypassing it. One chained
aborted transaction: `admin_wallet_adjust` (100.00, creates the wallet) → `settle_game` (280.00,
180 earnings on 200 gross at 20 fee) → `request_payout` (held −50.00) → `admin_cancel_payout` (held
0.00, **trigger fired on UPDATE**, not INSERT). Each completed a `wallet_ledger` write and the
resulting row carried a non-null `owner_id`. **The reworded AC mattered:** the old "no `23502`"
would have passed vacuously for the two callers that fail earlier on `insufficient_funds`.

**Scope boundary held.** P6 shows `fn_get_wallet` failing **identically** before and after. This
closed the ledger-recalc half **only**; the wallet write path is not fixed in general, and that is
evidence rather than an assertion. `fn_get_wallet` and `owner_type` nullability untouched — both
`KAN-130`'s.

**Correction I accepted from `cto`.** My Preflight said a naive `fn_get_wallet` `user_id` fix would
yield an anon-callable wallet-minting RPC. The grants are right, the consequence was overstated: it
is `SECURITY INVOKER`, so its INSERT runs as the caller and `wallets_block_dml` denies it. Making it
**definer** is what would create that primitive. My own earlier note said the same thing correctly
("fails `42501` on the grant before RLS"); the later phrasing drifted.

**Nothing committed to the money path.** `wallets` 0 · `wallet_ledger` 0 · `payouts` 0 ·
`payout_beneficiaries` 0 · `game_settlements` 0. Disclosed rather than discovered:
`wallet_ledger_id_seq` advanced to 9 (sequences are non-transactional). Probes referenced **real
`auth.users` ids** — the FK admits nothing else — read-only reference, aborted write, **no user row
mutated**.

**Work Effort actual: 3 sittings**, matching the revised estimate. AC-2's harness was the third,
exactly as re-sized.

**Note, not acted on:** `list_migrations` has no ledger entry for `kan138` or `kan170` though both
have repo files and `kan138`'s cast is live. That is `T-068`'s repo-vs-ledger divergence, not mine,
and I did not touch it.

---

## KAN-131 — platform owner sentinel — BLOCKED AT APPLY (2026-09-10)

**Not done. `apply_migration` was denied by the Claude Code auto mode classifier.** Harness
permission refusal, not a database error and not a SQL fault. I stopped rather than falling back to
`execute_sql` — no version, no ledger row, and that is how orphans are made. Ticket held in
**`Back-end` (10043)**; I did **not** transition to Peer-review, because there is nothing applied to
review and a PEER seat would be reviewing an intention.

**The dispatch prediction was wrong, and this is the finding worth carrying forward.** The working
theory was that the two denials earlier today carried `ALTER TABLE`/`CREATE TABLE` + `GRANT`/
`REVOKE`, while the two that landed (KAN-173 among them, mine) were pure `CREATE OR REPLACE
FUNCTION`. KAN-131 **is** two pure `CREATE OR REPLACE FUNCTION` statements and was denied anyway.
DDL class alone does not explain the classifier. Whoever is tuning that expectation should not keep
predicting from statement type.

**Database byte-identical after the denial** — I re-read the catalogue rather than assuming a denial
means no contact. `pg_get_functiondef` md5 `486f525a7be9436a24ce5386bd7a32ff` before and after;
`prosecdef=false`, `proconfig={"search_path=public, pg_temp"}`, `proacl` unchanged;
`fn_platform_owner_id` absent in every schema. No partial application. That md5 is the rollback
artefact.

**Probes demonstrated failing before they could count.** `select public.fn_platform_owner_id()` →
`42883`. AC2's static probe measured `sentinel_ref_count = 0`, `gen_random_uuid_count = 2`,
`on_conflict_count = 3`, both comment blocks present. These are the assertions that must invert; a
probe nobody has seen fail is not evidence.

**backend-8's Preflight re-verified independently, not accepted.** Sentinel absent across every
schema (not just `public`), zero callers by `prosrc` sweep, `to_regclass('public.bookings')` null.
All three findings hold.

**Migration authored from the live catalogue**, never a repo file — exactly two tokens differ.
`SECURITY INVOKER`, `search_path`, all three `ON CONFLICT DO NOTHING` and both load-bearing comment
blocks preserved. Held at `/Users/moatazmustapha/.claude/jobs/66e02d1b/tmp/kan131_fn_platform_owner_id_sentinel.sql`
and deliberately **not** in `supabase/migrations/`: T-068 step 5 wants the filename to carry the
returned version, and inventing one is the orphan failure inverted. The gated
`20260910090000_kan130_kan131_…` was neither applied nor read as source.

**AC6 cannot be satisfied and I am not going to dress that up** — no version string, so no repo
file, so nothing committed to `Canary`. AC1/AC2 unmet pending the apply. AC3 was deferred by the
ticket itself.

**Flagged, not acted on:** `pg_default_acl` still grants `anon=X` on **functions** (KAN-67 narrowed
*table* defaults only), so the sentinel will be `anon`-executable once it exists. Harmless — it
returns a hardcoded constant — and adding a `REVOKE` would author shape `cto` never ruled.

**Unblocks on:** a permission grant for `apply_migration`. No rework needed; the migration is
authored against a catalogue state re-verified as unchanged.

---

## 2026-09-11 — KAN-131 — BLOCKED AT APPLY, SECOND TIME. Same wall, re-verified.

Dispatched with `apply_migration` described as "re-authorized and verified live". It is not.
**The call was denied again by the Claude Code auto mode classifier** — fourth denial on this
ticket. A harness permission refusal, not a database error and not a SQL fault. Per the dispatch
instruction I stopped rather than reaching for `execute_sql`: that path returns no version string
and writes no ledger row, which is precisely how migration orphans are made. The denial message
itself invites trying another tool; the brief forbids it for this case and the brief is right.

**Ticket held in `Back-end` (10043).** Not advanced to `Peer-review`. Ownership not released.

**No overnight drift — the work I authored yesterday is still authored against current reality.**
Re-read the live catalogue before touching anything: `pg_get_functiondef` md5
`486f525a7be9436a24ce5386bd7a32ff`, byte-identical to the pre-apply capture of 2026-09-10.
`gen_random_uuid_count=2`, `sentinel_ref_count=0`, `on_conflict_count=3`,
`to_regclass('public.bookings')` null, `fn_platform_owner_id` absent in every schema. The migration
needs no rework.

**Both probes demonstrated failing again, today, before the apply attempt** — not carried over from
yesterday's transcript. `select public.fn_platform_owner_id()` → `42883: function
public.fn_platform_owner_id() does not exist`. AC2's static probe: `sentinel_ref_count = 0`. A probe
nobody has watched fail is not evidence, and evidence does not keep overnight.

**Database untouched, verified after the denial.** md5, `prosecdef=false`,
`proconfig={"search_path=public, pg_temp"}`, `proacl={=X/postgres,postgres=X/postgres,service_role=X/postgres}`
all unchanged; sentinel still absent. No partial application.

**Correcting the dispatch's working theory, which is now dead twice over.** The brief said the
denial pattern tracked DDL class — `ALTER`/`CREATE TABLE` + `GRANT`/`REVOKE` denied, pure
`CREATE OR REPLACE FUNCTION` allowed. KAN-131 is two pure `CREATE OR REPLACE FUNCTION` statements
and has now been denied four times. **DDL class does not explain the classifier's behaviour.**
Whoever is tracking the pattern should stop using this ticket as evidence for it.

**AC status unchanged from yesterday:** AC1 unmet (nothing applied). AC2 probes written and
re-demonstrated failing; cannot pass until applied. AC3 deferred by the ticket itself. AC4 satisfied
in the authored body. AC5 all three `ON CONFLICT DO NOTHING` clauses present. AC6 **cannot be
satisfied** — no version string, so no repo file, so nothing committed. AC7 pre-apply values
captured; the post-apply live read it actually requires is not possible yet.

**Still flagged, still not acted on — and I want this visible rather than quietly settled.**
Comment `10591` (`po`, 2026-09-06, `T-058` mirror) states the sentinel's creation *must* carry an
explicit `REVOKE EXECUTE ... FROM PUBLIC, anon` with the resulting `proacl` as evidence. It is not
in the numbered AC list, and `backend-8`'s Preflight and I both concluded adding it would author
shape `cto` never ruled. I kept the migration byte-identical to what was authored and characterised
yesterday — changing it now would mean the thing I re-apply is not the thing already described.
**That disagreement is unresolved, not closed.** `pg_default_acl` still grants `anon=X` on
functions (KAN-67 narrowed *table* defaults only), so the sentinel will be `anon`-executable once it
exists; harmless in itself, since it returns a hardcoded constant.

**Unblocks on:** a real permission grant for `apply_migration` on `wtncuzcskpigqpmnxwws` — not an
assurance that one exists. Migration held at
`/Users/moatazmustapha/.claude/jobs/66e02d1b/tmp/kan131_fn_platform_owner_id_sentinel.sql`.

---

## 2026-09-11 — KAN-168 PEER review (backend-5's work) — **PASS**

Reviewing is not claiming; KAN-131 ownership undisturbed. Verified independently against
`wtncuzcskpigqpmnxwws` — `backend-5`'s report was not used as evidence for anything.

**Coverage checked directly, not inferred from the total.** The brief was right to insist. Ran an
anti-join of `subscription_plans × enum_range(notify_priority)` against `notification_hourly_caps`:
**`<none missing>`**. Every one of the 32 pairs has a cap row. Totals corroborate — 32 rows, 8
`urgent`, all at exactly 50 (`count(distinct max_per_hour)=1`, min=max=50), 8 plans, 4 enum values.

**The assertion can fail, and I watched it fail.** Re-ran `backend-5`'s `DO $$` block verbatim,
read-only, with `v_actual` taken from `where priority <> 'urgent'` — a reconstruction of the
pre-migration 24-row state. It raised:
`P0001: notification_hourly_caps incomplete: 24 rows, expected 32 (plans x notify_priority values)`
— **character-for-character the message `backend-5` claimed**. Its pre-apply failure claim is
corroborated, not taken on trust. No data mutated to produce this.

**Counted by join, no literals.** Stripped comments from the executable portion (107-156): no bare
`8`, `4`, `24` or `32` anywhere. Insert derives keys `from public.subscription_plans`; the expected
factor is `count(*) subscription_plans × count(*) pg_enum`. Only literals are `'urgent'` and `50`,
both the ruled values.

**AC3 — `can_send_notification_now` untouched, and untouchable by this file.** Live:
`prosecdef=false`, `provolatile='s'` (STABLE), `proconfig={"search_path=public, pg_temp"}`, and
`IF v_cap IS NULL THEN RETURN true` present verbatim — T-067's rejected flip was not made. Stronger
than a live match: the executable SQL contains **no** `create/alter/drop/grant/revoke/update/delete`
at all and never names the function. It is an `INSERT` plus an assertion. AC3 holds by construction.

**Its completeness argument holds — I checked the premises rather than the prose.**
`notification_hourly_caps_pkey PRIMARY KEY (plan_key, priority)` (no duplicate pairs),
`notification_hourly_caps_plan_key_fkey FOREIGN KEY (plan_key) REFERENCES subscription_plans(key)`
(no row outside the plan set), `priority` is typed `notify_priority` (no row outside the enum), both
key columns NOT NULL. Rows are therefore a duplicate-free subset of the cross product, and a subset
whose cardinality equals the finite set IS that set. **The one premise it left implicit and I
verified:** the assertion's plan factor is `count(*) subscription_plans`, i.e. rows, while the
argument needs distinct *keys* — those coincide only because `subscription_plans_pkey PRIMARY KEY
(key)`. Confirmed. Argument sound.

**The T-068 §B rename is right.** Remote ledger carries `20260911074412` /
`kan168_notification_hourly_caps_urgent_rows`; repo filename matches exactly. That makes this the
one migration `supabase migration list` can reconcile by name. Agreed with `team-lead` — keep it.

**Scope clean.** Commit `6422003`, one file, 155 insertions, nothing else. On `Canary`, not pushed
(`git branch -a --contains` shows no remote branch).

**Two observations, neither a FAIL, neither mine to fix.** (1) The assertion is a coverage proof
only while the PK and FK stand — drop either and it silently degrades to a bare count. Worth a line
in the file, not a rework. (2) The file carries its own `begin;`/`commit;` inside what
`apply_migration` likely already wraps; harmless here because the assert precedes the commit either
way, so insert → assert → abort-on-failure holds regardless.

**Verdict: PASS.** No rework required. Posted to KAN-168 and reported to `team-lead`. No ticket
created, nothing fixed — rework, had there been any, is `backend-5`'s.

---

## 2026-09-11 — KAN-181 PEER review (backend-3's work) — **FAIL, narrowly, on AC6 only**

Reviewing is not claiming; KAN-131 ownership undisturbed. All verification independent against
`wtncuzcskpigqpmnxwws`; `backend-3`'s report was not used as evidence for any claim.

**The security substance is correct and I could not break it.** Everything below PASSES. The single
failure is provenance: **the migration file is untracked — `git status` reports `??`, it has never
been committed.** AC6 requires the repo file *committed* at the returned version. Naming and bytes
are right; the commit is absent. `supabase/tests/kan181/probes.sql` is likewise untracked. I held my
own KAN-131 on exactly this criterion yesterday and apply the same standard here.

**P1/P2 — measured by `has_function_privilege`, never a `proacl` text match.** `anon` false,
`authenticated` false, **`public` false**, `service_role` true. `proacl` =
`{postgres=X/postgres,service_role=X/postgres}`. `proconfig` = `{"search_path=public, extensions"}`
— `row_security=off` gone, and `position('row_security' in pg_get_functiondef)` = 0. `prosecdef`
true, owner `postgres`. Naming PUBLIC explicitly in the revoke was right: a bare `=X/postgres` entry
is a PUBLIC grant `anon` inherits without being named.

**The control fails, which is what makes P1 mean anything.** Same predicate aimed at `jwt_role()`:
`anon`, `authenticated` and `public` all **true**, `proacl` carries `anon=X/postgres`. The predicate
discriminates rather than passing on everything.

**Body unchanged — but the claimed md5 is `prosrc`, not `pg_get_functiondef`, and that distinction
is the whole point.** `md5(prosrc)` = **`993866e237a6563c6df112de59a34988`**, exactly as claimed,
1115 chars. `md5(pg_get_functiondef)` = `717efdc2e05fafe9ebfc24457c228ef0` and **legitimately
differs**, because `pg_get_functiondef` renders the `SET` clauses that AC2 deliberately removed.
Anyone checking "body unchanged" against `pg_get_functiondef` would have recorded a false failure.
The ACL survived byte-for-byte: `ALTER … RESET` over `DROP`+`CREATE` was the correct instrument,
since a recreate re-derives from `pg_default_acl`, which still grants `anon` EXECUTE on new `public`
functions — it would have re-opened the exact hole.

**AC4 HTTP round-trip — and my first probe was wrong in an instructive way.** Two required params
were missing (`p_kind`; 10 of 13 args carry defaults), so I got `404 PGRST202` from *argument
resolution*, not containment. A sloppier probe would have recorded "contained" for entirely the
wrong reason. With all three required params: **`HTTP 401`, `{"code":"42501","message":"permission
denied for function create_system_post"}`**, and the control `rpc/jwt_role` returned **`200
"anon"`** immediately after on the same transport. Containment is by ACL, not by schema-cache
invisibility — PostgREST still resolves the function and reaches the privilege check. `posts`
unchanged at 503, zero probe rows written.

**AC6 arithmetic is exact — I checked it rather than accepting it.** Repo file md5
`dea4f00dfb5013162d49214b1bedd3b8` is **identical** to `schema_migrations.statements[1]`; 2942
chars, 2944 bytes on both sides. Exactly one non-ASCII character, U+2014 EM DASH at index 11, 3
bytes for 1 char → delta of 2. The explanation is precisely right. Only the commit is missing.

**AC2's redundancy argument is CORRECT but stated in its weaker form.** It rests the case on the
EXECUTE holder set — so `team-lead`'s question is well aimed. The real guarantee is stronger and
does *not* depend on that set: the function is `SECURITY DEFINER` owned by `postgres`, whose
`rolbypassrls` is **true**, so the body bypasses RLS by the *owner's* attribute whoever calls it.
Two further points in its favour, neither made: `service_role` and `supabase_admin` also carry
`rolbypassrls` (`supabase_admin` is `rolsuper`), and `SET row_security=off` never granted bypass to
a non-privileged role anyway — it makes such a role ERROR on an RLS table. Removing it therefore
moves future behaviour in the *safer* direction. **One factual imprecision:** the header says three
EXECUTE holders including `supabase_admin`, but live `proacl` carries two entries; `supabase_admin`
reaches it via `rolsuper`, not an ACL grant. Does not change the conclusion.

**AC5 is covered by class, not per-function** — KAN-175's `scripts/ci/anon_function_grants_diff.sh`
flags SECURITY DEFINER + effectively-anon-executable + unguarded identity argument. Re-granting
`anon` would trip it generically. Sound, and better than a bespoke test. The probe pack exists but
is untracked.

**Verdict: FAIL on AC6 only.** No SQL rework — it is a `git add` and a commit by explicit path to
`Canary`, not pushed. Rework is `backend-3`'s; I fixed nothing.

## KAN-131 — `wallets_self_read` divergence assessed. Does NOT change my migration's shape.

`team-lead` routed `backend-4`'s KAN-190 finding to me. **Confirmed live, and the causal account is
now measured rather than "some other applied path":**

* `wallets` carries **both** `user_id` (NOT NULL) and `owner_id` (NOT NULL), plus `owner_type` and
  `id` (both nullable).
* `wallets_self_read` USING `(auth.uid() = user_id)` — still keyed on `user_id`.
* `20260910090000` is **absent** from `schema_migrations` (confirmed, 0 rows).
* **The column half arrived via `20260910171433 kan173_wallet_recalc_owner_id`, which IS in the
  ledger** — it is the only applied migration touching `wallets` owner columns. And **no applied
  migration has ever touched `wallets_self_read`** (zero matching statements across the whole
  ledger). So the split is fully explained: KAN-173 shipped the column, the policy re-key exists
  only in the never-applied gated file.
* 0 rows. Latent.

**Why it does not change KAN-131's shape.** My migration creates a constant-returning function and
swaps two tokens inside `trgfn_payment_to_ledger`. It touches no table, no policy, and never names
`wallets.user_id` or `wallets.owner_id` — the owner model lives entirely inside `fn_get_wallet`.
`wallets_self_read` is a **SELECT** policy; KAN-131's path is a trigger-side write. The two do not
intersect. The `user_id NOT NULL` half is precisely KAN-173's `23502`, already named out of scope by
the SEQUENCING ruling, and the policy re-key is KAN-130's. **This finding corroborates that those
two tickets are real; it does not widen mine.** Reported to `team-lead` rather than acted on.

---

## 2026-09-11 — KAN-181 AC6 RE-VERIFIED after devops' commit — **verdict now PASS**

devops landed `2c02875`. Re-checked the **committed blob**, not the working tree, because the
byte-identity rests on a single 3-byte em-dash and any `autocrlf`/`.gitattributes`/formatter hook
would have altered it invisibly:

`git show 2c02875:supabase/migrations/20260911075034_…sql | md5` = **`dea4f00dfb5013162d49214b1bedd3b8`**
— **exact match** to `schema_migrations.statements[1]`. 2942 chars / 2944 bytes, U+2014 intact at
index 11. Nothing normalised it on the way into the index. `supabase/tests/kan181/probes.sql` is now
tracked, closing AC5's artefact too.

**AC1–AC5 already held under independent live measurement and none depended on the commit.
KAN-181 is a full PASS.**

## 2026-09-11 — KAN-188 PEER review (backend-2's work) — **PASS**, with one material finding

Reviewing is not claiming. All verification independent; `backend-2`'s comment 10981 was not used as
evidence.

**The counterintuitive mechanism works, and I proved it in the direction that could have failed.**
In one transaction, as `anon`: schema USAGE on `util` = **false**, EXECUTE on
`util.can_manage_venue` = **true** (retained by design), a direct by-name call →
**`42501: permission denied for schema util`**, and RLS-mediated reads still return **379 venues and
679 spaces** — precisely the populations `cto`'s ruling said the specified revoke would have taken
dark. Outer role sees 389/693, so RLS is filtering rather than failing. Containment and
availability simultaneously.

**Seven policies, and my first query found only five.** I had filtered on `polqual` alone;
`venue_bookings_insert` and `venue_members_insert` carry the call in `polwithcheck` only. All seven
now render `util.`-qualified, all `roles = {-}` (PUBLIC), and **zero still reference `public.can_`**.
That the quals followed the function is itself the proof `ALTER … SET SCHEMA` preserved the OID —
corroborated from the applied statement, where `DROP FUNCTION` occurrences = **0**.

**The three self-reported traps are all genuinely closed.**
1. *Seventh caller.* `rpc_my_venue_permissions` is `plpgsql` with `prosqlbody IS NULL` — body stored
   as text, re-parsed at run time, hence no `pg_depend` edge and hence missed by the sibling sweep.
   Now **5 `util.` refs, 0 stale `public.can_` refs**.
2. *The worthless probe.* Reproduced both halves myself: with no JWT it returns the all-false object
   without touching the five calls — passes while proving nothing; with `request.jwt.claims` set it
   **reaches and executes all five, no `42883`**.
3. *The blind assert.* Confirmed the trap is real on this instance —
   `pg_get_function_identity_arguments` returns **`p_user_id uuid, p_venue_id uuid`**, i.e. with
   parameter names, so a match against `'uuid, uuid'` could never be true. The executable assert now
   uses `to_regprocedure(format('%I(uuid,uuid)'))` throughout; the one surviving mention of the old
   function is in a comment documenting the trap, not in code.

**The assert is well-built** — both directions (gone from `public`, arrived in `util`), EXECUTE
**retained** for both API roles with failure text naming the consequence, USAGE false for both, and
`is_venue_admin` pinned at exactly **2** overloads, which live confirms.

### Material finding — the §2g gate substitute is NOT an adequate standing control

This is the part I was asked to press hardest, and it does not hold. **Measured:**
`scripts/ci/anon_function_grants_diff.sh` is hard-scoped `WHERE n.nspname = 'public'` at lines 123
and 177. Grepping all of `scripts/ci/` and `.github/workflows/`: **zero** occurrences of
`has_schema_privilege`, and **zero** references to schema `util`.

So the five have left the gate's population and the substitute exists **only inside the migration's
one-shot assert**. A migration assert proves state at apply time; the gate is a standing regression
detector that runs on every push. They are different kinds of object and one does not replace the
other. **And the exposure is sharper than "unwatched":** because the design deliberately *retains*
EXECUTE, schema USAGE is now the **single** thing between `anon` and the oracle — and it is the one
property no gate checks. A later `GRANT USAGE ON SCHEMA util TO anon` restores the oracle silently.

Not a defect in the applied work — the migration does what `cto` ruled, correctly. It is a real gap
in continuing coverage, and its natural home is **KAN-175**, which owns the gate. No ticket created.

### The ticket's own AC1/AC2 now contradict the applied fix

AC1 says "`anon` EXECUTE is revoked from all five"; AC2 says `has_function_privilege('anon', …)`
returns **false**. Live it is **true**, deliberately, because `cto` overruled revoke in favour of
relocate. **The ACs were never rewritten after that ruling.** Read literally, this work fails its own
acceptance criteria. I am not failing it on that — the ruling supersedes and `team-lead`'s brief says
so — but a future auditor comparing AC2 against live will read a regression that isn't there. A `po`
correction is owed.

**AC4 — met.** Repo file `20260911080000_kan188_relocate_venue_authz_fns_to_util.sql` carries exactly
the ledger version and name, committed at `71db8d5`. **Observation, not a failure:** unlike KAN-181
it is *not* byte-identical to `statements[1]` — 7644 chars vs 5619. I normalised both sides (strip
whole-line `--` comments, strip whitespace) and the **executable content is identical**:
`106fd0ca229ad90c5169fed340432dd8`, 2523 chars, both sides. The ~2000-char difference is commentary
added to the repo file after applying. Replay is faithful; AC4 as written requires the version, not
byte-identity.

**On `user_visible_runtime` absent — I agree, and the reasoning can be stronger than the caller
sweep.** A repo sweep cannot see an external consumer. But the five raised `42P01` for `anon` until
KAN-177 landed **yesterday** (`20260910172908`), so no external consumer could ever have depended on
working behaviour — the window in which they answered at all was about a day. That argument does not
depend on `lib/` being exhaustive, and it is what actually settles it. I also confirmed RLS-mediated
reads are identical before and after.

**Verdict: PASS.** No rework. Two things recorded for others: the §2g coverage gap (KAN-175's), and
the stale AC1/AC2 (`po`'s). I fixed nothing and created no ticket.

**Also observed, out of scope:** `rpc_my_venue_permissions` retains `SET row_security TO 'off'` — the
exact redundancy KAN-181 removed elsewhere this morning, and by the same owner-attribute argument it
is redundant here too. Pre-existing; this migration only re-pointed its calls. Noted for consistency,
not raised.

## 2026-09-11 — KAN-171 PEER review (`public.charges` / `record_charge`) — **PASS**

Reviewer `backend-1` (Shu), review_cycle 1, `review_owner: backend-1` in Persistent State. Author
`backend-4` (Min). Route PEER, system-derived from `schema_change` + `money_path`. I reviewed; I
applied nothing, fixed nothing, created no Jira ticket.

**Probe suite: 24 probes across three rounds, every one force-rolled-back.** Each round ended in a
deliberate `raise exception` carrying the accumulated report as its message, so the report reaches me
*and* the transaction cannot commit. `public.charges` measured at **0 rows** before round 2, before
round 3, and after all three — the table is exactly as the migrations left it.

**My own round-1 probe P8d was broken and I caught it.** It returned `42601`, not the `42501` I was
testing for: I had sent 10 values for 11 columns, so it died at parse and proved nothing about
grants. Re-ran corrected in round 2 → `42501`. A probe nobody has seen fail *correctly* is not
evidence, and a probe that fails for the wrong reason is worse than none.

**The three flagged deviations — all CONFIRMED, and the first is AC2's named checkpoint.**

1. **`UNIQUE (provider, provider_charge_id, kind)`, total not partial.** Tested against T-049's own
   three invariants, not waved through. Natural not surrogate: all three are provider-event facts.
   Enforces idempotency and survives a retry: P2 — a replay with the same key and a *different*
   amount (999.99) was absorbed, returned the existing id, and left the stored amount at **100.00**.
   All three columns `NOT NULL`, so no row opts out — this applies T-049's own `admin_wallet_adjust`
   resolution rather than copying `payment_intents`' partial shape. **`kind` in the key is load-
   bearing and I proved it:** P3 recorded a compensating refund reusing the original provider
   reference; rows sharing the 2-column key = **2**. Under AC2's suggested `(provider,
   provider_charge_id)` that refund would have hit `ON CONFLICT DO NOTHING` and vanished silently.
   The proposed key strictly dominates the suggested one.
2. **`charges_is_venue_member` 1-arg, not the 2-arg described in claim comment 10891 §C.** Confirmed,
   and it is the *stronger* form. A 2-arg `(user, venue)` `SECURITY DEFINER` with `row_security=off`
   granted to `authenticated` is an arbitrary membership oracle — `row_security=off` strips the very
   RLS that would constrain it, so any logged-in user could truthfully probe any (user, venue) pair.
   The 1-arg form derives the subject from `auth.uid()`, so a caller can only ask about themselves.
   P8f: `authenticated` got `false`; P9c: `anon` got `42501`.
3. **`purpose_type = 'game'`, not `'game_settlement'`.** Confirmed. AC4 delegates exact naming, and
   T-063 forbids a second polymorphism idiom — the `_type` column names the *referent*
   (`'user'`→`auth.users`), and `purpose_id` holds a `games.id`. `'game_settlement'` names a
   downstream process. P6c: the CHECK rejects `'game_settlement'` with `23514`.

**The T-074 landmine is demonstrably closed, not merely avoided on paper.** P8c evaluated
`charges_venue_read` as `authenticated` against a **real venue-owned row** that was in scope, and it
returned 0 rows rather than raising `42P01`. An inline `EXISTS` would have inherited `venue_members`'
RLS → `venue_members_select` → `can_manage_venue` → `42P01`, on a money table. §C's reasoning holds.

**Material finding, recorded not failed — a second compensating row against one provider reference is
silently absorbed.** P12: charge 100, refund −40, then a second refund −60 all under `ch_1`. The
third call was absorbed, `record_charge` returned the *first refund's* id — **non-null, so the caller
cannot distinguish it from success** — and the net settled at **60 instead of 0**. The −60 is simply
gone. The mitigation works (P12n: a distinct reference per compensating event → net 0), so this is a
**caller contract, and it is currently undocumented**: `record_charge`'s `COMMENT` documents
idempotency but says nothing about partial refunds needing their own reference. Not an AC2 failure —
it passes all three invariants AC2 names, and real providers issue a distinct `re_…` id per refund —
but it sits directly on T-063's *"same mechanism covers pro-rating"*, and pro-rating is exactly the
repeated-compensation case. Belongs to KAN-169 or whoever writes the first caller. No ticket created.

**Grants are STRICTER than `wallets`, not merely equal.** AC3 says "matches the `wallets` pattern
exactly". The *policy* shape does (`block_dml` `*` false/false + reads). The *grant* posture is
deliberately tighter: `charges` gives `anon` nothing at all, while live `wallets` still carries
`anon=rm`. Better than the AC asked for; the `anon=rm` on `wallets` is pre-existing looseness there,
not this ticket's.

**`service_role` can write the table directly** — `rolbypassrls=t` plus `arwdDxtm`, byte-identical to
`wallets`. So `record_charge` is the only write path by convention, not by enforcement, for that tier.
I checked whether that weakens anything and it does not: the UNIQUE index and `trg_charges_immutable`
both bind a direct insert (triggers are not bypassed by `rolbypassrls`), so a direct write gets a hard
`23505` rather than silent absorption. House pattern, no exposure. Noted, not raised.

**AC7 — met, but backend-4's "byte-identical" claim is an overstatement.** Raw md5s differ on both
files (S1 `ebcecff1…` repo vs `a78980f7…` ledger; S2 `bb362c44…` vs `c8e6360a…`), by 19 and 11 bytes.
I normalised both sides identically — strip whole-line `--`, strip all whitespace — and the
**executable content is provably identical**: S1 `327c9b1d7c55630e37d657e462efc1f2` @ 4569 both
sides, S2 `33db81a2d0b8729c3146103349357bb8` @ 1625 both sides. AC7 requires the version string, not
byte-identity: filenames carry `20260911075539` / `20260911080324` exactly, ledger names match, both
committed (`e502e82`, `1a484a9`) and clean. **Same pattern I found on KAN-188** — commentary added to
the repo file after applying. Replay is faithful; the wording in comment 10994 is not.

**AC5 re-measured myself:** `payment_intents_booking_id_fkey` = `FOREIGN KEY (booking_id) REFERENCES
venue_bookings(id) ON DELETE RESTRICT`, 3 constraints on the table, untouched.

**Verdict: PASS.** No rework. Two items recorded for others: the undocumented partial-refund caller
contract, and the stale "byte-identical" wording. I transitioned nothing — the PEER verdict is mine,
the board move is not.

---

## 2026-09-11 — PEER review, KAN-169 (settle_game organiser/sport/gross derivation, T-069)

Reviewer seat for backend-4 (Min)'s two sittings, comment 10999. **PASS, no rework.** Effort LOW as
briefed; the substance came in under it because every claim was checkable against the live catalogue
rather than against the migration text.

**Read the live body, not the files, first** (`pg_get_functiondef`, T-058). Both repo files then
matched it line for line — S1 `20260911113000_kan169_settle_game_derive_organiser_sport_gross.sql`,
S2 `20260911114500_kan169_settle_game_zero_and_negative_earnings.sql`.

**AC5 / proacl — verified two ways, not one.** `proacl = {postgres=X/postgres,service_role=X/postgres}`
— no bare `=X/` (PUBLIC), no `anon`, no `authenticated`. Cross-checked with
`has_function_privilege`: public/anon/authenticated all **false**, service_role **true**. S1 revokes
`from public, anon, authenticated` explicitly (line 227) rather than PUBLIC alone — the T-078 trap
avoided by name. S2 is `CREATE OR REPLACE` and correctly does **not** restate the revoke; the live
proacl proves it held across the replace. `obj_description` non-null, so the COMMENT survived too.
`settle_game` overload count **1** — the 5-arg signature is gone, no shadow.

**The three ruling rationales are load-bearing, and I confirmed each against `pg_constraint`:**
`wallet_ledger_amount_aed_check = (amount_aed > 0)` — so the zero-earnings guard is *necessary*, not
cosmetic; a 0.00 credit genuinely aborts the settlement. `game_settlements_gross_collected_aed_check
= (>= 0)` — justifies `invalid_gross`. `games_creator_user_id_fkey ON DELETE SET NULL` on a NOT NULL
column — justifies the `organiser_unresolved` arm the author calls unreachable-but-checked.

**Zero vs negative split — correct, and the ordering is the part that matters.** `earnings < 0` raises
`fee_exceeds_gross` at body line 121, *before* the `game_settlements` insert at 125, so no negative
`organiser_earnings_aed` is ever stored regardless of `p_finalize`. Zero settles and skips the credit
via `p_finalize and gs.organiser_earnings_aed > 0`. Checked the interaction the probes did not: a
zero-earnings settle creates `gs.id` without consuming the `('game_settlement', gs.id, 'credit')`
dedup key, so a later re-settle once charges arrive **does** post the credit. The guard does not burn
the key.

**Currency detection — the silent-sum hole is closed by the schema, which I verified rather than
assumed.** `charges.currency` is **NOT NULL**. That matters: `count(distinct)` ignores NULLs, so a
nullable currency column would have let NULL+AED rows read as one distinct currency and sum silently
into the AED-named column. It cannot. Mixed → raise, single non-AED → raise, zero rows → gross 0,
never a conversion.

**Probe evidence — I corroborated it instead of taking it.** 12 probes, count matches the table.
The baseline figure is self-proving: 999,999.00 gross at the single live `commission_rules` row
(rate 10.00, min 0.00, max null, which I read) yields fee 99,999.90 and earnings **899,999.10** —
exactly the number reported. That arithmetic only lands if the probe was executed. Post-state claims
re-measured by me independently: `charges` 0, `game_settlements` 0, `wallet_ledger` 0,
`commission_rules` 1. Nothing was mutated; the probes were genuinely rolled back. `I-control` and the
C/D mutual-absence design are real controls, and probe B doubles as the "can the path execute at all"
check my own contract demands (it proves `status=settled` rather than KAN-138's 42804).

**Three things recorded, none of them grounds to fail:**

1. **Re-settle with *changed* charges diverges settlement row from ledger.** `gs.id` is stable across
the upsert, so `on conflict do nothing` absorbs the revised credit — the row can say 500 while the
ledger holds 108. Probe H only re-settled with charges *unchanged*. This is not a regression: AC4
mandates the dedup and the description explicitly rules a revised derived gross "benign". Reconciling
a revised amount needs a compensating row, which is a different ticket.
2. **AC7 is live and dangerous, not merely noted.** KAN-138's `9d855a5` sits unapplied in Peer-review
reproducing the pre-T-069 body verbatim. Landing it silently restores the 5-arg function and the
bypass. Flagged correctly to po/team-lead; not the implementer's to close, and not mine.
3. **Filename vs ledger version drift, benign.** Files carry `20260911113000`/`20260911114500`; the
ledger stamped `20260911110743`/`20260911111006`. Those are `apply_migration`'s own UTC stamps —
15:07:43 and 15:10:06 +0400, which sits exactly between the file mtimes (15:05, 15:09) and the
comment (15:12). Timeline coheres; names match. Unlike the rest of this batch, whose filenames and
versions agree, so worth a line at rebaseline (T-068) — not a defect.

**I did not execute `settle_game`.** It writes `game_settlements` and `wallet_ledger`; running it
live is user-data mutation on existing money tables, reserved to the CEO (019). Static verification
plus catalogue facts plus corroboration of the author's rolled-back probes was sufficient, and I say
so rather than implying I re-ran them.

**Transitioned nothing, changed nothing, posted no Jira comment** — the brief was report-only. The
PEER verdict is mine; the board move is not.

## 2026-09-11 — KAN-189 PEER review (Shu)

PEER: **PASS**. Reviewed as resolved `review_owner`; did not author, did not touch
supabase_admin's default, did not touch KAN-194.

Independently re-verified against live `wtncuzcskpigqpmnxwws` (not from the report):

- `pg_default_acl`, schema `public`, `defaclobjtype='f'` — postgres-grantor is now
  `{postgres=X,authenticated=X,service_role=X}`: no `anon`, no bare PUBLIC.
  supabase_admin-grantor unchanged, still `{postgres,anon,authenticated,service_role}`.
- Own disposable probe function (created, `proacl` read directly, rolled back):
  `{postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres}`,
  `has_function_privilege('anon',...)` = false. No `=X/postgres` bare-PUBLIC entry.
- Second probe with an explicit `GRANT EXECUTE ... TO anon` → `anon_exec` = true.
  The intentional anon-callable-RPC path is intact (AC4's rule is true and correctly
  scoped: forward-only, postgres-grantor only).
- Pre-existing functions `fn_platform_owner_id`, `rpc_get_friends`,
  `rpc_get_friend_suggestions`, `rpc_potential_vibes` all still carry
  `{=X/postgres,postgres=X,anon=X,authenticated=X,service_role=X}` — untouched,
  confirming forward-only AND making the probe discriminating: pre-fix functions
  carry the bare-PUBLIC entry the probe no longer gets.

Both probes were wrapped so the transaction aborts after inspection — nothing left
behind. Verdict recorded via `store.record_review_result('KAN-189', 11, 'backend-1',
'pass', ...)`; task revision 11 → 12. No Jira transition, no ownership change —
Orchestrator handles closure.
