#!/bin/sh
# Desktop single-root guard — PreToolUse hook entry point (Bash matcher).
#
# WHY THIS EXISTS. 2026-09-10 audit found three unregistered top-level Thebes
# folders on ~/Desktop (a frozen historical clone, a governance-candidate
# scratch clone, and rename-backup bundles) alongside the canonical checkout —
# ~16.5G of drift, one of them carrying a live credential. None were created
# by a script; they were ad-hoc `git clone` / `mkdir` actions with no rule
# stopping them. This hook is that rule.
#
# SCOPE. Only blocks commands that would create a NEW top-level entry under
# ~/Desktop outside this canonical checkout: `git clone` targeting Desktop,
# and `mkdir`/`cp -r`/`rsync` creating a directory directly under Desktop.
# Temporary work belongs under Thebes-Canonical/.worktrees/ (git worktrees)
# or Thebes-Canonical/.claude/worktrees/ (harness-managed worktrees) instead.
#
# It does NOT police paths inside Thebes-Canonical itself, does not touch
# Product code, Jira, databases, or global git config, and fails OPEN on any
# internal error — a guard that blocks the session is worse than no guard.
# Product main protection lives entirely in branch-guard.sh; this script is
# independent of it and must not be merged into it.
#
# Exit 0 = no opinion. Exit 2 = refuse the tool call, reason on stderr.
set -u

SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
ROOT=$(cd "$SELF/../.." 2>/dev/null && pwd) || exit 0
CANONICAL_NAME=$(basename "$ROOT")

payload=$(cat 2>/dev/null) || exit 0
[ -n "$payload" ] || exit 0

cmd=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cmd = (data.get("tool_input") or {}).get("command", "")
print(cmd)
' 2>/dev/null)
[ -n "$cmd" ] || exit 0

decision=$(printf '%s' "$cmd" | python3 -c '
import os, re, sys
cmd, canonical = sys.stdin.read(), sys.argv[1]
if "Desktop" not in cmd:
    print("PASS"); raise SystemExit
if re.search(r"(^|[;&|\s])git\s+clone(\s|$)", cmd):
    print("DENY"); raise SystemExit
if not re.search(r"(^|[;&|\s])(mkdir|rsync|cp\s+-r)(\s|$)", cmd):
    print("PASS"); raise SystemExit
paths = re.findall(r"(?:~|/Users/[^/\s]+)?/Desktop(?:/[^\s;&|]+)?", cmd)
for raw in paths:
    path = os.path.normpath(os.path.expanduser(raw.strip("\"\x27()")))
    desktop = os.path.expanduser("~/Desktop")
    allowed = os.path.join(desktop, canonical)
    if path != desktop and path != allowed and not path.startswith(allowed + os.sep):
        print("DENY"); raise SystemExit
print("PASS")
' "$CANONICAL_NAME" 2>/dev/null) || exit 0

if [ "$decision" = "DENY" ]; then
  echo "REFUSED: command would create a Desktop entry outside $CANONICAL_NAME. Use a git worktree under the canonical checkout." >&2
  exit 2
fi

exit 0
