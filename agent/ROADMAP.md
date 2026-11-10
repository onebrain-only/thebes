# Thebes program roadmap

Canonical repository: `onebrain-only/thebes`. Canonical checkout: `~/Desktop/Thebes-Canonical`.
Do not create another clone.

**This file holds the source order and the Product authorization gate, nothing else.**
The phase closures, the per-ticket acceptance records and the 2026-10-01 three-group
milestone were moved unchanged to
[`agent/archive/2026-11-10/ROADMAP-full-2026-11-10.md`](archive/2026-11-10/ROADMAP-full-2026-11-10.md)
on 2026-11-10. They are history and authorize nothing.

## Current position

- **Operating mode is not written here.** Read it from the store:
  `store.current_operating_mode()`. A mode written in a document goes stale.
- **Phases 1–5 are closed.** No infrastructure phase is current. Thebes changes are
  driven by real Product work only.
- **What to work on is the Jira board** (CEO 2026-11-10). No roadmap or plan file selects
  Product work.

Conversation memory is input to documentation work, never a canonical source. Fresh
controllers read `CLAUDE.md`, then this roadmap, then the sources linked below. A
missing source, missing mode record, or conflict is resolved in maintenance; it is
never interpreted as Product authorization.

## Canonical program document map

| Concern | Canonical source |
| --- | --- |
| Source order, gates, the Product authorization record | this file |
| How the orchestrator works | `agent/ORCHESTRATOR.md` |
| How review works | `agent/REVIEWER.md` |
| Ticket lifecycle, board, branches, Done | `agent/WORKFLOWS.md` |
| Dated CEO orders and settled decisions | `agent/DECISIONS.md` |
| Empirical operational lessons | `agent/LEARN.md` |
| Program chronology and evidence checkpoints | `agent/history/program-chronology.md` |
| Seats and authority | `agent/state/registry/seats.json`, `.claude/bindings/`, `agent/roles/` |
| Seat names | `agent/NAMING.csv` |
| Persistent State boundary and record contracts | `agent/state/README.md` |
| Live workspace-local mode, ownership and execution facts | Persistent State through `agent/state/store.py` |

Files under `agent/history/` and `agent/archive/` are evidence and ancestry, not current
authority. Product governance, Jira ticket text, role journals and runtime state keep
their existing ownership; this roadmap does not copy them.

## Program path

Status words are deliberate: **CLOSED** means the accepted baseline exists;
**CURRENT** means maintenance is active; **PENDING AUTHORIZATION** means no execution
may start; **FUTURE TARGET** means architecture direction, not implemented capability.

| Stage | Status | Purpose and exit condition |
| --- | --- | --- |
| Phase 1 — Agent Architecture, Waves 1–8 | CLOSED | Establish the role/seat model, routing, durable state, Jira-derived lifecycle, queues/claims, observability and inert learning. Closed at the accepted Wave 8 baseline and remediation checkpoints recorded in `agent/history/program-chronology.md`. |
| Post-Wave-8 Operational Hardening | CLOSED | Corrected real-operation defects, isolated Product from maintenance, established durable program memory, and removed permanent provider coupling. Closed after accepted provider-path remediation `ecac35d` and the final closure review. |
| Phase 2 — Tangible Operating Interface / Product Proof | **CLOSED 2026-09-14** | Objective: prove Thebes can operate real Product work safely and correctly. Accepted on the evidence in "Phase 2 closure" in the archived roadmap — KAN-183 carried a real work item from a CEO-supplied key to authoritative Jira Done through the flow, plus KAN-186's real PEER proof and the deterministic full-flow suites. One live dependency observation is deferred and non-blocking. Closure is not a claim of autonomous backlog execution, and no normal Product execution is authorized. |
| Phase 3 — Separate Listener | **CLOSED 2026-09-15** | Objective: separate intake from execution orchestration, so a CEO instruction enters Thebes without anyone invoking the Controller by hand. Accepted on the evidence in "Phase 3 closure" in the archived roadmap — a separately running loopback Listener with a durable, idempotent intent boundary that dispatches to the existing Controller in its own process and carries a correlated CEO decision back into the existing approval/continuation machinery. Closure is not a claim of remote access, authentication, or autonomous intake: transport is loopback-only and unauthenticated by design, and the Controller's authorization gate is unchanged. |
| Phase 4 — Codex → Listener integration | **CLOSED 2026-09-15** | Objective: make the Listener the normal external operational intake boundary, so a controller conversation expresses intent rather than invoking the Controller. Accepted on the evidence in "Phase 4 closure" in the archived roadmap — the front door moved and is enforced rather than documented, the executor firewall learned that the Listener exists, and the Controller's authority is unchanged. Closure is not a claim of authentication, remote access, or natural-language intake: transport stays loopback-only and the intent contract is unchanged from Phase 3. |
| Phase 5 — Listener evolves into Thebes Core | **CLOSED 2026-09-15** | Objective (§36): clean separation between Conversation, Canonical Company and Execution intelligence. Accepted on the evidence in "Phase 5 closure" in the archived roadmap — `agent/core` is the addressable composition of every responsibility §37 names, the Listener is its intake subsystem, and one derived lifecycle replaces the two records that could previously disagree. Closure is not a claim of a rewritten orchestration engine, of learning gaining influence, or of autonomous operation: Core reimplemented nothing, learning stayed inert, and every run is still one CEO-authorized work item. |
| Phase 6 — Knowledge scaling / RAG | FUTURE TARGET, DEFERRED | Add retrieval only when measured governance/history scale makes direct canonical reads a bottleneck. RAG is not authority and must preserve source provenance. No current evidence justifies implementing it now. |

The broader Phase 2–6 sequence is preserved in the historical target specification

## Authorization invariant

**DECISION/INVARIANT — Implementation complete != Product authorized.**

No controller may infer `PRODUCT_EXECUTION` from green tests, an empty maintenance
queue, finished documentation, or an implemented adapter. Only explicit CEO/lead
authorization can start bounded Product acceptance or normal Product execution. The
ordinary queue/pull path operates only inside an already authorized Product scope;
it cannot authorize that scope or autonomously choose its first ticket.


## Canonical Product acceptance protocol

This is the one canonical protocol. Other documents link here rather than restating it.

1. Obtain explicit CEO/lead authorization for bounded acceptance and record its
   reference here with exactly one explicitly selected existing ticket. Do not infer
   or autonomously select the ticket.
2. Run only that ticket under controller observation. Do not pull a next ticket,
   burn down a backlog, or broaden the accepted scope.
3. Preserve normal claim, ownership, continuation, lease, review and lifecycle rules.
4. If a Thebes/workflow defect appears, stop Product work and return to
   `SYSTEM_MAINTENANCE`; do not start another wake while transitioning.
5. Record result and evidence here. Failure or incomplete work leaves normal Product
   execution unauthorized.
6. After success, stop unless separate explicit CEO/lead authorization permits normal
   Product execution. Acceptance-only authorization never grants the next ticket.


## Phase and mode exit rules

- A completed slice does not close a phase.
- A phase closes only through an explicit recorded decision against its exit criteria.
- A mode transition changes only the mode record and must preserve Product lifecycle,
  ownership, review, dependencies and interventions.
- If documentary sources conflict with runtime state, remain/return to maintenance and
  reconcile; do not normalize toward Product execution.
- Future phases may be refined by evidence, but may not be silently promoted to current
  fact or implementation.


## Authorization record

`agent/controller` reads the three lines below. The last recorded exact-ticket
authorization (KAN-368, 2026-09-30) was consumed on completion; a standing grant is a
Persistent State record (`store.active_product_authorization`), not a line in this file.

PRODUCT_EXECUTION_AUTHORIZED: NO
Selected ticket: KAN-368
Authorization reference: CEO 2026-09-30 Ready-queue instruction; sole Ready ticket KAN-368, same frontend-1 continuation. CONSUMED.
