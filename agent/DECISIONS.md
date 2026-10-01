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

## D-022 — The intent lifecycle is derived from canonical truth, never stored beside it

**Status:** ACTIVE
**Decision:** There is one external vocabulary for a submitted intent's state, and
`agent/core/lifecycle.py` computes it read-only from the Listener's delivery record and
Persistent State. Core stores no status of its own. Where delivery evidence and canonical state
disagree, canonical state wins and the disagreement is named in the answer rather than resolved
silently.
**Why:** Phase 4 left an intent with two state machines that could disagree indefinitely with no
caller able to tell. Adding a third — a Core status — would have made it worse. A derived answer
cannot drift from its sources, and a reconciler that quietly picks a winner is how a fourth
source of truth is born.
**Consequences:** The transport record is authority for whether a message ARRIVED and for
nothing else; Persistent State remains authority for the work, Jira for Product lifecycle, Git
for code. `COMPLETED` means the Controller ANSWERED — a governance refusal is a completed
delivery carrying a refusal — and conflating it with success is the misreading the vocabulary
exists to prevent. The Phase-3/4 delivery record stays served alongside the derived answer as
the audit trail; making it unreadable to look tidier would destroy evidence.
**Evidence:** `agent/core/lifecycle.py`, `agent/core/tests/`, Phase 5 closure in
`agent/ROADMAP.md`.

## D-023 — An unobserved outcome is reported with evidence, never guessed

**Status:** ACTIVE
**Decision:** An intent whose dispatch was interrupted resolves to `INDETERMINATE`, which is
deliberately neither terminal nor a failure, and it is never re-dispatched. The answer carries
the claim, the open leases, the execution receipts and the work item's lifecycle from Persistent
State.
**Why:** Phase 3 established that a Product execution nobody can prove did not happen must not be
repeated on a hunch (L-014), and that remains right. But refusing to guess is not the same as
refusing to help: Phase 4's answer named the problem and left the person settling it to go and
find the facts themselves. Handing over the canonical evidence adds information without adding
permission.
**Consequences:** `INDETERMINATE` must never be collapsed into `UNDELIVERED`, which would assert
that nothing ran — the one thing that cannot be established. Automatic reconciliation of
interrupted dispatches remains deliberately absent; deciding is a human act performed against
the evidence the answer now carries.

## D-024 — The Product executor has a standing tool set; production mutation is never in it

**Status:** ACTIVE
**Decision:** Product executor sessions run with `Read`, `Bash`, `Edit`, `Write` and
read-only `execute_sql` standing. `apply_migration` and the other production-mutating Supabase
tools are permanently excluded, asserted at import and re-checked at call time. A CEO may still
approve a production mutation for one invocation; it can never become a default.
**Why:** The CLI runs in don't-ask mode, so without a standing set every ordinary tool call was
denied and became a separate Thebes approval plus a full resume invocation. One work item spent
four invocations on two catalogue reads, an `ls` and a file write. That was a tax, not a
control: each denial was approved anyway one round-trip later, so it bought no safety and made
routine operation impossible. Safety that only slows down the authorized path is not safety.
**Consequences:** The read-only limit on `execute_sql` is enforced by the environment authority
that grants it and by the brief the executor reads — not by hoping a tool name is harmless.
Production mutation stays a separate CEO act every time it happens, which is the boundary
Product execution has held since Phase 2. An unlisted tool is still denied and still returns as
`needs_input`.
**Evidence:** `agent/execution/claude.py`, `agent/execution/tests/test_executor_runtime.py`.

## D-025 — Thebes pins the executor toolchain per process, never machine-wide

**Status:** ACTIVE
**Decision:** Product executor subprocesses receive `DEVELOPER_DIR` pointing at the Command Line
Tools when that path exists. Thebes does not accept system licences, does not run
`sudo xcodebuild -license`, and makes no machine-wide configuration change.
**Why:** A machine whose full Xcode licence is unaccepted cannot run `/usr/bin/python3`, and
therefore cannot run any Thebes tool, git helper or build command an executor needs. The
Command Line Tools carry no such gate. But accepting a licence on the CEO's behalf is not
Thebes's to do, and changing a machine to fix one subprocess is a far larger act than the
problem requires.
**Consequences:** When the path is absent the inherited environment stands untouched — pinning
a path that does not exist would break a machine that was working. The executor environment
adds `DEVELOPER_DIR` and nothing else: no invocation id, lease, claim, seat or operating mode,
because an executor's environment must not become a side channel for the control-plane state the
brief firewall keeps out of its prompt.

## D-026 — The infrastructure programme is closed; Thebes changes are evidence-driven

**Status:** ACTIVE
**Decision:** Phases 1–5 and final operations hardening are closed and the maintenance baseline
is frozen. Further Thebes infrastructure work requires a real Product need as its evidence, not
an identified gap.
**Why:** The system is now capable of the thing it was built for, and the remaining risk changed
direction: an architecture programme with no Product pulling on it will keep finding defensible
work forever. `MASTER_ROADMAP.md` §58 named this as the Product-Build Continuity Rule before any
of it was built.
**Consequences:** Deferred hardening items stay deferred and remain listed rather than quietly
dropped. Phase 6 remains deferred under D-015's measured-need test; nothing observed in live
operation has justified it. The next act is Product.

## D-027 — Deterministic tests run before the reviewer; retest is bounded; a red run has four meanings

**Status:** ACTIVE (2026-09-15)
**Decision:** Repetitive test execution moves out of LLM reasoning. One canonical router
(`agent/qa/routing.py`) selects the lowest-cost sufficient deterministic layers for a change
from facts the task already carries; `agent/qa/gate.py` runs them by command inside the named
review cycle before any reviewer is dispatched; results reach the reviewer as bounded
structured evidence with artifact references. Every red run is classified as exactly one of
`PRODUCT_DEFECT`, `TEST_DEFECT`, `TEST_INFRASTRUCTURE_FAILURE`, `EXTERNAL_QA_FAILURE`. An
infrastructure failure refuses the validation act without a verdict and without spending a
cycle. A review may be reopened after FAIL at most `MAX_REVIEW_CYCLES = 3` times in total,
enforced in the canonical writer. TestSprite, k6 and BrowserStack are named layers that no
path selects: exploratory needs an explicit request on a user-visible change, performance an
explicit scope, real devices a release candidate.
**Why:** The evidence this milestone was pulled by (D-026's rule): the `qa` seat had burned
whole days in open-ended Chrome sessions; KAN-206's reviewer had to be told by a human that a
runtime check had been performed because nothing deterministic could say so; the retest loop
had no ceiling at all (`test_self_fail` #24 looped to cycle 4 to prove cycles never reset —
nothing stopped cycle 40); and the local `flutter test` toolchain fault looked exactly like a
Product failure. A model that navigates to learn what a command reports is the most expensive
possible way to obtain a bit, and it obtains it unreliably.
**Consequences:** The `qa` seat is test orchestration — interpret, classify, route,
accumulate regression — and no longer the primary functional gate; the layers are. No second
orchestrator, no new agent: `agent.qa` selects no reviewer, opens no context, writes no
verdict, and `record_review_result` still requires the recorded owner, so a green gate cannot
pass a review by itself and a reviewer may still fail a green gate on an unmet criterion.
Tests are Product assets under `Dabbler/dabbler-code/tests/` with a written contract
(`tests/README.md`). Reaching the retest ceiling is a human decision, never a retry. CI is
designed for and not yet wired; local execution is the proof. Secrets stay outside Git;
Product mutation authority is unchanged and no test integration reaches around it.

## D-028 — Seats are human-like employees; Roles own accountability, not model ability

**Status:** ACTIVE (2026-09-23)
**Decision:** Every Seat has four mandatory capabilities: understand and plan,
execute, self-review and audit, learn and adapt. Execution includes decisions,
directions and delegations as well as technical work. Roles define continuing
accountability, decision authority, routine scope and conflicts; providers and
models are replaceable mechanisms. Exactly one Role owns each decision class. CEO
approval is reserved for company direction, investment, legal/external commitment,
and authority constitution. Self-review is normal; independent review is triggered
only by enumerated risk or conflict. Every decision has temporal scope, and accepted
learning must have a behavioral hook or be explicitly informational.
**Why:** The former structure turned transient instructions into permanent identity,
routed routine technical questions to the CEO, treated senior decision work as
non-execution, and repeatedly requested approval for Definition-of-Done acts already
implied by an assigned task. That made the flow a bottleneck instead of a production
system.
**Consequences:** `agent/EMPLOYEE_MODEL.md` supersedes absolute incapability language
in older Role descriptions. Current Seat/Role ids remain compatible while the new
organization registry composes employee profiles and decision ownership. Work,
decision and delegation records become the professional ledger. RAG remains out of
scope until this foundation proves stable.
**Evidence:** `CONTEXT.md`, `agent/EMPLOYEE_MODEL.md`, `agent/organization/`,
`agent/state/registry/{roles,employee_profiles,authority}.json`.

## D-029 — The four employee capabilities operate on Role Work, not code by default

**Status:** ACTIVE (2026-09-23)
**Decision:** Planning, performing, self-reviewing and learning are phases of an
employee's own job. Their object is the Role-specific output named by the assignment.
Code implementation is only one possible output and is never implied by the word
"perform". A PO performs work by defining and preparing work; a CTO by deciding,
directing or delegating technical work; a software engineer may perform code work.
**Why:** Treating "execution" as a synonym for writing code falsely made leadership
and operational Roles appear unable to execute, while using the same word for the
provider runtime, Jira lanes, code implementation and professional work obscured the
actual authority boundary.
**Consequences:** The employee cycle calls its second phase `role_work`; every Role
declares concrete `work_outputs`; self-review checks the employee's own output and is
not automatically code review or independent acceptance. Technical execution names
remain valid in the provider and workflow contexts where they actually mean runtime
or implementation.
**Evidence:** `CONTEXT.md`, `agent/EMPLOYEE_MODEL.md`,
`agent/state/registry/roles.json`, `agent/organization/`.

## D-030 — The infrastructure freeze of D-026 is lifted for one evidence-backed milestone

**Status:** ACTIVE (2026-10-01). Supersedes the "baseline FROZEN" consequence of D-026;
D-026's rule that Thebes changes need real evidence stands and is satisfied here.
**Decision:** The CEO ruled on 2026-10-01 that the 2026-09-15 freeze was recorded by
mistake. One bounded maintenance milestone is authorized: the three-group operating
model in `agent/ROADMAP.md` "2026-10-01 — Three-group operating milestone". No other
infrastructure work is authorized by this decision.
**Why:** The evidence D-026 asked for exists. Live operation on 2026-09-28..30 produced
the Primary binding, the shared Codex runtime, conversation dispatch and worker-outcome
routing — all written under the freeze as "fixes" because the Product pulled on them.
That is a milestone being built without a name, which is worse than naming it.
**Consequences:** The milestone is scoped by its proofs, not by ideas. It adds no seat,
no agent and no layer. It runs in `SYSTEM_MAINTENANCE` for every code change and returns
to `PRODUCT_EXECUTION` on closure. D-002, D-003, D-005, D-014 and D-017 are unchanged.

## D-031 — Jev is a decision gate, never a seat; a provider never replaces a Role

**Status:** ACTIVE (2026-10-01)
**Decision:** TypeSafe's Jev (a System-One model returning typed Choice/Score/Noul
answers with calibrated confidence; it generates no text) is integrated as a
deterministic gate in front of the accountable decision owners named by
`agent/state/registry/authority.json`. Jev classifies a `decision_required`,
`blocked` or `clarification_required` outcome — decision class, accountable role,
act-autonomously-or-escalate — and scores confidence. The accountable seat still writes
the decision; below the threshold the question goes to the CEO. Jev holds no seat, no
Role, no authority and no write path into Persistent State, Jira or Git.
**Why:** CEO ruling 2026-10-01: *"the gate — model or provider doesn't replace the
seat."* This is D-004 (Role ≠ Seat), D-014 (providers sit behind Thebes) and D-028
(providers are replaceable mechanisms) applied to a model that decides rather than
writes. A model that could own a decision class would be a seat nobody constituted.
**Consequences:** Jev is called through a Thebes-owned adapter behind a fake-able
interface; a Jev failure or an absent key is `decision-gate-unavailable` and the
question routes to the CEO exactly as it does today. The confidence threshold and the
question schemas are tracked configuration, not prompt text. D-002's rule stands:
Jev never selects Product work and never wakes anything.
