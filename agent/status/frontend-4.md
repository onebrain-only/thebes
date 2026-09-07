# senior-frontend-4 — status

## 2026-09-06 · Skills audit (survey, no work) — first run of this seat

**Dispatched by** `team-lead-4`. Read-only survey. **No code written, no git, no Jira, no
`flutter`.** This file did not exist before today.

### What I did

Read `agent/skills/` (74), `agent/skills/AVAILABLE.md`, my role file, and then **opened
bodies** rather than judging by name: `release-it`, `ddia-systems` (+ their
`references/`), `paywalls` (full, + `references/experiments.md` listing), `pricing`,
`hooked-ux`, `microinteractions`, `drive-motivation`, `improve-retention`,
`flutter-implement-json-serialization`, `frontend-patterns`, `backend-patterns`.
Measured the repo where a claim depended on it.

### What I decided / found

1. **Enablement, not availability, is the binding constraint for my two stacks.**
   `/Users/moatazmustapha/Desktop/Thebes/.claude/settings.json` `enabledPlugins` does
   **not** contain `ux-design@wondelai-skills` and contains **zero** `marketingskills`
   plugins. So `hooked-ux`, `microinteractions`, `drive-motivation`,
   `improve-retention`, `paywalls`, `pricing`, `churn-prevention` — the seven closest
   to D7 Rewards and D4 Money — are installed on disk but **not invocable via `Skill`**.
   They can only be `cat`-ed. `AVAILABLE.md` lists them as "available to any seat today";
   for these seven that is not true of the `Skill` tool.

2. **A second `dart-flutter` member contradicts this repo**, on top of the one
   `senior-frontend-3` found. `flutter-implement-json-serialization` SKILL.md, Core
   Guidelines: *"Throw Exceptions on Failure… Do not return `null`."* That is the exact
   inverse of the repo's non-negotiable `Result<T, Failure>` / never-throw-across-layers
   rule. It also prescribes hand-written `fromJson`/`toJson` against a repo that uses
   Freezed + `build_runner`. `flutter-use-http-package` is dead here too — the client is
   `Supabase.instance.client`, not `package:http`. **Cite members, never the set.**

3. **Money-flow correctness has essentially no coverage in the ~524.** `idempoten*`
   appears in exactly two SKILL bodies: `ddia-systems` (one line, 153) and
   `marketing-loops` (a different sense of the word). The only real material is
   `release-it/references/stability-patterns.md:223-238` (retry budget, idempotency keys,
   retryable vs non-retryable split) and `ddia-systems/references/transactions.md:132-178`
   (write skew, worked `-- Double booking!` example). Both are server-side framing.
   **Nothing in the corpus is about payment *UI* correctness.**

4. **Two backend gaps found while checking whether the skill gap mattered** —
   `senior-backend`'s, not mine, flagged not fixed:
   - `payment_intents` (`supabase/migrations/20260829080500_baseline_schema.sql:23491-23503`)
     has **no idempotency-key column** and no uniqueness on `provider_intent_id`. Indexes
     at 28837/28841/28845 are all plain btree. A client retry mints a second intent.
   - `wallet_ledger` (`:26922-26940`) is documented append-only, but `(ref_type, ref_id)`
     carries only a plain index (`:29421`), not a unique constraint. Nothing at the schema
     level stops the same credit posting twice.

5. **`paywalls` implementation half is mine.** `content-manager` was right that the copy is
   its and the flow decision is `pm`/`cxo`'s, but SKILL.md §"Timing and Frequency" and
   §"Upgrade Flow Optimization" specify per-session caps, dismiss cool-downs measured in
   days, and post-upgrade immediate-access — all **client state I would have to build and
   persist**. It is not invocable (see 1), so today that is a read, not a `Skill` call.

### Blocked / not done

- Cannot invoke the seven skills in finding 1. Enabling `ux-design@wondelai-skills` and the
  relevant `marketingskills` plugins is a config decision above this seat — raised to
  `team-lead-4`, not acted on.
- The two schema gaps in finding 4 are `senior-backend`'s queue. Not raised as a ticket by
  me — I do not write tickets.
- **Not verified:** did not open all 524; did not read `churn-prevention`, `cro`,
  `ab-testing`, `onboarding`, `analytics`, `aso` bodies — judged from description only.
  Did not probe live Supabase; schema findings are from the baseline migration file, and
  `SCHEMA.md` §8 mismatch 7 warns the file is not the remote.

---

## 2026-09-06 — KAN-142, two dead navigation targets (`frontend-4`, Renenutet)

Pulled from `Ready`. Branch `Canary`, local commit `6c5bca4`, **not pushed**.

### The declare-or-delete question, measured

All three line numbers in the ticket were correct at execution time — `notifications_screen_v2.dart:543`,
`transactions_screen.dart:837`, `activities_screen_v2.dart:608`.

**`/phone-input` — neither declare nor delete. Repoint.** The brief offered two answers and the
measurement supports a third. `find lib -iname "*phone*"` returns **nothing** — there is no
`phone_input_screen.dart` anywhere, only three stale references to it in
`lib/core/design_system/README.md:441` and `MATERIAL3_MIGRATION_GUIDE.md:24,473`. Phone auth was
replaced by the email/OTP flow (`RoutePaths.emailInput`, `RoutePaths.otpVerification`, declared at
`identity_routes.dart:61,72`). But **both call sites are `Sign In` buttons on a signed-out empty
state**, and signing in is not a deleted feature. Deleting the button would remove a live
affordance; declaring `/phone-input` would build a door to a screen that does not exist. Both go to
`RoutePaths.authWelcome` — declared at `identity_routes.dart:50`.

**`/bookings/<id>` — delete.** No screen (`find lib -ipath "*presentation/screens*" -iname "*booking*"`
→ empty), no route, and no `booking` constant in `route_constants.dart`. The `bookings_repository`
/ `bookings_controller` layer under `lib/features/games/` still exists, but nothing renders it. The
`case 'booking':` branch in `_handleActivityTap` is removed; the switch has no default, so a booking
activity now taps inert instead of routing to a GoRouter error page.

### Files changed

- `lib/features/misc/presentation/screens/transactions_screen.dart` — +import `:12`, `:838`
- `lib/features/activities/presentation/screens/activities_screen_v2.dart` — +import `:5`, `:609`
- `lib/features/notifications/presentation/screens/notifications_screen_v2.dart` — `case 'booking'` removed at `:541-543`

### `T-062` disposition

**Nothing under `lib/app/routes/` was touched.** Read `T-062` at `DECISIONS.md:7536` before
starting; the partition does not bind this ticket because the fix is entirely in feature screens.
The route it now points at was *read* from `identity_routes.dart` (`team-lead-1`, clean) but not
written.

### Verified

- `flutter analyze --no-pub --no-fatal-infos` → **0 errors, 0 warnings**, 57 infos.
- `flutter test` → **106 tests, 10 files, All tests passed!** Count unchanged.

### Findings worth someone else's attention

- **The shared working tree is not clean and the other changes are not mine.** `git status` showed
  staged deletions of 26 rewards/payments model and repository files plus edits to
  `lib/data/models/models.dart` and `notifications_controller.dart` from another seat. I committed
  **only my three paths** with `git commit -o`. **Corrected at report time:** that seat has since
  committed them and `git status --porcelain` is now empty. The finding stands as a coordination
  note — a shared tree means `git commit -a` from any seat would have swept up another's work.
- `lib/core/design_system/README.md` and `MATERIAL3_MIGRATION_GUIDE.md` cite `phone_input_screen.dart`
  as the reference migrated screen. That file no longer exists. Documentation drift, not mine to fix.

### Running-app verification

Required by the brief. Three of four surfaces were unavailable:

- **iOS simulator** — `flutter run` failed: `Lexical or Preprocessor Issue (Xcode):
  'FirebaseMessaging/Sources/Token/FIRMessagingFIDRegisterOperation.h' file not found` in
  `build/ios/SourcePackages/checkouts/firebase-ios-sdk/.../FIRMessagingTokenManager.m:27`.
  Unrelated to this change. **This contradicts `drive-the-app`'s Trap 4, which marks iOS `[M]` working
  as of today.** Per that skill's own instruction — trust the machine, fix the line — someone should
  re-mark it.
- **Android emulator** — `emulator -avd Dabbler_test` refused: `Running multiple emulators with the
  same AVD is an experimental feature.` Another session holds it. (`flutter emulators --launch` had
  in fact succeeded on a slower path; `emulator-5554` came up later.)
- **Web `integration_test`** — blocked per Trap 3, not attempted.
- **Chrome / CanvasKit — used.** `flutter run -d chrome --dart-define-from-file=.env`, served on
  `localhost:65006`.

**What the running app measured.** The app dumps its full route table at boot. Of **49 declared
routes**, `/auth-welcome` is present; `phone-input` and `bookings` each appear **0 times**. That
confirms the ticket's premise from the runtime router rather than from grep, and confirms my
target is declared.

**Stated as unverified:** `/auth-welcome` renders **blank** in the browser. That is the existing
`KAN-119` defect on a file my bounds forbid me touching (`frontend-3` is live on it). The route
resolves; the screen does not paint. I am not claiming the sign-in flow works end to end.

### Capacity

**1 sitting, ceiling 2.** One sitting: no dependency boundary — the declare-vs-delete judgement is a
decision taken inside the pass, not a checkpoint the next part waits on. The ceiling carries one
rework cycle for the AC1 literal-reading gap flagged to `po`. **No date** — `po` converts.

Ticket moved **To Do → In Review** (transition 31). Note it was never moved to `Development` by a
lead; I pulled it from the board directly under the CEO's pull rule.
