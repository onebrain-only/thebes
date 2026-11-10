---
name: no-ui-review-tickets
description: "CEO 2026-10-29: tickets marked \"no UI needed / no UI review needed\" are simple; the test description is a code double-check only, no UI opening"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-29T05:24:06.239Z
---

Tickets labelled "no UI needed" / "no UI review needed" are simple tickets. Nobody opens the UI for them.

**Why:** CEO 2026-10-29: they are easy, and a UI pass adds cost with no signal.

**How to apply:** when I write the test/check description for such a ticket (for myself or for Codex), say it is a double-check only: after the code is done, confirm in the code that the change was applied, then pass it. No click-by-click UI scenarios, no screenshots, no live run. Overrides [[ui-tickets-test-scenarios]] for these tickets only.
