#!/bin/bash
# Bring Thebes back after a reboot (D-042). Safe to run any time: everything already running
# is left alone.
#
#   bash agent/scripts/thebes-up.sh            # start what is missing
#   bash agent/scripts/thebes-up.sh --check    # only report, change nothing
#
# Background loops: the watchdog and the Ready dispatcher (zero tokens).
# Sessions: the orchestrator and every bound team are resumed with their SAME session id, so
# no conversation, binding or memory is lost; a team with no session yet is started by
# start-teams.sh. Run it from your own terminal: Claude Code does not let a session create
# background sessions itself.
set -u
cd "$(dirname "$0")/../.." || exit 1
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1
RUNTIME=agent/state/runtime
say() { printf '%s\n' "$*"; }

loop() {   # name, module
  if pgrep -f "$2 serve" >/dev/null 2>&1; then
    say "ok       $1 is running"
  elif [ $CHECK = 1 ]; then
    say "MISSING  $1"
  else
    nohup python3 -m "$2" serve >> "$RUNTIME/$1.out" 2>&1 &
    sleep 1
    pgrep -f "$2 serve" >/dev/null 2>&1 && say "started  $1" || say "FAILED   $1 (see $RUNTIME/$1.out)"
  fi
}

say "== background loops"
loop watchdog agent.execution.watchdog
loop ready-dispatcher agent.execution.ready_dispatcher

say "== sessions"
live=$(claude agents --json 2>/dev/null | python3 -c "
import json,sys
try: rows=json.load(sys.stdin)
except Exception: rows=[]
print(' '.join(r.get('sessionId','') for r in rows if r.get('pid')))")
python3 - <<'EOF' > "$RUNTIME/.thebes-up.sessions"
import sys
sys.path.insert(0, '.')
from agent.state import store, teams
for tid, t in sorted(teams.read().items(), key=lambda kv: kv[1]["number"]):
    b = store.active_role_session(tid)
    print(tid, (b or {}).get("session_id") or "-", t["display_name"].replace(" ", "_"))
EOF
missing_teams=""
while read -r tid sid display; do
  display=${display//_/ }
  if [ "$sid" = "-" ]; then
    say "UNBOUND  $display"
    [ "$tid" != "orchestrator" ] && missing_teams="$missing_teams $tid"
    continue
  fi
  case " $live " in
    *" $sid "*) say "ok       $display (${sid:0:8}) is running" ;;
    *)
      if [ $CHECK = 1 ]; then
        say "STOPPED  $display (${sid:0:8})"
      else
        if [ "$tid" = "orchestrator" ]; then
          msg="Thebes restarted after a reboot. You are the orchestrator: re-read agent/ORCHESTRATOR.md, start your inbox waiter (section 1), then reply in one line that you are back."
        else
          msg="Thebes restarted after a reboot. You are team $display. Do nothing now; reply with one line that you are back and go idle. Your next work arrives as a THEBES_CONVERSATION_DISPATCH envelope."
        fi
        claude --bg --resume "$sid" "$msg" >/dev/null 2>&1 \
          && say "resumed  $display (${sid:0:8})" || say "FAILED   $display: claude --bg --resume $sid"
      fi ;;
  esac
done < "$RUNTIME/.thebes-up.sessions"
rm -f "$RUNTIME/.thebes-up.sessions"

if [ -n "$missing_teams" ] && [ $CHECK = 0 ]; then
  say "== starting unbound teams:$missing_teams"
  bash agent/scripts/start-teams.sh $missing_teams
fi
[ $CHECK = 0 ] && say "== done. The orchestrator needs Remote Control again: open it and type /rc (or set remoteControlAtStartup in /config once)."
exit 0
