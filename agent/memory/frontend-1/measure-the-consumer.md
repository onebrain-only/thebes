---
name: measure-the-consumer
description: Verify a figure by reading the widget that consumes it, not the plausible-looking constant or the inherited default — this beat a cxo ruling twice in one day.
metadata:
  type: feedback
---

Before accepting or quoting a measurement, read the widget that actually consumes it. Not the
nearest authoritative-looking constant, not the inherited default.

**Why:** 2026-09-18, D-047/D-048. `cxo` sized a nav rail from `DabblerMenu.minPopoverWidth`
(a popover's minimum, not this nav's content), then computed label widths from `DabblerType.body`
16px because `galleryTextStyle` makes it the gallery default — while the rows actually render at
`DabblerType.footnote` 13px. Both figures were wrong and a single on-screen check refuted them.
Its own conclusion: *"Measure the consumer, not the default."* The same failure mode produced the
earlier "the design declares no breakpoints" claim — grepping the design bundle's CSS for `@media`
while the thresholds lived in `guidelines/` HTML and in our own Dart.

**Read "consumer" widely — it also means *which file would actually tell me*.** The constant and
the search dialect are the same error in different clothes: one reaches for a plausible value, the
other for a plausible place to look. `cxo` accepted this generalisation over its own narrower one
(D-048 follow-up, 2026-09-18).

**How to apply:** a claim about size, colour or spacing is only as good as the file that renders
it. Quote the file and line. Before reporting an ABSENCE, check you searched the dialect the answer
would be written in — this system states thresholds in `guidelines/` HTML and in Dart, not in CSS
`@media`. Where a rendered check is possible, prefer it over arithmetic: a rendered observation
beats a computed one. See [[verify-visually-not-by-assertion]].
