---
name: shared-gallery-files-get-clobbered
description: In multi-agent waves, lib/main.dart and the barrel get silently overwritten mid-edit — re-check them before reporting done.
metadata:
  type: project
---

During parallel component waves in `dabbler-design-system`, `lib/main.dart` and
`lib/dabbler_design_system.dart` are written by many agents at once and overwrite each other
without conflict markers.

**Why:** they are the two files every component ticket must touch — one line in the entries
list, one export in the barrel. Observed 2026-09-17/18: `main.dart` was reverted to an older
revision (losing the theme switcher) seconds after being rewritten, and the barrel silently
lost its `gallery_theme_scope` / `gallery_theme_switcher` exports, which broke
`gallery_theme_switcher_test.dart` with `undefined_identifier`.

**How to apply:** after editing either file, re-read it before running the final
`flutter analyze` / `flutter test`, and re-apply if clobbered. When an `undefined_identifier`
appears for a symbol that should be public, check the barrel's export list first — the symbol
is usually still there, just no longer exported. Related:
[[compose-do-not-duplicate-chrome]].
