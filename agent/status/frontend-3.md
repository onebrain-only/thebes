# senior-frontend-3 — Horus

**Last updated:** 2026-09-06

## Current

Idle. KAN-125 (P0-4) landed at `dabbler-code` `da41d3b`. Phase 0 §10.6 landing test
passes on all four local figures; the Cloudflare `Canary` build is the one clause
not verified from here (no push under this brief).

## Recent

- **KAN-125 — `da41d3b`** (2026-09-06). Seven screens out of `lib/features/misc/presentation/screens/`:
  `game_composer_screen.dart` + the four composer steps → `features/games/presentation/screens/`;
  `activities_screen_v2.dart` → `features/activities/presentation/screens/`;
  `rewards_screen.dart` → `features/rewards/presentation/screens/` (both destination
  `screens/` dirs created — neither existed). File bodies unchanged: every import inside
  the seven was already an absolute `package:` path, so nothing inside them needed rewriting.
  Four route entries relocated `platform_routes.dart` → `play_places_routes.dart`
  (`/activities` + the three `GameComposerScreen` routes); `/rewards` stayed in
  `platform_routes.dart` per §10.3 rule 2. `app_router.dart` untouched — the module files
  are imported unprefixed, so a getter moving between them is invisible to the assembly.
  Residue is exactly the three ruled files. Golden green and byte-identical.

- **KAN-124 — `8e49b1d`** (2026-09-06). Router split. **Note: this was found staged but
  never committed.** HEAD was `93d6619`; the staged tree was complete, only the `git commit`
  was missing. I committed it verbatim as its own commit before starting KAN-125, so the two
  diffs stay separately reviewable — load-bearing, not tidiness: merged, the 17-file diff
  spans `lib/features/` and KAN-124 fails its own criterion 6 ("no `.dart` file outside
  `lib/app/` changed") on correct content.

  **Trace of the fabricated sha `c6d3e4f`, corrected.** It does not exist
  (`git cat-file -t` fails). Origin is `sf3-124`, which reported a commit it staged but never
  ran; `team-lead` relayed that sha upward without running `git cat-file`, and the relay fed
  my launching brief. **Not `team-lead-3`**, which I wrongly named first — it sent one message
  this session and cited the sha only to say it was invalid. Root cause is one failure, not
  two: an agent reporting the output of a command it never ran. General form, now in the
  lead's skill: when a report quotes a command's result, the question is not whether the
  result is plausible but whether the command was run.

  Figures for KAN-124 were re-measured in a clean detached worktree at `8e49b1d`, not from
  the KAN-125 working tree — a predecessor's criteria measured from a successor's tree
  attribute a green figure to the wrong commit. Worktree removed and pruned.
  Open item for the reviewer, unchanged: `AppRouter._rootNavigatorKey` was promoted to a
  public top-level `rootNavigatorKey` rather than create an eighth file outside the grant.

- **KAN-124 AC 8 — contiguous-run count: 25 at `8e49b1d`** (2026-09-06). >20, so T-056's flat
  getters is the justified shape; no `cto` escalation. **The count is per-commit, not a property
  of the route table** — it is **26 at `da41d3b`**, because KAN-125 moves four getters from
  `platform` to `play_places`. Both posted on KAN-124 together, deliberately.

  Two other seats (`team-lead-3`, `po`) independently reported 26 as a divergence from my 25;
  both had measured the working tree instead of the ticket's commit, so their agreement was the
  same error twice, not corroboration. Resolved by the run-start list itself: `createGameRoute`
  can only sit in `play_places` after KAN-125. No bucketing deviation existed; `rewardsRoute` is
  in `platform` at both commits, as §10.3 rule 2 requires.

  Method worth keeping: map identifiers to modules by parsing `^RouteBase\s+get\s+(\w+)\s*=>`
  across `lib/app/routes/*.dart`, then count maximal same-module spans — and **assert zero
  unresolved identifiers**. A missed identifier silently *shortens* a run, so the count fails
  low, which is the direction that falsely trips the ≤20 rework trigger.

## Standing

- Owns `auth_onboarding`, `username_engine`, `app_boot` under STACKS.md §11 (`team-lead-3`).
- Phase 0 exclusive grant (`CONTRACT.md` §4.1) expires with KAN-125 — subject to the lead
  confirming the Canary clause.

## KAN-142 — 2026-09-09

Claimed as current owner (revision 2), but found the defect already fixed on Canary by commit
`6c5bca4` (2026-09-06, "fix(nav): repoint dead /phone-input to /auth-welcome, drop dead /bookings
branch (KAN-142)"), predating this claim by three days. Verified against Canary HEAD (`715bb85`):
`grep -rn "/bookings\|phone-input" lib/` returns nothing; both sign-in buttons in
`transactions_screen.dart` and `activities_screen_v2.dart` already go to `RoutePaths.authWelcome`;
the `'booking'` case in `notifications_screen_v2.dart`'s `_handleActivityTap` is already removed.
`flutter analyze --no-pub --no-fatal-infos`: 0 errors, 0 warnings, 55 infos. `flutter test`: 106
passed. No files touched — nothing left to change. Posted findings as a Jira comment on KAN-142
and flagged the board/ownership drift (claimed as open work that was already closed) back to
team-lead rather than re-doing or fabricating a diff.

## 2026-09-09 — KAN-132 PEER review (cycle 1) — VERDICT: PASS

Reviewer, not executor. Executor was `frontend-2`. Reviewed dabbler-code Canary `b978647`, clean tree.

- Read KAN-132 and all 9 comments via `agent/integrations/jira.py`; read T-053 first-hand at `Dabbler/dabbler-docs/DECISIONS.md:7423`.
- Re-derived the unreachability proof myself: `supabase_profile_repository`, `SupabaseProfileRepository` and `data/repositories/profile_repository.dart` all return zero hits across `lib`/`test`; `lib/providers.dart` references neither; no barrel exports them. The 6 broad-grep hits are the unrelated live `lib/features/profile/domain/repositories/profile_repository.dart`.
- Verified delete-not-rename: `727448e` is two `D` entries, 92 deletions / 0 insertions; the class and its docstring exist nowhere in the tree; `profileRepositoryProvider` now has exactly one declaration (`lib/features/profile/presentation/providers/profile_providers.dart:73`).
- Gates re-run by me: `flutter analyze --no-pub --no-fatal-infos` -> 55 info, 0 warning, 0 error; `flutter test` -> 106/106 passed.
- Sequencing: `715bb85` (KAN-129) is the direct parent of `727448e` (KAN-132). AC 6 satisfied.
- SHA re-attribution checked directly: `c0d84d9` and `727448e` share tree `8d18aac`, `git diff` between them is empty. Content unchanged.
- AC 1 struck by `po` (comment 10638), not evaluated. No criterion required a database; nothing NOT VERIFIABLE.

No defect found, so PEER FAIL execution transfer does not apply. Wrote no product code, committed nothing, transitioned nothing — recording the verdict is the Orchestrator's act. Review posted as Jira comment **10836**.

## 2026-10-09 KAN-463 (Horus)
Composer sheets: vibes filtered per post kind (DabblerVibe.contexts = design, 119/119 match), place default (Use current location + empty Recent), game default (joined games via userUpcomingGamesProvider). Commit 82b85ce7f759658a40715d65debcb298fa05c53f on alpha-habu (not pushed). C1=0, C2=0 (composers), dependents=0. Open: current-location tap not wired (decision_required: no existing name source for device location); no recent-places read path.

## 2026-10-09 — KAN-469 (Create Post emoji + 162dp ComposerBox) — decision_required
Stopped at step 1 per brief STOP rule: sport rows need emoji but lib/core/widgets/sport_selection_sheet.dart (not in allowed paths) hard-wires DabblerSportIcon leading with no builder param. No code changed, no commit. Inventory: /Users/moataz/.claude/jobs/149908a7/tmp/kan469/inventory.md

## 2026-10-09 — KAN-462 Create Post emoji + 162dp ComposerBox (Horus)
- alpha-habu commit f38618a0514ba5bfddc2bc8559334dd2904127ad (not pushed). Emoji only via DabblerChip.emoji / DabblerBadge.emoji; minFieldHeight replaces minLines 7.
- C1 analyze exit 0 (0 err/0 warn); C2 composers 81 tests exit 0; l10n parity exit 0; importer tests exit 0.
- Emoji can't render in flutter test (Apple Color Emoji .ttc draws as boxes); screenshots in tmp/kan462/app show placeholders.
- Sport-sheet rows untouched (wait for KAN-478).

## 2026-10-09 KAN-478 (commit KAN-476:) Create Post sport-sheet emoji via DabblerInputRow.emoji on alpha-habu; C1/C2 exit 0; Create Game unchanged (73px rows base and after).

## 2026-10-09 KAN-472 Create Game frame (Horus)
Done on alpha-habu at 0a0d87cbfc6899982b392d70471de085fa9db5d7, not pushed. Meetup-parts frame plus GameComposerSheetPage (DabblerSheetRoute) for the 3 routes. The baseline payload is identical (base-commit run). C1 exit 0, whole analyze exit 0, C2 exit 1 only from 9 pre-existing game_venue_detail_render failures (same set as base). Gates and l10n tests exit 0. Evidence is in jobs/149908a7/tmp/kan472/.

## 2026-10-09 KAN-473 (Horus, team Habu)
Create Game sub-sheets (format, date, time, venue, skill) moved onto the design's sheet frame. Commit b0a7ad4dc4ee7058e1a6977db992f539ba8628a1 on alpha-habu, in worktree kan-456-habu. Not pushed. C1 exit 0. C2 exit 0 (584 passed). Gate tests exit 0. Evidence is in tmp/kan473. Luxor also logged a start on KAN-473 in Jira.

## 2026-10-10 — KAN-473 judge conditions (Horus)
Closed C1-C4 from the ux-engineer's PASS WITH CONDITIONS on b0a7ad4. Commit 4ec03c219a85358aed1ee1ba6e59ec911f038faf on alpha-habu (not pushed). Gaps now match the design (format 31/30, date/time 36, venue 24); venue header hairline dropped; header Clear tests added EN/AR. Open: foot-bottom gap (DS safe-area, device-only), time picker shape (DS ticket proposed), AR placeholder ellipsis (KAN-471).

## 2026-10-10 KAN-474 (Horus)
Wired KAN-471 keys into Create Game (sport tile semantic, duration chips, venue search/empty, create/save/load failure). New test game_composer_l10n_test.dart (13 pass). C1/C2 exit 0. Commit 37a2666465d537e26450eb18032fca2cbf9c126d on alpha-habu, not pushed. Notifier strings retained (KAN-477).

## 2026-10-11 KAN-492 app fix (Horus)
Composer sends area_id (venue area / resolved current-location area; key absent when unknown or no place); setRawLocation takes area/tag (ordering bug fixed); dead setLocationFromPickerResult removed; venue search fixed to real columns (name_en/area/area_id/lat/lng); feed + detail fall back to area name only when it resolves (postAreaNameProvider). Circle RPC still drops place fields (needs backend RPC params). Tests: composer_place_area_test (9), home_post_place_test (10 EN/AR). Worktree alpha-habu.

## 2026-10-13 KAN-500 (Horus)
message_preference save fix on alpha-habu, commit 56835da37a09bad8db10219bb463babcd09a8ba7 (not pushed). Red run: /Users/moataz/.claude/jobs/149908a7/tmp/kan500/red_run.txt. C1/C2 exit 0; C3 exit 1 on 2 existing infos in files this commit does not touch. Follow-up: gameInvitePreference bool? cast, privacy_controller.dart:181, and its anyone/none collapse in manage_privacy_usecase.dart:132-136.

## 2026-10-13 KAN-501 (game_invite_preference serialisation)
Committed fc4b0390dbab5371b91d3e04db71b20f45b94996 on alpha-habu (not pushed). Controller bool? cast + use-case bool collapse fixed; params carry CommunicationPreference. Red->green; C1/C2/C3 exit 0; full test 1870 pass.

## 2026-10-14 KAN-526 (Horus)
Manual Set location drawer on Games/Meetups/Venues/Home/ExploreScreen; persisted useManualPoint. Commit 99116b56d7a91266a2d02da9e52fc8edde817e8e on alpha-habu (not pushed). C1/C2/full test/analyze exit 0.

## 2026-10-14 — KAN-516 (Messaging T16a: game-chat thread + composer), team Habu
Built in worktree /Users/moataz/.claude/jobs/149908a7/wt/kan-456-habu (uncommitted). GameChatScreen (DS thread, pager, skeleton, composer, connection notice), thread mapping, flag-gated GameChatEntry on GameDetailScreen, controller loadOlder->bool + refreshNewest (polling), 17 ARB keys EN/AR. 27 new widget tests (5 states x LTR/RTL/200%) + entry gate tests; route test updated (placeholder -> screen). Gaps: no end_at/display name in Conversation/Message; AdaptiveScaffold absent (DabblerPage used); stale package_config fixed by pub get --offline.

## 2026-10-15 — KAN-550 (Messaging W1: real MessagingRepository), team Habu — STOPPED on contract/Worker mismatch
Read openapi.yaml, domain, fake, providers, controller, environment, cloudflare-build.sh, workers/messaging/src. No code written (worktree untouched). The Worker routes only GET/POST /v1/conversations/{id}/messages and POST /v1/messages/{id}/report; GET /games/{gameId}/conversation and PUT/DELETE /conversations/{id}/mute are absent (fall through to reasonError("not_found")). Per brief, raised ONE question instead of coding. Also noted: Worker sends 403 no-reason for messaging_off (brief already covers); msg_my_conversations is not in SupabaseConfig (out of allowed paths).

## 2026-10-15 — KAN-550 (Team Habu) real MessagingRepository
Built WorkerMessagingRepository (6 contract ops + listMyConversations over msg_my_conversations), MessagingHttpClient, UnavailableMessagingRepository, backend selection providers (fake / worker / unavailable), MESSAGING_API_BASE_URL env + build-script forwarding. Worktree kan-456-habu, uncommitted. messaging tests, analyze (0 err/0 warn) and full suite green.

## 2026-10-15 — KAN-562 (Messaging DMs F2), Team Habu worktree alpha-habu
- Built DM rows in the Messages list, MyConversation v2 fields, DmRepository (startDm/setMuted) in fake/worker/unavailable, dm_cap_reached as DmCapReachedFailure, 7 new l10n keys. Not committed.
- messaging tests exit 0 (493), l10n parity exit 0, analyze exit 0 (0 errors/warnings), full suite exit 0 (2750).
- Deviations: DmRepository sibling interface; dm_cap_reached not added to MessagingReason (contract pin); DS row has no photo slot (design gap); DM tap routes to game chat route until messagingThread exists.

## 2026-10-16 — KAN-552 (Team Habu) admin message Reports screen
Built in worktree /Users/moataz/.claude/jobs/149908a7/wt/kan-456-habu (alpha-habu), uncommitted. New ModerationReportsRepository sibling interface (list via msg_list_message_reports RPC, read via GET /v1/moderation/reports/{id}/message), NotAModeratorFailure (typed reason enum untouched), admin screen + panel (text held only in panel State, cleared on dispose), route /admin/message-reports with session/flags/is_admin redirect, one gated row on Safety Overview, 37 admin_message_reports_* l10n keys. Admin tests 609 green, full suite 2855 green, analyze 0 errors/0 warnings, parity green.

## 2026-10-19 KAN-572 (Habu) - game chat route without endAt
No lib change needed: route already maps non-DateTime extra to null; thread_items treats null endAt as not finished; read-only comes from the conversation status. Added test/features/messaging/presentation/game_chat_route_extra_test.dart (8 tests, EN+AR). messaging tests 0, analyze 0 (0 errors/warnings, 39 infos), full flutter test 0 (2996). Not committed.

## 2026-10-20 — KAN-596 (team Habu) bottom-drawer scrim slides with panel
Worktree kan-456-habu / alpha-habu @ a08947bc, uncommitted. Root cause DS sheet_route.dart:149-165 (route SlideTransition over a page that contains the scrim). Fix: lib/utils/transitions/app_sheet_route.dart (AppSheetRoute/showAppSheet drives DabblerSheet.open; no route slide; keyboard lifts the sheet), 62 call sites in 46 files routed through it; reduced motion added to BottomSheetTransitionPage/AdaptiveModalPage. New test test/utils/transitions/app_sheet_route_test.dart (11). analyze exit 0 (0 err/0 warn, 39 infos = baseline); flutter test exit 0, +3034. Not committed/pushed per brief.

## 2026-10-25 — KAN-589 round E (alpha-ramesseum, wt-639) five location defects
Commit 3acc0340 (base a689f41a), not pushed. Root causes found in the real browser (release build, 127.0.0.1:8595): (1) address search used Geocoding v6, which has no POIs, so it now uses the Search Box forward API; (3)+(4) on HEAD, saving any place failed with no write because profileControllerProvider is only loaded by the profile screens, so ProfileLocationNotifier now falls back to myProfileIdProvider. Duplicate block and delete (204) seen working. (2) drag/zoom and (5) manual location (home line, nearby, listings, survives logout/login) already worked on HEAD a689f41a; re-verified on the new build. The CEO's 8589 server was a stale round-C `flutter run` (PID 30223), now stopped. Tests: place_search_589e_test (3), save_place_profile_id_589e_test (3), both fail on the old code. analyze exit 0 (0 err/0 warn/43 infos); flutter test exit 0 (+4087). Shots in $CLAUDE_JOB_DIR/tmp/shots-589e/.

## 2026-11-02 — KAN-749 (frontend) — game view realtime on events/games
- Branch alpha-habu (worktree kan680), commit ea7a4638a5397e164c32cd20e50bd7343c4a42c0, not pushed.
- game_view_$gameId channel now also listens to events/games (id=eq.gameId) via existing debounce; single-channel guard; dispose/load inert after dispose; GameView.fromJson tolerates null end_at; SupabaseConfig.eventsTable added.
- Tests: test/features/games/game_view_realtime_test.dart 8/8 green; join-event regression 4/4; analyze 0 errors/0 warnings.
- Limitation: realtime publication of events/games not verified on prod; controller file is 784 lines (was 726, already over the 500 cap).

## 2026-11-04 — KAN-852 (Horus, dispatch cdispatch-afa2134a) — DONE on alpha-deir-el-bahari
- Bell → Activity log now merges rpc_get_activity_feed + the owner's public_activities (stable identity, dedupe, per-source paging); "All" chip restores the full list; error+Retry kept separate from empty; partial failure keeps the other source's rows.
- Owner Profile Activity tab and the All-sports → /activities entry removed; visitor Activity tab kept.
- Commit 0ba5f48d657404d2bbc7b7a9171e5f8d95d1895a pushed. analyze exit 0 (0 err/0 warn); full flutter test 4533 green. No new ARB keys.
- Gaps: RPC orders by time bucket but pages on happened_at (possible skipped rows, backend RPC change); mocks hand-written (build_runner stalled); notifications_screen_v2 still >500 lines (565→~521).

## 2026-11-04 — KAN-715 Events P3: Flutter games reads to event-backed projections (Horus)
- Worktree kan682-luxor, branch alpha-luxor, commit f2ca585f609106bb46e6c58f6e78373c44763858 (not pushed).
- Converted ACTIVE reads: G1 stream removed (no listeners), G3 getGames -> v_game_card, G7 -> v_my_games, G8 -> v_game_card, G14 sport-profile hosted -> v_game_card by creator_profile_id, G17 composer search -> v_game_card (sport:sport_key).
- GameModel.fromJson: invented fallbacks removed (title/sport/end/capacity); start/created/updated now() fallbacks kept (NOT NULL, unreachable).
- Named exception: G15 GDPR export (projection gap: description, cancelled_at, cancelled_reason, request_id, event_id, game_roster embed). UNREACHABLE sites left unchanged.
- D03 scan map + matrix 2a updated; stale design-gate allow entry for game_model removed.
- flutter test full: 4526 passed. flutter analyze: exit 0, 0 errors, 0 warnings, 44 infos.

## 2026-11-04 — KAN-865 (F10c, data export/retention games reads) — STOPPED, no commit
- Worktree kan784-deir-el-bahari @ 1fcadd3a, untouched. No diff, no push.
- Obstacle 1 (DELETE, data_retention_service.dart:317): no deletable events object on Alpha. public.events closed to API (kan710 20261101140000:98-102); kan718_games_compat is a read-only join view (d05 20261104110200:74-113, SELECT grants only :155-163); only events-aware delete is admin_cleanup_user_data (b13 20261104101300:180-215) = all games for the profile, no 2-year cutoff, plus posts/profiles — not identical.
- Obstacle 2 (reads :647, :1782): no `events`/`events_game` view exists. Only client-readable events-backed object is kan718_games_compat (authored-for-review, header says never applied; no SupabaseConfig constant and supabase_config.dart is forbidden; game_roster!inner embed through it not demonstrated, d05 header).
- Finding: games has no creator_id / participants columns (baseline 20260829080500:22863+); current :317 and :1782 filter on nonexistent columns, and games has RLS with zero policies (:32378), so authenticated callers get 0 rows today.

## 2026-11-04 — KAN-864 (Luxor, alpha-luxor 701f338d, not pushed)
- game_view_controller: dropped `gamesTable` realtime listener (game fields on events KAN-710; games writes route to events KAN-712). Test asserts new list + gamesTable absent.
- post_repository_impl / sport_profile_view_provider: already on vGameCardTable (KAN-715), covered by event_backed_game_reads_test; unchanged.
- Gap: public.events is NOT in supabase_realtime (KAN-716 header) and closed to API roles — the events listener delivers nothing today.
