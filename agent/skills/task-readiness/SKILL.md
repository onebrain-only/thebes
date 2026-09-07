---
name: task-readiness
description: Definition-of-Ready check for a decision, bug, or backlog item before it becomes a Jira ticket, or before a drafted ticket is judged in review. Use whenever writing acceptance criteria, whenever a criterion's number or scope feels assumed rather than measured, or whenever deciding if something is a task yet at all. Applies INVEST and Example Mapping's rule/example/question split so an unmeetable or untestable criterion is caught before it reaches a developer or a reviewer.
---

# Task Readiness

Task analysis — turning a request into work with testable criteria, and recognising when
something is **not yet a task at all** — is this seat's first duty (`AGENTS.md` §1, `G-023`).
This skill is how that duty gets done, rather than done by instinct.

Two frames, both real and citable, neither owned outright — adopt them, don't restate them
as trivia:

- **INVEST** (Bill Wake, 2003) — six letters, six ways a single story can fail to be workable.
- **Example Mapping** (Matt Wynne, cucumber.io, 2015) — a structured conversation using four
  card colours: **yellow** (the story), **blue** (rules — acceptance criteria), **green**
  (examples — concrete instances of a rule being satisfied), **red** (questions — things
  nobody in the room knows yet).

You are not running a live 25-minute workshop with a table of people. You are one seat,
usually alone with a decision or a bug report. The colours still do their job as a solo
discipline — a checklist you run against the thing before it becomes a ticket.

## The check

For a decision, bug, or backlog item that might become a ticket:

1. **State it as one line — the story.** What is being asked, in a sentence a developer
   with no memory of this conversation could read cold.

2. **List its rules.** Each rule is one acceptance criterion. Split a compound rule into two
   rather than writing an "and" inside one criterion — that is what §7's blue-card-density
   heuristic below is for.

3. **For every rule, produce one concrete example of a correct diff or action that satisfies
   it — before the ticket is written, not after someone claims it's done.** This is the
   green card, and it is the sharpest tool here: **if you cannot construct an example that
   both matches the rule's wording and is achievable in the codebase as it stands, the rule
   is wrong, not the future developer.** Fix the wording, narrow the scope, or don't write
   the ticket yet.

   This catches two distinct failures, and they are not the same fix:
   - **The rule blocks the only correct answer.** You try to sketch a compliant diff and the
     rule's own arithmetic forbids it. The rule is measuring something falsely.
   - **No example exists anywhere in scope.** You look for where the rule could ever be
     satisfied and there is nowhere — the ticket is demanding work that doesn't apply here.

4. **Write down what you don't know — the red card — instead of guessing at it.** A question
   captured is a known unknown; a question silently resolved by assumption is an unknown
   unknown wearing a checkmark. A question that only the `pm` or a `team-lead` can answer
   goes to them (`WORKFLOWS.md` §4) — it does not get filled in with a plausible-sounding
   number.

5. **Run every rule through INVEST** and name which letter fails when one doesn't fit:
   - **Independent** — does it overlap another rule, or must they land in one order?
   - **Negotiable** — is it a fixed contract when it should leave room for the developer's
     judgment, or vice versa?
   - **Valuable** — does passing it actually prove something a stakeholder cares about?
   - **Estimable** — can the owning `team-lead` size it well enough to give a `due_date`?
   - **Small** — is it a few days of work, not a program?
   - **Testable** — literally: could you write the command or the diff review that checks it?

6. **Read the density, not just the content.** Wynne's heuristic, restated for a ticket
   instead of a table of cards: a ticket with more open questions than answered rules is not
   ready to write — table it and escalate. A ticket with many rule cards and few examples is
   probably two tickets wearing one summary — split it before writing acceptance criteria,
   not after a developer asks which half to do first.

## Case studies — what this would and would not have caught

Four real ticket-analysis failures from Phase 0 (2026-09-05/06), checked against the steps
above:

- **`KAN-122`'s line budget permitted one changed line per file; three files needed two
  imports each.** Step 3, run honestly, catches this: sketching the compliant diff for those
  three files immediately hits the one-line ceiling. The rule blocked its own correct answer.
  **Caught.**

- **`KAN-126` demanded a demonstration commit pair on a P0 ticket, but no Phase 0 ticket
  touches generated output.** Step 3's second failure mode — no example exists anywhere in
  scope — catches this directly: looking for where the rule could be satisfied turns up
  nothing in the ticket's own phase. **Caught.**

- **`KAN-123` originally read "every pair of the 80 top-level entries" — 3,160 comparisons,
  ungradeable as stated.** Step 5's Testable check catches this: could you write the command
  that checks 3,160 pairs and read its output in finite time? No — restate as a per-entry
  collision set, which INVEST's Testable letter and Example Mapping's green card both accept.
  **Caught.**

- **A stale `flutter test` figure (103/9) was copied into five separate documents instead of
  cited from one, and drifted from the tree's actual 106/10.** This is not a ticket-criterion
  failure — it is a standing-document citation failure, and nothing in this skill's steps
  touches a document that isn't a ticket. **Not caught here — see `[[runbook-authoring]]`**,
  which owns single-sourcing a measured fact across documents that outlive one task.

## What this replaces

`to-tickets` and `to-spec` gesture at this territory but are both marked `[L]` in the
reflex table (`disable-model-invocation: true` — dead as a reflex) and neither carries the
rule/example/question discipline; this skill is the working replacement for the part of
their intent this seat actually needs, not a restatement of either.
