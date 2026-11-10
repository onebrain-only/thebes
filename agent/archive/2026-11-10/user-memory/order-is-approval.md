---
name: order-is-approval
description: "CEO 2026-10-25 — once he gives an order, that IS approval; never ask him to approve it again"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-25T11:37:14.126Z
---

When the CEO gives an order, treat it as approved and execute; never come back asking for his approval of that same thing.

**Why:** CEO: "انت ما ينفعش تسألني على موافقتي بعد ما انا مدي الامر... اديتك امر، يعني انا موافق."

**How to apply:** Don't list "needs your approval" items for work he already ordered; dispatch it. Hard safety prohibitions still stand. Related: [[ceo-standing-approvals]], [[ceo-delegates-decisions]].

**Made permanent in code 2026-10-25:** decision_gate.json now sends production, secrets/credentials, governance and destructive-git hits to the orchestrator (not the CEO). Only money, main and external sending reach him. A newer CEO order overrides an older Jira comment; write it into the ticket, don't report it to him. See agent/ORCHESTRATOR.md "Permissions are never the CEO's".
