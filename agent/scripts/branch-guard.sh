#!/bin/sh
# Repository-aware branch protection — PreToolUse hook entry point.
#
#   branch-guard.sh          # reads the hook payload on stdin
#
# Exit 0 = no opinion. Exit 2 = refuse the tool call, reason on stderr.
#
# WHY A WRAPPER RATHER THAN CALLING PYTHON DIRECTLY FROM settings.json.
# A hook command with a RELATIVE path resolves against whatever directory the
# session happens to be in, so `python3 agent/state/branch_guard.py` dies the
# moment a command runs from a subdirectory — and a guard that errors is a guard
# that blocks every call. This script resolves the repository root from its OWN
# location, the same way flow-hook.sh does, so it works from any cwd and from a
# fresh clone at any path.
#
# It also fails OPEN on infrastructure problems (missing python, missing module)
# and only ever fails CLOSED on an actual protected-branch verdict. A guard that
# blocks the whole session because its interpreter moved is worse than no guard;
# a guard that lets a production push through because its interpreter moved would
# be worse still, which is why the two cases are separated rather than merged.
set -u

SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
ROOT=$(cd "$SELF/../.." 2>/dev/null && pwd) || exit 0
GUARD="$ROOT/agent/state/branch_guard.py"

[ -f "$GUARD" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 "$GUARD"
rc=$?
# 2 is the deny verdict and is passed through. Anything else — a crash, a bad
# payload, an import error — is not a verdict and must not veto the call.
[ "$rc" -eq 2 ] && exit 2
exit 0
