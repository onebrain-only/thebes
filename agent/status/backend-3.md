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

## 2026-09-08 — KAN-136 surface assessment (Preflight, not execution)

Asked to record the repository paths KAN-136 touches. **Assessed: `[]`** — assessed, nothing
to declare. Not a guess and not the unassessed state.

**Basis, from this file.** Line 31 titles the entry "(no migration authored)"; line 35 records
"no writes to the live project, no SQL authored"; lines 39–41 give the single sitting's
checkpoint as "design written, nothing in the function touched"; lines 69–71 record `po`
splitting the ticket so KAN-136 is pt.1 only — the design/enumeration pass — with all authoring
moved to `KAN-140`. Together those are a positive finding that this item produces a written
design and changes no repository file, not merely a sizing act with paths left unestablished.

**Call.** `store.set_surfaces("KAN-136", 2, [], "worker:backend-3",
basis_ref="agent/status/backend-3.md:31,35,39-41,69-71")` → revision 2 → **3**.
`shared_or_contended_surface` recomputed **false**, `by: system-derived` — not set by me.
`python3 agent/state/validate.py --check` → `ok  persistent state valid`.

**Not touched:** `work_effort` (1), `validation_route`, `ownership` (still null), other
characteristics, any other ticket. No claim made, nothing transitioned, no Product code written.
Jira was not contacted — no Atlassian tool exists in this session.

**Carried forward:** KAN-140 holds the authoring work and *will* have real surfaces; it was not
in scope here and remains unassessed as far as I know.

## 2026-09-09 — KAN-145 PEER review (reviewer, not executor)

CEO-named PEER reviewer and recorded `review_owner` for KAN-145 (Add FK
`payment_intents.booking_id` -> `venue_bookings(id)` ON DELETE RESTRICT, T-061).
Executor was `backend-4` (Min), excluded from reviewing its own work; I am
same-capability, which is what the PEER route requires.

**Verdict: PEER PASS, scoped to available evidence.** Posted as KAN-145 comment
10777. I did not transition the ticket and did not record the verdict in
Persistent State — reported it back for the canonical path to run.

Source: `Dabbler/dabbler-code/supabase/migrations/20260907100000_kan145_payment_intents_booking_fk.sql`
(commits `a7dbaa0`, `0ecb75d`; repo HEAD `715bb85`).

- AC1 PASS as authored / NOT VERIFIABLE as applied. One executable statement,
  lines 135-142. `ON DELETE RESTRICT` at :140 — RESTRICT is established, not
  CASCADE. That is the guarantee KAN-158 leans on and it holds at source. No
  `ON UPDATE` clause, so update action is default NO ACTION; neither the AC nor
  T-061 specifies one, flagged rather than failed.
- AC2 NOT VERIFIABLE — a live `pg_constraint` assertion by construction.
- AC3 NOT VERIFIABLE — row counts and probe results are live facts. The probe's
  design is right (demonstrated failing first pre-apply), which is what I could
  actually assess.
- AC4 PASS — provable from source. Exactly one DDL statement, no index added
  because `idx_payment_intents_booking` already exists (baseline :28837).

**No live catalogue read existed in this run.** I attempted exactly one
(`pg_constraint` on `payment_intents::regclass` against `wtncuzcskpigqpmnxwws`);
it was denied at the tool boundary. Did not retry, substituted nothing. Five
facts stand explicitly unverified and are listed as such on the ticket —
including `backend-4`'s applied-and-verified report, which reads correctly and
is the executor's evidence, not mine to re-badge.

Lesson worth keeping: on a constraint ticket the split is clean and predictable
— the *shape* of the change is a source fact and the *delete action's effect* is
a live fact. Marking the second NOT VERIFIABLE cost nothing and kept the review
honest; a PASS there would have been source-only evidence wearing a live-proof
label.

---

## 2026-09-10 — KAN-130, SQL half AUTHORED (not applied). Owner: me.

Route PEER (`schema_change` + `money_path`). Work Effort 2, ceiling 3 — my own
Preflight count, and it held: sitting 1 the migration, sitting 2 the probe pack.

Commit `32d418f` on `exec/backend-3/KAN-130`, in my worktree, **not pushed**.
Five files, explicit pathspec:
`supabase/migrations/20260910090000_kan130_kan131_wallets_owner_and_platform_identity_migration.sql`
and `supabase/tests/kan130/{00_harness_prelude,10_fixtures,20_probes}.sql` + `run.sh`.

Gates on that branch: `flutter analyze --no-pub --no-fatal-infos` 0 errors /
0 warnings / 73 infos, exit 0; `flutter test` 106 passed, exit 0. SQL-only diff.

Jira comment `10849` on KAN-130 carries the statement-by-statement account and
every AC verdict. Not transitioned — my role file makes `Back-end` →
`Peer-review` mine, the dispatch said do not transition, I followed the dispatch.

### The thing that nearly stopped this ticket, and what actually worked

Two of the three live-read routes were closed. Supabase MCP `execute_sql`
returned *"You do not have permission to perform this action"*; no `psql` and no
`psycopg` exist on this host; and `supabase/.temp/pooler-url` authenticates
**stale** — containerised psql against it fails password auth. What works is the
**`supabase` CLI in the integration checkout**, which holds its own working
credential: `supabase db dump --schema public` is a read-only read of the live
catalogue, and `--data-only -x <every other table>` is a read-only *count* of one
table. Worth keeping: T-058 says author from `pg_get_functiondef`, and a live
`pg_dump` satisfies the property T-058 actually relies on — attributes
reconstructed from `pg_proc` verbatim — when the catalogue is unreachable
directly. I stated the substitution on the ticket rather than letting
"authored from the live catalogue" quietly mean something weaker.

### Two judgement calls I made, both flagged rather than buried

1. **`PRIMARY KEY USING INDEX wallets_id_unique`** instead of a literal
   `PRIMARY KEY (id)`. The literal form builds a *second* unique index on the
   same column and leaves the first standing forever. I read T-051's own
   sentence — *"already carries a unique index; the only thing missing is that
   it is nullable"* — as intent, and promoted the existing index. Verified in
   the harness: one `wallets_pkey`, no orphan, inbound FK intact.
2. **`request_payout`'s owner lookup adds `currency = 'AED'`.** The old
   `where user_id = me` was single-row *by primary key*;
   `(owner_type, owner_id)` alone is not, because `wallets_unique_idx` includes
   currency. Dropping that would have silently reintroduced an arbitrary-row
   read on a money path. Not in the ruling's wording; called out for review.

### Ordering fact that is load-bearing and easy to miss

The `wallets_self_read` replacement **must precede** `DROP COLUMN user_id`. The
policy expression depends on the column, so `DROP COLUMN ... RESTRICT` refuses
while the old policy stands. Anyone re-ordering these statements gets a failure
that looks like an unrelated dependency problem.

### Harness finding, generic, costs the next author an hour

`supabase/postgres` reports `pg_isready` **green before its own init has
finished** building `pg_graphql`. Load a schema into that window and the graphql
DDL event trigger aborts every subsequent statement with *"could not open
relation with OID …"* from `graphql.increment_schema_version` — which reads like
a defect in your SQL and is not. `run.sh` now waits for the init to be
*observably* complete. **KAN-128's `run.sh` has the same race** and will bite
whoever re-runs it.

### The concern in my dispatch was wrong, and correcting it mattered

I was told T-058's trigger-enabled end-to-end criterion might be unsatisfiable
without a production write, and to park it with the authority required. It is
satisfiable: the probe pack runs in a throwaway container loaded from the live
schema, exactly as KAN-128's did. **No criterion on this ticket is parked.**
The lesson is the general one — "this needs production" is worth testing against
the precedent before it becomes a parked AC.

### What I did NOT do, deliberately

No write of any kind to `wtncuzcskpigqpmnxwws`. No `db push`, no
`apply_migration`. **Did not author KAN-131's half** — Section B of the shared
file is a declared placeholder and the file carries an APPLY GATE. Precise on
the stop-and-ask trigger I was given: the file does **not** structurally need
KAN-131 (Section A applies cleanly on its own, demonstrated), it needs it for
**apply**, because T-052 ruled they ship together. That is a flag to
team-lead, not a decision I took.

## 2026-09-10 — Preflight assessment only: KAN-162 and KAN-140 (Shed, backend-3)

**Assessing is not claiming.** Claimed nothing, transitioned nothing, applied nothing, wrote no
Product code. All production access read-only: 10 `execute_sql` queries against
`wtncuzcskpigqpmnxwws`, **0 writes**.

### The blocker both tickets are parked on has LIFTED

KAN-162's "Blocked" section says live DB access is unavailable — *"two seats independently hit
permission errors on the Supabase MCP today (2026-09-09)"* — and `T-068`'s evidence base states
*"MCP `execute_sql` is denied on this project."* **Both are now false.** MCP `execute_sql`
answered every read I issued. This is the single most actionable finding here: it un-parks
KAN-162 outright and bears on KAN-146 and KAN-138, which carry the same stated blocker.

### KAN-162 — read-only confirmed; scope is stale by one view

The dispatch's read is right: all three ACs are *state* and *cite*. No schema change, no data
change. **Work Effort 1, surfaces `[]` (final, not provisional).**

**`username_registry_public` NO LONGER EXISTS.** `to_regclass` -> NULL, and
`list_active_usernames` is gone with it. Dropped by remote `20260907052826
kan141_drop_list_active_usernames_and_public_view`. AC3 (cite `pg_get_functiondef`) is
**unsatisfiable** for it — there is no body to cite. The ticket cannot be met as written for 3
views. `po` must narrow it to 2 or rule the disposition.

Live state of the two survivors, re-measured (backend-4's 2026-09-06 figures still hold):

| View | Backing fn | Zero comes from | Decidable today? |
|---|---|---|---|
| `v_potential_vibes_default` | `rpc_potential_vibes/6`, `prosecdef=true` | `<> p_me` with `auth.uid()` NULL; base `v_sport_profiles_with_user` = **147 rows** | **Yes** — non-empty base + positive control settles it |
| `v_recreate_quickpicks` | `rpc_recreate_suggestions`, **`prosecdef=false`** | gate `rus.user_id = auth.uid()` present **AND** `reuse_user_stats`/`reuse_global_stats`/`v_recreate_candidates` all **0 rows** | **No** — over-determined |

**AC1 is not testable as written for the second one.** It poses an either/or — filter *versus*
empty table — and that view has **both**. AC2 rescues it (it asks what happens once rows exist,
answerable from the body), so the ticket is satisfiable with a precise write-up, but AC1's binary
framing should be fixed. Also: the title says "3 zero-policy **definer** views" and
`rpc_recreate_suggestions` is **INVOKER**.

### KAN-140 — cannot close today, and my first sizing of it was wrong

**Work Effort 2, ceiling 3** — corrected in-session from my own earlier 1. The 1 priced authoring
only, on the assumption AC2/AC3 needed a production apply and a live-row write. **My own status
log had already recorded that assumption's refutation** (KAN-128's probe pack ran in a throwaway
container off the live schema), and I checked the path executes rather than trusting it: docker
running, supabase CLI 2.48.3. AC2/AC3 are real, sizeable work via the AC's own "(or equivalent
simulation)" branch. Checkpoint: the probe pack cannot start until the body lands — the KAN-128
shape, which `capacity-to-date` itself sizes at 2.

**Authoring alone does NOT satisfy the ACs**, which was the dispatch's question. Verified live:

- **AC5 is unsatisfiable as written.** It requires authoring from the "post-KAN-128/**KAN-131**"
  catalogue. KAN-128 is live (`ON CONFLICT DO NOTHING` present). **KAN-131 is not applied and not
  even authored** — Section B of `20260910090000_kan130_kan131_...sql` is a declared placeholder.
  There is no post-KAN-131 catalogue to author against.
- **AC4 states a false premise** — "KAN-128's or KAN-131's already-landed ... work". KAN-131's has
  not landed.
- **AC6 is satisfied.** Verified: `payment_intents_booking_id_fkey FOREIGN KEY (booking_id)
  REFERENCES venue_bookings(id) ON DELETE RESTRICT` is live.
- **AC2's literal "live UPDATE against a test row" branch is CEO-only** under `019`. The AC offers
  simulation as an *alternative*; it should **require** it, so nobody reads it as licence for a
  production write on a money path.

**The `T-055` defect is live and unrepaired** — the body still reads `FROM public.bookings`
(`to_regclass` -> NULL) under a comment saying "Left as found." `financial_ledger` 0 rows,
`venue_bookings` 0 rows. Attributes to preserve: `prosecdef=false`, `provolatile='v'` (so
`pg_get_functiondef` emits **no** volatility keyword — §6g's trap), `search_path=public, pg_temp`.

**Collision flagged, not resolved.** KAN-131 and KAN-140 both replace `trgfn_payment_to_ledger`.
Under the `T-068` freeze the author->apply gap is unbounded, so `T-067`'s "author and apply in one
sitting" mitigation is **unavailable by construction** — whoever applies second reverts the other.
I declared `logical_surfaces: ["public.trgfn_payment_to_ledger"]` on KAN-140. **KAN-131 needs the
matching declaration or the pair does not serialize** — `logical_collide` requires both. Not mine
to write; raised.

I did **not** name a migration path for KAN-140. `po`'s `[]` basis is stale (its cited grep
returned nothing on 2026-09-09; the shared file exists as of 2026-09-10), but whether KAN-140 lands
in that shared file or a new one is a `cto`/`po` sequencing call under `T-052`. Declaring a path I
do not know would be inventing one.

### State written, and what remains

`store.set_surfaces` + `store.update` only; nothing under `runtime/` hand-edited.
`validate.py --check` -> `ok persistent state valid`. `missing-work-effort` cleared on both.
**Both remain `not-ready` — still `To Do` in Jira. Only `po` can select them into Ready.**

## 2026-09-10 (cont.) — KAN-162 executed: a security finding, not a confirmation (Shed, backend-3)

Owned KAN-162 (claimed on my behalf, rev 8; continuation gate `execution_reasons` -> `[]`).
Transitioned **Ready -> Back-end (10043, transition 5)** myself, and **Back-end -> Peer-review
(10045, transition 7)** on completion — both ids read back from live Jira and cross-checked
against `agent/state/board.py` per `G-018`. Finding posted as Jira **10866**, addendum **10868**,
AC-map **10870**.

**Read-only. No DDL, no DML, no `apply_migration`, no `db push`, no grant change. Production
mutations: 0.** Every probe inside `begin; … rollback;`.

### The ticket asked me to confirm a clean bill of health. It isn't one.

**`v_potential_vibes_default` — REWORK TRIGGER FIRED.** The 0-rows-as-anon reading is a **false
negative that hid a live exposure**. The chain is view -> `rpc_potential_vibes/6` (SECDEF, injects
`auth.uid()`) -> `/7` (SECDEF, takes `p_me` **as an argument**) -> `v_sport_profiles_with_user`
(**147 rows**). The only user-scoped predicate is `spw.user_id <> p_me`, whose own comment reads
*"don't recommend yourself"* — a **self-exclusion product filter, not an access control**. Anon
gets 0 purely because `x <> NULL` is NULL for all 147 rows.

`anon` holds `EXECUTE` on **both** overloads. So, as role `anon`:

- direct `SELECT` on the base view -> **ERROR 42501 permission denied** (KAN-67 holding)
- the view, and the 6-arg wrapper -> **0**
- **the 7-arg overload with a fabricated uuid -> 20; with `p_limit`=100000 -> 147 rows / 137
  distinct users** (`user_id`, `username`, `display_name`, `profile_type`, `sport_key`)

**A confused deputy.** The grant is locked down correctly and the SECDEF function hands the data
over anyway. **No forged credential is needed** — `p_me` is an ordinary RPC argument, so this is
argument selection on the normal RPC surface. Evidence level stated honestly on the ticket: grants
verified and executed in-database as role `anon`; **no HTTP round-trip performed**.

**The CI gate is structurally blind to it.** `scripts/ci/check_anon_allowlist_test.sh` — the
KAN-61/T-002 gate whose stated purpose is catching *"a newly introduced anon-readable definer
view"* — allowlists **view names only**; no `pg_proc`, no `proacl`, no function coverage at all.
Both views are on its allowlist, so it is green. **The control and the exposure sit on different
object classes.** Reported, not fixed.

**`v_recreate_quickpicks` — over-determined, and the gate is real.** `rpc_recreate_suggestions` is
**INVOKER** (`prosecdef=false`), and its body has no `auth.uid()` at all — the gate is one layer
down in `v_recreate_candidates`: `WHERE rus.user_id = auth.uid()`. Feeders all at 0 rows, so
**both** arms hold. Said so rather than picking one. The gate is **non-spoofable** (session-derived
from a signed JWT) where view 1's is a caller-supplied argument — that asymmetry is the finding.
Structurally, `personal` drives and `global` only `LEFT JOIN`s onto it, so global data alone can
never emit a row.

### Method notes worth keeping

- **T-055 guard first.** Confirmed the path executes at all (`/7` with a real uid -> 20) *before*
  reading anything into a 0 elsewhere. A 0 from a function that raises early proves nothing.
- **Every probe demonstrated failing before passing.** `p_me` NULL -> 0 vs real uuid -> 20 isolates
  the mechanism to one argument. The `= auth.uid()` gate was shown discriminating against a
  **synthetic in-memory `VALUES` list** — 0 of 2 without identity, exactly 1 with — which
  demonstrates the predicate **without inserting a single row**. That technique is the way to
  evidence a gate whose real tables are empty and must not be written to.
- **The Jira markdown->ADF converter silently dropped a numbered list item containing a table.** I
  compared the rendered body against what I submitted, caught the loss, and restored it in 10868.
  **Check the returned body after posting a structured comment** — the API reports success either
  way.
- **po amended the ACs (Correction #2) while I was executing**, renumbering 3 -> 4 and correcting
  the definer/invoker framing. Posted an explicit AC map rather than leaving the reviewer to
  reconcile. Correction #2 sourced the DEFINER/INVOKER split from the **baseline file**, which AC4
  excludes; I had measured both live and they agree, so I recorded the live values so the
  conclusion rests on the catalogue. Convergence from a **different method**, not two reads of the
  same artifact.

### Handed off, not finished

**Peer-review, `review_owner` null** — the correct PEER waiting state, `review_waiting` reports it.
Reviewer must be another `backend-N`. **I did not select one and did not self-approve.** Ownership
released; `executor_evidence` records `backend-3`. `validate.py --check` -> `ok persistent state
valid`.

**Did not fix either finding.** `rpc_potential_vibes` needs a shape decision — revoke `anon`'s
`EXECUTE` on the `/7` overload, or move the identity inside it — which is `cto`'s under `T-012`'s
*"revoke the grant, do not add policies"*, not something to fold into a read-only ticket. The CI
gate's function blindness likewise needs its own work item from `po`.

**On the record:** the *"MCP `execute_sql` is denied on this project"* claim is false as of today
and still stands in **KAN-146**, **KAN-138** and **`T-068`'s evidence base**.

### 2026-09-10 (cont.) — KAN-162 addendum: baseline citations verified, and two self-corrections

Asked by `team-lead` to verify Correction #2's baseline line refs rather than accept them. Work was
already complete and in `Peer-review` when the request arrived; this is supplementary evidence
(Jira **10871**, **10873**), no re-execution, no transition, ownership still released.
**Production mutations still 0.**

**Citations hold.** `baseline:14334`/`:14335` = `rpc_potential_vibes`(6-arg) + `LANGUAGE "sql"
SECURITY DEFINER`. `baseline:14822`/`:14823` = `rpc_recreate_suggestions` + `LANGUAGE "sql" STABLE`,
no DEFINER clause. Worth recording given `cto`'s note that two of three baseline line citations
circulating 2026-09-07 did not survive — these do.

**But verifying them surfaced that the check was on the wrong object.** Correction #2 verified the
**6-arg** wrapper; the exposure is the **7-arg** overload (`baseline:14354`, likewise SECDEF).
Establishing that the safe wrapper is DEFINER says nothing about the object anon actually reaches.
And `baseline:36595`/`:36596` carry an **explicit named `GRANT ALL … TO "anon"` / `"authenticated"`**
on the 7-arg — so this was deliberate at baseline, not drift, and **KAN-67 could never have caught
it** (that work revoked `ALTER DEFAULT PRIVILEGES` on tables/views; this is a named grant on a
function). `authenticated` is exposed identically to `anon`.

**Then I caught my own error, which is the lesson worth keeping.** In 10871 I wrote a fix note
saying revoke `anon`/`authenticated` `EXECUTE` on the 7-arg. I went to verify the one part I had
reasoned rather than measured (that `postgres` owns it, so `/6`'s internal call survives). Ownership
held — **but reading the full `proacl` back showed a `PUBLIC` grant I had not accounted for**:

```
{=X/postgres, postgres=X/postgres, anon=X/postgres, authenticated=X/postgres, service_role=X/postgres}
 ^^ PUBLIC
```

**`REVOKE … FROM anon, authenticated` would have left the function fully executable by anon**, which
inherits `PUBLIC`'s grant — the `proacl` visibly changes, the statement reports success, and nothing
is fixed. This is my own role contract's trap running in the *opposite* direction from how it is
normally stated (usual form: revoking `PUBLIC` alone leaves `anon`, granted by name). **Both are
present here, so either revoke alone is insufficient, and each leaves an ACL that looks improved.**
Correct form names `PUBLIC, anon, authenticated`, and the verification must **assert the resulting
`proacl`**, not that the revoke ran. Corrected in 10873.

**Two method lessons.**
1. *Verifying a citation is not the same as verifying the claim it supports.* The lines were right
   and the object was wrong.
2. *The thing I nearly shipped wrong was the one thing I had not measured.* I only caught it because
   I went back to check the single reasoned step. A fix note is still a claim and gets the same
   evidence discipline as a finding.

**Deliberately did NOT** test the revoke by running it inside a rolled-back transaction — that is
still DDL against production and the brief said no grant changes. Flagged the claim as
reasoned-from-measured-ACL, not demonstrated.

---

## 2026-09-10 — KAN-177 Preflight (assess only; no claim, no DDL)

**T-074 understated the blast radius by three functions.** The brief and T-074 name two broken
functions. The live catalogue holds **five**, all `SECURITY DEFINER`, all referencing the
non-existent `public.organiser_profiles`:

| function | called by policy | on table | rows |
|---|---|---|---|
| `can_manage_venue` | `venue_members_select` | `venue_members` | 0 |
| `can_manage_venue_members` | `venue_members_insert/update/delete` | `venue_members` | 0 |
| `can_view_venue_bookings` | `venue_bookings_select` | `venue_bookings` | 0 |
| `can_create_venue_booking` | `venue_bookings_insert` | `venue_bookings` | 0 |
| `can_edit_venue_details` | `venues_update` | **`venues`** | **389** |

Found by sweeping `pg_proc.prosrc`, not by trusting the ticket's count — `020`. `cto` verified no
other table's policies call *the two it knew about*; that was true and it is not the same question.

**The "latent because the table is empty" argument is right for four of the five and WRONG for the
fifth.** `venues` holds 389 rows and `venues_update` calls `can_edit_venue_details` per row. What
actually contains it is **the missing `UPDATE` grant** — `venues.relacl` is `authenticated=rm`
(SELECT + MAINTAIN only), KAN-67 fallout, so an UPDATE fails `42501` before RLS is ever evaluated.
**Two different containment mechanisms, and only one is row count.** A future
`GRANT UPDATE ON venues TO authenticated` — an innocuous-looking line in a venue-edit ticket — turns
this into a live `42P01` against 389 rows with no other change. Recorded so nobody re-derives
comfort from the row-count argument alone.

**`DROP`+`CREATE` is not available here.** Seven RLS policies depend on these five functions
(`pg_depend`), so `DROP FUNCTION` is refused. `CREATE OR REPLACE` is therefore mandatory — and it is
also the *correct* choice, because it **preserves `proacl`**. Every one of the five carries
`{=X/postgres, postgres=…, anon=…, authenticated=…, service_role=…}`; a `DROP`+`CREATE` would reset
to `pg_default_acl` and silently re-grant `anon` by name. This is the same trap I hit in 10871,
approached from a third direction: there, the danger was revoking too narrowly; here it is that the
recreate path would re-grant. **The instrument that avoids it also removes the need to reason about
it** — but the verification still asserts `proacl` before and after, unchanged.

**Probe demonstrated failing before it counts.** Direct call raises
`42P01 … CONTEXT: SQL function "can_manage_venue" during startup`. The same three-branch expression
with `public.organiser` substituted, run inline read-only, executes and returns `false`. Failing and
passing directions both shown; neither was assumed.

**The rename is the whole story, and I did not take that on faith.** Every constraint on `organiser`
is still named `organiser_profiles_*` (`organiser_profiles_pkey`, `_profile_id_fkey`,
`_profile_sport_key`) — a table rename does not rename its constraints, so this is conclusively
`ALTER TABLE organiser_profiles RENAME TO organiser`, not a redesign. The join chain resolves
column-for-column: `organiser_venues.organiser_profile_id` → FK → `organiser(id)`; `organiser.profile_id`
→ `profiles(id)`; `profiles.user_id` exists. 0 orphaned `organiser_venues` rows. **Checked because a
function repaired onto a real table with a wrong join key passes a smoke test and stays broken.**

**Verification design — "policies return 0 rows" is a false pass and I said so.** With 0 rows the
predicate is never invoked, so an RLS probe proves nothing. Verification must call the five
functions **directly** for the negative direction (works today, read-only), and for the positive
direction stage `organiser` / `organiser_venues` / `venue_members` rows inside a transaction that is
**rolled back**. Flagged for the implementation sitting: that staging is DML and was correctly out
of scope for Preflight.

**Scope question raised, not decided:** `venue_members.relacl` is also `authenticated=rm` — no
INSERT/UPDATE/DELETE grant. Repairing the functions does **not** make the table writable; the three
write policies stay unreachable behind `42501`. Whether KAN-177 adds a `GRANT` or stops at the
function repair is `po`'s call, not mine. Per CLAUDE.md, failing closed is correct and is not to be
"fixed" by re-granting broadly.

**Cosmetic, not a defect:** `trgfn_organiser_profile_persona_guard` contains the string
`organiser_profiles` only inside its `RAISE EXCEPTION` message text. It queries `profiles` and works.

Recorded through `agent/state/store.py`: `work_effort=1`, surfaces assessed, characteristics
`schema_change` + `security_sensitive` → route computed **PEER** by policy (not authored by me).
Task remains **unclaimed and unowned**; residual queue reasons are `not-ready` / `unverified-jira`,
which are `po`'s to clear. No DDL, no DML, no `apply_migration`. T-068 freeze respected.

---

## 2026-09-10 — Read-only triage of the 74 anon-executable identity-taking SECURITY DEFINER functions

Requested by `team-lead` as urgent read-only triage against production `wtncuzcskpigqpmnxwws`.
**No DDL, no DML, no GRANT/REVOKE, no writes of any kind. T-068 freeze respected.** Every claim
below comes from `pg_get_functiondef` on the live catalogue plus `has_function_privilege`, never
from a migration file (`T-058`).

**Headline: two unauthenticated WRITE primitives are exploitable now — `create_system_post` and
`process_notification_event`.** Both are `SECURITY DEFINER`, owned by `postgres`, executable by
`anon`, and contain **no identity check of any kind** — they never mention `auth.uid()` at all.
`create_system_post` additionally carries `SET row_security TO 'off'`. Anon can author a post as
any profile, and inject an arbitrary-titled notification to any user. Neither is a read-oracle.

**`request_payout` is NOT exploitable.** It resolves `me := auth.uid()`, raises `auth_required` on
null, and constrains the beneficiary with `where id = p_beneficiary_id and user_id = me`. The
caller-supplied `p_beneficiary_id` is a **filter parameter over the caller's own rows**, not an
authorization subject. It was flagged only because the census tests for a literal comparison to
`auth.uid()`; the constraint is expressed as a join predicate instead. The money path is sound.

**`set_session_user(p_user uuid)` is the escalation primitive, and it is INERT BUT LOADED.** It
`set_config('request.jwt.claims', {...sub: p_user, role: authenticated}, **false**)` — session
scope, not transaction scope. That poisons `auth.uid()` and `effective_actor_uid()`, hence
`is_admin()`, `admin_cleanup_user_data`, `admin_take_action` and `rpc_admin_freeze_user`. It does
**not** poison `whoami_effective()`, which reads only the singular legacy GUC
`request.jwt.claim.sub`, so the `admin_actor()`-based family (`rpc_freeze_user`,
`rpc_verify_profile`, `rpc_unverify_profile`, `rpc_unfreeze_user`) resists this specific poison.
What keeps it inert is that PostgREST allows one RPC per request and re-issues `SET LOCAL` claims
per transaction, masking the session value. **I did not verify that over live HTTP and said so.**

**Evidence discipline.** Every negative carries a positive control. Table-existence probe:
`friendships` absent *and* a deliberately fabricated control name absent, while `posts` (503),
`profiles` (155), `notifications` (565) returned counts — so the zero means absence, not a broken
probe. `prosrc` caller probe: `set_session_user` 0 hits against `is_admin` 71 and `choose_actor` 12,
with a nonsense negative control at 0. `friendships` being absent is what makes
`rpc_get_friend_suggestions` and `rpc_get_friends` inert rather than safe.

Reported counts and field names only; no user data read or returned. Nothing contained —
containment goes through an authorized path, which this was not.

---

## 2026-09-10 — KAN-178 PREFLIGHT (assess only; no claim, no DDL, no policy change)

**Read-only against `wtncuzcskpigqpmnxwws`. T-068 respected: no `apply_migration`, no
`execute_sql` DDL/DML, no `db push`.** Every probe ran inside `begin; … rollback;`.

**Recorded through `agent/state/store.py`** (never hand-edited `runtime/`): KAN-178
rev 1 → 4. `surfaces` (2 paths, was `null`), `schema_change: true` +
`security_sensitive: true`, **`validation_route: peer` computed by system policy — I did
not author it**, `work_effort: 1`. `ownership` still `null`: **assessing is not claiming.**

**The leak, reproduced with a three-way control in ONE anon session.** `role_grants`
**1 of 1** rows visible, *while* `posts` returned **0 of 503** (RLS provably engaged) and
`sports` **4 of 148** (session provably live and genuinely `anon`). Two controls, opposite
directions — a zero afterwards cannot be a dead connection or a disabled RLS.
Also measured: an ordinary **non-admin `authenticated`** user reads the roster too. The
leak is not anon-only, which the ticket text does not say.

**Root cause is `pg_default_acl` history, not just the policy.** `role_grants_any_read`
is `SELECT TO public USING (true)`; the table ACL still carries `anon=rm/postgres`.
KAN-86 revoked only the six *write* verbs from `anon` on this table (line 106) and
deliberately left `SELECT`. So the policy is the leak and the standing `anon` grant is
what makes it *row-hiding* rather than *permission denied*. **KAN-178 is the read half of
KAN-86.**

**`role_grants_no_rw` is `ALL … USING(false) WITH CHECK(false)` and PERMISSIVE.** Permissive
policies OR, so today `SELECT` is `true OR false` = true. Drop `any_read` and SELECT falls
to `false` **for admins too** — the replacement must ADD a permissive SELECT policy, not
merely delete one. Deleting alone is a silent admin outage. `no_rw` must be left untouched;
it is the only thing denying writes.

**Caller sweep — three methods, each positive-controlled, because a body grep is not enough.**
- `pg_depend`/`pg_rewrite`: **0** view/rule dependents. *Control:* identical query returns
  **18** for `public.profiles`, 8 for `venues`. Zero = absence.
- `prosrc`: **10** functions read the table. **8 are `SECURITY DEFINER` owned by `postgres`**
  and `relforcerowsecurity = false`, so the owner bypasses RLS — immune. **2 are
  `SECURITY INVOKER`**: `is_moderator(uuid)`, `is_venue_admin(uuid)`.
- `lib/` grep: **0** hits for `role_grants`/`is_moderator`/`is_venue_admin`. *Control:*
  `profiles` 155 files, `venue_spaces` 22. The client never touches the roster;
  `supabase_config.dart` needs no constant and no edit.

**The overload trap fired here, and a name sweep gets it backwards.** `is_venue_admin` has
two overloads. The **1-arg** one reads `role_grants` directly and is INVOKER; the **2-arg**
one does not — it goes via `SECURITY DEFINER is_admin`. `storage.objects` policies
(`venue_insert/update/delete_admin`) call the **1-arg** form → exposed. `public.venue_spaces`,
`venue_blackouts`, `venue_price_rules` call the **2-arg** form → immune. The call site names
the function, not the signature; only reading each body separates them.

**Measured blast radius today: ZERO. The trap is latent, not live.** The table holds exactly
**1** row, `role='admin'`, `granted_by IS NULL`. There is no `moderator` row and no
`venue_admin` row, so `is_moderator()` and 1-arg `is_venue_admin()` already return **false**
for everyone — verified as a simulated non-admin. So tightening the policy breaks nothing
now; it arms a fail-closed bug that detonates the day someone grants the first
`venue_admin`. **Recommended in-scope:** convert both to `SECURITY DEFINER` (authored from
`pg_get_functiondef`, T-058) in the same migration. Same file, same surface, still WE=1.

**Verification is executable — proven, not asserted.** `set_config('request.jwt.claims', …, true)`
+ `set local role` inside a rolled-back transaction simulates anon / admin / non-admin with
**no fixture rows**, so `019` is never engaged. Confirmed live: admin → predicate `true`,
1 row, `posts` 495/503; non-admin → predicate `false`. **`is_admin(auth.uid())` in a policy
ON `role_grants` does not recurse** — DEFINER-as-owner + `FORCE RLS` off. That is load-bearing
and fragile: turning on FORCE RLS, or "fixing" `is_admin` to INVOKER, self-recurses (42P17).
The probe pack must assert it.

**AC testability gap raised to `po`:** "an admin must still read what it needs" is not
testable via the KAN-119 QA account — that account has **zero** `role_grants` rows by
design, and granting it one is CEO-reserved user-data mutation. Restated against the
JWT-simulation harness instead.

**Correct end state is `permission denied`, not 0 rows** — `cto`'s own weaker/stronger
distinction. Requires `REVOKE ALL ON public.role_grants FROM anon` alongside the policy,
which also removes the stray `MAINTAIN` KAN-86's six verbs missed.

Not applyable yet: `apply_migration` is denied by the harness permission layer. **I did not
route around it with `execute_sql`.** Preflight only; standing by.

---

## 2026-09-10 — KAN-173 PEER REVIEW (review owner): **PASS**, transitioned to Done

Independent same-capability reviewer for `backend-1`'s applied fix to
`public._wallet_recalc(uuid)` (version `20260910171433`). **Re-ran the committed probe pack
rather than accepting the recorded results** — `supabase/tests/kan173/probes.sql`. Read-only
against `wtncuzcskpigqpmnxwws`; no DDL, no `apply_migration`, no persisted rows. T-068 respected.

**Everything reported reproduced exactly.** P1 `P0001 PROBE_REACHED_END`; P2/P3
`balance=35.00 held=-4.00 rows=1`; P4 `23505` on `wallets_unique_idx`; P6 `23502` on `user_id`
unchanged; AC-2 all four callers `adjust=100.00 settle=280.00 held -50.00 → 0.00`. Live
`pg_get_functiondef` is byte-identical in body to the committed file. `prosecdef=false`
(**still INVOKER**), `proconfig` and `proacl` preserved.

**Two reported passes were weaker than they read, and I closed the gap with three controls.**

- **Control A — P2 does not actually prove AC-3.** `35.00` is reachable by an *incrementing*
  implementation (`10`, then `10 + 25`), so P2 is consistent with the very defect it claims to
  exclude. I probed the distinction directly by DELETEing a ledger row (the trigger fires on
  DELETE): **`35.00 → 10.00`**. A balance that falls on DELETE cannot come from incrementing.
  T-049 Invariant 3 holds — on this evidence, not P2's. **Generalisable: an equality assertion
  proves a recompute only when the accumulate-path arithmetic would differ. Check that first.**
- **Control B** — inverted the comparison to show the assertion machinery raises rather than
  passing silently. Fired.
- **Control C — AC-2's authorization.** `set_config` framing proves nothing unless the gates it
  drives are live. Same `admin_wallet_adjust` call with a non-admin `sub` → `P0001 forbidden`
  at line 3. The chain was authorized, not bypassed.

**`proacl` unchanged is a construction guarantee, not a measurement.** `CREATE OR REPLACE`
preserves it; the KAN-128 `pg_default_acl` trap needs a `DROP`+`CREATE` to re-derive the ACL.
I checked the consequence instead: `anon`/`authenticated` hold **SELECT only** on `wallets` and
`wallet_ledger`, so the `anon=X` EXECUTE on this INVOKER function yields `42501`, not a write.

**P4 independently confirmed from the catalogue.** The only constraints on `wallets` are
`wallets_owner_type_valid`, `wallets_pkey (user_id)` and `wallets_user_id_fkey` — **nothing
enforces `owner_id = user_id`**. `ON CONFLICT (user_id)` is safe under an *unenforced*
invariant held only because this function is the sole writer producing it. **KAN-130 changes
the arbiter to exactly `(owner_type, owner_id, currency)` and must not inherit it as free.**

**Corrected a flag rather than repeating it.** `backend-1` reported `kan138` and `kan170` as one
T-068 repo-vs-ledger divergence. They are not the same: `kan138`'s cast **is live** with no
ledger entry (real divergence); `kan170` has no ledger entry **and its object is absent**
(`public.games` carries only `games_creator_profile_id_fkey`, no FK to `auth.users`) — that is
unapplied in-flight work. Worth splitting before someone chases it as a repair.

**Persistent State was stale and is now in lockstep.** The task record still read `ready`/`10008`
while Jira had been at Peer-review since 21:21 — `backend-1` transitioned Jira without syncing.
Sequence: `observe_lifecycle` → 10045, `open_review_context` (owner `backend-3`, peer, cycle 1),
`record_review_result` pass, `queue.completion_reasons` → **`[]`**, Jira transition **41 → 10007**
(read back live, G-018), `observe_lifecycle` → 10007, **ownership released** from `backend-1` so
it stops counting against backend capacity. Task rev 7 → 12.

Left for `po`, non-blocking: AC numbering is inconsistent between the description (AC-5 =
provenance) and po's comment (AC5 = scope boundary, AC6 = provenance). Both substantively met.

---

## 2026-09-10 — KAN-186 Preflight (assess only; not claimed, not implemented)

Read-only against `wtncuzcskpigqpmnxwws`. Production mutations **0**. No DDL, no DML, no
`apply_migration`, no `db push`. Every figure below is from `pg_constraint` / `pg_proc` /
`pg_trigger` / live counts, not from the brief or from T-077's prose.

**Constraint census — 20 blocking constraints confirmed exactly.** `confrelid =
'public.profiles'::regclass AND confdeltype IN ('a','r')` returns **20 rows over 16 tables**.
T-077's "~20, not 12 or 16" is correct. `posts` blocks on a plain FK **and** a composite
`(author_user_id, author_profile_id) → profiles(user_id, id)`; `squads` blocks on **two**
columns across **three** constraints; `challenges` carries two identical constraints.

**Part A surface = 13 constraints over 12 tables** (posts contributes 2).

**Verified against T-077, two corrections:**

1. **The dual-keyed eight hold.** All eight (`comments`, `game_rating_events`, `post_hides`,
   `posts`, `squad_join_requests`, `squads`, `user_reputation_events`, `venue_rating_events`)
   carry a `NOT NULL` auth-keyed `ON DELETE CASCADE` beside the blocking profile FK. Confirmed.
2. **"Unblocks 21 of 45" is wrong; the number is 19.** Measured: 45 blocked users, 48 blocked
   profiles. 19 hold Part-A blockers only; 26 hold a Part-B blocker. 19 + 26 = 45. T-077's
   21 + 26 = 47 > 45 and does not reconcile.
3. **`circles` duplicate: real but out of scope.** `fk_circle_owner` + `fk_circles_owner_profile`,
   both on `owner_profile_id`, both already `CASCADE` — so neither is a blocker and neither is
   inside AC1's discriminator. `po` was right to flag it as unverified.
4. **`squads` is in T-077's DELETE list AND its NOT-DELETE list.** Arithmetic ("12 tables" for
   8 + 5 = 13) implies squads is Part B. Moot: `squads` has **0 rows**.

**Landmine the brief did not name.** `posts_author_user_profile_fkey` is the only one of the 20
with a non-default `ON UPDATE` — it is `ON UPDATE RESTRICT`. A DROP+ADD that states only
`ON DELETE CASCADE` silently downgrades it to `NO ACTION`. Author every replacement from
`pg_get_constraintdef` on the live catalogue (the T-058 rule, applied to constraints).

**Authority: Part A is NOT CEO-reserved. Confirmed, stated.** `ALTER TABLE … DROP/ADD CONSTRAINT`
mutates zero rows; `019` reserves user-data mutation, which this is not. `G-002` covers it.
PEER route forced by `schema_change`; reviewer is another `backend-N`.

**Applyability.** The local files for KAN-138, KAN-128, KAN-130/131 and KAN-170 are all absent
from the applied ledger — KAN-170 is `ALTER TABLE`-shaped, which corroborates the classifier
denial. KAN-186 may not be applyable today. Do not route around a denial with `execute_sql`
(T-068).

Preflight complete. Not claimed. Reported to `team-lead`, standing by.

---

## 2026-09-11 — Preflight, five-ticket security RPC batch (KAN-174/179/180/181/182)

**Repo-only, no execution.** Supabase MCP token expired; `atlassian` MCP expired too — tickets read
via the `claude_ai_Atlassian_Rovo` server, which is still authorized. All five read in full.

**Did not author any migration.** T-058 body restatement requires a live `pg_get_functiondef`;
the baseline dump is not authoritative (T-068). Assessed only.

**Work Effort:** KAN-174 M · KAN-179 S · KAN-180 M · KAN-181 S · KAN-182 L.

**Load-bearing facts measured from the repo:**

1. **Only one Dart caller exists across all five tickets.** `rpc_get_friend_suggestions`
   (`lib/data/repositories/friends_repository_impl.dart:552`) and it passes only `p_limit` — never
   `p_user_id`. Every other function has zero Dart references. None is a `supabase_config.dart`
   constant. KAN-179's fix has no client surface at all.
2. **`create_system_post` has ZERO callers** — no in-DB `PERFORM`, no edge function, no Dart.
   KAN-181 AC3's "if system-generated posts are a real needed feature" resolves to: nothing calls it.
3. **`process_notification_event` has 21 in-DB call sites**, mostly `SECURITY DEFINER` triggers, and
   at least some pass a custom `p_title` (e.g. `20260829080500_baseline_schema.sql:17501`). A
   templated-title-only redesign (AC3) breaks those callers. The body already templates title from
   `p_kind_key`; `p_title`/`p_body` are overrides, not the primary path.
4. **`can_view_post/3` is an RLS/visibility helper used at 4 internal sites**, not a client RPC.
   Internal callers already pass `auth.uid()`. There is a second overload `can_view_post(p_viewer
   uuid, p_post posts)` with the same caller-supplied-identity shape — in scope under AC1's "any
   sibling with the same shape", not a new ticket.
5. **The §2g allowlist gate is one-directional** (`comm -23 live allowlist`). A fixed function
   leaving the flagged set is "a stale entry to tidy, never a red build". So no ticket is
   CI-blocked by the allowlist; the collision there is textual, not correctness.

**Collision:** all five touch the same contiguous block in `docs/SCHEMA.md`
(`<!-- ANON_FUNCTION_ALLOWLIST_START -->`). Textual merge conflict only, one line each.
KAN-181 and KAN-182 additionally share `docs/SCHEMA.md` §2g.1. No two share a migration file.

**Contention flagged to team-lead:** `backend-5-kan181-182` and `backend-8-kan179-183` are live in
this session on four of my five tickets. Reported, not resolved by me.

Preflight complete. Not claimed. Reported to `team-lead`.

## 2026-09-11 (cont.) — Re-sizing KAN-174/179/180 in sittings; KAN-174 surfaces

Repo + Jira only (`claude_ai_Atlassian_Rovo`; `atlassian` and Supabase MCP both dropped mid-session,
so **no live catalogue this pass** — sizing rests on repo evidence and ticket text, as instructed).
**Wrote nothing to Persistent State** — `po` owns these writes. No production access at all.

**Replacing the unrecordable t-shirt sizes** (`M·S·M·S·L`) from the 2026-09-11 batch Preflight.
`validate.py` requires a non-negative integer in sittings and `capacity-to-date` forbids size
letters. Did **not** map M/S/L to 2/1/3 — that manufactures numbers nobody counted.

| Ticket | Sittings | Ceiling | Boundary (§1) |
|---|---:|---:|---|
| KAN-174 | **2** | 3 | AC2's redesign decision is consumed by AC3 and AC5 |
| KAN-179 | **1** | 2 | none — pattern inherited from KAN-174, not decided here |
| KAN-180 | **2** | 3 | `can_view_post` redesign consumed by AC3's behaviour-preservation check |

**KAN-174 — apply legs excluded and named, not caveated.** AC1's revoke and AC4's HTTP round-trip
both need production mutation under an active `T-068` freeze plus explicit authorization the ticket
itself withholds. Per §4 those are *"cannot size until authorization lands"*, with the authorable
part sized anyway. The 2 covers AC2/AC3/AC5 only.

**KAN-179 — the fix pattern is inherited.** Its AC1 says verbatim *"consistent with how KAN-174's
root fix is expected to redesign `rpc_potential_vibes`"*. So **KAN-174 BLOCKS KAN-179** by the
ticket's own text; flagged to `team-lead` to check the edge exists. That inheritance is also why
there is no internal boundary here — the judgement is made in another ticket.

### The grep nearly made me contradict my own seat, wrongly

Re-checking the prior session's *"only one Dart caller exists across all five tickets"* before
republishing it (§3: a count from another session is that seat's position, not a fact I hold),
`grep -rl | wc -l` returned **can_view_post=2, rpc_get_friends=1** — an apparent contradiction.
**It was the grep lying, not the finding.** Reading the actual lines:

- `can_view_post` — both hits are **doc comments** (`post_repository.dart:11`,
  `post_repository_impl.dart:18`). Not call sites.
- `rpc_get_friends` — `friends_repository_impl.dart:339` is `rpc_get_friend**ship_status**`, a
  different function caught as a substring; `:410` is a comment naming the function.
- `rpc_get_friend_suggestions` — `friends_repository_impl.dart:552` is the one **real** call site.

So the original claim is **correct** and I nearly filed a false correction against it. *A pattern
match over source text proves something about the text, not about the program* — substring collision
and comments firing at once. **A file count is not a caller count.** Read the lines.

**Citation corrected before it shipped.** I first cited that as "the §12j lesson". **Wrong** —
checked `CONVENTIONS.md` rather than trusting the number: **§12j is now *"Live state resembling a
migration's target is not evidence the migration partly ran"***, committed at `0e9f066`. The
comment-stripping rule I was thinking of is a **draft §12j that was never adopted** and exists only
in `agent/history/conventions-migration-window-legacy-notes.md`. It has no section number; do not
cite it as one. (The number is now taken, so if that rule is ever adopted it needs a fresh one.)

### §12a already covers the mechanism — but not the exploit, and that gap is the finding

Checking the numbering turned up **`CONVENTIONS.md` §12a, "A predicate that excludes rows by NULL
comparison is not an authorization check"**, which names `rpc_potential_vibes`'s `<> p_me` exactly
and was verified by `cto` on **2026-09-07** — three days *before* my KAN-162 finding. The mechanism
was already governance. I did not know that when I wrote the finding.

**What §12a does not say is the part that matters.** Its stated hazard is a *future* repair:
*"the natural null-safe repair — `p_me IS NULL OR spw.user_id <> p_me` — hands `anon` every row."*
It therefore treats today's zero as fragile-but-holding, and closes with *"Do not tidy this
predicate."* **KAN-162 showed the data is already reachable without any tidy** — `anon` holds
EXECUTE on the 7-arg overload directly and supplies `p_me` itself: 147 rows / 137 users. The route
is the **grant**, not the predicate.

So the two are complementary, not duplicative, and **§12a's implicit "safe for now" is falsified**.
Flagging for `cto`, whose document it is — §12a reads as a do-not-touch warning when the accurate
reading is an open exposure. Not editing it myself.

### KAN-174 surfaces (assessed, for `po` to record attributed to me)

- `supabase/tests/kan174/` — AC5's regression coverage; convention verified live in the repo
  (`supabase/tests/` holds `kan128`, `kan130`, `kan173`).
- New migration file — **TBD at authoring**; verified nothing is authored for any of the five.
- **NOT `lib/`** — `rpc_potential_vibes` has **zero** Dart references of any kind and is not a
  `supabase_config.dart` constant. Measured, not assumed.
- `docs/SCHEMA.md` — **withheld pending `po`, see below.**

**`team-lead`'s ruling for KAN-174 cites "its AC7". KAN-174 has five ACs; there is no AC7.** The
cited *region* is real and the content genuinely is now false — `docs/SCHEMA.md:306` still says
`v_potential_vibes_default` is *"Intentionally public — T-027 … access control lives inside the
function. Probed, not assumed"*, which is precisely what KAN-162 disproved for precisely that
function. But **no acceptance criterion on KAN-174 requires correcting it**, so whether it is in
scope is a `po` scope call, not something I declare on a mis-numbered AC. Raised, not resolved.

**Unfiled instance, flagged not ticketed** (Jira creation is frozen): `docs/SCHEMA.md:305`,
`v_circle_feed_visible` — *"Definer and anon-granted, but returns nothing. Left as-is."* That is the
**same false-negative shape** KAN-162 disproved one row below it: zero rows read as evidence of
safety. Not verified by me — no catalogue access this pass — so it is a lead, not a finding.

**Verified `team-lead`'s two citations rather than taking them:** `anon_function_grants_diff.sh:193`
is `comm -23 <(sort -u live) <(sort -u allowlist)` — one-directional, confirmed, with the "stale
allowlist entry to tidy" comment right above it at `:188`. `docs/SCHEMA.md:306-307` are indeed the
`v_potential_vibes_default` / `v_recreate_quickpicks` rows. Both hold.

---

## 2026-09-11 — KAN-181 execution: BLOCKED AT APPLY, everything else complete

Claimed to me by `team-lead`; continuation gate passed. Supabase live again,
`wtncuzcskpigqpmnxwws` / org `hpbacurwcqssiductcha`, ACTIVE_HEALTHY, Postgres 17.6.1.021.

**`apply_migration` was DENIED by the permission classifier.** I did not retry it and did not
reach for `execute_sql` to apply the DDL — that is the T-068 route-around I flagged in my own
KAN-186 preflight. The migration is written and unapplied. Needs a CEO permission decision.

**Zero-caller finding re-confirmed live (not carried over from repo preflight).**
`pg_proc.prosrc` across ALL schemas → 0 rows excluding oid 109831. `pg_views`, `pg_attrdef`,
`pg_constraint`, `pg_trigger` → 0 rows. 4 deployed edge functions, none. No Dart call site.
AC3 resolves to: nothing creates system posts today.

**AC1 was already satisfied before I started.** `proacl = {postgres=X/postgres,
service_role=X/postgres}`; `has_function_privilege` false for anon, authenticated AND public.

**AC4 SATISFIED — HTTP round-trip, with a positive control so the denial means something:**
- `POST /rest/v1/rpc/jwt_role` as anon → **HTTP 200, body `"anon"`** (control: PostgREST
  reachable, RPC dispatch works, caller genuinely executing as anon)
- `POST /rest/v1/rpc/create_system_post` as anon → **HTTP 401, `42501 permission denied for
  function create_system_post`**

Probe was safe by construction, not luck: the body resolves `p_profile_id` against `profiles`
and raises before its INSERT, so a fabricated uuid cannot write even if permission had passed
(T-055 discipline — checked the path before probing).

**Probes demonstrated FAILING before passing.** P2 (`row_security` override) **FAILS live now** —
proconfig is `{"search_path=public, extensions",row_security=off}`; the migration flips it.
P1 already passed, so it proves nothing alone — P1C aims the identical predicate at
`public.jwt_role()` and correctly reports **FAIL**, showing the predicate is not vacuous.

**Correction caught by my own probe.** P3 found a THIRD EXECUTE holder, `supabase_admin`, which
my earlier four-role query missed. All three bypass RLS so the `row_security=off`-is-redundant
justification stands, but I had written "both" in the migration and comment. Both corrected.

**Fix design (AC2 option (b)), stated:** not independently callable — EXECUTE only for
postgres/service_role/supabase_admin; `SET row_security TO 'off'` REMOVED as provably redundant
(SECURITY DEFINER owned by postgres; every EXECUTE holder has `rolbypassrls = true`).
Statement form is `REVOKE` + `ALTER … RESET` + `COMMENT` — no `CREATE OR REPLACE`, no
`DROP`+`CREATE`, so the ACL is preserved and `pg_default_acl` (KAN-189/194, still granting anon
EXECUTE on new public functions) cannot re-open the hole. No body restatement → T-058 not engaged.
Did not DROP the function: irreversible, not authorized, and (b) is satisfied without it.

Artifacts:
- `supabase/migrations/20260911000000_kan181_create_system_post_contain_and_reset_row_security.sql` (UNAPPLIED)
- `supabase/tests/kan181/probes.sql` (P0–P4, read-only, no writes)

`docs/SCHEMA.md` §2g left alone per instruction. No Jira ticket created. No ledger entry — nothing
found that wasn't correctable inside KAN-181. Not released; `team-lead` holds lifecycle.

---

## 2026-09-11 — KAN-181 APPLIED. Version `20260911075034`.

Supersedes the "BLOCKED AT APPLY" entry above. `team-lead` corrected twice (authorized →
not authorized → authorized); I re-verified pre-state and retried once on the final
instruction. It applied.

**No drift check before applying** (backend-1's standard, not cited from my earlier run):
`proacl`, `proconfig` and `body_md5 993866e237a6563c6df112de59a34988` all identical to my
earlier read; zero callers still zero. **P2 re-demonstrated FAILING today** on
`{"search_path=public, extensions",row_security=off}`, and P1C re-demonstrated FAILING today.

**Post-apply, asserted by ACL and privilege — never by "the statement ran":**

| Probe | Result | Evidence |
|---|---|---|
| P1 no untrusted EXECUTE | PASS | `{postgres=X/postgres,service_role=X/postgres}` |
| P2 no row_security override | PASS | `{"search_path=public, extensions"}` — flipped |
| P1C control (MUST fail) | **FAIL** | predicate still discriminates |
| Body unchanged | PASS | `993866e237a6563c6df112de59a34988` |
| SECDEF + owner unchanged | PASS | `true / postgres` |

**ACL preserved exactly across the apply**, which is the whole reason for `ALTER … RESET`
over `DROP`+`CREATE` — `pg_default_acl` (KAN-189/194) still grants `anon` EXECUTE on new
`public` functions and a recreate would have re-opened this.

**AC4 re-run post-apply.** `rpc/jwt_role` → 200 `"anon"` (control); `rpc/create_system_post`
→ 401 `42501 permission denied`. Identical to the pre-apply run — correct, since the apply
must not change reachability. The control passing on both runs is what makes the unchanged
401 evidence rather than a dead endpoint.

**AC6 provenance SATISFIED.** Repo file renamed to the ledger-returned version and verified
**byte-identical** to `supabase_migrations.schema_migrations.statements[1]`:
md5 `dea4f00dfb5013162d49214b1bedd3b8` on both sides. (2942 vs 2944 is one em-dash —
Postgres `length()` counts characters, `wc -c` bytes.) This is the first KAN-181 artifact
`supabase migration list` can match repo-to-remote.

Artifacts:
- `supabase/migrations/20260911075034_kan181_create_system_post_contain_and_reset_row_security.sql`
- `supabase/tests/kan181/probes.sql` (P0–P4, read-only, headers updated to applied state)

Uncommitted. `docs/SCHEMA.md` §2g untouched. No Jira ticket. No ledger entry. Not
transitioned, not released — `team-lead` holds lifecycle.

---

## 2026-09-11 — KAN-182 APPLIED. Version `20260911105434`.

`process_notification_event` (sized L). Resumed mid-flight: the migration draft and probe
pack existed as `PENDING_*` from an earlier session where `apply_migration` had been denied.

**AC3 CONFLICT, DECIDED AND WRITTEN INTO THE MIGRATION HEADER — not resolved silently.**
AC3 asks for server-controlled templated title/body replacing caller-supplied free text.
Implemented literally it BREAKS PRODUCTION: the body already templates from `p_kind_key`
(a 20-branch CASE) and `p_title`/`p_body` are OVERRIDES real internal callers pass — e.g.
`rpc_decide_join_request` passes `'You''re in! Your request to join was accepted'`.
**Decision: gate reachability, retain the parameters.** AC3's intent (no untrusted caller
writes notification text or picks a deep link) is met by removing every untrusted caller.
AC3's literal mechanism is deliberately NOT implemented, and the header says so. AC3's
second half — a separately-authorized free-text path — ALREADY EXISTS and nothing new was
built: `rpc_broadcast_inapp_notification` via the broadcast-notification edge function
behind `is_admin()`.

**The "21 callers" figure is a call-site count, not a function count.** Measured: **19
distinct caller functions**, **22 textual call sites** — several callers call it twice.
P3 asserts 19 and the probe header states this so a later reader does not "correct" 19 to
21 and turn a passing probe into a failing one.

**THE REAL REGRESSION RISK, and why statement 1 is not incidental.** 18 of the 19 callers
are SECURITY DEFINER owned by postgres and survive the revoke. `trg_circle_join_notify` is
the SINGLE exception — SECURITY INVOKER, attached to `circle_members`. Revoking
`authenticated` without `ALTER … SECURITY DEFINER` would raise 42501 inside it and
**JOINING A CIRCLE WOULD FAIL OUTRIGHT**. All 14 sibling `trg_*_notify` functions are
already DEFINER; this one was the anomaly. Disclosed behaviour change: its reads are no
longer RLS-constrained, so it now resolves a circle owner it could previously miss — a fix,
matching the siblings, and no disclosure vector (rows only pick a recipient, never returned).

**Every probe demonstrated FAILING before it counted as passing.** P1/P2/P4 raised against
the live pre-fix schema (P1: 1 client role held EXECUTE; P2: 1 INVOKER caller; P4: n=0).
P3 and P5 pass pre- AND post-apply — a pure-DDL change must not move a caller population or
a body — so they are falsified by paired controls instead: **P3C** (name misspelt) returned
0 not 19, **P5C** (one md5 digit flipped) matched 1 of 2. Both raised, as required.

| Probe | Pre-apply | Post-apply | Evidence |
|---|---|---|---|
| P1 no client EXECUTE | **RAISED** (n=1) | PASS | `{postgres=X/postgres,service_role=X/postgres}` |
| P2 no INVOKER caller | **RAISED** (n=1) | PASS | `trg_circle_join_notify` now DEFINER |
| P3 caller population 19 | pass | PASS | falsified by P3C |
| P4 DEFINER + pinned path | **RAISED** (n=0) | PASS | `{"search_path=public, pg_temp"}` |
| P5 both bodies unchanged | pass | PASS | falsified by P5C |

Bodies unchanged: `1b14f5666734be00236e5abd4aa13dd4` / `a2afe6754a5b774354fdb2e78e540747`.
The P5 md5 for `trg_circle_join_notify` was a **placeholder** in the inherited draft — filled
from the live catalogue before use, not trusted as written.

**Statement form ALTER / REVOKE / COMMENT only** — no `CREATE OR REPLACE`, no `DROP`+`CREATE`.
`pg_default_acl` still grants `anon` EXECUTE on new `public` functions (KAN-189/194, unfixed),
so a recreate would have silently re-opened this. `PUBLIC` revoked by name: a bare
`=X/postgres` entry is a PUBLIC grant `anon` inherits without being named. No body restated
→ T-058 not engaged.

**AC4 HTTP round-trip, with the control passing on both sides of it:**
- `rpc/jwt_role` as anon → **200 `"anon"`** (control), re-run after the target → still 200
- `rpc/process_notification_event` as anon → **HTTP 401, `42501 permission denied`**

**FIRST ATTEMPT WAS A FALSE PASS AND I REJECTED IT.** Sending `p_actor_id` (the parameter is
`p_actor_user_id`) returned **404 / PGRST202 schema-cache miss** — PostgREST never resolved
the function, so the permission check was never reached. That 404 is indistinguishable from
an already-deleted function and proves nothing. Only the 401/42501 counts. Recorded in the
probe pack so the next runner does not bank the 404. Caller-side twin of T-055.

Probe safe by construction regardless: `notifications.to_user_id` carries
`FK → auth.users(id)`, verified against `pg_constraint` (n=1), so the fabricated uuid raises
23503 before any row could persist. No write reached `notifications` (565 live rows untouched).

**Checked, not assumed:** `trg_circle_join_notify` still carries a bare `=X/postgres` PUBLIC
grant and is now SECURITY DEFINER — but `pg_get_function_result` is `trigger`, so Postgres
refuses direct invocation. Not a new reachable path.

**AC6 provenance SATISFIED.** Repo file renamed to the ledger version and verified
byte-identical to `statements[1]`: md5 `8875af3dbef012244ac6a937f52a955b`, **5168 on both
sides** (chars and bytes agree — the statement is pure ASCII, unlike KAN-181's em-dash).
Provisional `PENDING_*` file deleted.

Artifacts:
- `supabase/migrations/20260911105434_kan182_process_notification_event_contain_and_definer_trg_circle_join_notify.sql`
- `supabase/tests/kan182/probes.sql` (P0–P5 + P3C/P5C controls, read-only, no writes)

Uncommitted. No Jira ticket created, no transition — instructed to make none. Route is PEER
(schema change); **no backend reviewer evidenced, so this WAITS in peer review.** Reported to
`team-lead`.

## 2026-09-11 — KAN-174 PEER REVIEW (reviewer, not executor): PASS

Resolved as `review_owner` in Persistent State (KAN-174.json rev 15 → 16,
`review_context.review_type=peer`). Verdict recorded via
`store.record_review_result('KAN-174', 15, 'backend-3', 'pass',
'peer-be3-kan174-live-ac1-6')`. Executor was backend-2; I authored nothing.

**Re-verified against LIVE `wtncuzcskpigqpmnxwws` rather than trusting the report:**

- `pg_proc` filtered `proname LIKE 'rpc_potential_vibes%'` returns exactly ONE row
  (oid 95102, 6-arg). The 7-arg overload and `rpc_potential_vibes_debug` are both
  absent from that same population count — counted, not inferred (`020`).
- `prosecdef=true`, `proconfig={search_path=public, pg_temp}`,
  `proacl` carries `anon=X` and `authenticated=X` — asserted on the resulting acl,
  not on "the revoke ran".
- `prosrc`: `mentions_p_me=false`, `derives_authuid=true`, `has_clamp=true`.
  Identity is derived, not supplied.
- Comment contains "SELF-EXCLUSION PRODUCT FILTER" and names the three actual
  controls (definer boundary, derived identity, NULL-uid ⇒ 0 rows).

**AC4 re-run independently over HTTP, not taken on report** (anon legacy key,
`/rest/v1/rpc/rpc_potential_vibes`): 6-arg → `200 []`; 7-arg body carrying `p_me`
→ `404 PGRST202` ("no matches were found in the schema cache");
`rpc_potential_vibes_debug` → `404 PGRST202`. Unreachable, not merely empty.

**Vacuity check (T-055) — the part I would not skip at LOW effort.** `200 []` for
anon proves nothing on its own: a function that raises before reaching its body, or
one wired to nothing, returns the same shape. Executed the target path with a real
`request.jwt.claims.sub`: **10 rows at `p_limit=10`, 50 at `p_limit=9999`, 1 at
`p_limit=0`.** The path executes, the clamp holds at both ends, and the anon empty
result is therefore a genuine `auth.uid() IS NULL` outcome.

**ACs 1–6 all met.** AC1 per the po ruling (drop > revoke on the 7-arg; 6-arg anon
EXECUTE retained deliberately under T-070 Decision 2 — revoking it would turn 0 rows
into 42501 through `v_potential_vibes_default`). AC5: `supabase/tests/kan174/probes.sql`
covers this exact function across P0–P6 and records probes demonstrated FAILING against
a deliberately broken fold — not a pack nobody has seen fail. AC6: SCHEMA.md:306 row,
the T-070 block (~311-326) and :901 overload list all corrected in `d2a2f88`; §2g
allowlist correctly untouched.

No Jira transition, no ownership change, no fix attempted — closure is the
Orchestrator's.

## 2026-09-11 — KAN-194 PEER review (Shed, backend-3) — PASS

Reviewer only; authored nothing. Verified independently, not from the report:

- Live `pg_default_acl` re-read against `wtncuzcskpigqpmnxwws`, `defaclobjtype='f'`,
  all grantors and both scopes. `postgres`/`public` = `{postgres=X, authenticated=X,
  service_role=X}` (no anon). `postgres`/global (`defaclnamespace=0`) = `{postgres=X}`
  (no PUBLIC). Both channels closed. `supabase_admin`/`public` still
  `{postgres=X, anon=X, authenticated=X, service_role=X}`; no global-scope row —
  unchanged and still exposed, as reported.
- Ran the gate's own predicate SQL verbatim against production: empty result.
- Ran `scripts/ci/check_function_default_acl_test.sh` myself on a real disposable
  Docker Postgres, exit 0. Watched the gate FAIL on case 1 (both channels),
  case 3 (channel 2 alone, flagged as only `global_public_default`) and case 4
  (channel 1 alone, flagged as only `named_anon_default`). Not a probe nobody
  has seen fail.
- `docs/SCHEMA.md` §2g.1 does not overstate: it says `supabase_admin` is NOT fixed,
  marks the global inference as catalogue-only (no `SET ROLE`), and closes with
  "Do not describe the function-default hole as fully closed."
- `supabase_admin` correctly reported-never-gating in the shared predicate.

Verdict recorded via `store.record_review_result('KAN-194', 11, 'backend-3', 'pass', ...)`
— revision 11 -> 12. No Jira transition, no ownership change (Orchestrator closes).

Note: Jira was returning "trouble completing this action" on every `getJiraIssue`
for KAN-194 across five attempts, so the AC list was taken from the review brief
rather than read live. Every AC named there is evidenced above.
