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
payload=$(cat 2>/dev/null) || exit 0
[ -n "$payload" ] || exit 0

parsed=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tool_input = data.get("tool_input") or {}
print(json.dumps({"command": tool_input.get("command", ""),
                  "cwd": tool_input.get("cwd") or data.get("cwd") or ""}))
' 2>/dev/null)
cmd=$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["command"])' 2>/dev/null)
cwd=$(printf '%s' "$parsed" | python3 -c 'import json,sys; print(json.load(sys.stdin)["cwd"])' 2>/dev/null)
[ -n "$cmd" ] || exit 0

decision=$(printf '%s' "$cmd" | PYTHONPATH="$ROOT/agent/state" python3 -c '
import sys
from desktop_scope_guard import decide
print(decide(sys.stdin.read(), sys.argv[1], sys.argv[2] or None))
' "$ROOT" "$cwd" 2>/dev/null) || exit 0

if [ "$decision" = "DENY" ]; then
  echo "REFUSED: command would create a Desktop entry outside $(basename "$ROOT"). Use a git worktree under the canonical checkout." >&2
  exit 2
fi

exit 0
