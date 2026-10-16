#!/bin/bash
# Double-click this, or add it to System Settings > General > Login Items, to bring Thebes up
# after a restart: the loops (watchdog, Ready dispatcher) and every team session, on their SAME
# session ids. Terminal already has access to the Desktop folder, so no extra permission is needed.
cd "$(dirname "$0")/../.." || exit 1
bash agent/scripts/thebes-up.sh
echo
bash agent/scripts/thebes-up.sh --check
echo
echo "Thebes is up. Remaining by hand: Codex Desktop open, and tell the Reviewer conversation to start its wait loop."
sleep 20
