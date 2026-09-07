#!/bin/sh
# One Brain — flow event recorder.
#
# Called by Claude Code hooks. Reads the hook payload on stdin, appends one
# trimmed JSON line to agent/.flow/events.jsonl, and gets out of the way.
#
#   flow-hook.sh <EventName>
#
# Never fails and never blocks: a recorder that can break a tool call is worse
# than no recorder. Every exit path is 0.
#
# WHAT IT DELIBERATELY DOES NOT RECORD
#   tool_response  — a PostToolUse payload carries the tool's whole output, so
#                    recording it would turn this log into a copy of every file
#                    ever read. We only need that the call finished.
#   long strings   — every string is capped at 300 characters. Enough to know
#                    which command ran and against which file; not enough to
#                    accumulate contents.

set -u
EVENT="${1:-unknown}"

# resolve the repo root from this script's own location, not the caller's cwd —
# hooks fire with whatever directory the session happens to be in
SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
ROOT=$(cd "$SELF/../.." 2>/dev/null && pwd) || exit 0
OUT="$ROOT/agent/.flow"
mkdir -p "$OUT" 2>/dev/null || exit 0

jq -c --arg e "$EVENT" --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  def cap: if type == "string" then .[0:300]
           elif type == "object" then with_entries(.value |= cap)
           elif type == "array"  then (.[0:20] | map(cap))
           else . end;
  {event:$e, at:$t}
  + (del(.tool_response, .tool_result, .transcript_path) | cap)
' >> "$OUT/events.jsonl" 2>/dev/null

exit 0
