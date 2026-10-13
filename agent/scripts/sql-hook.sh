#!/bin/sh
# SQL hook — PreToolUse hook entry point for execute_sql (maintenance 2026-10-13). See sql_hook.py.
SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
exec python3 "$SELF/sql_hook.py"
