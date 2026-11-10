# backend-3 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-3.md`. This file is a work log, not a rule source.

  `game_ended` vs `game_cancelled` (409) on send, and Worker must not compute lifecycle. Asked caller which source decides.

## 2026-10-15 KAN-546 (Habu worktree)
CORS +https://app.dabbler.pro; wrangler env staging->production (name/db unchanged); README production + keep_vars doc (not added to toml, docs ambiguous for var also in committed vars); tests 242/242. Not committed.

## 2026-10-17 KAN-558 fix 1 (left_at_seq on meetup cancel) - STOPPED, no edits
Seq lives only in D1 (conversation_seq); no Postgres source. Game path has no writer either (registry comment says Worker/service_role writes it; workers/messaging/src has no such write). Reported options to caller.

## 2026-10-19 KAN-572 (server half)
Root cause: msg_notify only Realtime, no notifications row/push for chat. Authored (not applied) 20261019120000_kan572_msg_push.sql + probes/rollback + static test. npm/flutter test/analyze exit 0. Needs PEER backend review + ops apply.

## 2026-10-20 KAN-595 backend half (Active stream RPC)
Authored (not applied, not committed) public.active_stream read RPC in worktree kan-456-habu: migration 20261020120000_kan595_active_stream.sql, supabase/tests/active_stream/{probes,rollback}.sql + README, test/supabase/active_stream_migration_test.dart; one-line cut-off fix in messaging_registry_migration_test.dart. flutter test test/supabase exit 0 (388), analyze exit 0. Flags: is_profile_publicly_visible hides profiles with no user_status row; no transition timestamps (scheduled times used). Route PEER, waits for a backend reviewer.

## 2026-10-20 — KAN-611 (team Habu) idempotent creates — DECISION_REQUIRED, nothing written
None of create_post (20261013125000), rpc_create_game (20261008140000) or rpc_create_meetup (latest def, RENAME-to-legacy at line 447 of its migration) takes a params jsonb object; request_id needs a new parameter on all three => new signature. Per brief (b), stopped and asked one question. No files authored in worktree alpha-habu.

## 2026-10-27 — KAN-646 Personas S3 (capability + actor compatibility) — authored, NOT applied
Commit 2c860d22 on alpha-646-ramesseum (wt-646, from c80d6ca8), not pushed. Migration 20261026120000_kan646_personas_s3_capabilities.sql patches choose_actor, actor_is_player, actor_is_organiser, can_create_meetup, rpc_create_game_legacy_v2 gate, rpc_create_sport_profile from live pg_get_functiondef (drift + ACL asserts); new actor_is_host(uuid) authenticated/service_role only. Probes/rollback/README under supabase/tests/kan646_personas_s3, matrix docs/personas/kan646_operation_matrix.md. sql_hook: probes allow in ops lane; migration/rollback null (need maintenance release). Nothing executed on DB except catalogue reads; probes never run. Blockers B1 (squads broken live, missing helper fns), B3 (partner social block); findings F1, F2. Needs-ops: apply migration. AC7: re-run G/J against real S2 before KAN-649. Route PEER, waits for a backend reviewer.

## 2026-11-02 — KAN-713 Events P2 (access policies + location rules on events) — authored, NOT applied, NOT committed
Worktree kan682-luxor (alpha-luxor @791d6376). New: migrations 20261104100000_kan713_access_helpers.sql, 20261104110000_kan713_location_triggers.sql; supabase/tests/events_p2_kan713/{local_harness,matrix,fingerprint,probes,recursion,rollback}_kan713.sql + KAN713_CONTRACT.md. Local PG16 only (stopped). probes old 12/16 (all 16 K fail-first), new 28/0, fresh build 28/0; probes_kan712 55/0; recursion 6/0; matrix 1955 cells diff empty; rollback fingerprint pre=rolledback, data hashes equal across 3 states; rollback order 713 before 712 proven. Migration 2 gate split after first runs, re-verified on fresh build. Named exceptions E-1 (rpc_booking_hold_for_meetup m.owner_user_id 42703), E-2 (game_invites.to_profile_id 42703), both pre-existing, not fixed. Route PEER, waits for a backend reviewer; ops apply.

## 2026-11-02 — KAN-714 Events P2 (parent reads) — authored, NOT applied, NOT committed, PARTIAL scope
Worktree kan682-luxor (alpha-luxor @aaa3898e). New: migration 20261105100000_kan714_events_parent_reads.sql; supabase/tests/events_p2_kan714/{local_harness,snapshot,fingerprint,corrupt_legacy,adversarial,explain,rollback}_kan714.sql + KAN714_CONTRACT.md. Local PG16 only (stopped). Repointed 11 readers (6 views, 5 DEFINER fns) to events; snapshot parity diff empty (275 lines, ERR 35 both); provenance pre 187 lines differ / post 1 (E3 _can_view_game intersection); adversarial pre 10/14, post 24/0; 712 55/0, 713 28/0, recursion 6/0, matrix 1955 diff empty, pre and post; rollback fp+data+snapshot diffs empty; guard refused x3 + re-apply refused. NOT covered: 73 of 102 manifest readers not repointed (nearby/search/join/rating/booking/settlement/msg/feed/admin), 55 of 102 absent from local harness. Exceptions E1 rpc_meetup_my 42703, E2 search_tsv KAN-718, E3, E4 INVOKER readers (cto shape call), E5 tie-breaks, E6 v_game_rating. Route PEER, waits for a backend reviewer. Work was larger than one dispatch.

## 2026-11-02 — KAN-714 continuation on alpha-karnak — BLOCKED (worktree not writable by file tools)
Worktree /Users/moataz/.claude/jobs/1ee27200/worktrees/karnak-final-app @2ff529e09a55c1750e4d05f802d32ac251c48aa2. Done: recovered Luxor build recipe; copied 5 round-2 harness files (local_harness_kan714_2_{stubs,objects,exec_adds,exec_sync,exec_post}.sql) into supabase/tests/events_p2_kan714/ (uncommitted, no remote host refs). Blocked: Write tool refuses every path under ~/.claude/jobs ("Claude Code restarts background sessions from the files there, so they cannot be written directly"); not bypassed via shell. Not done: build script, rebuild on current migrations (KAN-716, KAN-718 D07), rollback part 2, fingerprint preimage_2, contract sections 9-12 + 102-row manifest, re-verification suite, commit. Needs: worktree relocated outside ~/.claude/jobs or explicit authorisation to write there. Local cluster /tmp/kan714_pg:54714 still running.

## 2026-11-02 — KAN-720 (KAN-714 B01) v_game_card + v_my_games read events — authored, NOT applied, committed 7d9be26c, pushed alpha-luxor
Files: supabase/migrations/20261104100100_kan714_b01_views_game_card_my_games.sql, supabase/tests/events_p2/kan714_b01_game_views.sql. Local PG16 throwaway (stopped): T0, A, B, C (+ probe proven failing on old defs), D (9 viewers as anon/authenticated), E, F all PASS, ALL PASS. Rollback copy identical to migration block; rollback restores exact pre-image viewdef md5. security_invoker guard proven to refuse. No grant/policy/RPC/DROP/data change. Limitations: test fixture is the untracked events_p2_kan714/local_harness_kan714.sql (not mine); file sorts before KAN-713 location triggers 20261104110000 so guard requires only access helpers; PostGIS stubbed locally; live catalogue not checked. Route PEER, waits for a backend reviewer.

## 2026-11-02 — KAN-721 (KAN-714 B02) v_meetup_list + v_meetup_counts read events — authored, NOT applied, committed 62efd916, pushed alpha-luxor
Files: supabase/migrations/20261104100200_kan714_b02_views_meetup_list_counts.sql, supabase/tests/events_p2/kan714_b02_meetup_views.sql. Local PG16 throwaway (stopped): negative T0 fail before migration; T0, A, B, C (+ probe proven failing on old defs), D (9 viewers, anon/authenticated), E, F all PASS, ALL PASS. Rollback restores the pre-image viewdef md5s exactly (list f467247f…, counts 068d2f9d…, opts {security_invoker=off}). New guards proven to refuse: security_invoker on a view; one meetup that disagrees with its events parent. rsvp_policy <- events.join_policy, skill ::integer, ORDER BY unchanged (no tie-break). No grant/policy/RPC/DROP/data change. Not mine and not touched: untracked 20261105* and events_p2_kan714/ (used as the fixture). Live catalogue not read. Route PEER; waits for a backend reviewer.

## 2026-11-02 — KAN-726 (KAN-714 B07) rpc_sport_overview counts + v_host_weekly_metrics read events — authored, NOT applied, committed be5dcaf0, pushed alpha-luxor
Files: supabase/migrations/20261104100700_kan714_b07_sport_overview_counts.sql, supabase/tests/events_p2/kan714_b07_sport_overview.sql. Local PG16 throwaway (stopped): negative T0 fails before migration; T0, A, B (96 calls/phase identical, exact e2 values), C (16 probes follow events on new, all fail on old), D, E (rollback md5 functiondef eef53819… / prosrc 1ba64439… / viewdef 2be17f30… = pre-image; re-apply round-trips), F all PASS, KAN-726 ALL PASS. rpc_sport_overview has no count helpers (all counts inline); not KAN-712-wrapped, so CREATE OR REPLACE is used and guarded. Profile game-count reader converted: v_host_weekly_metrics (dependents v_top_hosts_week, award_top_host_weekly follow). Client profile counts come from B01/B02 views; stored counters and admin_overview_row left out of scope. No grant/policy/DROP/data change. Live catalogue not read. Route PEER; waits for a backend reviewer.

## 2026-11-02 — KAN-720 C2 fix (dispatch cdispatch-c3276b2b)
Committed supabase/tests/events_p2_kan714/local_harness_kan714.sql (md5 5654644e8b73fec42771c2eded80aaf6 verified) on alpha-luxor as db36a6b44e3b943f2adc52189ee92887b3442dcf; pushed be5dcaf0..db36a6b4. Only that file staged; other untracked files and migrations 20261105100000/110000 left untouched. No DB touched.

## 2026-11-02 — KAN-729 (KAN-714 B10) settle_game reads shared facts from public.events — Shed (backend-3), Team Luxor

- Dispatch cdispatch-8e7fdcf0-66b3-42dc-92f0-60b824566838. Branch alpha-luxor, commit 4af89787afa565d1965f16efbc882119eadba78c, pushed (db36a6b4..4af89787).
- Files: supabase/migrations/20261104101000_kan714_b10_settle_game_reads.sql, supabase/tests/events_p2/kan714_b10_settle_game.sql.
- Change: organiser/sport derivation only — games JOIN events (e.id = g.event_id AND e.event_type='game'), e.creator_user_id + e.sport_id (migration :160-171; legacy 20260911114500:56-60). Writes, ledger keys, ON CONFLICT, zero/negative branches, signature, owner, ACL, SECDEF, search_path unchanged and asserted.
- settle_game is NOT KAN-712-wrapped (20261103110000_kan712_cutover.sql:102-112 list of 11; guard refuses if wrapped).
- Proof: clean git-archive export on local throwaway PG16 only; 3 negatives refused; T0, A-H, G PASS; KAN-729 ALL PASS. No Supabase/production touched.
- Conflict flagged: untracked 20261105110000_kan714_events_parent_reads_2.sql (other ticket) also rewrites settle_game from md5 9357b0e9; whichever applies second fails its drift guard.
- Route PEER: needs another backend-N reviewer; waits in Peer-review if none.

## 2026-11-02 — KAN-714 whole-ticket continuation — STOPPED: superseded on branch
Worktree Dabbler/worktrees/kan714-karnak (alpha-karnak). Built a fresh local chain incl. KAN-716 (publication stub) + KAN-718 D07 from 2ff529e0's files (build_local_kan714.sh): parts 1+2 applied with pins unchanged (D07 adds 1 fn only); 712 55/0, 713 28/0, recursion 6/0, matrix diff empty, snapshot n713b==n714b==n714c (293 lines, ERR 36 each), adversarial pre 10/14 post 24/0; exec parity equal per-table on fresh clones (earlier 5-case state diff = sequence drift across repeated runs). Then found HEAD moved to 81881d46: e7616a25 "KAN-722: revert 2ff529e0 (whole-KAN-714 import withdrawn; pieces arrive via KAN-720..735)", Orchestrator ruling dreq-29766e44; another session has B03/B04/B06/B09 committed and B11 untracked in that worktree. Stopped: no commit, no rollback/contract work (target files withdrawn). Moved my untracked build script + 5 harness files to /tmp/k714w/kept/ so they cannot enter the piece session's commits. Route PEER n/a — nothing to review.

## 2026-11-03 — KAN-732 (KAN-714 B13 analytics/admin/export/cleanup) — DONE, pushed, awaits PEER (backend-N)
Worktree kan682-luxor, branch alpha-luxor, commit 0e62436c2f8b881deab1efa0abf27657ec99ddb7 (pushed fb1ba279..0e62436c). Files: supabase/migrations/20261104101300_kan714_b13_analytics_admin_export_cleanup.sql, supabase/tests/events_p2/kan714_b13_analytics_export.sql. Converted 2: admin_cleanup_user_data (games DELETE by events.creator_profile_id via USING events) and admin_overview_row (games_week by events.created_at). Neither KAN-712-wrapped. Everything else in the family: not shared-column, B07-owned, or out of family (seed-bot get_open_games_for_seeding / get_games_needing_players read shared columns, left). Clean proof from git archive: 4 negatives refused, T0/A/B/C/D/E/F PASS, KAN-732 ALL PASS. Live catalogue NOT read (ops guard refused execute_sql) so guards are repo-derived. Findings: content_reports is created by no tracked migration (admin_overview_row would 42P01 on a repo-built DB; test fixture supplies it); dry-run ROW_COUNT carry-over and L-2 23503 preserved; untracked drafts 20261105100000/110000 also redefine both functions (conflict). Route PEER; not applied anywhere.

## 2026-11-03 — KAN-735 (KAN-714 B16) perf/N+1/duplicates/equal-start_at pagination — DONE (executor)
- Commits on alpha-luxor (worktree kan682-luxor): 3bb3bcf8 (test + report), e6e3ff03 (report timing spread). Not pushed.
- Files: supabase/tests/events_p2/kan714_b16_perf_pagination.sql, supabase/tests/events_p2/KAN714_PERF_REPORT.md.
- Proof: bash /Users/moataz/.claude/jobs/dcb6a775/tmp/clean735.sh e6e3ff03cb42162c2dbac2521d8877286dd756ad -> KAN-735 ALL PASS (local PG16 only).
- Baseline: no E1 artifact exists; baseline = pre-B01/B02/B04/B05 harness chain + verbatim nearby pre-image (md5 e14430ba...).
- No B-migration defect. Findings to route: app v_meetup_list OFFSET paging lacks id tie-break (frontend); nearby RPC lacks id tie-break (backend, new ticket via po).
- Needs PEER review by another backend-N.

## 2026-11-03 — KAN-734 (KAN-714 B15) read-coverage manifest — committed, clean proof ALL PASS
- Commit 1415fa3cc82e11b80bfd1b561608480108247c9c on alpha-luxor (worktree kan682-luxor). Not pushed or merged.
- Files: supabase/tests/events_p2/KAN714_READ_MANIFEST.md and supabase/tests/events_p2/kan714_b15_coverage_probe.sql. No migration.
- Matrix: 161 functions (32 converted / 95 unchanged / 34 open); 8 views (6/2/0); 21 FKs (all unchanged).
- 141 reconciliation: at the audit cut the repo gives 136 (name|body), so 5 are not documented. Views match the audit at 7. The repo has 21 FKs against an audited 20; the +1 is not documented.
- Clean proof (`clean734.sh <sha>`, archive of tracked files only, 0 untracked 20261105 files): D PASS; NEGATIVE 1/2/3 fail as designed; C1-C13 and S1-S5 PASS; "KAN-734 ALL PASS".
- Open: 34 functions. 17 of them overlap with the untracked 20261105* files, which I did not touch. There are 26 residual legacy references (phase-4 blockers), plus the KAN-711 whole-row functions. Route: PEER (another backend-N).

## 2026-11-03 — KAN-769 (KAN-718 D01) SQL consumer re-scan — DONE (evidence only)
- Branch alpha-luxor, worktree Dabbler/worktrees/kan682-luxor, commit 334795d3 (not pushed; Luxor pushes and merges).
- Files: supabase/tests/events_p4/kan718_d01_sql_consumer_scan.sql and KAN718_D01_SQL_CONSUMERS.md.
- Clean run: clean769.sh 334795d3 exited 0 and ended "KAN-769 ALL PASS". NEGATIVE 0 fails as expected before
  the B migrations.
- Verdict: all 40 slated pairs (21 games + 19 meetups, from the B15 shared set; no exact slated list exists)
  are PENDING. Deletion is blocked by:
  - the KAN-716 publication column list (dependency type n);
  - the KAN-711 and KAN-712 mirrors (KAN-713 intersection rule);
  - the B15 open rows, which have no ticket;
  - old builds that use PostgREST and realtime.
- Not run on production (forbidden). Edge, Dart and realtime clients were not scanned.
- No Jira transitions. No migration.

## 2026-11-03 — KAN-785 retire rpc_meetup_my() (Shed)
- Commit 9cea2d89 on alpha-luxor (worktree kan682-luxor): migration 20261104110400_kan785_retire_rpc_meetup_my.sql + supabase/tests/kan785_rpc_meetup_my.sql. Not pushed, not applied, Jira untouched.
- Retired (no caller in lib/, supabase/functions/, test/). Not KAN-712-wrapped. Guarded DROP (wrap check + md5 drift pin 9459dd31…), no CASCADE.
- clean785.sh 9cea2d89 exit 0, KAN-785 ALL PASS; flutter analyze exit 0 (45 infos, 0 errors/warnings).
- Pinned evidence (KAN-734 manifest row 73, B15 probe, B06 test R1/D4, KAN-718 D01 scan) names the function and is not edited; it will report it absent post-migration.

## 2026-11-03 — KAN-786 meetup leave raises P0001 'already' (Luxor dispatch cdispatch-a9aecf57, sres-148522e3)
- Commit b70525761b1575bb768feb0abace1403abb108df on alpha-luxor (worktree kan682-luxor, not pushed): migration 20261104110500_kan786_meetup_leave.sql + supabase/tests/events_p3/kan786_meetup_leave.sql.
- Root cause: rpc_meetup_rsvp (kan180:116) runs can_current_user_rsvp_meetup for every action (kan180:142-146); the helper denies a member with cta 'already' (kan713_access_helpers.sql:367-369), so 'cancel' by a member always raised. Fix: for 'cancel' accept only the 'already' denial; no active RSVP -> P0001 'not_attending'.
- Proof: /Users/moataz/.claude/jobs/dcb6a775/tmp/clean786.sh <sha> -> KAN-786 ALL PASS (log clean786_b7052576.log). Local throwaway PG16 only.
- Open: KAN-757 J6 script not found on disk (reconstructed); live body not readable (drift guard pins repo pre-image); untracked 20261105110000 re-creates the defective rpc_meetup_rsvp; b08 test mode pre-existing failure on this chain.
- Route PEER (backend reviewer); not self-reviewed.

### 2026-11-03 — KAN-786 follow-up (Luxor): original KAN-757 J6 + b08 no-regression
- Ran Memphis's journeys_kan757.sql unchanged (md5 aaee6961, same as source) on a build757-style chain from 43cbc365. Script: /Users/moataz/.claude/jobs/dcb6a775/tmp/c5_786.sh. Log: c5_786_b7052576.log.
- Run 1 (no fix): 38/4, the same as Memphis, with J6 ERR P0001 already. Run 2, migration applied literally: REFUSED fail-closed. The stub ACL lets PUBLIC and anon execute because the stubs omit hardening:740-741. This is not a defect. Runs 1b and 2b add hardening:740-741 verbatim: 38/4 → 40/2. J6.1 and J6.2 now PASS. J6.3 still fails with P0001 already. That is a separate pre-existing defect: an 'interested' (overflow) member cannot upgrade to going, because the helper's 'already' branch counts interested rows. It is outside leave scope, so I raised a routing request and did not change the commit. KAN-785 is not in the build757 chain, so the J5 failure is the harness rpc_meetup_my starts_at.
- b08 test mode: identical on 43cbc365 and b7052576 (:694 duplicate meetup_rsvps_meetup_user_key, a2 on M1, exit 3). Commit b7052576 is unchanged.

## 2026-11-03 — KAN-772 (KAN-718 D04), team Luxor, sres-e8f23466
- Triaged the 12 D02 §3 candidates on the full events chain at b7052576. All 12 already read events, directly or as a KAN-713/731 intersection, so **no migration ships**.
- Commit e86ea36c0b88fb8f3128f3ff9b7f50b5dd517048 on alpha-luxor contains one file: supabase/tests/events_p4/kan718_d04_last_reads.sql (345 lines, local k772* only).
- `clean772.sh e86ea36c` printed KAN-772 ALL PASS:
  - full chain: 42/42;
  - pre-B negative: 22/42 FAIL;
  - D02 re-run: 0 converted-without-events;
  - catalogue md5 unchanged.
- Nothing was applied anywhere and nothing was pushed. Open question to po: 13 B15 open-read functions (_user_hosted_game, meetup_counts, and 10 that are absent locally) overlap someone's untracked 20261105 drafts. Are they D04 scope, or a separate ticket?

## 2026-11-03 — KAN-792 (Luxor, sres-f8d49904) — kan714 part 2 rebased onto KAN-786 leave fix
- Commit 2ad61afc95230d8ff30f71b7a7a556a2ced0fe74 on alpha-luxor (not pushed): only supabase/migrations/20261105110000_kan714_events_parent_reads_2.sql (first time tracked). Pin rpc_meetup_rsvp a0a9a217… -> acc145f2… (measured); [manifest 70] = post-KAN-786 functiondef + the same 2 kan714 read substitutions; leave branch byte-identical to kan786.
- Proof: /Users/moataz/.claude/jobs/dcb6a775/tmp/clean792.sh -> KAN-792 ALL PASS (throwaway PG16 :55437 only). Partial apply (overlays+twins+manifest 70) — full apply impossible on repo chain: part 1 pin drifts (rpc_games_following_joined) and 34/42 part-2 pins missing/drifted, pre-existing vs b01-b14.
- Finding: untracked kan714 part 1/part 2 appear stale against committed kan714_b01..b14; needs a po/cto call on whether part 2 should exist.

## 2026-11-03 — KAN-776 (KAN-718 D08) rollback / sync-disable / write-loss-guard runbook + probe — Shed
- Commit 32fdd2d3ddf0c5132daa7beb36539d353465643e on alpha-luxor (worktree kan682-luxor), not pushed. Files: supabase/tests/events_p4/KAN718_RUNBOOK.md (296), kan718_d08_rollback_probe.sql (646).
- Proof: /Users/moataz/.claude/jobs/dcb6a775/tmp/clean776.sh 32fdd2d3 -> "KAN-776 ALL PASS" rc=0 (log tmp/k776/clean776_32fdd2d3....out). Applied ONLY on local k776* throwaway PG16 DBs; nothing on Supabase; no migration.
- Findings reported, not fixed: F1 compat mirror trg_zz_kan712_events_compat_mirror missing from KAN-774 manifest (events UPDATE 42703 after phase 4); F2 201/202 SET TABLE replaces whole supabase_realtime list; F3 restored columns append; F4 tgenabled not in triggerdef (8 disabled); F5 no post-phase-4 write path.
- Route: PEER (schema work) — needs a backend-N reviewer.

## 2026-11-03 — KAN-781 (KAN-719 Z04) post-removal checks — Shed (backend-3), Luxor, sres-042f0f6c
- Commit cdb6856e on alpha-luxor (worktree kan682-luxor). Contains only supabase/tests/events_p4/kan719_z04_postcheck.sql (488 lines) and KAN719_POSTCHECK.md (138 lines). Not pushed.
- Proof: /Users/moataz/.claude/jobs/dcb6a775/tmp/clean781.sh cdb6856e prints KAN-781 ALL PASS. The run is in tmp/k781/clean781_cdb6856e.out and run_cdb6856e.log.
- Z01 as shipped REFUSES on the repo chain even with G1 authorised. G3 fails because 13 baseline-only indexes are missing; G6 fails because v_meetup_list and kan718_meetups_compat read description, location_name and is_indoor.
- The post-Z01 state comes from a local stand-in: Z01's own statements, with 13 skipped and 3 held. It FAILS on C2/M1 (meetups.search_tsv), S2 (21 live functions), S3 (8), S4 (host_actor_stub trigger), M3 (F5 55000) and M4 (3 join paths).
- F1 is handled by Z01 statement 334. F2 is handled by the DROP/ADD pairs 201/202.
- No migration was applied and nothing touched live Supabase. Only throwaway k781* databases on port 55437 were used.

## 2026-11-04 — KAN-783 (KAN-719 Z06) migration completion report — DONE, handed to Luxor
- Commit `a91a041c709bfd54b88817620eaf6581985ce136` on `alpha-luxor` (worktree kan682-luxor), author Karnak (Claude), not pushed. Files: `supabase/tests/events_p4/KAN719_COMPLETION_REPORT.md`, `supabase/tests/events_p4/kan719_z06_report_check.sql`.
- Runner `/Users/moataz/.claude/jobs/dcb6a775/tmp/k783/run783.sh <sha>` → `RUN783 ALL PASS` (check PASS pre/post-Z01 39 checks + R, Z02 RESTORE TEST PASS, N1–N3 caught rc=3, cluster torn down).
- Z01 run with ON_ERROR_STOP=0: gate refuses on G1/G3/G6 locally; forced body removes 44 columns, 34 triggers; 6 functions break (KAN-834 census). kan798/799/800/803/804 refused rc=3 (pre-images absent). Production not read; apply status not documented. Brief's KAN-807 note is stale (97e5e6df is on the branch).

- 2026-11-04 KAN-853: re-pinned v_game_rating column-signature md5 98e6f13a… -> 92d98259… (numeric(3,2)) on lines 131/213 of 20261104100300_kan714_b03_views_rating_host_metrics.sql; commit fbae534e66756606c7474f881ecd9b111613e678 pushed to alpha-deir-el-bahari (0ba5f48d..fbae534e). No DB touched, no Jira posted.
  Sanity: md5('composite_score:numeric(3,2)')=3d5ff2c8…, not the pin; the file hashes the whole column list (string_agg attname:format_type, ',' ORDER BY attnum), so one column alone cannot reproduce it. Pin value taken from the brief's production reading.

## 2026-11-04 — KAN-718 handoff (sres-a68152d3), alpha-karnak
- Step 1: re-ran D01–D09 and the kan794–834 probes on local PG16 only. All PASS except: D01 test mode V2 (B04 anchor only exists on k788b; with the anchor removed it is ALL PASS), and 801/807 (FAIL env, their chains are lost).
- Step 2: re-scanned. Still pending: 19 lib/ games reads; homeless meetups cols in v_meetup_list and kan718_meetups_compat; get_nearby_games/getnearbygames/getnearbymeetups/rpc_meetup_visible. Delta: D06 M2 FAILs once D05 is applied (kan718_meetups_compat has no manifest entry). KAN-714 part 1 migration is absent.
- Step 3: wrote supabase/tests/events_p4/KAN718_HANDOFF.md and added one-line pointers in D04_DISPOSITION, DELETION_MANIFEST and RUNBOOK.
- Step 4: no fix migration. Every gap needs a ruling or a ticket, not a D-series conversion that was missed.
- Not pushed. Route PEER (backend-N).

## 2026-11-04 — KAN-718 docs: record CTO ruling dreq-8ae9bcfa (Karnak, sres-1266ab11)
- Edited only supabase/tests/events_p4/KAN718_HANDOFF.md on alpha-karnak; commit f8e7397d (not pushed).
- Added §(h) (line 161): rulings 1–3 and the F1–F11 table (ticket / capability / blocked-by).
- Counts 47→44 slated, 19→22 retained; moved meetups.description/location_name/is_indoor. Old-client verdict marked resolved by (C), deletion deferred to KAN-719b. §(g) prerequisites now map to F-numbers.
- States plainly that the D06 manifest, Z01 and G6 are NOT re-scoped yet (F8). No DB work, no probes.

## 2026-11-04 — KAN-854 (KAN-718 F1) get_nearby_games x2 — RETIRE (Shed, team Luxor)
- Worktree kan682-luxor, branch alpha-luxor, commit e4890a9e (not pushed). Files: supabase/migrations/20261104112200_kan718_f1_get_nearby_games.sql, supabase/tests/events_p4/kan718_f1_get_nearby_games_test.sql.
- Decision RETIRE: both baseline overloads select games.lat/lng (columns absent) -> 42703 on every call; lib callers dead (supabase_games_datasource.dart:659 wrong param names, no caller of GamesRepositoryImpl.getNearbyGames; nearby_games_repository_impl.dart:23 only via explore nearbyGamesProvider, hidden/unwatched); no SQL caller. A working rewrite would need SECURITY DEFINER over events (FORCE RLS, no API grant).
- Migration: pre-image gate (md5 prosrc + result sig) + COMMENT ON FUNCTION 'KAN-854 RETIRED'. No body, grant or DROP. Gate refusal demonstrated on a drifted body.
- Local PG16 chain (harnesses + 710/711/712A + baseline pre-image verbatim): RED 2 FAIL (T3.1/T3.2), GREEN 13/13 PASS. Cluster removed.
- Open: F8 removes both; routing request (frontend) to delete the two dead lib callers; PEER review by another backend-N required. Not consulted live pg_get_functiondef (forbidden); gate covers drift.

## 2026-11-04 — KAN-855 (KAN-718 F2) getnearbygames — RETIRE (Shed, team Luxor, sres-2fc26634)
- Worktree kan682-luxor, branch alpha-luxor, commit 6acb3114 (not pushed). Files: supabase/migrations/20261104112300_kan718_f2_getnearbygames.sql, supabase/tests/events_p4/kan718_f2_getnearbygames_test.sql.
- Decision RETIRE: zero `.rpc('getnearbygames'` callers in lib/ or supabase/ (no config constant); no SQL caller (T6). Baseline-only LANGUAGE sql body joins public.geolocations + reads games.sport/lat/lng/areaid/geolocationid (absent) -> 42P01 on every call. Rewrite would need SECURITY DEFINER over FORCE-RLS events.
- Migration: pre-image gate (md5 69ad4a90… + result sig) + COMMENT 'KAN-855 RETIRED'. No body, grant or DROP. Gate refusal shown on a drifted body (rc=3). pg_depend proc->games = 0, prosqlbody NULL: does not block Z01.
- Local PG16 chain port 55461 (harnesses + 710/711/712A + baseline pre-image, check_function_bodies=off): RED 1 FAIL (T3), GREEN 7/7 PASS. Cluster removed.
- Open: F8 drops it. PEER review by another backend-N required.

## 2026-11-04 — KAN-861 (Luxor, sres-ce7ed5d5)
- Part A done on alpha-luxor (not pushed): cdef747a revert e4890a9e; 6987bd9c merge alpha-karnak (datasource conflict resolved per brief; datasource_test re-pointed getGames/getMyGames to v_game_card/v_my_games, stream test removed); be4f6cb7 merge alpha-habu (HANDOFF.md add/add took habu's superset). part_2 diff vs d9a65dff empty; no 1122xx-1125xx duplicate. analyze 0 err/0 warn (42 infos); flutter test 4549 pass.
- Part B STOPPED before editing: ruling 1(C) applied to D03 (select('*') = every slated games column) retains all 22 KAN-711 games columns, contradicting the brief's 44 slated/22 retained; and retained games columns go stale once Z01 drops seq 334 (kan712_events_compat_mirror writes games at :241 and meetups at :262). One question returned. DROP FUNCTION for F1/F2 is consistent with their headers ("removing ... belongs to F8").

## 2026-11-04 — KAN-861 Part B (F8) under CTO ruling dreq-0f6e9434 (A) (Shed, team Luxor, sres-303f13ca)
- Worktree kan682-luxor, branch alpha-luxor, commit 71887109b84915ccef5db8931c3d83d1aaf749dd (NOT pushed; Luxor pushes).
- Z01 re-scoped: 22 slated (games 1 search_tsv; meetups 21) / 44 retained (games 35, meetups 9); 63 stmts (56 local, 7 baseline-only), md5 ed136455…; 334 removed; 690 mirror CREATE OR REPLACE (games branch verbatim from pg_get_functiondef, meetups branch removed) + 691 REVOKE; 801-803 DROP FUNCTION (no CASCADE, no dependants). Gate structure unchanged.
- Local PG16 only (/tmp:55861, data under /private/tmp). D06 check PASS M1-M5/D1/S1-S5; Z01 test PASS Z1-Z4, smokes a/b/c, R1; full-file apply with baseline-only objects recreated passes G1-G6 + post, rolled back. Fail-first shown for M1, G3-690, smoke (a), smoke (b), d03 pin.
- d03 scan test 8/8; flutter analyze 0 errors/warnings (42 infos); flutter test 4549 pass.
- Open: other events_p4 probes loading k774_manifest (d08_rollback_probe, z02_restore_test, z04_postcheck) not re-run, outside allowed paths. HANDOFF line 12 (outside b/d/h) still says F8 not done. PEER review by another backend-N required.

## 2026-11-04 — KAN-715 verification fix 1 of 3 (Luxor, sres-251ca689)
- C1: new migration `supabase/migrations/20261105140000_kan715_v_game_card_my_games_event_id.sql` (alpha-luxor). It appends `g.event_id` last on v_game_card (54 to 55 columns) and v_my_games (21 to 22). B01 bodies are otherwise byte-identical. Fail-closed guard, and the post-conditions hold. The KAN-714/2 dependency md5 pins are unchanged (d7c7…/3b76…). Proven on a throwaway local PG16 at /private/tmp/kan715_pg: 7464/5419 rows, 0 bad. On a game re-parented to a distinct event id, both views return id=games.id and event_id=the new parent.
- C2/C3: datasource fixtures now use the real projection shape. Added 2 tests (getGames / getMyGames carry both ids). Fail-first showed eventId null without the fixture's event_id. fromJson was unchanged.
- analyze: 0 errors, 0 warnings. flutter test: 4574 passed. Commit 4592fb6fba9be00448f29f5510238d31ca118441, not pushed.
- Limitation: the local chain stops at B03 on a pre-existing KAN-722 pin. Because of that, parent_reads_2/Z01/D05 were not applied locally, and their sort order relative to this file was checked by reading the files.

## 2026-11-05 — KAN-825 helper consolidation (Shed, backend-3)
- Commit 2a1502af on staging-luxor (kan682-luxor worktree), not pushed. It adds `supabase/migrations/20261105150000_kan825_helper_consolidation.sql` and `supabase/tests/events_p4/kan825_helper_consolidation_test.sql`.
- The new body of kan803_game_host_uid is `SELECT f.creator_user_id FROM public.kan804_game_event_facts(p_game_id) AS f`. Every attribute and the ACL are asserted unchanged before and after.
- Local PG16 on port 55825:
  - RED exits 3 at T1.
  - GREEN exits 0: T0 to T5 pass, 41 cases, parity over 3015 ids.
  - The cluster was torn down afterwards.
- Findings:
  - CHECK games_event_id_not_null makes a game with a NULL event_id impossible. S4 (a dangling event_id) covers the "no event" case.
  - build_kan850 and build_kan788 are broken at e57da574, for two reasons: a false positive in the order check on b06, and pin drift on v_game_rating at B03.
  - build_kan851 needs base ref 61ebab0d.
  - The KAN-803 test fails at Z01 on the k851 chain.
- Not applied remotely. This goes the PEER route and needs a backend-N reviewer. This entry is not committed, because it is outside the two-file scope.
