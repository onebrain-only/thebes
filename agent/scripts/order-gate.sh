#!/bin/sh
# Order gate — PreToolUse + PostToolUse entry point (D-044). See order_gate.py.
SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
exec python3 "$SELF/order_gate.py"
