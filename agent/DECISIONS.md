# Thebes durable decisions and invariants

Current as of 2026-11-11. Append or supersede; do not silently rewrite history.
Entries up to `D-052` keep their `D-` prefix; new entries are `TH-053` onward (see the
numbering note above `TH-053`).

This log owns durable cross-program decisions and their rationale. Exact mechanics remain
in the governing workflow/state source. Historical ticket decisions and Product technical
decisions remain in their Product authorities and are not copied here.

**Two logs, two subjects (`TH-070`).** This log decides how Thebes runs.
`Dabbler/dabbler-docs/DECISIONS.md` is the live log for Product, technical and experience
decisions about Dabbler (`P-`, `T-`, `D-`, `G-`). A `G-`, `T-` or `P-` number anywhere in this
repository means an entry in that log. A `D-` number written under `agent/` or in `CLAUDE.md`
means the `D-001` to `D-052` series in this file, which may also be cited as `TH-001` to
`TH-052` (table at the end of this file). The canonical Thebes repository began at Wave 5
without importing the older logs; see `agent/history/program-chronology.md`.

**Archived files (2026-11-10).** Entries below name `AGENTS.md`, `AGENTS_DESK.md`,
`PROGRAM_MEMORY.md` and `MASTER_ROADMAP.md` as they stood when the decision was taken. Those
files now live under `agent/archive/2026-11-10/`; the entries are not rewritten.

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

## D-032 — Teams are execution islands; seats are a shared pool, exclusive in time

**Status:** ACTIVE (2026-10-01)
**Decision:** A **team** is one persistent Claude session that receives a request from the
Codex Listener, runs the seats it needs as subagents inside itself, and returns one
report. Teams are generic, not per project, so one request that crosses the design system
and the app runs in one island when the work has a dependency. Five teams exist, named
after temples (`agent/state/registry/teams.json`: Karnak, Habu, Luxor, Ramesseum, Deir
el-Bahari), as seats are named after deities. Seats remain the single shared pool: a seat
runs in at most one team at a time, enforced by a `seat_reservation` taken before the
subagent is spawned and released when the team's dispatch settles; a team refused a held
seat takes a free seat of the same capability rather than waiting. One Codex Listener
conversation controls every team; one request goes to one free team, so several requests
run in parallel from one conversation.
**Why:** CEO ruling 2026-10-01. The previous shape — one persistent session per seat,
Codex choosing the seat — meant every new agent needed its own session and nobody could
run a dependent two-project change as one piece of work. A team is the Orchestrator
behaviour `CLAUDE.md` already defines (route, dispatch seats, verify, answer), given a
durable session and an address.
**Consequences:** A team is not a seat and not a Role: it holds no capability, claims no
Product work, and appears in no queue. Product work a team runs still goes through
claim → lease → validation under the seat that does it. Teams cannot be created by
Thebes (the Claude Code classifier refuses `claude --bg` from inside a session); the CEO
creates each island once. A team cannot reserve on another team's behalf and a seat
session cannot reserve at all — identity is the session id through its binding. D-002's
serial-by-default rule is unchanged: parallelism is one request per team, bounded by the
number of islands the CEO chose to open.
**Evidence:** `agent/execution/team_pool.py`, `store.reserve_seat`,
`agent/execution/tests/test_team_pool.py`.

## D-033 — Routine actions Jev may approve alone; actions that are always the CEO's

**Status:** ACTIVE (2026-10-01, CEO: "all approved")
**Decision:** When a worker stops to ask for permission, a deny-list in plain code runs
FIRST; anything on it goes to the CEO regardless of any model's confidence. Only then is
Jev asked one typed Choice: is this request one of the allowed routine actions? A
confident match is approved by policy and the same worker is resumed at once; anything
else goes to the accountable role or the CEO (D-031). Every approval is a durable
`decision_request` with the gate's confidence.

| Jev may approve alone (when confident) | Always the CEO's, enforced before Jev is asked |
|---|---|
| create or switch a working branch; commit on it | merge or push to `main`; `push --force`; `reset --hard`; delete a branch |
| run tests, lint, format, analyze | push to Canary (Canary is the release, P-030) |
| run code generation (one `devops` slot at a time) | production database, migrations, anything touching production data |
| install a package already in the lock file | starting the next Jira ticket (D-003); moving any ticket to Done outside its route |
| read-only queries: database, Jira, git history | adding a dependency; changing schema design; changing role files or decisions |
| post a findings comment on a Jira ticket | spending money; secrets, credentials, permissions, settings |
| file a follow-up ticket in Backlog | sending anything outside: email, Slack, publishing a page |
| move its own ticket into its own execution status | anything in another repository |
| open a pull request (never merge) | |
| retry a failed test or delivery, once | |
| resume the same worker with an answer | |
| choose between options the acceptance criteria already allow | |
| release a finished worktree; clean its own temp files | |

**Why:** The CEO's goal for Thebes: work continues to done without obstacles and with
less token usage. A worker that stops for "may I commit?" and waits for a human, or wakes
a Claude session to be told yes, spends minutes and tokens on a decision with one safe
answer. A typed yes from Jev costs ~$0.00003 and under a second. The deny-list exists
because confidence is not authority: no score lets a model push `main`.
**Consequences:** D-031's "a provider never replaces the seat" stands — Jev approves
actions the rules already permit; it decides nothing new. The deny-list is tracked
configuration (`agent/state/registry/decision_gate.json`) and tested. D-003 and P-030 are
unchanged.

## D-034 — The orchestrator is one Claude session, called only when a side chooses to ask

**Status:** ACTIVE (2026-10-01)
**Decision:** The orchestrator is ONE persistent Claude session (`orchestrator` binding)
that runs the leadership seats — `cpo`, `cto`, `cxo`, `analyst`, `pm`, `po`, `qa`,
`devops`, `content-manager` — as subagents and returns one answer. It is a service either
side calls, never a layer: Codex → team → result and team → Codex stay direct. Codex
dispatches to it when the CEO wants an answer rather than work ("what do we have?");
a team or seat reaches it through `decision_required` / `blocked` /
`clarification_required`. It decides who answers (route-to-seat), may combine several
roles for one question, and may answer a data question itself. Jev is used only for
closed choices (who owns this; is this routine; yes/no) and never as the front door.
**Why:** Jev returns typed values and cannot run a subagent or write an answer, so no
agent runs "on Jev". One session, not one per leader: nothing is gained by five
restarting processes, and the CEO wants to ask "what do we have?" without naming a role.
**Consequences:** The orchestrator binds like a team and shares the seat pool; it handles
one question at a time (a second orchestrator may be added when that bites). When it is
unbound, a decision falls back to the accountable seat's own session, then to the CEO.

## D-035 — Every decision is delegated to the orchestrator; four hard stops remain the CEO's

**Status:** ACTIVE for the delegation; **its four hard stops are SUPERSEDED by D-043
(2026-10-27)**: only money, `main` and sending outside reach the CEO.
(2026-10-01, CEO: option (أ) — "أقلل الرجوع ليا بأكبر شكل ممكن")
**Decision:** The CEO delegates every decision to the orchestrator and the roles it runs:
scope, priority, **the next ticket to start**, acceptance, architecture, **adding a
dependency or changing a schema design**, experience, content, releases to Canary
preparation, test strategy. A gate that is unsure, a CEO-class question, or an unbound
seat all go to the orchestrator, which decides who answers; a worker or role may never
answer "this needs the CEO". Exactly four hard stops remain the CEO's, enforced in plain
code before anything reaches a model: (1) merging or pushing `main` and destructive git
(P-030); (2) production data and migrations; (3) spending money, secrets, credentials,
permissions; (4) sending anything outside the company. Editing governance files
(`DECISIONS.md`, `CONTRACT.md`, `MANIFESTO.md`, role files, `authority.json`) stays a CEO
act, because the orchestrator must not rewrite the rule it is judged by.
**Why:** The CEO's goal is work that continues to done with the fewest returns to him.
The first live orchestrator answer listed three items "needing your decision"; under this
rule those go to `cpo`/`cto`/`cxo` inside the orchestrator instead.
**Supersedes:** D-003's "no autonomous next ticket" as a CEO gate — selection of the next
ticket is now `pm`/`po` Role Work inside the orchestrator, still through the canonical
Ready → claim path and still one ticket per team at a time. D-033's deny-list loses
`next_ticket` and `design_or_governance` (dependencies, schema design); `governance_files`
is added. The authority registry's four `ceo` classes are read as "orchestrator decides,
CEO informed" except where a hard stop applies.
**Consequences:** `agent/state/registry/decision_gate.json` deny-list; `decision_gate.
classify_and_resolve` routes unsure/CEO-class/unbound-seat to the orchestrator; the
orchestrator and Codex bootstraps carry the delegation text. The CEO can narrow this at
any time by adding a pattern to `ceo_only`.
## D-036 — Any Codex conversation on this machine is a Listener; reply mode is probed, not chosen

**Status:** ACTIVE (2026-10-02)
**Decision:** A Codex conversation opened in this folder — Desktop, Desktop over SSH, or
the phone over remote control — reads the Listener role from the repository's root
`AGENTS.md` and needs no pasted bootstrap. On its first dispatch Thebes registers it and
probes once whether it can write into the thread (`thread/resume`): writable → `push`
(result delivered as a turn while Codex is idle); held by another client → `inline`
(Codex collects the result itself with `conversation_dispatch wait`, which is durable and
repeatable). The accepted dispatch carries `reply_mode` and the exact `next` step.
**Why:** The CEO was away from the desk and could not reach the Mac over SSH; the phone's
remote-control link reached it but holds the thread's single writer while connected, so
Thebes could not push results into it. Registering by hand and pasting a bootstrap per
conversation is the kind of friction this programme exists to remove.
**Consequences:** `codex_runtime.auto_register`, `attach_inline`,
`conversation_dispatch.wait_for_result`; the pasted bootstrap stays only for conversations
Thebes created itself. The orchestrator and teams are unaffected: a result's route back is
the Listener's concern alone.

## D-037 — Three kinds of session only; CEO orders are executed; more than one PO

**Status:** ACTIVE (2026-10-02, CEO)
**Decision:** (1) Thebes runs exactly three kinds of Claude/Codex session: the Listener
(any Codex conversation), ONE orchestrator, and teams. Every role — po, cto, cxo, pm,
frontend-N, backend-N — is a subagent inside the orchestrator or a team; single-role
sessions are retired (`po`, `frontend-1`, `frontend-2` bindings set `retired`, records
kept). (2) A CEO direct order ("move KAN-348 to Ready") goes to the orchestrator marked
`CEO ORDER — execute, do not evaluate:`; the orchestrator runs the owning role and does it,
stopping only at a D-035 hard stop. (3) There is more than one PO seat (`po`, `po-2`;
topology ceiling 3) so a PO is free whenever teams run in parallel; a held `po` offers
`po-2` as the free alternative. Acceptance authority is per ticket (the PO who wrote its
criteria), not per Project.
**Why:** CEO, 2026-10-02: work stalled with "zero productivity, 100% complexity" — a CEO
order to move one ticket passed through a team and the orchestrator, then waited on a
single `po` held elsewhere, while a stray single-role `po` session added a fourth layer.
**Consequences:** `AGENTS.md` routing table; orchestrator envelope carries `ceo_orders`
and `po_pool`; `seats.json`, `topology.json`, `employee_profiles.json`, binding and
generated agent for `po-2`. The project registry keeps `current_po_seat_id: po` as the
Project's primary PO; `po-2` is an additional seat, not a second owner of the board.
Mode switches use `python3 -m agent.state.mode set …` so one permission rule can allow
them.

## D-038 — One Codex conversation, three Claude sessions

**Status:** ACTIVE (2026-10-02, CEO: "stop the mess … only 3 conversations on Claude —
Orchestrator, Karnak and Luxor — and talk to only one Codex conversation"; chose A)
**Decision:** The running Claude sessions are exactly `thebes-orchestrator`,
`thebes-team-karnak` and `thebes-team-luxor`. The CEO's single Listener is the Codex
conversation "Hi There from Local through SSH" (`01a0f777-…`, Desktop over SSH, also
visible on the phone), recorded in `agent/state/registry/listener.json`. Thebes refuses to
auto-register any other conversation (`not-the-listener`); every other registration is
retired, records kept. `frontend-1`, `frontend-2` and `po` sessions were stopped, not
deleted. Moving the Listener is one edit to `listener.json`.
**Why:** Test conversations and single-role sessions accumulated during the milestone and
the CEO could no longer tell where to look.

**Addendum to D-035, CEO 2026-10-02 — decide and go, no bureaucracy.** A decision is not a
record-keeping act. The orchestrator decides and the work proceeds; it does not write the
decision to Jira as a step of its own, and it does not treat "recording the decision" as
work. A ticket's own lifecycle (comments, transitions) stays with the seat executing that
ticket, as `WORKFLOWS.md` already says. The measure is the ticket reaching Done.

## D-039 — Claude-only Thebes: the orchestrator is the CEO's front door

**Status:** ACTIVE (2026-10-02, CEO: "I want to exit Codex … talk to the orchestrator
directly and remove the Listener island … send my request here and divide tasks to teams")
**Decision:** The CEO talks to the `thebes-orchestrator` Claude session directly (Remote
Control on desktop or phone). It is the Listener: it routes work to free teams with
`conversation_dispatch dispatch` (its own `CLAUDE_CODE_SESSION_ID` is the origin, accepted only
when it equals the bound orchestrator session), answers questions and executes CEO orders
itself with seats as subagents, and takes team results, team decision requests and watchdog
alerts from **its inbox** (`agent/execution/inbox.py wait`, one background command that exits
when something arrives). Nothing stops or resumes the orchestrator: a decision request routed
via the orchestrator is held for the inbox (fresh capability on collection) instead of being
delivered by stop → `--bg --resume`. The orchestrator may hold a seat for a CEO order it runs
itself under a `ceo-<label>` id (orchestrator only; lapses after one hour). Operating card:
`agent/ORCHESTRATOR.md`. The Codex path (D-036, D-038, root `AGENTS.md`) still works but is no
longer the front door; Codex is not required.
**Why:** One conversation for the CEO, no second app, no Listener hop, and the orchestrator's
live chat is never interrupted by a delivery. Teams stay the execution islands (D-032);
decisions stay delegated (D-035).
**Consequences:** `conversation_dispatch` (Claude origin, inline reply, no Codex turn),
`decision_gate` (inbox delivery, origin-aware continuation, origin-neutral envelopes),
`store.reserve_seat` (`ceo-` holds), validator (Claude-origin dispatch, `ceo-` reservations),
`inbox.py`, `test_inbox.py` (7 tests). P4 is proven by one live round-trip from the CEO's
message to the orchestrator; P5 (bootstrap) is still open.

## D-040 — Jira follows a team dispatch; the PO records Ready facts by command

**Status:** ACTIVE (2026-10-03, CEO: "when a dispatch carries a KAN key it moves the ticket … a
way to record effort and Ready from the PO", answered "1 yes, 2 yes")
**Decision:** (1) A conversation dispatch that names one ticket (`--ticket`, or the only KAN key
in the prompt) moves it in Jira: to its execution lane when the team receives the work (the
task's `required_capability`, or the dispatch's `--capability`; comment only when neither is
known), and to its review status when the team reports `completed` (the route Thebes policy
derived for the task; Self-review for a ticket Thebes has no record of). Each step is
commented with the team's name; `failed` and CEO escalations comment without moving. A
continuation dispatch inherits the ticket and never rescans the decision text. Persistent State
observes Jira after each move. A Jira failure never blocks the work: it is recorded on the
dispatch and raised as a `jira-sync-failed` alert. Only the canonical workspace's runtime
writes the real board. (2) `python3 -m agent.state.ready` lets the PO record capability and
Work Effort with provenance, admit a ticket Thebes has never seen, and optionally move it to
Ready, so a CEO-ordered ticket can take the normal claim path. Surfaces stay the executing
seat's assessment.
**Why:** A team dispatch bypasses claim → lease → execute, the only path that moved Jira, so
the board went stale and the PO synced it by hand.
**Consequences:** `agent/execution/jira_sync.py`, dispatch `--ticket`/`--capability`,
`store.admit_task` / `store.set_work_profile`, `agent/state/ready.py`,
`agent/state/registry/jira.json` (non-secret email and cloud id; the token stays in the
Keychain, service `thebes-jira`), `jira.py` reads both, `test_jira_sync.py` (10 tests).
**Defect found live while building (2026-10-03 12:02 UTC):** in-progress code read the
dispatch's secret capability as the lane, stored it on `cdispatch-4a2527ac…` (local runtime
only, gitignored; cleared) and moved KAN-408 from Design to Operations. Fixed (parameter
renamed, regression test). The ticket needs moving back to Design by hand: the automated
correction was refused by this session's permission check. Building outside
`SYSTEM_MAINTENANCE` let a live dispatch run half-built code, which is exactly what the mode
exists to prevent.

## D-041 — Review verifies the claim; it never redoes the work

**Status:** ACTIVE (2026-10-04, CEO: "the review is meant to confirm the work, not to redo it,
nor to spend time, effort and tokens"; also steps 1–3: a branch per team, a brief template,
decisions settled before dispatch)
**Evidence (measured 2026-10-04):** of 136 team dispatches, 40 stopped. Keyword tally of their
reports (approximate; a report can match several): decisions needed 27, permission/hook refusals
22, git/worktree clashes 21, missing input 8, session cut or limit 4. Karnak's session ran
`flutter test` 228 times and `flutter analyze` 195, and never once invoked the `qa` seat: Thebes'
cheapest-layer QA routing (`agent/qa`) and bounded retest exist, but a team dispatch bypasses
them, so review was subjective po/cxo opinion repeated per round (KAN-368: nine dispatches).
Since D-040 a completed dispatch moved its ticket to review and nothing ever closed it.
**Decision:** (1) One branch per team (`<base>-<team>`), enforced in the brief lint; integration
into a shared base is one serial `INTEGRATE` dispatch (`integration-busy` otherwise). (2) A
dispatch that names a ticket carries a brief (GOAL, BRANCH, ALLOWED PATHS, FORBIDDEN, DECISIONS
MADE, IF BLOCKED, CHECKS) or is refused naming everything missing
(`agent/execution/dispatch_brief.py`). (3) The orchestrator settles open decisions before
dispatching and writes them into DECISIONS MADE. (4) Review is verification: the team reports a
VERIFY block (branch, sha, worktree, evidence per check); `agent/execution/verify.py` re-runs
the declared `run` checks once on that commit at zero tokens, sends back only failures, allows
`MAX_CYCLES = 2`, then marks the review exhausted with a reason on the ticket and an alert —
no third pass. `judge` checks go to one reviewer for one pass. A SELF-route ticket closes on
pass; PEER/QA routes keep their review status with verified evidence. A check Thebes cannot run
is an infrastructure error, not a team failure. `--ticket` is explicit only: D-040's inference
from the one KAN key in a prompt is withdrawn, because a question that mentions a ticket would
have moved it.
**Consequences:** `dispatch_brief.py`, `verify.py`, `jira_sync.on_verified/on_exhausted`,
inbox `verification` and `judge` items, envelope VERIFY block, `store.admit_task(work_effort=)`,
`test_verify.py` (14 tests), `ORCHESTRATOR.md`, `WORKFLOWS.md` §3 "Team dispatches". Not done
here: automated golden/screenshot generation for design fidelity (a `run` check can call a
golden test that already exists), and a `qa`-seat runtime layer for dispatches.

## D-043 — Autonomy constitution: only money, `main` and outside reach the CEO

**Status:** ACTIVE (2026-10-27, CEO: "انا مش ديفلوبر، انا CEO … مهمتي بتنتهي عند التاسكات
وعايز اشوف الحاجة لايف"; he approves technical prompts unread, so a prompt to him is not a
safety check). **Supersedes** the hard-stop list of D-035, the CEO-only Supabase tools of the
D-042 draft and the "production data" / "secrets" CEO categories of D-033 wherever they disagree.
**Evidence (measured 2026-10-27):** 8 independent paths put a technical question in front of the
CEO — Claude Code permission prompts on his phone (4 teams in default mode, Memphis's
`sql_hook` returning `ask` on 195 writes, a classifier environment written for another
project), `ops_guard`/`sql_hook` texts telling teams "this is the CEO's", the Memphis brief's
"blocked needs-ceo" rule, substring CEO categories (replaying 376 recorded decision requests:
95 escalated under the old rule, 3 under the new one, all three genuine), stale hard-stop
texts, watchdog/osascript alerts, "relay every result" in ORCHESTRATOR.md, and no loop
breaker (KAN-645 was re-asked 140 times in 10 hours).
**Decision:**
1. **One source:** `agent/state/registry/autonomy.json`, read through `agent/state/autonomy.py`.
   Only `money`, `merge_or_push_main` and `external_send` reach the CEO, and only when a sentence
   ASKS for that act (a request cue) and does not negate it. A keyword alone never escalates.
2. **Owners, not askers:** database work (additive, user-data edits, DROP/DELETE/TRUNCATE) and
   alpha deploys are Memphis's — destructive SQL is snapshotted into `thebes_backup` first and
   logged to the SQL ledger; Canary, production configuration and governance are the
   orchestrator's. A permanent never-list (wrong Supabase project, vault/auth secrets, GRANT to
   anon/public, force-push, push `main`, project lifecycle) is refused by code with the
   alternative written in; a refusal is an answer, never a question.
3. **Nothing falls through to the CEO:** gate unavailable, orchestrator unbound and delivery
   failure all hold the request for the orchestrator's inbox (`via: orchestrator`).
4. **Repeat guard:** the 2nd identical report on a ticket goes to the orchestrator for a
   different decision; the 3rd (or more than 6 in 3 hours) labels the ticket `stuck`, comments on
   Jira and stops the loop.
5. **Review stalls** wake the reviewer (Edfu on the claude channel); no desktop notification.
**Consequences:** `autonomy.json`, `autonomy.py`, `decision_gate.py` (`ceo_only_hit`, `route`,
`repeat_count`, `_mark_stuck`, `_to_orchestrator`), `validate.py` (held-for-orchestrator
requests, `stuck`), `inbox.py`, `review_queue.notify_stalled`, `watchdog.py`,
`conversation_dispatch.py` (Memphis brief owns DB), `codex_runtime.py`, `ORCHESTRATOR.md` §5–6,
`REVIEWER.md`, `AGENTS.md`, `route-to-seat` skill. Still to land: a policy hook that answers
every permission prompt allow/deny (never ask), `sql_snapshot.py`, team settings with auto
mode, and Done gated on the commit being live on alpha.dabbler.pro.

## D-044 — The orchestrator speaks from state and acts only on the CEO's own words

**Status:** ACTIVE (2026-10-30, CEO: the orchestrator "creates tasks I didn't order", "says a
team holds a ticket it finished an hour ago", "merged without my order", and there was no record
of who did what). **Narrows** D-043: autonomy covers HOW work is done, not WHAT new work exists
or what reaches Alpha.
**Evidence (measured 2026-10-30, session `c49d2414`, 338 MB):** 162 compactions, 31 in the last
3 days, 3 during a live CEO exchange; 22 incidents. The orchestrator sent the PO to create the
"Recurring games" Epic and KAN-692..707 on an authority it wrote itself ("PM ruling + CPO
ranking already adopted by the orchestrator"), sent Memphis to merge KAN-700/704/706 into Alpha
unasked, and answered "KAN-693 is with Luxor" 40 minutes after Luxor had finished. Every ticket
is authored by `workflow@dabbler.pro`, and nothing linked a ticket or a merge to a CEO message.
No intervention was active: the refusals came from the classifier, the password rule and
dependency blocks, not a freeze.
**Decision:**
1. **CEO messages are recorded by the harness**, not the model: a `UserPromptSubmit` hook
   (`agent/scripts/ceo_prompt_hook.py`), orchestrator session only, keeps his text verbatim in
   `runtime/ceo-messages.jsonl`. Wakes, task notifications and other sessions' messages are not
   his and are not kept.
2. **Two acts need his order, enforced by code:** creating a Jira ticket/Epic and merging into
   Alpha. `python3 -m agent.execution.orders grant` accepts only a quote found verbatim in a
   message of his from the last 24h; a grant lasts 2h, a create grant counts down, a merge grant
   names tickets or says `all-reviewed`. `agent/scripts/order_gate.py` (PreToolUse) denies the
   Atlassian createJiraIssue tool, a shell `create_issue(` and a push to Alpha/alpha-ds without
   one; `intake.create` requires it; `integrate.dispatch_for` holds a branch whose tickets are
   not all ordered (`waiting-ceo-merge-order`). Order files cannot be written by hand. Only
   sessions bound to Thebes are gated; an unbound session is the CEO at his keyboard.
   Moving tickets to Ready and adopting CPO/CTO defaults are NOT gated (CEO's answer).
3. **Every act is on a ledger** (`runtime/action-ledger.jsonl`): dispatches from every path
   (orchestrator, ready-dispatcher, review-queue, verify, decision-gate, integration), grants,
   refusals, creations and Alpha pushes, each with its order or rule. `orders log` answers "who
   did this and on whose word".
4. **Facts in every turn:** the same hook injects `agent/state/facts.py` — teams BUSY/FREE from
   open dispatches, the last 8h of finished work with review and Alpha state, what passed review
   and waits for a merge order, open orders, recent acts — headed by the rule that claims come
   from that block or a fresh command, else ما أعرفش. Local files only, ~0.15 s.
5. **Rotation:** a `PreCompact` hook counts the orchestrator's compactions; the watchdog
   (`rotate_orchestrator`) starts a fresh `thebes-orchestrator` session after 4 compactions or at
   a new day, only when it is idle, the CEO has been quiet 10 min, no execution lease is open and
   nothing open still reports to the old session id. The handoff is the fact block plus his last
   24h of messages verbatim; nothing else from the old conversation. The binding is CAS-rebound
   (the old id kept in `previous_session_ids`) and the old waiter returns `rebound`.
**Consequences:** `orders.py`, `facts.py`, `ceo_prompt_hook.py`, `order_gate.py` (+ `.sh`),
`.claude/settings.json` hooks, `intake.py`, `integrate.py`, `conversation_dispatch.py` and the
`THEBES_ACTOR`/`THEBES_RULE` tags in `ready_dispatcher.py`, `review_queue.py`, `verify.py`,
`decision_gate.py`, `watchdog.py`, `inbox.py`, `ORCHESTRATOR.md` §8. Tickets now stay in Review
until he orders the merge, because D-043's "Done = live on Alpha" waits on that order — this is
his decision's consequence, not a defect.

## D-045 — Liveness: every team is probed every 5 minutes, busy or not

**Date:** 2026-11-01 · **By:** CEO
**Context:** The CEO found the orchestrator believing work was finished when it was not, or
that work sat with a team at some stage when it did not. Dispatch-and-wait only notices a team
when it reports back. A team that hangs (Memphis 2026-10-30: one `execute_sql` never returned,
and it looked busy for 10h), or a team the orchestrator thinks is free but is still working, is
never asked. His words: «اي اوركستريتور … مش بس يدي التاسك ويستنى الاجابة … كل 5 دقايق يشوف
الحاجة ايه اللي واقف فين … لكل التيمز حتى اللي ما بتشتغلش».
**Decision:**
1. **What runs:** `watchdog serve` calls `liveness.maybe_sweep()` every 5 minutes. It probes
   **every** team in `teams.json`, whatever the orchestrator believes.
2. **What a probe reads:** the CLI agent row, the transcript's last write, the pending tool call,
   open dispatches and held review claims. It never types into the session, because a probe that
   interrupts the work it is checking would itself be the fault.
3. **The statuses:**
   - `busy`
   - `free`
   - `silent` — working, but quiet for 20 minutes
   - `untracked` — working with no dispatch; 10 minutes of grace after a submit
   - `blocked`
   - `stalled`
   - `no-session`
4. **Where it shows:** the snapshot (`runtime/liveness.json`) appears as `LIVENESS` rows in every
   fact block (D-044). A snapshot older than 15 minutes is flagged STALE.
5. **What gets reported:** `silent`, `untracked`, `no-session`, and `blocked` without a dispatch
   each reach the orchestrator inbox once per occurrence, as a `liveness` item carrying the
   action to take. `stalled` and `blocked` with a dispatch were already alerts.
6. **Reviving:** `liveness revive <team>` stops a silent session and resumes the same session id
   with an explanation, and is ledgered (`revived-team`, rule D-045). It is refused unless the
   team really is silent.
7. **The rule binds every orchestrator, current and future:** `ORCHESTRATOR.md` §9. Claims
   about what a team is doing come from those rows.

**Also (D-044 hole found the same day):** the CEO typed «ادمج KAN-703» into the retired
orchestrator session `c49d2414`. It had no gate and no fact block, and the live session never saw
it. Now:
- his messages to a retired session are recorded (`retired_session`);
- they are shown to the live one under `CEO MESSAGES TYPED INTO A RETIRED SESSION`, and can be
  lifted as orders;
- the retired session is denied every act but reading, and tells him where to continue;
- the order gate's PreToolUse matcher widened to `mcp__.*|…|Agent|SendMessage`.

**Consequences:**
- new: `agent/execution/liveness.py`, `tests/test_liveness.py`;
- changed: `watchdog.serve`, `inbox.pending/collect/oldest_waiting`, `facts.build`,
  `orders.retired_orchestrator` and `record_message(retired=)`, `ceo_prompt_hook._retired`,
  `order_gate.retired`, `.claude/settings.json`, and `ORCHESTRATOR.md` §8–9.

## D-046 — The order rule stops invented work, never needed work (refines D-044)

**Date:** 2026-11-01 · **By:** CEO

**Context.** D-044 made two acts wait for the CEO's verbatim order: creating any ticket, and
merging into Alpha. The result was the opposite of its purpose. KAN-688 and KAN-689 passed review
and sat for hours on `waiting-ceo-merge-order` while all seven teams were idle. Meanwhile the
orchestrator ran its own one-minute cron, burning tokens on liveness checks with nothing to do.
CEO: *"احنا كده بنقول له خليك غبي… مش هو ده ابدا الغرض"* and *"مفيش حاجة وكل التيمات واقفة وعمال
بيبعت في لايفنس تشيك… ليه كده؟"*

**Decision.**
1. **Review-passed work integrates into Alpha automatically.** `integrate.ordered_items` lets
   every verified item through, ledgered with rule `review-passed`. A direct push to Alpha outside
   an integration dispatch still needs a `merge-alpha` grant.
   *(Superseded by D-052: review-passed work integrates into `staging`; Alpha moves only on a
   `promote-alpha` order.)*
2. **A ticket that supports existing work needs no order.** That means a non-Epic whose parent
   or blocker is a KAN key, or whose summary names the KAN ticket it serves (`orders.supports`).
   It is ledgered as `supports-KAN-N`, and is enforced in both `order_gate.pre` and
   `intake.create`. **An Epic, or new scope that serves no existing ticket, still needs the CEO's
   verbatim order.**
3. **The orchestrator never polls.** `order_gate` denies `CronCreate` and `ScheduleWakeup` to the
   bound orchestrator, and the settings matcher now includes both. Waking comes only from the
   inbox; the watchdog's liveness probe (D-045) costs no tokens.

**Consequences:**
- changed: `orders.supports`, `intake.create`, `integrate.ordered_items`, `order_gate.pre/post`,
  the `facts` RULE and its awaiting-merge row (a key already integrated by another record is no
  longer listed), `.claude/settings.json`, and `ORCHESTRATOR.md` §8;
- tests: `test_orders`, `test_intake`, `test_integrate`.


## D-047 — Liveness sees tickets with no team, not only idle sessions (extends D-045)

**Date:** 2026-11-02 · **By:** CEO

**Context.** KAN-694 sat in Back-end for days with every team `free`: its last dispatch had been
discarded, and nothing moves Jira when a dispatch dies. D-045 probed sessions only, so the
orchestrator could not see work that had lost its team. The dispatcher picks up `Ready` only, so a
ticket that fell back into a working column was never picked up again.

**Decision.**
1. The liveness sweep reads working-column tickets from Jira (one read-only query) and classifies
   each against the dispatch records and review queue (`agent/execution/orphans.py`):
   `ok`, `orphan`, `dead-end`, `waiting-judge`, `waiting-human`.
2. A `free` team's row says why it is free; `idle-work-waiting` names the tickets.
3. The ready dispatcher re-sends `orphan` and `dead-end` tickets through the normal free-team path,
   at most twice and 30 minutes apart, never into a review column. After that, or for a review
   column, an `orphan` inbox item reaches the orchestrator.
4. Nothing here claims, stops, resumes or types into a running session, and the CEO is not asked.

**Consequences:** changed `liveness`, `inbox`, `facts`, `ready_dispatcher`; new `orphans`;
tests `test_orphans`, `test_ready_dispatcher`. Not done: a ticket reviewed but not merged to Alpha
(branch missing on origin) is not yet an orphan state, and a dispatch discarded while the work is
on Alpha does not yet close its ticket; both wait for the CEO's go-ahead.


## D-048 — One orchestrator conversation, never rotated (supersedes D-044's rotation)

**Date:** 2026-11-02 · **By:** CEO ("موافق")

**Context.** D-044 rotation opened a fresh `thebes-orchestrator` conversation every new day and
after 4 compactions. Every one carries the same name, so the CEO could not tell which was live. Typing into an old one
restarted it: on 2026-11-02 three were running at once (b9b99f0a live; 4e79edf3 and f305ed4e
retired but revived).

**Decision.**
1. Rotation is off (`watchdog.ROTATION_ENABLED = False`). The orchestrator stays in one
   conversation. Compaction is safe because every CEO turn brings the fact block.
2. A prompt typed into a retired orchestrator session is blocked before the model sees it
   (`ceo_prompt_hook`, `decision: block`). The CEO gets one Arabic line, and his words are
   recorded and raised as a `ceo_retired` inbox item for the live orchestrator, which wakes and
   acts on them.
3. The two revived sessions were stopped. `order_gate` already denies any acting tool to a retired
   session.

**Consequences:** changed `watchdog`, `ceo_prompt_hook`, `inbox`; `test_rotation` covers both.
`rotate_orchestrator` stays in the code, unused, so the change can be reversed with one flag.


## D-049 — A ticket every 10 minutes: work runs in parallel, review only where an eye is needed

**Date:** 2026-11-02 · **By:** CEO ("I agree all your recommendations"; "I want work to be a
parallel even on same epic")

**Context.** The bottleneck was process, not coding. Dependent tickets waited for their blocker to
reach Alpha, tickets in one Epic were chained by Blocks links that were only ordering, every
change waited for a reviewer, a screen review covered two languages and two themes, and Ready
often held fewer tickets than there were free teams.

**Decision.**
1. Finished = on Alpha and Done in Jira. Target: 6 tickets an hour across teams, ~50 minutes of
   work at most per ticket.
2. **Stacking.** A ticket whose Blocks-inward blocker has a checked commit (verdict `pass` or
   `needs_judge`, not yet integrated) is no longer waiting: the brief tells the team to merge that
   exact sha, and `integrate.pending` holds the ticket until its blocker passed review
   (`ready_dispatcher.stack_source`, `integrate.stack_wait`). The reviewer judges only the
   commits that carry the item's own key.
3. **Review tiers.** Tier 1 (no screen, nothing sensitive, paths known) passes by itself on green
   analyze and tests (`review_queue.auto_pass_tier1`, reviewer `thebes-tier1-auto`). Tier 2 is one
   language and theme, AR+Dark when user-facing text changed. Tier 3 (money, sign-in, database) is
   unchanged.
4. *(Superseded by TH-077, 2026-11-11: no Ready target, no `ready-below-target`,
   `serial-chain` or `too-big`, and no ticket is split.)* **Ready target.** Ready holds at least 10 startable tickets. Below that the PM gets
   `ready-below-target`, every 15 minutes, whatever the Backlog, and cuts Epics the CEO already
   approved. New scope still needs his order. Ready tickets waiting on blockers raise
   `serial-chain`: the PM keeps a Blocks link only for a real code or data dependency; same Epic is
   not one. One ticket = one screen or one function plus its test.
5. Skills: official sources, plus community skills read in full; nothing that downloads or runs
   npx at runtime. Flutter web only for now.

**Consequences:** changed `ready_dispatcher`, `integrate`, `review_tier`, `review_queue`, `inbox`,
`REVIEWER.md`, `roles/pm.md`; tests `test_ready_dispatcher`, `test_review_fast_path`,
`test_review_tier`. The loop breaker and batched integration already existed; the review skip
already happened before any claim, so the measured "40% waste" was bookkeeping only.

**Correction 2026-11-03:** the tier-1 auto pass called `judge_verdict` with `failed=[]`, which
needs a dict, so every auto pass raised and left a `skipped: auto-pass-failed` done marker. That
marker also hid the item from reviewers, and KAN-736, 737, 738, 739 and 760 sat in review with
nobody looking at them. Fixed: it now passes `{}`, a failed-auto-pass marker is retried after 10
minutes, and a test binds the call to the real `judge_verdict` signature.
Same day: a gauge with the same numbers as last time is asked again only after 4 hours, not 15
minutes. The PM had already answered "Ready 1 of 10: only an Epic order fixes it", and the repeats
reached the CEO about a dozen times.

## D-050 — One live session per team; same-named leftovers are retired

**Date:** 2026-11-02 · **By:** CEO (approved plan; asked "why there is many teams in same name")

**Context.** `claude agents` showed karnak four times, edfu three and memphis twice. Each team
has one bound session and only that one receives work. The rest were leftovers:
`start-teams.sh --restart` and the old orchestrator rotation left old copies alive, a resume that
reaches a still-running session creates a copy (`claude_cli.wait_stopped`), and `start-teams.sh`
found the new session by name and could bind an older copy while the new one stayed orphaned.

**Decision.** `team_pool.sweep_duplicates` runs inside the 5-minute liveness sweep. Any
`thebes-team-*`, `thebes-orchestrator` or `conversation-dispatch-*` session that is not bound,
not targeted by an open dispatch and not the origin of one is retired. A live one is stopped,
which can be undone with `--resume`. One that exited more than 6 hours ago is removed with
`claude rm`, after its transcript is copied to `agent/state/runtime/session-archive/`. The
discard and force flags are never passed, so the CLI refuses on unpushed work. `start-teams.sh`
binds the session that was not there before it ran, then sweeps that team's copies.

## D-051 — The CEO hears a thing once: a gate on every orchestrator message
**Date:** 2026-11-05 · **By:** CEO ("the same message every 5 minutes, maybe thousands of times, and I don't even get a notification")

**Context.** The orchestrator transcript held 1,127 text blocks; one sentence ("the same alert is back, Ready below target, nothing for you") appeared 23 times and a quota message 14 times. The 5-minute wakes (inbox waiter, watchdog, liveness) are correct; the defect was that the orchestrator narrated every wake to the CEO.

**Decision.** `ORCHESTRATOR.md` §5a: speak to the CEO only for a direct answer, a step only he can do (`action`), or a finished task (`update`); everything else is silence. `agent/execution/ceo_notice.py check <kind> <key>` is the gate: an `action` repeats at most every 12 hours, an `update` never repeats, identical text is held for 12 hours, and any other kind is skipped. State lives in `agent/state/runtime/ceo-notices.json`.

**Not done.** Delivery of notifications to his phone is a separate question (Remote Control push); this gate only cuts what is sent.

## D-052 — staging integrates and tests; Alpha is the customer trial
**Date:** 2026-11-05 · **By:** CEO (order msg-20261105084204-831ccacb, "نفّذ التنظيف") · **Amended:** 2026-11-11 by TH-075 (integration runs per patch, not per ticket)

**Context.** Alpha did two jobs: Memphis integrated every verified team branch into it, and it was the build the CEO and trial customers saw at alpha.dabbler.pro. Integration churn therefore reached customers directly, and there was no place to test integrated work before they saw it.

**Decision.** Four branches, four jobs:
- **`staging`** (both repos) is internal integrate and test. Memphis merges verified team branches into it, and dabbler-code `staging` deploys to staging.dabbler.pro (Pages project `dabbler-staging`, production branch `staging`). A reviewed ticket is Done when its commit is on staging and staging.dabbler.pro serves it (`live_check`). `order_gate` refuses a push to `staging` unless an integration dispatch is open.
- **`Alpha`** is the customer trial. It moves only as a promotion of staging that the CEO chose. `order_gate` refuses a push to `Alpha` or `alpha-ds` unless a `promote-alpha` grant is open, and each push spends one unit. The `promote-alpha` grant replaced D-044's per-ticket `merge-alpha` grant, which is no longer accepted.
- **`main`** is production, frozen under P-030.
- **Team branches** are `staging-<team>` in dabbler-code and `staging-ds-<team>` in the design system. Older `alpha-<team>` and `alpha-ds-<team>` names still map to staging in `integrate.py` and `ready_dispatcher.fill_branch`, but no new branch takes them.

**Code.** The decision is implemented in:
- `integrate.BASES`: targets are keyed `staging` and `staging-ds`, and the worktrees are `integrate-staging` and `integrate-staging-ds`.
- `conversation_dispatch` (lane text), `ready_dispatcher.fill_branch`, `intake` (BRANCH template), `ops_guard` (team pushes and the integration refspecs), `orders` and `order_gate`.
- `live_check` and `review_queue`, which now mean staging when they say Done = live.
- `sql_hook.MIGRATIONS_REF` (`origin/staging`), `cloud_lane` and `cloud_prompt` (`staging-cloud-<key>`), `cut_plan`, `teams.json` and `autonomy.json`.

**Not done here.** The fixed push rules `Bash(git -C * push origin integrate-staging:staging)` and `…integrate-staging-ds:staging` must be added to the permission allow list by the CEO; an agent adding a permission rule is refused as self-modification. Until they exist, `integrate.dispatch_for` waits with `push-rule-missing`.

---

# Standing CEO orders moved in from session memory (2026-11-10)

Until 2026-11-10 the orders below lived only in the orchestrator's private session memory
on one machine. They are recorded here so that a fresh clone carries them. Each entry gives
the date and the CEO's words where they were kept, the rule as it stands today, and the
order that narrowed or replaced any part of it. The original memory files are kept unchanged
in `agent/archive/2026-11-10/user-memory/`.

**Numbering.** From this point new Thebes entries use the prefix `TH-` and continue the
number series (`TH-053` follows `D-052`). `D-` is the prefix of the experience decisions in
`Dabbler/dabbler-docs/DECISIONS.md`; the two logs no longer share a prefix for new entries.

## TH-053 — The orchestrator delegates and never executes
**Date:** 2026-10-07 · **By:** CEO · **Status:** ACTIVE

**Rule.** The orchestrator is a dispatcher. Every execution step goes to a team as a
dispatch: code, git merges, pushes, pulls into a checkout, database applies. The
orchestrator keeps discussion, decisions, review of results and the conversation with the
CEO.
**Why.** The orchestrator had been merging, pushing and applying migrations by hand. That
caused faults and kept it busy when new work arrived.
**Where.** `agent/ORCHESTRATOR.md`; `CLAUDE.md` "Which session you are".

## TH-054 — Database work in a team session
**Date:** 2026-10-08, amended 2026-10-13, 2026-10-14 and 2026-10-27 · **By:** CEO · **Status:** ACTIVE

**Rule.**
- A team never runs `DROP` and never calls `apply_migration`. A replacement is done by
  `RENAME` to `*_legacy_vN` plus `REVOKE`. A change is applied as ordered `execute_sql`
  steps, each run once.
- Destructive SQL is Memphis's. Memphis takes a `thebes_backup` snapshot first and records
  the action in the ledger (D-043). It is not a CEO stop.
- Only Memphis applies migrations (CEO 2026-11-10, knowledge inventory Q8).
- Tests do not sweep or scan real tables. They use specific test rows.
- Only the Supabase project `wtncuzcskpigqpmnxwws` is used. The other project on the same
  account is never touched.

**Amendment 2026-10-13 (CEO).** All accounts and data in `wtncuzcskpigqpmnxwws` are test
data; there are no real users yet. Reviewed migrations in a ticket's scope may be applied
there, and write and Realtime tests may run there, in dependency order, with the current
state checked first and a rollback written down. Stop if real user data appears. A test that
was written and not run is never counted as passed.
**Amendment 2026-10-14 (CEO, ledger ref `cloudflare-messaging-approval`).** The Messaging
Worker and D1 on the Cloudflare free tier are approved. Not approved: R2, any paid plan, a
custom domain or DNS change, any change to the Pages project `webapp` or to dabbler.pro.
Agents never write a secret value anywhere; the CEO sets secrets himself.
**Why.** On 2026-10-08 teams lost about three hours to sessions that hung on `DROP` and
`apply_migration`, and one team inserted test rows into live tables.
**Where.** `agent/state/registry/autonomy.json`; `agent/scripts/sql_hook.py`; the dispatch
envelope in `agent/execution/conversation_dispatch.py`.

## TH-055 — The orchestrator runs only `pm` and `po`
**Date:** 2026-10-09, amended 2026-10-21 and 2026-11-10 · **By:** CEO · **Status:** SUPERSEDED by TH-074 (2026-11-11: the orchestrator runs pm, po, cpo and analyst; Memphis runs cto, cxo and devops; qa is Edfu's)

**Rule.** The orchestrator runs two seats itself, `pm` and `po` (`po-2` for the design
system), in the background. A ruling from `cto`, `cpo` or `cxo` is one question dispatch to
Memphis that names every seat needed; Memphis returns one answer. A design-fidelity judge
goes to Memphis (`cxo`) and a behaviour judge goes to Memphis (`qa`). The orchestrator never
starts those seats as its own subagents.
**History.** On 2026-10-21 the CEO moved the PO into the teams. On 2026-11-10 (knowledge
inventory Q6) that was reversed: the PO runs only under the orchestrator, and a team that
needs a scope or acceptance answer ends its turn with one `decision_required` question.
**Where.** `agent/ORCHESTRATOR.md`; `agent/state/registry/teams.json`.

## TH-056 — Cleanup after integration
**Date:** 2026-10-11 · **By:** CEO · **Status:** ACTIVE (target branch changed by D-052)

**Rule.** Finished work ends in one place: the integration branch on origin (`staging`
since D-052) and the local folder `Dabbler/dabbler-code`. A temporary branch, scratch copy
or worktree is removed once its work is integrated. A branch is deleted only when an
ancestor check proves it is merged, or when it is an explicitly abandoned duplicate. Never
delete `main`, `Canary`, `Alpha`, `alpha-ds`, `staging`, `staging-ds` or anything in flight.
A refusal from `ops_guard` is reported, never bypassed.
**Why.** The CEO runs the app from `Dabbler/dabbler-code` and wants one place, with no
leftover branches or folders.
**Where.** `agent/WORKFLOWS.md` (branches); `agent/execution/integrate.py`.

## TH-057 — Claude builds, Codex reviews
**Date:** 2026-10-13, reaffirmed 2026-10-26 · **By:** CEO ("back to the default path, codex review not me or you, codex only reviewer now") · **Status:** ACTIVE

**Rule.** Claude Code teams build. Work that changes the product (code, design system,
migrations) stops in Review, and Codex carries the review. A defect sends the ticket back to
Development for the same team. The orchestrator never reviews product work and never starts
a judge for it. The CEO does not test or approve individual tickets. Text deliverables
(reports, plans, answers) are judged by the orchestrator in one pass.
The review channel is Codex by default; the orchestrator may switch it to Edfu
(`review_queue channel`).
**Where.** `agent/REVIEWER.md`; `agent/execution/review_queue.py`.

## TH-058 — UI tickets carry click-by-click test cases
**Date:** 2026-10-14, exception added 2026-10-29 · **By:** CEO · **Status:** ACTIVE

**Rule.** Every ticket that changes the UI has a test-case section: preconditions (account,
flags, platform), then numbered cases with the exact on-screen labels to click, the expected
result, and the acceptance criterion each case proves. It covers empty, error and denied
states, and RTL and dark theme where the change is visual.
**Exception (2026-10-29).** A ticket labelled "no UI needed" is a code double-check only:
confirm in the code that the change was applied, then pass it. Nobody opens the UI for it.
**Why.** Review slows down when the reviewer has to work out what to press.
**Where.** `agent/roles/po.md` "A ticket that changes the UI".

## TH-059 — A design is read from its Claude Design link, at task time
**Date:** 2026-10-15 ("In all designs just refer to Claude design"), 2026-10-24, 2026-11-05 · **By:** CEO · **Status:** ACTIVE

**Rule.** Any ticket or brief that needs a design points to the Claude Design project
(DesignSync, read-only). No invented layouts and no saved PNG copies. When a task carries a
design link, the team opens the design at that moment, records the file version and the read
time in its report, and implements it as it is. If the design cannot be read, the team
reports BLOCKED; it never builds from memory or from old code.
The Messaging project is `60c6ce9d-7bc1-48b0-855b-550493932c60`.
**Why.** KAN-640 was built from an old version of a design file. The CEO called it "the
biggest mistake".
**Where.** `CLAUDE.md` "Where things live"; `agent/roles/po.md` "A ticket that changes the UI".

## TH-060 — What is asked of the CEO is written in Arabic, with full paths
**Date:** 2026-10-18 ("بعتلي الاكشنز اللي انت محتاجها مني دايما بالعربي"), 2026-10-21 · **By:** CEO · **Status:** ACTIVE

**Rule.** Anything the CEO is asked to do is written in Arabic as one numbered list: where
to go, what to click or type, what to accept. Commands, paths and button labels stay as they
appear on screen. A file handed to him is given with its full real path and a ready command
(`open -e <path>` to read it, `pbcopy < <path>` to copy it).
**Where.** `CLAUDE.md` "Two ways of speaking"; `agent/ORCHESTRATOR.md`.

## TH-061 — Who creates tickets
**Date:** 2026-10-21, 2026-10-30, 2026-11-04 · **By:** CEO · **Status:** ACTIVE (narrowed by D-046, D-049)

**Rule.**
- `pm` runs the board: order, what goes first, what waits, and ticket cutting.
- `po` never creates a follow-up ticket from an existing one. A gap found inside a ticket is
  finished inside that ticket or returned to the orchestrator ("i didn't allow PO to make
  you create infinity tasks").
- A new ticket for a blocker is cut only when the blocker needs a different team. The same
  team does both inside the one ticket and leaves a comment.
- No ticket for new scope without the CEO's order ("متعملش تذاكر تاني من غير موافقتي").
  D-046 narrowed this: a child, a blocker or a defect on work already in flight is created
  without asking.
- Finish before creating (2026-11-04: "ask PM to decrease tasks creation, and let's focus on
  finishing current tasks end-to-end"). A Ready shortfall is answered by pushing open
  tickets to Done, not by cutting more.
- Jira edits (descriptions, labels, moves) are done by `pm` or `po`, with retries. They are
  never handed to the CEO.
**Where.** `agent/roles/pm.md`; `agent/roles/po.md`; `agent/ORCHESTRATOR.md`.

## TH-062 — A ticket that waits on the CEO
**Date:** 2026-10-21 · **By:** CEO ("needs-input column is useless now") · **Status:** ACTIVE

**Rule.** There is no Need Input column. A ticket that waits on the CEO stays in its own
column with the `need-input` label and a comment of numbered Arabic steps, and he is told in
chat. Only two kinds qualify: something only he can type or do, and an order he must give
(under D-043 that means money, `main` or something outside the company). A board move, work
a team can do, and manual testing never qualify. The CEO is never given a `claude attach`
command or a session id.
**Where.** `agent/WORKFLOWS.md` section 2 "Two labels and three moves"; `agent/state/board.py`.

## TH-063 — The board is the truth
**Date:** 2026-10-23, 2026-10-24, 2026-10-27, 2026-11-10 · **By:** CEO · **Status:** ACTIVE

**Rule.**
- Jira is the only task reference, for the orchestrator and every team ("المرجع الوحيد في
  التاسكات ليك وللتيم هو جيرا"). No plan or document is cited as the state of a task. Open
  work is counted from the board statuses.
- The ticket is kept current: on every dispatch, finish and wait, its status is moved (and
  its parent's) and a short comment says who, which branch and what is next.
- Before any status is given to the CEO, the ticket's Jira status and latest comments are
  read, and the full picture is reported: column, commit and branch, what was found, what is
  next. Never "no result yet".
- Status words follow the column. A ticket is "working" only in Front-end, Back-end or
  Operations. It is "finished" only in Review or Done. If the column is wrong against the
  evidence, fix the column and report the new one; do not explain the gap to him.
**Where.** `agent/WORKFLOWS.md`; `agent/execution/jira_sync.py`.

## TH-064 — Board moves
**Date:** 2026-10-22, 2026-10-24 · **By:** CEO · **Status:** ACTIVE

**Rule.**
- A ticket in the Operations column (Design, Content, Operations) never jumps to Review.
  Work that is not code goes to Done from there. Code work moves to a Front-end or Back-end
  status first, is built, and only then goes to Review.
- There is no Returned column. Returned work goes back to its own working column with the
  `returned` label and a comment giving the reason. The label is removed when the ticket
  passes.
- Design tickets have no special closing rule. A design-ready ticket takes the normal build
  and review path, and Thebes closes it on a review pass.
**Where.** `agent/WORKFLOWS.md` section 2 "Two labels and three moves"; `agent/execution/review_queue.py`.

## TH-065 — Local test first; no password typed on a hosted site
**Date:** 2026-10-23, reinstated 2026-10-30 · **By:** CEO · **Status:** ACTIVE (integration target changed by D-052)

**Rule.** App and UI changes are run and checked on localhost, by the team or by Edfu,
before the commit is integrated. The CEO does not test by hand. No agent types a password or
reads the keychain on a hosted site. Localhost with seed or test values is allowed. For a
check on a hosted site, the CEO signs in once in his own Chrome and the agent drives that
open session.
**Why.** KAN-640 was pushed first and tested after; the test showed the old screen and a
cycle was lost.
**Where.** `agent/WORKFLOWS.md` (Done); `agent/REVIEWER.md`.

## TH-066 — An order is an approval; work never stops
**Date:** 2026-10-25 ("اديتك امر، يعني انا موافق"), 2026-10-26 · **By:** CEO · **Status:** ACTIVE (bounded by D-043, D-044, D-046)

**Rule.** Once the CEO orders something, it is approved; nobody returns to ask him to
approve the same thing. Work never stops to wait for him, and he is not handed steps or
permission requests. Thebes decides and acts. The limits: money, `main` and anything outside
the company stay his (D-043), and "do everything" never means inventing new scope (D-044,
D-046). Those few items are batched into one short ask that blocks nothing else. A newer CEO
order overrides an older Jira comment. A classifier denial is never worked around.
**Where.** `agent/state/registry/autonomy.json`; `agent/state/registry/decision_gate.json`;
`agent/ORCHESTRATOR.md`.

## TH-067 — Edfu is QA and never builds
**Date:** 2026-10-25 · **By:** CEO ("edfu is our QA right why working on front end task?") · **Status:** ACTIVE

**Rule.** Edfu never builds, fixes, pushes or writes to the database. No frontend or backend
work is dispatched to it. The lane of a team is read from
`agent/state/registry/teams.json` before a dispatch.
**Where.** `agent/state/registry/teams.json`; `agent/execution/conversation_dispatch.py`.

## TH-068 — Review that cannot finish never reaches the CEO
**Date:** 2026-10-21, 2026-10-22, 2026-10-27 · **By:** CEO · **Status:** ACTIVE

**Rule.** When a review runs out of cycles and the only failing check is a coverage limit of
the reviewer (no defect wording, every other check passing), Thebes accepts the ticket by
code and writes the unverified part on it. A defect, or a doubt, goes to the orchestrator. A
refusal, or a brief the linter rejects, is a Thebes fix. A `review_stalled` alert is handled
silently: the reviewer is woken by code and work continues. A reviewer's question is
answered within 15 minutes.
**Why.** The CEO approves such items unread, so the approval protects nothing and costs his
attention.
**Where.** `agent/execution/exhaustion.py`; `agent/execution/review_queue.py`.

## TH-069 — Where things live
**Date:** 2026-11-05 · **By:** CEO (msg-20261105060822-79366836) · **Status:** ACTIVE

**Rule.** Plans, briefs and reports live only in `Dabbler/dabbler-docs/`. No folder or
worktree per task. One branch per team. No design PNGs. A live test comes before a
screenshot, and a screenshot taken is deleted when the task ends. Documents are moved, never
deleted on an agent's judgment.
**Where.** `CLAUDE.md` "Where things live" is the full text of this order.

## TH-070 — Operating rules live in Thebes; dabbler-docs is Product only
**Date:** 2026-11-11 · **By:** CEO (approval of the knowledge cleanup plan, inventory questions 14, 15 and 21) · **Status:** ACTIVE

**Rule.** How Thebes runs is written under `agent/` and nowhere else. `Dabbler/dabbler-docs/`
holds Product knowledge: what Dabbler is, how the app is built, and the Product, technical
and experience decisions. When the two logs seem to disagree, this log wins on how agents
work and that log wins on the Product.

**What moved.** Operating text that was written in dabbler-docs is copied word for word into
`agent/history/dabbler-docs-operating-rules-2026-11-11.md`. That copy is history. The live
home of each rule is:

| Was in dabbler-docs | Live home in Thebes |
|---|---|
| `CONTRACT.md` section 3: execution ownership, claim, STOP / HOLD / FREEZE, ACCELERATE, Agent View, one work item = one capability | `agent/ORCHESTRATOR.md` for today's dispatch path; `agent/controller/DOCTRINE.md` for the kept Controller path |
| `MIGRATION.md` (the 2026-09-02 repository split) | `CLAUDE.md` and `agent/SETUP.md` say where things live today |
| `G-013` (17 seats, no orchestrator) | Superseded: `agent/state/registry/seats.json`, `agent/ORCHESTRATOR.md` |
| `G-018` (the board is six columns) | Superseded: `agent/WORKFLOWS.md` |
| `G-022` (who writes which rule file) | The table "Where each rule lives" in `CLAUDE.md` |
| `G-029` (`po` owns Jira) | Narrowed by `TH-061` and `D-049`; `agent/roles/po.md`, `agent/roles/pm.md` |
| `T-088` to `T-095` (executor evidence, validation dispatch, review recovery, surfaces, validation workspaces) | `agent/controller/DOCTRINE.md` and the code it describes |
| `T-096` (integration lands a range in order) | `agent/WORKFLOWS.md`, `agent/execution/integrate.py` |

**In dabbler-docs.** The `CONTRACT.md` section and `MIGRATION.md` are replaced by a pointer.
The decision entries keep their text, because that log is append-only, and each carries a
note that names its live home. The IDs stay defined there and are not redefined here.

**Not moved.** Reports stay in `Dabbler/dabbler-docs/` under `TH-069`, including the two
reports about Thebes itself (`thebes-knowledge-inventory-ar.md`,
`thebes-problems-report-ar.md`).

## TH-071 — Staging's CI check stays required; integration waits for it
**Date:** 2026-11-11 · **By:** CEO (approved plan) · **Status:** ACTIVE

**Rule.** The protection on `staging` requires the check `analyze-and-test`, and nobody lowers
or removes it, not even for a short time. `ci.yml` runs on pushes to `staging` and to every
`staging-*` branch, and on PRs into `staging` and `main`. Memphis integrates by pushing
`staging-memphis`, waiting for a green `analyze-and-test` on that commit, and then
fast-forwarding `staging` to the same commit. GitHub ties a check to the commit, so the push to
`staging` is accepted.

**Why.** On 2026-11-10 the check was required, but `ci.yml` ran only on `Canary` and on PRs into
`main`. It never ran for staging, so every push was refused. Lowering the protection was proposed,
and the auto-mode classifier refused it as a CI bypass. Running the check is the fix.

## TH-072 — The orchestrator speaks only with news
**Date:** 2026-11-11 · **By:** CEO · **Status:** ACTIVE

**Rule.** These are not news, and the orchestrator ends them with no text: a wake, a waiter
restart, a session start or a resume after a reboot. It speaks only to answer him, to post a
finished task's update once, or to ask for something only he can do. An ask still open later is
reminded as one consolidated list, gated by `ceo_notice check pending`. That list is sent when the
set of asks changes, and otherwise at most once every 12 hours. Rule text: `agent/ORCHESTRATOR.md`
§1 and §5a. The waiter's `next` text and the start and resume prompts in `agent/scripts/` say the
same.

**Why.** He is often away from the PC, and the same "waiting / ready / I'm back" lines reached him
over and over.

## TH-073 — No dialogs from the orchestrator; a recreate keeps the conversation
**Date:** 2026-11-11 · **By:** CEO · **Status:** ACTIVE

**Rule.** The orchestrator never calls `AskUserQuestion`, `EnterPlanMode` or `ExitPlanMode`. When
it finds itself in plan mode, or in a mode that asks before each tool, it acts on nothing. It sends
him one gated Arabic line asking him to switch the session back to Auto. A CEO "stop" holds until
he himself says continue in that conversation, and no message from another session lifts it. To
"remove and create" the orchestrator or a team means rewriting its definition (its rules and
role files) and keeping the same conversation. It never means retiring the session and binding a
new one, unless he explicitly asks for a fresh session, as he did the same day (TH-074). Rule
text: `agent/ORCHESTRATOR.md` §5b.

**Why.** On 2026-11-10 and 2026-11-11 the orchestrator's session was switched to plan mode from
the app by accident. It answered every wake with a plan and a dialog. A session keeps its mode
on every flagless resume, and a resume that passes `--permission-mode` starts a copy, so the mode
cannot be reset from a script. On 2026-11-10 the old orchestrator and Memphis conversations were
retired and replaced, which was not what he asked for.

## TH-074 — The orchestrator is the business brain; Memphis is the Operations team
**Date:** 2026-11-11 · **By:** CEO · **Status:** ACTIVE

**Rule.**
- **The orchestrator** is the one conversation the CEO talks to for work and business; Thebes
  System is opened only to repair Thebes. It runs on Opus (`watchdog.py ORCHESTRATOR_MODEL`).
- **It runs the business team as subagents, and nothing else:** `pm`, `po`/`po-2`, `cpo` and
  `analyst` (`teams.py ORCHESTRATOR_ONLY_ROLES`). A team reserving one is refused with
  `orchestrator-only-seat`; the orchestrator reserving any other seat is refused with
  `orchestrator-business-only`.
- **When the CEO opens a topic**, it discusses in plain text, proposes and pushes back. It writes
  the plan as a file in `Dabbler/dabbler-docs/`, and it waits for his approval in the
  conversation. On its own wakes it never plans and never opens a dialog (TH-072, TH-073).
- **Memphis is the Operations team**, with the same name and lane. It runs `cto`, `cxo` and
  `devops`. It keeps migrations, CI, integration into `staging` and deploys.
- **`qa` moves to Edfu.**

The orchestrator and Memphis each got a fresh session on his order. The old conversations are
retired and kept: f6071922 for the orchestrator, 5984b1cc for Memphis.

Rule text: `agent/ORCHESTRATOR.md` §2a and §4, and `conversation_dispatch.py` (the envelope
lanes).

**Why.** The orchestrator only split tasks and relayed, and it could not discuss or plan a
direction with him. Memphis carried six seats: business and technical rulings, QA and
operations. The CEO wants one smart business conversation and one technical operations team.

## TH-075 — Integration per patch, not per ticket
**Date:** 2026-11-11 · **By:** CEO ("Ok agree, implement") · **Status:** ACTIVE (amends the
integration timing of D-052; Done is unchanged)

**Rule.**
- **A team keeps its verified work on its own branch** (`staging-<team>`). Nothing is merged
  into `staging` ticket by ticket.
- **A patch is due** when every ticket of an Epic that has waiting work is verified or Done,
  or when the oldest waiting work has waited 24 hours (`integrate.PATCH_CEILING_SECONDS`),
  whichever comes first. Work with no Epic goes at the ceiling. When Jira cannot be read,
  only the ceiling opens a patch. The patch then carries every team's verified work for that
  base in one Memphis dispatch, and the brief says why it is due (`Why now:`).
- **Early integration** stays possible. When something cannot wait (a migration another
  ticket needs, a fix the CEO is waiting to see), the orchestrator sends Memphis a hand-written
  `INTEGRATE:` dispatch that gives the reason.
- **A branch that breaks is dropped, and the rest still goes.** On a conflict or a check that
  fails only on the merged result, Memphis finds the branch behind it, merges the others again
  and pushes them through TH-071. The report names each dropped branch with its failing tests
  or conflicting files, and the orchestrator sends it back to its team.
- **"Verified" is a Jira label, not a status.** A passed ticket that waits for the patch keeps
  its review column and gets the label `verified` (`review_queue.VERIFIED_LABEL`). The label
  comes off at Done, and `returned` replaces it if the ticket is sent back. KAN is a
  team-managed project whose transitions are global and hard-coded in `board.py`; a new status
  would touch every transition. The CEO may still add a Verified column in the Jira UI.
- **Done is unchanged** (D-052): the commit is on `staging` and staging.dabbler.pro serves it.
  A passed ticket counts as late only after 30 hours (`review_queue.INTEGRATE_LATE_SECONDS`,
  the ceiling plus the merge).
- **A chain stays with one team.** A ticket stacked on a blocker's verified commit (D-049) goes
  first to the blocker's team when that team is free (`ready_dispatcher.stack_teams`), and
  `epic-cut` keeps a chain of dependent tickets inside one patch on one team.

Rule text: `integrate.py` (`patch_due`, `brief`), `review_queue.py`, `ready_dispatcher.py`,
`agent/ORCHESTRATOR.md` (integration), `agent/WORKFLOWS.md` (Which path is live) and the
`epic-cut` skill.

**Why.** Every verified ticket opened its own Memphis integration, so `staging` moved many
times a day and Memphis spent its time merging single tickets. The CEO wants each team to work
and test on its own branch, with the merge after a patch.

## TH-076 — The orchestrator's inbox arrives as a message; no waiter, no wake-ups
**Date:** 2026-11-11 · **By:** CEO ("لا مش عايز wake-up خالص … خليها تيجي ويرد عليها من غير ما
يعمل wake-up لوحده … ولا يبعتلي") · **Status:** ACTIVE

**Rule.**
- The orchestrator runs **no** inbox waiter and no background command that wakes it.
- The zero-token loop `agent.execution.inbox_push` watches its inbox. When items wait, it has
  a one-shot courier deliver one fixed line into the live conversation with SendMessage. The
  courier is `claude -p` on Haiku, with no MCP and no saved session, in the orchestrator's own
  permission mode. Nothing is stopped or resumed.
- The line carries no item and no capability. The orchestrator runs `inbox take`, handles
  the items, and writes nothing to the CEO unless `ceo_notice` prints SEND (TH-072).
- Batching is the waiter's (90 s quiet, 5 min at most). A set already announced is announced
  again only if it is still untaken an hour later.
- While the pusher runs, `inbox wait` refuses (`pushed`).

Rule text: `inbox_push.py`, `inbox.py` (`take`, `push_running`), `agent/ORCHESTRATOR.md` §1,
`agent/scripts/thebes-up.sh`.

**Why.** Every return of the waiter was a wake: idle every two hours, a restart on each Thebes
commit, and each batch cost a read of the output file and a restart call on top of the work.
The CEO wants items to reach the orchestrator the way his own messages do.

## TH-077 — Thebes splits nothing that is already split
**Date:** 2026-11-11 · **By:** CEO ("Remove cut-of"; "تقسيم التاسكات لتاسكات اصغر لان هو بيقسم
المتقسم اصلا"; earlier the same day "Don't cut anymore") · **Status:** ACTIVE · **Supersedes:**
D-049 item 4 and the D-049 size rules

**Rule.**
- An existing ticket is never split into smaller tickets. It goes to a team as written.
- An Epic that already has tickets is never re-cut.
- No Ready target. The Ready dispatcher raises no `ready-below-target`, `serial-chain` or
  `too-big`; a short Ready, a Blocks chain or a large estimate wakes nobody.
- `cut_plan check` has no size cap and no one-screen rule. It still catches two parallel
  tickets on the same files, a Blocks link with no reason, and a screen or function without a
  test.
- An Epic the CEO approves that has no tickets yet gets them once, at the level the Epic itself
  names (`epic-cut`). Nothing finer.
- A Blocks link that is only an order may still be removed. That changes no ticket.

Rule text: `ready_dispatcher.py`, `inbox.py` (the priority item's `how`), `cut_plan.py`,
`agent/roles/pm.md`, `agent/skills/epic-cut/SKILL.md`.

**Why.** The D-049 gauges asked the PM to cut every 15 minutes while Ready was under 10, and to
split any ticket over an hour. The tickets on the board were already cut, so the PM kept
splitting finished cuts, and each ask was an orchestrator turn.

## Session-memory orders that are no longer live

| Memory file | Dated | What it said | Replaced by |
|---|---|---|---|
| `ceo-decide-dont-wait` | 2026-10-03 | The orchestrator decides without waiting, inside hard stops | D-035, then D-043 |
| `ceo-delegates-decisions` | 2026-10-14 | Routing choices to the CEO is the riskier path | D-035, then D-043 |
| `messaging-no-po-tickets` | 2026-10-15 | During the Messaging launch the PO creates no tickets | D-046 and TH-061 |
| `ceo-approves-in-chat` | 2026-10-22 | The CEO replies "موافق <ticket>" in chat | D-043 |
| `ceo-standing-approvals` | 2026-10-22 | A list of standing approvals | D-043 (`autonomy.json`) |
| `pm-runs-board-po-in-teams`, PO part | 2026-10-21 | The PO runs inside the teams | TH-055 (2026-11-10) |
| `need-input-eligibility`, column part | 2026-10-21 | A Need Input column and its Jira statuses | TH-062 |
| `ceo-tests-localhost-first`, CEO part | 2026-10-23 | The CEO tests the localhost URL and says "موافق" | TH-057 and TH-065 |
| `autonomy-constitution`, one line | 2026-10-27 | Done means the commit is on Alpha | D-052 |
| `code-dod-review-pass-done` | 2026-11-04 | A review PASS is Done; integration is a separate ticket | D-052 |
| `batch-alpha-merges` | 2026-11-04 | Alpha merges are batched to the end of the day | D-052 |
| `memphis-rescue-ack-only` | 2026-11-05 | Three named rescue tickets get a single "ack" | Expired with those tickets |
| `thebes-three-islands-vision` | 2026-10-01 | A target shape of three groups | History; see D-031 to D-039 |

These session-memory files repeat an entry that already exists above and add nothing:
`one-orchestrator-conversation` (D-048), `liveness-every-team` (D-045),
`d049-parallel-throughput` (D-049), `orchestrator-facts-and-orders` (D-044, D-046),
`autonomy-constitution` (D-043).

Two product rules were moved to `Dabbler/dabbler-docs/DECISIONS.md`: the location permission
rule (P-045) and offline mode (P-046).

---

# Conversion table: Thebes `D-` numbers and their `TH-` names

`D-` is also the prefix of the experience decisions in `Dabbler/dabbler-docs/DECISIONS.md`.
To name a Thebes decision without that doubt, write `TH-` with the same number. The headings
above keep `D-`, because code, tests and older entries cite them that way; both spellings
name the same entry. New entries are `TH-053` onward.

| Written as | Same as | Title |
|---|---|---|
| `D-001` | `TH-001` | Repository memory is canonical |
| `D-002` | `TH-002` | Reject autonomous swarm management as the default |
| `D-003` | `TH-003` | No autonomous first or next Product ticket |
| `D-004` | `TH-004` | Role is not Seat |
| `D-005` | `TH-005` | Direct routing, no relay |
| `D-006` | `TH-006` | SELF / QA / PEER are derived routes |
| `D-007` | `TH-007` | PEER failure transfers remediation to the reviewer |
| `D-008` | `TH-008` | Implementation complete is not Product authorization |
| `D-009` | `TH-009` | Reported observation begins investigation |
| `D-010` | `TH-010` | Reported environment is authoritative |
| `D-011` | `TH-011` | Browser under test is not browser automation |
| `D-012` | `TH-012` | Validation follows causal and changed surfaces |
| `D-013` | `TH-013` | Dependencies are enforced state, not prose |
| `D-014` | `TH-014` | Providers sit behind Thebes |
| `D-016` | `TH-016` | Claude is the Product-code primary provider |
| `D-015` | `TH-015` | Retrieval is deferred until measured need |
| `D-017` | `TH-017` | The Listener is a communication boundary, never a second Controller |
| `D-018` | `TH-018` | Listener records are communication evidence, not a source of truth |
| `D-019` | `TH-019` | Durable intake and idempotent dispatch, not exactly-once |
| `D-020` | `TH-020` | The Listener is the operational front door; the Controller is internal |
| `D-021` | `TH-021` | The front-door gate is a misuse guard, not authentication |
| `D-022` | `TH-022` | The intent lifecycle is derived from canonical truth, never stored beside it |
| `D-023` | `TH-023` | An unobserved outcome is reported with evidence, never guessed |
| `D-024` | `TH-024` | The Product executor has a standing tool set; production mutation is never in it |
| `D-025` | `TH-025` | Thebes pins the executor toolchain per process, never machine-wide |
| `D-026` | `TH-026` | The infrastructure programme is closed; Thebes changes are evidence-driven |
| `D-027` | `TH-027` | Deterministic tests run before the reviewer; retest is bounded; a red run has four meanings |
| `D-028` | `TH-028` | Seats are human-like employees; Roles own accountability, not model ability |
| `D-029` | `TH-029` | The four employee capabilities operate on Role Work, not code by default |
| `D-030` | `TH-030` | The infrastructure freeze of D-026 is lifted for one evidence-backed milestone |
| `D-031` | `TH-031` | Jev is a decision gate, never a seat; a provider never replaces a Role |
| `D-032` | `TH-032` | Teams are execution islands; seats are a shared pool, exclusive in time |
| `D-033` | `TH-033` | Routine actions Jev may approve alone; actions that are always the CEO's |
| `D-034` | `TH-034` | The orchestrator is one Claude session, called only when a side chooses to ask |
| `D-035` | `TH-035` | Every decision is delegated to the orchestrator; four hard stops remain the CEO's |
| `D-036` | `TH-036` | Any Codex conversation on this machine is a Listener; reply mode is probed, not chosen |
| `D-037` | `TH-037` | Three kinds of session only; CEO orders are executed; more than one PO |
| `D-038` | `TH-038` | One Codex conversation, three Claude sessions |
| `D-039` | `TH-039` | Claude-only Thebes: the orchestrator is the CEO's front door |
| `D-040` | `TH-040` | Jira follows a team dispatch; the PO records Ready facts by command |
| `D-041` | `TH-041` | Review verifies the claim; it never redoes the work |
| `D-043` | `TH-043` | Autonomy constitution: only money, `main` and outside reach the CEO |
| `D-044` | `TH-044` | The orchestrator speaks from state and acts only on the CEO's own words |
| `D-045` | `TH-045` | Liveness: every team is probed every 5 minutes, busy or not |
| `D-046` | `TH-046` | The order rule stops invented work, never needed work (refines D-044) |
| `D-047` | `TH-047` | Liveness sees tickets with no team, not only idle sessions (extends D-045) |
| `D-048` | `TH-048` | One orchestrator conversation, never rotated (supersedes D-044's rotation) |
| `D-049` | `TH-049` | A ticket every 10 minutes: work runs in parallel, review only where an eye is needed |
| `D-050` | `TH-050` | One live session per team; same-named leftovers are retired |
| `D-051` | `TH-051` | The CEO hears a thing once: a gate on every orchestrator message |
| `D-052` | `TH-052` | staging integrates and tests; Alpha is the customer trial |

`D-042` has no entry in this file: it was written as a draft (the Ready dispatcher, domain
teams, one `ux-engineer` for each code team, the PM running the board's priorities) and was
never promoted. The parts that were built are cited as `D-042` across this repository; the
draft text is `agent/archive/2026-11-10/D-042-desk-dispatcher-operations.md`.
