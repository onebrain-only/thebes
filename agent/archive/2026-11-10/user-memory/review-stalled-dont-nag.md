---
name: review-stalled-dont-nag
description: "CEO 2026-10-21: do not message him on every review_stalled alert; keep working, he and Codex handle review"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-21T11:19:09.384Z
---

**Strengthened 2026-10-27 by [[autonomy-constitution]]:** a review_stalled alert never reaches him. On the claude channel the reviewer (Edfu) is woken by code, and Codex is not involved.


Stop telling the CEO "review is waiting" / pasting the Codex wake text on each review_stalled alert.

**Why:** it wastes his time and tokens; review is his and Codex's job.
**How to apply:** on review_stalled, silently restart the waiter and keep dispatching work. Only speak up if review is the real blocker for something (e.g. a dependent ticket cannot proceed at all). Reviewer questions still get answered within 15 minutes. See [[ceo-delegates-decisions]].
