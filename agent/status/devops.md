# devops status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/devops.md`. This file is a work log, not a rule source.

1. Its own Docker fallback (no env var set) — ran locally, all 9 fabricated cases + both diff directions passed.
2. `KAN175_TEST_DB_URL` set directly with `psql` on PATH against a standalone `postgres:16` container on a mapped port — the exact mechanics a GitHub Actions service container provides — installed `libpq`/`psql` via Homebrew locally to test this leg specifically rather than assume the CI YAML pattern would just work. Also passed clean.

**Wiring added to `.github/workflows/anon-allowlist-check.yml`:** a job-level `services.postgres` (postgres:16, health-checked, port 5432 mapped), plus two new steps after the existing KAN-61 view-allowlist step — the KAN-175 gate itself (shares `SUPABASE_DB_URL`, no new secret) and the self-test (`KAN175_TEST_DB_URL=postgresql://postgres:postgres@localhost:5432/kan175`). `flutter analyze` re-confirmed clean (0 errors/0 warnings/55 infos) before committing, though this change touches no Dart.

**Staged and committed by explicit path only** — `.github/workflows/anon-allowlist-check.yml`, `docs/SCHEMA.md`, `scripts/ci/README.md`, and the three new `scripts/ci/*.sh` files. Left untouched per backend-2's explicit warning: `docs/CONVENTIONS.md` (modified) and both wallet/creator-fk migration files (one modified, one untracked) — other seats' in-flight work, not KAN-175, T-068 freeze not implicated by my commit. Committed as `a08c057`.

**Pushed and deploy-verified, real CI run inspected, not assumed:** local Canary was already 1 commit ahead of origin (`cda7f0a`, KAN-167, pre-existing/not mine — pushed forward as part of the same fast-forward, since it was already a sealed commit sitting on local Canary, not WIP). `git push origin Canary` → `21389a6..a08c057`. Post-push local == origin/Canary == `a08c057`, `main` re-confirmed unchanged at `a1501904`.

Cloudflare: fingerprint `c77a2e0c3f9a` -> `62c55b2fa8fb`, HTTP 200 throughout, ~4 min. `gh api .../check-runs` on `a08c057`: `Cloudflare Pages` success, `analyze-and-test` (x2) success, `allowlist-check` (x2) success. Pulled the actual job log for `allowlist-check` (not just the green checkmark): the new gate step ran the real census against `wtncuzcschpigqpmnxwws` live (SECURITY DEFINER 303, both 292, 60 public-grant-only) and reported "OK: all 74 flagged function signature(s) are on the allowlist" — matches the seeded §2g baseline, first run green as backend-2 predicted. The self-test step ran against the service-container Postgres via `KAN175_TEST_DB_URL`, all 9 fabricated cases + both diff directions PASS. Total job runtime ~41s.

**Fact-check finding, reported to backend-2, not corrected by me:** `scripts/ci/README.md` and `docs/SCHEMA.md` §2g both state the census as "SECURITY DEFINER: 303; anon-executable: 292; both: 292." The live CI log shows the actual `anon_executable` column (not intersected with `prosecdef`) is **1748**, not 292 — 292 is the `both` (SECURITY DEFINER ∩ anon-executable) figure, reused incorrectly as the "anon-executable" figure in both docs. Doesn't affect the gate's correctness (the failing predicate already uses the correct intersection + identity-arg + no-comparison logic, and got 74/74 right), but understates the documented anon-executable attack surface by ~6x in two places. Not mine to silently amend — backend-2's authored security-audit content, already routed to Peer-review; flagged to backend-2 directly instead.

No force push, no `main` touch, no merge, no migrations authored or applied.

## devops — 2026-09-10/11 — KAN-175 closed: four commits pushed to Canary (012becc)

**Task (from team-lead):** push four unpushed local commits closing out KAN-175 AC7 (the anon-function-grants gate had a `LIMIT 1` blind spot — cleared a function that guarded only its first of two identity arguments) plus three unrelated DB fixes riding the same local Canary. Explicit instruction: do not apply the KAN-170 FK migration in `f6c5f10` (authored-but-never-applied, cto's T-077 Amendment 2 ruled it targets the wrong column) — push flow must not run migrations, stop if it would.

**Pre-push verification:**
- Confirmed exactly the four named commits, in the stated order, ahead of `origin/Canary`: `5d32afc`, `1dddd55`, `f6c5f10`, `012becc`. `main` unchanged at `a1501904`.
- Confirmed no pre-push/pre-commit hooks and no CI workflow runs `supabase db push` or any migration-apply step — `git push` cannot trigger the KAN-170 migration regardless of its presence in the tree. `f6c5f10`'s own commit message states "No production object was created or modified"; `1dddd55` and `5d32afc` record migrations already applied via `apply_migration` in a prior authorized session (T-068 step 5), not something this push executes.
- No Dart files touched across the four commits — skipped a redundant `flutter analyze`/`flutter test` run; `bash -n` confirmed clean on the three modified/touched shell scripts (`anon_function_grants_diff.sh`, `check_anon_function_grants_test.sh`, `check_anon_function_grants.sh`).
- **Independently re-ran the AC7 self-test locally before trusting the commit message** (`bash scripts/ci/check_anon_function_grants_test.sh`, Docker fallback path). First attempt hit a transient "disposable Postgres did not become ready" — local Docker flake, unrelated to the code (a pre-existing unrelated container, `kan128pg`, has been running 34h on this machine). Retry was clean: new CASE J (`rpc_second_arg_unguarded`, two identity arguments, only the first guarded) correctly flagged; all 12 assertions (6 must-flag/must-not-flag pairs + 2 diff-direction checks) passed.

**Push:** `git push origin Canary` → `a08c057..012becc`. Post-push local == origin/Canary == `012becc07ed0c40087fa50e28cf8cd0bd7106609`. `main` re-confirmed unchanged at `a1501904`.

**Deploy verified:** pre-push fingerprint `62c55b2fa8fb` (matches last-recorded live state) → changed to `d9ddcc7d84c3` at attempt 7 (~3.5 min), HTTP 200 throughout.

**Both workflows checked by reading the actual job logs, not just the checkmark**, per team-lead's explicit ask since `012becc` changes the gate's own predicate:
- `ci.yml` (`analyze-and-test`): success (x2, push + PR#12).
- `anon-allowlist-check.yml` (`allowlist-check`): success (x2). Log confirms: KAN-61 view gate "OK: all 10 anon-readable definer view(s) are on the allowlist"; KAN-175 live gate against `wtncuzcskpigqpmnxwws` "OK: all 70 flagged function signature(s) are on the allowlist" (down from the previously-recorded 74 — consistent with `1dddd55`'s organiser-rename repair fixing some previously-flagged functions; the diff is one-directional so a shrinking flagged set against a static allowlist passes by design, not a gap); self-test log shows `rpc_second_arg_unguarded` genuinely flagged and "Self-test result: ALL cases behaved correctly."

No force push, no `main` touch, no merge, no migration applied or attempted by this push. KAN-170's authored-but-unapplied migration file rode along in the repo per team-lead's explicit acknowledgment (T-068 makes the repo non-authoritative for live state; `po` separately marking it superseded).

## devops — 2026-09-11 — Correction to the KAN-175 census report: 74 vs 72 baseline, and the causal attribution retracted

Team-lead caught two errors in my prior status entry (the one reporting `012becc`'s deploy). Both confirmed real on re-reading the repo, neither guessed.

**Error 1 — wrong baseline figure, same shape as the AC6 mislabel the ticket exists to fix.** I wrote "down from 74." `74` is the static §2g **allowlist size** (`awk` between the markers in `docs/SCHEMA.md`, confirmed by direct count: exactly 74 lines, unchanged across `a08c057` and `012becc`). It is not a flagged-population count and never decreases on its own. The actual pre-`012becc` **flagged** count, already documented in `docs/SCHEMA.md` (added by `012becc` itself, backend-5's finding): `create_system_post` and `process_notification_event` were contained by `REVOKE` after the 74-baseline was taken, so **72 of the 74** were live just before `012becc` landed. The real movement my CI run measured was **72 -> 70**, not 74 -> 70.

**Error 2 — 1dddd55 is not a plausible cause, retracted.** `1dddd55` repairs five venue-authz function *bodies* (organiser-table rename) using `CREATE OR REPLACE` with each body taken verbatim from `pg_get_functiondef` on the live catalogue, changing only the broken table reference. `CREATE OR REPLACE` preserves `proacl` exactly (stated in the commit message itself), and a verbatim body swap changes neither the `anon`-executable axis nor whether an identity argument is compared to `auth.uid()`. It cannot have caused any function to leave the flagged set. My attribution was a plausible-sounding guess, not something I had checked before writing it.

**The two signatures, found by elimination against repo evidence — reported with the actual limit of what I could confirm:**

Cross-referenced team-lead's list of today's containment revokes/narrowings (`settle_game`, `rpc_potential_vibes`/7-arg, `create_system_post`, `process_notification_event`, `set_session_user`, `rpc_remove_player`, `rpc_decide_join_request`) against the 74-entry §2g list, confirmed by direct `grep`:
- `settle_game` — **not in the 74 list.** Consistent with `T-069`/`DECISIONS.md`: its live signature is `settle_game(uuid,uuid,text,numeric,boolean)`, no person-named argument, so this gate's identity-argument predicate was never going to flag it regardless of its (separately documented, unrelated) revoke.
- `rpc_potential_vibes` (bare, 7-arg, `p_me uuid`) — **not in the 74 list.** Confirmed a real, distinct function from the listed `rpc_potential_vibes_debug` (different body, present in `supabase/migrations/20260829080500_baseline_schema.sql`). `T-070`/`DECISIONS.md` documents this as the live finding; its absence from the 74-baseline means its containment (whenever it happened) predates the 2026-09-10 baseline reading, not something in the 72->70 window.
- `rpc_decide_join_request` — **not in the 74 list** at all; same conclusion.
- `create_system_post`, `process_notification_event` — in the 74 list, but already the documented cause of 74->72, not available to explain 72->70 again.
- `set_session_user(p_user uuid)` and `rpc_remove_player(p_game_id uuid, p_profile_id uuid)` — **the only two remaining candidates**: both present in the 74-entry list, both named in team-lead's revoke/narrow account, neither already used to explain an earlier step.

**What I could NOT independently confirm:** no migration file, no `docs/SCHEMA.md` entry, and no `docs/DECISIONS.md` entry documents a grant change to either `set_session_user` or `rpc_remove_player` — unlike `create_system_post`/`process_notification_event`, which backend-5 recorded in `docs/SCHEMA.md` itself. That these two specifically dropped, and that "narrowed" (rpc_remove_player's word, distinct from "revoked") actually flips its `anon`-executable bit to false rather than leaving it true under some other restriction, rests entirely on team-lead's account in this thread — not on anything I can point to in the repo. I also cannot rule out, without live DB access, a masked add-and-drop elsewhere in the 74-entry set that nets to the same -2, since no log enumerates the full flagged set at either point in time — only its count.

**Reported to team-lead as: determinable by elimination which two names are consistent with both the repo's static list and their account (`set_session_user`, `rpc_remove_player`); NOT independently verifiable beyond that without live DB access or a repo-committed record of either specific revoke.** Both errors in the original report corrected in that same message; no re-push, KAN-175 stays closed per team-lead's instruction.

## devops — 2026-09-11 — Burn-down: protected three uncommitted docs/migration-comment changes (791ff15, 0e9f066, fa38b00)

**Task (team-lead, burn-down mode):** commit and push three files sitting uncommitted on local `Canary` before a `git checkout` could lose them — KAN-172's retention ruling (migration comment), cto's KAN-195 AC4 §12k (CONVENTIONS.md), and cto's §2g.1 containment-revoke record (SCHEMA.md). Explicit instruction: read every diff before committing, stop on anything not matching the three described items, and never apply/run/replay the migration file (T-068 known-dangerous case).

**Diffs read in full before staging anything.** All three matched the brief, with one disclosed exception: `docs/CONVENTIONS.md`'s diff contains **two** new sections, not the one named — §12j ("Live state resembling a migration's target is not evidence the migration partly ran," generalizing T-073) alongside the named §12k. Assessed §12j as legitimate rather than foreign: internally coherent, cites T-068 Amendment 2 and T-073 (both already in `docs/DECISIONS.md`), same cto voice and dated the same night. Included it rather than holding the whole file back, but flagged it explicitly per the "stop and tell me" instruction rather than sweeping it in silently.

The migration file's diff is comment-only, confirmed by reading both hunks — no SQL statement touched. `flutter analyze` re-confirmed clean (0/0/55) before committing, though nothing here touches Dart.

**Split into three commits, one per file/topic** (team-lead left this to judgement):
- `791ff15` — the KAN-172 migration comment (cpo's P-036 financial_ledger retention ruling).
- `0e9f066` — `docs/CONVENTIONS.md` §12j + §12k, both included, discrepancy noted in the commit message itself.
- `fa38b00` — `docs/SCHEMA.md` §2g.1, the seven containment revokes. Notable: this section explicitly credits my own earlier elimination work tonight (the `set_session_user`/`rpc_remove_player` finding) and states plainly that none of the seven `proacl` states is repo-confirmed current, since Supabase MCP has been disconnected since T-077 Amendment 1 — consistent with what I found independently on the last task.

**Push and deploy, same discipline as `012becc`:** `git push origin Canary` → `012becc..fa38b00`. Local == origin/Canary == `fa38b00`, `main` unchanged at `a1501904`. Fingerprint `d9ddcc7d84c3` → `423860abb950` (~4.5 min), HTTP 200 throughout.

**Both workflow job logs read, not just checkmarks:**
- `anon-allowlist-check`: "OK: all 10 anon-readable definer view(s)" (KAN-61) and **"OK: all 70 flagged function signature(s) are on the allowlist"** (KAN-175) — same figure as the prior push, unchanged, since nothing in this push touches any function grant. Self-test: "ALL cases behaved correctly." Per team-lead's explicit instruction: reporting the figure only, no cause attributed — the gate does not emit membership, so movement or non-movement of this number is not something I attribute without it.
- `ci.yml`: "111 tests passed," 0 errors/0 warnings. Analyze reported **42** issues, not the usual 55 — traced to CI running Flutter **3.47.3** (cache key in the log) against my local **3.44.1**; both are info-level counts under `--no-fatal-infos`, so the difference doesn't affect the gate. This is the SDK-drift risk already named in `CLAUDE.md`'s CI section ("a future SDK bump can make a new lint fatal with no code change") — not itself a defect, just recorded since I read the actual log rather than the checkmark.

No Jira ticket created. No adjacent problem found that needed a `discovery-ledger.md` entry — the only discrepancy (§12j) was resolved by disclosure within the commit itself, not deferred as a finding.

## devops — 2026-09-11 — Pushed two already-applied migrations: KAN-168 (6422003) and KAN-170 setnull (3444540)

**Task (team-lead, T-068 orphan-shape protection):** push two commits closing the gap between production (both migrations already applied live) and the repo. Team-lead supplied the exact commit hashes in the brief.

**Correction to my own initial assumption:** I first treated this as "stage and commit two untracked files," per the pattern of the last several burn-down tasks. On checking, both commits (`6422003` KAN-168, `3444540` KAN-170) **already existed locally**, authored by the correct `dabblersport` identity, exactly matching the hashes team-lead gave — backend-5/backend-6 had committed them directly. My `git add` of the two migration files was therefore a no-op on already-committed content; no new commit was created by me. Re-read the situation before proceeding rather than committing a duplicate.

**Read both migration files in full before pushing** (both already committed, read for verification, not authored): KAN-168 (`20260911074412_kan168_notification_hourly_caps_urgent_rows.sql`) adds the missing `urgent` hourly-cap row per plan with an in-transaction completeness assertion; well-reasoned, self-verifying, explicitly latent-not-live. KAN-170 (`20260911074608_kan170_games_creator_user_id_fk_setnull.sql`) adds an integrity-only FK (`ON DELETE SET NULL`), explicitly non-load-bearing, and the same commit (`3444540`) also updates the earlier `20260910100000_kan170_..._fk.sql` (committed `f6c5f10`) to mark it superseded — both described in the commit message, not a surprise hunk.

**Tree hygiene, verified rather than assumed:** confirmed exactly these two commits sit ahead of `origin/Canary` (`git log origin/Canary..Canary`), nothing else. Working tree at the time carried `docs/CONVENTIONS.md`, `lib/data/models/squad.*` (frontend-1's KAN-192, in peer review, explicitly excluded), `scripts/ci/*` (KAN-193 in flight), and four other untracked migration/test paths (`kan181`, `kan186`, `kan188`, `supabase/tests/kan181/`, `test/data/models/`) — all attributable to other seats' declared in-flight work per the brief's "whatever backend-7/backend-8 have in flight" category. None of it touched. `main` confirmed unchanged at `a1501904` before and after.

**Push and deploy:** `git push origin Canary` → `fa38b00..3444540`. Local == origin/Canary == `3444540`. Fingerprint `423860abb950` → `b102d87e40ca` (~3.5 min), HTTP 200 throughout.

**Both workflow logs read directly:**
- `anon-allowlist-check`: KAN-61 "OK: all 10..."; KAN-175 **flagged count: 70** — unchanged from the last two pushes. Per team-lead's explicit instruction, reporting the figure only; no cause attributed (KAN-193, in flight, is what will let the gate answer this itself).
- `ci.yml`: 111 tests passed, 0 errors/0 warnings, 42 infos (consistent with the CI-vs-local Flutter version difference already noted last push, not a new anomaly).

No Jira ticket created. No adjacent discovery-ledger entry — nothing found outside what the brief already named and accounted for.

## devops — 2026-09-11 — KAN-193 AC4 pushed (7d6df21): the gate now emits membership, not just a count

**Task (team-lead):** commit and push three peer-reviewed files (backend-6 independently reproduced on its own disposable Postgres, backend-7 closed both review items) closing KAN-193's AC4 — the anon-function gate reports the full flagged population, not just its size.

**Diffs read in full before staging**, all three matching backend-7's description exactly: `anon_function_grants_diff.sh` emits the population between `ANON_FUNCTION_FLAGGED_BEGIN/END` markers, `LC_ALL=C` sorted, on both the pass and fail exit; `check_anon_function_grants_test.sh` adds AC1 (block reconstructs the population exactly, on both exits) and AC2 (a masked add-and-drop — one signature contained, a different one introduced, net count unchanged — is named exactly by diffing two runs' blocks); `scripts/ci/README.md` documents both, plus a self-correction backend-6 caught in peer review (a stale "nine cases" count sitting two lines from the corrected count). **Independently re-ran the self-test locally before committing** rather than trusting peer review alone (Docker fallback): all cases pass, including the AC2 masked add-and-drop naming `rpc_fetch_locker_contents` as departed and `rpc_late_arrival` as entered, exactly. `bash -n` clean on both scripts. `flutter analyze` re-confirmed clean (0/0/55), though nothing here touches Dart.

**Tree hygiene:** staged exactly the three named paths. Confirmed and left untouched, all attributable: `docs/CONVENTIONS.md` (further edits, not mine), `lib/data/models/squad.*` + `test/data/models/` (KAN-192 — **still uncommitted as of this push**, reporting per team-lead's "check and tell me" rather than deciding), `kan181`/`kan186`/`kan188` migrations + `supabase/tests/kan181/` (deliberately held per standing instruction), and a new `20260911075539_kan171_charges_table_invariants_rls.sql` (applied per its own header, T-068 step 1 — **reporting its existence at this path, not folding it into this commit**, per instruction). `main` unchanged at `a1501904` throughout.

**Push and deploy:** `git push origin Canary` → `3444540..7d6df21`. Local == origin/Canary == `7d6df21`. Fingerprint `b102d87e40ca` → `f73e1beab168` (~2.5 min), HTTP 200 throughout.

**KAN-193 AC4 evidence, captured from the live job log** (run `34577327291`, https://github.com/dabblersport/webapp/actions/runs/34577327291): the function-grants step now prints the full population between the markers — 65 signatures listed (admin_cleanup_user_data through unsync), followed by `OK: all 65 flagged function signature(s) are on the allowlist.` This is the first live baseline captured with membership, exactly the artifact the ticket exists to produce, saved here for the next run to diff against. Self-test: "ALL cases behaved correctly." `ci.yml`: 111 tests passed, 0 errors/0 warnings, 42 infos (same CI-SDK gap as the last two pushes).

**Flagged count: 65** — down from 70 at the last push. Per team-lead's explicit instruction, reporting the figure only; no cause attributed. I do not have a prior run's *block* to diff against (only prior counts), so a named comparison genuinely isn't available yet — this push is what makes that comparison possible starting next run.

No Jira ticket created. No discovery-ledger entry — nothing found outside what the brief already named.

## devops — 2026-09-11 — KAN-181/KAN-171 S1/KAN-188 committed and pushed (71db8d5), three separate commits

**Task (team-lead):** commit three applied-but-untracked migrations (KAN-181, KAN-171 S1, KAN-188) plus KAN-181's probe pack, closing the failing AC6 on KAN-181's peer review. Verify backend-2's claim that KAN-188 was already committed rather than assume it.

**Verified backend-2's claim first — it was wrong.** `git ls-files --error-unmatch` on the KAN-188 path failed (untracked) and `git log --all` on it returned nothing. Reported the correction rather than silently fixing it.

**Read all three migration files in full, plus the probe pack, before staging.** Independently re-computed the KAN-181 file's md5 — `dea4f00dfb5013162d49214b1bedd3b8`, matching backend-1's reported hash and the ledger's `statements[1]` exactly. All three are coherent, self-verifying (in-transaction assertions or DO-block post-conditions in every case), and match their own headers' claims about what was applied.

**Three separate commits, one per ticket, each naming its ledger version:**
- `2c02875` — KAN-181 (`20260911075034`) + its probe pack (`supabase/tests/kan181/probes.sql`), folded together since the pack is AC5 of the same ticket, not a separate concern.
- `e502e82` — KAN-171 sitting 1 (`20260911075539`), the `charges` table + T-049 invariants + RLS.
- `71db8d5` — KAN-188 (`20260911080000`), relocating five venue-authz functions from `public` to `util`.

**Explicitly left alone, all attributed:** `docs/CONVENTIONS.md` (not mine); `lib/data/models/squad.*` + `test/data/models/` (KAN-192 — **still uncommitted as of this push**, reporting per instruction rather than deciding); `supabase/migrations/kan186_profile_fk_cascade_part_a.sql` (no version prefix, deliberately held); a newly-appeared `supabase/migrations/20260911080324_kan171_record_charge_write_path.sql` (not named in the brief — presumably KAN-171 sitting 2 — left untouched, not requested). **Two other sealed commits appeared on local Canary between checks** (`84a012b` KAN-185 doc correction, `f774768` KAN-178 role_grants RLS fix, plus an earlier `af99cc7` KAN-185 fix already ahead) — all well-formed, correct `dabblersport` identity, coherent messages; pushed forward as already-sealed work, same pattern as prior sessions, not authored by me.

**One thing surfaced in passing, not mine to act on:** `agent/state/discovery-ledger.md` gained an entry mid-task (`Persistent State enforces at the point of use, never at the point of entry`) naming exactly the KAN-171 files I was committing — both migrations applied against an unowned ticket record due to an orchestrator release/dispatch race. Entry states the writes themselves are sound (hash-matched, probes passed) but the ownership state is not repaired and blocks KAN-171 S3/KAN-169. Already recorded by `backend-4`; noting it here since it's directly adjacent to what I pushed, not re-recording it.

**Push and deploy:** `git push origin Canary` → `7d6df21..71db8d5`. Local == origin/Canary == `71db8d5`. `main` unchanged at `a1501904`. Fingerprint `f73e1beab168` → `3530f84484e7` (~4 min), HTTP 200 throughout.

**Both job logs read directly** (run `34577836880` for the gate, `34577836881` for ci.yml). Self-test: "ALL cases behaved correctly." `ci.yml`: 111 tests passed, 0 errors/0 warnings, 42 infos.

**Flagged count: 65 — unchanged from the last push.** Programmatically diffed this run's `ANON_FUNCTION_FLAGGED` block against the immediately preceding run's (both captured via `gh run view --log`): **byte-identical, 65 lines each, zero diff.** None of KAN-188's five relocated functions were members of the flagged set before or after. Per instruction, reporting this mechanical fact only — no cause attributed. Job log: https://github.com/dabblersport/webapp/actions/runs/34577836880

No Jira ticket created. No new discovery-ledger entry from me — the one relevant finding was already recorded by `backend-4` before I got to it.

## devops — 2026-09-11 — KAN-182 committed (f8b6006); KAN-171 S2/KAN-192/KAN-178 found already committed by a concurrent session; block diff shows zero movement across three runs

**KAN-182 (low-effort task):** migration + probe pack were untracked on Canary (PEER FAILED on AC6 only). Read both files in full before staging — coherent, self-consistent, matches its own header (contains `process_notification_event`, flips `trg_circle_join_notify` to SECURITY DEFINER so the revoke doesn't break circle-join notifications). Staged both by explicit path, left `kan174_fold_potential_vibes_drop_identity_param.sql` (new, unrequested) and `kan186_...` (held) untouched. Committed as `f8b6006`.

**Correction to the prior task:** while working on it, discovered that my two outstanding commits from the previous task (KAN-171 S2 `record_charge`, KAN-192 `squad.dart` nullability) had already been committed and pushed by a concurrent session (`a18e0e4`, `1a484a9`), along with KAN-178 AC5's two commits (`c54b497`, `8bf9595`) and one more PEER-FAIL fix (`f53a85b`) — all correct `dabblersport` identity, all well-formed. Did not duplicate; verified via `git log`/`git status` before assuming anything needed staging, per the standing instruction.

**Push:** `git push origin Canary` → `a18e0e4..f8b6006` (the two commits genuinely still local: `f53a85b`, `f8b6006`). Local == origin/Canary == `f8b6006`. `main` unchanged at `a1501904`. Deploy verified by fingerprint: `9a1de5eaf758` → `d3c90607747b` (~3.5 min), HTTP 200 throughout.

**Both job logs read directly.** `ci.yml`: 116 tests passed (up from 111 — KAN-192's `squad_test.dart` landing in the concurrent push), 0 errors/0 warnings, 42 infos. `anon-allowlist-check`: KAN-61 "OK: all 10..."; self-test "ALL cases behaved correctly."

**Block diff, as requested — and it needed two comparisons, not one, to tell the real story:**
1. This push (`f8b6006`, run `34592401389`) vs. the immediately preceding run (`a18e0e4`, run `34591458144`): **zero movement.** 65 lines both, `comm` in both directions empty.
2. Because team-lead expected KAN-178's relocation to move the number, and it landed in a run I hadn't yet compared against a "before" baseline, also diffed the run from *before* KAN-178 AC5 applied (`71db8d5`, run `34577836880`, captured last task) against the run from *right after* (`a18e0e4`, run `34591458144`): **also zero movement.** Confirmed mechanically: none of `can_manage_venue`, `can_manage_venue_members`, `can_view_venue_bookings`, `can_create_venue_booking`, `can_edit_venue_details` (KAN-188), `is_moderator`, `is_venue_admin` (KAN-178) appear in the flagged block in any of the three captured runs. The flagged count has been exactly **65** across `71db8d5` -> `a18e0e4` -> `f8b6006`, byte-identical every time.

Reporting the diff, not a cause: all seven relocated functions were never members of the flagged population in the first place, in any run this tool has captured — so relocating them out of `public` had nothing to remove from this particular set. Whether that's because they were never anon-reachable-with-an-unguarded-identity-arg to begin with, or contained by an earlier, separately-recorded revoke, is not something the diff itself answers.

No Jira ticket created. No discovery-ledger entry — nothing found outside what's already accounted for.

## devops — 2026-09-11 — KAN-138 file marked SUPERSEDED AND DEAD (8df3c08), urgent low-effort

Verified before editing: `git log --all --oneline | grep 9d855a5` found the commit; `git show --stat` gave the exact path (`supabase/migrations/20260907130000_kan138_settle_game_settlement_status_cast.sql`); file was clean/unmodified beforehand. Cross-checked the claim rather than trusting it blind: line 143 confirmed the exact 5-parameter `settle_game(p_game_id uuid, p_organiser_user_id uuid, p_sport text, p_gross_collected numeric, p_finalize boolean DEFAULT true)` signature, and lines 69-70's exploit-proof comment matched team-lead's description verbatim. Confirmed `20260911113000_kan169_...` and `20260911114500_kan169_...` exist in the tree (both untracked, not part of this task's scope).

Prepended the exact header supplied, verified pure addition (27 insertions, 0 real deletions — the diff tool's one `-` line is just the file-header marker). Staged only this file by explicit path; `kan174`/`kan186`/`kan169`-x2 left untouched. Committed as `8df3c08`.

**Not pushed** — the task's instruction was "prepend... then commit," no push named, unlike prior tasks that explicitly said "after the push." Left for team-lead's call rather than assuming.

No Jira ticket created.

## devops — 2026-09-11 — KAN-138 header corrected per cto's T-082, committed and pushed (5e602aa)

cto corrected the reasoning in the header I pushed as `8df3c08`: the danger isn't reverting KAN-169 (the 5-param signature here doesn't match live `settle_game(uuid,boolean)`, so CREATE OR REPLACE would create a second overload, not revert the fix) — it's that the file has zero GRANT/REVOKE and `pg_default_acl` grants anon/authenticated EXECUTE on new public functions by default, so applying it would create a brand-new, unprotected, anon-reachable privilege-escalation function. Replaced exactly the flagged paragraph with team-lead's supplied text verbatim, verified diff was a clean swap (12 insertions/2 deletions, nothing else touched), confirmed tree clean of anything else before staging. Committed `5e602aa`, pushed immediately per the standing instruction not to hold a security marker local. Local == origin/Canary == `5e602aa`. `main` unchanged at `a1501904`.
2026-10-24 push 4f954339 -> origin/Alpha (FF from 88aa48f8); Alpha only, no deploy verification applicable

## 2026-10-25 KAN-591 push to Alpha
- Fast-forwarded origin/Alpha 4f954339 -> b6f8313f (alpha-591r2-edfu), no force. Ancestor check passed.
- Deploy result: pending, not verified; if no later entry exists, it was never confirmed. (Push only; no build check run.)

## 2026-10-25 KAN-642 ship to Alpha
DS alpha-ds dee5257..e9eb8b6 (ff). App Alpha b6f8313f..6abc112b (ff, pubspec.lock only). analyze exit 0, flutter test exit 0 (4027 pass). Alpha deploy build result: not verified; if no later entry exists, it was never confirmed.

## KAN-641 to Alpha (devops, 2026-10-25)
Alpha 6abc112b -> 8bdb2f1c. d97287d7 was NOT a fast-forward (Alpha had 3 KAN-642 commits); cherry-picked 004d436a+d97287d7 onto Alpha cleanly (b8b47f75, 8bdb2f1c). analyze 0 errors/0 warnings (43 infos), flutter test 4029 passed. Cloudflare Pages check-run on 8bdb2f1c: completed/success (verified via gh check-runs).

## 2026-10-25 KAN-640 to Alpha
Cherry-picked 9 KAN-640 commits onto origin/Alpha 8bdb2f1c, pushed b8dd5abc. analyze 0 errors/0 warnings (43 infos), flutter test 4063 passed. Cloudflare Pages check on b8dd5abc: completed/success. Temp worktree removed.

## 2026-10-27 dreq-2526 KAN-679
Decided: cherry-pick 1aafe33a onto alpha-habu and push; Ops applies via one execute_sql with before/after read-backs. Deploy result: not applicable, no push done by me. Decision at /Users/moataz/.claude/jobs/c49d2414/tmp/dreq-2526.md

## 2026-11-01 devops (Ptah) - alpha-luxor KAN-694/695 ruling
Read-only check: Alpha 55a839a9 holds KAN-694 files byte-identical to old remote alpha-luxor b05fe264 (commits 4c1bc31b, cf836e13). No KAN-695 work on Alpha or old branch. Ruled: no force push, no -s ours merge, nothing to integrate for 694. Deploy: n/a, nothing pushed. Answer: /Users/moataz/.claude/jobs/f305ed4e/tmp/ans2.md

## 2026-11-05 devops (Ptah) - dreq-eb54069e KAN-871/29a/KAN-827
Read-only ruling: Memphis does not author 29a; park 871 until dispatched; apply 29a class A, probe e5982fbd..., rerun 871 unchanged (896600b7...); 827 waits. Deploy: n/a, nothing pushed. Decision at /Users/moataz/.claude/jobs/b9b99f0a/tmp/dec-871b.md

## 2026-11-05 dreq-59a2d6a1 KAN-821 parked
Decision written to /Users/moataz/.claude/jobs/b9b99f0a/tmp/dec-821.md: Memphis does nothing on KAN-821/826/827/833 until predecessor Done in prod; single ack, no rescue. Dispatcher defect noted (KAN-871 counted satisfied after 'completed' parked report). No deploy involved; read-only.

## 2026-11-05 — dreq-8f92473f (KAN-871, meetup_counts md5) — Ptah
Result: decision written to /Users/moataz/.claude/jobs/b9b99f0a/tmp/dec-871b.md. Likely measurement difference (md5 of pg_get_functiondef vs CTO's md5 of prosrc), not drift. NOT measured by me: sql_psql refused devops (ops-only), so production was not read; verdict is from the file guard and the 885 header. Probe for Memphis is in the decision. No changes made, no deploy, no commit.

## 2026-11-05 dreq-418879f5 (KAN-886/KAN-871, 29a file) — Ptah
Decision at /Users/moataz/.claude/jobs/b9b99f0a/tmp/dec-886.md: no apply from staging-karnak; PEER KAN-885 (other backend-N) -> integrate to staging -> Memphis applies 886 then 871 with md5 recorded. Read-only, no deploy, no commit. Jira/branch not verified by me.
