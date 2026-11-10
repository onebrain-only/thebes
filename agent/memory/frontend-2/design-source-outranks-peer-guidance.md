---
name: design-source-outranks-peer-guidance
description: The design source under dabbler-design-system-design/project outranks a peer agent's or lead's steer about how to compose their component
metadata:
  type: feedback
---

The design source (`Dabbler/dabbler-design-system-design/project/**`) outranks a steer in
my brief about how to compose someone else's component — including one relayed from that
component's own author. Cite the source lines in the file and in the report, and the
disagreement resolves without a round trip.

**Why:** twice on KAN-250 (2026-09-17) the brief's guidance was wrong against the source, and
the lead accepted the source both times. DS-700's author said Select composes
`DabblerMenuList` at `role: listbox`; `Select.jsx:63-95` passes no `role` and
`fields.card.html:113` says `role="menu"`. DS-600's author said pickers use
`variant: select`; `PickerField.prompt.md` and `DateField.prompt.md` require typed entry,
which that variant cannot give.

**How to apply:** when the brief and the source disagree, follow the source, write the
deviation and its citations into the file's dartdoc, and say so plainly in the report rather
than silently complying or stopping to ask. Also check whether a named specimen is real: a
`.card.html` whose first line says `source-only` has been consolidated elsewhere.

Related: [[compose-do-not-duplicate-chrome]]
