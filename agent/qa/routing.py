"""Canonical test selection — the ONE place that decides which layers run.

THE PRINCIPLE: use the lowest-cost test that provides sufficient confidence.

Everything here is derived from facts the task already carries — its surfaces,
its five characteristics, its required capability and its primary target — and
from three explicit flags that only an authority sets. No seat re-implements this
table; a seat that wants a different layer changes the facts or asks for the
flag, never the routing.

WHAT "SUFFICIENT" MEANS PER CHANGE KIND

    docs only            nothing behavioural changed: no layer. That is a real
                         answer, not a gap. (config alone: the static gate, since
                         pubspec/asset changes can break a build analyze sees.)
    dart (lib/)          static + unit — always. Plus web E2E when the change is
                         user-visible at runtime or targets flutter_web; plus the
                         mobile smoke when it targets a mobile platform or touches
                         android/ ios/.
    backend (supabase/)  the API layer. Schema / money / security characteristics
                         also pull it in, whatever the paths say.
    web (web/, tests/e2e) web E2E.
    tests only           the layer that OWNS those tests, so a test change is
                         proven by running it.
    unknown / unassessed static + unit: cheap, and honest about not knowing.

INTENTIONAL AND RELEASE LAYERS are never selected from paths alone:
    performance_scope     -> k6_perf
    exploratory_requested -> testsprite_exploratory (only where the change is
                             user-visible; exploring a docs change is waste)
    release_candidate     -> browserstack_devices, plus the mobile smoke

Stdlib only. Pure: same profile in, same decision out.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple

from agent.qa.layers import INTENTIONAL, LAYERS, RELEASE, by_cost


# ----------------------------------------------------------------- inputs

@dataclass(frozen=True)
class ChangeProfile:
    required_capability: Optional[str]
    surfaces: Tuple[str, ...] = ()
    characteristics: Tuple[Tuple[str, bool], ...] = ()
    runtime: Optional[str] = None          # e.g. flutter_web, flutter_mobile
    platform: Optional[str] = None         # e.g. chrome, android, ios
    performance_scope: bool = False
    exploratory_requested: bool = False
    release_candidate: bool = False

    def characteristic(self, name):
        return bool(dict(self.characteristics).get(name))

    @classmethod
    def from_task(cls, task, **flags):
        profile = task.get("execution_profile") or {}
        context = task.get("operational_context") or {}
        target = context.get("primary_target") or {}
        chars = profile.get("characteristics") or {}
        return cls(
            required_capability=profile.get("required_capability"),
            surfaces=tuple(task.get("surfaces") or ()),
            characteristics=tuple(sorted((k, bool(v)) for k, v in chars.items())),
            runtime=target.get("runtime"),
            platform=target.get("platform"),
            **flags,
        )


# ------------------------------------------------------------ change kinds

DOCS, CONFIG, DART, WEB, BACKEND, MOBILE_NATIVE, TESTS, UNKNOWN = (
    "docs", "config", "dart", "web", "backend", "mobile_native", "tests", "unknown")

_TEST_OWNERS = (
    ("tests/e2e/", "playwright_e2e"),
    ("tests/api/", "api_postman"),
    ("tests/maestro/", "maestro_smoke"),
    ("tests/perf/", "k6_perf"),
    ("test/", "flutter_unit"),
    ("integration_test/", "flutter_unit"),
)


def _normalise(path):
    p = str(path).strip().lstrip("./")
    for marker in ("dabbler-code/", "webapp/"):
        i = p.find(marker)
        if i != -1:
            p = p[i + len(marker):]
    return p


def classify_path(path):
    p = _normalise(path)
    for prefix, _owner in _TEST_OWNERS:
        if p.startswith(prefix):
            return TESTS
    if p.startswith("docs/") or p.endswith(".md"):
        return DOCS
    if p.startswith("supabase/"):
        return BACKEND
    if p.startswith("android/") or p.startswith("ios/") or p.startswith("macos/"):
        return MOBILE_NATIVE
    if p.startswith("web/"):
        return WEB
    if p.startswith("lib/") and p.endswith(".dart"):
        return DART
    if p in ("pubspec.yaml", "pubspec.lock", "analysis_options.yaml",
             "package.json", "package-lock.json", "playwright.config.ts") \
            or p.endswith((".yaml", ".yml", ".json", ".toml", ".env.example")):
        return CONFIG
    return UNKNOWN


def classify_change(surfaces):
    """The set of change kinds a surface list implies. Empty surfaces -> unknown."""
    if not surfaces:
        return frozenset({UNKNOWN})
    return frozenset(classify_path(s) for s in surfaces)


def test_owners(surfaces):
    """Which layers OWN the test files a change touches."""
    owners = set()
    for s in surfaces:
        p = _normalise(s)
        for prefix, owner in _TEST_OWNERS:
            if p.startswith(prefix):
                owners.add(owner)
    return owners


# ---------------------------------------------------------------- decision

@dataclass(frozen=True)
class LayerSelection:
    layer_id: str
    reason: str


@dataclass(frozen=True)
class RoutingDecision:
    selected: Tuple[LayerSelection, ...]
    skipped: Tuple[Tuple[str, str], ...]
    change_kinds: Tuple[str, ...]
    basis: str
    flags: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def selected_ids(self):
        return tuple(s.layer_id for s in self.selected)

    def as_payload(self):
        return {
            "selected": [{"layer_id": s.layer_id, "reason": s.reason}
                         for s in self.selected],
            "skipped": [{"layer_id": lid, "reason": why} for lid, why in self.skipped],
            "change_kinds": list(self.change_kinds),
            "basis": self.basis,
            "flags": list(self.flags),
        }


def select_layers(profile):
    """The whole policy. Deterministic; sorted cheapest-first."""
    kinds = classify_change(profile.surfaces)
    picks = {}          # layer_id -> reason (first reason wins)
    flags = []

    def pick(lid, reason):
        picks.setdefault(lid, reason)

    behavioural = bool(kinds - {DOCS})
    if not behavioural:
        basis = "documentation-only: no behaviour changed; no test layer applies"
        return _decide(picks, kinds, basis, flags, profile)

    if kinds <= {DOCS, CONFIG}:
        pick("flutter_analyze", "config-only change: the static gate proves the build "
                                "still resolves")
        basis = "config-only: static gate, no E2E"
        return _decide(picks, kinds, basis, flags, profile)

    if UNKNOWN in kinds:
        pick("flutter_analyze", "surfaces unclassified: cheapest gate")
        pick("flutter_unit", "surfaces unclassified: unit layer as the honest floor")

    if DART in kinds:
        pick("flutter_analyze", "Dart change: the CI static gate")
        pick("flutter_unit", "Dart change: the CI unit gate")
        if profile.characteristic("user_visible_runtime") or profile.runtime == "flutter_web":
            pick("playwright_e2e", "user-visible runtime change on the web target")
        if profile.platform in ("android", "ios") or MOBILE_NATIVE in kinds:
            pick("maestro_smoke", "mobile target: the deterministic mobile smoke")

    if MOBILE_NATIVE in kinds:
        pick("maestro_smoke", "native mobile surface changed")

    if WEB in kinds:
        pick("playwright_e2e", "web surface changed")

    if BACKEND in kinds or any(profile.characteristic(c) for c in
                               ("schema_change", "money_path", "security_sensitive")):
        pick("api_postman", "backend surface or backend-risk characteristic: "
                            "the API layer")

    if TESTS in kinds:
        for owner in sorted(test_owners(profile.surfaces)):
            if LAYERS[owner].trigger == INTENTIONAL and not profile.performance_scope:
                continue        # editing a k6 script does not make a perf run routine
            pick(owner, "test files changed: run the layer that owns them")

    # Intentional and release layers: flags only, never paths.
    if profile.performance_scope:
        flags.append("performance_scope")
        pick("k6_perf", "explicit performance scope")
    if profile.exploratory_requested:
        flags.append("exploratory_requested")
        if profile.characteristic("user_visible_runtime") or DART in kinds or WEB in kinds:
            pick("testsprite_exploratory", "explicit exploratory request on a "
                                            "user-visible change")
    if profile.release_candidate:
        flags.append("release_candidate")
        pick("maestro_smoke", "release candidate: deterministic mobile regression")
        pick("browserstack_devices", "release candidate: real-device validation")

    basis = "change kinds %s -> lowest-cost sufficient layers" % ", ".join(sorted(kinds))
    return _decide(picks, kinds, basis, flags, profile)


def _decide(picks, kinds, basis, flags, profile):
    selected = tuple(LayerSelection(lid, picks[lid]) for lid in by_cost(picks))
    skipped = []
    for lid in by_cost(lid for lid in LAYERS if lid not in picks):
        layer = LAYERS[lid]
        if layer.trigger == INTENTIONAL:
            skipped.append((lid, "intentional layer: no explicit trigger"))
        elif layer.trigger == RELEASE:
            skipped.append((lid, "release-stage layer: not a release candidate"))
        else:
            skipped.append((lid, "no applicable surface for this change"))
    return RoutingDecision(selected, tuple(skipped), tuple(sorted(kinds)), basis,
                           tuple(flags))
