# Thebes program roadmap

Current as of 2026-09-12. Canonical repository: `onebrain-only/thebes`.
Canonical checkout: `~/Desktop/Thebes-Canonical`. Do not create another clone.

## Current position

**CURRENT FACT — MODE: `SYSTEM_MAINTENANCE`**
**CURRENT FACT — CURRENT PHASE: Phase 4 CLOSED 2026-09-15. No phase is current. Phase 5 has NOT started and requires a separate CEO decision.**
**CURRENT FACT — PRODUCT_ACCEPTANCE_STATUS: KAN-183 COMPLETE — the first real single-task run driven end to end by Thebes**
**CURRENT FACT — PRODUCT_EXECUTION_AUTHORIZED: NO — KAN-183's bounded authorization was consumed on completion 2026-09-14, and Phase 3 created none**

Post-Wave-8 Operational Hardening is closed. Phase 4 closed on 2026-09-15 against the criteria
in `agent/MASTER_ROADMAP.md` §34 and the CEO's Phase-4 brief; the closure record and its
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

Phase 5 (Listener evolves into Thebes Core) remains FUTURE TARGET and has **not** started.
Beginning it requires a separate CEO decision.

## Next bounded decision

Phase 4 is closed and no phase is current. The next decision is the CEO's alone: whether to
begin Phase 5 (the Listener evolving into a core that owns orchestration, routing, context
assembly, provider selection, lifecycle coordination and recovery behind stable interfaces), to
authorize another bounded Product ticket under the acceptance protocol above, or to take one of
the deferred items from any closure. This roadmap does not choose between them and authorizes
none of them.

## Phase and mode exit rules

- A completed slice does not close a phase.
- A phase closes only through an explicit recorded decision against its exit criteria.
- A mode transition changes only the mode record and must preserve Product lifecycle,
  ownership, review, dependencies and interventions.
- If documentary sources conflict with runtime state, remain/return to maintenance and
  reconcile; do not normalize toward Product execution.
- Future phases may be refined by evidence, but may not be silently promoted to current
  fact or implementation.
