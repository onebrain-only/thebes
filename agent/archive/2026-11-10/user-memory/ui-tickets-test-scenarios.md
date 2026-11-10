---
name: ui-tickets-test-scenarios
description: "CEO 2026-10-14 — every UI-changing ticket carries a \"Testing scenarios (for Codex QA)\" section with click-by-click test cases and expected results"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-14T05:29:13.324Z
---

CEO 2026-10-14: every ticket that changes the UI must carry a section of described test cases. Each case gives exact click steps, for example: log in, then click the location under the logo at the top left, then click "Use my current location". Each case also states the expected result, so Codex can run QA in review quickly. Apply it to open tickets (Ready and earlier); tickets already done stay as they are.

**Why:** Codex review slows down when it has to work out what to press. Scripted scenarios make QA fast and repeatable.

**How to apply:** when the PO writes or polishes a UI ticket, require the section. It covers preconditions (test account, flags, platform), TC1..n with real on-screen labels, the AC each case proves, empty/error/denied states, RTL and dark theme where visual, and what is out of scope. Location tickets include the denied-path case ([[location-permission-rule]]). Related: [[dev-claude-qa-codex-flow]].
