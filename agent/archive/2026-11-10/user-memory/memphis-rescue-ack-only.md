---
name: memphis-rescue-ack-only
description: "devops ruling 2026-11-05 — further rescues/continuations of KAN-833/827/848 blocked reports get only 'ack', no decision request"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 961bbed1-4415-4455-99d1-05b4a24efb27
  modified: 2026-11-05T17:44:09.513Z
---

On a rescue or continuation of KAN-833, KAN-827 or KAN-848 (blocked reports), Memphis submits only the single word `ack` and opens no decision request. Work on these resumes only through a normal ready-dispatcher dispatch.

**Why:** devops (dreq-42b48678, 2026-11-05) said this was the last answer on those blocked reports. Earlier rescues kept opening decision requests that nobody needed.

**How to apply:** verify the session id, then submit once with `--result "ack"`. Take no SQL or git action.
