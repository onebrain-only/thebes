"""The dispatch brief: what a team is told before it starts, in a fixed shape (D-041).

Measured 2026-10-04 over 136 dispatches: 40 stopped, and the causes were not vague
goals. They were two teams on one branch, paths the guards refuse, decisions nobody had
made yet, and — in review — no agreed way to say "done". So a dispatch that names a
ticket carries a brief with these parts, and Thebes refuses it, naming what is
missing, rather than let the team find out mid-work.

    GOAL: <one or two sentences — the outcome, not the method>
    BRANCH: <base>-<team>   (or `none` when no git work)   — one branch per team
    INTEGRATE: <base>       (only for the single serial integration dispatch)
    ALLOWED PATHS: <where it may write>
    FORBIDDEN: <what it must not touch or do>
    DECISIONS MADE: <rulings already taken, so it does not stop to ask>   (or `none`)
    IF BLOCKED: <one decision_required question, never a retry loop>       (default given)
    CHECKS:
    C1 | run   | flutter test test/forms/select_test.dart | exit 0
    C2 | run   | flutter analyze lib/src/forms             | exit 0
    C3 | judge | Home matches frame "Home Feed" 1:1        | named screenshot vs frame

A check is the agreed scenario for "done". `run` checks are re-run by Thebes itself, once,
on the commit the team reports (zero tokens). `judge` checks are things only an eye can
settle, and go to one reviewer for one pass. Nobody re-does the work to review it.

    python3 -m agent.execution.dispatch_brief template [--team karnak]
    python3 -m agent.execution.dispatch_brief lint --file brief.md --team karnak
"""
import argparse
import json
import re
import sys

REQUIRED = ("GOAL", "DECISIONS MADE", "CHECKS")
SECTION_RE = re.compile(r"^(GOAL|BRANCH|INTEGRATE|ALLOWED PATHS|FORBIDDEN|DECISIONS MADE|"
                        r"IF BLOCKED|CHECKS)\s*:\s*(.*)$", re.I)
CHECK_RE = re.compile(r"^(C\d{1,2})\s*\|\s*(run|judge)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
DEFAULT_IF_BLOCKED = ("return outcome decision_required with ONE specific question; do not "
                      "retry the same step more than twice")

TEMPLATE = """GOAL: <the outcome, in one or two sentences>
BRANCH: <base>-%(team)s
ALLOWED PATHS: <where you may write>
FORBIDDEN: <what you must not touch or do>
DECISIONS MADE: <rulings already taken, or `none`>
IF BLOCKED: %(blocked)s
CHECKS:
C1 | run   | <exact command, e.g. flutter test test/x_test.dart> | exit 0
C2 | judge | <what an eye must confirm> | <the evidence the reviewer is given>
"""


class BriefError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def template(team="<team>"):
    return TEMPLATE % {"team": team, "blocked": DEFAULT_IF_BLOCKED}


def parse(text):
    """Sections and checks from a brief. Unknown lines are ignored: the free text
    around the sections is the task and stays free."""
    sections, checks, current = {}, [], None
    for line in (text or "").splitlines():
        m = SECTION_RE.match(line.strip())
        if m:
            current = m.group(1).upper()
            sections[current] = m.group(2).strip()
            continue
        c = CHECK_RE.match(line.strip())
        if c:
            checks.append({"id": c.group(1), "kind": c.group(2).lower(),
                           "what": c.group(3), "pass": c.group(4)})
            continue
        if current and line.strip() and current != "CHECKS":
            sections[current] = (sections[current] + " " + line.strip()).strip()
    return sections, checks


def lint(text, team_id=None):
    """Returns (sections, checks). Raises BriefError listing EVERYTHING missing, so the
    orchestrator fixes the brief in one pass."""
    sections, checks = parse(text)
    problems = []
    for name in REQUIRED:
        if name == "CHECKS":
            continue
        if not sections.get(name):
            problems.append("%s: is missing" % name)
    if "BRANCH" not in sections and "INTEGRATE" not in sections:
        problems.append("BRANCH: is missing (use `none` when there is no git work)")
    branch = sections.get("BRANCH")
    if branch and branch.lower() != "none":
        first = branch.split()[0]
        if not BRANCH_RE.match(first):
            problems.append("BRANCH: %r is not a branch name" % first)
        elif team_id and not first.endswith("-" + team_id):
            problems.append("BRANCH: %r must end with -%s — one branch per team, so two teams "
                            "never share a checkout" % (first, team_id))
    if sections.get("INTEGRATE") and not BRANCH_RE.match(sections["INTEGRATE"].split()[0]):
        problems.append("INTEGRATE: needs the base branch name")
    if not checks:
        problems.append("CHECKS: needs at least one line `C1 | run|judge | <what> | <pass>` — "
                        "the agreed scenario for 'done'")
    seen = set()
    for c in checks:
        if c["id"] in seen:
            problems.append("CHECKS: %s appears twice" % c["id"])
        seen.add(c["id"])
        if c["kind"] == "run":
            from agent.execution import verify
            why = verify.command_problem(c["what"])
            if why:
                problems.append("CHECKS: %s command refused (%s)" % (c["id"], why))
            if c["pass"].strip().lower() != "exit 0":
                problems.append("CHECKS: %s `run` passes on `exit 0` only" % c["id"])
    if problems:
        raise BriefError(problems)
    # Malfunction #21: content that passes its own checks can still fail the repo-wide l10n
    # gate. Any brief that may write lib/l10n always carries the parity test.
    if "lib/l10n" in (sections.get("ALLOWED PATHS") or "") and not any(
            "l10n_parity_test" in c["what"] for c in checks):
        used = {c["id"] for c in checks}
        n = next(i for i in range(1, 100) if "C%d" % i not in used)
        checks.append({"id": "C%d" % n, "kind": "run",
                       "what": "flutter test test/l10n_parity_test.dart", "pass": "exit 0"})
    return sections, checks


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.dispatch_brief", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template"); t.add_argument("--team", default="<team>")
    li = sub.add_parser("lint"); li.add_argument("--file", required=True)
    li.add_argument("--team")
    ns = ap.parse_args(argv)
    if ns.cmd == "template":
        print(template(ns.team))
        return 0
    with open(ns.file, encoding="utf-8") as fh:
        text = fh.read()
    try:
        sections, checks = lint(text, ns.team)
    except BriefError as exc:
        print(json.dumps({"status": "refused", "problems": exc.problems}, indent=2))
        return 2
    print(json.dumps({"status": "ok", "checks": checks,
                      "sections": sorted(sections)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
