# junior-frontend-1a — status log

## 2026-09-06 — Skills audit of this seat (survey, from `team-lead`)

**What it was.** A read-only survey, not work: three questions about which skills this seat
needs, with the specific question of whether cluster size and coupling change `3a`'s answer.
First entry in this file — this seat has never run a task.

**What I did.** Read `agent/roles/junior-frontend-1a.md`, listed `agent/skills/` (75 entries
including `AVAILABLE.md`, so **74** repo skills — matches `3a`), read `agent/skills/AVAILABLE.md`,
read `junior-frontend-3a`'s entry, opened `project-audit`, `front-door`, `teach`, `wait-what`,
`codebase-design`, `working-with-legacy-code` and `remove-technical-debt`, and read
`Dabbler/dabbler-docs/PROJECT_STATE.md` §2 and §3. Then measured my own slices in
`Dabbler/dabbler-code` at the checked-out tree.

**What I touched.** This file only. No `lib/`, no `test/`, no git, no Jira, no `flutter`
command. `CONTRACT.md` §4.1 bars this seat from Phase 0 and Phase 0 is live.

**What I measured.**
- `lib/features/profile/data/` is **2,825 LOC** with **3** references from outside itself
  repo-wide, one of which is a doc comment. `lib/features/profile/domain/usecases/` has **2**.
- My five slices hold **167** non-generated Dart files. **14** reference `fpdart`/`Either<`;
  **19** reference `core/fp/result`. Both conventions are live in the same slices.
- `PROJECT_STATE.md:88-94` names `lib/features/profile/data/` as one of the three biggest
  pieces of the abandoned parallel clean-architecture stack — "roughly a quarter of `lib/` is
  a parallel implementation that no route reaches."

**The finding that is mine.** `lib/data/repositories/profiles_repository.dart:4-12` is a doc
comment that reads *"New code should prefer the clean-architecture `ProfileRepository` in
`lib/features/profile/domain/repositories/` and its `ProfileRepositoryImpl` in
`features/profile/data/repositories/`."* That is an in-repo instruction pointing this seat at
the stack the audit calls abandoned. Grep does not fail here — grep **succeeds** and returns
an authoritative-sounding sentence that is wrong. That is a worse failure mode than the
pattern-finding gap `3a` named, and no skill in the 524 catches it.

**Corroborating that naive liveness checks are unreliable in both directions:**
`lib/core/services/auth_service.dart:284-295` records `ProfileLocalDataSourceImpl` being
misclassified DEAD by grepping for the constructor and missing the provider name — corrected
2026-08-28.

**What I decided.**
- Agreed with `3a`'s rule and its "fewer, not more" verdict. No differences.
- No skill added. The three that carry the right keywords — `working-with-legacy-code`,
  `codebase-design`, `remove-technical-debt` — are all judgment skills (seams, deepening,
  dependency-breaking) and are disqualified by `3a`'s own rule.
- The gap is not a skill. It is a **provenance marker on the pattern**, and the artefact that
  would carry it (`PROJECT_STATE.md`) is a document this seat is not told to read.

**What is blocked.** Nothing. Survey answered; no follow-up requested.
