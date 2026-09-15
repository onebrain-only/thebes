#!/bin/sh
# Run the Thebes test suite — every package, one command, one verdict.
#
#   agent/scripts/run-tests.sh            everything
#   agent/scripts/run-tests.sh state      one package: state | controller | core
#                                         | execution | listener | qa
#
# Works from a fresh clone with nothing installed: stdlib-only, resolves the
# repository root from its own location, no runner to install.
#
# Two conventions coexist and both are honoured:
#   agent/state/tests/        print-harness scripts ("N passed, M FAILED")
#   agent/<pkg>/tests/        unittest modules, discovered with the tests
#                             directory as top level (they are plain
#                             directories, deliberately not packages)
#
# 2026-09-15: extended from the state suite alone to all six packages, so a
# change to the validation route or the QA layer cannot pass "the tests" by
# running only the package it did not touch.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Library/Developer/CommandLineTools}"

only="${1:-all}"
total=0
fails=0

run_state() {
  TESTS="$ROOT/agent/state/tests"
  [ -d "$TESTS" ] || { echo "ERROR: no $TESTS"; exit 1; }
  for t in "$TESTS"/test_*.py; do
    [ -e "$t" ] || continue
    echo "--- state/$(basename "$t") ---"
    if out=$(python3 "$t" 2>&1); then
      printf '%s\n' "$out" | tail -1
    else
      printf '%s\n' "$out"
      fails=$((fails + 1))
    fi
    n=$(printf '%s\n' "$out" | sed -n 's/^\([0-9]*\) passed.*/\1/p' | tail -1)
    total=$((total + ${n:-0}))
  done
}

run_unittest() {
  pkg="$1"
  dir="$ROOT/agent/$pkg/tests"
  [ -d "$dir" ] || { echo "ERROR: no $dir"; exit 1; }
  echo "--- $pkg (unittest) ---"
  if out=$(python3 -m unittest discover -s "$dir" -t "$dir" -p 'test_*.py' 2>&1); then
    printf '%s\n' "$out" | grep -E '^(Ran |OK)' || true
  else
    printf '%s\n' "$out" | tail -40
    fails=$((fails + 1))
  fi
  n=$(printf '%s\n' "$out" | sed -n 's/^Ran \([0-9]*\) test.*/\1/p' | tail -1)
  total=$((total + ${n:-0}))
}

case "$only" in
  all)
    run_state
    for p in controller core execution listener qa; do run_unittest "$p"; done ;;
  state) run_state ;;
  controller|core|execution|listener|qa) run_unittest "$only" ;;
  *) echo "usage: $0 [all|state|controller|core|execution|listener|qa]" >&2; exit 2 ;;
esac

echo
echo "TOTAL: $total passed, $fails suite(s) with failures"
[ "$fails" -eq 0 ] || exit 1
