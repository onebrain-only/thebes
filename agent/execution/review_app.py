"""Run the team's branch locally for the reviewer, on the web (CEO 2026-10-22).

Review happens on the exact commit a team handed over, on this Mac, before the work reaches Alpha,
and never on a public URL. One codebase, so ONE platform: a web build opened in the reviewer's
internal browser. (Phone simulators were tried on 2026-10-21/22: 14 to 27 minutes per build against
80 seconds on the web, so they were dropped.) Thebes does the build (zero
tokens); the reviewer only looks:

    python3 -m agent.execution.review_queue app <item_id>          # build + run; prints the URL
    python3 -m agent.execution.review_queue app <item_id> --stop   # stop it, remove the folder
    python3 -m agent.execution.review_queue app --list

`flutter build web --release` ONCE per commit sha (cached under runtime/review-build/<sha>), served
statically on the first free port of 8124-8127, so several tickets can run side by side. The URL is
printed only after a headless browser has seen `flt-semantics-placeholder` (the app really drew, 60s);
otherwise the run fails closed with "build not ready" and no PASS or FAIL can be recorded for it (live
2026-10-22: six tickets parked on a blank canvas).

The commit is checked out in a detached worktree under agent/state/runtime/review-wt/<ticket>
(never the shared checkout, which may hold someone's unsaved work). The dev `.env` is passed by path
and never read, printed or copied.
"""
import glob
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
# The Alpha messaging Worker's public base URL (non-secret; docs/messaging/live-worker-kan566.md). Without
# these two defines the Messages tab gets the unavailable repository and never calls msg_my_conversations.
MESSAGING_WORKER_URL = "https://dabbler-messaging-staging.dabbler-sport.workers.dev"
# The build is given this same-origin path, not the Worker URL: the Worker's CORS list is exact-match
# (https://{canary,alpha,app}.dabbler.pro) and answers a preflight from http://localhost:812x with a 404 and no
# allow-origin header, so the browser blocked every call and the chat drew its offline state (KAN-607). The
# static server forwards this prefix to the Worker, so the browser never makes a cross-origin call.
MESSAGING_API_BASE_URL = "/__worker"
MESSAGING_ACCESS_MODE = "all"
WEB_PORTS = range(8124, 8128)
# The old web marker ("is being served at") printed before the app compiled, so a blank canvas looked
# ready (KAN-593, 607, 612, 620, 589, 622). Web is ready only when RENDER_MARKER is seen in the DOM.
RENDER_MARKER = "flt-semantics-placeholder"
RENDER_SECONDS = int(os.environ.get("REVIEW_APP_RENDER_SECONDS", "60"))
BUILD_SECONDS = int(os.environ.get("REVIEW_APP_BUILD_SECONDS", "1800"))


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
        if name.endswith(".json") and not name.endswith(".render.json"):
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


# ---------------------------------------------------------------- build once per sha, serve static
def _sha_dir(sha):
    return os.path.join(_dir("review-build"), sha)


def _defines_key(defines):
    """What the build was given, minus the .env path (its content is never read here)."""
    return "\n".join(d for d in defines if not d.startswith("--dart-define-from-file="))


def cached_build(sha, defines=None):
    """The finished release build of this commit, or None. `.complete` is written last, so a build
    that died half way is never served. With `defines`, a build made with other messaging defines is not
    a hit (an old build points at the Worker directly and cannot reach it from localhost)."""
    done = os.path.join(_sha_dir(sha), ".complete")
    if not os.path.exists(done):
        return None
    if defines is not None:
        try:
            with open(done, encoding="utf-8") as fh:
                if fh.read() != _defines_key(defines):
                    return None
        except OSError:
            return None
    return os.path.join(_sha_dir(sha), "web")


def build_web(wt, sha, defines, log_path, runner=subprocess.run):
    """`flutter build web --release` once per sha. Returns (served_dir, cached)."""
    hit = cached_build(sha, defines)
    if hit:
        return hit, True
    with open(log_path, "a", encoding="utf-8") as log:
        cmd = ["flutter", "build", "web", "--release"] + defines
        log.write("$ %s\n" % " ".join(cmd)); log.flush()
        done = runner(cmd, cwd=wt, stdout=log, stderr=subprocess.STDOUT, timeout=BUILD_SECONDS,
                      stdin=subprocess.DEVNULL)
    built = os.path.join(wt, "build", "web")
    if done.returncode != 0 or not os.path.exists(os.path.join(built, "index.html")):
        raise RuntimeError("build not ready: `flutter build web --release` failed (log %s)" % log_path)
    final = _sha_dir(sha)
    shutil.rmtree(final, ignore_errors=True)
    os.makedirs(final)
    shutil.copytree(built, os.path.join(final, "web"))
    with open(os.path.join(final, ".complete"), "w", encoding="utf-8") as fh:
        fh.write(_defines_key(defines))
    return os.path.join(final, "web"), False


def _render_path(ticket):
    return os.path.join(_dir("review-app"), "%s.render.json" % ticket)


def render_record(ticket):
    """Outcome of the last web start for this ticket: {rendered, sha, reason, at} or None. It outlives
    `stop`, so the verdict gate in review_queue still sees it after the app is shut down."""
    try:
        with open(_render_path(ticket), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _record_render(ticket, sha, rendered, reason=""):
    with open(_render_path(ticket), "w", encoding="utf-8") as fh:
        json.dump({"rendered": bool(rendered), "sha": sha, "reason": reason, "at": time.time()}, fh)


BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PLAYWRIGHT_CHROMIUM = os.path.expanduser(
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium")


def find_browser(environ=None, exists=os.path.exists, globber=glob.glob):
    """The browser that proves a render, or None. Order: THEBES_REVIEW_BROWSER, Playwright's Chromium,
    Brave, Google Chrome. An explicit THEBES_REVIEW_BROWSER is taken as written, wrong or not: a bad
    path must fail closed, never fall through to another browser."""
    environ = os.environ if environ is None else environ
    named = environ.get("THEBES_REVIEW_BROWSER")
    if named:
        return named
    for path in sorted(globber(PLAYWRIGHT_CHROMIUM), reverse=True) + [BRAVE, CHROME]:
        if exists(path):
            return path
    return None


def _browser_probe(url, seconds, shot=None):
    """True when a headless browser sees `flt-semantics-placeholder` within `seconds`; `shot` saves a
    screenshot of the drawn page. Playwright (playwright-core from the app repo's node_modules) launches
    the binary find_browser() chose. Anything that stops the probe from running (no node, no browser,
    a wrong path) is False: fail closed."""
    browser = find_browser()
    if not browser:
        return False
    script = (
        "const {chromium}=require('playwright-core');"
        "(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.THEBES_REVIEW_BROWSER});"
        "try{const p=await b.newPage({viewport:{width:430,height:900}});"
        "await p.goto(process.argv[1],{timeout:30000});"
        "await p.waitForSelector(process.argv[3],{state:'attached',timeout:Number(process.argv[2])*1000});"
        "if(process.argv[4]){await p.waitForTimeout(1500);await p.screenshot({path:process.argv[4]});}"
        "}finally{await b.close();}})().then(()=>process.exit(0),e=>{console.error(String(e));process.exit(1)});")
    env = dict(os.environ, NODE_PATH=os.path.join(ROOT, APP_REPO, "node_modules"), THEBES_REVIEW_BROWSER=browser)
    try:
        done = subprocess.run(["node", "-e", script, url, str(seconds), RENDER_MARKER, shot or ""], env=env,
                              capture_output=True, text=True, timeout=seconds + 60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def wait_rendered(url, seconds=RENDER_SECONDS, probe=_browser_probe, shot=None):
    """(True, "") once the app drew; else (False, "build not ready: ...")."""
    try:
        ok = probe(url, seconds, shot) if shot else probe(url, seconds)
    except Exception as exc:                                    # noqa: BLE001  fail closed
        return False, "build not ready: the render probe could not run (%s)" % str(exc)[:200]
    if ok:
        return True, ""
    return False, ("build not ready: no %s element within %ds (blank canvas, or no browser to prove "
                   "the render)" % (RENDER_MARKER, seconds))


def _wait_port(port, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not _port_free(port):
            return True
        time.sleep(0.5)
    return False


def serve_main(directory, port):
    """Static server with the single-page fallback (an unknown path serves index.html)."""
    import functools
    import http.server

    class Handler(http.server.SimpleHTTPRequestHandler):
        def _forward(self):
            """/__worker/<rest> -> the messaging Worker, same origin for the browser."""
            import urllib.error
            import urllib.request
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            req = urllib.request.Request(MESSAGING_WORKER_URL + self.path[len(MESSAGING_API_BASE_URL):],
                                         data=body, method=self.command)
            for name in ("Authorization", "Content-Type", "Idempotency-Key", "Accept"):
                if self.headers.get(name):
                    req.add_header(name, self.headers[name])
            try:
                resp = urllib.request.urlopen(req, timeout=30)
            except urllib.error.HTTPError as exc:
                resp = exc
            except OSError:
                self.send_error(502, "the messaging Worker is unreachable")
                return
            data = resp.read()
            self.send_response(resp.status if hasattr(resp, "status") else resp.code)
            for name in ("Content-Type", "Retry-After"):
                if resp.headers.get(name):
                    self.send_header(name, resp.headers[name])
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _proxied(self):
            return self.path == MESSAGING_API_BASE_URL or self.path.startswith(MESSAGING_API_BASE_URL + "/")

        do_POST = do_PUT = do_DELETE = do_PATCH = lambda self: self._forward() if self._proxied() \
            else self.send_error(405)

        def do_GET(self):
            self._forward() if self._proxied() else super().do_GET()

        def do_HEAD(self):
            self._forward() if self._proxied() else super().do_HEAD()

        def send_head(self):
            if not os.path.exists(self.translate_path(self.path.split("?", 1)[0])):
                self.path = "/index.html"
            return super().send_head()

        def log_message(self, *args):
            pass

    http.server.ThreadingHTTPServer(("127.0.0.1", port),
                                    functools.partial(Handler, directory=directory)).serve_forever()


def _resolve_sha(wt, sha):
    if sha:
        return sha
    done = _git(["rev-parse", "HEAD"], cwd=wt)
    return (done.stdout or "").strip() or None


def app_defines(env_file):
    """The --dart-define list for a review build: the app .env, then the messaging Worker."""
    return (["--dart-define-from-file=%s" % env_file] if os.path.exists(env_file) else []) + [
        "--dart-define=MESSAGING_API_BASE_URL=%s" % MESSAGING_API_BASE_URL,
        "--dart-define=MESSAGING_ACCESS_MODE=%s" % MESSAGING_ACCESS_MODE]


def start(item):
    """Build the item's commit for the web and serve it. Returns where to look."""
    ticket = item.get("ticket") or "unknown"
    cur = running(ticket)
    if cur and not cur.get("dead"):
        if cur.get("sha") == item.get("sha"):
            return dict(cur, status="already-running")
        stop(ticket)
    wt = _worktree(ticket, item.get("sha"), item.get("branch"))
    env_file = os.path.join(ROOT, APP_REPO, ".env")
    defines = app_defines(env_file)
    log_path = os.path.join(_dir("review-app"), "%s.log" % ticket)
    open(log_path, "w").close()            # one log per run: an old "ready" line must not count
    port = _free_port({r.get("port") for r in list_running()})
    if port is None:
        raise RuntimeError("all review ports %d-%d are busy: stop a finished review first "
                           "(`review_queue app --list`)" % (WEB_PORTS[0], WEB_PORTS[-1]))
    sha = _resolve_sha(wt, item.get("sha"))
    try:
        served, cached = build_web(wt, sha, defines, log_path)
    except RuntimeError as exc:
        _record_render(ticket, sha, False, str(exc))
        raise
    rec = {"ticket": ticket, "platform": "web", "sha": sha, "branch": item.get("branch"),
           "worktree": wt, "log": log_path, "started_at": time.time(), "port": port,
           "url": "http://localhost:%d" % port, "build": served, "build_cached": cached,
           "rendered": False}
    cmd = [sys.executable, "-m", "agent.execution.review_app", "serve", served, str(port)]
    with open(log_path, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.PIPE, start_new_session=True)
    rec["pid"] = proc.pid
    with open(_state_path(ticket), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    evidence = os.path.join(store.RUNTIME, "review-evidence", ticket)
    ok, why = (True, "") if _wait_port(port) else (False, "build not ready: the static server did not start")
    if ok:
        os.makedirs(evidence, exist_ok=True)
        ok, why = wait_rendered(rec["url"], shot=os.path.join(evidence, "render.png"))
    _record_render(ticket, sha, ok, why)
    if not ok:
        stop(ticket)
        raise RuntimeError(why.strip()[-600:])
    rec["rendered"] = True
    with open(_state_path(ticket), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
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


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "serve":
    serve_main(sys.argv[2], int(sys.argv[3]))
