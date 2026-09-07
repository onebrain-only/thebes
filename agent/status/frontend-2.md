# senior-frontend-2 — status

## 2026-09-06 — Skills audit (survey, no work)

**First entry for this seat. It has never run a task.** Dispatched by `team-lead-2` under the
CEO's instruction *"ask everyone — we don't want them similar, we want each one a professional
in their own field."* Read-only survey: no code, no git, no Jira, no `flutter`.

### What I did

Read the roster's skill bodies rather than their descriptions, filtered to what D2 (games,
meetups, competition) and D8 (moderation, safety, trust) actually need.

**Opened in full or in substantial part:**
`flutter-add-widget-test` · `flutter-add-integration-test` · `dart-add-unit-test` ·
`dart-use-pattern-matching` · `flutter-build-responsive-layout` · `codebase-design` ·
`working-with-legacy-code` (§Core Principle + change algorithm) · `release-it` (§§1–2) ·
`secure-mobile-dev-guide` (section index) · `mobile-threat-model` (STRIDE table) ·
`supabase-postgres-best-practices` (index + `lock-skip-locked`, `schema-constraints`).

**Searched by body, not by name**, across every installed skill (`~/.claude/skills`,
`One Brain/.claude/skills`, all plugin caches) for: `optimistic ui`, `race condition`,
`idempoten`, `concurren`, `realtime`, `presence`, `broadcast`, `moderation`, `abuse`,
`harassment`, `blocklist`.

### What I decided

1. **`working-with-legacy-code` is the D2 skill**, not any Flutter skill. D2's headline problem
   is finished backends with no client (leagues, squads) plus 130 shipped features with no
   characterization. Feathers' "legacy code is code without tests" and cover-and-modify is the
   exact shape of the work. A greenfield seat does not need it.
2. **`codebase-design` is mine because of `explore`**, which imports 13 files across three of my
   slices and is imported back once. That is a seam decision and the skill is the vocabulary
   for it — not a general senior-frontend habit.
3. **Nothing in the roster addresses competitive correctness.** Zero body hits for optimistic
   UI, rollback, real-time client consistency, or multi-viewer state agreement. The `supabase`
   skill names Realtime once, in its own frontmatter, and never in the body.
4. **Nothing addresses moderation UI.** The security skills protect the app from an attacker;
   D8 protects a user from another user. Different actor, no overlap. I concur with `analyst`'s
   verdict on the seven MASVS skills and did not re-derive it.
5. **The one skill covering concurrent-write correctness is one I am forbidden to act on.**
   `supabase-postgres-best-practices` (`lock-skip-locked`, `schema-constraints`,
   `data-upsert`) is exactly a waitlist promotion / squad-slot claim, and my role file says
   never author SQL. That is a routing fact for `senior-backend`, not a skill gap.

### What I touched

This file only. No repo files read for content beyond skill bodies; no repo file changed.

### What is blocked

- **Two skill gaps are `cto`/`cxo` calls, not mine to author** — real-time client consistency
  in Flutter/Riverpod, and a fail-closed moderation-UI invariant list. Reported to
  `team-lead-2` for routing.
- **`flutter-add-integration-test` cannot be adopted by me alone.** It requires
  `enableFlutterDriverExtension()` in the app entry point and `flutter drive`, which `ci.yml`
  does not run (analyze + test only). That is a `devops` decision.
- Seat remains idle on app code: Phase 0 exclusive grant (`CONTRACT.md` §4.1) is live and
  `senior-frontend-3` holds the only write grant.

## 2026-09-06 — KAN-119 stood down (misdispatch). No work retained.

**Dispatched, then recalled.** I was sent KAN-119 (`/auth-welcome` renders blank) as Team 2's
work. `team-lead` recalled it mid-pass: `team-lead-3` (Khonsu) owns the `auth_onboarding` slice
and its brief names `frontend-3` (Horus), not me. The dispatch carried an earlier report past a
later, more specific one from the same lead. Not my error and not held against me — recorded
because the stand-down is the outcome of this task.

**What I did before the recall.** Read KAN-119 and comment `10639`, read both screens, and
applied the fix: wrapped the `Padding` at
`lib/features/auth_onboarding/presentation/screens/auth_welcome_screen.dart:298` in
`IntrinsicHeight`, matching `email_password_screen.dart:347`. One file, 218/211 lines (the
wrapper plus re-indent and a `dart format` pass on that file alone).

**Measured, and it survives the revert as information even though the diff does not:**

```
flutter analyze --no-pub --no-fatal-infos   → 0 errors, 0 warnings (57 infos, all pre-existing,
                                              none in this file)
flutter test                                → 106 tests, All tests passed! (count unchanged)
```

That is the ticket's AC 5. **Not measured:** the simulator render (AC 2–4) and the
`.start` vs `.stretch` question the lead flagged as the residual risk — the iOS build had not
finished attaching when the recall arrived. I make no claim about either, and Horus should
treat both as open.

**A path correction for whoever picks this up.** The dispatch brief cited
`lib/features/auth/presentation/screens/auth_welcome_screen.dart`. **That path does not exist.**
The file is under `lib/features/auth_onboarding/...`, as the ticket and Khonsu's brief both say.
I worked from the ticket rather than the brief, per instruction, so no wrong file was touched.

**What I touched.** The one file above, then reverted it: `git checkout --` on it,
`git status --porcelain` empty, `git diff --stat` empty, `git log -1` still `da41d3b`. No commit,
no push, no Jira comment, no transition. I also killed the `flutter run` I had building on the
iPhone 16 Pro simulator so it could not hot-reload a stale artifact into Horus's run. This status
file is the only thing I wrote.

## 2026-09-06 — KAN-130 client half + one unticketed lint (Sekhmet)

**A — KAN-130, AC 3 (client half). 1 sitting.** `Wallet.userId` → `Wallet.ownerId` and the
map key `user_id` → `owner_id`, four lines at `lib/data/models/wallet.dart:6,14,28,38`.
Commit `b6b2ea9`, local on `Canary`, not pushed. `WalletLedgerEntry.userId` deliberately
untouched — it maps `wallet_ledger.user_id`, a different column, per AC 3's own wording.

**Not transitioned.** KAN-130 is one ticket covering both halves and the SQL half has not
started (blocked on KAN-128, earliest 2026-09-10). Moving it to `In Review` would claim the
migration is done. Referred to `po` for the ruling: comment-and-hold, split, or otherwise.
Also flagged: the ticket's Executor line still names `senior-frontend-4`, a seat that no
longer exists — ticket text, `po`'s to fix.

**B — unticketed lint. Part of 1 sitting.** `avoid_renaming_method_parameters` at
`notifications_controller.dart:90` silenced with an `// ignore:` plus the reason: the base
`didChangeAppLifecycleState` parameter is named `state`, which would shadow
`StateNotifier.state`. An ignore survives an SDK bump promoting the lint to fatal, which is
the risk the brief named. Commit `2eca71d`.

**KAN-139 not started** — `T-062` rules `placeholder_screen.dart` SHARED with no single
writer, so permission was asked of `po` rather than assumed. No reply yet.

**Measured** in `Dabbler/dabbler-code` after both commits, tree clean:
`flutter analyze --no-pub --no-fatal-infos` → 56 issues, 0 errors, 0 warnings.
`flutter test` → `All tests passed!`, 106 tests.

**Hazard worth recording:** the working tree is shared with concurrently running agents. A
`git reset` from another agent silently unstaged my `git add` between the add and the commit,
and 26 unrelated file deletions (a dead-code prune, since committed) were in the tree while I
measured. `git commit -o <path>` per file rather than `git add` + `git commit` is what makes
this safe.

### KAN-139 — closed same sitting, after `po`'s go-ahead

`po` ruled `placeholder_screen.dart` is SHARED, first-to-pull, no conflict, and opened the
ticket to me. `const PlaceholderScreen({super.key, required this.title});` —
`lib/app/routes/placeholder_screen.dart:11`. Commit `90ea9f7`, local on `Canary`, not pushed.
Moved to `In Review`.

All four acceptance criteria measured, not inferred:
1. constructor forwards `super.key` — the only change on the line.
2. infos under `lib/app/` → **0** (`flutter analyze ... | grep -c "• lib/app/"`; was 1).
3. `flutter test` → `All tests passed!`, **106 tests**, unchanged.
4. one file touched — `git show --stat` reads `1 file changed, 1 insertion(+), 1 deletion(-)`.

Repo-wide after this commit: `flutter analyze --no-pub --no-fatal-infos` → 55 issues,
**0 errors, 0 warnings**. 57 → 56 → 55 across the three commits; each delta is one lint.

`po` also ruled KAN-130 stays in `Ready` with a comment recording the client half, and left
the stale `senior-frontend-4` executor line in place since the SQL-half line is still accurate.

### 2026-09-06 — two follow-ups verified, neither acted on

**1 — the `ownerType` gap is real. Confirmed, not accepted on report.**
`lib/data/models/wallet.dart` has `id, ownerId, availableCents, pendingCents, currency,
updatedAt` and **no `ownerType`** (`:5-10`); `toMap()` at `:36-43` emits `owner_id` with no
`owner_type`. With `wallets.owner_type` NOT NULL, an insert built from that map fails `23502`
— the same defect KAN-130 exists to fix, one layer up. Latent: still zero consumers, and
`wallet_repository.dart` and its impl were deleted by the dead-code prune mid-task.

**My sizing: trivial — 4 lines, the same shape as the rename** (field, constructor param,
`fromMap`, `toMap`), well inside one sitting. **Not written.** Diff not widened on my own
initiative; `po` is deciding whether it is an unmet AC on KAN-130 or a follow-up ticket.

**2 — KAN-148 capacity: 1 sitting, datable now, no blocker.** Agrees with `team-lead-2`,
measured independently rather than carried:
* Line counts confirmed exactly — 1179 + 525 + 571 + 749 = **3,024**.
* Zero external references by **filename** and, separately, by **public class name**
  (`SportFormatStep`, `VenueSlotStep`, `PlayerInvitationStep`, `ReviewConfirmationStep`) —
  0 hits each across `lib` and `test` outside the four files themselves.
* Nothing in `lib/providers.dart` or any barrel — the central-re-export trap the brief named
  does not apply here.
* No `.freezed.dart` / `.g.dart` siblings — the directory holds only the four `.dart` files.
* `git status --porcelain` empty at check time, so no overlap with `frontend-5`'s deletion.

Pure deletion, no dependents, one analyze+test cycle to verify. Nothing makes it undatable.

**Correction for the record:** repo-wide analyze is **55 issues**, not 56 — 57 → 56 → 55
across my three commits. The 56 figure predates the KAN-139 commit.

## 2026-09-07 — KAN-130 client half, `ownerType` gap closed (`7d2cd47`)

`team-lead-4`'s gap is real and I re-verified it myself rather than accepting it.
`lib/data/models/wallet.dart` at HEAD had `ownerId` (from `b6b2ea9`) and no
`ownerType`. `T-051` (`DECISIONS.md:6669`) makes the pair the design and makes
`owner_type` **NOT NULL**; `wallets_owner_type_valid` (baseline schema `:26687`)
constrains it to `'user' | 'venue' | 'platform'`. So the field's type and values
came from the schema, not from guesswork.

**Added** `Wallet.ownerType`, mirroring `ownerId` exactly: nullable field, required
in the const ctor, `m['owner_type']` in `fromMap`, `'owner_type'` in `toMap`.
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
