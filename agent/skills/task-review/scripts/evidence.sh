#!/usr/bin/env bash
# Mechanical evidence sweep for a ticket under review.
# Usage: evidence.sh KAN-NN
# Emits facts only. The reviewer reasons on top; it never concludes.
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
TICKET=${1:?usage: evidence.sh KAN-NN}
hr() { printf '\n== %s ==\n' "$1"; }

hr "WORKING TREE — uncommitted changes"
git status --short | head -40
[ -z "$(git status --short)" ] && echo "  (clean)"

hr "COMMITS MENTIONING $TICKET"
git log --oneline --all --grep="$TICKET" | head -20
[ -z "$(git log --oneline --all --grep="$TICKET")" ] && echo "  (none — work may be uncommitted)"

hr "FILES CHANGED IN THOSE COMMITS"
git log --all --grep="$TICKET" --name-only --format='' | sort -u | grep -v '^$' | head -40 || echo "  (none)"

hr "RECENT ACTIVITY (last 25 commits, for context)"
git log --oneline -25

hr "DOC FILES — spec-only vs filled"
for f in $(find docs -name '*.md' | sort); do
  if head -6 "$f" | grep -q 'FILE STATUS: EMPTY'; then
    printf '  %-45s SPEC ONLY (%s lines)\n' "$f" "$(wc -l < "$f" | tr -d ' ')"
  else
    printf '  %-45s FILLED    (%s lines)\n' "$f" "$(wc -l < "$f" | tr -d ' ')"
  fi
done

hr "GOVERNANCE AVAILABILITY — which gates can actually be checked"
for f in DECISIONS MANIFESTO CONTRACT CONVENTIONS SCHEMA ROADMAP ARCHITECTURE; do
  p="docs/$f.md"
  if [ ! -f "$p" ]; then echo "  $f — MISSING"
  elif head -6 "$p" | grep -q 'FILE STATUS: EMPTY'; then echo "  $f — NOT YET WRITTEN (cannot check against)"
  else echo "  $f — available"; fi
done

hr "ANALYZER (errors only)"
if command -v flutter >/dev/null 2>&1; then
  flutter analyze --no-pub 2>&1 | grep -E '^\s*(error|warning)' | head -20
  flutter analyze --no-pub 2>&1 | tail -3
else
  echo "  flutter not on PATH — analyzer gate not checked"
fi

hr "EVIDENCE SWEEP COMPLETE — reviewer reasons from here"
