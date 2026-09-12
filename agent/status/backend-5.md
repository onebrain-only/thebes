# agent/status/junior-frontend-4a.md

**Owner:** `junior-frontend-4a` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

## 2026-09-06 — Skills audit of this seat (survey, from `team-lead`)

**What it was.** A read-only survey, not work. Three questions: do I agree with
`junior-frontend-3a`'s rule and its "fewer, not more" verdict; does money change it; what
do I need that exists nowhere. First entry in this file — this seat has never run a task.

**What I did.** Read `agent/roles/junior-frontend-4a.md`, listed `agent/skills/` (75 entries
including `AVAILABLE.md`, so **74 skills**), read `agent/skills/AVAILABLE.md`, read
`agent/status/junior-frontend-3a.md`, and then read the one write path that actually exists
in my slices end to end: `lib/features/rewards/controllers/check_in_controller.dart`,
`lib/data/repositories/check_in_repository_impl.dart`,
`lib/features/rewards/presentation/widgets/early_bird_check_in_modal.dart`.

**What I touched.** This file only. No `lib/`, no `test/`, no git, no Jira, no `flutter`
command. `CONTRACT.md` §4.1 bars this seat from Phase 0 and Phase 0 is live.

**What I decided.**
- Agreed with `3a` on the rule and on "fewer, not more". I add nothing to the reflex table.
- **The lead's premise does not reach me.** D4 Money is not in my write boundary. My role
  file gives me `lib/features/rewards/**` and `lib/features/admin/**` and says the two
  dormant Commerce screens in `lib/features/misc/` are unowned and not to be touched. A
  junior on money does not currently exist; the question is `senior-frontend-4`'s.
- **But the failure mode does reach me, through rewards.** `perform_check_in` writes a
  streak. Credited twice is invisible in exactly the way the lead described.
- **Measured answer:** the safety is real and it is **server-side, not in the pattern.**
  `check_in_repository_impl.dart:33` calls RPC `perform_check_in`, which returns
  `is_first_check_in_today` — the dedup is in the function. The client has no guard:
  `check_in_controller.dart:26` `performCheckIn` sets `AsyncValue.loading()` and awaits with
  no in-flight flag, and `early_bird_check_in_modal.dart:232` is a bare
  `onPressed: onCheckIn`. Two taps are two RPC calls. The server absorbs it. Nothing in the
  Dart says so.
- So "repeat the pattern" is safe **only where the write goes through a server function that
  dedups**, and a junior reading the call site cannot tell whether it does. That is the
  narrow answer, and it is a documentation gap, not a skill gap.

**Defect noted in passing, not fixed.** `'perform_check_in'` is a hardcoded RPC name at
`check_in_repository_impl.dart:34`. My own conventions section forbids that — RPC names live
in `lib/core/config/supabase_config.dart`, which is a `CONTRACT.md` §4 contended file and not
mine to enter. Flagged for `senior-frontend-4` / `po`, not acted on.

**What is blocked.** Nothing. Survey answered; no follow-up requested.

---

## 2026-09-06 — KAN-138 sized: 2 sittings, ceiling 3 (no migration authored)

**Task.** `team-lead-4` assigned KAN-138 to Team 5 and could not size it; asked for my own
sitting count and nothing else. No SQL authored, no writes to the live project, no `duedate`.

**Count: 2 sittings on `backend-5`, ceiling 3. Plus 1 hand-off (`cto` apply) and 1 gate (`po`).**

- **Sitting 1 — author.** `pg_get_functiondef('public.settle_game')` on the *post-KAN-128*
  catalogue, cast the `CASE` to `settlement_status`, ship as one `CREATE OR REPLACE` in `G-002`
  format. Signature unchanged, so no `DROP`, so AC 5's grant/`proacl` work does not trigger.
  Mechanical and fully enumerable — one expression. **Checkpoint: migration body complete and
  posted; appliable, reviewable, abandonable.**
- **Sitting 2 — AC 2 demonstration.** Fixture + probe showing `settle_game` reaching the
  `wallet_ledger` insert, with the pre-fix `42804` shown first (`T-058`/`T-055` falsifiability).
  **Cannot start until `cto` has applied sitting 1's migration** — that dependency is the
  boundary, and it is a hand-off as well as a checkpoint.

**Fixture is inside the count**, and it is the whole reason sitting 2 exists. Measured, not
assumed: `games` has **8** NOT NULL columns with no default (`creator_profile_id`,
`creator_user_id`, `start_at`, `end_at`, `capacity`, `sport_id`, `geo_location_id`, `area_id`),
four of them FKs needing their own rows; `game_settlements` FKs to `games(id)` and
`auth.users(id)`; and `settle_game` is `SECURITY DEFINER` calling `auth.uid()`, which is NULL
outside a request context and raises `auth_required` on line 1 — so the probe must set
`request.jwt.claims` or the whole demonstration tests nothing. **No `commission_rules` row is
needed** — `resolve_commission` returns zero rows and `settle_game` coalesces to `10.00`.

**Ceiling 3, and the risk it banks is named.** `_wallet_recalc` inserts into `wallets` without
`owner_id` (`NOT NULL`, no default) and is fired by `trg_wallet_ledger_recalc` AFTER INSERT on
`wallet_ledger` — verified first-hand. So a post-fix `settle_game(p_finalize=>true)` reaches the
credit insert and then aborts `23502` inside the trigger. That fix is `KAN-130`'s
(`T-058` Decision 4), not mine.

**The one thing I could not settle, routed rather than assumed** (`capacity-to-date` §4): does
AC 2's *"reaches the credit insert"* accept a demonstration with `trg_wallet_ledger_recalc`
disabled — the deviation `cto` already accepted at `T-058` Decision 3 — or does it require the
trigger enabled, which nothing can satisfy until `KAN-130` lands? **The count is 2 either way**;
what changes is whether sitting 2 is datable. Owner: `cto` (`po` if read as ticket wording).

**Verified myself** against the live catalogue: `game_settlements.status` is `settlement_status`
(`typtype='e'`); `text`→`settlement_status` casts in `pg_cast` = **0**;
`pg_typeof(case when true then 'settled' else 'pending' end)` = `text`; the `CASE` is still
present in the live `pg_get_functiondef` at offset 1723 of 2848; `idx_game_settlement_unique`
exists on `game_id`, so the `ON CONFLICT (game_id)` clause is *not* a second defect.

**Taken from the ticket, not re-derived:** that `KAN-128` touches `settle_game:17154` and that
`cto` applies it Wednesday 2026-09-09; that KAN-138 shares no function with `KAN-136`/`130`/`131`.

**Not verified:** `cto`'s apply slot; whether `Ready` holds anything else for Team 5.

**Reported to** `po`, copying `team-lead-4`. **No `duedate` set.**

## 2026-09-06 — KAN-138 count held by `po` on an identity check; the roster files are the defect

**What happened.** `po` declined to date `KAN-138` because "backend-5 (Heka)" does not resolve
on the roster it reads: it has one shared `senior-backend` (Shu) and finds `Heka` naming
`junior-frontend-4a`. It reported the same pattern on a `KAN-136` report from `backend-3` (Shed).
The content was not disputed. **`po`'s check was correct against the file it read.** That file
is stale, and the mismatch is a documentation defect, not a spawn defect.

**Measured, on disk:**

| Source | Says | Last commit |
|---|---|---|
| `.claude/agents/backend-5.md:3,44,63` | `backend-5` **Heka**, Backend Dev, Team 5, paired with Pakhet | `9321ee6` |
| `agent/roles/backend-5.md:32,51` | same | — |
| `.claude/agents/` listing | `backend-1..8`, `frontend-1..8`. **No `senior-backend.md`. No `junior-*.md`.** | — |
| `agent/AGENTS.md:49,215,481` | "`senior-backend` ← ONE, shared"; roster history stops at **v0.8, 2026-09-05** (30 seats, `senior-frontend-N` + `junior-frontend-Na/b`) | `abdeb89` |
| `agent/NAMING.csv:26` | `Junior Frontend 4a,هكا (Heka)` — **0 rows mention Team 5 or any `backend-N`** | `00cfa5a` |

So `agent/AGENTS.md` and `agent/NAMING.csv` were never updated for the 2026-09-06 restructure
that rebuilt `.claude/agents/` and `agent/roles/` into eight paired teams. `NAMING.csv:26` is
the precise source of `po`'s "Heka is junior-frontend-4a".

**Why it matters beyond me.** Any seat validating a developer identity against `AGENTS.md` or
`NAMING.csv` will correctly refuse **all sixteen** developer seats. Two refusals in one day
(`backend-5`, `backend-3`) are the first two instances, not the last. `po` routed it to `pm` as
a spawn-side problem; on this evidence it is not — the spawns match their definitions exactly.

**Not mine to fix.** Both files are governance documents. Reported to `po` with the evidence and
copied to `pm`, whose spawn-side investigation would otherwise look in the wrong place.

**KAN-138's count is unchanged and stands: 2 sittings, ceiling 3.** Nothing in the identity
question touches the arithmetic.

## 2026-09-06 — T-060 closes my open branch; sitting 2 is datable. Count unchanged.

**Ruling received** from `cto`: for KAN-138's AC 2 probe, leave `trg_wallet_ledger_recalc`
**enabled**. The `23502` from `_wallet_recalc` *is* the proof the credit insert was reached,
because an `AFTER INSERT … FOR EACH ROW` trigger cannot fire until the row is inserted. No
harness deviation. May claim "the credit insert is reached"; may not claim "settles end to end"
— that stays `KAN-130`'s criterion.

**This resolves the one question I declined to size past.** Sitting 2 is **datable** and carries
no `KAN-130` dependency. **Count unchanged: 2 sittings, ceiling 3**, plus one hand-off and one
gate — as `cto` also states.

**Re-derived the ruling's mechanism myself rather than accepting it** (it is the premise sitting
2's whole evidence rests on):

- `trg_wallet_ledger_recalc`: `tgenabled='O'`, `tgtype=29` → ROW-level, AFTER, on
  INSERT/UPDATE/DELETE. Fires post-insert. `cto`'s reasoning holds.
- `_wallet_after_ledger()` body is `perform public._wallet_recalc(coalesce(new.user_id,
  old.user_id)); return null;` — **no `EXCEPTION` block**, so the `23502` propagates uncaught
  rather than being swallowed into a misleading success.
- `wallets.owner_id` NOT NULL with no default: confirmed again (count 1).

**One probe-design consequence, carried into sitting 2.** `cto` requires the output to name the
function that raised. A bare SQLSTATE does not carry origin — `_wallet_recalc` is reached via
`_wallet_after_ledger`, two frames below `settle_game`. The probe must capture
`GET STACKED DIAGNOSTICS PG_EXCEPTION_CONTEXT` and print the frame stack, not just `SQLSTATE`.
Without that the probe cannot distinguish "raised after the insert, inside the trigger" from
"raised by `settle_game`'s own statement" — which is precisely the distinction AC 2 turns on.
Method detail, not a sizing change.

**Separately:** `team-lead-4` retracted the identity escalation in full, confirmed `backend-5`
is Heka against `agent/roles/`, and confirmed my `T-052`/`T-058` citation correction was right —
it had been citing `T-052` for the author-from-live-definitions rule all session. It also
withdrew its own standing claim that `settle_game` was a *live* double-credit path; `T-058`
rules it a dead one. No action owed by me.

## 2026-09-06 — KAN-138 dated by `po`; two corrections sent back

`po` retracted the identity hold and dated the ticket: **earliest 2026-09-11, `due_date`
2026-09-13**, off my 2-sitting/ceiling-3 count plus the hand-off and gate, gated on `cto`'s
Wednesday apply slot for `KAN-128`. Not my numbers to set and I did not set them.

**Two things sent back, both found by reading rather than inferred:**

1. **`po`'s ticket comment records my AC 2 branch as "unresolved and routed to `cto`". It is
   resolved** — `cto` ruled `T-060` after `po` drafted it (`DECISIONS.md:7387`): the probe runs
   with `trg_wallet_ledger_recalc` **enabled**, and the `23502` is itself the proof. Accurate
   when written, stale by the time it posted — the relay-decay shape `capacity-to-date` §3 names.
   Asked `po` to update the comment so the executor does not re-escalate a closed question.
2. **`T-060` is used twice in `DECISIONS.md`.** `:7387` is the `KAN-138` AC 2 ruling; `:7436` is
   a `lib/app/routes/` partition ruling, same date, same owner. A duplicate decision ID makes
   every future citation of "`T-060`" ambiguous, and both are already being cited. Reported to
   `po`; `DECISIONS.md` is not mine to renumber.

**Count unchanged and now fully unblocked in principle: 2 sittings, ceiling 3.** Still cannot
start until the `KAN-128` apply lands.

## 2026-09-06 — T-060 addendum accepted; flagged a wrong apply-owner in `cto`'s closing line

`cto` folded both my probe-design points into `T-060` as binding: `GET STACKED DIAGNOSTICS
PG_EXCEPTION_CONTEXT` with the frame stack printed is now the requirement rather than an
implementation choice, and showing the pre-fix `42804` failing first is binding too. It also
recorded the `_wallet_after_ledger` no-`EXCEPTION`-block finding as closing the one way the
evidence could have been hollow. Sizing not reopened: **2 sittings, ceiling 3.**

**One thing in that message is wrong and I did not accept it.** `cto` closed with *"Nothing
starts until KAN-128 is applied; `devops` ships that, not me."* `devops` cannot apply it.
`CONTRACT.md:242` is explicit: writing to Supabase project `wtncuzcskpigqpmnxwws` is
**"NOBODY except `cto`, under `G-002`'s conditions"** — no `apply_migration`, no DDL, for any
other seat, "however correct or urgent". `:236` says the same from the authoring side:
`senior-backend` **"authors only — it never applies to production (`019`/`G-002`: `cto` or the
CEO)."**

**Why I did not let it pass as a slip.** It is my hand-off owner, and `capacity-to-date` §2
input 3 rules that each leg is sized by the seat that executes it — so a wrong owner makes the
hand-off leg unsized rather than merely mislabelled. Worse, it is the shape that strands work:
`cto` believing `devops` applies and `devops` correctly refusing under `G-002` leaves KAN-128
sitting with both seats behaving properly. That is the four-correct-refusals failure
`capacity-to-date` §3 already recorded on this exact ticket chain.

Raised with `cto`. Not mine to rule and not mine to renumber.

## 2026-09-06 — apply-owner resolved: the hand-off is `cto`'s; KAN-138 sizing final

`cto` confirmed the KAN-128 apply is its own under `G-002`, not `devops`'s. `G-002` has **not**
been amended. So my hand-off leg has an owner who can legally perform it, and `po`'s and
`team-lead-4`'s dating against "`cto`'s Wednesday apply slot" was correct all along — no
calendar needed fixing, only the sentence.

**KAN-138, final:** 2 sittings on this seat, ceiling 3, one hand-off (`cto`, under `G-002` with
`G-006`'s claim-comment), one gate (`po`). Earliest 2026-09-11, `due_date` 2026-09-13, both set
by `po`. Recorded as a second addendum to `T-060`.

**The mechanism `cto` gave is worth more than the slip, and it is the third instance today.**
Its role file quotes a PO decision of **2026-08-27** routing production fixes to `devops` via
Canary; `G-002` is dated **2026-08-28** and narrows that prohibition from "no agent, ever" to
"no agent except `cto`". The role file is stale by one day and one decision — **and it is the
document the seat reads first.** It also conflates repo changes (which do ship via `devops`
and Canary) with direct Supabase writes (which do not, and have not since `G-002`).

**Same failure class as the two roster documents I reported earlier**, and now a pattern rather
than an anecdote:

| Document | Stale against | Consequence observed today |
|---|---|---|
| `agent/AGENTS.md` | 2026-09-06 restructure | `po` and `team-lead-4` refused two real developer seats |
| `agent/NAMING.csv` | same | supplied the specific wrong fact ("Heka is `junior-frontend-4a`") |
| `agent/roles/cto.md` | `G-002`, 2026-08-28 | `cto` misrouted its own exclusive authority to `devops` |

Common cause: a seat's own definition is authoritative *to that seat* and is not regenerated
when `DECISIONS.md` moves, so each seat's first read is its most stale source. Every one of the
three was caught by a peer reading the primary document, never by the seat itself. Passed to
`pm`, which already holds the roster half. `cto` escalated its own role file to the CEO rather
than editing a generated definition on an agent's say-so — correct, and I did not touch it.

**Nothing owed by me on KAN-138 until the `KAN-128` apply lands.**

---

## 2026-09-08 — KAN-138 surface assessment recorded: `[]` (Preflight, not execution)

**Task.** Assess and record the repository paths KAN-138 touches. Assessment only —
**no claim taken, no ownership gained** (`store.set_surfaces` docstring: "Assessing is not
claiming"). KAN-138's underlying work was not started, resumed or continued.

**Answer: `[]` — assessed, nothing to declare.** Not `null`, and not a guess.

**Basis, from my own sizing entry at `agent/status/backend-5.md:57-72`:** KAN-138 is one
`CREATE OR REPLACE FUNCTION public.settle_game` authored from `pg_get_functiondef` and applied
to the live Supabase project, plus a fixture/probe demonstrating AC 2. **Signature unchanged**,
so no `DROP`, so no grant/`proacl` work; no new or renamed RPC, so **no
`lib/core/config/supabase_config.dart` entry**; and the entry records "no migration authored,
no SQL authored, no writes to the live project". Neither sitting authors a repository file.
`policy.normalise_path` confirms surfaces are repo-relative paths (`dabbler-code/`,
`webapp/` prefixes stripped) — a live-catalogue function is not one, and this checkout has no
`supabase/` tree at all. **I did not invent a `supabase/migrations/…` path to make the item
claimable.**

**Call and result.**
`store.set_surfaces("KAN-138", 2, [], "worker:backend-5", basis_ref="agent/status/backend-5.md:57-72 …")`
→ **revision 2 → 3**, `surfaces: []`, and `shared_or_contended_surface` recomputed
**`false`** by `system-derived` (not asserted by me). `python3 agent/state/validate.py --check`
→ `ok persistent state valid`.

**Untouched, as instructed:** `work_effort` (2), `validation_route` (still unset),
`ownership` (`null`), `characteristics` beyond the system-derived recompute. No hand-edit under
`agent/state/runtime/`. No other ticket read or written.

**Contention observed: none.** An empty set collides with nothing under
`queue.surfaces_collide`.

**Still open, unchanged by this act:** the `cto` AC-2 question routed on 2026-09-06 (trigger
enabled or disabled for the demonstration) is untouched and is not a blocker on assessment.

---

## 2026-09-09 — KAN-150 PEER review (CEO-named reviewer, recorded `review_owner`)

**Verdict: PEER PASS, scoped to available evidence.** Posted as Jira comment **10778** on KAN-150.

**No live database access in this run.** No credentials, no psql. Every criterion whose proof is
the live catalogue is recorded **NOT VERIFIABLE** with its reason — not passed from the migration
file, not failed for absent evidence.

| Criterion | Verdict |
|---|---|
| AC1 branches + orphaned vars removed | PASS (source) — live body NOT VERIFIABLE |
| AC2 scope fenced to two functions/two branches | PASS (source) — catalogue-wide claim NOT VERIFIABLE |
| AC3 authored from `pg_get_functiondef` live | **NOT VERIFIABLE** (provenance corroborated, not proved) |
| AC4 `search_path` kept, no `SECURITY DEFINER` | PASS (file) — "matches live" NOT VERIFIABLE |
| AC5 behaviour preservation | PASS on the explicit-statement limb — probes NOT VERIFIABLE |
| cto ruling 10716 (dormant-not-abandoned body comment) | PASS |

**Method worth keeping.** AC1/AC2 were settled by a *normalised mechanical diff* of both baseline
bodies (`20260829080500_baseline_schema.sql` :3473-3532, :17187-17215) against both replacement
bodies, comments and quoting stripped — so "nothing else was touched" is computed, not impressed.
The stale dump is used only as a pre-image for the SHAPE of the edit, never as an authority on the
live body.

**Corroboration found without a database, and it is the useful part:** quiet hours are enforced
INLINE in the push trigger (baseline :18246-18275) and that trigger does **not** call
`should_bypass_quiet_hours` — so reducing it to `RETURN false` disarms nothing in the shipped
path. That reaches cto's zero-caller finding from a second direction, at source.

**Carried observations.** (1) `should_bypass_quiet_hours` constant-false — IN SCOPE, not a defect:
it is AC1's required outcome and cto ruled it at 10716. (2) `urgent` has no cap row — OUT OF SCOPE
(KAN-155's surface); recorded for `cto` with source basis: `notify_priority` is a four-value enum
while caps are three rows per plan. **Mine:** `p_priority notify_priority` is unqualified, so it
resolves against the applying session's `search_path` — fails loudly, never silently overloads; no
live consequence, named only so it is not reread as sloppiness.

**Not done, deliberately:** nothing fixed, no Product code touched, no commit, no push, no
transition, no write to `agent/state/runtime/**`, no verdict recorded. Reporting only.

## 2026-09-10 — KAN-162 PEER review: **PASS**, every claim independently reproduced

PEER reviewer for KAN-162 (authored by `backend-3`, Peer-review, `review_owner` null). Same
capability, so the route is legal. Read-only against `wtncuzcskpigqpmnxwws` throughout — every
probe inside `begin; … rollback;`. **Production mutations: 0.** No DDL, no DML, no grant change,
no `apply_migration`, no `db push`. T-068 freeze untouched. Did not transition the ticket.

**Verdict: PASS.** I retrieved my own evidence rather than accepting the finding, and every
factual claim in comments 10866/10868/10870/10871/10873 that I checked held.

| Claim | My independent measurement |
|---|---|
| `v_sport_profiles_with_user` = 147 rows | 147 |
| `<> p_me` filter, not empty table | `p_me` NULL → **0**; real uuid → **20**. Same fn, one arg apart |
| anon enumerates via the 7-arg overload | as role `anon`: **147 rows / 137 distinct users**, `p_limit`=100000 |
| anon denied on the base view | `ERROR 42501: permission denied for view v_sport_profiles_with_user` |
| 6-arg DEFINER / `rpc_recreate_suggestions` INVOKER | `prosecdef` = t, t, **f**. Owner `postgres` on both overloads |
| `PUBLIC` `=X` *and* named anon/authenticated grants | `{=X/postgres,postgres=X/…,anon=X/…,authenticated=X/…,service_role=X/…}` |
| `v_recreate_quickpicks` over-determined | gate `rus.user_id = auth.uid()` present in `v_recreate_candidates` **and** `reuse_user_stats`=0, `reuse_global_stats`=0 |
| `username_registry_public` gone | `to_regclass` → NULL; absent from `pg_class`; dropped by `20260907052826_kan141_drop_list_active_usernames_and_public_view` |
| baseline `:14334/14335`, `:14354/14355`, `:14822/14823`, `:36595/36596` | all four verified verbatim |

**Decisive differential.** In a simulated authenticated session (real `sub`, role
`authenticated`, rolled back): `v_potential_vibes_default` → **20**, `v_recreate_quickpicks` →
**0**. The probe *flips* for view 1 and *does not* for view 2 — which is precisely why view 1 is
decidable and view 2 is not. That is the ticket's whole question, answered by measurement.

**The error the ticket exists to prevent — `backend-3` did not commit it.** It never presents a
zero-row result as proof of gating, and it explicitly refuses to pick an arm on the
over-determined view. The `<> p_me` NULL-comparison is correctly named a self-exclusion product
filter rather than an access control.

**Five qualifications, none FAIL-worthy, all reported to the requester:**

1. **`CONVENTIONS.md` §12a already documents the NULL-comparison mechanism**, verified by `cto`
   2026-09-07, and the finding does not cite it. Not an error — but §12a frames the risk as
   *latent on repair* ("the natural null-safe repair … hands `anon` every row"). The genuinely
   new and serious delta is that the **7-arg overload is granted to `anon` directly, so no repair
   is needed — it is already open.** That delta should be stated against §12a, not presented flat.
2. **CI-gate citation names the wrong artifact.** `check_anon_allowlist_test.sh` is the offline
   self-test carrying a *fixture* allowlist; the gate is `check_anon_allowlist.sh` and the
   authoritative allowlist is `docs/SCHEMA.md` §2f. **Substance confirmed more strongly from the
   gate itself:** its SQL reads `WHERE c.relkind = 'v'` — view-class only, no `pg_proc`.
3. **"so it is green" is unmeasured.** The gate hard-exits 1 without `SUPABASE_DB_URL`, which its
   own header says was unprovisioned at KAN-61 landing. Structural conclusion survives either way.
4. **No HTTP round-trip** — `backend-3` flagged this honestly and I did not close it either. The
   PostgREST overload-resolution step is reasoned, not demonstrated. The one open gap.
5. **`docs/SCHEMA.md`:306-307 is now contradicted** — it records both views as "intentionally
   public, access control lives inside the function." The finding shows that control is bypassable
   via the sibling overload. Doc update is `po`/`cto`'s, not mine.

**Not done, deliberately:** no fix, no Product code, no commit, no transition, no write to
`agent/state/runtime/**`, no reviewer selection, no revoke tested even in a rolled-back
transaction. Reported to the requester only.

## 2026-09-10 — KAN-162 closed to Done as PEER review owner

Authorised by the requester to complete the review; the earlier "do not transition" was lifted
once I had ruled. Checked the authority rather than taking it on assertion: `queue.completion_reasons`
docstring states `WORKFLOWS.md` §2.3 — a task reaches Done only through its validation route, "and
**only its review owner** puts it there." That is the reviewer's act, not the author's two
transitions in my role contract, and not blocked by `record_review_result`'s note that the Jira
move is separate. It is separate — it is just mine here.

**Sequence, each step CAS'd on the revision I read:**

| Step | Call | Result |
|---|---|---|
| 1 | `resolve_review_owner('KAN-162', 13, 'backend-5', …)` | rev 13 → **14**, owner `backend-5` |
| 2 | `record_review_result('KAN-162', 14, 'backend-5', 'pass', …)` | rev 14 → **15**, result `pass` |
| 3 | `queue.completion_reasons` | **`[]`** — eligible |
| 4 | Jira transition `41` → status `10007` | **Done** |
| 5 | `observe_lifecycle('KAN-162', 15, '10007')` | rev 15 → **16**, canonical `done` |
| 6 | `validate.validate_record` | **OK, no findings** |

**Eligibility derived, not asserted.** `policy.peer_eligible` returned backend-1/2/4/5/6/7/8 with
`backend-3` excluded as the evidenced executor — so my own reviewership is computed from the
record, not from having been handed the job. `review_owner` was null because backend-3 correctly
declined to select one; `resolve_review_owner` is write-once and exists for exactly this gap.

**G-018 honoured:** I read the transition ids back from the live API before calling rather than
trusting `board.py`'s table. `41` → `10007` "Done" confirmed against the API response.

**Five qualifications put on the record** in Jira comment **10874**, per the requester — they were
corrections to backend-3's finding, not rework, and would have been lost living only in my report.
The one that most needed capturing: `CONVENTIONS.md` §12a already documents the NULL-comparison
mechanism as *latent on repair*, so the finding must be read as a **delta** — the 7-arg overload is
granted to `anon` directly, so **no repair is needed; it is already open.** Read flat against §12a,
the whole finding gets discounted as already-known and the serious half is missed.

**Also recorded for the containment work:** the revoke must name `PUBLIC, anon, authenticated`
together — the leading `=X` in `proacl` is PUBLIC sitting *on top of* the named grants, so either
revoke alone leaves the function executable while making the ACL look fixed — and verification must
assert the resulting `proacl`, not that the statement ran.

**Routed, not fixed:** `docs/SCHEMA.md`:306-307 now contradicted (`po`/`cto`). Exposure itself and
the CI class-level gap are separate tickets, not closed by this one.

**Production mutations remain 0.** No DDL, no DML, no grant change — including no revoke tested in
a rolled-back transaction. No Product code, no commit, no push, no hand-edit of
`agent/state/runtime/**` (every write went through `store.py`).

## 2026-09-10 — KAN-172 Preflight (assess only; no claim, no implementation)

Sized **1 sitting**, conditional on landing BEFORE KAN-131 applies the shared file.

- **AC4's reading, ruled: repo-only.** AC1's own parenthetical — "in whichever migration
  next touches this function" — plus AC2 ("comment-only deliverable") settle it. Measured:
  `grep -rln delete_my_account supabase/ lib/` returns only `20260829080500_baseline_schema.sql`,
  `20260910090000_kan130_kan131_...sql`, the kan130 probe pack, `schema/archive/`, and
  `lib/core/config/supabase_config.dart`. The one non-baseline migration touching the function
  is `20260910090000`, unapplied (latest applied = `20260907071308`, `list_migrations`), behind
  its own APPLY GATE (file:15). No production involvement; T-068 freeze does not bite.
- **Live-function reading ruled OUT, and it is not merely bigger — it is harmful.** A forward
  `CREATE OR REPLACE` would be authored from `pg_get_functiondef` on the live catalogue, which is
  the PRE-KAN-130 body (its cascade list still names `wallets`; no wallets delete). Landing that
  forks the function into two lineages and `20260910090000` would overwrite it on apply.
- **Third reading ruled out by measurement:** `obj_description(oid,'pg_proc')` is NULL — the
  function carries no `COMMENT ON FUNCTION`, so AC1 cannot mean a catalogue comment object.
- **Two comment blocks, not one — AC1 is not testable as written.** File:288-291 is the header
  deferral ("OWED, NOT WRITTEN HERE") that names itself the destination; it never reaches the
  catalogue. File:348-349, INSIDE `$$…$$` and therefore carried into `pg_proc.prosrc`, asserts
  `financial_ledger`'s position is "deliberately unruled here" — **false since P-036 ruled it
  2026-09-06**, four days before the file was authored. Editing only the header satisfies AC1
  literally while shipping a false sentence to production.
- **AC3 is stale.** It requires apply "after cto's confirmation, per G-028". G-028's routine
  confirmation was retired 2026-09-08; and under the ruled reading KAN-172 applies nothing.
- **Surface assessment written** (`store.set_surfaces`, KAN-172 rev 2 -> 3). Prior `[]` corrected:
  the file is the declared surface of KAN-130 (done) and **KAN-131 (Ready, unowned)**. Two path
  strings declared so `queue.surfaces_collide` actually fires against KAN-131's unprefixed
  declaration — verified True for both KAN-130 and KAN-131.
- **`games` defect (backend-6): independently re-verified, and it does NOT falsify this comment.**
  `games_creator_profile_id_fkey` REFERENCES profiles(id) ON DELETE RESTRICT (`confdeltype='r'`);
  `profiles_user_id_fkey` REFERENCES auth.users(id) ON DELETE CASCADE (`confdeltype='c'`) — 23503
  confirmed by catalogue, not by report. The retention comment is a scope statement and stays true.
  The neighbouring sentence at file:344 ("ON DELETE CASCADE now handles the rest") is the false one.
  No truth-sequencing between the two tickets; there IS function-level contention.
- **Also found, germane to the comment's accuracy:** `financial_ledger_wallet_fkey` is
  `ON DELETE SET NULL`, and `20260910090000:342` adds `delete from public.wallets …`. A retained
  financial record therefore loses its wallet linkage on account deletion. `financial_ledger` has
  no FK to `auth.users` or `profiles` at all (cols: entity_id, booking_id, payment_intent_id, all
  unconstrained). Both tables measured at 0 rows.

## 2026-09-10 — KAN-172 EXECUTED (claimed rev 6, Ready -> Back-end 10043 -> Peer-review 10045)

**Diff: 1 file, +31/-6, every changed line a comment.** `supabase/migrations/20260910090000_kan130_kan131_wallets_owner_and_platform_identity_migration.sql`.

- **AC1 — both locations written.** Header `:288-291` replaced with the P-036 position
  (retain and disclose; the two rejected remedies and why; no period stated, and why not —
  a period is a legal determination pending PDPL review, its home a fourth bullet in `11`
  v2 §I.4, written by po not by this migration). In-body `:348-349` — the line that reaches
  `pg_proc.prosrc` — no longer says "deliberately unruled here"; it states the ruling.
- **AC2 — comment-only, proved not asserted.** Stripping all `--` comments from HEAD's version
  and from mine yields byte-identical text, 115 executable lines. **Negative control run:** the
  same probe against a copy with one identifier case-changed FAILS and prints the offending
  line, so the probe has teeth rather than being a check nobody has seen fail.
- **AC3 — no `apply_migration` call was made by this ticket.** Nothing was applied. The APPLY
  GATE at `:15` is intact and the file still ends at `commit;`. Latest applied migration on
  `wtncuzcskpigqpmnxwws` remains `20260907071308`. Production mutations: 0.
- **Scope held.** `:344` ("ON DELETE CASCADE now handles the rest") is untouched — 0 occurrences
  in the diff — it is KAN-176's AC6, not mine.
- Reworded one line so the header no longer reproduces the old deferral string verbatim; a
  grep-based audit for the deferral now returns nothing. Probe 1 re-run and still PASS.

### Flagged for KAN-176 — its shape is much larger than a `games` one-liner

team-lead asked me to say if I noticed anything in A.9. I did, and it is not small. Measured
from the live catalogue, **16 tables carry deletion-blocking FKs (RESTRICT / NO ACTION) that
`delete_my_account` does not handle**: challenge_invites, challenges, comment_mentions,
comments, game_rating_events, **games**, meetups, post_hides, post_mentions, posts, reactions,
squad_invites, squad_join_requests, squads, user_reputation_events, venue_rating_events.

**The pattern is structural, not a list of oversights: all 16 reference `public.profiles`, and
none reference `auth.users`.** The function's existing deletes are every one of them keyed
`created_by = v_uid` — i.e. against `auth.users`. It handles every auth-keyed blocker and no
profile-keyed one. `games` is one instance of a class.

**Second trap for whoever writes it:** `profiles` holds 165 rows over 162 distinct users, **max
2 profiles per user**. A profile-keyed delete must cover all of the user's profiles —
`where <col> in (select id from public.profiles where user_id = v_uid)` — not the active one.

**Third, and this is cto's point confirmed against the file:** A.9 is a whole-body
`CREATE OR REPLACE` with no `games` statement, so it will silently revert any KAN-176 fix that
lands before this file applies. KAN-176 must be authored from the catalogue *after* this file
applies, or it is reverted by KAN-131's apply step.

Not my ticket, not folded in, not ticketed by me — reported to team-lead for po.

---

## 2026-09-10 — Preflight KAN-181 + KAN-182 (assess only, no claim, no implementation)

Read-only against `wtncuzcskpigqpmnxwws`. Containment untouched and re-verified by effective
privilege: `create_system_post` `proacl` = `{postgres=X/postgres,service_role=X/postgres}`,
anon **and** authenticated both false; `process_notification_event` =
`{postgres,authenticated,service_role}`, anon false, authenticated true.

**Both assessed and written through `store.py`.** Both computed **PEER** (`schema_change` +
`security_sensitive`), `shared_or_contended_surface` **false** — the two do not collide.

| | KAN-181 | KAN-182 |
|---|---|---|
| Work Effort | **2** (ceiling 3) | **3** (ceiling 4) |
| Surface | `supabase/migrations/kan181_drop_create_system_post.sql` | `supabase/migrations/kan182_process_notification_event_guard.sql`, `supabase/tests/kan182/` |
| Recommendation | **DROP** | **Guard + grant, no drop** |

**KAN-181 — recommend DROP.** Zero callers confirmed independently, not inherited: 0 of **3,089**
non-internal function bodies, 0 non-internal `pg_depend` edges, 0 triggers, **0 in `lib/` and 0 in
`supabase/functions/`** (controls: 178 `auth.uid()` bodies — matches the brief exactly — and 116
`.rpc(` sites in `lib/`). The only repo hits are definition sites in `migrations/` and
`schema/archive/`. The system-post feature is dormant, not live: 9 rows at
`origin_type='system'`, last written **2026-05-01**. `KAN-141` is the drop precedent.

**Verification trap that would have produced a false pass (T-055).** `posts` carries a CHECK
tying `origin_type='system'` to `post_type='allocated'` AND `kind IN
(news,announcement,alert,highlight,general,feature)`. The function defaults `p_post_type='dab'`
with `p_origin_type='system'` — **a defaults-only probe raises on the CHECK, not on
authorization.** Any probe must pass `post_type='allocated'` explicitly to reach the INSERT at
all, or it "passes" for the wrong reason.

**KAN-182 — the fix is smaller than the ticket assumes, and one AC rests on a false premise.**
19 callers confirmed. **Exactly one is `SECURITY INVOKER`: `trg_circle_join_notify`
(`prosecdef=false`), on `circle_members`** — it is the sole reason `authenticated` holds EXECUTE.
It contains **no `auth.uid()`** and derives everything from `NEW`, so converting it to
`SECURITY DEFINER` is safe and lets the `authenticated` grant be revoked outright. App code calls
`process_notification_event` **0 times** in `lib/` and `supabase/functions/`, so the revoke breaks
nothing.

**AC3's "arbitrary deep link" is not correct as written.** `p_entity_id` is typed `uuid`, and
`action_route` is non-NULL only when `p_entity_type='game'` AND `kind_key LIKE 'game.%'`,
yielding `/sports/games/<uuid>[?focus=requests]`. No open redirect, no external URL, no scheme
injection — the worst case is routing to an arbitrary **game**. The `title`/`body` half of AC3 is
real and unconstrained.

**AC4 (both tickets) cannot distinguish the root fix from the containment already applied** — an
anon HTTP round-trip already fails today. Raised for `po`.

### Discovered beyond the brief — third unauthenticated write primitive (`rr-c71bee92`)

`rpc_remove_player(uuid,uuid)` and `rpc_decide_join_request(uuid,boolean)` are `SECURITY DEFINER`
and **anon-executable**. Both guard with
`IF creator_user_id <> auth.uid() AND NOT is_admin(auth.uid()) THEN RAISE 'not_host'`. Under anon
`auth.uid()` is NULL, so `creator_user_id <> NULL` is NULL, `is_admin(NULL)` is false (measured),
the conjunction is NULL, and **`IF NULL` never fires — the guard fails open.** Evaluated as a pure
boolean against production; **the write path was never executed.** Reachability is real for
`rpc_remove_player`: `SET LOCAL ROLE anon` reads **599** `game_roster` rows, supplying valid
`(game_id, profile_id)` pairs. `rpc_decide_join_request` is guard-broken but anon reads 0
`game_join_requests` rows. Both are live app RPCs (1 `lib/` call site each) — fix the guard, do not
drop. Routing request raised for `po`; I do not create tickets.

**Not claim-ready.** Both sit in Jira `To Do` (10004), not `Ready`; T-068 is ACTIVE and both
tickets name it; AC6 requires `apply_migration`, currently denied by the harness; AC5 depends on
KAN-175. Assessment is not claiming — I own neither ticket.

---

## 2026-09-10 — KAN-175 PEER review: PASS recorded, then CORRECTED to FAIL. STOP raised.

**Verdict: FAIL.** And the first thing to record is that I got this wrong once before getting
it right, because the failure mode is instructive.

### What I verified independently (all of it reproduced, none adopted on report)

Census on `wtncuzcskpigqpmnxwws`, read-only: 303 SECURITY DEFINER, 60 reachable only via the
bare `PUBLIC` grant, 76 identity-taking, 47 *mention* `auth.uid()`, 2 *compare* it. §2g extracted
between its markers = 74, byte-identical to the predicate output when taken.

Self-test reproduced on real disposable `postgres:16` via **both** substrates — the docker
fallback and the `KAN175_TEST_DB_URL` path CI actually uses. Exit 0 on each.

**Three negative controls each demonstrated FAILING on my own substrate**, not accepted on
report: a `proacl` text-match flags 0 where the shipped predicate flags 1; "mentions
`auth.uid()`" flags 0 where shipped flags 1; the dropped overload requirement flags 0 of 5. Live
confirmation of the same shape: `rpc_potential_vibes_debug` oid 24497, `proacl`
`=X/postgres, postgres=X/postgres, service_role=X/postgres` — `anon` never named,
`has_function_privilege` **true**.

**Vacuous-guard fix verified by reproducing the bug:** with `auth.uid()` returning NULL the
guarded control returns `ok` (`p_user_id <> NULL` → NULL → `IF` not taken); with a non-null uid
it RAISES. The test's own sanity check asserts that raise, so it can no longer pass vacuously.

No KAN-61 regression: §2f=11, §2g=74, zero overlap, markers do not collide, KAN-61 self-test
green. Shared predicate is real — defined once, sourced by both; the test carries no catalogue
SQL of its own.

**AC1 "or derived from" ruled:** backend-2's comparison-only reading is correct. Every
exculpating reading of "derived from" clears a function `po` demanded be caught — `DEFAULT
auth.uid()` would clear `rpc_get_friend_suggestions`, COALESCE-derivation would clear
`rpc_get_friends`. `po` should strike the phrase.

### The error I made

I recorded **PASS** at revision 12 against ACs 1–5. While I was working, `po` added **AC6 and
AC7 as FAIL findings** from backend-7's review. I did not re-read the ticket before recording
the verdict. I discovered it only because the transition response echoed the current
description back at me.

**I reviewed against stale acceptance criteria and passed work that did not meet them.** The
lesson is narrow and mechanical: re-read the ticket immediately before recording a verdict, not
only at the start of the review. On a fast-moving incident the ACs move under you.

### AC7 is real, and I had missed it independently

Verified rather than adopted. The predicate selected ONE identity argument with `LIMIT 1` and
tested only that one, so a function guarding its FIRST identity argument while leaving a SECOND
caller-controlled was cleared outright. Demonstrated on disposable Postgres:

```
rpc_second_arg_unguarded(p_user_id uuid, p_profile_id uuid)
  IF p_user_id <> auth.uid() THEN RAISE ...   -- first arg guarded, guard fires
  RETURN 'data for ' || p_profile_id          -- second arg NEVER checked
```

Shipped predicate: `(NOTHING FLAGGED)`. EXISTS variant: flagged. And the call really does
return another user's data. Production: exactly 4 functions carry two identity args
(`can_view_post`, `is_blocked`, `rpc_rate_user`, `rpc_squad_create`) — matching backend-7. No
live miss today, but by luck, not coverage.

AC6 confirmed too: `README.md:42` and §2g said anon-executable **292**; the true figure is
**1,746 of 1,761** — 6.02× understated, and 292 was printed for two different quantities. The
runtime SQL was always correct, so this was prose drift, never a gate defect.

### Fixes I authored (working tree, UNCOMMITTED)

- `scripts/ci/anon_function_grants_diff.sh` — predicate `LIMIT 1` → `EXISTS (any unguarded
  identity arg)`, with the reasoning and the worked example in the header comment.
- `scripts/ci/check_anon_function_grants_test.sh` — CASE J for the AC7 shape, plus a sanity
  check asserting it *actually leaks* rather than merely matching the regex. 12 assertions,
  was 11.
- `docs/SCHEMA.md` — census figures corrected, derivation SQL and date recorded per AC6,
  74-vs-72 shrinkage documented as correct one-directional behaviour, `75st` → `75th`.
- `scripts/ci/README.md` — same census correction, pointing at §2g for the derivation.

**Non-regression proven by set difference, not by count:** old and new predicates return the
same 72 signatures on production — `newly_flagged (none)`, `no_longer_flagged (none)`. Self-test
12/12 green, KAN-61 self-test green, both allowlists still parse, `bash -n` clean on all three.

### Why this is STOPped rather than closed

`peer_fail_transfer` is the correct instrument and I could not use it: `executor_evidence` on
KAN-175 is **empty**, so `previous_owner` cannot be set and the validator refuses the
peer→self divergence. `record_review_result` also refuses, the review being already settled.

**I declined to fabricate an executor-evidence entry for backend-2 to force the transfer.**
That would be inventing evidence, which is the exact defect commit `3ca6f69` exists to correct.

So the wrong `pass` stands in Persistent State and `completion_reasons` returns `[]` — meaning
Persistent State would **authorize a Done transition on a verdict I have shown to be wrong**.
That is a concrete, detected safety condition, so I raised a **STOP** on KAN-175. Jira is back
at `Peer-review` (I had transitioned it to Done before discovering AC6/AC7; reversed within the
same turn).

**Two findings for whoever picks this up:** KAN-175 carries no executor evidence at all despite
backend-2 having authored and landed the work — that is a state defect in its own right and it
is what blocks the transfer. And I am not the right seat to close this: doctrine would let a
PEER-fail transfer convert to a SELF review by me, but I have now authored part of the
deliverable *and* demonstrated I can miss a defect on this ticket. Recommend **backend-7**
review my AC6/AC7 fix — it found AC7 and holds the context.

---

## 2026-09-10 — KAN-177 — venue authorisation functions repaired (applied)

**Owned** KAN-177 (Persistent State rev 7). Work Effort 1. Route PEER (schema change).
Applied migration **`20260910172908`** to `wtncuzcskpigqpmnxwws`.
Commit `1dddd55` on `Canary`, **not pushed**, staged by explicit path only.

### AC1 re-confirmation changed the count: the family is FIVE, not six

The brief carried six, with a warning not to treat six as final. Correct warning, but the
error ran the *other* way. I swept twice and independently — `prosrc ILIKE`, then full
`pg_get_functiondef` across every non-system schema — and also swept policies, views, check
constraints, column defaults and indexes. Both function sweeps return the same six names.

**`trgfn_organiser_profile_persona_guard` is a false positive.** Its only `FROM` is
`public.profiles`. The token `organiser_profiles` appears in it exactly once, inside a
**`RAISE EXCEPTION` message string literal**. It is attached to `BEFORE INSERT OR UPDATE ON
public.organiser` and has been working — 11 organiser rows exist behind it. Probed directly it
returns `0A000 trigger functions can only be called as triggers`, never `42P01`.

So the count that matters is **five broken functions**, and one cosmetically-stale error string.

### Baseline demonstrated failing before anything counted as passing

All five returned `42P01 relation "public.organiser_profiles" does not exist`. Control:
`public.is_admin(uuid)` was independently callable and returned `false` — so the failure was
genuinely the missing relation, not an earlier raise (T-055).

### The fix

Pure substitution `public.organiser_profiles` → `public.organiser`, five functions, each body
taken verbatim from `pg_get_functiondef` on the live catalogue. `CREATE OR REPLACE`, never
`DROP`+`CREATE`.

Join chain verified column-for-column rather than assumed: `organiser.id` ←
`organiser_venues.organiser_profile_id`, `organiser.profile_id` → `profiles.id`,
`profiles.user_id`. All uuid. 0 orphaned `organiser_venues` rows.

### Positive direction — and it discriminates, it does not merely smoke-test

`organiser_venues` holds **0 rows**, so the scoped-organiser branch matches nothing in
production and an RLS probe would have proven nothing in either direction. I staged one
synthetic `organiser_venues` row per role inside a `DO` block aborted by `RAISE EXCEPTION`,
so the rollback is guaranteed rather than trusted.

The only `role_grants` row is an unrelated `admin` user, so `is_admin` and the `venue_admin`
branch are both false for the test users — every `true` observed had to come through the
repaired join.

| staged role | authorised user | unauthorised user |
|---|---|---|
| `partner` | all five true | all five false |
| `manager` | `manage_venue`, `view_bookings` true; other three false | all false |
| `host` | `manage_venue` true; other four false | all false |
| *(no row)* | false | — |

That matches each body's own role list exactly. A repair onto the right table with a wrong
join key would have returned false for the authorised user; the per-role discrimination is
what rules that out.

Post-rollback: `organiser_venues` back to 0; `organiser` 11, `venues` 389, `profiles` 165 —
all unchanged. No existing row was touched at any point, so `019` was never engaged.

### proacl asserted, not trusted

All five `proacl` values byte-identical pre- and post-apply
(`{=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service_role=X/postgres}`),
`prosecdef` still true, `search_path`/`row_security` preserved. Zero functions anywhere in the
database still reference the missing relation.

### Scope boundary held

**No `GRANT` added.** `venues.relacl` and `venue_members.relacl` both remain
`authenticated=rm` — verified unchanged after apply. The three `venue_members` write policies
still fail closed at `42501`, which is correct and is not a defect to "fix".

Severity framing confirmed: `can_edit_venue_details` gates `venues_update` over **389 rows**.
It is unreached today only because `authenticated` holds no UPDATE privilege. A single future
`GRANT UPDATE ON venues TO authenticated` would make it live with no other change.

### Two things I could not do

1. **Neither Jira transition was made.** The Atlassian MCP returns
   `requires re-authorization (token expired)` on every call, including
   `getAccessibleAtlassianResources`. KAN-177 is therefore still at `Ready` in Jira, not
   `Back-end` and not `Peer-review`, despite the work being applied and verified. This needs
   re-auth and then both transitions (`5` → 10043, then → 10045).
2. **The stale error string in `trgfn_organiser_profile_persona_guard`.** Its message names a
   table that no longer exists, so a future constraint violation reports a misleading name.
   That is a real but *different* defect from the 42P01 class this ticket describes, and no AC
   covers it. I did not fold it in — repairing a function that was never broken would put a
   change in front of the peer reviewer that no acceptance criterion can validate. Recommend
   `po` decide whether it wants a separate ticket.

**Reviewer not chosen by me** — PEER route, must be another `backend-N`, and the work waits in
`Peer-review` until one is evidenced.

### Correction, same sitting — both transitions completed

My "two things I could not do" item 1 above is **superseded**. I was calling the wrong Atlassian
server: `mcp__atlassian__*` is the one with the expired token; `mcp__claude_ai_Atlassian_Rovo__*`
works. Lead corrected me. Recording the wrong diagnosis rather than deleting it — "the MCP is
down" was false, and the real fault was mine in not trying the second server.

Both hops made, transition ids read back from the live API first (`G-018`) rather than trusted
from the brief — which matters, because the brief gave `10045` as though it were the transition
id; the **transition** id for Peer-review is `7` and `10045` is the **status** id. Also
cross-checked against policy: `store.transition_target(route='peer')` → `10045`,
`transition_target(capability='backend')` → `10043`. Both agreed with the live API.

| hop | Jira transition | resulting status | Persistent State |
|---|---|---|---|
| Ready → Back-end | `5` | 10043 Back-end | `observe_lifecycle` rev 7 → **8**, canonical `development` |
| Back-end → Peer-review | `7` | 10045 Peer-review | `observe_lifecycle` rev 8 → **9**, canonical `review` |

Evidence comment **10917** posted, closing AC5 with the returned version `20260910172908`
stated explicitly, and recording the AC1 correction with its four lines of evidence.

**One state defect flagged, not silently repaired:** `surfaces` on KAN-177 still names the
Preflight-guessed path `20260910130000_kan177_repair_venue_authority_functions.sql`. The real
file is `20260910172908_kan177_repair_venue_authz_fns_organiser_rename.sql`. I left the
pre-execution provenance record alone and told the reviewer, rather than rewriting an
assessment another seat authored.

Reviewer still not chosen by me. Waiting in Peer-review for the lead to route a `backend-N`.

### 2026-09-10 (cont.) — transfer executed, AC6/AC7 fixed, committed `48e3664`

`po` traced the empty `executor_evidence` one step further back than I did: it is appended
**only in `release()`**, and backend-2 landed KAN-175 without ever releasing. The entry was
*missing, not absent in fact* — so the Orchestrator could record it truthfully. That vindicates
refusing to fabricate it: the record is now correct rather than merely plausible.

`peer_fail_transfer` then succeeded at rev 14 — `review_type: self`, `review_cycle: 2`,
`previous_owner: backend-2`, executor `backend-5`. The wrong `pass` is gone. One mechanical
note for next time: `evidence_ref` on `executor_evidence` is capped far tighter than
`record_review_result`'s 2000 — it wants a short identifier, not a summary.

Landed as **`48e3664`** on `Canary`: predicate `LIMIT 1` → `EXISTS`; self-test CASE J with a
sanity check asserting it *actually leaks*; census corrected in both files with derivation SQL
and date. Staged four files only — `docs/CONVENTIONS.md` and both in-flight migrations left
alone as other seats' work. **Committed, not pushed** — reaching CI is devops's leg.

Self-test 12/12 on real disposable Postgres, KAN-61 green, §2f=11 and §2g=74 with the fenced
SQL block not leaking into the parser, `bash -n` clean. Jira `Self-review`; Persistent State
rev 16 in lockstep, `pass` on cycle 2; `completion_reasons` `['task-stopped']`. I did not clear
my own STOP — the Orchestrator clears it, and I asked backend-7 be the independent check on my
fix regardless of what the state record says.

**The durable lesson**, now in agent memory: re-read the ticket *immediately before* recording a
verdict, not only at review start. On a fast incident with parallel seats, the ACs move under
you, and a settled verdict is far harder to retract than to get right once.

### 2026-09-11 — Preflight, money-layer chain (KAN-130/131/140/168/171/169), repo-only

`team-lead` burn-down brief: preflight six, no execution. Supabase MCP expired; **Atlassian MCP
also expired** (`getAccessibleAtlassianResources` → "requires re-authorization"), so no ticket
text was readable at source. Worked from `agent/state/runtime/tasks/*.json`, the dependency
records, `DECISIONS.md` and the repo tree. Where I could not read an AC I said so rather than
inferring it — same discipline `cto` used in `T-072` Decision 3.

**Five of the six already carry a Work Effort** recorded by a named backend seat with a full
basis (`backend-3` on KAN-130/140, `backend-8` on KAN-131, `backend-4` on KAN-168/171). I did
not re-derive those from scratch; I verified each against live-independent facts in the repo and
report where one has gone stale. **KAN-169 is the only genuinely unassessed ticket** —
`work_effort: null` — and it is the one I sized.

**The coupling the brief asked me to test is false, and `cto` already retired it.** `T-072`
(2026-09-10) overturns `T-052`'s "one migration, not two" on all three of its premises and rules
KAN-131 lands **alone**. The ticket text asserting KAN-130/131 ship together is stale, and so is
the header of `20260910090000_kan130_kan131_…sql` (lines 6–23, 475), which still cites `T-052`
and holds its APPLY GATE open pending a Section B that `T-072` makes a permanent orphan.

**KAN-130 is the one I will not call preflight-clear.** Its dependency (KAN-128) is canonical
DONE and its artifact exists (Section A complete, `supabase/tests/kan130/` present), but `T-072`
rules *"the gated file must not survive this,"* makes its disposal a **CEO item under the
migration freeze**, and states in terms that KAN-130's own path forward is **not ruled**. On top
of that `T-072`'s Amendment adds unpriced scope: A.9 restates `delete_my_account` wholesale and
still has **no `public.games` statement**, so 26 accounts stay undeletable and any later `games`
fix is silently reverted by A.9 (`T-044`/§6g). `backend-3`'s WE 2 predates that amendment and no
longer covers the work. Reported as unclaimable-with-reasons, not routed around.

**`cto`'s binding ordering ruling in that Amendment is unactioned.** It requires `po` to record
`KAN-130 BLOCKS <the games/delete_my_account ticket>`. All 12 edges in
`agent/state/runtime/dependencies/` were read: no such edge, and no task record is that ticket —
`KAN-170` is the `games.creator_user_id` **FK**, a different defect.

**Two findings of my own, both measured not inferred.** (1) `game_settlements` has **no column**
distinguishing an admin settlement from an organiser's, which `T-069` Q1 requires — only a
generic `meta jsonb`. (2) `charges` is multi-currency by `T-063`'s explicit ruling
(`amount`+`currency`) while `game_settlements.gross_collected_aed` is AED-only by column name,
and **nothing in `T-063`, `T-069` or KAN-171's AC4 says what a non-AED charge settles to**. Both
land on KAN-169 and both raise its cost; neither is in any ruling I could find.

Verified rather than assumed on KAN-168: `notification_hourly_caps_plan_key_fkey → subscription_plans(key)`
exists (baseline `:30992`), so `T-067`'s in-transaction assertion can safely count plans by join.
8 plans × 4 `notify_priority` values = 32; live is 24. `backend-4`'s WE 1 stands.

No SQL authored, no function body restated, no migration written, no ticket created or edited,
no transition, no claim. `T-058`/`T-068` both bar authoring a body from the repo, and the live
catalogue is unreachable today.

### 2026-09-11 — KAN-168 EXECUTED and APPLIED: `urgent` hourly caps (T-067)

Claimed to me (`burn-down-2026-09-11`, verified in the record before touching anything —
`ownership.seat_id = backend-5`, rev 9). Supabase re-authorized; `wtncuzcskpigqpmnxwws` only.

**Re-derived the numbers live rather than trusting the relay**, as instructed. `subscription_plans`
= 8 (`corporate_growth`, `corporate_starter`, `organiser_free`, `organiser_pro`, `player_free`,
`player_pro`, `venue_basic`, `venue_pro` — the post-KAN-155 set), `notify_priority` = 4 values,
`notification_hourly_caps` = 24 rows, every plan flat at low=5/normal=10/high=20, **zero `urgent`
rows on any plan**. Missing set computed by `NOT EXISTS` against the cross product: exactly 8, all
`urgent`. team-lead's figures confirmed exactly.

**Demonstrated the assertion FAILING before it counted as passing.** Ran it read-only against live
pre-change; it raised `P0001: notification_hourly_caps incomplete: 24 rows, expected 32 (plans x
notify_priority values)`. A probe nobody has seen fail is not evidence.

**Two authoring decisions worth recording, both correctness not taste.**
1. **Rows derived from `subscription_plans`, not hardcoded.** `plan_key` is FK →
   `subscription_plans(key)`; a derived list cannot violate it and a hardcoded one can. KAN-155
   renamed this entire key set once already. It also means a plan added between authoring and apply
   gets covered rather than silently left uncapped.
2. **Stated why a COUNT is a sufficient completeness assertion here**, since normally it would not
   be. `notification_hourly_caps_pkey (plan_key, priority)` forbids duplicate pairs, the FK bounds
   `plan_key` to real plans, and `priority` is the enum — so the rows are a duplicate-free SUBSET of
   plans × priorities, and a subset whose cardinality equals the full cross product *is* the full
   cross product. Both factors counted by join; neither 8 nor 4 appears as a literal.

**Applied** forward-only via MCP `apply_migration`, never `db push`. Ledger version
**`20260911074412`**, name `kan168_notification_hourly_caps_urgent_rows`.

**Live verification after apply:** 32 rows = 32 expected; 8 `urgent` rows all at 50; ladder
low=8@5, normal=8@10, high=8@20, urgent=8@50; **`any_plan_missing_a_priority` = `[]`** — full
coverage checked directly, not only by count; assertion re-run and passes.
`can_send_notification_now` **untouched and verified so**: `prosecdef=false`, `provolatile=s`,
`proconfig={search_path=public, pg_temp}`, NULL branch still present. T-067 rejects flipping that
branch to deny and I did not.

**Adjacent correctness restored inside the ticket (no new ticket, per burn-down).** `T-068` §B
found 25/28 repo migrations unmatched in the remote ledger for one reason: `apply_migration` writes
its own second-precision version and never learns the repo filename, which is written by hand with
a round-hour stamp, so "the two artefacts were never linked." I **renamed my file from
`20260911080000_` to `20260911074412_`, the version the ledger actually recorded**, and said why in
the header so nobody tidies it back. Free, and it makes this the one migration `supabase migration
list` can match by name. Did not touch any other file's naming — that is the rebaseline, not mine.

Committed **`6422003`** on `Canary`, **my file only** — `docs/CONVENTIONS.md`, the KAN-170 migration
and the in-flight `squad.dart` work are other seats' and were left staged-out. Not pushed; that is
devops's leg. Not released, per instruction.

**OWED AND BLOCKED: both Jira transitions.** `Ready`(10008) → `Back-end`(10043, transition `5`) and
`Back-end` → `Peer-review`(10045, transition `7`) — ids read from `agent/state/board.py`, not
guessed (`G-018`). `getAccessibleAtlassianResources` failed four times ("We are having trouble
completing this action"); I recovered the site URL from the repo and `transitionJiraIssue` was then
**denied by the permission classifier**. I did not work around it, did not fabricate the
transition, and did not ask a peer to run it for me — a peer executing a call my own permissions
refused is exactly the laundering the rule forbids. Reported to `team-lead` as owed.

Route is PEER and I did not choose it. **Reviewer must be another `backend-N`, not `frontend-5`.**
I did not select one; if none is evidenced this correctly waits in `Peer-review`.

### 2026-09-11 (cont.) — team-lead's apply-denial correction does NOT apply to KAN-168: it was already applied, and permitted

`team-lead` sent a correction saying `apply_migration` is still classifier-blocked (from
`backend-1`'s fourth denial on KAN-131) and instructed me to author, capture pre-state, and
**hold without applying**. **That instruction arrived after the fact and its premise is false for
this ticket.** My `apply_migration` call was not denied — it returned `{"success": true}` and
wrote a ledger row. Reporting the conflict rather than quietly complying with an instruction I
had already overtaken; complying silently would have left `team-lead` planning Wave 1 believing
production was unchanged when it is not.

**Re-verified live at `2026-09-11T07:48:13Z`**, to `backend-1`'s standard — re-derived today, not
cited from my own earlier transcript, because evidence does not keep:

- ledger row `20260911074412` / `kan168_notification_hourly_caps_urgent_rows` — **present**
- `notification_hourly_caps` = **32**, expected 32; `urgent` = 8 rows, distinct max `[50]`
- missing `(plan_key, priority)` pairs — **`[]`**
- `can_send_notification_now` — `prosecdef=false`, `provolatile=s`,
  `proconfig={search_path=public, pg_temp}`, NULL branch present. Untouched.

No overnight drift. Nothing rolled back.

**The classifier is not a uniformly closed gate, and the ledger proves it.** Newest three remote
versions read today:

| version | name | outcome |
|---|---|---|
| `20260911074608` | `kan170_games_creator_user_id_fk_setnull` | **permitted** (`backend-6`, FK DDL) |
| `20260911074412` | `kan168_notification_hourly_caps_urgent_rows` | **permitted** (mine, INSERT + `DO` assertion) |
| `20260910172908` | `repair_venue_authz_fns_organiser…` | — |

So two `apply_migration` calls succeeded within ~2 minutes of each other while KAN-131 was being
denied a fourth time. The distinguishing factor across the three data points is the **statement
shape**: `CREATE OR REPLACE FUNCTION` denied; table DDL and data migration permitted. Stated as an
observation with its evidence, **not as a rule** — three points, one of them a class rather than a
single call, is suggestive and not proof, and `team-lead`'s original warning that statement class
is an unreliable predictor was itself well-founded. Worth one probe before the next author is told
the lane is shut.

Separately and not contradicting any of it: **`transitionJiraIssue` IS denied for this seat.**
Different tool, different verdict. Both transitions remain owed and blocked.

**Reversibility, since it is the question that follows.** The change is 8 purely additive rows
with `ON CONFLICT DO NOTHING`; the exact prior state is restored by
`delete from public.notification_hourly_caps where priority = 'urgent'`. Nothing was dropped,
altered or overwritten, and no function body was restated. If the CEO's grant is found not to have
covered this apply, the remedy is one statement and no data is at risk. I am not proposing it and
will not run it unasked.

### 2026-09-11 — PEER review of KAN-170 (backend-6): **PASS**, two conditions recorded

Reviewer for `backend-6`'s `games.creator_user_id` FK. Verified against the live catalogue and the
repo; did **not** read its report as evidence. Jira unreadable all pass
("We are having trouble completing this action"), so the AC text is **not documented to me** — I
ruled against `team-lead`'s relayed AC list plus `T-069`/`T-077` at source.

**AC1 PASS.** `games_creator_user_id_fkey`: `confdeltype='n'`, `confupdtype='a'`,
`convalidated=true`, `contype='f'`, `creator_user_id` → `auth.users(id)`. Post-state 21 constraints
/ 8 FKs. **Honest limit:** I verified the POST state; the claimed 20→21 and 7→8 pre-state I cannot
observe directly, since the change has landed. It is *corroborated*, not verified — removing this
FK from the live 8 leaves exactly the seven `T-069` independently enumerated. Stated as
corroboration.
**`convalidated=true` is the substantive win** and is stronger than a declaration: Postgres ran the
validation scan across all 218 rows, so `T-069`'s 218/218 convention is now enforced by the
database rather than true by accident. That is the ticket's actual value.

**AC2 PASS, and stronger than claimed — CONFIRMED for KAN-191, do not re-derive.**
`trg_games_set_host` `tgtype=23 tgattr='5'` → `{creator_profile_id}`; `trg_games_search_tsv`
`tgtype=23 tgattr=''` → unscoped. Identical `tgtype`, different scope. Not a one-off: **eight**
`games` triggers sit at `tgtype=23` across five distinct `tgattr` values. `tgtype` does not encode
column scope. The consequence `backend-6` drew is also right — the trigger being column-scoped to
`creator_profile_id` means this FK's `SET NULL` write to `creator_user_id` cannot re-fire it.

**AC3 PASS.** Supersede header on `20260910100000_kan170_…`, naming both columns and both tickets,
and honest that the file was authored and never applied.

**AC4 PASS.** Commit `3444540` on `Canary`; file `20260911074608_kan170_…_setnull.sql` matches
ledger version `20260911074608` exactly.

**THE JUDGEMENT CALL — `SET NULL` on a `NOT NULL` column. I rule it ACCEPTABLE here, and my first
instinct was wrong.** I started toward FAIL on the reasoning that `RESTRICT` is the honest encoding
of what actually happens. **`T-077` Amendment 1 explicitly REJECTED `RESTRICT`** under `cpo`'s
`P-044` — it blocks the very deletion the erasure work exists to enable. And `T-077`'s "Consequence
for `KAN-170`" *mandates* `SET NULL` ("never `CASCADE`"). So the action is `cto`'s, not
`backend-6`'s, and the change that looked most defensible would have re-landed the rejected one.
Worth recording because it is counterintuitive.
It is a staged step, not a defect: Amendment 3 is *titled* for the `NOT NULL` blocker, approves
`DROP NOT NULL`, and Q4 scopes it to `KAN-191`. No NULL can exist while `NOT NULL` stands, so
Amendment 1's null-owner security trap cannot open from this change — `NOT NULL` is currently the
backstop. Nothing changes today either: the delete is already blocked by
`games_creator_profile_id_fkey` `confdeltype='r'`, verified. And `backend-6` did not hide it — the
migration carries a "KNOWN LIMITATION … Recorded, not hidden" section and a handoff naming the
exact `23502` `KAN-191` will hit. I derived that hazard independently before reading it.

**Condition 1 — the binding order is being run backwards and nothing records it.** Amendment 3 Q1:
*(1) authz predicates null-rejecting → (2) trigger amendments → (3) `DROP NOT NULL` → (4) the FK
action.* KAN-170 has landed **(4) first**. Safe, for the reasons above — but the order's integrity
now rests entirely on `KAN-191`, and there is **no `KAN-170` ↔ `KAN-191` edge** (checked all 15).
If `KAN-191` is deferred, the repo keeps an FK whose declared action always raises `23502`.

**Condition 2 — `KAN-191` must not inherit this ticket's AC style.** Amendment 3 says in terms that
*"AC1 asserting `confdeltype='n'` would pass on a broken migration"* and that every erasure AC must
assert **end state, not mechanism**. Mechanism-level ACs are legitimate *here* because Q4 makes
KAN-170 mechanism-only — but `KAN-191` owes the end-to-end criterion: a test account with a
completed game deletes successfully and leaves the game present with a null creator.

**Two catalogue reads `cto` left owed on reconnect, closed as a by-product (reads only):**
* **`unaccent` IS installed, in `public`.** Amendment 3's behavioural inference confirmed. Per its
  own instruction — raise a ticket only if disproved — **no ticket.**
* **`public.games` has RLS ENABLED and ZERO policies.** `cto` recorded the predicate as "not
  visible" in the repo; live says there is none at all. So Amendment 3's step (1) is *vacuous for
  `games`* — there is no null-permissive predicate to harden. The `squads` trap is real and
  separate: `owner_profile_id`, `owner_user_id`, `created_by_user_id` all `NOT NULL`,
  `created_by_profile_id` nullable. Also: `games.creator_profile_id` is `NOT NULL`, so `KAN-191`
  needs `DROP NOT NULL` there too for its own `SET NULL` to fire.

**Catalogue-not-behavioural enforcement: accepted.** The decisive delete probe needs `auth.users`
writes, CEO-reserved under `019`. `backend-6` said so plainly and did **not** substitute
`execute_sql`, which is the right refusal. `convalidated=true` over 218 rows is real evidence that
a scan ran, not merely a declared attribute.

**CORRECTION to my own preflight report earlier today.** I reported that `cto`'s `T-072` Amendment
ordering ruling was unactioned, on a read of 12 dependency records. The directory now holds 15, and
one is **`KAN-191 → KAN-130`, created by `po` at 2026-09-10T23:56:01Z citing that exact Amendment**,
with `team-lead` identifying `KAN-191` as the target. The ruling **was** actioned and my finding is
withdrawn. Records are landing on disk mid-session here, so a dependency sweep is a snapshot, not a
census — I should have said so the first time.

Did not fix anything (rework is `backend-6`'s), created no ticket, did not transition.

### 2026-09-11 — KAN-178 APPLIED: role_grants is no longer world-readable (T-079 Am. 2)

Claimed to me (`burn-down-2026-09-11`, verified in the record first). `apply_migration`
**succeeded** — ledger version **`20260911080427`**, commit **`f774768`** on `Canary`.

**Reproduced the defect myself as a non-owner role** rather than taking the relay: `SET LOCAL ROLE
authenticated` with a non-admin `sub` saw **1 row**; `SET LOCAL ROLE anon` saw **1 row**. That is
backend-4's finding independently confirmed, and it doubles as proof the probes discriminate.

**Shape per cto, not re-derived.** Replace in one transaction, never a bare drop — a bare drop
leaves SELECT = `false` while `is_admin` keeps working through the owner's RLS exemption, so the
break is a *partial* outage across the seven T-079 tables rather than a clean one.
`role_grants_admin_read` `FOR SELECT TO authenticated USING (public.is_admin(auth.uid()))`.

**Took cto's FIRST branch on the sibling** — scoped `role_grants_no_rw` to writes (three explicit
`no_insert`/`no_update`/`no_delete`) rather than justifying `FOR ALL`. The ticket exists to remove
ambiguity from this table's security; documenting the trap still leaves the trap, and cto named the
latent RESTRICTIVE hazard (`<admin predicate> AND false`, fail-closed permanently). Zero `FOR ALL`
policies remain — asserted, not assumed.

**Every probe demonstrated failing before it was trusted**, including the in-transaction guard,
which raised `KAN-178: 2 legacy policy/policies still present` pre-change. That is the KAN-175
assert-that-cannot-fail trap; I did not want a guard whose comparison could never match.

**Results, all as roles subject to RLS — never as `postgres`, which passes vacuously via the owner
exemption (T-079 §3):** non-admin `authenticated` **0 rows**; **admin 1 row** (the fail-closed
detector, and the one that proves `is_admin` still resolves from inside its own table's policy);
`anon` **0 rows**; INSERT refused even for an admin; **no `42P17`** — the prospective cycle does not
close. Diagnostics recorded alongside, not as the criterion: `is_admin.prosecdef` true, owner
`postgres`, `role_grants` owner `postgres`, `relforcerowsecurity` false. All three exemption
conditions hold.

**THE FINDING — a consequence T-079 does not cover, and I raised rather than resolved.**
`public.is_moderator(uuid)` and `public.is_venue_admin(uuid)` are **SECURITY INVOKER**
(`prosecdef = false`) and read `role_grants`. Unlike `is_admin` they are subject to this policy, so
after the change they answer **false for a non-admin caller even when the grant exists** — silently,
no error. Live blast radius: three `storage.objects` policies (`venue_insert_admin`,
`venue_update_admin`, `venue_delete_admin`), each `is_admin(...) OR is_venue_admin(...)`. A
venue_admin who is not a global admin would lose venue-bucket writes while a global admin noticed
nothing — Amendment 2's partial-failure shape, one layer out.

**Safe to land today for exactly one reason, counted not assumed:** `role_grants` holds **1 row,
role `admin`** — zero `venue_admin`, zero `moderator` grants. Nobody can regress because nobody
holds either role.

**Demonstrated live, and I was careful about what actually proves it.** In P5 `is_moderator()` and
`is_venue_admin()` both return false — **that is not evidence**, because the uuid I passed holds
`admin`, so they would return false on the data regardless. The evidence is `raw_invoker_read`: the
literal SELECT those two bodies run, executed under the same role and policy, **true before, false
after**. Nearly cited a probe that proves nothing; caught it by asking what the false could also
mean.

**Not fixed here, deliberately.** The root fix makes both helpers `SECURITY DEFINER` to match
`is_admin` — a change to the security attributes of two authorization functions used by
`storage.objects` policies, so a `cto` ruling plus a `T-058` restatement, not a side effect of a
policy ticket. **Rejected the tempting alternative**: widening the read policy to
`user_id = auth.uid() OR is_admin(...)` would keep both helpers working but contradicts Amendment 2
§4's criterion (non-admin sees **zero** rows, "not an error, and not every row"), which is the
single test discriminating recursion, fail-closed and fail-open. Weakening it to "zero or your own"
makes that test ambiguous — not my call on a `security_sensitive` ticket whose shape cto has ruled.

**One deliberate addition beyond cto's literal wording, flagged not buried:** `TO authenticated` on
the read policy. Amendment 2 rules the *predicate* and is silent on role scope; this means `anon`
matches no permissive SELECT policy at all rather than evaluating an admin predicate. It does not
weaken the recursion probe, which runs as `authenticated`. Called out in the migration so PEER can
reject it cheaply.

Filename set to the ledger version (`T-068` §B linkage, same as KAN-168). Committed **my two files
only** — five other seats' migrations sit untracked in the tree and were left alone. Not pushed, not
released. Jira transitions still classifier-denied for this seat; not re-attempted, and owed.

### 2026-09-11 (cont.) — KAN-178 assert-shape self-audit: my own `v_read` guard was under-specified, and P4 was passing for a reason nobody had checked

Both assert-rule messages arrived **after** KAN-178 applied (`20260911080427`, commit `f774768`).
Said so rather than reporting compliance as if I had authored under the rule. The rule still lands
on the artifact, so I audited the form rather than asserting the guards were fine — which is the
refinement's actual point, and the one that caught `backend-8` on its own file.

**Named and classified, not blanket-cleared.** All three in-migration guards are **count-shaped**
(`count(*)` into int, `IF n <> expected RAISE`), so none can test NULL and all fail closed.
Substance differs:

| guard | shape | substance |
|---|---|---|
| `v_legacy <> 0` | count | **adequate** — absence keyed by policy name, the right key |
| `v_forall <> 0` | count | **adequate** — absence keyed by `polcmd`, the right key |
| `v_read <> 1` | count | **UNDER-SPECIFIED** — arity only |

`v_read` counts SELECT policies and **never inspects the predicate**, so a policy named anything
carrying `USING (true)` satisfies it. **It would not have caught the defect this ticket exists to
fix.** Exactly the failure the refinement predicts. Recorded rather than quietly corrected.

**Two discrimination pairs, because a single raise is not evidence.**
* **Predicate (P7):** same join, same schema, two expected values — `pg_get_expr(polqual) =
  'is_admin(auth.uid())'` → **1**; `= 'true'` (the old defect) → **0**. The comparison really
  compares.
* **Role (P8):** same query, same schema, same session — `postgres` (owner, RLS-exempt) → **1**;
  `authenticated` non-admin → **0**. This one matters most here because **zero rows is both the
  pass condition and what a dead test returns.** They differ, so P1 is measuring something.

**P4 was passing for a reason I had not checked — my own T-055 trap.** It claimed to test the three
new write policies. It does not. Captured the SQLSTATE instead of trusting the handler: **42501
permission denied**, and `has_table_privilege('authenticated','public.role_grants','INSERT')` =
**false** (`relacl` grants `authenticated` only `r,m`). **The denial is at the GRANT layer; the RLS
write policies are never reached.** No role on this project holds the write grant while remaining
subject to RLS, so those three policies are untestable here and belt-and-braces by design — which
the migration already said, but P4 implied evidence it never had.

Its original form also caught only `insufficient_privilege or check_violation` and would have
passed on an **uncaught FK violation** — reachable, since `role_grants.role` is FK → `roles` and
`user_id` is FK → `auth.users`, and my first P4 used a uuid absent from `auth.users`. Rewritten to
capture and report the SQLSTATE so a future run cannot pass unexamined. Re-measured both scenarios:
42501 in each, so the original verdict was right — **but it was right by luck, not by construction,
and that distinction is the whole rule.**

Nothing unguarded as a result: the behavioural probes P1/P2 assert the predicate's **effect**, which
is strictly stronger than any catalogue text match, and T-079 §4 makes the behavioural assertion the
criterion with catalogue reads as diagnostics. P7 is where `v_read` should have been; it lives in the
re-runnable pack because the migration has landed.

No migration change. Probe pack updated and committed **`c54b497`**; guard shapes now classified by
name inside the file. Not pushed, not released.

### 2026-09-11 — KAN-178 AC5 APPLIED: definer AND relocate, one transaction (T-079 Am. 3)

**Correcting my own earlier framing first.** I reported the INVOKER-helper problem as a discovery
needing a `cto` ruling. It was already **AC5 on this ticket**, in the "SCOPE WIDENED" section, sized
into `backend-3`'s Work Effort. **I read the ticket as ending at AC4.** The measurement was right;
treating it as new was not, and it cost an escalation that had to be withdrawn.

Applied: ledger **`20260911081512`**, commit **`8bf9595`** on `Canary`.

**The ruling that changed the shape**, and it is why definer-only would have been worse than the bug:
as INVOKER these hold `anon` EXECUTE but leak nothing, because RLS applies to the caller. As DEFINER
they bypass RLS, read `role_grants` in full, **and still take a caller-supplied uuid** — so
`/rpc/is_venue_admin` as `anon` would disclose whether an arbitrary user holds that role. That is the
T-070 identity-parameter oracle KAN-188 closed for five siblings. **I would have opened it on two
more.** Definer-first opens the oracle; relocate-first leaves them answering false. One transaction.

**Containment is the reverse of the usual and easy to get backwards.** EXECUTE **kept** for `anon`
and `authenticated`; `util` withholds USAGE. PostgREST resolves an RPC **by name** → needs USAGE →
closed. A policy qual stores the **OID** and resolves no name → only EXECUTE is checked → still runs.
Revoking EXECUTE instead reproduces KAN-188's `42501`.

**The §6d sweep is the step that mattered, and it was the overload trap again.** Swept `pg_proc`
across every schema, `pg_policy`, views/matviews and CHECK constraints. The three plpgsql callers
(`rpc_booking_cancel`, `_hold_for_game`, `_hold_for_meetup`) all call
`public.is_venue_admin(auth.uid(), vid)` — the **2-arg** overload, schema-qualified. **Measured from
`prosrc`, not inferred from the name.** My first regex truncated at the nested `)` and showed only
`is_venue_admin(auth.uid()`, which reads exactly like the 1-arg; I widened the window rather than
act on it. Had I trusted it I would have "fixed" a break that did not exist, or worse, moved the
2-arg. `is_moderator` has **zero** callers anywhere.

**Verified live as `authenticated` after apply** — pre-state was both *reachable by name, returning
false*:

| | before | after |
|---|---|---|
| `util.is_venue_admin(uuid)` by name | reachable | **42501 permission denied for schema util** |
| `util.is_moderator(uuid)` by name | reachable | **42501** |
| `public.is_venue_admin(uuid)` 1-arg | reachable | **42883 does not exist** |
| `public.is_venue_admin(uuid,uuid)` 2-arg | reachable | **reachable, returns true** |

That last row is the over-reach guard, and it is in the probe pack as one.

**Identity preserved, asserted not assumed:** OIDs **20147 / 20148 unchanged** across the move, and
all **three** `storage.objects` quals verified rebound to `util.is_venue_admin`. `ALTER … SET SCHEMA`,
never `DROP`+`CREATE` — a new OID would have silently orphaned those quals. `proacl`, `provolatile`
(STABLE), `proconfig` and owner all carried through unchanged (T-058 / T-044).

**AC5's demonstration:** both still return **false**, and false is now the *true* answer rather than a
fail-closed artifact — 0 `moderator` and 0 `venue_admin` grants of 1 total row. I did **not** create a
grant to exercise the true-branch: that is a write to a permissions table. The RLS bypass is asserted
from the catalogue (prosecdef, owner, no FORCE) and exemplified behaviourally by `is_admin`, which has
identical properties and returns true for a non-admin caller. Said as an exemplar argument, not as a
direct demonstration, because it is one.

**Guards applied my own earlier lesson**: all count-shaped against stated expectations, asserting
**properties** (schema, prosecdef, overload arity, anon EXECUTE, OID equality) rather than existence.
Demonstrated failing pre-change — `expected 2 relocated functions in util, found 0`.

**Two of my calls approved on the record and quotable at PEER:** `TO authenticated` — cto says it is
*better than what it ruled*, since anon matches no permissive SELECT policy rather than evaluating
`is_admin(NULL)`, one fewer anon-reachable definer invocation, and it moots the recursion question
for anon. And the `FOR ALL` call — cto accepted that zero `FOR ALL` policies remaining is the stronger
end state.

**Operative constraint now discharged:** the bar on issuing a `venue_admin` or `moderator` grant is
lifted — that was conditional on this landing, and it has.

Committed my two files only; other seats' untracked migrations left alone. Not pushed, not released.
Jira transitions remain classifier-denied; `team-lead` moved this to `Back-end` and it is now ready
for `Peer-review` by another `backend-N`.

### 2026-09-11 — KAN-178 AC5 PEER FAIL (backend-6) accepted and fixed: `row_security=off`

**The FAIL is correct and I verified it rather than accepting it.** All five `util.can_*` siblings
are `prosecdef=true` with `proconfig = {search_path=public,row_security=off}`. Before the fix my two
were the **only** SECURITY DEFINER functions in `util` without it. After: **zero remain** —
`util_definer_without_rs_off` returns `[]`.

Applied: ledger **`20260911105846`**, commit **`f53a85b`** on `Canary`.

**What I actually got wrong, stated precisely.** `20260911081512` made both DEFINER and relocated
them, but **carried the invoker-era `proconfig` through verbatim**. T-058 discipline covers restating
what exists; **it does not prompt you to add what the ruling requires and the live body lacks.** That
is the gap, and it is worth naming because "restate from `pg_get_functiondef`" felt like sufficient
rigour and was not. The reviewer's sharper point: it was **undeclared** — my header flagged the `TO
authenticated` deviation explicitly and never mentioned `row_security` at all, so nothing told a
reviewer whether it had been considered and rejected or simply missed. It was missed.

**Why it is a FAIL and not a nitpick — demonstrated behaviourally, as a non-exempt role:**

| | result |
|---|---|
| `row_security` on (default) | read of `role_grants` returns **false** — silently filtered |
| `SET row_security = off` | **42501** "query would be affected by row-level security policy" — **raises** |

So without the attribute, the day any of the three owner-exemption conditions flips — and `T-079`
names `ALTER TABLE … FORCE ROW LEVEL SECURITY` as the one-line change that *looks like hardening* —
these two quietly answer `false` again. **That is precisely the regression AC5 exists to remove,
reintroduced silently, from the direction nobody watches.** The attribute is the guard against this
ticket's own bug returning.

**Guards: four of six assert things this migration does NOT change** — `prosecdef`, `search_path`,
`anon` EXECUTE, the 2-arg overload, and both OIDs. That is deliberate: `CREATE OR REPLACE` silently
drops whatever is not restated, so the properties the *previous* migration established are exactly
what a careless rework destroys. All count-shaped; demonstrated failing pre-change with
`expected 2 with row_security=off, found 0`.

**Declined to bundle a second change, and reported it instead.** The siblings carry
`search_path=public`; mine carry `public, pg_temp`. The FAIL names `row_security` only. **Quietly
folding a second undeclared attribute change into the fix for an undeclared attribute change is the
same defect twice**, and would make the diff assert something the review never agreed to. Raised as
an observation with the analysis the reviewer needs: `pg_temp` is last and both bodies fully qualify
`public.role_grants`, so the shadowing exposure is small — small is not zero, and it is the
reviewer's call.

Post-fix live: both `proconfig = {"search_path=public, pg_temp",row_security=off}`, OIDs 20147/20148
unchanged, `proacl` retained, three `storage.objects` quals still bound, 2-arg untouched, AC5
still `false`/`false`. Not pushed, not released; back to `Peer-review`.

## 2026-09-11 — KAN-140 PEER review (reviewer, not author)

**Verdict: PASS.** Recorded via `store.record_review_result('KAN-140', 15, 'backend-5', 'pass', ...)`
(task revision 15 -> 16). No Jira transition, no ownership change — Orchestrator handles closure.

- Live re-verification against `wtncuzcskpigqpmnxwws` (reads only, 0 mutations): no `public.bookings`
  reference; two-hop `INTO STRICT` join present; exactly 3 `ON CONFLICT DO NOTHING`; exactly 2
  `fn_platform_owner_id()` call sites; `prosecdef=false`; `proconfig={search_path=public, pg_temp}`;
  `proacl={=X/postgres,postgres=X/postgres,service_role=X/postgres}` (CREATE OR REPLACE, so ACL
  preserved by construction); `payment_intents_booking_id_fkey -> venue_bookings(id) ON DELETE
  RESTRICT` unchanged. Fix premise re-checked: `venue_bookings.venue_space_id` and
  `venue_spaces.venue_id` are both `NOT NULL` with enforcing FKs — the NULL branch genuinely cannot
  arise.
- Ran `supabase/tests/kan140/run.sh` myself in a disposable container: PRE-FIX raised exactly
  `42P01 relation "public.bookings" does not exist` with no ledger rows; POST-FIX raised no error
  with user/debit, platform/credit, venue/credit all present. The probe is demonstrated failing
  before it counts as passing.
- AC4: diffed the committed body against the prior definition (`20260911120529`). Only delta is the
  venue-resolution `SELECT` and its comment, plus a whitespace-only `$function$;` terminator with no
  catalogue effect.
- The two declared harness deviations (`commission_rules` missing `applies_to`/`percentage`;
  `wallets.user_id` legacy PK/FK blocking `fn_get_wallet`) are correctly NOT touched in production
  or in the migration — `T-072` Decision 2 excludes `fn_get_wallet` and the `wallets` redesign by
  name, and Decision 3 says KAN-140 is authored against current live state only.

**Caveat, reported not inferred:** the Atlassian MCP returned "We are having trouble completing this
action" on every `getJiraIssue` attempt, so KAN-140's live AC text is `not documented` to me — the
same failure `cto` recorded inside `T-072` Decision 3. I reviewed against the brief's enumerated ACs
and `T-072`'s binding shape ruling. If the landed AC text diverges from that, this review does not
cover the divergence.

**Dispatch feedback:** LOW effort was right for the judgement, but the verification (container run,
live catalogue sweep, body diff) is not low-cost work regardless of effort setting.
