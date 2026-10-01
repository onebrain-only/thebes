# Thebes program roadmap

Current as of 2026-09-12. Canonical repository: `onebrain-only/thebes`.
Canonical checkout: `~/Desktop/Thebes-Canonical`. Do not create another clone.

## Current position

**CURRENT FACT — MODE: `PRODUCT_EXECUTION` (the store is authoritative: `store.current_operating_mode()`; this line was stale from 2026-09-12 until 2026-09-15). A bounded CEO standing grant `authz-8d4844a9-2c91-4dc4-b085-92b4bd7d88d8` is active with 2 of 10 items remaining (KAN-207, KAN-208); it is a Persistent State record, not a roadmap selection, so the `PRODUCT_EXECUTION_AUTHORIZED` line below stays NO.**
**CURRENT FACT — CURRENT PHASE: Phases 1–5 CLOSED. No phase is current. MAINTENANCE_BASELINE: STABLE. PRODUCT_DEVELOPMENT_READY: YES. Phase 6 DEFERRED; RAG NOT JUSTIFIED. QA LAYER INTEGRATION (2026-09-15) CLOSED — see "Professional QA layer integration" below.**
**CURRENT FACT — This is a maintenance FREEZE. Thebes infrastructure changes are now evidence-driven by real Product work only. Do not open another infrastructure milestone without one.**
**CURRENT FACT — PRODUCT_ACCEPTANCE_STATUS: KAN-183 COMPLETE — the first real single-task run driven end to end by Thebes**
**CURRENT FACT — PRODUCT_EXECUTION_AUTHORIZED: NO — KAN-183's bounded authorization was consumed on completion 2026-09-14, and Phase 3 created none**

**Final operations hardening closed 2026-09-15**, and with it the infrastructure programme.
The routine Product pilot that ran under `authz-5323c2c9-4ac0-4a0a-914b-c4aaefa47ce3` is
**stopped**: the CEO changed Product direction, the authorization is REVOKED with its full
history preserved, and KAN-184 is parked — unowned, returned to Jira Backlog, its migration
draft and executor worktree kept as evidence rather than deleted. No Product work is
authorized and none can start. See "Final operations hardening" below.

Post-Wave-8 Operational Hardening is closed. Phase 5 closed on 2026-09-15 against the criteria
in `agent/MASTER_ROADMAP.md` §40; the closure record and its evidence are in "Phase 5 closure"
below. **Thebes Core exists** as `agent/core` — the addressable composition of the
responsibilities §37 names, hosted by the long-running intake process — and it owns one
canonical answer to what happened to a submitted intent. Like Phases 3 and 4, Phase 5 is Thebes
infrastructure only: it selected no Product work, created no Product authorization, and left
Jira, Supabase, the Product repository and Persistent State byte-identical.

Phase 4 closed on 2026-09-15 against the criteria in `agent/MASTER_ROADMAP.md` §34 and the
CEO's Phase-4 brief; the closure record and its
evidence are in "Phase 4 closure" below. **The operational front door is now
`python3 -m agent.listener submit <WORK-ITEM>`** — the Controller's orchestrating commands are
launched by the Listener and refuse a direct operational invocation. Like Phase 3, Phase 4 is
Thebes infrastructure only: it selected no Product work, created no Product authorization, and
left Jira, Supabase, the Product repository and Persistent State byte-identical.

Phase 3 closed on 2026-09-15 against the criteria in `agent/MASTER_ROADMAP.md` §30 and the
CEO's Phase-3 brief; the closure record and
its evidence are in "Phase 3 closure" below. Phase 3 is Thebes infrastructure only — it
selected no Product work, created no Product authorization, and left Jira, Supabase, the
Product repository and Persistent State byte-identical.

Phase 2 closed on 2026-09-14 against the criteria in `agent/MASTER_ROADMAP.md`; the closure
record and its evidence are in "Phase 2 closure" below. KAN-198 was the first real Product proof under manual orchestration
(its original normalized receipt was lost when controller observation ended while the provider
continued; that history is not rewritten, and the corrected path now persists every terminal
result before lease closure). **KAN-183 is the proof that closes the phase**: a single
work-item key carried from CEO intent to authoritative Jira Done by Thebes, with no human
authoring the brief, creating the worktree, recording the verdict, committing, integrating, or
moving Jira.

Closure does not select further Product work, alter Product Jira lifecycle, touch production,
or begin Phase 3. One live dependency observation and several hardening items are recorded
below as explicitly deferred and non-blocking.

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
| Post-Wave-8 Operational Hardening | CLOSED | Corrected real-operation defects, isolated Product from maintenance, established durable program memory, and removed permanent provider coupling. Closed after accepted provider-path remediation `ecac35d` and the final closure review. |
| Phase 2 — Tangible Operating Interface / Product Proof | **CLOSED 2026-09-14** | Objective: prove Thebes can operate real Product work safely and correctly. Accepted on the evidence in "Phase 2 closure" below — KAN-183 carried a real work item from a CEO-supplied key to authoritative Jira Done through the flow, plus KAN-186's real PEER proof and the deterministic full-flow suites. One live dependency observation is deferred and non-blocking. Closure is not a claim of autonomous backlog execution, and no normal Product execution is authorized. |
| Phase 3 — Separate Listener | **CLOSED 2026-09-15** | Objective: separate intake from execution orchestration, so a CEO instruction enters Thebes without anyone invoking the Controller by hand. Accepted on the evidence in "Phase 3 closure" below — a separately running loopback Listener with a durable, idempotent intent boundary that dispatches to the existing Controller in its own process and carries a correlated CEO decision back into the existing approval/continuation machinery. Closure is not a claim of remote access, authentication, or autonomous intake: transport is loopback-only and unauthenticated by design, and the Controller's authorization gate is unchanged. |
| Phase 4 — Codex → Listener integration | **CLOSED 2026-09-15** | Objective: make the Listener the normal external operational intake boundary, so a controller conversation expresses intent rather than invoking the Controller. Accepted on the evidence in "Phase 4 closure" below — the front door moved and is enforced rather than documented, the executor firewall learned that the Listener exists, and the Controller's authority is unchanged. Closure is not a claim of authentication, remote access, or natural-language intake: transport stays loopback-only and the intent contract is unchanged from Phase 3. |
| Phase 5 — Listener evolves into Thebes Core | **CLOSED 2026-09-15** | Objective (§36): clean separation between Conversation, Canonical Company and Execution intelligence. Accepted on the evidence in "Phase 5 closure" below — `agent/core` is the addressable composition of every responsibility §37 names, the Listener is its intake subsystem, and one derived lifecycle replaces the two records that could previously disagree. Closure is not a claim of a rewritten orchestration engine, of learning gaining influence, or of autonomous operation: Core reimplemented nothing, learning stayed inert, and every run is still one CEO-authorized work item. |
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

Closure evidence: `fe997bb`, provider-path remediation `ecac35d`, and the final closure
review. The operational-hardening suite passed 38 checks at closure; the full State suite
passed 1,461 checks.

| Area | State | Boundary / evidence |
| --- | --- | --- |
| Operating-mode isolation | COMPLETE | `e3cf8c6`, `834b071`, `4948607`, `fe997bb`; claims and wakes are refused in maintenance, with wake authorization serialized by execution leases. Human authorization is still a governance gate, not authenticated by the setter. |
| Observation → investigation | COMPLETE | `agent/state/operations.py` and operational-context tests distinguish reported conditions from explicit reproduction requests. |
| Reported environment authority | COMPLETE | Operational context derives the primary target from the reported environment; local Flutter Chrome is not silently converted into browser automation. |
| Causal-surface validation | COMPLETE | Diagnosis records causal/changed surfaces and derives required versus optional validation targets. |
| Shared program documentation | COMPLETE | Roadmap, program memory, decision log, learning log, chronology and concise entry-point wiring agree on the closed hardening milestone and pending Product authorization. |
| Executor/provider abstraction | COMPLETE | Slices 1–3 added the neutral contract, neutral Seat/Role authority and byte-identical Claude renderer. Slices 4–6 added provider seams, normalized outcomes and the Codex CLI adapter. Slice 7 selects deterministically; remediation `ecac35d` wires selection and receipt into the wake, with one selected provider and no retry or fallback. |
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
invokes a provider. The neutral Seat/Role registry and execution contract now exist; Claude
rendering and wake preparation consume them without taking core authority. The actual Agent-tool
transport remains controller-native and external to the repository. Claude and Codex outcomes are
normalized into provider-neutral evidence, with provider failure distinct from execution failure.
Codex uses its local CLI adapter. Deterministic selection gates capability/model/effort fit and
an authorized explicit override; it never retries, falls back or changes workflow truth.

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

**Historical record — consumed, does not authorize current or future Product execution.**
On 2026-09-12 the CEO granted a third explicit, ticket-specific, non-renewing chat authorization
("CONTINUE EXISTING PRODUCT TICKET CLOSURE") naming **KAN-183**
(`public.set_session_user`: session-scope `request.jwt.claims` poisoning primitive; AC1 requires
verifying PostgREST's actual connection-pooling mode before selecting an implementation branch).
That authorization does not permit backlog burn-down, autonomous next-ticket selection,
Operational Hardening closure, Product Acceptance, continued Product execution after this one
ticket, or any provider-abstraction change. Authorization reference: CEO chat message,
2026-09-12, "CONTINUE EXISTING PRODUCT TICKET CLOSURE ... I explicitly select and authorize:
KAN-183". Selected ticket: KAN-183. Acceptance result/evidence:
BLOCKED — AC1 resolved technically (session-sharing IS possible: PostgREST holds a single
long-lived direct Postgres backend, not a transaction-mode pooler; live pg_stat_activity
evidence, 15+ day session age). AC4 found already satisfied live (`set_session_user`'s
`proacl` already excludes anon/authenticated; no revoke needed). AC3's fix (`set_config`
third argument `false`→`true`, CREATE OR REPLACE, body otherwise verbatim) was authored but
`apply_migration` was denied three times (twice, then once more under an explicit CEO retry
authorization) by the Claude Code harness's own auto-mode permission classifier — not
Persistent State, not Jira, not anything Thebes governance controls. Verbatim denial:
"Blocked by classifier ... To allow this type of action in the future, the user can add a
Bash permission rule to their settings." Resolution is a CEO-side settings action, not a
workflow action; no further retry was attempted after the third denial. Ticket not
transitioned to Done; AC1 and AC4 remain resolved and unaffected; AC3/AC5 blocked pending the
CEO's permission decision.

**Historical record — consumed, does not authorize current or future Product execution.**
On 2026-09-12 the CEO granted a second explicit, ticket-specific, non-renewing chat authorization
("CONTINUE PRODUCT EXECUTION FROM THE LAST COMPLETED TICKET") naming **KAN-180**
(`public.can_view_post/3` and `public.rpc_meetup_rsvp/4`: caller-supplied profile-identity
parameters must not be authorization/attribution authority; effective identity must derive
internally from `auth.uid()`). That authorization does not permit backlog burn-down, autonomous
next-ticket selection, Operational Hardening closure, Product Acceptance, continued Product
execution after this one ticket, or any provider-abstraction change. Authorization reference:
CEO chat message, 2026-09-12, "CONTINUE PRODUCT EXECUTION FROM THE LAST COMPLETED TICKET ...
I explicitly select and authorize: KAN-180". Selected ticket: KAN-180. Acceptance result/evidence:
DONE. Finding A (`can_view_post`, both overloads) fixed (migration 20260912182108, commit
155b5a8 on Canary) and independently PEER-verified PASS (backend-4). Finding B
(`rpc_meetup_rsvp/4`) initially stopped on a genuine blocker — `can_current_user_rsvp_meetup`
referenced a non-existent `meetups.owner_user_id` column — resolved not by a new Jira ticket
but by canonical-evidence investigation: the `meetups` table's own live, active RLS policy
already keys authorization on `creator_user_id`, settling the identity question from existing
established Product behaviour rather than a new ruling. Fixed (migration 20260912190747,
commit 0ca0e1a on Canary: helper corrected to `creator_user_id`; `rpc_meetup_rsvp/4` now
derives the stored profile from the caller's own `auth.uid()`-resolved active profile instead
of trusting caller-supplied `p_profile_id`) and independently PEER-verified PASS (backend-4).
A ticket (KAN-197) was briefly created to carry Finding B's blocker and then corrected per
CEO direction that this closure phase finishes existing pending tickets without creating new
Product tasks — KAN-197 closed as created-in-error, its Persistent State dependency edge
retired, all remaining work folded back into KAN-180 itself. Three pre-existing, unrelated
defects were discovered during investigation and left untouched as out of scope (a broken
meetup-creation trigger, a nonexistent `friendships` table breaking `circle`-visibility reads,
and one consequent unreachable branch) — flagged to the CEO for visibility, not filed as
tickets. KAN-180 transitioned to Jira Done; Persistent State reconciled to canonical `done`.

**Historical record — consumed, does not authorize current or future Product execution.**
On 2026-09-12 the CEO granted one explicit, ticket-specific, non-renewing chat authorization
("CEO AUTHORIZATION — ONE BOUNDED PRODUCT TICKET") naming **KAN-187**
(`trgfn_organiser_profile_persona_guard`: stale `organiser_profiles` table name in its
`RAISE EXCEPTION` message text; diagnostic-only, no logic/permission/trigger change). That
authorization did not permit backlog burn-down, autonomous next-ticket selection, Operational
Hardening closure, Product Acceptance, continued Product execution after that one ticket, or any
provider-abstraction change. The bounded run executed KAN-187 only: PEER review PASS, Jira
transitioned to Done/resolution Done, Persistent State lifecycle reconciled to `done`, one Product
commit (`cc45b5c` on Canary). The operating mode was transitioned `SYSTEM_MAINTENANCE` →
`PRODUCT_EXECUTION` for the run and restored to `SYSTEM_MAINTENANCE` on completion, with no
execution leases left open. **The authorization was consumed by that single ticket and does not
carry forward** — it establishes no ongoing or future Product authorization and must not be read
as broader Product acceptance.

**Historical record — consumed, does not authorize current or future Product execution.** On 2026-09-13 the CEO authorized
one newly created Product work item only after a live Jira search confirmed no exact unresolved
ticket exists: **KAN-198**, `Search — Recent item remove and Clear All actions do not clear
history`. Authorization reference: CEO chat message, 2026-09-13, "Continue ... create exactly
ONE bounded Jira work item ... Continue the SAME run". Scope is limited to the CEO-reported
Social Search recent-history removal and clear-all defect, its canonical Thebes lifecycle,
implementation, required validation and legitimate Jira completion. It authorizes neither a
second ticket nor another backlog item, Phase 3, normal Product execution, or any unrelated
Product, security, production, or Thebes work. This authorization is non-renewing and expires
when KAN-198 reaches a terminal lifecycle result or a genuine authority boundary is reported.

Authorization reference: CEO chat message, 2026-09-13, recorded above.
Selected ticket: **KAN-198**.
Acceptance result/evidence: **DONE.** Frontend Preflight recorded Work Effort 2 and a
capacity-derived due date; the ticket reached Ready, was claimed by `frontend-1`, executed once
by Codex CLI, independently QA-passed, and reached Jira Done. The exact lease closed. The
provider process continued after controller observation ended, so its original normalized receipt
was lost and remains absent; it is not reconstructed. The bounded Phase 2 repair persists all
later normalized terminal results before lease closure and has deterministic recovery evidence.
Normal Product authorization reference: **none**.

**Current authorization — bounded to this one run only.** On 2026-09-13 the CEO explicitly
selected **KAN-186** for one end-to-end Product Acceptance run. Scope is restricted to this
ticket's Jira acceptance criteria, its canonical Thebes lifecycle, one deterministic provider
dispatch, required PEER validation, bounded same-executor remediation if needed, Git integration,
and final Jira lifecycle reconciliation. It authorizes no other ticket, no fallback after Claude
dispatch, no bypass of native production permissions, and no normal Product execution after this
run. Authorization reference: CEO chat message, 2026-09-13, "Run exactly ONE Jira task
end-to-end: KAN-186".
Selected ticket: KAN-186
Acceptance result/evidence: BLOCKED — KAN-186 was observed in Jira Ready and reached the
canonical claim gate. Its only durable executor evidence names backend-8, but backend-8 already
owns KAN-184; `store.claim` refused a second concurrent ownership. No provider was dispatched,
no Product code or migration was changed, and no execution lease was opened. The controller
restored SYSTEM_MAINTENANCE. A CEO selection of an eligible backend seat, or completion/release
of KAN-184 by its owning workflow, is required before KAN-186 can resume; this single-ticket
authorization does not authorize work on KAN-184.

**Current authorization — bounded to this one run only.** On 2026-09-13 the CEO renewed the
single-task Product acceptance authorization for **KAN-186** after the verified controller
capability-pool allocation remediation (`3afb9d6`). Scope is limited to KAN-186's current Jira
acceptance criteria, one canonical controller execution, same-capability PEER validation, bounded
same-executor remediation if required, Git integration, and final Jira lifecycle reconciliation.
It authorizes no other ticket, no Product-provider fallback after Claude dispatch, no bypass of
native production permissions, and no normal Product execution after this run. Authorization
reference: CEO chat message, 2026-09-13, "Continue the existing Phase 2 bounded Product
acceptance work ... Target remains: KAN-186".
Selected ticket: KAN-186
Acceptance result/evidence: BLOCKED — canonical capability-pool allocation selected backend-2,
proving the prior backend-8 ownership no longer controls allocation. The atomic claim gate then
refused KAN-186 for `surface-contention` with KAN-184's active ownership: both declare
`public.user_reputation_events` as a logical surface. No provider was dispatched, no Product code
or migration changed, no receipt or execution lease was created, and the controller restored
SYSTEM_MAINTENANCE. KAN-184 is outside this authorization; its owning workflow must complete or
release it before KAN-186 can be claimed without bypassing canonical contention rules.

**Current authorization — bounded to this one run only.** On 2026-09-13 the CEO explicitly
continued the Phase 2 single-task acceptance test for **KAN-186** after KAN-184's stale claim was
released through the existing safe recovery path. Scope is only KAN-186's current Jira criteria,
one canonical controller execution, same-capability PEER validation, bounded same-executor
remediation, Git integration, and final lifecycle reconciliation. No other Jira ticket, no
post-dispatch provider fallback, no native-permission bypass, and no further Product work is
authorized. Authorization reference: CEO chat message, 2026-09-13, "Run exactly ONE Product task
end-to-end: KAN-186".
Selected ticket: KAN-186
Acceptance result/evidence: BLOCKED — KAN-186 entered PRODUCT_EXECUTION, capability allocation
selected backend-2, claim succeeded, and the canonical selector dispatched Claude Code exactly
once. The normalized terminal result was persisted before its exact lease closed. Claude
independently re-derived the 20 blocking FKs (13 Part A, 7 named Part B exclusions) and confirmed
the `posts_author_user_profile_fkey` ON UPDATE RESTRICT landmine, but native
`mcp__claude_ai_Supabase__apply_migration` permission was denied in don't-ask mode. No bypass,
Product mutation, Jira transition, or provider fallback occurred. The claim and durable receipt
are preserved; the controller restored SYSTEM_MAINTENANCE pending a CEO-side permission decision.

**Historical record — consumed, does not authorize current or future Product execution.**
On 2026-09-14 the CEO ruled KAN-186 a standalone Part-A structural deliverable and authorized
completion after authoritative production verification, provenance correction, SELF, canonical
PEER, truthful Jira evidence and lifecycle reconciliation, with AC3/AC4 explicitly deferred and
destructive account-erasure demonstration prohibited.
Selected ticket: KAN-186
Acceptance result/evidence: **DONE.** The migration had in fact already been applied —
`apply_migration` succeeded at 2026-09-14 10:56:53, ledger version `20260914105653` — some hours
before a 2026-09-14 15:16 Jira reconciliation comment that asserted `NOT_APPLIED / 0-of-13 CASCADE /
resume at MIGRATION`. That comment was stale in both directions (it also called the migration file
uncommitted, when it had been committed at `0cf7bf4`). Acting on it would have attempted a replay.
A replay interlock was run first and `apply_migration` was never called. Live readback, independently
re-derived three times: blocking FKs on `public.profiles` 20 → 7, all 13 in-scope constraints CASCADE
and `convalidated`, the `posts_author_user_profile_fkey` `ON UPDATE RESTRICT` landmine preserved, the
7 Part-B constraints untouched and still RESTRICT, `delete_my_account()` body untouched, row counts
unchanged. Provenance corrected in `fe7b4be` (filename pinned to the ledger version, false
"NOT APPLIED" header rewritten, DDL byte-identical to `0cf7bf4`). PEER PASS by backend-5, independent
of both evidenced executors. AC1/AC2/AC5/AC6 pass; **AC3/AC4 deferred and not authorized — no claim
is made that end-to-end account erasure works.** Jira Done, Persistent State reconciled, ownership
released, zero open leases, SYSTEM_MAINTENANCE restored. Recorded for Part B: the removed `23503`
errors were an incidental safety net on *every* profile-deletion path, not only `delete_my_account()`.

Existing Product ownership and lifecycle remain in Persistent State/Jira and are not
copied here.

**Current authorization — KAN-186 final completion only.** The CEO explicitly authorized
the already-owned `backend-2` continuation through the existing foreground-only Claude Code
provider. Scope is limited to the existing Part-A migration at project
`wtncuzcskpigqpmnxwws`, authoritative catalogue readback, Product acceptance, backend-2 SELF,
a distinct eligible backend PEER review (and its bounded canonical remediation if needed),
safe Canary integration, and KAN-186's normal Jira completion lifecycle. This does not
authorize another ticket, Part B, a compensating migration, provider fallback, or a bypass of
provider-native permissions. Authorization reference: CEO chat message, 2026-09-14,
"KAN-186 — FINAL PRODUCT EXECUTION AND COMPLETION".
Selected ticket: KAN-186
PRODUCT_EXECUTION_AUTHORIZED: NO — consumed by KAN-186's completion, 2026-09-14

**Marker corrected 2026-09-14 at Phase 2 closure.** This block previously ended with an
affirmative authorization marker. That marker was stale: KAN-186 reached Done and the
authorization was consumed, but `controller.RoadmapAuthorization` reads the flag as a substring
over the whole file, so a single surviving affirmative marker anywhere kept the *most recently
selected* ticket readable as authorized. Never write that literal string in this file except
as a genuine live grant — prose quoting it is indistinguishable from an authorization. At closure that meant KAN-183 — already Done — still resolved as
authorized. The prose record above is unchanged; only the machine-read flag is corrected to the
truth it always described. **Consequence: no Product execution is authorized, which is the
intended state at Phase 2 closure.**

**Current authorization — KAN-183, real single-task flow proof.** The CEO explicitly
authorized KAN-183 as the one selected Product work item for the first real end-to-end run
through the completed Thebes execution flow. Scope is limited to the Jira-defined KAN-183
scope: characterising and containing the `public.set_session_user` session-scope
identity-poisoning behaviour. Environment authority is PRODUCTION, primary target Supabase
project `wtncuzcskpigqpmnxwws`, and the grant is **READ-ONLY inspection only** — the
verification of PostgREST/pooling behaviour and current EXECUTE grants that the ticket's AC1
and containment criteria require. It does NOT authorize schema mutation, migration
application, grant/revoke mutation, data mutation, RLS or function changes, or any change to
production configuration or project settings; any such need stops at that exact CEO boundary.
Ownership stays with the existing owner `backend-1` through same-seat continuation; no new
competing claim and no manufactured due date. It does not authorize KAN-184, KAN-130,
KAN-191, KAN-195 or any other ticket.
Authorization reference: CEO chat message, 2026-09-14, "REAL SINGLE-TASK FLOW PROOF — KAN-183"
Selected ticket: KAN-183

Acceptance result/evidence (protocol step 5): **DONE — and this is the run that closes Phase 2.**
The CEO supplied one work-item key. Thebes derived the execution brief from canonical sources
(Jira summary/description/AC, `execution_profile`, `task.surfaces`, the Product/Project registry,
and the `operational_context` environment authority), preserved `backend-1`'s existing ownership
without a new claim, allocated the isolated worktree `exec/backend-1/KAN-183` bound to `fe7b4be`,
and dispatched a Product-only brief carrying no control-plane token.

The real Claude Code executor stopped twice at native permission boundaries and was resumed twice
through the canonical continuation path on its own session, under invocation-scoped CEO approvals
(`mcp__claude_ai_Supabase__execute_sql`, `Bash`, `Write` for the executor; a separate
`execute_sql` grant bound to the validator's own invocation and session). Executor grants were
never reused as validator authority.

Product outcome: AC1 was settled and resolved **in the unsafe direction** — PostgREST holds a
long-lived `authenticator` backend (17 days, `backend_start` reproduced to the microsecond by the
validator), so session-scoped `set_config` persists across requests and the "unreachable, close
it" branch does not apply. AC3 containment confirmed live and holding. The migration applies AC2's
pooling-independent structural fix and is deliberately unprefixed: **it is committed and
integrated but NOT applied to production**, which remains separate deployment authority.

Flow outcome: automatic SELF dispatch opened review context `review:KAN-183:self:1`; the validator
independently reproduced the live evidence and returned its own verdict; SELF PASS was recorded
through `store.record_review_result`; attribution passed; Product commit `2f007d5` was made;
serialized integration landed it on Canary as `05e38fb` (previous head `28e4fee`); Jira reached
**Done (10007)**, confirmed by an authoritative re-read; Persistent State reconciled to canonical
`done`; ownership released; the worktree was released with its branch kept; zero leases remained
open. `main` was untouched throughout, and no production mutation occurred.

No human authored the brief, created the worktree, recorded the verdict, committed, integrated,
moved Jira, or released ownership. **This authorization is consumed and does not carry forward.**
Normal Product authorization reference: **none**.

PRODUCT_EXECUTION_AUTHORIZED: NO — consumed by KAN-183's completion, 2026-09-14

## Phase 2 closure

**DECISION — Phase 2 is CLOSED and ACCEPTED, recorded 2026-09-14.**

Phase 2's objective was to prove Thebes can operate real Product work safely and correctly.
It is accepted on the evidence below. Closure is deliberately not a claim of perfection or of
autonomous backlog execution: Thebes runs **one authorized work item at a time**, and every run
still begins with an explicit CEO authorization recorded here.

### Evidence

Verified against Persistent State, Jira, Git and the test suites at closure, not from memory.

| # | Capability | Evidence |
| --- | --- | --- |
| 1 | Real single-task end-to-end Product execution | KAN-183 — key to authoritative Jira Done through the flow; result recorded in the acceptance protocol above |
| 2 | Canonical intent derivation | `agent/controller/intent.py`, `73ec03d`; KAN-183 ran with `brief_source: canonical-state` and no `--brief-file` |
| 3 | Product-only executor boundary | `agent/execution/brief.py` + firewall, `5288f40`; asserted against the live KAN-183 brief and every validator brief |
| 4 | Worktree isolation | `fcbb4b4`; KAN-183 ran in `exec/backend-1/KAN-183` bound to `fe7b4be` |
| 5 | Claims / leases | KAN-183 preserved `backend-1`'s ownership with no new claim; lease opened and closed; zero leases open at closure |
| 6 | Provider dispatch | Real Claude Code CLI, deterministic selection, no retry or fallback |
| 7 | `needs_input` continuation | Two real continuations on the same provider session; preparations `0a45996`, completion tail `384f788` |
| 8 | Invocation-scoped permission approvals | Four `execution_approval` records on KAN-183, bound to invocation + session; executor grants never reused as validator authority (`573f207`) |
| 9 | SELF validation | Real SELF dispatch and verdict on KAN-183, review context `review:KAN-183:self:1`, `a98ded9` + `c14b03b` |
| 10 | PEER validation | KAN-186 — real PEER PASS by `backend-5`, independent live read-only verification |
| 11 | PEER-fail remediation transfer | `ff3e645` — ownership now moves with the transfer; deterministic full-flow proof in `test_peer_fail_handoff.py` |
| 12 | QA route | Deterministic full flow, `test_validation_dispatch.py` |
| 13 | Product attribution | `worktrees.assert_attribution`; KAN-183 committed exactly its one declared surface |
| 14 | Product commit | `2f007d5` |
| 15 | Serialized Canary integration | `680d713`; KAN-183 landed as `05e38fb`, previous head `28e4fee` |
| 16 | Jira lifecycle completion | `069bbed`; KAN-183 Done (10007), confirmed by authoritative re-read |
| 17 | Persistent State reconciliation | KAN-183 canonical lifecycle `done`, written from the re-read |
| 18 | Ownership release | KAN-183 ownership `None` after confirmed Done |
| 19 | Workspace finalization | KAN-183 worktree released, branch kept |
| 20 | Environment authority through real Product work | `operational_context` drove a real read-only production target twice; AC1 settled from live evidence with zero mutation |
| 21 | Dependency blocking on real Product state | KAN-191 BLOCKS KAN-130; KAN-130 reports `dependency-blocked` and plans as `WAITING_DEPENDENCY` |
| 22 | Dependency resolution mechanism | `test_wave6.py`: a source in review still blocks, **only DONE satisfies**, and the edge stores no blocked/satisfied flag — satisfaction is derived, never written |
| 23 | Completed upstreams cease blocking, on real state | KAN-191 carries three inbound edges (KAN-170, KAN-190, KAN-192), all Done, and shows no `dependency-blocked` reason. The satisfied KAN-128 edge likewise no longer contributes to KAN-130's block |
| 24 | Backlog / sprint / multi-task planning | `agent/controller/backlog_plan.py`, `sprint_plan.py`; planning reflects dependency truth in admission classes |

Suite state at closure: State 1,491 passed; 21 execution/controller suites passing;
`validate.py --check` reports persistent state valid. One pre-existing State failure remains —
`test_wave6.py` "no fresh Jira read -> stale-jira" — unrelated to dependencies; every dependency
assertion in that suite passes. It predates this work and was not opportunistically repaired.

### What closure does not claim

Thebes does not select its own work, drain a backlog, or run unattended. Each run is one
CEO-authorized ticket. Native provider permissions are still denied by default and granted only
per invocation. Production mutation remains a separate authority that Phase 2 never exercised.

### Deferred — explicitly non-blocking

**DEFERRED_LIVE_PROOF**
- *Same-run dependency observation.* An upstream reaching Done **through Thebes** and its
  downstream unblocking in the same run has not been observed live. The mechanism is proven
  deterministically (row 22) and the real-state behaviour is evidenced (rows 21, 23). To be
  collected opportunistically from the next naturally admissible bounded dependency pair.
  KAN-191 — the only currently open upstream — must not be executed for this purpose: its
  acceptance criteria require production DDL across four tables and real account-deletion data
  mutation, which is precisely the sensitive scenario `MASTER_ROADMAP.md` says should not come
  first.

**DEFERRED_HARDENING**
- *Historical Done-ticket provenance audit.* KAN-169 and KAN-188 both reached Done with PEER
  PASS while their deliverables were never committed; both were recovered during the KAN-183 run
  (`c1077d7`, `28e4fee` on Canary). Other pre-Thebes Done tickets may carry the same gap. The
  attribution gate now prevents it going forward. No audit has been started.
- *Integration receipt observability.* A failed integration receipt omits an already-created
  `product_commit` SHA; the refusal evidence drops what the attempt established. Git remains the
  truth. Observed on KAN-183's first integration attempt; it blocked nothing.

**PRODUCT_DEPLOYMENT_FOLLOWUP**
- *KAN-183 migration not applied.* `kan183_set_session_user_containment.sql` is committed and
  integrated on Canary but deliberately unprefixed and **not applied** — production still carries
  the session-scope defect, and the validator confirmed session-sharing is possible. Applying it
  is Product/deployment authority, not unfinished Phase 2 work.

### Next

Superseded 2026-09-15: Phase 3 was authorized by the CEO's Phase-3 brief and is now CLOSED.
See "Phase 3 closure" below.

## Phase 3 closure

**DECISION — Phase 3 (Separate Listener) is CLOSED and ACCEPTED, recorded 2026-09-15.**

Phase 3's objective was to separate intake from execution orchestration: a CEO instruction must
be able to enter Thebes without anyone invoking the Controller by hand, survive process
boundaries, reach the existing Controller exactly once, return a durable result or authority
request, and let a correlated CEO response continue the same workflow through the machinery
Phase 2 already built.

It is accepted on the evidence below. **Closure is deliberately narrow.** The Listener is a
communication boundary and nothing else: it decides nothing about Product work, it is
loopback-only, it is not authenticated, and it grants no authorization the Controller did not
already own. No Product work was selected, no Product authorization was created, and the mode
never left `SYSTEM_MAINTENANCE`.

### Architecture

```text
CEO / local caller
   ↓ loopback HTTP, allow-listed intent
Thebes Listener            (python3 -m agent.listener serve — its own process)
   ↓ durable intent, idempotent
subprocess, argv array     (the OS enforces the boundary, not discipline)
   ↓
Thebes Controller          (python3 -m agent.controller — unchanged authority)
   ↓
existing orchestration: authorization, claim, lease, provider, validation, integration, lifecycle
   ↓
durable Listener result / authority request
   ↓
CEO
```

Entry point `agent/listener/`; contract, durable inbox/outbox, restart semantics, the authority
loop and the operator commands are documented in `agent/listener/README.md`. The boundary's
rationale is `agent/DECISIONS.md` D-017, D-018 and D-019.

### Evidence

Verified against the repository, the running processes, Persistent State and the suites at
closure, not from memory.

| # | Criterion | Evidence |
| --- | --- | --- |
| A | Separate entry point | Live: `python3 -m agent.listener submit KAN-183` and `KAN-191` both reached the real Controller. No human invoked `python3 -m agent.controller` for either |
| B | Process boundary | The Listener ran as pid 11029 bound to `127.0.0.1:8787` (`lsof` confirmed one loopback listener); the Controller ran in its own subprocess per intent. `dispatch.argv_for` builds an array, `shell=False`, never an import |
| C | Durability | The Listener was `SIGKILL`ed and restarted; `GET /intents/<id>` still returned the intent and its result. Acknowledgement is fsynced before the caller is answered |
| D | Idempotency | Live duplicate submission of `phase3-proof-kan183` returned the SAME `intent_id`, `duplicate: true`, `dispatch_attempts: 1`. Deterministically: a 4-thread barrier race over one intent produced exactly one Controller invocation |
| E | Controller authority preserved | The Listener holds no Jira client, no seat, no provider, no workspace, no claim, no lease and no lifecycle. Its contract has no field that can express any of them, and unknown fields are rejected |
| F | Result delivery | Both live results carry the original `correlation_id` (`phase3-proof-kan183`, `phase3-proof-kan191`) and the Controller's verbatim JSON |
| G | Authority loop | `test_decision_loop.py` — needs_input → durable `WAITING_INPUT` → correlated decision → canonical `agent.controller decide` naming the same work item and the same invocation → terminal result to the ORIGINAL correlation, original intent untouched |
| H | Safe failure | Result is written before the intent is settled; an interrupted dispatch is marked `dispatch-interrupted` and never retried; timeout/unavailable/unreadable each settle `FAILED`, never `COMPLETED` |
| I | Security | Loopback bind plus a client-address check; allow-listed intent types; 64 KiB body cap refused before parsing; no command, path, seat, provider or workspace field; argv arrays only. Live: `KAN-1; rm -rf /` refused `invalid-field`, `RUN_SHELL` refused `unknown-intent-type` |
| J | Real proof | Two real intents traversed Listener → Controller → durable result. Both returned `authorization_status: product-execution-not-authorized` with `claim_status: not-started`, `lease_closure_status: not-opened`, `invocation_id: null`, `jira_transition_performed: false` — the real governance boundary reached and surfaced, not bypassed |

**Zero mutation, measured.** The `agent/state/runtime` tree hashed
`704e371b53a7898f8eeb00f2b1478798463a187250d5bcf0d0c6983487cd8249` over 328 files both before
and after the live proof. Mode stayed `SYSTEM_MAINTENANCE`, open leases stayed 0, KAN-183 stayed
`done`, KAN-191 stayed `ready` owned by `backend-3`, and the Product checkout stayed at
`05e38fb` with a clean tree. No Jira call and no Supabase call was made by Phase 3 at any point.

### Against `MASTER_ROADMAP.md` §30

| §30 criterion | Result |
| --- | --- |
| a stable intake contract | MET — `agent/listener/contract.py`, one versioned envelope, two allow-listed families, derived identity |
| separation between conversational input and execution orchestration | MET — separate process, separate package, no Controller logic duplicated, D-017 |
| removal or reduction of temporary Phase-2 entry glue | **PARTIALLY MET, deliberately.** Reduced: `resume` and the new `decide` were previously reachable only from inside a Python session already holding the controller's imports, so a decision arriving over any boundary had nowhere to land; the CLI is now the complete process-callable surface. Not removed: `agent/controller` remains the direct entry point and still calls itself temporary. Moving controllers off it is Phase 4's exit condition, not Phase 3's |
| no regression to provider/lifecycle architecture | MET — State 1,491 passed with the one pre-existing failure unchanged; 307 controller/execution tests pass; `validate.py --check` reports persistent state valid |

### What closure does not claim

The Listener is not reachable from anywhere but this machine's loopback interface, and it does
not authenticate the caller — `actor` records who submitted without proving it. It does not
brief a controller, does not choose work, does not drain a queue, and does not make Thebes
autonomous. A CEO instruction still names exactly one work item, and the Controller's
authorization gate refuses it exactly as it refuses a human.

### Deferred — explicitly non-blocking

**DEFERRED_HARDENING**
- *Caller authentication.* Required before any non-loopback exposure. Loopback-only is the
  Phase-3 mitigation, not a permanent answer.
- *Live authority-loop proof.* The decision loop is proven deterministically end to end
  (`test_decision_loop.py`) and its controller half is proven against the canonical approval
  writer. Exercising it live would require authorizing real Product work that stops at a native
  permission boundary; risky Product work was not manufactured to demonstrate transport. To be
  collected opportunistically from the next naturally authorized run that stops at a boundary.
- *Interrupted-dispatch reconciliation is manual.* A `dispatch-interrupted` intent is surfaced
  and left alone by design. Reconciling it against canonical receipts could be automated later;
  doing it automatically now would risk the duplicate execution the rule exists to prevent.

**DOCUMENTARY OBSERVATION**
- `agent/MASTER_ROADMAP.md` is referenced by this roadmap as the canonical Phase-2 and Phase-3
  criteria source, but is **untracked in this checkout**. It was untracked before Phase 3 began
  and was deliberately left untouched. A canonical source that git does not carry cannot be
  reconstructed by a fresh clone; deciding whether to track it is the CEO's, not this phase's.

### Next

Superseded 2026-09-15: Phase 4 was authorized by the CEO's Phase-4 brief and is now CLOSED.
See "Phase 4 closure" below.

## Phase 4 closure

**DECISION — Phase 4 (Codex → Listener Integration) is CLOSED and ACCEPTED, recorded 2026-09-15.**

Phase 4's objective was to move the normal CEO/Codex operational path from `Codex → Controller`
to `Codex → Listener → Controller`, making the Listener the sole normal external intake boundary
while the Controller stays the authoritative orchestration engine.

It is accepted on the evidence below. **Closure is narrow and two things it is not are worth
stating plainly.** It is not authentication — the gate that enforces the front door is an
environment marker, a misuse guard, and loopback-only remains the real mitigation (D-021). And
**no authority moved**: the Listener owns exactly what it owned at Phase 3 closure, and the
Controller decides exactly what it decided before. What changed is which door is normal.

### Architecture

```text
CEO
   ↓ natural language
Codex / controller conversation      (interprets intent; derives no execution detail)
   ↓ canonical intent envelope, unchanged from Phase 3
Thebes Listener                      (python3 -m agent.listener submit <KEY> --wait)
   ↓ durable, idempotent, correlated; subprocess with argv array
Thebes Controller                    (execute | resume | decide — Listener-launched only)
   ↓ unchanged authority
authorization → claim → lease → workspace → provider → validation → integration → lifecycle
   ↓
durable Listener result / authority request
   ↓
Codex → CEO
```

### Entry-point classification

Phase 4 retired an execution front door, not an architecture. What moved, and what deliberately
did not:

| Interface | Category | Phase 4 |
| --- | --- | --- |
| `agent.controller execute` | external operational front door | **retired** — Listener-launched only; direct invocation refuses `direct-controller-entry-retired`, exit 2 |
| `agent.controller resume` | external operational front door | **retired** — same gate |
| `agent.controller decide` | external operational front door | **retired** — same gate |
| `agent.controller integrate` | recovery | **kept, ungated** — orchestrates nothing new; recovery genuinely needs it |
| `plan-sprint`, `plan-backlog`, `authority-manifest` | read-only inspection | **kept, ungated** — orchestrate nothing |
| `--brief-file`, `--maintenance-reason` | debug / maintenance | **kept** — the override must state its reason, which is recorded |
| `agent.controller.*` Python API, `execute_product_wake` | internal | unchanged |

### Evidence

Verified against the repository, running processes, Persistent State and the suites at closure.

| # | Exit criterion | Evidence |
| --- | --- | --- |
| 1 | Normal intake goes through the Listener | Live: `python3 -m agent.listener submit KAN-183 --wait --source codex-controller` returned the Controller's answer without any direct Controller invocation |
| 2 | Controller authoritative behind the Listener | Both live intents returned `authorization_status: product-execution-not-authorized`, `claim_status: not-started`, `lease_closure_status: not-opened`, `invocation_id: null` — the Controller's own gate, unchanged |
| 3 | Direct operational path no longer needed | Live: `python3 -m agent.controller execute KAN-183` refused `direct-controller-entry-retired`, exit 2, before reaching authorization. Enforced by `agent/controller/entry.py`, not documented |
| 4 | Decision responses traverse the Listener | Live: a `DECISION_RESPONSE` through the front door was correlation-checked and refused `decision-target-not-waiting`. Deterministic: a dispatched decision reaches a **real** `agent.controller decide` process as a Listener caller; the positive resume is `test_decision_loop.py` |
| 5 | Listener remains authority-neutral | No code moved into `agent/listener`. Its contract is unchanged from Phase 3 — live rejections: `seat_id` → `unknown-field`, `provider` → `unknown-field` |
| 6 | Idempotency intact | Live duplicate returned the same `intent_id`, `duplicate: true`, `dispatch_attempts: 1` |
| 7 | Restart recovery intact | Live `SIGKILL` and restart; result still queryable, still `dispatch_attempts: 1`, never re-dispatched |
| 8 | Injection impossible | Live: `RUN_SHELL` → `unknown-intent-type`; `KAN-1; rm -rf /` → `invalid-field`; `seat_id` and `provider` → `unknown-field` |
| 9 | Separate processes | Listener pid 29053 on `127.0.0.1:8788` (`lsof`-confirmed); Controller a subprocess per intent, `shell=False`, argv array |
| 10 | Executor self-orchestration prevented | `be15b75` — seven listener instructions that previously passed the executor firewall are now refused; five pieces of ordinary Product English asserted to still pass |
| 11 | Documentation truthful | `agent/controller/README.md`, `agent/PROGRAM_MEMORY.md`, `agent/listener/README.md`, `CLAUDE.md` and the `route-to-seat` skill all now name the Listener as the front door |
| 12 | Fresh clone contains the roadmap | `1954f55` tracks `agent/MASTER_ROADMAP.md`; `981c941` supersedes its stale current-position sections |

**Zero mutation, measured.** The `agent/state/runtime` tree hashed
`704e371b53a7898f8eeb00f2b1478798463a187250d5bcf0d0c6983487cd8249` over 328 files both before
and after the live proof — the same hash Phase 3 closed on. Mode stayed `SYSTEM_MAINTENANCE`,
open leases stayed 0, KAN-183 stayed `done`, KAN-191 stayed `ready` owned by `backend-3`, and
the Product checkout stayed at `05e38fb` with a clean tree. No Jira call and no Supabase call was
made by Phase 4 at any point.

### Against `MASTER_ROADMAP.md` §34

| §34 criterion | Result |
| --- | --- |
| Codex/controller can submit work through the Listener | MET — live, `--source codex-controller`, with `--wait` so a controller reads an answer rather than busy-polling |
| no manual execution brief copying is normally necessary | MET — unchanged from Phase 2: the brief is derived from canonical state and the intent carries only a work-item key. `--brief-file` remains exceptional and now also sits behind the maintenance override |
| Listener input maps deterministically into Thebes | MET — one intent, one argv array, one Controller process; `test_front_door.py` asserts the mapping and the provenance |
| authorization remains explicit | MET — every live intent hit the Controller's own authorization gate and was refused; the Listener grants nothing |
| conversation state does not replace canonical state | MET — the envelope carries no seat, provider, workspace, route or lifecycle, and unknown fields are rejected |
| provider-neutral execution still works unchanged | MET — nothing in `agent/execution` changed except the firewall's surface list; 21 controller/execution suites pass |

### What closure does not claim

Natural language is not authorization and nothing here makes it so — Codex interprets intent,
and Thebes re-derives every fact. The Listener is still loopback-only and still does not
authenticate its caller. The front-door gate stops a mistake, not an attacker. And Thebes still
does not select its own work: a CEO instruction names exactly one work item and the
authorization gate refuses it exactly as it always did.

### Deferred — explicitly non-blocking

**DEFERRED_HARDENING**
- *Caller authentication.* Unchanged by Phase 4 and still required before any non-loopback
  exposure. The front-door marker is explicitly not a substitute (D-021).
- *Live authority-loop proof.* Still deterministic-only, for the Phase-3 reason: proving it live
  needs authorized Product work that stops at a native permission boundary, and risky work is not
  manufactured to demonstrate transport. Phase 4 did add a real-process proof of the decision
  path's front-door admission and canonical refusal.
- *Interrupted-dispatch reconciliation stays manual*, by design.

**OBSERVATION — pre-existing, not repaired**
- `authority-manifest` on a nonexistent work item raises an unhandled `ValueError` and prints a
  traceback instead of a structured blocker; only `ControllerInputError` is caught. Unrelated to
  the front door, predates Phase 4, and was left alone rather than opportunistically fixed. The
  Phase-4 suite uses a real key and says why.

### Next

Superseded 2026-09-15: Phase 5 was authorized by the CEO's Phase-5 brief and is now CLOSED.
See "Phase 5 closure" below.

## Phase 5 closure

**DECISION — Phase 5 (Listener evolves into Thebes Core) is CLOSED and ACCEPTED, recorded
2026-09-15.**

Phase 5's objective, from `MASTER_ROADMAP.md` §36, was a clean separation between Conversation
Intelligence, Canonical Company Intelligence and Execution Intelligence, with §37 drawing the
middle one as a single box called Thebes Core.

It is accepted on the evidence below. **Three things closure explicitly does not claim**, each
because the opposite would be easy to assert and false: the orchestration engine was not
rewritten and no second one exists; learning gained no influence over any decision; and Thebes
did not become autonomous — every run is still one CEO-authorized work item, refused by the same
gate as before.

### Architecture

```text
CEO
 ↓  natural language
Conversation Intelligence     the controller conversation (Codex). Outside this
 ↓  canonical intent envelope repository. Interprets intent; derives no
                              execution detail; holds no state.
THEBES CORE                   agent/core — composition, hosted by the
 ├── Intake                   long-running intake process
 ├── Persistent State
 ├── Company Rules            each responsibility maps to the module that
 ├── Product State            already owns it; `core.SUBSYSTEMS` is that map
 ├── Work Lifecycle           in code, and a test imports every entry
 ├── Capability Model
 ├── Authorization
 ├── Dependencies
 ├── Context Assembly
 ├── Validation
 ├── Learning                 (inert; not consulted when answering)
 ├── Provider Selection
 └── Execution
 ↓  per-intent subprocess, argv array
Execution Intelligence        provider adapter → executor. Product work only.
```

### The defect Phase 5 closed

After Phase 4 an intent had **two durable state machines**. The Listener's transport record said
`RECEIVED` / `DISPATCHING` / `COMPLETED`; Persistent State separately knew whether a claim
existed, whether a lease was open, whether a receipt landed and where the work item's lifecycle
stood. Nothing reconciled them, they could disagree indefinitely, and no caller could tell.
"One canonical intent lifecycle" is exactly that reconciliation — see D-022, and L-017 for why
two records with no reconciler is not redundancy.

### Evidence

Verified against the repository, running processes, Persistent State and the suites at closure.

| # | §40 criterion | Evidence |
| --- | --- | --- |
| 1 | one durable Thebes Core | `agent/core` — `SUBSYSTEMS` maps all 13 §37 responsibilities to modules, and `test_core_contract` imports every one. Live: the real runtime answered on `127.0.0.1:8789`, survived SIGKILL twice, and recovered |
| 2 | conversation-independent company state | Asserted against executable source with docstrings stripped: Core reads no transcript, conversation, chat history, session or message source. `resolve` takes no session, caller identity or conversation handle |
| 3 | minimum-context executor briefing | §38's six items asserted field-by-field against `PRODUCT_BRIEF_FIELDS`, plus fifteen things with no rendering path at all. Structural, not habitual: an absent field cannot be rendered |
| 4 | stable provider-neutral execution | `agent/execution` unchanged except the firewall's surface list; 21 controller/execution suites pass |
| 5 | stable intake | Phase 3/4 suites pass unchanged; live duplicate returned the same `intent_id`, `duplicate: true`, one dispatch |
| 6 | stable lifecycle | One external vocabulary, derived; every transport state maps into it; canonical state wins and disagreement is named |
| 7 | durable learning inputs | `telemetry → retrospective → candidate → explicit ceo/cto decision` persists in Persistent State; asserted to have no write path into work or governance |
| 8 | no dependence on chat memory | Follows from 2 and 7; the answer is reproducible from disk alone |

**Live proof, on the real runtime.** A Codex-style intent (`--source codex-controller`) went
`submit KAN-183 --wait` → Core → Controller subprocess (`entry_path: listener`) → durable answer:
`lifecycle_state: COMPLETED`, `reconciliation: agrees`, and — new in Phase 5 — the canonical
state behind it: KAN-183 `done`, unowned, zero open leases, four historical execution receipts.
KAN-191 likewise, independently. Duplicate collapsed. Direct `agent.controller execute` still
refused `direct-controller-entry-retired`. Five injection attempts refused
(`unknown-intent-type`, `invalid-field`, and `unknown-field` for `seat_id`, `lifecycle` and
`provider`). A `DECISION_RESPONSE` was correlation-checked and refused
`decision-target-not-waiting`. Six executor-brief probes — including `from agent.core import
lifecycle` — were all blocked.

**The ambiguous dispatch, proven live.** An intent left `DISPATCHING` and unsettled was recovered
by the real Core on restart: `INDETERMINATE`, **not terminal**, `unobserved-execution`,
`dispatch_attempts: 1`, pending queue 0 — never re-dispatched — and carrying KAN-183's lifecycle,
ownership, open leases and receipts so the person settling it is handed the facts instead of
being sent to look. *Method stated precisely:* five attempts to catch a natural mid-dispatch
crash by racing SIGKILL all landed after the answer, because the Controller refuses at the
authorization gate in under 40ms. The durable condition was therefore induced directly in the
real transport store; the recovery, the derivation and the answer are the real runtime's.

**Zero mutation, measured.** `agent/state/runtime` hashed
`704e371b53a7898f8eeb00f2b1478798463a187250d5bcf0d0c6983487cd8249` over 328 files before and
after — the same hash Phases 3 and 4 closed on. Mode stayed `SYSTEM_MAINTENANCE`, open leases 0,
KAN-183 `done`, KAN-191 `ready` owned by `backend-3`, Product checkout `05e38fb` clean. No Jira
call and no Supabase call was made by Phase 5 at any point.

### The per-intent subprocess: kept, deliberately

Phase 3 introduced `Listener → subprocess → agent.controller` to prove process separation, and
Phase 5 had to decide whether that is final architecture or temporary glue. **It is kept**, and
the reasoning matters more than the verdict:

- **Crash containment.** Core is long-running and hosts intake. An orchestration that dies must
  not take the front door down with it. Collapsing the boundary would make "one durable Core"
  less durable, not more.
- **It implements the Phase-4 front door.** Caller classification is done by the OS handing the
  child an environment marker. Removing the boundary would mean re-inventing that inside one
  process.
- **It stopped being glue.** Phase 5's reduction was the *state duplication*, not the process.
  Core now owns the invocation model and reconciles its outcome against canonical truth, which
  is what §37 asked for.

What is honestly recorded: the subprocess boundary is *why* an interrupted dispatch is
unobservable in the first place. That cost was weighed and accepted, and D-023 is the mitigation.

### What closure does not claim

Core did not absorb the Controller and did not reimplement any subsystem — `test_core_contract`
asserts Core's own source contains no claim, lease, provider-selection, Jira-transition, receipt
or state-write call. Learning remains inert and is deliberately not consulted when answering
(§39). Transport is still loopback-only and still unauthenticated. And Thebes still does not
select its own work.

### Deferred — explicitly non-blocking

**DEFERRED_HARDENING**
- *Caller authentication.* Unchanged across Phases 3–5; still required before any non-loopback
  exposure.
- *Live authority-loop proof.* Still deterministic-only, for the reason given since Phase 3:
  proving it live needs authorized Product work that stops at a native permission boundary, and
  such work is not manufactured to demonstrate transport.
- *Automatic reconciliation of an interrupted dispatch.* Deliberately absent (D-023). Core now
  supplies the evidence; deciding remains a human act.
- *A naturally-occurring interrupted dispatch has still not been observed.* The window is under
  40ms while Product execution is unauthorized. To be collected opportunistically from a real
  authorized run, where the window is a provider wake rather than a gate refusal.

**OBSERVATION — pre-existing, not repaired**
- `authority-manifest` on a nonexistent work item still raises an unhandled `ValueError`.
  Unrelated to Phase 5 and explicitly out of scope.

### Next

Phase 6 (Knowledge scaling / RAG) remains FUTURE TARGET and DEFERRED, and has **not** started.
`agent/DECISIONS.md` D-015 stands: retrieval waits until canonical direct reads become a
measured bottleneck. Beginning it requires a separate CEO decision.

## Final operations hardening — 2026-09-15

**DECISION — the infrastructure programme is CLOSED and the baseline is FROZEN.**

Phases 1–5 are closed. This milestone removed the last two pieces of executor-runtime friction
that live Product operation exposed, stopped the old-backlog pilot, and left Thebes in a clean
`READY_FOR_PRODUCT_DEVELOPMENT` state.

### Program position

```text
PHASES_1_TO_5            CLOSED
MAINTENANCE_BASELINE     STABLE
PRODUCT_DEVELOPMENT_READY YES
PHASE_6                  DEFERRED
RAG                      NOT_JUSTIFIED
```

**From here, Thebes changes are evidence-driven by real Product work only.** Another
infrastructure milestone needs a real Product need behind it, not a tidy-looking gap.

### The pilot is stopped

The CEO changed Product direction: existing Ready/backlog tickets are no longer assumed to
represent current priorities.

| | |
| --- | --- |
| Authorization `authz-5323c2c9…` | **REVOKED** by the CEO, 0 of 3 consumed. Full history preserved — the grant, its scope, its maximum and its empty completion list all remain readable. |
| KAN-184 | Parked, **not completed**. Ownership released, Jira returned to Backlog (`To Do`, 10004) by `po` with a comment recording that this is deprioritization and that its three unguarded-write findings remain real and unresolved. |
| KAN-184 evidence | **Preserved.** The 19KB migration draft and the `exec/backend-1/KAN-184` worktree are untouched. It was never applied, and it carries no timestamp prefix, which is what says so. |
| Automatic execution | Impossible. No active grant, so every work item answers `product-execution-not-authorized`. |

`KAN-191` and `KAN-130` remain Ready in Jira and are deliberately untouched — rewriting the
historical backlog is explicitly not this milestone's job. Nothing can execute them.

### What this milestone fixed

**Standing executor tools.** The CLI runs `--permission-mode dontAsk`, so without a standing
set every single tool call — every read, edit and shell command — was denied and became a
separate Thebes approval plus a full resume invocation. KAN-184 burned four invocations on two
catalogue reads, one `ls` and one file write. That protected nothing: each denial was approved
anyway one round-trip later. `Read`, `Bash`, `Edit`, `Write` and `execute_sql` are now standing;
`NEVER_STANDING` names `apply_migration` and seven other production-mutating tools, asserted at
import and re-checked at call time. A CEO may still approve `apply_migration` for one
invocation — that path is unchanged — but it can never become a default.

**A working toolchain.** The pilot hit a machine whose full Xcode licence was unaccepted, which
makes `/usr/bin/python3` fail and with it every tool an executor runs. Executor subprocesses now
receive `DEVELOPER_DIR` pointing at the Command Line Tools. Process-scoped deliberately:
accepting a licence on the CEO's behalf is not Thebes's to do.

**An adjective gap in the executor firewall.** `select a different provider` walked straight
through — the rule allowed a determiner but no adjective, so the natural phrasing was the one
that passed. Found by probing the smoke proof, not by reading the regex.

### Final flow smoke proof

Non-mutating, on the real runtime.

| Claim | Evidence |
| --- | --- |
| Listener/Core is the external path | `submit KAN-184 --wait` → `entry_path: listener`, canonical answer returned |
| Direct external Controller is retired | `agent.controller execute` → `direct-controller-entry-retired`, exit 2 |
| Governance still refuses | `product-execution-not-authorized`; `claim_status: not-started`, lease `not-opened` |
| **Executor uses its tools without round-trips** | A real Claude CLI invocation read a file, ran `wc -l` and wrote a result in ONE invocation — `permission_denials: []`. Before this fix that prompt cost three approval cycles. |
| Production mutation denied | `apply_migration` absent from the standing set; 8 tools guarded |
| Executor cannot reach the control plane | 10/10 probes blocked, including the newly-closed provider phrasing |
| Restart/reconciliation healthy | SIGKILL + restart → `COMPLETED`, `dispatch_attempts: 1`, `reconciliation: agrees` |
| Claims/leases | 0 open, none leaked |

Persistent State hashed `d7ab6a7a…5315` before and after the proof. Product checkout `05e38fb`,
clean. No Jira mutation beyond KAN-184's authorized Backlog return; no Supabase call.

### Next

**Create the new Product roadmap and feature backlog.** The CEO intends new work focused on
Product experience, features, user value and growth. Historical engineering tickets stay in
Backlog until a real Product need pulls one back — and a well-specified old ticket is not, by
itself, such a need.

## Next bounded decision

The infrastructure programme is closed and the baseline is frozen. The next act is Product, not
Thebes: define the new Product direction and the work that serves it. This roadmap authorizes no
Product execution — a bounded or standing grant remains a separate CEO decision, and the
machinery to honour either is built, proven and idle.

## Phase and mode exit rules

- A completed slice does not close a phase.
- A phase closes only through an explicit recorded decision against its exit criteria.
- A mode transition changes only the mode record and must preserve Product lifecycle,
  ownership, review, dependencies and interventions.
- If documentary sources conflict with runtime state, remain/return to maintenance and
  reconcile; do not normalize toward Product execution.
- Future phases may be refined by evidence, but may not be silently promoted to current
  fact or implementation.

## Bounded authorization — KAN-206 continuation after PEER FAIL

**CURRENT FACT — PRODUCT_EXECUTION_AUTHORIZED: NO — consumed by KAN-206's completion, 2026-09-15.**
*(This read YES for one item, KAN-206, continuation only, between 16:30 and 16:42 on 2026-09-15.
The marker is a whole-file substring test, so retiring this authorization means editing this exact
line — appending a later NO elsewhere would leave the grant live.)*

**Why this record exists.** KAN-206 was selected and executed under the CEO's bounded standing
grant `authz-8d4844a9-2c91-4dc4-b085-92b4bd7d88d8`. `frontend-2` peer-reviewed it and returned
FAIL on exactly one criterion: D-001's mandated runtime mitigation had not been performed.
Ownership transferred to `frontend-2` under `peer_fail_transfer`, opening review cycle 2.

The CEO then performed that mitigation personally on 2026-09-15 — `flutter run -d chrome` against
commit `b0118a4` on `exec/frontend-1/KAN-206`, not against `Canary` — reporting a clean cold start
with no observed problem. Recorded as Jira comment `11012` on KAN-206.

**The blocker this record clears.** `ProductAuthorization.for_work_item` proves a bounded grant's
authority through `canonical_admissibility`, which asks `queue.unclaimable_reasons` — the CLAIM
question. That predicate emits `already-owned` for any item with an owner. `controller.execute`
itself supports continuations (`if already_owned: claim_status = "preserved"`), so the body is
willing and only the gate in front of it refuses. Consequence: **a bounded grant can start work it
is structurally unable to finish.** Any PEER FAIL under a bounded grant strands its item.
This is a Thebes defect, recorded below as maintenance, and is NOT fixed by this authorization.

**Scope.** This authorizes continuation of KAN-206 ONLY, preserving `frontend-2`'s existing
ownership — no new claim, no new due date, no reselection. It does not authorize KAN-207, KAN-208
or any other ticket, does not alter the bounded grant's quota accounting, does not widen any
authorization gate, and does not authorize merging to `main` (`P-030` stands).

Authorization reference: CEO decision, 2026-09-15, KAN-206 continuation after PEER FAIL
Selected ticket: KAN-206

Acceptance result/evidence (protocol step 5): **DONE, 2026-09-15.** `frontend-2` completed review
cycle 2 and recorded SELF **PASS** through `store.record_review_result`. Product commit `b389214`
integrated onto `Canary` as `d9d161f` (previous head `15a685d`): 7 files, 973 deletions, confined
to the declared surfaces. The barrel retains 14 export lines. Jira reached **Done (10007)**,
confirmed by an authoritative re-read; Persistent State reconciled to canonical `done`; ownership
released; zero leases remained open. `main` untouched. The bounded standing grant recorded KAN-206
as its 8th consumed item, leaving 2 of 10 against KAN-207 and KAN-208.

**This authorization is consumed and does not carry forward.** It did not fix the continuation gap
recorded below, which remains open.

## Maintenance item — bounded-authorization continuation gap

**Recorded 2026-09-15, not yet fixed, by explicit CEO decision to authorize first and repair
separately.**

`agent/controller/__init__.py::ProductAuthorization.for_work_item` proves admissibility with
`canonical_admissibility`, which asks the claim question (`queue.unclaimable_reasons`,
`already-owned` at `agent/state/queue.py:266`) about an item the same grant already selected and
that is legitimately mid-lifecycle. Roadmap authorization is unaffected, because it returns
`authorized` before that gate is consulted — so the gap exists only on the bounded-grant path.

The fix is a SYSTEM_MAINTENANCE act and requires its own CEO decision: widening an authorization
gate is precisely the self-granting shape the CEO's standing instruction forbids
("Do NOT allow Thebes to grant authority to itself"), so it is not folded into a Product run.

## Professional QA layer integration — CLOSED 2026-09-15

**CEO brief:** evolve the existing validation capability into a professional, token-efficient
QA system; inspect first; smallest architecture adjustment; no second orchestrator; no new
agent; Phases 1–5 stay closed. Ran in `SYSTEM_MAINTENANCE` (no leases open) and returned to
`PRODUCT_EXECUTION` on closure. Decision record: `DECISIONS.md` D-027. Mechanics:
`PROGRAM_MEMORY.md` "Validation and review model".

**What was inspected before anything changed** (repository as source of truth): the SELF/QA/
PEER route derivation (`policy.validation_route`), the validation runner
(`controller/validation.py::run_validation`), the evidence model (`ExecutionResult` →
`TestClaim`/`EvidenceClaim`), the three FAIL semantics and the review cycle (no ceiling
existed), the Listener/Core path, the provider abstraction, the `qa` role (480 lines, manual
driving as doctrine), the Product test structures (15 Dart test files; `flutter test` broken
locally by a native-asset link fault; Playwright with a placeholder anon key; 12 Maestro flows
targeting an app id that exists nowhere; per-ticket SQL probe packs; `scripts/qa.sh`), CI
(`ci.yml`: analyze + test on Canary pushes and PRs), and local tools: node 24, Java 17/24,
Maestro 2.10.0, Playwright 1.63 (npx), Postman CLI 1.56.3, k6 2.2.0; no TestSprite or
BrowserStack credentials in the environment; a TestSprite MCP entry configured for this
project but not loaded in the session.

**What changed in Thebes** (`bddb03f`, `e0a235f`, plus this docs commit):
- `agent/qa/` — routing (one deterministic function), layers (registry with trigger policy),
  runner (commands, artifacts on disk, bounded tail, stops at first infrastructure failure,
  never invokes an external layer), results (the four-way failure contract and the fold into
  the canonical evidence model), retest (read-only explanation of the ceiling), gate (the one
  seam). 56 tests.
- `policy.MAX_REVIEW_CYCLES = 3` enforced in `store.open_review_context`; `test_self_fail` #24
  amended to keep its "never reset" invariant within the ceiling and assert the refusal;
  `test_retest_bound.py` (21 checks).
- `run_validation` runs the gate after the context opens and before the reviewer is
  dispatched; `VALIDATION_INFRASTRUCTURE_FAILED` refuses without a verdict; reviewer effort
  follows the evidence. 7 controller tests. `core.SUBSYSTEMS["validation"]` names
  `agent.qa.routing` and `agent.qa.gate`.
- `agent/roles/qa.md` and its binding: the seat is test orchestration. Regenerated agent.
- `run-tests.sh` runs all six packages.

**What changed in the Product repository** (`a86ddf8`, `1859ef8`; nothing under `lib/`):
`tests/e2e` signs in once per run and shares the session (three measured Flutter-web facts
encoded); `tests/maestro` with a runner and one smoke flow — **proven: 1/1 Flow Passed in 14s
on the `Dabbler_test` emulator**; the 12 legacy flows moved under `tests/maestro/legacy/`
as non-runnable notes; `tests/api` Postman collection (success on an allowlisted view,
authentication, health, RLS authorization) — **proven: 4/4 requests, 7/7 assertions** via
newman, Postman CLI when a key is present; `tests/perf` k6 smoke with thresholds, intentional
only, not run; `tests/README.md` as the test contract; `package.json` scripts.

**Findings recorded on the way, none of them Product changes:** the REST OpenAPI root is
`service_role`-only on this project (correct posture; the API success case reads an allowlisted
view instead); `flutter test` is unrunnable on this machine for a toolchain reason and is the
first entry in the infrastructure signature table; iOS simulators sit behind the unaccepted
Xcode licence, so Maestro's local target is Android.

**Deferred, truthfully:** TestSprite (configured, not reachable in-session; routing names it,
nothing invokes it); BrowserStack (no credentials; release-stage integration point documented
in `tests/maestro/README.md`); CI wiring (designed for — PR: fast targeted; Canary: broader
deterministic; release: mobile/web/API + devices; performance milestone: k6 — and not
rolled out; local execution is the proof); iOS device runs; the bounded-authorization
continuation gap above, which this milestone did not touch.

**Acceptance against the brief:** governance authoritative and unchanged; routing canonical
and deterministic; not every task invokes QA (docs-only selects nothing) and no QA task
invokes every tool; Maestro runs a representative flow; Playwright usable; API deterministic
path reusable; TestSprite reachable-in-principle but never default; k6 intentional;
BrowserStack release-stage; failures structured; Product defects route to `frontend`/
`backend`; test defects and infrastructure failures cannot masquerade as Product defects;
retest bounded; deterministic regression preferred over repeated exploration; expensive
navigation no longer the default; secrets outside Git; Core/Listener/controller boundaries
intact; QA integrations grant no execution authority; documentation describes local and
future-CI operation.

## 2026-09-30 — KAN-368 Ready continuation

The CEO directed Codex to inspect the live Jira Ready queue, order Claude to work its
pending ticket, and follow through until completion. Jira returned one Ready ticket:
KAN-368. Its existing `frontend-1` owner and Claude session continue; this selection
does not authorize another ticket or a replacement worker. The PO's 2026-09-27 Jira
correction adds only the minimal `lib/widgets/app_button.dart` onTap null-check change
to the existing test-file scope.

PRODUCT_EXECUTION_AUTHORIZED: NO
Selected ticket: KAN-368
Authorization reference: CEO 2026-09-30 Ready-queue instruction; sole Ready ticket KAN-368, same frontend-1 continuation.

Closure, 2026-09-30: KAN-368 passed SELF review, both owned commits landed on
Canary as `d97fad5` and `33f1f7d`, and a fresh Jira read returned Done (10007).
The exact-ticket execution authorization above is consumed. The five pre-existing
deleted assets in the Canary checkout were restored to their original staged and
unstaged state after integration.

## 2026-10-01 — Three-group operating milestone (Listener / Decision gate / Execution)

**Status: AUTHORIZED, NOT STARTED.** Authorized by the CEO on 2026-10-01 under D-030;
it supersedes the D-026 freeze for this milestone only. Shape and gate rulings: D-031.

### What the CEO asked for, in the repo's names

Three **groups**, explicitly not layers: the Listener may reach execution directly, and
the decision group enters only when a decision is needed.

| CEO's word | What it is in Thebes today | Gap |
| --- | --- | --- |
| **Listener** — any chat; listen, form a professional prompt, send | The **Primary** (Conversation Intelligence): `primary_binding`, `bootstrap_prompt`, `conversation-dispatch`, `PRIMARY_COMMAND` + gateway | Implemented for Codex threads on the shared runtime; Claude is STANDBY only; the bootstrap is a prompt, not a tracked skill |
| **Decision group** — orchestrator + cto/cpo/cxo…, runs Jev | `authority.json` decision classes; `decision_required` → accountable role → **same worker resumed** (`primary_notify.NEXT_STEP`) | Routing lives as prose in the Primary's head; no deterministic classifier; no confidence gate; no CEO escalation threshold |
| **Execution** — execute, ask for a decision, report done | Bound `role_session` Claude seats; outcomes `completed/blocked/decision_required/clarification_required/failed`; `session_outcome` | Every outcome returns to the **origin conversation**; a `decision_required` has no direct path to the decision group |

**Definition of success (CEO):** A sends to B and goes idle; B works alone; B's result
**wakes A** as a new turn; delivery is durable and exactly-once; the model behind A is
swappable without touching B. The Codex ↔ Claude path already meets this
(`cdispatch-b7ddac1e…`, 2026-09-30). The ChatGPT web/desktop app cannot be woken and is
out of scope as a Listener runtime; "ChatGPT" in this milestone means the Codex app on the
ChatGPT account, which the shared runtime already owns.

### Proofs — the milestone is scoped by these and nothing else

| # | Proof | Pass when |
| --- | --- | --- |
| P1 | **Codex Listener round-trip, live, current code.** Start Listener + shared runtime; new Thebes conversation; CEO text → bootstrap prompt → `conversation-dispatch` to a bound Claude seat → Claude works → `submit --outcome completed` → result arrives as a new turn on the same Codex thread with Codex idle in between | Observed live and recorded; every failure found is named here as a defect, not fixed in place |
| P2 | **Decision outcome reaches the decision group.** The same loop, but the worker returns `decision_required`. The outcome is routed to the accountable role per `authority.json` (through the Jev adapter with a **fake Jev**), the role's answer resumes the **same** worker, and the Listener hears only the final `completed` | No new ticket, no new worker, no Listener involvement between the question and the answer |
| P3 | **Jev live.** P2 repeated with `TYPESAFE_API_KEY` set; the adapter's Choice/Score/Noul questions return typed answers; a below-threshold confidence escalates to the CEO; an unavailable Jev degrades to today's CEO path | Recorded typed answers with confidence; the escalation and the degradation both exercised |
| P4 | **Listener model swap.** The Listener role runs on a Claude session (STANDBY → ACTIVE through `set_primary_active`) with no change to execution or the decision group | Same round-trip as P1 with a Claude Primary |
| P5 | **Fresh-machine bootstrap.** A documented sequence brings up Listener, shared runtime, bound seats and the gateway from a clean clone | Followed verbatim on this machine after a runtime reset |

### Steps

0. Transition to `SYSTEM_MAINTENANCE` before any code change (0 leases open at
   authorization; mode is `PRODUCT_EXECUTION`). Return on closure.
1. Run P1 on the code as it is. Record every defect found (expected: the Claude
   background daemon failure seen on `cdispatch-cab93b9e…`, Listener not auto-started,
   bootstrap prompt not versioned as a skill).
2. Add the **decision routing seam**: `session_outcome` / `conversation_dispatch.submit`
   route `decision_required`, `blocked` and `clarification_required` to a decision
   dispatcher instead of the origin thread; `completed`/`failed` keep going to the origin.
   The dispatcher wakes the accountable seat with a bounded brief and resumes the same
   worker with the answer. Record type: `decision_request` (durable, one per outcome).
3. Add the **Jev adapter** (`agent/execution/decision_gate.py`): one interface, a fake
   implementation for tests, the real `POST /v1/systemone` behind it; tracked question
   schemas; confidence threshold in tracked config; `decision-gate-unavailable` fallback.
   Firewall tokens extended so no executor brief can name it (L-015).
4. Run P2 (fake), then P3 (live) once the CEO supplies a key.
5. Promote the Listener bootstrap from prompt text to a tracked skill
   (`agent/skills/listener/`), provider-neutral, rendered into the Codex bootstrap turn and
   the Claude Primary resume envelope alike. Run P4.
6. Write `agent/BOOTSTRAP.md` (P5). Close with a recorded decision against this table.

### P1 — PASSED live, 2026-10-01 10:11–10:16 UTC

Mode `SYSTEM_MAINTENANCE` (rev 79, 0 leases). Listener on `127.0.0.1:8787`; shared
runtime `thebes` pid 36646 on `~/.thebes-codex` with the CEO's ChatGPT login (Codex CLI
0.159.3, installed that morning). CEO text → Codex conversation `01a0f6f4-93de-…`
(bootstrap `THEBES_BOOTSTRAP_READY`, first turn "Dispatch accepted by frontend-1 … Going
idle") → `cdispatch-9aa36a63…` DELIVERED to `frontend-1` session `c515fbd4-…` (stopped,
resumed same SID) → worker `submit --outcome completed` → `cevt-cresult-9aa36a63…` drained
as turn `01a0f6f5-09ce-…` on the same Codex thread while Codex was idle. Codex's reply
quoted the worker's answer (728 Dart files, exact command). Delivery exactly once; no
polling; no Jira, no Product file touched.

**Defects found, not fixed (step 1 says record):**
1. **Worker seats cannot be created by Thebes from inside a Claude session.** `claude --bg`
   was refused by the Claude Code permission classifier ("Create Unsafe Agents"). The CEO
   started the session by hand. Bootstrap (P5) must list seat creation as a human step or
   name the permission rule that allows it.
2. **Bindings from another machine stay `active`.** `frontend-1/2` and `po` were bound to
   sessions under `/Users/moatazmustapha/…`; none existed here, yet the Codex bootstrap
   offered all three as dispatch targets. A binding whose session is absent from
   `claude agents --all` should render as unreachable, not as a choice.
3. **Nothing starts the Listener or the runtime.** Both were down at the start of the
   session and started by hand. P5 territory.
4. The result Codex received is the worker's full text; the Listener's own "done" message
   to the CEO is Codex's paraphrase. Acceptable for P1; P2 decides whether the Listener
   also gets the typed outcome.

### P1b — PASSED live with both Desktop apps open, 2026-10-01 12:38 UTC

The CEO's own success definition, met as stated: Codex Desktop open, Claude Desktop open.
A Codex Desktop conversation opened over SSH to this machine (`thebes-local`) lives on the
user's own `codex app-server daemon`; Thebes attaches to that daemon as one more client
(`codex_runtime attach-conversation`, `3500c4b`), so there is one writer and no
`CODEX_PRIMARY_THREAD_BUSY`. Thread `01a0f777-d0e4-…` received the bootstrap live, the
CEO typed in Desktop, Codex dispatched and went idle, `frontend-1` (visible in Claude
Desktop after `/rc`) replied, and "hi back" appeared in the same open Codex conversation.

**Remaining gap — Remote Control does not survive delivery.** Delivery is stop → `--bg
--resume`, which starts a new process without Remote Control, so the seat drops out of
Claude Desktop. Installed Claude Code 2.1.285 carries a global config key
`remoteControlAtStartup` (string present in the binary; not found in published docs). The
CEO sets it through `/config`; Thebes does not edit `~/.claude.json`. Resuming with an
extra `--remote-control` flag is rejected: extra flags on `--resume` were observed to start
a copy (`WORKFLOWS.md` §4).

### Step 1b — Teams (execution islands) and the seat pool, 2026-10-01

CEO redirection after P1b, recorded as D-032: the execution group is **five generic
islands** (teams Karnak, Habu, Luxor, Ramesseum, Deir el-Bahari), each one persistent
Claude session that runs seats as subagents and returns one report; seats are a shared,
time-exclusive pool (`seat_reservation`); one Codex conversation controls all islands,
one request per free team. Built: `agent/state/registry/teams.json`, `agent/state/teams.py`,
`store.reserve_seat` / `release_seat_reservations`, `agent/execution/team_pool.py`, the team
block in the dispatch envelope, teams in the Codex bootstrap, a busy refusal that names
free teams, firewall tokens (L-015), `test_team_pool.py`. Validator: a team may bind a
session and receive conversation deliveries, never Product session dispatches.

**P1c — PASSED live, 2026-10-01 16:16–16:22 UTC.** Islands `karnak` (`1ee27200…`) and
`luxor` (`698a2e83…`) bound; Codex Desktop conversation `01a0f777…` re-bootstrapped to
list teams. CEO requests: Karnak reserved `frontend-1` + `po` (16:16:35) then
`frontend-1` (16:18:30), ran them as subagents, released on completion. Forced parallel
proof from the controller: A to Karnak (holds `frontend-1` from 16:20:13, 60 s sleep),
B to Luxor 25 s later — Luxor was refused `frontend-1` (`seat-held`, Karnak named) and
took `frontend-2` (16:20:37); Luxor finished first; both reports landed as separate turns
on the same Codex conversation; all reservations released `dispatch-completed`. Sandbox
finding: Codex Desktop blocks `127.0.0.1:8787` unless it asks for approval; the bootstrap
now instructs it to ask. The CEO set Remote Control at startup through `/config`.

### Step 2 — the decision group, built 2026-10-01

`agent/execution/decision_gate.py` + `agent/state/registry/decision_gate.json` +
`decision_request` records. A `decision_required` / `blocked` / `clarification_required`
outcome from an island or seat no longer returns to Codex: the gate (FakeGate keyword table
for P2; JevGate typed Choice for P3) names the decision class and the accountable role from
`authority.json`, the question is delivered to that role's bound session as one
`THEBES_DECISION_REQUEST` turn, the owner answers once (identity + capability), and the
**same** asker is resumed with a `THEBES_DECISION_ANSWER` dispatch on the same origin thread
— so Codex hears only the final `completed`. Escalation to the CEO through the origin
conversation, marked `ESCALATED TO THE CEO`, when: the owner is the CEO, confidence is below
the threshold, the gate is unavailable or malformed, the owner has no bound session, or
delivery fails. `task_owner` classes go straight back to the asker. 7 tests. Firewall tokens
added (L-015).

**Known limitation, recorded (CEO observation 2026-10-01):** every delivery stops and
restarts the target Claude process, so Claude Desktop shows the island as archived or with a
connection error while a turn is being delivered, even with Remote Control at startup on.
A delivery that does not restart the process needs a Claude Code transport that does not
exist today; parked, not fixed.

**P2 — PASSED live, 2026-10-01, on the third run.** Run 1: the fake gate tied "scope"
against "acceptance criteria", chose `cpo` (unbound) and escalated to Codex marked
`ESCALATED TO THE CEO` — the safety net worked; the gate now weights phrases over words and
treats a tie as low confidence. Run 2: `po` was woken but the delivery record (`dreq-` id)
was refused by the validator, so the request escalated after delivery and `po`'s answer was
refused `decision-request-not-open` — fixed (validator accepts `dreq-` deliveries) and
covered by a test. Run 3: Karnak (`cdispatch-d291df4c…`) → `decision_required` →
`dreq-a9ccc979` routed `work_acceptance` → `po` (session resumed from exited) → answered →
continuation `cdispatch-6dfa206d…` resumed Karnak → `completed` → one turn on the Codex
conversation. The `decision_required` itself never reached Codex.

**P3 (next):** `gate: jev` with `TYPESAFE_API_KEY`; the same loop with a typed Choice.

### Not in scope

A ChatGPT web Custom GPT (send-only; it cannot satisfy the success definition). Any new
seat, agent or Role. Autonomous ticket selection. RAG. Changing SELF/QA/PEER, claims,
leases or Jira authority.

PRODUCT_EXECUTION_AUTHORIZED: NO
