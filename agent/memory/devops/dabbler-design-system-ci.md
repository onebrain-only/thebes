---
name: dabbler-design-system-ci
description: dabbler-design-system CI workflow, pinned Flutter version, and the 4 tests that cannot pass in a clean checkout
metadata:
  type: project
---

Repo `dabblersport/dabbler-design-system` had no `.github/` until 2026-09-20
(CEO-authorised, via team-lead). Added `.github/workflows/ci.yml` running on
every push and PR: `flutter analyze --no-pub --no-fatal-infos`, `flutter
test`, `dart run tool/check_doc_figures.dart` (the `@figure` co-location
gate, `T-086`). Flutter is pinned to an exact version (`flutter-version:
'3.44.1'`, `subosito/flutter-action@v2`) rather than tracking `stable`, to
avoid the failure mode recorded in the main app's own CLAUDE.md (an unpinned
channel let an SDK bump make a clean lint fatal with no code change, killing
`deploy-web.yml`). Commit `aae79d4`.

**4 of the 1382 tests cannot pass in a clean CI checkout, structurally, as
currently written.** First CI run (`c80b52b`, run
35532692731) came back 1351 passed / 4 failed / 5 skipped, all 4 failing at
`setUpAll` with `Expected: not null / Actual: <null>`:
- `test/tokens/dabbler_palette_test.dart`
- `test/tokens/dabbler_type_test.dart`
- `test/tokens/design_source_token_declarations_test.dart`
- `test/tokens/design_source_export_transcription_test.dart`

Root cause: each walks up to 8 parent directories at runtime looking for
`dabbler-design-system-design/project/...` (colors.css, typography.css, a
Figma export) to transcribe design tokens against, then
`expect(found, isNotNull, reason: 'design source not found: ...')`. That
directory is **not a separate repo** — verified `git rev-parse
--show-toplevel` from inside it returns the *Thebes-Canonical* repo root
(no `.git` of its own), and Thebes-Canonical's own root `.gitignore` line 1
(`/*`) ignores that whole path. It only exists on a machine that has this
specific Thebes-Canonical workspace checked out next to this repo — a bare
`actions/checkout` of `dabbler-design-system` alone can never produce it.
This is unrelated to and predates the CI workflow; the workflow only made it
visible.

**Why this matters for future work here:** don't trust "flutter test passes
locally" as evidence the CI gate will be green for this repo specifically —
verify against a fresh checkout or the Actions run. Also relevant to
[design-system-repo-boundary](placeholder — see
`~/.claude/projects/.../memory/design-system-repo-boundary.md` in the user's
global memory): `dabbler-design-system-design` is described there as a
"read-only Claude Design reference" sibling, which matches what was found
here — it was never meant to be a CI dependency.

Escalated to team-lead 2026-09-20 rather than fixed unilaterally — options
raised: (1) convert the 4 `expect(isNotNull)` calls to a skip when the
source isn't found, preserving local drift-checking while letting CI pass
on the other 1378 [recommended], (2) vendor a snapshot of the needed
design-source files into this repo as fixtures, (3) leave it red. Whoever
owns these test files (not devops) should decide; check whether it was
resolved before assuming CI is green here.

**How to apply:** before reporting `flutter test` green for this repo in
any context that implies CI can reproduce it, check whether these 4 files
were fixed. If asked to touch CI again for this repo, re-check the Actions
tab rather than assuming the prior red run was resolved.
