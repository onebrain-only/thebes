"""Check an Epic cut plan before any ticket is written (D-049, skill `epic-cut`).

The PM cuts an approved Epic into tickets that several teams can run at once. This reads the
plan as JSON and says what would make it serial or unsafe:

  python3 -m agent.execution.cut_plan check <plan.json>     # errors exit 1
  python3 -m agent.execution.cut_plan hotspots [--days 30]  # files most tickets fight over

Plan shape (one object):
  {"epic": "KAN-708",
   "tickets": [{"id": "T1", "summary": "...", "component": "Listings",
                "capability": "backend", "kind": "contract",
                "surfaces": ["supabase/migrations/2026..._events_v2.sql", "test/..."],
                "blocked_by": {"T0": "reads table events_v2 that T0 creates"},
                "estimate_min": 40, "tcs": 0}]}

kind is one of contract, migration, function, screen, strings. Collisions use the same rule
claimability uses (`queue.surfaces_collide`), so a plan that passes here does not stall on
`surface-contention` later.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.state import policy, queue                                  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODE = os.path.join(ROOT, "Dabbler", "dabbler-code")
KINDS = ("contract", "migration", "function", "screen", "strings")
CODE_TEAMS = 5
# Generated from the .arb files: a conflict there is resolved by `flutter gen-l10n`, not by hand.
REGENERATED = re.compile(r"^lib/l10n/app_localizations(_\w+)?\.dart$|^pubspec\.lock$")
STRINGS = re.compile(r"\.arb$")
TEST = re.compile(r"(^|/)test/|_test\.dart$|(^|/)supabase/tests/")


def _paths(t, *, drop_strings=False):
    out = []
    for p in t.get("surfaces") or ():
        p = policy.normalise_path(p)
        if REGENERATED.search(p) or (drop_strings and STRINGS.search(p)):
            continue
        out.append(p)
    return out


def _upstream(tickets):
    """id -> every id it waits for, directly or through others."""
    direct = {t["id"]: set((t.get("blocked_by") or {}).keys()) for t in tickets}
    memo = {}

    def walk(i, seen=()):
        if i in memo:
            return memo[i]
        if i in seen:
            raise ValueError("Blocks cycle through %s" % " -> ".join(seen + (i,)))
        acc = set()
        for d in direct.get(i, ()):
            acc |= {d} | walk(d, seen + (i,))
        memo[i] = acc
        return acc

    return {i: walk(i) for i in direct}


def waves(tickets, up=None):
    """Lists of ids that can run together: wave 1 starts now, wave n after wave n-1."""
    up = up or _upstream(tickets)
    level = {}
    direct = {t["id"]: (t.get("blocked_by") or {}).keys() for t in tickets}

    def lv(i):
        if i not in level:
            level[i] = 1 + max([lv(d) for d in direct[i] if d in direct] or [0])
        return level[i]

    out = collections.defaultdict(list)
    for t in tickets:
        out[lv(t["id"])].append(t["id"])
    return [out[k] for k in sorted(out)]


def critical_minutes(tickets):
    by = {t["id"]: t for t in tickets}
    memo = {}

    def cm(i):
        if i not in memo:
            t = by[i]
            memo[i] = (t.get("estimate_min") or 0) + max(
                [cm(d) for d in (t.get("blocked_by") or {}) if d in by] or [0])
        return memo[i]

    return max([cm(i) for i in by] or [0])


def check(plan, hot=()):
    """-> {"errors": [...], "warnings": [...], "waves": [[ids]], "critical_min": n}"""
    errors, warnings = [], []
    tickets = plan.get("tickets") or []
    ids = [t.get("id") for t in tickets]
    if not tickets:
        return {"errors": ["plan has no tickets"], "warnings": [], "waves": [], "critical_min": 0}
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append("%s: id used twice" % dup)
    for t in tickets:
        i = t.get("id")
        for d, why in (t.get("blocked_by") or {}).items():
            if d not in ids:
                errors.append("%s: blocked_by %s, which is not in the plan" % (i, d))
            if not str(why or "").strip():
                errors.append("%s: Blocks %s has no reason. A link needs a real code or data "
                              "dependency; same Epic is not one" % (i, d))
    try:
        up = _upstream(tickets)
    except ValueError as exc:
        return {"errors": errors + [str(exc)], "warnings": warnings, "waves": [], "critical_min": 0}

    for t in tickets:
        i, kind = t.get("id"), t.get("kind")
        if kind not in KINDS:
            errors.append("%s: kind %r is not one of %s" % (i, kind, ", ".join(KINDS)))
        if not t.get("component"):
            errors.append("%s: no domain component (Auth, Social, Listings, Money, Platform)" % i)
        if t.get("surfaces") is None:
            errors.append("%s: surfaces not assessed. Read the code and name the files" % i)
            continue
        est = t.get("estimate_min")
        if not isinstance(est, (int, float)) or est <= 0:
            errors.append("%s: no estimate_min" % i)
        # TH-077 (CEO 2026-11-11): no size cap and no one-screen rule. A ticket is not split.
        paths = _paths(t)
        if kind in ("function", "screen", "migration") and not any(TEST.search(p) for p in paths):
            errors.append("%s: no test file among its surfaces. One function or screen plus its "
                          "test" % i)
        if kind == "screen" and not t.get("tcs"):
            errors.append("%s: a screen ticket needs click-by-click test scenarios (tcs)" % i)
        if kind != "strings" and any(STRINGS.search(p) for p in paths):
            warnings.append("%s: edits .arb files. Put the Epic's strings in one `strings` ticket "
                            "every screen ticket waits on, or this collides with every other "
                            "screen" % i)
        for p in paths:
            if p in hot:
                warnings.append("%s: touches hotspot %s (%d recent commits). Keep the edit "
                                "small or give it to one ticket" % (i, p, hot[p]))

    by = {t["id"]: t for t in tickets if t.get("surfaces") is not None}
    order = list(by)
    for n, a in enumerate(order):
        for b in order[n + 1:]:
            if a in up.get(b, ()) or b in up.get(a, ()):
                continue                                    # serial already: no contention
            if queue.surfaces_collide(_paths(by[a], drop_strings=True),
                                      _paths(by[b], drop_strings=True)):
                errors.append("%s and %s run in parallel but touch the same files. Re-cut "
                              "so they do not, or add a Blocks with the reason" % (a, b))
    for t in by.values():
        for d, why in (t.get("blocked_by") or {}).items():
            src = by.get(d)
            if not src or src.get("kind") in ("contract", "migration", "strings"):
                continue
            if not queue.surfaces_collide(_paths(t, drop_strings=True),
                                          _paths(src, drop_strings=True)):
                warnings.append("%s waits on %s but they share no file and %s is not a "
                                "contract or migration: probably an ordering-only link (%s)"
                                % (t["id"], d, d, why))

    w = waves(tickets, up)
    if w and len(w[0]) < min(CODE_TEAMS, len(tickets)):
        warnings.append("only %d ticket(s) can start now for %d code teams. Cut a contract "
                        "first, then fan out" % (len(w[0]), CODE_TEAMS))
    return {"errors": errors, "warnings": warnings, "waves": w,
            "critical_min": critical_minutes(tickets)}


def hotspots(days=30, top=15, repo=CODE, ref="origin/staging"):
    """{path: commits} for the files touched most often lately, generated files left out."""
    try:
        out = subprocess.run(["git", "-C", repo, "log", "--since=%d.days" % days, "--name-only",
                              "--pretty=format:", ref], capture_output=True, text=True,
                             timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    c = collections.Counter(p for p in out.splitlines() if p and not REGENERATED.search(p))
    return dict(c.most_common(top))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("plan")
    c.add_argument("--no-hotspots", action="store_true")
    h = sub.add_parser("hotspots")
    h.add_argument("--days", type=int, default=30)
    a = ap.parse_args(argv)
    if a.cmd == "hotspots":
        print(json.dumps(hotspots(a.days), indent=1))
        return 0
    with open(a.plan, encoding="utf-8") as f:
        plan = json.load(f)
    res = check(plan, {} if a.no_hotspots else hotspots())
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
