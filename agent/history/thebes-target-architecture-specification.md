> **HISTORICAL / REFERENCE ONLY — preserved 2026-09-10.**
> This document is a pre-Thebes draft, salvaged verbatim from an unregistered legacy clone
> (`~/Desktop/Thebes`, remote `structure.git`) during Desktop single-root cleanup. It describes
> an early "target architecture" proposal — the document's own closing line says the design
> "can later evolve into Thebes without rebuilding its fundamental operating principles." **It
> predates and is superseded by the live Thebes system** documented in the top-level `CLAUDE.md`
> "Orchestrator" section and `agent/WORKFLOWS.md` (capability queues, atomic claims, the
> continuation gate, STOP/HOLD/FREEZE, Wave 6+ doctrine — none of which exist in this draft).
> **It carries no authority.** Nothing here overrides current governance, and no seat, agent, or
> future session should treat any rule, org-chart, or workflow below as active — check
> `CLAUDE.md` / `WORKFLOWS.md` / `AGENTS.md` for what is actually in force. Kept only so the
> reasoning behind the current design's ancestry is not lost when the legacy clone is removed.

---

# Thebes — Target Architecture Specification

**Status:** Draft for Architecture Review
**Purpose:** Consolidated target-state specification based on the completed architecture questionnaire.
**Scope:** Phase 1 — redesign the Claude Code agent architecture only.
**Important:** This document defines the agreed target architecture. It is not yet an implementation prompt.

---

## 1. Architecture Principles

Thebes is designed as an autonomous, scalable software-company operating model with minimal management overhead and minimal token waste.

### Constitutional rules

1. **Command decides, planning defines, execution builds.**
2. **Protocol > Personality.**
3. **Repository remembers, not Claude sessions.**
4. **Hierarchy defines responsibility, not routing.**
5. **Authority follows responsibility.**
6. **Awareness ≠ Approval.**
7. **Executives govern; they do not sit in the routine critical path.**
8. **No relay roles.**
9. **Scale because of proven parallel demand, never because a new ticket exists.**
10. **Role ≠ Seat.**
11. **Autonomy by default, escalation by exception.**
12. **Escalation is routed, not hierarchical.**
13. **Centralized governance, decentralized execution.**
14. **The Orchestrator does not manage normal work. It protects flow.**
15. **If a role has authority and capability to resolve an issue it discovered, it resolves it rather than relaying it backwards.**
16. **Work Effort and Reasoning Effort are independent concepts.**
17. **Jira is the work lifecycle, not system memory.**
18. **Products are execution-independent. Dependencies never cross Product boundaries.**
19. **Execution capacity includes model/token availability, not merely the number of agent seats.**
20. **Calendar closes the Sprint, not task completion. Unfinished work is data, not a reason to extend the Sprint.**

---

## 2. Target Organisational Model

```text
THEBES
│
├── Orchestrator
│
├── Company-Level Governance
│   ├── CTO
│   ├── CPO
│   └── CXO
│
├── Product-Level
│   ├── PM
│   └── DevOps
│
├── Project-Level
│   └── PO
│
├── Shared Capabilities
│   ├── Frontend Engineer
│   ├── Backend Engineer
│   ├── UX Engineer
│   ├── Product Designer [currently inactive]
│   ├── QA
│   ├── Content
│   └── Analyst
│
├── Persistent State Layer
│
└── System Maintenance Mode
```

This hierarchy describes **ownership and responsibility**, not mandatory communication paths.

Agents do not route routine work through their managers.

---

# 3. Main Session / Orchestrator

The Main Claude session operates as:

> **Dispatcher + Coordinator + Verifier — never a normal product execution worker.**

Responsibilities:

- Understand incoming user intent.
- Coordinate operational execution.
- Verify outcomes.
- Read/write durable system state.
- Monitor system flow.
- Protect execution when exceptional conditions occur.
- Execute direct flow-control commands when necessary.

It must not become a mandatory intermediary for normal specialist-to-work assignment.

Normal work is driven through capability queues and persistent work state.

---

# 4. Role vs Seat

A **Role/Capability** defines:

- responsibility;
- authority;
- execution contract;
- capability;
- learning profile.

A **Seat** is a temporary execution instance of that capability.

Example:

```text
Frontend Engineer
├── Shared Role Contract
├── Shared Learning Profile
├── FE-01 [Active]
├── FE-02 [Active]
└── FE-03 [Inactive]
```

Seats do not own permanent knowledge silos.

Transient execution state may belong to a seat while work is active, but durable learning belongs primarily to the Role/Capability.

---

# 5. Dynamic Seat Scaling

New seats are activated only when additional concurrency creates real throughput.

Never:

```text
New Ticket → New Agent
```

Instead:

```text
Parallel Demand
      ↓
Can existing seats handle it?
      ↓
Would another seat create useful throughput?
      ↓
Check actual execution capacity
      ↓
Activate seat only when beneficial
```

Scaling must consider:

- genuinely parallelisable work;
- available seats;
- token/model capacity;
- dependencies;
- expected task duration;
- file/code contention;
- duplicate-work risk;
- current usage burn;
- expected remaining capacity.

A new seat must **not** be activated when the real bottleneck is Claude/model usage.

> **Never scale seats when the constrained resource is model/token capacity rather than worker capacity.**

When demand disappears, temporary seats return to inactive state.

---

# 6. Role Learning

All seats of a capability share the same Role Learning Profile.

Examples:

```text
agent/learning/
├── frontend.md
├── backend.md
├── qa.md
├── po.md
├── pm.md
├── devops.md
├── cto.md
├── cpo.md
├── cxo.md
├── analyst.md
├── content.md
├── ux-engineer.md
└── orchestrator.md
```

Learning is an optimisation layer, not the source of truth for project knowledge.

Learning may improve:

- model selection;
- reasoning effort;
- effort forecasting;
- execution strategy;
- validation choice;
- token efficiency;
- routing/scaling recommendations;
- recurring failure avoidance.

---

# 7. Authority Model

> **Authority follows responsibility. Every role has full execution authority within its defined scope. Escalation occurs only when work crosses that scope or reaches a genuinely critical exception.**

Examples:

- Backend Engineer has normal backend/database authority within scope.
- Frontend Engineer owns frontend implementation decisions within scope.
- UX Engineer owns design-to-code fidelity execution within scope.
- DevOps owns normal CI/CD, environment, build and infrastructure work within scope.
- QA owns validation within its selected QA route.

Routine actions do not require executive approval.

Final destructive or irreversible production actions require explicit user/CEO approval.

---

# 8. Executive Roles

## CTO — Company Level

The CTO is **outside the Development Lifecycle**.

The CTO does not routinely:

- receive development tickets;
- estimate implementation work;
- approve code;
- review code;
- approve normal migrations;
- approve normal architecture decisions;
- participate in developer feedback loops.

The CTO handles technical governance and rare critical technical exceptions outside normal development flow.

If an unresolved critical exception genuinely requires CTO authority, the Orchestrator routes it directly to the CTO. The CTO may then communicate directly with the original agent who raised the issue.

That is consultation/decision authority — not development ownership.

---

## CPO — Company / Portfolio Level

CPO owns high-level product governance and portfolio direction.

CPO is not a routine routing or approval layer.

---

## CXO — Company Level

CXO owns experience governance:

- experience strategy;
- design principles;
- cross-product experience standards;
- brand direction;
- content direction.

Experience organisation:

```text
CXO
├── Product Designer [shared / currently inactive]
├── UX Engineer [shared / active]
└── Content [shared / on-demand]
```

The specialists consume persistent Experience Context rather than waking the CXO for routine work.

---

# 9. PM and PO Scope

## PM — Product Level

Each Product has its own PM.

PM owns:

- Product Backlog;
- cross-project Product priorities;
- product-level sequencing;
- product-level capacity conflicts between Projects.

The PM does **not** perform Sprint Planning for each Project.

---

## PO — Project Level

Each Project has its own PO.

Multiple POs may operate on the same Product Jira board.

Example:

```text
PRODUCT JIRA BOARD
│
├── PM — Product Level
│
├── Project A
│   └── PO-A
│
├── Project B
│   └── PO-B
│
└── Project C
    └── PO-C
```

PO owns:

- Project work definition;
- acceptance criteria;
- capability requirement;
- Work Effort for PO-authored primary work;
- Sprint preparation for its Project;
- Project execution scope;
- carry-over/replanning.

The PM owns and prioritises the Product Backlog.

The PO selects work for its Project's Sprint based on:

- PM priority;
- carry-over;
- dependencies;
- capacity recommendation;
- project context.

---

# 10. DevOps

DevOps is Product-level.

It serves all Projects within that Product.

DevOps has normal authority over:

- CI/CD;
- build/release preparation;
- environment configuration;
- infrastructure;
- rollback preparation;
- normal operational engineering.

Final irreversible/destructive production actions require explicit user/CEO approval.

There is no CTO/PM approval chain for routine DevOps work.

---

# 11. Shared Capabilities

Shared capabilities may serve work dynamically without becoming management layers.

Current shared capabilities include:

- Frontend Engineer
- Backend Engineer
- UX Engineer
- Product Designer
- QA
- Content
- Analyst

They may scale by seats according to proven parallel demand and actual execution capacity.

## Product Designer

Shared capability, currently inactive because the user is currently the design source.

## UX Engineer

Active shared capability.

Primary responsibility:

> high-fidelity translation of design into implementation.

## Frontend Engineer

Responsible for application implementation including:

- state;
- logic;
- integration;
- navigation;
- frontend application behaviour.

No Senior/Junior distinction exists in the target model.

Task complexity determines execution profile rather than job title.

---

# 12. Analyst

Analyst is a Company-level shared specialist/team.

Analyst is **outside the normal execution lifecycle**.

Tasks do not pass through Analyst by default.

Analyst is used for explicit analytical work such as:

- product analysis;
- project analysis;
- market analysis;
- competitive analysis;
- metrics;
- sprint/system performance analysis.

At weekly close, Analyst also analyses system telemetry and produces retrospective analysis/dashboard outputs.

Analyst **measures and analyses**; Analyst does not modify the operating system.

---

# 13. Persistent State

Persistent State is an independent system layer.

It is **not an Agent** and **not Orchestrator memory**.

The Orchestrator operationally reads/writes/manages it.

Canonical organisation:

```text
Company
└── Product
    └── Project
        ├── Task State
        └── Decisions
```

Persistent State may contain:

- current execution state;
- execution profiles;
- handoffs;
- task context;
- orchestration state;
- durable decisions;
- operational metadata.

Agent learning is separate from canonical state.

Future RAG may retrieve from this organised knowledge, but RAG is not required for Phase 1.

---

# 14. Jira Model

> **Jira = Work Lifecycle only.**

Jira does not become:

- architecture memory;
- agent memory;
- system learning storage;
- Thebes system-maintenance tracker.

Separation:

```text
Git / Repository
→ code + architecture + durable technical/project decisions

Jira
→ work lifecycle + assignment + priority + acceptance

Persistent Thebes State
→ orchestration state + execution profiles + handoffs + current context

Role Learning
→ execution optimisation
```

Each Product can have a different Jira board/workflow appropriate to that Product.

Jira is Product-level.

Multiple Project-level POs may work on the same Product board.

---

# 15. Work Creation and Capability Queues

The system follows:

> **Centralized governance, decentralized execution.**

Any authorised Agent may create a necessary execution-discovered sub-task/follow-up inside the current work context.

Creating work does **not** mean selecting or directly calling another Agent.

The creator records:

- discovered scope;
- required capability;
- relationship to parent work;
- dependency/blocker information.

The work enters the appropriate Ready queue.

An available seat of the required capability claims it according to deterministic capacity and queue rules.

Forbidden normal flow:

```text
Frontend → Backend direct delegation
Frontend → Orchestrator → Backend
Frontend → PO → Backend
```

Instead:

```text
Frontend discovers Backend work
        ↓
Creates capability-based work item
        ↓
Backend Ready Queue
        ↓
Eligible Backend seat claims it
```

Direct Agent-to-Agent **delegation** remains prohibited.

Direct Agent-to-Agent **consultation** is allowed when an authorised exception route explicitly connects the relevant decision authority to the original Agent.

---

# 16. PO-Authored Work vs Execution-Discovered Work

These are intentionally different.

## PO-Authored Primary Work

PO defines:

- Scope
- Acceptance Criteria
- Capability
- Work Effort
- Priority

This is considered execution-ready.

The developer does not re-estimate the PO's primary task as a prerequisite to starting it.

If genuinely new work outside the contract is discovered, create new execution-discovered work.

---

## Execution-Discovered Work

The discovering Agent defines:

- discovery;
- scope;
- required capability;
- relationship;
- dependency.

The creator does **not** estimate effort for another capability.

When the target capability claims the work, it performs a short **Preflight**:

- understand scope;
- inspect relevant context/code;
- validate dependency;
- estimate complexity;
- estimate Work Effort;
- assess risk;
- confirm capability fit.

Then system policy derives execution configuration.

High effort is not itself an escalation reason.

If execution-discovered work is not executable as defined because its definition/dependency/scope is invalid, it may return to PO as a work-definition issue.

---

# 17. Execution Profile

Every executable task receives an Execution Profile before execution.

It may include:

- Capability
- Work Effort
- Execution Complexity
- Risk
- Model
- Reasoning Effort
- Validation Route
- Parallelism characteristics
- Completion Route
- relevant execution constraints

The PO does **not** choose the model or reasoning effort.

System policy derives them.

---

# 18. Work Effort vs Reasoning Effort

These concepts are independent.

## Work Effort

Measures:

- size;
- amount;
- duration;
- implementation volume.

Used primarily for planning/capacity.

## Execution Complexity

Measures reasoning difficulty.

## Reasoning Effort

Derived from task characteristics and execution policy.

A large task does not automatically require a more expensive model or higher reasoning effort.

Likewise, a small but conceptually difficult task may require stronger reasoning.

---

# 19. Model Selection

Model and reasoning selection begins rule-based.

Each role receives general guidance describing:

- model differences;
- when stronger models are appropriate;
- Low/Medium/High reasoning usage;
- complexity classification;
- risk classification;
- quality vs token efficiency.

The policy then improves through measured sprint learning.

> **Model selection starts rule-based and improves through sprint-level learning.**

---

# 20. Development Lifecycle

Core lifecycle:

```text
READY
  ↓
DEVELOPMENT
  ↓
REVIEW
  ↓
DONE
```

There is no direct:

```text
Development → Done
```

Every implementation passes through Review.

Review is a lifecycle state, not synonymous with QA.

---

# 21. Validation Routes

There are exactly three mutually exclusive validation routes:

1. **Self Review**
2. **Peer Review**
3. **QA Review**

The Execution Profile chooses one route.

The PO does not manually select the validation route.

---

## 21.1 Self Review

```text
Developer
   ↓
Development complete
   ↓
Review — same Developer
   ↓
Pass → Done

Fail
   ↓
Development — same Developer
   ↓
Fix
   ↓
Self Review
```

---

## 21.2 Peer Review

```text
Developer A
   ↓
Development complete
   ↓
Review — Peer Developer B
   ↓
Pass → Done

Issue found
   ↓
Development ownership → Peer B
   ↓
Peer B fixes directly
   ↓
Self Review — Peer B
   ↓
Done
```

The peer does not relay defects backwards to the original developer when the peer has the authority and capability to fix them.

No QA is inserted into this route.

---

## 21.3 QA Review

```text
Developer A
   ↓
Development complete
   ↓
QA Review
   ↓
Pass → Done

Fail
   ↓
Development — original/current Developer
   ↓
Fix
   ↓
Return directly to same QA validation cycle
   ↓
Repeat until pass
```

QA does not modify production code.

The repeated QA loop is one validation cycle, not a new routing chain.

---

# 22. Escalation Philosophy

Default:

> **Decide and continue.**

Escalation is an exceptional safety mechanism.

Do not escalate because of:

- ordinary uncertainty;
- high effort;
- normal implementation choices;
- routine reversible decisions.

Potential critical escalation reasons include:

- destructive/irreversible production action;
- risk of user-data deletion/loss;
- serious security/privacy risk;
- foundational architecture outside current contract;
- decision materially changing scope/acceptance;
- genuinely unresolved critical blocker.

---

# 23. Exception Routing — No Relay

There are no hierarchical escalation chains.

Normal critical exception pattern:

```text
Developer
   ↓
PO
```

PO attempts to resolve the exception.

If PO can resolve it:

```text
PO ↔ Developer directly
```

If PO cannot resolve it:

```text
PO
 ↓
Orchestrator
 ↓
Correct Decision Authority
 ↓
Direct conversation with original Developer
```

The exception record retains:

- `raised_by`
- `return_to`

The Orchestrator redirects the exception once and leaves the decision conversation.

Forbidden:

```text
Authority → Orchestrator → PO → Developer
```

Also forbidden:

```text
Developer → PO → PM → CPO → CTO → Orchestrator → User
```

> **Escalation goes up for a decision, not ownership.**

---

# 24. Orchestrator Intervention Modes

The Orchestrator does not manage normal work.

It protects flow through exceptional intervention modes.

There are three operational intervention semantics.

---

## 24.1 Life Saver — `STOP`

Used for workflow-integrity failures such as:

- conflicting execution;
- incorrect command followed by correction;
- overlapping execution;
- bad routing;
- malformed/incomplete work dispatched;
- superseded instruction;
- dangerous system-level workflow inconsistency.

Life Saver may be triggered:

- automatically when a clear workflow-integrity failure is detected;
- manually by the user.

Command semantics:

> **STOP**

The system preserves execution state and prevents unsafe continuation while the workflow is corrected.

Life Saver is the strongest intervention class.

---

## 24.2 Consumption Emergency — `HOLD`

Used when model/token capacity becomes a critical execution constraint.

The Orchestrator receives temporary authority to change execution order.

Available commands include:

```text
HOLD
PRIORITY CHANGE
CONTINUE
RESUME
```

`HOLD` means:

- pause selected work at the nearest safe execution boundary;
- preserve task context/state;
- do not rollback;
- do not cancel;
- do not destroy work.

A held task does not automatically make its seat reusable.

The Orchestrator performs capacity-aware reassignment.

The seat may work on another task only if doing so is beneficial under:

- remaining capacity;
- dependency impact;
- temporary priority;
- expected token/model consumption.

Otherwise the seat remains Idle.

---

## 24.3 Other Emergency — `FREEZE`

Used for critical blockers or exceptional conditions where the affected execution cannot safely continue until a decision/correction occurs.

`FREEZE` affects the relevant execution rather than automatically invoking a Life Saver system-wide stop.

The Orchestrator resolves/routes the emergency and later sends correction + RESUME directly to the affected Agent.

---

# 25. Orchestrator Direct Control During Emergency

During Emergency, the Orchestrator has temporary operational authority over execution order.

Example:

```text
Capacity / Dependency Risk
        ↓
Orchestrator
        ↓
HOLD affected work
        ↓
PRIORITY CHANGE
        ↓
CONTINUE dependency-critical work
        ↓
RESUME held work when safe
```

No PO/PM relay is required.

> **PM owns business priority. Orchestrator owns emergency execution order.**

Emergency execution priority is temporary.

It does not permanently rewrite PM Product Backlog priority.

---

# 26. Emergency Resume Authority

If the Orchestrator creates a HOLD or FREEZE, the Orchestrator owns its release.

The Orchestrator sends correction and RESUME directly to affected Agents.

```text
Orchestrator
    ↓ direct
HOLD / FREEZE
    ↓
resolution
    ↓
Correction / Priority Change
    ↓ direct
RESUME
    ↓
Affected Agent
```

If user input is required:

```text
Orchestrator → User
User → Decision
Orchestrator → Affected Agent directly
```

No relay channel is inserted.

---

# 27. Idle Recovery

The Orchestrator distinguishes:

## Healthy Idle

No actionable work exists.

No intervention required.

## Stalled Idle

Unfinished/ready/blocked work exists but nothing is executing.

The Orchestrator detects why flow stopped and restores the appropriate execution path.

---

# 28. Usage and Capacity Model

Claude/model execution capacity is a **Company-level shared resource**.

Products do not receive hard token quotas.

Capacity monitoring considers relevant usage windows, including:

- approximately 5-hour execution window;
- weekly usage window;
- Sprint forecast.

The architecture should verify during implementation what usage data can be retrieved reliably/programmatically rather than assuming unsupported structured fields.

---

# 29. Shared Flexible Capacity

Capacity is shared flexibly.

There is no fixed hard quota such as:

```text
Product A = 40%
Product B = 30%
Product C = 30%
```

Likewise, Projects inside a Product do not receive rigid token quotas.

Usage is forecast and attributed for analysis, but unused capacity remains available to other work.

---

# 30. Forecast-Based Capacity Thresholds

There is no universal static percentage such as:

```text
80% = Critical
```

Capacity state is forecast-based.

Conceptually:

```text
Projected Remaining Capacity
vs
Projected Capacity Required
for protected / dependency-critical work
before reset
```

A lower usage percentage may be critical when substantial dependency-critical work remains.

A higher usage percentage may be acceptable when little important work remains.

---

# 31. Usage Monitoring

The Orchestrator is the **canonical usage monitor**.

Agents may also perform direct usage checks when necessary.

Usage checking is not mandatory for every task.

Monitoring should combine event-driven and sensible periodic checkpoints, such as:

- beginning an execution window;
- before expensive work;
- after significant work completion;
- scaling decisions;
- detected Capacity Risk;
- long-running execution checkpoints.

Agents do not independently change Company execution flow based on usage.

If an Agent detects Capacity Risk:

```text
Agent
  ↓
CAPACITY_RISK signal
  ↓
Orchestrator
  ↓
recalculate forecast
  ↓
CONTINUE / HOLD / PRIORITY CHANGE
```

The signal should include relevant information such as:

- current task;
- remaining work estimate;
- dependency state;
- available usage reading when known.

---

# 32. Dependency-Aware Priority

Inside a Product, dependencies affect execution ordering.

A lower business-priority task may temporarily execute before a higher-priority task when it unlocks blocked downstream work.

Execution ordering may consider:

```text
Business Priority
+ Dependency Impact
+ Critical Path
+ Capacity
```

This does not permanently change PM business priority.

When consumption becomes critical, the Orchestrator may temporarily reorder execution directly.

---

# 33. Dependency Graph

Every Product has an independent machine-readable Dependency Graph.

Dependencies may cross Projects **inside the same Product**.

Dependencies may **never cross Products**.

Valid:

```text
Product A
├── Project A1 / Task X
│       ↓ BLOCKS
└── Project A2 / Task Y
```

Invalid:

```text
Product A / Task X
    ↓ BLOCKS
Product B / Task Y
```

Competition between Products for Claude/model capacity is a **Company Capacity issue**, not a dependency.

Dependency relationships should be explicit, such as:

- `BLOCKS`
- `IS BLOCKED BY`

Any Agent may record a genuine technical/execution dependency directly.

If the discovered relationship actually changes business scope or business sequencing, it must go to the appropriate PO/PM authority instead of being silently treated as a technical dependency.

Dependency cycles are invalid by design and should not be created.

---

# 34. Product-Level Capacity Conflicts

Multiple Projects may share capabilities inside one Product.

Example:

```text
PO-Mobile ─┐
           ├── Backend demand
PO-Web ────┘
```

The system first evaluates whether existing seats and available execution capacity can handle the demand.

If additional parallelism genuinely improves throughput and token/model capacity supports it, another seat may be activated.

If the bottleneck is model/token capacity, do **not** add a seat.

If a real Project-level capacity conflict remains, the **PM** is the Product-level authority for prioritisation.

---

# 35. Company-Level Consumption Emergency

When shared Company execution capacity becomes critical, Product PMs cannot independently solve the conflict.

Dependencies/critical path and protected in-progress work are evaluated first.

If a real trade-off remains, this becomes an Orchestrator Consumption Emergency.

The Orchestrator may:

- HOLD work;
- temporarily change execution priority;
- CONTINUE selected work;
- RESUME held work later.

When a business trade-off requires human authority, the Orchestrator asks the user directly.

Example:

```text
Capacity Critical
      ↓
Dependency / Critical Path Analysis
      ↓
Cannot safely resolve automatically
      ↓
Orchestrator
      ↓
User
      ↓
Continue X / Hold Y / Wait for reset
      ↓
Orchestrator issues direct commands
```

---

# 36. Sprint Scope

The Sprint is a **Development cadence**, not a Company cadence.

It applies to development work and the work flowing through its delivery/review cycle.

PO, PM, executives, shared Company-level resources and System Maintenance are not constrained to only work during a Sprint.

---

# 37. Sprint Schedule

Sprint schedule:

```text
Monday
  ↓
Sprint automatically opens
  ↓
...
  ↓
Friday 19:00
  ↓
Sprint automatically closes
```

No Agent manually opens or closes the Sprint.

The calendar is the trigger.

The Sprint closes Friday at 19:00 regardless of whether all work is complete.

---

# 38. Sprint Close and Carry-Over

At Sprint close, the system snapshots final state.

Example:

```text
Done
Development
Review
QA
Blocked
Other Product-specific states
```

Any unfinished Sprint work moves into the backlog for the next Sprint preparation.

This includes unfinished work in Development, Review/QA or other relevant Sprint states.

The PO handles carry-over/replanning for its Project during weekend preparation.

Carry-over should record useful metadata such as:

- carried-over status;
- previous Sprint;
- state at close.

Carry-over is a **signal**, not automatically a Defect.

The retrospective determines why it happened.

---

# 39. Weekend Sprint Preparation

PO may prepare the next Sprint on Saturday/Sunday.

Inputs include:

- PM Product priorities;
- carried-over work;
- new Product Backlog work;
- dependencies;
- available capacity;
- system capacity recommendation;
- historical throughput;
- expected model/token availability.

The PO owns final Project Sprint composition within guardrails.

---

# 40. Capacity Recommendation

The system recommends Sprint capacity.

The recommendation may consider:

- historical throughput;
- available seats;
- model/token budget;
- expected complexity;
- carry-over;
- parallelisability;
- dependency constraints;
- previous Sprint consumption;
- recent rework/validation history.

If the previous Sprint exhausted most available model usage, the correct response may be to **reduce Sprint load**, not activate more seats.

The planning system must remain highly flexible.

---

# 41. Soft and Hard Capacity Guardrails

Sprint capacity recommendations are soft by default.

## Soft Warning

The PO may override the recommendation.

## Hard Capacity Guardrail

Used only when the forecast indicates the proposed scope is effectively impossible under known execution constraints.

PO and PM cannot override a Hard Capacity Guardrail.

Exceptional override authority belongs to the user/CEO.

```text
Soft Warning
→ PO may decide

Hard Capacity Guardrail
→ cannot proceed normally

Exceptional Override
→ User/CEO only
```

---

# 42. Flexible Sprint Scope

Sprint scope is intentionally flexible.

During the Sprint, PO may:

- add work;
- remove Ready work;
- reprioritise;
- replace planned work.

Changes must be tracked with:

- what changed;
- when;
- reason;
- actor.

This lets retrospective analysis distinguish:

- estimation failure;
- capacity failure;
- blocker;
- deliberate scope change.

Capacity guardrails continue to apply to mid-Sprint additions.

---

# 43. In-Progress Work and Scope Changes

Changing Jira/Sprint scope does not automatically interrupt active execution.

PO may freely manage Ready/Backlog work.

If already-running work must actually pause, the appropriate Orchestrator intervention semantics are used.

> **Jira scope change ≠ automatic HOLD/FREEZE.**

This prevents accidental context loss or conflicting execution.

---

# 44. Weekly Retrospective

Every week/Sprint close triggers an automatic retrospective.

The retrospective evaluates the entire operating system, not only developers.

Participants/data sources include:

- Developers
- PO
- PM
- QA
- shared capabilities
- executives when involved
- Analyst
- Orchestrator
- System Maintenance activity
- system-level intervention events

The fact that a role is outside the Development Sprint does not exclude it from weekly measurement.

---

# 45. Retrospective Metrics

Useful telemetry includes:

- expected Work Effort;
- completion;
- actual rework;
- validation failures;
- defects;
- blockers;
- escalations;
- model used;
- reasoning level;
- token/model consumption;
- outcome quality;
- completion success;
- carry-over;
- capacity utilisation;
- idle time;
- seat scaling;
- Orchestrator interventions;
- HOLD events;
- FREEZE events;
- Life Saver / STOP events;
- estimation accuracy;
- recurring workflow failures.

The exact dashboard may evolve as evidence accumulates.

---

# 46. Analyst Retrospective Responsibility

At weekly close, Analyst performs analysis over collected evidence.

Analyst produces:

- problems;
- defects;
- recurring patterns;
- inefficiencies;
- lessons;
- capacity findings;
- model/reasoning findings;
- estimation findings;
- dashboard/reporting.

Analyst does not modify system rules.

> **Analyst measures.**

---

# 47. System Maintenance Mode

System Maintenance Mode owns improvement of Thebes itself.

It is separate from normal Product execution.

Current Phase 1 behaviour:

> The Main Claude session may enter System Maintenance Mode under direct user instruction and modify the architecture/system itself without delegating to Product Agents.

Future possibility:

```text
Thebes
├── Orchestrator / Runtime
└── Thebes Maintainer / System Architect
```

A dedicated Maintainer is not required yet.

---

# 48. System Maintenance Lifecycle

System Maintenance:

- has no Sprint;
- is not governed by Product Sprint timing;
- has no Jira Product ticket requirement;
- can operate while a Sprint is running;
- can operate while development is idle;
- works directly with the user;
- maintains the Thebes workflow/agent architecture.

System Maintenance work is **not placed on Jira**.

Jira remains Product work lifecycle only.

---

# 49. Automatic Learning Loop

At each weekly close:

```text
Weekly Close
    ↓
Collect Execution Evidence
    ↓
Analyst
    ↓
Analysis + Dashboard
    ↓
System Maintenance Mode
    ↓
Learning Review
    ↓
Update Operational Learning
```

Potential updates include:

- General Execution Policy;
- Role Learning Profiles;
- model selection guidance;
- reasoning guidance;
- estimation guidance;
- efficiency rules;
- scaling recommendations;
- recurring failure prevention;
- Orchestrator learning.

The Orchestrator itself is subject to retrospective analysis and learning.

---

# 50. Constitutional Change Protection

System Maintenance may improve operational learning automatically.

However, it must not autonomously rewrite foundational governance.

Examples requiring user approval:

- authority boundaries;
- constitutional rules;
- fundamental role ownership;
- destructive safety policy;
- executive responsibility;
- core governance model.

A retrospective may recommend such a change, but the user governs constitutional changes.

---

# 51. System Maintenance vs Orchestrator

The separation is:

> **Orchestrator operates and protects the system. System Maintenance improves the system.**

Orchestrator:

- runtime coordination;
- canonical usage monitoring;
- Idle Recovery;
- Emergency intervention;
- Life Saver;
- exception redirection;
- direct flow-control commands.

System Maintenance:

- retrospective learning;
- workflow improvement;
- agent architecture maintenance;
- learning-file updates;
- execution-policy improvement;
- routing/scaling policy refinement.

The Orchestrator does not autonomously redesign itself.

---

# 52. Completion Route

Completion Route is predetermined in the Execution Profile.

Agents do not invent the next workflow route after finishing Development.

All implementation follows:

```text
Development
    ↓
Review
    ↓
Self / Peer / QA route
    ↓
Done
```

This keeps execution consistent across Claude sessions.

---

# 53. Product Independence

Products are independent execution domains.

Each Product may have:

- its own Jira board/workflow;
- PM;
- DevOps;
- Projects;
- Project-level POs;
- Product Dependency Graph;
- backlog priorities.

Company-level shared capabilities and Claude/model usage may be shared resources.

Shared resource contention does not create Product-to-Product dependencies.

---

# 54. Architecture Summary

The target operating model can be summarised as:

```text
USER / CEO
     │
     ├────────────── System Maintenance Mode
     │                    │
     │                    └── improves Thebes itself
     │
     ↓
ORCHESTRATOR
     │
     ├── protects runtime flow
     ├── monitors shared execution capacity
     ├── handles Idle Recovery
     ├── handles Emergency
     └── handles Life Saver

NORMAL PRODUCT WORK
     │
     ↓
Product Jira Board
     │
     ├── PM → Product Backlog + Product Priority
     │
     ├── PO-A → Project A Sprint
     ├── PO-B → Project B Sprint
     └── PO-C → Project C Sprint

Capability Queues
     │
     ├── Frontend
     ├── Backend
     ├── UX Engineer
     ├── QA
     ├── DevOps
     └── other capabilities

Execution Profile
     ↓
Development
     ↓
Review
     ├── Self Review
     ├── Peer Review
     └── QA Review
     ↓
Done
```

Supporting layers:

```text
Persistent State
→ canonical operational/project context

Role Learning
→ execution optimisation

Analyst
→ measurement + retrospective analysis

System Maintenance
→ system learning + improvement

Git
→ code + architecture + durable decisions

Jira
→ Product work lifecycle
```

---

# 55. Phase Roadmap

The agreed roadmap remains gradual.

## Phase 1 — Current

Fix the Claude Agent Architecture only.

## Phase 2

Prove the architecture through real Product work.

## Phase 3

Introduce a separate Listener.

## Phase 4

Connect Codex → Listener.

## Phase 5

Evolve Listener into Thebes Core.

## Phase 6

Add RAG when scale justifies it.

Do not prematurely implement later phases during Phase 1.

---

# 56. Future Codex Context Principle

Long-term architecture:

```text
User ↔ Codex
        ↓
agree on intent
        ↓
Codex → Thebes
        ↓
Thebes determines execution context
        ↓
Claude Code / other execution engines
```

Core rule:

> **Codex never briefs Claude. Codex briefs Thebes. Thebes briefs Claude.**

Context separation:

1. **Codex Context** — discussion and decision.
2. **Thebes Context** — canonical persistent state.
3. **Claude Context** — minimum context required for execution.

This future architecture is **not part of the current Phase 1 implementation**.

---

# 57. Pre-Implementation Review Gate

Before implementation:

1. Review this Target Architecture Specification.
2. Correct any architecture mismatch.
3. Explicitly approve the target architecture.
4. Only then produce one consolidated Claude Code implementation prompt.
5. Claude Code remains the sole writer to the repository during the redesign.

No implementation should be inferred from unresolved architecture assumptions.

---

## End State

The intended result is a system where:

- specialists execute autonomously;
- management layers do not consume tokens as routine relays;
- Product priorities remain owned by Product leadership;
- Project Sprint execution remains owned by Project POs;
- work moves through deterministic capability queues;
- validation is explicit and predictable;
- additional seats appear only when they increase real throughput;
- shared Claude usage is forecast rather than blindly consumed;
- dependencies influence execution without corrupting business priority;
- emergencies are handled directly by the Orchestrator;
- no relay chains exist;
- weekly evidence drives measurable system learning;
- System Maintenance improves the operating system continuously;
- durable state survives sessions;
- and the architecture can later evolve into Thebes without rebuilding its fundamental operating principles.
