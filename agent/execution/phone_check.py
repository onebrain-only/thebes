"""A phone check for visual work (maintenance report 2026-10-10, Fix 1).

A broken native screen passes widget tests and headless Chrome, and comes back hours later as a
new round. This looks at the app on an already-booted iOS simulator or Android emulator, only
when the diff touches native or startup code, and NEVER costs more than the Chrome check:

    PHONE_CHECK_BUDGET_SECONDS   the budget; measure the Chrome check once and set it
    one shared lock per device   only one team drives a device at a time
    timebox                      over budget -> stop; the ticket passes on web evidence and the
                                 skip is listed for the CEO ("phone check skipped: over budget")

    python3 -m agent.execution.phone_check needed <changed-path>...
    python3 -m agent.execution.phone_check run ios|android --app <dir> [--out shot.png]
    python3 -m agent.execution.phone_check log          # the measured times, per ticket

Devices are booted once, outside any ticket (see agent/scripts/phone-setup.md); this module
never cold-boots one. Written without a device on the machine: the pure parts are tested, the
device commands are the standard `xcrun simctl` / `adb` / `flutter` calls.
"""
import argparse
import fcntl
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNTIME = os.path.join(ROOT, "agent", "state", "runtime", "phone-check")
PHONE_CHECK_BUDGET_SECONDS = int(os.environ.get("PHONE_CHECK_BUDGET_SECONDS", "180"))
TRIGGERS = ("ios/", "android/", "lib/features/app_boot/", "lib/core/services/theme_service.dart",
            "pubspec.yaml")


def needed(paths, labels=()):
    """True when the change touches native/startup code or the ticket says `visual:native`."""
    if "visual:native" in (labels or ()):
        return True
    return any(p.lstrip("./").startswith(t) or p.lstrip("./") == t.rstrip("/")
               for p in paths for t in TRIGGERS)


def booted_device(platform, runner=subprocess.run):
    """Id of the already-booted simulator/emulator, or None. Never boots one."""
    if platform == "ios":
        out = runner(["xcrun", "simctl", "list", "devices", "booted", "-j"],
                     capture_output=True, text=True, timeout=30).stdout
        for devs in (json.loads(out or "{}").get("devices") or {}).values():
            for d in devs:
                if d.get("state") == "Booted":
                    return d["udid"]
        return None
    out = runner(["adb", "devices"], capture_output=True, text=True, timeout=30).stdout
    for line in out.splitlines()[1:]:
        if line.strip().endswith("device"):
            return line.split()[0]
    return None


class Lock:
    """One team per device at a time (flock on a file in the shared runtime)."""

    def __init__(self, device, wait_seconds=0):
        os.makedirs(RUNTIME, exist_ok=True)
        self.path = os.path.join(RUNTIME, "device-%s.lock" % device)
        self.wait = wait_seconds

    def __enter__(self):
        self.fh = open(self.path, "w")
        deadline = time.time() + self.wait
        while True:
            try:
                fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.time() >= deadline:
                    self.fh.close()
                    raise TimeoutError("another team is driving this device")
                time.sleep(2)

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def record(entry):
    os.makedirs(RUNTIME, exist_ok=True)
    with open(os.path.join(RUNTIME, "measured.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def run(platform, app_dir, out_png, budget=None, runner=subprocess.run, bundle="app.dabbler.pro"):
    """Install+launch the debug build on the booted device and take a screenshot, inside the
    budget. Returns {status: ok|skipped|failed, seconds, reason}."""
    budget = budget or PHONE_CHECK_BUDGET_SECONDS
    started = time.time()
    device = booted_device(platform, runner)
    if not device:
        result = {"status": "skipped", "reason": "no booted %s device" % platform}
    else:
        try:
            with Lock(device):
                left = lambda: max(1, int(budget - (time.time() - started)))   # noqa: E731
                # incremental debug build on an already-built project, then launch + screenshot
                env_file = os.path.join(app_dir, ".env")   # gitignored dev keys: without them the
                runner(["flutter", "build", "ios" if platform == "ios" else "apk", "--debug",  # app stops on "Missing environment variables"
                        "--no-pub"] + (["--simulator"] if platform == "ios" else [])
                       + (["--dart-define-from-file=%s" % env_file]
                          if os.path.exists(env_file) else []),
                       cwd=app_dir, check=True, timeout=left(), capture_output=True)
                if platform == "ios":
                    runner(["flutter", "install", "-d", device], cwd=app_dir,
                           check=True, timeout=left(), capture_output=True)
                    runner(["xcrun", "simctl", "launch", device, bundle], check=True,
                           timeout=left(), capture_output=True)
                    time.sleep(6)
                    runner(["xcrun", "simctl", "io", device, "screenshot", out_png],
                           check=True, timeout=left(), capture_output=True)
                else:
                    runner(["flutter", "install", "-d", device], cwd=app_dir,
                           check=True, timeout=left(), capture_output=True)
                    runner(["adb", "-s", device, "shell", "monkey", "-p", bundle, "-c",
                            "android.intent.category.LAUNCHER", "1"], check=True,
                           timeout=left(), capture_output=True)
                    time.sleep(6)
                    with open(out_png, "wb") as fh:
                        runner(["adb", "-s", device, "exec-out", "screencap", "-p"],
                               stdout=fh, check=True, timeout=left())
                result = {"status": "ok", "screenshot": out_png}
        except subprocess.TimeoutExpired:
            result = {"status": "skipped", "reason": "phone check skipped: over budget (%ds)" % budget}
        except TimeoutError as exc:
            result = {"status": "skipped", "reason": "phone check skipped: %s" % exc}
        except (subprocess.CalledProcessError, OSError) as exc:
            result = {"status": "failed", "reason": str(exc)[:300]}
    result["seconds"] = round(time.time() - started, 1)
    result["platform"] = platform
    record(dict(result, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.phone_check", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("needed"); n.add_argument("paths", nargs="*")
    n.add_argument("--label", action="append", default=[])
    r = sub.add_parser("run"); r.add_argument("platform", choices=("ios", "android"))
    r.add_argument("--app", required=True); r.add_argument("--out", default="phone-check.png")
    r.add_argument("--bundle", default="app.dabbler.pro", help="app id to launch")
    sub.add_parser("log")
    ns = ap.parse_args(argv)
    if ns.cmd == "needed":
        yes = needed(ns.paths, ns.label)
        print(json.dumps({"needed": yes, "budget_seconds": PHONE_CHECK_BUDGET_SECONDS}))
        return 0 if yes else 1
    if ns.cmd == "log":
        path = os.path.join(RUNTIME, "measured.jsonl")
        print(open(path).read() if os.path.exists(path) else "nothing measured yet")
        return 0
    out = run(ns.platform, ns.app, ns.out, bundle=ns.bundle)
    print(json.dumps(out, indent=2))
    return 0 if out["status"] in ("ok", "skipped") else 2


if __name__ == "__main__":
    sys.exit(main())
