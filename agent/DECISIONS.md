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

**Status:** ACTIVE (2026-10-01, CEO: option (أ) — "أقلل الرجوع ليا بأكبر شكل ممكن")
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
