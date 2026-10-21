"""How deep a review goes, and on which platform (CEO 2026-10-21).

Review happens on the team's branch, locally, before the work reaches Alpha, on ONE platform (one
codebase): the Codex internal browser on a web build by default, the Android emulator only when the
change touches native or startup code. Depth follows risk so review never becomes the bottleneck:

    1  light      no screen touched: diff, tests and the team's evidence. No app run.
    2  normal     a screen changed: the ticket's test scenarios in EN+Light and AR+Dark.
    3  sensitive  a screen in money, sign-in or database work: every scenario, both languages and
                  themes, plus a 10-minute exploratory pass.

Pure functions: the queue, the evidence gate and the tests all read the same answer.
"""
import re

from agent.execution import phone_check

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


def platform(paths, labels=()):
    """`android` when native/startup code changed (or the ticket says so), else `web`."""
    labels = {str(l).lower() for l in labels or ()}
    if "platform:android" in labels:
        return "android"
    if "platform:web" in labels:
        return "web"
    return "android" if paths and phone_check.needed(paths, labels) else "web"


def describe(paths, labels=()):
    t = tier(paths, labels)
    return {"tier": t, "platform": platform(paths, labels) if t >= 2 else None,
            "min_screenshots": MIN_SCREENSHOTS[t]}
