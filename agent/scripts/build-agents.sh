#!/bin/sh
# Build .claude/agents/<seat>.md from a Role contract + a Claude-specific binding.
#
#   .claude/bindings/<seat>.yml      YAML frontmatter body        — the SEAT
#   agent/roles/<role>.md            neutral markdown, no frontmatter — the ROLE
#   .claude/agents/<seat>.md         generated: fence + binding + fence + banner
#                                    + role
#
# ROLE + BINDING IS SUFFICIENT. Wave 6 retired agent/seats/*.md: the Role defines
# capability and authority, the binding defines seat identity, and nothing else is
# needed to generate a seat. `seat_context:` is no longer read — a binding that
# still declares one is an ERROR rather than a silent no-op, because a seat
# carrying private product knowledge is the thing Role ≠ Seat exists to prevent.
#
# ROLE ≠ SEAT. A binding names the Role it instantiates, so many seats may share
# one Role contract — frontend-1..8 all resolve to agent/roles/frontend.md. The
# mapping is explicit, never inferred from the seat's filename.
#
#   role: <role-id>            REQUIRED. Resolves agent/roles/<role-id>.md
#
# It is generator metadata and is stripped before the frontmatter is emitted: the
# generated file is what Claude Code parses, and implementation-only keys do not
# belong in it. Every other binding key passes through untouched.
#
# Only seats that have a binding are generated; every other file in
# .claude/agents/ is left untouched.
#
# Usage:
#   agent/scripts/build-agents.sh          regenerate
#   agent/scripts/build-agents.sh --check  verify regeneration is a no-op (exit 1 if not)
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
BINDINGS="$ROOT/.claude/bindings"
ROLES="$ROOT/agent/roles"
AGENTS="$ROOT/.claude/agents"

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

[ -d "$BINDINGS" ] || { echo "ERROR: no $BINDINGS"; exit 1; }
mkdir -p "$AGENTS"

# value of a top-level key in a binding, empty if absent
field() {
  sed -n "s/^$2:[[:space:]]*//p" "$1" | head -1 | sed 's/[[:space:]]*$//' | tr -d '"'"'"''
}

status=0
found=0
for binding in "$BINDINGS"/*.yml; do
  [ -e "$binding" ] || continue
  found=$((found + 1))
  seat=$(basename "$binding" .yml)
  out="$AGENTS/$seat.md"

  role_id=$(field "$binding" role)
  if [ -z "$role_id" ]; then
    echo "ERROR: binding $seat declares no role:"
    status=1
    continue
  fi

  role="$ROLES/$role_id.md"
  if [ ! -f "$role" ]; then
    echo "ERROR: binding $seat declares role '$role_id' but $role does not exist"
    status=1
    continue
  fi

  # Wave 6: seat context is retired. A binding still declaring it is a defect.
  if grep -q '^seat_context:' "$binding"; then
    echo "ERROR: binding $seat declares seat_context, retired in Wave 6 — Role + Binding is sufficient"
    status=1
    continue
  fi

  tmp=$(mktemp)
  printf -- '---\n' > "$tmp"
  # generator metadata is consumed here, never emitted
  grep -v '^role:' "$binding" >> "$tmp"
  printf -- '---\n' >> "$tmp"
  printf -- '<!-- GENERATED FILE — do not edit. -->\n'                                 >> "$tmp"
  printf -- '<!-- Seat:    .claude/bindings/%s.yml -->\n' "$seat"                      >> "$tmp"
  printf -- '<!-- Role:    agent/roles/%s.md -->\n' "$role_id"                         >> "$tmp"
  printf -- '<!-- Rebuild: agent/scripts/build-agents.sh -->\n'                        >> "$tmp"
  printf -- '\n'                                                                       >> "$tmp"
  cat "$role" >> "$tmp"

  if [ "$CHECK" -eq 1 ]; then
    if [ -f "$out" ] && cmp -s "$tmp" "$out"; then
      echo "ok      $seat"
    else
      echo "STALE   $seat  ($out differs from generated output)"
      status=1
    fi
    rm -f "$tmp"
  else
    mv "$tmp" "$out"
    echo "built   $seat"
  fi
done

[ "$found" -eq 0 ] && { echo "ERROR: no bindings found in $BINDINGS"; exit 1; }
exit "$status"
