---
name: edfu-is-qa-never-build
description: Edfu is the QA lane (teams.json lane qa) — never dispatch build/frontend tickets to it
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-25T00:27:22.636Z
---

Edfu (team 7) is the QA conversation. Its role: it never builds, fixes, pushes or writes to the DB. Never dispatch frontend or backend work to it. Build work goes to Luxor, Karnak, Habu, Ramesseum, Deir el-Bahari or Memphis (ops).

**Why:** On 2026-10-25 the CEO caught KAN-641 (and earlier KAN-591) sent to Edfu: "edfu is our QA right why working on front end task?"

**How to apply:** Check the lane in agent/state/registry/teams.json before picking a team for a dispatch.
