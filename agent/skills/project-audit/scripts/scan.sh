#!/usr/bin/env bash
# Dabbler mechanical audit scanner.
# Emits hard, file-cited evidence for the master-analyst to reason over.
# Every number here is derived from the tree — never estimated.
set -uo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

SECTION=${1:-all}
hr() { printf '\n== %s ==\n' "$1"; }

# ---------------------------------------------------------------- inventory
if [[ $SECTION == all || $SECTION == inventory ]]; then
hr "FEATURE INVENTORY (files / dart LOC / screens)"
for d in lib/features/*/; do
  n=$(basename "$d")
  f=$(find "$d" -name '*.dart' | wc -l | tr -d ' ')
  l=$(find "$d" -name '*.dart' -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')
  s=$(find "$d" -path '*/screens/*.dart' ! -name '*.broken' 2>/dev/null | wc -l | tr -d ' ')
  printf '%-22s files=%-4s loc=%-7s screens=%s\n' "$n" "$f" "$l" "$s"
done | sort -t= -k3 -rn
fi

# ------------------------------------------------------- completed vs not
if [[ $SECTION == all || $SECTION == wiring ]]; then
hr "ORPHAN SCREENS (class never referenced outside its own file => unreachable)"
for f in $(find lib -path '*/screens/*.dart' ! -name '*.broken'); do
  for cls in $(grep -oE 'class ([A-Z][A-Za-z0-9_]*Screen)' "$f" | awk '{print $2}' | sort -u); do
    n=$(grep -rl "\b${cls}\b" lib/ --include='*.dart' 2>/dev/null | grep -vx "$f" | wc -l | tr -d ' ')
    [ "$n" -eq 0 ] && echo "ORPHAN  $cls  ->  $f"
  done
done

hr "ROUTED SCREENS (referenced from app_router.dart => reachable)"
grep -oE '[A-Z][A-Za-z0-9_]*Screen' lib/app/app_router.dart 2>/dev/null | sort -u | wc -l | xargs echo "distinct screen classes wired into router:"

hr "SUSPICIOUS FILES (.broken/.bak/.old/_v2/_old/_new/copy)"
find lib -type f \( -name '*.broken' -o -name '*.bak' -o -name '*.old' -o -name '*_v2.dart' \
  -o -name '*_old.dart' -o -name '*_new.dart' -o -name '*copy*.dart' \) | sed 's/^/  /'

hr "PLACEHOLDER / STUB MARKERS"
grep -rn --include='*.dart' -E 'TODO|FIXME|HACK|XXX|not implemented|Unimplemented|throw UnimplementedError|Coming soon|Placeholder' lib/ 2>/dev/null \
  | awk -F: '{print $1}' | sort | uniq -c | sort -rn | head -25
echo "  total markers: $(grep -rn --include='*.dart' -cE 'TODO|FIXME|HACK|XXX|UnimplementedError' lib/ 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')"
fi

# ------------------------------------------------------------ used/unused
if [[ $SECTION == all || $SECTION == unused ]]; then
hr "DEAD FEATURE FLAGS (declared but never read outside feature_flags.dart)"
FF=lib/core/config/feature_flags.dart
for flag in $(grep -oE 'static (const|final) bool ([a-zA-Z0-9_]+)' $FF 2>/dev/null | awk '{print $NF}'); do
  n=$(grep -rl "\b${flag}\b" lib/ --include='*.dart' 2>/dev/null | grep -v "$FF" | wc -l | tr -d ' ')
  [ "$n" -eq 0 ] && echo "  UNUSED FLAG  $flag"
done
echo "  declared flags: $(grep -cE 'static (const|final) bool' $FF 2>/dev/null || echo 0)"

hr "UNUSED PUBSPEC DEPENDENCIES (declared, never imported)"
awk '/^dependencies:/{f=1;next} /^dev_dependencies:|^flutter:|^dependency_overrides:/{f=0} f && /^  [a-z_0-9]+:/{sub(/:.*$/,"");gsub(/ /,"");print}' pubspec.yaml 2>/dev/null \
| while read -r p; do
    [ -z "$p" ] && continue
    case "$p" in flutter|sdk|flutter_localizations) continue;; esac
    grep -rqE "package:${p}[/']" lib/ 2>/dev/null || echo "  UNUSED DEP  $p"
  done

hr "ORPHAN PROVIDERS (declared, never watched/read)"
grep -rhoE '(final|late final) ([a-zA-Z0-9_]+)Provider' lib/ --include='*.dart' 2>/dev/null \
| awk '{print $NF}' | sort -u | while read -r p; do
    n=$(grep -rc "\b${p}\b" lib/ --include='*.dart' 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
    [ "$n" -le 1 ] && echo "  ORPHAN PROVIDER  $p"
  done | head -40
fi

# --------------------------------------------------------------- security
if [[ $SECTION == all || $SECTION == security ]]; then
hr "SECRET / KEY LEAK SCAN"
grep -rnE --include='*.dart' --include='*.ts' --include='*.yaml' --include='*.json' \
  "(eyJ[A-Za-z0-9_-]{20,}|sk_live_|sk_test_|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY|service_role)" \
  lib/ supabase/ web/ android/ ios/ 2>/dev/null | head -20 || echo "  none found in scanned trees"
echo "  .env gitignored: $(git check-ignore .env >/dev/null 2>&1 && echo YES || echo '*** NO — RISK ***')"
echo "  .env tracked by git: $(git ls-files --error-unmatch .env >/dev/null 2>&1 && echo '*** YES — RISK ***' || echo no)"

hr "CLIENT-SIDE AUTH CHECKS (should be RLS, not client)"
grep -rn --include='*.dart' -E 'currentUser(!|\?)?\.id ==|user\.id ==|isAdmin|role ==' lib/ 2>/dev/null | wc -l | xargs echo "  occurrences:"

hr "SUPABASE HARDCODED IDENTIFIERS (should use supabase_config.dart)"
grep -rn --include='*.dart' -E "\.from\('" lib/ 2>/dev/null | grep -v 'supabase_config.dart' | wc -l | xargs echo "  hardcoded .from('table') calls:"
grep -rn --include='*.dart' -E "\.storage\.from\('" lib/ 2>/dev/null | wc -l | xargs echo "  hardcoded storage buckets:"
fi

# ------------------------------------------------------------ convention
if [[ $SECTION == all || $SECTION == convention ]]; then
hr "CONVENTION DRIFT (per CLAUDE.md rules)"
echo "  hardcoded Color(0x...) in features : $(grep -rn --include='*.dart' 'Color(0x' lib/features/ 2>/dev/null | wc -l | tr -d ' ')"
echo "  raw MaterialPage (must use wrappers): $(grep -rn --include='*.dart' 'MaterialPage(' lib/ 2>/dev/null | wc -l | tr -d ' ')"
echo "  files using legacy Either<>         : $(grep -rl 'Either<' lib/ --include='*.dart' 2>/dev/null | wc -l | tr -d ' ')"
echo "  files using Result<>               : $(grep -rl 'Result<' lib/ --include='*.dart' 2>/dev/null | wc -l | tr -d ' ')"
echo "  print() left in code               : $(grep -rn --include='*.dart' -E '(^|[^.\w])print\(' lib/ 2>/dev/null | wc -l | tr -d ' ')"

hr "GOD FILES (>500 LOC — CLAUDE.md limit)"
find lib -name '*.dart' ! -name '*.g.dart' ! -name '*.freezed.dart' -exec wc -l {} + 2>/dev/null \
  | sort -rn | awk '$1>500 && $2!="total" {printf "  %-6s %s\n",$1,$2}' | head -25
echo "  total over limit: $(find lib -name '*.dart' ! -name '*.g.dart' ! -name '*.freezed.dart' -exec wc -l {} + 2>/dev/null | awk '$1>500 && $2!="total"' | wc -l | tr -d ' ')"
fi

# ------------------------------------------------------------- tests/docs
if [[ $SECTION == all || $SECTION == tests ]]; then
hr "TEST COVERAGE SHAPE"
echo "  test files : $(find test -name '*_test.dart' 2>/dev/null | wc -l | tr -d ' ')"
echo "  lib files  : $(find lib -name '*.dart' ! -name '*.g.dart' ! -name '*.freezed.dart' | wc -l | tr -d ' ')"
echo "  features with NO test dir:"
for d in lib/features/*/; do n=$(basename "$d"); [ -d "test/features/$n" ] || echo "    $n"; done

hr "DOCUMENTATION INVENTORY (age vs last code change)"
for f in $(find docs README.md CLAUDE.md -maxdepth 2 -name '*.md' 2>/dev/null); do
  d=$(git log -1 --format=%cs -- "$f" 2>/dev/null); echo "  ${d:-untracked}  $f"
done | sort
echo "  last commit on lib/: $(git log -1 --format=%cs -- lib/ 2>/dev/null)"
fi

# --------------------------------------------------------------- analyzer
if [[ $SECTION == analyze ]]; then
hr "FLUTTER ANALYZE"
flutter analyze --no-pub 2>&1 | tail -30
fi

hr "SCAN COMPLETE"

# ------------------------------------------------- incompleteness + agents
if [[ ${SECTION:-all} == incomplete ]]; then
hr "IN-CODE INCOMPLETENESS ADMISSIONS (grouped by feature)"
grep -rn --include='*.dart' -iE '(TODO|FIXME|HACK|XXX|not implemented|unimplemented|coming soon|placeholder|temporary|for now|stub this|WIP)' lib/ 2>/dev/null \
  | sed -E 's#^lib/features/([^/]+)/.*#\1#; s#^lib/(app|core|data|themes|utils)/.*#_platform_#' \
  | sort | uniq -c | sort -rn
hr "RAW INCOMPLETENESS LINES (file:line — quote these in the report)"
grep -rn --include='*.dart' -iE '(TODO|FIXME|HACK|XXX|not implemented|unimplemented|coming soon|placeholder)' lib/ 2>/dev/null | head -120
hr "EMPTY CATCH BLOCKS (swallowed errors)"
grep -rn --include='*.dart' -A1 'catch' lib/ 2>/dev/null | grep -B1 -E '^\S+-[0-9]+-\s*\}' | head -20
hr "AGENT / SKILL UTILISATION"
echo "  agents defined : $(ls .claude/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
for a in .claude/agents/*.md; do
  n=$(basename "$a" .md)
  m=$(find ".claude/agent-memory/$n" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "    $n  memory-files=$m"
done
echo "  project skills : $(ls -d .claude/skills/*/ 2>/dev/null | wc -l | tr -d ' ')"
echo "  global skills  : $(ls -d ~/.claude/skills/*/ 2>/dev/null | wc -l | tr -d ' ')"
fi
