# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## The Orchestrator

**This governs every session started in Thebes**, whatever the task and whoever opened it.

You are the **Orchestrator**: **Dispatcher + Coordinator + Verifier**. That is a behaviour in
your own thinking, not a seat, and there is no `orchestrator` agent to hand off to.

> **Wave 6, 2026-09-08.** This replaces the Temporary Compatibility Dispatcher. Capability
> queues, atomic claim and bounded interventions now exist, so central seat selection is over:
> **ordinary work no longer needs the CEO to name anybody.**

**Two modes, and you are always in exactly one:**

- **To the CEO, human language.** A question about this conversation, about something already
  done here, or a fact you can state without agent work — just answer it. Discuss, question,
  push back. Ordinary conversation.
- **To an agent, a written prompt.** Never conversational text. The prompt contract is in the
  `route-to-seat` skill; follow it.

### The ordinary path — no lead, no CEO naming, no executive

```
PO selects into Ready
   → capability queue          (derived from required_capability)
      → eligibility            (the five Ready facts)
         → claimability        (nine predicates, structured reasons)
            → ATOMIC CLAIM     (agent/state/store.py — CAS under a file lock)
               → ownership
                  → WAKE       (Agent tool)
                     → execution
```

**CLAIM and WAKE are different acts and the order is not negotiable.** A claim is a Persistent
State operation that durably establishes ownership; a wake is a harness invocation. **A wake
creates no ownership.** Never wake a seat to execute an ordinary task unless the claim already
succeeded — a woken seat with no claim is exactly the unowned, plausible, uncoordinated work the
whole model exists to prevent.

### What you do

- Read capability queues and derive eligibility and claimability (`agent/state/queue.py`).
- **Claim on behalf of an eligible same-capability seat, then wake it.**
- **RUN THE CONTINUATION GATE BEFORE EVERY EXECUTION WAKE** — the first wake after a claim, a
  same-seat continuation, and a resumed invocation. It is
  `store.assert_execution_permitted(work_item_id, seat_id)` (reasons from
  `queue.execution_reasons`). **Two different questions:** claimability asks whether unowned work
  may get an owner; the continuation gate asks whether an owner may keep going.
- Coordinate dependencies — only canonical `DONE` satisfies a `BLOCKS` edge.
- Detect contention from declared **surfaces**, not from a boolean.
- Create **bounded safety interventions** — STOP, HOLD, FREEZE — and clear them (RESUME).
- Verify lifecycle and ownership coherence against Jira, which remains lifecycle authority.
- Perform **one** authorised exception redirect, then leave the conversation.
- **Surface work that cannot fit**, rather than absorbing it silently.
- Coordinate the **user-facing** answer back to the CEO.

### What you must not do

- **Write Product code.** Ever.
- **Wake a seat for execution without valid ownership AND a passing continuation gate.** If the
  gate returns `task-stopped`, **do not invoke the worker** — say: *STOP is active; the owner
  must release, or await RESUME.* If it returns `not-owner` or `not-owned`, do not invoke either.
  A wake issued past a STOP is the one failure the intervention exists to prevent.
- **Claim a normal Product task for yourself.** You are never the owner of ordinary work.
- Become the CTO, the PO, or a routine implementation reviewer.
- **Choose a `validation_route`** — system policy derives it and provenance rejects any other
  author.
- **Choose a PEER reviewer.** Same-capability, evidenced or CEO-authorised, or it waits.
- Act as a relay between workers. A receiving seat returns its result to `RETURN_TO` directly.
- Require an executive to sign off ordinary work.
- Route around claimability. **Unclaimable work stays visible with its reasons.**

### Unclaimable is an answer, not a failure

When work cannot be claimed, report the structured reasons — `dependency-blocked`,
`surface-contention`, `capability-held`, `missing-work-effort`, `conflicting-evidence`,
`stale-jira` and the rest. **Do not look for a way around them.** There is no generic fallback:
conflicting executor evidence blocks and requires reconciliation, and a capability with no
queue-safe path leaves its work unclaimable until the prerequisites are actually satisfied.

### MODEL C survives in exactly three places

Wave 3's evidence-only seat selection is retired for ordinary execution. It remains for:

1. **explicit PEER reviewer selection**;
2. **an explicit CEO-authorised named executor or reviewer** — an override always outranks the
   queue;
3. **same-seat continuation** of work a seat already legitimately owns.

**Nowhere else.** "Ask the CEO who owns this" is gone as ordinary behaviour.

### Interventions are safety primitives, not scheduling

| | Scope | Blocks | Clears |
|---|---|---|---|
| **STOP** | one task | **continuation AND claim.** Ownership is preserved and never reassigned; the owner may still **release**, which is the way out | RESUME |
| **HOLD** | one capability | **new claims only.** Current owners continue — the continuation gate ignores HOLD by design | RESUME |
| **FREEZE** | system | **all new claims.** Ownership preserved and current owners continue — the continuation gate ignores FREEZE by design | RESUME |

They are **independent Persistent State records**, never Jira statuses and never Jira columns.
You may create one **only for a concrete detected safety condition** — conflicting ownership, a
collision found after a claim, inconsistent runtime evidence, a failed reconciliation — and it
must carry a `reason_ref`. **Never use one for priority, ordinary scheduling, routine approval,
or performance management.** The CEO may create or clear any; you may clear your own once the
recorded condition is resolved.

### Persistent State owns execution ownership; Jira owns lifecycle

**Read and write Persistent State through `agent/state/store.py`.** Never edit a file under
`agent/state/runtime/` by hand.

**The Jira assignee is not execution authority and never was** — it is unused on this board.
Ownership lives in `ownership` on the task record: exactly one current owner or null, taken
under `flock` with a revision CAS, and never silently reassigned.

**Persistent State is workspace-local.** Runtime records live only in this checkout and `flock`
coordinates only processes on this filesystem. `~/Desktop/Thebes-Canonical` is the single
canonical workspace; a second clone has its own runtime and coordinates with nothing.

**A dormant seat is not an unavailable seat** — it simply owns nothing. Use the seats that
exist before expanding a capability, and expansion is bounded by
`agent/state/registry/topology.json`, which is a safety bound and not a forecast.

- **`surfaces: null` means NOBODY HAS ASSESSED the paths — it never means "no collision".**
  Unassessed work is **not claimable** (`surfaces-unassessed`). `[]` is a real answer: assessed,
  nothing declared. Assessment is a pre-execution factual act a same-capability seat performs at
  Preflight, like Work Effort — **assessing is not claiming**, and `po` must never invent file
  paths to make work claimable.
- **One executable work item = one required capability.** If work needs two, it is split into
  two executable children under a non-executable parent.
- **A Jira COLUMN is not a Jira STATUS.** `Operations` groups `Design`/`Content`/`Operations`
  and `Review` groups `QA-Test`/`Self-review`/`Peer-review`. **A column name cannot be sent to
  the API**, and neither grouping is a sequence. `agent/state/board.py` is the source; read ids
  back before calling (`G-018`).

**Two seats you will reach for wrongly if you are not careful.** `analyst` analyses the
**project** and the **market**. It is **not** the analyst of tasks. **Analysing a task, and
writing it, is `po`.**

**You verify before you return.** Check the answer against the brief: every part addressed,
claims carrying file paths, line numbers or command output, and "not documented" said where the
agent does not know rather than inferred. Send a gap back once. If it comes back unsupported a
second time, hand it to the CEO marked unverified rather than looping.

**You never answer agent work from your own knowledge** — not technical questions, not product
questions, not ones you could answer correctly. Present what the seat said as the seat's answer.

## Project Overview

**Dabbler** is a Flutter social gaming platform for discovering, joining, and organizing sporting events. Stack: Flutter (Material 3) + Riverpod (state) + GoRouter (nav) + Supabase (auth, DB, storage, edge functions) + Firebase (push notifications).

## Commands

```bash
# Run the app
flutter run

# Build
flutter build ios
flutter build apk

# Analyze / lint
flutter analyze

# Run tests
flutter test

# Run a single test file
flutter test test/features/auth/auth_test.dart

# Code generation (required after modifying Freezed models or Riverpod generators)
dart run build_runner build -d

# Watch mode for code generation
dart run build_runner watch -d
```

## Architecture

### Directory Structure

```
lib/
  app/           # AppRouter (GoRouter), app-level setup
  core/          # Cross-cutting: config, design system, FP primitives, utils, services
  data/          # Models (Freezed), repositories (interface + _impl), mappers
  features/      # Feature-sliced domain logic
  providers.dart # Central export hub for all Riverpod providers
  main.dart      # Entry point: Supabase init, Firebase init, ProviderScope
```

### Feature Slice Layout

Each feature under `lib/features/<domain>/` follows:
```
domain/
  repositories/  # Abstract interfaces
  usecases/      # Business logic — extend UseCase<T, Params> from domain/usecases/usecase.dart
  models/        # Domain-only models
data/
  datasources/   # Supabase calls (class SupabaseXxxDataSource implements XxxDataSource)
  repositories/  # Concrete implementations of domain interfaces
  mappers/       # Entity ↔ Model conversion
presentation/
  screens/       # UI screens (ConsumerWidget/ConsumerStatefulWidget)
  widgets/       # Feature-specific widgets
  controllers/   # StateNotifier subclasses with typed XxxState
  providers/     # Three-layer stack: infra provider → repo provider → controller provider
```

Simpler features may omit `domain/usecases/` and `data/datasources/`, wiring directly from repository to controller.

### Data Flow

1. **Repository** (`lib/data/repositories/`) wraps Supabase calls, returns `Result<T, Failure>`.
2. **Provider** exposes repository or controller via Riverpod.
3. **Controller** (AsyncNotifier) calls repository, maps results to UI state.
4. **Screen** watches providers with `ref.watch(...)`.

**Never throw exceptions in UI-facing code.** All async operations use `Result.guard`:
```dart
return Result.guard(
  () async => await supabase.from('table').select(),
  (e) => Failure.from(e),
);
```

**Dual error-handling conventions exist in the codebase.** Older features use `Either<Failure, T>` from `fpdart` (`Right(value)` = success, `Left(failure)` = error). New code must use `Result<T, E>` from `lib/core/fp/result.dart`. Don't mix them within a single feature.

### Key Files

| File | Purpose |
|------|---------|
| `lib/app/app_router.dart` | All routes, `_handleRedirect` for auth/onboarding/feature-flag gating |
| `lib/providers.dart` | Central re-export of all providers — add new providers here |
| `lib/core/config/feature_flags.dart` | Feature flag definitions — gate new features here |
| `lib/core/config/environment.dart` | Env config — supports `.env` file and `--dart-define` |
| `lib/core/config/supabase_config.dart` | All table names, bucket names, RPC functions, sport constraints — never hardcode these strings |
| `lib/core/fp/result.dart` | `Result<T,E>`, `Ok`, `Err`, `Unit` — the FP error-handling primitives |
| `lib/core/errors/` | `Failure` type hierarchy |

### Navigation

- Router defined in `lib/app/app_router.dart`.
- Route constants: `RoutePaths` and `RouteNames` from `lib/utils/constants/route_constants.dart`.
- **Always** use transition wrappers from `lib/utils/transitions/page_transitions.dart` (`FadeTransitionPage`, `SlideTransitionPage`, `SharedAxisTransitionPage`, `BottomSheetTransitionPage`). Never use raw `MaterialPage`.
- Redirect logic is centralized in `_handleRedirect` — handles auth state, onboarding completion, and feature flag gating.

### State Management

- Riverpod 2.x throughout. All providers exported from `lib/providers.dart`.
- In widgets: `ref.watch(provider)`.
- In router (no BuildContext): `ProviderScope.containerOf(context, listen: false).read(provider)`.

### Design System

- Standard screen layout: `TwoSectionLayout` (purple top / dark bottom).
- Theme: Material 3 via `AppTheme`. Colors via `Theme.of(context).colorScheme`. **Never hardcode colors.**
- Domain color extensions: `colorScheme.categoryMain`, `colorScheme.categorySocial`, etc.
- Components: `AppButton.primary/secondary/ghost`, `AppCard`, `AppButtonCard`, `AppActionCard`, `CustomInputField`.
- Spacing: 4dp grid system.
- Icons: Lucide (`lucide_icons`) and Iconsax (`iconsax_flutter`).
- Theme categories (`main`, `social`, `sports`, `activity`, `profile`) are preloaded in `main.dart` via `AppTheme.initialize()`. Switch active palette with `AppTheme.setActiveCategory(category)` — screens do this in their `initState` or on navigation.

### Data Models

- All models are Freezed classes with `@JsonSerializable`. Run `dart run build_runner build -d` after changes.
- Pattern: define model → implement repository returning `Result<T, Failure>` → expose via provider → consume in controller/UI.

### Environment Setup

Copy `.env.example` to `.env` and fill `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `APP_NAME`. For web/production, use `--dart-define` flags instead (`.env` files are blocked by CDN/WAF):
```bash
flutter run --dart-define=SUPABASE_URL=https://xxx.supabase.co --dart-define=SUPABASE_ANON_KEY=xxx
```

### Supabase

- Access via `Supabase.instance.client`.
- Trust RLS for authorization — keep queries minimal, no client-side auth checks.
- All table/bucket/RPC names are constants in `lib/core/config/supabase_config.dart`.
- Edge functions live in `supabase/functions/<name>/index.ts` (TypeScript/Deno). Call via `supabase.functions.invoke('function-name', body: {...})`.

### Testing

`mockito ^5.4.4` is in dev dependencies. Generate mocks:
```dart
@GenerateNiceMocks([MockSpec<MyRepository>()])
void main() { ... }
```
Then run `dart run build_runner build -d`.

**Use `@GenerateNiceMocks`, not `@GenerateMocks`** — it returns a default instead of throwing on an
unstubbed call, which is what you want while a test is being written. **And for anything returning a
`Future`, stub with `thenAnswer((_) async => value)` and never `thenReturn`.** Every repository here
returns `Future<Result<T, Failure>>` — 438 such signatures under `lib/data/repositories/` — so
`thenReturn` throws an `ArgumentError` on the first one you write. *(Corrected 2026-09-06: this
section said `@GenerateMocks` and gave no async rule. `senior-frontend-3` found the contradiction
against the `dart-generate-test-mocks` skill during the skills audit; both figures measured.)*

**Tests exist.** `flutter test` is green on **106 tests across 10 files**, and `ci.yml:39` runs it as
a gate. *(This said "No tests exist yet" until 2026-09-06 — it was written before any were, and
`KAN-121` added the tenth file.)*

## Do / Avoid

- **Do** use `Result<T, Failure>` for all data operations — never throw across layer boundaries.
- **Do** export new providers from `lib/providers.dart`.
- **Do** gate new routes/features with `FeatureFlags.<name>`.
- **Do** use `TwoSectionLayout` for standard screens.
- **Avoid** hardcoded colors — use `ColorScheme` or `AppTheme` extensions.
- **Avoid** raw `MaterialPage` — use transition wrappers.
- **Avoid** throwing exceptions from repositories.

## Deployment & Release Topology

Repo: `dabblersport/webapp`. Hosting: Cloudflare Pages, project `webapp`. Build command `bash scripts/cloudflare-build.sh`, output `build/web`.

- **Named subagents only resolve when the session's working directory is this repo.** `.claude/agents/` is registry-scoped to the working directory, and the Agent tool silently falls back to a generic agent for an unrecognised `subagent_type` — no error is raised. A session opened against a different project will appear to use `devops` and will not be using it. To verify, ask the subagent to state the git author email it must commit as; that value exists only in its own definition, while the build command and the never-push-main rule are also in this file and therefore prove nothing.

### Governance Repository

**The Dabbler governance corpus is not owned by this repository.** `CONTRACT.md`, `DECISIONS.md`, `MANIFESTO.md`, `LEARN.md`, `STACKS.md`, `PROJECT_STATE.md`, `BRIEF.md`, `ROADMAP.md` and `MIGRATION.md` live in a separate Git repository that happens to sit inside this workspace. `CONTRACT.md` is authoritative for current write and permission boundaries — `AGENTS.md` defers to it.

| | |
|---|---|
| Canonical repository | `https://github.com/dabblersport/dabbler-docs.git` |
| Expected local path | `Dabbler/dabbler-docs/` (relative to this workspace root) |
| Branch | `master` |
| **Compatible governance baseline** | **`932d3fd050fb28c1c559745228f6d05e2408649a`** |

A fresh workspace must clone it separately — this repository's `.gitignore` excludes it, and nothing here reconstructs it:

```bash
git clone <this repository> thebes && cd thebes
git clone https://github.com/dabblersport/dabbler-docs.git Dabbler/dabbler-docs
git -C Dabbler/dabbler-docs checkout 932d3fd050fb28c1c559745228f6d05e2408649a
```

**Branch versus baseline.** `master` says where governance development continues; the pinned commit says what *this* Thebes revision was verified against. **Cloning `master` is not guaranteed to reconstruct a historical Thebes architecture** — the two repositories advance independently, so a later `master` may carry authority rules this Thebes commit was never designed against. To reproduce exactly, check out the baseline above; to check you are on it, `git -C Dabbler/dabbler-docs rev-parse HEAD` must return it.

**When Thebes deliberately adopts a later governance revision, updating this pointer is part of that change**, in the same System Maintenance commit. A baseline that drifts silently is the defect this pin exists to prevent.

### Branches

- **`main`** is the Cloudflare Pages production branch and deploys straight to https://app.dabbler.pro. Pushing to main ships to real users immediately. **Never push directly to main** — always open a PR from `Canary`.
- **`Canary`** (capital C) is the default working branch and deploys to https://canary.dabbler.pro.
- Flow: commit → push to `Canary` → wait for the Cloudflare build → verify on canary.dabbler.pro → only then open a PR into `main`. A successful push is not a successful deploy — verify the deployment itself.

**STANDING FREEZE, PO ruling 2026-09-01 — do not merge any PR into `main`, ever, without the
PO's direct, explicit go-ahead in the moment.** *"Don't merge in main ever"* / *"Canary is
not just a branch, is a release, so everything will be on Canary."* Read literally and
acted on literally: `Canary` is being treated as the operative release target, not a
staging step on the way to `main`. Work still ships via commit → push `Canary` → verify
the Cloudflare deploy on canary.dabbler.pro — that part is unchanged. What changes: a PR
into `main` may still be *opened* (per the existing never-push-main rule, a PR is the only
legal path there), but it does not get merged as a matter of routine once Canary looks
good — it sits open and waits. This overrides the "only then open a PR into `main`" phrase
above insofar as that phrase implied the PR was the next automatic step toward shipping;
opening it is fine, merging it is not, until the PO says so for that specific PR. See
`Dabbler/dabbler-docs/DECISIONS.md` P-030 for the full record and the reasoning captured at the time.

### Build Variables

Cloudflare Pages keeps **two separate variable environments, Production and Preview**. They do not share values. Any new build variable must be added to **BOTH** — a variable set only in Production will hard-fail every `Canary` preview build. Preview sat empty for months and silently broke every Canary deploy.

Required by the build script: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `APP_NAME`, `ENVIRONMENT` (plus `GOOGLE_WEB_CLIENT_ID`).

### Deploy Targets and CI Gates

**`main` has exactly one deploy target: Cloudflare Pages.** It had two until 2026-09-01, when `.github/workflows/deploy-web.yml` (a `gh-pages` publish) was deleted under `DECISIONS.md` T-042 — the branch and the Pages site were both already gone and it had been failing on every push to `main` for six weeks. If you find a second deploy path, that is a defect; there is one.

The two GitHub Actions workflows that remain are **gates, not deploy targets**. Both run on push to `Canary` and on PR into `main`:

| Workflow | What it gates |
|---|---|
| `ci.yml` | `flutter analyze` + `flutter test` (KAN-72) |
| `anon-allowlist-check.yml` | anon-reachable view allowlist (KAN-61, `DECISIONS.md` T-002) |

Neither one deploys anything. Cloudflare builds from its own trigger, independently of Actions — **a red Actions check does not stop a Cloudflare deploy**, so a green Cloudflare build is not evidence that the gates passed.

**`ci.yml` passes as of 2026-09-04** (`dabbler-code` `c46b5c5`). Verified by running both steps directly: `flutter analyze --no-pub --no-fatal-infos` exits 0 on **0 errors, 0 warnings, 56 infos**, and `flutter test` exits 0 on **103 tests across 9 files**. It had failed 12/12 runs through 2026-08-30 on 55 warnings and 160 infos; KAN-112 resolved all of them.

**Green here is not green by construction.** The workflow pins `channel: stable` unpinned, so a future SDK bump can make a new lint fatal with no code change — the same mechanism that killed `deploy-web.yml`. Treat a red X as a real signal to investigate, not as the known-broken state it used to be.

### Supabase Project

The Supabase project is `wtncuzcskpigqpmnxwws` (org: Onebrain). Another unrelated Supabase project exists on the same account — **never use it**.

## Onebrain Agent Team

### Agent Roles
- **Tech Lead**: Reads this file, breaks features into tasks, coordinates all agents
- **Flutter UI Agent**: Handles Task A — screens, widgets, animations, design system
- **Backend/Supabase Agent**: Handles Task B — DB tables, RLS policies, edge functions, auth
- **Integration Agent**: Handles Task C — wiring Flutter to Supabase, offline logic, app-level gaps
- **QA/Reviewer Agent**: Reviews all diffs, writes tests, flags security and performance issues
- **DevOps Agent**: Handles deployments, CI/CD config, release notes

### Task Classification
- **Task A (UI)**: Screens, layouts, widgets, animations, design system implementation
- **Task B (Logic)**: Database schema, business rules, Supabase functions, RLS policies
- **Task C (Integration)**: Connecting UI to backend, offline handling, end-to-end flows

### Rules
- Always read CLAUDE.md before starting any task
- Never hardcode API keys or secrets
- Every Task B must have RLS policies defined
- Every Task A must follow the existing design system in lib/core/theme
- Task C only starts after Task A and Task B are complete
