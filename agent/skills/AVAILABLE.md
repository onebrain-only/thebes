# Skills available on this machine, beyond the ones each role file names

**Regenerated 2026-11-02** (CEO 2026-11-02: teams were not using skills; briefs now name them).
Earlier copies of this file listed eight plugin marketplaces; `~/.claude/plugins/installed_plugins.json`
showed NONE installed on 2026-11-02, and `.claude/settings.json` still enables 29 plugins that do not exist.
Only what is below is real today.

## Project skills — `agent/skills/` (`.claude/skills` is a symlink to it) — 81

Visible to every session whose working directory is this repo, i.e. every team (their stable home is this root).
Invoke with the Skill tool by name. The ones a code brief names: `tdd`, `rtl-arabic-checklist`, `drive-the-app`;
Edfu (QA) also: `task-review`. Full list:

`agentdb-advanced`, `agentdb-learning`, `agentdb-memory-patterns`, `agentdb-optimization`, `agentdb-vector-search`, `auth-assessment`, `browser`, `capacity-to-date`, `code-review`, `codebase-design`, `cpo-advisor`, `cpo-review`, `crypto-review`, `cto-advisor`, `cto-architecture-decision-skill`, `cto-engineering-metrics-skill`, `cto-review`, `cto-risk-resilience-skill`, `cto-technology-roadmap-skill`, `diagnosing-bugs`, `domain-modeling`, `drive-the-app`, `front-door`, `git-guardrails-claude-code`, `github-code-review`, `github-multi-repo`, `github-project-management`, `github-release-management`, `github-workflow-automation`, `grill-me`, `grill-peer`, `grill-po`, `grill-with-docs`, `grilling`, `hooks-automation`, `implement`, `improve-codebase-architecture`, `loop-me`, `masvs-checklist`, `mobile-threat-model`, `money-write-invariants`, `network-security-check`, `pair-programming`, `privacy-audit`, `project-audit`, `reasoningbank-agentdb`, `reasoningbank-intelligence`, `research`, `resolving-merge-conflicts`, `route-to-seat`, `rtl-arabic-checklist`, `runbook-authoring`, `secure-mobile-dev-guide`, `secure-storage-audit`, `skill-builder`, `sparc-methodology`, `store-release`, `stream-chain`, `supabase`, `supabase-postgres-best-practices`, `swarm-advanced`, `swarm-orchestration`, `task-readiness`, `task-review`, `tdd`, `teach`, `to-spec`, `to-tickets`, `ui-ux-pro-max`, `v3-cli-modernization`, `v3-core-implementation`, `v3-ddd-architecture`, `v3-integration-deep`, `v3-mcp-optimization`, `v3-memory-unification`, `v3-performance-optimization`, `v3-security-overhaul`, `v3-swarm-coordination`, `verification-quality`, `wait-what`, `writing-for-agents`

## Installed plugins

### `dart-flutter@dart-flutter` v1.0.7 — 25 skills

Installed 2026-11-02, scope user, from `/Users/moataz/.claude/plugins/cache/dart-flutter/dart-flutter/1.0.7`.

| skill | does |
|---|---|
| `dart-add-unit-test` | Write and organize unit tests for functions, methods, and classes using `package:test`. Use when creating new  |
| `dart-build-cli-app` | >- |
| `dart-collect-coverage` | Collect coverage using the coverage packge and create an LCOV report |
| `dart-fix-runtime-errors` | Uses get_runtime_errors and lsp to fetch an active stack trace, locate the failing line, apply a fix, and veri |
| `dart-generate-test-mocks` | Define and generate mock objects for external dependencies using `package:mockito` and `build_runner`. Use whe |
| `dart-migrate-to-checks-package` | |- |
| `dart-resolve-package-conflicts` | Workflow for fixing package version conflicts. Use this when `pub get` fails due to incompatible package versi |
| `dart-run-static-analysis` | Execute `dart analyze` to identify warnings and errors, and use `dart fix --apply` to automatically resolve me |
| `dart-setup-ffi-assets` | "Guides agents in compiling and packaging C/C++ source code into dynamic or static libraries (Code Assets) usi |
| `dart-use-doc-examples` | "How to inject external code examples into Dartdoc using the {@example} directive, and how to filter those fil |
| `dart-use-ffigen` | Guide agents to use `package:ffigen` to automatically generate FFI bindings instead of writing them manually.  |
| `dart-use-path-package` | >- |
| `dart-use-pattern-matching` | >- |
| `dart-use-primary-constructors` | > |
| `dart-write-documentation` | "Rules and formatting guidelines for writing Dart /// API documentation and doc comments. Use when documenting |
| `flutter-add-integration-test` | Configures Flutter Driver for app interaction and converts MCP actions into permanent integration tests. Use w |
| `flutter-add-widget-preview` | Adds interactive widget previews to the project using the previews.dart system. Use when creating new UI compo |
| `flutter-add-widget-test` | Implement a component-level test using `WidgetTester` to verify UI rendering and user interactions (tapping, s |
| `flutter-apply-architecture-best-practices` | Architects a Flutter application using the recommended layered approach (UI, Logic, Data). Use when structurin |
| `flutter-build-responsive-layout` | Use `LayoutBuilder`, `MediaQuery`, or `Expanded/Flexible` to create a layout that adapts to different screen s |
| `flutter-fix-layout-issues` | Fixes Flutter layout errors (overflows, unbounded constraints) using Dart and Flutter MCP tools. Use when addr |
| `flutter-implement-json-serialization` | Create model classes with `fromJson` and `toJson` methods using `dart:convert`. Use when manually mapping JSON |
| `flutter-setup-declarative-routing` | Configure `MaterialApp.router` using a package like `go_router` for advanced URL-based navigation. Use when de |
| `flutter-setup-localization` | Add `flutter_localizations` and `intl` dependencies, enable "generate true" in `pubspec.yaml`, and create an ` |
| `flutter-use-http-package` | Use the `http` package to execute GET, POST, PUT, or DELETE requests. Use when you need to fetch from or send  |

## Enabled in `.claude/settings.json` but NOT installed

`everything-claude-code`, the 20 `pm-skills` entries and the 7 `wondelai-skills` entries. Role files that cite
`systems-architecture` or `code-craftsmanship` cite skills that are not on this machine; nothing resolves them.

## Not plugins, but part of the QA toolchain

- Playwright `@playwright/test` 1.63 + chromium: installed at `Dabbler/dabbler-code` root (`npm run test:e2e`).
- Maestro (mobile.dev): NOT installed; `tests/maestro/run.sh` exits 2 (infrastructure) until it is.
- `dart mcp-server`: works (dart-flutter plugin starts it as `dart-mcp-server`).
