# Thebes durable operational lessons

Current as of 2026-09-12. This is an evidence-led learning source, not a live work queue,
ticket history or authority. Decisions derived from lessons belong in `DECISIONS.md`;
mechanics belong in `WORKFLOWS.md` or `state/README.md`.

## L-001 — Management loops can consume the constrained resource

**Classification:** LESSON
**Observation:** The controller record reports an early swarm run consuming approximately
41% of a Max-plan allowance in about 20 minutes, with substantial management/coordination
traffic. The repository has no primary token ledger, and Wave 8 explicitly deferred token
and cost analytics for lack of a factual source (`b1da48c`).
**Lesson:** More concurrent agents can reduce useful capacity when each requires repeated
briefing, supervision and synthesis. Optimize for completed bounded work per constrained
model budget, not awake-seat count.
**Applied decision:** D-002 serial controller-driven default.

## L-002 — Dependency prose does not prevent execution

**Classification:** LESSON
**Observation:** KAN-192’s required ordering before KAN-191 existed in Jira material, but the
Persistent State edge was absent until the PO created `KAN-192 BLOCKS KAN-191`; subsequent
verification showed `queue.unclaimable_reasons` enforced it. `agent/status/po.md` records the
missing edge, creation, and claim-time verification.
**Lesson:** Important order must be encoded at the claim boundary. An acceptance criterion is
useful defense in depth, not a substitute for the dependency graph.
**Applied decision:** D-013.

## L-003 — Claim/dependency refusal is a successful outcome

**Classification:** LESSON
**Observation:** The Product record shows dependent work such as KAN-130/KAN-131 remaining
unclaimable while prerequisites were not `Done`, with structured reasons including
`dependency-blocked`. The requested KAN-130/KAN-191 example changed direction as evidence and
rulings evolved; the durable principle is the enforced edge, not a frozen ticket narrative.
**Lesson:** A queue that refuses invalid work is operating correctly. Controllers must report
the reason rather than route around it or manufacture readiness.
**Evidence:** `agent/status/po.md` KAN-129/130/131 readiness entries and dependency rulings;
`agent/state/README.md` dependency contract.

## L-004 — Reported environment must drive the first investigation

**Classification:** LESSON
**Observation:** Post-Wave-8 operation exposed environment-targeting drift, captured by the
controller as KAN-196: a report against local Flutter web/Chrome was at risk of being tested
through a different browser/deployment substrate. The hardening implementation now derives
the primary target from `reported_environment` and rejects Canary replacing localhost.
**Lesson:** Tool convenience is not evidence equivalence. Start where the condition was
observed; add comparison environments only for a stated reason.
**Evidence:** `agent/state/README.md` operational context; hardening commits `e3cf8c6`,
`834b071`, `4948607` and their isolated tests. Ticket-specific primary evidence is in Product
history and is not duplicated here.

## L-005 — Reproduction can become theater

**Classification:** LESSON
**Observation:** The old default treated a reported condition as if a reproduction ceremony
had to precede investigation. Hardening separated `observed_condition` from
`reproduction_request`.
**Lesson:** First classify the evidence and investigate the likely causal surface. Reproduce
when it discriminates hypotheses, verifies a fix, or is explicitly requested—not to satisfy
a ritual.
**Applied decision:** D-009.

## L-006 — Validation breadth must match the change

**Classification:** LESSON
**Observation:** A single list of every platform mentioned in a report over-scoped shared
fixes and under-explained platform-specific ones. The hardening model now records causal and
changed surfaces, derives required and optional targets, and keeps audited supersession when
a corrected diagnosis narrows requirements.
**Lesson:** “Test everywhere” is not a validation strategy. Shared code and platform-specific
code need different proof, and the reported runtime remains required.
**Applied decision:** D-012.

## L-007 — Maintenance and Product must be isolated

**Classification:** LESSON
**Observation:** Before the dedicated operating-mode record, maintenance intent depended too
heavily on controller instruction and could coexist ambiguously with Product queue semantics.
Commits `e3cf8c6` through `fe997bb` added mode isolation, continuation gating and serialized
execution leases.
**Lesson:** A policy banner is insufficient when claims/wakes remain technically available.
Mode must be an execution-domain fact, while authorization remains a separate governance fact.
**Applied decision:** D-008; current gate in `ROADMAP.md`.

## L-008 — Observation is not execution evidence

**Classification:** LESSON
**Observation:** Commit `3ca6f69` corrected work where assessment had been classified as
executor evidence.
**Lesson:** Preflight, surface assessment and factual observation may make work claimable, but
they do not establish ownership or prove execution. A wake creates no ownership either.
**Evidence:** commit `3ca6f69`; claim/evidence boundaries in `CLAUDE.md` and
`agent/state/README.md`.

## L-009 — Derived observability must not become authority

**Classification:** LESSON
**Observation:** Before Wave 7, Agent View inferred activity from transcripts and displayed
fabricated roster/activity states. Wave 7 replaced this with read-only derivation over actual
orchestration sources (`e6e896a`). Wave 8 kept telemetry and learning inert (`b1da48c`).
**Lesson:** A dashboard, event stream or learned pattern can summarize authority but must not
quietly become it. Unknown is safer than a plausible invented state.

## L-010 — Advisory features require production-path wiring

**Classification:** LESSON
**Observation:** Wave 8 primitives passed tests but blocker and acceleration telemetry had no
production callers. Closure review found the gap; `3a9eb3a` wired canonical boundaries and
made completeness scoped rather than falsely global.
**Lesson:** A correct unused emitter is no capability. Validate from the real orchestration
boundary, and distinguish “no event occurred” from “nobody observed it.”

## L-011 — Workspace-local state is not global coordination

**Classification:** LESSON
**Observation:** Persistent State uses filesystem locks and git-ignored runtime records.
Different clones do not share either.
**Lesson:** A second checkout creates a second execution domain, not redundancy. Keep one
canonical checkout until a designed distributed-state layer exists.
**Evidence:** `agent/state/README.md`; reconciliation history.

## L-012 — Correct history by supersession, not erasure

**Classification:** LESSON
**Observation:** The repository preserves retired seat names, legacy statuses, corrected
validation plans and withdrawn advisory facts so later readers can explain why state changed.
**Lesson:** Rewrite current doctrine, but preserve historical evidence with explicit
classification and supersession. Silent cleanup makes past evidence impossible to interpret.

## L-013 — A capability with no entry point is an unfinished capability

**Classification:** LESSON
**Observation:** Phase 2 built the whole CEO-decision path — `needs_input` receipts,
continuation preparation, invocation-scoped approvals, `compose_execution_approvals`, and
`controller.resume` — and every piece worked. None of it was on the CLI. It was reachable only
from inside a Python session that already held the controller's imports, so a decision arriving
over any boundary at all had nowhere to land. Phase 3 could not transport a decision until
`decide` and `resume` were given entry points. The same shape appeared once before, inside
Phase 2: `record_execution_continuation_preparation` existed and nothing called it, so a
`needs_input` result was durably recorded and then unreachable.
**Lesson:** "Implemented and tested" is not the same as reachable. A function whose only caller
is a test is indistinguishable from an unfinished feature the moment something outside the
process needs it. When a capability is declared complete, name the boundary it is callable from.
**Evidence:** `98024fe`; `agent/controller/continuation.py` module docstring.

## L-014 — A retry you cannot justify is worse than a stall

**Classification:** LESSON
**Observation:** Designing the Listener's crash recovery, the tempting behaviour was to
re-dispatch an intent left mid-flight. It is wrong: the Listener cannot prove the Controller did
not already run, and the Controller may have claimed, dispatched a provider, or mutated
production before dying. Re-dispatching would turn an unknown into a duplicate Product
execution.
**Lesson:** Where a boundary cannot observe an outcome, the safe default is to stop, mark the
unknown honestly, and surface it — not to guess in the direction that looks like progress. This
is the same reasoning as the KAN-186 replay interlock, where a stale reconciliation comment
would have caused a migration replay had it been acted on.
**Applied decision:** D-019.
