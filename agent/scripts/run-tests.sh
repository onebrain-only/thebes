#!/bin/sh
# Run the Thebes state/orchestration suite.
#
#   agent/scripts/run-tests.sh
#
# Works from a fresh clone with nothing installed: the suite is stdlib-only and
# resolves the repository root from its own location, so there is no external
# fixture file, no THEBES_ROOT requirement and no test runner to install.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TESTS="$ROOT/agent/state/tests"

[ -d "$TESTS" ] || { echo "ERROR: no $TESTS"; exit 1; }

total=0
fails=0
for t in "$TESTS"/test_*.py; do
  [ -e "$t" ] || continue
  echo "--- $(basename "$t") ---"
  if out=$(python3 "$t" 2>&1); then
    printf '%s\n' "$out" | tail -1
  else
    printf '%s\n' "$out"
    fails=$((fails + 1))
  fi
  n=$(printf '%s\n' "$out" | sed -n 's/^\([0-9]*\) passed.*/\1/p' | tail -1)
  total=$((total + ${n:-0}))
done

echo
echo "TOTAL: $total passed, $fails suite(s) with failures"
[ "$fails" -eq 0 ] || exit 1
