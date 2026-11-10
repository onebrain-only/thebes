---
name: design-source-authority-map
description: Which files in the design bundle carry authority and which are demos, exports or inventions — check the header before ruling on any fidelity conflict.
metadata:
  type: project
---

In `Dabbler/dabbler-design-system-design/project/`, a file's authority is readable from its own
header, and three classes have been mistaken for the design:

- **`// figma node: N:NN` header** — a drawn component. Highest authority (`NavigationTopBar`,
  `NavigationTabBar`, `NavigationBottomBar`, most of `components/`).
- **No figma header, with a stated rationale** — hand-authored, authority from its reasoning
  (`Tabs.jsx`). **No figma header, no rationale** — an invention: `TimePicker.prompt.md` says
  *"Intentional addition: the kit has no time picker"* (D-030).
- **`ui_kits/dabbler-app/`** — a click-through recreation of the SHIPPING Flutter app, using
  Lucide stand-in glyphs, with navigation excluded from its own composition list. **No authority
  over any component** (D-026).
- **`tokens/figma/fig-tokens.css`** — export artefact only (D-004). `--purple-700`,
  `--font-size-small`, `--neutral-white` exist only here, so anything built from them is residue.

**Why:** three of seven fidelity conflicts in the 2026-09-18 pass dissolved on reading the source
header rather than the report — and two more dissolved on reading the committed Dart
(`badge.dart:264`, brand is *decorative* so it draws no border; `Avatar.jsx:91` is `0 0 0 2px`, a
stroke not a shadow).

**How to apply:** on any "design says X, we built Y", first classify both sides by this map, then
verify the claimed values in the files. Never rule from a tabulated comparison someone else made.
See [[source-precedence-jsx-vs-prose]] and [[token-source-of-truth]].
