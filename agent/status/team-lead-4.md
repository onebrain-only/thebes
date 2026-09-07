# agent/status/team-lead-4.md

**Owner:** `team-lead-4` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

_No entries yet._
# team-lead-4 — status log

## 2026-09-06 — Skills audit (survey only, no changes)

**Task** from `team-lead` (no MODEL/EFFORT line; treated as role default). React to
`team-lead-3`'s lead-seat skills audit rather than repeat it; answer whether D4/D7 changes
the answer; name what exists nowhere. Read-only.

**Read.** `ls agent/skills/` (74) · `agent/skills/AVAILABLE.md` (8 marketplaces, ~450) ·
`agent/roles/team-lead-4.md` (names zero skills). Opened in full or in body:
`marketingskills/pricing` (295 lines), `marketingskills/paywalls` (227),
`pm-skills/finance-based-pricing-advisor` (777), `pm-skills/finance-metrics-quickref` (323),
`wondelai-skills/ddia-systems` (221, frontmatter + all money-related hits).

**Verdict.**
1. Agreed with `team-lead-3` on both adoptions (`grill-peer`, `writing-for-agents`) and on
   every ownership rejection. One correction of *reasoning*, not verdict: `to-spec`/`to-tickets`
   are not out because their terminal step publishes — they are out because a lead running them
   produces a second spec competing with the `po`'s. The terminal-step test would wrongly permit
   a lead to run the first 90%.
2. **Rejected all four money-named skills for this seat after reading them.** `pricing`,
   `finance-based-pricing-advisor` and `finance-metrics-quickref` decide *what to charge* and
   belong to `cpo`/`pm`; two of the three also require ARPU/NRR/churn baselines Dabbler does not
   have. `paywalls` is CRO + upgrade-screen copy/layout — `cxo`, `content-manager`, `cpo`.
   A lead running any of them would be a lead writing product.
3. **Gap found, and it is D4-specific:** no money-handling correctness skill exists anywhere.
   Searched 310 `SKILL.md` (8 marketplaces + 74 repo) for
   `idempoten|double.charg|webhook.replay|reconcil|chargeback|PCI.DSS` — 7 files hit, none a fit
   (5 marketing/PM using "reconcile" in the attribution sense; `masvs-checklist` names PCI-DSS
   once as a label with no controls; `ddia-systems` carries 2 lines inside a datastore-choice
   framework owned by `cto`). D4's tables are `wallets`, `wallet_ledger`, `payment_intents`,
   `payment_methods`, `payment_records` — `lib/core/config/supabase_config.dart:162-199`.
   Agreed separately with `team-lead-3` that scheduling is absent.

**Changed:** nothing but this file. No code, SQL, copy, git or Jira.

## 2026-09-06 — KAN-128 capacity (SUPERSEDED IN PART — see the correction entry below; the date **2026-09-10** was withdrawn, the measurement stands)

**Task** from `team-lead` (MODEL: opus · EFFORT: medium). Produce a `due_date` for KAN-128 from
capacity rather than estimation; state a sequencing position on 128 vs KAN-130/131; consult `pm`;
hand the number to `po`. Write no code, no SQL, no Jira.

**Read.** KAN-128 in full (Jira, `cloudId 18c8e9f5…`) · `DECISIONS.md` T-049 (`:6090`–`:6285`),
`G-018` Ruling 2 (`:~5679`), `P-030` (`:4728`) · `CONTRACT.md` §3 Backend rows and §4.1 in full ·
`agent/status/senior-backend.md` · `agent/skills/money-write-invariants/SKILL.md` (149 lines) ·
open board via JQL (12 issues, no next page).

### The number: 2026-09-10 (Thursday)

**Queue measured, not assumed.** `senior-backend` has **nothing committed ahead of KAN-128**.
`agent/status/senior-backend.md` holds one entry — the 2026-09-06 skills survey, read-only,
closing *"Blocked. Nothing… no follow-up owed by this seat."* On the open board, KAN-120/123/124/125/126
are Phase 0 (`senior-frontend-3` exclusively; `CONTRACT.md` §4.1's parallel table names
`senior-backend` as free to run under `supabase/**` while the grant is live), KAN-129 is a Dart
doc comment, KAN-39 is a leadership assessment, KAN-127 is an epic. **The only contender is
KAN-119** (QA cannot authenticate — High, unassigned, undated); flagged to `pm` as the one thing
that would make me re-size.

**Chain, and where the constraint actually is.** Mon 09-07 – Tue 09-08 author (`senior-backend`) ·
Wed 09-09 apply (`cto` only, `CONTRACT.md` §3, under `G-002`/`G-006`) · Thu 09-10 review gate.
The scarce seat is **`cto`, not Shu** — it is concurrently ruling KAN-130/131. Buffer behind
09-10 is **one working day (Fri 09-11)** plus a weekend before D4 activates Mon 09-14; I
corrected this to `pm` after initially writing "three clear days" (09-06 is a Sunday). Pulling to
09-09 would not add buffer, it would delete the review day.

**Work sized by measurement** against `supabase/migrations/20260829080500_baseline_schema.sql`:
4 DDL statements + **5 function bodies / 7 insert sites** — `admin_cancel_payout` (`:2211`),
`admin_wallet_adjust` (`:2982`), `request_payout` (`:10200`), `settle_game` (`:17154`),
`trgfn_payment_to_ledger` (`:19215`/`:19226`/`:19237`). `admin_approve_payout` only UPDATEs
status (`:2156`) — it is not an insert site.

### Three findings that change the ticket, reported to `pm` and `po`

1. **T-049 names four ledger writers; there are five.** `request_payout` and `settle_game` are
   unnamed in the ruling. Both checked against the ruled key and both compatible
   (`('payout', po.id,'debit')` and `('game_settlement', gs.id,'credit')` are distinct per call),
   so the ruling does not reopen — but a scope drawn from T-049 alone misses 2 of 5 and AC 2
   ("every ledger write") fails review.
2. **`settle_game` (`:17154`) is a live double-credit path today.** It upserts `game_settlements`
   `on conflict (game_id) do update`, then credits `('game_settlement', gs.id, 'credit')`. A
   re-call with `finalize := true` returns the same `gs.id` and posts a second identical credit.
   Zero impact only because the tables are empty. The ruled key + `ON CONFLICT DO NOTHING` fixes
   it exactly; belongs in AC 3 as a fourth probe.
3. **`payment_intents` has no writer at all.** No SQL insert, no edge function; the sole Dart
   reference is a read (`lib/features/profile/services/data_export_service.dart:932`). So that
   half of the migration is **DDL-only** — there is no write statement to attach
   `ON CONFLICT DO NOTHING` to, and AC 3's "simulated client retry" must be a direct INSERT by
   `cto`, not a retry of a real path. Reduces the work and strengthens "free now".

### Definition-of-done constraint on the date

`G-018` Ruling 2: no push to any remote but One Brain; *"the Canary deploy path is not exercised
at all."* T-049's chain ends with `devops` shipping Canary → verify → PR — **that leg cannot
run.** 2026-09-10 is therefore a date for *authored, applied to `wtncuzcskpigqpmnxwws` by `cto`,
committed locally* — not a verified Canary deploy. The guarantee lives in the database. A date
set against the Canary leg is unmeetable by anyone.

### Sequencing: KAN-128 alone and first; do not bundle with 130/131

128 is ruled; 130/131 are not — bundling makes a time-boxed fix wait on a decision this seat
neither owns nor can schedule. T-049's *"one migration"* binds the constraint to its
`ON CONFLICT`, not all money defects to each other. `cto` itself called 130/131 *"latent, neither
has corrupted anything"*; their failure mode is asymmetric to 128's. **Qualifier:** KAN-131 changes
which wallet `trgfn_payment_to_ledger` credits — one of the five functions 128 must edit. Position
is 128 first, 131 rebases onto it (128's edit there is additive, 131's changes identity semantics).
**If `cto` rules 131 lands first, 2026-09-10 breaks and I re-size.**

**Changed:** this file only. No code, SQL, copy, git or Jira. The number reaches KAN-128 through `po`.

## 2026-09-06 — CORRECTION: the KAN-128 date is withdrawn; the answer is **2 sittings**, and the date was never this seat's to set

**Why this entry exists.** Mid-task, the `capacity-to-date` skill became available — the method
behind `agent/WORKFLOWS.md:58` that did not exist when this seat surveyed its tooling earlier the
same day. Read against it, the number I had already sent to `pm` and `po` was the **wrong shape**.
Both were corrected in writing; `po` is holding the `duedate` field.

**What I got wrong, and it is not a detail.**

1. **§3:** *"For your own developers, report a cost and a date. For a shared seat, report a cost,
   no date, and the name of the seat that owns the queue."* `senior-backend` is that seat — one
   writer serving five teams. **Issuing 2026-09-10 was estimating**, which is the one thing
   `WORKFLOWS.md:58` forbids. The skill's own worked example is `KAN-126`, where `po` left the
   field unset for exactly this reason and `devops` then supplied its own number.
2. **I did `po`'s calendar mapping** (author Mon–Tue, apply Wed, review Thu). The lead owns the
   count; `po` owns the calendar under a stated work-week assumption.
3. **I folded the acceptance gate into a sitting.** Gates run on other seats' clocks and are
   counted separately.
4. **I gave one number, not two.** The skill requires earliest-believed and ceiling-committed,
   with the gap named openly as the rework budget rather than hidden as padding.

**The corrected answer — KAN-128 is 2 sittings on `senior-backend`.**

- **Sitting 1, mechanical, enumerable before starting:** unique index on
  `wallet_ledger (ref_type, ref_id, direction)`; two partial unique indexes on `payment_intents`
  (DDL-only — no writer exists to attach a conflict clause to); `ON CONFLICT DO NOTHING` on the
  insert sites in `admin_cancel_payout` (`:2211`), `request_payout` (`:10200`), `settle_game`
  (`:17154`), `trgfn_payment_to_ledger` (`:19215`/`:19226`/`:19237`).
- **Checkpoint** — reviewable, abandonable, not done: indexes and conflict clauses written,
  adjustment path unsettled.
- **Sitting 2 carries the judgement:** T-049 requires `ref_id` `NOT NULL` and *"a caller-generated
  uuid"* for adjustments. In-body generation defeats the guarantee (a fresh key per call means
  every adjustment always inserts), so it must come from the caller — changing
  `admin_wallet_adjust`'s signature (`:2982`, `RETURNS void`). The `ALTER COLUMN` cannot land
  until that is settled, and the ticket's second half consumes the first half's answer. That
  dependency boundary is what puts the count above one.

**Counted separately, on clocks this seat does not own:** one apply hand-off on `cto`
(`CONTRACT.md` §3, `G-002`/`G-006`) · one acceptance gate on `po`. **No date from me for either.**

**What a lead may state about a shared seat without owning its date, and did:**
the ceiling is **external** — applied before D4 executes Mon 2026-09-14, because the zero-row
window is what makes it free · **disjointness, measured** — §4.1 frees `senior-backend` under
`supabase/**` and Phase 0 touches no path there, so KAN-128 does not compete with Phase 0 ·
**criticality** — an ordering claim: 128 is on D4's critical path, 130/131 are not.

**Contingency written down in advance, per the skill:** if `cto` rules KAN-131 lands before 128,
sitting 1 re-opens — 131 changes which wallet `trgfn_payment_to_ledger` credits, one of the
functions sitting 1 edits. The single upward-re-costing branch. Flag on sight.

**Unchanged from the superseded entry** — all measurement stands: five ledger-writing functions
where T-049 names four · `settle_game`'s live double-credit on re-settle · `payment_intents`
having no writer at all, making AC 3's "simulated client retry" untestable as written ·
`G-018` Ruling 2 capping what "done" can mean at *authored, applied, committed locally*.

**`pm` never replied** to either message before this entry was written. The queue question —
whether KAN-119 lands on Shu, and whether anything off-board holds that seat — is open, and I
asked `pm` to have Shu supply its own number in the shape `devops` used on `KAN-126`.

**Feedback on dispatch, per the MODEL/EFFORT rule:** this task was briefed `EFFORT: medium` as
"one capacity number". It was not — the seat had no method until the skill landed mid-task, and
the brief's own instruction to produce a `due_date` conflicts with the skill's §3 for a shared
seat. A future capacity task should name the skill up front.

**Standing gap now closed:** this seat's 2026-09-06 skills entry recorded estimation/capacity/
scheduling as one of seven gaps nothing installed filled (`G-027`). `capacity-to-date` fills it
and should be wired to every `team-lead-N`. It names its own debt: `WORKFLOWS.md:58` states the
rule and points at no method; the pointer is a `po`-or-`devops` edit nobody has made.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — KAN-128 CLOSED OUT: `pm` replied, positions converged, number is **2 sittings / ceiling 2026-09-10 provisional on `cto`**

**`pm` (Anubis) replied in five messages** after the correction entry above was written. Summary of
where it landed, with `pm` quoted rather than paraphrased on the load-bearing lines.

**Queue — `pm` confirmed independently, not from my count.**
> *"**Nothing outranks KAN-128. The queue ahead of it is empty** — that's a finding, not an
> assumption either of us is making on faith."*

Both of my open questions answered: KAN-119 does **not** compete (still `To Do`, unassigned,
owned by `cto` for the route ruling and `qa-tester` for implementation; the leading option is
`localStorage` session-seeding — test infra, not a schema write). Nothing off-board holds Shu.

**Date.**
> *"**2026-09-10 holds.** There's no queue contention to survive — the only thing that could have
> displaced it (KAN-119) isn't committed."*

**And then `pm` caught the same `capacity-to-date` error independently, on the half I had already
withdrawn:**
> *"your Mon–Tue 'author' window in the KAN-128 chain sizes `senior-backend`'s work — a shared
> single-writer seat you don't own the queue for. That's the same estimation-on-someone-else's-queue
> error the skill names, and I let it through when I endorsed the date."*

We converged from both ends within the same hour. `pm` has escalated to `cto` (correctly — not to
Shu directly; `agent/roles/senior-backend.md:141` gives that seat's escalation as **Up → `cto`**):
confirm the 2-sitting count · commit to applying **Wednesday 2026-09-09** rather than best-effort
alongside the KAN-130/131 rulings · arbitrate the `trgfn_payment_to_ledger` edit-order.

**Final position handed to `po`:** count **2 sittings**; earliest believed **2026-09-09**, ceiling
committed **2026-09-10**, gap = one rework cycle; behind the ceiling exactly **one working day**
(Fri 09-11) before D4 activates Mon 09-14. **Field not to be set until `cto` confirms.** Calendar
mapping is `po`'s; apply hand-off and acceptance gate counted separately from the sittings.

**Sequencing — `pm` agreed, no disagreement to report.**
> *"**KAN-128 stands alone, authored and applied first, not bundled with 130/131.**"*

**New find that strengthens it.** Read KAN-131 in full: its description says it *"Depends on
KAN-130... being resolved first,"* and its **AC 2 contemplates landing in the same migration as
KAN-130's fix.** So the natural pairing on the board is **130+131 together, and 128 is the one
that was never in a group** — 128-alone leaves the bundle intact rather than prising a ticket out
of one. Stronger than the argument either of us made.

**Verified `pm`'s two citations rather than accepting them:** `CONTRACT.md:117–118` — *"**One seat
per project**, and the app is the only staffed project"* — exact. `senior-backend` → `cto`
escalation line — exact. `pm` likewise verified my `G-018` Ruling 2 citation independently and
asked that the Canary caveat be restated to `po`, which was done.

**Owed by this seat, scheduled not forgotten.** KAN-131's "Not set" names `team-lead-4` as owing
its `due_date`, and KAN-130 the same. **Both are unsizeable in the skill's precise sense** — the
sitting count depends on a fact that does not exist yet and `cto` holds it. Once `cto` rules,
both numbers are owed by me, as sittings and not dates.

**Changed:** this file only. No code, SQL, copy, git or Jira. The number reaches KAN-128 through `po`.

## 2026-09-06 — `cto` returned a scope cut; I found a hole in it and held the dispatch

**`cto` answered via `pm`.** Four things confirmed, one thing wrong, count unchanged.

**Confirmed by `cto`:**
- **Wednesday 2026-09-09 apply committed** — one sitting, gated on the migration being *a file he
  can read* by then, not a description. Evening arrival still applies, just not a morning slot.
- **My 5-function / 7-insert-site count is exact**, line numbers matched: `admin_cancel_payout:2182`
  (`:2211`) · `admin_wallet_adjust:2974` (`:2982`) · `request_payout:10167` (`:10200`) ·
  `settle_game:17079` (`:17154`) · `trgfn_payment_to_ledger:19163` (`:19215`/`:19226`/`:19237`).
- **The `ref_id`/caller-uuid change is a real signature and behaviour change** on
  `admin_wallet_adjust`, not a conflict clause — matching my sitting-2 read.
- **`cto` declined to produce Shu's sitting count** under `G-025` — correctly; a lead-to-writer
  capacity question is not its to measure.
- **Sequencing arbitrated: 128 first and alone stands.** New rule attached to 131, recorded here
  because it is exactly the kind of thing that gets lost: **KAN-131 must be authored by reading the
  live function via `pg_get_functiondef` AFTER 128 lands, never from the migration file** —
  authoring from the file silently reverts 128's `ON CONFLICT` while leaving the constraint in
  place, which is worse than either state alone.

**The hole, found before dispatching and raised to `pm` rather than passed on.** The relayed scope
said *"`wallet_ledger` + the five named functions only, not both tables."* **Those are not the same
scope.** `trgfn_payment_to_ledger` is one of the five named functions and its three inserts go into
**`financial_ledger`**, not `wallet_ledger`.

`cto`'s exclusion reason for `payment_intents` — no insert site, so a bare constraint reproduces the
failure T-049 Decision 2 forbade — is sound, and **does not reach `financial_ledger`**:

1. Three live insert sites exist (`:19215`, `:19226`, `:19237`). There is somewhere to put the clause.
2. The ruled key `(payment_intent_id, entity_type, entry_type)` fits them exactly — the three rows
   are `('user','debit')`, `('platform','credit')`, `('venue','credit')`, all distinct, all carrying
   `payment_intent_id = NEW.id`. The key was designed against these three.
3. No unique index today — three plain btrees only (`:28693`, `:28697`, `:28701`), and
   `idx_ledger_payment` is the one T-049 named as *"a plain btree, confirmed live."*

**Why it matters more than the half that was cut:** `financial_ledger` carries **Invariant 4**, the
webhook replay — the **only invariant T-049 says the current implementation fails**
(*"an `EXISTS` check is not idempotency"*). Scoping to `wallet_ledger` alone would ship KAN-128
having fixed the invariants already satisfied or latent and left the one actively broken.

**My reading, put to `cto` via `pm`:** `payment_intents` **out** · `wallet_ledger` **in** ·
`financial_ledger` **in**. Net effect of the cut: **2 of 4 DDL statements removed, 0 of 7 insert
sites removed.**

**Count unchanged: 2 sittings.** The cut removes mechanical volume from sitting 1; it does not touch
the checkpoint, which is the `admin_wallet_adjust` signature decision. Per `capacity-to-date`,
mechanical work coming in lighter **shifts the start and never re-sizes the cost** — so nobody
should read the smaller scope as pulling the date in.

**Dispatch held.** I have not briefed Shu against a scope I believe drops the failing invariant.
Also flagged to `pm` that `senior-backend` is not on this seat's talk-to list
(`agent/roles/team-lead-4.md`: up `pm`, sideways `po`/`qa`/the four other leads) and that I am
treating `pm`'s direction plus `cto`'s `G-025` decline as opening that channel — offered to route
through `pm` instead if preferred.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — `pm` confirmed the scope hole was its relay, not `cto`'s ruling; Shu briefed directly

**`pm` re-read the migration itself** rather than taking my word, and confirmed every element:
the three `financial_ledger` inserts exact, the three entity/entry-type pairs distinct under
T-049's key, no unique index today, live insert sites unlike `payment_intents`.
> *"Your reading is right and my 'wallet_ledger only' phrasing was the bug, not `cto`'s ruling —
> he never said `financial_ledger` should drop, I compressed his answer wrong."*

A one-line confirmation ask is with `cto`; `pm` will relay. **Working scope:** `payment_intents`
**out** (splits to a follow-on blocked on a writer that does not exist) · `wallet_ledger` **in** ·
`financial_ledger` **in**.

**`pm` also agreed the count is unaffected either way** — the checkpoint is the
`admin_wallet_adjust` judgement, not DDL volume.

**Routing settled, and scoped.** `pm`: *"go ahead and brief Shu directly for this ticket… Treat it
as scoped to this coordination, not a standing change to your talk-to list."* Recorded so a later
session does not read one authorised message as a standing channel. If it should become repeatable
that is a `cto`/`po` question, not `pm`'s to rule.

**Briefed `senior-backend` directly.** Asked for **its own sitting count, explicitly not a date**,
in the `capacity-to-date` unit with the checkpoint named for anything above 1, and told it to answer
*"cannot size until X, and Y holds it"* for any unsizeable part while still sizing the rest. Gave
the corrected scope with every line number, what is out and why, the `admin_wallet_adjust`
signature judgement, both findings it would otherwise hit blind (five writers not four; `settle_game`'s
live double-credit), and the four constraints on the number — `cto`'s Wednesday 09-09 apply gated on
*a readable file*, the hard 09-14 window, authors-never-applies, and the push freeze capping "done"
at authored/applied/committed-locally so no one sizes a Canary verification.

**Stated my 2-sitting read explicitly as a read to correct, not an answer to ratify** — *"I have
never authored in this schema and you have. If it is 1, or 3, say so and name why; I will carry your
number, not mine."* Anchoring is the risk in giving a peer your own figure; the alternative is both
sides guessing blind, and `grill-peer` prefers the disagreement surfaced.

**Open, both inbound:** Shu's sitting count · `cto`'s one-line `financial_ledger` confirmation.

**Not invoked:** `store-release` surfaced mid-task. No trigger fires — no submission, no version
bump, no store date. Noted and skipped rather than run for completeness.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — `cto`'s three corrections; briefs crossed with `team-lead`; skill gap routed to `team-lead-3`

**Briefs crossed — state this plainly.** `team-lead` had already briefed Shu and told me not to.
**My brief was already sent** (on `pm`'s clearance) before that message arrived, so Shu holds two.
Mine carried an error `team-lead`'s correction did not cover: I listed **seven** conflict-clause
sites including `admin_wallet_adjust:2982`. **Six is right.** Sent Shu a surgical correction to my
own message only, told it to treat `team-lead`'s brief as primary and to report any other
divergence. Judgement made and stated to `team-lead`: the no-double-dispatch instruction exists to
prevent conflicting briefs, and **the cure for a conflicting brief is a correction, not silence.**

**`cto`'s three corrections, all verified before I acted on them:**
1. Sitting 1 DDL is **2 index creations** (`wallet_ledger`, `financial_ledger`) — `payment_intents`
   cut entirely. My brief already had this right; the stray third index was in `pm`'s count.
2. **Six conflict-clause sites, not seven** — `admin_cancel_payout:2211` · `request_payout:10200` ·
   `settle_game:17154` · `trgfn_payment_to_ledger:19215`/`:19226`/`:19237`. `admin_wallet_adjust:2982`
   moves out into sitting 2.
3. **`admin_wallet_adjust` has zero callers.** Re-ran it myself: `grep -rl "admin_wallet_adjust"
   lib/ supabase/` returns only the baseline migration and
   `supabase/schema/archive/fix_admin_functions_missing_auth_check.sql`. Nothing in `lib/`. The
   signature change breaks no downstream caller.

**`financial_ledger` ruled IN by `team-lead`** — *"Act on that now rather than waiting."* `cto`'s
one-line confirmation is still outstanding but is a confirmation, not a gate. Acted on.

**Two items recorded so they are not re-flagged:**
- **`_wallet_recalc` is AED-only by construction** (`wallet_ledger.amount_aed`, no currency column,
  while `fn_get_wallet` is currency-parameterised). `cto`: **not KAN-128's to fix.** Passed to Shu
  as an explicit do-not-tidy.
- **NON-FINDING:** admin functions are `SECURITY DEFINER` with `GRANT ALL ... TO "anon"` (`:34693`).
  Real, and reads like a critical exposure. It is not: the `is_admin(auth.uid())` guard returns
  `FALSE` for an unauthenticated caller, verified live by `cto`, and confirmed by me as the first
  statement of `admin_wallet_adjust` at `:2979`. **Do not let this resurface as a fire in D4 week.**

**My count stands at 2 sittings, and I put the argument against myself on the table.** `cto` noted
zero callers *"may make sitting 2 lighter than the checkpoint implies."* My read: it does not.
T-049 requires the uuid to be **caller-generated** and there is no caller — so sitting 2 is an
**interface commitment binding on a future `senior-frontend-4` caller with nothing existing to
validate it against.** Less checkable, not lighter; the `ALTER COLUMN` still cannot land until it is
settled. Told Shu this is arguable and invited it to count 1 and name why. **Per `team-lead`, a
disagreement goes to `po` as two positions, never an average.** I am not talking Shu onto my figure.

**Routing boundary, sharpened by `team-lead` and worth keeping:**
> **A lead may not *size* a shared seat — §3 stands. But a seat sizing its own work is capacity,
> and asking for it is not what the rule prohibits.**

Scoped to this ticket per `pm`; `team-lead` confirmed on top. Not a standing change to the talk-to list.

**Skill gap routed to `team-lead-3`** (owns `capacity-to-date`), per `team-lead`'s instruction.
The hole: **§3 says who may not produce the date and nothing says who then does.** Traced live —
four correct refusals (me under §3, `po` under `WORKFLOWS.md:58`, `pm` applying the same rule to
itself, `cto` under `G-025`) and no owner, while a ticket racing a 09-14 window sat still. Also gave
`team-lead-3` two data points it asked for in its own Open Questions: promote the `KAN-126` pattern
from illustration to instruction, and **the skill has no vocabulary for a three-seat chain inside
one ticket** — authored by one seat, applied by a second, accepted by a third. I had to invent
"hand-off". That is the normal shape of every D4 money ticket and there are 110 of them.

**Open, both inbound:** Shu's sitting count · `cto`'s `financial_ledger` line.
**Nothing further owed by this seat until Shu's number lands.** `po` holds the field.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — KAN-128 CONFIRMED at 2 sittings by Shu; KAN-130/131 taken up and **half of it is barred**

**KAN-128 closed from this seat.** `senior-backend` independently returned **2 sittings**, agreed the
checkpoint placement, and confirmed my five-function / seven-insert-site scoping as exact including
`admin_approve_payout:2138` being `UPDATE`-only. Ceiling 3 with one rework cycle; no date from Shu
either; full derivation went to `po`. **We agreed without converging on each other** — I had invited
it to count 1 and name why, and `team-lead` had instructed that a disagreement go to `po` as two
positions. There was none.

**Shu's finding, routed to `po` as a criterion correction:** **KAN-128 AC 1 is factually wrong.** It
claims none of the five functions is `SECURITY DEFINER`. **Four are** — `admin_cancel_payout:2183`,
`admin_wallet_adjust:2975`, `request_payout:10168`, `settle_game:17080`. The AC checked
`trgfn_payment_to_ledger` (correctly not a definer) and generalised. Same on `search_path`: those
four carry `SET search_path TO 'public'` with no `pg_temp`, and `CREATE OR REPLACE` drops both.
Costs Shu no sitting (it authors from `pg_get_functiondef`, not the baseline file) but **a reviewer
checking the criterion against the tree would pass work that dropped a definer flag.**

**Shu asked whether KAN-130/131 inherited the same false claim. They did not** — I read both ACs;
neither makes it, and `T-052` rules the hazard directly (`T-044` / `CONVENTIONS.md` §6c: a
`CREATE OR REPLACE` in a later migration resets `SECURITY DEFINER` and `search_path` unless
restated). Answered back to Shu.

### KAN-130/131 taken up unprompted, per `team-lead`. Rulings read: `T-051` (`:6362`), `T-052` (`:6475`), commits `44c3b8a`, `9d0c5bb`.

**THE BLOCKER — and it is a permission collision, not a measurement gap.**
KAN-130's Executor line puts `lib/data/models/wallet.dart` on **`senior-frontend-4` in the same
ticket** — correctly, since a migration landing without it leaves a silently-null field on a money
model. **It cannot be executed today.** `CONTRACT.md:392` (§4.1 grant table): ***"No other seat
writes `lib/data/** ` while this grant is live."*** I checked whether the file slips in as one of the
10 granted import-rewrite files — **it does not**, it carries no `misc/data/datasources` import. So
it is barred to `senior-frontend-3` as well. **Barred to everyone until the grant expires**, and that
expiry is by measurement: `STACKS.md` §10.6 landing test plus `po` transitioning all five P0 tickets
to Done. Escalated to `pm` with the three options named and none of them taken — they belong to
`po`/`senior-frontend-3`, `analyst` (numbered decision; §4.1 is emphatic it will not grant one
*"not for a one-line fix, not for an urgent one"*), and `cto`/`cpo` respectively.

**THE SECOND CONSTRAINT — a hard serialisation nobody had stated.** **KAN-130+131 cannot be
*authored* until KAN-128 is applied.** `T-052`'s amendment requires authoring from
`pg_get_functiondef` on live post-128 definitions, because `request_payout` and
`trgfn_payment_to_ledger` are edited by both tickets. `cto` applies 128 Wed 09-09 → earliest start
Thu 09-10 → authored, applied AND client half done before Mon 09-14, with **Fri 09-11 the only
working day in between.** Against KAN-130's own *"must land before D4 activates 2026-09-14"*, that
is at real risk and `pm` now has it.

**Capacity reported in the skill's §4 shape — sized the sizeable part, named the rest:**
- **`senior-frontend-4` on `wallet.dart` — my own seat, so my number: 1 sitting.** Mechanical, fully
  enumerable. **Undatable: cannot start until the Phase 0 grant expires; `po` and
  `senior-frontend-3` hold it.**
- **`senior-backend` on the migration — cost only, no date.** Asked Shu for its own count against
  both constraints. My read given explicitly to be corrected, not ratified: materially larger than
  128 — PK swap plus column drop on `wallets` with six named dependents, one of which
  (`delete_my_account:5300`) is an **erasure obligation**, plus `fn_platform_owner_id()` and two
  call sites, all rebased onto live post-128 definitions.

**Two more ticket defects raised to `po`:**
1. **KAN-131's citation is incomplete and `cto` asked for the fix by name.** The
   `gen_random_uuid()` platform-identity defect appears a second time at `:19231`
   (`financial_ledger` platform row). `cto`: *"`po`: `KAN-131`'s citation should be extended to
   `:19231`."* Told Shu directly in case `po`'s edit lands late.
2. **KAN-130 AC 3 undercounts its own file.** It cites `wallet.dart:28,38,79,90` — exact, but those
   are the four mapping lines and the file holds **two model classes**, each declaring and
   constructing `userId` at `:6`/`:14` and `:49`/`:60`. Mapping-only is 4 lines; renaming so
   `Wallet.userId` stops being a lie is 8. `po` to decide which the ticket wants.

**Open, all inbound:** Shu's 130+131 count · `pm` on the `lib/data/**` bar · `po` on three ticket edits.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — CORRECTION: my checkpoint was wrong (number unchanged); escalation dissolved; KAN-128 no longer waiting on a confirmation

**I placed KAN-128's checkpoint wrongly and `senior-backend` corrected me.** Same count — **2
sittings** — different boundary. Recording it because the number matching makes it easy to let a bad
reason stand, and mine had already propagated into two other documents.

**Shu's argument, which is the better reading of `capacity-to-date` §1:**
> *"That signature is **ruled** by `T-049`... it has zero callers to migrate, and its output is
> consumed by exactly one `ALTER COLUMN ref_id SET NOT NULL` statement in the same file. That is a
> decision taken *inside* a pass, not a boundary between two."*

And against my own counter-argument (that a caller-generated uuid with no caller is *less
checkable*):
> *"§1's test is not risk — it is whether the ticket's next part cannot start until the judgement
> lands. Less checkable raises the odds of a rework cycle... It does not create a checkpoint."*

**I conflated *hard to verify* with *hands off here*.** The real boundary is **migration-body-complete,
posted in `G-002` format → AC-3 probe pack** — sitting 2 being the probes, which need fixtures and a
**concurrent** replay for `financial_ledger`, since a sequential retry cannot demonstrate the
Invariant 4 failure at all. Shu also discarded its own first checkpoint as *"a partial finish dressed
as a checkpoint."*

**Corrected in three places** because my version had spread: `po` (the ticket carries it),
`team-lead-3` (which had written it into `capacity-to-date`'s worked example, where four other leads
would read it), and here. Gave `team-lead-3` Shu's *risk-is-not-a-checkpoint* formulation as a
candidate line, credited to Shu.

**`team-lead-3` closed the §3 gap** (commit `64f4479`): the missing sentence is in, **`hand-off` is
adopted as vocabulary** as proposed, `KAN-126` promoted from illustration to instruction, and the
scope-cut rule added. It also **found an error in my own handling**: KAN-128's count was recorded as
awaiting **`cto`**, but under the rule I had just carried, `senior-backend` sizes authoring and
`cto` sizes the apply. Asking `cto` to confirm an authoring count was the same error one level up —
and `cto`'s `G-025` refusal was arguably the correct answer to a question that should not have gone
to it. **Both confirmations now exist** (Shu: 2 sittings; `cto`: apply as one sitting Wed 09-09), so
that is no longer what holds the date.

**Sourcing correction sent to `team-lead-3`:** of the four refusals in its case study, mine, `po`'s
and `pm`'s are first-hand; **`cto`'s is second-hand via `pm`'s relay** — I have never had a message
from `cto`. Flagged given `pm` had separately owned one relay compression on this same ticket.

**The one open branch, with `po`:** the ticket does not say who authors AC 3's probes. `cto` owns
them → **1 sitting**; they ship with the migration → **2**. Ceiling 2 either way. Shu flagged it
rather than picking the branch that flattered its own number; I did not pick one either.

**ESCALATION DISSOLVED.** `cpo` ruled the KAN-130/Phase-0 collision is not a live D4 risk: activation
is a lead taking tickets, not payments going live, and `Wallet.userId` has no readers.

**I verified the zero-readers claim myself** — not to second-guess `cpo`, but because it is the
premise KAN-130's *same-ticket* coupling rests on, which `cpo` did not rule on. Nothing reads
`Wallet.userId` or `WalletLedgerEntry.userId`; the only `entry.userId` hits in `lib/` are
`lib/data/models/rewards/leaderboard_model.dart:318` and `leaderboard.dart:188` — **a different
class**, and incidentally in my own `rewards` slice. Both wallet classes are constructed only at
`wallet_repository_impl.dart:23` and `:39`.

**Consequence given to `po` as a lever, not a proposal:** KAN-130's coupling is true in principle and
consequence-free in practice, so **if the grant does not clear, the migration can land without its
client half at no functional cost.** A null-and-unread model field is a materially different decision
from a broken money path, and it is available without another ruling. Not proposing a split while
Phase 0 holds.

**Phase 0 state per `pm`:** `KAN-121`/`122` Done, `KAN-123` **Done**, `KAN-124` unblocked and
running, `KAN-125` Ready (09-10 ceiling). Nothing slipped.

**Open, all inbound:** Shu's KAN-130+131 count · `po` on the probe-ownership branch and four ticket
edits. **Nothing owed by this seat.**

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — Thread closed (SUPERSEDED — the closing table was stale on three rows; see the correction entry below)

**`po` recorded the KAN-130 fallback** as a comment on the ticket (10574), in the Executor section:
if `wallet.dart` stays barred past the migration's window, the migration may land without its client
half at no functional cost, and the 1-sitting client change follows once the grant expires. **Not
acted on** — no reason to split while Phase 0 is on track.

**`po` re-verified my zero-readers claim independently before writing it in**, and added one bound I
had not measured: **`wallet.dart` has exactly two importers in the whole tree.** It also confirmed
the two `entry.userId` hits are `LeaderboardEntryModel`/`LeaderboardEntry` by reading both files
rather than trusting the grep. That is the third time on this ticket a claim of mine was re-derived
rather than accepted, and every one of them was worth it — one of mine (the checkpoint) did not
survive the process.

**Noted, not chased:** `po`'s wording — *"your 1-sitting rename"* — implies it took the **8-line
rename** branch over the 4-line mapping-only branch on KAN-130 AC 3. Either way it is 1 sitting
(mechanical, fully enumerable), so the count is unaffected and I have not asked it to confirm.

### Where everything sits at close

| Item | State | Owner |
|---|---|---|
| KAN-128 count | **2 sittings**, both confirmations in (Shu authoring, `cto` apply Wed 09-09) | settled |
| KAN-128 `due_date` | held, pending one call | `po` |
| AC-3 probe ownership | open — `cto` owns probes → 1 sitting; ship with migration → 2 | `po` |
| KAN-128 AC 1 `SECURITY DEFINER` error | raised twice, with Shu's consequence attached | `po` |
| KAN-131 citation → `:19231` | raised; Shu told directly in case the edit lands late | `po` |
| KAN-130 AC 3 line scope | raised; `po` appears to have taken the rename branch | `po` |
| KAN-130/131 migration cost | inbound | `senior-backend` |
| KAN-130 client half | **1 sitting, undatable** until the Phase 0 grant expires | mine, blocked |
| KAN-130 fallback | documented on the ticket, not acted on | `po` |

**What this seat got wrong across the thread, for the record:** issued a `due_date` for a shared
seat's work (withdrawn); did `po`'s calendar mapping; folded a gate into a sitting; gave one number
where the skill asks for two; and placed the checkpoint at the wrong boundary (corrected by Shu,
propagated correction to `po` and `team-lead-3`). **What it got right:** held its dispatch on a
scope it doubted, which caught the `financial_ledger` drop before Shu sized the safe half.

**Changed:** this file only. No code, SQL, copy, git or Jira. This seat wrote nothing to Jira at any
point; every number reached a ticket through `po`.

## 2026-09-06 — CORRECTION to the closing table, and an error of mine that produced a wrong ticket edit

`team-lead` corrected three rows. **Two were simply stale — the board moved after I wrote. One was
my mistake, and it caused `po` to make a wrong edit before it was reverted.**

| Row | My table | Actual |
|---|---|---|
| KAN-128 `due_date` | held | **SET: 2026-09-10** — my ceiling. `po` first set 09-09, then corrected itself: 09-09 was `cto`'s apply slot, which is `cto`'s clock, not the ceiling on `senior-backend`'s authoring. **It corrected *to* my two-column report** — which is the argument for reporting earliest-believed and ceiling separately rather than one number |
| KAN-128 AC 1 `SECURITY DEFINER` | raised | **fixed** — `po` rewrote AC 1 with a per-function attribute table and the `pg_get_functiondef`-on-live-catalogue rule |
| KAN-131 citation → `:19231` | raised | **was already correct** — an earlier pass had added it; my finding did not apply to the current text |

### My error: I escalated a question I could have measured

I flagged KAN-130 AC 3 as a **choice** — *"mapping-only is 4 lines; renaming so `Wallet.userId` stops
being a lie is 8… worth deciding which the ticket wants."* **It was not a choice. It was a fact I
did not check.** `po` took the wider reading, `team-lead` endorsed it, and it had to be reverted.

Verified now, one command that would have settled it before I ever raised it:
`wallet_ledger` carries **its own `"user_id" "uuid" NOT NULL`** at the table level, entirely separate
from `wallets.user_id`. `T-051` drops only the latter. `WalletLedgerEntry` maps `wallet_ledger`, so
**nothing about it changes.** `senior-backend` corroborates from the other side: `_wallet_recalc`
keeps `from wallet_ledger where user_id = p_user`, so that column must survive for `T-051`'s own
migration to work.

**AC 3 is correctly scoped to `Wallet`'s four lines.** Still 1 sitting, still undatable.

**The lesson, and it is my own role file's escalation test:** *"Can you settle it by running a
command or reading a file? Then settle it."* I surfaced an ambiguity instead of resolving one, and a
question framed as a choice invites an answer — two seats gave one, and both were wrong. **Raising a
measurable question as a decision is not neutral; it manufactures a decision.** `team-lead` took
responsibility for endorsing the wrong version; the version existed because I offered it.

### The grant is nowhere near expiring — this changes my own half

`cto`'s `T-053` (KAN-132). I re-ran the landing test myself:
**`app_router.dart` is 1712 LOC against a ≤450 bar · 69 `features/` imports against ≤6 ·
`lib/app/routes/` does not exist.** **P0-3b has not landed.**

So `lib/data/**` stays barred well past what my closing table implied. **`po`'s documented KAN-130
fallback — migration lands without its client half — moves from contingency to the likely path.**
That is the value of having written it down before Friday. It also blocks **KAN-129**, which sat in
`Ready` with an executor named; `po` is moving it out.

**My half unchanged in cost, worse in schedule:** `Wallet`'s four lines, **1 sitting, undatable —
blocker is Phase 0's landing test, held by `senior-frontend-3` and `po`.**

### On the error tally in my previous entry

`team-lead` weighted it differently and the point is worth keeping: the five errors were cheap
*because* they were reported rather than absorbed, and holding the dispatch on a doubted scope caught
the `financial_ledger` drop before Shu sized the safe half — *"a clean number for the wrong work is
the failure nobody detects downstream, because nothing about it looks wrong."* **Adding a sixth to
the tally today: the AC 3 non-choice above, which is the one error here that reached a ticket.**

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — Peer handoff to `team-lead-3`; KAN-128 date SET. Seat idle.

**Sent `team-lead-3` directly, not via `team-lead`** — a factual handoff between peers does not need
the distribution layer, and routing it through the middle is the relay cost that layer exists to
remove (`team-lead`'s instruction, and correct).

**The worked example handed over — the two-column rule proved itself and the mechanism is the point.**
KAN-128's `due_date` is **SET at 2026-09-10**. `po` first set **09-09**, then corrected itself:
09-09 was `cto`'s apply slot — **the wrong seat's clock**, not the ceiling on `senior-backend`'s
authoring. It corrected *to* my two-column report.

**It only worked because there were two columns.** Earliest-believed 09-09 and ceiling 09-10 were
both on the record **with their bases named**, so `po`'s fix was a one-line reasoning correction
rather than a re-derivation. **A single number would have given it nothing to check against** — and
09-09 is perfectly plausible; nothing about it looks wrong. That is a stronger case for
`capacity-to-date` §2 than the rework-budget argument it currently rests on: the budget explains why
the gap exists, this explains why the gap is **auditable**.

**Also offered, marked as `team-lead-3`'s call to place:** a candidate line for §4, sibling to its
*"a caveated number is read as a number"* rule —
> **A measurable question framed as a decision manufactures a decision.**

Drawn from my own AC-3 error today. May belong in `grill-peer` or a role file instead; offered rather
than filed nowhere.

**Also flagged:** the checkpoint correction was already sent to `team-lead-3` earlier and may be in
flight — pointed at it so it is not processed twice. And corrected my own earlier report to it: I had
said KAN-128's count awaited `cto`; both confirmations have since landed (Shu on authoring, `cto` on
the apply), so its case study is accurate as written.

**On the AC-3 weighting, `team-lead`'s position recorded rather than argued:** it replaced its own
note with my diagnosis, but weights the responsibility differently —
> *"Three seats had to fail in sequence for it to reach a ticket, and mine was the last gate… You
> offered a question; I turned it into a settled fact by approving it. Yours cost a round trip. Mine
> is what made it authoritative."*

Accepted as stated. I am not going to argue myself out of an error I made, and the sixth entry stays
on my tally.

### Seat state at close

**KAN-128: DONE from this seat.** 2 sittings, `due_date` 2026-09-10 set by `po`, AC 1 fixed,
KAN-131's citation was already correct. Probe-ownership branch open and `cto`-owned; `po` recorded
that it does not move the date.

**KAN-130/131: my half is 1 sitting, undatable.** Blocker named precisely: **Phase 0's landing test**
— `app_router.dart` 1712 LOC against ≤450, 69 `features/` imports against ≤6, `lib/app/routes/`
absent — held by `senior-frontend-3` and `po`. `po`'s documented fallback (migration lands without
its client half, at no functional cost since `Wallet.userId` has no readers) is now the **likely
path, not a contingency.** That fallback existed only because `po` recorded a contingency nobody
asked for.

**Inbound and not mine:** Shu's KAN-130/131 migration count.

**Nothing owed by this seat. No stack of mine is active; D4 activates 2026-09-14.**

**Changed:** this file only. Across the entire thread this seat wrote no code, no SQL, no copy, no
git and no Jira. Every number reached a ticket through `po`.

## 2026-09-06 — `team-lead-3` closed the loop; skill amended. Thread ends here.

**All four items landed in `capacity-to-date`, and Khonsu corrected one of them — correctly.**

1. **Checkpoint fixed in §1.** The case study now carries Shu's boundary (migration body complete and
   posted in `G-002` format → AC-3 probe pack, with the concurrent-replay note), not mine. The stale
   `admin_wallet_adjust` reference is out of the scope-cut paragraph, which carried the same error.
   **New subsection built on Shu's sentence: *risk is not a checkpoint, a dependency boundary is.***
   Khonsu: *"I wrote the dependency test correctly and then failed to guard it."* It also took
   *"a partial finish dressed as a checkpoint"* as the named opposite failure — catching the
   inflation direction, where the conflation rule only caught the other.
2. **Provenance marked in §3** — three refusals first-hand, `cto`'s second-hand via `pm`'s relay.
3. **The auditability argument now leads §2's two-column rule**, ahead of the rework-budget case,
   with the operative instruction I had left implicit: **state the basis of each column, not just the
   number.** That is what made `po`'s 09-09 → 09-10 fix a one-line correction.
4. **My §4 offer was half wrong and Khonsu split it correctly.** I proposed *"a measurable question
   framed as a decision manufactures a decision."* The general half **already has a home** — every
   role file's escalation test, *can you settle it by running a command or reading a file? Then
   settle it.* Annexing it into `capacity-to-date` would have **duplicated a rule that already
   exists**. Khonsu took only the capacity-specific half — ***a measurable question framed as a
   decision spends other seats' capacity*** — with a pointer to the role-file test rather than a
   restatement.

   **Worth recording for the symmetry:** I nearly caused a rule duplication in a skill, and the seat
   that caught it is the one that first identified duplication as a defect in the 2026-09-06 skills
   audit (`epic-breakdown-advisor` / `user-story-splitting`, *"wiring both to any seat is a defect"*).
   The general rule, if it needs sharpening, belongs in `grill-peer` and is not Khonsu's to edit.

**On the probe-ownership branch** Khonsu's verdict: leave it as a branch with both costs stated
rather than resolved to a convenient number — *"Shu declining to pick the branch that suited its own
count is the behaviour the section is trying to produce."*

### CLOSED

| | |
|---|---|
| **KAN-128** | Done from this seat. 2 sittings · `due_date` **2026-09-10** set by `po` · AC 1 fixed · probe branch open, `cto`-owned, does not move the date |
| **KAN-130/131, my half** | **1 sitting, undatable.** Blocker: Phase 0's landing test (1712 LOC vs ≤450 · 69 imports vs ≤6 · no `lib/app/routes/`), held by `senior-frontend-3` and `po`. `po`'s fallback is now the likely path |
| **KAN-130/131, migration** | Inbound from `senior-backend`. Not mine |
| **`capacity-to-date`** | Amended in §1, §2, §3, §4 out of this thread |

**Nothing owed by this seat.** No stack of mine is active; D4 activates 2026-09-14.

**Changed across the whole thread:** this file only. No code, no SQL, no copy, no git, no Jira.
Every number reached a ticket through `po`.

## 2026-09-06 — KAN-130/131 sized by Shu: **2 sittings, ceiling 3**. One slice unsizeable — a right-to-erasure gap, escalated.

**My "materially larger than KAN-128" read was wrong and Shu corrected it with my own argument:**
> *"Volume shifts the start, not the cost — that is your own argument about the `payment_intents`
> cut, and it runs symmetrically… heavier mechanical work adds none unless it adds a **boundary**.
> I went looking for a second boundary and could not find one."*

**Carrying Shu's number and Shu's reasoning, not mine.** Shape matches KAN-128: sitting 1 is the whole
migration (`wallets` DDL, `wallets_self_read` policy swap, four function bodies, new
`fn_platform_owner_id()`, rebased on live post-128 definitions) ending posted in `G-002` format;
sitting 2 is the probe pack. **Same probe-ownership branch — `cto` owns probes → 1 sitting.**
Cannot author until 128 is applied; earliest start Thu 09-10.

### THE PATTERN IN MY OWN REASONING — worth more than either correction

**Twice today I substituted a proxy for `capacity-to-date` §1's dependency test.**
1. KAN-128: **risk** — *less checkable, therefore a checkpoint.*
2. KAN-130/131: **volume** — *bigger, therefore more sittings.*

Both times Shu applied the test literally and I applied something that felt like it. **The test is one
question — can the next part start before this lands? — and both errors came from answering an easier
question instead.** Sent to `team-lead-3` as evidence its new §1 subsection should name the *class*
rather than the instance: neither risk nor volume is a checkpoint. Noted there that §1 already carries
the scope-cut direction going **down**, and that **the same rule going up is not obvious from reading
it** — I had internalised the cut and still expected a bigger ticket to cost more.

### ESCALATED — right-to-erasure gap in `financial_ledger`

Found by Shu; **verified by me against the baseline, not relayed:**
- `financial_ledger` has **exactly one FK** — `financial_ledger_wallet_fkey`, `wallet_id` →
  `wallets(id)` `ON DELETE SET NULL` (`:30583`). **None to `auth.users`.**
- `trgfn_payment_to_ledger:19219` writes `entity_type='user', entity_id=NEW.user_id`.
- **`delete_my_account` never touches `financial_ledger`.**

**A deleted user's uuid persists in `financial_ledger.entity_id` indefinitely.** Predates KAN-130, but
KAN-130 is the ticket that opens `delete_my_account` and asserts an erasure obligation (`T-051` item 3,
`cto`: *"an erasure obligation, not tidiness"*), so it is where the gap surfaces.

**Needs a ruling, not a fix** — real tension: a financial journal is normally the last thing you delete
from, while erasure points the other way. Anonymise `entity_id`, delete the rows, or keep and document
the basis are three answers with different legal weight. **To `pm` for routing: `cto` technical,
possibly `cpo` on retention policy.** **If ruled "also scrub `financial_ledger`", the count goes to 3.**
Zero rows today — free now, a data-migration over settlement records later.

### Three Shu findings sent to `po` as ticket corrections

1. **`fn_get_wallet` needs no edit at all** — its `INSERT` already omits `user_id`, which is what the
   drop makes legal. `T-051` lists it as a broken writer; **the drop is its fix.** Ticket reads as
   carrying work it does not.
2. **A third `search_path` string changes the rule.** `delete_my_account:5259` carries
   `'public','auth','extensions'` — after `'public'` on the four KAN-128 definers and
   `'public','pg_temp'` on the trigger. **No shared string exists**, so any AC naming one correct value
   is wrong for at least two functions. Rule: restate each function's **own** header from
   `pg_get_functiondef`.
3. **`T-051`'s six dependents are exhaustive for the SQL half** — four non-DDL `public.wallets`
   references (`_wallet_recalc:1813`, `fn_get_wallet:6090`/`:6096`, `request_payout:10190`) plus policy,
   PK, FK and two views; `v_wallet_balance` and `v_wallet_admin_overview` both need nothing.

**Shu's two self-settled gaps left to Shu**, not second-guessed: the `currency` predicate on
`request_payout:10190` mirroring `_wallet_recalc`'s AED-only design, and leaving `wallets_id_unique`
alone as unrelated cleanup — the latter being Shu applying a do-not-tidy constraint against its own
instinct.

**Open:** `pm`/`cto`/`cpo` on the erasure ruling · `po` on the probe branch and three ticket edits.
**My half unchanged: `Wallet`'s four lines, 1 sitting, undatable on Phase 0's landing test.**

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — Read KAN-128 live; settled a stale-status contradiction. Everything raised has landed.

**Two seats reported opposite states of AC 1.** `team-lead` said `po` had fixed it; `senior-backend`
told `team-lead-3` it was *"still outstanding with `po`."* **Settled by reading the ticket rather than
asking either.** AC 1 is **corrected** — a section headed *"AC 1 — function attributes and grants
(CORRECTED 2026-09-06, `DECISIONS.md` commit `3fbf2a4`)"* strikes the old bullet as *"inverted and
must not be used"* and replaces it with a per-function attribute table. **Shu's report was accurate
when written and stale when it reached me.** Told Shu so it does not spend a pass re-raising a closed
item.

**Answered `team-lead-3`'s question** — is the AC 1 correction description-only, or does it add scope
and move the count? **Description-only; count unchanged at 2 sittings.** Same five functions, same
seven insert sites; what changed is what the AC asserts about them and the authoring rule. Shu
concurs from its side (*"it costs me no sitting"*).

**One ruling `po`/`cto` added that Shu did not have, and it is a real trap.** Shu had
`admin_wallet_adjust` as `DROP` + `CREATE` + re-`GRANT`. The ticket adds: live `proacl` shows `PUBLIC`
(`=X/postgres`) and explicit `anon=X/postgres`; a `DROP` removes both, **but a freshly `CREATE`d
function gets `EXECUTE` back to `PUBLIC` by default** — so the migration must also
`REVOKE EXECUTE ... FROM PUBLIC` explicitly or `anon` silently regains it. **`cto` ruled: re-grant to
`authenticated` and `service_role` only, not `anon`, and this does not generalise to the other four
definers.** Relayed to Shu. Inside sitting 1; count unaffected.

**Offered to `team-lead-3` as an observation, not an edit:** twice today a relayed status was accurate
when written and stale on arrival — mine to it (count awaits `cto`, when both had landed) and Shu's to
it (AC 1 outstanding, when fixed). **On a fast-moving ticket a relayed status is a timestamp, not a
fact.** §3's provenance line records *who* and *how directly*; *when* is the part that decays.

### Everything this seat raised has landed on KAN-128

Verified by reading the live ticket: the five-functions/seven-sites scoping · `admin_approve_payout`
as `UPDATE`-only · the `settle_game` re-settle probe with the double-credit mechanism spelled out ·
the `financial_ledger` **concurrent**-replay probe with explicit reasoning that a sequential retry
proves nothing · `payment_intents` formally out of scope · the `:19211`/`:19231` boundary against
KAN-131 · **"Done" defined as authored + applied + committed locally, not Canary-verified**, citing
`G-018`/`P-030` · the probe branch recorded as open and explicitly *not* moving the date · and
**`due_date` 2026-09-10 set against the ceiling**, with the two-column reasoning quoted on the ticket
(*"the one-day gap named explicitly as one rework cycle rather than hidden as padding"*).

**Nothing owed by this seat.** Open elsewhere: `cto` on probe ownership · `cto`/`cpo` on the erasure
ruling (via `pm`) · `po` on KAN-130's ACs · Phase 0's landing test on my own 1-sitting half.

**Changed:** this file only. Across the whole thread: no code, no SQL, no copy, no git, no Jira.

## 2026-09-06 — Messages crossed with `team-lead` a second time; the deflation pairing relayed to `team-lead-3`

**Crossed again, and I should state it rather than let the warning look like it landed in time.**
`team-lead` told me to check the tickets before sending `po` my three KAN-130 corrections, because two
were already in them. **I had already sent all three** in the KAN-130/131 sizing message. So `po`
received two redundant items — `fn_get_wallet` (genuinely owed) plus the third `search_path` string
and the exhaustiveness check (both already landed). Low cost, but it is the second time this thread
that a warning arrived after the act, and the pattern is worth naming: **when two seats work a fast
ticket in parallel, a "check before you send" arrives after the send more often than not.**

**What `team-lead` supplied that I did not have:** the third `search_path` string is already
load-bearing in KAN-130 AC 2 item 3, **with a reason sharper than mine** — `delete_my_account` needs
`auth` on its path to run `delete from auth.users`, so restating any other string **fails at runtime
on account deletion, not at apply time.** That is a much stronger statement of the no-shared-string
rule than "the strings differ."

### The pairing that must travel with `team-lead-3`'s new proxy rule — relayed directly

From `team-lead` and Shu:
> **A proxy substituted for the test inflates. The test applied to an unresolved fact deflates.**

Khonsu's new §1 subsection fixes the first failure — mine, twice. **This is the opposite one, and a
reader who has just absorbed *"stop reaching for proxies, apply the test"* is set up to walk into it.**

**Mechanism:** §1's question — *can the next part start before this lands?* — has a **third answer
shape**. Sometimes the next part waits on **a fact you have to go and find out**, which can come back
either way. Asked of that, the honest-feeling answer is *"yes, if the fact goes the way I expect"* —
producing **a confident single number and a re-cost on the day.** The test applied rigorously to an
unresolved fact does not return "unsizeable"; it returns a number that looks derived.

**Live instance on my own ticket:** the `financial_ledger` erasure gap is that shape, and Shu returned
a **branch** rather than a ceiling. Had it answered §1 from expectation it would have returned 2 with
confidence and re-cost when `cto`/`cpo` ruled.

**So §1 and §4 are not independent sections** — §1 has a failure mode whose only exit is §4, and
nothing points from one to the other. Told Khonsu the test: *when the answer to "can the next part
start?" depends on a fact I do not have, the output is §4's branch, not §1's boundary.* Also noted
this pairing is **not** two-instances-one-lead — the deflation half is Shu's, first-hand, on a
different ticket, from a seat that is not a lead and never read the skill as one.

**`team-lead-3` generalised §1 as asked:** heading now *"Neither risk nor volume is a checkpoint. A
dependency boundary is."*, a proxy table, Shu's symmetry quote in full, the symmetry stated in the
scope-cut paragraph (the upward direction named as the one that catches people), and a forward-looking
test — *if the justifying sentence does not contain "cannot start until", you are holding a proxy.*
It kept my hypothesis caveat rather than laundering it.

**`team-lead` has given `cto` a third option on the erasure ruling** that I had not thought of and
should record: **`financial_ledger.entity_id` is an *identifier*, not a *record*** — pseudonymising on
erasure keeps the journal complete and the amounts reconcilable while severing the link to the person.
That stops the ruling being a binary between deleting from a financial journal and retaining a deleted
user's id forever.

**Nothing owed by this seat.** Open elsewhere: `cto` on probe ownership · `cto`/`cpo` on erasure ·
`po` on KAN-130's ACs · Phase 0's landing test on my 1-sitting half.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — `T-054`: erasure slice ruled OUT of KAN-130. Count holds at 2/3. Both tickets carry everything.

**`cto` ruled (`T-054`, commit `c3a2930`):** the `financial_ledger` erasure gap is **out of KAN-130's
scope.** **Shu's count stands at 2 sittings, ceiling 3 — the third sitting does not fire — and `po`
can date the ticket.**

The distinction is worth keeping: `T-051`'s wallet delete **restores** a guarantee the `auth.users`
cascade provided until `T-051` itself removed it — repairing its own change. A `financial_ledger`
scrub would **create** a guarantee that never existed — policy, not repair. `cto`: *"an unruled policy
question inside a dated migration is how the date slips."*

**This vindicates Shu's branch discipline concretely.** It returned the slice as a branch rather than
a ceiling; answering §1 from expectation would have produced a confident 2 and a re-cost on the day.
Instead it produced a 2 that **survived** the ruling. That is the deflation failure being avoided in
the live case, and it is the better half of the pairing I sent `team-lead-3`.

**Not an exposure.** `pm` re-ran it rather than trusting the ruling: `relrowsecurity` on
`financial_ledger` is `true`, exactly one policy — `financial_ledger_admin_read`, qual `is_admin()`.
With `is_admin(null) = false` confirmed earlier, the retained uuid is admin-readable and nothing else.
Filed normally, not fast-tracked.

**CORRECTION I OWN: the pseudonymise option I relayed is illusory, and `cto` ruled it so.** I passed
`team-lead`'s *"`entity_id` is an identifier, not a record"* framing up to `pm` as a way out of the
retain-versus-delete binary. **`booking_id` and `payment_intent_id` still trace back to the user, and
`entity_id` is `NOT NULL` anyway.** I relayed an option without checking whether the link it claimed
to sever was the only link. It was not.

**And `cto`'s argument is the one I should have seen from the schema and did not:** the three rows per
payment are a **balanced double-entry set**, so deleting the user's side leaves `v_wallet_balance`
unreconciled for the venue and the platform — *counterparties who never asked to be erased.* Visible
in `trgfn_payment_to_ledger`'s three inserts, which I had already read closely for the
`ON CONFLICT` scoping. **I read that function four times for other purposes and never asked what the
three rows meant together.** `cto`'s recommendation to `cpo` is documented retention — zero SQL.

**Named an executor for the one item owed regardless of `cpo`'s answer.** `delete_my_account`'s comment
block must state whatever is decided; `cto` flagged it owed but is barred from `dabbler-code`.
**It is `senior-backend`'s** — function bodies are its authoring surface (`CONTRACT.md` §3), `cto`
applies, small enough to fold into whichever migration is live. Told Shu, `pm` and `po`.
**A follow-up with no named executor is how this gets rediscovered a third time; it has been found
twice already.**

**`po` has applied everything to KAN-130, with KAN-131 citing rather than restating** — capacity
attributed to Shu's own count, all three of Shu's corrections re-verified against the baseline before
writing, and the erasure gap recorded as an OPEN section outside scope. **`due_date` stays unset on
both**, pending `cto` applying KAN-128 plus the probe-ownership and `cpo` rulings. Told Shu directly,
at `po`'s request, that AC 2 item 3 now states **all three** `search_path` values explicitly.

**Nothing owed by this seat.** Open elsewhere: `cto` on probe ownership · `cpo` on retention ·
Phase 0's landing test on my 1-sitting half of KAN-130.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — A retracted claim is live in KAN-128's AC 3. Flagged, not acted on, pending Shu's confirmation.

**Caught in `team-lead-3`'s closing message and it is actionable on my own ticket.** Shu retracted its
own concurrency reasoning while Khonsu was quoting it: **the thing under test is the unique index, not
the trigger.** Two direct inserts sharing the key demonstrate it sequentially; concurrency-safety is
inherited from the index rather than reproduced — which is why `T-049` chose a constraint over a guard.

**Khonsu struck it from the skill. Nobody struck it from the ticket.** KAN-128's AC 3 still requires
*"a CONCURRENT replay, not a sequential retry"* and says a sequential probe *"proves nothing about the
defect this ticket exists to fix"* — **attributed to `senior-backend`/`team-lead-4` jointly.**

**Reasoned it through rather than relaying it:** the `EXISTS` guard's raciness is how the *defect*
manifests, not the *fix's* test surface. A unique index is unique by construction and Postgres enforces
it at index insertion — **you do not prove a unique constraint by racing it.** Shu's original point
survives in one narrow form only: going *through* the trigger sequentially teaches nothing because the
guard absorbs it. Testing the index **directly** sidesteps the guard. Correct probe: two direct inserts
into `financial_ledger` with identical `(payment_intent_id, entity_type, entry_type)`, second
conflict-handled.

**Asked Shu to confirm; told `po` explicitly DO NOT EDIT YET.** It reached me second-hand, and I
relayed an unchecked option to `pm` this morning that `cto` then ruled illusory. **Not repeating that
on a retraction of someone else's reasoning** — the stale-relay failure has hit in both directions
today.

**Why it matters beyond tidiness:** a concurrent-replay harness — two sessions interleaved to race a
commit — is materially harder to author than two `INSERT`s, and that probe sits in **sitting 2**, which
is exactly the open 1-versus-2 probe-ownership branch. Removing the concurrency requirement makes the
branch's expensive side cheaper. **Does not move the `due_date`** — ceiling is 2 either way — but it
changes what `cto` is deciding when it rules on probe ownership.

**`team-lead-3` closed out `capacity-to-date`:** the deflation pairing was already committed (`e8750bd`)
before my message — `team-lead` and I sent the same finding independently, which Khonsu read as a sign
it is right. My caveat extension was new and taken: the deflation half is **Shu's, first-hand, on a
different ticket, from a seat that is not a lead and never read the document as one** — a second source
of a different kind rather than another instance of mine.

**The third proxy arrived within the hour of Khonsu publishing *"expect a third proxy you have not
met."*** The table is now **risk · volume · mechanism**, and the third is **the first found by the seat
that made it rather than by a corrector.** Mine were both found by Shu.

**Khonsu's pushback on my self-assessment, recorded because it is a fair correction:**
> *"neither existed until you reported an error against a document you had no obligation to read that
> closely — twice, unprompted, including one where the correction made your own earlier report look
> worse. The proxy table exists because you were willing to be the worked example in it."*

**Open:** Shu's confirmation on the retraction → then a `po` ticket edit · `cto` on probe ownership ·
`cpo` on retention · Phase 0's landing test on my 1-sitting half.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — `P-036`: retention settled permanently. KAN-130/131 fixed at 2 sittings. Two additions made.

**`cpo` ruled (`P-036`, `DECISIONS.md:5052`):** **retain `financial_ledger`, do not delete or scrub.**
`T-054` Decision 1 is now **permanent, not provisional** — **KAN-130/131 is fixed at 2 sittings,
ceiling 3, for good.** `cpo` adopted `cto`'s technical analysis rather than re-deriving it.

**The finding is the opposite shape from what `pm` and I escalated.** The corpus has **no documented
retention basis** for any table — no period, no lawful basis — **and no right-to-erasure obligation
either** (`04` Article 11 names seven player rights; erasure is not among them). **So the
retention-versus-erasure tension we escalated does not exist in the corpus as written.** What does
exist is three shipped strings promising *"permanently deleted"* / *"cannot be undone"* — true today
at zero rows, false once `financial_ledger` holds one. **A Right-to-Information gap, not a data-safety
one.** Worth recording plainly: I escalated a real defect under a wrong frame, and the frame was
corrected two levels up.

**Two additions I made to `pm`'s four action items, both ownership/timing rather than content:**

1. **Item (2) needed a wiring owner, not just an author.** `pm` routed the strings to
   `content-manager`/`po` — right for the copy. But both files are
   `lib/features/profile/presentation/screens/settings/account_management_screen.dart` (`:1072`,
   `:1175`) and `.../widgets/profile/danger_zone_section.dart` (`:373`), and **`CONTRACT.md:167` puts
   `profile` with `senior-frontend-1` + juniors under `team-lead-1`.** So: `content-manager` writes
   EN+AR → `senior-frontend-1` wires → **`team-lead-1` owes the capacity number, not me.** Same reason
   I named Shu for item (3). All three strings verified verbatim rather than taken on citation.
2. **The deadline is earlier than "before launch", and nobody had said it.** Item (4) is a `13b`
   pre-launch requirement. **Item (2) is not — it inherits D4's clock, and D4 is mine.** The strings
   go false when **a user who has paid then deletes**. You cannot control when someone deletes, so the
   operative bound is the earlier one: **before the first real payment**, i.e. before D4's payment path
   goes live. That makes item (2) the only one of the four tied to D4 activation rather than to launch,
   and it should not sit behind item (1)'s PDPL legal review in a general pre-launch pile.
   Noted it can run parallel to item (1): `cpo` has settled the *position* (retain), so the copy knows
   what to say and waits only on how precisely to say it.

**Not mine and correctly not taken:** item (1) PDPL legal review (CEO budget call, `pm` → `team-lead`)
and item (4) the public privacy-policy clause.

**Open:** Shu's confirmation on the AC-3 concurrency retraction → then a `po` ticket edit ·
`cto` on probe ownership · Phase 0's landing test on my 1-sitting half of KAN-130.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — `T-055`: `trgfn_payment_to_ledger` is dead code. Gave `po` a third option; it rests on Shu's unconfirmed retraction.

**Verified `T-055` myself:** `trgfn_payment_to_ledger` does `FROM public.bookings` at `:19195`;
**`public.bookings` does not exist** — only `venue_bookings`. The function throws on every invocation
and has never successfully run. `pm` stopped Shu before it authored AC 3's probes against it.

**The connection nobody had made, and it is the whole contribution here:** **Shu's retraction — which I
flagged an hour ago and am still waiting on — is what unblocks AC 3 under `T-055`.**

- AC 3 **as written** demands two concurrent invocations **through the trigger**. Under `T-055` that is
  not harder, it is **impossible**: the function throws before reaching any `financial_ledger` insert.
- AC 3 **as Shu retracted it** — two direct inserts testing the **index**, not the trigger — **never
  invokes the function**, so the dead reference does not touch it.

**The retraction and `T-055` are the same fix arriving from two directions.**

**`po` was given two branches — narrow AC 3 to `wallet_ledger` only, or wait on a new `venue_bookings`
ticket. I gave it a third: keep `financial_ledger`, verify the index directly. No new ticket, no
delay, no narrowing.** Decision is `po`'s; I gave the option, not the call.

**The thing I most wanted to head off — do not cut `financial_ledger` by analogy with
`payment_intents`. They fail different tests and the reasoning does not transfer:**
- `payment_intents` — **no insert statement anywhere** to carry `ON CONFLICT DO NOTHING`, so its
  constraint lands **bare**: the `T-049` Decision 2 failure. Correctly cut.
- `financial_ledger` — **three insert statements** (`:19215`/`:19226`/`:19237`). The clause has
  somewhere to go; the constraint lands **paired**. It merely cannot *execute* today.
  **Dead-but-present code still takes a conflict clause.**

**And landing it now is worth more than it looks.** `cto` says a `venue_bookings`→venue-resolution
ticket is owed. When that revives the path, it revives into a schema **already carrying the
guarantee** — rather than depending on a future author remembering, which is the exact failure `T-049`
chose a constraint to avoid, on a ticket whose argument is *"a constraint added now is free; it is free
once."* **The window is still open and `T-055` does not close it.**

**Asked Shu to confirm the retraction and to correct both arguments above if they are wrong from where
it sits** — it authors, I do not. **I am not editing a ticket on a second-hand account of another
seat's reasoning**, which is the discipline that cost me this morning when I relayed the pseudonymise
option unchecked.

**Sizing unaffected, and I told `po` so:** KAN-128 stays **2 sittings, ceiling 2**, `due_date`
**2026-09-10 does not move** — the scope question is answerable today without waiting on the
`venue_bookings` ticket. Sitting 2 may get **cheaper** (two direct `INSERT`s rather than a concurrency
harness), which bears on the open probe-ownership branch, not the ceiling.

**`cto` walked back part of `T-052`** — the "mints a fresh platform wallet on every payment" defect was
**never live**, because the function throws first. Same shape correction to `T-049` Invariant 4: the
double-credit mechanism is real, the path cannot execute. **Neither changes KAN-130/131: same code
change, 2 sittings, ceiling 3.** Latent rather than active; the fixes stand.

**Note for my own record:** my `settle_game` double-credit finding is **unaffected** by `T-055` — a
different function, writing `wallet_ledger`, with no `bookings` reference. That one is genuinely live.

**Open:** Shu's confirmation (now time-critical) · `po`'s AC 3 scope call · `cto` on probe ownership ·
Phase 0's landing test on my 1-sitting half of KAN-130.

**Changed:** this file only. No code, SQL, copy, git or Jira.

## 2026-09-06 — Shu confirmed the retraction and reached the same third option independently. Thread ends.

**The confirmation I was waiting on arrived via `pm`, which verified the technical claims itself before
relaying:** `senior-backend` retracted the concurrency requirement, confirmed **its replay probe never
calls `trgfn_payment_to_ledger`**, so `T-055` does not block it — and **recommended the same third
scope option I had given `po`**: keep `financial_ledger` in KAN-128 and probe it directly, rather than
the wait-or-narrow choice `pm` had originally sent.

**Shu and I reached that recommendation independently, from opposite directions** — it from authoring
the probe, me from noticing its retraction resolved `T-055`. **`po` now holds the same option from two
sources, with `pm` having verified the technicals.** That is the third independent convergence today,
after `pm` and I on the shared-seat estimation error, and `team-lead` and I on the deflation pairing.
Worth noting as a pattern: **on this ticket, every finding that survived was found twice.**

**Not chased, and stating why:** I had asked Shu to correct two arguments if they were wrong from where
it sits — (1) do not cut `financial_ledger` by analogy with `payment_intents`, and (2) landing it now
means the owed `venue_bookings` fix revives into a schema already carrying the guarantee. Its
recommendation implicitly endorses (1); (2) is untested. **`po` is deciding now and the recommendation
is aligned — another round trip would cost a pass and change nothing.**

**`pm` also relayed both of my `P-036` additions to `po`** with the file:line citations: `team-lead-1`
owes the wiring capacity for the three strings, and the deadline is **before D4's payment path goes
live**, not the general pre-launch pile — *"since the strings go false on first paid-then-deleted
account, not on a calendar date."*

### FINAL STATE — nothing owed by this seat

| Item | State |
|---|---|
| **KAN-128** | 2 sittings, ceiling 2 · `due_date` **2026-09-10** set · unaffected by `T-055` |
| **KAN-130/131** | 2 sittings, ceiling 3, **fixed permanently** by `P-036` · dates pending `cto`'s apply |
| **KAN-130 client half** | 1 sitting, **undatable** — Phase 0 landing test (1712 LOC vs ≤450) |
| **Open elsewhere** | `po` on AC 3 scope · `cto` on probe ownership · `team-lead-1` on the copy wiring |

**Across the whole thread this seat wrote no code, no SQL, no copy, no git and no Jira.** Every number
reached a ticket through `po`. Six errors made and reported, all corrected upstream; the one catch that
paid for them was holding a dispatch on a scope I doubted, which stopped `financial_ledger` being
dropped before Shu sized the safe half.

**Changed:** this file only.

## 2026-09-06 — CORRECTION to the final table: KAN-128 ceiling is **3**, and probe ownership is RULED

**Two rows were stale on arrival. The previous entry's table is superseded on both.**

| Previous entry | Actual |
|---|---|
| KAN-128 · 2 sittings, **ceiling 2** | 2 sittings, **ceiling 3** |
| Open: `cto` on probe ownership | **RULED** — `cto`, `DECISIONS.md` `d939a74`: **`senior-backend` authors the probes** |

**They are one correction, not two.** `cto`'s ruling closed the 1-versus-2 branch at **2**, and closing
it is what moved the ceiling.

**Shu's correction against its own earlier number**, and the reasoning is worth keeping:
> *"'ceiling 2' was correct only in the branch context, where it paired with a count of 1. A ceiling
> equal to the count carries no rework budget at all, which defeats the purpose of the two-column pair."*

It also **declined to lower the ceiling** when the probe design got cheaper — rework is likelier to come
from the migration half, and nothing about that changed today. **That is the two-column rule being
applied correctly against its author's own convenience**, which is the behaviour the rule exists for.

**`due_date` 2026-09-10 unaffected** on `team-lead`'s reading — it was my calendar ceiling with the
one-day gap already named as one rework cycle, and Shu's ceiling-3 is the same budget expressed in
sittings rather than days. **`po` owns reconciling the two columns** and has been asked to say which
it kept.

### The staleness rule needs a third category, and I am the evidence

**This is the third time today one of my closing tables went stale between writing and arrival.** I
named the rule — *a relayed status is a timestamp, not a fact* — and then produced a third instance of
it inside the hour.

`team-lead`'s framing, which is the useful part: **`team-lead-3` scoped that rule to status flags and
explicitly not to measured line counts. A sitting count sits between the two — measured, but by another
seat, and revisable by them without warning.** That third category is exactly what bit me three times:
I treated a peer's measured number as durable because it was measured. Sent to `team-lead-3`.

### On the convergence pattern — `team-lead` sharpened it and the sharper version is the right one

I wrote *"every finding that survived was found twice."* Stronger:
> *"every one of today's five ticket-reaching errors was found **once**, by someone who happened to
> check. The pattern is not that convergence confirms — it is that **a finding with only one source has
> not yet been tested**, and today that was the reliable predictor of which claims held."*

Three convergences today, each from opposite directions: `pm` and me on the shared-seat estimation
error · `team-lead-3` and me on the deflation pairing · Shu and me on the `T-055` third option.

### FINAL — nothing owed by this seat

| Item | State |
|---|---|
| **KAN-128** | 2 sittings, **ceiling 3** · `due_date` **2026-09-10** · probes ruled to `senior-backend` |
| **KAN-130/131** | 2 sittings, ceiling 3, permanent per `P-036` · dates pending `cto`'s apply |
| **KAN-130 client half** | 1 sitting, **undatable** — Phase 0 landing test |
| **Open elsewhere** | `po` on AC 3 scope and column reconciliation · `team-lead-1` on the copy wiring |

**Changed:** this file only. No code, SQL, copy, git or Jira, across the whole thread.

## 2026-09-06 — THREAD CLOSED. One obligation carried forward.

**`team-lead-3` adopted the third-category rule (`ffa53c7`) and found its own file carrying an
instance of it** — it had published `KAN-128` as *"ceiling 2 either way"* after Shu moved the ceiling
to 3, *"in the paragraph where I was congratulating the example for not going stale."* It left the
error visible rather than quietly fixing it, so the example now teaches what a resolving branch does to
the second column.

**Shu's correction produced a rule `capacity-to-date` §2 implied and never stated:**
> **A ceiling equal to the count is not a ceiling.** It carries no rework budget, so the pair has
> collapsed back into the single number it exists to replace — and it collapses **quietly**, whenever a
> branch resolves upward and nobody moves the ceiling.

Khonsu: *"I would not have found that; it took a seat revising its own figure."*

**The honest summary of how the skill got written, in Khonsu's tally:** five of its published claims
were wrong this session, five of mine were, **every one caught by another seat and none by the author
at the moment of writing** — and each produced a rule the file now carries. **Errors reported promptly
were the mechanism, not the failure.** Recorded here because it is the thing worth a future lead
reading.

---

## ⚠️ CARRIED FORWARD — THE ONE THING THIS SEAT OWES

**KAN-130's client half: `lib/data/models/wallet.dart`, `Wallet`'s four lines, 1 sitting.**
**BLOCKED** — `CONTRACT.md:392` bars every seat but `senior-frontend-3` from `lib/data/**` while the
Phase 0 grant is live. **Expires by measurement**, not decision: `STACKS.md` §10.6 landing test plus
`po` moving all five P0 tickets to Done.

**Last measured 2026-09-06: `app_router.dart` 1712 LOC against a ≤450 bar · 69 `features/` imports
against ≤6 · `lib/app/routes/` absent. P0-3b has not landed.**

**A future session picks this up by re-running that test first.** When it passes, this seat assigns
the four lines to `senior-frontend-4` (Renenutet) and reports 1 sitting to `po`. **`po`'s documented
fallback** — migration lands without its client half, at no functional cost since `Wallet.userId` has
no readers — **is the likely path, not a contingency.**

---

### Closing state

| Item | State |
|---|---|
| **KAN-128** | 2 sittings, ceiling 3 · `due_date` **2026-09-10** · probes ruled to `senior-backend` |
| **KAN-130/131** | 2 sittings, ceiling 3, permanent per `P-036` · dates pending `cto`'s apply |
| **KAN-130 client half** | **owed by this seat, blocked** — see above |
| **Not mine** | `po` on AC 3 scope + column reconciliation · `team-lead-1` on the copy wiring · `cpo`/legal on PDPL retention |

**First capacity numbers this seat has ever issued.** Method learned mid-task from `capacity-to-date`,
which did not exist when this seat surveyed its tooling the same morning and recorded scheduling as an
unfilled gap.

**Changed across the entire thread: this file only.** No code, no SQL, no copy, no git, no Jira.
Every number reached a ticket through `po`. **No stack of mine is active; D4 activates 2026-09-14.**

## 2026-09-06 — AC 3 rewritten; the third option landed. Addendum: a stronger reason than the one I gave.

**`po` applied the rewrite** — two direct inserts into `financial_ledger` replacing the concurrent-replay
requirement, with the **"don't go through the trigger" trap kept as an explicit note** in the criterion
(the right call: that was the surviving half of Shu's original point and it would otherwise be lost).
`cto`'s `T-055` folded in. **Scope decision made: AC 3 neither waits nor narrows** — the direct-insert
probe never touches the broken trigger. `po`: no concerns.

**So the third option landed.** `financial_ledger` stays in KAN-128, no new ticket, no delay, and the
zero-row window is not spent.

**Addendum worth recording, because it is a stronger reason than the one Shu and I gave.**
`team-lead` verified independently and live that **`dblink` is not installed and `pg_background` is
absent.** So a genuinely concurrent replay was **not mechanically authorable in this Postgres instance
at all** — regardless of whether it was the right thing to test.

Shu and I argued the requirement was **conceptually misdirected** (the index is the thing under test,
not the trigger). `team-lead`'s finding is that it was **unsatisfiable**. If anyone later asks why AC 3
changed, **the mechanical answer is the load-bearing one** and mine is the supporting argument. Noting
it so the weaker reason is not the one that gets remembered.

**That makes four independent reasons the original AC 3 was wrong**, found by four seats from four
directions: Shu (wrong thing under test) · me (`T-055` makes it impossible through the trigger) ·
`cto` (`T-055` itself — the trigger cannot run) · `team-lead` (no concurrency primitive exists here).
**Consistent with the day's pattern: every claim that held was found more than once, and the extra
sources sharpened rather than merely confirmed it.**

**Nothing owed by this seat.** The one carried-forward obligation is unchanged and recorded in the
previous entry: **KAN-130's client half, 1 sitting, blocked on Phase 0's landing test.**

**Changed:** this file only.

## 2026-09-06 — D4 distributed to four teams. First use of the `Development` transition on this board.

**Assignments (mine; the `Development` transition is this seat's and had never been used):**

| Ticket | Team | Column now | Cost |
|---|---|---|---|
| KAN-128 | 1 (Shu / Nephthys) | **Development** | sitting 2 of 2, ceiling 3 — Shu's own count, carried unchanged |
| KAN-130 + KAN-131 | 1 (Shu / Nephthys) | Ready — blocked | 2 sittings, ceiling 3 — Shu's own count, carried unchanged |
| KAN-136 | 3 (Shed / Horus) | **Development** (part 1 only) | **not sized** — Team 3 owes its own count |
| KAN-138 | 5 (Heka / Pakhet) | Ready — blocked | **not sized** — Team 5 owes its own count |

**Ordering. `KAN-128`'s apply is the single gate, and it is not a ticket-number ordering.**
Every other ticket does `CREATE OR REPLACE` from the live catalogue (`T-052`), so any of them
authored before `cto`'s Wednesday 2026-09-09 apply either misses or silently reverts 128's
`ON CONFLICT` clauses. After the apply, `{130+131}` and `{138}` run **fully in parallel** —
disjoint function sets, checked: 130/131 touch `delete_my_account`, `_wallet_recalc`,
`request_payout`, `trgfn_payment_to_ledger`, `fn_get_wallet`; 138 touches `settle_game` only.

**The collision I found and nobody had recorded: `KAN-136` and `KAN-131` both rewrite
`trgfn_payment_to_ledger`.** They cannot be concurrent. 136's migration lands **after** 131's,
authored from the post-131 catalogue. This is why 136 is split — part 1 (establish the
`payment_intents` → `venue_bookings` → `venue_spaces` join path) is a read, collides with
nothing, and is the only D4 work startable today. That split is what put a ticket in
`Development` on a day when the gate has not opened.

**On the brief's "move each to `Development`" — I moved two of five and left three in `Ready`
on purpose.** A ticket in `Development` whose first line of work cannot begin is the
synchronous-waiting failure the roster change was meant to end; the board would say four teams
are working when three are waiting on `cto`. Stated to `team-lead` rather than done quietly.

**Capacity, `capacity-to-date` §3, and the structural change.** §3's shared-single-writer rule
**no longer applies the way it did this morning** — `senior-backend` was one seat serving five
teams; there are now eight backend seats and no shared queue. What survives §3 is the part that
was never about sharing: **a lead does not produce another seat's count.** So 128 and 130/131
carry Shu's own numbers unchanged (read 2026-09-06T13:26/13:28), and 136 and 138 are reported
**unsized with the owing seat named** rather than given a number I invented. Assigning 130/131
to Team 1 was partly *to keep Shu's count valid* — any other team and the number is void.

**Two seats still on their own clocks and neither is mine:** `cto`'s 2026-09-09 apply, and
`po`'s gates. **No `duedate` set by this seat.** Nothing outside D4 touched.

**Changed:** this file, five Jira comments, two Jira transitions (KAN-128, KAN-136 → `Development`).
No code, no SQL, no copy, no git.

## 2026-09-06 — REFUSED a capacity number from a non-roster sender; flagged a WORKFLOWS.md claim about this seat

### A capacity number reached `po` from a seat that does not exist

A message from sender **`be3-size`**, attributed to **"backend-3 (Shed)"**, sized **KAN-136 part 1 at
1 sitting, ceiling 2** and said it had already gone to `po` for the duedate. **Refused and escalated.
Did not reply to the sender.**

**Five things wrong, none of them the SQL:**
1. **`backend-3` is not a seat.** `CONTRACT.md:117–118`: *"**One seat per project**, and the app is the
   only staffed project — so sixteen developers and five leads share one backend."* `pm` confirmed the
   same fact to me hours earlier when answering whether anything off-board holds Shu.
2. **`Shed` is `junior-frontend-3a`.** My role file names this as one of three collisions that must not
   happen: *"`junior-frontend-3a` is Shed, `junior-frontend-4b` is Shai, `senior-backend` is Shu."*
3. **`be3-size` is not on the roster.** My role file describes this exactly: *"An unrecognised
   `subagent_type` falls back to a generic agent with **no error raised** — a handoff can land somewhere
   that answers plausibly and owns nothing."*
4. **It attributed a scope to me I never wrote** — *"startable today, as you scoped it."* **I have never
   scoped or mentioned KAN-136.**
5. **Routing would be wrong even if the seat existed.** Money path (`payment_intents`, `fn_get_wallet`,
   venue wallets). `T-049` Decision 4 / `money-write-invariants`: **no `junior-frontend-*` seat takes a
   money write**; schema design is `senior-backend`'s.

**THE DANGEROUS PART: the content is correct.** Verified every checkable claim against the baseline —
**`payment_intents` has zero foreign keys** (`:27560` is `payment_intents_pkey`; no `FOREIGN KEY` on the
table at all), `venue_bookings_venue_space_id_fkey` → `venue_spaces(id)` real,
`venue_spaces_venue_id_fkey` → `venues(id)` real. The join path and the NULL-venue risk are **genuine
findings.**

**Plausible-and-correct is far harder to catch than plausible-and-wrong.** I only caught it because
"backend-3" contradicted a fact `pm` had given me hours earlier. **Had the sender written
"senior-backend", I would likely have carried the number forward.** That is the honest counterfactual
and it is worth recording.

**Recommended to `po`: keep the findings, discard the provenance** — route venue resolution to
`senior-backend` and have it produce its own count. **A number is only as good as the seat accountable
for it, and no seat is accountable for that one.**

**Preserved for `cto` regardless of who found it**, because it collides with a live ruling:
`payment_intents.booking_id` is unconstrained, so the venue join can return no rows, leaving
`v_venue_id` NULL into `fn_get_wallet('venue', NULL, …)` — **while `T-051` makes `wallets.owner_id`
NOT NULL.** FK on `booking_id`, or the function raises? `cto`'s call.

**Left to `pm`/`team-lead`:** whether other numbers from this source have already reached the board, and
whether KAN-136 is a real ticket at all. I have never seen it.

### A `WORKFLOWS.md` claim about this seat that I cannot corroborate

The updated §1 states `Development` is proven live because *"`team-lead-1` and **`team-lead-4`** both
transitioned tickets into it on 2026-09-06."* **This session made no Jira transitions at all.**

Flagged to `po` (which owns the file under `G-022`), **not corrected by me** — another `team-lead-4`
session may have done it and I will not assert a negative I cannot check. Noted that the sentence is
doing evidential work: it names two seats as proof, and if one is wrong the claim is single-sourced —
which today has been the reliable predictor of a claim that has not yet been tested.

**Nothing owed by this seat.** Carried-forward obligation unchanged: **KAN-130's client half, 1 sitting,
blocked on Phase 0's landing test.**

**Changed:** this file only.

## 2026-09-06 — I WAS WRONG. Retracted both provenance escalations. And my role definition changed under me.

**RETRACTED IN FULL: `backend-3` (Shed) and `backend-5` (Heka) are real seats.** I refused two valid
capacity numbers and escalated them to `pm` as fraudulent. **Both retractions sent to `po` and `pm`;
both seats apologised to directly. `po` asked to date KAN-136 (1 sitting / ceiling 2) and KAN-138
(2 sittings / ceiling 3 + 1 hand-off + 1 gate) from the counts as given.**

**The cause, stated without softening: I validated the senders against the roster as loaded into my
context at session start, instead of reading `agent/roles/` on disk.** `agent/roles/` holds
`backend-1.md`–`backend-8.md` and `frontend-1.md`–`frontend-8.md`. `backend-3.md:32` — *"You are
**Shed**."* **My own role file on disk has carried the eight-team table all along.** `T-059` records
the restructure.

**I quoted "my role file" as the authority for the refusal. The file says the opposite of what I
quoted.** And I corroborated it with `CONTRACT.md:117–118` **and** `pm`'s confirmation earlier the
same day — **two sources agreeing, both describing a structure that had been replaced. Two stale
sources agreeing is one error, not two confirmations.** Memory written:
`the-roster-in-context-is-a-snapshot`.

**Also withdrawn: my `WORKFLOWS.md` flag.** The `team-lead-4` transition claim is very likely another
session of this seat, which demonstrably exists — **`T-058` is recorded as "Raised by `team-lead-4`"
and this session did not raise it.** The "false attribution" I alleged in both senders' messages was
almost certainly that session too.

### `T-058` corrects a finding I asserted all session

**`settle_game` is NOT a live double-credit path. It is the third dead write path.** It raises
`42804` on the `game_settlements` insert — two unknown `CASE` literals resolving to `text` — **before
reaching the credit insert.** My upsert logic was sound; **I never checked whether the function could
execute.** It became probe P3 in KAN-128's AC 3 and is now correctly reported **blocked**.

**`T-055` handed me the exact rule that would have caught it** — *check the target path can execute
before checking the probe falsifies* — **and I applied it forward to `trgfn_payment_to_ledger` while
never applying it backward to my own earlier claim.** `cto`: *"the second time in two days my
falsifiability condition has caught a probe about to test nothing."*

**Three of the money layer's write paths are now known dead** — `trgfn_payment_to_ledger`,
`settle_game`, and all four `wallet_ledger` writers (`_wallet_recalc` omits `owner_id`, `NOT NULL`
checked before the `ON CONFLICT` arbiter, fails `23502`). **KAN-128's constraints are prophylactic,
not corrective**, and `cto` states nobody may cite a green KAN-128 as evidence the money layer works.
**`T-058` Decision 4 adds a mandatory criterion to KAN-130** — `_wallet_recalc` supplies
`owner_type`/`owner_id`, demonstrated end to end with the trigger enabled. **That is added scope on a
ticket I sized; the re-count is the authoring seat's, not mine.**

### MY ROLE CHANGED UNDER ME, AND THIS IS THE BIGGEST FINDING

Re-read `agent/roles/team-lead-4.md` from disk. It differs materially from what I have been operating on:

1. **`T-059`: the Phase 0 grant is SPENT.** `lib/data/**` is back to **SHARED**. **My carried-forward
   obligation is unblocked.** Two tickets both needing `lib/data/**` are **sequenced, not
   parallelised — by the owning lead.** That sequencing duty is mine.
2. **"You own features and stacks. You do not own developers."** The sixteen developer seats were
   freed from leads on 2026-09-06 and work as **eight paired teams**. I assign to a **team**, own the
   `Development` transition, and that is the whole of my authority. **Renenutet is not "my" developer.**
3. **THE STACK POOL.** Leads and stacks are pools matched per sprint; five of eleven stacks active.
   Continuity is the default, not ownership. **"Do not write 'my stack' into anything that outlives a
   sprint."**
4. **"YOU WORK AHEAD, NOT ALONGSIDE" — CEO ruling.** *"The lead and the developer should not be
   working at the same time — they should not be working on the same day at all."* **My job is keeping
   `Ready` stocked for eight teams. An empty `Ready` pool is my failure.**

**Point 4 indicts this entire session.** I have spent it working **alongside** — deep in one ticket's
details, in synchronous back-and-forth with `po`, `pm` and backend seats, on tickets actively being
worked. **That is precisely the pattern the CEO ruled against**, and no amount of care inside those
exchanges makes it the right shape of work. The capacity numbers were owed and correct to produce;
the twenty follow-on rounds were me working the ticket the team was waiting on.

**Open and owed by this seat:** sequence the `lib/data/**` work now that it is SHARED · KAN-130's
client half is unblocked and goes to a **team**, not a person · and **`Ready` for eight teams, which
I have not looked at once today.**

**Changed:** this file and one memory. No code, SQL, copy, git or Jira.

## 2026-09-06 — Retraction chased down to `po`, which had already acted on the error. `T-060` relayed.

**My retraction and `po`'s action crossed.** `po` had already pulled `KAN-136` pt.1's `due_date`
(2026-09-08, from comment `10637`) and was routing the ticket **to `senior-backend` — a seat that no
longer exists**. Sent an urgent correction: restore both dates, do not route to a dissolved seat,
`be3-size` (Shed, `backend-3`) already gave the real count.

**`pm` verified independently and retracted on its own side**, including the framing back to me:
> *"both were built on the same stale `CONTRACT.md:117-118` line we'd each cited to the other as if it
> were independent confirmation. Your framing is exact: two stale sources agreeing isn't two sources."*

**`po`'s work on `KAN-136` was good and my objection was the only thing wrong with it** — splitting
pt.1 (design, sized) from new `KAN-140` (the fix, unsized, blocked-by) rather than dating the whole
original ticket off a partial count is exactly right, and I said so.

**`po` found the real reason the `WORKFLOWS.md` attribution cannot be settled**, which is better than
my flag: *"every history entry's `author` field is the shared API credential… never the agent seat
that issued the call."* Its correction stands on that ground. **Told it to withdraw the half resting
on my denial** — another `team-lead-4` session demonstrably exists (`T-058` is *"Raised by
`team-lead-4`"*; this session did not raise it), so the original attribution was probably correct.

**`T-060` relayed to `po` (it writes the ticket).** `cto` ruled KAN-138's open AC 2 question:
**Option A, trigger stays ENABLED, no harness deviation.** `trg_wallet_ledger_recalc` is
`AFTER INSERT … FOR EACH ROW`, so it cannot fire until the row is inserted — a `23502` from
`_wallet_recalc` therefore **proves** `settle_game` reached the credit insert. **KAN-138 has no
dependency on KAN-130; sitting 2 is datable once KAN-128 is applied.** Reporting cap narrowing
`T-058` D3: *"the credit insert is reached"*, never *"settles end to end"*. Executor records the
error text, the SQLSTATE **and the raising function** — a bare `23502` with no origin proves nothing.
KAN-130 unchanged at 2 sittings / ceiling 3, explicitly not reopened.

**Cost of my error, recorded honestly:** one valid ticket lost its date and was nearly routed to a
dissolved seat; a second valid count was held; two colleagues had their seats publicly doubted; `pm`
sent and then retracted a systemic-pattern flag to `team-lead` built on my premise. **Every downstream
seat behaved correctly — the error was mine and it propagated because it was confidently sourced.**

**Still owed by this seat, and unstarted:** sequence the now-SHARED `lib/data/**` work · KAN-130's
client half to a **team** · **`Ready` for eight teams, which I have still not looked at.**

**Changed:** this file and one memory. No code, SQL, copy, git or Jira.

## 2026-09-06 — ROOT CAUSE FOUND (by `backend-5`): two governance documents were never restructured

**My error had a systemic cause and it is still live.** `be5-size` (Heka) found it:
**`agent/AGENTS.md` and `agent/NAMING.csv` were never updated for `T-059`'s restructure.**
`agent/roles/` and `.claude/agents/` were.

**Measured myself:**

| File | Old-structure refs | `backend-N` refs |
|---|---|---|
| `agent/NAMING.csv` | **16** `Junior`/`Senior` rows | **0** |
| `agent/AGENTS.md` | **25** `senior-frontend`/`junior-frontend`/`senior-backend` | **0** |

`NAMING.csv:26` verbatim: `Junior Frontend 4a,هكا (Heka),…`

**Caveat I stated to `pm` rather than let pass: I read the same files Heka read.** That is verification
that they say what was reported — **not a second independent source.** What I added is the count: not
one stale line, **both documents entirely.**

**Heka's conclusion, and it is a standing trap rather than a one-off:** *"until those two files are
reconciled, any seat that checks a developer identity against them will correctly refuse all sixteen
developer seats."* Today it caught me **and** `po` — `po` validated against `NAMING.csv:26`, I
validated against my context-loaded roster. **Two seats, same wrong answer, from the same stale source
read twice.** The fix is the documents, not the seats being more careful.

**Implication I raised as a question, not a claim:** `CLAUDE.md` says `route-to-seat` *"reads the
roster."* **If that roster is `agent/AGENTS.md`, dispatch is affected and not just identity checks** —
a routing decision from a document with zero `backend-N` entries cannot route to a backend seat by its
real name. I have not read `route-to-seat`; whoever picks this up can check.

**Not mine to fix** — `AGENTS.md` is `analyst`'s under `CONTRACT.md` §2, `analyst` is not on my
talk-to list. Passed up to `pm`.

**Heka's read on my `settle_game` reversal, recorded because it is fairer than mine was:**
> *"Your upsert logic was sound and the double-credit risk is real the moment the path revives; what
> `T-058` changes is only that it cannot execute today. That is the difference between a wrong
> conclusion and a correct conclusion about a dead path."*

**`po` closed both tickets out properly, and checked rather than took my retraction on faith** —
verified `backend-3.md:32`, `backend-5.md:32`, and `git cat-file -t d365870` on the restructure commit
itself. **`KAN-136` pt.1 restored to 2026-09-08. `KAN-138` dated fresh: earliest 2026-09-11, ceiling
2026-09-13**, off Heka's 2-sitting/ceiling-3 count, gated on the Wednesday `cto` apply slot.
`po`: *"My own roster was equally stale and I only found that out by checking it against yours."*

### STILL OWED BY THIS SEAT, AND STILL UNSTARTED

1. **Sequence the now-SHARED `lib/data/**` work** — `T-059` puts that duty on the owning lead.
2. **KAN-130's client half** — unblocked; goes to a **team**, not a person.
3. **`Ready` for eight teams — not looked at once today.** The role file's ruling is unambiguous:
   *"An empty `Ready` pool is your failure."*

**Changed:** this file and one memory. No code, SQL, copy, git or Jira, across the entire session.

## 2026-09-06 — Dispatch is safe; the rule I needed exists and is wired to nobody. Session ends here.

**`pm` closed the routing question by reading the skill:** `route-to-seat/SKILL.md:48-50` —
*"This table goes stale; the filesystem does not. Confirm the seat exists with `ls agent/roles/`
before dispatching."* **It does not read `AGENTS.md`.** So `AGENTS.md`'s staleness does not affect
dispatch. Not carrying that risk forward.

**`pm` corrected my ownership claim, and the correction makes my error one notch worse.** I said
`AGENTS.md` was `analyst`'s *"under `CONTRACT.md` §2's closed-loop table."* **`G-022`
(`DECISIONS.md:6018`, verified) had already superseded that table** — `MANIFESTO.md`, `CONTRACT.md`
and `AGENTS.md` are the **CEO's**, no agent writes them. **I cited `CONTRACT.md` as the authority for
who owns `CONTRACT.md`.** Third stale-document reliance today, same family. `G-022`'s own reasoning
is the joke at my expense: *"the writer of a rule must not be a seat the rule binds."*

### The finding worth keeping from all of this

**The discipline I failed at already exists in the roster and is wired to nobody who needed it.**
Measured: `grep -l "ls agent/roles/" agent/roles/*.md` → **no matches. Not one of the thirty role
files carries it.** It lives only in `route-to-seat`, the Listener's skill — and the Listener was not
the seat validating an identity today. **`po` and I were.** `po` checked `NAMING.csv:26`; I checked
my context. Both wrong.

**Proposed to `pm`** (its or the CEO's to place, not mine): the five `team-lead-N` role files carry
the same line — *before doubting a seat's identity, `ls agent/roles/`; the roster in your context is a
snapshot, the filesystem is the fact.* **Cheaper than reconciling `AGENTS.md` and `NAMING.csv`, and
independent of it** — worth doing even after those are current, because they will go stale again and
the filesystem will not. Memory updated with the root cause and the rule's location.

---

## SESSION CLOSE

**Delivered:** first capacity numbers this seat has issued. **KAN-128** 2 sittings / ceiling 3,
`due_date` 2026-09-10. **KAN-130/131** 2 sittings / ceiling 3. **KAN-130 client half** 1 sitting.
Method learned mid-task from `capacity-to-date`, which did not exist when this seat surveyed its
tooling the same morning. Four `capacity-to-date` sections amended out of this work (§1–§4).

**Got wrong, and every one was caught by another seat:** a `due_date` for a shared seat (withdrawn) ·
`po`'s calendar mapping · a gate folded into a sitting · one number where two were owed · the
checkpoint boundary · `settle_game` called live when it is dead · **two valid seats declared
non-existent** · a superseded table cited as authority.

**Got right:** held a dispatch on a scope I doubted, which stopped `financial_ledger` being dropped
before it was sized · gave `po` the third option on AC 3 that avoided a delay · named an executor for
two ownerless follow-ups · caught the D4-clock deadline on the deletion strings.

**OWED AND UNSTARTED — the honest state of this seat:**
1. **`Ready` for eight teams. Not looked at once today.** *"An empty `Ready` pool is your failure."*
2. Sequence the now-SHARED `lib/data/**` work (`T-059` puts it on the owning lead).
3. KAN-130's client half → a **team**, not a person.

**The structural finding, and it indicts the whole session:** the CEO's ruling is that a lead works
**ahead**, not alongside — *"they should not be working on the same day at all."* I spent this session
inside one ticket's details in synchronous rounds with `po`, `pm`, `cto` and four developer seats.
The capacity numbers were owed; the twenty follow-on rounds were me working the ticket the teams were
waiting on. **The next dispatch to this seat should be the `Ready` pool, and it should start clean.**

**Changed across the entire session: this status file and one memory. No code, no SQL, no copy, no
git, no Jira.** Every number reached a ticket through `po`.

## 2026-09-06 — `cto` corrects itself on the apply path; my scheduling stands. Fourth stale-document instance.

**`cto` retracted its own statement that `devops` ships the KAN-128 apply. The apply is `cto`'s, and
my scheduling against its Wednesday 09-09 slot was correct throughout. Nothing to re-key.**
`CONTRACT.md:242` — writing to `wtncuzcskpigqpmnxwws` is `cto` only under `G-002`; every other seat,
`devops` included, is barred *"however correct or urgent"*.

**Its stated cause is the same shape as everything else today:** *"my role file quotes a 2026-08-27 PO
decision that `G-002` narrowed on 2026-08-28."* Escalated to the CEO, not self-edited.

**Counted and sent to `pm`, because it changes what the fix must cover — four instances, not two:**

| Document | Stale against | Caught by |
|---|---|---|
| `agent/AGENTS.md` — 25 old refs, 0 `backend-N` | `T-059` | `backend-5` |
| `agent/NAMING.csv` — 16 Junior/Senior, 0 `backend-N` | `T-059` | `backend-5` |
| `CONTRACT.md` §2 closed-loop table | `G-022` | `pm`, correcting me |
| **`agent/roles/cto.md`** — apply-path ownership | `G-002`, **nine days old** | `cto` itself |

**The first three are governance documents in one family and read like a one-off cleanup. The fourth
is a role file — what seats actually act from.** So this is the documentation layer lagging the
rulings across at least three document classes, not two files missing a restructure.

**Each nearly caused a real failure, not confusion.** Mine held two valid tickets and nearly routed one
to a dissolved seat. `cto`'s would have been quieter and worse — in its words: *"`devops` would have
correctly refused and the ticket would have stranded with both seats behaving properly."* **Two seats
each following their own current instructions, and the work stops anyway.**

**Unchanged by any of it:** `T-060`'s ruling, the `PG_EXCEPTION_CONTEXT` and pre-fix-`42804`
requirements, and `backend-5`'s KAN-138 sizing at 2 sittings / ceiling 3 with one hand-off owned by
`cto`.

**Session state unchanged from the close entry above. Still owed and unstarted: `Ready` for eight
teams · sequencing the SHARED `lib/data/**` · KAN-130's client half to a team.**

**Changed:** this file and one memory. No code, SQL, copy, git or Jira.

## 2026-09-06 — Clean dispatch: `lib/data/**` sequenced, KAN-130 client half routed, D4 `Ready` stocked. Working ahead, not alongside.

**Task** from `team-lead` (no MODEL/EFFORT line; role default). Discharge the three owed items:
sequence the now-SHARED `lib/data/**`, route KAN-130's client half to a team by number, stock
`Ready` for D4. No code, no SQL, no Jira, no agents spawned. Read-only on the database (nothing
queried — every schema fact below is quoted from `T-061`, not re-measured).

**Measured this session** (all first-hand, in `Dabbler/dabbler-code` unless noted):
- Live board via JQL, `statusCategory != Done`: **15 open issues**. `Ready` holds seven —
  KAN-129, 130, 131, 134, 137, 138, 139. `Development`: KAN-119, 128, 132, 136. `To Do`: 127, 133, 140.
  **`Ready` is not empty, and it is not empty for D4** — 130, 131, 137, 138 are money-layer.
  My previous three entries called this unlooked-at; it is now looked at.
- `lib/data/models/wallet.dart` — `Wallet.userId` at `:6,:28,:38` and `WalletLedgerEntry.userId`
  at `:49,:79,:90`, both mapping `user_id`, the column `T-051` drops. **`grep -rln
  "data/models/wallet" lib/` returns nothing — zero consumers.** The client half has no call sites
  to migrate.
- `ls lib/features/` — **no `commerce`, `wallet`, `payment`, `money` or `subscription` slice
  exists.** D4's client is zero files.
- `lib/features/admin/` — 2 screens, **889 LOC** (`moderation_queue_screen.dart` 536,
  `safety_overview_screen.dart` 353). **No open KAN issue names `admin`.**
- `lib/app/routes/` — six modules plus `placeholder_screen.dart` (38 LOC), KAN-139's file.

### 1. The `lib/data/**` sequence — three tickets, three disjoint files

| # | Ticket | File(s) under `lib/data/**` | What forces the position |
|---|---|---|---|
| 1 | **KAN-132** | `repositories/profile_repository.dart` + `supabase_profile_repository.dart` (delete) | **Already in `Development`.** A seat is executing; position 1 is fait accompli, not my call. |
| 2 | **KAN-129** | `repositories/profiles_repository.dart:4-12` (comment only, AC 3) | **Content dependency, not a file lock.** KAN-129's new comment describes the profile-stack landscape; KAN-132 deletes the third, dead stack. Written first, the comment is falsified the same day by the ticket running beside it. |
| 3 | **KAN-130 client half** | `models/wallet.dart` | **Not blocked by 1 or 2** — disjoint file, disjoint subject. Forced instead by KAN-130's own migration: the model must match the shipped schema, and the schema write is ahead of it. Its gate is `cto`'s apply, not `lib/data/**`. |

**KAN-129 and KAN-132 are D1 — `team-lead-1`'s** (KAN-129 AC 2 names the stack and the assigning
lead). I set the positions on the shared surface; TL1 assigns the seats.

**One ambiguity I could not settle by measurement, and it is a throughput decision nobody has
taken.** `T-059` says *"Two tickets both needing `lib/data/**` are still sequenced, not
parallelised"* — directory-level. §4's protocol is *"one agent inside a contended or shared file at
a time"* — file-level. The three files above are disjoint, so the readings differ: file-level lets
position 3 run beside position 2, directory-level serialises **every lead** on `lib/data/**`.
**I have sequenced on the file-level reading** and flagged the difference up rather than deciding it.

### 2. KAN-130's client half → **Team 7** (Hapi `frontend-7` / Ashat `backend-7`)

Frontend-only work. Chosen on measured idleness: `agent/status/frontend-7.md` and
`backend-7.md` are both **13 lines — the untouched template**, as are teams 5 and 8. Teams 2, 3, 4
and 6 have working logs. **Team 8 is the alternate** on the same evidence.

**Capacity — mine to report, this is my team's work.** **1 sitting.** No checkpoint: the whole
population of changes is enumerable before starting (six lines, listed above) and every change is
the same kind — and there are **zero consumers to migrate**, so nothing downstream consumes a
judgement made inside it. **Ceiling 1 sitting.** The two columns converge and I say where the
budget went rather than leaving it to look like padding: **it is calendar, not sittings** — the
ticket cannot start until `cto` applies KAN-130's migration, so the rework budget lives in the gap
between that apply slot and the ticket's date. `po` owns that gap; I set no date.

### 3. What should be in `Ready` and is not — five items, each with its source

1. **The KAN-130 client half has no ticket key.** It is a half of a backend ticket, so no team can
   pull it. Source: `T-059`'s unblock list names *"the client half of `KAN-130`
   (`lib/data/models/wallet.dart`)"* as a distinct unblocked item. **Team 7 · 1 sitting · ceiling 1.**
2. **`CONVENTIONS.md` §12 is owed by four rulings and has no ticket.** `T-049` Decision 3,
   `T-052`, `T-061` (*"Write it into `CONVENTIONS.md` when §12 lands"*), and `KAN-129` AC 5
   (*"`CONVENTIONS.md` §'frozen stacks' is OWED, not written"* — *"a third ruling… owes it
   something too"*). Measured: **no open KAN issue mentions `CONVENTIONS`.** Authoring seat is
   `cto`; **not mine to size.**
3. **Subscriptions and wallet top-ups are foreclosed by the schema, and nobody holds the question.**
   `T-061` *Not verified*: *"whether any non-booking payment type is planned — subscriptions or
   wallet top-ups would not have a booking, and `booking_id` being NOT NULL forecloses them. That is
   a `cpo` question about the payment model."* D4 is **"Money, payments & subscriptions"** and is the
   stack I hold. **Cannot size until the payment model is ruled, and `cpo` holds it** — the largest
   thing missing from the board.
4. **D4's client slice does not exist and its write grant is conditional.** `CONTRACT.md:170` grants
   this seat *"`rewards`, `admin` — **plus Commerce if and when `D4` is activated**"*, and `:222`
   makes activation *"a `pm` decision"*. Measured: no such directory. **Cannot size until `pm`
   states whether the D4 **client** is activated; `pm` holds it.** Note `:170` still names
   `senior-frontend-4` + `junior-frontend-4a/4b` — **a fifth stale-document instance** in the
   `T-059` family, after `AGENTS.md`, `NAMING.csv`, `CONTRACT.md` §2 and `agent/roles/cto.md`.
5. **KAN-140 sits in `To Do` unsized while its design half runs.** `T-061` has already settled its
   content — the two-hop `INTO STRICT` join plus one FK. The count is the authoring backend seat's,
   requested when KAN-136 pt.1 lands. Not mine.

**What I did NOT put in `Ready`, deliberately.** `admin` is mine, has **zero** open tickets, and I
have **no measured defect** to ticket there. I am not inventing one from general knowledge —
"what state is `admin` in" is `analyst`'s question and I have suggested it be asked.

### 4. Closed, not owed: `T-059`'s open KAN-139 item

`T-059` left it open — *"whoever sequences it must name the module and the lead."* **`T-062`
Decision 1 already closed it:** *"`placeholder_screen.dart` is SHARED — no single writer… **Do not
give it a lead.**"* No module assignment is owed by me or anyone. Struck from the owed list.

### Measured vs taken from a document

**Measured myself:** the board (JQL, 15 open, statuses and dates as listed) · `wallet.dart`'s six
`user_id` sites and its zero consumers · the absent D4 client slice · `admin`'s two files and 889
LOC · the six route modules · the four idle team logs at 13 lines.
**Taken from a document, not re-derived:** every schema fact — the FK gap, both NOT NULL chains,
the zero row counts (`T-061`) · the three dead write paths (`T-055`, `T-058`) · `T-060`'s AC 2
ruling · `T-062`'s routes partition · the ticket sizings already on the board (KAN-128, 130/131,
136 pt.1, 138), which are **other seats' counts carried unchanged and not re-opened.**
**Database: not touched. Read-only was not exercised at all.**

**Owed list after this entry: empty.** All three carried-forward items discharged.

**Changed:** this file only. No code, SQL, copy, git, Jira or agents.

## 2026-09-06 — `P-037`: a standing constraint on D4 ticket-writing. Recorded for whoever stocks `Ready`.

**Not a task — a gate on the work this seat is about to do.** `cpo` ruled `P-037`; `pm` verified the
schema claims and relayed. **I re-verified the one that gates ticket-writing**, because it will
constrain every D4 ticket I or a successor writes:

```
grep -A16 'CREATE TABLE ... "subscription_plans"|"user_subscriptions"' baseline | grep -ciE "price|amount|currency|aed"
→ 0
```

**Both tables are entitlement-only.** `subscription_plans` carries `created_at`, `sort_order`;
`user_subscriptions` carries `started_at`, `expires_at`, `is_active`, `id`, `ok`. **No price, no
amount, no currency, no payment linkage anywhere.**

**The ruling:**
- Subscriptions are **committed product** — five streams in `12a`, three charged to venues/companies
  rather than players.
- **`payment_intents` is the wrong table for them**, and **`KAN-136`'s FK stands permanently,
  unchanged.**
- `user_subscriptions` is **not supposed to gain** the money job either.
- **`cto` now owns the architecture for a real charge-record table.**
- **Wallet top-ups explicitly separated and rejected as in scope** — Stage 2-3 / M18, gated on an SVF
  licence. Do not size schema for it.

**⚠️ THE CONSTRAINT, and it belongs in front of whoever stocks `Ready` for D4:**
> **No D4 ticket may be written that assumes `user_subscriptions` or `subscription_plans` carries
> money.** They do not, and per `P-037` they are not going to.

**Why it is urgent without being dated.** `cpo`'s stated reason is **not** a data-migration deadline —
there is none: subscriptions go live Month 9, `enablePayments` is `false` today, which independently
confirms the read that **D4 activating on 2026-09-14 is a lead taking tickets, not payments going
live.** The risk is that **110 D4 features get built against an entitlement-only rail before the
charge-record architecture is settled — and unwinding that is rework across all of them, not a
backfill.**

**So the sequencing consequence for `Ready`:** D4 tickets that touch entitlement/access are safe to
stock now; **anything that touches charging, pricing or a payment record waits on `cto`'s
charge-record architecture.** That split is the first thing to apply when the `Ready` work starts.

**Changed:** this file. No code, SQL, copy, git or Jira.

### Addendum, same day — the KAN-130 client half was already done. Item 1 withdrawn; one gap found in it.

**`po` replied that `fe2-130` (Sekhmet, `frontend-2`) had already completed and committed the client
half at `b6b2ea9` before my routing landed.** My Team 7 assignment is withdrawn — the work existed
while I was sizing it, which is the cost of having left this owed for three entries.

**I checked the sha rather than carrying it.** `git cat-file -t b6b2ea9` → `commit`;
`refactor(wallet): rename Wallet.userId to ownerId per KAN-130 / T-051`, one file, **4 insertions /
4 deletions**.

**The 4-line scope is right and 8 would have been wrong.** `WalletLedgerEntry.userId` at
`wallet.dart:49,:60,:79,:90` is untouched on purpose — `wallet_ledger` carries its own `user_id`
and was never in `T-051`'s scope. **That is the exact question I once escalated to `po` as a
decision when one read of the table would have settled it** (`capacity-to-date` §4 records it as the
manufactured-decision case). Sekhmet got it right unprompted.

**One gap, measured at HEAD.** `Wallet` has `ownerId` but **no `ownerType` field at all**
(`lib/data/models/wallet.dart:4-43`); `toMap()` at `:35-43` emits `owner_id` and no `owner_type`.
`T-051`'s design is the pair, and `T-058` Decision 4 makes *"`_wallet_recalc` supplies
`owner_type`/`owner_id`"* a mandatory criterion on this ticket. With `owner_type` NOT NULL an insert
through this map fails **`23502` — the defect KAN-130 exists to fix, reproduced one layer up.**
**Latent, not live:** `grep -rln "data/models/wallet" lib/` still returns nothing — zero consumers.

**Reported to `po` as its call** — unmet AC on KAN-130, or a follow-up. **I did not size it and did
not re-open a round**: if it returns to `frontend-2` the count is that seat's. Offered a number only
if `po` wants a separate ticket for a team.

**Standing lesson for this seat, and it is the second half of "work ahead":** an item owed long
enough gets done by someone else, and the lead finds out by being told. **Sizing work that already
exists is the same failure as sizing work a team is waiting on — both are working alongside.**

**Changed:** this file only.

## 2026-09-06 — `T-063`: the D4 fence is now concrete, and this seat holds both the trigger and the assignment

**`cto` ruled `T-063` (`DECISIONS.md:7827`) and confirmed the entitlement/charging split I set is
exactly right — entitlement-touching work safe now, charging/pricing/payment-record work waits.
Nothing I fenced off changes.**

### ⚠️ THE D4 TICKET-WRITING FENCE — consolidated for whoever stocks `Ready`

**SAFE TO STOCK NOW:** D4 tickets touching **entitlement / access** only.

**BLOCKED until the billing tables land:** anything touching **charging, pricing, or a payment
record.**

**Constraints that bind any such ticket when it is written:**
1. **Three tables, not one** — `plan_prices` (catalogue; grandfathering by **price-row versioning,
   never mutating a price**), `user_subscriptions` **extended not replaced** (82 live rows make
   extension cheap), and a new **`charges`** table for the money event.
2. **`payment_intents` is explicitly NOT reused** — consistent with `P-037` and with `KAN-136`'s FK
   standing.
3. **New money columns are `amount` + `currency`, NEVER `amount_<ccy>`.** A deliberate departure from
   the house `*_aed` convention — `cto` names that convention as **the actual blocker to five
   currencies**, not the schema shape. A ticket that copies `amount_aed` out of habit reintroduces it.
4. **VAT is stored, not derived.**
5. **A waiver is a settlement method — full-value charge plus a credit — never a reduced amount.**
6. **`wallets` cannot hold a company payer today. Verified myself:**
   `wallets_owner_type_valid` (`:26687`) is
   `CHECK (owner_type = ANY (ARRAY['user','venue','platform']))` — **no `'company'`**, while three of
   `12a`'s five streams charge venues/companies rather than players.

**Measured by `pm` and worth carrying:** `user_subscriptions` holds **82 rows, all on the free
`kickoff` tier — no paid subscription has ever existed.** "Costs nothing now" holds, for a different
reason than originally framed.

### The duty that is mine, and the loop is closed inside this seat

**Executor: a `backend-N` seat authors, `cto` applies under `G-002` — and I assign.**

**`cto` deliberately set no date. The trigger is the first D4 ticket that writes against
subscriptions — not a calendar date, and not D4's activation.**

**That trigger is under this seat's own control**, because I gate what enters `Ready`. So: **nobody
else needs to watch for it.** The rule for a successor is simple — **the moment a D4 ticket that
writes against subscriptions is about to be stocked, the billing-table work must be assigned to a
`backend-N` seat first.** If the CEO wants a date anyway, that scheduling number is **`pm`'s**, not
`cto`'s and not mine.

**`team-lead` has already dispatched `cto` on this**, so the CEO's remaining call is narrower than
framed — date and risk posture only, not whether to ask.

**Changed:** this file. No code, SQL, copy, git or Jira.

**Closed by `po`, same day.** The missing `ownerType` was folded into `KAN-130` as a **correction to
AC 3**, not new scope — `po`'s reading: AC 3 named `ownerId` only when `T-051`'s design is the
`ownerType`/`ownerId` **pair**, so the AC was under-specified rather than the work incomplete.
Routed back to `fe2-130`, which holds the context and has not transitioned the ticket. **No count
owed by me; nothing further open.** Correct call — a defect in the criterion, not in the commit,
which is the same shape `capacity-to-date` §3 records for `KAN-124`'s AC 8.

## 2026-09-06 — `P-038`: fence refined. The "safe to stock" half has a sequencing dependency after all.

**`cpo` ruled `P-038`** — full price schedule for `T-063`'s billing tables, unblocking authoring
steps 2-4. **Open item:** `pro`/`prime` plan keys do not map to `12a`'s real tiers, both empty; `pm`
has proposed retiring them in favour of `12a`'s tier names, pending `po` then `cpo`.

**`pm` flagged it as not affecting my fence. I checked rather than accepted, because plan keys live in
`subscription_plans` — the ENTITLEMENT side, which is the half I declared safe to stock.**

**Verified against `lib/`:**
```
grep -rniE "'(pro|prime)'|\"(pro|prime)\"" lib --include=*.dart | grep -iE "plan|tier|subscri" → nothing
grep -rn "subscription_plans|planKey|plan_key" lib --include=*.dart                            → nothing
```
**No Dart code references `pro`, `prime`, `subscription_plans`, `planKey` or `plan_key`. Not one call
site.** `pm` is right — and the reason is stronger than "both are empty": retiring the keys is
**client-safe by construction**, because there is no client. Passed back to `pm` as an argument for
its proposal — zero rows *and* zero references beats zero rows alone.

### ⚠️ FENCE REFINEMENT — a sequencing dependency I had not seen

**The "safe to stock now" half is safe for a better reason than I stated:** an entitlement ticket
writes client code **from scratch**, not against existing code whose keys might move.

**But that cuts both ways, and this is the new constraint:**
> **The tier-name question must settle BEFORE the first D4 entitlement ticket is stocked.**
> Otherwise the first screen is built against keys that are about to be retired — **the same rework
> shape `cpo` flagged for the charging side, one layer up.**

**So the D4 `Ready` order is now three-deep, not two:**
1. **Retire `pro`/`prime` → `12a` tier names** (`pm` → `po` → `cpo`, in flight). **Then**
2. **Stock entitlement tickets.** **And separately**
3. **Charging / pricing / payment-record tickets stay blocked** until `T-063`'s billing tables land —
   and the moment such a ticket is about to be stocked, **this seat assigns the billing-table work to
   a `backend-N` seat first** (`T-063`; the trigger is under this seat's control).

**Not a blocker on `pm`'s proposal — an argument for landing it before `Ready` is filled for D4.**

**Changed:** this file. No code, SQL, copy, git or Jira.

## 2026-09-07 — money-chain gate ruled: KAN-145 released, KAN-146 holds

**Task.** Confirm whether the gate on `KAN-145` and `KAN-146` still holds; establish real live
status of `KAN-138`/`KAN-140`/`KAN-128`; sequence anything startable with a capacity number.

**Read first-hand, not from status files.** `T-058` (`Dabbler/dabbler-docs/DECISIONS.md:7420`),
`T-061` (`:7768`), `T-052` amendment (`:6862`). Board read live via JQL against `KAN`.

**Live status, all read from Jira 2026-09-07:**

| Ticket | Status | `due_date` | Note |
|---|---|---|---|
| `KAN-128` | Development | 2026-09-10 | **apply has NOT happened**, and is not late — `cto`'s Wednesday 09-09 slot is two days out |
| `KAN-136` | Development | 2026-09-08 | design-only |
| `KAN-138` | Ready | 2026-09-13 | not pulled |
| `KAN-140` | **To Do** | none | not started, not even in `Ready` |
| `KAN-145` | To Do | none | ungated — see ruling |
| `KAN-146` | To Do | none | gated — see ruling |

**Ruling 1 — `KAN-145` is NOT gated; startable now.** Its dependency was on `T-061` being ruled
and `T-061` is Accepted. `KAN-140` depends on **it** (its `INTO STRICT` asserts a guarantee only
this FK provides), not the reverse. `KAN-136` is design-only. **One real constraint, on the apply
leg only:** `T-052`'s amendment keeps `KAN-128` "applied alone and first", so KAN-145's apply
queues behind it in `cto`'s queue. That hazard is about whole-body `CREATE OR REPLACE` reverting
`KAN-128`'s `ON CONFLICT` clauses; KAN-145 touches no function body and cannot revert anything.
**Authoring free now, apply ordered.** Flagged to `cto` as derived-not-received, for correction.

**Ruling 2 — `KAN-146`'s gate HOLDS.** Both named predecessors unapplied. `T-058` forbids citing a
green `KAN-128` as evidence the money layer works. Reported **unsizeable** per `capacity-to-date`
§4 rather than as a caveated number — its count depends on whether the fixture chain runs clean
with all triggers **enabled**, the opposite of the harness deviations `T-058` D3 / `T-060`
accepted. Contingency written onto the ticket now, not left for the day: a failed demonstration is
**blocked and reported**, never narrowed into a pass.

**Capacity reported.** `KAN-145` authoring: **1 sitting, earliest 1, ceiling 2** — one migration
file, one deliverable, one kind, population enumerable before starting; no dependency boundary
(AC 3's "or" is satisfiable in the one file). The 1→2 gap **is** the rework budget, named as such;
basis is that it is a money write. **Apply leg: hand-off to `cto`, no date from me** — requested
`cto`'s own count to carry back unchanged (`capacity-to-date` §3).

**Deliberately NOT transitioned to `Development`.** `agent/WORKFLOWS.md:60` puts the lead's
transition *after* a developer pulls, and developers self-pull from `Ready`. `KAN-145` sits in
`To Do` with no date, so nobody can pull it. Routed to `po` for the date and the `Ready`
transition; I make the `Development` call once a `backend-N` seat picks it up. No developer
hand-assigned.

**Sent:** `po` (capacity + Ready request), `cto` (apply-leg count request + the ordering
confirmation). Ruling comments posted on `KAN-145` and `KAN-146`.

**Not verified.** That the executing seat agrees with 1 sitting — that count is mine on ticket
content, not carried from an executor, and is revisable by whoever pulls it. Nor `cto`'s apply-leg
count, which is requested and outstanding. Nor whether "alone and first" is meant more broadly
than the function-body hazard — I derived that reading and asked `cto` to confirm or correct it.

**Brief calibration, per the MODEL/EFFORT rule.** No MODEL/EFFORT line on this brief; treated as
role default. The work needed high effort and got it — the brief's step 3 assumed `KAN-145` could
be sequenced straight to `Development`, and that is wrong under `WORKFLOWS.md:60`; it needs `po`'s
`Ready` gate first. A similar task should be briefed as "rule the gate and route the capacity",
not "transition it".

**Closed the loop, same day.** `po` converted the count and transitioned it. **Verified live in
Jira rather than taken from the reply** (read 2026-09-07T00:38): `KAN-145` status **Ready**,
`due_date` **2026-09-09**; `KAN-146` still **To Do**, `due_date` unset. Both match what `po`
reported.

`po`'s mapping is consistent with my count and is its own to own: earliest 2026-09-08 (1 sitting),
ceiling 2026-09-09 (the 2-sitting ceiling), one sitting per working day — so the 1-day gap carries
the rework budget I named. It also separated the legs correctly: the date covers **authoring
only**, `cto`'s apply is a further date to add rather than a correction to this one, and it flagged
the `KAN-128` 09-09/apply-slot confusion by name so nobody reads 2026-09-09 as `cto`'s apply date.
That is the exact category error `capacity-to-date` §2 warns about, caught on the way in.

**`Ready` is now stocked for this chain.** Remaining open: `cto`'s apply-leg count (requested,
outstanding) and its confirmation of my "alone and first" reading. My next action is the
`Development` transition, once a `backend-N` seat self-pulls `KAN-145` — not before.

## 2026-09-07 — KAN-155 sized (D4 subscriptions); three stale criteria found

**Task.** Supply capacity for `KAN-155` (plan-key migration `kickoff`/`pro`/`prime` →
persona-qualified keys), under new epic `KAN-154`. Custody confirmed by `pm` against `STACKS.md`
§11.2/§11.5 — accepted. **Does not activate D4**; `STACKS.md:144` still has it as backlog.

**Verified the brief before sizing on it, and both of its load-bearing claims held.** The brief
carried two things the ticket's own criteria did not contain. Rather than size on a relay — the
brief itself noted `cto` had corrected its restatement once already today — I read
`DECISIONS.md` direct: `P-039` (`:5359`), `P-040` (`:5485`), **`P-041` (`:5605`)**. Both confirmed.
`P-041` was ruled 2026-09-07 by `cpo` and **supersedes the `P-040` basis the ticket was written on**.

**Capacity — authoring leg: 1 sitting, earliest 1, ceiling 3.**
- **1 sitting.** Sequence, values, row counts and delete semantics are all ruled or measured before
  start. No judgement inside the ticket whose output the next part consumes — §1's only test.
- **The 4× scope growth (24 → 96 child rows) buys no sitting.** §1: heavier mechanical work adds
  none unless it adds a *boundary*. 96 rows is 8 keys × one 12-row template at one value set.
- **Tested the obvious checkpoint and rejected it.** "Migration written, function edit not yet" is
  a **pause, not a boundary** — that artifact is applicable and ships the regression, so it cannot
  be reviewed to a verdict. The half-file failure §1 names.
- **Ceiling 3 = two rework cycles, both named:** (a) the 96-row value surface, where
  `is_enabled = false` denies exactly like a missing row; (b) the whole-body `CREATE OR REPLACE`,
  which has bitten this codebase twice (`T-058` D1, `T-052` amendment `:6875`).
- **Apply leg: `cto`'s, no date from me.** Queues behind `KAN-128` ("applied alone and first").

**Three stale criteria reported to `po` — the first is a live safety defect.**
1. **AC 3 as written ships the regression `P-041` exists to prevent.** It seeds child rows for
   `player_pro`/`organiser_pro` only (24, `P-040`'s scope) while AC 1 inserts **all eight** plan
   rows — so six keys get no child rows, and `P-041` says those "would each grant unlimited
   notifications to their subscribers."
2. **No AC covers the `can_send_notification_now` edit** that `cpo` requires in the same change
   set (`v_plan := 'kickoff'` fallback breaks once `kickoff` is deleted). Needs AC 8.
3. **The ticket names `check_notification_rate_limit`, which does not exist.** `P-041` opens by
   correcting exactly that; the ticket copied the pre-correction name forward.

Count already assumes all three are fixed, so fixing them does not re-open the sizing.

**Not verified.** `cto`'s 82/9/3 counts and the 96-row arithmetic — carried unchanged, not
re-derived. Flagged to `po` as **single-sourced**: `P-041`'s own *Not verified* line says `cpo`
took the arithmetic from `cto` too, so two seats citing it is one source. AC 2's
re-measure-at-authoring requirement is the right guard and I asked for it to stay.

**Owed next:** `KAN-150` sizing, after `KAN-155`'s criteria settle — its scope depends on what
lands here.

**KAN-155 re-sized against the corrected ticket — count held at 1 sitting, ceiling 3.**

A hold arrived saying the ticket was missing two ACs, followed by a release saying `po` had
applied `cto`'s addendum. **Both missing items were the ones I had already found and reported
myself**, from reading `P-041` first-hand rather than sizing on the brief — so the corrections
aligned the ticket with what I had costed rather than enlarging it.

**Re-read the corrected ticket rather than assuming my earlier read still covered it.** It now
carries 8 ACs: AC 3 is 96 rows phrased as *every plan row* with a values check, AC 4 is the
`can_send_notification_now` fallback fix via `pg_get_functiondef`, and the nonexistent function
name is gone throughout. Nothing else material changed.

**Held the number against an explicit expectation that it would rise.** The brief stated both
corrections "push the number up." They do not, and the rule is documented: `capacity-to-date` §1 —
heavier mechanical work adds no sitting **unless it adds a boundary**. 96 rows is 8 keys × one
12-row template at one value set; AC 3 and AC 4 do not consume each other's output; the split at
"migration written, function edit not yet" re-tested as a **pause, not a boundary**. Risk is banked
in the ceiling (3, two named cycles), not spent on a sitting. This is the volume proxy §1 names,
and refusing it is the whole point of the unit.

**One structural finding handed to `po`:** AC 3's before/after assertion and AC 4's behavioural
effect **cannot be checked by the author** — only after apply, and apply is `cto`'s. So that
verification lands in `po`'s acceptance gate, not in an authoring sitting. Counted separately per
§2, so the number is unaffected, but `po`'s gate on this ticket is unusually heavy and it should
know that before scheduling rather than at review.

**Process note worth keeping.** `cto` found the ticket gap by re-opening the artefact instead of
trusting `po`'s summary of what it had written — a recipient's summary faithfully reports what the
writer believes it did, which is exactly what a partial delivery cannot reveal. My own independent
catch came from the same move: reading `DECISIONS.md` rather than sizing on the brief that
summarised it. Two seats, same control, same day.

**Owed next:** `KAN-150`, once `po` sends it. Expect it small — `P-041` says its `'prime'` branches
are dead-code tidying with no behaviour change — but size it by boundary test, not by analogy.

**KAN-155 ceiling revised down 3 → 2 on new evidence; sittings unchanged at 1.**

`cto` measured two composite constraints today: `subscription_features_plan_key_feature_key_key`
UNIQUE `(plan_key, feature_key)` and `notification_hourly_caps_pkey` PRIMARY KEY
`(plan_key, priority)`. An AC2-repoint + AC3-seed collision on `player_free` therefore **aborts**
rather than corrupting silently. That retires the expensive shape, so I dropped rework cycle (a).
Cycle (b) — the whole-body `CREATE OR REPLACE` — stands untouched. **Sitting count unmoved at 1**:
this is a budget revision, not a re-size, and the boundary analysis did not change.

**Corrected an overclaim in the evidence I was adopting.** `cto` wrote *"no path where the
migration reports success while carrying duplicate **or wrong-valued** entitlement rows."* The
constraints are on **key columns only** and say nothing about `is_enabled` or `max_per_hour`.
Duplicates are loud; **wrong values are still silent** — a seed carrying `pro`'s values inserts
cleanly with correct keys. That is the failure the ticket itself names as likeliest (AC 3 item 6,
copy-paste). Raised to `cto` as its call to confirm or correct, and told `po` that **AC 3's values
check is NOT made redundant by the measurement and must stay as written** — the live risk is
someone arguing the new constraints prove it unnecessary. Adopting a correction is not a reason to
adopt its quantifier: the constraint facts were right, the scope word was too strong.

**Carried `cto`'s `ON CONFLICT` ruling into the brief and asked `po` to make it a criterion.** Seed
INSERTs take **no `ON CONFLICT`** — it would convert the loud abort into a silent no-op. Deliberately
opposite to `T-049` Decision 2 (tolerable duplicate on a replayed webhook vs. a defect on a one-shot
structural migration). `T-049` is fresh on this chain and the habit pulls the wrong way.

**Refused to guess a count I am meant to carry unchanged.** `cto`'s message closed with *"the apply
leg remains mine, still 1 sitting, still ceiling 1"* while distinguishing the zero-row constraint add
from the data-migration apply — unattributable to `KAN-145` or `KAN-155`. Asked for both explicitly
rather than assigning it myself. `capacity-to-date` §3: a shared-seat count is requested and carried,
never inferred.

**Open:** `cto`'s apply-leg counts for `KAN-145` and `KAN-155`; its confirmation of the wrong-value
gap; its answer on whether `KAN-128`'s "alone and first" is scoped to the function-body hazard.
`KAN-150` still owed once `po` sends it.

**Both apply-leg counts received from `cto` and carried unchanged; a phantom blocker caught.**

`cto` answered all three open items. Counts carried to `po` verbatim, attributed, unadjusted
(`capacity-to-date` §3 — requested and carried, never confirmed by a third seat):

| Ticket | Apply leg (`cto`'s own count) | Blocker |
|---|---|---|
| `KAN-145` | **1 sitting, ceiling 1, datable** | none — waits only on authoring (dated 09-09) |
| `KAN-155` | **1 sitting, ceiling 2, datable** | none of `cto`'s; queues behind unstarted authoring |

`cto` set `KAN-155`'s ceiling at 2 **specifically on the wrong-value failure mode I raised** — if
the counting query passes and the values check fails, reconciling is a second sitting. Correct
basis, and a further reason AC 3's values check stays.

**`cto` withdrew the "wrong-valued" claim in full** — *"The second half is false and I withdraw
it… duplicates are loud, wrong values are silent"* — and is sending the correction to the ticket
rather than leaving it in a thread. My authoring ceiling of 2 stands; it rested on the duplicate
half.

**Caught a phantom blocker that would have stalled the money chain, and it is a repeat.** `cto`
reported `KAN-141`/`KAN-145` have *"no seat to land on"* because `devops` is unspawnable.
**Measured `agent/roles/cto.md:91-99`: still the superseded 2026-08-27 PO decision routing all
production writes through `devops`.** `G-002` (2026-08-28) narrowed it the next day;
`CONTRACT.md:242` gives writing to `cto` only. **This is the exact section `cto` diagnosed and
escalated this morning (`T-061` 2nd addendum) — unamended, so it is still read first and produced
the wrong conclusion a second time in one day.** Handed `cto` back its own correction, told `po`
not to leave the apply legs undated on a blocker that does not exist, and escalated the unamended
file to `pm` as no longer latent. Also flagged that I checked only `cto.md` and a sweep of the
other thirty role files is unowned.

**Corrected my own premise on the `KAN-128` queue order.** I had ruled `KAN-145`'s apply queues
behind `KAN-128` partly because I read `T-052` as requiring it. `cto` confirmed the scope is narrow
— the hazard is `CREATE OR REPLACE` reverting `ON CONFLICT`, and these objects are disjoint — so
**`T-052` does not require it and my premise was wrong.** I am keeping the order as **my own choice
with a named reason** (one money migration in flight at a time, so a bad apply has one suspect,
`T-058` having established three dead write paths) and a named cost (**near zero** — 09-09 timing
already separates them). Told `cto` to say so if it ever becomes expensive, and I drop it: a
preference must not survive becoming costly.

**Reported to `pm` as a dependency, not a date request:** `cto`'s queue now holds two
authored-but-unapplied migrations. One seat holding every production write is a throughput question
for `pm` if D4 work keeps landing.

**Open:** `KAN-150` sizing, once `po` sends it.

**KAN-155 dated from a superseded ceiling; KAN-150 sized and its authoring released.**

**Verified live before acting** (`KAN-155` Ready/09-10, `KAN-145` Ready/09-09, `KAN-150` To Do).
`po` converted **ceiling 3**, which my revision to **2** had already superseded — we crossed.
Asked for **09-09**, while saying plainly it is `po`'s call and that a generous ceiling is slack,
not a defect. The reason to correct it is not the day: it is that the two-column method only works
if the ceiling on the board is the current one, and an unexplained extra day is the silent collapse
back to a single number the pair exists to prevent. Asked `po` to state a reason on the ticket if
it holds 09-10 for an independent one.

**`KAN-150` — 1 sitting, earliest 1, ceiling 2.** Two `CREATE OR REPLACE` bodies, fully specified,
scope fenced to two branches by AC2; neither consumes the other's output, so no boundary — two
functions is volume, not a checkpoint. Ceiling 2 carries one cycle: the whole-body replacement trap,
present **twice** here.

**Ruled its authoring free now — the useful part.** The ticket says "blocked on `KAN-155` landing";
**I ruled that binds the apply, not the authoring.** `cto`'s stated reason is risk profile
("bundling turns a trivially-revertible data change into one carrying a function rewrite") — an
argument about landing together, not about when the file is written. The bodies are **disjoint**
(`can_send_notification_now` vs `calculate_notification_score`/`should_bypass_quiet_hours`), so
AC3's live-catalogue requirement is satisfiable today; and removal is behaviour-preserving on both
sides of the rename by the ticket's own reasoning. Same shape as the `KAN-145` ruling: **authoring
free, apply ordered.** This stocks `Ready` instead of leaving a ticket parked.

**Flagged to `cto` as derived, not received** — with an explicit invitation to correct it, because
the last sequencing constraint I inferred from `T-052` had a wrong premise that `cto` caught. If it
meant authoring too, only the date moves; the count is unaffected either way.

**Could not date `KAN-150`'s apply** — it chains behind `KAN-155`'s apply, which is `cto`'s undated
leg. `capacity-to-date` §4: sized the sizeable part, named the blocker and its owner. Warned `cto`
a third apply count is coming so it is not a surprise.

**Accepted a correction on my own conduct.** `team-lead` recorded that its "both corrections push
the number up" was an inference stated as a finding, and that holding the count was right. Noted
without re-litigating: the volume proxy is exactly what §1 exists to refuse, and the same seat had
earlier suggested me for `KAN-155` on adjacency. Useful distinction it added, which I had collapsed:
**82/9/3 are measurements that can go stale; 96 is arithmetic that cannot while its inputs hold** —
and `9`/`3` set the matrix width, so a tenth `feature_key` silently makes it 8 × 13. AC3's "exactly
9 + 3 on completion" fails loudly in that case, so the guard holds; the width is the input worth
re-deriving. `cto` separately declined to re-run its own query on the grounds that a second
identical number from the same seat is the appearance of corroboration, not corroboration — right,
and a sharper form of my own flag.

**Open:** `po`'s decision on 09-09 vs 09-10; `cto` on the `KAN-150` authoring reading; `cto`'s
`KAN-150` apply count once `KAN-155` has a slot.

**KAN-155's apply left `cto`'s authority — and "the PO" in `G-002` is the CEO, not the `po` seat.**

`cto` re-read `G-002` in full and **withdrew its own `KAN-155` apply count** — not the number, the
seat. Condition 3 is *"schema/privilege/definition changes only — not bulk data mutation"*;
`KAN-155` `UPDATE`s **82 live `user_subscriptions` rows**. `G-009` covers security remediation and
excludes product-data corrections. Correct, and adopted without argument.

**Checked the destination rather than relaying it, and it was wrong.** `cto` wrote the apply
*"requires the PO to apply it personally"* — **verbatim from `G-002` and accurate as a quote.**
Measured the sources because that phrase decides who touches 82 live rows:

- `019` (2026-08-27): *"only the PO can authorise a production write"* — and `G-002` opens *"The PO,
  live in chat, directly instructed the assistant…"*
- **`CONTRACT.md:242`**, the governing row: *"**User-data mutation is CEO-only (`019`)** except
  security-remediation changes meeting `G-009`'s three tests."*

**In `019`/`G-002` "the PO" is the human decision-maker — Moataz — written before `po` existed as
an agent seat.** `CONTRACT.md:242` is that rule already translated; `G-002`'s body is not. **Relayed
unchecked, it routes a live-data money migration to Horemheb, who has no such authority and would
have had to refuse it.** Same failure class as the stale `cto.md` section, one layer down: not a
stale document but a **stale term inside a live one**, where the quotation is correct every time.
Flagged to `cto` as worth recording durably, since the next seat to quote condition 3 hits it
identically.

**Consequence, worse than a re-route: `KAN-155`'s apply is in no agent's queue.** I cannot request
a sitting count from the CEO the way I request one from `cto`, so **that leg is undatable by me**.
Told `po` to name the CEO as holder rather than leave it blank so it does not read as an oversight.

**Reported to `pm` as a D4 planning fact:** its throughput ledger had one bottleneck (`cto` as sole
production writer); **there are two**, and the second is narrower — every D4 migration touching
existing rows needs a CEO action, on a stack of 110 features on a live billing rail. Not asking for
the rule to be relaxed; `019`'s reasoning is sound. Offered one judgement: the CEO should know this
as a standing property of D4, not as a surprise on `KAN-155` — and that routing is `pm`'s.

**Unaffected, stated so nothing over-corrects:** `KAN-155` authoring untouched (1 sitting, ceiling
2, 09-09 request stands); `KAN-145` **1 sitting ceiling 1** and `KAN-141` **1 sitting** stay
`cto`'s, both definition-only and inside condition 3. **Carried `cto`'s `G-002` condition-1
addition, which I had not been counting:** the `KAN-67`-format migration comment posted to the
ticket *before* applying, plus `G-006`'s claim-comment re-checked immediately before — inside its
sitting, as it stated.

**Sharpened rather than mooted: `KAN-150`'s apply stays `cto`'s** — two `CREATE OR REPLACE`s,
definition-only, still inside condition 3 even though the ticket it chains behind has left it. So
if `cto` confirms its authoring is free, it can be written and posted while `KAN-155`'s apply waits
on a CEO action, instead of the chain idling behind something nobody here can schedule.

**`pm` confirmed** it escalated the stale-role-file issue to `main`/CEO verbatim and has taken the
single-writer throughput point onto its own ledger.

**Ceiling ruled: 3, reverting my own reduction. I was wrong and `cto` caught it.**

Three accounts of the ceiling were in circulation and `po` had already dated on one. Ruled it
rather than letting agreement between other seats settle a number that is mine.

**Both originally-named cycles stand; nothing was retired.** (a) the **96-row value surface**
(`is_enabled = true` required, so a present-but-disabled row denies exactly like a missing one);
(b) the **whole-body `CREATE OR REPLACE`**. **Ceiling 3, `due_date` back to 2026-09-10.**

**Why the reduction was wrong.** `cto`'s composite constraints catch **duplicates**. **Duplicates
were never one of my two priced cycles** — (a) was always the *value* surface. The measurement
retired nothing from the 3; it added a new guard against a risk that was never in the number. Real
safety improvement, worth zero on the ceiling.

**The proof was my own argument, which I failed to apply to my own figure.** I established that the
constraints are key-column-only — uniqueness is not correctness — which is exactly why AC 3's
values check is load-bearing. **That same fact means cycle (a) was never covered.** I withdrew the
ground under my own reduction and did not carry the consequence back to the number. Tested both
failure modes to be sure: wrong values in non-key columns — not caught; missing rows — not caught,
since a UNIQUE constraint never forces a row to exist.

**The lesson worth keeping, because it is not "check your arithmetic".** When you demolish a claim,
check what you had already changed on the strength of it. I lowered a number on `cto`'s claim, then
personally refuted that claim, and left the number down. **The refutation and the figure resting on
it were two separate acts and only one got updated.** The sitting count never moved — this was only
ever a rework-budget question — which is why it was easy to miss.

**Also corrected `po`'s rendering on the ticket:** it read *"the duplicate-row rework cycle was
retired"*. **There was no duplicate-row cycle** — that phrasing came from the shape of `cto`'s
measurement, not from my naming, and would have left the board traceable to a cycle that never
existed. Posted the full ruling as a ticket comment rather than a thread reply, on my own argument:
a ceiling nobody can trace to a named cycle is the silent collapse the two-column method prevents.
That argument cut against me here and the correction was worth more than the day.

**`KAN-150` fully settled and unaffected.** `cto` **verified my disjointness premise rather than
agreeing with it** — measured that **neither `KAN-150` function carries a hardcoded `'kickoff'`
fallback** (only `can_send_notification_now` does, which is `KAN-155`'s), so no hidden coupling
through the rename. Authoring **released**: mine, 1 sitting, ceiling 2. Apply: **`cto`'s, 1 sitting,
ceiling 1** — definition-only, so it stays inside condition 3 **even though `KAN-155`'s apply left
it**. Asked `po` to date and `Ready` it: the chain does not idle behind a CEO action.

**`cto` recorded my term-drift finding as `CONVENTIONS.md` §12f** — *a term can go stale inside a
document that is still live, and the quotation stays correct* — with the operative rule I derived:
**where a decision's body and a `CONTRACT.md` row disagree on WHO, the row governs.** It noted this
is **permanently unfixable at source** (decisions are superseded, never rewritten; `G-022` puts role
custody off the seats a rule binds), which is what makes the check load-bearing rather than a
stopgap. Sibling of §12e: both fail by being accurate.

**`pm` verified my `CONTRACT.md:242` citation before relaying** and has both D4 bottlenecks on its
ledger. **Nothing outstanding from me.**

**Closing state, verified live 2026-09-07.** Board read directly rather than from `po`'s account:

| Ticket | Status | `due_date` (authoring) | Apply leg |
|---|---|---|---|
| `KAN-145` | Ready | 2026-09-09 | `cto` — 1 sitting, ceiling 1 |
| `KAN-150` | Ready | 2026-09-09 | `cto` — 1 sitting, ceiling 1 |
| `KAN-155` | Ready | 2026-09-09 — **should be 09-10** | **CEO personally** — no agent count exists |

Three tickets stocked in `Ready` where the day started with one gated and two unsized. Flagged to
`po` that `KAN-155` still carries 09-09 against my withdrawn ceiling of 2 — my revert crossed with
its `KAN-150` work, so no action beyond the flag.

**Also asked `po` to drop a caveat that has gone stale in my favour.** It had recorded the
`KAN-150` authoring-free reading as *my inference, not `cto`'s confirmation* — **accurate when
written, and no longer true.** `cto` has since confirmed it and verified the premise by measuring
the catalogue. Left uncorrected it gives a reader standing to park a ticket that is genuinely
released. Worth noting the symmetry: I have spent the day telling other seats their claims were
stale, and this one was stale in the direction that flattered me. Same check either way.

**Nothing outstanding from me.** No capacity numbers owed, both `cto` legs carried unchanged, the
CEO leg named rather than left blank.

**Final board, verified live (not from `po`'s account):** `KAN-145` Ready/09-09 · `KAN-150`
Ready/09-09 · `KAN-155` Ready/**09-10** — the revert landed. All three stocked in `Ready`; apply
legs attributed (`cto` for `KAN-145`/`KAN-150`, **CEO personally** for `KAN-155`). Day opened with
one ticket gated and two unsized. **Nothing outstanding from this seat.**

Saved one durable lesson to `.claude/agent-memory/team-lead-4/` — *refutation orphans dependent
figures*: when you demolish a claim, re-check what you already changed on the strength of it. Kept
because it is about how this seat reasons, not about repo state; the term-drift rule from the same
day is already in `CONVENTIONS.md` §12f and is deliberately not duplicated.

---

## 2026-09-07 — resumed after the project-wide halt; G-028 re-seated three apply legs, and the brief that told me so had it backwards

**Re-verified the board live before acting, per the brief's own instruction, and the verification
mattered — the brief was wrong on the most consequential point.**

**What I found on re-verification.** Board read directly, not from any account of it:

| Ticket | Status found | `due_date` | Parent |
|---|---|---|---|
| `KAN-145` | Ready | 2026-09-09 | `KAN-127` |
| `KAN-150` | Ready | 2026-09-09 | `KAN-154` |
| `KAN-155` | Ready | 2026-09-10 | `KAN-154` |
| `KAN-141` | QA-Test | — | `KAN-127` |

Two corrections to the brief's picture of my own queue. **It named `KAN-155` and `KAN-150` and
omitted `KAN-145` entirely** — a third Ready ticket in my slice, and as it turns out the only one of
the three that `G-028` fully unblocks. And `KAN-155` carried **09-10**, not the 09-09 I flagged as
wrong yesterday: my revert had landed, so that flag was already resolved.

**The substantive finding: the brief inverted `G-028` on `KAN-155`, in both halves.**

I was told *"`KAN-155`'s and `KAN-150`'s apply legs are no longer `cto`'s hands to hold; they're
`backend-4`'s."* `G-028`'s own text names `KAN-155` under **"Left open, deliberately"** and says it
**"stays with the CEO personally"** — 82 live `user_subscriptions` rows — and states in terms that
**"`019`'s reservation of user-data mutation to the CEO is untouched."** Acting on the brief would
have handed a junior an apply that breaches `019`.

**And the half the brief missed is the half that actually moved.** `KAN-155`'s ticket text (AC10,
and its "Not set" section) assigns the **authoring** to `cto`. Under `G-028` `cto` does not work
with its hands — *"الـ CTO مش بيشتغل بإيديه… مش بيكتب migration بإيديه."* So on that ticket
**authoring moves `cto` → `backend-4` and apply stays CEO** — the exact inverse of what I was told,
on both legs. `cto` keeps AC10's substantive duty but now writes that brief over `backend-4`'s SQL
rather than its own.

**What I assigned.** All to Team 4 (`backend-4`/Min), which holds the whole context from `KAN-141`:

1. **`KAN-145`** → Development. Both legs `backend-4`'s. **The only one whose apply is unblocked**,
   so it goes first and can run the complete cycle today. `KAN-140` depends on it landing.
2. **`KAN-155`** → Development, **authoring only**. Critical path: `KAN-150`'s apply chains behind
   this one's apply, so this authoring is what eventually lets the CEO act.
3. **`KAN-150`** → **left in `Ready` on purpose.** Authoring is free, but the apply is CEO-blocked
   via `KAN-155`. Moving it to Development would park an authored-but-unappliable migration in an
   in-flight column — the exact stranded state the same-day audit found on `KAN-119`/`139`/`142`.
   **Better an honest `Ready` than a Development column that lies.** It moves when `KAN-155` applies.

**Sizing: no number changed, and I checked rather than assumed.** `KAN-145` 1+1 sittings ceiling 1
each; `KAN-155` authoring 1 sitting ceiling 3 (both named cycles intact — the composite constraints
prove uniqueness only and never touch `is_enabled`/`max_per_hour`, so AC3's values check stays
load-bearing); `KAN-150` authoring 1 sitting ceiling 2, apply 1/1 undated. **The hands moving does
not change the work** — same DDL, same four `G-002` conditions, same live re-measurement, same
verification block.

**Two real consequences I did record, because they are not nothing.**

*Direction of travel, good:* the apply legs come **off a shared single-writer seat onto a seat I
route to.** Under `capacity-to-date` §3 I quote work sized against `cto` as a **cost**, never a
date, because I do not own its queue. `KAN-145`'s apply is **the first leg on that ticket I have
been able to date rather than merely price.**

*Load transfer, worth naming:* those sittings did not evaporate, they **relocated onto my team** —
**+2 sittings on `backend-4`, −2 on `cto`** across `KAN-145` and `KAN-150`. I prefer holding
sittings I can schedule to costs I can only quote, but a transfer that goes unrecorded becomes a
surprise later.

**I declined to price the new confirmation gate as a sitting, on measurement rather than optimism.**
`KAN-141`'s full author → confirm → apply → verify cycle ran in comments `10684` (09:22), `10685`
(09:26), `10687` (09:29) — **seven minutes**. One sample and a light migration, so I said so, but it
settles that the gate is not a day-scale cost while `cto` is responsive.

**Flagged to `po`, not fixed by me:** `KAN-145`'s description still reads *"Apply is `cto`'s
(`CONTRACT.md:242`)"*, and `KAN-155`'s AC10 still has `cto` authoring. Both pre-`G-028`. **Ticket
text is not mine to write** — and `CONTRACT.md:242` is itself CEO-custody under `G-022`, so it will
keep reading wrong no matter who notices. Told `backend-4` to expect that rather than trust it.

**Nothing outstanding from this seat.** Three tickets assigned, one deliberately held with its
reason written down, one `019` breach prevented.

### Same day, later — `backend-4` returned `KAN-145` authored, and caught me contradicting myself

**Authoring leg done in the 1 sitting I priced** — `20260907100000_kan145_payment_intents_booking_fk.sql`,
committed `a7dbaa0`, posted for `cto` confirmation as comment `10703`. **Nothing applied.**

**The thing worth recording is not the delivery, it is what it exposed in my own record.**

`backend-4` asked whether `T-052`'s *"`KAN-128` authored and applied alone and first"* still ordered
`KAN-145`'s apply. **It does, and I had written the opposite three hours earlier.** Comment `10663`
(00:34): *"the apply queues behind `KAN-128`'s **in `cto`'s queue**."* Comment `10696` (09:59):
*"nothing blocks this ticket."*

**How the error got in.** `G-028` moved the apply off `cto`. I had recorded the ordering **in terms
of `cto`'s queue** — so when that queue stopped mattering, the constraint looked like it dissolved
with it. **It did not.** "Applied alone and first" is a property of the **migration sequence**, not
of whose queue holds the migration. **Reassigning hands does not reorder a database.**

**This is the second time in two days I carried a conclusion past the collapse of its stated
reason** — yesterday the `KAN-155` ceiling, today this. Both caught downstream of me, never by me.
I generalised the memory accordingly: the trigger is not "refutation", it is **any disappearance of
stated ground — refuted, superseded, or reassigned** — and the structural fix is to **state durable
constraints in terms of the artifact, not the actor**, because actor-phrased constraints look
retired the moment the actor changes.

**Verified rather than accepted:** ran `list_migrations` myself. Latest applied is
`20260907052826 kan141_...`; **no `KAN-128` migration appears at all.** `backend-4`'s reading exact.

**Withdrew my own sentence publicly** (comment `10704`) rather than quietly fixing the line, and
**withdrew the apply date with it.** Authoring `due_date` 09-09 met and unaffected; the apply is
undated pending `cto`. **I did not reinterpret "alone" in my own favour on a ticket I own** — `pm`
and I set that sequencing jointly and `T-052` says it is not reopened, so `cto` arbitrates and
`backend-4` routed it correctly. Told `backend-4` explicitly not to apply even if `cto` blesses the
SQL, until the *ordering* is ruled.

**`backend-4`'s best catch, which cost nothing because it measured:** `idx_payment_intents_booking`
**already exists.** Had it not, this ticket forced a choice between breaching AC4 ("no other schema
object touched") and shipping `ON DELETE RESTRICT` with a sequential-scan cliff on every
`venue_bookings` delete. A real escalation that never had to happen. Recorded on the ticket.

**Released `KAN-155` authoring to proceed in parallel** — I gated only `KAN-150` behind it, and my
one-money-migration-in-flight preference governs **applies, not authoring**. A developer idling
through a confirmation round is the stall this seat exists to prevent.

**Second data point on the `G-028` gate:** `cto` turned `KAN-145`'s confirmation round in seven
minutes, matching `KAN-141`. I continue not to price it as a sitting, now on two samples rather
than one.

### Same day, close — `KAN-145` landed, `KAN-155` authored, and I reversed my own hold on `KAN-150`

**Delivered by Team 4 (`backend-4`/Min):**

| Ticket | State | Legs |
|---|---|---|
| `KAN-145` | **In Review** | authoring + apply both done, applied and verified |
| `KAN-155` | Development | **authoring done** (`cb5edf1`), apply refused and outstanding (CEO) |
| `KAN-150` | Development | released by me, authoring starting |

**`KAN-145` is complete and `KAN-140` is unblocked.** `backend-4` asserted `confdeltype='r'` explicitly
rather than merely that an FK appeared — **a `CASCADE` FK would have satisfied "an FK exists" while
being precisely what `T-061` rejects.** Probe flipped `P0001` → `23503`. Every number I priced held:
1 + 1 sittings, ceiling 1 on both, no rework cycle consumed.

**Second self-correction of the day, and I reversed myself rather than defend the call.** I had held
`KAN-150` in `Ready` citing the `KAN-119`/`139`/`142` stranded state. **I had misread that
pathology.** Those tickets were stranded because their work had **shipped unseen** — the defect was
**invisibility, not duration**. A ticket in `Development` carrying a dated comment naming its blocker
is the opposite of stranded. **I generalised "don't let tickets sit" from a case that was really
"don't let tickets go unseen," and I did it in the direction of idling my own team** — the one
direction a lead should be most suspicious of its own reasoning. Released in comment `10708` with
the reasoning written down rather than quietly moved.

**What I did NOT relax:** the apply stays blocked behind `KAN-155`'s apply. And I attached a
condition that costs nothing because I had already priced it — **both function bodies must be
re-measured at apply time and re-authored if drifted**, since authoring and apply are now separated
by an indefinite CEO-held wait, making the whole-body `CREATE OR REPLACE` trap likelier here than
anywhere it has bitten before.

**`backend-4` corrected itself on a premise it had given `cto` to rule on** — it asserted both
migrations touch `payment_intents`; `cto` read the file and found them **disjoint at the object
level**. I told it why that class matters more than a wrong conclusion: **a wrong premise attached
to a question you want settled acquires the senior seat's authority when they rule on your framing.**
Said plainly that I was not lecturing from above, having made two of the same class today.

**Best thing in its `KAN-155` work, and better than the ticket asked for:** the ticket demanded
*care* not to copy `pro`'s values; `backend-4` seeded by `SELECT` from the rows just repointed to
`player_free`, making `pro`'s values **structurally unrepresentable**. Converting a discipline
problem into an impossibility is the right move whenever it is available. Its live measurement
showed `pro` really does carry `quiet_override_high=TRUE` and caps `10/25/50` — **the trap was real,
not theoretical.**

**Routed out of my stack:** `venues` CASCADE→ `venue_spaces` CASCADE→ `venue_bookings`, with
`RESTRICT` now on the payment side — so once data exists, **deleting a venue whose booking carries a
payment fails with `23503`.** Blast radius is *venue deletion*, which is not where anyone would look.
In the migration header, but a header only reaches someone already in the file. **D3 is not my stack
and this is not mine to ticket** — sent to `team-lead` for the owning lead or `po`.

**Gate evidence now two samples:** `cto` turned confirmation in seven minutes on both `KAN-141` and
`KAN-145`. Still not pricing it as a sitting.

**Outstanding, neither mine:** `KAN-155`'s apply (CEO), `KAN-150`'s apply behind it. Five commits
unpushed and waiting on `devops`. **Nothing outstanding from this seat.**

### Close of day — `KAN-150` authored; the D4 backend queue is dammed, and I found a ticket dated as if it weren't

**`KAN-150` authoring done** (`4c0f4c4`, posted for `cto` as comment `10712`). **All three assigned
tickets delivered to the extent they are Team 4's.** Six commits unpushed, `devops`'.

**`backend-4` found a new form of the `T-055` trap and reported it instead of taking a free pass.**
`T-055`'s recorded form is a function that **raises** before reaching the code under test. This is
the same trap by **early return**: `notification_scores` holds **zero rows**, so
`calculate_notification_score` hits `IF NOT FOUND THEN RETURN 1` and returns a plausible `1` for
every input, never reaching the Prime boost. **A before/after probe reads "identical" for reasons
having nothing to do with the change.** The raising form announces itself; **this one hands you a
green tick.** It established preservation by construction instead — always-false guard plus a
side-effect-free read — which is stronger than the probe would have been had it worked. Routed to
`cto` as worth recording beside `T-055`, since you cannot catch it by watching for errors.

**That report is why I went looking at the rest of `Ready`, and the rest of `Ready` is the story.**

**The dam.** Every D4 backend ticket is blocked behind one of two applies, **neither Team 4's**:
`KAN-128` (Development, authored, **not applied** — verified, latest applied is still
`20260907052826 kan141`) blocks `KAN-130`/`KAN-131`/`KAN-138`; `KAN-155`'s CEO-held apply blocks
`KAN-150`'s. The remaining six `Ready` tickets are D6 frontend, content, or D1.

**So I told `backend-4` to stand down rather than pull.** `T-047`: an idle seat costs nothing, a
wandering one serialises everybody. **Team 4's backend is stopped for structural reasons, not
capacity ones** — and I escalated that as `pm`'s call rather than manufacturing work to look busy.
**An empty `Ready` is normally my failure; this one I cannot stock, because what would fill it is
behind two applies I do not hold.** Said so plainly rather than softening it.

**The board defect, and it is the kind that bites someone who trusts the board.** `KAN-138` edits
`settle_game` — **one of `KAN-128`'s five writer functions** (`T-052`'s amendment names
`settle_game:17079`, insert `:17154`). A whole-body `CREATE OR REPLACE` authored before `KAN-128`
applies **silently reverts its `ON CONFLICT` clause**, no error at apply time. **Identical to the
hazard `T-052` already ruled on for `KAN-131` — and `KAN-131`'s summary says "after `KAN-128`" on
its face while `KAN-138`'s says nothing.** Worse, `KAN-138` had acquired `due_date` 2026-09-13 while
its own description reads *"No executor or capacity number yet — `team-lead-4`/`pm` size and
schedule it."* **I did not produce that date.** Its two siblings with the same blocker correctly
carry none; **the asymmetry is the defect.**

Ruled its authoring behind `KAN-128`'s apply — **applying an existing `cto` ruling to a function
that ruling already names, not inventing one**, and the sequencing half is mine on `T-052`'s own
record. Sized 1 sitting / ceiling 3 (cycle (b) disappears and it drops to 2 if the ordering is
honoured). **No date from me:** it now chains behind a queue I do not own, which under
`capacity-to-date` §3 is a cost. Flagged to `cto` to confirm, and to `po` to strip the date.

**Protected `backend-4`'s ceiling from a scope change.** If `cto` rules
`should_bypass_quiet_hours` should be **dropped** rather than reduced to `RETURN false`, that is a
**new ticket, not rework on `KAN-150`** — AC2 fences the ticket to two functions and two branches.
Told it so unprompted, so a design ruling does not get charged to its rework budget.

**Routed out of D4:** `notification_scores` empty → the whole notification weighting system inert in
production (**D6**); the venue-deletion cascade from `KAN-145` (**D3**).

**Nothing outstanding from this seat.** Everything assignable is assigned or delivered; what remains
is two applies and a `pm` decision, none of them an agent's to take.

### Correction to the entry above — "six commits unpushed" was wrong, and so was the correction to it

**Appending rather than editing, per the rule I applied to `KAN-145` this morning: the fix for a
stale record is a dated correction on top, not surgery underneath.**

**I wrote "six commits unpushed, `devops`'" in the entry above and repeated it to `team-lead`.
Wrong.** `backend-4` corrected itself to "two unpushed, plus `cto`'s docs uncommitted in a dirty
tree." **Also wrong by the time I read it.**

**Measured myself, authoritatively — `git ls-remote` against the actual remote, not a local ref:**

- `origin/Canary` tip = **`8363a0f`**, and local `HEAD` = **`8363a0f`**. Identical.
- **All seven commits are pushed.** Verified individually with `git merge-base --is-ancestor`:
  `4c0f4c4` and `6a353e6` — the pair `backend-4` called unpushed — are both ancestors of the remote
  tip.
- **`cto`'s documentation is committed AND pushed**, as `8363a0f`: `SCHEMA.md` §8a, `CONVENTIONS.md`
  §6g and §12g, plus the duplicate-§6c renumber to §6f.
- Working tree clean apart from an untracked `.claude/`.

**Both risks `backend-4` escalated are closed.** The docs are not stranded in a dirty tree, and
§12g — the rule that just prevented a production regression — is on `Canary`.

**Three successive snapshots of the same fact, each stated as standing, each expired before it was
read.** Mine, then `backend-4`'s correction of mine, then the truth. `backend-4` diagnosed its own
error as *"a snapshot that expired"* — correct, but **its correction expired the same way, between
writing and my reading it.**

**So the lesson is not "measure more carefully."** It is that **push state is not a fact, it is a
reading**, and a reading has a timestamp. **The fix is to stop stating volatile facts as standing
ones** — cite the command and the moment, or do not assert the number. And the part that is mine
specifically: **I re-broadcast `backend-4`'s figure to `team-lead` without re-deriving it, which
made me its author.** A number I repeat is a number I have asserted. Saved as a memory.

**Also now stale:** `backend-4`'s offer of *"the `CONVENTIONS` §6g draft `cto` has not yet ruled
on."* §6g is committed and pushed in `8363a0f`. **`cto` has ruled and it has landed.**

**One item genuinely open and unchanged:** `KAN-155`'s migration (`cb5edf1`) is on `Canary`.
`backend-4` verified no CI path can apply it — neither workflow references supabase and
`scripts/cloudflare-build.sh` does not touch migrations — so the residual risk is **manual only**: a
CEO-reserved migration mutating 82 live `user_subscriptions` rows now sits in the release branch
where a seat running `supabase db push` would execute it. **Not an emergency, not a reason to
revert**, and its file header states the CEO-only boundary in the first twenty lines. Recorded so it
is not rediscovered as new.

### Correction to the correction — one unpushed commit, not zero; and `backend-4`'s mechanism was wrong

**Reading at 2026-09-07T06:29:52Z**, `Dabbler/dabbler-code`: HEAD **`fed3b01`**
(*"docs(migration): mark should_bypass_quiet_hours dormant, not abandoned (KAN-150)"*), remote
`Canary` tip **`8363a0f`**, `fed3b01` **ahead of the remote and unpushed.**

`backend-4` committed it implementing `cto`'s AC1 ruling on `KAN-150` (comment `10716`) — **after my
measurement and while I was writing the message reporting zero.** My reading was accurate and
expired in under a minute. **Fourth successive statement of this one number in the exchange; three
were true when made and false when read.** The rest of my report stands: the other seven are pushed
and `cto`'s docs did land in `8363a0f`.

**Routed to `devops` via `team-lead`:** `fed3b01` must travel with the next push. Not urgent —
comments-only, executable bodies byte-identical, and `KAN-150` cannot apply until `KAN-155` lands.
But left behind, `devops` holds a file that **does not match the version `cto`'s ruling is recorded
against**, which is a bad thing to discover at apply time. Neither of us attempted the push.

**The part worth keeping is `backend-4`'s mechanism, which was wrong in the reassuring direction.**
It attributed the miss to `CONVENTIONS.md` §12b — *concurrent seats do not share a working tree* —
and concluded I had measured a different tree. **We share one.** `git worktree list` shows exactly
one worktree at that path (the only other entry is an unrelated prunable detached scratchpad), and
my HEAD now **is** `fed3b01`. We measured the **same tree 42 seconds apart**.

**Why I corrected it rather than accepting a right answer:** a seat that believes it holds a private
tree will assume its working-tree state is its own. It is not. **A shared tree means concurrent
uncommitted edits by two seats occupy the same files and can collide** — the inferred fact is
comforting, the real one demands more care. This is the same shape I put to `backend-4` on `KAN-145`
this morning: **a correct conclusion resting on a premise that does not hold.** It has now run in
both directions between us inside one day, which reads as the seam working rather than either seat
being careless.

**Accepted from `backend-4` without reservation:** the symmetry on bare numbers. I took the author's
half — repeating a figure makes me its author — but **the issuer's half is equally real: a naked
number invites the relay.** Attach the command and the moment when issuing, not only when consuming.
Both halves are now in the memory.

**Nothing else changed.** D4 backend still dammed behind `KAN-128`'s and `KAN-155`'s applies;
`backend-4` deliberately idle; `KAN-138` awaiting `po` (date) and `cto` (sequencing); `KAN-155`'s
migration on `Canary` carrying a manual-only risk no CI path can trigger.

### `backend-4` accepted the shared-tree correction and turned it into a rule worth propagating

**It verified rather than accepted** — `git worktree list` and `git rev-parse --git-common-dir` in
its own hands — and withdrew the `§12b` diagnosis. Its account of its own error is sharper than
mine was: **"the operative fact was right, so I stopped testing the explanation."** A confirmed
number does not confirm the story told about it. It also noted it reached for `§12b` because it had
just read it — **a rule you have just read is the one you reach for.**

**Then it went looking for whether the hazard I described had actually bitten it, instead of
accepting the correction and moving on.** That audit is the valuable part of this whole exchange.

**The near-miss.** All agent seats share **one** working tree. Its seven commits each carry exactly
one file — nothing swept — **but by habit, not by rule:** it used `git add <path>` every time. For
several of those commits **`cto`'s `docs/SCHEMA.md` and `docs/CONVENTIONS.md` were sitting `M` in
that same tree.** A single `git add -A` would have folded `cto`'s §8a, §6g and §12g into a migration
commit **under `backend-4`'s authorship with a message describing something else** — discovered, if
ever, when `devops` read the diff.

**The rule it derived, which I routed to `cto` as a candidate convention:**

> **In a shared tree: stage by explicit path. Never `-A`, never `-a`. Read `git status` before
> committing — an unexpected `M` is likely another seat's live work, not yours to carry.**

**Routed, not written.** `CONVENTIONS.md` is `cto`'s document. I added one second-order point for
it: **the failure is silent and asymmetric** — the sweeping seat sees a clean commit, the swept seat
watches its work vanish from `git status` and may re-do it, and neither gets an error. That is what
makes it worth a written rule rather than care.

**Why it went up rather than staying here:** sixteen developer seats plus `cto`, `devops` and `po`
all write into that one tree. **This is not Team 4's problem and a Team 4 status entry is the wrong
place for it.**

**Nothing outstanding from this seat.** Team 4 idle and correctly so; queue still dammed behind
`KAN-128`'s and `KAN-155`'s applies; `fed3b01` with `devops`; `KAN-138` awaiting `po` (date) and
`cto` (sequencing).

### The dam broke — `KAN-128` applied; I withdrew my own hold on `KAN-150` and discharged my own conditional on `KAN-138`

**Verified myself before acting on any of it.** `list_migrations`: `20260907064216
kan128_ledger_unique_keys_and_on_conflict` **applied**, and `20260907061206
kan145_payment_intents_booking_fk` with it. Not relayed.

**`KAN-150` — ruled (b), date it. My preference lost on its own terms.** `cto` found this ticket
said two incompatible things: *"cannot be dated until `KAN-155` applies"* and, three paragraphs
later, *"preference, not a rule."* **Both were mine and the ambiguous middle was the real defect.**

The preference exists so a **bad apply has one suspect** — worth something when a migration can
plausibly *be* the bad apply. **This one cannot:** behaviour-preserving by construction
(`backend-4`), disjoint from `KAN-155` (`cto`, measured), and I confirmed its two functions are
absent from `KAN-128`'s five. **So it bought isolation against a failure it cannot produce, and cost
an indefinite wait behind an unscheduled CEO action.** Released.

**The rule I took from `cto` and applied to myself, which is the durable part: a preference written
as a dependency stops being a preference.** The next reader sees a blocker and has no idea there is
anything to weigh. In future it goes in **as a preference with its cost named, or not at all.**

**Kept the re-measure-at-apply-time condition anyway**, even though `KAN-150` is now provably
disjoint from `KAN-128` — **"provably disjoint" is exactly the belief a whole-body `CREATE OR
REPLACE` punishes when it turns out stale.** Cheap check, silent failure, and today produced four
readings that expired between being taken and being used.

**`KAN-138` — ceiling 3 → 2, and I said so rather than letting 3 stand.** Comment `10714` had priced
it at 3 *and stated the condition*: drops to 2 if `KAN-128` lands first. **It landed; the number
moves.** Stated explicitly because **a conditional nobody discharges silently becomes a permanent
figure** — the same class that caught me twice today, now caught deliberately in my own favour's
opposite direction. Also told `po` the pre-existing 2026-09-13 should be **replaced, not kept**: it
was set before any count existed, so it agrees with the new one only by coincidence, and **a date
never derived from a count should not survive by luck once one exists.**

**Team 4 off idle:** `KAN-150` apply, then `KAN-138`. Carried `cto`'s two corrections verbatim —
**cite `CONVENTIONS.md` §6g not §6c** (§6c is the *view* case; they became distinct when today's
duplicate numbering was fixed), and the **VOLATILE/STABLE** trap `backend-4` had already caught
independently. Re-flagged that `KAN-138`'s real cost is **AC2's demonstration, not the cast** —
constructing a reachable caller where none occurs naturally — and pointed it at its own `KAN-150`
finding as the trap to avoid.

**Asked rather than took: `KAN-130`/`KAN-131`.** Unblocked, unassigned, no dates, ship as one
migration. They read as D4 money and therefore mine, **but they reached the board by a route I was
not part of, and my instruction is to coordinate rather than take.** Put the ownership question to
`team-lead` and told `backend-4` explicitly not to self-pull them. **I would rather ask than
discover I have taken another lead's work while their developer sits idle.**

**Outstanding:** `KAN-155`'s apply (CEO, undated), `fed3b01` (`devops`), `KAN-130`/`131` ownership
(`team-lead`/`pm`), `KAN-138`'s stale date (`po`).

### `pm` ruled `KAN-130`/`131` mine — assigned, and I declined to reinstate a number I had lost

**`pm`'s ruling, and its boundary, both recorded:** `KAN-128`/`145`/`150`/`155`/`130`/`131` are
backend schema hygiene on tables `STACKS.md` already names as D4's — **not D4 activation**, which
still needs the formal `pm`+CEO call. **Taking these two is not licence to pick up D4 client-facing
scope** (screens, `enablePayments`, new features). Logged by `pm` as precedent rather than escalated.

**Assigned the SQL half to `backend-4`, third behind `KAN-150`'s apply and `KAN-138`.**

**The count, and the part of this I care about.** The standing figure is **2 sittings / ceiling 3**,
authored by `senior-backend`. The ticket records that **I argued the work was "materially larger"
and lost** — *"larger in volume, same in cost"* — and that its number stood. **`senior-backend` has
since been retired and the executor is now `backend-4`.**

**I carried 2/3 forward unchanged rather than reinstating my own figure.** The self-serving move was
available and obvious: the seat that beat me no longer exists, so my number could quietly become the
number. **Losing an argument does not become winning it because the other party left.** What I did
instead is tell `backend-4` the count is open to **its** revision as the new executor — a count
belongs to the seat that produces it — and that I will carry whatever it produces, **attributed to
it**, up or down. What I will not do is launder my old opinion through a personnel change.

**Discharged another stale conditional, worth three days.** The ticket says *"Earliest start
Thursday 2026-09-10,"* conditional on `KAN-128` applying. **`KAN-128` applied today** (verified
`20260907064216`). **Earliest start is now.** Left unstated, that figure would have idled a
developer for three days against a blocker that no longer exists. **Second conditional I have
discharged today** — the other being `KAN-138`'s ceiling 3 → 2.

**Third instance of the same collision, and I think it has stopped being a per-ticket problem.**
**Three tickets replace `trgfn_payment_to_ledger` whole:** `KAN-128` (applied), `KAN-131` (about to
be authored), `KAN-140` (`To Do`). `KAN-131` carries its ordering on its face; **nothing states that
`KAN-140` must be authored after `KAN-131`**, and if it is not it silently reverts both `KAN-128`'s
conflict clauses and `KAN-131`'s identity fix, with no error at apply time.

**Flagged, not ruled** — `KAN-140` is `KAN-136` pt.2 and I have not established it as mine. Routed
to `cto` (sequencing) and `po` (record it on the ticket). **But this is the third one I have found
unrecorded today** — `KAN-138`, now `KAN-140` — and catching it per-ticket only works while someone
keeps looking. **Proposed to `cto` as a standing `CONVENTIONS.md` §6g rule: a ticket replacing a
function another pending ticket also replaces must state its ordering on its face.**

**Declined a half that is not mine.** `KAN-130` AC3's `wallet.dart` change is **`frontend-2`'s
(Team 2)** by the ticket's own text, and `wallet.dart` is outside my write-slice. **Did not assign
or transition it**, told `backend-4` it is not theirs. `cpo` ruled it a **condition, not a date**
(zero readers today), so it does not gate the SQL — **but one ticket spanning two teams has no seat
owning whether the halves ever meet**, and I cannot own that from inside Team 4. Raised to `pm`;
suggested the alternative is splitting the ticket.

**Outstanding, none mine:** `KAN-155` apply (CEO), `fed3b01` (`devops`), `KAN-138`'s stale 09-13
date (`po`), `KAN-140` sequencing (`cto`), the two-team join on `KAN-130` (`pm`).

### `backend-4` refused to apply `KAN-150` and was right — the omission was in my brief

**`fed3b01` verified pushed** (`ls-remote` 06:57:11Z; remote tip since moved to `f9b7cd6`, nothing
local ahead). **Dropped from tracking.** `team-lead`'s operative claim correct; its mechanism
slightly off — `fed3b01` is a **child** of `8363a0f`, so it went out in a *later* `devops-push2`
cycle, not as part of that one. Changes nothing; noted only because "right answer, wrong mechanism"
has now recurred four or five times today across seats.

**The real item: `backend-4` held `KAN-150` on `G-028`'s confirmation gate, and it caught a defect
in my brief rather than a subtlety in the rules.**

On `KAN-145` I wrote the assignment as *"both legs are `backend-4`'s, **gated on `cto`'s posted
confirmation**."* On `KAN-150` I wrote **"apply it. I withdrew my own hold"** plus three paragraphs
on the re-measure condition — **and never restated the confirmation gate.** I knew the rule. I was
writing about the constraint I was **changing** and stopped restating the one I was **not**.

**Had `backend-4` obeyed me it would have applied a production migration without the confirmation
`G-028` requires** — the `KAN-141` failure exactly in reverse, where a dispatch assumed a
confirmation nobody had posted and cost a day. Instead it re-read every comment and found `10716`
(design ruling), `10735` (sequencing ruling), `10736` (my release) — **none carrying the shape `cto`
used on `KAN-141` (`10685`) and `KAN-145` (`10705`)**, an explicit `G-028` confirmation with its own
re-measurement. `10735` even says *"after `cto`'s confirmation on this ticket"* — **naming the gate,
not clearing it.**

**Adopted `backend-4`'s wording, which is sharper than mine was:** I ruled it **technically
unblocked**; only `cto` can make it **confirmed**. **My release lifted a scheduling constraint I had
imposed; it could not clear an authority gate I do not hold.** Told `backend-4` to refuse on this
ground **even if I tell it to apply again** — I would rather be caught than obeyed.

**Saved as memory** (`lifting-one-constraint-drops-the-others`): a brief that releases one constraint
silently drops every gate it fails to restate, and **"go" is the most dangerous word in a brief.**
Same root as the conditional failures I logged earlier — **attention follows what moved**, and the
unchanged background stops being seen.

**`backend-4`'s null result on my re-measure condition is a genuine deliverable.** It compared
**full definition text**, not attributes — attribute equality would have passed while a body
differed — and established the `KAN-128` disjointness **by comparing bodies rather than matching
names against a list**, which is the better method and what I will ask for in future. Both
byte-identical, no drift. The failure it guards is silent, so **the only evidence it did not happen
is having looked.**

**Its own diagnosis, third instance it has named in itself today:** *"the operative instruction was
clear, so I stopped interrogating the reason behind it."* I told it the symmetry plainly — **I have
logged four of that shape in this file today, and the contradiction it read straight past on
`KAN-150` was one I wrote.** The reader was not the one who failed there.

**`KAN-150` now needs one thing: `cto` to post a `G-028` confirmation, or rule that `10735`
counted.** `backend-4` has asked directly; I flagged it for a nudge if `cto` is idle, since the
ticket is otherwise finished and re-verified.

**Outstanding, none mine:** `KAN-150`'s `cto` confirmation, `KAN-155`'s apply (CEO), `KAN-140`
sequencing (`cto`), the `KAN-130` two-team join (`pm`), `KAN-138`'s stale date and `KAN-140`'s note
(`po`, folded into its next pass).

### `cto` confirmed `KAN-150`; the `KAN-130` split landed — and left its own requirement behind

**`cto` posted the `G-028` confirmation as `10740`** (*"KAN-150 CONFIRMED — apply; you read 10735
correctly"*). **`backend-4`'s refusal to infer approval was vindicated by the answer itself** —
`cto` had to say it, which is the whole point of a posted gate. Applying now.

**Two of my routed findings became tickets, which is the outcome I wanted rather than a header
nobody reads:** `KAN-158` (*"venue deletion will hit ON DELETE RESTRICT once payment data exists"*)
under a new **`KAN-157` D3 epic**, and **`KAN-159`** carrying the `wallet.dart` client half split out
of `KAN-130`.

**But I checked the split rather than trusting it, and the source ticket did not move.** Re-read
`KAN-130`'s description directly: **AC3 still requires the full `wallet.dart` change** — rename,
added `ownerType`, `toMap()`/`fromMap()`, "eight lines total", the reader sweep — **word for word
what `KAN-159` now owns.** The Executor section still reads *"Dart change at `wallet.dart` — done by
`frontend-2`, **same ticket**"* and still names retired **`senior-backend`** as author.

**Why I did not let it pass as cosmetic.** An AC that has moved but stays behind **fails in both
directions**: at the review gate `po` either marks AC3 unmet — blocking a ticket whose SQL half is
complete — or waives it informally, teaching the next reader that this ticket's ACs are negotiable.
And **two tickets can be closed for the same eight lines, or neither. A split that leaves the
requirement in both places has not split anything.**

**Flagged, not edited** (comment `10743`) — ticket text is `po`'s, and I have held that line all day
across `KAN-145`, `KAN-138`, `KAN-155` and now this. **Suggested replacing AC3 with a pointer rather
than deleting it:** the reasoning is load-bearing — the model needs **both** fields because
`owner_type` is `NOT NULL`, so a model carrying only the rename cannot build a legal insert — and
that belongs on `KAN-159` if it is not there already.

**Nothing blocked by it.** `backend-4` already has in writing that `wallet.dart` is outside our
write-slice, so the stale AC3 cannot make it touch a file it should not. **The exposure is at the
review gate, not during the work** — cheap now, expensive at the moment someone tries to close the
ticket.

**Also verified today and dropped:** `fed3b01` is pushed (`ls-remote` 06:57:11Z, remote since moved
to `f9b7cd6`, nothing local ahead).

**Queue:** `KAN-150` applying → `KAN-138` → `KAN-130`+`131`. **Nothing outstanding from this seat.**
Open items all elsewhere: `KAN-155` apply (CEO), `KAN-140` sequencing (`cto`), and `po`'s next pass
(`KAN-138`'s stale date, `KAN-140`'s note, `KAN-130`'s AC3).

### `KAN-138` authored and moved to Development; `KAN-150` confirmed and applying; a money path goes live

**Moved `KAN-138` `Ready` → `Development`** (transition 4). `backend-4` correctly did not move it
itself — that transition is mine and it waited.

**Verified `cto`'s `KAN-150` confirmation myself rather than taking it on report.** `10740` exists,
posted **10:55:52**: *"G-028 CONFIRMATION: APPROVED TO APPLY."* `backend-4`'s "not confirmed"
message went up at **10:53:46** — **true when written, stale by two minutes.** Same shape as
everything else today; no fault in it, and worth recording that the pattern is now so routine it is
the default explanation rather than a surprise.

**`cto` on the hold:** *"`backend-4` read `10735` correctly: it was NOT a confirmation, and it was
right to hold… **This comment is the gate.** …this is the second time today `backend-4` has refused
to act on an inferred approval; both times it was right."* **The gate I forgot to restate in my own
brief is the gate that has now twice done real work.**

`cto` also ran the drift check **in a way `backend-4` could not** — it had read both bodies earlier
today *before* `KAN-128` applied, while measuring for `KAN-155`, and compared those against live
now. **The no-drift claim therefore rests on two independent readings taken either side of
`KAN-128`'s apply**, not on name-matching.

**Routed up, and this is the item that matters beyond the ticket: `KAN-138`'s fix makes
`settle_game` genuinely callable for the first time.** It is unreachable today because it raises
`42804` on every invocation — **an accidental protection, not an intended gate.** After the fix any
authenticated user can settle their own game and the `wallet_ledger` credit path executes for the
first time.

**Intended end state, and I am holding nothing on it** — `T-058` ruled the fix and the ticket exists
to make that path reachable. But **"a money path that has never once executed becomes live" is a
fact someone should choose to accept, not discover afterwards.** Sent to `pm`/`cpo` *before* the
apply, when gating it would still cost nothing. Noted the pairing: `KAN-145`'s `ON DELETE RESTRICT`
and `KAN-128`'s ledger conflict clauses landed the same day — **the money paths are being made
correct and reachable together, which is the right order, but it moves the first real execution
closer than it has been.**

**`backend-4`'s AC2 work is the strongest thing it produced today.** The obstacle was a *second*
`T-055` trap: `settle_game` raises `auth_required` when `auth.uid()` is NULL, so an ordinary
service-role probe dies **three guards before the insert** and would have reported *"settle_game
raises"* while proving nothing about the type error — **the original form of the trap, guarding the
ticket that exists because of the early-return form.** It built a caller via `request.jwt.claims`,
**asserted `auth.uid()` actually resolved rather than assuming**, reached line 39 and reproduced
`42804` verbatim. Nothing committed, 0 rows either side.

**Its `proacl` non-finding is worth as much as a finding.** A bare `=X/postgres` on a `SECURITY
DEFINER` function looks exactly like the `KAN-79`/`113`/`141` class; it established it is not, since
the body gates on `auth.uid()` and is-admin-or-self. *"The grant alone does not tell you; the body
does."* **Not raising it was correct, and telling me it had checked is what made the silence
useful.**

**Told it explicitly that AC5 here inverts AC2 there:** on `KAN-138` the caller was constructible and
had to be built; on `KAN-150` no `prime` caller can exist and **stating that is what AC5 asks for** —
`cto`'s instruction, and worth flagging given how hard it had just worked to construct one.

**`backend-4` declined to price `KAN-130`/`131` on a skim.** I asked for that and prefer it: **"I
have not read it yet" beats a number.**

**Queue:** `KAN-150` applying → `KAN-138` on `cto` → `KAN-130`+`131`. **Nothing outstanding from
this seat.**

### `KAN-150` applied and In Review — and a lucky outcome I declined to claim as foresight

**Applied 11:03**, verification `10746`, moved to In Review (`backend-4`'s own transition).
`provolatile` still `'v'` and `'s'` — **the §6g asymmetry survived the replacement** — `prosecdef`
false on both, `proconfig` unchanged, zero executable `'prime'`. **It verified `10740` existed on the
ticket before acting rather than trusting the message announcing it**, which is the discipline that
has paid repeatedly today.

**Routed to `cto` as a candidate rule — a post-change grep must strip comments first.**
`prosrc ILIKE '%''prime''%'` returns **true** on `should_bypass_quiet_hours`, and `v_is_prime`
returns **true** on `calculate_notification_score` — **because the change's own explanatory comments
quote the predicate that was removed.** `cto`'s `10716` ruling *required* those comments, so **this
ticket was guaranteed to produce the false positive: the better the documentation, the louder the
noise.** Both wrong responses are available — report phantom leftovers, or narrow the pattern until
the noise disappears and lose real hits with it, **trading a false positive for a false negative on
the one check whose job is catching a silent revert.** `regexp_replace(prosrc,'--[^\n]*','','g')`
before matching is the only response that trades neither. `backend-4` paired it with the morning's
`posts_mapping_check` case — someone else's identifier then, its own documentation now — which makes
it a shape rather than an incident.

**A correction to my own record, in the direction that does not flatter me.** `backend-4` observed
that applying ahead of `KAN-155` produced **better** evidence than waiting would have: `prime` is
**still a live row** (count 1), so preservation was demonstrated *with the retired key present* —
testing `cto`'s shape argument directly instead of assuming it. **True, and I did not foresee it.**
I released the hold because it had started costing an indefinite wait and buying isolation against a
failure the migration could not produce. **The stronger evidence is a benefit I got for reasons I
did not have.** Said so plainly to `backend-4` and to `team-lead`, because **a lead who lets a lucky
outcome ratify their reasoning will make the same call next time in a case where it does not hold.**

**What does generalise, and it is `cto`'s point not mine:** `backend-4`'s original justification was
*"safe because zero `prime` rows"*; `cto`'s was *"safe because they **compare** and therefore fail
closed."* **The shape argument is the one that survived contact with a live `prime` row.** A
justification resting on a row count expires when the count changes; one resting on shape does not.

**No duplication on the `settle_game` consequence:** it is already the close of `backend-4`'s
comment `10742` on `KAN-138`, so `po` has it on the ticket; my routing covers `pm`/`cpo` and
`backend-4` is not repeating it. **Checked rather than assumed, both halves covered once.**

**`backend-4` is using the blocked gap to READ `KAN-130`/`131` and produce a real count** — reading,
not authoring, so nothing lands out of order. **I will carry its figure and attribute it**, per my
own ruling that I do not reinstate a number I lost.

**Queue:** `KAN-138` on `cto`'s confirmation → `KAN-130`+`131`. **Nothing outstanding from this
seat.**

### `KAN-130`/`131` count settled at 2/3 — re-derived, not inherited; and I was wrong yesterday

**Settled: 2 sittings, ceiling 3.** `po` may date it; `KAN-128`'s apply discharged the "earliest
Thursday 2026-09-10" constraint.

**What makes it trustworthy is that it now has two independent authors.** It was `senior-backend`'s
figure, which **I argued against and lost**, and which I refused on `10739` to reinstate merely
because that seat retired. **`backend-4` has re-derived 2/3 from its own measurement of the live
schema** — `wallets` column state, four indexes, two policies, three distinct `search_path` values
and a `SECURITY DEFINER` split across the four functions — **and said explicitly that agreeing is
not deferring.**

**It tested the retired seat's *argument*, not its conclusion.** *"Larger in volume, same in cost"*,
checked against **its own measured rework rate on the §6g whole-body trap today: zero across three
functions** (`KAN-150`'s two, `KAN-138`'s one), all attribute-correct first pass. **Volume of a
mechanical step is volume, not risk.** **I disagreed with that yesterday; three same-day data points
say it was right and I was wrong**, and I put that on the ticket in those words. **A figure produced
twice from different starting points is evidence; a figure deferred to is an echo.**

**I ruled against extra margin I was offered.** `backend-4` flagged that `KAN-145`'s FK makes AC3's
probe harder — real `venue_bookings` parents now required — and said it would not argue if I priced
a **fourth** cycle. **I ruled it scaffolding and left the count alone.** Test applied rather than
the out taken: known before starting (yes), population enumerable (yes — 389 `venues`, 693
`venue_spaces`, only the booking needs creating), judgement feeding the next step (no). **And the
sharper one: a rework cycle is a redo of the *deliverable*.** If scaffolding fails you fix the
probe; if building it reveals the migration is wrong, that is **cycle 1, already priced.** No fourth
cycle hiding.

**Corrected `backend-4`'s framing, which mattered more than the ruling.** It wrote *"a cost that did
not exist when this was priced, and **it is mine**."* **It is not.** The FK was `T-061`'s ruling,
correctly authored and applied, and it unblocked `KAN-140`. **Making the schema correct makes
fabricating test data harder — the constraint working as designed, not a debt anyone incurred.**
Told it not to carry it as one.

**And it is a STANDING cost, not this ticket's** — routed to `pm`/`cto` rather than buried. Every
future probe touching `payment_intents` needs real `venue_bookings` parents: `KAN-140`,
`KAN-128`'s downstream P3 probe, every D4 money probe after. **Pricing it into one ceiling would
hide a permanent general cost where the next author rediscovers it from scratch.**

**Two `backend-4` checks of ticket claims, both the right posture.** The **views** confirmation is
not a non-event — `v_wallet_balance` and `v_wallet_admin_overview` neither read `user_id`, so the
drop cascades no view away; **had either read it, that was a material addition nobody had priced.**
The **"four non-DDL references"** claim it could not confirm — its comment-stripped sweep finds
**three** functions, all already named — **flagged to reconcile rather than declared wrong**, and it
cannot move the count dangerously since the set is *smaller*, not larger. Routed to `cto`.

**Two implementation subtleties recorded on the ticket:** `ADD CONSTRAINT wallets_pkey PRIMARY KEY
USING INDEX wallets_id_unique` (a plain `ADD PRIMARY KEY` leaves a duplicate index, and dropping the
unique first is blocked by `financial_ledger_wallet_fkey`), and **replace `wallets_self_read` before
dropping `user_id`** or the drop needs `CASCADE` and silently takes the policy.

**Queue:** `KAN-138` on `cto` → `KAN-130`+`131`. Both still in `Ready`; **I transition when
`backend-4` starts**, and told it to tell me rather than find the column in the wrong state.
**Nothing outstanding from this seat.**

### Amended the verification rule before `cto` records it — the form I sent could have been read backwards

**`backend-4` sharpened the comment-stripping finding and the sharpening is load-bearing**, so I
sent it as an amendment rather than letting the rule land in my weaker form.

**What I routed:** *"a post-change grep must strip comments first, because the change's own
documentation quotes what was removed."*

**What was missing:** `cto`'s `10716` **required** those comments, and required them to quote the
removed predicate specifically, because **that is what distinguishes dormant from abandoned.** So
**the rule that made the code honest is the same rule that made the naive verification lie.**

**Why the omission was dangerous rather than merely incomplete.** The lazy reading of my version is
*"comments caused a false positive, so write fewer comments"* — **exactly backwards**, and it would
land in a codebase where `cto` has **just ruled explanatory comments mandatory for this very class
of change.** A rule recorded without the framing **could be cited to undo `10716`.** Re-sent in two
halves: (1) strip comments when verifying; (2) **this is a fix to the verification, never to the
code.**

**`backend-4`'s self-observation is the sharpest thing either of us said today**, and I told it so:
it had reached for ownership of a correct decision's downstream friction *"the same way I have been
reaching for ownership of errors all day — and the two are not the same act."* **Owning a mistake is
accurate; owning a correct decision's friction miscategorises work as damage.** Its own conclusion
is the one that matters — it would make a backend **quietly reluctant to add constraints**, which is
precisely the wrong instinct for the seat. A backend that hesitates to add a foreign key because the
last one made a probe harder ships weaker schemas.

**Symmetry closed on the foresight point.** `backend-4` volunteered that it did not sequence
`KAN-150` ahead of `KAN-155` for the evidence either — it noticed while writing the verification.
**Neither of us gets that outcome as foresight**, and both of us said so unprompted. What survives
is `cto`'s correction, chosen by neither: **a justification resting on a row count expires when the
count changes; one resting on shape does not.**

**One stale crossing, no action:** `backend-4`'s earlier message still asked whether the FK cost
moves the ceiling to 4. Already ruled — **2/3, scaffolding** — and it has since acknowledged the
ruling.

**Queue unchanged:** `KAN-138` on `cto`'s confirmation → `KAN-130`+`131`, which stay in `Ready`
until `backend-4` tells me it is starting. **Nothing outstanding from this seat.** Open elsewhere:
`KAN-155` apply (CEO), `KAN-138` confirmation (`cto`), `KAN-140` ordering (`cto`), the standing
`payment_intents` probe cost (`pm`/`cto`), `KAN-130`'s AC3 and `KAN-138`'s stale date (`po`).
