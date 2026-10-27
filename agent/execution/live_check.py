"""Is it live? (autonomy constitution, D-043 section 6, 2026-10-27.)

The CEO's part ends at the task and resumes when he SEES it live. So a ticket that passed review
is Done only when the reviewed commit is on Alpha AND alpha.dabbler.pro is serving a build that
contains it. This module answers both, by code:

    on_alpha(sha)        the commit is an ancestor of origin/Alpha (Dabbler/dabbler-code)
    deployed_sha()       the commit alpha.dabbler.pro says it was built from, read from its
                         /version.json (`git_sha`/`commit`/`sha`, written by
                         scripts/cloudflare-build.sh from CF_PAGES_COMMIT_SHA); None when the
                         build does not carry one yet
    status(sha)          'live' | 'on-alpha' (deployed build older, or not yet built) |
                         'on-alpha-unverified' (the site does not say its commit) | 'not-on-alpha'

Never raises: a network or git failure is reported as the weaker status, never as live.
"""
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REPO = "Dabbler/dabbler-code"
BASE = "Alpha"
SITE = "https://alpha.dabbler.pro"
SHA_FIELDS = ("git_sha", "commit", "sha", "commit_sha")


def _git(args, runner=None, timeout=60):
    return (runner or subprocess.run)(["git", "-C", os.path.join(ROOT, REPO)] + args,
                                      capture_output=True, text=True, timeout=timeout,
                                      stdin=subprocess.DEVNULL)


def is_ancestor(sha, ref, runner=None):
    try:
        return _git(["merge-base", "--is-ancestor", sha, ref], runner).returncode == 0
    except Exception:                                      # noqa: BLE001
        return False


def on_alpha(sha, runner=None, fetch=True):
    """The reviewed commit is contained in origin/Alpha."""
    if not sha:
        return False
    if fetch:
        from agent.execution import integrate
        integrate._fetch_base(REPO, BASE, runner)
    return is_ancestor(sha, "origin/%s" % BASE, runner)


def deployed_sha(fetch_json=None):
    """The commit alpha.dabbler.pro was built from, or None when it does not say."""
    try:
        body = (fetch_json or _fetch_json)(SITE + "/version.json")
    except Exception:                                      # noqa: BLE001
        return None
    for field in SHA_FIELDS:
        v = (body or {}).get(field)
        if isinstance(v, str) and len(v) >= 7:
            return v.strip()
    return None


def _fetch_json(url):
    req = urllib.request.Request(url + "?t=%d" % int(__import__("time").time()),
                                 headers={"Cache-Control": "no-cache", "User-Agent": "thebes-live-check"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def status(sha, runner=None, fetch_json=None, fetch=True):
    if not on_alpha(sha, runner, fetch):
        return "not-on-alpha"
    live = deployed_sha(fetch_json)
    if not live:
        return "on-alpha-unverified"
    if is_ancestor(sha, live, runner):
        return "live"
    if fetch:                                              # the deploy may be newer than our fetch
        from agent.execution import integrate
        integrate._FETCHED.pop((REPO, BASE), None)
        integrate._fetch_base(REPO, BASE, runner)
        if is_ancestor(sha, live, runner):
            return "live"
    return "on-alpha"


if __name__ == "__main__":
    print(json.dumps({"sha": sys.argv[1] if len(sys.argv) > 1 else None,
                      "deployed": deployed_sha(),
                      "status": status(sys.argv[1]) if len(sys.argv) > 1 else None}))
