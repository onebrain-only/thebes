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
