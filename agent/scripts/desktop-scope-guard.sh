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

case "$cmd" in
  *git\ clone*)
    case "$cmd" in
      *Desktop*)
        case "$cmd" in
          *"$CANONICAL_NAME"*|*.worktrees*) exit 0 ;;
          *)
            echo "REFUSED: git clone targeting ~/Desktop outside $CANONICAL_NAME. Recurrence guard (2026-09-10): temporary/scratch clones must live under ${CANONICAL_NAME}/.worktrees/ — use a git worktree instead of a new top-level Desktop clone." >&2
            exit 2
            ;;
        esac
        ;;
    esac
    ;;
  *mkdir*Desktop*|*cp\ -r*Desktop*|*rsync*Desktop*)
    case "$cmd" in
      *"$CANONICAL_NAME"*) exit 0 ;;
      *)
        echo "REFUSED: command would create a new entry directly under ~/Desktop outside $CANONICAL_NAME. Recurrence guard (2026-09-10): put temporary/scratch directories under ${CANONICAL_NAME}/.worktrees/ instead." >&2
        exit 2
        ;;
    esac
    ;;
esac

exit 0
