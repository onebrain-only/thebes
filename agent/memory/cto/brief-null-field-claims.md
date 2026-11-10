---
name: brief-null-field-claims
description: Briefs about Persistent State repeatedly assert a field is empty/unset when it is set — re-read through the store API before ruling on any "X is absent" premise.
metadata:
  type: feedback
---

Never rule on a brief's claim that a Persistent State field is null, empty or missing. Re-read it
through `store.read` / `store.evidenced_executors` / `validate.py --check` first.

**Why:** three consecutive briefs (2026-09-20, 2026-09-21) on the same seven review records each
carried wrong measurements, two asserting a field was empty when it was set — `validation_route`
reported as `None` on KAN-285/323/331 when it was `qa`/`self`/`self`, and `KAN-292`'s
`work_effort`/`required_capability` reported null when both were set. Hand-rolled JSON scans and
stale validator output were the cause both times. Had I accepted either, I would have designed a
mechanism for a blocker that did not exist (see `T-088`, `T-089`).

**How to apply:** when a brief's premise is "this is absent, so build a way around the absence",
treat the absence itself as the first thing to verify. Check revisions too — identical revisions
across two readings prove the record did not change, so the reading did. Also confirm the *reason*
a value is absent: `executor_evidence` is written by `store.release`, not by the receipt path, so
an item still holding ownership can still be evidenced truthfully rather than needing rescue.

Related: [[identity-columns-profile-vs-auth-uid]].
