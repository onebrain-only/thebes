---
name: project-audit
description: Use when auditing the Dabbler codebase — assessing project health, finding what is finished vs half-built, locating dead/unused/orphaned code, spotting broken or unreachable screens, checking documentation drift, or reviewing security posture. Triggers on "audit", "project status", "what's broken", "what's unused", "state of the codebase", "health report", "tech debt", "what's actually working". Produces or refreshes docs/PROJECT_STATE.md with file-cited evidence.
---

# Dabbler Project Audit

Produce an evidence-backed report on the real state of this codebase. Every claim
carries a `file:line` citation or a number the scanner produced. **No estimates.**

This repo is ~1 year old with heavy rework. Screens were built, abandoned,
rebuilt, and left in the tree. The audit's job is to tell truth from residue.

## Prime directive

> Findings engineers act on. Anything that "feels comprehensive but changes
> nothing" is a failure. No sycophancy, no diplomatic softening, no
> "the codebase is well-structured overall."

Equally: **do not cry wolf.** A finding you cannot cite is not a finding.

---

## Phase 1 — Orient (never skip)

Build a real mental model before judging anything.

```bash
cat CLAUDE.md README.md 2>/dev/null | head -120
git log --oneline -100
git log --stat --since="6 months ago" --format='%cs' -- lib/ | head -60
ls docs/
```

Write 1–2 paragraphs: what this app is, how it is structured, where change is
actually concentrated. Explicitly flag contradictions between what the docs claim
and what the tree shows. Churn tells you where the pain is.

## Phase 2 — Mechanical scan

```bash
.claude/skills/project-audit/scripts/scan.sh            # everything
.claude/skills/project-audit/scripts/scan.sh wiring     # completed vs not
.claude/skills/project-audit/scripts/scan.sh unused     # dead flags/deps/providers
.claude/skills/project-audit/scripts/scan.sh security
.claude/skills/project-audit/scripts/scan.sh convention
.claude/skills/project-audit/scripts/scan.sh tests
.claude/skills/project-audit/scripts/scan.sh analyze    # slow: flutter analyze
```

The scanner emits evidence, not conclusions. **You** interpret it. Never paste raw
scanner output into the report as if it were analysis.

## Phase 3 — Audit dimensions

Nine dimensions. Cite `file:line` on every concrete finding.

1. **Completion state** — for each feature: shipped / partial / scaffolded / dead.
   Judge on *reachability*, not file count. A screen no route reaches is not shipped.
2. **Dead & orphaned** — orphan screens, orphan providers, unused flags, unused
   deps, `.broken`/`_v2`/`_old` residue.
3. **Architectural decay** — god files >500 LOC (CLAUDE.md limit), duplicated logic
   in 3+ places, circular deps, abstractions with one implementation.
4. **Consistency rot** — `Result<T,Failure>` vs legacy `Either` (never mix inside a
   feature); naming drift; slices that skip the standard layout.
5. **Test debt** — which features have no `test/features/<name>/` at all; whether
   critical paths (auth, payments, join-game) are covered.
6. **Dependency & config** — unused deps, undocumented env vars, the dual
   Cloudflare Production/Preview variable split.
7. **Error handling** — swallowed exceptions, blanket catches, stray `print()`,
   repositories that throw instead of returning `Result`.
8. **Security** — secrets, client-side auth checks that belong in RLS, tables
   missing RLS, storage buckets missing a SELECT policy.
9. **Documentation drift** — docs older than the code they describe; docs
   describing features that no longer exist.
10. **Agent & skill utilisation** — which agents in `.claude/agents/` and skills in
   `.claude/skills/` are actually exercised vs installed and idle; which of the
   ~33 globally installed skills are irrelevant noise for a Flutter project.
   Check `.claude/agent-memory/*/` for evidence an agent has ever run.
11. **In-code incompleteness signals** — harvest and classify every author comment
   admitting unfinished work: `TODO`, `FIXME`, `HACK`, `XXX`, "coming soon",
   "not implemented", "temporary", "for now", "placeholder", "stub",
   `UnimplementedError`, empty catch blocks, and functions whose body is only a
   `return null` / `return []`. Group by feature and quote the line. These are the
   author telling you what is unfinished — treat them as primary evidence, not noise.

## Phase 4 — Deliverable

Write / refresh **`docs/PROJECT_STATE.md`**:

1. **Executive summary** — max 10 bullets, ranked by impact.
2. **Mental model** — 1–2 paragraphs.
3. **Feature completion table** — every feature: LOC, screens, routed?, tests?,
   status (`SHIPPED` / `PARTIAL` / `SCAFFOLD` / `DEAD`), evidence.
4. **Findings table** — `ID | Category | File:Line | Severity | Effort | Finding | Recommendation`.
   Target 30–80. Severity `CRITICAL/HIGH/MED/LOW`. Effort `S/M/L`.
5. **Top 5 priority fixes** — with a sketch of the change.
6. **Quick wins** — low effort × medium-plus severity.
6b. **Agent & skill utilisation table** — installed vs actually used, with a
   recommendation to keep / adopt / remove for each.
6c. **Incompleteness register** — every in-code admission of unfinished work,
   grouped by feature, quoted with `file:line`.
7. **"Looks bad but is actually fine"** — **mandatory.** Omitting it signals a
   shallow audit. (Example: the Firebase API keys in `lib/firebase_options.dart`
   and `android/app/google-services.json` are *client* identifiers, public by
   design, and not a leak. Flagging them as a breach is a false positive.)
8. **Open questions for the PO.**

## Phase 5 — Repeat-run mode

If `docs/PROJECT_STATE.md` already exists, **read it first**. Then:
- mark fixed findings `RESOLVED` (with the commit if you can find it),
- update entries whose numbers moved,
- tag new findings `NEW`,
- append a dated row to the changelog.

The report is a living document tracking the project over time, not a fresh dump.

---

## Dabbler-specific knowledge

Facts that change how evidence should be read. Get these wrong and the report lies.

| Signal | Correct reading |
|---|---|
| Firebase `AIza…` keys in the tree | **Not a leak.** Public client identifiers. |
| `service_role` in `supabase/functions/**` | Server-side edge functions — expected. Only a finding if it reaches `lib/`. |
| Feature flag declared but never read | Dead flag. **A flag is not a feature.** |
| Screen class referenced only in its own file | Unreachable. Not shipped, whatever its LOC. |
| `dabbler_design_system` unused | Local package — confirm whether it's being adopted or abandoned. |
| `.g.dart` / `.freezed.dart` | Generated. Exclude from god-file and style counts. |
| `lib/l10n/app_localizations*.dart` | Generated. Exclude. |
| Bucket `venue-images` / `avatars` | **These do not exist.** Bucket-name mismatch is a recurring bug class. |
| Storage upload without a SELECT policy | Broken — uploads need read-back. Recurring bug class. |
| App hangs on launch screen | Expected without `flutter run --dart-define-from-file=.env`. Not a bug. |
| Push to Canary looked green | Proves nothing. Cloudflare Production and Preview hold **separate** variables; Preview sat empty for months and silently broke every Canary build. |
| `encrypted_password` NULL on new users | By design — trigger `trg_strip_signup_password`. Accounts are passwordless. |

Supabase project is `wtncuzcskpigqpmnxwws` (org Onebrain). **A second, unrelated
project exists on the account — never read or write it.**

## Constraints

- **Read-only.** This skill audits; it does not fix. Findings become work for
  feature agents.
- Never recommend a rewrite. Scoped, specific changes only.
- Never pad the findings table to look thorough.
- If a scan is unavailable, log the gap and continue — never fabricate around it.
