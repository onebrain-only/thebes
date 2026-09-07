# agent/status/cpo.md — cpo status log

**Owner:** `cpo` — **this agent, and only this agent, writes here.**
Every other agent reads it. master-analyst reads it to reconcile `agent/STATUS.md`;
it does not write here.

**Purpose:** The product judgement record. Every verdict on every idea, with the
document it was judged against.

---

## SCOPE

Judges ideas, features, scope changes and pivots against the 26-document business
corpus. Product **and** protect. Read-only on code and on the corpus — it judges,
it does not edit either.

## THE RULE

The status entry is **part of the decision, not offered afterwards.** It is the last
thing written before closing, and the agent may not report DONE without it. A verdict,
a refusal, or a question escalated to the PO still gets an entry — those are the ones
most likely to be skipped and most needed.

## FORMAT — newest first

```
## YYYY-MM-DD — KAN-NN — Title
**Question:** what was put to you
**Verdict:** the call, in one line
**Why:** the reasoning, with the citation
**Consequence:** what this forces elsewhere
**Escalated:** what went to the PO, or none
**Handoff:** which agent picks this up, or none
```

---

# LOG

## 2026-08-27 — B4 — A correction to a correction: WIRE-09 overcorrected, B4 stands
**Question:** `master-analyst` re-checked WIRE-09 and reported all seven placeholder routes
unreachable — *"Zero navigation sites"* for all six owning route constants. That would have
retired **B4**, one of my four remaining promotion blockers.

**Verdict:** **Right for five constants, wrong for `socialChat` — the one B4 rests on.
B4 stands.**

**Why:** `user_profile_screen.dart:1475` does `context.push('${RoutePaths.socialChat}/$userId')`
— one live navigation site. The Message button at `:1093` is unconditional; the screen is
routed at `app_router.dart:1463`; the route's guard at `:1607` reads
`if (!FeatureFlags.messaging) return RoutePaths.home;` and **`FeatureFlags.messaging = true`**
(`feature_flags.dart:53`), so it does not fire. The user lands on the placeholder.
`master-analyst`'s own `INDEX.md` §11b still ranks this **#1 in "Worst 5"** — the re-check
contradicts their own INV-01, and INV-01 holds.

Corrected figure: **7 placeholder routes · 6 unreachable · 1 reachable.** The six are not
uniform either — `socialChatList`, `socialEditPost` and `socialAnalytics` carry **no guard**
and are unreachable only because nothing links them, which matters on a web app where
routes are URL-reachable.

**Consequence:** `BRIEF.md` §10 B4 narrowed with the full chain cited, and the wider §16
counts now explicitly marked as `master-analyst`'s and cited rather than independently
verified. Two smaller defects logged on the same path for whoever fixes it: `_sendMessage`
wraps the push in `isBlocked.whenData(...)` so the button does nothing while that provider
loads or errors, and the placeholder title calls `conversationId.substring(0, 8)`, which
throws on ids under 8 characters.

**The lesson this adds — the reciprocal of this morning's.** A correction that **softens**
a finding earns the same check as one that hardens against it. Relief is a bias like any
other; taking WIRE-09 at face value would have dropped a real blocker on a blanket claim.
Recorded in agent memory alongside `P-006`. Also recorded: check
`.claude/agent-memory/master-analyst/INDEX.md` **§11b** — a "corrected facts, do not quote
the old version" table — before citing any figure of theirs read earlier in a session.

**Escalated:** asked `master-analyst` to add **WIRE-09** to §11b with the `socialChat`
exception spelled out, so the next reader does not retire INV-01 off the blanket claim.

**Handoff:** none. WIRE-09 and WIRE-10 both fold into the dead-route cleanup.

## 2026-08-27 — KAN-50 — CORRECTION: three code claims in the launch-readiness assessment did not hold
**Question:** `team-lead` verified the code claims in my KAN-39 assessment before relaying
them and found three wrong. Correct the record before `cto` builds on it.

**Verdict:** **The corrections are accepted in full. I re-verified all four myself.**
**B3 is retracted — the claim was false**, and it had been ranked a promotion blocker and
dispatched to `cto` as KAN-53. B5's count was wrong. B6 overstated. B2 I had understated in
my own favour. **The overall verdict — not launch-ready — is unchanged; B1 and B2 carry it.**

**Why:** all three errors were **code measurements**, taken directly, by a seat whose
evidence domain is the business corpus. The corpus half of the same document — where I
quoted documents I had read — held up completely under the same review.

- **B3 (retracted).** `settings_screen.dart:104` has a Language row; `:1064` opens
  `_showLanguagePicker()`; `:1091` reads and writes `localeProvider`, which `main.dart:254`
  watches and `:268` passes into the app. Switching works. `PROJECT_STATE.md` WIRE-10
  attributes the `app_router.dart:590` placeholder to `/settings/language`; it belongs to
  `/language_selection`, an orphaned route. **I repeated the record and then escalated a
  MED/small finding to a launch-gate P0 without opening the screen.**
- **B5 (number wrong, finding sharper).** 4 empty methods, not 18 — the static sink
  `trackEvent`/`trackScreen`/`setUser`/`reset`. The other ~14 tracking methods are fully
  written and call `trackEvent`. So the instrumentation already exists and one empty sink
  discards all of it: KAN-51 is wiring a provider, not building instrumentation.
- **B6 (restated).** Cricket is supported — 107 occurrences. Absent is the *wedge*:
  CricClubs, Playtomic, Strava all 0. Strategic conclusion unchanged.
- **B2 (understated).** 2,092 LOC, not ~1,500. Zero importers confirmed.

**Consequence:** `BRIEF.md` §10 corrected with a correction banner and a status table;
`DECISIONS.md` P-004 amended and **P-006** added (the CPO sources code facts from the
Analyst, never by measuring); `ROADMAP.md` Wave P reduced to four blockers; `LEARN.md`
gains the generalising lesson. KAN-53 retitled `[RETRACTED]`, commented and moved to In
Review for `task-auditor` to close. KAN-51 rescoped, KAN-52 line count fixed, KAN-54
retitled and restated.

**Escalated:** **`master-analyst` must correct `PROJECT_STATE.md` WIRE-10** — the route path
is wrong and it is not my file to edit.

**Handoff:** `cto` — **do not action KAN-53.** KAN-51 is smaller than first scoped. KAN-52
is larger. `task-auditor` — KAN-50 and KAN-53 are both back in In Review.

## 2026-08-27 — KAN-39 / KAN-50 — Launch-readiness: the business gap analysis
**Question:** Is the business ready for a commercial launch, and what specifically is not?
Fill `docs/BRIEF.md` from the 26-document corpus; find the contradictions, the gaps, and
the drift from measured build state.

**Verdict:** **NOT READY.** Four of `13b`'s ten binding P0 launch criteria are red against
`PROJECT_STATE.md`, plus the GTM playbook's analytics gate. Separately, the cricket-first
wedge — the entire acquisition strategy — has no cricket feature in the product. The app
being live is not in question; being *promotable* is.

**Why:** the bar is the corpus's own, not mine. `13b launch runbook`: *"The go/no-go gate
(Section C) is binding. If a P0 criterion is red, you hold the launch. No exceptions, no
'we'll fix it live.'"* Red: P0-9 security (609 notification rows across 49 recipients
readable by the `anon` key that ships in the public web bundle), P0-6 data safety (PDPL
export unreachable — `DataExportService` has zero importers), P0-10 bilingual integrity
(`/settings/language` renders `Text('Language Selection - Coming Soon')` against
`06e` §5.3's *"Not 'Arabic version coming soon.'"*), and `14` H6 no-dead-buttons (a
"Message" button on every user profile routes to "Coming Soon"). Plus `08` Part 2 §A.2's
*"Analytics instrumentation verified"* — `AnalyticsService` is 18 empty method bodies, so
"games confirmed" (`02`'s north star, `01` Truth 7's optimisation target), CSAU, every
Month-3/6/9 target and all six Path-C pivot triggers are uncomputable.

On the wedge: `07d` calls cricket-first *"the single most important strategic
recommendation in this document"*; `13a` Sprint 7 gates on a working CricClubs deep-link.
`grep` over `lib/` and `supabase/`: CricClubs 0, Playtomic 0, Strava 0, find-a-4th 0,
women-only 0, Ramadan/prayer-time 0.

**Consequence:** `docs/BRIEF.md` rewritten — §§1–7 filled from the corpus (retiring most of
the ten `NEEDS PO INPUT` markers), §§8–14 carrying seven blockers, fourteen internal
contradictions, seven gaps, and a per-document improvement list. Five decisions logged as
`P-001`–`P-005`. Five new blocker tickets raised: KAN-51 (analytics), KAN-52 (data export),
KAN-53 (Arabic switcher), KAN-54 (the cricket wedge — PO decision), KAN-55 (hold the venue
partner pack — it contracts deliverables that do not exist). `docs/ROADMAP.md` needs a
promotion-gate wave carrying the five blockers; not yet written.

**Escalated:** six questions to the PO, `BRIEF.md` §14. The two that block other work —
(1) **which financial model is the plan**: `00`/`02`/`03` say ~$1.5M Year 1 on 50K MAU,
`12c` says $82K base — 13–27× apart, and until it is settled "on track" has no meaning;
(2) **does the App Fee stand** — `12b` charges free players AED 1.3 per transaction and
takes 80% of the organiser uplift out of what a player pays, against `01` Permanent Truth 1,
`02`'s *"Dabbler does not extract value from players"* and `04` Non-Negotiable 1, which
`04` Art. 33.1 says no officer may waive. This must be ruled on before any pricing is built.

**Handoff:** `cto` owns B1 (KAN-36/37/38) and the technical shape of KAN-51/52/53.
`master-analyst` owns `PROJECT_STATE.md`, which this analysis consumed rather than
re-measured. KAN-54 and KAN-55 are the PO's, not an agent's.

---

## 2026-08-29 — Backlog clearance + MVP 1+ prep

**Notion corpus study: COMPLETE.** All 26 documents read and mapped (`corpus-map` memory).
No document remains unprocessed. The container/child traps (`06`, `07`, `08`, `11`,
financial model, Sport Reference) are all resolved to their children; `11 v2` supersedes v1.

**Backlog closed:**
- **KAN-29** (rewards) — framing posted. Verdict ALIGNED WITH CONSEQUENCE. Gamification is
  committed (`05` slide 4, `11 v2` §F.3, `13a` Sprint 11, `14` D52–D54) so the slice cannot
  be buried wholesale, but only the 3-tier surface is Phase 1A. Recommended: keep the ~985
  LOC check-in surface, cut the 19,560 above it, revisit at Stage 2. Three sub-questions
  isolated as genuinely the PO's.
- **KAN-30** (clean architecture) — verdict NOT ESTABLISHED, **and reassigned**. The corpus
  contains no reference to internal code architecture in any of the 26 documents. This is
  `cto`'s under `CONTRACT.md`, not the PO's. One product constraint handed over: it must not
  sit between now and closing the P0s.

**Deliverable:** `docs/briefs/MVP1-PLUS-LAUNCH-CHECKLIST-DRAFT.md` — draft only, for a
negotiation. Part A is the promotion gate judged against `13b`'s ten P0s (5 red, 1 amber,
2 unverified). Part B is next-release scope. Part C is 8 open questions.

**The finding I most want the PO to see:** P0-7 (monitoring) and P0-8 (rollback) are the only
two P0 criteria with **no ticket and no owner**. They are also what makes the rest of the gate
measurable and a bad promotion recoverable.

---

## 2026-09-06 — Skills audit of this seat (survey, no changes)

Read `agent/skills/` (74), `agent/skills/AVAILABLE.md`, `agent/roles/cpo.md`. Opened
SKILL.md bodies for: `incoming-request-advisor`, `derisk-measurement-advisor`,
`prd-development`, `autonomous-investigation`, `positioning-statement`, `cpo-advisor`,
`cpo-review`, `grill-with-docs`, `to-spec`, `front-door`, `wait-what`,
`good-strategy-bad-strategy`, `blue-ocean-strategy`, `crossing-the-chasm`,
`monetizing-innovation`, `inspired-product`, `continuous-discovery`,
`porters-five-forces`, `problem-framing-canvas`, `ansoff-matrix`, `swot-analysis`,
`feature-investment-advisor`, `prioritization-advisor`, `epic-breakdown-advisor`,
`roadmap-planning`.

**Kept:** `incoming-request-advisor`, `derisk-measurement-advisor`, `cpo-review`,
`positioning-statement`, `jobs-to-be-done`, `competitive-analysis-process`,
`autonomous-investigation`, `writing-for-agents`, `grill-po`, `grill-peer`.

**Rejected from my own role file:** `cpo-advisor` (portfolio/PMF/org-design for a
multi-product company with retention data — Dabbler is pre-launch, one product, no
retention curve; its calculators are also documented as not installed).
`prd-development` (60–120 min PRD workflow that ends in an engineering-ready spec —
`po` owns tickets and `to-spec` covers the synthesis; this seat's output is a verdict).
`tam-sam-som-calculator`, `saas-revenue-growth-metrics`,
`saas-economics-efficiency-metrics`, `business-health-diagnostic` — all four assume a
running SaaS with live revenue; the numbers they want are in `02`/`15`/`17` as
committed forecasts, not measurements, so running them would manufacture analysis of
our own assumptions.

**Recommended additions (bodies read):** `good-strategy-bad-strategy` (audits whether a
corpus document is a strategy or a goal list — the strongest single fit for this seat),
`monetizing-innovation` (the only opened skill that reasons about pricing/packaging as
design input, which is what `02` and `16` are), `crossing-the-chasm` (beachhead and
whole-product for the GTM playbook), `problem-framing-canvas` (for NOT ESTABLISHED
verdicts, where the job is to say what would settle it).

**Rejected candidates from the offered list:** `porters-five-forces`, `swot-analysis`,
`ansoff-matrix` (all three are web-research instruments over public sources; my ground
truth is a private corpus and the market mandate is `analyst`'s and unscoped),
`blue-ocean-strategy` (category creation is already decided in `00`/`01`),
`inspired-product` / `continuous-discovery` (both require weekly live customer contact
we do not have pre-launch).

**Gap with no tool:** nothing anywhere holds a proposal against a written corpus and
returns which document it contradicts, with the passage. `grill-with-docs` writes ADRs;
it does not test against existing ones. Nearest public method is a policy/compliance
conformance review (a control-mapping matrix, as MASVS does for security); no product
framework I know of does this. The four-verdict ladder in my role file IS the method —
it is written as prose in one role file and has no skill, so no other seat can apply it
and it cannot be improved independently of the file.

**Structural defect noted, not acted on:** `agent/roles/cpo.md` has no mandate section.
It did not change these answers — the corpus section carries enough of the remit.

**Handoff:** `team-lead` holds this survey. Nothing changed but this file.

---

## 2026-09-06 — The D4 fallback ruled: the premise is wrong, and the null field is in dead code

**Task:** `team-lead` asked for a pre-decided fallback for the case where KAN-130's client
half (`lib/data/models/wallet.dart`) cannot land before D4 activates Mon 2026-09-14 — three
options offered: accept the null, hold D4, or amend `CONTRACT.md` §4.1.

**Verdict: ACCEPT (option 1), and no window needs defining in days.** Two independent
grounds, one strategic and one measured.

**1. The date is not a money commitment.** D4 activating is a lead taking tickets. `13b`
(`37dd4c6dd86d805f9602dc53bcd725f5`) P0-5 makes **payments dormant** a binding go/no-go
criterion — *"`paymentsLive=false` confirmed; no real charge possible"* — and §A.2 states
*"Phase 1A takes no real payments."* §I.3 puts booking activation at **Month 9**. Nothing
in the corpus commits money movement to 2026-09-14. `02` Pillar 1 says the Venue
Partnership layer activates *"Day One (Year 1, Q1)"*, which is the revenue *pillar*, not a
build date, and it names no calendar date at all. **Noted as a new corpus contradiction:
`02` "Day One" vs `13b` "payments dormant / Month-9 booking activation".** `02` outranks
`13b` on precedence; neither yields 09-14.

**2. Severity is nil, measured not inferred.** The field is `Wallet.userId` /
`WalletLedgerEntry.userId`, `wallet.dart:6,28` and `:49,79`. **It has zero readers.**
`grep -rn "\.userId" lib` returns only the two declarations and two constructor params.
The only files importing `models/wallet.dart` are `wallet_repository.dart` and
`wallet_repository_impl.dart`; **`WalletRepositoryImpl` is instantiated nowhere** — no
provider, no controller, no screen, no test. `getWallet()` (`:20`) does not filter on
`user_id`; it relies on RLS. Balances read `available_cents`/`balance_cents`
(`wallet.dart:29`), untouched by the drop. `toMap()` writes `'user_id'` but nothing calls
it — and an insert against a dropped column fails **loudly**, not silently. `T-049`
measured all five money tables at **0 rows**. So: not user-visible, touches no balance
anyone reads, reaches no money movement.

**The window, stated as a condition rather than a date:** the null is acceptable until the
wallet slice acquires its first reader — a provider, controller or screen. Whoever wires
one is blocked on `wallet.dart` first. That is measurable by anyone and does not expire
into an accident the way a date does.

**Option 3 (amend §4.1) — ruled on, since nobody had.** Permitted, and wrong. `G-019` and
`G-021` already amended §4.1 twice, so amendment is not foreclosed; the exclusion bars
*other seats*, which is a different clause. But the grant is scoped to **five named
tickets** — *"Work outside those five tickets is not covered by this grant, whatever path
it touches"* — and KAN-130 is not one. Adding the file without adding the ticket grants
nothing; adding the ticket converts a Phase 0 refactor grant into a general write licence
and destroys `P0-1`'s golden test as evidence, which is the grant's whole purpose.
**Recommendation: do not amend.**

**Option 2 (hold D4) — rejected.** Holding a date to protect a field nothing reads is cost
with no benefit. Had severity been real, the corpus's own answer is not "hold" but
**contain**: `13b` §G.4, *"Risky features (booking, payments...) sit behind flags.
Disabling = a config change, seconds, no redeploy."*

**The corpus DOES address correctness-versus-date** — three passages, all pointing the same
way: `13b` §C.1 *"When in doubt, hold"*; §G.3 *"Never apply a destructive migration (drop
column/table) on launch week — use additive-only changes; deprecate later"*; Appendix C
*"No schema changes except additive + reversible"* from T-7. So this is **not** a strategy
gap. What the corpus does not address: how an internal engineering stack activation relates
to those launch-window rules at all — §G.3 and Appendix C are scoped to launch week, and
the corpus has no rule for a destructive migration outside it.

**Not verified:** that `T-051`'s migration drops only `user_id` and touches no other column
`wallet.dart` maps (`cto`'s domain, taken from the brief); whether `payouts.dart` or any
other money model carries the same field (out of scope as briefed); the timing arithmetic —
taken from `pm` and `team-lead-4` as measured, not re-derived.

**Changed:** this file only. No code, SQL, copy, git, Jira or Notion. `T-051` untouched.

**Reported to:** `team-lead`.

---

## 2026-09-06 — `P-036`: the `financial_ledger` retention ruling (routed by `pm`, referred by `cto` at `T-054`)

**Task:** two arrived. (1) `team-lead` re-asked for the D4/KAN-130 fallback ruling — **already
delivered earlier today**, recorded in the entry above; re-verified rather than re-ruled, and all
three measurements hold: `Wallet.userId` (`wallet.dart:6`) and `WalletLedgerEntry.userId` (`:49`)
have **zero readers**, `WalletRepositoryImpl` (`wallet_repository_impl.dart:13`) is **instantiated
nowhere**, and `wallet.dart` is **not** in the §4.1 grant. (2) `pm` routed the `financial_ledger`
right-to-erasure gap. That one was unruled; it is now `P-036`.

**Ruling: retain, and disclose.** Adopted `cto`'s `T-054` technical analysis rather than
re-deriving it — deletion unbalances a double-entry journal, and scrubbing `entity_id` while
`booking_id`/`payment_intent_id` survive is anonymisation in appearance only. Concurs with `cto`.

**Governing documents.** `13b` §C.2 **P0-6** (binding): *"PDPL consent + export + delete verified in
production"*; §A.2 *"Data export + account deletion verified working"*. `04` Article 11 **Right 6**:
*"Every player has the right to know how their data is being used."*

**The gap, stated as a gap.** `04` Article 11 lists **seven** rights *"without exception and
regardless of jurisdiction"* and **erasure is not one of them**. **No corpus document names any
retention period or lawful basis.** `12b` §I.1 raises PDPL only against data products; §I.2 Flag 3
budgets *"$25-50K PDPL legal"* — unspent. **A retention period is obtained, not ruled**, and I did
not assert one.

**The finding nobody had — a live disclosure defect.** Three shipped strings promise total erasure:
`account_management_screen.dart:1072` and `:1175`, `danger_zone_section.dart:373`. `financial_ledger`
holds zero rows, so they are true today and false on the first row. The retained uuid was never the
exposure (`T-054` measured it admin-only); **the mismatch is.** Owners: legal review → CEO via `pm`;
EN+AR strings → `content-manager`, filed by `po`; `delete_my_account` comment → already owed at
`T-054`; privacy-policy clause → `13b` §A.2. **Zero SQL — `KAN-130` stays at 2.**

**Not verified:** every migration fact (single FK, trigger body, cascade list, zero-row count,
`is_admin()` anon behaviour) taken as measured by `senior-backend`/`pm`/`cto`; whether AR strings
mirror the EN three; whether a privacy policy exists at a public URL.

**Changed:** this file, `DECISIONS.md` (`P-036` inserted before `G-012`), and `cpo` memory. No code,
SQL, copy, migration, git, Jira or Notion write. `T-051` and `T-054` untouched.

**Reported to:** `pm` (ruling, to relay to `team-lead-4`, `cto`, `po`) and `team-lead`.

---

## 2026-09-06 — `P-036` re-asked and re-verified; one factual claim in it corrected

**Task:** `team-lead` asked for the `financial_ledger` retention ruling. **It was already
delivered by this seat today and is committed** — `P-036` in `DECISIONS.md` (rode in on
`dabbler-docs` `9715c93`), entry above. The brief was dispatched before that report landed.
I did not re-rule it. I did re-read the corpus independently, and the ruling holds:
**retain, and disclose.**

**What the independent pass changed.** `P-036` as written claimed *"No document in the
corpus names a retention period, a lawful basis, or a financial-records exception for
anything."* **The first clause is wrong and I have corrected it in place.** `11` service
blueprint **v2** (`367d4c6dd86d80c6aacdc130d6c92027`) §I.4 does carry one:

> *"Data retention policies (game data 7 years; analytics 2 years; logs 90 days)"*

and the deletion SLA the ruling turns on: *"Deletion (14 days SLA)"*.

**The gap survives in narrowed form, and is more useful narrowed:** three categories named,
**financial/payment records not among them** — while the same document lists Stripe as a
required integration and enumerates *"Payment records (split records, transactions, audit
trail)"*. So the corpus has a retention policy with a financial-records-shaped hole, not an
absence of one.

**This answers `team-lead`'s question 2 — where it gets documented.** Not a new instrument:
a **fourth bullet in `11` v2 §I.4**, beside the three that exist. **`po` writes it** —
Notion is read-only for me. The period still comes from the PDPL legal review (`12b` §I.2
Flag 3, unspent); `11` v2's existing *"game data 7 years"* is the customary commercial-books
figure and the precedent that review will confirm or displace. **I assert no number.**

**Second addition to the disclosure half:** `13c` requires declaring in Google Play Data
Safety that *"users can delete their account + data in-app"* and *"Can users request data
deletion? → Yes."* A second public artefact the three in-app strings must stay consistent
with, alongside the privacy policy.

**Re-confirmed and unchanged:** `04` Article 11 lists **seven** rights *"without exception
and regardless of jurisdiction"* and **erasure is not among them** — Right 2 is visibility
control, Right 3 portability. The erasure duty is regulatory/operational (`13b` P0-6, `13c`,
`11` v2's 14-day SLA), never constitutional. No Permanent Truth or Non-Negotiable is touched
by retaining an admin-only uuid. `cto`'s `T-054` untouched; both defective remedies adopted
as `cto` stated them, not re-derived.

**Not verified:** every migration fact (`financial_ledger`'s single FK at `:30583`, the
trigger at `:19219`, `delete_my_account`'s cascade list at `:5257`–`:5302`, zero rows,
`is_admin()` anon behaviour) — I read the schema lines and they match what was reported, but
the live-catalogue and RLS measurements are `cto`'s and `pm`'s; whether the AR strings mirror
the EN three; whether a privacy policy exists at a public URL today.

**Changed:** this file and `DECISIONS.md` (`P-036` correction block, local only). No code,
SQL, copy, migration, Jira, Notion write, push or PR.

**Reported to:** `team-lead`.

---

## 2026-09-06 — `pm` peer question on `FeatureFlags.squads`: already ruled at `P-035`, re-verified, unchanged

**Task:** `pm` asked peer-to-peer whether to rename or drop `FeatureFlags.squads` (`FLAG-04`,
`PROJECT_STATE.md` §24d/§24h). **Already ruled 2026-09-04 as `P-035` — cut it, do not rename.**
Re-verified rather than re-ruled; nothing changed, and I did not re-open it.

**Every `P-035` figure holds at HEAD:** `feature_flags.dart:75` `static const bool squads = true`;
exactly one consumer, `main.dart:88`; `lib/features/squads/` absent; `squads_repository.dart` (112)
+ `_impl` (762) = 874 LOC live via `social/providers.dart:8-9`.

**Two measurements `P-035` did not carry, both reinforcing it.** `lib/core/auth/session_cleanup.dart:65-68`
invalidates three squad providers on sign-out — the capability is wired deeper than "a repository
with 3 importers". And the word is **user-visible in shipped copy**: `nav_trend_community_title` =
"Growing squads" / "Squads بتكبر" (`app_localizations_en.dart:1356`, `app_localizations_ar.dart:1326`).
The concept is neither dead nor its own slice — it lives inside `social`, which is an argument
*against* renaming, since a rename attaches the name to a slice boundary that does not exist.

**`pm`'s third framing — hold it as a placeholder if squads returns — `P-035` already rejects:** if
squads is later ruled in scope the correct state is the flag at **`false`**, tracking an unbuilt
client, never `true`. All three framings resolve to "delete now"; only "leave it `true`" is wrong
under every ruling.

**Not mine to close.** `P-035` is **`PROPOSED`, awaiting `po`** — and under `ROADMAP.md` §5 it
would be the first formal CUT, so it needs a decision id on approval.

**Changed:** this file, and a dated re-verification note appended inside `P-035`. No code, flag,
copy, SQL, git or Jira write.

**Reported to:** `pm`.

---

## 2026-09-06 — `P-037`: subscriptions need a charge record; `payment_intents` is not it, and `KAN-136`'s FK stands permanently

**Task:** `pm` routed `cto`'s `T-061` model question — does the committed subscription/top-up model
require a `payment_intents` row with no `booking_id`, and is there an eight-day clock before D4
activates 2026-09-14? Not blocking `KAN-136`.

**Ruling: ALIGNED WITH CONSEQUENCE — but the consequence is not the one asked about.**

**Product half, decisive.** `12a` designs **five** subscription streams in full, every one a
recurring charge with no booking: Player Pro §B.2 (AED 29/mo), Organiser Pro §C.2 (AED 99/mo),
**Venue Basic listing fee §D.2 (AED 99/mo, charged to a venue)**, **Venue Pro §D.3 (AED 299/mo)**,
**Corporate §E.1 (AED 7.5–25K/yr, annual, by invoice)**. `12b` §J.2 confirms two rails — Stripe
Billing for subscriptions vs Stripe Connect for marketplace. `12a` §A.2 **Principle 8** is an
explicit instruction to make billing-schema room ahead of the feature.

**The correction that matters — nullable `booking_id` would be the wrong fix.** `payment_intents`
(`baseline_schema.sql:23491`) is `booking_id` NOT NULL **and** `user_id` NOT NULL, RLS owner-read on
`user_id` (`:32824`). **Three of the five streams are not charged to a player at all.** Relaxing
`booking_id` half-solves one stream, leaves three unrepresentable, and weakens the integrity `T-061`
just added. **`payment_intents` is the booking rail; the FK should stand permanently.**

**The real gap — the subscription rail records no money.** `subscription_plans` (`:24673`) is
`key, label, description, created_at`, **no price**. `user_subscriptions` (`:24897`) is
`user_id, plan_key, started_at, expires_at, is_active` — **no amount, currency, provider, cycle or
payment linkage.** Entitlement-only. Nothing today can record a subscription charge.

**The clock — real, but not eight days of the kind claimed.** `12a` §A.3 *"During Phase 1A (Months
0-9, pre-booking), ALL features are free for everyone"*; §H.3 *"Month 9 (Phase 1B): Subscriptions go
live"*; `12b` §A.1 streams 1/2/5 at M9; `13b` **P0-5** `paymentsLive=false`. **The zero-row window
closes at Phase 1B M9, not 09-14 — there is no data-migration deadline.** There *is* a **rework**
deadline: 110 D4 features built against an entitlement-only rail encode "subscriptions carry no
money", and fixing that after is code rework, not a backfill. Sufficient reason to settle before
09-14; costs nothing now, since `12a` holds every input.

**NOT ESTABLISHED — wallet top-ups.** `pm` paired them with subscriptions. The corpus commits no
user-initiated top-up. `12b` §F.4 Stream 13 is *Wallet Float* — organiser fee collection, M18,
gated on a Central Bank UAE **SVF licence above AED 50K** (§I.2 Flag 1), with the standing rule
*"keep wallet balances below threshold via fast payouts."* Do not size schema for it.

**Owed:** `KAN-136` unchanged; the charge-record shape is **`cto`'s** architecture call and I handed
over the product requirement, not a design; the date recommendation is **`pm`'s with the CEO** —
I do not move activation dates.

**Not verified:** whether any D4 ticket already assumes a charge shape; whether `wallet_ledger` or
`financial_ledger` could carry it (`cto`'s); `T-061`'s migration text, taken as described.

**Changed:** this file, `DECISIONS.md` (`P-037`). No code, SQL, migration, Jira or Notion write.
`T-061` and `T-049` untouched.

**Reported to:** `pm`.

---

## 2026-09-06 — `P-038`: the `plan_prices` schedule, supplied in full — and the plan-key mapping that blocks the backfill

**Task:** `T-063` step 1 — *"`cpo` supplies the numbers; I do not invent prices."* Supplied, from
`12a` verbatim, in `T-063`'s own column shape.

**The blocker `T-063` step 1 hits immediately.** `subscription_plans` holds `kickoff`, `pro`,
`prime`. **`12a` designs no such ladder and no third player tier** — its player ladder is exactly
two, Player Free (§B.1, *"AED 0, forever"*) and Player Pro AED 29 (§B.2); the other three committed
tiers are venue- and company-scoped, not player-scoped. `kickoff` = **0** is safe and may be
backfilled now. **`pro` and `prime` are NOT mappable and I did not invent them** — `12a` has *two*
different "Pro" products at different prices (Player AED 29, Organiser AED 99), and `prime` has no
counterpart at all. Naming `pro` at 29 would encode an unmade product decision into the price
catalogue, where it then reads as committed — the `P-035` error. **`po`/`pm` rule the mapping;
`T-063` steps 2–4 are unblocked.**

**Checked and cleared a suspicion rather than raising it.** `prime` buys a score boost, so I checked
Permanent Truth 3 (*"the discovery feed... treat every player as equally indexable"*).
`calculate_notification_score` (`baseline_schema.sql:3473`) scores notifications delivered **to** the
prime user — delivery priority for yourself, not visibility over others. **No conflict.** Recorded so
the next reader does not re-raise it. This is [[stay-in-evidence-domain]] working as intended.

**Supplied in full:** Player Pro and Organiser Pro × 5 markets, monthly and annual; Venue Basic and
Venue Pro × 4 markets; Corporate three tiers (UAE, annual, invoice); plus the grandfathered rows
§K.2 says never move — Founding Organiser AED 49 for life, Founding Player AED 19 year 1, Founding
Venue 6 months free, and the §J.2 save offers. **VAT is inclusive** (§F.3 *"All displayed prices are
final prices"*): `amount` is gross and `vat_amount` decomposes out of it — `cto`'s store-not-derive
is right, and this is the direction. **`valid_from` dates from Phase 1B (§A.3, §H.3), not today** —
a row valid now asserts a price was sellable during the free phase.

**Gaps in `12a` flagged, not filled:** no RoW USD VAT rate; Venue Basic has no annual price anywhere;
Venue Pro annual exists only in AED; Corporate has no non-UAE prices and Enterprise is *"25,000+
custom"*, not a catalogue row; §F.2 warns Egypt may launch subscription-light so its rows may never
activate.

**Not verified:** whether `subscription_features` implies a mapping (`cto`'s); whether client code
hardcodes `pro`/`prime`; `12c` not consulted — `12a` governs plan prices, `12c` is downstream (§L.3).

**Changed:** this file, `DECISIONS.md` (`P-038`). No code, SQL, migration, Jira or Notion write.
`T-063` untouched.

**Reported to:** `pm`.

## 2026-09-07 — Ruled the plan-key mapping (`P-039`). Retire `pro` and `prime`; the key must be persona-qualified

**Asked by `team-lead-4`** as the D4 entitlement gate, answering the question `P-038` reserved to this
seat. **ALIGNED WITH CONSEQUENCE.** Full entry: `Dabbler/dabbler-docs/DECISIONS.md` `P-039`.

**Both counts in the request were checked and the second was wrong.** Three live keys is right —
`select key, label from public.subscription_plans` returns exactly `kickoff`/`pro`/`prime`,
`description` NULL on all three, and **no seed `INSERT` exists in any migration**, so the key set is
unreadable from the repo. But **`12a` has no five tiers and no tier ladder at all**: its §A.3 matrix is
**persona × tier** across five personas. That is the ruling — `subscription_plans.key` is
one-dimensional and cannot express it, and **a key named `pro` is ambiguous across four products** —
Player Pro 29, Organiser Pro 99, Venue Pro 299, and Corporate, which §E.2 grants Player Pro free.

**The mapping:** `kickoff` → `player_free` (§B.1); `pro` → **two rows**, `player_pro` (§B.2) *and*
`organiser_pro` (§C.2); `prime` → **nothing, retired** — no third player tier exists in `12a`. Also
seed `organiser_free`, `venue_basic`, `venue_pro`, `corporate_starter`, `corporate_growth`. **Refused
four:** `corporate_enterprise` (§E.1 *"25,000+ (custom)"* — not a catalogue row), Verified Organiser
Certification (§C.4 *"Not a subscription tier"*), `venue_unclaimed` (§D.1 — no owner, so no subscriber),
and **Socialiser — NOT ESTABLISHED**, handed to `po` with the test that decides it.

**The consequence I measured rather than assumed.** `user_subscriptions`: 82 rows, all `kickoff`, none
on `pro`/`prime` — retirement strands no customer. But `subscription_features` holds 9 rows per key and
`notification_hourly_caps` 3 per key, and `prime`'s are wired into shipped functions (`:3513` rank
boost, `:4006` caps, `:17203` quiet-hours bypass). **`12a` commits no notification-priority product** —
§B.2's four pillars do not include it. So that is built behaviour with no committed product, and I
declined to give it a home to make the migration tidy. `:4006` defaults an unknown plan to free, so it
degrades safely; the `'prime'` literals become permanently false and need a ticket, not a dead branch.
Re-checked Permanent Truth 3 again: not engaged — the score is for notifications delivered *to* the user.

**Nothing becomes sellable.** §A.3 / §H.3 still bind: paid rows date from Phase 1B, per `P-038`.

**Verified myself:** the three live keys and labels, four live row counts, the table definition
(`baseline_schema.sql:24673`) and its three FKs, and `12a` read end to end. **Taken on relay:** the two
empty client greps and the skill-tier false lead — engineering facts that do not move the product answer.

**Changed:** this file and `DECISIONS.md` (`P-039`). No code, SQL, migration, Jira or Notion write.

**Reported to:** `pm` and `po`. Owed: `cto` the rename mechanism and the `'prime'` literals; `po` the
Socialiser question. **The D4 entitlement gate is open.**

## 2026-09-07 — `P-040`: `pro`'s 12 child rows. The split is **two product decisions, not twelve**

**Asked by `team-lead-4`** after `cto` refused the allocation as a product call — correctly; `P-039`
should not have parked it on `cto`'s read. **ALIGNED WITH CONSEQUENCE.** Entry: `P-040`.

**Counts confirmed by re-measuring** (9 `subscription_features` + 3 `notification_hourly_caps` per
key). **But the framing was wrong.** `subscription_features` is a **complete 9 × 3 matrix** — all nine
`feature_key`s exist on all three plans including `kickoff`. The rows are not entitlements granted to
`pro`, so they do not get allocated. **Eight of nine values are identical on free and paid.** `pro`'s
entire product content over `kickoff` is **one flag** — `quiet_override_high` false→true — plus a caps
uplift 5/10/20 → 10/25/50. Twelve rows, two decisions.

**The finding that drives the ruling: the two read paths default in opposite directions.**
`user_has_feature` (`:20776`) is an `EXISTS` join — **missing row = deny**, so an incomplete set would
give a paying subscriber *less than Player Free* (a downgrade-on-upgrade, against §A.1).
`check_notification_rate_limit` (`:4006`) does the reverse — `no cap rule = allow`, so **omitting caps
rows grants unlimited**. Omission is never the cautious option; it is deny in one table and unlimited
in the other. **So both new keys take a complete set — 24 rows. Structural, not a product claim.**

**Both real decisions: NOT ESTABLISHED, set to Player Free values** — `quiet_override_high` `false`,
caps `5/10/20`. Not a default-assignment to unblock: `false` **asserts nothing** and reproduces the one
tier `12a` fully specifies, whereas `true` encodes a product nobody committed. **Zero subscribers on
`pro`/`prime`, so nobody loses anything**, and it is one `UPDATE` when a product exists. Named the
`11b` test that settles it.

**The near-miss I recorded so it is not made later:** §C.2 commits *"Unlimited payment reminders +
bulk messaging"*, which looks like this. It is not — these tables govern notifications delivered **to**
the holder (`to_user_id`), the Organiser commitment is **outbound**. Opposite direction.

**Also caught for the migration author:** the FK is `ON DELETE CASCADE` (`:31558`), so dropping `prime`
deletes its 12 children automatically — explicit deletes will report zero rows and must not read as a
failure. Six acceptance criteria written into `P-040` at `cto`'s request.

**Still owed and NOT answered:** the Socialiser question from `P-039`. Turns on the same `11b` read;
settling all three in one pass is the efficient shape.

**Changed:** this file and `DECISIONS.md` (`P-040`). No code, SQL, migration, Jira or Notion write.
**Reported to:** `po` and `cto`.

## 2026-09-07 — `P-041`: the values for all eight keys, and a function name I cited wrong

**`cto` accepted `P-040` and correctly generalised its structural half.** My argument — omission is
deny in `user_has_feature`, unlimited in the caps function — never depended on which key. So **all
eight new keys need a complete set: 96 child rows, not 24.** `organiser_free`, `venue_basic`,
`venue_pro`, `corporate_starter`, `corporate_growth` with no caps rows would each grant unlimited
notifications. `cto`'s scope correction is right.

**But rows without values decide nothing, and that handed six keys back to me.** Ruled `P-041`: **all
eight take `kickoff`'s values** — nine flags at Player Free, caps 5/10/20. I checked each persona's
feature list rather than extending the earlier two by analogy: §B.2, §C.1, §C.2, §D.2, §D.3, §E.2 —
**none commits any notification-delivery product.** NOT ESTABLISHED throughout.

**A consistency check that confirms the shape.** §E.2 grants Corporate employees *"Player Pro features
free"*. Since `player_pro` carries Player Free values under `P-040`, the Corporate keys taking the same
values satisfies §E.2 exactly. **Had I granted `player_pro` an uplift, the Corporate keys would have
had to inherit it or contradict §E.2** — the conservative value is the only self-consistent one.

**I cited a function name wrong.** There is no `check_notification_rate_limit`; it is
**`can_send_notification_now`** (`:3987`, test at `:4006`). Verified by grep after `cto` flagged it;
**`P-040` corrected in place** so it does not travel. The body I quoted and the ruling were right —
only the name was wrong. `cto` also sharpened `user_has_feature` (`:20776`): it requires
`is_enabled = true`, so a `false` row denies exactly like a missing one — which is why the criterion
specifies values, not just row counts.

**`cto` found a regression the rename creates** and I agree it cannot be deferred:
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
