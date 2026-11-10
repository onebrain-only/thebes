---
name: escalate-contended-primitives
description: Report a cross-cutting primitive defect with the fix spelled out rather than editing it mid-session; and distrust names that assert their own correctness
metadata:
  type: feedback
---

When a defect is found in a primitive that many seats are building on right now,
**report it with the evidence and the exact fix, and wait to be authorised** —
even when the file is nominally your surface.

**Why:** on 2026-09-17 I found `DabblerIconRegistry.keyFor` had `linear` and
`bold` mapped to the wrong `Iconsax` keys, so every icon in the package drew at
the wrong weight. It was my surface and the fix was one line, but ~30 agents were
building against it, the fallback direction had to invert with it, and 6+
assertions encoded the old behaviour. I escalated instead of editing; the lead
authorised it immediately and told the other agents it was landing, so nobody
re-derived it or worked around it. Escalating cost minutes and prevented that.
The lead called it the highest-impact find of the session *and* called
escalating-rather-than-editing the right call — both halves mattered.

**How to apply:**

- Judge by **blast radius and concurrency**, not by whether the path is in your
  assignment. One line in a token or a registry can outrank a whole component.
- Make the report actionable enough to be approved in one round: the evidence,
  the exact change, and every consequence you already know (here: the fallback
  inversion and the affected tests).
- **Distrust a name that asserts its own correctness.** `boldSuffix = '_copy'`
  was not merely wrong beside the inverted mapping — it *was* the mapping,
  restated as an identifier, so every reader who checked the function against the
  constant found them agreeing. Rename such a thing as part of the fix
  (`linearSuffix`), and never treat "the constant agrees with the function" as
  evidence.
- Repairing tests that pinned the defect is legitimate and is not "writing new
  tests"; adding coverage beyond that repair is.

Related: [[verifying-fidelity-work]], [[rulings-can-outrank-the-drawing]].
