---
name: project-wave3-doc-gallery-state
description: KAN-293 epic (Wave 3, in-app documentation gallery) status as of 2026-09-18 — what's Done, what's blocked, and the process gap found on KAN-323
metadata:
  type: project
---

Status snapshot, 2026-09-18, of the documentation-gallery chain under epic `KAN-293`:

- `KAN-295` (GalleryEntry page/group/id fields) — **Done**.
- `KAN-322` (asset move), `KAN-326` — **Done** (per predecessor po session).
- `KAN-325` (D-042 heading migration + `@specimen` audit) — **Done**, closed 2026-09-18 on the
  D-043 ruling (see [[feedback_specimen_confirms_not_replaces]]); no rework was needed.
- `KAN-323` (loader/splitter/`@specimen` resolution, `doc_loader.dart`/`doc_page.dart`/
  `doc_specimen_resolver.dart`/`doc_vocabulary.dart`/`doc_view.dart`) — code implemented and
  committed (`8bc96df`), moved to **Self-review** 2026-09-18 (validation_route computed `self` by
  system-policy). **Blocked from Done** on two independent things: (1) AC5 named committed unit
  tests that collide with the CEO's standing no-new-tests instruction — same shape as KAN-294,
  put to the CEO, answer not back as of 2026-09-18; (2) a Persistent State process gap — this
  task's `executor_evidence` is empty (`store.release` was never called when the code landed), so
  `store.open_review_context` cannot resolve a SELF owner. Do not fabricate evidence to force it;
  this is a finding for the Orchestrator about how the work reached the repo outside the normal
  claim/wake/release pipeline.
- `KAN-324` (heading-vocabulary test gate) — Ready, re-baselined, unstarted. Must import
  `DabblerDocVocabulary` (`doc_vocabulary.dart:62`), `DabblerDocSplitter.split`
  (`doc_page.dart:182`) and `DabblerDocSpecimenResolver.unresolvedIds`
  (`doc_specimen_resolver.dart:55`) rather than re-deriving any of them — all landed under
  `KAN-323`.
- `KAN-327` (render screen, wiring `doc_view.dart` into a navigable route) — Ready, blocked on
  `KAN-323`/`KAN-325`. **Partially pre-built**: `DabblerDocPageView` (`doc_view.dart`, landed
  under `KAN-323`) already renders lead prose and section/`@specimen` content via existing
  `gallery_page.dart` chrome — that's this ticket's AC2/AC3 rendering logic. Still open: the
  path/id-to-loader wiring, title (`#`) rendering, `## Source` rendering, and `lib/main.dart`
  route registration.
- **`KAN-329`** — the `## Axes` figure gate, ticketed 2026-09-18 against `cto`'s T-086 ruling
  (`DECISIONS.md:14144`). One Task (not split): `@figure <value> <claim>` block type in
  `doc_page.dart` beside `@specimen`; 19 additive directives across 11 files (member/token/ruling
  claim, resolved per-site, not assumed uniform — `progress_bar.dart`'s `SIZES` comment is a
  dartdoc quoting JSX, the real member is `trackHeightFor`); `tool/check_doc_figures.dart`, a
  plain `dart run` script importing `doc_page.dart` ONLY (never `doc_loader.dart`/
  `doc_specimen_resolver.dart` — both pull in Flutter transitively) so the CEO's no-new-tests
  constraint is met by construction; resolution + completeness scan must land together. Separate
  from `KAN-324` (different evidence domain/runner) but shares `DabblerDocSplitter.split` — no
  second parse, no ordering dependency, but both tickets touch `doc_page.dart`. Ready,
  `required_capability: frontend`, due 2026-09-25.

**Why this matters:** the chain is nearly complete but has a real process irregularity (the
executor-evidence gap on KAN-323, and KAN-295 before it) worth watching for on other tickets from
this same session — check `executor_evidence` in the task's Persistent State record before
assuming a formal SELF review can open, even when the code is visibly committed.

**Root cause, confirmed by team-lead 2026-09-18: this is a Thebes infrastructure gap, not a
Product one — do not try to reconcile it from the PO seat.** team-lead dispatched `fe-295` and
`fe-323` as direct Agent invocations rather than through the claim -> wake -> ExecutionRequest ->
release path, so no `store.release` was ever called and no durable evidence exists that a seat
owned and released the work, even though the code is correct and committed. team-lead is carrying
this to the CEO as a SYSTEM_MAINTENANCE finding about how the session was run, not opening a
Product ticket for it. If a future task shows the same shape (code committed, `executor_evidence`
empty, `ownership: null`), recognize it as this same pattern rather than re-diagnosing from
scratch — flag it and move on, don't fabricate evidence to force a review context open.

**Taxonomy relationship, D-047(e), worth keeping durable:** one taxonomy (D-033), two views in
strict containment. `GalleryIndex._bands()` renders **45** specimen pages (`GalleryEntry`
registrations grouped by `GalleryPurpose`); the nav (parsed from `_order.md`) renders **all 58**
doc pages. Zero specimens point at a missing page; **13** doc pages have no specimen of their own
(9 components folded into a sibling's combined specimen — e.g. `radio`/`toggle` into `checkbox`'s
— plus the 3 `patterns/` pages plus `start-here`). Both views are correct; neither should be
merged into the other (a `_bands()`-reuse instruction for the nav was ruled and then withdrawn
once this was measured). The drift protection is a **containment invariant** — every specimen's
`page` must resolve to a real doc page — not a shared derivation. **`KAN-332`** tickets this gate,
held in Backlog pending CEO prioritization (not urgent: the invariant already holds).

**KAN-328 AC3 — RULED, D-049, 2026-09-18.** Option (a), scoped to order only:
`_bands()` reads its nine-group sequence from `_order.md` at runtime; the `GalleryPurpose` enum
stays for membership/typing, only its declaration order stops being load-bearing; not a call into
the nav's derivation (two independent readers of one authored file); Foundations-before-the-nine
section order stays hardcoded (D-033(a), ruled); **and the index must fall back to
`GalleryPurpose.values` if `_order.md` is unreadable/unparseable — D-047(d) forbids the index
degrading the way the nav may.** D-049(f) also adds a fourth `D-043` figure class: **AUTHORED**
(single home is a file under `assets/documentation/`; read at runtime, never transcribe) — keep
this in mind for any future doc-corpus ticket in this project. Posted to `KAN-328` (comment
11177); `fe-nav` was holding pending this and can now proceed.

**KAN-330 — FINAL RECONCILED SHAPE, D-051/D-052, 2026-09-18.** Severity order (was wrongly
###-only, then wrongly links-first): **1. `###` (181/57) 2. bold-across-break (66/43) 3. list
items (78/32, ruled: bullet `textTertiary`, item text `textSecondary`, hanging indent, space4
indent/space2 between items) 4. links (was 87/33, now 9/3 — see below).** Root cause for all four:
`_spans` has exactly two alternatives (bold/code), no fallback branch — D-051(b) rules the
renderer completes to the corpus, never the reverse, and explicitly wants no gate (D-051(f)).
Links dropped 87→9 because D-052 found **zero** component-to-foundation links (the D-033
architecture KAN-330 first ranked #1 was never built) and ruled 78 of the 87 aren't links at all —
governance citations (`[D-004 (cxo)](../../../../dabbler-docs/DECISIONS.md)`) are wrong
independently of any renderer (misaddress a 13,000-line file, cross an unpublished repo boundary,
meaningless at runtime bundled assets) — **`KAN-334`** removes their link syntax, content-manager
work, NOT a renderer fix, NOT a `D-051`(b) breach. The 9 that remain (three `patterns/*.md`
`## Related` sections, D-042(c) required) get text-only + underlined treatment; **tappability is
explicitly out of scope** — a joint future `cto`/`cxo` mechanism call, resolve-by-page-id like
`@specimen`, not an executor judgement.

**KAN-330 AC2 (superseded detail below, kept for history) — RULED, D-050, 2026-09-18: this was a live defect, not an open nicety.** `###`
sub-headings are not parsed at all (190 lines, 58/59 pages) — confirmed by reading
`doc_page.dart:206-210` (only `'# '`/`'## '` recognised). Treatment: `DabblerType.caption1`
(12px, same as body — deliberate, avoids the size-inversion reflex), `FontWeight.w700`
(distinguishes from inline bold's `w600`), `textPrimary`, sentence case, no letterspacing.
Guardrail: if w700 isn't visually distinct from bold at 12px in the shipped face, that's a
re-rule for `cxo` — never fix by enlarging or uppercasing (uppercase belongs to
`GallerySectionLabel`, not this). Ticket's AC2 updated to the ruled treatment.

**KAN-333 — new, found by `cxo` while ruling KAN-330 AC2, ticketed separately as instructed.**
`_DocSection` (`doc_view.dart:64-72`) has zero interior spacing at all — section label welded to
its first paragraph, prose blocks abut. D-050(c) rules the exact ramp: before `###` 18 (space6),
after `###` 6 (space2), between sibling prose 12 (space4), after `##` label 12 (space4), specimen
block same 18 as a sub-heading (named extension, not ruled). Ready, due 2026-09-21 (same as
`KAN-330`, same urgency/file area, deliberately separate tickets).

**Superseded — KAN-328 AC3, open as of 2026-09-18 mid-session, was awaiting `cxo-ds`:** `_bands()`
(`gallery_index.dart:90-104`) orders by `GalleryPurpose.values` (`gallery_entry.dart:59`), a
hand-authored enum. Verified myself: its declaration order and doc-comment text match
`_order.md`'s `### 1 ·` through `### 9 ·` numbered groups exactly, word for word in places — the
coupling is real but held together only by matching prose, not structure. Reordering either file
produces no error, no failing test, no visible symptom. Four framed options, none chosen (escalated
to `cxo-ds`, comment 11176 on `KAN-328`): (a) `_bands()` looks up each purpose's **position** in
the parsed `_order.md` order (fe-nav's refinement of my original (a) — shares only the ORDER, not
the object set, so it is NOT the merge D-047(e) withdrew); (b) amend AC3 to match what was built;
(c) leave both separate, fold an agreement-check into `KAN-332`'s containment script (needs the
CEO's approval of that gate existing); (d) do nothing, leave the comment as the only coupling.
Leaning (a)-as-fe-nav-framed if `cxo-ds` agrees it doesn't reopen the withdrawn merge — it makes
AC3 genuinely met rather than amended away, at the cost of touching committed, verified, working
code. `fe-nav` is holding, will not touch this without a ticket.

**Side nav rail, D-045/D-046/D-047, `KAN-331`:** `lib/src/gallery/gallery_index_rail.dart` already
existed (built under `KAN-328`'s implicit scope, never reflected in that ticket's ACs) with
now-superseded values (`_railWidth: 200`, `_sideNavBreakpoint: 900`) and a now-withdrawn data
source (`GalleryIndex._bands()`, 45 pages). Ruled: rail = **288**, breakpoint = **1000**, and the
rail must re-source from `_order.md` (58 pages) since it must reach the 13 specimen-less pages
`_bands()` cannot. `KAN-328` itself also has an unmet AC3 (`GalleryPurpose.values`' order is a
hand-authored second copy of `_order.md`'s order, not read from the file at runtime) — flagged on
that ticket directly, not folded into `KAN-331`.

**How to apply:** before scoping further Wave 3 work, re-check this list — most of it will be
stale within days. Check `cto-ds2` for the Axes-gate ruling before writing that ticket. Before
trusting any "N pages have no specimen" figure in this corpus, recompute it — my predecessor and I
both got it wrong once (12 vs the correct 13) before `cxo`/team-lead caught it.
