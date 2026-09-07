---
name: runbook-authoring
description: Write or amend a standing multi-step procedure document — a runbook or SOP like agent/WORKFLOWS.md — that other agents follow repeatedly, unlike a one-off prompt or brief. Use when authoring or editing a lifecycle, a review gate, a handoff rule, a transition table, or any numbered procedure meant to outlive the task that produced it. Distinct from writing-for-agents, which covers a single act; this covers a document a different agent, with no memory of today, must execute correctly weeks from now.
---

# Runbook Authoring

`writing-for-agents` is scoped to a prompt or a brief for one act. `agent/WORKFLOWS.md` is
neither — it is a standing procedure a different agent runs cold, on a different day, with
no memory of the conversation that produced it. Nothing in the 74 repo skills or the ~450
installed ones is shaped for that specifically; the nearest public material (PagerDuty's
incident-response runbooks) is incident-shaped, built for a crisis with one clock running,
not for a lifecycle a board runs every day for months. This is authored from what actually
went wrong in `WORKFLOWS.md` itself, not adopted from an external framework.

Everything in `writing-for-agents` still applies underneath this — the information
hierarchy, steps versus reference, leading words, pruning. This skill adds what's specific to
a document that must stay correct **across many separate future readings by agents who were
not there when it was written.**

## Rules specific to a standing procedure

1. **A measured fact lives in exactly one place; everywhere else points at it.** A number
   that came from running a command — a test count, a file count, a line budget — is a
   snapshot, and a snapshot copied into a second document is a second thing that can go
   stale independently of the first. Cite it ("see `X` for the current count") rather than
   restate it. If restating is unavoidable, tag it with the date and command it came from, so
   a reader can tell a live figure from an inherited one at a glance.

2. **Every non-obvious rule carries its `why`, not just its `what`.** A rule with no reason
   attached reads, to a future editor with no memory of the incident, as ceremony — and
   ceremony is what gets quietly deleted during a cleanup pass. State the incident or the
   defect the rule closes, in one sentence, next to the rule.

3. **Every step names who executes it and who verifies it, as two different cells, not one.**
   A step that only says what happens invites the wrong seat to run it or nobody to check it.
   The review-gate table and the transition table in `WORKFLOWS.md` §1/§3 are the pattern —
   copy its shape, don't invent a new one.

4. **Version the rule, not just the document.** A document-level "last updated" date tells a
   reader the file changed; it doesn't tell them *which* rule changed or why theirs might now
   be stale. Where a rule was added or amended under a specific decision (a `G-NNN`, a ticket
   key), cite it inline so a reader mid-procedure can tell whether the ground shifted under
   the exact clause they're relying on.

5. **Dry-run the procedure against a real past incident before publishing it.** Don't ask "is
   this rule clearly worded" — ask "would this rule, as written, have caught the thing that
   already went wrong." A rule that reads well but wouldn't have caught its own motivating
   incident is decoration.

## Case study — the failure this skill is built to close

**A `flutter test` figure (103 tests / 9 files) was correct when first measured, then
transcribed into five separate documents instead of cited from one.** The tree moved to
106/10 and each copy went stale independently; five different agents each tripped on the
mismatch and fixed their own copy separately, at five different times, none aware of the
other four. `analyst`'s diagnosis of the root cause — *"a measured figure was transcribed
into five documents instead of cited from one"* — is rule 1 above, named after the fact
instead of before it.

Rule 1, applied at the time `WORKFLOWS.md`, `CONTRACT.md`, `DECISIONS.md` and the rest first
needed that figure, would have put the number in one place (the ticket or status entry that
measured it) and pointed the other four at it. That is the difference between a fact that
goes stale once and one that goes stale five times on five different days.

## What this does not cover

This skill governs the document, not the ticket. A stale number *inside a single ticket's
acceptance criterion*, or a criterion nobody can satisfy, is `[[task-readiness]]`'s territory,
not this one — see its case studies for the boundary the other direction.
