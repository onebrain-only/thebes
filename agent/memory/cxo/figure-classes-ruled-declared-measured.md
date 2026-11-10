---
name: figure-classes-ruled-declared-measured
description: Before calling a transcribed number a D-037(c) violation, classify it — ruled, declared, or measured. Only measured is forbidden.
metadata:
  type: project
---

A number in a documentation page is not automatically a "transcribed measured figure".
D-043 splits it three ways by **what makes it true**:

- **ruled** — an entry in `DECISIONS.md` fixed it (45 tap target, 16/12 radius, 21 corner,
  weight 400). Transcribe freely, naming the ruling. A ruling cannot rot.
- **declared** — resolves to exactly ONE named constant in the source the page's `## Source`
  already cites (`dialog.dart:15` `sm(340)`). Transcribe where the figure is what
  distinguishes named options — i.e. `## Axes`.
- **measured** — no declaring site; checkable only by re-measuring, and two people may get two
  answers (contrast ratios, realised font metrics). **Never transcribed** — D-037(c).

**Operative test: can a reader resolve it to one named line of source?**

**Why:** D-037(c) ruled only the measured class but was being read as ruling all numbers,
which nearly stripped 19 correct figures out of `## Axes`. On a size axis the figure IS the
axis — remove it and "`sm` (dense rows), `md` (the default)" stops answering the only question
the section exists for.

**How to apply:** classify before ruling a figure a defect. Resolve it to source first —
that act decides the class. Bidirectionality's removal fix was right only because font metrics
are measured; it is not a precedent for removal as default. See
[[touch-target-is-not-the-painted-mark]], [[measure-before-ruling-on-contrast]].
