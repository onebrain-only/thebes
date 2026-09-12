# Thebes program roadmap

Current as of 2026-09-12. Canonical repository: `onebrain-only/thebes`.
Canonical checkout: `~/Desktop/Thebes-Canonical`. Do not create another clone.

## Current position

**CURRENT FACT — MODE: `SYSTEM_MAINTENANCE`**
**CURRENT FACT — CURRENT PHASE: Post-Wave-8 Operational Hardening**
**CURRENT FACT — PRODUCT_ACCEPTANCE_STATUS: NOT AUTHORIZED / NOT STARTED**
**CURRENT FACT — PRODUCT_EXECUTION_AUTHORIZED: NO**

The current bounded step is this durable-documentation pass. It changes Thebes
governance only. It does not select Product work, alter Product Jira lifecycle,
touch Product code or production, begin acceptance, or implement an executor adapter.

Conversation memory is input to documentation work, never a canonical source. Fresh
controllers read `CLAUDE.md`, then this roadmap, then the sources linked below. A
missing source, missing mode record, or conflict is resolved in maintenance; it is
never interpreted as Product authorization.

## Canonical program document map

| Concern | Canonical source |
| --- | --- |
| Current position, program sequence, gates and next bounded step | this file |
| Durable shared architecture and operating context | `agent/PROGRAM_MEMORY.md` |
| Settled decisions and invariants, including rationale | `agent/DECISIONS.md` |
| Empirical operational lessons | `agent/LEARN.md` |
| Program chronology and evidence checkpoints | `agent/history/program-chronology.md` |
| Roles, seats and authority | `agent/AGENTS.md` and role contracts |
| Work movement, review and handoff mechanics | `agent/WORKFLOWS.md` |
| Persistent State boundary and record contracts | `agent/state/README.md` |
| Live workspace-local mode, ownership and execution facts | Persistent State through `agent/state/store.py` |

Historical files under `agent/history/` are evidence and ancestry, not current
authority. Product governance, Jira ticket text, role journals and runtime state keep
their existing ownership; this roadmap does not copy them.

## Program path

Status words are deliberate: **CLOSED** means the accepted baseline exists;
**CURRENT** means maintenance is active; **PENDING AUTHORIZATION** means no execution
may start; **FUTURE TARGET** means architecture direction, not implemented capability.

| Stage | Status | Purpose and exit condition |
| --- | --- | --- |
| Phase 1 — Agent Architecture, Waves 1–8 | CLOSED | Establish the role/seat model, routing, durable state, Jira-derived lifecycle, queues/claims, observability and inert learning. Closed at the accepted Wave 8 baseline and remediation checkpoints recorded in `agent/history/program-chronology.md`. |
| Post-Wave-8 Operational Hardening | CURRENT | Correct defects revealed by real operation, isolate Product from maintenance, establish durable program memory, and remove permanent provider coupling. Exit requires all accepted hardening slices complete and an explicit phase-closure decision; green tests alone do not close it. |
| Phase 2 — Bounded Product Proof / Acceptance | PENDING AUTHORIZATION | Prove Thebes against exactly one explicitly selected existing Product ticket under controller observation. Exit requires recorded acceptance success and explicit authorization for normal Product execution. |
| Phase 3 — Listener | FUTURE TARGET | Separate event/request/state ingress from controller conversation memory and ad-hoc polling. Exit criteria must be designed and approved before implementation. |
| Phase 4 — Controller-to-Listener integration | FUTURE TARGET | Controllers brief Thebes through the Listener; they do not brief a concrete executor directly. Exit requires provider-neutral context handoff to be demonstrated. |
| Phase 5 — Thebes Core | FUTURE TARGET | Evolve ingress into a core that owns orchestration, routing, context assembly, provider selection, lifecycle coordination, recovery and emergency handling behind stable interfaces. Exit criteria remain to be designed. |
| Phase 6 — Knowledge scaling / RAG | FUTURE TARGET, DEFERRED | Add retrieval only when measured governance/history scale makes direct canonical reads a bottleneck. RAG is not authority and must preserve source provenance. No current evidence justifies implementing it now. |

The broader Phase 2–6 sequence is preserved in the historical target specification
at `agent/history/thebes-target-architecture-specification.md` §§55–56. That file is
pre-Thebes and non-authoritative; only the phase direction is adopted here. Current
doctrine lives in this roadmap and `agent/PROGRAM_MEMORY.md`.

## Phase 1 history — Waves 1–8

| Wave | Accepted purpose | Status / evidence |
| --- | --- | --- |
| 1 | Reconcile documentary truth and remove competing or hard-coded authorities. | CLOSED. The current repository begins after this experimental history; use the frozen predecessor reference in commit `cd753d0`, not invented reconstruction. |
| 2 | Establish Role versus Seat and generated executor definitions. | CLOSED. Current Role/Binding/generator doctrine is in `agent/AGENTS.md`; detailed predecessor commits are outside this repository. |
| 3 | Establish direct routing, no-relay delegation and evidence-bound selection. | CLOSED, then ordinary selection was superseded by Wave 6 queues. Historical routing-request compatibility remains documented in `agent/WORKFLOWS.md` §4.1. |
| 4 | Add Persistent State, Execution Profile, routing/exception context and dependencies without duplicating Jira or Git. | CLOSED. Boundary and schema history are in `agent/state/README.md`; predecessor commit history is outside this repository. |
| 5 | Make Jira the lifecycle authority; derive validation; formalize Sprint and one-capability work items. | CLOSED at canonical baseline `cd753d0`. |
| 6 | Add capability queues, atomic claims, ownership, continuation gates, interventions, capacity and bounded seat expansion. | CLOSED at `0f4f805`. |
| 7 | Make Agent View reflect orchestration truth rather than transcript activity. | CLOSED at `e6e896a`. |
| 8 | Add advisory telemetry, retrospective and capability-scoped learning without creating authority. | CLOSED at `b1da48c`; wiring remediation `3a9eb3a`; later isolation/integrity correction `2c5bb1b`. |

This table records durable purpose, not every implementation detail. See
`agent/history/program-chronology.md` for checkpoints and verification limits.

## Current hardening work

Evidence baseline: `fe997bb` plus this documentation pass. The operational-hardening
test suite previously passed 38 isolated checks; this pass must re-run it and document
the observed result rather than inheriting that number silently.

| Area | State | Boundary / evidence |
| --- | --- | --- |
| Operating-mode isolation | IMPLEMENTED | `e3cf8c6`, `834b071`, `4948607`, `fe997bb`; claims and wakes are refused in maintenance, with wake authorization serialized by execution leases. Human authorization is still a governance gate, not authenticated by the setter. |
| Observation → investigation | IMPLEMENTED | `agent/state/operations.py` and operational-context tests distinguish reported conditions from explicit reproduction requests. |
| Reported environment authority | IMPLEMENTED | Operational context derives the primary target from the reported environment; local Flutter Chrome is not silently converted into browser automation. |
| Causal-surface validation | IMPLEMENTED | Diagnosis records causal/changed surfaces and derives required versus optional validation targets. |
| Shared program documentation | CURRENT SLICE | Roadmap, program memory, decision log, learning log, chronology and concise entry-point wiring. Exit: links and source order validate, classifications remain explicit, and no competing truth is introduced. |
| Executor/provider abstraction | REMAINING | Target is defined below. No adapter is implemented in this documentation pass. |
| Product acceptance | NOT AUTHORIZED / NOT STARTED | Protocol is canonical below. No ticket is selected. |

## Executor/provider target

**FUTURE TARGET**

```text
Thebes Controller
        ↓
Thebes Listener / Core context boundary
        ↓
executor/provider adapter
        ├── Claude Code
        ├── Codex
        └── future provider
```

Claude Code is an available provider, not a permanent architectural dependency.
Codex, Claude Code and future executors sit behind Thebes. Controllers communicate
intent and constraints to Thebes; Thebes assembles minimum execution context and
invokes a provider. Current Claude-specific bindings and Agent-tool wakes are the
known gap, not evidence that the target already exists.

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

Authorization reference: **none**.
Selected ticket: **none**.
Acceptance result/evidence: **none**.
Normal Product authorization reference: **none**.

Existing Product ownership and lifecycle remain in Persistent State/Jira and are not
copied here.

## Next bounded decision

After this documentation slice is reviewed and accepted, the remaining maintenance
decision is whether to design the executor/provider abstraction or to authorize the
separately bounded Product acceptance protocol. This roadmap does not choose between
them and does not authorize either.

## Phase and mode exit rules

- A completed slice does not close a phase.
- A phase closes only through an explicit recorded decision against its exit criteria.
- A mode transition changes only the mode record and must preserve Product lifecycle,
  ownership, review, dependencies and interventions.
- If documentary sources conflict with runtime state, remain/return to maintenance and
  reconcile; do not normalize toward Product execution.
- Future phases may be refined by evidence, but may not be silently promoted to current
  fact or implementation.
