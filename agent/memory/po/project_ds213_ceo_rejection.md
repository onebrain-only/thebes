---
name: project-ds213-ceo-rejection
description: KAN-213 (Dabbler Design System, ~40-component first cut) was rejected by the CEO on visual fidelity on 2026-09-17 despite 36/36 tickets meeting their written criteria
metadata:
  type: project
---

Epic `KAN-213` closed at 36/36 tickets Done, `flutter analyze` clean, tests green, and was then
rejected by the CEO on visual fidelity after reviewing the running gallery directly. In
substance: components read as Material widgets, not the Dabbler design; fonts were never wired
(Roboto everywhere, though the binaries sat in the design bundle the whole time); the gallery
defaulted to dark/system instead of the design's light-paper default; the gallery chrome was a
bare Material Scaffold/AppBar/ListTile app; and several components (CardTicket, Button, others)
were under-built against what `*.card.html` actually draws, not merely mis-styled.

**Why:** root cause was ticket-writing method, not execution — see [[feedback_specimen_is_spec]].

**How to apply:** six fidelity-recovery tickets are open under KAN-213 (KAN-287 gallery chrome,
288 cards, 289 controls, 290 forms, 291 surfaces+foundations, 292 nav/overlays/feedback/
layout/calendar), all with visual acceptance criteria and explicitly **no new tests**, per the
CEO's direct instruction to put effort into implementation rather than test-proving for this
pass. KAN-254 (fonts) was unblocked the same day — its earlier "blocked, no Work Effort" status
was a process artefact, not a real blocker; the binaries were always present. Before scoping any
further DS work, check whether these six are still open — if so, fidelity recovery is still the
active priority over new-component work. This memory should be updated or removed once the six
land and the CEO re-reviews.
