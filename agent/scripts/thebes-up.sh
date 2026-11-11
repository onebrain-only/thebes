#!/bin/bash
# Bring Thebes back after a reboot (D-042). Safe to run any time: everything already running
# is left alone.
#
#   bash agent/scripts/thebes-up.sh            # start what is missing
#   bash agent/scripts/thebes-up.sh --check    # only report, change nothing
#
# Background loops: the watchdog, the Ready dispatcher and the inbox pusher (zero tokens).
# Sessions: the orchestrator and every bound team are resumed with their SAME session id, so
# no conversation, binding or memory is lost; a team with no session yet is started by
# start-teams.sh, and an unbound orchestrator is started and bound here. Run it from your own terminal: Claude Code does not let a session create
# background sessions itself.
set -u
cd "$(dirname "$0")/../.." || exit 1
export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE="${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-20}"   # compact sessions near 200k, not 900k (2026-10-20)
export CLAUDE_CODE_PLUGIN_DIRS="${CLAUDE_CODE_PLUGIN_DIRS:-$PWD/agent/mods/thebes-context}"   # the thebes-context mod: self-compaction + tracker (2026-10-20)
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
loop inbox-push agent.execution.inbox_push   # the orchestrator's inbox arrives as a message

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
missing_orchestrator=0
while read -r tid sid display; do
  display=${display//_/ }
  if [ "$sid" != "-" ]; then
    # A session keeps its mode on every resume; only the CEO can switch it back (TH-073).
    mode=$(python3 -c "from agent.execution import liveness as l; print(l.permission_mode('$sid') or 'auto')")
    [ "$mode" = "auto" ] || say "MODE     $display is in '$mode' mode, not Auto: افتح الجلسة دي من التطبيق واختار Auto"
  fi
  if [ "$sid" = "-" ]; then
    say "UNBOUND  $display"
    [ "$tid" = "orchestrator" ] && missing_orchestrator=1 || missing_teams="$missing_teams $tid"
    continue
  fi
  case " $live " in
    *" $sid "*) say "ok       $display (${sid:0:8}) is running" ;;
    *)
      if [ $CHECK = 1 ]; then
        say "STOPPED  $display (${sid:0:8})"
      else
        if [ "$tid" = "orchestrator" ]; then
          msg="Thebes restarted after a reboot. You are the orchestrator: re-read agent/ORCHESTRATOR.md (your inbox now arrives as a message: start no waiter, section 1), then end the turn with the single character · and nothing else (TH-072)."
        else
          msg="Thebes restarted after a reboot. You are team $display. Do nothing now and do not reply; go idle. Your next work arrives as a THEBES_CONVERSATION_DISPATCH envelope."
        fi
        claude --bg --resume "$sid" "$msg" >/dev/null 2>&1 \
          && say "resumed  $display (${sid:0:8})" || say "FAILED   $display: claude --bg --resume $sid"
      fi ;;
  esac
done < "$RUNTIME/.thebes-up.sessions"
rm -f "$RUNTIME/.thebes-up.sessions"

if [ $missing_orchestrator = 1 ] && [ $CHECK = 0 ]; then
  # No orchestrator is bound (a new machine, or the old conversation was retired): start one
  # and bind it. The name and model have one home, agent/execution/watchdog.py.
  say "== starting the orchestrator"
  read -r oname omodel <<< "$(python3 -c "
from agent.execution import watchdog as w
print(w.ORCHESTRATOR_NAME, w.ORCHESTRATOR_MODEL)")"
  before=$(claude agents --json --all 2>/dev/null | python3 -c "
import json,sys
print(' '.join(r.get('sessionId','') for r in json.load(sys.stdin)))" 2>/dev/null)
  claude --bg --name "$oname" --model "$omodel" --permission-mode auto "You are the Thebes orchestrator, in a fresh session. Read CLAUDE.md and agent/ORCHESTRATOR.md now (your inbox arrives as a message: start no waiter, section 1), then end the turn with the single character · and nothing else (TH-072)." >/dev/null
  osid=""
  for _ in $(seq 1 30); do
    osid=$(claude agents --json 2>/dev/null | python3 -c "
import json,sys
before=set('$before'.split())
rows=[r for r in json.load(sys.stdin) if r.get('name')=='$oname' and r.get('sessionId') not in before]
print(rows[0]['sessionId'] if rows else '')" 2>/dev/null)
    [ -n "$osid" ] && break
    sleep 2
  done
  if [ -z "$osid" ]; then
    say "FAILED   the orchestrator session did not appear in 'claude agents'"
  else
    python3 - "$osid" "$PWD" "$oname" <<'EOF'
import sys
sys.path.insert(0, '.')
from agent.state import store, teams
sid, home, name = sys.argv[1:]
cur = store.read("role_session", teams.ORCHESTRATOR_ID)   # a retired binding is replaced
store.bind_role_session(teams.ORCHESTRATOR_ID, "claude", sid, home, "ceo", session_name=name,
                        expected_revision=cur["revision"] if cur else None)
print("started  Orchestrator (%s)" % sid[:8])
EOF
  fi
fi

if [ -n "$missing_teams" ] && [ $CHECK = 0 ]; then
  say "== starting unbound teams:$missing_teams"
  bash agent/scripts/start-teams.sh $missing_teams
fi
[ $CHECK = 0 ] && say "== done. The orchestrator needs Remote Control again: open it and type /rc (or set remoteControlAtStartup in /config once)."
exit 0
