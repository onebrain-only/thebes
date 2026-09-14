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
lease must authorize the invocation. Claude normalizes the native outcome into the
provider-neutral `ExecutionResult`; provider failure and execution failure remain distinct.
Completion is evidence for controller verification, not Product acceptance or lifecycle truth.
The core wake constructs the request after the lease, passes it through the deterministic
capability/model/effort-gated selector, executes exactly the selected provider, and sends every
normalized result through inert core receipt before the exact lease closes. Codex uses that same
request/result boundary through the local `codex exec` CLI; cwd, sandbox, timeout, model and
reasoning effort are transport-enforced, while Role, context, surfaces, environment, validation
and return constraints are an explicit deterministic executor brief. Controller-authorized
overrides still pass through selection, with no retry, fallback or workflow authority.

**CURRENT FACT — the routine execution brief is derived, not authored.** `python -m
agent.controller execute KAN-XXX` takes only the work-item key.
`agent/controller/intent.py` resolves it from the sources that already own each fact: Jira for
the Product definition (summary, description, acceptance criteria, bounded — never dumped),
Persistent State for capability, surfaces, characteristics, the canonical validation route and
the `operational_context` environment authority, and the Product/Project registry for the
repository. It creates no second task store and no second prompt builder; its output feeds the
existing `ExecutionRequest` and the one canonical executor brief. It asserts no characteristic
and derives no route — a Jira description that *says* "security" changes nothing, because only
typed canonical state feeds `policy.validation_route`. Derivation runs before the claim, so a
fact canonical state does not hold stops as a named governance input classified
`CEO_INPUT_REQUIRED` or `DERIVABLE` rather than as an invented default. `--brief-file` remains
an exceptional debug path: it fills gaps, never overrules a canonical safety fact, and never
bypasses the firewall. Evidence: `agent/controller/tests/test_canonical_intent.py`.

**CURRENT FACT — Thebes allocates the Product workspace; the executor never does.** The
execution path allocates the isolated worktree after the claim and before the lease, request and
provider, through the canonical `agent/state/worktrees.py` and no second manager. The identity
of what comes back is verified rather than assumed (path ownership, branch name, registration,
not the canonical checkout), and `expected_revision` is bound to `git rev-parse HEAD` in the new
tree rather than invented. A failed isolation is a bounded orchestration blocker and never a
reason to execute against the canonical Product checkout; an allocation refusal means zero
provider invocations. Workspace lifetime follows the Product lifecycle, not function scope:
`needs_input` and pending validation preserve the tree for the continuation or the reviewer, a
provider failure before any Product mutation releases a freshly allocated clean tree, a
canonically `done` item releases a clean tree keeping its branch, and a tree holding uncommitted
Product work is never deleted. Evidence: `agent/controller/tests/test_workspace_allocation.py`.

**CURRENT FACT — validated Product work lands without a human running git.**
`python -m agent.controller integrate KAN-XXX` attributes, commits and integrates one work
item's isolated branch onto Canary, through the existing `agent/state/worktrees.py` and no second
git subsystem or integration queue. The gate is the canonical validation route: integration
consumes `queue.completion_reasons` (minus `already-done`) rather than inventing a second
validation model, so a completed provider result, a Jira status and a seat's assertion all remain
incapable of landing code. Attribution runs before anything is staged and refuses a change the
task never declared, leaving it in place. A conflict aborts cleanly, leaves the branch where it
was, and is classified as Product remediation with the worktree preserved — never as a provider
or PEER failure, and never as permission to force or reset. Integration is verified by asking git
afterwards, not by a zero exit code. A durable `integration_receipt` records the Product commit,
the integrated sha, the branch, the previous head, the route and verdict, the attributed files
and whether remediation is required; Git remains the authority on the code. Evidence:
`agent/controller/tests/test_integration_flow.py`.

**CURRENT FACT — a validated, integrated work item completes its own lifecycle.** `execute
KAN-XXX` runs integration and lifecycle completion as its tail; both gate themselves, so an
execution whose review has not happened yet changes nothing, and `integrate KAN-XXX` remains only
for recovery. `agent/controller/completion.py` adds no lifecycle machinery: `board`, `jira`,
`store.observe_lifecycle` and `store.release` are used unchanged. The integration receipt is
evidence, never authority — it is validated against the work item, owner, outcome, branch and
shas it claims, and a foreign, failed or malformed one refuses before any Jira call. The gate is
`queue.completion_reasons` consumed whole, with `already-done` treated as the idempotent case
rather than a refusal. **Persistent State is written from an authoritative RE-READ of Jira, never
from the fact that a transition was accepted**; a transition that lands elsewhere is
`jira-state-diverged-after-transition` with no local Done and ownership preserved. Ownership
releases only after confirmed Done and survives every failure, and a Jira failure is never a
reason to re-run a provider. Evidence: `agent/controller/tests/test_lifecycle_completion.py`.

**CURRENT FACT — validation is dispatched by the flow, not recorded by a human.** `execute
KAN-XXX` runs the canonical route between execution and integration.
`agent/controller/validation.py` adds ordering and dispatch only: the route is
`policy.validation_route_for_profile`, the owner is `policy.resolve_owner_or_wait` through
`store.open_review_context`, the verdict is `store.record_review_result`, and each FAIL keeps its
own handler. Ownership is released first because `store.release` is the only act that creates
executor evidence — which SELF's owner *is* and which PEER eligibility *excludes* — and Jira moves
before the context because a review context opens only on an item canonically in review. A
validation request is an `ExecutionRequest` of kind `validation` through the same brief and
firewall; the contract refuses it unless it is read-only and carries an open review context, and
it opens no claim and no lease because a reviewer is deliberately not the owner. **A provider
that returned `completed` has passed nothing**: the verdict is an explicit `verdict` evidence
claim, and its absence or contradiction is surfaced rather than guessed. A PEER route with no
eligible peer waits rather than downgrading. Evidence:
`agent/controller/tests/test_validation_dispatch.py`.

**CURRENT FACT — PEER FAIL hands over ownership, so remediation needs no human.**
`store.peer_fail_transfer` now writes ownership in the same atomic mutation as the evidence
replacement, the SELF route, the cycle and `previous_owner`. It is a transfer of already-
authorised execution authority, not a claim, and deliberately bypasses queue claimability: the
work goes to the seat the review context records. It requires a recorded `fail`, the exact review
owner, a seat holding the task's capability and not already owning other work; every refusal
leaves the record byte-identical, and a replay is refused because a completed transfer leaves the
route on `self`. The reviewer then executes its fix, SELF-validates, integrates and completes
through the ordinary flow, with no second PEER loop. Evidence:
`agent/controller/tests/test_peer_fail_handoff.py`.

**DECISION/INVARIANT — the executor brief is Product-only.** There is exactly one executor
brief builder, `agent/execution/brief.py`, and both providers render the same text from the
immutable request. It reads a closed allowlist of Product fields, so control-plane request
fields — invocation id, seat, claim, execution lease, operating mode and revision, model and
effort intent — have no rendering path at all. Before any provider is selected, the same module
firewalls the request: its instruction surface may not instruct the executor to continue,
resume or launch itself, choose a provider, open or close a lease, claim or release work,
bootstrap the controller, create or resume a session, or drive Jira lifecycle, and no
executor-visible field may name a Thebes internal identifier. A Product constraint stated as a
prohibition stays legal; naming the mechanism does not. **The executor never orchestrates its
own execution** — KAN-186 leaked `execute_approved_claude_continuation` into an executor prompt
through exactly that gap. Evidence: `agent/execution/tests/test_executor_brief_boundary.py`.

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

**CURRENT FACT.** The neutral execution contract,
Seat registry, Claude renderer and Claude wake-preparation seam exist. Claude bindings and the
controller-native external Agent-tool transport remain provider-specific. Claude and Codex result
normalization use the neutral `ExecutionResult`; Codex's local CLI adapter and deterministic
provider selector exist. Provider abstraction is complete; a repository-callable Claude transport,
automatic retry and automatic fallback do not exist.

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
