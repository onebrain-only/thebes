#!/usr/bin/env python3
"""The prompt for a Claude CLOUD session that does one Jira ticket (CEO 2026-10-20: the $250 cloud
credit). Prints text to paste into claude.ai/code (environment `dabbler-flutter`, repo
`dabblersport/webapp`).

    python3 agent/scripts/cloud_prompt.py KAN-606 [--base staging-deir-el-bahari]
    python3 agent/scripts/cloud_prompt.py KAN-606 --continue --paths "lib/features/social/**, test/**" \\
            --note "Games/Venues/Meetups are done; do the feed and search parts"

`--paths` replaces the ticket's ALLOWED PATHS (briefs have named folders that do not exist: the cloud
session on KAN-606 stopped on lib/features/feed and lib/features/search, 2026-10-20). Every path the
prompt allows is checked against the repo and the missing ones are reported on stderr.

The ticket's own brief is included whole; this adds what a cloud session does not know: which
branch to start from and push to, the commit prefix, the checks to run, and what it must never
touch. The cloud has no `.env`, so it verifies with the analyzer and the tests only.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

RULES = """You are doing ONE Jira ticket, {key}, in this Flutter repo (the Dabbler app). You work alone in a
cloud sandbox with no database and no secrets.

START: {start}
BRANCH: your branch is `{branch}`. Ignore the `BRANCH:` line inside the ticket. Push ONLY this branch,
  with `git push origin {branch}`. Never push, merge or open a pull request into staging, staging-*,
  Alpha, main, master or Canary. Never force-push. Do not touch any other branch.
COMMITS: every commit message starts with `{key}:`.
SCOPE: stay inside the ticket's ALLOWED PATHS; if the ticket needs a file outside them, stop and say so.
  No secrets, no .env, no new paid service, no database change, no unrelated refactor or restyle.
CHECKS before your final commit (all must pass, and say so with the real output tail):
  flutter analyze --no-pub --no-fatal-infos      (exit 0)
  flutter test --no-pub                          (exit 0; no test may fail)
  and every CHECKS line of the ticket that you can run. A check you could not run is FAIL with the
  reason; never mark PASS by assumption.
IF BLOCKED: do not guess and do not expand scope. Stop, push what is safe, and write exactly what is
  missing (a design, an approval, another ticket's code).
FINISH with a report: branch, last commit sha, files changed, what each acceptance criterion's
  evidence is (file and test names), the check results, and anything not verified.

THE TICKET ({key}):
"""


REPO = os.path.join(ROOT, "Dabbler", "dabbler-code")


def allowed_paths(text):
    m = re.search(r"^ALLOWED PATHS:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def missing_paths(paths, ref, runner=None):
    """Named folders/files that do not exist in the repo at `ref` (new ones are marked `(new)`)."""
    import subprocess
    run = runner or subprocess.run
    out = []
    for part in [p.strip() for p in paths.split(",") if p.strip()]:
        if "(new)" in part:
            continue
        core = re.split(r"\*\*|\s\(", part)[0].strip().rstrip("/")
        if not core:
            continue
        got = run(["git", "-C", REPO, "ls-tree", "--name-only", ref, core], capture_output=True, text=True)
        if got.returncode != 0:
            return None                     # cannot check (ref not fetched locally)
        if not (got.stdout or "").strip():
            out.append(core)
    return out


def build(key, base, jira=None, paths=None, continue_branch=False, note=None):
    if jira is None:
        from agent.integrations import jira as jira_mod
        jira = jira_mod
    issue = jira.get_issue(key)
    desc = (issue.get("description") or "").strip()
    if not desc:
        raise SystemExit("%s has no description" % key)
    branch = "staging-cloud-%s" % re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    if paths:
        desc = (re.sub(r"^ALLOWED PATHS:.*$", "ALLOWED PATHS: %s" % paths, desc, count=1, flags=re.M)
                if allowed_paths(desc) else desc + "\nALLOWED PATHS: %s" % paths)
    start = ("git fetch origin && git checkout %s   (it already exists: continue on it, then push it)" % branch
             if continue_branch else "git fetch origin && git checkout -b %s origin/%s" % (branch, base))
    head = RULES.format(key=key, branch=branch, base=base, start=start)
    if note:
        head += "\nCONTINUATION NOTE (from the CEO): %s\n\n" % note.strip()
    return head + "%s: %s\n\n%s\n" % (key, issue.get("summary") or "", desc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key")
    ap.add_argument("--base", default="staging", help="the branch to start from (default staging)")
    ap.add_argument("--paths", help="replaces the ticket's ALLOWED PATHS")
    ap.add_argument("--continue", dest="cont", action="store_true",
                    help="continue on the existing staging-cloud-<key> branch instead of creating it")
    ap.add_argument("--note", help="what is already done / what to do now")
    ap.add_argument("--check-ref", help="the ref the paths are checked against (default origin/<base>)")
    ns = ap.parse_args(argv)
    text = build(ns.key, ns.base, paths=ns.paths, continue_branch=ns.cont, note=ns.note)
    ref = ns.check_ref or ("origin/%s" % ns.base)
    miss = missing_paths(allowed_paths(text), ref)
    if miss is None:
        sys.stderr.write("WARNING: could not check the paths against %s (fetch it, or pass --check-ref)\n" % ref)
    elif miss:
        sys.stderr.write("WARNING: these ALLOWED PATHS do not exist at %s: %s\n"
                         "         the session will stop on them; fix them with --paths\n" % (ref, ", ".join(miss)))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
