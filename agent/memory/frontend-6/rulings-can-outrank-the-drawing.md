---
name: rulings-can-outrank-the-drawing
description: When a governance ruling and the rendered design disagree, match neither silently — report the conflict and leave the ruling standing
metadata:
  type: project
---

"The rendered design is the spec" does **not** override a `DECISIONS.md` ruling.
Where they genuinely disagree, keep the ruling, document the delta on the widget,
and send the conflict to `cxo` — it owns that call.

**Why:** the design draws Rating's empty star at `#B8B0A0`
(`--color-text-tertiary → --subtle`), but this system paints `#8C8C8C` because
**D-003(a)** demoted `--subtle` out of every light-brightness text role at 2.15:1
contrast, enforced by `test/tokens/no_subtle_as_text_test.dart`. Reaching past
`DabblerColors` to `DabblerPalette.subtle` would have matched the screenshot by
evading an accessibility decision. The lead accepted the refusal and took it to
`cxo`; the same applied to `--accent-indigo`, which is undeclared and whose
stand-in `DabblerColors.info.base` is `#3B82F6` — a **blue**, and a wider gap
than the code comment had claimed.

**How to apply:**

- Before transcribing a drawn value, check whether a ruling already governs that
  token. A contrast or a11y ruling is the usual case.
- Write the delta into the component's dartdoc with both measured values and the
  ruling's id, so the next reader sees a decision rather than a bug.
- Say plainly in the report which are yours to fix and which are `cxo`'s. If the
  ruling is later reversed, the fix should land in the token layer and leave the
  component untouched — if it wouldn't, you transcribed it in the wrong place.

Related: [[verifying-fidelity-work]], [[escalate-contended-primitives]].
