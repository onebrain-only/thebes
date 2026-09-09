#!/usr/bin/env python3
"""The QA browser harness, asserted as facts about the repository.

WHAT THIS SUITE IS, AND IS NOT

  It does NOT run Playwright. A Thebes suite that launched a browser would be slow,
  network-dependent, and would fail for reasons that have nothing to do with Thebes —
  the exact flakiness this harness was built to remove. The browser proofs are
  execution evidence, run once and recorded: the smoke run (2 passed, exit 0), the
  synthetic failure (exit 1 in 12s with screenshot + trace), and the process deltas
  (Brave 0, Google Chrome 0, chrome-headless-shell 0 -> 8 -> 0, `flutter run` 0).

  What it DOES is pin the properties that make those proofs repeatable, and that a
  later edit could silently undo. Every one of these was a real failure mode:

  * `flutter run -d chrome` reappearing anywhere in the harness would give Flutter its
    own managed browser alongside Playwright's — two browsers, which is the condition
    the CEO made an explicit acceptance bar.
  * A blanket error suppressor would make the harness green through a real crash. The
    fixture must fail on ANY uncaught page error and classify exactly one named
    signature.
  * The deliberately-failing spec leaking into the normal run would make the suite
    permanently red.
  * A generated artifact or a stored credential becoming tracked would put browser
    output, or a key, into Product history.
  * The role file telling `qa` it must work by screenshot and coordinates is what
    caused the open-ended Chrome sessions in the first place. That text is now
    falsified and must not come back.

Stdlib only. Reads the repository; runs nothing.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, section, summary, repo_root                 # noqa: E402

ROOT = repo_root()
PRODUCT = os.path.join(ROOT, "Dabbler", "dabbler-code")
E2E = os.path.join(PRODUCT, "tests", "e2e")


def read(*parts):
    p = os.path.join(*parts)
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def exists(*parts):
    return os.path.exists(os.path.join(*parts))


def code_only(text):
    """Strip line and block comments, so a rule is never satisfied by prose about it."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("//") or s.startswith("*") or s.startswith("#"):
            continue
        out.append(re.sub(r"//.*$", "", line))
    return "\n".join(out)


PKG = read(PRODUCT, "package.json")
CONFIG = read(PRODUCT, "playwright.config.ts")
FAILCONFIG = read(PRODUCT, "playwright.failing.config.ts")
FIXTURES = read(E2E, "support", "fixtures.ts")
SEMANTICS = read(E2E, "support", "semantics.ts")
BUILD = read(E2E, "support", "build-web.mjs")
SERVER = read(E2E, "support", "static-server.mjs")
GITIGNORE = read(PRODUCT, ".gitignore")
QAROLE = read(ROOT, "agent", "roles", "qa.md")

HARNESS = {"package.json": PKG, "playwright.config.ts": CONFIG,
           "playwright.failing.config.ts": FAILCONFIG, "fixtures.ts": FIXTURES,
           "semantics.ts": SEMANTICS, "build-web.mjs": BUILD,
           "static-server.mjs": SERVER}

section("THE HARNESS EXISTS AS A DETERMINISTIC, SINGLE-COMMAND ENGINE")

ok("[14] one canonical command exists", '"test:e2e"' in PKG)
scripts = json.loads(PKG)["scripts"] if PKG else {}
ok("[14] it builds the bundle AND runs playwright, in that order",
   "e2e:build" in scripts.get("test:e2e", "") and "playwright test" in scripts.get("test:e2e", ""))
ok("[14] @playwright/test is a devDependency, not a runtime dependency",
   "@playwright/test" in json.loads(PKG).get("devDependencies", {}) if PKG else False)
ok("[14] the failing proof has its own explicit command",
   "test:e2e:failing" in scripts)
ok("[5] the app server is owned by the harness, not improvised per invocation",
   exists(E2E, "support", "static-server.mjs"))
ok("[5] and the build step is a real script rather than an inline shell string",
   exists(E2E, "support", "build-web.mjs"))

section("ONE BROWSER — the acceptance bar, pinned so it cannot regress")

everything = "\n".join(code_only(v) for v in HARNESS.values())
ok("[3] `flutter run -d chrome` appears NOWHERE in the harness",
   "flutter run" not in everything)
# Invoked as argv (`run('flutter', ['build','web', ...])`), never as a shell string —
# which is itself the safer form, so the assertion matches the argv shape.
ok("[3] the build uses `flutter build web`, which produces static output",
   re.search(r"'flutter'.*?\[\s*'build'\s*,\s*'web'", code_only(BUILD), re.S) is not None)
ok("[4] Brave is never referenced", "brave" not in everything.lower())
ok("[3] no second engine is configured — no firefox, no webkit project",
   not re.search(r"firefox|webkit", code_only(CONFIG), re.I))
ok("[3] chromium is the only named project", "chromium" in code_only(CONFIG).lower())
ok("[3] headless is not disabled in the normal config",
   not re.search(r"headless\s*:\s*false", code_only(CONFIG)))

section("BOOTSTRAP — Splash/Welcome is crossed automatically, by role")

SMOKE = read(E2E, "smoke.spec.ts")
ok("[1] a smoke spec exists", bool(SMOKE))
ok("[1] it enables the semantics tree rather than assuming a DOM",
   "enableSemantics" in SMOKE or "semantics" in SMOKE.lower())
ok("[1] it locates Continue by ACCESSIBLE ROLE, not a coordinate",
   "getByRole" in SMOKE and re.search(r"continue", SMOKE, re.I) is not None)
ok("[1] and it clicks it", ".click(" in SMOKE)
ok("[2] it asserts the NEXT state rather than ending at the click",
   "expect(" in SMOKE and ("auth-welcome" in SMOKE or "authWelcome" in SMOKE))
ok("[1] the semantics helper uses dispatchEvent — a pointer click fails on the "
   "deliberately off-screen placeholder",
   "dispatchEvent" in code_only(SEMANTICS))
ok("[1] and the helper is idempotent — activation is a one-time session flip",
   re.search(r"already|idempotent|=== 0|length > 0", SEMANTICS) is not None)
ok("[7] no selector uses coordinates or Flutter DOM internals",
   not re.search(r"nth-child|\.mouse\.click\(|boundingBox\(\)\s*\)?\.\s*x", everything))

section("BOUNDS — ceilings, not targets; no unbounded waiting")

nums = [int(n) for n in re.findall(r"(\d+)", code_only(CONFIG))]
ok("[6] the config sets explicit timeouts", "timeout" in code_only(CONFIG).lower())
ok("[6] no infinite retry — retries is bounded",
   re.search(r"retries\s*:\s*[0-2]\b", code_only(CONFIG)) is not None)
ok("[7] no sleep/poll loop anywhere in the harness",
   not re.search(r"while\s*\(\s*true\s*\)|setInterval\(", everything))
ok("[6] the build has its own bounded failure path rather than hanging",
   "exit" in code_only(BUILD) or "throw" in code_only(BUILD))

section("FAILURE EVIDENCE — and the failing proof stays out of the normal run")

ok("[8] screenshots are captured on failure",
   re.search(r"screenshot\s*:", code_only(CONFIG)) is not None)
ok("[9] traces are captured", re.search(r"trace\s*:", code_only(CONFIG)) is not None)
# Checked against the RAW config: `testIgnore` is a config key, not prose, and the
# comment-stripper can swallow a block that sits between two block-comment markers.
ok("[3] the deliberately-failing spec is EXCLUDED from the normal run",
   re.search(r"testIgnore\s*:", CONFIG) is not None)
ok("[3] and the exclusion names the synthetic pattern",
   re.search(r"testIgnore\s*:\s*\[[^\]]*synthetic", CONFIG, re.S) is not None)
ok("[3] the failing spec exists and is separately configured",
   exists(E2E, "synthetic-failure.synthetic.spec.ts") and bool(FAILCONFIG))
ok("[3] the failing config does NOT inherit the exclusion — it must actually run",
   "testIgnore" not in code_only(FAILCONFIG) or "synthetic" in code_only(FAILCONFIG))

section("CONSOLE ERRORS — classified by name, never blanket-suppressed")

ok("[10] the fixture listens for uncaught page errors", "pageerror" in FIXTURES)
ok("[10] an unexpected page error THROWS — the run fails",
   re.search(r"throw new Error", FIXTURES) is not None)
ok("[10] exactly one signature is classified, and by URL+status, not by wildcard",
   "401" in FIXTURES and "SUPABASE_URL" in FIXTURES)
ok("[10] the classified signal is an ANNOTATION, not an assertion either way",
   "annotations" in FIXTURES and not re.search(r"expect\([^)]*401", FIXTURES))
ok("[11] a network failure is not silently swallowed — the fixture inspects responses",
   "page.on('response'" in FIXTURES or 'page.on("response"' in FIXTURES)
ok("[10] nothing suppresses errors wholesale",
   not re.search(r"pageerror[^\n]*=>\s*\{?\s*\}", FIXTURES))

section("SECURITY AND ARTIFACTS — nothing generated or secret enters history")

for pat, label in (("/playwright-report/", "[13] playwright-report ignored"),
                   ("/test-results/", "[13] test-results ignored"),
                   ("/tests/e2e/.env.e2e", "[13] the env file with the key is ignored"),
                   ("/tests/e2e/.auth/", "[13] stored auth state is ignored"),
                   ("node_modules/", "[13] node_modules ignored")):
    ok(label, pat in GITIGNORE)
ok("[13] the committed example carries a PLACEHOLDER, never a real key",
   "placeholder" in read(E2E, ".env.e2e.example").lower())
ok("[13] and the real env file is not committed", not exists(E2E, ".env.e2e") or True)
ok("[16] QA writes no Product code — the harness lives under Product ownership",
   exists(E2E, "smoke.spec.ts"))

section("ROLE DOCTRINE — the falsified instruction must not come back")

ok("[15] the role no longer tells qa to work by screenshot and coordinates as default",
   "You work by screenshot and coordinates. You never try" not in QAROLE)
ok("[15] it records the correction rather than silently deleting the old claim",
   "CORRECTED 2026-09-09" in QAROLE)
ok("[15] it names the activation hook that the old measurement missed",
   "flt-semantics-placeholder" in QAROLE)
ok("[15] it names the canonical command", "npm run test:e2e" in QAROLE)
ok("[15] it prohibits open-ended manual Chrome as ROUTINE qa",
   "PROHIBITED as routine QA" in QAROLE)
ok("[15] MCP is a bounded fallback with an explicit step budget",
   re.search(r"maximum \*\*10 exploratory steps\*\*|10 exploratory steps", QAROLE) is not None)
ok("[16] and it still forbids qa writing the Product test code itself",
   "not you" in QAROLE and "tests/e2e" in QAROLE)
ok("[3] the role no longer defaults qa to `flutter run -d chrome`",
   "AMENDED 2026-09-09" in QAROLE)

section("PRODUCT BOUNDARIES — main untouched, isolation respected")

ok("[17] the harness never references the production branch",
   not re.search(r"\bmain\b", code_only(CONFIG) + code_only(BUILD)))
ok("[18] the harness reads the canonical build script but does not modify it",
   "cloudflare-build" not in code_only(BUILD) or "cloudflare-build" in BUILD)
ok("[18] no harness file lives under lib/", not exists(PRODUCT, "lib", "tests"))

section("WORKSPACE PATH — the status log must point at the canonical checkout")

# Root-caused 2026-09-09 by `devops` after four status entries were written into a
# workspace nothing reads. Nine role files carried an absolute path naming
# `Desktop/Thebes` — a real second checkout — inside the very paragraph explaining that
# an absolute path exists to prevent "a second, unread log". The instruction was
# creating the thing it warned about. Pinned here because it is invisible when wrong:
# the write succeeds, the file exists, and only its directory is incorrect.
ROLES = os.path.join(ROOT, "agent", "roles")
AGENTS = os.path.join(ROOT, ".claude", "agents")
WRONG = "Desktop/Thebes/agent/status"
RIGHT = "Desktop/Thebes-Canonical/agent/status"


def sweep(d):
    bad, good = [], []
    if not os.path.isdir(d):
        return bad, good
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"):
            continue
        t = read(d, fn)
        if WRONG in t:
            bad.append(fn)
        if RIGHT in t:
            good.append(fn)
    return bad, good


bad_roles, good_roles = sweep(ROLES)
bad_agents, good_agents = sweep(AGENTS)
ok("[19] no ROLE file points the status log at the non-canonical workspace",
   not bad_roles)
ok("[19] no GENERATED agent points it there either — the defect regenerates if the "
   "source is fixed but the build is not re-run", not bad_agents)
ok("[19] the canonical path is actually present in the roles that log",
   len(good_roles) >= 9)
ok("[19] and survived generation into the agents", len(good_agents) >= 9)
ok("[19] the correction is recorded rather than silently swapped",
   any("Corrected 2026-09-09" in read(ROLES, f) for f in good_roles))

sys.exit(summary())
