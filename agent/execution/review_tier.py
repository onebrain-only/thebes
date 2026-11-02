"""How deep a review goes, and on which platform (CEO 2026-10-21).

Review happens on the team's branch, locally, before the work reaches Alpha, on ONE platform (one
codebase): a web build in the Codex internal browser (CEO 2026-10-22: no simulators). Depth follows
risk so review never becomes the bottleneck:

    1  light      no screen touched: diff, tests and the team's evidence. No app run. Not
                  sensitive either: no reviewer at all, green run checks pass it (D-049).
    2  normal     a screen changed: the ticket's test scenarios in ONE language and theme;
                  AR+Dark when user-facing text changed (D-049).
    3  sensitive  a screen in money, sign-in or database work: every scenario, both languages and
                  themes, plus a 10-minute exploratory pass.

Pure functions: the queue, the evidence gate and the tests all read the same answer.
"""
import re

UI_PATH = re.compile(r"(^|/)(presentation|widgets|screens|app_boot)/|^lib/core/design_system/|"
                     r"^(ios|android|web|assets)/|\.arb$")
SENSITIVE_PATH = re.compile(r"^lib/features/(auth|authentication|payments?|wallet|money)/|"
                            r"^supabase/|/migrations?/")
SENSITIVE_LABELS = {"money", "auth", "db", "migration", "payments"}
# screenshots a PASS must carry, per tier (evidence gate in review_queue.submit_*)
MIN_SCREENSHOTS = {1: 0, 2: 1, 3: 2}


def tier(paths, labels=()):
    """1, 2 or 3. Unknown paths (None) are treated as a screen change: look rather than guess.
    Sensitivity only deepens a review that has a screen to look at: a migration or a repository
    change with no screen is read in the diff and its tests (tier 1), never photographed."""
    labels = {str(l).lower() for l in labels or ()}
    if "tier:1" in labels:
        return 1
    if "tier:3" in labels:
        return 3
    screen = paths is None or "tier:2" in labels or any(UI_PATH.search(p) for p in paths)
    if not screen:
        return 1
    sensitive = bool(labels & SENSITIVE_LABELS) or any(SENSITIVE_PATH.search(p) for p in paths or ())
    return 3 if sensitive else 2


TEXT_PATH = re.compile(r"\.arb$|(^|/)l10n/|(^|/)(strings|copy)\.dart$")


def sensitive(paths, labels=()):
    labels = {str(l).lower() for l in labels or ()}
    return bool(labels & SENSITIVE_LABELS) or any(SENSITIVE_PATH.search(p) for p in paths or ())


def auto_pass(paths, labels=()):
    """D-049 (CEO 2026-11-02, Q3): tier 1 needs no human or model reviewer. A change whose paths
    are KNOWN, touch no screen and nothing sensitive (money, sign-in, database) passes on its green
    run checks (analyze + tests). Unknown paths, a screen, or anything sensitive: a reviewer looks."""
    return paths is not None and bool(paths) and tier(paths) == 1 and not sensitive(paths, labels)


def coverage(paths, labels=()):
    """What a reviewer must look at, per tier (D-049, Q3). Tier 2 is ONE language and theme;
    when the change touches user-facing text it is Arabic + Dark, where RTL and copy break."""
    t = tier(paths, labels)
    if t == 1:
        return "diff and tests only"
    if t == 3:
        return "EN+Light and AR+Dark, every TC, plus the exploratory pass"
    if paths is None or any(TEXT_PATH.search(p) for p in paths):
        return "AR+Dark only (text changed)"
    return "one of EN+Light or AR+Dark"


def describe(paths, labels=()):
    t = tier(paths, labels)
    return {"tier": t, "platform": "web" if t >= 2 else None, "min_screenshots": MIN_SCREENSHOTS[t],
            "coverage": coverage(paths, labels), "auto_pass": auto_pass(paths, labels)}
