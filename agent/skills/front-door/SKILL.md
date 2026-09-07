---
name: front-door
disable-model-invocation: true
description: The skills only you can start, and when to reach for each.
---

# Front door

Nine skills fire **only when you type them**. Agents cannot reach these — that is the
design, not a gap: each one needs intent that lives in your head, not in the repo.

Everything else routes itself. Each agent carries its own reflex table naming the
skills it should reach for, so you never pick a skill on an agent's behalf.

## Before work exists

| You want | Type |
|---|---|
| To be interrogated until an idea is sharp | `/grill-me` |
| The same, leaving ADRs and a glossary behind | `/grill-with-docs` |
| To design a recurring workflow worth delegating | `/loop-me` |
| The conversation turned into a spec, no interview | `/to-spec` |
| A plan broken into tickets with their blocking edges | `/to-tickets` |

**The usual order:** `/grill-me` → `/to-spec` → `/to-tickets` → `/implement`.
Skip straight to `/to-spec` when the thinking is already done and you only want it
written down.

## While work runs

| You want | Type |
|---|---|
| A spec or set of tickets built | `/implement` |
| To understand something rather than have it done | `/teach` |
| To say *that did not land, try again* | `/wait-what` |

## Looking at the codebase

| You want | Type |
|---|---|
| Deepening opportunities found and worked through | `/improve-codebase-architecture` |

## What routes itself — do not reach for these

Agents fire these on their own: `grill-po` (I grill you when a message describes
rather than directs) · `grilling`, `grill-peer` · `research`, `autonomous-investigation`
· `code-review`, `diagnosing-bugs`, `tdd` · `codebase-design`, `domain-modeling`,
`writing-for-agents` · every `cpo-*`, `cto-*`, and mobile-security skill · the
`dart-flutter` set and the Dart MCP server.

## Who to ask, when you would rather ask a person than a skill

| Question | Agent |
|---|---|
| *Does this idea fit the business?* | `cpo` |
| *How should this be built?* | `cto` |
| *What is actually true about the codebase?* | `master-analyst` |
| *Is this ticket really done?* | `task-auditor` |
| *Ship it* | `version-control` |
