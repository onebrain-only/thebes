---
name: drive-the-app
description: Get a running Dabbler app in front of you and drive it, on the surface that actually works today. Use when a ticket must be tested end to end, when a "done" claim needs checking against real running behaviour, when a bug must be reproduced, or when you need a screenshot of the real app rather than a widget test. Covers choosing a surface (Android emulator, Chrome/CanvasKit, iOS simulator, web integration_test), starting it, driving it by screenshot and coordinate — including tapping and typing on iOS, where simctl has no tap command — and the traps that make a run lie to you.
---

# Drive the App

The only seat that opens the running Dabbler app is `qa`. This is how, in steps, on the
surfaces measured to work **on this machine**.

Every step below is marked. **[M]** = measured, with the date it was last run.
**[U]** = untested here; inherited or documented but not executed. Do not present a `[U]`
step's outcome as fact — run it and upgrade it, or say it is untested in your report.

Repo root throughout: `/Users/moatazmustapha/Desktop/Thebes/Dabbler/dabbler-code`.
**Use absolute paths.** A relative `agent/status/` resolves against the project tree and
silently creates a second, unread log.

---

## Step 0 — Pick the surface before you start anything

Do not default to web. **[M] 2026-09-06** — surface availability was measured today and
is not what the older prose assumed:

| Surface | State today | Use it for |
|---|---|---|
| **Android emulator** (`Dabbler_test`) | **[M]** works — `integration_test` runs green in 12s | automated harness runs; ADB screenshot/tap driving |
| **Chrome, `flutter run`** | **[U]** documented, not run today | manual screenshot-and-coordinate driving |
| **iOS simulator** | **[M]** **works** — builds and runs; see Step 2c | manual screenshot-and-coordinate driving; reaching a route directly with `--route` |
| **macOS desktop** | **[M]** not configured — `No macOS desktop project configured` | nothing |
| **Web + `integration_test`** | **[M]** **BLOCKED** two ways — see Trap 3 | nothing |

Rule of thumb: **an automated harness run goes to Android. Manual driving goes to Chrome, or
to iOS when the ticket is iOS-specific.** iOS was blocked until 2026-09-06 and is not any more —
see Step 2c.

---

## Step 1 — See what is actually connected

```bash
cd "/Users/moatazmustapha/Desktop/Thebes/Dabbler/dabbler-code"
flutter devices
```

**[M] 2026-09-06.** With nothing booted this returns only `macOS` and `Chrome`. An
emulator or simulator appears here **only after you boot it** — its absence is not a
finding.

Boot the Android emulator **[M] 2026-09-06**:

```bash
flutter emulators --launch Dabbler_test
sleep 45
~/Library/Android/sdk/platform-tools/adb devices     # expect: emulator-5554  device
```

`flutter emulators` **[M]** lists exactly two: `Dabbler_test` (android) and
`apple_ios_simulator` (ios).

---

## Step 2a — Run the automated harness (Android)

`integration_test/app_test.dart` boots the **real** app through the production bootstrap
(`Environment.load` → Firebase → ThemeService → AppTheme → Supabase → `runApp`) and
asserts a `MaterialApp` mounted. It is a launch smoke test, not a feature test.

**[M] 2026-09-06 — this is the command that works:**

```bash
cd "/Users/moatazmustapha/Desktop/Thebes/Dabbler/dabbler-code"
flutter test integration_test/app_test.dart -d emulator-5554 --dart-define-from-file=.env
```

Measured result: **exit 0, `00:12 +1: All tests passed!`**. It leaves the git tree clean —
`git status --porcelain` was empty afterwards.

**Do not use `scripts/run_integration_tests.sh`.** **[M] 2026-09-06** — two independent reasons.
It auto-detects a booted *iOS* simulator and routes there regardless of what you wanted; and
**both its `exec` lines (`:40`, `:45`) omit `--dart-define-from-file=.env`**. `.env` is not in
`pubspec.yaml`'s `assets:`, so `Environment.load()` finds no asset, falls back to
`dotenv.testLoad(fileInput: '')`, and `_validate()` throws
`Missing environment variables: SUPABASE_URL, SUPABASE_ANON_KEY, APP_NAME, ENVIRONMENT` before
any test runs. Call `flutter test` directly with `-d` and the dart-define flag.

**[M] This run hits LIVE Supabase and authenticates as a real user.** The measured run
logged `FCM token saved for user ec959ff7-46ef-4bf2-aab4-3515b81f5846` and loaded 20 real
notifications from the emulator's persisted session. It is not hermetic. Treat every run
as touching production data, and never point it at anything you would not want written to.

---

## Step 2b — Drive the app by hand (Chrome)

**[U] — documented in `agent/roles/qa.md`, not executed in this pass.**

```bash
flutter run -d chrome --dart-define-from-file=.env
```

**The `--dart-define-from-file=.env` flag is not optional** — without it the app hangs on
the launch screen. Test the local `localhost:<port>` build, never `canary.dabbler.pro`
(that is `devops`' release-verification surface) and **never** `app.dabbler.pro` (real
user data).

Then drive with `mcp__claude-in-chrome__computer` — screenshot, click, type, scroll — and
`resize_window` for the viewport. Cover **both** ~390×844 (phone, the primary form factor)
and desktop width as full passes; desktop web is a supported surface and a desktop-only
bug is a real bug at its real severity.

### Driving Android by ADB instead **[U]**

`computer-use` cannot see the Android emulator on this machine (a Claude Desktop rollout
flag, `"androidEmulator":{"status":"unsupported"}`). Use ADB over plain Bash:

```bash
ADB=~/Library/Android/sdk/platform-tools/adb

$ADB -s emulator-5554 shell screencap -p /sdcard/qa_shot.png
$ADB -s emulator-5554 pull /sdcard/qa_shot.png <local-path>.png    # then Read the file
$ADB -s emulator-5554 shell input tap <x> <y>
$ADB -s emulator-5554 shell input text "some%stext"                # %s = space
$ADB -s emulator-5554 shell input swipe 500 1500 500 500 300
$ADB -s emulator-5554 shell input keyevent KEYCODE_BACK
$ADB -s emulator-5554 logcat -v time | grep -i flutter
```

Tap coordinates are in the **device's native pixels**, not the screenshot's displayed
size. If a screenshot came back scaled, convert first:
`real_x = displayed_x * (device_width / displayed_width)`.

---

---

## Step 2c — Drive the app by hand (iOS simulator) **[M] 2026-09-06**

```bash
cd "/Users/moatazmustapha/Desktop/Thebes/Dabbler/dabbler-code"
xcrun simctl list devices booted                       # get the UDID
flutter run -d <udid> --dart-define-from-file=.env
```

`--dart-define-from-file=.env` is **not optional** here either — see the
`run_integration_tests.sh` note in Step 2a for why the fallback cannot work.

**Reach a route directly, without navigating to it:**

```bash
flutter run -d <udid> --dart-define-from-file=.env --route=/enter-password
```

Measured working: the router logs `[Router] loc=/enter-password ... allow (unauth on auth page)`.
This is how you test a screen that sits behind a broken one. **`xcrun simctl openurl <udid>
"dabbler:///enter-password"` does NOT work** — no router activity at all, despite the `dabbler`
scheme and `FlutterDeepLinkingEnabled` both being set in `ios/Runner/Info.plist`. Unexplained;
worth its own investigation, since deep links are a shipped feature.

### Tapping and typing — there is no `simctl` tap

`xcrun simctl` has **no tap or input command** (unlike ADB), and neither `idb` nor `cliclick` is
installed on this machine. What works is `System Events` clicking Mac-desktop coordinates over
the Simulator window.

**Read the mapping live every session — never hardcode it; the window moves.**

```bash
osascript -e 'tell application "System Events" to tell process "Simulator" \
  to get {position, size} of group 1 of window 1'
# -> 670, 168, 402, 874     origin x,y on the desktop ; size in device POINTS
```

`group 1` is the device screen itself, excluding the bezel and toolbar. Screenshots come back at
**3×** those points (1206×2622 for an iPhone 16 Pro), so:

```
mac_x = origin_x + screenshot_x / 3
mac_y = origin_y + screenshot_y / 3
```

```bash
# tap
osascript -e "tell application \"System Events\" to click at {$MX, $MY}"

# type — Simulator MUST be frontmost first
osascript -e 'tell application "Simulator" to activate'
osascript -e "tell application \"System Events\" to keystroke \"$TEXT\""

# screenshot, then Read the file
xcrun simctl io <udid> screenshot /path/out.png
```

**The silent failure that will waste your time:** typing without activating Simulator first
*focuses* the field — you can see the purple border and the caret in the screenshot — but enters
no text. It looks exactly like a broken text field. Activate first, every time.

Typing also needs *I/O ▸ Keyboard ▸ Connect Hardware Keyboard* enabled (it was already on here;
check with the menu-item's `AXMenuItemMarkChar` if text still will not land).

**Accessibility works, and is a better handle than coordinates.** The simulator does expose a
real AX tree — a click resolved to
`button 1 of group 1 of … sheet 1 of group 3 of group 15 of group 1 of window …`. A shallow
`entire contents` of `window 1` returns only the bezel buttons and hides this, so do not conclude
from that alone that the tree is unavailable.

### Two iOS-only traps that will break a scripted run

**TWO native permission alerts fire on a fresh install, not one.** *"Dabbler" Would Like to
Send You Notifications*, then *Allow "Dabbler" to use your location?* — and the location one has
**three** buttons (*Allow Once*, *Allow While Using App*, *Don't Allow*), so a script written for
a two-button alert mis-taps. Both are **SpringBoard** alerts outside the Flutter view:
`tester.tap` cannot reach them, `find.text` will not see them, and a fresh-install
`integration_test` hangs. `xcrun simctl privacy` has no service for notifications, so dismiss by
coordinate or avoid triggering the requests during tests.

**They swallow input silently, and that is the dangerous part — worse than hanging.** With an
alert up, every tap and keystroke goes to the alert and never reaches Flutter. The screen
afterwards is **indistinguishable from a login that was attempted and rejected**: empty form, no
session, no error. **[M] 2026-09-06 — this cost a full run and was nearly filed as an app
defect.** Only the absence of any auth activity in the log revealed that no attempt had been made.

> **The rule: screenshot before you type, every time, and confirm the app — not a dialog — has
> focus. Never report a failure from a screenshot alone; require a log line proving the action
> reached the network.** A clean launch last run is not evidence of a clean launch this run.

**A persisted session makes a login test pass vacuously.** A previously-installed app boots
straight past auth — `[Router] redirect (authed on auth page) -> /home` and an `FCM token saved
for user <uuid>` line. Clear it first, verified working:

```bash
xcrun simctl uninstall <udid> app.dabbler.pro
```

The next launch then logs `Can't refresh session, no refresh token found` and stops on
`/landing`. Note the bundle id is **`app.dabbler.pro`** (`ios/Runner.xcodeproj/project.pbxproj:503`)
— the `.maestro/` flows' `com.onebrain.dabbler` is stale and would not even launch.

---

## The traps that make a run lie to you

Trap 4 is kept as a **resolved** entry rather than deleted, because the stale version of it
caused real damage and the correction is worth reading. Two more iOS-only traps live in Step 2c.

### Trap 1 — CanvasKit gives you no DOM **[U, inherited; measured 2026-08-29]**

Dabbler's web build is CanvasKit. The page is a canvas: no readable DOM, no accessibility
tree, no trustworthy `aria-label`s. `read_page {filter:"interactive"}` returns one generic
node, `document.body.innerText` is empty, `flt-semantics-host` has zero children.

**You work by screenshot and coordinate. Never "find" an element by DOM query, text
content, or accessibility role.** A call that tries returns nothing — and reporting that
nothing as a missing button is a false bug. This is also why the `browser` skill's
`@e1`/`@e2` element-ref model does not apply to you.

### Trap 2 — `read_network_requests` only captures from the moment you arm it **[U, inherited]**

Arm it (call once) → act → read. Calling it after the fact and seeing nothing means you
forgot to arm it, **not** that no request happened. This is your substitute for database
access: verify persistence by reloading and re-checking, never by querying Postgres.

### Trap 3 — the web integration_test path does not exist here **[M] 2026-09-06**

Two independent blockers, both measured today:

- `flutter test integration_test/app_test.dart -d chrome` exits with
  **`Web devices are not supported for integration tests yet.`** `flutter test` cannot
  drive web at all.
- The documented alternative, `flutter drive` + ChromeDriver, has **neither half present**:
  `chromedriver` is not on `PATH` and not under `/opt/homebrew`, `/usr/local` or
  `~/Downloads`; and `test_driver/` does not exist in the repo — `flutter drive` for web
  requires a `test_driver/integration_test.dart` entry point that has never been written.

So the gap on web is **setup that was never done**, not a tool that is forbidden. See the
`#356` note in `agent/roles/qa.md`.

### Trap 4 — RESOLVED 2026-09-06. iOS is no longer blocked. **[M]**

This trap used to say every iOS build died in SwiftPM because the space in `One Brain` was
percent-encoded twice (`One%20Brain` in `NSFilePath` vs `One%2520Brain` in `NSURL`), so the
resolver looked for a directory literally named `One%20Brain`.

**The `One Brain` → `Thebes` rename removed the space and the bug with it.** Measured today from
`/Users/moatazmustapha/Desktop/Thebes/Dabbler/dabbler-code`: SwiftPM resolved all ~20 packages,
`Running pod install... 810ms`, `Xcode build done. 162.1s`, app launched and ran on
iPhone 16 Pro / iOS 18.5.

**This entry stayed stale for a while and it cost us.** Reading "iOS is blocked" stopped anyone
opening the app on iOS, and a screen that renders blank on `/auth-welcome` sat undiscovered
behind it. If you find a `[M]` line here that contradicts what your machine just did, **trust
your machine and fix the line** — that is the whole point of the `[M]`/`[U]` marking.

What to still expect: the **first** build is ~8 minutes wall clock, almost all of it one-time
SwiftPM clones (`firebase-ios-sdk`, `abseil-cpp-binary`, `GoogleAppMeasurement`, …). It looks
like a hang and is not. Later launches are well under a minute.

### Trap 5 — an HTTP 200 on `*.dabbler.pro` is not evidence a file exists **[U, inherited; measured 2026-08-29]**

Cloudflare Pages' SPA fallback serves the same `index.html` for *any* unmatched path — a
real 200, real `text/html`, identical bytes. Before escalating "sensitive path X is
exposed", **run the discriminator**: fetch the suspect path, a known-nonexistent path, and
a known-real asset (`/flutter_bootstrap.js`). If the suspect matches the nonexistent one
in size, content-type and hash, nothing is served there.

---

## Step 3 — Report honestly

- **Untested is never reported as passing.** A feature you could not log into is
  *blocked*, never *clean*.
- **Never report an absence without confirming the check could have found the thing.**
  Before filing "there is no error state", confirm you triggered the error condition.
  Before filing "the button is missing", confirm you screenshotted the right scroll
  position and viewport.
- Say which surface you ran on. "It works" means nothing without "on Android emulator,
  `integration_test`, exit 0".
- Leave the tree clean. Run `git status --porcelain` before you report and paste it. If a
  run left artefacts, say where they are — do not `git clean` them.
- You never fix what you find; findings become tickets for the owning specialist.

## Read, don't run

`.maestro/dabbler_tests/` holds 12 YAML flows (account creation, login, OTP
rate-limit/invalid/expired, password reset, session expiry, find-nearby-venue). Read them
as a source of intended-behaviour cases. You do not run Maestro.
