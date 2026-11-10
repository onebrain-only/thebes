---
name: measure-before-ruling-on-contrast
description: A failing contrast pairing is usually a ROLE/STRUCTURE defect, not a wrong hex — recompute before ruling
metadata:
  type: feedback
---

When a contrast failure is reported, recompute the ratios yourself and ask what the token is being
*asked to be* before touching any hex.

**Why:** on 2026-09-17 six Dabbler pairings failed AA and they turned out to be three unrelated
defects. `--muted`/`--subtle` were signed-off Figma *surface-ramp* neutrals wrongly mapped to text
roles. The five dark `on-brand × primary` failures were one structural error — the 400 shade being
used as a fill and as a light-on-dark accent at once — fixed by keeping the 600 shade as the fill
(all four then clear AA) with no hex invented. Only one, `--tag-pending-ink`, was a genuine wrong
value. Retinting to green would have "fixed" five things that were not broken.

**How to apply:** before any ruling, run the WCAG luminance formula over the candidates (the
package already has it in `test/tokens/dabbler_colors_test.dart`). Separate: signed-off source vs
provisional; hex vs mapping. Never edit a pinned measured ratio to match a ruling — pins record the
source, and the source moves first. See [[token-source-of-truth]].
