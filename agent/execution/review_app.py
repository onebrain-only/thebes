"""Run the team's branch locally for the reviewer, on the web (CEO 2026-10-22).

Review happens on the exact commit a team handed over, on this Mac, before the work reaches Alpha,
and never on a public URL. One codebase, so ONE platform: a web build opened in the reviewer's
internal browser. (An iOS simulator and an Android emulator were tried on 2026-10-21/22: 14 to 27
minutes per build against 80 seconds on the web, so they were dropped.) Thebes does the build (zero
tokens); the reviewer only looks:

    python3 -m agent.execution.review_queue app <item_id>          # build + run; prints the URL
    python3 -m agent.execution.review_queue app <item_id> --stop   # stop it, remove the folder
    python3 -m agent.execution.review_queue app --list

`flutter run -d web-server` on the first free port of 8124-8127, so several tickets can run side by
side. The commit is checked out in a detached worktree under agent/state/runtime/review-wt/<ticket>
(never the shared checkout, which may hold someone's unsaved work). The dev `.env` is passed by path
and never read, printed or copied.
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
READY_SECONDS = int(os.environ.get("REVIEW_APP_READY_SECONDS", "600"))
READY_MARKERS = ("is being served at", "lib/main.dart is being served")
FAILED_MARKERS = ("Could not build the application", "Error launching application")


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


def _worktree(ticket, sha, branch):
    """A detached worktree at the reviewed commit (fetched first). Returns its path."""
    path = os.path.join(_dir("review-wt"), ticket)
    repo = os.path.join(ROOT, APP_REPO)
    _git(["fetch", "--quiet", "origin"] + ([branch] if branch else []), timeout=300)
    target = sha or ("origin/%s" % branch if branch else None)
    if not target:
        raise RuntimeError("the item names no commit and no branch: nothing to run")
    if os.path.exists(os.path.join(path, ".git")):
        done = _git(["checkout", "--quiet", "--force", "--detach", target], cwd=path)
    else:
        if os.path.exists(path):           # a half-removed folder of an earlier run of ours
            _git(["worktree", "prune"], cwd=repo)
            shutil.rmtree(path, ignore_errors=True)
        done = _git(["worktree", "add", "--detach", path, target], cwd=repo)
    if done.returncode != 0:
        raise RuntimeError("cannot check out %s: %s" % (target, (done.stderr or "").strip()[:300]))
    return path


def _wait_ready(log_path, proc, seconds=READY_SECONDS):
    """Ready when the server line appears; failed as soon as flutter exits or prints a build
    failure. `proc.poll()`, not kill(pid, 0): an exited child stays a zombie and looks alive."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(3)
        try:
            text = open(log_path, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        if any(m in text for m in READY_MARKERS):
            return True, ""
        if proc.poll() is not None or any(m in text for m in FAILED_MARKERS):
            return False, text[-1500:]
    return False, "not ready after %ds" % seconds


def start(item):
    """Build and run the item's commit on the web. Returns where to look."""
    ticket = item.get("ticket") or "unknown"
    cur = running(ticket)
    if cur and not cur.get("dead"):
        if cur.get("sha") == item.get("sha"):
            return dict(cur, status="already-running")
        stop(ticket)
    wt = _worktree(ticket, item.get("sha"), item.get("branch"))
    env_file = os.path.join(ROOT, APP_REPO, ".env")
    defines = ["--dart-define-from-file=%s" % env_file] if os.path.exists(env_file) else []
    log_path = os.path.join(_dir("review-app"), "%s.log" % ticket)
    open(log_path, "w").close()            # one log per run: an old "ready" line must not count
    port = _free_port({r.get("port") for r in list_running()})
    if port is None:
        raise RuntimeError("all review ports %d-%d are busy: stop a finished review first "
                           "(`review_queue app --list`)" % (WEB_PORTS[0], WEB_PORTS[-1]))
    rec = {"ticket": ticket, "platform": "web", "sha": item.get("sha"), "branch": item.get("branch"),
           "worktree": wt, "log": log_path, "started_at": time.time(), "port": port,
           "url": "http://localhost:%d" % port}
    cmd = ["flutter", "run", "-d", "web-server", "--web-port", str(port),
           "--web-hostname", "127.0.0.1"] + defines
    with open(log_path, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=wt, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.PIPE, start_new_session=True)
    rec["pid"] = proc.pid
    with open(_state_path(ticket), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    ok, why = _wait_ready(log_path, proc)
    if not ok:
        stop(ticket)
        raise RuntimeError("the app did not start: %s (log %s)" % (why.strip()[-600:], log_path))
    evidence = os.path.join(store.RUNTIME, "review-evidence", ticket)
    os.makedirs(evidence, exist_ok=True)
    return dict(rec, status="running", evidence_dir=evidence)


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
