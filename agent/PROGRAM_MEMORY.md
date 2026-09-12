# Thebes durable program memory

Current as of 2026-09-12.

## Purpose and classification

This file is the shared context a fresh controller needs to understand Thebes without
conversation memory. It holds stable program architecture and operating concepts that
are neither workflow mechanics nor live runtime facts.

Every material statement is classified:

- **CURRENT FACT** — verifiable in the current repository or runtime source.
- **DECISION/INVARIANT** — a settled rule; rationale is canonical in `DECISIONS.md`.
- **HISTORICAL FACT** — an observed past condition with an evidence reference.
- **LESSON** — an empirical implication; evidence is canonical in `LEARN.md`.
- **FUTURE TARGET** — intended direction, not implemented capability.

This file does not replace `ROADMAP.md`, workflow mechanics, role contracts, Jira,
Persistent State, Product governance, role learning or history. When a concern has an
owner, it links to that owner instead of copying its full prose.

## What Thebes is

**CURRENT FACT.** Thebes is the operating system for a scalable software-company agent
model. The controller is Dispatcher + Coordinator + Verifier, not a normal Product
worker or a seat. Roles define capability and authority; seats are execution instances.
Work moves through capability-derived eligibility, atomic ownership, an execution gate,
a provider wake, validation and lifecycle reconciliation.

**DECISION/INVARIANT.** The hierarchy describes responsibility, not a relay path.
Requests go directly to the capability that owns the answer. Agents do not brief chains
of managers, and the controller does not become a relay between workers.

**DECISION/INVARIANT.** Repository sources remember the program; conversations do not.
Controllers may use conversation history as evidence to curate a repository update, but
future behavior must be recoverable from canonical repository/runtime sources.

## Source-of-truth model

| Domain | Authority | Boundary |
| --- | --- | --- |
| Source code, architecture, governance and durable decisions | Git in `onebrain-only/thebes` and the applicable Product/governance repositories | Git does not own live work lifecycle or workspace-local execution ownership. |
| Product work lifecycle, ticket content and changelog | Jira | Jira assignee is not Thebes execution authority. A Jira column is not a status. |
| Current Thebes operating mode, ownership, claims, interventions and execution context | Persistent State through `agent/state/store.py` | Workspace-local, not distributed or global; stores references/minimum facts, not canonical prose. |
| Role behavior and authority | `agent/AGENTS.md`, `agent/roles/*.md`, generated bindings | A Role is not a Seat; generated runtime definitions are not hand-authored authority. |
| Workflow mechanics and review routes | `agent/WORKFLOWS.md` plus executable state policy | Does not authorize entering Product mode. |
| Capability-scoped optimization | Role Learning / Wave 8 learning records | Advisory and inert; never lifecycle, claim or review authority. |
| Program position and authorization | `agent/ROADMAP.md` | Does not duplicate live Product ownership/lifecycle. |
| Durable rationale and empirical lessons | `agent/DECISIONS.md`, `agent/LEARN.md` | Not a session journal or ticket database. |

When sources disagree, follow their domain ownership. Jira wins lifecycle conflicts;
Persistent State wins execution ownership; governance defines rules; `ROADMAP.md` owns
program authorization. A conflict never grants broader authority.

## Controller and executor responsibilities

**CURRENT FACT — Controller.** The controller interprets intent, reads canonical state,
derives queue/claimability, coordinates dependencies and contention, opens the
authorized execution boundary, verifies results, and returns the user-facing answer. It
does not write Product code, claim ordinary Product work for itself, select a validation
route, or appoint an ineligible reviewer.

**CURRENT FACT — Executor.** A provider-hosted seat performs the bounded work its Role,
ownership and prompt authorize. Thebes owns the provider-neutral `ExecutionRequest`; the
Claude-specific seam validates it and prepares the exact native `Agent` wake. The controller
still owns that external transport because no repository-callable Claude launcher exists. A
wake creates no ownership; ownership must already exist and the continuation gate and execution
lease must authorize the invocation. The current raw Claude result remains unnormalized.

**FUTURE TARGET.** Provider invocation becomes an adapter boundary owned by Thebes. The
controller should not embed Claude Code, Codex or any future provider as architectural
identity. See `ROADMAP.md` “Executor/provider target.”

## Role, Seat and capability routing

**DECISION/INVARIANT — Role != Seat.** A Role is a durable capability, authority and
learning contract. A Seat is a bounded execution instance of one Role. Seats do not own
permanent knowledge silos, and idleness does not make a seat eligible for another Role’s
work. See `agent/AGENTS.md` for the current roster and exact authority.

**CURRENT FACT.** One executable work item has exactly one `required_capability`.
Multi-capability work is split into executable children under a non-executable container.
Capability queues, eligibility, claimability and capacity are derived; storing them would
create a second authority.

**DECISION/INVARIANT — serial controller-driven execution.** Product execution is
intentionally bounded and serial at the controller level unless explicit safe
parallelism is planned by the current execution policy. One controller turn does not
autonomously continue into a new ticket. Parallelism is constrained by dependencies,
surfaces, ownership, available seats and model/token capacity—not by ticket count.

## Context-budget rules

**DECISION/INVARIANT.** Give each actor the minimum canonical context needed for its
decision. Do not replay the entire management conversation into every executor. Prefer
references to canonical files and identifiers over copied prose. Do not wake additional
agents merely to narrate, supervise or relay work.

**LESSON.** Multi-agent management loops can consume more model capacity than the work
they coordinate. Seat count is not execution capacity; model/token availability is a
first-class constraint. The historical usage incident and resulting rule are recorded in
`agent/DECISIONS.md` and `agent/LEARN.md`.

## Operating modes

**CURRENT FACT.** Exactly one operating mode is active:

- `SYSTEM_MAINTENANCE` builds, documents and tests Thebes. Product claims and wakes are
  refused; Product lifecycle and ownership remain untouched.
- `PRODUCT_EXECUTION` executes explicitly authorized Product work against stable Thebes
  infrastructure. It is not a license to redesign Thebes opportunistically.

Mode is independent of STOP/HOLD/FREEZE and ACCELERATE/NORMAL. A transition changes only
the mode record. The current mode and authorization gate are in `agent/ROADMAP.md`; the
runtime contract is in `agent/state/README.md`.

**DECISION/INVARIANT.** Implementation complete does not mean Product authorized. No
controller selects the first or next Product ticket without scope already established by
the applicable authorization and workflow.

## Validation and review model

**CURRENT FACT.** Validation route is derived from task characteristics; an executor does
not choose its reviewer. The three routes are SELF, QA and PEER. Exact mechanics belong to
`agent/WORKFLOWS.md` §3.

**DECISION/INVARIANT — PEER remediation.** A PEER reviewer must share the required
capability because a failure transfers bounded remediation responsibility to that
reviewer. The reviewer fixes the failed scope, SELF-reviews that remediation as the
explicit below-floor exception, and preserves the evidence chain. No eligible peer means
wait; it never means downgrade.

**DECISION/INVARIANT — investigation semantics.** A reported observation begins
investigation. Reproduction is required only when evidence or an explicit request makes
it necessary; it is not a mandatory ceremony before diagnosis.

**DECISION/INVARIANT — environment authority.** The environment in which the condition
was reported is the primary target. “Browser under test” and “browser automation
environment” are different facts. Local Flutter web in Chrome means the local runtime is
primary; a remote automation browser may be optional comparative evidence.

**DECISION/INVARIANT — causal validation.** Required validation follows the diagnosed
causal and changed surfaces. Shared changes require shared automated proof plus the
reported primary runtime; platform-specific changes require each affected platform.
Merely mentioning a platform does not make it a required validation target.

## Safety and workspace boundaries

**CURRENT FACT.** `~/Desktop/Thebes-Canonical` is the one canonical Thebes checkout and
its runtime state coordinates only processes on that filesystem. Another clone would have
independent state and cannot safely represent the same execution domain.

**CURRENT FACT.** During the current maintenance phase, Product/Dabbler code, Product
Jira lifecycle, production databases and existing open Product tickets are outside scope.
The high-level pause is recorded here only to orient controllers; live Product state is
not duplicated.

**DECISION/INVARIANT.** STOP/HOLD/FREEZE are safety primitives, not scheduling or
performance-management tools. Dependencies are enforced as Persistent State edges; prose
that says “blocked by” is documentation until the edge exists.

## Current architecture and known gap

**CURRENT FACT.** The current system contains role/binding generation, Jira-derived
lifecycle, Persistent State, capability queues, claims, ownership, execution gates and
leases, safety interventions, Agent View, and advisory telemetry/learning.

**CURRENT FACT.** Provider neutrality is not yet complete. The neutral execution contract,
Seat registry, Claude renderer and Claude wake-preparation seam exist. Claude bindings and the
controller-native external Agent-tool transport remain provider-specific. Live result
normalization, provider selection, an interchangeable Codex adapter and a repository-callable
Claude transport do not exist.

**FUTURE TARGET.** Listener → controller integration → Thebes Core → measured knowledge
scaling is the approved direction, not current implementation. RAG is deferred until
direct canonical reads demonstrably stop scaling. See `agent/ROADMAP.md` for sequencing.

## Fresh-controller reconstruction checklist

Before deciding what happens next:

1. Read `CLAUDE.md` and `agent/ROADMAP.md`.
2. Read this file for architecture and source ownership.
3. Read `agent/DECISIONS.md` and `agent/LEARN.md` when rationale or operating judgment is
   relevant; read `agent/history/program-chronology.md` for checkpoint claims.
4. Read `agent/WORKFLOWS.md`, `agent/AGENTS.md` and applicable Role contracts for action.
5. Read `agent/state/README.md`, then query Persistent State through its API for current
   operational facts.
6. Stop and reconcile in maintenance if sources conflict or authorization is absent.
