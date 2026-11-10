#!/usr/bin/env python3
"""Knowledge lint: keeps the rule files of Thebes in one piece.

Every rule has one home (see the table in CLAUDE.md). This script fails when the
files that hold those rules drift apart again:

  seats      every seat in seats.json has one NAMING row, one binding, one role
             file, and its rendered agent names it the way NAMING does
  counts     topology.json and every "N seats" sentence agree with seats.json
  stale      no retired term is left in a live file
  paths      no absolute home path in a tracked live file
  links      every relative link and repository path named in a rule file exists
  decisions  no decision ID is defined twice

Run it from anywhere:  python3 agent/scripts/knowledge_lint.py
Exit code 0 means no findings. The pre-commit hook runs it.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Files that record the past. They may name retired things; nothing reads them as a rule.
HISTORY = (
    "agent/archive/",
    "agent/history/",
    "agent/status/",
    "agent/memory/",
    "agent/reviews/",
    "agent/errors/",
    "agent/DECISIONS.md",
    "agent/LEARN.md",
    "agent/skills/capacity-to-date/",
    "agent/state/discovery-ledger.md",
)
# Files that must spell a retired term to forbid or test it.
SPELLS_THE_TERM = (
    "agent/scripts/knowledge_lint.py",
    "agent/scripts/apply_settings.py",
    "agent/execution/tests/",
    "agent/state/tests/",
    "agent/controller/tests/",
)
TEXT_SUFFIXES = (".md", ".py", ".sh", ".json", ".yml", ".yaml", ".csv", ".tsx", ".ts",
                 ".command", ".txt", ".toml")

# Retired term -> what replaced it.
STALE_TERMS = {
    r"alpha-karnak": "team branches are staging-<team>",
    r"merge-alpha": "Memphis integrates into staging; Alpha moves on promote-alpha",
    r"\bteam[- ]leads?\b": "there are no team leads; the orchestrator dispatches to teams",
    r"\.claude/worktrees": "worktrees are under agent/state/runtime/worktrees/",
    r"moatazmustapha": "a path from another machine",
    r"Onebrain Agent Team": "the system is called Thebes",
}
# A live file may say a retired thing is gone. These words on the same line allow it.
NEGATION = re.compile(
    r"\b(no|not|never|removed|retired|legacy|historical|formerly|were|was|"
    r"superseded|replaced|until|before|had|old|gone|without)\b", re.I)

# Owned by apply_settings.py, which has its own --check.
MACHINE_SETTINGS = (".claude/settings.json",)

HOME_PATH = re.compile(r"(/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/)")
# Placeholders that are not a person's home.
HOME_PLACEHOLDER = re.compile(r"/(Users|home)/(<|\$|you/|name/|USER|username|\.\.\.|\*)")

RULE_FILES = (
    "CLAUDE.md",
    "agent/ORCHESTRATOR.md",
    "agent/REVIEWER.md",
    "agent/WORKFLOWS.md",
    "agent/CONTEXT.md",
    "agent/ROADMAP.md",
    "agent/SETUP.md",
    "agent/controller/DOCTRINE.md",
)
RULE_DIRS = ("agent/roles/",)
# Repository paths written in backticks are checked when they start with one of these.
PATH_ROOTS = ("agent/", ".claude/", "Dabbler/dabbler-docs/")
# Created at run time or on a machine, so absent from a clean checkout.
NOT_IN_CHECKOUT = (
    "agent/state/runtime",
    "agent/status/",
    ".claude/agent-memory",
    ".claude/settings.local.json",
    ".claude/agents/",
    "agent/.flow",
)

DECISION_FILES = ("agent/DECISIONS.md", "Dabbler/dabbler-docs/DECISIONS.md")
DECISION_HEADING = re.compile(r"^#{2,4}\s+([A-Z]{1,2}-\d{3})\b")
# Both logs carry a D- series for now; the conversion table in agent/DECISIONS.md maps them.
SHARED_PREFIXES = ("D",)


def tracked_files(root):
    out = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True)
    if out.returncode != 0:
        files = []
        for base, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in (".git", "runtime", "node_modules", "Dabbler")]
            files.extend(os.path.relpath(os.path.join(base, n), root) for n in names)
        return sorted(files)
    return [line for line in out.stdout.splitlines() if line]


def read(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def is_live(rel):
    return rel.endswith(TEXT_SUFFIXES) and not rel.startswith(HISTORY)


def naming_rows(root):
    rows = {}
    text = read(root, "agent/NAMING.csv")
    if text is None:
        return rows
    for row in csv.DictReader(text.splitlines()):
        seat = (row.get("Seat") or "").strip()
        match = re.search(r"\(([^)]+)\)\s*$", row.get("Given Name (Arabic)") or "")
        rows.setdefault(seat, []).append(match.group(1) if match else None)
    return rows


def load_seats(root):
    text = read(root, "agent/state/registry/seats.json")
    return json.loads(text)["seats"] if text else {}


def check_seats(root):
    findings = []
    seats = load_seats(root)
    names = naming_rows(root)
    for seat in sorted(seats):
        role = seats[seat].get("role")
        rows = names.get(seat, [])
        if len(rows) != 1:
            findings.append(("seats", "agent/NAMING.csv",
                             "seat %s has %d naming rows, expected 1" % (seat, len(rows))))
        elif not rows[0]:
            findings.append(("seats", "agent/NAMING.csv",
                             "seat %s has no name in brackets" % seat))
        binding = ".claude/bindings/%s.yml" % seat
        if read(root, binding) is None:
            findings.append(("seats", binding, "binding missing for seat %s" % seat))
        role_file = "agent/roles/%s.md" % role
        if read(root, role_file) is None:
            findings.append(("seats", role_file, "role file missing for seat %s" % seat))
        agent = ".claude/agents/%s.md" % seat
        body = read(root, agent)
        if body is not None and rows and rows[0]:
            if "You are **%s**." % rows[0] not in body:
                findings.append(("seats", agent,
                                 "body does not name the seat %s as NAMING does" % rows[0]))
            head = re.search(r'^description: "\*\*([^*]+?)\.?\*\*', body, re.M)
            if head and head.group(1) != rows[0]:
                findings.append(("seats", binding,
                                 "description opens with %r, NAMING says %r"
                                 % (head.group(1), rows[0])))
    for seat in sorted(names):
        if seat and seat != "—" and not seat.startswith("team:") and seat not in seats:
            findings.append(("seats", "agent/NAMING.csv",
                             "naming row %s is not a seat in seats.json" % seat))
    for rel in tracked_files(root):
        if rel.startswith(".claude/bindings/") and rel.endswith(".yml"):
            if os.path.basename(rel)[:-4] not in seats:
                findings.append(("seats", rel, "binding has no seat in seats.json"))
    taken = {}
    for seat, rows in names.items():
        if seat in seats and rows and rows[0]:
            taken.setdefault(rows[0], []).append(seat)
    for name, holders in sorted(taken.items()):
        if len(holders) > 1:
            findings.append(("seats", "agent/NAMING.csv",
                             "name %s is used by %s" % (name, ", ".join(sorted(holders)))))
    return findings


def check_counts(root, files):
    findings = []
    seats = load_seats(root)
    per_role = {}
    for seat in seats.values():
        per_role[seat.get("role")] = per_role.get(seat.get("role"), 0) + 1
    allowed = {len(seats)} | set(per_role.values())
    text = read(root, "agent/state/registry/topology.json")
    if text:
        for capability, record in json.loads(text).get("capabilities", {}).items():
            defined = record.get("defined_seats")
            allowed.add(record.get("ceiling"))
            if defined != per_role.get(capability, 0):
                findings.append(("counts", "agent/state/registry/topology.json",
                                 "%s: defined_seats %s, seats.json has %d"
                                 % (capability, defined, per_role.get(capability, 0))))
    for rel in files:
        if not (is_live(rel) and rel.endswith(".md")):
            continue
        for number, line in enumerate((read(root, rel) or "").splitlines(), 1):
            for match in re.finditer(r"\b(\d+) (?:defined )?seats\b", line):
                if int(match.group(1)) not in allowed:
                    findings.append(("counts", "%s:%d" % (rel, number),
                                     "says %s; seats.json has %d seats"
                                     % (match.group(0), len(seats))))
    return findings


def check_stale(root, files):
    findings = []
    for rel in files:
        if not is_live(rel) or rel.startswith(SPELLS_THE_TERM):
            continue
        for number, line in enumerate((read(root, rel) or "").splitlines(), 1):
            for pattern, why in STALE_TERMS.items():
                if re.search(pattern, line, re.I) and not NEGATION.search(line):
                    findings.append(("stale", "%s:%d" % (rel, number),
                                     "%s (%s)" % (re.search(pattern, line, re.I).group(0), why)))
    return findings


def check_paths(root, files):
    findings = []
    for rel in files:
        if not is_live(rel) or rel.startswith(SPELLS_THE_TERM) or rel in MACHINE_SETTINGS:
            continue
        for number, line in enumerate((read(root, rel) or "").splitlines(), 1):
            if HOME_PATH.search(line) and not HOME_PLACEHOLDER.search(line):
                findings.append(("paths", "%s:%d" % (rel, number), "absolute home path"))
    return findings


def _exists(root, rel):
    return os.path.exists(os.path.join(root, rel))


def check_links(root, files):
    findings = []
    rule_files = [f for f in files if f in RULE_FILES or f.startswith(RULE_DIRS)]
    docs_present = _exists(root, "Dabbler/dabbler-docs")
    for rel in rule_files:
        base = os.path.dirname(rel)
        for number, line in enumerate((read(root, rel) or "").splitlines(), 1):
            targets = []
            for match in re.finditer(r"\]\(([^)\s]+)\)", re.sub(r"`[^`]*`", "", line)):
                link = match.group(1).split("#")[0]
                if link and not re.match(r"[a-z]+:", link):
                    targets.append(os.path.normpath(os.path.join(base, link)))
            for match in re.finditer(r"`([^`\s]+)`", line):
                path = match.group(1).split("#")[0].split(":")[0].rstrip(".,;")
                if path.startswith(PATH_ROOTS) and not re.search(r"[<>*{}$…]|\.\.\.", path):
                    targets.append(path)
            for target in targets:
                if target.startswith(NOT_IN_CHECKOUT):
                    continue
                if target.startswith("Dabbler/") and not docs_present:
                    continue
                if not _exists(root, target):
                    findings.append(("links", "%s:%d" % (rel, number),
                                     "%s does not exist" % target))
    return findings


def check_decisions(root):
    findings = []
    seen = {}
    for rel in DECISION_FILES:
        local = {}
        for number, line in enumerate((read(root, rel) or "").splitlines(), 1):
            match = DECISION_HEADING.match(line)
            if not match:
                continue
            key = match.group(1)
            if key in local:
                findings.append(("decisions", "%s:%d" % (rel, number),
                                 "%s is already defined at line %d" % (key, local[key])))
                continue
            local[key] = number
            if key in seen and key.split("-")[0] not in SHARED_PREFIXES:
                findings.append(("decisions", "%s:%d" % (rel, number),
                                 "%s is also defined in %s" % (key, seen[key])))
            seen.setdefault(key, rel)
    return findings


def run(root=ROOT):
    files = tracked_files(root)
    findings = []
    findings += check_seats(root)
    findings += check_counts(root, files)
    findings += check_stale(root, files)
    findings += check_paths(root, files)
    findings += check_links(root, files)
    findings += check_decisions(root)
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=ROOT)
    parser.add_argument("--only", help="run one check: seats, counts, stale, paths, links, decisions")
    args = parser.parse_args(argv)
    findings = run(args.root)
    if args.only:
        findings = [f for f in findings if f[0] == args.only]
    for check, where, what in findings:
        print("%-9s %s  %s" % (check, where, what))
    print("knowledge lint: %d finding(s)" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
