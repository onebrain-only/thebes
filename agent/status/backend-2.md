# backend-2 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-2.md`. This file is a work log, not a rule source.

**deliberately broken fold** — identical body and clamp, self-exclusion predicate
deleted — in a rolled-back transaction. Both caught it: *"self-exclusion broken - 1
own rows returned for sport padel"* and *"no caller identity returned 50 rows,
expected 0"*. **The second is the KAN-174 incident reproduced**, and the assertion
is what stops it committing. Production re-read after that rollback and confirmed
unchanged (183 bytes, no clamp, original ACL) before anything else was done.

**One assertion is NOT discriminating and is labelled so in the file rather than
counted as green.** "Body free of `p_me`" passes pre-migration because the 6-arg
body never had `p_me` — the 7-arg's did. Its real case is a botched fold that
re-imports the parameter. Stating that is the difference between a probe pack and a
row of green ticks.

**P4 and P6 passing pre-fix is correct, and misreading that would be the whole
error.** The 6-arg wrapper's self-exclusion always worked and `anon` always got 0
rows *through it*. The incident was never the 6-arg — it was the 7-arg sibling,
directly reachable, taking identity from the caller. So P4/P6 are **regression
guards** that must keep passing across the fold, while P1 and P5 are the only
probes that change state. A pack where every probe flipped would be one that had
misread the defect. Recorded in the pack header with the measured results.

**AC1 vs `T-070` D2 — a real divergence, flagged not resolved.** AC1 asks for
`anon` EXECUTE revoked from **both** overloads. `T-070` post-dates the filing and
rules the 6-arg keeps both `SECURITY DEFINER` and `anon`'s EXECUTE. Measured today:
`v_sport_profiles_with_user` grants `anon=xtm` / `authenticated=xtm` — **no `r`**,
`has_table_privilege(…,'SELECT')` **false for both**. So an invoker function returns
nothing to anyone, and revoking `anon`'s EXECUTE turns 0 rows into **`42501` raised
through `v_potential_vibes_default`**, which `anon` *does* hold `r` on and which the
anon-allowlist gate watches. A live break for nothing. **Containment on the 7-arg
already held** (`proacl = {postgres=X,service_role=X}`, no PUBLIC entry,
`has_function_privilege` false for both client roles) — and removing the object
beats revoking its grant. Posted to the ticket as a divergence for `po`, not
decided unilaterally.

**`rpc_potential_vibes_debug` is DROPPED, not revoked, and the probe says why.**
As `anon` it raises **`42P01` relation "public.v_vibes_candidates" does not exist**,
NOT `42501` — it *passes* the permission check on a bare PUBLIC `=X` and dies on a
missing relation. `to_regclass` NULL, confirmed same run. Inertness is luck. It is
the richer body (3,599 vs 725 bytes) with skill_level, composite_score, mutual
counts and geo-locality, and its `search_path` is `public` alone — no `pg_temp`,
unlike every sibling. One `CREATE VIEW` away from reproducing the incident with a
worse payload and no new grant.

**§2g checked rather than assumed.** Dropping the debug function leaves its
signature in my own KAN-175 allowlist at `docs/SCHEMA.md:769`. Read
`anon_function_grants_diff.sh` to confirm the consequence instead of guessing: the
diff is **one-directional by design** — a signature leaving the flagged set is a
stale entry, never a red build. So the gate stays green and §2g stays untouched,
which is also what AC6 requires.

**AC6 deliberately NOT written.** It is conditional on AC2's redesign landing, and
AC2 has not landed. Writing a `docs/SCHEMA.md` row describing a post-fix mechanism
that is not live would put a false statement into the exact document the AC exists
to de-drift. Replacement text prepared verbatim in KAN-174 comment 10997, to apply
in the same change that lands the migration.

**One further doc line this migration falsifies, raised not edited.**
`docs/SCHEMA.md:901` — *"`rpc_potential_vibes` ×2 (one takes `p_me`)"* — is a live
claim about the catalogue and becomes false when the fold lands. Outside §2g and
outside AC6's scope, so raised to `po` rather than edited unilaterally. By contrast
`docs/SCHEMA.md:684` (§2g.1's containment table) is a **dated historical record** of
what was revoked on 2026-09-10 and stays true as history — left alone deliberately.

**Not transitioned to `Peer-review`.** AC2 has not landed and there is nothing for a
peer to review as done. Ticket stays in `Back-end` (10043), **ownership retained**.
Route PEER; reviewer must be another `backend-N`. `G-006` claim comment posted
BEFORE the attempt (10995) with preconditions re-measured immediately beforehand;
outcome posted back after (10997). **What unblocks this: permission to run
`apply_migration` on `wtncuzcskpigqpmnxwws` for this one file.** Everything else is
finished and measured.

## 2026-11-02 — KAN-723 (KAN-714 B04, Epic KAN-708): nearby/following RPCs read events
- Commit `4de93e4fbd0f16e4a2ba0df0520beccc03baba83` on `alpha-habu` (worktree kan680), not pushed.
- Files: `supabase/migrations/20261104100400_kan714_b04_rpc_nearby_following.sql`, `supabase/tests/events_p2/kan714_b04_nearby_following.sql`.
- Local throwaway PG 54775 only: with B04 `#TOTAL|pass=39|fail=0`; control (no B04) `#TOTAL|pass=26|fail=13|K_fail=13|eq_fail=0`. Server stopped. Nothing applied to Supabase.
- Findings for routing: 5-arg/6-arg `rpc_get_nearby_games` overload drift makes a 5-arg call ambiguous where both exist; Dart `nearby_games_datasource.dart:45` hardcodes the RPC name; `supabase_games_datasource.dart:665` calls `get_nearby_games` (different function).
- Route PEER: needs another backend-N reviewer. Did not self-review.

## 2026-11-02 — KAN-727 (KAN-714 B08) capacity/join/rating checks read events — Nekhbet

- Commit `aba8732e7aca51c40b904e9bd9928b18d3f5c622` on `alpha-habu` (worktree kan680), not pushed.
- Files: `supabase/migrations/20261104100800_kan714_b08_capacity_join_rating_checks.sql`, `supabase/tests/events_p2/kan714_b08_capacity_join.sql`.
- Converted: game_slots_left (sql -> plpgsql INVOKER, events branch when events readable), meetup_slots_left, rpc_rate_game/user/venue (end_at + cancel union from events). Join path relies on KAN-713's can_current_user_join_game (already events-backed) and the converted slots.
- Local only (port 54775): B08 `#TOTAL|pass=69|fail=0|K_fail=0|eq_fail=0`; control `#TOTAL|pass=55|fail=14|K_fail=14|eq_fail=0`. Production untouched. Server stopped.
- Not converted: rpc_meetup_decide_request, rpc_remove_player (out of planned surface); rpc_meetup_rsvp absent locally. join_policy vs rsvp_policy reported only.
- Estimate 45 min exceeded (multi-session). This status entry is outside the planned surfaces (role rule).
- Route: PEER (schema) — needs another backend-N reviewer.

## 2026-11-03 — KAN-722 (KAN-714 B03) rescue
- Cherry-picked Karnak c6e80c4d onto alpha-habu (kan680 worktree) as 6e47b63f; follow-up 63a5208d removes the v_host_weekly_metrics rewrite (B07/KAN-726 owns it), test asserts B03+B07 chain, rollback restores only v_rateable_after_game.
- Local PG16 (port 54775) only: with B03+B07 27/0, control (B07, no B03) 23/4 FAIL, rollback expect=pre 27/0 with the fingerprint unchanged. Not applied anywhere live. Not pushed (the orchestrator pushes). Next step: PEER review by another backend seat.

## 2026-11-03 — KAN-733 (KAN-714 B14) rescue — completed (not applied anywhere live)
- Cherry-picked Karnak 3f21e3ab + bbea705d onto alpha-habu; fix commit 314d9bdd.
- Stage guard no longer requires 20261104110000 / 20261104110300 triggers (both sort after B14; original refused in filename order).
- Wrapped series RPCs now changed via kan712_unwrap_rpc -> replace -> kan712_wrap_rpc (migration and rollback); post-checks prove wrapper survived.
- Local PG16: strict order 189/0, control 167/22, rollback expect=pre 189/0 with unchanged fingerprint. Route: PEER (backend reviewer).

## 2026-11-03 — KAN-789: refresh stale rpc_meetup_my evidence after KAN-785
- Commit 6c7fd2f72c05a52be02d78e201c69120335a8f9f on alpha-habu (worktree kan680), not pushed. 8 files, all under supabase/tests (40+/26-).
- Manifest row 73 kept as RETIRED by KAN-785. Totals: 161→160, unchanged 95→94, pinned 7→6. B15 C2 99→98, C3 100→99, C6 26→25. D01 anchors 30→29.
- Proof on a throwaway PG16 (port 54789, built from the commit archive): B15 ALL PASS exit 0, D01 test PROBE ALL PASS exit 0, D01 scan 40/40 pending exit 0.
- Negatives: the old probes failed on post-785 (B15 C3 and D01 V2, exit 3). B15 corrupt=1 failed at C4, exit 3. Cluster stopped.
- Extra file: KAN718_D01_SQL_CONSUMERS.md (stale counts). rollback_kan714_b06.sql got a note only; the order is to roll back KAN-785 first.
- Route: PEER (backend-N reviewer).

## 2026-11-03 — KAN-787 (Nekhbet)
Removed retired rpc_meetup_my pins (header, R legend, S1/S2/S3, D4, R1) from supabase/tests/events_p2/kan714_b06_meetup_reads.sql on alpha-habu, commit 5a20e4465413bb25529e095e40b0e3da5edb7f6b (not pushed). Local PG16 :54787 only. New file: 24/24 PASS in post (B06+785) and pre (785 only) images; RED step still D1,D2,D3,X1,P1..P4. Old file aborts at line 333 (function does not exist) on both post-785 images; 26/26 on the pre-785 B06 image. Corrupted S1 expectation: 1 FAIL. Cluster stopped. Outputs in /Users/moataz/.claude/jobs/3aff666d/tmp/kan787-*.txt. Route PEER (another backend-N).

## 2026-11-03 — KAN-791 local app-level stack (Nekhbet, backend-2)
- Commit `a271381b7236f06a2bf9c083e78e28648b301e3f` on `alpha-habu` (worktree `Dabbler/dabbler-code/.claude/worktrees/kan680`), not pushed. 10 new files under `scripts/local_stack/`, +791 lines. No existing file was touched.
- Components: PG 16.15 (Homebrew), PostgREST v16.5, GoTrue v2.197.0, Realtime v2.152.0 (built from source with Elixir 1.20.4/OTP 29 from brew, 1 install attempt), wal2json_2_6.
- Recorded run start → start (reuse) → smoke → teardown → teardown. Smoke results: (a) PASS, (b) PASS, (c) PASS. Both teardowns rc=0, with no stack process and no run dir. Evidence is in `/Users/moataz/.claude/jobs/3aff666d/tmp/kan791-{start,smoke,teardown1,teardown2}.txt`.
- Probe (c) was first seen FAILING (`library "wal2json" may not be used as an output plugin`). PG 16.15 has an `output_plugin_libraries` allowlist, and adding wal2json to it fixed the failure.
- Production project was not touched. Supabase MCP was not used, and nothing ran on port 5432.
- This status file is outside the brief's allowed paths, as the brief itself noted.

## 2026-11-03 — KAN-792 rescue (team Habu, sres-23dc064e)
- Carried Luxor's 2ad61afc onto alpha-habu as one commit 04e50b691c1e426cf9eb242d55ec27ef9b7c3aaf (only supabase/migrations/20261105110000_kan714_events_parent_reads_2.sql, md5 0ada038e40ac5a78d4da03cf3d477429). Not pushed.
- Re-verified on throwaway PG16 port 55479 (k792h, now stopped and deleted). kan786 + its test, and part 1, were supplied as temp copies only. C1 leave branch md5 a30e8b81… equal. C2: kan786 test 18/18, and the negative run gave P0001 already. C3: 3 hunks, 1-file commit. Evidence: /Users/moataz/.claude/jobs/3aff666d/tmp/kan792-verify.txt.
- Limitations: the full file cannot apply (part 1 is untracked and has pin drift); the proof used a partial apply, the same as Luxor's.

## 2026-11-04 — KAN-799 (Habu, reservation sres-9afd9c89): D04 blockers rpc_remove_player / rpc_recreate_from_game
- Migration 20261104110600_kan799_d04_blockers_remove_recreate.sql + test supabase/tests/events_p4/kan799_d04_remove_recreate_test.sql, commit 9a42c849 on alpha-habu (not pushed; Habu pushes). Authored, not applied anywhere but a throwaway PG16 (port 54799, deleted).
- Shared-field reads moved to events via games.event_id; baseline bodies otherwise verbatim; attributes/ACL unchanged. Pre-image 42703 after Z01 dry run, new body identical on 7 cases before/after Z01.
- Flag: 20261105110000_kan714_events_parent_reads_2.sql drift-pins both functions to the baseline md5 — it will refuse after this applies.
- Route: PEER (backend-N reviewer). Evidence /Users/moataz/.claude/jobs/3aff666d/tmp/kan799-verify.txt.

## 2026-11-04 — KAN-800 (team Habu, sres-51d09e13) — authored, not applied
- Commit 67201194 on alpha-habu (worktree kan680, not pushed): `20261104110700_kan800_d04_blockers_meetup_requests.sql` + `supabase/tests/events_p4/kan800_d04_meetup_requests_test.sql`.
- rpc_meetup_decide_request / rpc_meetup_remove_attendee: `meetups%rowtype` + `select *` → record filled with ev.creator_user_id (+ ev.is_cancelled) via meetups.event_id; lock stays `for update of mt`. Pre-image 20260915120000 (md5 d8c60f06 / 7fec2761). Local PG16 port 54800: RED 10/13 after Z01 on pre-image; GREEN 13/13 identical pre vs post vs post_z01; ACL/attrs unchanged; cluster deleted. Evidence /Users/moataz/.claude/jobs/3aff666d/tmp/kan800-verify.txt.
- Open: KAN-714 part 2 (20261105110000) pins these two md5s; will refuse once KAN-800 applies (same as KAN-799).

## 2026-11-04 — KAN-803 (Habu, sres-2f9c3158) — BLOCKED, one question returned, nothing written
- Synced alpha-habu with origin/Alpha (up to date, HEAD 67201194). No file created, no commit, no cluster started.
- Pre-images: only CREATE OR REPLACE is baseline 20260829080500 (:18977 invite, :19032 joinreq, :20320 waitlist); 20261013135000 only revokes. All three are SECURITY INVOKER and read only `g.creator_user_id` (Z01 seq 603).
- Blocker: public.events has zero client grants (KAN-710 :100-102) and the app inserts game_join_requests directly as `authenticated` (supabase_games_datasource.dart:1140; KAN-86 :167 grant; policy joinreq_insert_requester). A direct events read in an INVOKER trigger raises 42501 for every client join request; the KAN-772 has_table_privilege fallback still 42703s after Z01. A body-only, attribute-preserving fix needs a SECURITY DEFINER read path that does not exist on the applied chain. Returned to the Habu orchestrator as one question.

## 2026-11-04 — KAN-803 (CTO dreq-da12f7c0 option a) — committed 8ca6d3d30a2c6823c08c41ffd4ebee9a34101966 on alpha-habu (not pushed)
- Migration `supabase/migrations/20261104110800_kan803_d04_blockers_frozen_guards_a.sql`: new `public.kan803_game_host_uid(uuid)` (STABLE, SECURITY DEFINER, search_path public, pg_temp; EXECUTE authenticated + service_role only), and the invite/joinreq/waitlist frozen-guard bodies take the host from it. The RLS-scoped games lookup still decides game_not_found. Roster guard not touched.
- Test `supabase/tests/events_p4/kan803_d04_frozen_guards_a_test.sql`: 27 cases run as authenticated (direct, visible-games probe and definer-RPC paths). Results are identical pre/post and after the Z01 dry run. The pre-image fails with 42703 in 21/27 cases after Z01. 42501 is shown for an authenticated events read and for an inline events join in the trigger.
- C1-C5 PASS. Evidence is in /Users/moataz/.claude/jobs/3aff666d/tmp/kan803-verify.txt. The local cluster on :54803 is stopped and deleted. Production was not touched.
- Finding: games has RLS enabled and no policy (baseline :32378), so it does not expose creator_user_id. The helper is a NEW exposure: any authenticated caller who knows a game id can read its host uid.
- Route: PEER. A backend-N reviewer is needed; until then the work waits in Peer-review.

## 2026-11-04 — KAN-807 (D04 residual reads of Z01-dropped columns) — backend-2 Nekhbet, team Habu, sres-e6fbd13f

- Commit `97e5e6dfa1e07164be65ceadadc97b4ddc133ce6` on `alpha-habu` (worktree kan680). NOT pushed. 3 files, 1069 insertions: `supabase/migrations/20261104110900_kan807_d04_residual_a.sql` (507), `supabase/migrations/20261104111000_kan807_d04_residual_b.sql` (257), `supabase/tests/events_p4/kan807_d04_residual_test.sql` (305).
- Fixed (8, all SECURITY DEFINER, bodies now read events via event_id; md5 pre/post pins and attribute snapshot guards): _can_view_game, _is_game_host, active_stream, rpc_get_activity_feed, rpc_get_nearby_games(6), rpc_rate_game, rpc_rate_user, rpc_rate_venue.
- Left (8): _can_view_game_for_join, _slot_conflicts_game, game_slots_left (INVOKER and API-reachable; reading events would raise 42501, the KAN-803 rule); kan711_events_map_game/meetup (dead mappers, need a retire ruling, DROP forbidden); rpc_unified_search_sectioned (also reads search_tsv, under that ruling); rpc_challenge_spawn_game (write path, create ruling KAN-797); rpc_join_game member path (raised in out-of-scope callee can_current_user_join_game).
- Test on local k807t2: ALL PASS. T2 RED pre-image after Z01, T4/T5 32 cases equal to pre, T6 attributes unchanged for all 16 functions.
- C1-C5 PASS. Evidence is in /Users/moataz/.claude/jobs/3aff666d/tmp/kan807-verify.txt. Local cluster :54807 is stopped and removed. Production was not touched.
- Difficulty matched the brief. Route: PEER. A backend-N reviewer is needed; until then the work waits in Peer-review.

## 2026-11-04 — KAN-819 (KAN-781 postcheck S4 skips harness objects)
- alpha-habu (worktree kan680): cherry-pick -x cdb6856e -> 169ecfa6; KAN-819 -> 29e1c415 (S4 trigger loop gets the S2 proname exclusion; new kan805_s4_harness_skip_test.sql). Not pushed.
- Test RED on cherry-picked postcheck ((a) harness trigger counted), GREEN after; (b) shown failing on an over-broad exclusion.
- C2 on local PG16 :54819 (base781 chain + D05 + seed + capture + Z01-local): only S4 lines differ — S4 FAIL (harness_host_actor_stub) -> S4 PASS; summary 37 -> 36 fails, sections C2,M1,M3,M4,S2,S3. Cluster stopped, data dir deleted.
- Flags: KAN719_POSTCHECK.md line 103 now stale (lists the S4 harness finding); S4 PASS count still counts harness triggers (8 incl. harness_host_actor_stub) — left unchanged per brief.

## 2026-11-04 — KAN-857 (KAN-718 F4, rpc_meetup_visible convert)
- alpha-habu c7b8aec0626902de2fbb0ccc5bf690c8dc26b988, pushed. New: 20261105130500_kan718_f4_rpc_meetup_visible.sql + events_p4/kan718_f4_rpc_meetup_visible_test.sql.
- Finding: the baseline body never worked (meetups has no starts_at/visibility/owner_user_id; 42703 for every role). Parity reference used = meetups RLS rows per viewer.
- New body reads kan718_meetups_compat (D05; events values, filter = meetups policy/kan713_meetup_visible); invoker cannot read events directly. Dependency on the view is not in pg_depend.
- Local PG16 :55857 (build_kan788.sh; chain stops at B03 pin drift, k788 had B01/B02): C1-C4 PASS. Cluster stopped and deleted. Awaiting PEER (backend-N).

## 2026-11-04 — KAN-860 (KAN-718 F7): kan801/kan807 proofs reproducible from tracked files
- Commit d1588c30e43fb4f2f59c88d86263ad4e517a261a on alpha-habu (pushed, c7b8aec0..d1588c30).
- Added the tracked builders under supabase/tests/events_p4/: base781_with_d04.sh (ported from the untracked Thebes review-evidence KAN-781/judge-04740e4f copy), build_kan807.sh, and build_kan801.sh (reconstructs the lost clean801/seed781/harness801 steps from the baseline, verbatim, and pins set_attendee md5 118f1db9). Changed only the header comments of the two test files. Brought in KAN718_HANDOFF.md unchanged from origin/alpha-karnak 8d4c7443 and edited section (g) only.
- Fixed a B03 KAN-853 pin drift on the Alpha chain with a marked numeric(3,2) stand-in for the v_game_rating harness view, in the throwaway DB only.
- Clean PG16 clusters, deleted afterwards: :54862 gave KAN-807 ALL PASS. :54861 gave KAN-801 RED pass=17 fail=8 (identical to the judged run) and GREEN pass=25 fail=0.
- Gap: the post-Z01 801 variant was not reproduced. Effort was more than about 1h because of the chain reconstruction.

## 2026-11-04 — KAN-859 (KAN-718 F6) fix 1 of 3, C2: null-safe drift guard
- Commit c220c5e7ec43ff7fe6c9f142f0e3db665100faf2 on alpha-karnak (pushed). Drift predicate for both functions now
  IS NOT DISTINCT FROM / IS TRUE / IS FALSE per term, wrapped in NOT COALESCE((...), false).
- Probe phase=drift added: red 6/7 on old guard, green 7/7 on fixed guard; happy path pre 5/5, post 3/3, pg_proc -2.
- Disposable PG16 only (port 55859), cluster stopped and removed. No live Supabase contact.

## 2026-11-04 — KAN-880 (KAN-865 export_own_game_history, CTO dreq-5087907b pt 1) — team Karnak
- Commit dcdc36afd84d09c3e5a569a822914ccc122f1f00 on alpha-karnak (worktree kan714-karnak). Not pushed.
- New: supabase/migrations/20261105130000_kan865_export_own_game_history.sql (CREATE + COMMENT + GRANT authenticated only), supabase/tests/events_p4/kan865_export_own_game_history_test.sql.
- Live FK (read-only): game_roster_game_id_fkey FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE. Function joins roster on g.id. export_own_events joins gr.game_id = e.id; that does not follow the FK and depends on games.id = games.event_id (the trigger enforces it). Not fixed.
- Probe via prove + psql (no pgTAP or pg_prove installed): RED 8/8 before, GREEN 8/8 after. A mutant (ASC order, no event_type filter) failed T1/T3/T4. Local PG16 :55880 stopped and deleted.
- PUBLIC keeps the default EXECUTE (proacl had =X and anon=X locally). Per the ruling, no REVOKE was added; this is flagged for review.
- Route: PEER (backend-N). Waits in Peer-review.

## 2026-11-05 — KAN-885 (Karnak) — supplement migration meetup_counts D04
- Authored supabase/migrations/20261105105900_kan823b_d04_meetup_counts.sql on staging-karnak, commit fe59c77f8bdaef9b0ef1b01ca15293ea2e8351a0 (not pushed, not applied; needs-ops, PEER by another backend-N).
- Local PG16 proof: good DB applies (ec29fe4c -> e5982fbd, owner/ACL/oid kept); drift DB aborts at guard.
- Open: live md5 of _recent_activity_score / game_is_joinable not read (ops guard refused execute_sql). KAN-834 (20261104112100) pins both at KAN-772 post-image; if production is at KAN-772 pre-image, KAN-834 fails closed -> they join 29a (CTO/PO call).

## 2026-11-06 — KAN-887 (Karnak, sres-056a77e3) — part 2 re-pinned on step-25 rpc_create_* bodies
- Commit 701354113191ad1811b99f6831f23c7d2297b180 on staging-karnak, pushed. Repository text only; no Supabase touched.
- Delta part 2 adds to these two functions (vs KAN-772 bodies): replay lookup `public.games g` / `public.meetups m` -> `public.kan714_games_read g` / `public.kan714_meetups_read m`. Applied the same to the kan794 bodies.
- Pins 5b8883b2 / 0f5ba02e; post-images 1b3aa6f2b8033bdf64c5bc856d6c7f43 / f347168e1c1a6b424ebabea41ff3e85f (asserted in section 5).
- Proof supabase/tests/events_p4/kan887_part2_after_kan794_test.sh: RED (no step 25) aborts on rpc_create_game; PRE step 25 applies; GREEN part 2 applies. ALL PASS on throwaway PG16 :55887 (removed).
- Note: HEAD's B06 (KAN-881) breaks build_kan788's order check locally; the test uses cdc1810b^ B06 (pins only differ). kan858_part2_guard_test.sh likely has the same break.
- Route: PEER (backend-N reviewer).
