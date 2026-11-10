---
name: code-dod-review-pass-done
description: "CEO 2026-11-04 — code ticket DoD = built + review PASS → Done; Alpha integration is a separate Operations ticket for Memphis, created straight in Operations"
metadata:
  node_type: memory
  type: feedback
  originSessionId: b9b99f0a-421b-44b0-ba8d-923d3efd43c5
  modified: 2026-11-04T06:40:38.247Z
---

CEO order 2026-11-04: a code ticket is Done when it is built and passes review. It does not wait in Review for its commits to reach Alpha. The integration becomes its own Operations ticket for Memphis, created directly in the Operations status, never through Backlog or Ready.

**Why:** KAN-756/757/758/761/762/763 sat in Self-review a day after PASS because sweep_live waits for Alpha ancestry and integrate.pending skipped them. The CEO saw nothing move.

**How to apply:** two separate DoDs. Code ticket: work + review PASS = Done. Operations ticket: integration merged on Alpha = Done. Never mix them. On every review PASS, have the PM/PO close the code ticket and open the Memphis integration ticket in Operations. The permanent code change (sweep_live closing on PASS, auto-creating the integration ticket) is SYSTEM_MAINTENANCE, not done from PRODUCT_EXECUTION. See [[operations-never-to-review]], [[focus-finish-not-create]].
