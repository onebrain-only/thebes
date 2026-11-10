---
name: token-source-of-truth
description: colors.css is the only colour source of truth; fig-tokens.css is an export diagnostic, never authoritative (D-004)
metadata:
  type: project
---

`Dabbler/dabbler-design-system-design/project/tokens/colors.css` `:root` is the SOLE colour source
of truth. `tokens/figma/fig-tokens.css` is a raw Figma export — useful only as a diagnostic that a
token was missed, never transcribed from, never cited as provenance. `DabblerPalette` is
contractually a verbatim transcription of `colors.css` and a test enforces it.

**Why:** a token present in the export and absent from `colors.css` is an omission to fix at the
source, not a licence for a developer to invent a hex. `--accent-indigo` (#5C50E6) was exactly
this — wanted by five components, declared only in the export.

**Sharpened 2026-09-18 (D-028).** "Missing token" is usually the wrong diagnosis. `--accent-indigo`
was **declared all along**, at `fig-tokens.css:5` — `colors.css` never picked it up. The real defect
class is a **transcription gap between the export and the hand-authored file**, the same mechanism as
`D-007`'s `_adherence.oxlintrc.json` drifting from `tokens/*.css`. A name can be exported, used by
five components, and absent from the authoritative file **with nothing failing**. A non-empty export
is still not a source.

**How to apply:** when a component needs a colour that is not in `colors.css`, the answer is
always "declare it in colors.css, then transcribe" or "re-specify against an existing role" —
never "read it from fig-tokens.css". Approximating against a *status* token (e.g. `--social-info`)
is role abuse and here was also an accessibility regression (4.47:1 vs 5.61:1 against white).
See [[measure-before-ruling-on-contrast]].
