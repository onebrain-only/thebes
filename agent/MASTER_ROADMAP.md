
# Thebes — Master Roadmap

**Document type:** Canonical Program Roadmap  
**Scope:** Thebes as a company operating system  
**Repository:** Thebes-Canonical  
**Owner:** CEO / Program Controller  
**Status:** Active  
**Current Phase:** see `agent/ROADMAP.md` "Current position" — it owns current
position and this file does not duplicate it (§48–§51, superseded 2026-09-15).  

---

# 1. Purpose of This Document

This document defines the long-term program for Thebes.

It exists to prevent local implementation work, architectural ideas, temporary
solutions, Product incidents, or individual conversations from silently
changing the direction of the program.

It answers:

- What is Thebes ultimately intended to become?
- What are the major phases required to reach that state?
- What has already been completed?
- What is currently being built or proven?
- What must wait until a later phase?
- What constitutes acceptance for each phase?
- Which ideas belong in the Parking Lot rather than becoming immediate work?

Detailed implementation plans, wave plans, incident reports, design notes,
provider specifications, Product tickets, and temporary execution plans may
exist elsewhere.

They are subordinate to this roadmap.

A detailed implementation document may explain HOW a roadmap item is built.

It may not silently change WHAT the roadmap is.

---

# 2. North Star

Thebes is intended to become the operating system for a small software company.

The CEO should eventually interact primarily with one intelligent controller
conversation.

The CEO should not need to manually coordinate:

- specialist agents
- execution providers
- Jira lifecycle
- capability assignment
- repository state
- execution context
- validation routing
- dependency resolution
- retry/failure semantics
- production permissions
- knowledge retrieval
- learning state
- handoff prompts
- provider-specific implementation details

The desired high-level operating model is:

```text
CEO
 ↓
Controller / Conversation
 ↓
Thebes
 ├── Company Knowledge
 ├── Product Knowledge
 ├── Persistent State
 ├── Work Lifecycle
 ├── Roles / Capabilities
 ├── Authorization
 ├── Routing
 ├── Validation
 ├── Dependencies
 ├── Learning
 ├── Context Assembly
 └── Execution
      ├── Claude
      ├── Codex
      └── Future Providers
 ↓
Real Product
```

Thebes should behave like company infrastructure rather than like a collection
of prompts.

---

# 3. Long-Term Human Experience

The long-term experience should approach:

```text
CEO:
"Fix the onboarding issue."

Controller:
- understands the request
- identifies the relevant Product work
- knows the current company state
- identifies missing decisions if necessary
- prepares the required work definition
- submits bounded work to Thebes

Thebes:
- checks authorization
- resolves dependencies
- selects capability
- claims the work
- assembles minimum execution context
- selects a compatible provider
- invokes exactly the required executor
- validates according to policy
- records state
- returns the result

Controller:
- interprets the outcome
- explains important decisions/blockers
- asks the CEO only when real authority or Product judgment is required
```

The CEO should increasingly operate the company rather than operate individual
AI tools.

---

# 4. Fundamental Architecture Principle

The long-term system must maintain separation between three kinds of context.

## 4.1 Controller Context

Used for:

- discussion
- reasoning
- interpretation
- planning
- CEO interaction
- decision support

The controller may reason broadly.

It is not the canonical company database.

---

## 4.2 Thebes Context

Used for:

- canonical company state
- work state
- authorization
- dependencies
- execution state
- capability ownership
- routing rules
- durable decisions
- learning
- governance
- context references

Thebes is authoritative.

---

## 4.3 Executor Context

Used only to perform one bounded authorized task.

It should contain the minimum context needed for execution.

The executor should not receive the entire conversational history merely
because it exists.

---

# 5. Core Context Rule

Long-term principle:

> Codex never briefs Claude.  
> Codex briefs Thebes.  
> Thebes briefs Claude.

More generally:

> Controllers brief Thebes.  
> Thebes assembles executor context.  
> Executors execute bounded work.

This principle becomes progressively stronger through Phases 3–6.

During earlier phases, temporary bridges may exist.

Temporary bridges must not become accidental permanent architecture.

---

# 6. Program Principles

Thebes development follows these principles.

## 6.1 Build from evidence

Architecture changes should increasingly come from observed Product behavior,
not speculative complexity.

---

## 6.2 Bounded execution

One executable work item represents one required capability.

Executors receive bounded work.

They do not autonomously consume the backlog.

---

## 6.3 Responsibility is not routing

Organizational responsibility hierarchy does not mean every task must travel
through every management layer.

CTO, CPO, PM, PO, specialists, QA, and other Roles have responsibilities.

They are not mandatory hops in every execution.

---

## 6.4 Authority follows responsibility

The entity responsible for a decision must have the authority required to make
that decision.

Agents must not invent authority they do not have.

---

## 6.5 Escalation is exceptional

Default behavior:

> Decide and continue within authorized responsibility.

Escalation exists for actual authority boundaries, ambiguity, risk, or required
Product decisions.

It is not a routine feedback loop.

---

## 6.6 Environment fidelity

An executor must not change the environment simply to make validation easier.

If the reported defect is localhost, validation must include localhost.

A different environment may provide comparative evidence.

It may not replace the reported environment.

---

## 6.7 Validation follows causal surface

Validation scope should follow the surface affected by the change.

Do not inflate every change into full-system validation.

Do not under-test the actual causal surface.

---

## 6.8 Provider neutrality

Thebes owns execution semantics.

Providers are execution transports.

Claude and Codex must not define Product lifecycle semantics independently.

---

## 6.9 No silent fallback

If a selected provider fails:

- do not silently switch provider
- do not silently downgrade model
- do not silently downgrade effort
- do not reinterpret provider failure as Product failure

The controller may later authorize a separate execution.

---

## 6.10 Native permissions remain real

Thebes authorization does not erase native provider or platform permissions.

If Claude Code, Codex, Supabase, GitHub, the operating system, or another
execution environment requires explicit permission, that boundary must remain
visible.

The system must never bypass it merely to complete the task.

---

# 7. Program Structure

The Thebes program is divided into six major phases.

```text
Phase 1 — Company / Agent Architecture
Phase 2 — Product Proof
Phase 3 — Separate Listener
Phase 4 — Codex → Listener Integration
Phase 5 — Listener → Thebes Core
Phase 6 — Knowledge Scale / RAG
```

These phases are sequential in architectural maturity.

Small preparatory work for a later phase may occur earlier only when genuinely
required to unblock the current phase.

A future phase must not become current work simply because an interesting idea
belongs there.

---

# 8. PHASE 1 — Company / Agent Architecture

**Status: CLOSED**

## 8.1 Objective

Build a deterministic company operating architecture before attempting broad
autonomous Product execution.

The system needed a stable answer to:

- who can perform work
- how work is represented
- how work is claimed
- how validation is selected
- where state is stored
- how dependencies work
- how execution is authorized
- how providers are separated from company logic
- how failures are represented
- how orchestration state survives individual conversations

---

# 9. Phase 1 — Wave Program

Phase 1 was delivered through Waves 1–8.

## Wave 1 — Truth Reconciliation

Established a reliable distinction between:

- intended architecture
- repository reality
- runtime reality
- documentation claims

Reduced hard-coded or stale assumptions in Agent View and orchestration.

---

## Wave 2 — Role / Seat Model

Established the distinction:

```text
Role ≠ Seat
```

Roles represent durable responsibility/capability.

Seats represent active execution instances.

Removed organizational assumptions such as mandatory Senior/Junior execution
hierarchies.

Durable capabilities include areas such as:

- backend
- frontend
- QA
- UX Engineering
- Product/management responsibilities where applicable

---

## Wave 3 — Routing / Delegation Doctrine

Established that:

- agents do not directly delegate execution to other agents
- consultation is distinct from execution delegation
- management hierarchy is not an execution chain
- work routes according to capability and policy
- arbitrary back-and-forth loops are undesirable

---

## Wave 4 — Persistent State / Execution Profile / Dependencies

Introduced persistent orchestration state.

Established Execution Profile concepts including:

- project
- required capability
- work effort
- characteristics
- validation route
- completion route

Established dependency semantics:

```text
BLOCKS
```

A completed blocker resolves the dependency.

---

## Wave 5 — Jira Lifecycle / Validation

Defined Jira as work lifecycle infrastructure rather than the entire source of
company truth.

Established validation alternatives:

```text
SELF
QA
PEER
```

Validation is chosen according to execution characteristics.

---

## Wave 6 — Capability Queues / Claims / Ownership / Capacity

Introduced:

- capability queues
- claimability
- ownership
- dynamic Seats
- capacity concepts
- orchestration control
- STOP / HOLD / FREEZE semantics

Removed Team Leads as required execution-routing layers.

---

## Wave 7 — Agent View

Improved operational visibility.

Agent View became a view over actual orchestration state rather than a
hard-coded representation of an imagined company.

---

## Wave 8 — Learning / Retrospective / Analytics

Introduced the foundations for:

- learning
- retrospective evidence
- operational analytics
- execution history

This created a basis for future optimization without making learning itself an
execution authority.

---

# 10. Phase 1 — Post-Wave-8 Operational Hardening

**Status: CLOSED**

Phase 1 required one final hardening program before Product proof.

Six areas were completed.

## 10.1 Operating Mode Isolation

Established explicit distinction between:

```text
SYSTEM_MAINTENANCE
PRODUCT_EXECUTION
```

SYSTEM_MAINTENANCE means Thebes itself is being built or repaired.

Product backlog execution must remain frozen unless explicitly authorized.

---

## 10.2 Observation → Investigation Semantics

Established:

```text
User observation
→ investigation
→ root cause
→ fix
→ validation
```

User-reported runtime evidence is authoritative input.

An agent must not replace the reported observation with a more convenient
interpretation.

---

## 10.3 Reported Environment Authority

Established:

> The reported environment is the primary validation target.

Example:

If a defect occurs in local Flutter Chrome, the executor must validate local
Flutter Chrome.

Running another environment may support diagnosis.

It cannot replace primary validation.

---

## 10.4 Causal-Surface Validation

Validation should reflect the actual changed surface.

A startup/bootstrap defect should be validated at the startup/bootstrap
surface.

A database security migration should include database-specific validation.

A UI defect should include the affected UI/runtime environment.

---

## 10.5 Canonical Repository Memory

Established durable program memory in the repository.

Important canonical documents include:

```text
CLAUDE.md
agent/ROADMAP.md
agent/PROGRAM_MEMORY.md
agent/DECISIONS.md
agent/LEARN.md
agent/WORKFLOWS.md
agent/AGENTS.md
agent/history/program-chronology.md
agent/state/
```

Repository memory exists so the program does not depend on one AI conversation
remembering everything.

---

## 10.6 Provider / Executor Abstraction

Established provider-neutral execution.

Core contract:

```text
capabilities() -> ProviderCapabilities
execute(ExecutionRequest) -> ExecutionResult
```

Current providers:

```text
ClaudeProvider
CodexProvider
```

Thebes owns the execution contract.

Providers implement transport.

---

# 11. Provider Architecture

## 11.1 Authoritative execution flow

```text
authorization
→ exact execution lease
→ immutable ExecutionRequest
→ deterministic provider selection
→ exactly one provider
→ normalized ExecutionResult
→ core result receipt
→ exact lease closure
```

---

## 11.2 ExecutionRequest

The provider-neutral request carries bounded execution information including
concepts such as:

- invocation identity
- work item
- Seat
- required capability
- execution kind
- objective
- Role/context references
- workspace
- allowed surfaces
- prohibited surfaces
- operating mode
- revision
- claim/lease references
- reported environment
- primary validation target
- additional validation targets
- model intent
- reasoning effort
- required execution features
- timeout
- return contract

---

## 11.3 Model intent

Core model intent is provider-neutral.

Conceptual values:

```text
cost_efficient
balanced
highest_capability
```

Reasoning effort:

```text
low
medium
high
```

Provider adapters map these to their native model configuration.

No silent downgrade is permitted.

---

## 11.4 ExecutionResult

Normalized result classes include:

```text
completed
needs_input
execution_failed
provider_failed
```

Provider failures and Product execution failures remain distinct.

---

## 11.5 Provider selection

Provider selection is:

- deterministic
- compatibility-first
- policy-controlled
- incapable of Product lifecycle mutation

Current ordering prefers Claude when equally eligible, followed by Codex,
unless an authorized override applies.

There is:

- no automatic retry
- no automatic fallback
- no silent provider substitution

---

# 12. Phase 1 Acceptance

Phase 1 was accepted only after:

- Waves 1–8 closed
- Operational Hardening closed
- Provider Abstraction completed
- production execution bypasses removed
- execution selection wired into the authoritative path
- result receipt wired into the authoritative path
- regression suites passed

Phase 1 is therefore:

# CLOSED

It must not be reopened merely for speculative improvement.

A concrete Phase 2 defect may justify bounded remediation.

---

# 13. PHASE 2 — Product Proof

**Status: CURRENT**

Phase 2 changes the nature of development.

Phase 1 asked:

> Is the architecture internally coherent?

Phase 2 asks:

> Can the architecture operate real Product work correctly?

The goal is evidence.

The goal is NOT broad autonomy.

The goal is NOT to empty the Jira backlog.

The goal is NOT to add architecture for hypothetical future problems.

---

# 14. Phase 2 — Entry Milestone: Tangible Operating Interface

**Status: CURRENT / IN PROGRESS**

A usability gap was discovered after Phase 1 closure.

Thebes possesses an internal provider-neutral execution architecture.

However, the CEO does not yet have a practical front door into that
architecture.

Today the architecture can internally represent:

```text
ExecutionRequest
→ provider selection
→ provider execution
→ ExecutionResult
→ receipt
```

But the desired human operating experience is not yet complete.

---

# 15. Tangible Milestone — Definition of Success

The first tangible milestone is complete when the CEO can open the Codex
controller environment and say, conceptually:

```text
Work on KAN-XXX through Thebes.
```

without manually:

- writing a Claude execution prompt
- opening Claude separately for every task
- selecting providers
- building ExecutionRequest objects
- managing leases
- transferring execution results
- reconstructing canonical context
- manually coordinating the lifecycle

Codex should remain an intelligent controller.

Thebes should remain the execution/governance authority.

---

# 16. Codex Controller Role

Codex is not merely a launcher.

During the Phase 2 temporary interface, Codex is expected to provide controller
intelligence.

Codex may:

- interpret CEO intent
- inspect canonical repository state
- inspect the selected Product work
- understand requirements
- identify the relevant capability
- identify required context
- construct a professional bounded execution brief
- invoke the supported Thebes entry point
- interpret the returned execution result
- explain the result to the CEO

Codex must not:

- invent execution authorization
- bypass Thebes lifecycle
- directly perform Product work when acting as controller
- silently become the selected executor
- silently substitute providers
- rewrite company policy
- select unrelated backlog work

---

# 17. Temporary Controller Entry Point v1

**Status: NEXT IMPLEMENTATION**

Phase 2 requires a small temporary front door.

It is intentionally temporary.

Conceptual flow:

```text
CEO
 ↓
Codex Controller Conversation
 ↓
professional bounded execution brief
 ↓
Temporary Controller Entry Point v1
 ↓
Thebes Core
 ├── authorization
 ├── readiness
 ├── capability / Seat
 ├── claim
 ├── continuation
 ├── ExecutionRequest
 ├── provider selection
 ├── provider invocation
 ├── ExecutionResult
 └── receipt / lease closure
 ↓
Codex Controller
 ↓
CEO
```

---

# 18. Temporary Entry Point — Scope

The v1 bridge should perform only the minimum composition necessary to expose
the already accepted Thebes execution path.

It may provide:

- explicit work-item input
- explicit bounded objective / execution brief input
- canonical state checks
- authorization checks
- readiness checks
- claim integration
- ExecutionRequest creation
- provider registry composition
- call into authoritative wake/execution
- structured result returned to controller

---

# 19. Temporary Entry Point — Non-Goals

It is NOT:

- the Listener
- a natural-language understanding architecture
- a conversational memory system
- a RAG system
- a workflow redesign
- an autonomous backlog runner
- a replacement for Persistent State
- a second provider-selection system
- a second validation system
- a second lifecycle system
- a provider optimization engine

The bridge should remain small enough to replace later.

---

# 20. Temporary Entry Point — Acceptance Criteria

The Phase 2 entry milestone requires:

### A. Controller entry exists

Codex can invoke an explicit supported Thebes command or equivalent
programmatic boundary.

---

### B. Current architecture is reused

The bridge does not rebuild:

- provider selection
- execution leases
- result normalization
- validation policy
- capability policy
- lifecycle semantics

---

### C. Unauthorized Product execution fails closed

If Product execution is not authorized:

```text
NO EXECUTION
NO PROVIDER INVOCATION
NO PRODUCT MUTATION
```

---

### D. Exactly one provider is invoked

One bounded request.

One selected provider.

One invocation.

---

### E. Result returns through Thebes

The result must return through the existing core receipt.

The controller must not treat raw provider stdout as canonical company state.

---

### F. Native permissions remain visible

If Claude Code or another provider requires native permission for an operation,
Thebes must surface that fact.

The controller must not bypass the permission by performing the sensitive
operation itself.

---

### G. First safe smoke test succeeds

A bounded non-Product or isolated execution proves the complete path.

---

### H. First real Product ticket succeeds through the same interface

No separate manual execution path should be required.

---

# 21. Phase 2 — Product Acceptance Program

After the Tangible Operating Interface is accepted, begin bounded real Product
testing.

This is NOT broad Product Execution.

It is controlled acceptance.

---

# 22. Product Acceptance Principles

Use real Product work whenever possible.

Do not manufacture architecture tests if genuine Product work can exercise the
same behavior.

Start simple.

Increase complexity only after the previous level is understood.

Suggested progression:

```text
simple bounded execution
→ real normal Product task
→ QA-routed task
→ PEER-routed task
→ dependency/blocker scenario
→ native permission scenario
→ environment-specific scenario
→ failure/recovery scenario
→ high-authority/sensitive scenario
```

Sensitive scenarios should not be first.

---

# 23. Phase 2 — Behaviors to Prove

Phase 2 should produce evidence for:

## Work definition

Can one bounded work item remain one bounded capability?

---

## Authorization

Can Thebes distinguish:

- authorized
- unauthorized
- CEO-only
- provider-native permission

---

## Capability routing

Does the correct capability execute the task?

---

## Claims

Can one eligible Seat claim work atomically?

---

## Dependencies

Does blocked work remain blocked?

Does completion of the blocker correctly resolve the dependency?

---

## SELF validation

Can low-risk bounded work complete with executor SELF validation where policy
permits it?

---

## QA validation

Can user-visible runtime work route to QA?

---

## PEER validation

Can sensitive/shared/schema/money-related work route to PEER?

---

## PEER remediation

If PEER fails:

- execution transfers according to policy
- reviewer fixes
- reviewer SELF validates
- no uncontrolled peer loop occurs

---

## QA remediation

If QA fails:

- execution returns according to policy
- the executor fixes
- QA revalidates

---

## Environment authority

Does validation remain on the reported environment?

---

## Provider failure

Can a provider fail without moving Product lifecycle incorrectly?

---

## Execution failure

Can execution failure remain distinct from provider failure?

---

## Native permission failure

Can the system surface external permission requirements without bypassing them?

---

## Recovery / continuation

Can the system continue the same bounded work safely instead of restarting
investigation unnecessarily?

---

# 24. Phase 2 — Initial Real Scenarios

Known Product work may provide useful evidence.

Examples include:

## KAN-191

Useful for:

- genuine Product decision blocker
- dependency behavior
- bounded escalation
- avoiding invented Product decisions

A known unresolved decision exists around squad deletion semantics.

The system must not decide this autonomously.

---

## KAN-130

Useful for:

- BLOCKS dependency behavior
- shared-surface dependency
- continuation after blocker resolution

---

## KAN-183

Useful for:

- security-sensitive database execution
- Thebes authorization vs native Claude permission
- migration execution boundary
- PEER validation
- continuation from an existing blocked state

KAN-183 should not be the first smoke test.

It becomes valuable after the controller entry path itself is proven.

---

## KAN-146

Potential future acceptance evidence for:

- money-path authority
- live mutation
- CEO-only execution

This should occur later.

It must not be used casually as an early test.

---

## KAN-195

Potential evidence for:

- credential/security authority
- CEO-only boundary

This is a later sensitive scenario.

---

# 25. Phase 2 — Exit Criteria

Phase 2 is complete when the program has sufficient real Product evidence that:

- the CEO can practically operate Thebes
- real work enters through the intended interface
- capability routing works
- claims work
- authorization works
- provider selection works
- provider execution works
- results return through core receipt
- SELF works where appropriate
- QA works where appropriate
- PEER works where appropriate
- blocked work remains blocked
- dependencies resolve correctly
- failures do not corrupt lifecycle
- environment authority survives real incidents
- native provider permissions remain truthful
- remediation/continuation works
- the architecture does not require manual orchestration for routine work

Phase 2 is NOT defined by finishing the Product backlog.

It is defined by proving the operating architecture.

---

# 26. PHASE 3 — Separate Listener

**Status: FUTURE**

Phase 3 introduces a dedicated Listener/intake layer.

By this point, Product Proof should have established which controller
interactions are actually necessary.

The Listener should be designed from evidence gathered during Phase 2.

---

# 27. Phase 3 Objective

Separate conversational intake from execution orchestration.

Concept:

```text
CEO
 ↓
Listener
 ↓
Thebes
```

The Listener begins to normalize human requests before they enter core
execution state.

---

# 28. Listener Responsibilities

Potential responsibilities include:

- receive controller/user intent
- normalize incoming request form
- identify request category
- resolve explicit work references
- request missing bounded information
- prepare structured intake
- deliver intake to Thebes

The exact contract should be based on Phase 2 evidence.

---

# 29. Listener Non-Responsibilities

The Listener should not become:

- the Product lifecycle database
- the execution provider
- the Jira replacement
- the validation authority
- the persistent company memory
- an autonomous Product manager
- an unrestricted natural-language agent

Thebes remains authoritative.

---

# 30. Phase 3 Acceptance

Phase 3 should finish with:

- a stable intake contract
- separation between conversational input and execution orchestration
- removal or reduction of temporary Phase 2 entry glue
- no regression to provider/lifecycle architecture

---

# 31. PHASE 4 — Codex → Listener Integration

**Status: FUTURE**

Phase 4 connects the intelligent Codex controller experience to the dedicated
Listener.

Target:

```text
CEO
 ↓
Codex Controller
 ↓
Listener
 ↓
Thebes
 ↓
Provider
```

---

# 32. Phase 4 Objective

Make the controller conversation the normal operating surface while keeping
execution state outside the conversation.

Codex may reason broadly.

The Listener translates the required output into structured intake.

Thebes remains authoritative.

---

# 33. Phase 4 Key Outcome

The CEO should increasingly be able to use normal language while the system
maintains deterministic execution underneath.

Example:

```text
CEO:
"Continue KAN-183 now that I've approved the permission."

Codex:
understands conversational meaning

Listener:
resolves structured request

Thebes:
validates actual authorization/state
and decides whether execution can continue
```

Natural language must never itself become authorization.

---

# 34. Phase 4 Acceptance

Phase 4 should demonstrate:

- Codex/controller can submit work through Listener
- no manual execution brief copying is normally necessary
- Listener input maps deterministically into Thebes
- authorization remains explicit
- conversation state does not replace canonical state
- provider-neutral execution still works unchanged

---

# 35. PHASE 5 — Listener Evolves Into Thebes Core

**Status: FUTURE**

Phase 5 matures the intake/orchestration architecture.

At this stage, Thebes should move toward a complete persistent company Core.

---

# 36. Phase 5 Objective

Create clean separation between:

```text
Conversation Intelligence
Canonical Company Intelligence
Execution Intelligence
```

---

# 37. Phase 5 Target Architecture

```text
CEO
 ↓
Controller
 ↓
THEBES CORE
 ├── Intake
 ├── Persistent State
 ├── Company Rules
 ├── Product State
 ├── Work Lifecycle
 ├── Capability Model
 ├── Authorization
 ├── Dependencies
 ├── Context Assembly
 ├── Validation
 ├── Learning
 ├── Provider Selection
 └── Execution
       ↓
   Provider Adapter
       ↓
    Executor
```

The Listener may become an internal subsystem of Thebes rather than a separate
conceptual product.

The exact architecture must come from evidence.

---

# 38. Phase 5 — Minimum Context Execution

A major target is executor context minimization.

The executor should receive:

- bounded objective
- required constraints
- required files/context references
- allowed/prohibited surfaces
- validation targets
- return contract

It should not receive unnecessary company history.

---

# 39. Phase 5 — Learning

Learning may increasingly influence:

- context selection
- prompt construction
- execution recommendations
- provider recommendations
- recurring failure detection

Learning must not silently gain authority over:

- Product decisions
- security decisions
- money-path decisions
- irreversible actions
- CEO-only operations

---

# 40. Phase 5 Acceptance

Phase 5 should demonstrate:

- one durable Thebes Core
- conversation-independent company state
- minimum-context executor briefing
- stable provider-neutral execution
- stable intake
- stable lifecycle
- durable learning inputs
- no dependence on individual chat memory for company operation

---

# 41. PHASE 6 — Knowledge Scale / RAG

**Status: FUTURE**

RAG is deliberately Phase 6.

It should not be introduced merely because RAG is technically attractive.

Thebes should first prove its deterministic knowledge model.

---

# 42. Phase 6 Trigger

Phase 6 should begin only when evidence shows that the existing direct
repository/state/context model is becoming insufficient.

Possible signals:

- canonical knowledge becomes too large to retrieve deterministically
- executor briefs regularly include excessive irrelevant context
- important historical decisions become difficult to locate
- retrieval latency or manual context assembly becomes operationally expensive
- knowledge spans multiple repositories/systems in a way that deterministic
  references cannot efficiently handle
- repeated retrieval failures are observed during real Product execution

---

# 43. Phase 6 Objective

Introduce retrieval as a scaling layer for knowledge.

Potential capabilities:

- indexed company knowledge
- Product knowledge retrieval
- historical decisions
- architecture history
- Role-specific retrieval
- execution history
- incident history
- minimum-context retrieval
- semantic search
- relevance ranking
- context assembly

---

# 44. Phase 6 RAG Principle

RAG does not become company truth.

Canonical systems remain canonical.

Retrieval answers:

> What relevant knowledge should be supplied?

It does not answer:

> What is the authoritative current company state?

Persistent State, Git, Jira, and other canonical sources retain their
respective authority.

---

# 45. Phase 6 Evaluation

RAG should have measurable evaluation.

Examples:

- retrieval precision
- relevant-context recall
- context size reduction
- execution success impact
- hallucination reduction
- historical decision retrieval accuracy
- stale-context detection

The RAG layer should be justified empirically.

---

# 46. Phase 6 Acceptance

Phase 6 should finish with a scalable knowledge layer that:

- improves context assembly
- reduces unnecessary executor context
- preserves canonical-source authority
- does not turn retrieval into autonomous decision authority
- improves real execution outcomes measurably

---

# 47. Architecture Beyond Phase 6

The six phases define the current master program.

Ideas beyond Phase 6 may eventually include:

- more providers
- advanced analytics
- provider optimization
- cost optimization
- stronger autonomous planning
- broader company functions
- richer Product intelligence

These are not current roadmap commitments.

Do not create Phase 7 merely because such ideas exist.

Extend the Master Roadmap only after Phase 6 direction becomes materially
clearer.

---

# 48. Current Program Position

**SUPERSEDED 2026-09-15. `agent/ROADMAP.md` owns current position; read it there.**

This section, and §49–§51 below, were written when Phase 2 was current and were
never refreshed as phases closed. They are preserved rather than deleted so the
program's own history stays interpretable (`LEARN.md` L-012), but they are not
current fact and must not be read as one. §51 already said as much at the time:
*"Runtime state remains authoritative if it later changes."*

Position as of 2026-09-15:

```text
THEBES MASTER PROGRAM
══════════════════════════════════════════════════════════

PHASE 1 — Company / Agent Architecture          CLOSED
Post-Wave-8 Operational Hardening               CLOSED
PHASE 2 — Product Proof                         CLOSED 2026-09-14
PHASE 3 — Separate Listener                     CLOSED 2026-09-15
PHASE 4 — Codex → Listener                      CLOSED 2026-09-15
PHASE 5 — Listener → Thebes Core                FUTURE
PHASE 6 — Knowledge Scale / RAG                 FUTURE
```

Historical text as written:

```text
PHASE 1 — Company / Agent Architecture
████████████████████████████████████████████████  CLOSED ✅

PHASE 2 — Product Proof
████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  CURRENT 🟡

PHASE 3 — Separate Listener
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  FUTURE

PHASE 4 — Codex → Listener
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  FUTURE

PHASE 5 — Listener → Thebes Core
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  FUTURE

PHASE 6 — Knowledge Scale / RAG
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  FUTURE
```

---

# 49. Current Zoom

**SUPERSEDED 2026-09-15 — historical, not current fact.** See §48 and `agent/ROADMAP.md`. The Temporary Controller Entry Point this section calls unimplemented was built in Phase 2 (`agent/controller`), and Phase 4 is retiring it as the external front door.

```text
PHASE 2 — PRODUCT PROOF
│
├── 2.0 Tangible Operating Interface              ← CURRENT
│   │
│   ├── Temporary Controller Entry Point v1        ← NEXT
│   ├── Safe end-to-end smoke test
│   ├── First real Product ticket
│   └── Tangible Milestone acceptance
│
├── 2.1 Basic Product Acceptance
│   ├── normal bounded task
│   ├── SELF validation
│   └── result/lifecycle verification
│
├── 2.2 Validation Acceptance
│   ├── QA
│   └── PEER
│
├── 2.3 Dependency / Blocker Acceptance
│
├── 2.4 Environment / Runtime Acceptance
│
├── 2.5 Provider / Permission Failure Acceptance
│
├── 2.6 Recovery / Continuation Acceptance
│
├── 2.7 Sensitive Authority Acceptance
│
└── Phase 2 Acceptance
```

This is a logical acceptance progression.

It does not require creating artificial work for every sub-stage.

Real Product work should be used where possible.

---

# 50. Current Immediate Sequence

**SUPERSEDED 2026-09-15 — historical, not current fact.** See §48 and `agent/ROADMAP.md`. The Temporary Controller Entry Point this section calls unimplemented was built in Phase 2 (`agent/controller`), and Phase 4 is retiring it as the external front door.

The current sequence is:

```text
1. Build Temporary Controller Entry Point v1
2. Validate it without Product execution
3. Perform safe controller smoke test
4. Execute first bounded real Product ticket
5. Verify controller → Thebes → provider → result loop
6. Continue Product Acceptance using real tasks
```

Do not skip directly from Step 1 to broad Product execution.

---

# 51. Current Operating Status

**SUPERSEDED 2026-09-15 — historical, not current fact.** See §48 and `agent/ROADMAP.md`. The Temporary Controller Entry Point this section calls unimplemented was built in Phase 2 (`agent/controller`), and Phase 4 is retiring it as the external front door.

At the time this roadmap is established:

```text
Phase 1:
CLOSED

Post-Wave-8 Operational Hardening:
CLOSED

Provider Abstraction:
COMPLETE

Current Operating Mode:
SYSTEM_MAINTENANCE

Phase 2:
CURRENT

Product Acceptance:
NOT STARTED / PENDING AUTHORIZATION

Product Execution:
NOT AUTHORIZED

Temporary Controller Entry Point:
NOT YET IMPLEMENTED
```

Runtime state remains authoritative if it later changes.

This roadmap must not be used as a substitute for live Persistent State.

---

# 52. Source-of-Truth Hierarchy

Thebes intentionally has multiple sources of truth for different domains.

## Git

Used for:

- code
- architecture
- durable decisions
- governance documentation

---

## Jira

Used for:

- work lifecycle
- Product ticket definition
- status
- dependencies where represented

---

## Persistent State

Used for:

- orchestration
- execution state
- claims
- leases
- routing state
- operating mode
- runtime authorization
- exception/dependency state

---

## Role Learning

Used for:

- optimization
- retrospective evidence
- future recommendations

Learning does not override authority.

---

## Product / Governance Documentation

Used for:

- durable Product knowledge
- governance
- policies
- design/architecture context

---

# 53. Roadmap Authority Rule

This file is the canonical high-level program map.

However:

```text
MASTER_ROADMAP.md
≠ runtime authorization
```

A roadmap item marked CURRENT does not automatically authorize execution.

Authorization must still come through the appropriate runtime/governance
mechanism.

---

# 54. Anti-Branch Rule

Every new architecture idea must be classified before implementation.

Classification:

```text
A — required to unblock the current Phase
B — evidence-driven remediation from current Phase testing
C — already belongs to a future Phase
D — Parking Lot
```

Only A and B normally interrupt current work.

C waits for its Phase.

D remains parked.

---

# 55. Architecture Conversation Rule

Whenever significant Thebes architecture is discussed, the discussion should
remain anchored to:

```text
MASTER POSITION
+
CURRENT ZOOM
```

The purpose is to prevent local ideas from replacing the master program.

---

# 56. Parking Lot

The Parking Lot contains potentially valuable ideas that are not current work.

Examples:

- advanced unified-chat experience
- sophisticated natural-language controller
- token optimization architecture
- model-cost optimizer
- learned provider routing
- provider scoring
- autonomous backlog selection
- autonomous Product management
- controller redesign
- generalized company simulation
- advanced analytics
- RAG before Phase 6
- convenience automation not required by current Product evidence

Parking does not mean rejection.

It means:

> Not now.

---

# 57. Scope-Control Rule

A temporary problem should receive the smallest solution that allows the
program to continue.

Example:

The missing controller front door during Phase 2 does NOT justify building the
Phase 3 Listener early.

Build a thin replaceable bridge.

Continue Phase 2.

Learn from actual use.

Build the Listener later with evidence.

---

# 58. Product-Build Continuity Rule

Thebes must not become an endless architecture project.

Once minimum infrastructure required for the current Phase exists, return to
real Product proof.

The program should alternate increasingly toward:

```text
Build minimum infrastructure
→ use on Product
→ observe
→ fix evidence-backed weakness
→ use again
```

rather than:

```text
architecture
→ more architecture
→ more architecture
→ hypothetical optimization
```

---

# 59. Tangibility Rule

A milestone should eventually create a capability the CEO can observe or use.

The current tangible milestone is:

> I can operate Thebes from Codex and cause one bounded Product work item to
> travel through Thebes to the selected executor and back.

Internal implementation alone is not sufficient for this milestone.

---

# 60. Final Program Direction

Thebes development should move through the following maturity progression:

```text
ARCHITECTURE
    ↓
PROVE IT
    ↓
CREATE INTAKE
    ↓
CONNECT INTELLIGENT CONTROLLER
    ↓
FORM DURABLE CORE
    ↓
SCALE KNOWLEDGE
```

Or:

```text
Phase 1
Build the company machinery.

Phase 2
Prove the machinery on the real Product.

Phase 3
Give the machinery a proper intake layer.

Phase 4
Connect the intelligent conversation to that intake.

Phase 5
Mature the pieces into the durable Thebes Core.

Phase 6
Scale knowledge only when evidence requires retrieval infrastructure.
```




