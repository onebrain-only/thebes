---
name: feedback-untested-gallery-wiring
description: Per-component RTL/theme tests bypass GalleryAppearance entirely, so the switcher-to-component wiring itself has no automated test
metadata:
  type: feedback
---

Found while reviewing KAN-294 (gallery direction switcher, closed 2026-09-18). Every per-component
RTL test (`code_input_test.dart`, `calendar_test.dart`, `slider_test.dart`, etc.) wraps its own bare
`Directionality` directly rather than going through `GalleryAppearance`/`GalleryThemeScope`. That is
correct test design — a component test should not depend on the gallery app shell — but it means
**nothing tests the switcher-to-component wiring itself**: the `Directionality` placement in
`gallery_app.dart`, above the Navigator, driven by `GalleryAppearance.direction`. That seam had no
automated coverage for roughly a year (the whole time RTL was "specified in prose and rendered by
nobody," per D-033(d)) and still has none — KAN-294 closed on documented manual/screenshot
verification instead, because the CEO's standing no-new-tests instruction for this pass made an
automated test something the executing agent was told not to write.

**Why:** not a defect — a deliberate, escalated trade-off (team-lead put the ambiguity to the CEO
rather than resolve it unilaterally). Recorded so it isn't silently lost once the no-new-tests
period ends.

**How to apply:** once the CEO's standing "no new tests, prove it by looking" instruction for the
fidelity/documentation recovery period lifts, this is a small, well-scoped follow-up: one widget
test that drives `GalleryAppearance.direction` (or `.theme`/`.mode`) through the app shell and
asserts a real rendering change on a component already known to be direction/theme-sensitive
(e.g. `Slider`'s pointer position, or `CodeInput`'s digit-box order). Same shape likely applies to
the theme/brightness switcher (KAN-285) — check whether an equivalent wiring test exists for that
axis before assuming only direction is gapped.
