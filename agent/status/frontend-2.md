# frontend-2 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/frontend-2.md`. This file is a work log, not a rule source.

`WalletLedgerEntry.userId` is a different column — untouched.

**No `build_runner` step.** `Wallet` is a plain `@immutable` class, not Freezed —
the brief's step 3 assumed otherwise. Worth knowing before the next wallet ticket.

`flutter analyze --no-pub --no-fatal-infos` → 0 errors, 0 warnings, 55 infos.
`flutter test` → 106 tests, all passed.

**Size: 1 sitting.**

**Two things I did not do, deliberately.**

1. **Did not push.** `origin/Canary` is 14 commits behind local; 13 are other
   agents' unshipped work. Pushing would deploy all of it to canary.dabbler.pro,
   which is outside this ticket. Left for the lead to sequence.
2. **Did not transition the ticket.** The SQL half has not started and is gated on
   `cto` applying `KAN-128`. `KAN-130` is not done; only its client half is.

**Discrepancy raised to `po`:** AC3 on `KAN-130` as it reads today still says only
"rename `Wallet.userId` → `Wallet.ownerId` (four lines)" — no mention of
`ownerType`. The brief said `po` had corrected AC3 in place. Either the correction
did not land or I read it before it did. The code is right either way (it follows
`T-051`, which is unambiguous), but the criterion does not yet describe it.

**Discrepancy resolved (`po`, 2026-09-07).** The AC3 correction had never landed —
`po` narrated it in comment 10659 on 2026-09-06 but did not call the edit that
writes the description field. The ticket I read was the live one and it genuinely
said four lines, `ownerId` only. `po` has now edited AC3 to require both fields,
corrected the count to eight lines, and repointed the Executor section from the
retired `senior-frontend-4` seat to `frontend-2`. `7d2cd47` satisfies the corrected
criterion as shipped — no rework. Ticket stays in `Ready`; the SQL half is still
gated on `cto` applying `KAN-128`.

Worth carrying forward: the brief asserted a ticket edit had happened, and it had
not. Reading the live ticket rather than trusting the brief is what caught it, and
building from `T-051` rather than from either text is what made the commit correct
regardless of which was right.

## 2026-09-09 — KAN-129 PEER review (reviewer, not executor)

CEO-authorised PEER reviewer for KAN-129, a comment-only change to
`lib/data/repositories/profiles_repository.dart` executed by `frontend-1` at
Canary `715bb85`. Verified HEAD matches `origin/Canary` and the tree is clean
before reading anything.

Verdict: **PEER PASS**, all six criteria with evidence, posted to KAN-129 as
comment `10771`. No directive language, no legacy/deprecated/abandoned wording, no
removal or migration promise — one case-insensitive grep over the whole file for
`legacy|deprecat|abandon|prefer|should|eventual|migrat|remov` returns nothing. The
comment cites a re-runnable grep and contains no numeral at all. Every changed line
in the commit is a `///` line, and the commit touches exactly one file.

Gates re-measured myself rather than taken from the executor:
`flutter analyze --no-pub --no-fatal-infos` exit 0, 0 errors / 0 warnings / 55
infos; `flutter test` exit 0, 106 passing. Both match baseline.

Two things worth carrying forward. First, the ticket's AC1 cites lines 4-12 and the
block is at 5-15 — recorded as ticket drift, not an implementation defect; line 4 is
a real blank line (`sed -n '4p' | od -c` -> a lone `\n`). Second, re-running the
cited grep gives 38 hits / 14 files excluding the definition site, against the 36
the ticket recorded three days ago. The count moved again, which is the argument for
the design the executor chose: the comment is correct *because* it cites no number.

Not recorded in Persistent State — the review context was opened with a null owner
and there is no released operation to set `review_owner` afterwards. Known blocker,
reported by the orchestrator, not mine to write; I wrote nothing under
`agent/state/runtime/` and transitioned nothing in Jira.

## 2026-09-09 — KAN-132 executed: dead profile stack deleted (`c0d84d9`)

CURRENT OWNER per Persistent State (claimed 2026-09-09, revision 2, continuation gate
passed). `T-053` (`DECISIONS.md:6704`, `cto`, 2026-09-06): delete both files, not
rename — the collision is latent (no importers), so a rename fixes nothing.

**Re-confirmed unreachability myself before touching anything**, at Canary HEAD
`715bb85`:
- `grep -rln "supabase_profile_repository" lib test` — zero hits.
- `grep -rn "SupabaseProfileRepository" lib test` — 3 hits, all inside the file's
  own definition (class + factory), zero external references.
- `grep -rn "SupabaseProfileRepository\|supabase_profile_repository\|profile_repository.dart" lib test`
  — 7 hits: 6 are the unrelated, live
  `lib/features/profile/domain/repositories/profile_repository.dart` (imported by
  `profile_repository_impl.dart`, three usecases, and
  `auth_onboarding/location_controller.dart:3` — expected, not this ticket's
  concern) plus 1 hit, `supabase_profile_repository.dart:6` importing the sibling
  file being deleted alongside it.
- `lib/providers.dart` — no reference to either file or either class name.

No live importer of either file. Deleted both together, one `git rm`, one commit:
`lib/data/repositories/profile_repository.dart` and
`lib/data/repositories/supabase_profile_repository.dart`.

`flutter analyze --no-pub --no-fatal-infos` → 0 errors, 0 warnings, 55 infos
(unchanged, none in the deleted files). `flutter test` → 106 tests, all passed.

Commit `c0d84d9` on `Canary`, **not pushed**, exactly the two deletions
(`git commit -o` per file). Two unrelated modified files were sitting in the
working tree from a concurrently running agent
(`lib/core/config/feature_flags.dart`, `lib/main.dart`) — left untouched and
unstaged, not part of this commit; the hazard noted 2026-09-06 (shared tree,
`git commit -o` rather than `git add`+`git commit`) is what kept this clean.

No other file touched. Did not push, did not open a PR, did not transition the
Jira ticket, did not write under `agent/state/runtime/`. Findings posted as Jira
comment `10794` on `KAN-132`.

---

## 2026-09-11 — KAN-192 PEER review (reviewer, not executor)

**Verdict: PASS.** `frontend-1` executed; I verified independently and did not
edit, fix, commit, push, transition, or create any Jira ticket.

**AC1 — generated code, not the annotation.** Read the pre-change file straight
from git rather than trusting the report: `git show HEAD:lib/data/models/squad.g.dart`
lines 12-13 were literally `json['owner_profile_id'] as String` /
`json['owner_user_id'] as String`. Post-change both are `as String?`.
`squad.freezed.dart` declares `String?` getters at :399,:402 and switches both
`copyWith` sentinels from `null ==` to `freezed ==` with `as String?`. Proved the
throw mechanism by running the exact pre-change cast standalone — it produces
`type 'Null' is not a subtype of type 'String' in type cast`, verbatim the claim.

**AC2 — 5 tests, 4 of them discriminating.** Tests 1, 2, 3 and 5 all decode a row
with a null owner and would throw on the pre-change generated code, so each fails
without the fix. Test 4 (fully-populated row) passes either way **by design** — it
is the over-relaxation guard the ticket asked for, paired with test 5, which
guards that a nulled owner round-trips back to `null` and not to `''`. Called out
explicitly rather than let it read as an accidental pass.

**AC3 — re-derived the enumeration; did not count files.** Grepped `ownerProfileId`
and `ownerUserId` across `lib/` and `test/` and read every hit. The identifier is
noisy: `ownerProfileId` also belongs to `UserCircle`
(`lib/data/models/user_circle.dart`, `user_circles_repository*.dart`,
`user_circles_providers.dart`) and `ownerUserId` also to `Benefit`
(`lib/data/models/benefit.dart`, `organiser_benefits_repository_impl.dart`) —
different classes, `wc -l` on the file list would have inflated this to ~10 files.
Zero dereferences of either field on a `Squad` instance anywhere in `lib/`.
`Squad` is constructed only via `Squad.fromJson` at
`squads_repository_impl.dart:133,167,551,626` — exactly the four claimed. The one
raw read of the column, `squads_repository_impl.dart:275-281`, already casts
`as String?` and guards the null with an early `Failure` return.

**AC4 — ran both.** `flutter analyze --no-pub --no-fatal-infos` → 55 issues, all
`info`; grep for `error •`/`warning •` returns 0. `flutter test` → `+116: All tests
passed!` (111 pre-existing + 5 new).

**Scope — clean.** KAN-192's four files only. The shared tree held other seats'
live work throughout (`docs/CONVENTIONS.md`, `scripts/ci/*`, KAN-181/KAN-186
migrations, and it shifted between my first and last `git status`); none of it is
squad-related and none was swept in.

**Finding raised, not fixed — belongs to KAN-191, not here.**
`squads.created_by_user_id` is `NOT NULL` with FK → `auth.users`
**`ON DELETE CASCADE`** (`baseline_schema.sql:31533`), and `delete_my_account()`
ends with `delete from auth.users where id = v_uid`
(`baseline_schema.sql:5302`). So erasure deletes the squad row outright via
`created_by`, and the owner columns never get the chance to go null. If KAN-191
fixes that by making `created_by_user_id` SET NULL, `squad.dart:22`
`required String createdByUserId` throws the identical
`type 'Null' is not a subtype of type 'String'` — KAN-192's own defect, one column
over, and outside its declared scope. Not a KAN-192 defect; reported to
`team-lead` for KAN-191's owner. No KAN-191 migration exists in the tree yet, so
this is read from the baseline, not from KAN-191's actual content.

Adjacent finding recorded in `agent/state/discovery-ledger.md`: `SocialConsumer`
is the only widget that renders a `Squad` and nothing references it — AC3's "no UI
renders a squad owner" is true, but no UI renders a squad at all.

## 2026-10-06 — CEO order: launch video splash (integ-app, alpha-k437)
Committed d5550f12 (not pushed). StartupSplash plays assets/Splash.mp4 while bootstrap runs; native/web launch plain #7328CE. analyze 0 err/0 warn, flutter test 1187 pass, build web ok. iOS/Android not run.

## 2026-11-03 — KAN-743 (Events P3, R03) — Team Habu frontend
- Worktree kan680, branch alpha-habu, commit c4c2b030c91950b5a4714bc346e04762d68c1e78 (not pushed).
- B04 keeps RPC names and result columns (no event_id); Dart callers already matched. Doc-only changes to model and datasource, plus new test/features/games/nearby_games_event_backed_test.dart (10 tests).
- analyze: 0 errors, 0 warnings, 45 infos (same as baseline). New test green. Games suite: 6 failures in game_composer_request_id_test.dart, the same 6 at baseline.

## 2026-11-03 — KAN-745 (Events P3, KAN-715 R05) sport overview reads event-backed counts — Team Habu frontend
- Worktree kan680, branch alpha-habu, base c4c2b030 -> commit 11f2a4e556d10c9e432565ff877d7f5638b6c733 (not pushed).
- B07 (20261104100700_kan714_b07_sport_overview_counts.sql:189-191) keeps rpc_sport_overview's RETURNS TABLE shape unchanged; Dart change is comments only plus new test test/features/sports/sport_overview_event_backed_test.dart (4 tests).
- C1 analyze --no-fatal-infos exit 0, 45 infos (no new); C2 exit 0; test/features/sports/ 93 passed. Tests shown to fail on four deliberate breaks, then restored.
- Jira transitions not performed by me (brief ran under the Habu orchestrator).

## 2026-11-03 — KAN-747 (Team Habu subagent) — offline cache/codec version bump
- Commit 29cfd9d9 on alpha-habu (worktree kan680). Entry format version 2 + account tag in OfflineCache; kGameCodecVersion 2 in game_codec; decodeGame returns null on old/missing version or missing required field.
- Chose payload versioning over renaming `_root` (v1 -> v2): the rename would break ~12 assertions in test/core/cache/{offline_cache,cache_cleanup}_test.dart (outside planned surfaces) and orphan v1 keys outside the sign-out wipe.
- C1 exit 0 (45 infos, unchanged); C2 exit 0 (8/8). test/core + test/features: 3795 pass, 5 fail — same 5 fail at base without the change.

## 2026-11-03 — KAN-748 (Events P3, KAN-716 V01): event cache invalidation contract
- Worktree Dabbler/dabbler-code/.claude/worktrees/kan680, branch alpha-habu, commit c551ad908f5f94a874c221f7cb32e99d547862b4 (not pushed).
- Contract + isInvalidatedBy in cache_policy.dart; EventCacheInvalidator + eventCacheInvalidatorProvider in cache_providers.dart; late-write guards in swrFetch and readThrough (currentAccountId param).
- Exception outside planned four: lib/core/cache/offline_cache.dart +5 lines, public keysOf(accountId).
- analyze --no-fatal-infos exit 0, 45 infos (unchanged); plain analyze exit 1 (infos). New test 19/19; core+meetups+games 724 passed, 0 failed.
- Feature call sites not wired (other KAN-716 pieces).

## 2026-11-04 — KAN-878 (KAN-873 split 5/6) Activity log no-match state + searching-older indicator
- Commit 00e78546ea1c260015a8f0ac14ad56f760f9df7a on alpha-karnak (pushed). Worktree kan714-karnak clean.
- New ActivityNoMatchState + ActivitySearchingOlderIndicator + activityLogCategoryLabel; slivers branch on query/isSearchingOlder/hasMore.
- C1 analyze exit 0 (0 errors, 0 warnings); C2 9/9 pass; l10n parity + activities + notifications_render 85 pass.
- Design link not re-read (claude.ai/design not reachable from this seat); kept ActivityEmptyState visual family.
