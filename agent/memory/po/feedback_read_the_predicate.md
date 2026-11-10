---
name: feedback-read-the-predicate
description: "A reason code emitted because the CALLER omitted an argument is not a finding about the data — read the predicate function before trusting its output, and re-measure a reported null field before setting it"
metadata:
  type: feedback
---

Before acting on a reported-null Persistent State field, **re-measure it yourself**, and
before trusting any `claimable()` / `eligible()` / reason-code output, **read the function
that produced it.**

On 2026-09-20 team-lead reported `required_capability = None` on four peer-review tickets and
asked me to set it. It was already set on all of them (po provenance, 2026-09-18), and
board-wide only 6 of 194 records were null — none in that queue. Writing as asked would have
bumped five revisions and written fresh provenance over good provenance for no change.

The thing that fooled us both: `queue.eligibility_reasons(task, jira=None)` appends
`unverified-jira` **unconditionally whenever the caller passes no live Jira facts**
(`agent/state/queue.py:75-83, :103` — the docstring states it: "Omitting them is not treated
as a pass"). So a bare `claimable(t)` returns False for *every* task on the board regardless
of its data. Two independent agents read that False as a data defect.

**Why:** a reason code has two possible authors — the data, or the call. Only one of those is
a finding. A predicate with an optional evidence parameter will usually fail closed when you
omit it, which is correct behaviour and useless as a measurement.

**How to apply:** when a queue/eligibility/claimability check returns a blocking reason,
(1) open the function and find the line that emits that exact string, (2) check whether it is
reachable purely from how you called it, (3) only then report it as a finding. And when asked
to write a field somebody else measured as missing, read the record first — the cheapest
possible check, and the one that prevents a spurious write.

Corollary worth keeping: the blocker is often one layer below where the reported symptom sits.
Here the true blocker was `open_review_context` failing on empty `executor_evidence`, which
`resolve_review_owner` depends on — fixing capability would have changed nothing.

Related: [[unwired-vs-orphaned]] (same family: the measurement was right, the conclusion was
not).
