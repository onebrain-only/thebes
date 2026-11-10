---
name: feedback-unwired-vs-orphaned
description: "'X is not wired up' and 'X is orphaned' are the same measurement and opposite rework briefs — check what else already does the job before writing the first"
metadata:
  type: feedback
---

When a component/widget/module has no caller, do not write the rework brief as "it is not
wired up" until you have checked **what else already does its job**. The same measurement
supports two opposite briefs:

- **"not wired up"** names an absence and tells the executor to ADD the wiring.
- **"orphaned/superseded"** names a duplicate and tells the executor to consider REMOVING it.

Getting this backwards ships the duplication. On KAN-327 (2026-09-20) I wrote that
`GalleryDocPage` "is never routed in `lib/main.dart`" — true, but `_DocPane` was already
rendering every documentation page, and its own doc comment said it was "the shell half
KAN-327 asks for". Routing the orphan would have put two doc renderers in one gallery, which
is the [[specimen-is-spec]]-adjacent D-053(b) defect shape (two card treatments in one
gallery) one level up.

**Why:** `grep` for a symbol's references answers "who calls this", not "is this needed".
The second question needs a search for the CAPABILITY, not the symbol — who else loads a doc
page, who else renders a card, who else parses this file. team-lead caught this one; the
measurement was right and the brief was wrong.

**How to apply:** before writing "not wired up / not routed / not registered" in any rework
brief, grep for the *job* as well as the *name* — the sibling that quietly took it over is
usually in the same directory, and its doc comment often says so outright. Then decide which
brief the evidence actually supports. Applies to review verdicts especially, where the brief
is the whole deliverable and an agent with no context will do exactly what it says.

Related: [[standard-by-construction]] (post the note on the ticket that will CAUSE the drift),
[[specimen-confirms-not-replaces]].
