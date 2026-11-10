---
name: rtl-is-asserted-but-never-rendered
description: The design-system gallery has no direction switcher — every RTL contract is prose that nobody has seen render.
metadata:
  type: project
---

`GalleryAppearance` (`lib/src/gallery/gallery_theme_scope.dart:34-69`) carries `theme` and `mode` only.
There is no `TextDirection` control. Meanwhile RTL behaviour is specified in at least ten component
files — `calendar.dart:126` (week starts Saturday), `code_input.dart:51` (boxes stay LTR),
`slider.dart:373` (pointer inverts), plus `input_row`, `menu`, `tooltip`, `tabs`,
`picker_field_shell`, `time_picker`, `top_bar`; type forks by script at `dabbler_type.dart:456`.

**Why:** found while ruling `D-033`. Bilingual EN/AR is a layout contract, not a translation pass, and
a contract that has never been rendered is a claim, not a fact.

**How to apply:** treat any RTL fidelity claim about this system as unverified until a direction
switcher exists. Do not accept "supports RTL" as a review answer; ask what rendered it.
