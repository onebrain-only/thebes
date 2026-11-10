---
name: feedback-standard-by-construction
description: A standard that depends on nobody remembering it is the only kind that survives — build the reminder into the artifact that will trigger the drift, not into a discipline to be recalled later
metadata:
  type: feedback
---

team-lead, 2026-09-18, while closing the documentation rollout: "a standard that depends on
nobody remembering it is the only kind that survives" — said of the same species of problem as
[[feedback_hit_box_bounds]] (D-039's false padding-is-a-wall comment surviving uncorrected because
nobody re-derived it from scratch).

**The rule:** when closing a ticket whose correctness is time-bound — a doc that accurately
describes *today's* code but will go stale the moment a dependent ticket lands — do not just note
the staleness risk in the closing comment and move on. Post the forward-note on the *other*
ticket, the one whose landing is what invalidates the first. The note must live where the person
who causes the drift will see it, not where the person who already knows about it will re-read it.

**Why:** a note left only on the closed ticket (KAN-310, KAN-311) is read by nobody once the
ticket is Done — it is exactly the shape of "documented in a place nobody returns to" that let
D-039's false comment survive. A note on the ticket that will *cause* the drift (KAN-319, KAN-320)
is read by whoever executes that ticket, at the moment the drift is created, when fixing it costs
one edit instead of a rediscovery.

**How to apply:** applied directly 2026-09-18 — closing `KAN-310`/`KAN-311` (TopBar/EmptyState doc
pages, accurate to current code) while `KAN-319`/`KAN-320` (the code changes that will make those
same pages stale) were still open. Rather than trust memory or a status-file line to catch the
staleness later, posted a comment on `KAN-319` and `KAN-320` themselves naming the exact doc file,
the exact stale sentence, and what it must become. Generalize: any time a closure's accuracy is
conditional on another open ticket's *not yet* having landed, that open ticket is where the
follow-up note belongs — not a memory entry, not a status log, the ticket that will trigger it.
