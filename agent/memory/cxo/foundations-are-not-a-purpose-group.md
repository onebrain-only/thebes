---
name: foundations-are-not-a-purpose-group
description: D-033(b)'s nine purpose groups subdivide Components only; Foundations is that section's sibling. Read (b) with (a).
metadata:
  type: project
---

D-033(a) fixes **four sections** (Start here, Foundations, Components, Patterns). (b)'s nine
purpose groups are the subdivision of **Components alone** — they name what a component does
on a screen. Colour is not a thing a screen contains; it is a rule everything obeys.

**Why:** putting foundations into the nine would not add a tenth group — it would move
Foundations *into* Components and collapse two of the four sections, sideways, through a
nullable field. D-044 refused it; D-033 is unamended.

**How to apply:** (b) is routinely read without (a) and then looks like a gap. It is not.
Also: `gallery_index.dart` bands foundations on `page.startsWith('foundations/')`, **not**
`group == null`, deliberately — a component that forgot its group lands nowhere and is visibly
missing rather than quietly filed under foundations. Collapsing those two predicates is a
regression, not a cleanup. `group: null` is accurate; how Dart spells "not a component" is
`cto`'s type call. See [[source-precedence-jsx-vs-prose]].
