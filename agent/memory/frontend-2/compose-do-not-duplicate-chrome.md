---
name: compose-do-not-duplicate-chrome
description: When a peer's component and mine would both paint the same chrome, mine composes theirs — validated by the lead on KAN-250
metadata:
  type: feedback
---

When my component and a peer's would both paint the same chrome, mine composes theirs
rather than sitting beside it. Confirmed by the team lead on KAN-250 (2026-09-17), which
called it "the more important half" of the work: `DabblerPickerField` composes
`DabblerPickerFieldShell` instead of keeping a second copy of the picker box.

**Why:** two implementations of one chrome in the design system is the drift the no-fork
rule exists to prevent, and it drifts silently — both look right the day they land.

**How to apply:** on discovering a peer has built the same chrome, move theirs in verbatim
(only the parts of its dartdoc that became untrue), compose it, and report every import I
changed in files outside my `Surfaces:` line. Do not improve a peer's component under them
even when the source supports the improvement — report it so it gets its own ticket, as the
missing `dbl-focus` focus ring on `_PickerButton` did.

Related: [[oversized-ds-files-split-by-part]], [[design-source-outranks-peer-guidance]]
