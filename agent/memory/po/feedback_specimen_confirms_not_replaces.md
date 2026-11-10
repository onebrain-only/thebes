---
name: feedback-specimen-confirms-not-replaces
description: A figure in a doc page is ruled, declared, or measured — only measured figures are D-037(c) violations, and @specimen confirms a figure, it never replaces one
metadata:
  type: feedback
---

When writing or reviewing an AC that asks whether a numeric/weight/hex figure in a
`components/`/`foundations/` doc page violates D-037(c) ("never transcribe a measured figure"),
the test is not "is it a number" — it is what makes the figure true. `cxo` ruled this as D-043
(`DECISIONS.md`, 2026-09-18), completing D-037(c) rather than reversing it:

- **Ruled** — a `DECISIONS.md` entry fixed it. Transcribe freely, naming the ruling.
- **Declared** — resolves to exactly one named constant in the source file the page's own
  `## Source` section already cites (e.g. `sm(340)` in `overlays/dialog.dart:15`). Transcribe,
  where the figure is what distinguishes named options — on a size axis the figure often IS the
  axis, not decoration on it.
- **Measured** — no declaring site; the only way to check it is to re-measure rendered output
  (e.g. a contrast ratio). **Never transcribed** — D-037(c) binds only here.

**`@specimen <id>` is not a third treatment and never replaces a figure.** It renders the thing
without printing the number — putting it in place of a declared/ruled figure leaves the reader
measuring a screenshot, the exact act D-037(c) exists to stop. `@specimen` only **confirms** a
figure already stated in prose; it is the right addition beside a declared figure, never a
substitute for it. I (a previous session) offered "replace with `@specimen`" as one of three
available treatments when this reached `KAN-325`'s original AC4 text — that framing was wrong
and D-043(c) says so explicitly.

**Why:** 19 candidate figures were flagged on `KAN-325` (border widths, tap targets, a font
weight) as possible D-037(c) violations. All 19 resolved to declared or ruled sources and are
legitimate as plain transcribed prose — no rework needed, no `@specimen` line required. Only one
real violation existed in the corpus (Bidirectionality's Glory/Meral Sans px citation, a genuinely
measured type-fork metric) and it was correctly fixed by removal + prose cross-reference, not by
adding `@specimen`.

**How to apply:** when an AC or a review touches a transcribed figure on a doc page, resolve it
to its source before calling it a violation — check the page's own `## Source` citation for a
named constant first, then `DECISIONS.md` for a ruling, and only call it measured if neither
exists. Never write or accept "replace figure X with `@specimen`" as a fix — write "confirm figure
X with `@specimen`" if anything, and only if the figure is legitimately declared/ruled already.
See [[feedback_specimen_is_spec]] for the unrelated `.card.html` visual-fidelity specimen
convention — different artifact, same word, do not conflate them.
