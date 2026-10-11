# One-time phone setup (maintenance report 2026-10-10, Fix 1)

State on the CEO's Mac, checked 2026-10-10: CocoaPods installed, `pod install` done, iOS 27 runtime and
the iPhone 18 Pro simulator present and booted. Android installed the same day (command-line tools, JDK 21, SDK 35/36, AVD `thebes_pixel`).

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

## Keep them booted

    xcrun simctl boot "iPhone 18 Pro"
    export JAVA_HOME=/opt/homebrew/opt/openjdk@21 ANDROID_SDK_ROOT=/opt/homebrew/share/android-commandlinetools
    export PATH=$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH
    nohup emulator -avd thebes_pixel -no-window -no-audio > /dev/null 2>&1 &
