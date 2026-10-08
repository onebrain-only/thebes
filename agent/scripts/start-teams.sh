#!/bin/bash
# Start the idle execution teams (D-032) and bind each to its durable session id.
#   bash agent/scripts/start-teams.sh              # every unbound team
#   bash agent/scripts/start-teams.sh habu         # just one
# Teams already bound to a session are skipped. Run it from your own terminal: Claude
# Code's permission check does not let a session create background sessions itself.
set -u
cd "$(dirname "$0")/../.." || exit 1
HOME_DIR="$(pwd)"

unbound=$(python3 - "$@" <<'EOF'
import sys
sys.path.insert(0, '.')
from agent.state import store, teams
want = set(sys.argv[1:])
for tid, t in sorted(teams.delivery_teams().items(), key=lambda kv: kv[1]["number"]):
    if want and tid not in want:
        continue
    if not store.active_role_session(tid):
        print(tid, t.get("lane", "code"), t["display_name"])
EOF
)
[ -z "$unbound" ] && { echo "Every requested team already has a session."; exit 0; }

while read -r tid lane display; do
  name="thebes-team-$tid"
  echo "Starting $display ($name, lane $lane) ..."
  if [ "$lane" = "ops" ]; then
    role="the Thebes OPERATIONS team (D-042): the only team that applies database migrations, pushes, and integrates team branches into Alpha; you also answer questions and write ticket briefs, running seats as subagents"
  else
    role="a Thebes code team, an execution island that runs seats as subagents; you never write to the database or push"
  fi
  claude --bg --name "$name" "You are Thebes team $display, $role. Read CLAUDE.md and agent/skills/route-to-seat/SKILL.md. Do nothing now. Reply with one line: $(echo "$display" | tr a-z A-Z) READY, then go idle. Later a THEBES_CONVERSATION_DISPATCH envelope will arrive as a user turn; follow its team, lane and report instructions exactly." >/dev/null
  sid=""
  for _ in $(seq 1 30); do
    sid=$(claude agents --json 2>/dev/null | python3 -c "
import json,sys
rows=[r for r in json.load(sys.stdin) if r.get('name')=='$name']
print(rows[0]['sessionId'] if rows else '')" 2>/dev/null)
    [ -n "$sid" ] && break
    sleep 2
  done
  if [ -z "$sid" ]; then echo "  could not find the session for $name — check 'claude agents'"; continue; fi
  python3 - "$tid" "$sid" "$HOME_DIR" "$name" <<'EOF'
import sys
sys.path.insert(0, '.')
from agent.state import store
tid, sid, home, name = sys.argv[1:]
store.bind_role_session(tid, "claude", sid, home, "ceo", session_name=name)
print("  bound %s -> %s" % (tid, sid))
EOF
done <<< "$unbound"

echo; python3 -m agent.execution.team_pool free
