#!/bin/bash
# Set up a fresh clone of Thebes on a new machine. Safe to run again: every step checks
# first and changes only what is missing. The steps are explained in agent/SETUP.md.
#
#   bash agent/scripts/bootstrap.sh                  # everything
#   bash agent/scripts/bootstrap.sh --skip-product   # do not clone the two Product repositories
#
# It never touches an existing checkout, never writes a secret and never starts a session.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
SKIP_PRODUCT=0
[ "${1:-}" = "--skip-product" ] && SKIP_PRODUCT=1
say() { printf '%s\n' "$*"; }
problems=0

say "== tools"
for tool in git python3; do
  if command -v "$tool" >/dev/null 2>&1; then say "ok       $tool"; else say "MISSING  $tool"; problems=$((problems + 1)); fi
done
for tool in claude codex flutter gh; do
  command -v "$tool" >/dev/null 2>&1 && say "ok       $tool" || say "absent   $tool (needed to run sessions or Product checks, not to pass this script)"
done
[ "$problems" -eq 0 ] || { say "Install the missing tools and run this again."; exit 1; }

say "== repositories"
PIN="$(sed -n 's/.*Compatible governance baseline.*`\([0-9a-f]\{40\}\)`.*/\1/p' CLAUDE.md | head -1)"
[ -n "$PIN" ] || { say "FAILED   no governance pin found in CLAUDE.md"; exit 1; }
mkdir -p Dabbler
if [ -d Dabbler/dabbler-docs/.git ]; then
  HEAD_NOW="$(git -C Dabbler/dabbler-docs rev-parse HEAD)"
  [ "$HEAD_NOW" = "$PIN" ] && say "ok       dabbler-docs is at the pin" \
    || say "note     dabbler-docs is at $HEAD_NOW, the pin is $PIN (left as it is)"
else
  git clone https://github.com/dabblersport/dabbler-docs.git Dabbler/dabbler-docs
  git -C Dabbler/dabbler-docs checkout -q "$PIN"
  say "cloned   dabbler-docs at the pin"
fi
clone_product() {   # folder, url, branch
  if [ -d "Dabbler/$1/.git" ]; then say "ok       $1"
  elif [ "$SKIP_PRODUCT" = 1 ]; then say "skipped  $1"
  else git clone --branch "$3" "$2" "Dabbler/$1" && say "cloned   $1 on $3"; fi
}
clone_product dabbler-code https://github.com/dabblersport/webapp.git staging
clone_product dabbler-design-system https://github.com/dabblersport/dabbler-design-system.git staging

say "== runtime folders (local to this checkout, never tracked)"
for dir in agent/state/runtime agent/state/runtime/worktrees agent/listener/runtime agent/qa/runtime agent/.flow; do
  mkdir -p "$dir"
done
say "ok       created"

say "== settings"
python3 agent/scripts/apply_settings.py

say "== generated files"
stale="$(python3 agent/scripts/render_claude_agents.py --check | grep -vc '^ok' || true)"
[ "$stale" = "0" ] && say "ok       .claude/agents matches its sources" || { say "STALE    $stale agent definition(s): run python3 agent/scripts/render_claude_agents.py"; problems=$((problems + 1)); }
python3 agent/scripts/render_skills_index.py --check || problems=$((problems + 1))

say "== left for you (agent/SETUP.md, section 3)"
say "  1. Jira: JIRA_API_TOKEN, JIRA_ACCOUNT_EMAIL and JIRA_CLOUD_ID, in the environment or the macOS keychain."
say "  2. claude and codex signed in; the dart-flutter plugin installed (/plugin install dart-flutter@dart-flutter)."
say "  3. The watchdog under launchd: bash agent/scripts/install-watchdog-agent.sh"
say "  4. Start the sessions: bash agent/scripts/thebes-up.sh"
[ "$problems" -eq 0 ] && say "bootstrap finished" || { say "bootstrap finished with $problems problem(s)"; exit 1; }
