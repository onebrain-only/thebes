---
name: reread-acs-before-verdict
description: Re-read the Jira ticket immediately before recording a review verdict, not only at review start — ACs move mid-review on fast incidents
metadata:
  type: feedback
---

Before calling `store.record_review_result`, **re-fetch the ticket description**. Reading it at
the start of the review is not enough.

**Why:** On KAN-175 (2026-09-10) I read the ticket, spent a long review verifying ACs 1–5
against production and a disposable Postgres, and recorded PASS. While I was working, `po` had
added **AC6 and AC7 as FAIL findings** from another backend seat's parallel review. AC7 was a
real exploitable defect (`LIMIT 1` meant only the *first* identity argument was checked, so a
function guarding arg 1 and leaking arg 2 was cleared). I passed work that did not meet its
criteria, and briefly transitioned it to Done. I only caught it because the Jira transition
response echoed the current description back at me — pure luck.

**How to apply:** On any ticket, but especially a security incident with multiple seats working
in parallel, the last action before the verdict is a fresh `getJiraIssue`. Diff the ACs against
what you actually reviewed. If they moved, the review is not finished.

Two related traps from the same incident:
- A verdict recorded in Persistent State is **hard to retract**. `record_review_result` refuses
  once settled, and `peer_fail_transfer` refuses when `executor_evidence` is empty (no
  `previous_owner` can be set). Getting it right the first time matters more than usual.
- When both correction paths are blocked, the honest move is a **`stop` intervention**
  (`store.create_intervention('stop', ...)`, lowercase kind, `reason_ref` must be a short
  identifier pointing at the status log — not narrative). That flips `completion_reasons` to
  `['task-stopped']` and prevents anyone acting on the bad verdict.
  **Clearing it is the creator's, not the Orchestrator's** — the CEO may clear any, but a seat
  clears its *own*. On KAN-175 team-lead initially told me to leave mine for it to clear and
  then corrected itself. Hold a STOP until the *recorded* condition is resolved, and say
  plainly if the reason to keep holding has changed to a different one.
- **Never fabricate state to force a transfer through.** `executor_evidence` is appended *only*
  in `release()`, so a seat that lands work without releasing leaves it empty and blocks
  `peer_fail_transfer` (no `previous_owner` derivable). The fix is for an authority to record
  the true entry — not for me to invent one. Refusing is why the record ended up correct rather
  than merely plausible.
- `evidence_ref` caps differ by field: `record_review_result` took ~1,900 chars, but the one
  written into `executor_evidence` wants a short identifier. Put narrative in the status log
  and reference it.

See [[peer-review-evidence-discipline]].
