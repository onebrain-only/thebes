#!/bin/sh
# Build .claude/agents/<seat>.md from the neutral Seat registry, a Role contract,
# and Claude-specific rendering configuration.
#
#   agent/state/registry/seats.json  Seat identity + Role mapping — neutral
#   .claude/bindings/<seat>.yml      YAML frontmatter body        — Claude
#   agent/roles/<role>.md            neutral markdown, no frontmatter — the ROLE
#   .claude/agents/<seat>.md         generated: fence + binding + fence + banner
#                                    + role
#
# The neutral registry defines which Seats exist and which Role each instantiates.
# Claude configuration supplies only the provider-specific frontmatter. Its legacy
# `role:` duplicate is retained temporarily, validated for parity, and never used
# by the renderer as the Role source of truth.
#
# `seat_context:` remains retired. A configuration that declares it is an error.
# Every Claude configuration key other than legacy `role:` passes through byte for
# byte, and only neutral Seats are rendered.
#
# Usage:
#   agent/scripts/build-agents.sh          regenerate
#   agent/scripts/build-agents.sh --check  verify regeneration is a no-op (exit 1 if not)
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec "${PYTHON:-python3}" "$ROOT/agent/scripts/render_claude_agents.py" "$@"
