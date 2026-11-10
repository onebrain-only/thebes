---
name: liveness-every-team
description: "CEO 2026-11-01 D-045 — every orchestrator liveness-checks ALL teams every 5 min, even idle ones; never just dispatch-and-wait"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0a2fe358-3c7d-441e-b22d-9153cd1adc00
  modified: 2026-11-01T03:15:07.221Z
---

Every orchestrator, new or running, must have a 360 view of every team every 5 minutes. That includes teams it believes are idle and teams it believes are holding a task. It never just dispatches and waits.

Implemented as D-045: `agent/execution/liveness.py`, swept by `watchdog serve`, shown as LIVENESS rows in the fact block, with `liveness` inbox items and `liveness revive <team>` for silent teams.

**Why:** the CEO caught the orchestrator believing work was done when it was not, or that it sat with a team when it did not. Checking only the busy teams misses a team stuck on a task the orchestrator no longer sees.

**How to apply:**
- Claims about what a team is doing come from the LIVENESS rows (see [[orchestrator-facts-and-orders]]).
- When the checked line is STALE, restart with `thebes-up.sh`.
- Never narrow the probe to the busy teams only.
