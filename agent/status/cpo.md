# cpo status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/cpo.md`. This file is a work log, not a rule source.

`can_send_notification_now` hardcodes `v_plan := 'kickoff'` for users with no subscription, so after
the rename the lookup misses and returns true — **unlimited notifications for most users**. Must move
to `'player_free'` in the same change set. His separate-ticket position on the `'prime'` dead branches
still stands; that distinction is correct.

**Changed:** this file, `DECISIONS.md` (`P-041`, plus the name correction inside `P-040`).
**Reported to:** `cto` and `po`. **Still owed:** the Socialiser question.

## 2026-09-07 — `P-042`: ran the `11b` test myself. All three open questions close

**Sequencing decided and then executed.** `po` correctly declined to sequence my seat's work, and
`cto`'s point settled it: with the tables uniform, entitlement tickets have no positive case and
someone manufactures a differentiating row — the exact outcome the NOT ESTABLISHEDs exist to prevent.
So: **before** entitlement tickets, not after. Cheapest way to sequence work onto my own seat was to
do it, so I read `11b` rather than tasking it. **ALIGNED.**

**The test returned a positive result.** `11b` §C.2 (the Player Free vs Pro table) **does** attribute
notification entitlements to Player Pro — **124** saved searches 3→unlimited, **431** quiet hours
Standard→granular, **444** new-venue smart alerts. **None is `quiet_override_high` or an inbound cap.**
So those two values move from NOT ESTABLISHED to **confirmed**: `false` and `5/10/20` stand on positive
evidence, not on absence.

**The trap I recorded, because a grep will find it.** 431 pairs "Quiet hours setting" with "Granular
control" and looks like the warrant. It is not — 431 is **the user configuring** their quiet hours;
`quiet_override_high` is **the system delivering through** them (`should_bypass_quiet_hours:17203`).
**Opposed, not the same capability at a different grain.** Reading 431 as the warrant would let a paid
tier interrupt a user *because* they paid — inverting §A.1 and sitting badly against the prayer-time
and Ramadan commitments (features 432, 433, both Basic).

**`cto`'s missing-positive-case concern: risk real, premise false.** The differentiation exists — §C.2,
§D.2, §E.2 are full of it — it just does not live in these two tables. `subscription_features` is a
**notification-delivery** matrix, not the entitlement surface. **Entitlement tickets should assert
against `11b` §C.2; nobody needs to manufacture a row.** Uniform values across all eight keys is the
correct end state, not a gap.

**Socialiser answered: no plan row; a Socialiser holds `player_free`.** `11b` gives it no entitlement
column and names it **once** in ~650 features — Feature 37, "Persona switch (Socialiser →
Player/Organiser)". A persona you switch *out of*. Delta is empty, which was my own stated condition.
A row would assert a commercial relationship §A.3 excludes from revenue. **The follow-up `INSERT` is
not needed at all.**

**Nothing in `KAN-155` changes.** **No open product questions remain on the plan-key work.**

**Changed:** this file, `DECISIONS.md` (`P-042`). **Reported to:** `po`, `cto`, `pm`.

---

## 2026-09-07 — `KAN-155` AC1: the two Corporate labels, confirmed against `12a` §E.1 (not `P-039`)

**Asked by `team-lead-4`**, relaying `cto`'s flag: six of the eight new `subscription_plans.label`
values match `P-039` verbatim, but `corporate_starter`/`corporate_growth` expanded `P-039`'s prose
rendering *"Corporate Starter · Growth · Enterprise"* into two names. AC1 says exact, not inferred,
so the expansion needed checking against the source rather than against my own decision record.

**Read the source. `12a` §E.1 is a table, and it spells both names out in full** — Tier column,
bolded: **Corporate Starter** (up to 100, AED 7,500/yr) · **Corporate Growth** (up to 500,
AED 15,000/yr) · **Corporate Enterprise** (500+, AED 25,000+ custom). `P-039`'s middle-dot line was
my shorthand for that table, never a name in its own right.

**Exact strings: `Corporate Starter` and `Corporate Growth`.** `cto`'s reading was right, and it
was not actually an inference — the names exist verbatim one level below the document I had cited.

**Migration already correct, nothing to change.**
`Dabbler/dabbler-code/supabase/migrations/20260907110000_kan155_plan_key_migration.sql:226-227`
writes `'Corporate Starter'` and `'Corporate Growth'`. No `UPDATE` needed now or later; AC1 holds on
all eight labels. Recorded as a Jira comment on `KAN-155`.

**No `DECISIONS.md` entry** — this sets no precedent. It confirms `P-039` against its own source and
changes nothing about the ruling.

**The lesson worth keeping, and it is about my own writing.** `P-039` compressed a three-row table
into one line of prose with middle dots, then a downstream criterion said *"`12a`'s exact product
name"* — pointing at `12a` while the reader only had my compression of it. That gap is what cost
`cto` and `team-lead-4` a round trip. **When a decision record names a product, give the name in the
form the source gives it, not a rendering of it.**

**Same question arrived twice, from `team-lead-4` and then from `cto` directly.** Answered `cto`
too, with the confirmation plus one addition it needed: **`12a`'s own summary tables abbreviate the
product names.** §A.3 renders the Venue row as *"Venue Basic → Verified Venue Pro"* and the
Corporate row as *"Corporate Tier (3 sizes)"*; §D.4's column headers are bare *"Basic"* / *"Pro"*.
The full names live in the section headings and the §E.1 table. **Anything reading a label off a
summary row gets it wrong** — the same failure mode as my own compression in `P-039`, one level up.

Also noted `cto`'s measurement that `prime`'s two orphaned functions (`calculate_notification_score`,
`should_bypass_quiet_hours`) only *compare* against the literal and so fail closed at zero
subscribers. That confirms an assumption `P-039` made without measuring: retiring `prime` destroys no
reachable behaviour. `KAN-150` can remove those branches with no product question attached.

## 2026-09-07 — `KAN-138` / `settle_game` go-live: ALIGNED, apply as-is (`P-043`)

**Asked by** `team-lead-4` via `team-lead`: does `settle_game` becoming callable need a gate —
feature flag, staged rollout, manual review of first N settlements — before `cto` confirms the apply?

**Verdict: ALIGNED, apply as-is, no gate.** Posted as a comment on `KAN-138` (comment `10747`) and
recorded as `P-043` in `Dabbler/dabbler-docs/DECISIONS.md`.

**What I measured rather than accepted:**
- `admin_approve_payout` (`supabase/migrations/20260829080500_baseline_schema.sql:2138`) and
  `admin_mark_payout_paid` (`:2458`) both gate on `public.is_admin(me)`. Money leaves only via that
  chain, so a human admin already reviews every payout — the requested gate exists.
- `grep -rn "settle_game"` across `lib/`, `supabase/functions/`, `dabbler-web`, `dabbler-admin`:
  **zero** call sites. Nothing to flag or stage.
- `request_payout` (`20260909090000_kan128...sql:286`) requires a default beneficiary and sufficient
  `wallets.balance_aed`; `wallets` = 0 rows.
- Corpus: `11b complete features list`, rows **160** (Organiser earnings wallet) and **161**
  (Organiser auto-payout, weekly T+7), both **1A** — the wallet is committed strategy.

**The finding that was not the one escalated.** `settle_game`'s `p_gross_collected` is caller-
supplied and authorised on `me = p_organiser_user_id`, with no tie to any collected payment. Inert
today; becomes a direct assertion-to-money path the day `11b` row 161's T+7 auto-payout removes the
admin approval. Handed to `po` as a precondition on (1) the call-site ticket and (2) the auto-payout
ticket. Derivation design is `cto`'s.

**Did not escalate to the CEO** despite the brief offering it: both premises ("real money", "first
execution reachable") fail measurement, and the question was settleable by reading two function
bodies and running a grep.

---

## 2026-09-10 — `KAN-176` Part B: what happens to games, meetups, squads and challenges when their creator deletes their account

**Task:** `team-lead`, routed from `cto`'s `T-077`, which ruled Part A (12 tables → delete) and
deliberately left Part B (4 tables, 26 users) as a product decision. No MODEL/EFFORT line in the
brief; treated as role default.

**Verdict: CONFLICTS for "delete them". ALIGNED for preservation. ALIGNED WITH CONSEQUENCE for the
sentinel — preservation is right, the sentinel *framing* is wrong.** Recorded as **`P-044`** in
`Dabbler/dabbler-docs/DECISIONS.md`.

**One rule, not four:** a participation object outlives its creator; on deletion the departed
person's link is **severed — every link, including the auth key** — and the object preserved. A
*live* object needing somebody in charge passes that role to a **remaining participant**, never to
Dabbler; deleted only if no participant remains. **The discriminator is live-vs-completed, not which
table.** Today: `games` 218 (all completed) and `meetups` 1 → preserve+sever; `squads` 0 and
`challenges` 0 → promote-else-delete when they exist.

**What I measured rather than accepted** (read-only, `wtncuzcskpigqpmnxwws`, 0 mutations):
- **All 218 games are in the past** (`start_at` 2025-11-18 → 2026-08-31), **zero** future-dated,
  **zero** cancelled. `cto` framed the product question as *"a scheduled game whose organiser
  leaves"* — **that scenario has zero live instances**, so it is not what blocks the 26 users, and I
  refused to rule it on no evidence.
- **175 of 218** games carry a non-creator participant. 602 `game_roster` rows, **396 belonging to 19
  people other than the creator**, 600 with `left_at IS NULL`. `game_roster.game_id` is
  `ON DELETE CASCADE` — deleting the games destroys those 396 rows. **That is the conflict**: those
  rows are 19 players' history/ratings/achievements, which `04` Art 5.1 says are *theirs* and Art 4.2
  says Dabbler holds *in trust on their behalf*.
- **`games.creator_user_id` is populated on all 218 rows (26 distinct) and has no FK.** Severing only
  `creator_profile_id` leaves the auth uuid on every row — `P-036`'s "anonymisation in appearance
  only", live. Made binding: **both keys, or the erasure is cosmetic.**
- `posts.game_id` is `ON DELETE NO ACTION` with 0 rows attached today — dormant, but it would *block*
  a game delete the moment anyone posts about a game. The delete option is not even reachable later.

**The mechanism finding that may dissolve the CEO-reserved blocker.** `T-077` says Part B needs a
sentinel row and that inserting one is CEO-reserved. Making the organiser columns **nullable** with
`ON DELETE SET NULL` reaches the same product outcome with **DDL only — no data insert, same class as
Part A**, and `KAN-131` may then be unnecessary. I ruled the outcome and handed the feasibility call
to `cto`; told `po` not to size Part B until that is answered.

**Corpus finding, unprompted:** `13a` §E3.2 TICKET 3.2.1 commits *"account deletion (**soft-delete
with 14-day SLA, then hard purge**)"* and `11` v2 §I.4 repeats the 14-day SLA. **The live
`delete_my_account` is an immediate hard delete with no window.** Committed architecture the build
contradicts; not this ticket's scope, handed on.

**Recorded the commercial conflict of interest rather than leaning on it.** Preserving game history
also preserves the talent-graph asset `03` values and `02` monetizes. `04` Art 9.2 is explicit that
treating the graph as Dabbler's own asset forfeits the trust that makes it valuable, so I based the
ruling solely on the other 19 players' claim and said in `P-044` that the commercial benefit must not
be cited as a reason.

**Two defects found and handed to `po`:** the `KAN-160`/`161` strings shipped today
(`lib/l10n/app_en.arb:591,593`) disclose retention of *"Payment and booking records"* only — games are
neither, so this ruling creates a second disclosure gap of exactly `P-036`'s kind; and
`danger_zone_section.dart:373` still carries the hardcoded *"permanently delete … all associated
data"* (which of the two renders, I did not verify).

**Numbering defect found:** this log's own previous entry records a `KAN-138` verdict published to
Jira comment `10747` as **`P-043`** — **and no `P-043` exists in `DECISIONS.md`**. Lost write, not a
wrong-tree write (`~/Desktop/Thebes` does not exist). I took `P-044` rather than squat on a number a
public Jira comment already cites. `po` re-lands `P-043` without renumbering.

**Not delivered:** the Jira comment on `KAN-176`. The Atlassian MCP returned
*"requires re-authorization (token expired)"*. The full verdict is in `P-044`; the comment needs
re-posting once auth is restored.

## 2026-10-09 — KAN-452 Notion messaging/follow report
Read-only observation report written to /Users/moataz/.claude/jobs/7f6ff1a6/tmp/kan452-report.md. Finding: corpus (11b) lists chat features but no follow/block permission rules; only non-corpus "Play mode" gates chat; conflicts with P-002/P-033 flagged. No rulings, no writes to Notion/Jira/DB.
- 2026-10-15 cpo: product plan for CEO order 'open game chat to everyone + Home entry'; read-only; verdict ALIGNED WITH CONSEQUENCE (reverses KAN-516 no-inbox/no-unread and P2 internal-only cohort; needs D1/P-002/P-020 ruling). Plan returned to orchestrator.

## 2026-10-27 — next product scope ruling
Ranked 5 deferred items (offline, squads, ratings, recurring games, map view) from ROADMAP.md §4 + PROJECT_STATE.md. Notion corpus NOT read this pass (low effort); citations to corpus marked unverified. No tickets written.

## 2026-10-27 — organiser definition (actor_is_organiser)
Read-only verdict: organiser = persona_type=organiser; profile_type=business not a corpus concept. Cited BRIEF.md §2, DECISIONS.md P-003. No Jira/DB writes.

## 2026-10-29 dreq-de35fff8 (KAN-682 Contributor profile gaps A-F)
Decided: A = client-side definition (joined/confirmed, non-cancelled, deduped by game id, meetups out); B and C omitted; D = Upcoming plus Games I organise only; E = real Primary with zero history; F = organiser view, post-count error state. Follow-ups listed. File: /Users/moataz/.claude/jobs/c49d2414/tmp/dreq-de35fff8-decision.md

## 2026-10-30 — recurring-games product Qs + next ranking
Recurring end/cap/cancel/paid: not documented in corpus; recommended defaults. Next: analytics instrumentation (GTM launch gate, BRIEF:27,475) > bench mode > venue booking (Phase 1B M9) > wallet (SVF-gated, BRIEF:224). R2 outside CEO-approved Workers+D1 -> CEO money call. No tickets written.
