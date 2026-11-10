---
name: oversized-ds-files-split-by-part
description: Design-system files over the 500-line rule are split with part/part-of under a po ticket, never by inventing a file mid-wave or granting an exemption
metadata:
  type: project
---

When a `dabbler-design-system` file exceeds the 500-line house rule, the remedy is a
`po` ticket that splits it with `part` / `part of` — one library, every file under 500,
private members staying private. It is never fixed by inventing a new file mid-wave, and
never granted an exemption. Precedent set 2026-09-17 by the team lead: `sheet.dart` (684
lines, KAN-265) and `picker_field.dart` (609 lines, from KAN-250) are both handled this way.

**Why:** a new filename outside any ticket's `Surfaces:` line is a collision with whoever
else is in the package, and forcing `_PickerButton`-style privates into the public surface
to enable a plain split is worse than the oversized file.

**How to apply:** if my work leaves a file over 500 lines, report the number and the
structural options to the lead and keep working — do not create the file, and do not
delete a component to get under the limit. A component with no consumer inside this
repo is not dead code: the consumers are the app's screens, not this package.

Related: [[compose-do-not-duplicate-chrome]]
