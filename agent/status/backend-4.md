# backend-4 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-4.md`. This file is a work log, not a rule source.


Nothing further to do until a review verdict returns.

### 2026-09-11 — KAN-171 DONE. KAN-169's `surface-contention` diagnosed: it is NOT KAN-131.

KAN-171 passed PEER (`backend-1`) and is canonical `DONE`, rev 18. Work Effort landed at 3 of 3,
under the ceiling of 4.

`team-lead` reported KAN-169 blocked by `surface-contention` with **KAN-131** and held rather than
releasing `backend-1`'s ownership — correct instinct, wrong target. Measured read-only:

    contending_owner(KAN-169, all_tasks)  ->  KAN-178     (not KAN-131)

`contending_owner` returns the **first** colliding owned task, so it names one of several rather
than the cause. Enumerating all of them:

| contender | owner | its declared surface |
|---|---|---|
| KAN-178 | `backend-5` | `…/20260910140000_kan178_role_grants_admin_only_read.sql` |
| KAN-182 | `backend-3` | `…/kan182_process_notification_event_guard.sql` |
| KAN-131 | `backend-1` | `…/kan131_platform_owner_sentinel.sql` |
| KAN-184 | `backend-8` | `…/kan184_unguarded_write_lower_tier.sql` |

**4 of the 5 owned tickets on the board.** Releasing KAN-131 would have cleared nothing and cost
`backend-1` its claim for no gain.

**Cause — a surface-declaration defect on KAN-169, not a real collision.** Its `surfaces` are
`['supabase/migrations/', '…/20260907130000_kan138_settle_game_settlement_status_cast.sql']`. The
first entry is a **bare directory**, and `queue.surfaces_collide` implements directory containment
(`b.startswith(a.rstrip('/') + '/')`). So KAN-169 collides with **every ticket declaring any file
under `supabase/migrations/`** — which is every backend migration ticket that will ever exist. It is
not blocked by one peer; it is permanently unclaimable until the declaration is narrowed, and the
next claim by any backend seat would re-create the block instantly.

Fix is to drop the bare-directory entry and keep the specific file. **That is a `po` write** —
surfaces are recorded by `po`, and I do not edit another ticket's declared scope. Reported; not
actioned by me.

Side observation: **KAN-184 is now owned by `backend-8`**, which answers the flag I had been
carrying about its unapplied containment — it has an executor.

---

## 2026-09-11 — KAN-169 APPLIED: `settle_game` derives organiser, sport and gross (T-069)

Claimed to me (`claim_ref: burn-down-2026-09-11`); I re-ran the continuation gate myself before
touching anything — `store.assert_execution_permitted('KAN-169','backend-4')` passed, ownership
`backend-4`, route `peer`. Transitioned `Ready` → `Back-end` (5) → `Peer-review` (7) myself.

**Landed, two sittings, both via `apply_migration` (never `db push`, T-068):**
- `20260911113000_kan169_settle_game_derive_organiser_sport_gross.sql`
- `20260911114500_kan169_settle_game_zero_and_negative_earnings.sql`

Signature `settle_game(uuid,uuid,text,numeric,boolean)` → `settle_game(uuid,boolean)`. `DROP`+`CREATE`,
`overload_count = 1` asserted. `proacl` after apply is `{postgres=X/postgres,service_role=X/postgres}` —
`pg_default_acl` names `anon` **and** `authenticated` for functions, so the `CREATE` re-granted both and
revoking `PUBLIC` alone would have left `anon` executable (T-078). Both revoked by name.

**The lesson I want to keep from this one: the probe found a defect inspection would not have.**
Making gross derived changed what `gross = 0` *means*. It stopped being a value a caller opts into and
became the default state of every game with no succeeded charges — today, every game. The credit then
hit `wallet_ledger_amount_aed_check CHECK (amount_aed > 0)` and blew up with 23514. Sitting 1 on its own
could not settle **any** game, and it read perfectly correct. I only saw it because I ran the organiser
path for real instead of asserting the body looked right.

Ruled the two cases apart rather than together: `earnings = 0` settles and posts no credit; `earnings < 0`
raises `fee_exceeds_gross` before the settlement row is written, because that is a debit and this function
has no authority to invent one. Collapsing them into one `> 0` guard would have silently swallowed an
organiser owing the platform money.

**Both open design questions ruled, not deferred** (the brief was explicit about that):
1. No admin-settlement column on `game_settlements` — recorded in `meta` (`settled_by`, `settled_via`)
   instead. `meta` IS on the row, which is what T-069 asked for, and widening a money table is a shape
   call reserved to `cto`. Flagged for promotion to a typed column if it ever needs an index.
2. AED vs multi-currency — detect and raise (`mixed_currency_charges` / `non_aed_charges`), never sum
   across currencies into an AED-named column. KAN-171 deliberately left currency per-row so this was
   detectable; I used that rather than pinning AED.

Twelve probes, each demonstrated failing before counting as passing, all inside `begin`/`rollback`;
post-state re-measured at 0/0/0 rows. Baseline first: against the pre-fix body a non-organiser settled a
game they did not own and credited themselves **899,999.10 AED**. Added an I-control probe so the
`invalid_gross` probe was known to fail on the condition and not on the fixture.

**Raised, not actioned by me:**
- **KAN-138's staged migration (`9d855a5`, Peer-review, unapplied) reproduces the pre-T-069 vulnerable
  body verbatim.** Landing it now would silently restore the five-parameter function and the bypass I
  just proved. This is AC7 and it is now urgent rather than theoretical.
- `games_creator_user_id_fkey` is `ON DELETE SET NULL` while `games.creator_user_id` is `NOT NULL` — a
  contradiction that errors on user deletion rather than nulling. KAN-170's surface, not mine.

Waiting in `Peer-review` for another `backend-N`. Not seeking a QA or SELF path around it.

## 2026-09-11 — KAN-131 PEER REVIEW (as review_owner) — PASS

Reviewed backend-1's applied work, independently re-verified against live `wtncuzcskpigqpmnxwws`:
- `public.fn_platform_owner_id()` exists; two direct calls both return `00000000-0000-0000-0000-000000000000` (AC1/AC2).
- Live `pg_get_functiondef(public.trgfn_payment_to_ledger)`: 2 `fn_platform_owner_id()` refs, 0 `gen_random_uuid()`, 3 `ON CONFLICT DO NOTHING`, both load-bearing comment blocks (KAN-128/T-049 Invariant 4, KAN-136/T-055) present, `prosecdef=false`, `proconfig=search_path=public, pg_temp`. Live md5 `bcf6b44408a7c38fbe855b8a5572c043`.
- AC4 no-regression: user-wallet and venue-wallet `fn_get_wallet` lines verbatim unchanged.
- AC6: ledger head version `20260911120529` = committed filename `20260911120529_kan131_fn_platform_owner_id_sentinel.sql` (Canary `8aa43f9`).
- Gated combined migration `20260910090000_kan130_kan131_...sql` untouched, per T-072 sequencing.
- AC3 (end-to-end) explicitly deferred by the ticket; not attempted.

Caveat recorded: the Jira issue itself was unreachable during this review (`getJiraIssue` failed repeatedly with a transient site error), so AC text was taken from the review brief rather than read live. Every AC verified above was verified against the database and the repo directly, not against the executor's report.

Verdict recorded via `store.record_review_result('KAN-131', 18, 'backend-4', 'pass', ...)` → revision 19.

## 2026-11-02 — KAN-724 (KAN-714 B05) search/filter over events — AUTHORED, NOT APPLIED
- Seat backend-4 (Min), team Ramesseum, worktree .claude/worktrees/ramesseum-kan724 on alpha-ramesseum. No commit/push.
- Files: supabase/migrations/20261104100500_kan714_b05_search_filter_indexes.sql (491 lines),
  supabase/tests/events_p2/kan714_b05_search_indexes.sql (370 lines).
- Changed: rpc_unified_search_sectioned (games: events.search_tsv + events AND legacy filters; meetups: match stays
  on meetups.search_tsv, filters events AND legacy; tie-break score DESC, start_at, id). New partial GIN index
  events_game_public_search_tsv_idx. Not KAN-712-wrapped, so plain replace (asserted in preconditions).
- Exceptions left unchanged: rpc_search_entities / rpc_autocomplete_entities (pre-existing 42703 on sport), nearby/geo
  family (PostGIS not in harness), getnearby* (dead), no viewer/block filtering in unified search (pre-existing).
- Evidence (local /tmp/kan724_pg :54724 only): pre-image 7/7 [K] FAIL + all [=] PASS; post ALL PASS (60 checks);
  real rollback block restored md5 fe3382197842fa66564b2f62d9b754f5, data hashes identical; cluster stopped.
- Live catalogue reads refused by ops guard (D-042): inventory derived from migrations; md5 pin fails closed.
- Route: PEER (schema_change) — needs a backend-N reviewer; live apply is Memphis/ops (needs-ops).

## 2026-11-02 — KAN-724 rework: verifier C2 (not runnable from the documented chain) — FIXED
- Cause: the first run's pre-image rpc_unified_search_sectioned (and the empty section stand-ins) were installed by
  hand on /tmp/kan724_pg; nothing in the repo created them, so the documented chain died at test :177 / migration P5.
- Added (supabase/tests/events_p2/): local_harness_kan724.sql (161 lines; pre-image extracted by sed from
  baseline_schema.sql:16246-16337 + grants :36875-36877, md5 pin asserted, empty stand-ins, Supabase refusal guard),
  build_kan724.sh (59 lines; fresh cluster + full 14-step chain), datahash_kan724.sql (11 lines; read-only hashes).
  Changed: kan714_b05_search_indexes.sql Build/Run header (now 399 lines). Migration NOT changed.
- Proof on brand-new /tmp/kan724b_pg :54725 following only the header: pre-image PRE-IMAGE OK (50 PASS, 7 K FAIL);
  apply NOTICE Q1-Q3 ok, 35 probe queries identical; ALL PASS (60 checks); rollback block: 3 table hashes identical,
  fn md5 fe338219... restored, index gone; restored PRE-IMAGE OK (7 K). Numbers equal the first report. Cluster stopped.
- Not committed (orchestrator commits). Route still PEER.

## 2026-11-03 — KAN-731 (KAN-714 B12) feed / meetup notification triggers / active_stream read events — authored, local proof green, NOT applied
- Files (worktree ramesseum-kan724, uncommitted): supabase/migrations/20261104101200_kan714_b12_feed_notifications_stream.sql (937), supabase/tests/events_p2/kan714_b12_feed_stream.sql (881), local_harness_kan731.sql (433), build_kan731.sh (59), datahash_kan731.sql (17).
- Fresh PG16 /tmp/kan731_pg:54731: run1 PRE-IMAGE OK (12 K) / apply NOTICE Q1-Q3 ok, 63 probes identical / run3 ALL PASS (263) / rollback: 6 table hashes identical, 4 pins restored / run5 PRE-IMAGE OK. Cluster stopped.
- Route: PEER (backend-N reviewer). Production never touched. Pins taken from repo migration text, not live catalogue — reviewer must re-check pins against live before apply.

## 2026-11-03 — KAN-772 (KAN-718 D04) return-for-fix 1/3 — Min (backend-4)
- Commit 5abda4d272a22dc546d6ecb48a5bbb3d09317e98 on alpha-karnak (worktree kan714-karnak). Not pushed, not applied to any hosted DB.
- Converted 8 of the 34 D01 B15-open functions to events reads (migration 20261104110100). 2 proved to have no legacy read (rpc_join_game, rpc_challenge_spawn_game). The other 24 are BLOCKERs, each with a reason and an owner, in KAN718_D04_DISPOSITION.md.
- Local runs:
  - k772fix: pass=69, fail=0.
  - k772neg (no migration): pass=48, fail=21.
  - Rollback restored the function md5 and left the data md5 unchanged.
  - The divergence and drift preconditions refuse.
- D02 A2: converted 35 | infra 8 | open 18 | trigger 3. A8 still shows DELETION BLOCKED.
- Finding: _game_belongs_to_venue and rpc_booking_cancel are open in the D02 scan but are not on the D01 list.
- Route PEER. Needs a backend-N reviewer.

## 2026-11-04 — KAN-798 (KAN-718 D04 blockers 16/17/26: join/invite/link host read) — Min (backend-4)
- Commit 97369708f227f0d2823fa0ebed8f987919e15be9 on alpha-karnak (worktree kan714-karnak), 2 new files only; not pushed (Karnak pushes); no hosted access.
  - supabase/migrations/20261104110600_kan798_d04_blockers_join_invite.sql (AUTHORED, NOT APPLIED)
  - supabase/tests/events_p4/kan798_d04_join_invite.sql
- Change: host read g.creator_user_id -> events e.creator_user_id via JOIN events e ON e.id = g.event_id AND e.event_type='game'; decide keeps FOR UPDATE OF jr, g (pre-image lock set). Header/grants/owner/DEFINER/proconfig unchanged (post-check asserts).
- Pre md5: decide 7c03f929..., invite f090ca17..., mint 6ffbb7cd...; post md5: 2fcf8e73..., 265a1206..., d6f6d1f5....
- Local PG16 :54798, k788 chain + KAN-772 layer: pre-Z01 pass=48 fail=0; post-Z01-local pass=42 fail=0 (migration before and after Z01); pre-images on post-Z01 fail=39 (42703, the failure demo); kan718_d04_last_reads pass=69 fail=0; drift + creator-mismatch pre-checks refuse. Cluster removed (C5).
- Verbatim Z01 refuses at G3/G4/G6 on this chain (baseline-only indexes, realtime publication, trg_kan718_* absent; v_meetup_list reads homeless meetups cols) -> post-Z01 is a labelled SIMULATION. game_slots_left works post-Z01-local.
- Findings: (1) KAN-714 part 2 (20261105110000) redefines the same 3 functions with md5 pins on the pre-image; applying KAN-798 makes part 2 refuse — sequencing decision for po/cto. (2) Pre-existing: rpc_decide_join_request with auth.uid() NULL skips not_host (NULL comparison) — anon with a request id can approve/deny; preserved unchanged (no behaviour change), needs escalation (cto, security).
- Route PEER; needs a backend-N reviewer.

## 2026-11-04 — KAN-802 (dispatch cdispatch-9e14092a, team Karnak) — STOPPED, no commit
Asked to move rpc_meetup_invite_user / rpc_meetup_mint_link host reads from Z01-dropped meetups columns to events.
Found: both pre-images read `m.owner_user_id`, which public.meetups has never had (baseline table def; no ADD COLUMN
anywhere). Locally (build_kan788 chain, port 54802) both raise 42703 on every call, host or stranger, BEFORE Z01; no
rows written. Z01 drops neither `id` nor `owner_user_id`, so these are not Z01 blockers. Any events rewrite would
turn always-42703 into working invite/link minting = new behaviour, forbidden by the brief. No files authored.
Evidence: /Users/moataz/.claude/jobs/1d9f2532/tmp/k802/evidence.md. Cluster stopped and deleted.
Needs a po/cto decision: reclassify D04 rows 20-21 (same class as row 25 rpc_meetup_visible), or a new ticket that
explicitly authorises repairing the host gate.

## 2026-11-04 — KAN-804 (cdispatch-454f8298, sres-b40d0b7f) — STOPPED at premise, decision_required
- Both target trigger functions are SECURITY INVOKER (prosecdef=f). Clients fire them: posts has INSERT/UPDATE for authenticated (kan86:149, posts_insert_policy); game_roster INSERT for authenticated (kan86:166) under `roster_insert_via_fn` = `CURRENT_USER <> SESSION_USER`, which holds under SET ROLE / PostgREST.
- public.events has no client grant (KAN-710). Measured on local chain: the direct events read raises 42501 for authenticated in both bodies; pre-images succeed. Any rewrite inside the brief's limits changes behaviour (42501) or keeps the 42703-after-Z01 path (KAN-772 fallback). Nothing written, no commit.
- Premise otherwise holds: events carries creator_user_id/geo_location_id/area_id; parity 0 mismatches / 0 orphans over 3010 games; pre-images run pre-Z01 and fail 42703 post-Z01-local.
- Evidence: /Users/moataz/.claude/jobs/1d9f2532/tmp/k804/evidence.md. Cluster k804_pg deleted, port 54804 free.

## 2026-11-04 — KAN-804 resume (cdispatch-54c47d1c, sres-387ff919) — STOPPED on a new fact
- public.games has RLS ENABLED and ZERO policies (baseline:32378; no CREATE POLICY on games in any migration; KAN-595:40 and KAN-773 pin it). So today an authenticated invoker sees no games at all: the roster guard raises game_not_found and posts PATH 2 nulls geo for EVERY game, even when _can_view_game is true (measured, host a1 on G1). Only RLS-bypass invokers (postgres in DEFINER RPCs, service_role) see games.
- The ruling's helper with _can_view_game would therefore widen behaviour for clients. Run 1's probe had a permissive games-policy stand-in that masked this; corrected here.
- Nothing written. Evidence tmp/k804/evidence2.md. Cluster deleted, port free.

## 2026-11-04 — KAN-806 (sres-73c59c71 / cdispatch-4976566c) — kan712_update_event_shared works after Z01

- Cause: the ops path's first guard requires an ENABLED trg_zz_kan712_events_compat_mirror; Z01 seq 334 drops it, so every call after Z01 raised 55000 kan712_not_cut_over. Caller is the service_role ops/admin path (KAN712_CONTRACT.md:37; KAN718_RUNBOOK.md F5); no app/edge caller.
- Fix: supabase/migrations/20261104110700_kan806_kan712_write_path_after_z01.sql — CREATE OR REPLACE, guard only. Opens when mirror enabled OR (mirror absent AND all 42 mirror write-target columns on games/meetups gone). Stage 1, disabled mirror, partial column state still 55000. Pre-image md5 pin e25772a4..., post-check proves attrs/ACL unchanged and body byte-identical outside the guard.
- Test: supabase/tests/events_p4/kan806_write_path_after_z01.sql (standalone, phase auto-detect, PASS/FAIL lines). Fixed states: 0 FAIL; unfixed negative controls: 11 FAIL.
- Local PG16 only (port 54806, torn down). Evidence: /Users/moataz/.claude/jobs/1d9f2532/tmp/k806/. No hosted DB touched.
- Route: PEER (schema_change) — waits for a backend-N reviewer. Not applied anywhere hosted.

## 2026-11-04 — KAN-809 (cdispatch-ed0fc41e, sres-a419ec3d): rpc_update_game stale guard — authored, pushed cc8b65e4
- New overload `public.rpc_update_game(p_game_id, p_start_at, p_end_at, p_expected_updated_at timestamptz /*pos 4, no default*/, <14 existing optionals>)`. It locks events FOR UPDATE (the wrapper's lock), raises 40001 `stale_update` on a version mismatch (NULL = no check), then delegates to the existing public 17-arg function. secdef, search_path '', kan712.contract=on, owner postgres, ACL equal to the old one (no anon/PUBLIC). Not registered in kan712_wrapped_rpcs.
- Local PG16 proof (port 54809, cluster deleted): C1 repro reverts; C2 guarded B gets 40001 and the reschedule is kept; C3 the old shape still reverts, and plain updates are md5-identical before and after; C4 parity in every case; C5 only one pg_proc row added. Probe: 23 PASS post-fix; guard cases FAIL pre-fix.
- Not applied anywhere; route PEER (backend-N reviewer). Caveats: PostgREST overload pick untested locally. The full rollback_kan712.sql already aborts on this chain before KAN-809 (events trigger-set check). The kan798 migration (110600) fails its precondition on this local chain and was left out.

## 2026-11-04 — KAN-810 (KAN-761 F4): rpc_cancel_game repeat-cancel idempotency — authored, local proof done (Team Ramesseum)
- Authored in worktree ramesseum-kan724 (uncommitted; Ramesseum commits/pushes): migration `supabase/migrations/20261104110600_kan810_cancel_game_idempotent.sql` (323 lines; KAN-712 unwrap → CREATE OR REPLACE → re-wrap; inner UPDATE gains `AND is_cancelled IS NOT TRUE`, repeat cancel by host/admin returns 'cancelled'; md5 pins pre/post; rollback block), test `supabase/tests/events_p4/kan810_cancel_idempotent.sql` (198), build `supabase/tests/events_p4/build_kan810.sh` (93).
- Proof on throwaway PG16 /tmp/kan810_pg port 54810: before 16 pass / 3 [K] fail (defect), after 19/19. Signature/ACL/owner/proconfig unchanged; inner md5 e12056fd… → 89cb1823…, wrapper bf9763ac… unchanged. Cluster stopped and deleted. Production not touched.
- Owed: second-backend PEER review; phase-4 events repoint (z03:72) still separate.
- FLAG: version 20261104110600 is also used by kan798 (alpha-karnak), kan799 (alpha-habu) and kan801 (alpha-luxor); 110700/110800/110900/111000 are taken on those branches too. This is not renamed here because the brief fixed the path. The integrator must re-number it before Alpha. The proof chain did not include those sibling migrations.
