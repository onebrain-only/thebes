---
name: no-tickets-without-ceo-approval
description: "CEO 2026-10-30: no NEW-SCOPE tickets without his approval (KAN-705/707 cancelled); D-046: tickets supporting existing work are fine"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-30T17:48:13.630Z
---

CEO 2026-10-30: "امسحهم ومتعملش تذاكر تاني من غير موافقتي". KAN-705/KAN-707 (Apple sign-in, created by PO unasked) are cancelled. No ticket is created by any seat without his approval.

**Why:** PO opened tickets he never requested (Apple access would have needed his Developer account).
**How to apply:** Tell PO/PM briefs not to create tickets; propose to the CEO first. Jira connector has no delete action, so deletion of 705/707 is left to him (comment left on both). Narrowed 2026-11-01 (D-046): the rule targets invented scope only. A ticket that supports existing work — a child, a blocker, or a defect on in-flight KAN work — is created without asking. See [[orchestrator-facts-and-orders]]. Related: [[po-no-followup-tickets]], [[order-is-approval]].
