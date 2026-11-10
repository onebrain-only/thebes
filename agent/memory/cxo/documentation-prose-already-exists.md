---
name: documentation-prose-already-exists
description: The design system's guidance prose already exists in three sources (64 *.prompt.md, FOUNDATIONS.md, dartdoc) — documentation work is assembly, not authoring.
metadata:
  type: project
---

Before commissioning any design-system documentation writing, check the three existing prose sources:
`dabbler-design-system-design/project/components/**/*.prompt.md` (64 files, per-component definition
and props), `…/project/guidelines/FOUNDATIONS.md` plus 18 `guidelines/*.html` (the global rules), and
the Flutter dartdoc under `dabbler-design-system/lib/src/**` (why the build diverges from the design).
`DECISIONS.md` `D-` entries are the change log.

**Why:** ruling `D-033` began as "design a documentation system" and the measurement showed most of
the content was already written in a place the gallery never reads. A brief that assumes authoring
commissions a second copy of rules that already exist — and a second copy is a second place to be wrong.

**How to apply:** when documentation is requested, name the source per section and mark the sections
with no source; those are the only ones anyone writes. See [[source-precedence-jsx-vs-prose]] and
[[design-source-authority-map]] for which source wins when two disagree.
