"""Run the team's branch locally for the reviewer (CEO 2026-10-21).

Review happens on the exact commit a team handed over, on this Mac, before the work reaches Alpha,
and never on a public URL. Thebes does the build (zero tokens); the reviewer only looks:

    python3 -m agent.execution.review_queue app <item_id>          # build + run; prints where
    python3 -m agent.execution.review_queue app <item_id> --stop   # stop it, remove the folder
    python3 -m agent.execution.review_queue app --list

  web      `flutter run -d web-server` on the first free port of 8124-8127 (several tickets can
           run side by side); the reviewer opens the printed URL in its internal browser.
  ios      the booted iPhone simulator (or one booted here) for native/startup changes (CEO
           2026-10-21: iOS, not Android). Driven with Meta's idb, no window needed:
           `review_queue app <item_id> --shot NAME | --tap X Y | --swipe X1 Y1 X2 Y2 | --type TEXT`
           (coordinates are pixels of the last screenshot).
  android  only on request (label platform:android); one ticket per device at a time.

The commit is checked out in a detached worktree under agent/state/runtime/review-wt/<ticket>
(never the shared checkout, which may hold someone's unsaved work). The dev `.env` is passed by
path and never read, printed or copied.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402

APP_REPO = "Dabbler/dabbler-code"
WEB_PORTS = range(8124, 8128)
SDK = os.path.expanduser("~/Library/Android/sdk")
AVD_PREFERENCE = ("thebes_review", "Pixel8_PlayStore_API36", "Pixel8_PlayStore")
READY_SECONDS = int(os.environ.get("REVIEW_APP_READY_SECONDS", "600"))
ANDROID_READY_SECONDS = int(os.environ.get("REVIEW_APP_ANDROID_READY_SECONDS", "1200"))  # Gradle
WEB_READY = ("is being served at", "lib/main.dart is being served")
NATIVE_READY = ("Flutter run key commands", "A Dart VM Service on")
ANDROID_READY = NATIVE_READY
IOS_PREFERENCE = ("iPhone 17", "iPhone 17 Pro", "iPhone 18 Pro", "iPhone Air")
IOS_READY_SECONDS = int(os.environ.get("REVIEW_APP_IOS_READY_SECONDS", "1800"))  # first Xcode build


def _dir(*parts):
    path = os.path.join(store.RUNTIME, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def _state_path(ticket):
    return os.path.join(_dir("review-app"), "%s.json" % ticket)


def running(ticket):
    try:
        with open(_state_path(ticket), encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    try:
        os.kill(rec["pid"], 0)
    except (OSError, KeyError, TypeError):
        rec["dead"] = True
    return rec


def list_running():
    out = []
    for name in sorted(os.listdir(_dir("review-app"))):
        if name.endswith(".json"):
            rec = running(name[:-5])
            if rec:
                out.append(rec)
    return out


def _git(args, cwd=None, timeout=300, runner=subprocess.run):
    return runner(["git", "-C", cwd or os.path.join(ROOT, APP_REPO)] + args, capture_output=True,
                  text=True, timeout=timeout, stdin=subprocess.DEVNULL)


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _free_port(taken):
    for port in WEB_PORTS:
        if port not in taken and _port_free(port):
            return port
    return None


def pick_avd(avd_root=os.path.expanduser("~/.android/avd"), sdk=SDK):
    """THEBES_AVD, else the first preferred (then any) AVD whose system image is installed (live
    2026-10-21: thebes_pixel points at an image that is not on this Mac)."""
    if os.environ.get("THEBES_AVD"):
        return os.environ["THEBES_AVD"]
    names = [f[:-4] for f in sorted(os.listdir(avd_root)) if f.endswith(".avd")] if os.path.isdir(avd_root) else []
    for name in sorted(names, key=lambda n: (AVD_PREFERENCE.index(n) if n in AVD_PREFERENCE else 99, n)):
        try:
            cfg = open(os.path.join(avd_root, name + ".avd", "config.ini"), encoding="utf-8").read()
        except OSError:
            continue
        sysdir = next((l.split("=", 1)[1].strip() for l in cfg.splitlines()
                       if l.startswith("image.sysdir.1=")), "")
        if sysdir and os.path.isdir(os.path.join(sdk, sysdir)):
            return name
    return None


def _android_device(runner=subprocess.run):
    from agent.execution import phone_check
    device = phone_check.booted_device("android", runner)
    if device:
        return device
    avd = pick_avd()
    if not avd:
        raise RuntimeError("no Android emulator with an installed system image")
    log_path = os.path.join(_dir("review-app"), "emulator.log")
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen([os.path.join(SDK, "emulator", "emulator"), "-avd", avd, "-no-audio",
                                 "-no-boot-anim"], stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 900          # a new AVD's first (cold) boot is slow
    while time.time() < deadline:
        time.sleep(5)
        if proc.poll() is not None:
            tail = open(log_path, encoding="utf-8", errors="replace").read()[-500:]
            raise RuntimeError("emulator %s stopped: %s" % (avd, tail.strip()))
        try:
            device = phone_check.booted_device("android", runner)
            booted = device and runner(["adb", "-s", device, "shell", "getprop", "sys.boot_completed"],
                                       capture_output=True, text=True, timeout=30).stdout.strip()
        except subprocess.TimeoutExpired:          # adb hangs while the device is still booting
            continue
        if device and booted == "1":
            return device
    return None


def _ios_device(runner=subprocess.run):
    """The booted simulator, else boot an iPhone (preferred models first) and wait for it."""
    from agent.execution import phone_check
    device = phone_check.booted_device("ios", runner)
    if device:
        return device
    out = runner(["xcrun", "simctl", "list", "devices", "available", "-j"], capture_output=True,
                 text=True, timeout=60).stdout
    phones = [d for devs in (json.loads(out or "{}").get("devices") or {}).values() for d in devs
              if d.get("name", "").startswith("iPhone")]
    if not phones:
        raise RuntimeError("no iPhone simulator is installed")
    phones.sort(key=lambda d: IOS_PREFERENCE.index(d["name"]) if d["name"] in IOS_PREFERENCE else 99)
    udid = phones[0]["udid"]
    runner(["xcrun", "simctl", "boot", udid], capture_output=True, text=True, timeout=120)
    runner(["xcrun", "simctl", "bootstatus", udid, "-b"], capture_output=True, text=True, timeout=600)
    return udid


def _idb():
    """Meta's idb (CEO installed it 2026-10-22): taps and types on a simulator with no window, so
    review works while the Mac's screen is locked. The pip client lands in the user's Python bin."""
    found = shutil.which("idb") or os.path.expanduser("~/Library/Python/3.9/bin/idb")
    if not os.path.exists(found):
        raise RuntimeError("idb is not installed (brew install idb-companion; pip3 install fb-idb)")
    return found


def _ios_rec(ticket):
    rec = running(ticket) or {}
    if rec.get("platform") != "ios" or not rec.get("device"):
        raise RuntimeError("%s is not running on iOS: start it with `review_queue app <item_id>`" % ticket)
    return rec


def _density(udid, runner=subprocess.run):
    """Screenshot pixels per point (3.0 on current iPhones), from idb's own description."""
    out = runner([_idb(), "describe", "--udid", udid, "--json"], capture_output=True, text=True, timeout=60)
    try:
        return float(json.loads(out.stdout).get("screen_dimensions", {}).get("density") or 3.0)
    except ValueError:
        return 3.0


def _ui(ticket, args, runner=subprocess.run):
    rec = _ios_rec(ticket)
    done = runner([_idb(), "ui"] + args + ["--udid", rec["device"]], capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise RuntimeError("idb ui %s failed: %s" % (args[0], (done.stderr or "").strip()[:300]))
    return rec


def ios_tap(ticket, x, y, runner=subprocess.run):
    """Tap at screenshot pixel (x, y)."""
    rec = _ios_rec(ticket)
    d = _density(rec["device"], runner)
    _ui(ticket, ["tap", str(int(x / d)), str(int(y / d))], runner)
    return {"tapped_pixels": [x, y], "points": [int(x / d), int(y / d)]}


def ios_swipe(ticket, x1, y1, x2, y2, runner=subprocess.run):
    """Swipe between two screenshot pixels (scroll: swipe up to move the content up)."""
    rec = _ios_rec(ticket)
    d = _density(rec["device"], runner)
    _ui(ticket, ["swipe"] + [str(int(v / d)) for v in (x1, y1, x2, y2)], runner)
    return {"swiped_pixels": [x1, y1, x2, y2]}


def ios_type(ticket, text, runner=subprocess.run):
    """Type into the focused field (tap the field first)."""
    _ui(ticket, ["text", text], runner)
    return {"typed": len(text)}


def shot(ticket, name, runner=subprocess.run):
    """Save a screenshot of the running app into the ticket's evidence folder."""
    rec = running(ticket) or {}
    path = os.path.join(store.RUNTIME, "review-evidence", ticket,
                        name if name.lower().endswith(".png") else name + ".png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if rec.get("platform") == "ios":
        runner(["xcrun", "simctl", "io", rec["device"], "screenshot", path], capture_output=True, timeout=60)
    elif rec.get("platform") == "android":
        with open(path, "wb") as fh:
            runner(["adb", "-s", rec["device"], "exec-out", "screencap", "-p"], stdout=fh, timeout=60)
    else:
        raise RuntimeError("web: take the screenshot from your browser and save it to %s" % path)
    return {"screenshot": path}


# A native build in a fresh folder rebuilds Xcode/Gradle from scratch (live 2026-10-22: 27 minutes on
# iOS). Native platforms therefore keep ONE folder each that is moved to the next ticket's commit, so
# only what changed is rebuilt; their ignored build caches survive. Web keeps a folder per ticket.
NATIVE_SLOTS = {"ios": "_ios", "android": "_android"}


def _ios_prepare(wt, log_path, runner=subprocess.run):
    """Resolve the Swift packages BEFORE flutter run. Flutter asks Xcode for build settings under a
    short timeout; when a new commit makes Xcode re-resolve Firebase & co. first, that times out and
    flutter says "No Xcode build settings have been found" (live 2026-10-22, KAN-620)."""
    with open(log_path, "a", encoding="utf-8") as log:
        for cmd, limit in ((["flutter", "pub", "get"], 600),
                           (["xcodebuild", "-resolvePackageDependencies", "-workspace",
                             "ios/Runner.xcworkspace", "-scheme", "Runner"], 1800)):
            log.write("$ %s\n" % " ".join(cmd)); log.flush()
            done = runner(cmd, cwd=wt, stdout=log, stderr=subprocess.STDOUT, timeout=limit,
                          stdin=subprocess.DEVNULL)
            if done.returncode != 0:
                raise RuntimeError("iOS preparation failed at `%s` (log %s)" % (" ".join(cmd[:2]), log_path))


def _worktree(name, sha, branch):
    """A detached worktree at the reviewed commit (fetched first). Returns its path."""
    path = os.path.join(_dir("review-wt"), name)
    repo = os.path.join(ROOT, APP_REPO)
    _git(["fetch", "--quiet", "origin"] + ([branch] if branch else []), timeout=300)
    target = sha or ("origin/%s" % branch if branch else None)
    if not target:
        raise RuntimeError("the item names no commit and no branch: nothing to run")
    if os.path.exists(os.path.join(path, ".git")):
        done = _git(["checkout", "--quiet", "--force", "--detach", target], cwd=path)
        if done.returncode == 0:
            _git(["clean", "-fdq"], cwd=path)      # untracked files go; ignored build caches stay
    else:
        if os.path.exists(path):           # a half-removed folder of an earlier run of ours
            _git(["worktree", "prune"], cwd=repo)
            shutil.rmtree(path, ignore_errors=True)
        done = _git(["worktree", "add", "--detach", path, target], cwd=repo)
    if done.returncode != 0:
        raise RuntimeError("cannot check out %s: %s" % (target, (done.stderr or "").strip()[:300]))
    return path


FAILED_MARKERS = ("Could not build the application", "Error launching application")


def _wait_ready(log_path, proc, markers, seconds=READY_SECONDS):
    """Ready when a marker appears; failed as soon as flutter exits or prints a build failure.
    `proc.poll()`, not kill(pid, 0): an exited child stays a zombie and looks alive."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(3)
        try:
            text = open(log_path, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        if any(m in text for m in markers):
            return True, ""
        if proc.poll() is not None or any(m in text for m in FAILED_MARKERS):
            return False, text[-1500:]
    return False, "not ready after %ds" % seconds


def start(item, platform=None):
    """Build and run the item's commit. Returns where to look."""
    ticket = item.get("ticket") or "unknown"
    platform = platform or item.get("platform") or "web"
    cur = running(ticket)
    if cur and not cur.get("dead"):
        if cur.get("sha") == item.get("sha") and cur.get("platform") == platform:
            return dict(cur, status="already-running")
        stop(ticket)
    if platform in NATIVE_SLOTS:
        holder = [r for r in list_running() if r.get("platform") == platform and r["ticket"] != ticket]
        if holder:
            raise RuntimeError("the %s device is in use by %s: stop it first (`review_queue app %s "
                               "--stop`)" % (platform, holder[0]["ticket"], holder[0]["ticket"]))
    wt = _worktree(NATIVE_SLOTS.get(platform, ticket), item.get("sha"), item.get("branch"))
    env_file = os.path.join(ROOT, APP_REPO, ".env")
    defines = ["--dart-define-from-file=%s" % env_file] if os.path.exists(env_file) else []
    log_path = os.path.join(_dir("review-app"), "%s.log" % ticket)
    open(log_path, "w").close()            # one log per run: an old "ready" line must not count
    rec = {"ticket": ticket, "platform": platform, "sha": item.get("sha"),
           "branch": item.get("branch"), "worktree": wt, "log": log_path, "started_at": time.time()}
    if platform == "web":
        port = _free_port({r.get("port") for r in list_running()})
        if port is None:
            raise RuntimeError("all review ports %d-%d are busy: stop a finished review first "
                               "(`review_queue app --list`)" % (WEB_PORTS[0], WEB_PORTS[-1]))
        cmd = ["flutter", "run", "-d", "web-server", "--web-port", str(port),
               "--web-hostname", "127.0.0.1"] + defines
        rec.update(port=port, url="http://localhost:%d" % port)
        markers = WEB_READY
    elif platform == "ios":
        device = _ios_device()
        _ios_prepare(wt, log_path)
        cmd = ["flutter", "run", "-d", device] + defines
        rec.update(device=device, how=("review_queue app <item_id> --shot <name> | --tap X Y | "
                                       "--swipe X1 Y1 X2 Y2 | --type TEXT  (screenshot pixels)"))
        markers = NATIVE_READY
    elif platform == "android":
        holder = [r for r in list_running() if r.get("platform") == "android" and r["ticket"] != ticket]
        if holder:
            raise RuntimeError("the emulator is in use by %s: stop it first (`review_queue app %s "
                               "--stop`)" % (holder[0]["ticket"], holder[0]["ticket"]))
        device = _android_device()
        if not device:
            raise RuntimeError("the Android emulator did not finish booting in 15 minutes")
        cmd = ["flutter", "run", "-d", device] + defines
        shots = os.path.join(store.RUNTIME, "review-evidence", ticket)
        rec.update(device=device, screenshot_cmd="adb -s %s exec-out screencap -p > %s/<name>.png"
                   % (device, shots))
        markers = ANDROID_READY
    else:
        raise RuntimeError("platform %r is not one of web, ios, android" % platform)
    with open(log_path, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=wt, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.PIPE, start_new_session=True)
    rec["pid"] = proc.pid
    with open(_state_path(ticket), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    ok, why = _wait_ready(log_path, proc, markers,
                          {"android": ANDROID_READY_SECONDS, "ios": IOS_READY_SECONDS}.get(platform, READY_SECONDS))
    if not ok:
        stop(ticket)
        raise RuntimeError("the app did not start: %s (log %s)" % (why.strip()[-600:], log_path))
    os.makedirs(os.path.join(store.RUNTIME, "review-evidence", ticket), exist_ok=True)
    return dict(rec, status="running",
                evidence_dir=os.path.join(store.RUNTIME, "review-evidence", ticket))


def stop(ticket):
    rec = running(ticket) or {}
    pid = rec.get("pid")
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass
    wt = rec.get("worktree") or os.path.join(store.RUNTIME, "review-wt", ticket)
    removed = False
    if os.path.basename(wt) in NATIVE_SLOTS.values():
        pass                                       # kept: the next native review builds incrementally
    elif os.path.exists(wt):
        removed = _git(["worktree", "remove", "--force", wt]).returncode == 0
    try:
        os.unlink(_state_path(ticket))
    except OSError:
        pass
    return {"status": "stopped", "ticket": ticket, "worktree_removed": removed}
