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

## KAN-156 — stale MVP comment on createGameRoute (2026-09-09)

Work Effort (own Preflight): 1 sitting — single check-then-maybe-fix, matches what the
ticket actually contains.

**Verdict: STALE, corrected (outcome 2 of 3).** `play_places_routes.dart:162-163` said
`// Organisers can create, players cannot (MVP)`. Checked against the `createGameRoute`
redirect (`play_places_routes.dart:169-188`) and `enablePlayerGameCreation` /
`enableOrganiserGameCreation` (`feature_flags.dart:44-47`) — both are plain `const bool`
literals (not computed expressions, correcting `team-lead-5`'s original premise) and both
are currently `true`, so neither redirect branch blocks either profile type today. Fixed
the comment (lines 162-165) to describe the gating structurally rather than asserting a
fixed restriction, without citing the current true/true values (KAN-149 lesson — a value
that can flip without a code change shouldn't be baked into the comment). No other line of
mine touched. `flutter analyze` clean on the file and project-wide (0 errors/warnings, 55
pre-existing infos). Posted as Jira comment (id 10806).

**Incident, self-caused and resolved by `team-lead`'s correction.** My commit
(`a23c6d9`) also picked up 4 unrelated file deletions (3024 LOC:
`player_invitation_step.dart`, `review_confirmation_step.dart`, `sport_format_step.dart`,
`venue_slot_step.dart`) staged concurrently by another seat in the shared checkout. I
tried to undo it (`git reset --soft`), briefly orphaning `exec-144`'s legitimate KAN-144
commit before recovering it correctly, then hit a permission block on three separate
attempts to restore the 4 files — stopped and reported rather than forcing a workaround.
`team-lead` confirmed those deletions are `frontend-5`'s completed, verified, Done work
(KAN-148 — 4 orphaned game-composer step screens, zero importers, re-derived by
`frontend-5` itself) landing in the same commit object as an attribution artifact, not
contamination. Correctly left in place; not reverted.

SELF review, all four acceptance criteria: PASS (criterion 3, "no other line touched",
resolved — my own diff touched only lines 162-165; the deletions in the same commit
object are KAN-148's separately-owned, separately-verified work).

**What is blocked.** Nothing. Commit `a23c6d92f32c7f4f8fc8541e5cc1ce0cc5c8394a` stands as
part of Canary HEAD `61ae33eef26aadf55dc0f1c68c8fc303e8866fef`, 3 commits ahead of
`origin/Canary` (`715bb85`), not pushed. Ticket not transitioned (SELF route, `team-lead`
already recorded the review outcome per its message).
