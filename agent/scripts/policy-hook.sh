#!/bin/sh
# Policy hook — PermissionRequest entry point (autonomy constitution, D-043). See policy_hook.py.
SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
exec python3 "$SELF/policy_hook.py"
