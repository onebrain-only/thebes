# frontend-1 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/frontend-1.md`. This file is a work log, not a rule source.

Auth Welcome nodes 23 and 25 carrying `-google` / `-email` with their roles and names. Node totals
**14** and **19**, matching the unmodified baseline — proving no second node was created, which is
exactly what AC2 guards. Selector counts 1/1/1. KAN-166's `smoke.spec.ts` and `auth-welcome.spec.ts`
both pass, which is AC3's own wording.

Measurement spec was temporary and **deleted after capture** — evidence, not a deliverable, and AC3
asks that the *existing* scenarios keep passing rather than that a new one be added.

**Gates:** analyze 0 errors / 0 warnings / 55 infos; `flutter test` 111 passed.

**Reported honestly, not glossed:** the Apple call site is wired but `/continue with apple/i` = 0 on
web (`!kIsWeb && iOS` gate). Verified by construction, never claimed as measured. Same position I
took on KAN-165 and it has not changed.

**Handoff state:** Jira `QA-Test`; `observe_lifecycle` -> `release` (evidence `['frontend-1']`) ->
`open_review_context`, which resolved `review_owner: qa`, `review_result: pending`, cycle 1.
Evidence comment 10886. I did not pick the reviewer and did not record a verdict.

**Work Effort: 1 predicted, 1 actual.** The prediction was mine from Preflight and transcribed
rather than re-estimated; it held because the work was already measured.

**Observed, not mine to fix:** `docs/CONVENTIONS.md` and `docs/SCHEMA.md` are modified and unstaged
in this shared canonical checkout — another seat is working here concurrently. Both my commits today
used explicit pathspecs, so neither swept them up. Flagging because a seat committing with `-a` here
would silently ship another seat's in-progress work.

---

## 2026-09-11 — KAN-192 PREFLIGHT (assessment only; no claim, no execution)

Asked for Work Effort, Surfaces, and an AC-by-AC confirmation on KAN-192 (`squad.dart` nullable
owner fields, T-077 Am.3, frontend child of KAN-176). Burn-down mode: bounded, no ticket creation.

**Work Effort: 1 sitting.** Two words changed on two lines, then `build_runner`, one decode test,
`analyze` + `test`. I would have said 2 if the call-site audit had found dereferences needing
fallback copy — it found none, so 1 is the honest number rather than a padded one.

**Surfaces assessed (a real answer, not `null`):** `squad.dart`, its two regenerated companions
`squad.freezed.dart` / `squad.g.dart`, and a new `test/data/models/squad_test.dart` for AC2. All
under `Dabbler/dabbler-code/` — **the brief's path `lib/data/models/squad.dart` does not resolve
from the workspace root**; the app is not at the root. Lines 14-15 were correct within the real file.

**Contention flagged, not glossed:** `build_runner build -d` regenerates `*.freezed.dart`/`*.g.dart`
repo-wide, so surfaces 2 and 3 are shared for the duration of the build. `lib/` is clean right now
(only `docs/` and one migration modified), so no live collision — but the window must not overlap
another seat's model edit.

**AC3 answered at Preflight rather than deferred:** the call-site enumeration is the **empty set**.
No `Squad` instance's `ownerProfileId`/`ownerUserId` is dereferenced anywhere in `lib/` or `test/`;
`Squad` is never built by its constructor, only via `fromJson`; and no UI renders a squad owner, so
AC3's "empty owner name/avatar with no fallback copy" failure mode has no surface to occur on.
`squads_repository_impl.dart:281` already casts `as String?` and needs no change. Doing this audit
before claiming is what made the sizing defensible instead of a guess.

**AC5 flagged as not self-satisfiable.** It requires a statement recorded *in the Jira ticket*, and
I do not create or edit tickets. I supplied the substance — KAN-191 is `To Do` and unstarted, so
KAN-192 shipping in this burn-down ships **BEFORE** the migration, the safe order — and said plainly
that someone with ticket-write authority must land it. Reported 4 of 5 satisfiable rather than
claiming 5 and quietly leaving one unmet.

**Lifecycle fact surfaced, determination left to the claimer:** KAN-192 is in `To Do` (10004), not
`Ready`. My transition is `Ready -> Front-end`, and Ready-eligibility gates the claim. Parent
KAN-127, sibling KAN-191 and split parent KAN-176 are all `To Do` too. Blocks direction confirmed in
Jira and consistent with `dep-6dcbdbfa`: KAN-192 blocks KAN-191. I did not route around it.

**No claim taken, nothing executed, no Jira object created or edited.**

## 2026-09-11 — KAN-192 EXECUTED (claimed, owned, all ACs met except AC5 which is po's)

Claimed by team-lead (`burn-down-2026-09-11`), continuation gate passed, work_effort 1. Executed
exactly the preflighted plan — no scope drift, no adjacent audit.

**The change:** `squad.dart` `ownerProfileId`/`ownerUserId` `required String` -> `String?`.

**AC1 — generated code, not the source annotation.** The regenerated diff is the whole proof:
`squad.g.dart` went `as String` -> `as String?` on both fields; `squad.freezed.dart` now declares
`String? get ownerProfileId` / `String? get ownerUserId`. The old `as String` is *literally* the
line that threw `type 'Null' is not a subtype of type 'String'` — so the diff documents the crash
mode and its fix in the same two lines.

**AC2 — demonstrated by decode, not inspection.** New `test/data/models/squad_test.dart`, 5 tests:
both owners null, each one null alone, a fully-populated row still decoding unchanged (guarding
against over-relaxation, since every production row is non-null today), and a round-trip proving a
nulled owner serializes back to `null` rather than to a placeholder string.

**AC3 — enumeration is the empty set, and I re-verified it after the change rather than resting on
the preflight.** Zero production dereferences of either field on a `Squad` instance anywhere in
`lib/`. The only `.ownerProfileId`/`.ownerUserId` hits post-change are my own test assertions plus
`UserCircle`/`Benefit`, which are different models on CASCADE-group tables the ticket explicitly
says not to "fix". `Squad` is only ever constructed via `fromJson`, so dropping `required` broke no
construction site; no UI renders a squad owner, so AC3's "empty owner name/avatar with no fallback
copy" failure has no surface to occur on. `squads_repository_impl.dart:281` already cast
`as String?` and was left alone. I did not report this as "it compiles" — the AC rejects that.

**AC4 — gates green.** `flutter analyze --no-pub --no-fatal-infos`: **0 errors, 0 warnings**, 55
infos, exit 0. `flutter test`: **116 passed** (111 baseline + my 5), all passed.

**AC5 — not mine, said so rather than quietly skipping it.** It needs the before/with-KAN-191
sentence recorded *in the Jira ticket*, and I do not create or edit tickets. Substance supplied to
team-lead for po to land: KAN-191 is `To Do` and unstarted, so this ships **BEFORE** its migration —
the safe order, and the one thing the ticket exists to guarantee.

**Shared-surface window closed clean.** `build_runner build -d` wrote 80 outputs repo-wide but only
my two generated files differ from HEAD — the other 78 were byte-identical rewrites, so no other
seat's work was churned. Confirmed by `git status`, not assumed.

**Observed, not mine:** `docs/SCHEMA.md` and the KAN-130/131 migration were committed by another
seat between my preflight and execution, and an untracked KAN-168 migration appeared during it.
Concurrent activity in the shared checkout; I touched none of it and used no `-a` commit.

**Lifecycle deliberately NOT touched.** My contract gives me `Front-end` -> computed review status,
but team-lead said "do not release; I'll handle lifecycle." I flagged the tension rather than
transitioning unilaterally, so the transition does not silently go unmade. Working tree left
uncommitted — commits/pushes are devops'. **Work Effort: 1 predicted, 1 actual.**

### 2026-09-11 — KAN-192 lifecycle: BOTH transitions taken (the missed start one included)

team-lead handed me the transition and asked for `Front-end` -> `Peer-review`. **Read the board
live first (G-018) and the premise was false: KAN-192 was in `Ready` (10008), never `Front-end`.**
Someone moved it To Do -> Ready after my preflight; I had skipped my own `Ready` -> `Front-end`
start transition earlier because team-lead had said it would handle lifecycle.

Jumping straight Ready -> Peer-review was available (every transition on this board is
`isGlobal: true`), but it would have left a board history saying the development step never
happened. Both transitions are mine under the contract, so I made the missed one first:

* **transition `8`** -> `Front-end` (10046)
* **transition `7`** -> `Peer-review` (10045)  ← final state

**G-018 held again, and is worth restating:** transition ids are NOT status ids. Peer-review is
status **10045** but transition **7**; Front-end is status **10046** but transition **8**. Read back
live, never inferred.

Route was PEER (`shared_or_contended_surface: true`, from the two Freezed-generated files) —
**computed by system policy and handed to me; I did not choose it and did not pick the reviewer.**
`assignee` remains null, correct for this board where assignee is not execution authority.

**Ownership NOT released** — team-lead handles that after review.

## 2026-10-06 — Action Area commits 2, 3, 4 (CEO order, worktree integ-app, branch alpha-k437)
- 1181a7a1 commit 2: ShellActionAreaHost over DabblerNavigationStatus; DS lock -> 6df77e0.
- 0dbef267 commit 3: join game / RSVP retry / check-in on FeedbackCenter.
- 30834db7 commit 4: ShellAwareToastController bridge (shell toasts -> Action Area; absent -> standard toast).
- Checks: analyze exit 0 (0 errors/0 warnings, 38 infos); flutter test 1179 passed; gates 74 passed. Not pushed.

## 2026-11-04 — KAN-863 (KAN-708 F10a) games reads -> events-backed projection — HELD, not committed
- Worktree kan714-karnak, branch alpha-karnak @ 8d4c7443. All 13 `.from(SupabaseConfig.gamesTable)` reads now `.from(_gamesReadView)` = private const 'kan718_games_compat' (KAN-773 view, 20261104110200_kan718_d05...sql:74-112, grants :156-166). No signature/model change.
- New test test/features/games/data/datasources/supabase_games_datasource_test.dart: 9/9 pass. analyze exit 0 (0 err / 0 warn).
- Full suite: 4540 pass, 2 FAIL — test/features/games/data/supabase_games_datasource_write_test.dart (fakes '/rest/v1/games' at :48; outside allowed paths). Passes at HEAD. Did not commit or push a red suite; question returned to caller.
- 2026-11-04 KAN-863 RESUMED (dreq-60e59915 YES): write_test.dart:47 fake path -> '/rest/v1/kan718_games_compat' (one line). C1 0; analyze exit 0 (0 err/0 warn); new test 9/9; full suite `03:51 +4542: All tests passed!`. Commit c30a6644 pushed to origin/alpha-karnak (8d4c7443..c30a6644). Status clean.

## 2026-11-04 — KAN-874 (KAN-873 split 1/6) activity log search contract
- Commit 89ee124206db3c7dd24acdb28c55094019498337 on alpha-deir-el-bahari (not pushed).
- searchActivityLog in activity_log_merge.dart; ActivityLogState.query + changeQuery; filteredActivities = category then search; stats read state.activities (full list), unchanged.
- C1 analyze exit 0, 0 errors/warnings (45 infos). C2 flutter test test/features/activities: +41 All tests passed.

## 2026-11-04 — KAN-875 (search keeps paging older) — committed, not pushed
- Commit 31b7c1cdfd81294f0559b73c2235a24393e811dd on alpha-deir-el-bahari (worktree kan784-deir-el-bahari).
- _searchOlder() loop over loadMore(), cap 20 pages/run, generation-token cancellation; isSearchingOlder on ActivityLogState.
- New test/features/activities/activity_log_search_paging_test.dart (hand-written fakes, 12 tests). C1 exit 0, C2 exit 0 (53 tests).
- Known edge: if a loadMore() not started by the loop (e.g. scroll) is in flight when a loop starts, the loop ends at once.

## 2026-11-04 — KAN-877 (split 4/6 of KAN-873) — STOPPED at caller break, not committed
- Wrote ActivitySearchRow as StatefulWidget(query, onChanged, onClear) over an enabled, clearable, full-width DabblerSearchField; filter button removed. 5 widget tests (TC1–TC5) pass.
- Brief's stop condition hit: `const ActivitySearchRow()` at lib/features/notifications/presentation/screens/notifications_screen_v2.dart:198 fails with 3 missing_required_argument errors; analyze exit 1; notifications suite exit 1 (compile failure). Screen is forbidden (KAN-879). Changes left uncommitted in worktree kan784-deir-el-bahari.
- Design not read: DesignSync tool not available in this session.

## 2026-11-04 — KAN-877 continuation (CTO ruling dreq-cf4ae682 opt 1)
- ActivitySearchRow ctor now `const`, `query` default '', `onChanged`/`onClear` nullable, invoked via `?.call`; didUpdateWidget sync kept.
- Added TC6 (`const ActivitySearchRow()` no-callback type/clear do not throw).
- analyze exit 0 (0 errors/warnings, 45 infos); notifications suite +72 pass; activity_search_row_test +6 pass. Uncommitted in worktree kan784-deir-el-bahari; orchestrator commits.

## 2026-11-04 — KAN-865 (F10c) — STOPPED, question returned, no code changed
- Site export:647 (`_getEnhancedGameHistoryData`) reads games the user is ON THE ROSTER of (`game_roster!inner`, `eq game_roster.user_id`), all `games.*` columns plus embedded roster `user_id, joined_at, status, role`. `export_own_events()` (kan865 migration :112-163) returns only events the user CREATED (`creator_user_id = auth.uid()`, :161) and 12 fields; joined-but-not-created games and `joined_at`/`role` are absent. No Alpha target returns that row set + fields (v_my_games has created-OR-roster rows but no joined_at/role and not games.*). Brief STOP rule applied.
- Side finding: sites export:1782 and retention:317 filter on `creator_id` / `participants`, neither of which exists on public.games (baseline :22863) — both reads already fail at PostgREST today.
- Worktree untouched; git status clean for allowed paths.

## 2026-11-04 — KAN-865 (F10c) — continuation under CTO ruling dreq-5087907b — partial, local, NOT landed
- Retention `_cleanupGameHistory` -> `retention_cleanup_own_events(p_cutoff = now-2y UTC)`, RPC int returned, catch -> 0 (static seam `cleanupOwnEventsVia`).
- Export `_getEnhancedGameHistoryData` + `_gatherAllUserData` -> literal `'export_own_game_history'` (pending backend migration). Rows mapped back to the old key set: `my_roster` -> `game_roster` (1-row list or []), `event_type` stripped, data_source text unchanged.
- Test: test/features/profile/kan865_retention_export_events_test.dart, 7/7 green. analyze exit 0, 0 errors/0 warnings. gamesTable count 0 in both files. Uncommitted; orchestrator handles git.

## 2026-11-04 — KAN-878 (sres-6845656a) Activity log no-match + searching-older
- Worktree kan878-deir-el-bahari. New ActivityNoMatchState + ActivitySearchingOlder; buildActivityLogSlivers branches on query/isSearchingOlder/hasMore and skips the Load-more tail on a searched miss.
- Tests: activity_no_match_state_test.dart 8/8; analyze 0 errors 0 warnings; l10n parity + notifications/ 90 pass. Not committed (orchestrator commits). Design not readable (no DesignSync tool).

## 2026-11-05 — KAN-852 QA-Test evidence gap (sres-6a8eb175 / cdispatch-dd852163)
- Added test 'empty only after a successful fetch: not before, not while loading' to test/features/activities/activity_log_controller_test.dart (:222) in worktree kan784-deir-el-bahari; commit c5bfa851637fe0239a5768987a3cea51f3b33fd1, not pushed. Controller untouched; no defect found.
- File run: +9 all passed. Full run: +4621 -1. The one failure (active_write_paths_test manifest) is caused by the uncommitted KAN-865 edit to data_retention_service.dart, which removes a games write. Not touched.

## 2026-11-05 — KAN-873 Activity log search wiring (sres-6e6f8e00 / cdispatch-59c6cb87)
- Wired `ActivitySearchRow` in `notifications_screen_v2.dart` to `ActivityLogController.changeQuery` (query, onChanged, onClear -> changeQuery('')).
- New test `test/features/notifications/activity_search_wiring_test.dart` (4 widget tests). Controller: no defect (changeCategory keeps query; changeQuery keeps category).
- analyze exit 0 (0 errors/warnings); focused tests +138 green; full suite +4621 green.
- Commit 6bcd42b38a05375dd9605a45a7b4ad154db6e963 on staging-deir-el-bahari, not pushed.

## 2026-11-06 — KAN-865 (F10c) export/retention off games
- Commit bc6b6d0475ef3b25c17e3eb8ab9a16b1a0604e6e on staging-deir-el-bahari (not pushed). Export + legacy export via export_own_game_history; retention via retention_cleanup_own_events. Manifest test entry removed.
- Flags: RPC name export_own_game_history held as a private const (no SupabaseConfig constant, file out of scope); KAN715_ACTIVE_CALL_SITES.md D4 row now stale (supabase/ out of scope); old legacy-export and retention queries used non-existent games columns (creator_id, participants) so they always failed. Retention now really deletes.
