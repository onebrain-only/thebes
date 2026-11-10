# backend-1 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-1.md`. This file is a work log, not a rule source.

**Grants are STRICTER than `wallets`, not merely equal.** AC3 says "matches the `wallets` pattern
exactly". The *policy* shape does (`block_dml` `*` false/false + reads). The *grant* posture is
deliberately tighter: `charges` gives `anon` nothing at all, while live `wallets` still carries
`anon=rm`. Better than the AC asked for; the `anon=rm` on `wallets` is pre-existing looseness there,
not this ticket's.

**`service_role` can write the table directly** — `rolbypassrls=t` plus `arwdDxtm`, byte-identical to
`wallets`. So `record_charge` is the only write path by convention, not by enforcement, for that tier.
I checked whether that weakens anything and it does not: the UNIQUE index and `trg_charges_immutable`
both bind a direct insert (triggers are not bypassed by `rolbypassrls`), so a direct write gets a hard
`23505` rather than silent absorption. House pattern, no exposure. Noted, not raised.

**AC7 — met, but backend-4's "byte-identical" claim is an overstatement.** Raw md5s differ on both
files (S1 `ebcecff1…` repo vs `a78980f7…` ledger; S2 `bb362c44…` vs `c8e6360a…`), by 19 and 11 bytes.
I normalised both sides identically — strip whole-line `--`, strip all whitespace — and the
**executable content is provably identical**: S1 `327c9b1d7c55630e37d657e462efc1f2` @ 4569 both
sides, S2 `33db81a2d0b8729c3146103349357bb8` @ 1625 both sides. AC7 requires the version string, not
byte-identity: filenames carry `20260911075539` / `20260911080324` exactly, ledger names match, both
committed (`e502e82`, `1a484a9`) and clean. **Same pattern I found on KAN-188** — commentary added to
the repo file after applying. Replay is faithful; the wording in comment 10994 is not.

**AC5 re-measured myself:** `payment_intents_booking_id_fkey` = `FOREIGN KEY (booking_id) REFERENCES
venue_bookings(id) ON DELETE RESTRICT`, 3 constraints on the table, untouched.

**Verdict: PASS.** No rework. Two items recorded for others: the undocumented partial-refund caller
contract, and the stale "byte-identical" wording. I transitioned nothing — the PEER verdict is mine,
the board move is not.

---

## 2026-09-11 — PEER review, KAN-169 (settle_game organiser/sport/gross derivation, T-069)

Reviewer seat for backend-4 (Min)'s two sittings, comment 10999. **PASS, no rework.** Effort LOW as
briefed; the substance came in under it because every claim was checkable against the live catalogue
rather than against the migration text.

**Read the live body, not the files, first** (`pg_get_functiondef`, T-058). Both repo files then
matched it line for line — S1 `20260911113000_kan169_settle_game_derive_organiser_sport_gross.sql`,
S2 `20260911114500_kan169_settle_game_zero_and_negative_earnings.sql`.

**AC5 / proacl — verified two ways, not one.** `proacl = {postgres=X/postgres,service_role=X/postgres}`
— no bare `=X/` (PUBLIC), no `anon`, no `authenticated`. Cross-checked with
`has_function_privilege`: public/anon/authenticated all **false**, service_role **true**. S1 revokes
`from public, anon, authenticated` explicitly (line 227) rather than PUBLIC alone — the T-078 trap
avoided by name. S2 is `CREATE OR REPLACE` and correctly does **not** restate the revoke; the live
proacl proves it held across the replace. `obj_description` non-null, so the COMMENT survived too.
`settle_game` overload count **1** — the 5-arg signature is gone, no shadow.

**The three ruling rationales are load-bearing, and I confirmed each against `pg_constraint`:**
`wallet_ledger_amount_aed_check = (amount_aed > 0)` — so the zero-earnings guard is *necessary*, not
cosmetic; a 0.00 credit genuinely aborts the settlement. `game_settlements_gross_collected_aed_check
= (>= 0)` — justifies `invalid_gross`. `games_creator_user_id_fkey ON DELETE SET NULL` on a NOT NULL
column — justifies the `organiser_unresolved` arm the author calls unreachable-but-checked.

**Zero vs negative split — correct, and the ordering is the part that matters.** `earnings < 0` raises
`fee_exceeds_gross` at body line 121, *before* the `game_settlements` insert at 125, so no negative
`organiser_earnings_aed` is ever stored regardless of `p_finalize`. Zero settles and skips the credit
via `p_finalize and gs.organiser_earnings_aed > 0`. Checked the interaction the probes did not: a
zero-earnings settle creates `gs.id` without consuming the `('game_settlement', gs.id, 'credit')`
dedup key, so a later re-settle once charges arrive **does** post the credit. The guard does not burn
the key.

**Currency detection — the silent-sum hole is closed by the schema, which I verified rather than
assumed.** `charges.currency` is **NOT NULL**. That matters: `count(distinct)` ignores NULLs, so a
nullable currency column would have let NULL+AED rows read as one distinct currency and sum silently
into the AED-named column. It cannot. Mixed → raise, single non-AED → raise, zero rows → gross 0,
never a conversion.

**Probe evidence — I corroborated it instead of taking it.** 12 probes, count matches the table.
The baseline figure is self-proving: 999,999.00 gross at the single live `commission_rules` row
(rate 10.00, min 0.00, max null, which I read) yields fee 99,999.90 and earnings **899,999.10** —
exactly the number reported. That arithmetic only lands if the probe was executed. Post-state claims
re-measured by me independently: `charges` 0, `game_settlements` 0, `wallet_ledger` 0,
`commission_rules` 1. Nothing was mutated; the probes were genuinely rolled back. `I-control` and the
C/D mutual-absence design are real controls, and probe B doubles as the "can the path execute at all"
check my own contract demands (it proves `status=settled` rather than KAN-138's 42804).

**Three things recorded, none of them grounds to fail:**

1. **Re-settle with *changed* charges diverges settlement row from ledger.** `gs.id` is stable across
the upsert, so `on conflict do nothing` absorbs the revised credit — the row can say 500 while the
ledger holds 108. Probe H only re-settled with charges *unchanged*. This is not a regression: AC4
mandates the dedup and the description explicitly rules a revised derived gross "benign". Reconciling
a revised amount needs a compensating row, which is a different ticket.
2. **AC7 is live and dangerous, not merely noted.** KAN-138's `9d855a5` sits unapplied in Peer-review
reproducing the pre-T-069 body verbatim. Landing it silently restores the 5-arg function and the
bypass. Flagged correctly to po/team-lead; not the implementer's to close, and not mine.
3. **Filename vs ledger version drift, benign.** Files carry `20260911113000`/`20260911114500`; the
ledger stamped `20260911110743`/`20260911111006`. Those are `apply_migration`'s own UTC stamps —
15:07:43 and 15:10:06 +0400, which sits exactly between the file mtimes (15:05, 15:09) and the
comment (15:12). Timeline coheres; names match. Unlike the rest of this batch, whose filenames and
versions agree, so worth a line at rebaseline (T-068) — not a defect.

**I did not execute `settle_game`.** It writes `game_settlements` and `wallet_ledger`; running it
live is user-data mutation on existing money tables, reserved to the CEO (019). Static verification
plus catalogue facts plus corroboration of the author's rolled-back probes was sufficient, and I say
so rather than implying I re-ran them.

**Transitioned nothing, changed nothing, posted no Jira comment** — the brief was report-only. The
PEER verdict is mine; the board move is not.

## 2026-09-11 — KAN-189 PEER review (Shu)

PEER: **PASS**. Reviewed as resolved `review_owner`; did not author, did not touch
supabase_admin's default, did not touch KAN-194.

Independently re-verified against live `wtncuzcskpigqpmnxwws` (not from the report):

- `pg_default_acl`, schema `public`, `defaclobjtype='f'` — postgres-grantor is now
  `{postgres=X,authenticated=X,service_role=X}`: no `anon`, no bare PUBLIC.
  supabase_admin-grantor unchanged, still `{postgres,anon,authenticated,service_role}`.
- Own disposable probe function (created, `proacl` read directly, rolled back):
  `{postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres}`,
  `has_function_privilege('anon',...)` = false. No `=X/postgres` bare-PUBLIC entry.
- Second probe with an explicit `GRANT EXECUTE ... TO anon` → `anon_exec` = true.
  The intentional anon-callable-RPC path is intact (AC4's rule is true and correctly
  scoped: forward-only, postgres-grantor only).
- Pre-existing functions `fn_platform_owner_id`, `rpc_get_friends`,
  `rpc_get_friend_suggestions`, `rpc_potential_vibes` all still carry
  `{=X/postgres,postgres=X,anon=X,authenticated=X,service_role=X}` — untouched,
  confirming forward-only AND making the probe discriminating: pre-fix functions
  carry the bare-PUBLIC entry the probe no longer gets.

Both probes were wrapped so the transaction aborts after inspection — nothing left
behind. Verdict recorded via `store.record_review_result('KAN-189', 11, 'backend-1',
'pass', ...)`; task revision 11 → 12. No Jira transition, no ownership change —
Orchestrator handles closure.

## 2026-11-02 — KAN-775 (KAN-718 D07) series occurrence uniqueness — AUTHORED, committed 00564a7ced8c04ad4429bae6cef347f275994f62 on alpha-habu (not pushed, not applied)
- Migration 20261104110300_kan718_d07_series_occurrence_unique.sql: immediate AFTER ROW guard (events start_at / games series_id,event_id), same advisory key as KAN-710; legacy index kept; KAN-710 deferred backstop kept.
- Test supabase/tests/events_p4/kan718_d07_series_unique.sql: 35/35 PASS on local chain + D07; 5 [K] FAIL without D07 (W1 loses occurrence_time_taken, W4b statement-time refusal). Idempotent re-apply proven; pre-check refusal proven (index absent).
- Follow-ups: withdrawal ticket must pre-check D07 live; fn_generate_game_series_occurrences + kan694 RPCs still read games.start_at (slated). Local PG only; no remote DB touched.

## 2026-11-02 — KAN-722 (KAN-714 B03) rating/host-metrics views on public.events — DONE locally, awaiting PEER
- Commit `c6e80c4d87a4a85bc6518fdbf08287cdf1c994a7` on `alpha-karnak` (worktree Dabbler/worktrees/kan714-karnak), 3 files only: migration `20261104100300_kan714_b03_views_rating_host_metrics.sql`, test `supabase/tests/events_p2/kan714_b03_rating_views.sql`, rollback `supabase/tests/events_p2/rollback_kan714_b03.sql`. Not pushed, not applied remotely.
- v_rateable_after_game + v_host_weekly_metrics repointed to events (join id + event_type='game'); v_game_rating unchanged (reads games.id only). Owner views; ACL/owner/reloptions asserted unchanged; no grant on events.
- Local postgres@16: RED 18/25 (7 expected fails) without, GREEN 25/25 with; rollback back to pre 25/25, fingerprint 7873d6fb... equal; second run refused by drift pin; stage guard demonstrated failing.
- CONFLICT: Luxor's 20261105100000 aborts after this file (v_host_weekly_metrics dep pin 49ec8d... now 0c619a...). Not fixed — owner's call.

## 2026-11-02 — KAN-725 (KAN-714 B06) meetup read RPCs -> events — DONE locally, commit 3514b6be on alpha-karnak (not pushed)
- rpc_meetup_card + rpc_meetup_attendees repointed: shared columns from events (id + event_type='meetup'); description/location_name/host_actor_id stay on meetups. None KAN-712-wrapped; caller rpc_meetup_update_kan712_inner unchanged (C1 pass).
- rpc_meetup_my left unchanged: pre-image raises 42703 (nonexistent meetups columns), no app caller. Needs separate ticket via po.
- Local harness only (b3713 clone): RED post 18/8, pre 26/0, GREEN post 26/0, re-apply refused by pin, rollback -> pre 26/0 fingerprint equal, rollback re-run refused.
- No Jira change, no push, no remote DB. Awaits PEER (backend-N) review.

## 2026-11-02 — KAN-728 (KAN-714 B09) booking reads — Shu
- Commit `44a3494d39309839927529ddb94d54f45be042ff` on `alpha-karnak` (worktree kan714-karnak), not pushed. Local harness only (PGPORT 54714, clones of `b3713b`), no Jira, no remote DB.
- Changed: `rpc_booking_hold_for_meetup` only (owner_user_id 42703 -> creator from events). Not wrapped.
- Pinned unchanged: `_slot_conflicts_game` (INVOKER, E4-blocked), `rpc_booking_hold_for_game` (+inner, KAN-712 wrapped; unwrap needs DROP), `rpc_booking_cancel`, `_game_belongs_to_venue`.
- Evidence: RED post 14/11, pre 25/0, GREEN 25/0, re-apply refused by pin, rollback -> pre 25/0 fingerprint equal, rollback re-run refused.
- Open: cto decision on `_slot_conflicts_game` (has_table_privilege branch / DEFINER / stay on mirror). Route PEER, needs a backend-N reviewer.

## 2026-11-03 — KAN-730 (KAN-714 B11, msg_* readers onto events) — committed locally, not pushed
- Commit 914e486a on alpha-karnak (worktree Dabbler/worktrees/kan714-karnak). Migration 20261104101100_kan714_b11_msg_functions.sql (591), test events_p2/kan714_b11_msg_functions.sql (1018), rollback_kan714_b11.sql (404).
- Changed: msg_evaluate, msg_authorize, msg_my_conversations (SECDEF, superuser owner; not wrapped). Pinned: msg_game_conversation, msg_user_unavailable, msg_system_game_trg.
- Local harness kv730r (from b3713b): RED post 108/24, pre 132/0, GREEN 132/0, re-apply refused by md5 pin, rollback -> pre 132/0 with fingerprint equal (c3993faa...), rollback re-run refused.
- Open: harness kind_check stub (game only) replaced inside the test's rolled-back tx; production md5s/callers not verified. Needs PEER review by another backend-N. No Jira or push done (per brief).

## 2026-11-03 — KAN-733 (KAN-714 B14, series RPC reads) — for team Karnak
- Committed `3f21e3ab17f29f3e7a021ef4209302237791574a` on alpha-karnak (worktree kan714-karnak). Not pushed. Not applied to any hosted DB.
- The three series RPCs are KAN-712-wrapped. Only the `*_kan712_inner` bodies were replaced, in place. Wrappers, ACLs and `kan712_wrapped_rpcs` are byte-identical.
- Local b3713b clone results: RED post 167/22, pre 189/0, GREEN 189/0, after rollback pre 189/0. Fingerprint `ca37ec03…` was the same in every run. A re-apply is refused and a second rollback is refused.
- DECISION open for cto or the owner: does the in-place inner replacement satisfy the KAN-712 "unwrap/wrap only" rule, given that test group K proves the round trip gives the same end state?

## 2026-11-03 — KAN-728 (KAN-714 B09, _slot_conflicts_game decision) — for team Karnak
- Pushed alpha-karnak `50fafe21796484e4869b9e8d39682618b52a8e98` (my work in `0d1b0966`, then merge of origin/Alpha `d824a4f7`). Not applied to any hosted DB.
- `_slot_conflicts_game`: has_table_privilege branch (option a). Privileged callers read time and cancelled state from events. Other callers read the games mirror. The language changed from sql to plpgsql, because a sql version raises 42501 (C3b proves it). The game hold is unchanged and recorded as an accepted exception under the KAN-712 wrap.
- Fresh b3713b clone: pre 35/0, RED post 17/18, GREEN post 35/0, after rollback pre 35/0. Fingerprint `fe9a7f4d…` was the same in every run. A re-apply is refused, and so is a second rollback.
- Harness fact: games has RLS with zero policies, so `authenticated` sees no games and the mirror branch is always false for it. To exercise the mirror over real rows, the test uses a BYPASSRLS probe role that it creates and then rolls back.

## 2026-11-04 — KAN-856 (KAN-718 F3, getnearbymeetups) — for team Karnak
- Pushed alpha-karnak `cd2639ed14f55a7c47eac85cae49798c615c54f4`. Two new files only: `supabase/migrations/20261104112200_kan718_f3_getnearbymeetups.sql` and `supabase/tests/events_p4/kan718_f3_getnearbymeetups_test.sql`. Not applied to any hosted DB.
- REWRITE, not retire: the app calls it (supabase_config.dart:200, then supabase_meetup_datasource.dart:37). The new body reads only m.id and m.event_id from meetups. Everything else comes from events and geo_locations. The signature is unchanged.
- Attribute change worth reviewing: INVOKER became DEFINER. The body now checks can_view_owner on events, following the meetup_counts pattern. The reason: events has no client grant, and an INVOKER draft raised 42501 for anon (observed).
- Local throwaway PG16 chain, built as build_kan851.sh does, plus the baseline pre-image. TAP run under `prove --exec psql`. pg_prove and pgTAP are not installed. RED: 8 of 9 tests failed. GREEN: 9 of 9 passed. A re-apply is refused.

## 2026-11-04 — KAN-859 (KAN-718 F6, DROP retired meetup RPCs) — for team Karnak
- Pushed alpha-karnak `8d4c7443f0d9c86a77791553cc7982007a1be149`. Two new files: `supabase/migrations/20261104112400_kan718_f6_drop_retired_meetup_rpcs.sql` and `supabase/tests/events_p4/kan718_f6_drop_retired_meetup_rpcs_test.sql`. Not applied to any hosted DB.
- C1: no caller. lib/ and supabase/functions/ have 0 hits. test/ has one static test that reads the text of 20260915120000. migrations/ has the baseline definitions and the hardening ACL lines only.
- The guard refuses in three cases, each shown locally: a view dependent, another function's prosrc naming one of them, and a drifted body. The rollback block restores both md5 pins and the ACL.
- Local chain (build_kan851 green path + baseline pre-image): pre phase 5/5 then 0/3 post; after apply, post 3/3 and pre 1/5. A re-apply is refused. Fingerprint: pg_proc dropped by 2, nothing else changed.
- Found: version 20261104112300 is taken by kan718_f2 on another branch. 20261104112200 is used twice (f1 and f3) across refs. The b15 coverage probe and the READ_MANIFEST rows 20-21 still list both functions as present (F8).
- Needs PEER review by a backend-N.

## 2026-11-04 — KAN-872 (Backend F12, supports KAN-865) — committed locally, not pushed
- Commit c4034793734235e66a737eed2d70b7903aa20a91 on backend-f12-kan865-deir-el-bahari (worktree Dabbler/worktrees/kan784-deir-el-bahari).
- Migration supabase/migrations/20261105120000_kan865_events_retention_export_rpcs.sql: retention_cleanup_own_events(timestamptz), export_own_events(); SECURITY DEFINER, search_path '', REVOKE PUBLIC+anon, GRANT authenticated. Plus 2 constants in supabase_config.dart.
- Local only (cluster port 54872, now stopped). C1–C6 PASS. Logs: ~/.claude/jobs/a2a56da6/tmp/kan872/{apply_kan872,red,green,analyze}.log.
- Limitations: harness chain stopped at B03 (KAN-722 v_game_rating pin drift, not mine); local postgres is superuser (prod is BYPASSRLS non-superuser).
- No remote writes. Route: PEER (backend-N reviewer).

## 2026-11-04 — KAN-881 b06 drift re-pin (files only)
Worktree kan881-deir-el-bahari. Migration 20261104100600: card pin -> cb4265a2..., rpc_meetup_my absent-tolerant in pre-pins, temp capture (to_regprocedure), post md5, and both counts (2 + exists). Rollback: post card md5 -> cb4265a2..., rpc_meetup_my absent-tolerant, header updated. No DB touched, nothing committed. Returned to orchestrator.

## 2026-11-05 — KAN-883 (b12 trg_meetup_rsvps_notify pin)
- Worktree kan784-deir-el-bahari, branch staging-deir-el-bahari, commit 6c3746535339c002fcb8840cf8c2a3d83556a3b1 (not pushed, not applied).
- Pin row now accepts 55efefd5 (authored) or 0dbf2b3c (prod, comment-free) via a CASE on the live md5(prosrc); per CTO ruling 2026-11-05. Function body block md5 unchanged (2320de56...). New file md5 12a129e540da732ff07eb06b0dca15c3.
- Apply-order check: decided order OK; filename order fails identically at HEAD (pre-existing KAN-788). No dart tests read the file; no SQL parser installed; no DB touched.
- Follow-up flag: local_harness_kan731.sql:422 and kan714_b12_feed_stream.sql:858 still assert 55efefd5 only (out of scope, untouched).
