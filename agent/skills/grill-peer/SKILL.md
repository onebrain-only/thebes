---
name: grill-peer
description: Grill another agent relentlessly to reach shared understanding before work starts or a result is accepted. Use when briefing a subagent, when a returned report is about to be acted on, when a ticket's acceptance criteria are ambiguous, or when you are the agent and your brief leaves a question you cannot settle by looking.
---

Interview a **peer agent** until you reach shared understanding. Same discipline as
`grilling`, aimed at a correspondent who can run commands instead of a human who
holds intent.

Map the work as a **design tree**: every decision branches into the decisions
hanging off it. Work the tree in **rounds**. The **frontier** is every decision
whose prerequisites are settled. Ask the whole frontier in one round, numbered,
each with your recommended answer. Wait for the reply. The answers reshape the
tree, push the frontier outward, and unblock the next round.

Format a round exactly as `grilling` does:

```
❓ **Q1** - **<title>**: <body, including options where they exist>

➡️ <your recommended answer>
```

Send rounds with `SendMessage`. One round per message.

## WHAT GRILLING IS NOT — WAVE 3 BOUND

**Grilling is asking, never handing over.** A grill may end with you understanding something
better. It may never end with someone else holding your work.

**Prohibited, however it is phrased:**

- *"take this ticket"* · *"implement this part for me"* · *"you do the migration"* —
  **delegation.** Return a structured routing request instead (`WORKFLOWS.md` §4.1).
- spawning anyone with `Agent` or `fork` to answer your question.

**The test is the work item, not the wording.** If the interaction would change who executes,
it is delegation. **Nothing in the harness stops you** — no binding restricts tools — so this
is a contract you keep, not a wall you hit.

**Which grills are open to you, in Wave 3:**

| Grill | Open? |
|---|---|
| Your **pair**, on the work item you both hold | **Yes** — temporary compatibility exception, exit Wave 6 |
| **`po`** on scope, acceptance, criteria | **Yes** — an authorised decision route |
| **`cto`** for a `G-028` confirmation | **Yes** — specifically authorised, unchanged |
| A **peer**, for a fact it uniquely holds | **Yes** — a question, and it stays a question |
| Any seat, for a **decision** outside those routes | **No** — raise an exception request; the Dispatcher redirects once |


## What changes when the peer is an agent

**A peer can look. A human cannot be asked to.** `grilling` forbids asking the user
for facts. That rule inverts here: your peer runs commands, reads the tree, and
queries the database. Ask it for **the measurement**, and ask it to say **how it
measured** — a number without its command is a claim, not evidence.

**Grill for evidence and reasoning, not intent.** A peer holds what it found and
why it concluded. Press on: the command behind each number, what it checked versus
inferred, what it could not verify, and which of its claims would change if one
assumption were wrong.

**Look before you ask.** Anything you can establish yourself, establish. A round
spent asking what one `grep` would answer wastes a turn and teaches the peer that
your questions are cheap.

**Verify the answer you get.** Re-measure the load-bearing ones. A peer answers
fluently whether or not it is right, and a confident wrong number that survives a
grill is worse than one that was never grilled.

## Escalate rather than decide

Some questions are the PO's: product intent, scope, priority, anything touching
production or cost. When the frontier surfaces one, **stop that branch and send it
up**. Keep grilling the branches that do not depend on it.

A decision made between two agents because neither wanted to wait is the failure
this whole system exists to prevent.

## Done

The frontier is empty: every branch visited, nothing silently assumed, every
load-bearing number carrying the command that produced it. Open questions belong
to the PO, and are named as such.

Then act — and say what you are acting on.
