<!-- ============================================================
FILE STATUS: EMPTY — SPEC ONLY
Created with its specification but no content. Filled by its owning agent.
Delete this banner when the file is first genuinely filled.
============================================================ -->

# agent/status/app-store-submission-fixer.md — app-store-submission-fixer status log

**Owner:** `app-store-submission-fixer` — **this agent, and only this agent, writes here.**
Every other agent reads it. The master-analyst reads it to reconcile
`agent/STATUS.md`; it does not write here.

**Purpose:** The detail behind this agent's work. `agent/STATUS.md` is the summary
the PO reads; this file is where the specifics live.

---

## SCOPE

Apple App Store review rejections, App Store Connect metadata, Info.plist
purpose strings, and submission blockers.

## THE RULE

The status entry is **part of the task, not offered afterwards.** It is the last
thing written before the agent closes, and the agent may not report DONE without
it. A task that ends in a refusal, a diagnosis, or an unanswered question still
gets an entry — those are the ones most likely to be skipped and most needed.

## FORMAT — newest first

```
## YYYY-MM-DD — KAN-NN — Title
**Task:** what was asked
**Did:** what actually changed, with file:line or commit
**Did not:** what was out of scope or deliberately left
**Not verified:** stated explicitly, never omitted
**Handoff:** which agent picks this up, or none
```
