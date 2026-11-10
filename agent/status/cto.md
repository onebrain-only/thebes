# cto status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/cto.md`. This file is a work log, not a rule source.

the easy miss — **definer alone would CREATE an oracle that does not exist today.** While invoker they
leak nothing the caller could not already read; definer + caller-supplied uuid + anon EXECUTE is
exactly the `T-070` oracle `KAN-188` closed for their five siblings yesterday. Ordering is not free:
definer-first opens the oracle, relocate-first leaves them answering false. Neither intermediate state
may exist. §6d caller sweep runs first.

**Operative constraint recorded: no `venue_admin` or `moderator` grant may be issued until this lands**
— today the grant silently does nothing and the symptom surfaces nowhere near `role_grants`.

**`TO authenticated` deviation: approved, and better than what I ruled.** Amendment 2 ruled the
predicate and was silent on role scope. Same 0-row outcome either way, but it removes an anon-reachable
definer invocation and moots the recursion question for `anon`. No objection at PEER.

**Methodological note worth keeping:** `backend-5`'s probe nearly cited the wrong evidence — both
helpers returned false, which proved nothing, because the uuid tested held `admin` and they would
return false on the data regardless. The real evidence was the raw invoker read, true before / false
after. It caught itself by asking what else the false could mean. **Fourth probe-that-passed-for-the-
wrong-reason today, third caught by its own author** — the §12h discipline is propagating without
being invoked by name, which is the outcome a convention is for.

## 2026-09-11 — T-082: the parked KAN-138 file, and what retiring a gate leaves behind

**Source:** `po-zero-lifecycle` flagged commit `9d855a5` directly and urgently. Substance correct;
three framings wrong, one of them understating the hazard badly.

**Recorded:** `DECISIONS.md` **T-082** (Accepted). **Note — numbered T-070 on first append and
renumbered:** the corpus grew from 9,366 to 11,208 lines overnight (other seats appending) and
`T-070`–`T-081` were taken. `grep -oE '^### T-[0-9]{3}' | sort | uniq -d` now returns empty.
**Check the high-water mark before appending; do not assume yesterday's tail.**

**Verified myself, read-only:** `9d855a5` = 2026-09-07 10:59:22 +0400, one file, 303 lines, commit
body "AUTHORING ONLY — awaiting cto's G-028 confirmation". `git diff 9d855a5 -- <path>` **empty**;
file unchanged. Line 170 declares the 5-param signature, line 191 the defective gate.
Live `pg_proc`: **`settle_game(uuid,boolean)`, one row** — KAN-169/T-069 applied, 5-param gone.

**The correction that matters.** Replay would **not** revert KAN-169. Signatures differ, so
`CREATE OR REPLACE` **creates a second overload** beside the hardened one, which is left untouched
along with its revoke. And `pg_default_acl` for `public`/`f` grants **`anon=X` and
`authenticated=X`** (both `postgres` and `supabase_admin` as grantor) — the file has **zero
executable GRANT/REVOKE** — so the replay product is an `anon`-reachable privilege-escalation
function. **Worse than the pre-containment state**, because the containment protects a different
object.

**Superseded my own T-068 Amendment 2 §7** (in T-082, not by editing T-068): the "KAN-138/KAN-128
ordering → replay restores the uncast body" bullet was right on 2026-09-10 and is now wrong — it is
not an undo and sort order is irrelevant. Corrected in place of record, original left standing.

**Corrected the G-028 framing.** `G-028` is a `CONTRACT.md` rule, **not a per-ticket approval
token** — "close G-028 for KAN-138" is not an available act. The commit waited on G-028's *routine
per-apply confirmation*, **retired by Wave 5 on 2026-09-08**, one day later. So the 4-day gap is
**orphaning, not a neglected sign-off** — which decides the remedy: no sign-off was ever coming.

**Ruled.** (1) File is dead, superseded by KAN-169/T-069, never to be applied; must say so *in the
file* — annotate or delete, I did not rule between them, that is the migration tree's owner's call.
Not authorised: applying it, `db push`, editing its SQL body, any ledger write. (2) Standing
safeguard — **retiring a gate is incomplete until the queue behind it is re-routed or killed.**
Same shape as T-068 Am2 §7's third replay mode. I did **not** implement a sweep and said so;
**whether other artefacts were orphaned by the same Wave 5 retirement is NOT DOCUMENTED — I checked
one commit, not the population.** That ticket is `po`'s.

**Verified so it is not assumed wrong later:** backend-4's 899,999.10 AED exploit demo left **no
residue** — `wallet_ledger` 0 rows/sum 0, `game_settlements` 0/0, `wallets` 0.
**Did not claim a gap that is not there:** `anon-allowlist-check.yml` **does** gate anon-executable
SECURITY DEFINER functions (`scripts/ci/check_anon_function_grants.sh`, with a disposable-Postgres
self-test). But it is a **CI gate on push/PR** — nothing applied directly to the database passes
through it, so it would not have caught this. Whether it reads the live catalogue or the repo I did
**not** verify and said so.

**Not done, deliberately:** no migration file edited or deleted, no SQL authored, no production
change, no Jira, no ticket transitioned, no sweep performed, no ruling on `pg_default_acl`'s blanket
EXECUTE (flagged as far larger than this ticket and explicitly not settled inside it).
**Effort feedback:** worth the high-effort pass. Three of the reporter's framings were wrong and the
real mechanism — overload creation plus default ACL — is invisible unless you check both `pg_proc`
for the live signature and `pg_default_acl`. A low-effort pass would have ratified "it reverts the
fix" and missed that the replay lands `anon`-executable.

## 2026-10-08 — favourites shape ruling
Ruled activity_favorites keyed on public_activities.id; see handback.

## 2026-10-09 — KAN-451 observation report (read-only)
Wrote /Users/moataz/.claude/jobs/7f6ff1a6/tmp/kan451-report.md. Live DB evidence from Memphis, not re-run by CTO; code cross-checked at origin/Alpha b1c051a3. Findings: no messaging store; follows gate no communication; friend/vibe RPCs dangling and anon-executable; rpc_block_user overloads inconsistent. No files or DB changed.
- 2026-10-14 Khnum: Messaging Worker+D1 free-tier deployment PLAN delivered to orchestrator (reply only; read-only on origin/Alpha; no resource created, no secret seen). Flags: no CORS in Worker src; KAN-505 msg_authorize is a prerequisite; app.msg_hmac_secret as a DB GUC is readable to any role that can current_setting — recommend Vault.
- 2026-10-14 Khnum: realtime game-chat delivery plan returned to Orchestrator (read-only, origin/Alpha). Candidate msg_notify SECURITY DEFINER via user token accepted; system-line wakes from msg_system_notify trigger; payload {type,conversation_id,seq?}; 5 tickets; CEO decisions: public-access off timing, staging-vs-prod T-run, throttle.
- 2026-10-15 cto: KAN-496 open-to-everyone technical plan (read-only, origin/Alpha). Rulings: promote the single staging Worker+D1 to production (a second Worker on one Supabase project splits messages and the system-line trigger can reach only one); add app.dabbler.pro to CORS; mode 'all' already exists in msg_evaluate; Home list via new Supabase RPC + last_activity_at stamped by msg_notify (no Worker cost); kill switch = MESSAGING_ACCESS_MODE=off; recommend Workers Paid before launch. Delivered in reply; tickets for po to write.

## 2026-10-20 — KAN-581 R2 images readiness report (read-only)
- Read KAN-494/495/502/581, Brief v1.0, origin/Alpha 82db0c74 workers/messaging + docs/messaging, pm-ledger cloudflare-messaging-approval (line 245), design export §12/Q1-Q12.
- Finding: no R2 binding/code/migration exists; only operating approval is Workers+D1 free (2026-10-14), R2 explicitly excluded; no newer approval found. No approved image limits. Live not inspected (wrangler not installed).
- Output: report handed back to orchestrator; nothing created, no ticket moved.

## 2026-10-20 — dreq-2a502389 (KAN-580 receipts UI unblock)
Ruled: (a) Luxor lands receipt components in alpha-ds, Ramesseum bumps pin; (b) Ramesseum authors Worker GET summary+recipients routes (sender-of-seq check in Worker; recipients fn EXECUTE service_role only); (c) DS || Worker routes in parallel, Memphis applies 150000 then 160000 then one Worker deploy, then pin bump + render; (d) stays under KAN-580, no new ticket. No files changed besides this entry.

## 2026-10-21 — KAN-580 receipts migrations review (read-only)
Reviewed 20261020150000_kan580_msg_receipts.sql and 20261020160000_kan580_msg_receipt_recipients.sql. Both Class A, APPLY. Flagged follow-ups: unbounded p_through_seq can poison own watermark permanently; msg_receipt_summary exposes aggregate counts for any seq to any member (Worker filter bypassable via PostgREST); caller-controlled p_access_mode semantics not verified. No SQL run, no files changed beyond this entry.
- 2026-10-21 dreq-9882ee33: ruled YES on DS DabblerMessage sender maxLines 1 + ellipsis; KAN-620 passes with one skip that names the DS ticket key; unskip when the DS pin bumps.

## 2026-10-22 — Migration classification for Memphis (KAN-585, KAN-611 x4, KAN-621)
Read-only review of alpha-habu 61e2e186 + 63fd9c33. KAN-585 and KAN-621 = A (additive). KAN-611 file 1 = A; files 2-4 = B (RENAME + replace + ACL tightening on rpc_create_game). No anon caller of rpc_create_game in lib/ or supabase/functions/. Ruling: idempotency_tests.sql may run on live only as single BEGIN..ROLLBACK batches with seeded test accounts; otherwise X1 + read-back. Nothing applied.

## 2026-10-22 — KAN-611 / KAN-584 ruling (Memphis ops batch)
- KAN-611: live profile-keyed version stands; Habu four-file split (61e2e186) withdrawn, not to land on Alpha; no delta required. Evidence: habu split pre-checks RAISE when *_legacy_v2 exists (…120200:24-26, …120300:23-24) so it cannot apply on live.
- KAN-584: class A additive (new table, RLS, own-row policies, anon revoked; file :9-34). May apply under standing additive approval before KAN-585 with pre-checks listed in report.

## 2026-10-26 — ceo-kan646-edges (Personas S2–S6 parallelism ruling)
Read KAN-645..649 and alpha-644-karnak S1 migration. Ruling: remove 645->646 (contract fixed in 645 brief; 646 fixtures built as owner role, S1 trigger blocks only anon/authenticated); split 648 into 648a (intention model/state/ARB/copy/RPC constant, start now) and 648b (final wiring + evidence, after 645+647); keep 647 independent of 645; 649 stays tail. Risks: function-ownership partition 645 vs 646; ARB/l10n generated files shared by 647/648a; migration timestamps must be distinct and 646 must not CREATE OR REPLACE rpc_onboard_*. No files or Jira touched.

## 2026-10-27 — four rulings for next wave
T-097..T-100 appended to dabbler-docs/DECISIONS.md (offline cache, squad SELECT policies, game_series, flutter_map+OSM). No DB writes.

## 2026-10-27 — KAN-673 ruling (read-only)
- F2: REVOKE alone insufficient (SECURITY DEFINER, no owner check, authenticated can write any profile's sport_profiles; baseline :11990-12003). Ruled: REVOKE PUBLIC/anon + CREATE OR REPLACE same signature adding `user_id = auth.uid()` owner check.
- F1: deferred to its own ticket. profiles_profile_type_check (baseline profiles table) forbids 'organiser', so actor_is_organiser (:2040-2048) and policy at :25102 are constant-false; fixing widens authorization across host/challenge/meetup paths — needs a separate cto-shaped ticket + cpo on who an organiser is.
- Single backend ticket; PEER (schema_change).

## 2026-10-27 — KAN-673 F1 ruling (actor_is_organiser), read-only
- Ruled: rewrite actor_is_organiser body to persona_type='organiser' AND is_active (CREATE OR REPLACE, same signature, revoke anon); one backend ticket, one migration. Meetup + challenge gates stay organiser-only pending cpo; game hosting gate is advisory only (capability map), no enforcing caller found. v_actor_context.organiser_profile_id (baseline :25102) needs the same fix in the same migration.
- Open for cpo: whether meetups/challenges should be organiser-only; whether 'host' persona counts.

## 2026-10-27 dreq-0ca2 (KAN-644/646)
- D1: trgfn_contributor_sports_check CASE in DECLARE resolves NEW.profile_id/NEW.id on wrong table -> every profiles/sport_profiles write fails at COMMIT. P0, backend CREATE OR REPLACE with IF branches, PEER.
- D2: J1/J4 expectation not changed; legacy control also not_found => fixture defect; fix fixture first.
- choose_actor anon revoke P2; rpc_challenge_create sport P1 (shape ruling needed).
- Decision file: /Users/moataz/.claude/jobs/c49d2414/tmp/dreq-0ca2.md

## 2026-10-27 — KAN-678 shape ruling (read-only)
Ruled: (B) explicit 5-arg overload `rpc_challenge_create(p_profile_type text, p_title text, p_visibility text, p_sport text, p_description text)`, p_sport REQUIRED (no DEFAULT — a defaulted trailing arg makes 4-arg calls ambiguous against the surviving 4-arg function). Param is a sport KEY (text), not p_sport_id: the trigger resolves `sport_id` from `challenges.sport` text and recomputes on INSERT regardless (old is null), so a passed sport_id is overwritten. Rejected (A) defaulted param, (C) derive from organiser. Old 4-arg overload kept (no DROP), anon/PUBLIC revoked. Evidence: baseline 20260829080500 L19774 trigger, L36151 anon grant; zero callers in lib/ and supabase/functions.

## 2026-10-30 — dreq-4777f8ba (KAN-685) ruling
Ruled: Memphis authors, commits, pushes, applies the Dabbler-Test Player->Contributor data migration end to end in /Users/moataz/.claude/jobs/1ee27200/worktrees/kan685 (alpha-kan685-karnak); constraints: idempotent, keyed on both ids, before-state snapshot, exact rollback, isolation probes; C3 app check by QA (Codex) after apply. Nothing applied by cto.

## 2026-10-30 — dreq-e2a1e56f KAN-685 (decision only, nothing applied)
Ruled YES to scoped onboard=false -> persona/intention -> organiser insert -> onboard=true in one transaction for profile 5eeb4305 only; not a global bypass (uses the guard's own unfinished-sole-row path). Preconditions: read-only probe that primary_sport=4fd36109 is in interests, has a sport_profiles row, and every sport_profiles sport is in interests; else abort, no invented rows. Post-commit rollback is impossible by design (contributor->player raises persona_conversion_blocked); rollback = in-transaction abort only. Evidence: 20261026100000_kan644_personas_s1_schema_guards.sql lines 77-127, 139-164.

## 2026-11-04 — KAN-815 ruling (supports KAN-798), read-only
rpc_decide_join_request host guard fails open on auth.uid() NULL (20261105110000:1536); chain grants anon EXECUTE (baseline 36235) with no REVOKE in any migration; prod revoke 2026-09-10 out-of-band only (SCHEMA.md §2g.1). Ruled: both null-guard + REVOKE PUBLIC/anon, one class-A migration. No edits, no SQL, no tickets.

## 2026-11-04 — KAN-842 ruling (kan711 backfill, step 5)
- Read-only review of backfill.sql (md5 d6064b8d…), agent/scripts/sql_hook.py:293-300,497-541, agent/execution/sql_snapshot.py.
- Ruled: file DDL additive; run = class C; run IS step 5, validate_links is NOT (later schema step, PEER).
- Finding: hook is_probe() rejects any probe whose text contains "commit" incl. procedure body :260 and DO-block comment :341 -> probe must omit section 4 and that comment; real apply sends file verbatim.
- Run mechanics: prefer 4 separate SELECT kan711_events_backfill_batch calls (games 2, meetups 2); lone CALL behaviour under execute_sql not documented.
- No SQL run, no file edited. Returned to calling session.

## 2026-11-04 KAN-843 (Memphis ops)
Classified step6 20261103100000_kan712_events_write_contract.sql (md5 4e6431f6...): class A, no existing function replaced, inert (no trigger, no wrap). GO conditional on steps 1-5 applied and kan711 parity green. Read-only; nothing applied.

## 2026-11-04 — KAN-844 step-7 4d block (run_seed_meetup_template)
Ruling (c): capture prod-drift function verbatim in a repo migration, then allowlist it in a revised step-7 4d. No DROP/rewrite unless dumped body shows UPDATE/dynamic SQL/guard bypass. Author: backend-N under new supporting ticket; PEER required (schema_change). Ruling file: /Users/moataz/.claude/jobs/b9b99f0a/tmp/kan844-seed-ruling.md. Caveat: local cutover copies md5 0b2d4b0e, not origin/Alpha 17b88c87; 4d to be re-checked against that file.

## 2026-11-04 — KAN-845 (Memphis, apply KAN-811 steps 8-11) — STOPPED before step 8
- Step 8 file 20261104100000_kan713_access_helpers.sql (md5 3686f8a8 verified) contains `DELETE FROM public.kan713_preimage WHERE kind IN ('function','policy');` at line 127, plus a persistent `CREATE TABLE IF NOT EXISTS public.kan713_preimage` (line 112). Brief's STOP rule fires on DELETE. Nothing executed against production; steps 8-11 not applied. Needs a ruling that the DELETE on the migration's own preimage table is acceptable (or a file revision) before re-dispatch.
- 2026-11-04 10:07Z follow-up after Memphis ruling: public.kan713_preimage does not exist in prod (snapshot skipped); step 7 confirmed (5 trg_zz_kan712_* enabled 'O', run_seed_meetup_template present). Pre-image /Users/moataz/.claude/jobs/5b44f4da/tmp/kan845/preimage-8.sql. Step 8 probe execute_sql returned "confirmation expired after 2 minutes" (human gate, unanswered) — not executed. Stopped; steps 8-11 NOT applied.
- 2026-11-04 10:41Z KAN-845 re-dispatch: step 8 full probe REFUSED by sql_hook "deny:grant-to-public" (never-list). Nothing applied; steps 8-11 not run. Earlier 10:08:09Z partial probe (sections 1-2, BEGIN..ROLLBACK) was in fact allowed by the hook as "probe" even though the connector returned "expired".

## 2026-11-04 — dreq-fd5f4a36 (KAN-845 step 8)
Ruled option (b): a narrow sql_hook carve-out allowing EXECUTE to anon/authenticated/service_role on the four kan713_meetup_* helpers only. Step 8 unchanged. Reason: the policies apply to all roles (baseline :32534, :32570), so without EXECUTE every anon meetup query errors. The hook change is SYSTEM_MAINTENANCE. Record: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-fd5f4a36.md. No prod writes.

## 2026-11-04 dreq-5f635fe5 (KAN-845)
Ruled: Memphis submits `blocked` and releases, no workaround; dreq-fd5f4a36 option (b) stands; hook carve-out is SYSTEM_MAINTENANCE, scheduling left to Orchestrator/CEO. Evidence: grep -c kan713 agent/scripts/sql_hook.py = 0. Nothing run on prod. File: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-5f635fe5.md

## 2026-11-04 dreq-a6450bc9
Verified f936954 sql_hook KAN-845 carve-out (line 168, 23 tests OK). Ruled: Memphis resumes KAN-845 step 8 on unchanged 523c389a file, probe/apply/postcondition, steps 9-11, Jira comment. Decision at /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-a6450bc9.md. Nothing run on prod.

## 2026-11-04 — KAN-845 step 11 ruling
Ruled: Memphis may apply 20261104110000 (probe, run, read-back) before 20261104100300; KAN-722 guard not amended. Evidence 523c389a 110000:37-396, 100300:60-90. Ruling at /Users/moataz/.claude/jobs/b9b99f0a/tmp/kan845-step11-ruling.md. Prod untouched.

## 2026-11-04 — dreq-8ae9bcfa (KAN-718)
Ruled: old-client compat = C (keep legacy games columns until lib/ reads ship + old builds age out); meetups description/location_name/is_indoor retained as subtype columns (slate 47->44); KAN-718 submit blocked + release, keep f2485ae5; 11 follow-ups listed for PM. Decision file /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-8ae9bcfa.md. No prod/migration/code/Jira touched.

## 2026-11-04 dreq-9da13118 (KAN-865)
Ruled (a): KAN-865 blocked on a supporting backend ticket (own-events retention RPC + export read object + config constants). Ruling: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-9da13118.md. Read-only, no prod touch.

## 2026-11-04 dreq-ffef0d16 (KAN-854)
RETIRE accepted over literal REWRITE for get_nearby_games x2; verified games lacks lat/lng (baseline :22863), lib callers dead, migration has no DROP/GRANT. Cleared for PEER backend review as-is. Decision: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-ffef0d16.md

## 2026-11-04 dreq-1fb4de80 (KAN-861)
Ruled: KAN-854 canonical d61226b3 (F1 @112500), Luxor reverts e4890a9e; KAN-858 canonical d9a65dff (patch-identical to 0c4bcb04); 112200 = F3; datasource = KAN-715 v_game_card at 2 sites + KAN-863 compat at other 9, stream stays removed. No renames, no new tickets. Answer: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-1fb4de80.md

## 2026-11-04 dreq-0f6e9434 (KAN-861)
Ruled Z01 shape: option A, mirror CREATE OR REPLACE inside Z01 (games half kept, meetups half removed), seq 334 retained, only games.search_tsv dropped (~22/44), DROP FUNCTION x3 no CASCADE. B rejected (violates ruling 1(C)). Stale d03 scan test -> KAN-861/backend-3; schema_migrations read-only check -> backend-3 now, re-run by F9 applier. Answer: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-0f6e9434.md. Nothing applied.

## 2026-11-04 dreq-5087907b (KAN-865)
Ruled: option (a) via a new additive RPC export_own_game_history(); retention differences accepted; identical = same keys and intended rows; asker does local partial work and lands it after the RPC. Ruling: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-5087907b.md

## 2026-11-05 dreq-983521ce
Ruled KAN-592/KAN-639 resolveComposerOrigin conflict: keep KAN-639 2-param version; drop KAN-592 promotion (dead, composer never builds allocated). Habu rebases; Memphis re-integrates. File: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dreq-983521ce-decision.md. Jira not read (low effort).

## 2026-11-05 — KAN-847 messaging prerequisites ruling
Ruled: apply kan563/558/559/595 + kan579/580(x2) as one prereq ticket in timestamp order (safe: widening constraint, CREATE OR REPLACE, re-asserted grants). trg_meetup_rsvps_notify 0dbf2b3c = 20260915 file minus comments; re-pin b12:132 to accept both. Written: /Users/moataz/.claude/jobs/b9b99f0a/tmp/cto-messaging-prereq.md. No SQL run; decision_gate not answered.

## 2026-11-05 — Review KAN-714/716/713 migrations (steps 21-24) for Memphis
Read-only. All four GO, class A (net). Indirect wrapper drop/recreate in b14 via kan712_unwrap_rpc/wrap_rpc in one txn; kan713_preimage DELETE is bookkeeping. No SQL, no edits.

## 2026-11-05 — KAN-871 meetup_counts guard abort
Decided: KAN-858 pin correct (e5982fbd = KAN-772 body md5, recomputed); prod ec29fe4c = KAN-772 pre-image; D04 meetup_counts never delivered (KAN-772 fails closed, KAN-823 excludes it). Directed supplement step 29a before KAN-871. Decision: /Users/moataz/.claude/jobs/b9b99f0a/tmp/dec-871.md. Read-only; no SQL, no writes.

## 2026-11-06 — dreq-9e4edd4c (KAN-871 step 30 drift)
Ruled: rpc_create_game 5b8883b2 = post-image of 20261105120000_kan794_d04_on_live_bodies.sql:297 (KAN-823, step 25); part 2 pinned local KAN-772 post e565a2ba (KAN792_PIN_AUDIT.md Hazard 4, :151). rpc_create_meetup will fail next (77a14a22 vs 0f5ba02e). Fix = re-author part 2 (pins + both rpc_create_* bodies on kan794 bodies), PEER, new md5; not a 29a supplement, not reorder. Class A, no DROP.
