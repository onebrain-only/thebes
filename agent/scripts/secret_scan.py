#!/usr/bin/env python3
"""Refuse credential-shaped strings in knowledge files that are tracked in git.

`agent/memory/` was ignored until 2026-11-10 because seats write it during a session and a
seat could paste a token into a note. It is tracked now (knowledge cleanup step 5), so this
scan is the guard: run it before committing anything under the scanned folders.

    python3 agent/scripts/secret_scan.py            # scans the default folders
    python3 agent/scripts/secret_scan.py PATH ...   # scans the given files or folders

Exit 0 when nothing matched, 1 when something did. A match prints the file, the line number
and the name of the pattern, never the matched text.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS = ("agent/memory", "agent/archive/2026-11-10/user-memory")

# Each pattern is anchored on a word boundary so that ordinary words do not match
# ("ask-what-else" is not an "sk-" key).
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("atlassian-token", re.compile(r"\bATATT[A-Za-z0-9_=-]{10,}")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("api-key-sk", re.compile(r"(?<![A-Za-z0-9-])sk-[A-Za-z0-9_-]{20,}")),
    ("supabase-token", re.compile(r"\bsb[ps]_[A-Za-z0-9]{20,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}")),
    ("aws-key", re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("long-hex", re.compile(r"\b[A-Fa-f0-9]{48,}\b")),
    (
        "assigned-secret",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|THEBES_DISPATCH_CAPABILITY)"
            r"[\"' ]*[:=][\"' ]*[A-Za-z0-9_/+=-]{16,}"
        ),
    ),
)


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line number, pattern name) for every match in `text`."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS:
            if pattern.search(line):
                hits.append((number, name))
    return hits


def files_under(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(p for p in sorted(path.rglob("*")) if p.is_file())
        elif path.is_file():
            found.append(path)
    return found


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv] or [ROOT / p for p in DEFAULT_PATHS]
    failed = False
    for file in files_under(targets):
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, name in scan_text(text):
            failed = True
            print(f"{file}:{number}: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
