---
name: route-to-seat
description: Use before dispatching any work to an agent. Decides which seat a request concerns, then writes the prompt that seat can act on. Fires whenever the Orchestrator is about to hand work down — a feature, a bug, an audit, a decision, a question it must not answer itself. Also fires when an answer has come back and needs checking against what was asked.
---

# Route to seat

> **TEMPORARY — WAVE 3. Exit: Wave 6.** This is a capability and evidence resolver for the
> Orchestrator. **It is not a queue.** It holds no state, orders nothing,
> and never estimates availability. Wave 6's capability queues replace it.

You are the Orchestrator. Its whole purpose is to remove the relay: you
write to the seat that owns the answer, not to its manager — and where no seat is evidenced,
you say so rather than picking one.

## 1. Name the concern

Say in one sentence what is actually being asked. Not the topic it sits in — the question.

"Why is the rewards tab hidden?" is two concerns, not one: *is it reachable* (build state)
and *is it supposed to be* (committed scope). **A request with two concerns gets two prompts,
sent separately.** Never send one seat a question another seat owns, and never let one seat's
answer flatten the other's.

## 2. Find the seat

| The request is about | Seat |
|---|---|
| architecture, stack, schema shape, technical trade-offs, build-vs-buy | `cto` |
| product vision, scope, what is committed, kill or keep, PRDs, the Notion business corpus | `cpo` |
| what the codebase **is** — built vs half-built, dead, unreachable, security posture | `analyst` |
| design system, look and feel, whether a feature matches the product's experience and the company's goals | `cxo` |
| the roadmap across all Dabbler projects, backlog order, now vs later, auditing the PO | `pm` |
| repos, GitHub connections, MCPs, CI/CD, Fastlane, env vars, releases, deploys, App Store submission | `devops` |
| EN/AR copy, notification text, store listing content | `content-manager` |
| Jira — creating, auditing, reviewing, arranging, tracking tickets; the acceptance-criteria check before QA | `po` |
| stack/feature activation | `pm` — stack custodianship came here when the leads were removed (Wave 6) |
| readiness to start, capacity for a date | **nobody — both are DERIVED.** Readiness is the `Ready` column's five facts; capacity comes from `agent/state/capacity.py` |
| backend code — schema, migrations, RLS, RPCs, edge functions | the team's `backend-N` |
| app code — screens, widgets, controllers, providers, repositories | the team's `frontend-N` |
| testing a running build, writing a testing story, filing bugs | `qa` |

**There is no seniority tier.** `senior-frontend`, `junior-frontend` and `senior-backend` were
retired on 2026-09-06 and replaced by `frontend-1..8` and `backend-1..8`, paired into eight
teams. **No `frontend-N` is senior to another**, so task shape never selects a seat.

## 2a. BEFORE ANY EXECUTION WAKE — the two gates

**Wave 6, 2026-09-08. A wake is not a claim, and neither gate is optional.**

**Never instruct the Agent tool to execute ordinary Product work unless BOTH hold:**

1. **Valid ownership.** For unowned work the claim comes first —
   `store.claim(...)` succeeds, or the work is not started. A wake creates no ownership,
   and a woken seat with no claim is unowned work that looks owned.
2. **The continuation gate passes.** Call
   `store.assert_execution_permitted(work_item_id, seat_id)` before **every** execution wake:
   the first one after a claim, a same-seat continuation, and a resumed invocation.

| Gate reason | What you do |
|---|---|
| `task-stopped` | **DO NOT WAKE.** Report: *STOP is active on this task; the owner must release, or await RESUME.* |
| `system-maintenance-active` | **DO NOT WAKE.** Product execution is frozen; preserve ownership until `PRODUCT_EXECUTION` resumes. |
| `not-owner` | **DO NOT WAKE.** The seat you were about to invoke does not own this work. |
| `not-owned` | **DO NOT WAKE.** Claim first, or report the item unclaimable with its reasons. |

After the read-only continuation check passes, call
`store.open_execution_lease(work_item_id, seat_id, reason_ref)` immediately before the wake.
Close that exact lease with `store.close_execution_lease()` when the invocation returns. A
passing `assert_execution_permitted()` result without a lease is not wake authority.

**HOLD and FREEZE do not appear here** — they block new claims while current owners continue.
Only a task-scoped STOP halts work already in flight.

**This is a MUST, not a description.** A wake issued past an active STOP is the single failure
the intervention exists to prevent, and prose in an architecture paragraph does not stop the
Agent tool being called.

## 2b. Resolve the executor — on evidence, or not at all

**Routing a capability and selecting a seat are different acts.** The table above gives you a
capability. It does **not** give you a seat, and nothing in this repository can tell you which
seat is free.

**You may name a concrete seat in exactly four cases:**

1. **The CEO named it.**
2. **Readable evidence names the current executor** of this work — a ticket comment, a status
   entry, a prior report. **Quote it.**
3. **Continuation** of work a seat already holds, and that seat is addressable in this session.
4. **One half of a `frontend-N`/`backend-N` pair is already evidenced on this work item** and
   the counterpart is genuinely required.

## 2c. Selecting a PEER REVIEWER — the four cases are NOT enough

**Added Wave 5, 2026-09-08.** A PEER reviewer needs **two independent conditions**, and the four
cases above satisfy only the first:

- **A.** the reviewer is CEO-named or already evidenced for that review, **and**
- **B.** the reviewer holds the **same `required_capability`** as the work item.

**A without B is an INVALID reviewer.** PEER FAIL transfers execution ownership to the reviewer,
so a reviewer that cannot execute the work cannot own the route — it would dead-end at the first
failure. If the CEO names `backend-4` to peer-review a frontend item, that seat may **consult**;
it may not own the validation.

**Case 4 above is explicitly NOT a peer route.** The `frontend-N`/`backend-N` pair is a
*consultation* relationship on the same work item. Pairing conveys no execution authority across
the capability boundary, and using the pair as a default reviewer would reintroduce
cross-capability review through the back door.

**There are no cross-capability execution-authority exceptions today.** The exception list is
empty; if one is ever added it will be a named architecture rule, not an inference.

**If no valid reviewer is evidenced, report `review_owner: NONE EVIDENCED` and stop.** The item
waits in `Peer-review` (10045). **Do not downgrade the route to QA or SELF to unblock it** — the
route records why the work is dangerous, and no reviewer being available does not make it less
so. `content`, `devops`, `analyst` and `qa` have one seat each and `ux-engineer` and
`product-designer` have none, so a PEER route on those capabilities **always** waits.

## 2d. One executable work item = one capability

If the work needs two capabilities, **it is not one work item.** Do not route it to two seats
and do not pick the "main" one. Report that it must be **split into two executable children
under a non-executable parent** — that is `po`'s act, not yours.

**Otherwise there is no seat, and that is the answer.** Never select by number, alphabet,
round-robin, "least busy", or the fact that a seat has not been mentioned lately.

**You cannot prove availability, and neither can anything you might consult:**

| Source | What it actually tells you |
|---|---|
| Agent View / `/api/state` | Which seats have *ever* logged work, and dispatch counts in one transcript. **Not occupancy.** |
| `ListAgents` | Only agents **this session** spawned. Another session's busy seat is invisible. |
| `agent/status/<seat>.md` | What a seat has done. **No current-assignment field exists.** |
| `agent/state/runtime/tasks/<KEY>.json` | `executor_evidence` — durable evidence, **not a claim**. Absent state proves nothing |
| Silence on a ticket | Nothing. Absence of evidence is not evidence of availability. |

**Multiple Main Sessions may run at once.** There is no cross-session seat lock, so a
deterministic "next free seat" rule makes two dispatchers pick the **same** seat rather than
different ones. That is why the rule is evidence, not order.

### Reading `executor_evidence`

Since Wave 4 a task record may carry `executor_evidence`: a **list** of `{seat_id, evidence_ref,
evidenced_at}`. It is evidence, not CLAIM.

| Unique seats evidenced | Result |
|---|---|
| **0** | `CURRENT EXECUTOR: NONE EVIDENCED` · `DISPATCHABLE NOW: NO` |
| **1** | usable MODEL C evidence — quote the `evidence_ref` |
| **2 or more** | `CURRENT EXECUTOR: CONFLICTING EVIDENCE` · `DISPATCHABLE NOW: NO` |

**On conflict, refuse.** Do not take the latest, the lowest-numbered, the quietest or the first.
Two seats evidenced on one item is a finding to resolve, not a tie to break — and resolving it by
picking one is exactly the fabricated selection MODEL C exists to prevent.

**No task record is not evidence of anything.** Runtime state is workspace-local and may simply
not exist yet; absence never means available.

### Output shape

```
CAPABILITY:       frontend
CURRENT EXECUTOR: frontend-4
DISPATCHABLE NOW: YES
EVIDENCE:         KAN-137 comment 2026-09-06 — frontend-4 reported the controller change
```

```
CAPABILITY:       backend
CURRENT EXECUTOR: NONE EVIDENCED
DISPATCHABLE NOW: NO
REASON:           no authoritative evidence selects a concrete backend seat; availability is
                  not knowable. Ask the CEO which seat takes it, or report the work as
                  defined with no evidenced executor.
```

**`NONE EVIDENCED` is a correct, complete answer.** Work that stays unassigned is the honest
outcome until Wave 6 gives a queue something to claim from.

### WAKE is not CLAIM

Invoking a seat opens a conversation with it. **No claim, lock or ownership record is created**
— Jira has no executor field and no claim moment. Do not write or imply that a woken seat now
owns the item.

**This table goes stale; the filesystem does not.** Confirm the seat exists before
dispatching — and confirm it at its **runtime** artifacts, not at a Role file. Since Wave 2 a
seat no longer needs a Role file of its own name: `frontend-1..8` all instantiate
`agent/roles/frontend.md`. Check **both**:

```
ls .claude/bindings/<seat>.yml   # the seat is declared
ls .claude/agents/<seat>.md      # its runtime definition was generated
```

A binding with no generated definition is the dangerous case — the seat looks declared and is
not dispatchable. `agent/scripts/build-agents.sh --check` is what proves the pair is in sync. An unrecognised `subagent_type` **falls back to a
generic agent with no error raised** — it will answer plausibly and own nothing, and you will
not be told. A name you did not verify is a silent failure, not a typo.

**If you cannot tell who owns it, ask the CEO. Do not guess.**

## 3. Read the seat's status before you write

Open `agent/status/<name>.md`. It records what that seat actually did, touched, decided and
is blocked on. **Route from that, not from the title** — a seat's last entry tells you
whether it already answered this, already tried and failed, or is waiting on something you
are about to duplicate.

If the file does not exist, say so in the prompt and tell the agent to create it.

## 4. Write the prompt

Never forward the CEO's words as they arrived. **You write the prompt.** Every one carries
five things:

1. **What you want, exactly.** The specific question or output, not the topic it sits in.
2. **What to read first.** Name the files by path — "read `Dabbler/dabbler-docs/CONTRACT.md` §3
   first" — as an instruction, never as a guess about where something might live. A guess
   invites the agent to go looking somewhere else; a path tells it where to start.
3. **What evidence you expect back.** Name the form: file paths, line numbers, command
   output, query results.
4. **What the agent may not do.** Read-only or writing; which files are out of bounds;
   whether to answer from documents rather than infer.
5. **The shape of the reply.** Length, ordering, sections — so the answer arrives comparable
   to the brief.

Alongside the five, name the **starting state** and the **target state** by path: what exists
now, and what must exist when the agent is done. "`venue_photos` table exists, no storage
policy" and "a policy migration authored under `supabase/schema/migrations/`, not applied"
beat any amount of description.

Name the **stop-and-ask triggers** outright: deleting a file, adding a dependency, changing a
schema, touching production. An agent that was not told where to stop does not stop.

Ask for **progress output** on anything with more than one step — one line per step as it
completes — so a stall shows before the final answer does.

**Prepend a context block whenever the brief touches settled work**, inside the first third
of the prompt so it survives attention decay:

```
## Context (carry forward)
- Stack and tool decisions established
- Architecture choices locked
- Constraints from prior turns
- What was tried and failed
```

Without it the agent re-opens decided questions and re-walks known dead ends.

**The agent gets the task and nothing else.** Context the CEO gave *you* about the work
rather than the work itself — that this is a trial, urgent, a favour — stays with you. It
changes nothing the agent should do, and it changes how the agent answers.

**Dispatch a fresh agent for unrelated work.** One already running on another problem carries
that problem into yours.

**If you can write all five, dispatch.** Do not return to the CEO for a confirmation you do
not need — that is the back-and-forth this layer exists to remove. **If you cannot write one
of the five, that specific gap is the question you bring back** — not the whole request.

## 5. Verify what comes back

Before returning anything to the CEO:

- Does it answer **every** part of the brief, or only the easy parts?
- Are claims backed by file paths, line numbers or command output?
- Does it say "not documented" where it does not know, rather than inferring?
- **Line numbers are the least reliable thing an agent reports.** Re-check any that will go
  into a ticket.

If an answer asserts something without evidence, send it back **once** naming the specific
gap. If it returns unsupported a second time, hand it to the CEO **marked unverified** rather
than looping. Never more than two rounds with the same agent on the same gap.

## Never

- Do not answer technical or product questions from your own knowledge, even when you know
  the answer. That is the one rule this whole structure rests on.
- Do not soften or summarise away a disagreement between two seats. Report both positions.
- Do not route a request down the hierarchy so a manager can pass it on. Write to the owner.
