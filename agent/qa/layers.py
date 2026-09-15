"""The deterministic test-layer registry.

A layer is DATA: what command runs it, which workspace marker proves the layer
applies, which tool must exist, how expensive it is, and whether it runs
routinely or only on an explicit trigger. Routing reads this table; the runner
executes it; nothing here decides anything.

COST TIERS are an ordering, not a measurement. "Lowest-cost sufficient" is the
routing principle and this is the axis it sorts on.

TRIGGER POLICY
    routine      selectable by routing from the change profile alone
    intentional  selectable only when the profile carries an explicit flag —
                 performance scope, exploratory request
    release      selectable only for a release candidate

EXTERNAL layers (TestSprite, BrowserStack) have no local command. They exist in
the registry so routing can NAME them in a decision and a reviewer can request
them; the runner never invokes them.
"""

import shutil
from dataclasses import dataclass
from typing import Optional, Tuple


COST_TIERS = ("static", "unit", "api", "web_e2e", "mobile_e2e",
              "exploratory", "performance", "device_matrix")

ROUTINE, INTENTIONAL, RELEASE = "routine", "intentional", "release"
TRIGGERS = (ROUTINE, INTENTIONAL, RELEASE)


@dataclass(frozen=True)
class Layer:
    layer_id: str
    family: str                 # what it proves: static | unit | api | web | mobile | ...
    cost_tier: str
    argv: Tuple[str, ...]       # () for an external layer
    cwd_marker: Optional[str]   # a path that must exist in the workspace, or None
    tool: Optional[str]         # binary that must resolve on PATH, or None
    trigger: str
    timeout_seconds: int
    external: bool = False
    description: str = ""

    def __post_init__(self):
        if self.cost_tier not in COST_TIERS:
            raise ValueError("unknown cost tier %r" % self.cost_tier)
        if self.trigger not in TRIGGERS:
            raise ValueError("unknown trigger %r" % self.trigger)
        if self.external and self.argv:
            raise ValueError("an external layer has no local argv")
        if not self.external and not self.argv:
            raise ValueError("a local layer needs an argv")

    @property
    def cost(self):
        return COST_TIERS.index(self.cost_tier)


LAYERS = {
    "flutter_analyze": Layer(
        "flutter_analyze", "static", "static",
        ("flutter", "analyze", "--no-pub", "--no-fatal-infos"),
        "pubspec.yaml", "flutter", ROUTINE, 600,
        description="The CI gate's first half (ci.yml). Sees barrel exports; "
                    "blind to path-string asset loading."),
    "flutter_unit": Layer(
        "flutter_unit", "unit", "unit",
        ("flutter", "test"),
        "pubspec.yaml", "flutter", ROUTINE, 900,
        description="Dart unit and widget tests under test/. The CI gate's "
                    "second half."),
    "api_postman": Layer(
        "api_postman", "api", "api",
        ("npm", "run", "test:api"),
        "tests/api/run.sh", "postman", ROUTINE, 600,
        description="Repository-owned Postman collection against the Supabase "
                    "REST surface, anon key only, read-only requests."),
    "playwright_e2e": Layer(
        "playwright_e2e", "web", "web_e2e",
        ("npm", "run", "test:e2e"),
        "playwright.config.ts", "npm", ROUTINE, 1500,
        description="Deterministic web E2E: builds the static bundle, signs in "
                    "once, drives one headless Chromium. Owns the browser."),
    "maestro_smoke": Layer(
        "maestro_smoke", "mobile", "mobile_e2e",
        ("npm", "run", "test:maestro"),
        "tests/maestro/config.yaml", "maestro", ROUTINE, 1500,
        description="Deterministic mobile E2E flows on the local Android "
                    "emulator (iOS simulators are behind the Xcode licence on "
                    "this machine)."),
    "k6_perf": Layer(
        "k6_perf", "performance", "performance",
        ("npm", "run", "test:perf"),
        "tests/perf/k6", "k6", INTENTIONAL, 1800,
        description="Intentional load validation. Never on the routine path."),
    "testsprite_exploratory": Layer(
        "testsprite_exploratory", "exploratory", "exploratory",
        (), None, None, INTENTIONAL, 0, external=True,
        description="Autonomous exploratory QA via the TestSprite MCP. Tester "
                    "and discovery role only; never edits Product code; never "
                    "auto-invoked."),
    "browserstack_devices": Layer(
        "browserstack_devices", "device_matrix", "device_matrix",
        (), None, None, RELEASE, 0, external=True,
        description="Real-device matrix reusing the Maestro suites. Release "
                    "stage only; deferred until credentials exist."),
}


def by_cost(layer_ids):
    """Stable ordering: cheapest first, then by id so output is reproducible."""
    return sorted(layer_ids, key=lambda lid: (LAYERS[lid].cost, lid))


def availability(which=shutil.which):
    """Which local tools resolve. A report, not a decision; secrets never appear."""
    out = {}
    for lid, layer in LAYERS.items():
        if layer.external:
            out[lid] = {"tool": None, "available": None, "external": True}
            continue
        out[lid] = {"tool": layer.tool, "available": bool(which(layer.tool)),
                    "external": False}
    return out
