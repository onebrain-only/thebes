# One-time phone setup (maintenance report 2026-10-10, Fix 1)

Do this once, outside any ticket. It costs minutes now and nothing per ticket afterwards.
These are installs on the CEO's Mac, so they are the CEO's to run.

1. `brew install cocoapods`
2. Xcode: install one iOS runtime, create one simulator (iPhone 18 Pro), boot it: `xcrun simctl boot "iPhone 18 Pro"`
3. Android: install the SDK and one emulator image, start it: `emulator -avd <name> -no-snapshot-load &` (or boot with a snapshot)
4. `cd Dabbler/dabbler-code/ios && pod install`
5. Do one `flutter build ios --debug --simulator --no-pub` so the first build of the day is paid now.
6. Measure today's Chrome check once (a release web build plus the headless screenshots) and set
   `PHONE_CHECK_BUDGET_SECONDS` to it (default 180). Keep both devices booted all day.

Then, for a ticket whose diff touches `ios/`, `android/`, `lib/features/app_boot/`,
`lib/core/services/theme_service.dart`, `pubspec.yaml` or that is marked `visual:native`:

    python3 -m agent.execution.phone_check needed <changed paths>   # exit 0 = run it
    python3 -m agent.execution.phone_check run ios --app Dabbler/dabbler-code --out ios.png

Over budget it stops and the ticket passes on web evidence, with "phone check skipped: over
budget" listed for the CEO. `phone_check log` shows the measured times; after five tickets,
compare them with the Chrome time and adjust the budget.
