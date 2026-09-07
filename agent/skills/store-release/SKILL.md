---
name: store-release
description: Shipping a Dabbler build to the App Store or Google Play, and what stands between this repo and that. Use when asked to submit, upload, release, ship to TestFlight or Play, cut a version, or bump a build number; when a store rejection arrives and someone reaches for a rebuild; when someone asks whether Fastlane or a store pipeline exists here; and before promising any store date, because the freeze stops this process before it starts.
---

# Store release

Owned by `devops` and by no other seat. Everything below was measured in
`Dabbler/dabbler-code` on 2026-09-06; each claim carries the command or the file and line.

## Read this first: nothing ships today

**`G-018` Ruling 2 (`Dabbler/dabbler-docs/DECISIONS.md:5672`) — no push to any remote except
the One Brain repo until the CEO lifts it, explicitly. Silence does not lift it.**

An upload to App Store Connect or Play Console is a push to a remote — the most outward-facing
one this company has, and the only one that reaches real users through a gatekeeper we do not
control. **While Ruling 2 is live, no build is uploaded, no submission is filed, no TestFlight
distribution goes out.** Building locally is fine; distributing is not.

`P-030` (`DECISIONS.md:4728`) freezes merges into `main` on top of that. It governs the **web**
release path, not this one — but it is why nobody should read "Canary is green" as permission
to submit.

**Where the process resumes when the freeze lifts:** at *Sequence* below, step 1, from a clean
`Canary`. Nothing in this skill is executed before then. If a seat is asked to submit while
Ruling 2 stands, the answer is the ruling, not a build.

## What exists here

| Thing | Where | State |
|---|---|---|
| Version source of truth | `pubspec.yaml:19` — `version: 1.7.8+174` | live |
| iOS release build script | `build_ios.sh` (repo root) | live, and the only sanctioned iOS build |
| iOS dart-define bridge | `scripts/gen_dart_defines.sh` → `ios/Flutter/DartDefines.xcconfig` | live, output gitignored |
| iOS signing | `ios/Runner.xcodeproj/project.pbxproj:494,503,683` — `CODE_SIGN_STYLE = Automatic`, `DEVELOPMENT_TEAM = J5636UH8V8`, bundle `app.dabbler.pro` | live, Xcode-account-bound |
| iOS version wiring | `ios/Runner/Info.plist` — `$(FLUTTER_BUILD_NAME)` / `$(FLUTTER_BUILD_NUMBER)` | live, reads `pubspec.yaml` automatically |
| Android signing | `android/app/build.gradle.kts:45-58`, reading `android/key.properties` | live |
| Android identity | `android/app/build.gradle.kts:38` — `applicationId = "com.dabbler.dabblerapp"`, `targetSdk = 36` | live |
| App Store Connect | team `J5636UH8V8`, real submissions filed (`.claude/agent-memory/devops/app-store-inherited/app_store_submission_170.md`) | set up |
| Play Console | enrolled in Google Play App Signing; upload key rotated 2026-08-30 (`android/key.properties` header, `T-003`) | set up |
| Rejection handling | `agent/roles/references/app-store-review.md` | live — see *The gates that are not ours* |

**The two application identities differ and that is not a bug.** iOS is `app.dabbler.pro`;
Android is `com.dabbler.dabblerapp`. Do not "fix" either — changing an `applicationId` on a
published Play listing orphans it.

**Credentials, and where each belongs — never a value, never in a tracked file.**
`android/key.properties` (gitignored, `android/.gitignore:12`) holds `storePassword`,
`keyPassword`, `keyAlias`, `storeFile`; the `.jks` it points at lives outside the repo. `.env`
holds the Supabase values `build_ios.sh` bakes. Verified 2026-09-06 that none of
`android/key.properties`, `deployment_cert.der`, `.env`, `android/local.properties` is tracked
(`git ls-files --error-unmatch <path>` → error on all four; `git check-ignore -v` → all four
matched), and that no keystore, `.p12`, `.p8`, `.pem`, `.mobileprovision` or service-account
file is tracked anywhere (`git ls-files | grep -iE '\.(jks|keystore|p12|pem|mobileprovision|cer|der|p8)$|key\.properties|service.*account'` → empty).

## What does not exist

Each measured, each returning nothing.

- **Fastlane, in any form.** `find . -iname "*fastlane*" -not -path "./build/*"` → **empty**.
  No `fastlane/`, no `Fastfile`, `Appfile`, `Matchfile`, `Deliverfile`, no `fastlane/metadata`.
  There is no pipeline here to run. Anyone citing one is citing a document, not this repo.
- **`ios/ExportOptions.plist`** → `No such file or directory`. `build_ios.sh` accepts
  `--export-options-plist` as a pass-through, but the file it would name has never been written.
- **Any store step in CI.**
  `grep -rniE "ipa|apk|appbundle|aab|xcode|testflight|fastlane|app-store|play" .github/workflows/`
  → **empty**. The two workflows are `ci.yml` (`flutter analyze` + `flutter test`) and
  `anon-allowlist-check.yml`. Both are gates; neither builds or ships a binary.
- **An Android release build script.** `build_ios.sh` has no sibling. `ls` of the repo root
  shows `build_ios.sh` and `run.sh` and nothing else of that shape.
- **Any runtime read of the real version.** `package_info_plus` is absent from `pubspec.yaml`
  and `PackageInfo` appears nowhere in `lib/`.

## Version and build-number discipline

`pubspec.yaml:19` is the source of truth. iOS reads it through `$(FLUTTER_BUILD_NAME)` /
`$(FLUTTER_BUILD_NUMBER)`; Android reads it through `flutter.versionName` /
`flutter.versionCode` (`android/app/build.gradle.kts:41-42`). Bump it there and both platforms
follow.

**A build number is spent the moment a store accepts it.** Apple rejects a reused
`CFBundleVersion` for a version train with `ITMS-4238`; Play rejects a reused `versionCode`
outright. Neither is recoverable — you bump and rebuild. Never re-upload a binary under a
number that has been accepted, including one that was accepted and then *rejected in review*:
review rejection does not free the number.

**A rejected marketing version must be bumped, not just the build number.** Apple closes a
version train once approved; a `CFBundleShortVersionString` that was rejected needs a new
marketing version (`1.7.8` → `1.7.9`), not `1.7.8+175`.

**Three hardcoded copies exist and are stale by design of neglect, not of intent.** Measured:

| File | Line | Value |
|---|---|---|
| `lib/core/utils/constants.dart` | 6 | `appVersion = '1.7.8'` |
| `lib/utils/constants/app_constants.dart` | 5 | `appVersion = '1.7.8'` |
| `lib/features/profile/presentation/screens/settings/settings_screen.dart` | 52 | `_appVersion = '1.7.8'` |

Only the third is reachable — it renders at `settings_screen.dart:1070`. The two constants have
**no consumers at all**: `grep -rn "\.appVersion" lib/ test/ integration_test/ --include="*.dart"`
→ **empty**. **Bump all three anyway** when the marketing version changes; the settings screen
is what a reviewer sees, and leaving the dead pair behind at an old value is how the next seat
bumps the wrong one.

The role file also names a *rewards analytics payload* as a fourth copy. It does not exist:
`grep -rn "app_version" lib/ --include="*.dart"` outside `lib/core/analytics/analytics_constants.dart`
→ empty, and the two hits inside it are parameter-key names, not version literals. Three
locations, not four.

## Sequence

Executable only after the freeze lifts. Each step names the observable that proves it worked.

1. **Confirm the freeze is lifted by the CEO, explicitly.** No observable, no step 2.
2. **Bump the version.** Edit `pubspec.yaml:19` and the three literals above. Observable:
   `grep -rn "1\.7\.8" pubspec.yaml lib/core/utils/constants.dart lib/utils/constants/app_constants.dart lib/features/profile/presentation/screens/settings/settings_screen.dart`
   returns nothing at the old value.
3. **Gate on CI's own two commands** — `flutter analyze --no-pub --no-fatal-infos` then
   `flutter test`. Observable: both exit 0. This is `ci.yml:36,39` run locally; a store build
   is not the place to discover a red analyze.
4. **iOS build:** `./build_ios.sh`. Observable: the banner prints the Supabase ref and
   `ENVIRONMENT` **before** the build — read it, because shipping a stale backend to TestFlight
   is a mistake this project has already made once, which is why the banner exists
   (`build_ios.sh:23-36`). Then `build/ios/ipa/*.ipa` exists.
5. **Android build:** *does not exist yet.* See gap 1. A bare `flutter build appbundle` bakes
   empty Supabase config for the same reason `build_ios.sh` exists — do not substitute it.
6. **Upload.** No credentialled path exists (gaps 3, 4). Today this is a human in Xcode
   Organizer / Play Console, not a command this seat runs.
7. **Submit,** then hand the outcome to *The gates that are not ours*.

## The gates that are not ours

Apple review and Play review are external gatekeepers. **A rejection is not a build failure and
is not fixed by rebuilding.** A rebuild under a fresh build number with unchanged behaviour
returns the same rejection and spends a number.

`agent/roles/references/app-store-review.md` owns everything downstream of a rejection: parsing
the guideline, classifying the fix, drafting the Resolution Center reply, the resubmission
checklist. **This skill stops where that file starts.** The handoff is one-directional and the
split is clean: this skill answers *how a build becomes a submission*; that reference answers
*what to do when a submission comes back*. Its only overlap is the bumped build number, which
this skill owns and it consumes.

Two facts from that reference change what you build, so they belong here too:

- **Auth is passwordless (OTP).** When Apple asks for demo credentials, there is no password to
  give. Do not invent one.
- **Verify version claims against `pubspec.yaml` directly.** A rejection brief citing a
  build number has been wrong before (submission `9e8a4758-58a4-4bba-baff-960517f83e1e`: the
  brief said `1.0+170`, the repo said `1.7.3+169`).

## Out of scope: the Cloudflare variable split

The Production/Preview variable split (`CLAUDE.md` §Build Variables) does **not** belong to this
skill. It governs the **web** deploy — Cloudflare Pages building `Canary` and `main` — which
ships no binary and reaches no store. It is already carried by `CLAUDE.md` and by
`agent/roles/devops.md`, and duplicating it here would put a web trap in front of a seat doing
store work. Named here only so the next seat does not go looking for it.

## The gap list

What standing up a real release path requires, ordered by what blocks what. Nothing below is
started; each is a decision or an artifact this seat does not currently hold.

1. **An Android release build script** — the `build_ios.sh` sibling, baking `.env` through
   `--dart-define-from-file` into `flutter build appbundle`, with the same pre-build banner.
   Blocks every Android step. Cheapest item on this list and the one with a working model
   already in the repo.
2. **`ios/ExportOptions.plist`** — needed for any export that is not a human in Xcode Organizer.
   Blocks 3 and 4 on iOS.
3. **Upload credentials, held outside the repo.** An App Store Connect API key (`.p8`, key id,
   issuer id) and a Play Console service-account JSON with release permissions. **Neither
   exists; where they live is a decision, not a measurement, and it is `cto`'s.** Blocks 4 and 6.
4. **Fastlane itself** — `Appfile`, `Fastfile` with `build_app` + `upload_to_testflight`, and
   `supply` for Play. **Deliberately fourth.** Fastlane wraps steps; wrapping steps that do not
   work yet produces a pipeline that fails further from its cause.
5. **Headless iOS signing.** `CODE_SIGN_STYLE = Automatic` works for a logged-in Xcode account
   and not for an unattended build. Moving to manual profiles or `match` is a decision with a
   credential-storage consequence — `cto`'s, and it depends on 3.
6. **CI wiring, last, and not before the freeze lifts.** A workflow that can upload is a
   workflow that can breach `G-018` Ruling 2 by merge alone.

## Owed elsewhere

`agent/WORKFLOWS.md` has no workflow for store submission. This skill does not create one and
`devops` does not edit that file unasked. If the roster wants the sequence above as a numbered
`W`, that is a `po`/`cto` call.
