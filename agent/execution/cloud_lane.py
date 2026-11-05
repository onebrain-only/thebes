#!/usr/bin/env python3
"""The cloud lane (CEO 2026-10-20): a ticket labelled `cloud` is built by a Claude CLOUD session the CEO
starts (the cloud credit), and nobody copies anything back by hand.

The cloud session pushes its work to the branch `staging-cloud-<key>` on GitHub (see
agent/scripts/cloud_prompt.py). From there Thebes does the rest, at zero tokens:

    1. DETECT    every tick, a `cloud` ticket whose branch exists on origin. A branch that is still
                 being pushed to is left alone: it is checked only after QUIET_SECONDS without a new push.
    2. VERIFY    a fresh clone of that exact commit under agent/state/runtime/cloud-wt (never the CEO's
                 folders): `flutter pub get`, `flutter analyze --no-pub --no-fatal-infos`,
                 `flutter test --no-pub`. The cloud's own claim is never taken on trust.
    3. REPORT    one Jira comment: branch, commit, files changed against staging, the checks, and what failed.
    4. HAND OFF  all checks green -> the ticket moves to QA-Test, where the Codex reviewer looks.
                 A failure -> the comment carries the failing tests AND a ready prompt for the next cloud
                 session on the same branch; the ticket stays where it is.

Integration into staging is the ops team's (Memphis) and waits for the ticket's blockers to be integrated.

    python3 -m agent.execution.cloud_lane scan            # one pass (the dispatcher runs it every tick)
    python3 -m agent.execution.cloud_lane verify KAN-606 <sha>
    python3 -m agent.execution.cloud_lane status
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

from agent.state import store                                           # noqa: E402

REPO = os.path.join(ROOT, "Dabbler", "dabbler-code")
QUIET_SECONDS = 600
VERIFY_STALE_SECONDS = 50 * 60
CLOUD_JQL = ('project = KAN AND labels = cloud AND status in ("Ready", "Front-end", "Back-end", '
             '"Operations", "QA-Test") ORDER BY rank ASC')
QA_TEST_ID = "10009"
STEP_TIMEOUTS = {"pub get": 900, "analyze": 900, "test": 1800}


def _dir():
    d = os.path.join(store.RUNTIME, "cloud")
    os.makedirs(d, exist_ok=True)
    return d


def _path(key):
    return os.path.join(_dir(), "%s.json" % re.sub(r"[^A-Za-z0-9-]", "_", key))


def read_state(key):
    try:
        with open(_path(key), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_state(key, st):
    tmp = _path(key) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1, sort_keys=True)
    os.replace(tmp, _path(key))


def branch_name(key):
    return "staging-cloud-%s" % re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


def remote_branch(key, runner=None):
    """(name, sha) of the cloud branch on origin, matched ignoring letter case, or (None, None)."""
    run = runner or subprocess.run
    done = run(["git", "-C", REPO, "ls-remote", "--heads", "origin"], capture_output=True, text=True,
               timeout=60, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        return None, None
    want = "refs/heads/%s" % branch_name(key)
    for line in (done.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lower() == want:
            return parts[1][len("refs/heads/"):], parts[0]
    return None, None


def cloud_info(key):
    """What the Codex reviewer needs to look at a cloud ticket: the branch and the verified commit."""
    st = read_state(key)
    if not st.get("verified_sha"):
        return None
    return {"cloud_branch": st.get("branch"), "sha": st["verified_sha"], "checks": st.get("checks")}


# ------------------------------------------------------------------------------------- scan
def scan(*, jira=None, now=None, runner=None, spawn=None):
    """One pass. Returns what it did. Never raises."""
    now = now or time.time()
    out = []
    try:
        if jira is None:
            from agent.execution import jira_sync
            jira = jira_sync._client(None, store)
        if jira is None:
            return out
        for issue in jira.search_issues(CLOUD_JQL, fields=["status"], limit=30):
            key = issue["key"]
            name, sha = remote_branch(key, runner)
            if not name:
                continue
            st = read_state(key)
            if st.get("verified_sha") == sha or st.get("failed_sha") == sha:
                continue                                   # this exact commit is already judged
            if st.get("seen_sha") != sha:
                st.update(seen_sha=sha, seen_at=now, branch=name)
                write_state(key, st)
                out.append({"cloud": key, "action": "branch-seen", "sha": sha[:10]})
                continue
            if now - st.get("seen_at", now) < QUIET_SECONDS:
                continue                                   # still being pushed to
            if st.get("verifying_since") and now - st["verifying_since"] < VERIFY_STALE_SECONDS:
                continue
            st["verifying_since"] = now
            write_state(key, st)
            (spawn or _spawn)(key, sha)
            out.append({"cloud": key, "action": "verify-started", "sha": sha[:10]})
    except Exception as exc:                                # noqa: BLE001
        out.append({"cloud": None, "action": "scan-failed", "error": str(exc)[:200]})
    return out


def _spawn(key, sha):
    log = os.path.join(_dir(), "verify.log")
    with open(log, "a") as fh:
        subprocess.Popen([sys.executable, "-m", "agent.execution.cloud_lane", "verify", key, sha],
                         cwd=ROOT, stdin=subprocess.DEVNULL, stdout=fh, stderr=fh, start_new_session=True)


# ---------------------------------------------------------------------------------- verify
def _sh(argv, cwd, timeout, runner=None):
    run = runner or subprocess.run
    env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID")}
    try:
        done = run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                   stdin=subprocess.DEVNULL)
        text = ((done.stdout or "") + (done.stderr or "")).strip().splitlines()
        return done.returncode, "\n".join(text[-40:])
    except subprocess.TimeoutExpired:
        return None, "timed out after %ds" % timeout


def failing_tests(output):
    """Names of failing tests from `flutter test` output (the `[E]` lines and `Some tests failed`)."""
    names = []
    for line in output.splitlines():
        m = re.match(r"^\d\d:\d\d \+\d+(?: ~\d+)? -\d+: (.+?) \[E\]\s*$", line.strip())
        if m:
            names.append(m.group(1))
    return names[:20]


def verify(key, sha, *, runner=None, jira=None, now=None):
    """Clone, run the checks, then report. Returns the result dict."""
    now = now or time.time()
    st = read_state(key)
    name = st.get("branch") or branch_name(key)
    wt = os.path.join(_dir(), "wt", key)
    try:
        url = _sh(["git", "-C", REPO, "remote", "get-url", "origin"], ROOT, 30, runner)[1].strip()
        if os.path.isdir(wt) and runner is None:
            import shutil
            shutil.rmtree(wt, ignore_errors=True)
        os.makedirs(os.path.dirname(wt), exist_ok=True)
        steps = [("clone", ["git", "clone", "--filter=blob:none", "--single-branch", "--branch", name, url, wt], ROOT, 900),
                 ("checkout", ["git", "-C", wt, "checkout", "-q", sha], ROOT, 120),
                 ("fetch staging", ["git", "-C", wt, "fetch", "-q", "origin", "staging"], ROOT, 300)]
        for label, argv, cwd, timeout in steps:
            code, tail = _sh(argv, cwd, timeout, runner)
            if code != 0:
                return _finish(key, sha, name, {"setup": ("fail", "%s: %s" % (label, tail[-300:]))}, [], jira, now)
        _, files = _sh(["git", "-C", wt, "diff", "--name-only", "origin/staging...HEAD"], wt, 120, runner)
        changed = [f for f in files.splitlines() if f.strip()]
        checks = {}
        for label, argv in (("pub get", ["flutter", "pub", "get"]),
                            ("analyze", ["flutter", "analyze", "--no-pub", "--no-fatal-infos"]),
                            ("test", ["flutter", "test", "--no-pub"])):
            code, tail = _sh(argv, wt, STEP_TIMEOUTS[label], runner)
            checks[label] = ("pass" if code == 0 else "fail", tail)
            if code != 0:
                break
        return _finish(key, sha, name, checks, changed, jira, now)
    except Exception as exc:                                  # noqa: BLE001
        return _finish(key, sha, name, {"setup": ("fail", str(exc)[:300])}, [], jira, now)


def _finish(key, sha, name, checks, changed, jira, now):
    ok = all(v[0] == "pass" for v in checks.values()) and {"analyze", "test"} <= set(checks)
    st = read_state(key)
    st.pop("verifying_since", None)
    st["checks"] = {k: v[0] for k, v in checks.items()}
    if ok:
        st.update(verified_sha=sha, failed_sha=None)
    else:
        st["failed_sha"] = sha
    write_state(key, st)
    try:
        report(key, sha, name, checks, changed, ok, jira=jira)
    except Exception as exc:                                  # noqa: BLE001
        st = read_state(key)
        st["report_error"] = str(exc)[:200]
        write_state(key, st)
    return {"key": key, "sha": sha, "ok": ok, "checks": st["checks"]}


def report(key, sha, name, checks, changed, ok, *, jira=None):
    """The Jira comment (and the move to QA-Test when green)."""
    if jira is None:
        from agent.execution import jira_sync
        jira = jira_sync._client(None, store)
    if jira is None:
        return
    lines = ["Thebes verified the cloud branch (zero tokens, a fresh clone, never the CEO's folders).",
             "Branch: %s   Commit: %s" % (name, sha[:12]),
             "Files changed against staging: %d%s" % (len(changed), (" - " + ", ".join(changed[:12]) +
                                                                  (" ..." if len(changed) > 12 else "")) if changed else "")]
    for label, (verdict, tail) in checks.items():
        lines.append("%s: %s" % (label.upper(), verdict.upper()))
    if ok:
        lines.append("All checks passed. Moved to QA-Test for the Codex reviewer (branch %s at %s)." % (name, sha[:12]))
        jira.add_comment(key, "\n".join(lines))
        from agent.execution import jira_sync
        jira_sync._move(key, QA_TEST_ID, jira, store)
        return
    failed = [(l, t) for l, (v, t) in checks.items() if v != "pass"]
    note = "The checks failed on commit %s: %s. Fix only that." % (
        sha[:8], "; ".join("%s%s" % (l, (" (" + ", ".join(failing_tests(t)[:6]) + ")") if failing_tests(t) else "")
                           for l, t in failed))
    import cloud_prompt
    prompt = cloud_prompt.build(key, "staging", jira=jira, continue_branch=True, note=note)
    lines.append("")
    lines.append("What failed:")
    for l, t in failed:
        lines.append("--- %s ---\n%s" % (l, t[-1500:]))
    lines.append("")
    lines.append("Next cloud session on the same branch: paste this prompt into claude.ai/code "
                 "(environment dabbler-flutter, repo dabblersport/webapp):")
    lines.append(prompt[:9000])
    jira.add_comment(key, "\n".join(lines))


def status():
    rows = []
    for name in sorted(os.listdir(_dir())):
        if name.endswith(".json"):
            st = read_state(name[:-5])
            rows.append({"key": name[:-5], "branch": st.get("branch"), "seen": (st.get("seen_sha") or "")[:10],
                         "verified": (st.get("verified_sha") or "")[:10], "failed": (st.get("failed_sha") or "")[:10],
                         "checks": st.get("checks")})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.cloud_lane", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    sub.add_parser("status")
    v = sub.add_parser("verify"); v.add_argument("key"); v.add_argument("sha")
    ns = ap.parse_args(argv)
    if ns.cmd == "scan":
        print(json.dumps(scan(), indent=2))
    elif ns.cmd == "status":
        print(json.dumps(status(), indent=2))
    else:
        print(json.dumps(verify(ns.key, ns.sha), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
