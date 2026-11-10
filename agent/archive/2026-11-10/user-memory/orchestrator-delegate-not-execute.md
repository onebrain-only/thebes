---
name: orchestrator-delegate-not-execute
description: "CEO wants the orchestrator to only distribute tasks to teams; no hands-on code, git, merges, pushes or DB work by the orchestrator"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-06T19:37:35.875Z
---

The CEO (2026-10-07) objected that the orchestrator was working "by hand" in the code (merging, pushing, pulling into checkouts, applying migrations, editing lock files). Rule: the orchestrator is only a dispatcher. Any task that needs no discussion goes straight to a team (Karnak / Luxor via conversation_dispatch), and the team executes it, including git merges, pushes, pulls into the CEO checkout and DB applies. The orchestrator stays free to take new tasks, reviews results, and talks to the CEO (in Arabic when the CEO writes Arabic) only when a real decision is needed.

**Why:** avoid problems from the orchestrator acting directly, and keep it available for new work.
**How to apply:** finish what is already in flight, then route every new execution step (including "push", "pull into dabbler-code", "apply migration") through a team dispatch with a brief. Only discussion/decisions stay with the orchestrator. Related: [[ceo-decide-dont-wait]].
