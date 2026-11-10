---
name: orchestrator-runs-only-pm-po
description: D-042 — the orchestrator runs only the PM and POs (background); rulings and design/behaviour judges go to Memphis as one dispatch
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-08T21:44:26.750Z
---

CEO 2026-10-09: I run only `pm`, `po` (app) and `po-2` (design system), always in the background. Rulings from cto/cpo/cxo: ONE question dispatch to Memphis (no `--ticket`), naming every seat; Memphis returns one answer; then log it with `pm_ledger add`. Judge items: design fidelity → Memphis (cxo), behaviour → Memphis (qa); only an acceptance judge on a project's own ticket may use that project's PO.

**Why:** D-042 makes Memphis the ops lane that runs leadership/reviewer seats; the orchestrator stays free for the CEO.
**How to apply:** never `Agent(subagent_type=cto|cpo|cxo|qa|...)` myself. Related: [[orchestrator-delegate-not-execute]], [[briefs-no-drop-no-prod-test-writes]].
