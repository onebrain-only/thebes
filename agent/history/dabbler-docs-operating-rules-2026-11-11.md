# Operating rules that lived in dabbler-docs

Copied here on 2026-11-11 by `TH-070`. `Dabbler/dabbler-docs/` holds Product knowledge; how
Thebes runs is owned by `agent/`. These texts described how Thebes ran when they were
written. **They are history and authority for nothing.** The live home of each rule is in
the table under `TH-070` in `agent/DECISIONS.md`.

The decision IDs stay defined in `Dabbler/dabbler-docs/DECISIONS.md`, where each entry now
carries a note that points here. Text is copied without edits; home paths and seat names in
it are as they were written.

Contents:

1. `CONTRACT.md` section 3, the four execution sub-sections (claim, ACCELERATE, Agent View,
   one work item = one capability)
2. `MIGRATION.md`, the 2026-09-02 repository split
3. Governance decisions `G-013`, `G-018`, `G-022`, `G-029`
4. Technical decisions `T-088` to `T-096`

---

## 1. CONTRACT.md section 3: execution ownership

### Execution ownership, claim, and the Orchestrator's bounded authority

**Added 2026-09-08 (Wave 6).**

**Persistent State owns execution ownership; Jira owns lifecycle.** The Jira `assignee` is not
execution authority and never was — it is unused on this board. Ownership lives on the task
record as `ownership`: **exactly one current owner or null**, taken under a file lock with a
revision compare-and-swap. There is no force claim, no last-write-wins and **no silent
reassignment**; release sets ownership to null and never hands the slot to anyone.

**Ordinary work is claimed, not assigned.** `po` selects into `Ready`; the item enters the queue
for its single `required_capability`; a seat of that capability claims it; only then is that
seat woken. **No lead, no CEO naming, no executive sign-off.** Where executor evidence conflicts,
the item **blocks and requires reconciliation** — it does not fall back to anyone choosing.

**Contention is decided by declared file surfaces**, not by a coordinator and not by a boolean:
a claim is refused when the paths actually collide with work already owned. The four contended
files and the shared prefixes in §4 are unchanged and remain authoritative.

**Surface scope must be ASSESSED before work is claimable.** A work item's `surfaces` is the set
of repository-relative paths it touches, and **`null` means nobody has assessed it — never "no
collision".** `[]` is a real answer: assessed, nothing declared. Unassessed work is **not
claimable**. Assessment is a pre-execution factual act a same-capability seat performs at
Preflight, like Work Effort sizing; **assessing is not claiming**, and the assessing seat does
not thereby become the executor. **`po` must not invent implementation paths to make work
claimable.** Legacy Ready work that lacks an assessment stays in `Ready` and simply waits.

**The Orchestrator may create bounded safety interventions — STOP (a task), HOLD (a capability),
FREEZE (the system) — and clear them (RESUME).** Only for a concrete detected safety condition,
always with a `reason_ref`. **Never for priority, ordinary scheduling, routine approval or
performance management.** They are Persistent State records, **never Jira statuses or columns**.
The CEO may create or clear any. **The Orchestrator never owns ordinary Product work, never
writes Product code, never chooses a `validation_route` and never chooses a PEER reviewer.**

**An active STOP blocks CONTINUATION, not merely a future claim.** Before every execution wake —
the first one after a claim, a same-seat continuation, and a resumed invocation — the Orchestrator
**must** pass the continuation gate. **A STOP that only prevented a new claim would do nothing at
all for an already-owned task**, which is the case it exists for. While a STOP is active:
ownership is preserved and never reassigned, no new claim or reclaim succeeds, **the Orchestrator
must not wake the owner to continue**, and the owner is directed to release or await RESUME.
**Release stays permitted under STOP** — a STOP must not trap ownership. Jira status does not
change merely because a STOP exists. **HOLD and FREEZE block new claims only; current owners
continue**, and neither is equivalent to STOP.

**`ux-engineer` is an active shared capability** as of 2026-09-08 — one seat, executing in
`Design` (10047). It owns design-to-code fidelity and the application of the design system in
UI implementation. **It does not own business logic, application state, backend integration or
navigation architecture** — those remain `frontend` and `backend`. `product-designer` remains
defined with no seat: the CEO supplies design.

### ACCELERATE is an execution policy, not an intervention

**Added 2026-09-09.**

**STOP, HOLD and FREEZE remain safety-only.** This section exists because the rule above — that an
intervention is created *only* for a concrete detected safety condition and **never for priority,
ordinary scheduling, routine approval or performance management** — must not be read as forbidding
a scheduling control. It forbids expressing one *as an intervention*.

**ACCELERATE is that scheduling control, and it is a separate thing.** It is a Persistent State
`policy` record with its own kind, directory and reader, scoped to the **system**, one **product**
or one **capability**. It changes **only how aggressively the Orchestrator fills safe capacity**.
It never weakens authority, validation, ownership, dependency, contention, interventions or any
safety gate, and removing every policy record leaves behaviour identical.

**Interventions outrank ACCELERATE, always.** FREEZE blocks new accelerated claims system-wide,
HOLD blocks them for its capability, STOP blocks its task's claim and continuation. ACCELERATE
may never clear, weaken or mutate one, and a large backlog is never a reason to relax a rule:
a PEER route with no authorised reviewer **still waits**, and work is still allowed to wait.

**Scopes union; absence means normal.** There is no negative policy, no "NORMAL" record and **no
TASK scope** — a task-scoped accelerator would be priority under another name, which is the thing
this section's first paragraph forbids. `CLEAR ACCELERATE` is the only inverse, and **clearing
never cancels ownership**: current owners continue.

**The CEO activates and clears ACCELERATE by scope**, and does not specify seats, agent counts,
parallelism numbers, reviewers or execution order — the Orchestrator derives safe capacity. Every
accelerated claim is still an atomic claim that re-checks every predicate under the lock, still
followed by the continuation gate before any wake. **The Orchestrator coordinates and never
becomes a Product executor.**

### Agent View is observability and holds no execution authority

**Wave 7, 2026-09-09.** Agent View — `agent/scripts/flow.py` and its derivation seam
`agent/state/view.py` — **reads every authoritative source and mutates none of them.** It may
consume Persistent State, bindings, Roles, topology, derived queues, capacity, historical status
and session telemetry. It has **no** authority over routing, claim, ownership, release, Jira
lifecycle, validation route, review owner, dependency satisfaction, interventions, dynamic seat
creation or capacity decisions, and it exposes no control that mutates any of them.

**It is not a second state machine, not a second Jira cache, and not a source of agent
availability.** Where a rendered value and Persistent State disagree, **Persistent State is
correct.** Two consequences follow and are binding: a seat that owns nothing is **UNOWNED, never
"available"** — current-session dispatchability is not observable and is reported UNKNOWN rather
than inferred; and **historical evidence is never rendered as current execution** —
`executor_evidence` and `agent/status/` record what happened, not what is happening.

### One executable work item = one required capability

**Settled 2026-09-08.** An executable work item carries **exactly one** `required_capability`,
and that capability decides four things at once: its Development column, its valid PEER
reviewer, who holds execution authority, and its future capability queue. Work that genuinely
needs two capabilities is **split into two executable children under a non-executable parent**,
each with its own capability-scoped acceptance criteria, Work Effort, lifecycle and validation —
not run as one item that would have to occupy two columns.

**Do not copy a mixed parent's acceptance criteria into both children.** `po` writes only the
capability-relevant criteria for each.

---

## 2. MIGRATION.md

### Migration record — dabbler repo split into One Brain (2026-09-02)

#### Why this file exists

On 2026-09-02 the `dabbler` repo at the old path `~/Desktop/dabbler` was split in
two. If a session, an agent, a script, or a stale absolute path reference expects
something at its pre-migration location and can't find it, the mapping below says
where it actually is now. Read this before assuming something was lost.

#### Path mapping

| Old path (pre-migration) | New path |
|---|---|
| `~/Desktop/dabbler` (repo root) | `~/Desktop/One Brain/dabbler` (same repo, same `.git`, same remote — only the parent directory changed) |
| `~/Desktop/dabbler/.claude/` | `~/Desktop/One Brain/.claude/` |
| `~/Desktop/dabbler/.agents/` | `~/Desktop/One Brain/.agents/` |
| `~/Desktop/dabbler/.claude-flow/` | `~/Desktop/One Brain/.claude-flow/` |
| `~/Desktop/dabbler/.kilo/` | `~/Desktop/One Brain/.kilo/` |
| `~/Desktop/dabbler/.opencode/` | `~/Desktop/One Brain/.opencode/` |
| `~/Desktop/dabbler/.mcp.json` | `~/Desktop/One Brain/.mcp.json` |
| `~/Desktop/dabbler/CLAUDE.md` | `~/Desktop/One Brain/CLAUDE.md` |
| `~/Desktop/dabbler/docs/DECISIONS.md` | `~/Desktop/One Brain/docs/DECISIONS.md` |
| `~/Desktop/dabbler/docs/PROJECT_STATE.md` | `~/Desktop/One Brain/docs/PROJECT_STATE.md` |
| `~/Desktop/dabbler/docs/LEARN.md` | `~/Desktop/One Brain/docs/LEARN.md` |
| `~/Desktop/dabbler/docs/CONTRACT.md` | `~/Desktop/One Brain/docs/CONTRACT.md` |
| `~/Desktop/dabbler/docs/AGENTS.md` | `~/Desktop/One Brain/docs/AGENTS.md` |
| `~/Desktop/dabbler/docs/BRIEF.md` | `~/Desktop/One Brain/docs/BRIEF.md` |
| `~/Desktop/dabbler/docs/MANIFESTO.md` | `~/Desktop/One Brain/docs/MANIFESTO.md` |
| `~/Desktop/dabbler/docs/ROADMAP.md` | `~/Desktop/One Brain/docs/ROADMAP.md` |
| `~/Desktop/dabbler/docs/WORKFLOWS.md` | `~/Desktop/One Brain/docs/WORKFLOWS.md` |
| `~/Desktop/dabbler/docs/STATUS.md` | `~/Desktop/One Brain/docs/STATUS.md` |
| `~/Desktop/dabbler/docs/status/*` | `~/Desktop/One Brain/docs/status/*` |
| `~/Desktop/dabbler/docs/briefs/*` | `~/Desktop/One Brain/docs/briefs/*` |

#### What did NOT move — still inside `One Brain/dabbler/`

Everything else: `lib/`, `android/`, `ios/`, `macos/`, `web/`, `assets/`, `test/`,
`integration_test/`, `supabase/`, `scripts/`, `.github/`, `.maestro/`,
`pubspec.yaml`/`.lock`, `analysis_options.yaml`, `.env`/`.env.example`,
`firebase.json`, `l10n.yaml`, `devtools_options.yaml`, `package.json`, `run.sh`,
`build_ios.sh`, and the technical docs that describe the app itself:
`docs/ARCHITECTURE.md`, `docs/SCHEMA.md`, `docs/CONVENTIONS.md`, `docs/README.md`,
`docs/LOCATION.md`, `docs/NOTIFICATIONS.md`, `docs/APPLE_REVIEW_SIGNIN.md`,
`docs/PLAN.md`, `docs/RESEARCH.md`, `docs/flutter_localization_checklist.md`,
`docs/screen-report.md`.

#### Why named agents (cto, backend-owner, etc.) stopped resolving

Their registry is scoped to the session's working directory at launch. The session
that did this migration launched from the old `~/Desktop/dabbler` path, which no
longer exists (it's now `One Brain/dabbler`) — so its agent registry broke mid-move,
as expected. **A session launched from `~/Desktop/One Brain` (the new root, not the
`dabbler` subfolder) should resolve the full agent roster again**, since
`.claude/agents/` now lives at that root.

#### Git state at time of migration

- `dabbler` repo: cleanup committed locally (`8f19922`, `7420408`), **not pushed**.
  Remote (`dabblersport/webapp`) still shows the old, unsplit history — nothing
  public has changed yet.
- `One Brain` repo: brand-new local repo (`abf851d`), no remote. The moved
  governance docs' history before 2026-09-02 lives only in the `dabbler` repo's
  history up to commit `a81da87` — `git log` on a file now under `One Brain/docs/`
  won't show anything before this migration unless you look in the old `dabbler`
  history for the same filename.
- The `.mcp.json` moved to `One Brain/` contains a live GitHub PAT — flagged to the
  PO for rotation, not yet acted on.

#### Known harmless artifact

Right after the move, this session's own background hooks (claude-flow
intelligence, configured before the move) briefly recreated an empty
`~/Desktop/dabbler/.claude-flow/data/pending-insights.jsonl` at the *old* path —
a stale in-memory reference in this one session, not a sign anything else was
left behind. Its 3 lines were copied into `One Brain/.claude-flow/data/`. The
leftover empty directory at the old path is harmless and can be deleted manually
whenever convenient; a fresh session started at the new `One Brain` path won't
recreate it.

#### If something still seems missing

Check this table first. If a file genuinely isn't at its mapped new location, it
likely means it was created *after* this migration in a session still pointed at
the old `dabbler` path (before the registry break was noticed) — check
`~/Desktop/dabbler` (the old, now-orphaned path) directly before assuming data loss.

#### Second rename — 2026-09-02 (same day, later)

Per the PO's confirmed target layout:

```
Desktop/One Brain/
  CLAUDE.md
  .claude/agents/ ...
  Dabbler/dabbler-code/     (was: dabbler/)
  Dabbler/dabbler-docs/     (was: docs/)
```

| Old (from the first split, same day) | New |
|---|---|
| `One Brain/dabbler/` | `One Brain/Dabbler/dabbler-code/` |
| `One Brain/docs/` | `One Brain/Dabbler/dabbler-docs/` |

Nothing else moved. This was a plain rename (`mv`) on both — `dabbler-code`'s `.git`,
remote, and history are untouched, exactly as the first move preserved them.

Updated as part of this rename:
- `One Brain/.gitignore` — now ignores `Dabbler/dabbler-code/` (was `dabbler/`).
- `Dabbler/dabbler-code/docs/README.md` — pointer updated to `../Dabbler/dabbler-docs/`.
- All `.claude/agents/*.md` files and `CLAUDE.md` — every bare `docs/X.md` reference
  disambiguated to either `Dabbler/dabbler-docs/X.md` (governance: DECISIONS, PROJECT_STATE,
  LEARN, CONTRACT, AGENTS, BRIEF, MANIFESTO, ROADMAP, WORKFLOWS, STATUS, status/,
  briefs/) or `Dabbler/dabbler-code/docs/X.md` (technical: ARCHITECTURE, SCHEMA, CONVENTIONS,
  PLAN, README). This also fixed a pre-existing ambiguity from the first split, where
  agent definitions referenced bare `docs/X.md` without saying which of the two
  `docs/` folders they meant.

Not yet swept: the governance docs' own bodies (`DECISIONS.md`, `CONTRACT.md`, etc.)
may still contain bare `docs/` self-references from before either split — not fixed
in this pass, flagged if it comes up.

---

## 3. Governance decisions

### From dabbler-docs: G-013 — The company restructure: One Brain is the company, four levels, 17 seats, no orchestrator
**Date:** 2026-09-05
**Source:** CEO-direct, in session, over an extended design conversation. Transcribed at the
point of decision by the Listener under `CONTRACT.md` §9.3, which names the Listener as
`G-nnn`'s second appender for CEO-direct structural decisions specifically.

**Decision.** The agent system is restructured from a single product team into a company.

**One Brain is the company, the workspace and the holding layer** — no `Dabbler/` directory and
no extra nesting. **Dabbler is a product** with four projects: the **app** (staffed), the
**design system**, the **admin dashboard** and the **website** (declared, unstaffed). **Seats
are shared across projects and must be told which project they are working in.**

**Four levels replace two:**

| Level | Seats |
|---|---|
| 0 | CEO · **Listener** (the main session, not an agent) |
| 1 — Company | `cto` · `cpo` · `cxo` · `analyst` — four peers |
| 2 — Product | `pm` · `devops` · `content-manager` |
| 3 — Project | `po` · `team-lead-1..5` · `qa` |
| Developers | `senior-backend` · `senior-frontend` · `junior-frontend` |

**The distribution layer is a behaviour, not a seat.** The Listener writes directly to whichever
seat owns the question — a senior developer included — and never down a chain of managers. **The
`orchestrator` seat is deleted**; a seat whose only job is routing is a relay, and the relay is
the cost this design removes. Routing is carried by the new `route-to-seat` skill, which
inherited the deleted seat's prompt contract and verification rules intact.

**Seat changes.** Renamed: `master-analyst`→`analyst`, `version-control`→`devops` (**and promoted
to product level** — it now owns every project's repo, not one), `qa-tester`→`qa`,
`backend-owner`→`senior-backend`, `flutter-feature-agent`→`senior-frontend`. Merged:
`task-auditor`→`po`, `app-store-submission-fixer`→`devops`. Split by evidence:
`notifications-specialist` across the two seniors. New: `cxo`, `pm`, `content-manager`, `po`,
`team-lead-1..5`, `junior-frontend`. **Nothing was deleted without its knowledge being placed
where a live seat reads it**; three retired status logs are at `agent/status/archive/`.

**`cxo` is the Chief Experience Officer** — design system standards, look and feel, whether a
feature serves the company's goals. It judges and never edits what it judges. It takes a new
`D-nnn` prefix in this file and **never starts a parallel decision store.**

**`cpo` becomes the sole writer to the Notion business corpus**, reversing the explicit
prohibition in its own role file. Notion holds the core business documents; `dabbler-docs/`
holds the business-**technical** documents. Two stores, one writer each, neither a copy.

**`po` absorbs the review gate**, creating a closed loop: it writes the acceptance criteria and
judges work against them. **This trade was made deliberately by the CEO to cut back-and-forth.**
It is held by two rules — the `po` never reviews work it executed, and where a criterion proves
badly written the verdict says so rather than failing the developer for the PO's wording.
**Watch it:** if rework starts being blamed on developers for the PO's own criteria, the loop has
failed and the gate needs an independent seat again.

**Model and effort** are reset by the CEO in `AGENTS.md` §9b. Two overrides are deliberate and
recorded there rather than inherited: `senior-backend` runs **Sonnet/high** — the seat where a
mistake is least recoverable, on the cheaper model — and `junior-frontend` runs **Opus/low**.

**What this decision does NOT do.**

**It does not resolve `G-012`, and it must not be read as having done so.** `G-012` (`cto`,
2026-09-04, still **PROPOSED**) proposes seven ownership stacks S1–S7 from measured file-import
coupling and **explicitly rejects the D1–D11 census clustering** this decision assigns to team
leads. That rejection is on the record with measurements behind it.

**Why the two are not necessarily in conflict.** `G-012` measured collisions between *writers*.
Under this structure **team leaders write no code at all** — they plan and assign, and every file
is written by one of three developers whose paths are governed by `CONTRACT.md` §3 and serialised
by §4 and §7. A feature taxonomy used to decide *what to work on* is not a write boundary. It
would be dangerous as one; here it is not one.

**What survives from `G-012` and still needs a CEO ruling**, unchanged by this decision:

- `lib/app/app_router.dart` — **1,712 LOC, 85 `GoRoute`**, a contended file, one writer at a time.
- `lib/features/profile/presentation/providers/profile_providers.dart` — **870 lines holding
  three domains' concerns**, consumed by `social` (10 providers) and `home` (5).

Until those two are split, **three developers will serialise on them however stacks are grouped.**
That is `G-012`'s Phase 0 / Phase 1 gate and it is a measurement, not a preference.

**Two stacks are active — D2 and D6 — because three developers cannot feed five leads.** Capacity
sets that number. Activating a stack is a `pm` decision with the CEO.

**B.9 Organiser dashboard (40 features) is assigned to no app lead.** It has no app slice because
it is not an app feature — it belongs to the **admin dashboard project**, which is declared and
unstaffed. `G-012` reached a different conclusion (organiser is a persona, ~30 of 40 are
game/venue operations, so it proposed S3). **Both readings are recorded; neither is ruled.**

**The append-only history was deliberately not rewritten.** `DECISIONS.md`, `LEARN.md`,
`STATUS.md` and the archived status logs still use retired seat names. Rewriting a log to match a
later reorganisation falsifies it. **The rename map is in `AGENTS.md` §2.**

**Consequence.** `CLAUDE.md`'s Listener section, `agent/AGENTS.md` (v0.7), `agent/WORKFLOWS.md`
(§1, §2, §3, §4, W1, W5, §7) and `CONTRACT.md` §3 are rewritten. `CONTRACT.md` §3 is restructured
from column-per-agent to **writer-per-path** — 17 columns of `R` hid the one cell that carried
meaning, and had already produced two documented column-artefact errors.

**Status:** ACTIVE

---

### From dabbler-docs: G-018 — The board is six columns inside three states; `In Development` is dropped, and nothing is pushed off One Brain
**Date:** 2026-09-05
**Source:** `analyst`, recording the CEO's own model of the board after he built it, plus a
standing push constraint he stated in the same session. **Two rulings, both his; this entry
records them and corrects the documents that contradicted the first.**

---

**Ruling 1 — the board is six columns, organised by Jira's three states.**

The restructure spec called for seven columns. The CEO built six, and his reasoning replaces
the spec's. His model: **Jira has three states, and columns live inside them.**

| State (Jira `statusCategory`) | Columns |
|---|---|
| **To Do** | `To Do` · `Ready` |
| **In Progress** | `In Progress` · `In Review` · `QA-Test` |
| **Done** | `Done` |

Verified against the live board this session — the six statuses map to exactly those three
categories, 2 / 3 / 1.

**`In Development` is dropped deliberately, not by oversight.** It and `In Progress` were both
to be moved by the team lead, and nobody ever defined what separated them. It would have been
a column no seat knew when to use. It is not coming back; `team-lead-N` owns one transition,
into `In Progress`.

**The live ids, read from the API this session** (`getTransitionsForJiraIssue`,
`includeUnavailableTransitions: true`):

| Status name (exact) | status id | transition id | Category |
|---|---|---|---|
| `To Do` | 10004 | `11` | To Do |
| `Ready` | 10008 | `2` | To Do |
| `In Progress` | 10005 | `21` | In Progress |
| `In Review` | 10006 | `31` | In Progress |
| `QA-Test` | 10009 | `3` | In Progress |
| `Done` | 10007 | `41` | Done |

**`Ready` is `2` and `QA-Test` is `3` — they break the 11/21/31/41 pattern**, and an id guessed
from the pattern is a failed call. The standing rule stands above the table: **call
`getTransitionsForJiraIssue` and read the ids back**; ids are project configuration and this
table will go stale (`WORKFLOWS.md` §2).

**The CEO's spoken labels are not board statuses.** He says *Backlog* for `To Do`,
*Development* for `In Progress`, *Testing* for `QA-Test`. Documents and API calls carry the
exact names above; the informal labels are noted once in `WORKFLOWS.md` §1 and `po.md` so a
reader is not confused when he uses them, and are never sent to the API.

**Why this entry exists at all: the documents named columns that do not exist.**
`WORKFLOWS.md`, `CONTRACT.md` §3 and `agent/roles/po.md` all carried the seven-column
lifecycle. A seat calling `transitionJiraIssue` with `In Development` or `In Testing` gets a
failure on the first real ticket. Corrected in the same session:

| File | What changed |
|---|---|
| `agent/WORKFLOWS.md` §1 | Lifecycle line, the three-state table, the `In Development` note, the spoken-labels note, and the "who moves it" mapping |
| `agent/WORKFLOWS.md` §2 | Columns row; the four-column transition paragraph replaced by the six-row id table |
| `agent/WORKFLOWS.md` §3, §5 | Review-gate outcome and W1 steps 2–4: pass → `QA-Test`, fail → `Ready` |
| `Dabbler/dabbler-docs/CONTRACT.md` §3 | "Release and the board" rows; one row added naming the six statuses |
| `agent/roles/po.md` | Board section rewritten with names, ids, the pattern warning and the read-the-ids-back rule |
| `agent/roles/qa.md` | States that QA's work arrives in `QA-Test` and that `qa` does not transition it |
| `agent/AGENTS.md` | `team-lead-1..5` owns one transition, not two |
| `.claude/bindings/team-lead-1..5.yml` | Same, in the seat descriptions; `.claude/agents/**` regenerated |
| `agent/skills/task-review/SKILL.md` | Id table completed to six; verdict targets corrected from Done/To Do to `QA-Test`/`Ready`, which is what `WORKFLOWS.md` §3 and `po.md` require |

The board itself was **not** reconfigured. It is correct as built; the documents were wrong.

---

**Ruling 2 — nothing is pushed to any remote except the One Brain repo, until the CEO lifts it.**

Stated by the CEO this session: work stays on One Brain *"until we trust the agency"*. This is
a **standing constraint on `devops`** and binds every seat that could reach a remote.

**No push to any remote other than One Brain** — not `dabblersport/webapp`, not
`Canary`, not `main`, not `dabbler-docs`, not `dabbler-admin`. Committing locally is fine and
expected; pushing is not. This sits above, not beside, the `Canary` flow and the `main` freeze
(`P-030`): while it is live, the Canary deploy path is not exercised at all.

**The `dabbler-admin` merge is committed locally at `2f8d349` and is deliberately not pushed.**
It is not an outstanding task, not a defect, and not something for a later session to "finish".
Anyone finding an unpushed local commit under this constraint leaves it alone.

Lifted only by the CEO, explicitly. Silence does not lift it.

**Status:** ACTIVE

---

### From dabbler-docs: G-022 — rule custody moves off `analyst`: the writer of a rule must not be a seat the rule binds
**Date:** 2026-09-06
**Source:** CEO, direct, in conversation. Transcribed by the Listener; the CEO holds the decision.
**Decision:** `MANIFESTO.md`, `CONTRACT.md` and `agent/AGENTS.md` are **the CEO's**. No agent writes
them; any seat may propose an amendment with its measurement and the CEO applies it.
`agent/WORKFLOWS.md` moves to **`po`**. `PROJECT_STATE.md` and the measured project-truth files stay
with `analyst`.

**Why.** `analyst`'s role file justified sole custody with a good principle — *"an agent must never be
able to edit the rule it is judged against"* — and then violated it, because those rules bind
`analyst` too. On 2026-09-05 it amended `CONTRACT.md` §4.1 twice, under `G-019` and `G-021`. Both
were correct fixes and both were a seat editing a rule that binds it. Sole custody did not satisfy
the principle; it **concentrated** the violation.

`WORKFLOWS.md` goes to `po` because `po` already owns the review gate and acceptance criteria, which
is the same substance stated in a different place.

**Measured consequence.** On 2026-09-05 `analyst` ran 181 tool calls, second highest of any seat, and
not one was project or market analysis — they were `G-021`'s line budget, W6, and a stale figure in
`CONTRACT.md:440`. Ownership was pulling a strategic seat into document surgery.

**Status:** ACTIVE.

---

### From dabbler-docs: G-029 — `po` owns Jira and holds final authority over the board

**Date:** 2026-09-07
**Source:** CEO, direct, live in conversation. Appended by the Listener under `§9.3`.

**Decision.** *"الـ PO يقدر يحرك أي task في Jira. PO is owning Jira."* — **`po` owns Jira. It holds
final authority over the board and may move any ticket, to any column, at any time.**

**The ordinary transitions remain the normal path.** The CEO confirmed this reading explicitly:
`pm`→`Backlog`, `po`→`Ready`, the owning lead→`Development`, the **developer**→`In Review`,
`po`→`QA-Test`, `qa`→`Done` still describe how a ticket moves in the usual case, and every seat
keeps making its own transition. `po`'s authority sits **above** that chain rather than replacing
it: it is an override, exercised when the chain has stalled or produced a wrong state, not a
requirement that `po` perform every move.

**Why it was needed, and it is not theoretical.** A board audit the same day found **three tickets
whose work had shipped while their tickets sat unmoved** — `KAN-119` in `Development` with no
assignee and its fix live on `Canary` (`5f32b06`), plus `KAN-139` (`90ea9f7`) and `KAN-142`
(`6c5bca4`) stranded in `In Review`. The mechanism: `In Review` is the developer's own transition,
and every downstream seat works by **pulling** — so a ticket the developer never moves is never
seen by anyone, and no seat had standing to move it. Under this ruling `po` does.

It also resolves a live deadlock: `qa` is paused by CEO order, which makes `QA-Test` a column
nothing can leave. `po` may now move what is stuck there rather than the board holding work
hostage to a paused seat.

**Boundary.** Authority over the board is not authority over the work. `po` moving a ticket does
not make the underlying change reviewed, tested or shipped, and `po` still records the evidence
for any move it makes — a column is a claim, and an unevidenced move is the drift this ruling
exists to correct, not a licence for it.

---

---

## 4. Technical decisions

### From dabbler-docs: T-088 — Absent executor evidence: the blocker as reported does not exist, six of seven items unblock with machinery already in the tree, and the CEO's authorised exception is spent on the real hole — a PEER reviewer that stops excluding the executor. The absence becomes a FACT on the record that only ever ADDS exclusions, never an argument at a call site and never an owner

**Date:** 2026-09-20 · **Seat:** `cto` (Khnum). **Rules the mechanism the CEO authorised on
2026-09-20 — *"open the review context with an explicit record that the executor evidence is
absent, and why"*, following the earlier ruling **لا تصحّح الماضي — لا تكرّره** (do not correct the
past; do not repeat it). Does not supersede anything. Constrains `agent/state/store.py`,
`agent/state/policy.py` and `agent/state/validate.py`, none of which this entry modifies.**

#### (a) The reported blocker is not the blocker. Measured, not assumed

The brief given to this seat stated: nine tickets in Jira `Peer-review`; `resolve_review_owner()`
resolves onto an open PEER context; `open_review_context()` refuses when `executor_evidence` is
empty. **All three are wrong.** Read through the store API, never a hand-rolled scan of the JSON:

```
python3 agent/state/validate.py --check        # 7 items, not 3 — the brief's count was stale
```

Every executable record whose `lifecycle.canonical` is `review` (`store.read`,
`store.evidenced_executors`, `validate.seats_by_capability`):

| id | Jira status | local `validation_route` | capability | evidence | `review_context` |
|---|---|---|---|---|---|
| KAN-175 | Self-review | peer | backend | `['backend-5']` | owner `backend-5` |
| KAN-285 | QA-Test | **qa** | frontend | `[]` | none |
| KAN-297 | Peer-review | self | content | `[]` | none |
| KAN-323 | Self-review | **self** | frontend | `[]` | none |
| KAN-329 | Peer-review | self | frontend | `[]` | none |
| KAN-330 | Peer-review | self | frontend | `[]` | none |
| KAN-331 | Peer-review | self | frontend | `[]` | none |
| KAN-333 | Peer-review | self | frontend | `[]` | none |

**Not one of the seven is on the `peer` route**, so `resolve_review_owner` — which refuses any
route but PEER (`store.py:1087`) — is not on the path for any of them. And
`open_review_context` does **not** refuse on empty evidence in general. It refuses only inside the
SELF branch (`store.py:789-801`), because `policy.resolve_owner_or_wait` returns an owner for
QA unconditionally and `None` for PEER as the *legitimate waiting state*
(`policy.py:231-246`). Simulated against the live seat registry:

```
resolve_owner_or_wait('qa',   'frontend', sbc, executor_seats=[]) -> ('qa', 'qa')
resolve_owner_or_wait('peer', 'frontend', sbc, executor_seats=[]) -> (None, 'peer')   # waiting, legal
resolve_owner_or_wait('self', 'frontend', sbc, executor_seats=[]) -> (None, 'self')   # the only refusal
```

#### (b) Decision 1 — six of the seven need NO new mechanism, and `po` tickets them as repair, not as exception

- **KAN-285 (route `qa`)** is not blocked at all. `open_review_context` succeeds today and writes
  owner `qa`. It has been sitting behind a refusal that does not apply to it.
- **KAN-297, 329, 330, 331, 333** sit in Jira `Peer-review` while local state says `self`. The
  validator already names the repair — *"Jira wins for the active review status; reconcile local
  state to it"* — and the operation already exists: **`store.reconcile_review_from_jira`**
  (`store.py:345`). It raises the route `self`→`peer`, which is a **strengthening**; the function
  refuses only to adopt a route *weaker* than characteristics require, so this is squarely inside
  what it was built for. Afterwards `open_review_context` writes a PEER context waiting at
  `review_owner: null`, and `resolve_review_owner` names the reviewer. **Zero code changes.**
- **KAN-297 will then wait indefinitely**, because `peer_eligible('content', …)` returns exactly
  one seat, `content-manager`. That is doctrine working, not a fault: *"a PEER route with no
  available peer waits in Peer-review rather than becoming QA or SELF"* (`policy.py:226-229`).
  **It is reported, never routed around, and never downgraded to get it moving.**

#### (c) Decision 2 — KAN-323, the one genuine SELF refusal, is routed UP, not let through

KAN-323 is the only item where `no-executor-evidence` is a real, correct refusal: on SELF the
evidenced executor *is* the owner, so absent evidence means there is no owner to have.

**The repair is to move the Jira issue to `Peer-review` and reconcile, exactly as in (b)** — a
different seat reviews work whose author cannot be established. Rejected: adding an evidence-absent
path into the SELF branch. SELF review means *the person who did it checks their own work*; with no
established author that sentence has no referent, and any mechanism that supplies one is
fabrication under a different name, which the CEO's first ruling forecloses.

#### (d) Decision 3 — the CEO's exception is spent on the REAL hole, which nobody had named

Absent executor evidence does not block a PEER review. **It silently weakens one**, and that is the
defect worth the CEO's authorisation. `policy.peer_eligible(cap, sbc, exclude=executors)`
(`policy.py:203-219`) exists so the seat that wrote the code cannot review it — because a PEER
FAIL transfers execution to the reviewer. With `executor_evidence: []` the exclusion set is
**empty**, so all eight frontend seats are eligible *including the one that actually built it*. The
five items in (b) would each pass through that gate. Verified:

```
peer_eligible('frontend', sbc, exclude=[]) -> all 8 frontend seats
```

So the mechanism is **not** a way past a refusal. It is a way to restore an exclusion the missing
evidence removed.

**`evidence_absence` is a FACT ON THE RECORD, written before the review opens.** Not a parameter on
`open_review_context` and not a separate open-anyway operation — the brief was right that an
argument at the call site is the abusable shape, and this seat agrees. Its required shape:

| field | meaning |
|---|---|
| `declared_by` | the authoring seat. Restricted to `po` and `ceo`, the same authority set as `RECOVERY_AUTHORITIES` (`store.py:822`) |
| `reason_ref` | why the evidence is absent. **No default, no inference.** For these items: dispatched as direct `Agent` invocations rather than claim → wake → release, so the code landed with no durable ownership record |
| `presumed_executors` | the seats believed to have done the work. **Explicitly NOT authoritative and never an owner** — it feeds exclusion only |
| `declared_at` | timestamp |

**Its only two effects, both restrictive:**

1. `peer_eligible`'s exclusion set becomes `evidenced_executors ∪ presumed_executors`. The record
   makes the review **harder** to own, never easier.
2. `open_review_context` copies an `evidence_absence_ref` onto the `review_context` it writes, so
   the resolving reviewer and every later reader can see the review was opened over a recorded
   absence.

**What it must NOT do, and this is the whole of its boundedness:** it never yields a `review_owner`,
it never satisfies the SELF branch, and it never counts as `executor_evidence` anywhere — not in
`evidenced_executors()`, not in completion eligibility, not in receipts. **A seat in a hurry gains
nothing by reaching for it**, because it unblocks nothing and only narrows the reviewer pool. That
is why it cannot become the path of least resistance: it is a cost with no shortcut attached.
Rejected: teaching the existing refusal to accept a flag, and a `force=` argument — both make the
absence a property of the caller rather than of the work.

#### (e) Decision 4 — the validator must distinguish RECORDED absence from UNEXPLAINED absence

`validate.py:387-388` currently warns *"lifecycle is 'review' with no review_context — legitimate only
for an unreconciled legacy item"* on records created this week. The wording is actively misleading
and cost this investigation time. Two changes:

- Re-word that warning to state what it actually detects — an item in a review status whose review
  has not been opened — with no claim about legacy.
- Add a distinct, quieter line for a record carrying an `evidence_absence`, and keep the loud one
  for absence with no record. **Losing that signal is not acceptable**: it is what caught this.

#### (f) The `T-087` boundary, applied to my own ruling

Both checks implied here — the exclusion-set union and the validator wording — are **gates in the
production path**, not unit tests: they run inside `policy.py` and `validate.py` on every real
call. **Gate side of the line. No new file under `test/`, and no unit test restating any of it.**

#### (g) Operating mode — this cannot be implemented from the current mode

`store.current_operating_mode()` returns **`PRODUCT_EXECUTION`**. Every change in (d) and (e)
touches `agent/state/`, which is Thebes infrastructure, so **the session must transition to
`SYSTEM_MAINTENANCE` before anyone implements this.** The **Orchestrator** performs the transition
via `store.set_operating_mode(mode, changed_by, reason_ref)`, and it will be refused while any
execution lease is open (`store.py:204-209`). The repairs in (b) and (c) are Product-state
reconciliation using operations that already exist and do not themselves require the transition.

**Consequence.** `po` tickets three separate things, not one: **(1)** the reconciliation of KAN-285,
297, 323, 329, 330, 331, 333 using existing operations, noting that KAN-297 will legitimately wait;
**(2)** the `evidence_absence` record and its two restrictive effects, as SYSTEM_MAINTENANCE;
**(3)** the validator re-wording. Any future review opened over a recorded absence is marked and
auditable, and the executor — where anyone is willing to name one — is excluded from reviewing its
own work rather than silently eligible.

**Status:** Accepted.

### From dabbler-docs: T-089 — Executor evidence is written by `store.release`, not by the receipt path. Three of the four tickets claimed on 2026-09-21 can therefore be evidenced TRUTHFULLY today by their own owners releasing them. No mechanism change is warranted, and I RETRACT `T-088`(d)'s `evidence_absence` record as over-built

**Date:** 2026-09-21 · **Seat:** `cto` (Khnum). **Supersedes `T-088`(d) only — the proposed
`evidence_absence` record is withdrawn. `T-088`(a), (b), (c), (e), (f) and (g) stand unchanged and
re-verified. Answers the Orchestrator's re-framed question of 2026-09-21: *"is any mechanism change
actually warranted?"* The answer is **no**, for a reason neither of us had found.**

#### (a) The re-framing's central measured claim is wrong. Third correction on the same records

The Orchestrator reported `validation_route=None` on KAN-285, KAN-323 and KAN-331, and concluded
the three sit *earlier* than the refusal, with no derived route. Re-read through `store.read` on
2026-09-21:

```
KAN-285  rev=4  route='qa'    cap='frontend'  work_effort=2  evidence=[]  owner=None
KAN-323  rev=4  route='self'  cap='frontend'  work_effort=3  evidence=[]  owner=None
KAN-331  rev=3  route='self'  cap='frontend'  work_effort=3  evidence=[]  owner=None
```

**Every route is derived**, and the revisions are identical to `T-088`(a) — the records have not
changed; the reading did. The same applies to the two offered data facts: `KAN-292` carries
`work_effort: 3` and `required_capability: 'frontend'`, **not null**, so it is not an item claimed
with two empty predicates. `KAN-335`–`KAN-339` having no Persistent State record **is** confirmed.

`T-088`(b) and (c) therefore stand exactly as written: KAN-285 opens today on the `qa` route;
KAN-297/329/330/331/333 reconcile `self`→`peer` through `store.reconcile_review_from_jira`;
KAN-323 is routed up rather than let through.

#### (b) The one thing in the re-framing that IS right — and its mechanism is not what was reported

The Orchestrator is correct that **ownership and evidence are separate fields, and a clean claim
writes only the first.** `KAN-292` proves it: `ownership.seat_id = frontend-4`,
`executor_evidence = []`. That is a real and important finding, and the seat that refuted the
Orchestrator was right to.

But the stated mechanism is wrong: *"Evidence is written downstream of
`record_execution_receipt`."* It is not. **`store.release` writes it** (`store.py:2900-2903`),
appending `{seat_id, evidence_ref: release_ref, evidenced_at}` from the ownership record as
ownership goes to null. `open_review_context`'s own refusal text says so in as many words —
*"Evidence arises from store.release, not from ownership, a status file or a Jira status"*
(`store.py:793-797`). Confirmed empirically: `KAN-292` has **zero** `execution_lease` and **zero**
`execution_receipt` records, yet nothing about evidence depended on either.

**This inverts the remedy, in the Orchestrator's favour.** Had evidence come from the receipt
path, work woken outside `execute_product_wake` could never be evidenced and would need a new
authority to rescue. Because it comes from `release`, the ordinary operation still works.

#### (c) Decision — the three tickets still owned are evidenced by being RELEASED, today

Items currently holding ownership with no evidence, all claimed under `ceo-parallel-2026-09-21`:

| id | owner | lifecycle | evidence |
|---|---|---|---|
| KAN-290 | frontend-2 | ready | `[]` |
| KAN-291 | frontend-3 | ready | `[]` |
| KAN-292 | frontend-4 | ready | `[]` |

**Each owner calls `store.release` with an honest `release_ref`.** That writes true executor
evidence: `frontend-4` genuinely holds the claim and genuinely did the work, and release is the
act of giving that claim up having done it. **Nothing is backdated and nothing is invented** — an
operation that was never completed is completed now. This satisfies **لا تصحّح الماضي — لا تكرّره**
exactly: the past is not rewritten, and the repeat is prevented by (e).

The absent `execution_lease` and `execution_receipt` are a **separate, honestly missing** record of
the invocation. They stay missing. Evidence of *who executed* and a receipt of *how they were
invoked* are different facts, and supplying the first does not assert the second.

`KAN-327` (frontend-5) already carries evidence and needs nothing.

#### (d) Decision — `T-088`(d) is RETRACTED. No `evidence_absence` record

`T-088`(d) identified a real hole and then over-built for it. The hole stands as a fact:
`policy.peer_eligible(cap, sbc, exclude=executors)` with empty evidence excludes nobody, so on the
five items reconciled to `peer` the author is silently eligible to review its own work. What I got
wrong was the remedy.

**The exclusion is restored by the existing named-reviewer path, with no new code.**
`store.resolve_review_owner` already requires an `evidence_ref` recording *what authorised this
exact reviewer* (`store.py:1073-1076`). A CEO or Orchestrator naming a reviewer who is not the
author achieves precisely the exclusion the empty set lost, and forces the namer to write down why
— which is the audit trail `evidence_absence` was invented to provide.

Building a new record type, a new authority set and two new code paths, for a bounded set of seven
items that an existing operation already handles, is the general hole this seat was asked to
prevent. **Rejected on cost, not on principle.** The principle in `T-088`(d) — that an absence must
be a fact on the record and must only ever add exclusions — was sound; it simply describes what
`resolve_review_owner`'s `evidence_ref` already is.

#### (e) The repeat is prevented procedurally, and that is the whole fix

Route every Product wake through `agent.execution.wake.execute_product_wake` so a lease opens, a
receipt is written, and release follows. **Claim plus continuation gate is not sufficient** — the
Orchestrator's own diagnosis, and it is correct. Claiming correctly and then invoking the seat
through the `Agent` tool directly leaves ownership with no lease, no receipt and, until release,
no evidence.

#### (f) `EVIDENCE_AUTHORITIES` is intentional, not a gap

`EVIDENCE_AUTHORITIES = ("ceo", "orchestrator")` (`store.py:1580`) gates
**`classify_executor_evidence`**, which only *marks an existing entry* as execution-vs-assessment.
The Orchestrator is right that it creates nothing and that `po` cannot author evidence. That is
**correct as designed and should not change**: the creator is `release`, and release is restricted
to the item's own owner for the same reason a signature is restricted to its signer. A general
"create evidence" API is exactly the fabrication both CEO rulings forbid. **No gap. No change.**

#### (g) What remains warranted — the validator change, for the Orchestrator's own reason

`T-088`(e) stands, and this episode is its strongest argument: the same warning text, worded for
legacy items, has now produced three different misreadings of the same seven records by two
different readers. `validate.py:387-388` must say what it detects, and must distinguish an item in
a review status whose review has not been opened from one blocked on absent evidence. **This is
now the ONLY code change this seat rules for**, it is a production-path gate not a unit test
(`T-087`), and it alone requires the `SYSTEM_MAINTENANCE` transition described in `T-088`(g).

**Consequence.** `po` tickets three things: **(1)** `release` on KAN-290, KAN-291, KAN-292 by their
owners with honest refs; **(2)** the `T-088`(b)/(c) reconciliations, unchanged; **(3)** the
validator re-wording, as SYSTEM_MAINTENANCE. No new store operation, no new record type, no new
authority. **The answer to "is any mechanism change warranted" is no** — the process was wrong, and
one warning message is misleading.

**Status:** Accepted. Supersedes `T-088`(d).

### From dabbler-docs: T-090 — Retroactive attestation of executor evidence is refused, a third time and now as a rule: no authority may author `executor_evidence`. The thirteen design-system SELF items with no evidence go UP to PEER by the T-088(c) path, and the executor hint is used only to exclude the probable author from reviewing

**Date:** 2026-09-21 · **Seat:** `cto` (Khnum). **Rules the Orchestrator's question of 2026-09-21: may a named authority attest executor evidence retroactively (working name `attest_executor_evidence`)? Answer: no. Supersedes nothing; applies `T-088`(c) and `T-089`(f) to KAN-287, 288, 289, 303, 318, 319, 320, 321, 323, 324, 328, 334, 341. Constrains `agent/state/store.py`, which it does not modify.**

#### (a) The facts

All thirteen sit in Jira `Self-review` (10044) with local `validation_route: self`, `ownership: None`, `executor_evidence: []`, `review_context: None` (read through `store.read`, 2026-09-21). Nine carry a `po` acceptance PASS dated 2026-09-20. Their code reached the repository through direct `Agent` invocations, never through claim → wake → release, so the store witnessed no ownership. Executor hints exist only in seat status logs (KAN-323 → `frontend-2`, `agent/status/frontend-2.md:721`; KAN-328 → `frontend-1`, `agent/status/frontend-1.md:1134`) and, for KAN-323, in a Jira comment. Every git commit carries one author. `T-089`(c)'s remedy — the owner releases — is unavailable: there is no owner.

#### (b) Decision 1 — no attestation, no create-evidence operation, under any authority

Evidence is written by `store.release` from the ownership record the store itself witnessed (`store.py:2893-2895`), and the refusal text is explicit: "Evidence arises from store.release, not from ownership, a status file or a Jira status" (`store.py:793-796`). `classify_executor_evidence` was built one-way for this reason: "evidence may be reclassified as assessment, never INTO execution … a sizing report turned into a claim" (`store.py:1617-1621`). An attest function gated on `ceo` is a create-evidence API with a signature block. `T-089`(f) already said so: "A general 'create evidence' API is exactly the fabrication both CEO rulings forbid." Restricting the author does not change what is authored. **Rejected**, and so is the variant "CEO-authorised claim followed by immediate release": `claim` refuses non-Ready items (`store.py:830`), and a claim taken in order to be released without execution is a fabricated ownership act that exists only to launder a fabricated evidence entry.

#### (c) Decision 2 — this conflicts with the CEO's ruling, and the distinction `T-089` drew is the whole test

The CEO ruled **لا تصحّح الماضي — لا تكرّره** (do not correct the past; do not repeat it), recorded at `T-088` header and on KAN-323 comment 11239 (2026-09-20T23:31+04). `T-089`(c) permitted release on still-owned items because "an operation that was never completed is completed now" — nothing backdated, nothing invented. Attestation is the opposite case: a fact about the past, absent from the store, reconstructed from a seat's own narrative and written as if witnessed. That is correcting the past. `agent/status/po.md` (2026-09-20 cont. 4) records that entries in a seat status file were written by an unauthorised fork under the seat's identity; a status line is not a witnessed fact and cannot become one by attestation.

#### (d) Decision 3 — the thirteen go UP, exactly as `T-088`(c) sent KAN-323

For each item, in order: (1) `po` transitions Jira `Self-review` → `Peer-review` (10045), comment first, citing this entry; (2) `po` calls `store.reconcile_review_from_jira` (`store.py:345`), which raises `self`→`peer` — the strengthening direction, the only one the no-downgrade rule (`WORKFLOWS.md:465`) permits, and the operation `po` already ran on eleven sibling items on 2026-09-21; (3) `po` calls `store.open_review_context`, which writes a PEER context waiting at `review_owner: null` (`store.py:714-716`); (4) the Orchestrator or CEO names a same-capability reviewer through `store.resolve_review_owner` (`store.py:1047`), whose `evidence_ref` states the authorising session AND the exclusion basis — the status-log line naming the probable author, who may not be named. `policy.peer_eligible` (`policy.py:203`) cannot enforce that exclusion with empty evidence, so the namer must; naming the probable author is an invalid selection under §PEER condition A (`WORKFLOWS.md:516`). **The hint excludes; it never owns** — `T-088`(d)'s rule for `presumed_executors`, kept. (5) The existing `po` PASS verdicts are acceptance findings and stand as input to the reviewer; they are not the PEER verdict.

KAN-303, 334, 341 are `content`. Until 2026-09-21 `topology.json` declared `content` at one seat, ceiling two, expandable, and with one seat the PEER route waits, which is doctrine (`WORKFLOWS.md:525-529`; `T-088`(b) on KAN-297). That expansion is already executing: `content-2` was created on 2026-09-21 on Thebes branch `worktree-maint-review-column`, commit `04e9039` (`seats.json`, `topology.json` `defined_seats` 1→2, binding, rendered agent, status log), pending the CEO's merge into local `main`. Once merged, the three content items resolve through step (4) like the frontend ten; until then they wait at `review_owner: null`. Never a downgrade.

#### (e) No schema change, no validator rule

No field, kind, record or authority is added; `SCHEMA_VERSION` stays at 3 (`store.py:32`). The only validator work remains `T-088`(e)/`T-089`(g), unchanged.

#### (f) If the CEO overrides and orders attestation regardless — the floor, stated once so it is not reinvented

Authority `ceo` alone, matching `CORRECTION_AUTHORITIES` (`validate.py:118-120`) and never `po`; `evidence_ref` a first-hand CEO record, never a status line; the entry carries `classification: "attested"` and is EXCLUDED by `evidenced_executors()` (`store.py:694-696`), so it feeds reviewer exclusion only and never resolves a SELF owner — which means the item still goes to PEER and the override buys nothing (d) does not already give; refused when evidence is non-empty (two entries are a conflict, `store.py:1320-1322`); write-once; schema bump and validator rule then required. This paragraph is a boundary, not a recommendation.

**Consequence.** `po` tickets one thing: the thirteen transitions and reconciliations in (d). The Orchestrator names reviewers with exclusion-bearing refs. No store change. The repeat is prevented by `T-089`(e): every Product wake through `execute_product_wake`.

**Status:** Accepted. Applies `T-088`(c) and `T-089`(f); supersedes nothing.

### From dabbler-docs: T-091 — An already-open review context is dispatched by a new Listener intent, `VALIDATE_WORK_ITEM`, through a new controller act `validate`; it is not a Product wake, opens no claim and no lease, skips `enter_review`, reads the integration branch in the reviewer's own read-only worktree, and records its verdict through the one canonical writer

**Date:** 2026-09-21 · **Seat:** `cto` (Khnum). Line citations are to Thebes `main` at `ace6c9b`. **Rules the Orchestrator's question of 2026-09-21: what is the smallest correct Listener/controller change that lets an ALREADY-OPEN review context be dispatched to its recorded `review_owner` without a new Product execution? Applies `T-089`(e) and `T-090`(d); supersedes nothing. Constrains `agent/listener/contract.py`, `agent/listener/dispatch.py`, `agent/listener/__main__.py`, `agent/controller/entry.py`, `agent/controller/__main__.py`, `agent/controller/__init__.py`, `agent/controller/validation.py`. Modifies none of them: this entry is the design; the edit is SYSTEM_MAINTENANCE work under it.**

#### (a) The facts

The Listener allow-lists exactly two intent families, `EXECUTE_WORK_ITEM` and `DECISION_RESPONSE` (`agent/listener/contract.py:24-26`), and the dispatcher builds argv for exactly those two (`agent/listener/dispatch.py:49-57`). An `EXECUTE_WORK_ITEM` on KAN-267 — canonically `review`, Jira `Peer-review` 10045, `review_context` `{peer, frontend-6, pending}`, `ownership: None`, `executor_evidence: []` (runtime task record, read 2026-09-21) — returned `bounded-authorization-selection-not-admissible: not-ready, surface-contention`, claim not started, validation not attempted. That refusal is CORRECT: the execute path is claim → wake → release → `run_validation` (`agent/controller/validation.py:668-759`), and `run_validation` begins with `enter_review` (`:142-166`), which releases ownership and transitions Jira — two acts already performed for all 27 items in `queue.review_work` (`agent/state/queue.py:355-372`): KAN-267, 285, 286, 287, 288, 289, 297, 303, 318, 319, 320, 321, 323, 324, 327, 328, 329, 330, 331, 333, 334, 335, 336, 337, 338, 339, 341. Their contexts were opened by `po` on 2026-09-21 and their owners resolved through `store.resolve_review_owner` per `T-090`(d). No integration receipt exists for any of them (`integration_receipt/` is empty, 2026-09-21); no execution lease is open; no intervention is active. The validation machinery itself is complete and reusable: `build_validation_request` (`:276`), `dispatch` (`:349`), `verdict_from` (`:359`), `_record_validation_receipt` (`:400`), `_prepare_validation_continuation` (`:417`), `record_verdict` (`:621`), `remediate` (`:630`), and `resume_validation` (`:504`) for an APPROVED validator. What is missing is one entry point that starts at "context already open" instead of "execution just returned".

#### (b) Decision 1 — a new intent family, `VALIDATE_WORK_ITEM`; `EXECUTE_WORK_ITEM` is not overloaded

The contract says adding a family "is a deliberate act" (`contract.py:22-23`), and the dispatcher is "deliberately thin … not a second controller" (`dispatch.py:3-15`). Making `EXECUTE_WORK_ITEM` detect an open review context and skip to validation would make the same envelope mean two different acts depending on state the caller cannot see, and it would put a lifecycle decision — "this is a review, not an execution" — into the one module that must own no lifecycle decision. It would also silently convert a CEO's execute submission on a mis-staged item into a review of it. **Rejected.** `VALIDATE_WORK_ITEM` carries the same payload as execute — `work_item_id` only (`contract.py:40-45`) — and nothing else: no reviewer, no route, no workspace, no receipt reference. Everything is re-derived from canonical state by the controller, exactly as the dispatch docstring requires. The controller gains a fourth orchestrating command, `validate`, beside `execute|resume|decide`.

#### (c) Decision 2 — this is not a Product wake, and `T-089`(e) is satisfied, not bypassed

`T-089`(e) requires every Product WAKE through `execute_product_wake`. A validation is not a wake: `validation.py:33-40` states why it deliberately composes the provider seam without the ownership gate, and the request contract enforces it — kind `validation` must be read-only (`agent/execution/provider.py:234-240`) and, unlike an execution request, needs no `claim_ref` and no `execution_lease_id` (`:243`). `T-091` reuses that exact path. A VALIDATE opens no claim, opens no lease, and cannot write to the Product tree.

#### (d) Decision 3 — preconditions, verified by the controller before any dispatch, each with a structured refusal

In this order, and the first failing reason is returned; nothing is dispatched on any refusal:

1. `system-maintenance-active` — `store.current_operating_mode()` is not `PRODUCT_EXECUTION` (same gate as `execute`, `integrate`, `resume_validation`: `agent/controller/__init__.py:721-724`).
2. `work-item-not-found` — `store.read("task", id)` is None.
3. `not-in-review` — the controller reads the issue live (`jira_client.get_issue`), records it with `store.observe_lifecycle` (`agent/state/store.py:317-340`, CAS), and refuses unless the observed canonical state is `review`. Jira is lifecycle authority; the stored lifecycle alone is not consulted, because `stale-jira` is a standing claimability reason and a review must not run on a stale observation.
4. `no-review-context` / `review-already-settled` — `review_context` must be a dict with `review_result == "pending"` (the same guard `record_review_result` applies at `store.py:1170-1177`, applied early so no reviewer is spent on a context that could not accept its verdict).
5. `review-owner-unresolved` — `review_owner` is null. This is `VALIDATION_WAITING_FOR_REVIEWER` (`validation.py:80`): the doctrine's waiting state, reported, never filled by the controller (`queue.py:359-362`).
6. `review-route-mismatch` — the observed Jira status is not `store.transition_target(route=review_context.review_type)` (`store.py:296`). Reconciling that is `po`'s act by `reconcile_review_from_jira` (`T-090`(d) step 2); the controller refuses rather than reconciles.
7. `task-stopped` — an active `stop` intervention targets this item (`store.active_interventions()`, `store.py:1464`). STOP blocks continuation and claim; a review is the item's continuation in flight, and recording a verdict past a STOP would advance exactly the work somebody stopped — the same reasoning `completion_reasons` records at `queue.py:441-446`.
8. `execution-lease-active` — an execution lease on this item has `closed_at: None` (`read_all("execution_lease")`). An open lease means an executor is inside a wake on the same item; reviewing under it would read a tree that is being written.
9. `validation-continuation-pending` — `_pending_validation_preparation` (`validation.py:608-618`) finds a prepared continuation for this exact `review_ref` with no terminal receipt. The validator already ran and is waiting at a native permission boundary; the answer is a `DECISION_RESPONSE`, not a second reviewer.

**HOLD and FREEZE do not apply, explicitly.** Both gate NEW CLAIMS only (`store.intervention_blocks_claim`, `store.py:1468-1481`; `queue.execution_reasons` docstring, `queue.py:326-328`: "HOLD and FREEZE deliberately do NOT appear here"). A VALIDATE claims nothing, so a capability HOLD or a system FREEZE neither blocks nor is consulted by it. This is the same rule the continuation gate already applies to owners, and `T-091` does not invent a third reading of the primitives.

#### (e) Decision 4 — `enter_review` is skipped; the entry point is open context → gate → dispatch → record → remediate

`enter_review` releases ownership and transitions Jira (`validation.py:142-166`). Both are done. Calling it again would (i) call `store.release` on a null owner, which it guards against, and (ii) re-observe a transition already observed — harmless but false as an act, and its `route_for(task)` derives the route from `execution_profile`, which `T-090`(d) deliberately left below the context's raised `review_type` for the thirteen items. `open_context` is also skipped: it already returns the existing pending owned context unchanged (`:187-190`), so it would be a no-op, and calling it advertises a creation that is not happening. The new act composes, in order, the functions that already exist:

| Step | Existing function | Note |
|---|---|---|
| context | the task's `review_context` as read; `review_ref = store.review_context_ref(id, rc)` (`store.py:2189-2193`) | no open, no resolve |
| gate | `agent.qa.gate.run_deterministic_gate(id, task, realized, None)` (`agent/qa/gate.py:90-101`) | reads only `realized["path"]`; `execution` is discarded at `:94`; `GATE_INFRA` refuses with `VALIDATION_INFRASTRUCTURE_FAILED` exactly as `run_validation:701-713` |
| brief | `build_validation_request(id, task, issue, None, realized, reviewer, review_ref, receipt_ref, gate)` (`:276`) | see (f) for `execution=None` and `receipt_ref` |
| dispatch | `dispatch(request, providers, override)` (`:349`) | one provider, no retry |
| receipt | `_record_validation_receipt` (`:400`); on `NEEDS_INPUT`, `_prepare_validation_continuation` (`:417`) | authorised by the review context, as today |
| verdict | `verdict_from` (`:359`) → `record_verdict` (`:621`) → `store.record_review_result` (`store.py:1134`) | only the recorded owner may write it |
| remediate | `remediate` (`:630`) on FAIL | PEER → `peer_fail_transfer`; SELF → `self_fail_reentry`; QA → executor or none |

The tail from "gate" onward is IDENTICAL to `run_validation:697-759`. The implementation factors it into one private function used by both callers so that ordering exists once; `run_validation` keeps `enter_review` + `open_context` in front of it and changes behaviour in no way.

**On PASS the act stops.** It does not call `integrate()`: the work of these 27 items is already on the integration branch, there is no Product commit to land, and `integrate` would refuse `not-owned` anyway because `_integration_seat` needs an owner or a single evidenced executor (`__init__.py:903-918`) and these items have neither. Completion remains DERIVED (`queue.completion_reasons`, `queue.py:397-455`) and the Done transition remains the Orchestrator's separate act, as `record_review_result`'s docstring states (`store.py:1144-1147`). Whether a completion path exists for an item with `executor_evidence: []` beyond `completion_reasons` is **not documented** here; `completion_reasons` does not consult evidence, so on the reading of that function alone a PASS makes the item eligible.

#### (f) Decision 5 — what `execution` and `realized` are when there was no execution

**`execution` is `None`, stated, never synthesised.** A fabricated `ExecutionResult` would be a fabricated executor report — the thing `T-089`(f) and `T-090`(b) refuse in every form. `validation_objective` already tolerates it: every executor field is read by `getattr(execution, …, None)` with a rendered default ("no executor summary recorded", `:245-253`). One rendering change is required so the brief does not merely say "none reported": when `execution is None`, the "What the executor reported" section states that no execution receipt exists because the work reached the integration branch outside the wake seam (`T-089`, `T-090`), and the "Changed surfaces" section lists the task's DECLARED `surfaces` (already the request's `allowed_surfaces`, `:311`) under the heading "Declared surfaces", so the reviewer confines the review to them and reports any change outside them as a finding.

**`realized` is the reviewer's own worktree, allocated from the integration branch, read-only by contract.** `realize_workspace(work_item_id, reviewer, {"repository_root": <resolved>}, base=worktrees.INTEGRATION_BRANCH)` (`agent/controller/workspace.py:69-107`; `allocate` defaults `base` to `Canary`, `agent/state/worktrees.py:120-128`; `INTEGRATION_BRANCH`, `:63`). The repository root is resolved exactly as `_integration_workspace` resolves it (`__init__.py:934-944`, `read_project_repository(product_id, project_id)`). Rejected alternatives: the canonical Product checkout is "never a target of execution" (`worktrees.py:112-115`; `workspace.py:95-97`), and a bare `git worktree add --detach` would bypass `assert_isolated_identity` (`workspace.py:110-150`). The (seat, item) tree is also the right tree for what follows: on a PEER FAIL `peer_fail_transfer` makes the reviewer the executor of the fix, and its worktree already exists. Read-only is enforced by the request contract (`provider.py:239-240`), not by the filesystem. The workspace is concluded after the act by the ordinary concluder; whether `release_decision` (`workspace.py:153`) needs a review-only branch is an implementation detail the tests in (h) must settle.

**`receipt_ref` cites the integration revision, not a receipt that does not exist.** The verdict's `evidence_ref` (built at `validation.py:742-744`) already carries route, verdict, reviewer and summary; the validation act's own receipt (`_record_validation_receipt`) is the durable evidence of the act. The brief's "executor evidence" line (`:270-271`) and the act's `receipt_ref` are `integration:<branch>@<expected_revision>` from `realized`, e.g. `integration:Canary@<sha>` — the exact tree the reviewer read. No `execution receipt for KAN-x` string is written for a receipt that was never recorded.

#### (g) Decision 6 — idempotency

- **Settled context** (`review_result` `pass` or `fail`): refused `review-already-settled` (`VALIDATION_ALREADY_SETTLED`, `validation.py:90`) at precondition 4, before any workspace or Jira write.
- **Pending, nothing recorded:** dispatched once.
- **Pending, a terminal validation receipt already exists for this `review_ref`** (a prior VALIDATE whose `record_verdict` did not complete): settle from that receipt — the `_settle_from_receipt` behaviour (`:571-598`) generalised to take a receipt without a continuation preparation — never re-wake a reviewer over a judgement already recorded. This mirrors `resume_validation:522-528`.
- **Pending, continuation prepared:** refused `validation-continuation-pending` (precondition 9).
- **Two VALIDATEs in flight:** the same `idempotency_key` is the same intent by identity (`contract.py:160-170`); different keys serialise on the Listener's single worker thread (`agent/listener/server.py:46-52`), so the second runs after the first has settled and hits `review-already-settled`. The durable floor is `record_review_result`'s CAS and `review-already-settled` guard (`store.py:1165-1177`): at worst one wasted reviewer invocation, never two verdicts.

#### (h) Decision 7 — the change list and the tests

**Change list (file · function · what it adds).**

1. `agent/listener/contract.py` · module constants · `VALIDATE_WORK_ITEM = "VALIDATE_WORK_ITEM"`, added to `INTENT_TYPES`; `PAYLOAD_FIELDS[VALIDATE_WORK_ITEM] = (("work_item_id",), ())`. · `_payload` · returns the `work_item_id`-only clean payload for VALIDATE as it does for EXECUTE (`:143-144`). `normalize` unchanged: `responds_to` remains DECISION-only.
2. `agent/listener/dispatch.py` · `argv_for` · `[sys.executable, "-m", "agent.controller", "validate", work_item_id]` for VALIDATE. Nothing else in the module changes.
3. `agent/listener/__main__.py` · `main` · a `validate <work_item_id>` subcommand mirroring `submit` (`--idempotency-key`, `--actor`, `--source`, `--wait`), posting `intent_type: VALIDATE_WORK_ITEM`; the module docstring gains its line.
4. `agent/controller/entry.py` · `ORCHESTRATING_COMMANDS` · `("execute", "resume", "decide", "validate")`; the refusal text adds `python3 -m agent.listener validate <WORK-ITEM>`. This is what makes precondition (i) hold: a direct `python3 -m agent.controller validate KAN-x` refuses `direct-controller-entry-retired` exactly as `execute|resume|decide` do, and `--maintenance-reason` remains the recorded bypass.
5. `agent/controller/__main__.py` · `main` · `validate` subparser with `work_item_id` and `--maintenance-reason`; routes to `validate(...)`; `entry_path`/`entry_reference` stamped as for the other orchestrating commands; exit 0 iff a verdict was recorded (`validation_status` in `VALIDATION_PASSED`, `VALIDATION_FAILED`), 1 otherwise. A FAIL verdict is an authoritative answer, which is why it exits 0 and the Listener classifies it COMPLETED.
6. `agent/controller/__init__.py` · new `validate(work_item_id, *, state_store=store, jira_client=jira, providers=None, workspace_allocator=realize_workspace, workspace_concluder=conclude_workspace, interventions=None, worktree_root=None, provider_override=None)` · the mode gate, the task read, the live Jira read + `observe_lifecycle`, preconditions (d) 3 and 6-9 in the controller and 4-5 through the validator's own refusals, the reviewer worktree allocation from the integration branch, the call to `validation_policy.run_open_review`, workspace conclusion, and a result shell reporting `validation_status`, `validation_route`, `reviewer`, `review_cycle`, `verdict`, `validation_blocker`, `remediation_owner`, `remediation_route`, `workspace_path`. It never calls `integrate`.
7. `agent/controller/validation.py` · new `run_open_review(work_item_id, task, realized, state_store, jira_client, providers, issue=None, seats_by_capability=None, provider_override=None, deterministic=None)` · the composition in (e), with `execution=None`, refusing `VALIDATION_CONTEXT_REFUSED` (no context), `VALIDATION_ALREADY_SETTLED` (settled) and `VALIDATION_WAITING_FOR_REVIEWER` (null owner) in that order before touching the gate; `receipt_ref` per (f). · new private `_dispatch_and_settle(...)` · the shared tail extracted verbatim from `run_validation:697-759`, called by both `run_validation` and `run_open_review`. · `validation_objective` · the two `execution is None` renderings of (f). · `_settle_from_receipt` · accepts `preparation=None` and takes `reviewer`/`review_ref` from the review context in that case. The preconditions in (d) that need Jira, interventions or leases (3, 6, 7, 8, 9) live in the controller's `validate`, which has those clients; the context-shape refusals (4, 5) live in `run_open_review`, so each has one wording.

**Tests required.** `agent/listener/tests/test_contract_store.py`: a VALIDATE envelope round-trips; its payload refuses every field but `work_item_id`; `responds_to` on a VALIDATE is refused; a VALIDATE and an EXECUTE under the same `idempotency_key` are different intents. `agent/listener/tests/test_dispatch.py`: `argv_for` yields exactly `[python, -m, agent.controller, validate, KAN-x]` and no token from intake reaches argv; the real-subprocess case (`:7-9`) is repeated for `validate` and proves it refuses with `direct-controller-entry-retired` when launched without the intent marker. `agent/controller/tests/test_entry.py` (or a new `test_validate_entry.py`): each of (d) 1-9 refuses before any workspace allocation, Jira transition or provider call, with a fake store carrying the KAN-267-shaped record above; HOLD and FREEZE do NOT refuse; the happy path allocates the reviewer's worktree from the integration branch, dispatches one read-only request whose `seat_id` is the recorded owner, records a receipt bound to `review_ref`, records the verdict, and does not call `integrate`; PASS leaves Jira untouched; PEER FAIL transfers to the reviewer; a NEEDS_INPUT prepares a continuation and a second VALIDATE refuses `validation-continuation-pending`; a second VALIDATE on a settled context refuses `review-already-settled`; a stale-write on the task revision surfaces as `VALIDATION_DISPATCH_FAILED`, not as a verdict. `agent/controller/tests/test_validation_dispatch.py`: `run_validation` output is byte-identical before and after the extraction of the shared tail (the existing 16 cases are that proof); `validation_objective(execution=None)` renders the declared-surfaces heading and the outside-the-seam sentence and never invents a summary. `agent/controller/tests/test_deterministic_gate.py`: the gate runs on `realized["path"]` with `execution=None` and `GATE_INFRA` refuses before dispatch.

#### (i) The draft that already exists, judged against this ruling

Thebes worktree `.claude/worktrees/maint-validate-intent` (off `ace6c9b`, uncommitted, 7 files, +266/-8, read 2026-09-21) already carries an implementation of exactly this shape: `VALIDATE_WORK_ITEM` in the contract, the `validate` argv in the dispatcher, the Listener `validate` subcommand, `validate` in `ORCHESTRATING_COMMANDS`, the controller `validate` subparser with `--maintenance-reason` and the verdict-recorded exit rule, `run_open_review` + `_dispatch_and_settle` in `validation.py`, and a controller `validate()` that observes Jira live, refuses `not-in-review`, `task-stopped`, `execution-lease-active`, allocates the reviewer's worktree through `_integration_workspace`, and lets `run_open_review` word the context refusals. Decisions 1-4 and the extraction in (e) are met by it. It is **not acceptable as it stands**; the defects, each a fact of the diff:

1. **The lease check is a silent no-op.** `_open_leases` looks up `state_store.open_execution_leases`, which does not exist in `agent/state/store.py` (grep, 2026-09-21), and returns `()` when the attribute is absent. Precondition (d) 8 must read `read_all("execution_lease")` and refuse on any record for the item whose `closed_at` is null.
2. **PASS calls `integrate()`.** It refuses `not-owned` for every one of the 27 (`_integration_seat`, `__init__.py:903-918`: no owner, no evidenced executor) and returns before any receipt is written, so it is harmless but false — a call whose only possible answer is a refusal is not a tail, it is noise in every result. Per (e), `validate` stops on PASS. Its docstring and the `__main__` help text ("then run integration and completion") must say so instead.
3. **Missing preconditions:** `review-route-mismatch` (d) 6 and `validation-continuation-pending` (d) 9; missing the settle-from-existing-receipt branch of (g).
4. **`validation_objective` is unchanged**, so the brief for these items still says "no executor summary recorded" / "none reported" as if an executor had been asked and had nothing to say. (f) requires the outside-the-seam sentence and the "Declared surfaces" heading.
5. **`receipt_ref`** is `open review context <ref> (executor evidence: none recorded)`. Truthful; incomplete. It must also carry the integration revision read, `integration:<branch>@<expected_revision>`, so the verdict names the exact tree it judged.
6. **No tests.** None of (h) exists in the worktree; `git status` shows only the seven source files.

Fix 1 is a correctness defect and blocks any dispatch of the 27 through this door; 2-6 are acceptance conditions.

#### (j) What this does not do

No schema change (`SCHEMA_VERSION` stays 3); no new store record or operation; no new authority; no validator rule; no change to claimability, the continuation gate, the interventions or Jira. It does not reconcile a route, name a reviewer, or create evidence — `T-090` stands, and the thirteen items it sent UP reach their PEER reviewer through this door once the Orchestrator submits `python3 -m agent.listener validate <WORK-ITEM> --wait` for each.

**Consequence.** `cto` tickets the seven-file change as SYSTEM_MAINTENANCE, starting from the draft in `maint-validate-intent` with the six corrections in (i) and the tests in (h) as its acceptance; it ships before the 27 items are dispatched. The Orchestrator submits one VALIDATE per item in `review_work`, in PRODUCT_EXECUTION, and reports refusals by their reason rather than routing around them.

**Status:** Accepted. Applies `T-089`(e) and `T-090`(d); supersedes nothing.

### From dabbler-docs: T-092 — A PEER FAIL on an item with NO evidenced executor cannot transfer; it returns to `Ready` through a new `po` recovery writer that closes the failed context, and the remediation is won by an ordinary claim. Neither the transfer nor the validator carve-out is loosened

**Date:** 2026-09-21 · **Seat:** `cto` (Khnum). Line citations are to Thebes `main` at `7e0a43c`. **Rules the Orchestrator's question of 2026-09-21: what is the canonical disposition of a PEER FAIL where `executor_evidence` is empty, so `store.peer_fail_transfer` is refused? Applies `T-090`(d) and `T-091`; extends the execution-recovery row of `WORKFLOWS.md:203`; supersedes nothing. Constrains `agent/state/store.py`, `agent/state/validate.py`, `agent/WORKFLOWS.md`. Modifies none of them: this entry is the design; the edit is SYSTEM_MAINTENANCE work under it. No Product code, no Jira write, no store write here.**

#### (a) The facts

KAN-288 (`frontend`, revision 7) and KAN-303 (`content`, revision 8) both read, through `store.read` on 2026-09-21: Jira `Peer-review` 10045, `ownership: None`, `executor_evidence: []`, `review_context {peer, cycle 1, result fail}` with `review_owner` `frontend-8` and `content-2` respectively, `execution_profile.validation_route: peer` with provenance `reconciled_from_jira: 10045` (the `T-090`(d) raise), `characteristics {shared_or_contended_surface: false}`, `execution_recovery: null`, `completion_reconciliation: null`. The verdicts are durable: `record_review_result` committed them (`store.py:1189-1194`) and the receipts `review:KAN-288:peer:1` and `review:KAN-303:peer:1` carry the findings. Both findings say the same thing: no work for the ticket exists in the tree at `2c22f034`; for KAN-303 the six declared surfaces are stale (moved by KAN-293 `a33d7b8` to `assets/documentation/foundations/`). `remediate` (`agent/controller/validation.py:648-680`) then called `store.peer_fail_transfer`, whose single write composes `previous_owner: prev[0] if len(prev) == 1 else None` from `executor_evidence` (`store.py:1382-1395`); with an empty list that is `None`, and `_validate_one` refused the merged record: "review_type 'self' does not match validation_route 'peer' — the only legal divergence is after a PEER-fail transfer, which sets previous_owner" (`validate.py:407-410`). Nothing was written; Jira was not transitioned (`remediate` transitions only after the transfer returns, `:671-676`). The items are not stuck by accident: they are the first FAILs on the path `T-090`(d) opened, and that path was for items that reached the tree with no witnessed executor, so a transfer that presumes one has nothing to transfer from.

#### (b) Decision 1 — disposition is option (a): back to `Ready`, findings as the rework brief, remediation by ordinary claim

Options (b) and (c) are rejected on the record:

- **(b) allow `peer_fail_transfer` with `previous_owner: null` when evidence is empty — rejected.** `previous_owner` is not decoration; it is *the* record that a transfer happened, and it is what distinguishes the authorised below-floor state from an ordinary drag from `Peer-review` to `Self-review` (`validate.py:745-752`; `WORKFLOWS.md:471-474`; `reconcile_review_from_jira`, `store.py:378-380`). A null value that the validator must accept makes the carve-out unenforceable for every item, not just these two. Worse, the transfer writes `executor_evidence` for the reviewer at transfer time (`store.py:1386-1388`). That is tolerable when the reviewer inherits an existing execution; here it would evidence execution nobody has performed, which is the fabrication `T-089`(f) and `T-090`(b) refuse in every form. `T-090`(f) already drew this line: even a CEO-attested entry may never resolve a SELF owner.
- **(c) CEO names the reviewer as executor — permitted, not needed.** MODEL C survives for an explicit CEO-named executor (CLAUDE.md, "MODEL C survives in exactly three places", item 2), so the CEO may name `frontend-8` or `content-2` if the CEO wants to. But the capability queue exists for exactly this: once the item is `Ready`, any same-capability seat can claim it, and the CEO's directive names a **provider** (Claude, model Fable, effort low), which is a provider-selection matter for the wake seam (`execute_product_wake` and the controller's authorised `provider_override`, `T-091`(h) 6), not a seat naming. Naming is unnecessary and is not recommended.

**Option (a) is the canonical path, and it composes existing doctrine with one missing writer.** `Ready` is the Product-selected execution queue and returning INCOMPLETE, UNOWNED work to it is `po`'s lifecycle act (`WORKFLOWS.md:203, 208-227`; `store.recover_execution_to_ready`, `store.py:825-931`). These items are unowned and the work is incomplete by the reviewer's own finding. What differs is only that they sit in a REVIEW status with a FAILED context, and the existing writer refuses both facts by design (`not-orphaned-execution`, `:887-892`; `review-in-progress`, `:902-905`) — correctly, because a failed context normally has a route that decides what happens next. Here the route's own remediation (`peer_fail_transfer`) is refused, and every other exit is closed: `open_review_context` refuses to reopen a failed PEER context (`:764-767`); `self_fail_reentry` is SELF-only; `supersede_task` needs a replacement (`:1699-1701`); and `observe_lifecycle` at `Ready` is refused while the context stands, because `review_context must be null in 'ready'` (`validate.py:393`; verified by dry-run on copies of both records, 2026-09-21: refused with the context, valid with it null). The only writer that nulls a context is `supersede_task` (`:1729`). **So the recovery row needs an extension and a writer; it is not an operating question `po` can answer with today's functions.**

#### (c) Decision 2 — the SYSTEM_MAINTENANCE change: `store.recover_failed_review_to_ready`

A **new** writer, not a widening of `recover_execution_to_ready`, whose refusals of review status and review context stay exactly as they are. Signature: `recover_failed_review_to_ready(work_item_id, expected_revision, recovery_ref, actor, jira_status_id)`. CAS'd under the record lock. It refuses, in order, with structured reasons: `expected_revision` None; empty `recovery_ref`; `actor` not in `RECOVERY_AUTHORITIES` (`po`/`ceo`, `store.py:822`); container record; `lifecycle.canonical != "review"` (`not-in-review`); `review_context` not a dict (`no-review-context`); `review_context.review_type != "peer"` (`not-a-peer-review` — SELF and QA FAILs re-enter by their own paths); `review_context.review_result != "fail"` (`review-not-failed`); `ownership` not None (`already-owned`); `evidenced_executors(cur)` non-empty (`executor-evidenced: the PEER-fail transfer is the path when an executor is evidenced; recovery to Ready is only for a FAIL with nobody to transfer from`); `completion_reconciliation` not None (`already-reconciled-complete`); an active task-scoped STOP (`task-stopped`, HOLD and FREEZE deliberately do not block, as at `:911-919`); and `str(jira_status_id) != queue.READY_STATUS_ID` (`jira-not-ready: po transitions the issue to Ready (10008) first and passes the status read back`). It writes, in one atomic replace: `review_context: None`; `execution_recovery: {by, at, recovery_ref, from_status: "10045", closed_review: {review_type, review_cycle, review_owner, review_result, evidence_ref, decided_at}}` — the validator's required fields are unchanged (`validate.py:958-970`) and `closed_review` preserves the closed verdict on the record, since `review_context` is current state and not history (`validate.py:380-382`) while the receipt, the `review_decided` event and the Jira comment remain the authorities; `lifecycle` observed at 10008 from the status passed in, exactly as `supersede_task` does (`:1736-1742`); and **`execution_profile.validation_route` recomputed to `policy.validation_route(characteristics)`** with provenance `{by: "system-policy", at, reset_after_peer_fail_without_executor: <recovery_ref>}`. Everything else — surfaces, work effort, characteristics, dependencies, profile — untouched.

**Why the route is recomputed, and why that is not a downgrade.** The stored `peer` was written by `reconcile_review_from_jira` as the `T-090`(d) raise, whose sole reason was that no SELF owner could exist without evidence. It is not a characteristic. The no-downgrade rule forbids a route weaker than the **policy floor** (`WORKFLOWS.md:465-469`; `store.py:381-386`), and the floor for both items is SELF (`shared_or_contended_surface: false`). Leaving `peer` in place would also break the next review outright: `enter_review` derives the route from characteristics through `route_for` (`validation.py:119-127`, `145-170`) and would transition to `Self-review`, while `open_review_context` reads the stored `validation_route` (`store.py:748`) and would open a PEER context — a Jira/context mismatch that `T-091`(d) 6 refuses at the next VALIDATE. `escalate` (`policy.py:186-198`) is not violated: it holds a route once *execution has started*, and no execution of either item has ever been witnessed. If `po` records a characteristic that requires PEER, policy raises it again through `set_characteristics`; nobody hands in a route.

**`WORKFLOWS.md` gains one row** under "Into / Moved by" after line 203: "**back to `Ready` from `Peer-review`, after a PEER FAIL on an item with NO owner and NO evidenced executor** — `po`, failed-review recovery, added 2026-09-21 (`T-092`). The transfer is the path whenever an executor is evidenced; this row exists only for the evidence-less items `T-090`(d) sent up." And one sentence under §PEER after line 539: "Where `executor_evidence` is empty the transfer has nothing to transfer from and is refused by construction; the item returns to `Ready` by `store.recover_failed_review_to_ready` (`T-092`)."

**Tests required.** `agent/state/tests` (the store's existing suite): each refusal above leaves the record byte-identical; the happy path on a KAN-288-shaped record nulls the context, records `closed_review`, observes 10008, resets the route to the floor and leaves `executor_evidence: []`; a record with one evidenced executor is refused (`executor-evidenced`); a SELF FAIL is refused; a stale revision is refused; `validate.py` passes on the result and `queue.unclaimable_reasons` on it returns `[]` for the KAN-288 shape and `['missing-work-effort']` for the KAN-303 shape (both verified on copies, 2026-09-21).

No schema change (`SCHEMA_VERSION` stays 3); no new authority (`po`/`ceo` are already the recovery authorities); no validator rule; no Listener intent — this is a `po` lifecycle act like `T-090`(d) steps 1-3, not a wake.

#### (d) Decision 3 — who executes, and the review that follows

**The reviewer is not barred and is not the natural executor.** §PEER makes the reviewer the executor *because it must not relay the defect back* to the developer (`WORKFLOWS.md:511-512, 531`); with no developer there is nobody to relay to, and the transfer is refused anyway. Once `Ready`, ownership is won the way every item wins it (`WORKFLOWS.md:214-218`): capability queue → eligibility → claimability → atomic `store.claim`. Eligible seats are the capability's declared seats (`validate.seats_by_capability()`, read 2026-09-21): KAN-288 any of `frontend-1` … `frontend-8`; KAN-303 `content-manager` or `content-2`. No exclusion applies: nobody executed, so there is no probable author to exclude. `frontend-8` and `content-2` may claim like any other seat; if one does, it then SELF-reviews its own execution, which is the ordinary SELF path and not a self-review of a peer verdict.

**The next review route is SELF, by the executor** — because the route is the floor after (c), and because the executor will be *evidenced* by `store.release` (`store.py:2893-2895`) at the end of the wake, which is what `T-090` said evidence must come from. The PEER findings (receipts `review:KAN-288:peer:1`, `review:KAN-303:peer:1`) are input to the executor's brief, not a verdict on the new work. If the CEO wants a second pair of eyes on the rework regardless of characteristics, that is a CEO-named PEER reviewer at the next review under MODEL C item 1, named through `store.resolve_review_owner` after `po` opens the context — not a route edit.

**Provider.** The CEO's "Claude, model Fable, effort low" is honoured at the wake seam (`execute_product_wake`, provider selection, authorised `provider_override`), and by nothing else. It changes no seat, no claim, no route.

#### (e) Decision 4 — re-validation before the blocker is formally cleared is refused, and "formally cleared" is a record state

A second `VALIDATE_WORK_ITEM` on either item is refused by construction today: `run_open_review` refuses `VALIDATION_ALREADY_SETTLED` on a context whose result is not `pending` (`T-091`(h) 7). Nobody submits it, and nobody reopens the context: `open_review_context` refuses a failed PEER context (`store.py:764-767`) and `record_review_result` refuses a settled one (`:1176-1179`). **The blocker is formally cleared when, and only when, the record reads all three of:** `review_context: null`, `execution_recovery.from_status: "10045"` with `closed_review.review_result: "fail"`, and `lifecycle.jira_status_id: "10008"` — the single write of (c). A Jira transition alone does not clear it (the store would still refuse the observation, `validate.py:393`); a Jira comment does not; a status-file line does not. The next validation of either item is a **new** context at cycle 1 on the SELF route, opened by `enter_review` + `open_context` inside the ordinary execute path after the wake returns — never a cycle 2 of the closed PEER context.

#### (f) The acts, in order

**`cto` — SYSTEM_MAINTENANCE, before any `po` act below.** Ticket and ship (c): the writer, the two `WORKFLOWS.md` edits, the tests. `SYSTEM_MAINTENANCE` cannot begin while an execution lease is open (none is, 2026-09-21).

**`po` — PRODUCT_EXECUTION, per item, once (c) is on `main`.**
1. Jira comment on the issue, first: the PEER FAIL (reviewer, cycle 1, receipt id, the finding verbatim or by reference), this entry, and that the item returns to `Ready` for rework with the finding as the brief. For KAN-303 the comment also states the corrected surfaces (`assets/documentation/foundations/{colour,type,spacing-geometry,motion,themes,bidirectionality}.md`, per KAN-293 `a33d7b8`).
2. `transitionJiraIssue` `Peer-review` → `Ready` (transition id `2`, `board.py:47`; every transition on this board is global). Read the status back.
3. `store.recover_failed_review_to_ready("KAN-288", <revision>, "<T-092; Jira comment id>", "po", "10008")`; same for KAN-303. Verify `python3 -m agent.state.validate` reports the store valid.
4. Update the acceptance criteria on the ticket only if the finding shows them wrong (`po` is the only writer of AC, `WORKFLOWS.md:268`); the KAN-288 AC already requires the built/partial/absent report the reviewer found missing, so it stands.

**Same-capability seat at Preflight — assessment, not claiming** (`CLAUDE.md`, "assessing is not claiming"): KAN-303 needs `store.set_surfaces` with the six current paths (`store.py:2001`) by a `content` seat, and a Work Effort by a `content` seat (`WORKFLOWS.md:274-276`); until both land it is unclaimable (`surfaces` stale is a wrong assessment, `missing-work-effort` is verified). How Work Effort is written to the store today has no dedicated writer that this ruling can cite — **not documented**; the KAN-288 provenance shows `po` wrote it on 2026-09-17 with a `basis_ref`. KAN-288 needs neither: `work_effort: 3` and `surfaces: ["lib/src/cards/"]` are on the record and the reviewer confirmed the missing components belong under that path.

**Orchestrator — PRODUCT_EXECUTION, per item, ordinary path.** `queue` derives eligibility and claimability; `store.claim` on behalf of an eligible seat (`store.py:2817`); `store.assert_execution_permitted` (`:2116`); then `python3 -m agent.listener submit <KAN> --wait`, with the provider override for Claude/Fable/low passed where the controller accepts it. The wake ends in `store.release`, `enter_review`, `open_context` (SELF, owner the evidenced executor) and the ordinary validation dispatch. Report refusals by their reason. **Do not** submit `validate` on either item before step 3 has landed, and do not call `peer_fail_transfer`, `open_review_context` or `resolve_review_owner` on them at all.

#### (g) What this does not do

It does not weaken `peer_fail_transfer`, the `previous_owner` carve-out, or the no-downgrade rule. It does not create evidence, name an executor, or reassign ownership. It does not touch the other 25 design-system items `po` moved to Done on 2026-09-21. It does not make PEER FAIL generally recoverable to `Ready`: with one evidenced executor the transfer remains the only path, and the new writer refuses that case by name.

**Consequence.** `cto` tickets (c) as SYSTEM_MAINTENANCE. `po` performs (f) 1-3 for KAN-288 and KAN-303 after it ships, and files the KAN-303 surface correction for a `content` seat's Preflight. The Orchestrator claims and dispatches through the Listener in the ordinary way, and reports the two items' claimability reasons until then.

**Status:** Accepted. Applies `T-090`(d) and `T-091`; extends `WORKFLOWS.md:203`; supersedes nothing.

### From dabbler-docs: T-093 — A SELF FAIL re-entry is a continuation the standing grant must admit for the SAME seat; and KAN-344's CI cannot see a design source that lives only in this workspace, so the four source-transcription tests skip when it is absent and the deterministic gate must resolve packages before it analyzes

**Date:** 2026-09-21 · **Seat:** `cto`. **Two concerns from the Orchestrator, both read against Thebes `main` `b6b1804` and `dabbler-design-system` `Canary` `9de494e`. No code edits, no Jira or store writes were made for this entry.**

#### A. KAN-292: the front door refuses the very continuation the doctrine mandates

**(a) The mechanism, cited.** `store.self_fail_reentry` re-establishes `ownership` on the exact `review_owner` and leaves `review_context` reading `fail` at cycle N (`agent/state/store.py:1340-1420`; the record for KAN-292 today: owner `frontend-2`, `review_type: self`, `review_result: fail`, `review_cycle: 1`, `lifecycle.canonical: development`, Jira `10046`, revision 15). `execute()` asks authorization first (`agent/controller/__init__.py:246-253`) and only then resolves the seat, where an existing owner is honoured as a continuation (`_resolve_seat`, `:1110-1123`; `claim_status: preserved`, `:293-297`). Under the standing grant, authorization is `ProductAuthorization.for_work_item` (`:124-160`) whose proof is `canonical_admissibility` (`:163-180`), which returns `queue.unclaimable_reasons(..., include_execution_gate=False)`. That predicate set is the CLAIM gate: it emits `not-ready` for any Jira status but Ready (`agent/state/queue.py:90-92`) and `already-owned` whenever `ownership` is set (`:266-267`). So a re-entered item is refused at the door by construction, and the continuation branch that would carry it is unreachable. `resume` handles only an APPROVED `needs_input` continuation (`:603-611`). The README's table promises "execution returns to the exact same seat, ownership re-established" (`agent/controller/README.md:189`) and no front door delivers it.

**(b) Ruling 1 — yes, admissibility must admit it, because the grant is being asked the wrong question.** The bounded grant exists to let canonical planning choose WHICH unowned item fills an envelope the CEO sized (`:100-118`). A SELF FAIL re-entry is not a selection: `self_fail_reentry` is documented as "NOT A CLAIM, AND NOT QUEUE COMPETITION" (`store.py:1353-1360`) and the owner is already fixed by evidence. Asking claimability whether an owner may keep going is precisely the conflation `CLAUDE.md` forbids ("Two different questions"). The right question for an owned item is the continuation gate, `execution_reasons` (`queue.py:320-346`), which is what `assert_execution_permitted` runs (`store.py:2244`) before every wake anyway. Releasing the claim to let the grant re-claim is refused as a workaround: `unclaimable_reasons` would then let any eligible `frontend` seat take it and the item would carry two evidenced executors.

**(c) Ruling 2 — the minimal change, SYSTEM_MAINTENANCE, one function.** In `canonical_admissibility.prove` (`agent/controller/__init__.py:163-180`), before calling `queue.unclaimable_reasons`, recognise a self-fail continuation and prove it with the continuation gate instead:

```
rc = task.get("review_context") or {}
own = task.get("ownership") or {}
if (rc.get("review_type") == "self" and rc.get("review_result") == "fail"
        and own.get("seat_id") and own["seat_id"] == rc.get("review_owner")
        and (task.get("lifecycle") or {}).get("canonical") == "development"
        and board.canonical_for(issue["status_id"]) == board.DEVELOPMENT):
    return list(queue.execution_reasons(task, own["seat_id"],
                                        interventions=state_store.active_interventions()))
```

All five conjuncts are required. `review_type == self` and `review_result == fail` name the only re-entry this covers (PEER FAIL is a transfer with its own writer, `store.py:1344-1345`; QA FAIL re-enters by ordinary claim and needs nothing here). `ownership.seat_id == review_owner` is the invariant `self_fail_reentry` asserts (`:1402-1405`), so an owner who is not the failed reviewer is still refused. `lifecycle.canonical == development` plus the live Jira status in the capability's execution status (the `board` lookup, never a hard-coded id, per `store.py:1369-1371`) proves the Orchestrator has already done its separate Jira act; a re-entered item still sitting in `Self-review` stays refused. `execution_reasons` keeps STOP effective (`task-stopped`) and keeps `not-owner`. `include_execution_gate=False` is preserved in the ordinary branch and the mode check is still `execute()`'s own (`:256-258`). The grant's quota is untouched: a continuation consumes nothing until the completion that already counts (`test_a_real_completion_consumes_exactly_one`).

It is `SYSTEM_MAINTENANCE` — it changes an authorization predicate in `agent/controller/`, not Product code — and it cannot begin while an execution lease is open. **Tests required, in `agent/controller/tests/test_standing_authorization.py` beside the existing grant tests (`:73-345`), gates in T-087's sense because each prevents a recurrence:** (1) a self-fail re-entered item owned by its review owner, in development, is authorized under the grant with `bounded-authorization`; (2) the same record with `ownership.seat_id != review_owner` is refused; (3) the same record with Jira still in `Self-review` is refused `not-ready`-equivalent; (4) a PEER-route fail is not admitted by this branch; (5) a STOP on the item refuses `task-stopped`; (6) the ordinary unowned path is unchanged and still returns `already-owned` for an owned Ready item, so claimability itself is not weakened. `queue.unclaimable_reasons` is not modified: claimability must keep answering `already-owned`.

**(d) Ruling 3 — the interim, today.** MODEL C item 2 applies: an explicit CEO authorization naming `frontend-2` on KAN-292 outranks the queue. The legitimate carrier is the exact-ticket path, not the bounded grant: `ProductAuthorization.for_work_item` honours `RoadmapAuthorization` first (`:124-126`), which is the CEO's exact-ticket record. If the roadmap carries a KAN-292 exact authorization naming `frontend-2`, `python3 -m agent.listener submit KAN-292 --wait` is the command, and `execute()` then takes the continuation branch on its own (`:293-297`) after the Orchestrator's `assert_execution_permitted("KAN-292", "frontend-2")`. How an exact-ticket authorization is written into the roadmap for a re-entry is **not documented** in the sources I read; the CEO records it, Thebes cannot (`:104-106`). `python3 -m agent.controller execute --maintenance-reason` is NOT an authorization: it bypasses only the Listener door (`agent/controller/__main__.py:6-7, 68-71`; `entry.py:44-52`) and still reaches the same `for_work_item` refusal, so it would not wake the seat and must not be used for this. No `release`, no `claim` by another seat, no hand edit under `agent/state/runtime/`.

#### B. KAN-344: the workflow is right and the runner cannot see the tests' source

**(e) The facts.** `.github/workflows/ci.yml` (`Canary` `aae79d4`) checks out, pins Flutter 3.44.1, runs `flutter pub get`, then the three checks as three named steps. The one real run (35532692731, `c80b52b`) is 1351 passed / 4 failed / 5 skipped; devops diagnosed it correctly (`agent/status/devops.md:1452`). The four failing `setUpAll` blocks assert the design source is present (`test/tokens/dabbler_palette_test.dart:57-63`, `dabbler_type_test.dart:83-86`, `design_source_export_transcription_test.dart:227-236`, `design_source_token_declarations_test.dart:183-188`) after walking up to eight parents looking for `dabbler-design-system-design/project` or `Dabbler/dabbler-design-system-design/project` (`..._transcription_test.dart:177-190`). `Dabbler/dabbler-design-system-design` is **not a git repository**: it has no `.git`, `git remote -v` inside it answers with Thebes' own remote, and Thebes' `.gitignore:1` (`/*`) ignores it. It has 374 files and no upstream. **Option (c), checking it out in CI, is unavailable — there is nothing to check out.**

**(f) Ruling 1 — option (a), skip-when-absent, with the guard shaped the way the package already does it.** `dabbler_geometry_test.dart:49-53, 106` already skips its source-backed group with `skip: source == null ? '...not found beside the package' : false`, and that file passed in the red run. Apply the same shape to the four files: locate the source at top level, wrap the source-backed groups with the `skip:` reason, keep the assertions unchanged. No `test/` file is added and no assertion is loosened, so T-087 is not engaged (the ruling forbids new unit tests; it says nothing about a skip condition on an existing gate) and KAN-344 AC6 ("no change to any of the three checks") is honoured in substance: the checks are the three commands, not each test's applicability. The CI run must then print the four skips by name so a reader sees the design source was absent, not that it passed. Option (b), vendoring `tokens/{colors,typography,spacing}.css` and the Figma export into the package, is refused: the Orchestrator's brief cites a 2026-09-21 CEO policy that the design folder is reference only and never enters code, assets or fallback — that policy is **not documented** in `DECISIONS.md`, `ROADMAP.md` or the status files I searched, so I rule on the narrower ground that a copy inside the package is a second source of truth the transcription tests exist to prevent. Option (d), moving the four tests out of CI, hides exactly what T-087(d) said was rotting. **AC change KAN-344 needs (`po` writes it):** AC6 gains one sentence — *"A test whose input is the design source, which exists only in the Thebes workspace and never on the runner, is skipped by name when that source is absent; skipping is reported in the run output, and the test itself is not altered."* AC5 then reads as a green run with four named skips. This is a `frontend` change in `test/tokens/`, not `devops`, so it is a separate executable item; KAN-344 stays with devops for the workflow and blocks on it.

**(g) Ruling 2 — the deterministic gate's `flutter analyze: 23739 issues found` is a missing `flutter pub get`, not the design source.** The artifact `agent/qa/runtime/artifacts/flutter_analyze-20260921T164120Z.log` runs `flutter analyze --no-pub --no-fatal-infos` with cwd the devops worktree; every error is `uri_does_not_exist` on `package:flutter/...` and `package:dabbler_design_system/...`. That worktree has no `.dart_tool/` and no `pubspec.lock`. `--no-pub` is correct as the CI mirror (`agent/qa/layers.py:63-68`) but nothing in `realize_workspace` (`agent/controller/workspace.py:69`) or the runner (`agent/qa/runner.py:49-100`) resolves packages, and the layer's precondition is only that `pubspec.yaml` exists (`layers.py:66`). The classifier fell through to `TEST_INFRASTRUCTURE_FAILURE` by default (`agent/qa/results.py:124`), which is the correct label. **Fix, SYSTEM_MAINTENANCE, `agent/qa/`:** add a package-resolution precondition for the two Flutter layers: when `pubspec.yaml` exists and `.dart_tool/package_config.json` does not, run `flutter pub get` in the workspace once before the layer (or add a `flutter_pub_get` layer the routing selects ahead of both) and record it in the artifact; failure of that step classifies as infrastructure. Add `uri_does_not_exist` to `INFRASTRUCTURE_SIGNATURES` (`results.py:60-74`) so the fall-through is named. The design source is irrelevant to `analyze`; it matters only to `flutter_unit`, where (f) applies identically in a worktree — the walk-up finds `Thebes-Canonical/Dabbler/dabbler-design-system-design/project` from `.claude/worktrees/product/devops/KAN-344`, four parents up, so locally those tests run rather than skip. One store correction for `po`: KAN-344's `surfaces` reads `github/workflows/ci.yml`; the path is `.github/workflows/ci.yml`.

**Consequence.** `cto` tickets (c) and (g) as `SYSTEM_MAINTENANCE`. `po` writes the AC6 sentence in (f), tickets the four-file skip guard as a `frontend` item KAN-344 blocks on, and corrects the KAN-344 surface. The CEO decides the interim in (d) for KAN-292; until (c) ships, the item is owned by `frontend-2`, correctly, and waits.

**Status:** Accepted. Applies `T-087`, `T-091`(h) and `T-092`; extends `README.md:189`; supersedes nothing.

### From dabbler-docs: T-094 — A surface is a BARE REPOSITORY-RELATIVE PATH, refused at write time, not at integration; `normalise_path` must strip a leading `./` SEQUENCE and never a character set; a trailing `/` attributes by prefix; and the repository marker comes from the project registry, not a two-item constant

**Ruling by `cto`, 2026-09-21, PRODUCT_EXECUTION. No code was changed by this entry.** `po` raised four cases (`agent/status/po.md`, "SURFACE-GRAMMAR QUESTION FOR cto"); `cto` re-verified each against the canonical checkout at `4ec4ad2` and found **the blast radius larger than reported in three of the four**. The defect class is one sentence: **surfaces are accepted loosely at Preflight and matched literally at integration**, so a malformed surface costs a wake and a completed review before anyone learns it was malformed.

**(a) Ruling — the store REFUSES a non-bare path at write time. Confirmed: nothing checks today.** `validate_surfaces` (`agent/state/validate.py:329-372`) checks exactly seven things — non-empty string, `MAX_REF_LEN`, not absolute, no backslash, no `..` segment, equal to its own `normalise_path`, not a duplicate. **There is no whitespace check, no parenthesis check and no glob check**, so `tool/ (possible new drift-class gate)` is a well-formed surface as far as the store is concerned. `set_surfaces` (`agent/state/store.py:2156`) does `sorted({policy.normalise_path(p) for p in surfaces})` and stores whatever comes back. The cost asymmetry `po` names is correct and decides it: a write-time refusal costs one retry by a seat that is standing at Preflight anyway; an integration-time refusal costs a claim, a wake, an execution and a passed review.

**This is live in ten tickets, not three.** Scanning every record under `agent/state/runtime/tasks/`, **14 stored surface entries across 10 tickets are not paths**: KAN-324 `test/ (new heading-vocabulary test)`; KAN-323, KAN-327, KAN-328 each `lib/src/gallery/ (…)`; KAN-329 `tool/check_doc_figures.dart (new)`, `assets/documentation/components/** (11 of the 19-figure files)`, `assets/documentation/foundations/** (interaction.md, type.md)`; KAN-330 `lib/src/gallery/gallery_page.dart (GalleryUsage/_spans)` and `lib/src/gallery/docs/doc_page.dart (possible ### block type)`; KAN-331 `lib/src/gallery/docs/ (new _order.md parser)` and `lib/main.dart (possible routing change)`; KAN-333 `lib/src/gallery/docs/doc_view.dart (_DocSection)`; KAN-334 `assets/documentation/patterns/** (31 files, 78 citation occurrences)`; KAN-295 `lib/src/**/*_gallery.dart (58 entries, 33 files)`. **Every one of these will fail attribution at integration.** Two forms are present and both are refused by this ruling: the parenthesised annotation, and the `**` glob — a glob is not a path and `attributed_changes` does no globbing. KAN-342 and KAN-332, the two `po` cited, have since been corrected in the store and now read `tool/check_order_bands.dart` and `tool/check_specimen_containment.dart`; the grammar hole that admitted them is unchanged.

**The predicate, and where it belongs.** One function, `policy.is_bare_surface(p)`, in `agent/state/policy.py` beside `normalise_path`, because policy is where the path grammar already lives and two callers must not each carry their own copy. A string is a bare surface when, after `normalise_path`, it is non-empty, and: contains no ASCII whitespace; contains none of `( ) [ ] { } * ? \ : ,` ; is not absolute and has no `..` segment; has no empty segment (`a//b`); is at most `MAX_REF_LEN`. A single trailing `/` is legal and means a directory, per (c); a trailing `/` is the only place a segment may be empty. **Both callers use it, for different jobs:** `store.set_surfaces` raises `StateError` before taking the lock, which is the gate that actually costs one retry, and `validate_surfaces` appends an error, which is what catches records written before this ruling. A refusal must quote the offending entry and say *"a surface is a bare repository-relative path; describe it in the ticket, not in the surface"* — the annotations above are all information that belonged in the Jira description.

**(b) The leading dot — `po`'s diagnosis is CONFIRMED by reading the line, and it is a plain bug.** `agent/state/policy.py:121` reads `p = str(p).strip().lstrip("./")`. `str.lstrip` takes a **character set**, not a prefix: it removes every leading character that is `.` or `/`, so `.github/workflows/ci.yml` becomes `github/workflows/ci.yml` and `.gitignore` becomes `gitignore`. `validate.py:369` then requires the stored value to equal `normalise_path` of itself, which means **the true path can never be held in the store** — writing `.github/workflows/ci.yml` normalises away the dot, and writing it back with the dot fails validation. `set_surfaces` accepted KAN-344's dotted input silently, value changed, no error, which is exactly what `po` observed.

**Fix:** strip a leading `./` **sequence** only — `while p.startswith("./"): p = p[2:]` — then `p.strip()`. The validator's expected form is then the dot-preserving path, so `.github/workflows/ci.yml` and `.gitignore` become the storable and required forms.

**Migration is required and the records are named.** **Four stored surfaces across four tickets hold a wrongly-stripped value:** KAN-344 `github/workflows/ci.yml`, KAN-175 `github/workflows/anon-allowlist-check.yml`, KAN-194 `github/workflows/anon-allowlist-check.yml`, KAN-166 `gitignore`. Each must be rewritten with its leading dot restored. KAN-175 and KAN-194 are already `DONE`, so their correction is a record repair, not a re-integration; KAN-344 is live and its correction is the one `T-093`(g) already asked `po` to make.

**(c) Directory-versus-file — today a trailing `/` attributes NOTHING, and this is about to break KAN-292.** `attributed_changes` (`agent/controller/integration.py:100-118`) computes `undeclared = sorted(set(actual) - set(declared))` — an **exact string set difference**. `actual` comes from `worktrees.changed_files` (`agent/state/worktrees.py:217-242`), which returns `git status --porcelain` paths and, deliberately, **expands an untracked directory into its files** (`:236-239`). So `actual` never contains a trailing-slash entry, and a declared `lib/src/navigation/` matches nothing at all. KAN-292 and KAN-346 each declare the same five directories — `lib/src/navigation/`, `lib/src/overlays/`, `lib/src/feedback/`, `lib/src/layout/`, `lib/src/calendar/` — and KAN-292's integration must attribute `lib/src/navigation/tab_bar.dart`. **As the code stands it will refuse with `ATTRIBUTION_FAILED` after a passed review.**

**Ruling: attribution is by file, and a declared entry ending in `/` covers every file beneath it.** A directory declaration is the honest unit for work whose file list is not knowable at Preflight — a new widget set, a new screen — and forcing a file list there would force `po` to invent filenames, which is the same failure `surfaces: null` exists to prevent. The change is a covering test in place of set difference: an actual path is attributed when it equals a declared entry, or when some declared entry ends in `/` and the actual path starts with it. Nothing else moves: `derive_contended` (`policy.py:133-141`) already matches `SHARED_PREFIXES` by `startswith`, so a directory surface widens contention exactly as it should, and `worktrees.assert_attribution` (`:245`) must take the same covering test rather than its own comparison.

**A directory is not a licence.** A trailing `/` on its own — a bare `/`, or `lib/` for a whole source tree — is too coarse to attribute anything meaningfully; a declared directory must have at least two segments. That is part of the (a) predicate.

**(d) Repository markers — make the list per-project from the registry. The hardcoded pair is wrong for three of the four projects.** `normalise_path` strips only `dabbler-code/` and `webapp/` (`policy.py:123`). The Product registry already holds the answer: `agent/state/registry/products/dabbler/projects/*.json` each carry a `repository` field — `Dabbler/dabbler-code` (app), `Dabbler/dabbler-design-system` (design-system), `Dabbler/dabbler-admin` (admin), `Dabbler/dabbler-web` (web). **Three of those four have no marker**, so a design-system, admin or web seat that writes a workspace-relative path stores a string `changed_files` can never produce. It is already in the store for the governance repository: KAN-190 declares `Dabbler/dabbler-docs/DECISIONS.md`.

`normalise_path` therefore takes an optional marker tuple, and `set_surfaces` and `validate_surfaces` pass the markers derived from the record's `project_id`. `webapp/` stays as a legacy alias for the app project and `dabbler-docs/` is added as a system marker available to every project, since governance edits are cross-project. **Adding two more constants would have been the cheaper answer and it is the wrong one** — it would be wrong again the next time a project is registered, and the registry is already authoritative for exactly this fact.

**Ticketable brief for `po` — SYSTEM_MAINTENANCE, `required_capability: cto`.** Four executable children under one non-executable parent, because (b) and (d) both change `normalise_path` and must not be two seats: **(1)** `policy.is_bare_surface` plus the `./`-sequence fix plus registry-derived markers in `policy.py`; **(2)** refusal wiring in `store.set_surfaces` and `validate.validate_surfaces`; **(3)** prefix attribution in `integration.attributed_changes` and `worktrees.assert_attribution`; **(4)** the record migration for the four dot-stripped surfaces and the fourteen annotated ones. Surfaces for (1)-(3) are `agent/state/policy.py`, `agent/state/store.py`, `agent/state/validate.py`, `agent/controller/integration.py`, `agent/state/worktrees.py` and `agent/tests/`; (4) declares `agent/state/runtime/tasks/` and is a store write, not a code change. **One test per case:** an annotated surface and a `**` glob are both refused by `set_surfaces` with the entry quoted; `.github/workflows/ci.yml` and `.gitignore` survive `normalise_path` unchanged and validate; `attributed_changes` accepts `lib/src/navigation/tab_bar.dart` against a declared `lib/src/navigation/` and still refuses `lib/src/other/x.dart`; a design-system path written as `Dabbler/dabbler-design-system/lib/src/x.dart` normalises to `lib/src/x.dart` under that project and is left alone under the app project. **Work Effort: `M` for (1) and (3), `S` for (2) and (4)** — the logic is small and the test surface is the cost. **(3) is the one that blocks KAN-292's integration and should be sequenced first if they are not taken together.**

**Status:** Accepted. Extends `T-093`(g), which named the KAN-344 surface correction without ruling the grammar; supersedes nothing.

### From dabbler-docs: T-095 — A validation workspace must be CURRENT with the integration branch, and the T-091 open-review path silently reuses the executor's stale tree; `self_fail_reentry`'s `already-owned` refusal is correct and the defect is that an open review may be dispatched on an item that still has an owner

**Concern raised by `cto` relaying `po`, 2026-09-21. Every claim below re-verified at Thebes `main` `4ec4ad2` and at `dabbler-design-system` `Canary` `9d47652`.**

**(a) The mechanism is confirmed. `worktrees.allocate` never re-bases a worktree it reuses.** `agent/state/worktrees.py:136-141`: if the path exists and is registered, the function returns immediately with `reused: True`, `base_commit` set to the worktree's CURRENT head and the `base` argument echoed back untouched. The "created FROM the integration branch" contract in its own docstring (`:123-124`) holds only on the `worktree add` path (`:146-150`), i.e. at FIRST allocation. `T-091`'s statement that a validation workspace is allocated "from the integration branch" is therefore true only for a reviewer who has never held one. `agent/controller/workspace.py:112-117` already says reuse is "correct for a same-seat continuation and wrong for anything else" — but `assert_isolated_identity` checks identity, never currency.

**(b) On the SELF route the reviewer IS the executor, so the open-review path reuses the executor's tree BY CONSTRUCTION.** `agent/controller/__init__.py:634-635` calls `workspace_allocator(work_item_id, reviewer, mapping)`; `worktree_path(seat, item)` for a SELF reviewer resolves to the executor's existing worktree, which `release_decision` deliberately PRESERVES for exactly these routes (`agent/controller/workspace.py:195-196`). Reuse is therefore the normal case, not the edge case. The receipt then compounds it: `:664-666` builds `receipt_ref = "integration:<branch>@<revision>"` from whatever came back, so a verdict on `exec/frontend-1/KAN-219@58cd8b8` is filed under the word `integration`. **The label is false and the reviewer has no way to see that it is.**

**(c) KAN-219's cycle-2 FAIL did read the pre-rework tree.** `.claude/worktrees/product/frontend-1/KAN-219` stands at `58cd8b8` on `exec/frontend-1/KAN-219`, **68 commits behind `Canary`**, with `lib/src/tokens/dabbler_colors.dart`, `lib/src/tokens/dabbler_dark_provisional.dart`, `test/tokens/dabbler_colors_test.dart` and `test/tokens/dark_provisional_isolation_test.dart` all still UNTRACKED — the state of 2026-09-17. The committed work is `7834709`, carried through `2f4ae58`.

**(d) But the FAIL is half stale and half live, and this correction matters more than the rule.** At `Canary` HEAD, light `textSecondary` resolves to `DabblerPalette.inkSoft` citing `D-003(a)` in the code (`lib/src/tokens/dabbler_colors.dart:344-349`) and `dabbler_colors_test.dart:375-390` asserts it clears 4.5:1 on all six paper surfaces — that half of the verdict is superseded. **Light `textTertiary` still resolves to `DabblerPalette.muted`** (`:350-351`), and `dabbler_colors_test.dart:340-372` still PINS six ink-on-surface measurements between **1.64:1 and 3.36:1** with `lessThan(4.5)`, under a comment headed `OPEN AGAINST AC6`. The reviewer's structural objection — the test encodes the shortfall instead of asserting the criterion — survives the rework for the tertiary role. **A cycle-3 review against a current tree is required work, not a formality.**

**RULING (1) — the two cases are different and must be separated explicitly.**

**Execution-time review** (`run_validation`, the tail of an execution this process woke): the thing under review IS the executor's worktree including its uncommitted work. It must NOT be re-based, re-allocated or cleaned. "Fresh" has no meaning here; currency was the executor's problem at execution time, and touching that tree would destroy the artefact being judged. Unchanged.

**Open review** (`run_open_review` via `controller.validate`, work already carried on the integration branch): the reviewer is judging what the branch says, so **the tree it reads must equal the integration branch tip at allocation time, and must carry no uncommitted work.** A reused tree that is behind is not a workspace, it is a different version of the Product. This is the case that broke.

**RULING (2) — the exact minimal change. Four edits, one of them a string. SYSTEM_MAINTENANCE, `required_capability: cto`.**

- **(i)** `agent/state/worktrees.py` — `allocate` gains `require_base=False`. When true and the worktree is reused: if it is DIRTY, raise `WorktreeError("stale-workspace: ...")` naming the head, the base tip and the dirty paths; if it is CLEAN and behind, fast-forward it to the base tip (`git merge --ff-only`, never a merge or a rebase) and return `rebased_to` in the allocation. A tree that cannot fast-forward is a refusal, never a reset.
- **(ii)** `agent/controller/workspace.py` — `realize_workspace` passes `require_base` through and maps the refusal to `WorkspaceUnavailable("workspace-stale-for-validation", ...)`, carrying `rebased_to` into the realized mapping.
- **(iii)** `agent/controller/__init__.py:635` — `validate()` alone passes `require_base=True` with the integration branch as base. `execute()` and `integrate()` never do.
- **(iv)** `agent/controller/__init__.py:664-666` — the receipt reference stops asserting what it has not checked: `"tree:<branch>@<revision>"`, and the `integration:` prefix only when the branch IS the integration branch.

**No auto-repair beyond a fast-forward.** A stale dirty tree is a blocker the Orchestrator sees with a structured reason, in the doctrine of *unclaimable is an answer*. Silently rebasing or discarding a seat's uncommitted work to make a review runnable is the one outcome worse than the stale read.

**RULING (3) — the audit of today's verdicts. One other stale read, not as unsafe; one unverifiable.** PEER and QA reviews allocate against a reviewer-seat path that usually does not yet exist, so they base off `Canary` and are not exposed. The SELF verdicts of 2026-09-21 were checked by comparing each verdict's own cited revision against `Canary`'s commit timestamps (`Canary` tips that day: `2c22f03` 00:16, then `fb33948`/`409ce44` 20:31, `23baa9a` 20:33, `9de494e` 20:34, `098371a` 20:51, `3b08b89` 21:10, `9d47652` 21:17, all +04:00):

- **Current or self-consistent, no defect found:** KAN-317 and KAN-342 (`9de494e`, the tip), KAN-332 (`3b08b89`, the tip), KAN-344 (`aae79d4` shown as an ancestor of the then-tip `9de494e`), KAN-327 (`2c22f03`, the tip at 14:43), KAN-345, KAN-288 and KAN-291 (each reading its own exec branch, which carried the work under review), KAN-292 (which explicitly reconciled its head `cd02a5b` against the expected `1fb8ba0` in the verdict itself).
- **KAN-290 — stale, but not shown wrong.** Reviewed at 20:32 on `exec/frontend-2/KAN-290@2c22f03`, roughly twenty hours and at least four commits behind `Canary`. The verdict's reasoning is confined to `lib/src/forms/`, and the newest forms commit (`c1172d1`) is present at that revision, so I cannot demonstrate the PASS is wrong. **It is still a verdict that did not know what branch it was on, and its receipt says `integration:`.**
- **KAN-303 — not documented.** `content-2`'s worktree has been released and the verdict cites no revision, so which tree it read is not recoverable from the record. That is itself an argument for (iv).

**No PASS recorded today is as unsafe as KAN-219's FAIL was.** The asymmetry is structural, not luck: a stale tree lacks LATER work, so it tends to fail work that has since been fixed rather than pass work that has since broken. That is not a reason to leave it — a stale PASS becomes possible the moment a review depends on a fix landed by another ticket.

**RULING (4) — KAN-219. Run cycle 3 against a correct tree; the cycle-2 FAIL is not discarded.** There is no canonical way to discard a review cycle and there should not be: `open_review_context` increments only FROM a recorded fail (`agent/state/store.py:721-726`), and `self_fail_reentry` states the reason in terms (`:1362-1367`) — erasing a failure makes a failed review indistinguishable from one that never happened. Nor is the premise for a discard sound, per **(d)**: the tertiary-role objection survives at HEAD. The correct act is the ordinary rework loop — release, re-enter, fix the `textTertiary` half or obtain a criterion amendment from `cxo` (the code comment's large-text carve-out is a change to AC6, not satisfaction of it), then cycle 3 against a current tree. **If cycle 3 also fails, `MAX_REVIEW_CYCLES` is exhausted and that is a CEO escalation, not something to engineer around.**

**RULING (5) — CONCERN B. `self_fail_reentry` must NOT become idempotent.** The predicate is `already-owned` (`agent/state/store.py:1406-1409`) and it is correct as written. An item in review has no owner by construction, because **`release` is the only act that mints executor evidence** (`:3021-3023`), and SELF's owner is derived from that evidence. Making re-entry tolerate an existing owner would let an item be re-entered without ever having released, leaving SELF ownership self-certifying.

**The defect is upstream, and KAN-219's record shows it exactly.** Its `ownership.claim_ref` is the CYCLE-1 fail verdict, claimed `2026-09-17T03:46:45Z` — a completed re-entry whose owner then did the rework and went back to `Self-review` **without ever releasing**. The canonical path releases first (`agent/controller/validation.py:145-157`, `enter_review`); the T-091 open-review path deliberately does not (`:753-756`, "there is no ownership to release"); and `store.open_review_context` does not check ownership at all (`:699-760`). So a review can be opened, and dispatched, on an owned item.

**Minimal repair:** `open_review_context` refuses with `owner-not-released` when `cur.get("ownership")` is not None, naming the owner and pointing at `release`. One predicate, one place, `agent/state/store.py`. SYSTEM_MAINTENANCE, `required_capability: cto`.

**KAN-219 needs no new code to unstick.** `store.release("KAN-219", "frontend-1", <current revision>, "<cycle-2 verdict ref>", authority="orchestrator")` is legal today — the owner releasing is always permitted and is the documented way out of a stuck ownership — and it appends the cycle-2 evidence rather than discarding it. `self_fail_reentry` then admits the re-entry normally.

**Ticketable brief for `po` — SYSTEM_MAINTENANCE, `required_capability: cto`.** One non-executable parent, three executable children: **(1)** `require_base` in `allocate` plus the `realize_workspace` passthrough — surfaces `agent/state/worktrees.py`, `agent/controller/workspace.py`, `agent/state/tests/`, **Work Effort M**; **(2)** `validate()` passes it, and the receipt-reference wording — surface `agent/controller/__init__.py` and its tests, **Work Effort S**; **(3)** the `owner-not-released` refusal in `open_review_context` — surface `agent/state/store.py` and its tests, **Work Effort S**. **Tests, one per case:** a reused CLEAN worktree behind the base is fast-forwarded and reports `rebased_to`; a reused DIRTY worktree behind the base raises `workspace-stale-for-validation` and names its dirty paths; `execute()` still reuses a stale tree untouched; a receipt for a non-integration branch does not carry the `integration:` prefix; `open_review_context` refuses an owned item and accepts the same item after `release`. **(3) is independent of (1) and (2) and unblocks the KAN-219 loop, so sequence it first if they are not taken together.**

**Status:** Accepted. Corrects the scope of `T-091`'s workspace statement, which is true only at first allocation; extends `T-093`'s re-entry admissibility by locating the KAN-219 refusal upstream of the predicate it fired in; supersedes nothing.

### From dabbler-docs: T-096 — Integration lands the RANGE `<integration-branch>..HEAD` in order, one commit per wake, all-or-nothing under one lock; it never squashes, and the range's UNION of changed files is what attribution checks

**Raised by `cto`, 2026-09-21, on KAN-292 — SELF review PASSED at cycle 3, the last, and integration refuses. Verified at Thebes `main` `4ec4ad2`, `dabbler-design-system` `Canary` `9d47652`.**

**(a) The facts hold.** `exec/frontend-2/KAN-292` carries three commits, one per wake: `1fb8ba0` "port the missing NavigationTabBar" (20:46), `cd02a5b` "correct the Divider label's D-003 rationale" (21:04), `0275c00` "the tab bar drew 47 tall against a specimen that draws 49" (21:30). `integration.unintegrated_commit` (`agent/controller/integration.py:147-153`) runs `rev-list --max-count=1 <branch>..HEAD` and returns **only the newest**, so `_integrate_once` offers `0275c00` alone. `0275c00` MODIFIES `lib/src/navigation/tab_bar.dart`; `1fb8ba0` CREATES it; `Canary` has never had the file. The cherry-pick therefore conflicts, correctly, and `Canary` is untouched.

**(b) "One work item, one commit" is nowhere stated as a rule.** It survives as an unexamined assumption in two docstrings — `unintegrated_commit`'s "the newest commit" and `worktrees.integrate`'s "Land ONE task's commit" (`agent/state/worktrees.py:316`) — and `worktrees.py:40`'s "one lock, one commit onto Canary at a time" is about SERIALIZATION, not about how many commits a work item may have. Every item integrated before today carried one commit, so the assumption was never tested. **It is wrong.** A work item gets as many wakes as its review cycles and its `needs_input` continuations require, and each wake that changes the Product commits its own work in its own worktree. Requiring one commit per item would mean either forbidding a second wake from committing — which loses the work on the next failure — or rewriting the seat's history at integration time.

**RULING (1) — the range, in order, never a squash.** Integration cherry-picks every commit in `<integration-branch>..HEAD` oldest-first, preserving each commit and the message its wake wrote. Four reasons, the first decisive:

- **Idempotency is implemented per-sha and a squash destroys it.** `worktrees.integrate` detects an already-landed commit two ways: direct ancestry (`agent/state/worktrees.py:354-356`) and the `-x` trailer `cherry picked from commit <sha>` (`:357-362`). Both key on the SOURCE sha. A squash produces a synthetic commit whose trailer names nothing, so a retry after a partial or failed landing could not tell what was already on the branch and would re-apply it. With a range, a resumed integration knows exactly which commits are present and lands only the remainder. **Fail-closed retry is the property that must not be traded.**
- **Each commit is a wake's evidence, and the record already cites shas.** KAN-292's own cycle-2 verdict reconciles head `cd02a5b` against the expected `1fb8ba0` by name. Squashing invalidates every such citation retroactively.
- **A squash needs an author and a message for a commit no seat wrote.** `commit_message` (`integration.py:121-132`) would emit one `type(KEY): summary` line from the Jira summary and discard three seat-authored messages. That is fabricated authorship, and it is the same class of defect the attribution rules exist to prevent.
- **Atomicity, the only real argument for a squash, is solvable without one.** One lock, and on any failure `reset --hard` to the head the attempt started from — exactly the rollback the gate-failure path already performs (`worktrees.py:383-390`). `Canary` stays all-or-nothing, which is what "the branch is untouched" means today and must keep meaning.

**RULING (2) — what the range does to the three things named.**

- **Attribution.** The unit becomes the **union of files changed across the range**, computed as `diff --name-only <branch>..<newest>` in the seat's worktree — the NET change, so a file created in one commit and modified in another counts once. This is stricter than today and deliberately so: a per-commit check would let a range land files the item never declared as long as no single commit looked wrong. **It has an immediate consequence for KAN-292, in (5).**
- **`verify_integration` (`integration.py:155-173`).** Its missing-file check reads `show --name-only` of ONE landed sha and must become `diff --name-only <previous_head>..<branch>`, and the ancestry assertion must run over every landed sha, not just the last. Left as it is, a range would verify only its final commit and report a clean landing for a range whose earlier commits were silently dropped.
- **The receipt's `product_commit`.** It keeps naming exactly one sha — **the NEWEST source commit**, the tip the branch offered — so every existing reader keeps working. A new `product_commits` list carries the full range in order, and `integrated_as` keeps naming the final landed sha on the integration branch. Adding a list beside the scalar is what makes this change compatible; redefining the scalar would break every receipt already written.

**RULING (3) — the exact minimal change. SYSTEM_MAINTENANCE, `required_capability: cto`.**

- **(i)** `agent/controller/integration.py` — `unintegrated_commit` becomes `unintegrated_commits(worktree_path, branch)`, returning `rev-list --reverse <branch>..HEAD` as an ordered tuple, oldest first. It has exactly one caller (`:200`).
- **(ii)** `agent/state/worktrees.py` — `integrate` takes an ordered SEQUENCE in place of a single `expected_commit`. Inside the one existing lock: for each sha, skip it if ancestry or the `-x` trailer already places it on the branch; otherwise cherry-pick `-x`. **On any conflict, `reset --hard` to the head the attempt started from before raising**, so the branch is where it began, and name the offending sha alongside its conflicting paths. Gates run ONCE after the whole sequence, with the same rollback. Return `integrated_as` (final landed sha), `previous_head`, and `integrated_shas` mapping source to landed.
- **(iii)** `agent/controller/integration.py:198-215` — `pending` becomes the list; the clean-tree branch sets `attributed_files` to the range's net union; evidence gains `product_commits` and keeps `product_commit` as the newest source sha.
- **(iv)** `agent/controller/integration.py:155-173` — `verify_integration` reads landed files from `diff --name-only <previous_head>..<branch>` and asserts ancestry for every landed sha.

**Tests, one per case.** A two-commit branch whose second commit modifies a file the first creates lands both, in order, and `Canary` ends with both messages. A range whose MIDDLE commit conflicts leaves the branch byte-identical to `previous_head` and reports that sha with its paths. A re-run after a partial landing lands only the remainder and reports the rest already-present via the `-x` trailer. A single-commit branch behaves exactly as it does today, including `product_commit`. `verify_integration` refuses a range that lost a file. A range whose union includes an undeclared file is refused as `ATTRIBUTION_FAILED` and names that file.

**RULING (4) — sequencing, for one seat in one pass.** All of these touch two files between them, so they are serial, not parallel: **`T-094`'s KAN-348 (prefix attribution) first** — it edits `integration.attributed_changes` and `worktrees.assert_attribution`, and directory surfaces like KAN-292's five do not attribute at all without it; **then this ticket** (same two files); **then `T-095`(1) and (2)** — (1) also edits `agent/state/worktrees.py`, so it must not be concurrent with (ii) above. **`T-095`(3)** is `agent/state/store.py` alone and is independent of all of them; take it whenever. Surface contention here is real and is the reason for the order, not caution.

**RULING (5) — can KAN-292 integrate TODAY, without the code change? No, on two independent grounds, and the second does not go away when the code lands.**

**First, there is no front door that could name an older commit.** The Listener's allow-list is `EXECUTE_WORK_ITEM`, `VALIDATE_WORK_ITEM` and `DECISION_RESPONSE` (`agent/listener/contract.py:22-33, 50-56`); no intent carries a commit selector, and integration runs only as a tail inside the seam. Every route around that is refused here: squashing the exec branch with a `reset --soft` in the seat's worktree fabricates a commit no wake produced and destroys three real messages; the `source_repo` recovery parameter changes where a commit is READ from and still lands exactly one sha (`worktrees.py:330-335`); there is no fast-forward path; and nothing may rewrite `Canary`. **It waits for the build, which can start now.**

**Second, and this is new information: KAN-292's declared surfaces do not cover its own change.** The item declares `lib/src/navigation/`, `lib/src/overlays/`, `lib/src/feedback/`, `lib/src/layout/`, `lib/src/calendar/`. `1fb8ba0` also modifies **`lib/dabbler_design_system.dart`**, the package barrel — necessarily, since it exports a newly ported component — and that file is under none of the five, nor under any prefix of them once KAN-348 lands. Today this is invisible because the worktree is clean, so `integrate_validated_work` takes the branch at `:198-207` that never re-checks attribution. Under RULING (2) it becomes a refusal, correctly. **So KAN-292 needs `po` to extend its surfaces before it can land.** That is a factual pre-execution assessment act and it belongs to `po` — the Orchestrator must not invent the path, and neither must `cto`. It is a single store write and can be done when `po` returns.

**Status:** Accepted. Retires the undocumented "one work item, one commit" assumption; depends on `T-094`'s KAN-348 for directory-surface attribution; sequenced against `T-095`(1) by shared surface. Supersedes nothing.
