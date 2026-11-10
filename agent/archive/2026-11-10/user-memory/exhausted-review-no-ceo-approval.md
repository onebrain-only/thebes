---
name: exhausted-review-no-ceo-approval
description: "CEO 2026-10-22: an exhausted review or a permission refusal must not reach him for a blind 'accepted'; Thebes decides by code, the orchestrator otherwise"
metadata:
  type: feedback
---

CEO 2026-10-22 ("We still have no benefits from Jev. This kind of message should go and get approved directly"), after the orchestrator asked him to say "موافق قبول KAN-602" (review exhausted after 4 cycles, only the Codex QA check failing on a locale/theme limit) and reported a permission refusal on a PO edit of KAN-622.

**Why:** he approves unread, so such approvals protect nothing and cost him attention; Jev (the decision gate) was supposed to make those calls. [[ceo-delegates-decisions]] already said so.

**How to apply:** `agent/execution/exhaustion.py` accepts such a ticket by code (coverage limit, no defect wording, all other checks passing) and writes the unverified part on it; defect or unsure goes to the orchestrator, never to the CEO. A refusal or a brief the linter rejects is a Thebes fix (the linter now reads "exit 0" loosely and splits "A and B" run checks), not a CEO message. This supersedes the chat-approval habit of [[ceo-approves-in-chat]] for exhausted reviews; keep that one for money, secrets, main and sending outside. Only those four reach him.
