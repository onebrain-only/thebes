#!/bin/bash
# Double-click this after a restart to bring Thebes up: the loops (watchdog, Ready dispatcher)
# and every team session, on their SAME session ids. It is NOT a Login Item: Thebes never starts
# by itself (CEO 2026-11-11). Terminal already has access to the Desktop folder, so no extra
# permission is needed.
cd "$(dirname "$0")/../.." || exit 1
bash agent/scripts/thebes-up.sh
# The Thebes-owned Codex (the headless reviewer): its app-server and the local Listener both stop
# with a restart. Both are idempotent: an already running one is left alone.
python3 -m agent.execution.codex_runtime start > /dev/null 2>&1 && echo "ok       codex runtime (headless reviewer)" || echo "FAILED   codex runtime"
if ! python3 -m agent.listener health > /dev/null 2>&1; then
  nohup python3 -m agent.listener serve >> agent/state/runtime/listener.out 2>&1 &
  sleep 2
fi
python3 -m agent.listener health > /dev/null 2>&1 && echo "ok       listener" || echo "FAILED   listener"
echo
bash agent/scripts/thebes-up.sh --check
echo
echo "Thebes is up. Remaining by hand: if you also use the Desktop reviewer, open Codex Desktop and tell the Reviewer conversation to start its wait loop. The headless reviewer needs nothing: Thebes wakes it."
sleep 20
