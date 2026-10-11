#!/bin/sh
# Ops guard — PreToolUse hook entry point (D-042). See ops_guard.py.
SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
exec python3 "$SELF/ops_guard.py"
