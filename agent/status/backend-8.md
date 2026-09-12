# agent/status/backend-8.md

**Owner:** `backend-8` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

## 2026-09-10 — no ticket (security incident, caller sweep) — `rpc_potential_vibes` anon-caller sweep
**Agent:** `backend-8` (Saa)
**Outcome:** READ-ONLY sweep for legitimate unauthenticated callers of both `public.rpc_potential_vibes`
overloads. **7-arg: NO anon caller — safe to revoke `anon`+`PUBLIC` EXECUTE.** **6-arg: NO direct anon
caller, but it has ONE in-database dependent — the view `public.v_potential_vibes_default`, which is
granted SELECT to `anon` and is on the CI anon allowlist.** Two findings beyond the brief: (a) the 6-arg
overload is ALSO `SECURITY DEFINER` (brief described only the 7-arg as such); (b) `PUBLIC` holds EXECUTE
on both overloads and on `rpc_potential_vibes_debug` (`=X/postgres` in every `proacl`), so revoking `anon`
alone is insufficient. `rpc_potential_vibes_debug` is anon-reachable via `PUBLIC` but INERT — it raises
`42P01` on a dropped view `public.v_vibes_candidates` before touching data.
**Evidence:** Exposure reproduced in `begin;…rollback;` as role `anon`: 7-arg with a fabricated uuid →
**147 rows / 137 distinct users**; 6-arg → 0; `v_potential_vibes_default` → 0. Negative controls both
demonstrated failing as `anon`: `v_sport_profiles_with_user` → `42501`, `public.get_push_trigger_secret()`
→ `42501` (proves the role switch is real and function ACLs are enforced against the current role).
Repo grep for `rpc_potential_vibes` hits only docs + `supabase/migrations/20260829080500_baseline_schema.sql`
+ CI fixture — **zero Dart callsites**; control: 116 `.rpc(` callsites found under `lib/`. No vibes RPC
constant in `lib/core/config/supabase_config.dart` (control: 184 `static const`, `rpcCreateGameFn` found).
Edge functions: 0 hits across 4 functions (control: 4 files match `serve|Deno`). Catalogue: 2,954 function
bodies scanned via `pg_get_functiondef`, 1 external referrer (`rpc_potential_vibes_debug`); controls
`v_sport_profiles_with_user`=1, `auth.uid()`=180. `pg_depend`: exactly 1 non-index edge →
`v_potential_vibes_default` (control: 90 view→function edges exist db-wide). Triggers 0 of 185 non-internal.
`cron.job` read in full: 1 job, `flush_notifications_every_10_seconds`, unrelated. Runtime logs (24h):
616 edge rows, 0 mention `potential_vibes`, control 125 `/rpc/` calls across 8 distinct RPCs; 17,844
postgres rows, 0 mentions, control 8,622.
**Not verified:** (1) Whether `v_potential_vibes_default` actually breaks for `anon` once EXECUTE is
revoked. `reloptions IS NULL` so it is not `security_invoker`, but PostgreSQL checks *function* EXECUTE
against the **current** role regardless — so I expect the view to start raising `42501` for `anon` instead
of returning 0. I could not prove this empirically without a REVOKE, which the brief forbids, and no
natural control pair exists in this database (0 views anon may SELECT over a function anon may not
EXECUTE). **This must be verified inside the containment transaction.** (2) Whether an external HTTP
client outside the 24h log window calls either overload — no catalogue read can rule this out; logs are
capped at 24h. (3) Log windows older than 24h. (4) The matview result (0) is trivially true — the database
contains 0 matviews.
**Production mutations:** 0. No DDL, no DML, no GRANT/REVOKE, no migration. All probes inside
`begin;…rollback;`. No user data printed — counts and field names only.
**Next:** Unblocks `team-lead`'s containment decision. Recommended: revoke `anon` AND `PUBLIC` on the
7-arg unconditionally; for the 6-arg, decide `v_potential_vibes_default`'s fate first (it is on the
`docs/SCHEMA.md` anon allowlist under `T-027`, so removing anon's reach is an allowlist + CI change too).

---

## 2026-09-10 — KAN-131 Preflight (`fn_platform_owner_id()` sentinel) — ASSESS ONLY, not claimed

**Task:** Preflight KAN-131 under `cto`'s `T-072` (overturns its own `T-052` "one migration").
Verify `cto`'s safety reasoning independently, size it, declare surfaces, design the verification,
state the authority conclusion. No claim, no implementation, no DDL/DML.

**Production reads only,** `wtncuzcskpigqpmnxwws`. **0 mutations:** no DDL, no DML, no
`apply_migration`, no `db push`, no GRANT/REVOKE. `T-068` freeze respected — its step 1 sanctions
forward-only apply for *execution*, not Preflight.

### `cto`'s three safety premises — all VERIFIED independently, none inherited

1. **Sentinel has no callers.** `fn_platform_owner_id` does not exist (`pg_proc` count = 0), and a
   seven-way sweep for the NAME returns `NONE` on every axis: `pg_proc.prosrc`, `pg_views`,
   `pg_constraint`, `pg_attrdef` column defaults, `pg_policies` (qual + with_check), `pg_indexes`.
   **Swept by NAME, not signature** — this is exactly the trap `cto` proved on my own
   `rpc_potential_vibes` sweep earlier today (a catalogue-body sweep cannot see overload dispatch
   because the call site names the function). A function that does not exist has no overloads, so
   the name sweep is sound here — but the reason it is sound is stated, not assumed.
2. **`public.bookings` genuinely absent.** `pg_class` across ALL schemas returns `NONE`, and
   `select 'public.bookings'::regclass` raises **`42P01: relation "public.bookings" does not exist`**
   — the error class named, demonstrated, not predicted.
3. **`42P01` precedes both call sites — but `cto`'s "two statements before" is imprecise.** Measured
   order in the live body: (1) status guard, (2) `financial_ledger` EXISTS guard, (3) **`SELECT
   venue_id FROM public.bookings`** ← raises, (4) `commission_rules` SELECT, (5)(6) two assignments,
   (7) `fn_get_wallet('user',…)`, (8) **`fn_get_wallet('platform', gen_random_uuid(), …)`** ← site 1,
   then the platform INSERT's **`'platform', gen_random_uuid()`** ← site 2. That is **four**
   statements to site 1, not two. **The direction of the argument survives and is actually
   stronger when stated correctly:** every execution path that could reach either
   `gen_random_uuid()` site must first pass through the `bookings` SELECT, so both sites are
   *unreachable*. Note the function is NOT dead in general — statements 1 and 2 return `NEW` early
   and never raise; it is dead *for the paths that reach the call sites*, which is the only claim
   the change needs.

### Live attributes captured (this IS the rollback artifact)

`trgfn_payment_to_ledger()` — `prosecdef=false` (**SECURITY INVOKER**, confirmed; do not add
DEFINER), `proconfig={search_path=public, pg_temp}`, `proacl={=X/postgres,postgres=X/postgres,
service_role=X/postgres}`, `plpgsql`, body 2676 chars via `pg_get_functiondef`. Fired by
`trg_payment_to_ledger` on `payment_intents`. `fn_get_wallet` has exactly ONE signature
`(text,uuid,text)` — no overload ambiguity.

### Three findings that CORRECT or EXTEND the brief

- **TWO load-bearing comment blocks, not one.** `cto`'s ruling names only the KAN-128/`T-049`
  Invariant 4 idempotency note. The live body ALSO carries `-- KAN-136 / T-055: public.bookings
  does not exist. Left as found.` Both must survive `CREATE OR REPLACE` verbatim (`T-044`/§6g).
- **AC5 raises the bar again:** the body must still carry KAN-128's **three** `ON CONFLICT DO
  NOTHING` clauses. Verified present on all three `financial_ledger` inserts in the live body.
- **Function default privileges still grant `anon`.** `pg_default_acl` shows
  `f={postgres=X,anon=X,authenticated=X,service_role=X}`. KAN-67 revoked the *table/view* defaults
  (`r=` is narrowed to `anon=rxtm`) but **not the function ones**. So the new sentinel will be
  created EXECUTE-able by `anon` and `authenticated`. Judged **harmless** — it returns a hardcoded
  all-zeros constant, no data, no privilege, no information. Flagged rather than silently
  "fixed": adding a REVOKE would be authoring shape `cto` did not rule, and `021` reserves shape.

### Surfaces / Work Effort — written via `agent/state/store.py`, KAN-131 now revision 12

- **`surfaces`: `["supabase/migrations/kan131_platform_owner_sentinel.sql"]`** — CORRECTS po's
  prior declaration of the gated shared file, which was right under `T-052` and is stale under
  `T-072`. Timestamp prefix omitted per the repo's own established precedent.
- **`logical_surfaces`: `["public.trgfn_payment_to_ledger", "public.fn_platform_owner_id"]`** —
  NEW. With KAN-131 no longer sharing a file with anything, the real KAN-131/KAN-140 contention is
  a database OBJECT and a file-only declaration would hide it entirely. Matches `backend-3`'s own
  declaration on KAN-140.
- **`work_effort`: 1 sitting, ceiling 2.** Deliberately NOT 2 (unlike KAN-130/KAN-140): those
  needed a throwaway container with a fabricated FK chain seeded across four empty tables. This
  needs **no container and no rows** — verification is a text diff of `pg_get_functiondef` plus
  attribute equality, so the authoring→verifying checkpoint is seconds wide, not a sitting boundary.
- **CONSEQUENCE for another ticket, stated not buried:** KAN-172's engineered collision with
  KAN-131 is **DISSOLVED**. KAN-172 declared both spellings of the gated path specifically to
  contend with KAN-131; under `T-072` KAN-131 will never touch that file, so KAN-172's
  "CONDITIONAL on landing before KAN-131 applies" sizing is moot and its 1-sitting path is safe.
- **Reconciled a parallel `backend-8` assessment** written at 12:50:40Z that reached the same
  `T-072` conclusion but recorded `[]`. Merged both into one basis rather than silently
  overwriting; the notation differs, the substance does not.

### Claimability

`queue.claimable` = **false**, single reason **`unverified-jira`** (identical from `queue.unclaimable_reasons` and
`queue.eligibility_reasons`) — the Jira
lifecycle observation (12:23:59Z) is stale against `CLAIM_FRESHNESS_SECONDS`. Not a defect in the
work; it needs a fresh Jira observation. No STOP/HOLD/FREEZE active; `active_execution_policies`
empty; `ownership` null; route `peer`; `surfaces_assessed` true.

### AC2 and AC3 are NOT TESTABLE AS WRITTEN — the ticket contradicts itself

AC3 demands "two simulated successful payments … both resolve `v_platform_wallet` to the same
`wallets.id`; `wallets_unique_idx` shows exactly one `owner_type='platform'` row per currency."
AC2 demands repeated invocations resolve to the same `wallets.id`. **Neither can ever be
demonstrated on this ticket's scope,** for two independent reasons: the function raises `42P01` at
statement 3 and never reaches wallet resolution at all, and `fn_get_wallet` would then raise
`23502` on `wallets.user_id` (KAN-173). The ticket's own SEQUENCING section says exactly this —
*"this makes a dead path correct; it does not make it live"* — and puts `public.bookings`,
`fn_get_wallet`'s `23502` and the wallets redesign explicitly out of scope. **AC2/AC3 text was
never updated to match the overturn.** Raised to `po` as a ticket defect, not worked around.

### Jira connectivity — ANSWERED

**I can read tickets.** The primary `mcp__atlassian__*` connector fails
("trouble completing this action"); the **Rovo** variant works. The failure everyone has been
hitting is a wrong site: it is **`dabbler.atlassian.net`**, cloudId
**`18c8e9f5-d139-4e03-b5d8-89122cc14937`** — not `onebrain.atlassian.net`. Read KAN-131 in full
with it. KAN-140 timed out at 329s on one attempt (connector intermittent, as warned); did not
retry — KAN-140 is not mine and the cloudId above lets `cto` read it directly.

**Authority conclusion (stated, not asked):** `backend-N` under `CONTRACT.md:399` / `G-002` with
PEER. **NOT CEO-reserved.** Two `CREATE OR REPLACE FUNCTION` statements are a *definition* change
mutating zero rows of any user table; `019` reserves *user-data mutation*, which this is not.
`CONTRACT.md:399` gives the owning `backend-N` authorship AND apply of "structure/schema/privilege/
definition changes." Derived from the contract first, then found independently confirmed by the
ticket's own Executor section ("Not CEO-reserved — confirmed by `cto`"). No authorization batch needed.

**Next:** Standing by. Not claimed, not owned, nothing implemented. Blockers to clear before an
execution wake: (1) `unverified-jira` needs a fresh Jira observation; (2) AC2/AC3 need `po` to
reconcile them with the overturn; (3) a `backend-N` PEER reviewer must be evidenced — not
`frontend-8` (Mafdet), however closely paired.

---

## 2026-09-10 — Preflight KAN-179 + KAN-183 (assess only; no claim, no apply, no containment)

**Saa (`backend-8`).** Read-only against `wtncuzcskpigqpmnxwws`. No DDL/DML/grant/`apply_migration`.
`set_session_user` never called. All negatives carry positive controls.

### KAN-179 — scope question answered with evidence, not assumption

- **`rpc_get_friends` has TWO overloads**, not one: `()` oid 101016 (correctly guarded, `auth.uid()`
  only) and `(p_user_id uuid DEFAULT NULL)` oid 101061 (the bypass). The brief described one.
- **`public.rpc_get_friends()` is `42725 function ... is not unique`** — a no-arg call resolves to
  neither. Proven live. The safe overload is unreachable by name.
- Positive control: explicit `rpc_get_friends(NULL::uuid)` → `P0001 User not authenticated`,
  `PL/pgSQL function rpc_get_friends(uuid) line 10 at RAISE`. Discriminator fires.
- **Class sweep across all of `public`**: exactly 2 functions take a caller-supplied authorization
  subject (`COALESCE(param, auth.uid())` or `DEFAULT auth.uid()`) — and they are exactly the
  KAN-179 pair. **The two-function scope is correct and now measured.**
- 16 functions reference the missing `friendships` (counted via `pg_class`/`pg_proc`, = 0 relations).
  14 of 16 already derive the subject from `auth.uid()`. Only `rpc_get_friend_suggestions` is
  SECURITY DEFINER with **no** `auth.uid()` reference at all.
- **Neither `rpc_get_friends` overload is called by the app.** `getFriends()` at
  `lib/data/repositories/friends_repository_impl.dart:410` routes around them by comment
  ("broken/overloaded rpc_get_friends"). `getFriendSuggestions()` (:552) calls suggestions with
  `{'p_limit'}` only — omitting `p_user_id`, the one case where `DEFAULT auth.uid()` does apply.
- `v_circle` — the view `getFriends()` falls back to — **is also MISSING**. Friends is dead at
  every layer.
- **AC3 does NOT need a Supabase branch.** The guard raises at line 10, before `friendships` is
  touched (P0001, not 42P01). Auth logic is provable in production without fabricating anything.

### KAN-183 — AC1's configuration half is ANSWERED, and unfavourably

- `pg_stat_activity`: `application_name='postgrest'`, `usename='authenticator'`, **2 connections,
  oldest 13 days, both idle between requests**. PostgREST holds **persistent direct sessions**.
  No transaction-mode pgbouncer in front of it (`pgbouncer` usename appears only for Storage API).
  **AC2's "transaction-mode confirmed → close with containment" branch does not apply.**
- `pgrst.db_pre_request`: **NONE** configured. One arming path ruled out.
- `auth.uid()` = `coalesce(legacy 'request.jwt.claim.sub', 'request.jwt.claims'->>'sub')` — the
  plural GUC `set_session_user` writes IS a poisoning input.
- **Blast radius is larger than the ticket names**: 5 additional anon-executable SECURITY DEFINER
  **writing** admin RPCs derive identity straight from `request.jwt.claims->>'sub'` —
  `rpc_admin_approve_venue_submission`, `_reject_`, `_return_`, `rpc_admin_revoke_venue`,
  `rpc_admin_revoke_venue_submission`.
- **A correctly-built twin already exists**: `debug_assume_user(uuid,text)` uses
  `set_config(..., true)` (transaction scope) **and** is not anon-executable. It is the fix shape.
- **AC4 containment is answerable now**: `proacl` = `{=X/postgres,postgres=X,service_role=X}`;
  `anon` is **not named** but `has_function_privilege('anon',...)` = **true** via the bare
  `PUBLIC =X`. Control: `pg_read_file` = false, so the probe discriminates.
- **`pg_default_acl` still grants `anon=X` on FUNCTIONS in `public`** (grantors `postgres` and
  `supabase_admin`). KAN-67's revoke did not cover functions. A `DROP`+`CREATE` re-grants `anon`
  by name — so for KAN-183 a bare `DROP` beats a recreate.
- **A safe, zero-DDL, zero-write probe finishes AC1**: `public.jwt_claims()` is STABLE,
  SECURITY INVOKER, anon-executable, and returns `current_setting('request.jwt.claims', true)`.
  One anonymous `POST /rest/v1/rpc/jwt_claims` settles whether PostgREST populates the GUC on an
  anonymous request. No HTTP exploit and no production poisoning required.

### Claimability — both UNCLAIMABLE, correctly

`store.read('task', …)`: both records have `surfaces: null` (**`surfaces-unassessed`**) and no
`work_effort` (**`missing-work-effort`**). `ownership: null`. Jira status `To Do` (10004) on both.
Assessed values reported to `team-lead`; **not written** — the brief said assess only, so the
mutation is left as a decision for the caller.

**Next:** Standing by. Nothing claimed, nothing applied, nothing contained. Route is PEER for both
(schema work); reviewer must be a `backend-N`, never `frontend-8` (Mafdet).

---

## 2026-09-10 — KAN-177 PEER REVIEW (reviewer, not executor): **PASS**

Independent same-capability review of `backend-5`'s applied venue-authz repair. Read-only against
`wtncuzcskpigqpmnxwws`. Nothing accepted from comment 10917 or the dispatch summary; every claim
re-derived. Verdict comment **10920**.

### The overturn I was asked to test hardest — UPHELD, by a method backend-5 did not use

`cto` T-074's sixth member (`trgfn_organiser_profile_persona_guard`) is a **false positive**.
Rather than re-running backend-5's two catalogue sweeps, I went to the **origin record**:
`supabase/migrations/20260829080500_baseline_schema.sql` carries **exactly five**
`join public.organiser_profiles op` sites — lines **3616 / 3793 / 3861 / 3896 / 4307**, enclosed by
`can_create_venue_booking` / `can_edit_venue_details` / `can_manage_venue` /
`can_manage_venue_members` / `can_view_venue_bookings`. The sixth's only occurrence is line
**19152**, the `RAISE EXCEPTION` string. **The family was five from origin.** Live confirmation:
full `pg_get_functiondef` sweep (`prokind in ('f','p')`, all non-system schemas) returns one row;
its only `FROM` is `public.profiles`; direct probe returns `0A000`, never `42P01`.

**No seventh.** One union sweep over views/matviews, policies, constraint *definitions*, index
definitions, column defaults, triggers and rules: only five **index names** carrying the old
prefix, every one defined `ON public.organiser`. Names are rename residue, not references — which
also corroborates the rename premise without relying on anyone's account of it.

### What I re-derived rather than accepted

- **AC3 rebuilt from scratch** with my own anchor (organiser `2c7f8be0…`, user `3305873a…`,
  `is_admin=false`, zero `venue_admin` grants; the single `role_grants` row is a *different* user
  holding `admin`, so every `true` had to come through the repaired join). Per-role staging in a
  `DO` aborted by `RAISE EXCEPTION`. Matched backend-5 exactly, **plus a row it did not test**:
  role `organiser` — the column DEFAULT — correctly denies all five.
- **Join key genuinely discriminated**: I staged `organiser_profile_id = organiser.id`; a repair
  joining `organiser.profile_id` would have returned false everywhere. It matched.
- **Every probe observed failing** (no-row baseline, control venue) — no probe here is one nobody
  has seen fail (`T-055`).
- **Rollback genuine**: `organiser_venues` 0 (`max(created_at)` NULL), `organiser` 11, `venues` 389,
  `profiles` 165. `019` never engaged.
- **Scope held**: `venues.relacl` and `venue_members.relacl` both `anon=rm/authenticated=rm` — no
  `a`/`w`/`d`. Writes still fail closed at `42501`. No `GRANT` added, correctly.

### Where I refused to overclaim

`proacl` **byte-identity pre/post is not re-derivable post-apply** — the pre-state is gone. I said
so rather than repeating it as verified. What supports it: all 174 lines of the migration are five
`CREATE OR REPLACE` with no `DROP`, `CREATE OR REPLACE` cannot alter `proacl`, and the surviving
ACL carries no seat-specific grant beyond the default shape.

### New finding — raised, not folded in

**All five repaired functions are `anon`-executable and now ANSWER instead of erroring.** Verified:
`SET LOCAL ROLE anon` → `current_user=anon` → clean `false` from three of them, no denial. They are
`SECURITY DEFINER` with `row_security=off`; `proacl` grants EXECUTE to `PUBLIC` *and* `anon` by
name. That is an **authorisation oracle** over any `(user_id, venue_id)` pair — inert only because
`organiser_venues` has 0 rows, i.e. exactly the state this repair prepares to leave. **Not a
KAN-177 defect**: the grant is inherited from baseline and AC4 forbids touching it. Raised for `po`
as follow-up. Did **not** test whether PostgREST exposes them at `/rest/v1/rpc/`; did not assert it.

This is the same `pg_default_acl` / `PUBLIC =X` mechanism I measured on KAN-179/183 — the earlier
entry above records that KAN-67's revoke never covered FUNCTIONS in `public`. Same root, third
ticket to surface it.

### Both record defects in my brief were already fixed

Checked, not assumed. `surfaces` now names the real migration file (`po`, 17:47:07Z), and the
summary/description now state FIVE.

### Lifecycle — my transition, as review owner

`open_review_context` (rev 11, waiting) → `resolve_review_owner` = `backend-8`, evidence comment
10920 (rev 12) → `record_review_result` **pass** (rev 13). `queue.completion_reasons` → **`[]`**.
Jira transition **`41`** → status **`10007` Done** (transition id read back live; `10045` is a
*status* id, not a transition). `observe_lifecycle('10007')` → rev 14, canonical `done`.

**Ownership NOT released — and that is correct, not an omission.** `ownership.seat_id` is
`backend-5`. `store.release` as `backend-8` refuses: `not-owner: KAN-177 is owned by backend-5, not
backend-8`. Only the owner releases, or a named `ceo`/`orchestrator` authority. I hold neither and
did not borrow one. **`backend-5` must release**, which is also what writes its `executor_evidence`
— currently absent from the record.

**Next:** Standing by. Nothing claimed, nothing applied.

---

## 2026-09-11 — T-077 Am.2 `search_tsv` null-tolerance (repo-only assessment)

Requested by `team-lead`. **Assessment, not execution** — no ticket claimed, no migration
written, nothing applied. Supabase MCP was disconnected for this task, so repo-only was
forced as well as instructed (`T-068`: repo is authoritative for nothing about live state).

### cto's open item: CLOSED — the four `search_tsv` triggers are null-tolerant

All four are unscoped `BEFORE INSERT OR UPDATE ... FOR EACH ROW`, so cto's premise is right:
they *do* fire on the erasure UPDATE. But none of the four bodies references
`creator_profile_id`/`owner_profile_id`, and every text input is `coalesce(...,'')`-guarded, so
no NULL reaches `to_tsvector`/`unaccent`/`||`. No exception, no silently-blanked index.
`search_tsv` is plain nullable `tsvector` on all four tables — **zero** `NOT NULL` and zero
`CHECK` hits repo-wide — so even a NULL result would store without error.

### But two harder blockers sit on the same UPDATE, and they are not search_tsv

1. **`games.creator_profile_id` and `meetups.creator_profile_id` are declared `NOT NULL`**
   (baseline 22867, 23086). `ON DELETE SET NULL` against a `NOT NULL` column raises 23502.
   `squads.owner_profile_id`/`owner_user_id` likewise (24611-24612).
2. **`trg_squads_owner_defaults` re-populates the column the erasure nulls** — pure `COALESCE`
   chain, so it is null-*tolerant* but not null-*preserving*: it silently undoes the SET NULL,
   or re-points at the row being deleted. Quiet failure, the class team-lead asked me to watch for.

`trgfn_games_set_host_user`'s `P0001` fires on this path too — column-scoped to exactly
`UPDATE OF creator_profile_id` — confirming cto's existing finding rather than adding to it.

**Did not fix any of it.** cto's binding rule ships fixes in the same migration as the DDL, and
that migration is blocked on a CEO permission. Reported to `team-lead`.

**Scope note:** brief bounded me to 3-4 bodies; I read 6. The two extra were the only triggers
that actually dereference the nulled column, so stopping at 4 would have returned a clean
answer to a narrow question while missing the blockers. Flagged as expansion, not absorbed.

**Also outstanding from 2026-09-10:** the `create_system_post` / `process_notification_event`
anon-caller sweep completed; result was reported to `team-lead` in-session. Both **ANON CALLER:
NO**; `process_notification_event` has 19 real internal callers and `authenticated` is
load-bearing via `trg_circle_join_notify` (SECURITY INVOKER on `circle_members`).

**Next:** Standing by. Nothing claimed, nothing applied.

## 2026-09-11 — Eight-ticket Preflight batch (KAN-170/185/186/187/188/189/191/194)

Requested by `team-lead` under CEO BACKLOG BURN-DOWN MODE. **Preflight only, repo-only, no
execution.** Supabase MCP token expired for the whole task, so `T-068` applied as a hard
constraint as well as an instruction: nothing below is a live-state claim. The Atlassian MCP
under `atlassian` was also expired; ticket bodies were read through the `claude_ai_Atlassian_Rovo`
server instead. No ticket claimed, no transition, no Jira write, no migration authored, no
function body restated (`T-058`).

### Sized

| Ticket | Work Effort | Boundary that sets it |
|---|---|---|
| KAN-170 | 1 | re-size after Am.3 narrowing; supersede-comment + one new SET NULL FK |
| KAN-185 | 1 | single column default; the implementer's-call branch is pre-settled offline |
| KAN-186 | **2** (backend-3 said S) | AC3/AC4 live erasure demo cannot be authored until the DDL lands |
| KAN-187 | 1 | one message string, one `CREATE OR REPLACE` from live `pg_get_functiondef` |
| KAN-188 | 1 | pure `REVOKE`, no body restatement |
| KAN-189 | 1 | one `ALTER DEFAULT PRIVILEGES` |
| KAN-191 | **floor 4, no ceiling** | unsizable until `KAN-190` resolves `games`' step (1) |
| KAN-194 | 2 | AC4's CI-gate assertion direction is only knowable after AC1's live read |

### Findings that change how these tickets should be run

1. **KAN-170 AC2 has a real answer and it is not "no interaction".** `trg_games_set_host` is
   column-scoped — `BEFORE INSERT OR UPDATE OF creator_profile_id` (baseline:29860). An UPDATE
   that sets only `creator_user_id` (which is exactly what KAN-170's FK `SET NULL` issues) does
   not fire it, so KAN-191's guard cannot re-derive over it. Had it been unscoped, the trigger
   would have overwritten the `SET NULL` back to `uid` and aborted the deletion with 23503.
   The answer rests entirely on `pg_trigger.tgattr`, which KAN-191 already owes on reconnect.
2. **`KAN-190` blocks KAN-191 but has no `BLOCKS` edge.** Only `dep-6dcbdbfa` (`KAN-192` →
   `KAN-191`) exists in Persistent State. The `KAN-190` block is prose on the ticket only.
3. **KAN-186's "backend-3 preflighted it fully (Work Effort S)" is not in Persistent State** —
   `surfaces`, `work_effort` and `characteristics` are all null on `KAN-186.json`, so it is
   `surfaces-unassessed` and unclaimable regardless of permission.
4. **KAN-189 as written would violate `T-045`** if the live read finds a `supabase_admin`
   grantor. KAN-194 carries the role-split guard; KAN-189 does not.
5. **KAN-188 needs no `docs/SCHEMA.md` edit to keep CI green.** `anon_function_grants_diff.sh`
   is one-directional (`comm -23`, :193): a signature leaving the flagged set is a stale
   allowlist entry, not a failure. All five ARE currently listed (`docs/SCHEMA.md`:723-730).
6. **KAN-185's "remove the default" branch is safe** — the only repo-visible `profiles` insert
   path, `rpc_onboard_profile`, names `country` in its INSERT column list (baseline:14280),
   so it never reads the default and the column is nullable. Also: `profiles_country_fkey` is
   `NOT VALID` (baseline:31263), which exempts existing rows but **not** new inserts, so the
   defect stands.

Reported all eight to `team-lead` in one message. **Nothing claimed, nothing applied.**

## 2026-09-11 — KAN-186 sitting 1: authored in full, APPLY DENIED, production untouched

Claimed to me by `team-lead` (`ownership.claim_ref` `burn-down-2026-09-11`, `claimed_at`
07:40:24Z) with Supabase re-authorized against `wtncuzcskpigqpmnxwws` and the execution gate
passing. **`apply_migration` was refused by the Claude Code permission classifier.** So was the
Jira transition `Ready` → `Back-end` (transition `5`, read back live per `G-018`). The ticket
therefore still reads `Ready` while being actively worked, which is a board inaccuracy I could
not correct myself.

### What I did not do

**I did not re-route the DDL through `execute_sql`.** That tool would have run all 13 statements
— its own description says to use `apply_migration` for DDL. Doing so would have bypassed the
denial rather than respected it, and would have left the remote migration ledger with no record
of a schema change: the exact `T-068` divergence this board has spent two weeks cleaning up.

### AC1 — satisfied, derived live, not copied from the ticket

`confrelid = 'public.profiles'::regclass AND contype='f' AND confdeltype IN ('a','r')` → **20**
constraints (51 FKs reference `profiles` in total). Seven excluded **by constraint name**, which
matters because `squads` carries three and `challenges` two, so no table-level filter can express
the exclusion: `challenges_owner_profile_id_fkey`, `fk_challenges_owner_profile`,
`games_creator_profile_id_fkey`, `meetups_owner_profile_id_fkey`, `squads_created_by_profile_fkey`,
`squads_owner_profile_fkey`, `squads_owner_profile_id_fkey`. **20 − 7 = 13**, across the 12
DELETE-group tables — `posts` contributes two. My repo pre-derivation at Preflight had predicted
exactly this set; the live read confirmed it rather than being replaced by it.

### The landmine is a population of exactly one, and it is confirmed

`posts_author_user_profile_fkey` — `confupdtype = 'r'`, where all other 12 are `'a'`:

```
FOREIGN KEY (author_user_id, author_profile_id) REFERENCES profiles(user_id, id)
  ON UPDATE RESTRICT ON DELETE RESTRICT
```

Postgres cannot `ALTER` an FK's `ON DELETE` action in place — `ALTER CONSTRAINT` reaches only
deferrability — so `DROP`+`ADD` is forced, and `DROP` discards **every** attribute, not just the
one being changed. Every one of the 13 replacements is transcribed from its own live
`pg_get_constraintdef`, with `ON UPDATE RESTRICT` restated verbatim on that one.

### The authored file asserts its own correctness rather than describing it

`supabase/migrations/kan186_profile_fk_cascade_part_a.sql`, **uncommitted, no version prefix**
(`T-068` step 5 — a guessed timestamp is indistinguishable at a glance from a real ledger
version, which is the trap `KAN-170`'s file had to disclaim in prose).

- **Pre-check** aborts the transaction unless all 13 are still in their authored state *and* the
  blocking set is still exactly 20 — a constraint appearing between census and apply fails loudly
  instead of being silently skipped — and unless `uq_profiles_user_id_id` still exists, without
  which the composite FK could be dropped but not recreated.
- **Post-check** asserts, in the same transaction, all 13 at `confdeltype='c'` with `confupdtype`
  unchanged and `convalidated`, the 7 Part-B constraints still present and still `RESTRICT`
  (AC5 asserted, not promised), and exactly 7 blocking FKs remaining.

Neither check can pass by reading the file. A partial result rolls back.

### Sitting 2 not attempted, and not attemptable

ACs 3 and 4 need a real blocked account to complete `delete_my_account()` — production user-data
deletion, CEO-only under `019`, not granted — and are not authorable until the DDL lands. AC6
cannot be satisfied at all: no version string was returned, so there is nothing to name the file
after. Stated on the ticket rather than left to be noticed.

### Persistent State

`surfaces` recorded from the live census (rev 7; `team-lead` had already set the same path at
claim time — I re-recorded it with a `basis_ref` that cites measurement rather than anticipation).
Then asserted `schema_change: true` (rev 8), which was **absent** — with no characteristics the
policy had derived **no `validation_route` at all**, so this ticket would have reached review with
no route. It now derives `peer`, which is what my schema work always is. I asserted the fact; the
policy chose the route.

### Found live, belongs to neighbours, no ticket created

- `meetups_owner_profile_id_fkey` sits on column **`creator_profile_id`**, not `owner_profile_id`.
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
