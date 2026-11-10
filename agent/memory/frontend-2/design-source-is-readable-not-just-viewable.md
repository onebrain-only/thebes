---
name: design-source-is-readable-not-just-viewable
description: The served design bundle's page chrome is inline CSS in each .card.html — read it for exact values instead of eyeballing screenshots.
metadata:
  type: feedback
---

When replicating the Dabbler design, `curl` the `.card.html` / `guidelines/*.html` pages from
the served bundle and read their inline `<style>` blocks, rather than working only from
screenshots. Screenshot to confirm; read the source to get the numbers.

**Why:** every specimen page carries its own page furniture as literal CSS — `body{background:
var(--surface-page);padding:20px}`, the `Group` label at `11px/.08em/uppercase/700/var(--muted)`,
`.usage` at `12px/1.5` in `--ink-soft`, `section` hairlines in `--outline-card`. `tokens/colors.css`
gives the hex for each var. That turns "match the drawing" from estimation into transcription,
and it is how the gallery chrome rebuild got exact values in one pass instead of iterating on
pixel comparisons.

**How to apply:** at the start of any fidelity task, fetch the assigned specimen page plus
`styles.css` and `tokens/colors.css`, map the CSS vars onto `DabblerColors` fields, then build.
Related: [[design-source-outranks-peer-guidance]].
