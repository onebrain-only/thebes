#!/bin/bash
# B3: keep the Thebes watchdog alive across reboots and crashes (launchd KeepAlive). The
# watchdog in turn restarts the Ready dispatcher. Run once, from your own terminal:
#   bash agent/scripts/install-watchdog-agent.sh          # install and start
#   bash agent/scripts/install-watchdog-agent.sh --remove # undo
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/pro.dabbler.thebes.watchdog.plist"
if [ "${1:-}" = "--remove" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true; rm -f "$PLIST"; echo "removed"; exit 0
fi
pkill -f "agent.execution.watchdog serve" 2>/dev/null || true
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>pro.dabbler.thebes.watchdog</string>
  <key>ProgramArguments</key><array>
    <string>$(command -v python3)</string><string>-m</string><string>agent.execution.watchdog</string><string>serve</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/agent/state/runtime/watchdog.out</string>
  <key>StandardErrorPath</key><string>$ROOT/agent/state/runtime/watchdog.out</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
sleep 2
pgrep -f "agent.execution.watchdog serve" >/dev/null && echo "watchdog running under launchd" || echo "FAILED: see agent/state/runtime/watchdog.out"
