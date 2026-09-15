# Thebes durable decisions and invariants

Current as of 2026-09-12. Append or supersede; do not silently rewrite history.

This log owns durable cross-program decisions and their rationale. Exact mechanics remain
in the governing workflow/state source. Historical ticket decisions and Product technical
decisions remain in their Product authorities and are not copied here.

References elsewhere in the repository to numbered `G-`, `T-`, `P-` or `D-` decisions in
an older `DECISIONS.md` refer to the frozen predecessor/Product governance history, not to
the `D-001` series in this file. The canonical Thebes repository began at Wave 5 without
importing those legacy logs; see `agent/history/program-chronology.md`.

## D-001 — Repository memory is canonical

**Status:** ACTIVE
**Decision:** Conversation memory, provider memory and controller summaries are not
canonical. Durable program facts, rules, rationale and lessons must be curated into the
Thebes repository under the source that owns the concern.
**Why:** Sessions are bounded, providers differ, and paraphrased handoffs lose constraints.
A system whose operation depends on one conversation cannot be reconstructed safely.
**Consequences:** `ROADMAP.md` owns program position; `PROGRAM_MEMORY.md` owns shared
context; this file owns decisions; `LEARN.md` owns lessons; runtime facts remain in
Persistent State. Duplicated prose is replaced with links.

## D-002 — Reject autonomous swarm management as the default

**Status:** ACTIVE
**Historical input:** The controller record reports that an early swarm-style run consumed
approximately 41% of a Max-plan allowance in roughly 20 minutes, largely through parallel
management/coordination loops. The current repository has no primary token ledger for that
incident, so the figures are preserved as controller-reported history, not repo-verified
telemetry. Wave 8 commit `b1da48c` independently confirms tokens/cost were deferred because
no factual source existed.
**Decision:** Thebes uses a serial, controller-driven default. Parallel execution is a
bounded policy choice based on independent work, ownership, surfaces, dependencies and
actual model capacity—not an autonomous swarm or one-agent-per-ticket rule.
**Why:** Management chatter and duplicate context can consume the constrained resource
faster than useful execution. More seats do not create more model capacity.
**Consequences:** No standing swarm, no agent supervising agents, no autonomous backlog
burn-down, and no new seat merely because a ticket exists.

## D-003 — No autonomous first or next Product ticket

**Status:** ACTIVE
**Decision:** A controller or executor may not infer permission to select the first or next
Product ticket from queue availability, green tests, a completed task or remaining budget.
**Why:** Queue mechanics answer what is claimable inside authorized Product scope; they do
not establish that scope.
**Consequences:** Bounded acceptance names exactly one existing ticket explicitly. Normal
Product execution requires separate explicit authorization. Canonical protocol:
`agent/ROADMAP.md` “Product acceptance protocol.”

## D-004 — Role is not Seat

**Status:** ACTIVE
**Decision:** Role defines durable capability, authority and learning; Seat is a bounded
instance of a Role. A seat is never repurposed because it is idle.
**Why:** Treating seats as fungible workers turns specialist authority into an ungoverned
pool and fragments learning into seat-specific silos.
**Evidence:** Current constitution `agent/AGENTS.md`; Wave 6 `0f4f805`.

## D-005 — Direct routing, no relay

**Status:** ACTIVE
**Decision:** Hierarchy defines responsibility, not mandatory communication hops. The
controller routes directly to the owning capability; workers return to the declared target
and do not brief chains of agents.
**Why:** Relay roles add latency, token cost and opportunities for distortion without adding
authority.
**Evidence:** `agent/AGENTS.md` and `agent/WORKFLOWS.md` §4.

## D-006 — SELF / QA / PEER are derived routes

**Status:** ACTIVE
**Decision:** Task characteristics are facts; the validation route is a system-derived
consequence. SELF handles bounded low-risk work, QA validates running behavior where policy
requires it, and PEER provides same-capability independent review for elevated risk.
**Why:** Letting executors choose their own route lets them choose the strength of their own
review.
**Consequences:** No route downgrades for throughput. Exact policy is executable in
`agent/state/policy.py` and documented in `agent/WORKFLOWS.md` §3.

## D-007 — PEER failure transfers remediation to the reviewer

**Status:** ACTIVE
**Decision:** On PEER failure, the same-capability reviewer takes bounded ownership of the
failed scope, remediates it, then SELF-reviews that remediation under the explicit exception
recorded by Persistent State.
**Why:** A reviewer who cannot repair the capability is not an effective peer; returning
failure through a management relay recreates the coordination loop.
**Consequences:** Pairing alone grants no cross-capability authority. No eligible peer means
the work waits rather than downgrades.
**Evidence:** `agent/state/README.md` review context and peer-fail transfer contract;
`agent/WORKFLOWS.md` §3.

## D-008 — Implementation complete is not Product authorization

**Status:** ACTIVE
**Decision:** Completing maintenance implementation, documentation or tests never causes an
automatic mode transition or Product selection.
**Why:** Technical readiness and business authorization are different facts.
**Consequences:** The explicit roadmap gate always wins over historical queue/pull prose.
The mode setter records state but does not authenticate human authorization.

## D-009 — Reported observation begins investigation

**Status:** ACTIVE
**Decision:** `observed_condition` begins investigation. Reproduction is a separate explicit
intent and is required only when the evidence needs it.
**Why:** Mandatory reproduction before diagnosis creates ceremony, may target the wrong
environment, and delays inspection of already-useful evidence.
**Evidence:** Post-Wave-8 hardening `e3cf8c6` through `4948607`; operational-context contract
in `agent/state/README.md`.

## D-010 — Reported environment is authoritative

**Status:** ACTIVE
**Decision:** The environment named by the report is the primary target until evidence
corrects it explicitly.
**Why:** Quietly substituting Canary, a deployed site or an automation browser changes the
question being investigated.
**Consequences:** Comparative targets may add confidence but cannot replace the reported
primary runtime.

## D-011 — Browser under test is not browser automation

**Status:** ACTIVE
**Decision:** A report about local Flutter web in Chrome derives a local terminal launch as
the primary path. Browser automation is a distinct execution environment and cannot be
selected merely because the word “browser” appears.
**Why:** Browser identity describes the runtime under test, not the tool used to control it.
**Evidence:** `agent/state/README.md`; hardening tests in
`agent/state/tests/test_operational_hardening.py`.

## D-012 — Validation follows causal and changed surfaces

**Status:** ACTIVE
**Decision:** Required validation scope is derived from diagnosed cause and changed surface.
Shared changes require shared automated coverage and proof on the reported primary runtime;
platform-specific changes require proof on each affected platform. Mentioned but unaffected
platforms are optional confidence targets.
**Why:** Requiring every named platform wastes effort and can obscure whether the actual fix
was proven; under-testing an affected platform is equally unsafe.
**Evidence:** diagnosis/validation-plan contract in `agent/state/README.md`; hardening
implementation `e3cf8c6` through `4948607`.

## D-013 — Dependencies are enforced state, not prose

**Status:** ACTIVE
**Decision:** A cross-ticket order is enforced by one canonical Persistent State `BLOCKS`
edge. Ticket prose and review criteria may explain or defend the order but do not replace
claim-time enforcement.
**Why:** Detecting wrong order at review is later and weaker than preventing an invalid claim.
**Evidence:** KAN-192 → KAN-191 edge recorded in `agent/status/po.md`; dependency model in
`agent/state/README.md`.

## D-014 — Providers sit behind Thebes

**Status:** ACTIVE DECISION; provider abstraction implemented
**Decision:** Claude Code is a provider, not the permanent executor. Codex, Claude Code and
future execution engines sit behind a Thebes-owned provider adapter and receive minimum
execution context assembled by Thebes.
**Why:** Binding controllers directly to one provider makes orchestration, memory and
recovery depend on a vendor-specific interface.
**Core rule:** Codex does not brief Claude directly; Codex briefs Thebes, and Thebes briefs
the selected provider.
**Evidence:** historical target specification §§55–56; current target adopted in
`agent/ROADMAP.md`. Claude and Codex adapters exist; deterministic selection gates capability,
model and effort compatibility.

## D-016 — Claude is the Product-code primary provider

**Status:** ACTIVE
**Decision:** For `PRODUCT_EXECUTION` requests that edit a Product repository, Claude Code is
the default primary provider. Codex CLI is selected only when Claude has a pre-dispatch,
provider-level unavailability or incompatibility that Thebes can name. The receipt records the
primary considered, the ineligibility reason when applicable, and the provider selected.
**Why:** The temporary Codex controller must not bias executor selection toward itself. A Product
execution failure after Claude dispatch remains evidence for the same claimed work; it never
causes a silent switch to Codex.
**Consequences:** This does not alter non-Product reasoning/coordination routing, provider
capability gates, immutable requests, leases, claims, validation routes, or retry policy.

## D-015 — Retrieval is deferred until measured need

**Status:** ACTIVE TARGET DECISION; DEFERRED
**Decision:** Do not add RAG merely because program history is large. Add a knowledge-scaling
layer only after canonical direct reads become a measured bottleneck, and preserve source
identity/provenance when retrieval is introduced.
**Why:** Premature retrieval creates another derived index and another place for stale or
decontextualized truth.
**Evidence:** historical target specification §55; current sequence in `agent/ROADMAP.md`.

## D-017 — The Listener is a communication boundary, never a second Controller

**Status:** ACTIVE
**Decision:** The Thebes Listener owns intake, transport validation, intent normalization,
durable acknowledgement, idempotency, correlation and durable result delivery. It owns no
orchestration decision: not Jira interpretation, Product authorization, capability resolution,
seat selection, claims, leases, workspace allocation, provider selection, validation routing,
integration or lifecycle completion. Those remain the Controller's, and the Controller
re-derives each of them from canonical sources on every invocation.
**Why:** An intake layer that starts deciding anything about Product work is a second
orchestrator with a different name, and two orchestrators disagreeing is the failure the whole
ownership model exists to prevent. Separation is only real if the Listener cannot make the
decision even when it would be convenient.
**Consequences:** No Controller logic may be duplicated into the Listener. Its intent contract
carries no seat, provider, workspace, path, command, validation route or lifecycle field, and
unknown fields are rejected rather than ignored. It invokes the Controller as a separate
process with an argv array, never by importing it, so the boundary is enforced by the operating
system and not by discipline alone. Phase 3 transport is loopback-only and unauthenticated by
design; any non-local exposure requires authentication first.
**Evidence:** `agent/listener/`, `agent/listener/README.md`, Phase 3 closure in
`agent/ROADMAP.md`.

## D-018 — Listener records are communication evidence, not a source of truth

**Status:** ACTIVE
**Decision:** Listener inbox/outbox records state what arrived, whether it was dispatched, and
what the Controller answered. They are authority for nothing. Where a listener record and a
canonical source disagree, the canonical source wins without exception: Jira owns Product
lifecycle, Persistent State owns Thebes operational truth, Git owns code truth.
**Why:** A durable record that is convenient to read is exactly how a fourth source of truth
gets created by accident. A delivery state that merely *looks* like a lifecycle is worse than
no record at all.
**Consequences:** Listener records live under `agent/listener/runtime/`, deliberately outside
`agent/state/runtime/`, and `agent/state/validate.py` does not know they exist. Delivery states
describe the fate of a message only — `COMPLETED` means the Controller returned an
authoritative answer, including a refusal, and never that Product work succeeded. The Listener
reuses Persistent State's atomic-write and `flock` mechanics and nothing else.

## D-019 — Durable intake and idempotent dispatch, not exactly-once

**Status:** ACTIVE
**Decision:** The Listener guarantees durable intake, idempotent dispatch, a durable result and
no silent duplicate Product execution. It does not claim distributed exactly-once semantics,
which the underlying operations cannot provide.
**Why:** Promising a guarantee the mechanism cannot keep is how a system starts lying about its
own failures. Stating the real boundary lets a reader trust the parts that are true.
**Consequences:** An acknowledged intent is on disk before the caller is answered. A result is
written before its intent is settled, so a crash in between is recoverable and truthful rather
than a false success. An interrupted dispatch is marked and left non-eligible, never retried:
the Listener cannot prove the Controller did not already run, and a Product execution it cannot
prove did not happen must not be repeated on a hunch — that is a human decision made against
canonical state.

## D-020 — The Listener is the operational front door; the Controller is internal

**Status:** ACTIVE
**Decision:** Normal CEO/controller operation enters Thebes through the Listener. The
Controller's three orchestrating commands — `execute`, `resume`, `decide` — are launched by the
Listener, not typed; invoked directly they refuse. The direct path survives for recovery,
debugging and tests behind an explicit `--maintenance-reason`, and `integrate` plus the
read-only planning commands are not gated at all because they orchestrate nothing.
**Why:** Phase 3 left the direct Controller path in place and said so honestly, which meant the
front door was a documentation claim. This program has learned twice that prose does not stop a
command being run — `route-to-seat` has to shout "This is a MUST, not a description" for exactly
that reason, and L-013 recorded that a capability's reachability, not its existence, is what
decides behaviour. An enforced default is the only version of this that is true tomorrow.
**Consequences:** The authorizing intent id travels into the Controller's subprocess and returns
on the result as `entry_path` / `entry_reference`, so an operational run names the intake that
caused it and a bypass is visible in the record. **No authority moved.** The Controller decides
exactly what it decided before — authorization, Jira facts, claims, leases, capability routing,
provider selection, validation, lifecycle, continuation, receipts and remediation — and the
Listener gained nothing. Phase 4 changed which door is normal, not who decides.
**Evidence:** `agent/controller/entry.py`, `agent/listener/tests/test_front_door.py`, Phase 4
closure in `agent/ROADMAP.md`.

## D-021 — The front-door gate is a misuse guard, not authentication

**Status:** ACTIVE
**Decision:** The marker that distinguishes a Listener-launched Controller invocation from a
typed one is an environment variable. It must never be described, documented or relied upon as
a security control.
**Why:** Any local process can set an environment variable. Calling this authentication would
be a false claim that invites someone to expose the boundary on the strength of it — and Phase 3
chose loopback-only precisely because nothing here authenticates a caller. A guard that stops
a mistake is genuinely useful; a guard mistaken for a security control is dangerous.
**Consequences:** Loopback-only remains the actual mitigation. Real caller authentication is
still required before any non-local exposure and remains deferred, unchanged by Phase 4. Every
document describing the gate states its limit in the same breath as its behaviour.
