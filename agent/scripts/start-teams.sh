#!/bin/bash
# Start the idle execution teams (D-032) and bind each to its durable session id.
#   bash agent/scripts/start-teams.sh              # every unbound team
#   bash agent/scripts/start-teams.sh habu         # just one
#   bash agent/scripts/start-teams.sh --restart    # restart every FREE team on the current model
#   bash agent/scripts/start-teams.sh --restart habu
# Teams already bound to a session are skipped, unless --restart: then a team with no open
# dispatch is stopped and replaced by a fresh session (the binding keeps the old id in its
# lineage), and a busy team is left alone so its ticket is never cut off. Run it from your own terminal: Claude
# Code's permission check does not let a session create background sessions itself.
set -u
cd "$(dirname "$0")/../.." || exit 1
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE="${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-20}"   # compact sessions near 200k (2026-10-20)
# Permission prompts are answered by agent/scripts/policy_hook.py (D-043): never a question to the CEO.
export CLAUDE_CODE_PLUGIN_DIRS="${CLAUDE_CODE_PLUGIN_DIRS:-$PWD/agent/mods/thebes-context}"   # the thebes-context mod: self-compaction + tracker (2026-10-20)
HOME_DIR="$(pwd)"
MODEL=claude-opus-5-5   # CEO 2026-11-02: every team on Opus 5.5, effort medium
EFFORT=medium
RESTART=0
[ "${1:-}" = "--restart" ] && { RESTART=1; shift; }

# One line per team to start: id, lane, old session id, old binding revision ("-" for
# both when the team is unbound), display name last because it may hold a space.
unbound=$(python3 - "$RESTART" "$@" <<'EOF'
import sys
sys.path.insert(0, '.')
from agent.state import store, teams
from agent.execution import team_pool
restart = sys.argv[1] == "1"
want = set(sys.argv[2:])
busy = {t["team_id"] for t in team_pool.team_bindings() if t["busy"]}
for tid, t in sorted(teams.delivery_teams().items(), key=lambda kv: kv[1]["number"]):
    if want and tid not in want:
        continue
    b = store.active_role_session(tid)
    if not b:
        print(tid, t.get("lane", "code"), "-", "-", t["display_name"])
    elif restart and tid in busy:
        print("  %s is busy, left running; restart it once its ticket is done" % tid, file=sys.stderr)
    elif restart:
        print(tid, t.get("lane", "code"), b["session_id"], b["revision"], t["display_name"])
EOF
)
[ -z "$unbound" ] && { echo "Nothing to start: every requested team has a session (or is busy)."; exit 0; }

while read -r tid lane old_sid old_rev display; do
  name="thebes-team-$tid"
  if [ "$old_sid" != "-" ]; then
    echo "Restarting $display ($name) on $MODEL/$EFFORT; stopping $old_sid ..."
    claude stop "$old_sid" >/dev/null 2>&1
  else
    echo "Starting $display ($name, lane $lane) ..."
  fi
  if [ "$lane" = "ops" ]; then
    role="the Thebes OPERATIONS team (D-042): the only team that applies database migrations, pushes, and integrates team branches into staging (Alpha only on a CEO promotion order, D-052); you also answer questions and write ticket briefs, running seats as subagents"
  elif [ "$lane" = "qa" ]; then
    role="the Thebes QA conversation (D-043 fallback): you review finished work; you never build, fix, push, merge or write to the database. You stay idle until the orchestrator sends you a dispatch that turns the Claude review channel on or off; then follow agent/REVIEWER.md (the Claude variant section) exactly"
  else
    role="a Thebes code team, an execution island that runs seats as subagents; you push only your own branch, never merge into staging, Alpha, Canary or main, and never write to the database"
  fi
  # D-050: the new session is the one that was NOT there before, not the first row by name.
  before=$(claude agents --json --all 2>/dev/null | python3 -c "
import json,sys
print(' '.join(r.get('sessionId','') for r in json.load(sys.stdin)))" 2>/dev/null)
  claude --bg --name "$name" --model "$MODEL" --effort "$EFFORT" --settings agent/state/registry/team-settings.json "You are Thebes team $display, $role. Read CLAUDE.md and agent/skills/route-to-seat/SKILL.md. Do nothing now. Reply with one line: $(echo "$display" | tr a-z A-Z) READY, then go idle. Later a THEBES_CONVERSATION_DISPATCH envelope will arrive as a user turn; follow its team, lane and report instructions exactly." >/dev/null
  sid=""
  for _ in $(seq 1 30); do
    sid=$(claude agents --json 2>/dev/null | python3 -c "
import json,sys
before=set('$before'.split())
rows=[r for r in json.load(sys.stdin) if r.get('name')=='$name' and r.get('sessionId') not in before]
print(rows[0]['sessionId'] if rows else '')" 2>/dev/null)
    [ -n "$sid" ] && break
    sleep 2
  done
  if [ -z "$sid" ]; then echo "  could not find the session for $name — check 'claude agents'"; continue; fi
  python3 - "$tid" "$sid" "$HOME_DIR" "$name" "$old_rev" <<'EOF'
import sys
sys.path.insert(0, '.')
from agent.state import store
tid, sid, home, name, old_rev = sys.argv[1:]
store.bind_role_session(tid, "claude", sid, home, "ceo", session_name=name,
                        expected_revision=None if old_rev == "-" else int(old_rev))
print("  bound %s -> %s" % (tid, sid))
EOF
  python3 -m agent.execution.team_pool sweep-duplicates "$tid" >/dev/null \
    && echo "  retired old $name copies"
done <<< "$unbound"

echo; python3 -m agent.execution.team_pool free
