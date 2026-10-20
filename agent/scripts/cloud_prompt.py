#!/usr/bin/env python3
"""The prompt for a Claude CLOUD session that does one Jira ticket (CEO 2026-10-20: the $250 cloud
credit). Prints text to paste into claude.ai/code (environment `dabbler-flutter`, repo
`dabblersport/webapp`).

    python3 agent/scripts/cloud_prompt.py KAN-606 [--base alpha-deir-el-bahari]

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

START: git fetch origin && git checkout -b {branch} origin/{base}
BRANCH: your branch is `{branch}`. Ignore the `BRANCH:` line inside the ticket. Push ONLY this branch,
  with `git push origin {branch}`. Never push, merge or open a pull request into Alpha, alpha-*, main,
  master or Canary. Never force-push. Do not touch any other branch.
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


def build(key, base, jira=None):
    if jira is None:
        from agent.integrations import jira as jira_mod
        jira = jira_mod
    issue = jira.get_issue(key)
    desc = (issue.get("description") or "").strip()
    if not desc:
        raise SystemExit("%s has no description" % key)
    branch = "alpha-cloud-%s" % re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return (RULES.format(key=key, branch=branch, base=base)
            + "%s: %s\n\n%s\n" % (key, issue.get("summary") or "", desc))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key")
    ap.add_argument("--base", default="Alpha", help="the branch to start from (default Alpha)")
    ns = ap.parse_args(argv)
    sys.stdout.write(build(ns.key, ns.base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
