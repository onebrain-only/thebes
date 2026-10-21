"""Run the team's branch locally for the reviewer (CEO 2026-10-21).

Review happens on the exact commit a team handed over, on this Mac, before the work reaches Alpha,
and never on a public URL. Thebes does the build (zero tokens); the reviewer only looks:

    python3 -m agent.execution.review_queue app <item_id>          # build + run; prints where
    python3 -m agent.execution.review_queue app <item_id> --stop   # stop it, remove the folder
    python3 -m agent.execution.review_queue app --list

  web      `flutter run -d web-server` on the first free port of 8124-8127 (several tickets can
           run side by side); the reviewer opens the printed URL in its internal browser.
  android  the booted emulator (or the first AVD with an installed image, booted here); one
           ticket per device at a time.

The commit is checked out in a detached worktree under agent/state/runtime/review-wt/<ticket>
(never the shared checkout, which may hold someone's unsaved work). The dev `.env` is passed by
path and never read, printed or copied.
"""
import json
import os
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
AVD_PREFERENCE = ("Pixel8_PlayStore_API36", "Pixel8_PlayStore", "thebes_pixel")
READY_SECONDS = int(os.environ.get("REVIEW_APP_READY_SECONDS", "600"))
ANDROID_READY_SECONDS = int(os.environ.get("REVIEW_APP_ANDROID_READY_SECONDS", "1200"))  # Gradle
WEB_READY = ("is being served at", "lib/main.dart is being served")
ANDROID_READY = ("Flutter run key commands", "A Dart VM Service on")


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
    deadline = time.time() + 300
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


def _worktree(ticket, sha, branch):
    """A detached worktree at the reviewed commit (fetched first). Returns its path."""
    path = os.path.join(_dir("review-wt"), ticket)
    repo = os.path.join(ROOT, APP_REPO)
    _git(["fetch", "--quiet", "origin"] + ([branch] if branch else []), timeout=300)
    target = sha or ("origin/%s" % branch if branch else None)
    if not target:
        raise RuntimeError("the item names no commit and no branch: nothing to run")
    if os.path.exists(os.path.join(path, ".git")):
        done = _git(["checkout", "--quiet", "--detach", target], cwd=path)
    else:
        done = _git(["worktree", "add", "--detach", path, target], cwd=repo)
    if done.returncode != 0:
        raise RuntimeError("cannot check out %s: %s" % (target, (done.stderr or "").strip()[:300]))
    return path


def _wait_ready(log_path, pid, markers, seconds=READY_SECONDS):
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(3)
        try:
            text = open(log_path, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        if any(m in text for m in markers):
            return True, ""
        try:
            os.kill(pid, 0)
        except OSError:
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
    wt = _worktree(ticket, item.get("sha"), item.get("branch"))
    env_file = os.path.join(ROOT, APP_REPO, ".env")
    defines = ["--dart-define-from-file=%s" % env_file] if os.path.exists(env_file) else []
    log_path = os.path.join(_dir("review-app"), "%s.log" % ticket)
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
    elif platform == "android":
        holder = [r for r in list_running() if r.get("platform") == "android" and r["ticket"] != ticket]
        if holder:
            raise RuntimeError("the emulator is in use by %s: stop it first (`review_queue app %s "
                               "--stop`)" % (holder[0]["ticket"], holder[0]["ticket"]))
        device = _android_device()
        if not device:
            raise RuntimeError("the Android emulator did not finish booting in 5 minutes")
        cmd = ["flutter", "run", "-d", device] + defines
        shots = os.path.join(store.RUNTIME, "review-evidence", ticket)
        rec.update(device=device, screenshot_cmd="adb -s %s exec-out screencap -p > %s/<name>.png"
                   % (device, shots))
        markers = ANDROID_READY
    else:
        raise RuntimeError("platform %r is not routine: web or android (iOS only on a CEO order)" % platform)
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=wt, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.PIPE, start_new_session=True)
    rec["pid"] = proc.pid
    with open(_state_path(ticket), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    ok, why = _wait_ready(log_path, proc.pid, markers,
                          ANDROID_READY_SECONDS if platform == "android" else READY_SECONDS)
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
    if os.path.exists(wt):
        removed = _git(["worktree", "remove", "--force", wt]).returncode == 0
    try:
        os.unlink(_state_path(ticket))
    except OSError:
        pass
    return {"status": "stopped", "ticket": ticket, "worktree_removed": removed}
