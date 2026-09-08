# agent/WORKFLOWS.md — Workflows and Handoffs

**Owner:** `po` (write) · all agents (read) — moved from `analyst` 2026-09-06, `G-022`
**Last updated:** 2026-09-06 — W1 corrected: `Development` is a real column, not a dropped
one (see below); ownership table given its `Development` row and `Done` corrected to `qa`.
§2's column line changed from restating the column list to citing §1's table, after the
restatement went stale there while §1 was fixed — one fact, one place, from here on.
Previously: 2026-09-05, W6 added (regeneration), W1 amended to match.
**Purpose:** The procedure. `AGENTS.md` carries the shape of the roster; this carries how
a task that crosses two or three agents actually moves, end to end.

---

## 1. THE TASK LIFECYCLE

**Jira is the single source of truth for progress.** Not the terminal, not an agent's
final message, not this repo. If the board does not show it, it did not happen.

```
CEO request
   → Epic (the container — NOT executable)
      → child Tasks (the trackable, executable units)
         → Backlog → Ready → ONE execution status → ONE review status → Done
```

### One executable work item = one required capability

**Settled 2026-09-08.** An executable work item carries **exactly one** `required_capability`,
and that one fact decides four things: its execution status, its valid PEER reviewer, who
holds execution authority, and its future Wave 6 capability queue.

**The five execution statuses are ALTERNATIVES, never a sequence.** A work item enters
exactly one of them and returns to the same one after a review failure. Nothing traverses two.

| Capability | Execution status (id) | Board column |
|---|---|---|
| `frontend` | **`Front-end`** (10046) | Frontend Development |
| `backend` | **`Back-end`** (10043) | Backend Development |
| `content` | **`Content`** (10048) | Operations |
| `product-designer` · `ux-engineer` | **`Design`** (10047) | Operations |
| `devops` · `analyst` · any other shared specialist | **`Operations`** (10049) | Operations |
| `qa` | **none** — QA is a **validation route**, not an execution lane | — |

**`Design`, `Content` and `Operations` are three separate statuses grouped into one column.**
They are specialist lanes, not stages: nothing flows `Design → Content → Operations`. Content
work goes to `Content` and design work to `Design` — **they are not collapsed into a generic
status**, because the board now names them separately.

Work that genuinely needs two capabilities is **split into two executable children under a
non-executable parent**, each with its own capability-scoped acceptance criteria, Work Effort,
lifecycle and validation. It is not run as one item, because one item cannot occupy two
statuses. **Do not copy a mixed parent's criteria into both children** — `po` writes only the
capability-relevant criteria for each.

**Epics, split parents and coordination items are containers.** They may span capabilities and
they carry **no** capability, Work Effort, validation route or review context. **A parent is
not executable merely because its children are.**

### How work reaches a seat — capability queues and claim

**Wave 6, 2026-09-08.** Ready work is discoverable through a **capability queue**, and the queue
key is the item's `required_capability`. Not the hierarchy, not a lead, not the frontend/backend
pair, not a manager's routing.

```
PO selects into Ready
   → capability queue      → eligibility → claimability → ATOMIC CLAIM → ownership → WAKE
```

**READY IS NOT CLAIMABLE.** Ready means selected and prepared — the five facts below.
**Claimable** means every execution prerequisite holds *right now*:

| Claimability requires | Reason code when it fails |
|---|---|
| queue-eligible (the five Ready facts) | `not-ready` · `missing-project` · `missing-capability` · `missing-work-effort` · `missing-due-date` · `missing-acceptance-criteria` |
| nobody owns it | `already-owned` |
| no incoming `BLOCKS` edge whose source is short of `DONE` | `dependency-blocked` |
| no active STOP on it, HOLD on its capability, or FREEZE | `task-stopped` · `capability-held` · `system-frozen` |
| no declared-surface collision with work already owned | `surface-contention` |
| exactly one evidenced executor, or none | `conflicting-evidence` |
| a fresh Jira read backs the commit | `stale-jira` |

**An item can sit in Ready for days and never be claimable, and that is a correct state.**
Report the reasons; do not route around them.

**CLAIM and WAKE are different acts, in that order.** A claim is a Persistent State operation
that durably establishes ownership — compare-and-swap inside a file lock, exactly one winner. A
wake is a harness invocation. **A wake creates no ownership**, and no seat is woken for ordinary
work before its claim has succeeded.

**Nothing is assigned.** There is no lead to assign it, and the CEO does not name an executor
for ordinary work. Where evidence conflicts — two or more evidenced seats — the item **blocks
and requires reconciliation**; it does not fall back to anyone choosing.

**Watching this happen is not doing it.** Agent View (`agent/scripts/flow.py`) renders queues,
claimability reasons, ownership and interventions read-only. It never claims, wakes, releases,
transitions, assigns a reviewer or clears an intervention — every one of those runs through the
canonical path above. A queue shown there is a report, not a control.

### A COLUMN IS NOT A STATUS

**This is the single most important thing to understand about the current board.** Two columns
deliberately group several statuses, so one Jira column no longer means one Jira status:

- **`Operations`** holds `Design`, `Content` and `Operations` — three execution lanes.
- **`Review`** holds `QA-Test`, `Self-review` and `Peer-review` — three validation routes.

A lifecycle observation therefore records **three separate facts**, and none of them derives
the other two:

```
jira_column   = "Review"        <- what the board shows
jira_status   = "Peer-review"   <- which validation route is active
canonical     = "review"        <- the lifecycle state Thebes reasons in
```

### Eleven live statuses, seven columns, four canonical states

Jira has exactly three `statusCategory` values and the columns live inside them. Thebes reasons
in **four canonical states**, derived from the status **id** — never from the name, because
names change and ids do not. **The board model is machine-readable in `agent/state/board.py`;
that file is the single source, and this table describes it.**

| Column | Status (exact name) | id | transition | Canonical |
|---|---|---|---|---|
| **Backlog** | `To Do` | 10004 | `11` | **READY** |
| **Ready** | `Ready` | 10008 | `2` | **READY** |
| **Operations** | `Design` | 10047 | `9` | **DEVELOPMENT** |
| **Operations** | `Content` | 10048 | `10` | **DEVELOPMENT** |
| **Operations** | `Operations` | 10049 | `12` | **DEVELOPMENT** |
| **Frontend Development** | `Front-end` | 10046 | `8` | **DEVELOPMENT** |
| **Backend Development** | `Back-end` | 10043 | `5` | **DEVELOPMENT** |
| **Review** | `QA-Test` | 10009 | `3` | **REVIEW** |
| **Review** | `Self-review` | 10044 | `6` | **REVIEW** |
| **Review** | `Peer-review` | 10045 | `7` | **REVIEW** |
| **Done** | `Done` | 10007 | `41` | **DONE** |

**Read the ids back before calling** (`G-018`).

> **Two spellings that will bite you if you type them from memory.** The review statuses are
> **`Self-review`** and **`Peer-review`** with a **lowercase r**. And the first column is
> called *Backlog* but the status inside it is still **`To Do`** — there is no status named
> "Backlog". Both were verified against a live read on 2026-09-08.

> **THREE LEGACY STATUSES STILL EXIST AND ARE NOT BOARD TARGETS.** `In Progress` (10005),
> `Development` (10010) and `In Review` (10006) were not deleted when the new statuses were
> added. **Never transition new work into them.** They stay mapped for one reason: every
> historical changelog entry names them, and Sprint reconstruction replays that history. A
> record observed on one of them is a WARNING, not an error — it is a migration state, not a
> corrupt one.
>
> **The guard is `board.assert_transition_target()`, and it is enforced, not advisory.**
> `board.canonical_for()` accepts a legacy id so history stays readable;
> `assert_transition_target()` refuses it as a destination. **Every transition on this board is
> global and unconditional, so Jira itself will happily accept a legacy target — nothing but
> this guard stops it.** That is not hypothetical: seven executable issues were found parked in
> `Development` and `In Review` after the board was reconfigured, invisible on the board until
> they were moved out.

**Do not cite the Jira changelog as evidence of which seat performed an action.** Every API
call in this workspace authenticates as the one account (`Moataz Mustapha`) — re-confirmed by
direct read 2026-09-08, where every `changelog.histories[].author` on every issue is that
single account. The changelog proves a transition happened and when, **never who**.

### Who moves a ticket into each column

A transition made by the wrong seat is a process failure, not a shortcut.

| Into | Moved by |
|---|---|
| `Backlog` | `po` |
| `Ready` | `po` — selection is Sprint preparation, and requires the five facts below |
| its **execution status** (`Front-end` / `Back-end` / `Design` / `Content` / `Operations`) | **the executing worker** |
| its **review status** (`QA-Test` / `Self-review` / `Peer-review`) | **the executing worker** — the status is chosen by system policy, not by the worker |
| back to its **same** execution status (review FAIL) | **the review owner** |
| `Done` | **the review owner** — SELF: the worker · PEER: the reviewer · QA: `qa` |

**THERE ARE NO TEAM LEADS.** The five `team-lead-N` seats were **removed in Wave 6,
2026-09-08**. Nothing replaced them as a seat, and nothing should: their three remaining duties
became derivations. Capacity comes from ownership, queue depth, Work Effort and defined seats
(`agent/state/capacity.py`); stack custodianship went to `pm`; contended-surface sequencing
became a claimability predicate over declared file surfaces (§7). Their status files stay in
`agent/status/` as durable historical evidence — the seats are gone, the record is not.

**`po` is no longer a gate in the path.** The universal review gate is retired. `po` writes
acceptance criteria, selects into `Ready`, decides scope, and answers a scope or acceptance
question when a route owner or the CEO raises one — it does not stand between every ticket and
its completion.

**`Ready` requires five facts.** Project · required capability · acceptance criteria ·
non-null Work Effort · `due_date`. An item missing any of them stays in `Backlog`. **A
dependency-blocked item may sit in `Ready`** — `Ready` means *selected and prepared*, not
*startable*, and blocked-ness is derived from the dependency graph, never stored on the item.

**Writing acceptance criteria is `po`-only.** No other seat writes them. **But a worker that
discovers real work mid-execution files the follow-up itself** — discovery, minimum scope,
dependency/context, Project and required capability — into **`Backlog`**, with `work_effort`
null. It does not write the acceptance criteria and **does not estimate another capability's
Work Effort**.

**Work Effort is recorded by a seat of the capability that will do the work**, at its own
Preflight, after MODEL C has evidenced it and it has been woken. **This is sizing, not a
claim** — CLAIM does not exist, the sizing seat does not thereby own the work, and a different
same-capability seat may revise the number at its own Preflight.

**Three standing rules on every ticket:**

- **No ticket without a `due_date`.** A ticket with no date is not scheduled, it is a wish.
- **The date comes from capacity, not estimation.** Capacity is **derived** —
  `agent/state/capacity.py`, from current ownership, queue depth, Work Effort and defined seats.
  The `po` may not estimate it and may not ask a developer directly; it reads the derived
  figure. See `agent/skills/capacity-to-date/SKILL.md` for the sitting unit and the
  ceiling-versus-earliest discipline, both unchanged — **only the source of the number moved.**
- **A slot frees on acceptance, not delivery.** A developer who has handed work to review is
  still holding that slot until the route owner passes it. This is what stops the board
  filling with work that is "done" and not accepted.

**Rules that keep that true:**

1. **A task is transitioned into its execution status when work starts**, not retroactively.
2. **Findings are commented on the ticket as the work produces them**, not saved for a
   summary at the end. The board should tell the story without anyone opening the repo.
3. **A task reaches `Done` only through its validation route**, and only its review owner puts
   it there. There is no path from an execution status straight to `Done`.
4. **An Epic closes only when its children are Done.** If children remain open by design —
   follow-ups, deferred work — say so explicitly in the closing comment. A green Epic
   above open CRITICAL children is a lie the board tells.
5. **No task is complete until the agent has appended to its own
   `agent/status/<name>.md`.** **The path is resolved from the One Brain workspace
   root, never from the project tree the agent happens to be standing in** — today
   that root is `/Users/moatazmustapha/Desktop/Thebes`, so the entry goes to
   `/Users/moatazmustapha/Desktop/Thebes/agent/status/<name>.md` and the 30 role
   files carry it absolute for exactly this reason. **The failure this prevents is
   silent:** on 2026-09-05 `po` ran with its working directory set to
   `Dabbler/dabbler-code`, and the "create the file if it does not exist" clause below
   turned a relative path into a brand-new `dabbler-code/agent/status/po.md` that
   nothing reads. No error was raised. This binds every agent, on every task, with no
   exemption for small work. The entry records **what it did, what it touched,
   what it decided, and what is blocked**. **Create the file if it does not
   exist** — several seats have none yet, and a missing file is not a reason to
   skip the entry. A task that ends with no change still gets one: a refusal, a
   question returned, a diagnosis. Write that explicitly so the silence reads as
   deliberate rather than as an agent that stopped early. The principle is
   `MANIFESTO.md` §5; this is the operational form of it.

---

## 2. JIRA CONVENTIONS

| Setting | Value |
|---|---|
| Site | `dabbler.atlassian.net` |
| cloudId | `18c8e9f5-d139-4e03-b5d8-89122cc14937` |
| Project key | `KAN` — "Dabbler Team", **team-managed** |
| Columns | See §1's table — do not restate the list here; a second copy is exactly how `Development` went missing from this section before. |

**Epics do not render as cards on a team-managed board. Tasks do.**

This is the rule that was got wrong once, and it is why every trackable unit is filed as
`issueTypeName: "Task"` with a `parent` Epic. An Epic alone is invisible to the person
watching the board — the work exists in the API and nowhere a human is looking.

**Transition ids are project configuration, not constants.** These are the live values, read
back from `getTransitionsForJiraIssue` with `includeUnavailableTransitions: true` on
2026-09-05:

| Status (exact name) | status id | transition id | Column | Category |
|---|---|---|---|---|
| `To Do` | 10004 | `11` | Backlog | To Do |
| `Ready` | 10008 | `2` | Ready | To Do |
| `Design` | 10047 | `9` | Operations | In Progress |
| `Content` | 10048 | `10` | Operations | In Progress |
| `Operations` | 10049 | `12` | Operations | In Progress |
| `Front-end` | 10046 | `8` | Frontend Development | In Progress |
| `Back-end` | 10043 | `5` | Backend Development | In Progress |
| `QA-Test` | 10009 | `3` | Review | In Progress |
| `Self-review` | 10044 | `6` | Review | In Progress |
| `Peer-review` | 10045 | `7` | Review | In Progress |
| `Done` | 10007 | `41` | Done | Done |
| *legacy* `In Progress` | 10005 | `21` | **none** | In Progress |
| *legacy* `Development` | 10010 | `4` | **none** | In Progress |
| *legacy* `In Review` | 10006 | `31` | **none** | In Progress |

**The transition ids break every pattern you might guess** — `Ready` is `2`, `QA-Test` is `3`,
`Back-end` is `5`, `Operations` is `12`. Anyone extrapolating from `11/21/31/41` guesses wrong,
which is exactly why the next rule exists.

**Two columns hold three statuses each** (`Operations`, `Review`), so a column name is not a
status name and cannot be sent to the API. **Match on the id, never on the name**, and treat
`agent/state/board.py` as the machine-readable source this table describes.

**Always call `getTransitionsForJiraIssue` and read the ids back** — never write a remembered
number into a transition call. Any id in any document here is a convenience, not an
authority; the board carried four columns until the 2026-09-05 restructure and the table
above will go stale the same way.

**Issue keys are not assigned sequentially.** Creating twelve tickets does not give you
twelve consecutive keys — KAN-5, 8, 10, 12 were interleaved with another epic's children in
the same session. **Never write a ticket key into a comment before the ticket exists.**
Create first, read the returned key, then reference it. Getting this wrong requires editing
a comment afterwards, which is recoverable but visible.

**Labels in use:** `audit`, `security`, `follow-up`, `bug`, `cleanup`, `config`,
`quality`, `po-decision`.

### A silent data-loss trap in the Jira tooling — read before editing any ticket

**A markdown table inside a numbered list item silently destroys the content it is part
of, and the API reports success.** Found by `po` on 2026-09-06 while correcting KAN-128's
AC 1: the edit dropped the acceptance criterion's **entire** body, and the tool returned
no error. It was caught only because `po` re-read the ticket immediately afterwards.

The cause is the markdown→ADF conversion, so it is not specific to one ticket, one field
or one seat. Any agent writing an acceptance criterion with a table in it — which is the
natural way to express a per-function or per-file rule — will hit it.

**Two rules, both cheap:**

1. **Never nest a table inside a numbered or bulleted list item.** Pull the table out into
   its own section and reference it from the list item. This is what `po` did to recover
   KAN-128, and the ticket reads better for it.
2. **Re-read every ticket immediately after editing it.** Not the edit response — the
   ticket. A success code from this API is not evidence the content landed. `po` adopted
   this as standing practice after the incident; it is the general rule, not one seat's.

**Why it is in this file rather than in a status log:** the failure is invisible at the
moment of writing and the loss is total, so the seat that hits it next will not know to
look unless it was told beforehand.

---

## 3. VALIDATION — THREE ROUTES, ONE COLUMN

The **Review column** is not decoration. A ticket sitting there has a claim attached to it —
"this is done" — and validation is where that claim is tested rather than accepted.

**The three review statuses are ALTERNATIVES grouped in one `Review` column.** A normal item
enters exactly one of them. **Nothing flows `Self-review → Peer-review → QA-Test`**, or any
other order — they are not stages.

**Every executable item takes exactly one of three routes: SELF, PEER or QA.** They are
mutually exclusive. The route is a property of the *work*, recorded before the item enters
its review status, and it does not change while the item is being validated.

### The route is DERIVED. No seat chooses it.

    TASK CHARACTERISTICS  are facts about the work.   Actors state them.
    VALIDATION ROUTE      is a consequence.           System policy computes it.

If a seat could write `validation_route` it would be choosing its own reviewer. If it could
freely assert the characteristics that *determine* the route, it would be choosing its own
reviewer indirectly — the same defect wearing a different field name. So the route carries
provenance `system-policy` and nothing else, and the validator recomputes it and **rejects a
stored route weaker than the computed one**.

The policy is `agent/state/policy.py`, and it is deterministic — first match wins:

| Condition | Route | Jira status |
|---|---|---|
| `schema_change` · `money_path` · `security_sensitive` · `shared_or_contended_surface` | **PEER** | `Peer-review` (10045) |
| `user_visible_runtime` | **QA** | `QA-Test` (10009) |
| everything else | **SELF** | `Self-review` (10044) |

**The board now expresses the route directly, so there is ONE authority and it must not
split.** Policy still *chooses* the route before the transition; once the Jira transition
succeeds, **the Jira status is authoritative evidence of which route is active**, and
Persistent State is reconciled to it — never the reverse.

Three outcomes when the two disagree, and the difference matters:

| Jira vs local | Treatment |
|---|---|
| equal | coherent |
| Jira **stricter** than local | **WARNING, repairable.** Jira wins; reconcile local up to it. This is exactly the state a successful Jira transition followed by a failed local write leaves behind, and it must stay repairable — hard-failing it would strand the record with no legal way back |
| Jira **weaker** than the policy floor | **ERROR.** Every transition on this board is global and unconditional, so anyone can drag an item from `Peer-review` to `Self-review`. "Jira wins" must never launder that into a downgrade: **the repair is to move the issue back in Jira**, not to lower the route in state |

**The one authorised exception below the floor** is the PEER-fail transfer: the reviewer
SELF-reviews its own fix, so a peer-floor item legitimately sits in `Self-review` afterwards.
`previous_owner` is the record that the transfer happened, and it is what distinguishes that
from an ordinary drag.

**These rules are not new judgement.** They are this section's own former "what goes through
review" table, `CONTRACT.md` §4's contended and shared surfaces, and the
`money-write-invariants` table set — made executable rather than re-derived. No `risk` or
`execution_complexity` value is invented to feed it; the policy does not consume them, which is
exactly why it can be deterministic while those fields stay deferred to Wave 6.

`shared_or_contended_surface` is **system-derived from the paths the work names** and is
asserted by nobody. `schema_change`, `money_path` and `security_sensitive` may be raised by
`po`, `cto`, `analyst` or **any worker that discovers one mid-execution**, each with a
`basis_ref` naming its evidence.

**Escalation is one-way.** A developer who finds mid-execution that ordinary work needs an RLS
migration raises `schema_change` and the route moves SELF → PEER. Nobody walks it back: only
`cto` may withdraw a safety characteristic, only before review has begun, and the route floor
never drops within a lifecycle. **Escalation is available to whoever finds the danger;
de-escalation is not available to whoever would benefit from an easier review.**

### SELF → `Self-review` (10044)

The worker validates its own work against the acceptance criteria and the build gates, then
transitions to `Done`. On FAIL it returns to its own execution status, fixes, and comes back
on the same route with the cycle incremented.

> **A scoped, deliberate exception to "the reviewer is never the author."** That rule still
> governs everywhere it is load-bearing — it is exactly why the PEER and QA routes exist, and
> why the policy sends every dangerous class of work to one of them. SELF applies only where
> the policy has found no such class. **A schema, money, security or contended-surface change
> is never SELF**, and no actor can make it so.

`review_owner` is the evidenced executor. **If executor evidence is ambiguous — zero seats, or
two or more — the route cannot start**, `review_owner` stays null, and the ambiguity is
surfaced rather than resolved by picking. That is the same refusal MODEL C makes.

### PEER → `Peer-review` (10045)

**The reviewer must be able to FIX.** PEER FAIL transfers execution ownership to the reviewer,
so a reviewer without execution authority for that work is not a reviewer at all.

Selection needs **two independent conditions**:

- **A.** the reviewer is **CEO-named or already evidenced** for that review, **and**
- **B.** the reviewer holds the **same `required_capability`** as the work item.

**A without B is INVALID.** If the CEO names `backend-4` to peer-review a frontend task, that
seat may **consult** — it may not own the validation, because PEER FAIL would require it to fix
frontend work. There are **no cross-capability execution-authority exceptions today**, and the
`frontend-N`/`backend-N` pair is **consultation only**: pairing grants no execution authority
and no review ownership across the boundary.

**If no valid reviewer is evidenced, `review_owner` is null and the item WAITS in
`Peer-review`.** It is never downgraded to QA or SELF for throughput. The route records
*why* the work is dangerous, and the absence of a validator does not make it less so — waiting
is visible on the board and a CEO can resolve it, where a silent downgrade is invisible and
nobody resolves it. **Work is allowed to wait.**

**PEER FAIL — the reviewer fixes it, and does not relay the defect back:**

```
review_result: fail
→ executor_evidence REPLACED with the reviewer (evidence_ref names the authorising event)
→ previous_owner: the original developer
→ review_type becomes SELF, owner the reviewer, cycle incremented
→ reviewer transitions to THE SAME execution status, fixes, returns via `Self-review`
```

The column does not change: the reviewer shares the item's capability by construction, so
`required_capability` is unchanged and so is its column. **Evidence is replaced, not appended** —
two entries mean *conflicting* evidence and routing must refuse, whereas here the workflow has
explicitly transferred responsibility. The original ownership survives in Jira history and in
`previous_owner`. **This is not CLAIM:** no lock, no exclusivity, no queue.

### QA → `QA-Test` (10009)

`qa` is a single seat, so the owner is determinate and the PEER selection problem does not
arise. Its status is `QA-Test` (10009). `qa` executes its testing story against the running app, then transitions to `Done` on
PASS. On FAIL it files the defect as a comment and **the current executor** returns the item to
its execution status, fixes it, and comes back to **`QA-Test` with the same owner**
and the cycle incremented — one validation cycle, not a new routing chain.

**`qa` never fixes Product code**, never edits another seat's work, and retains **no database
access at all**. **`qa` writes the testing story during Development, in parallel with the
developer** — but now only where the QA route applies, not for every ticket.

**Never assign a PEER route to a single-seat capability.** `content`, `devops`, `analyst` and
`qa` have one seat each; `ux-engineer` and `product-designer` have none. Their work would enter
`Peer-review` and could never leave. The policy consults live seat topology, and where
PEER is genuinely required for such work, **the work waits for an authorised validator** — it
is not rerouted.

---

## 4. THE HANDOFF RULE

**Agents do not brief each other, and no agent hands execution to another.** Briefs come from
the Orchestrator. A worker needing a scope or acceptance decision asks
**`po`** directly; a general domain decision goes up as an exception request for one redirect.

**The no-delegation rule is contractual, not enforced by the harness.** No binding restricts
tools, and runtime evidence shows the harness blocks only *named teammate → named teammate*
spawning — `fork` and unnamed subagent creation are available. **You may not call `Agent` or
`fork` to create an executor, and you may not use `SendMessage` to hand your work to another
seat.** Nothing will stop you; the rule is the constraint.

**Amended 2026-09-06 by the CEO (`G-024`).** Until today every question and every finished
report came back to the Orchestrator, and that was never written anywhere — no role file
mentions the Orchestrator at all. It happened because the Orchestrator dispatches, so agents reply
to their caller. The cost is measurable: every report enters the Orchestrator's context and is
re-sent on every request after it. **The hierarchy exists; use it.**

**Corrected 2026-09-05.** This section used to read *"Everything routes through the master…
reports to `master-analyst` / the orchestrating session."* That was wrong twice over:
`AGENTS.md` §1 has said since `G-005` that **nothing routes through `analyst`** — it measures,
it does not route — and the `orchestrator` seat that the phrase also pointed at **no longer
exists.**

**The Listener is the distribution layer**, and it is a behaviour in the main session's
thinking rather than a seat in the tree. It writes **directly** to whichever seat owns the
question — a senior developer included — and never down a chain of managers. An agent
finishing a step reports to the Orchestrator, which decides what happens next. Agent A does not
hand work straight to Agent B.

Use the **`route-to-seat`** skill to decide who is concerned and to write the prompt.

**Why, given direct messaging is technically available:**

- **Subagents cannot spawn subagents.** Nesting is off by default and version-dependent, so
  a chain assembled from inside the chain breaks in a way that is hard to see. Parallelism
  and sequencing come from the top.
- **A silent fallback beats an error here.** `.claude/agents/` is registry-scoped to the
  working directory, and an unrecognised `subagent_type` falls back to a generic agent with
  no error raised. An agent-to-agent handoff can therefore land in a generic agent that
  answers plausibly and owns nothing.
- **A worker does not decide who executes next.** That is a routing decision, and after
  Wave 3 it belongs to the Dispatcher — on evidence, or not at all. **`po` owns task analysis,
  acceptance criteria and `Ready` selection; the executing worker owns its own transitions; the
  review owner owns the verdict.** **A team lead owns capacity, its stack and contention
  sequencing only — it transitions nothing and confirms no readiness** (2026-09-08), and it
  does not choose or assign the developer (`YOU PULL`, §1).

**The channels, corrected 2026-09-07 (Wave 3):**

| Direction | Goes to | Example |
|---|---|---|
| **Down — a brief** | the **Orchestrator** (the Main Session), and only it | dispatching work from the CEO's word |
| **Up — scope, acceptance, work definition, criteria** | **`po`**, directly. `po` answers directly | "this acceptance criterion cannot be met" · "this needs a second sitting" |
| **Up — a general domain decision outside your authority** | a **structured exception request** to the Dispatcher, which redirects **once** | "this needs an architecture call nobody has made" |
| **Standing authorised direct routes** | the named authority, directly | `backend-N` → `cto` for `G-028` confirmation |
| **Sideways — a factual question** | the **peer**, directly (`grill-peer`) | "does the notification schema already have a `read_at` column?" |
| **Cross-capability work you discovered** | a **structured routing request** to the Dispatcher (§4.1) | frontend finds the RPC does not exist |

**The team lead is no longer an escalation target for finding an executor.** It never chose
the developer (`YOU PULL`), and after Wave 3 it does not appear in any routing path. It keeps
its readiness, transition, capacity and contention duties — see §1 and §7.

**One redirect, then the Dispatcher exits.** After a redirect the authority talks to the
original worker directly. **Forbidden:** `Authority → Dispatcher → po → developer`, or any
chain where an answer is passed along rather than given.

**What still reaches the Dispatcher:** a dispute no single seat owns, anything touching the
CEO's own files, structured routing requests, and general exception requests. On 2026-09-05
`team-lead-3` and `devops` disagreed on whether `KAN-126` was on Phase 0's critical path.
Neither could settle it; `CONTRACT.md:378` did. **That is the shape of it, and it is rare.**

---

## 4.1 STRUCTURED ROUTING REQUEST — TEMPORARY, WAVE 3

> **TEMPORARY. Exit: Wave 6.** Capability queues replace this.
>
> **Wave 4 made these records durable.** A routing request is written through
> `agent/state/store.py` and gets an `rr-<uuid>` id; an exception gets `exc-<uuid>`. They survive
> session loss, which prompt text did not. **They are still not a queue** — nothing claims from
> them, nothing pulls from them, nothing orders them, and `selected_seat` stays null until MODEL C
> evidence determines one.

**A worker that discovers work for another capability does not hand it over.** Direct
execution delegation is prohibited (§4). Instead it returns a structured request:

```
ORIGINATING WORK ITEM:  KAN-nnn
REQUIRED CAPABILITY:    backend | frontend | content | qa | devops | ...
DISCOVERED SCOPE:       what is actually needed, in one or two sentences
DEPENDENCY / BLOCKER:   what it blocks, or what blocks it
RAISED_BY:              the seat raising it
RETURN_TO:              where the result should go
```

**The discovering worker names the capability. It does not name the seat** — that is the
Dispatcher's job, and only on evidence (`route-to-seat`).

**Jira authority is unchanged.** If genuinely new work must be authored, the request goes to
**`po`**, which writes it. **A developer does not create or edit tickets.**

**Blockers, since Wave 4:** a structural blocker may become a **dependency record** —
`source BLOCKS target`, one canonical direction, `IS_BLOCKED_BY` derived by query and never
stored as a second record. Written through `store.py` under the Product graph lock, which is
what rejects cycles and duplicate edges. Continue to name the blocker in a ticket comment where
the current workflow already requires one, citing the `dep-<id>`.

**Satisfaction is not something you write.** An edge carries `completion_condition: DONE`, so a
prerequisite sitting in review has satisfied nothing. Whether it is satisfied is derived once
canonical lifecycle exists (Wave 5). **Blockers recorded before Wave 4 stay as ticket comments —
there is no backfill**, because inferring past relationships from comment prose would be
fabrication.

### The result comes back directly

**The Dispatcher is not in the technical return path.** The receiving seat sends its result to
`RETURN_TO` **directly** via `SendMessage` when that seat is addressable in the same session.

**When `RETURN_TO` is not addressable** — a different session, or an identity that no longer
resolves — the Dispatcher may re-wake the originating seat with the result as context. That is
a **COMPATIBILITY RE-WAKE**, and it must be called that. **It is not direct messaging**, and
cross-session `SendMessage` does not exist. The exception and routing records live only in
prompt context until Wave 4 gives them durable state.

---

## 5. NAMED WORKFLOWS

### W1 — A feature change

1. **`po`** writes the ticket with testable acceptance criteria and a `due_date` taken from the
   owning lead's capacity, sets its **single `required_capability`** and Project, and — once a
   seat of that capability has sized it — moves it to **Ready**. Work needing two capabilities
   is **split into two executable children** first (§1).
2. **The executing worker** pulls it from `Ready` and transitions it into **its own capability's
   execution status** — `YOU PULL, YOU DO NOT WAIT`. **Since Wave 6 the pull is a real
   mechanism, not an instruction:** the item is claimed atomically from its capability queue
   before the seat is woken, and there is no lead in the loop because the seats no longer exist.
   Readiness is the `Ready` column's five required facts, and `po` owns selection.

   *(Corrected twice. This step originally had the lead hand-assign each subtask by task shape;
   a 2026-09-07 correction removed the assignment but left the lead making the transition. Wave
   5 removes the lead from the step entirely.)*
3. **The developer** implements, following the build order (`MANIFESTO.md` §2): database →
   constants → repository → providers → screen → route. Writes tests for what it built, runs
   `flutter analyze` and `flutter test`, and **pastes the output rather than summarising it.**
   **It commits hand-written source only — generated output is `devops`'s, at step 6 (W6).**
   Where the change touches a Freezed model, a Riverpod generator or an `.arb` file, it may run
   `build_runner` locally to make `analyze` pass, but **leaves the regenerated files out of the
   handoff and says in the ticket that regeneration is owed.** It records the review context and
   moves the item to **its computed review status**.
4. **The review owner** validates on the item's route (§3) and transitions to **Done** on PASS.
   On FAIL the item returns to its **same** execution status with the cycle incremented — SELF and QA
   return it to the current executor, PEER hands it to the reviewer, who fixes it itself.
5. **`cxo`** is consulted where a user-visible change raises an experience question — **no
   longer a mandatory step on every user-visible ticket** (retired 2026-09-08). `cxo` keeps the
   design-system standard, the `D-` decisions and experience governance, and an experience
   concern is raised as an exception rather than as a gate every ticket queues behind.
6. **`devops`** regenerates if regeneration is owed — **W6**, a separate commit of its own —
   then commits, pushes `Canary`, and verifies canary.dabbler.pro.

| Step | Seat | Receives | Produces | Done when |
|---|---|---|---|---|
| 1 | `po` | The request | A ticket with criteria, one capability, a Project and a date | Criteria testable; **exactly one** `required_capability`; date came from capacity; Work Effort recorded by that capability |
| 2 | the executing worker | A Ready ticket | The item in its own execution status | It pulled it itself. **No lead transition, no assignment** |
| 3 | the executing worker | The work | Code through step 6 of the build order, **hand-written source only** | A route reaches it; `analyze` 0 errors; `test` passes; **no `*.g.dart` / `*.freezed.dart` in the diff** |
| 4 | the review owner | The claim "this is done" | Verdict on the item's route | Done, or back to the **same** execution status with the cycle incremented |
| 5 | `cxo` | An experience question, if raised | Experience verdict | Rule named — **consulted, not queued behind** |
| 6 | `devops` | Approved work | **Regeneration commit if owed (W6)**, then a verified Canary deploy | Generated output is its own commit; **the site shows it** |

**Step 1 is where money is saved or wasted.** A work item with two capabilities in it cannot be
scheduled, sized or validated honestly — it is split before it is selected, not after it stalls.

### W2 — A schema change

1. Backend agent inspects live state first — `list_tables`, `get_advisors`, and a probe as
   `anon`. **Never work from the migration file alone**; the remote is the truth, and
   **`SCHEMA.md` §8 mismatch 7 is the authoritative statement of the migration situation —
   read it, do not restate it.** In brief: 237 migrations are applied per
   `supabase_migrations.schema_migrations`; the 38 `.sql` files tracked at
   `supabase/schema/` are outside the path the CLI reads, so `db diff` and
   `migration list` see nothing.
2. Writes the change **as a migration**, plus its RLS policies in the same change.
3. Applies it under `G-002`'s four conditions — claim-comment posted and re-checked
   immediately before applying (`G-006`), preconditions measured live, schema/privilege/
   definition only, verified and posted back after. **`G-028`'s routine `cto` confirmation was
   retired 2026-09-08**; the second pair of eyes is now the PEER route at step 6.
4. Verifies empirically: query as `anon` and as `authenticated`, with a control query that
   should return 0 to prove the probe works.
5. Adds any new identifier to `supabase_config.dart`.
6. **PEER validation by another `backend-N`** — **mandatory and automatic**: `schema_change`
   forces the PEER route, and no seat can author or lower it. **If no backend reviewer is
   evidenced, the work WAITS** in `Peer-review`. It is never downgraded to QA — `qa` has no
   database access and could not validate a migration — and never to SELF.
7. devops ships. **Destructive or irreversible production action, and any user-data mutation,
   remain CEO-only** — unchanged by `G-028`'s retirement.

| Step | Agent | Receives | Produces | Done when |
|---|---|---|---|---|
| 1 | the owning `backend-N` | The requirement | Current live state | Probed, not assumed |
| 2 | the owning `backend-N` | State | Migration + policies | Both in one change |
| 3 | the owning `backend-N` | The migration | Applied change | `G-002`'s four conditions met and posted |
| 4 | the owning `backend-N` | Applied change | Probe results | `anon` returns what it should, control returns 0 |
| 5 | the owning `backend-N` | New names | Constants | No literal in `lib/` |
| 6 | **another `backend-N`** | The change | PEER verdict | Approved — **or the item waits, with a null review owner** |
| 7 | devops | Approved | Deploy | Verified on canary |

### W3 — A release

1. devops confirms the launch gate (`MANIFESTO.md` §4) — **all seven items**.
2. Bumps the version in every place it is duplicated.
3. Commits, pushes `Canary`.
4. **Waits for the Cloudflare build and loads canary.dabbler.pro.** A green push is not a
   green deploy.
5. Opens a PR from `Canary` into `main`. **Never a direct push.**
6. After merge, confirms app.dabbler.pro serves the change.

| Step | Agent | Receives | Produces | Done when |
|---|---|---|---|---|
| 1 | devops | Work on Canary | Gate check | All 7 pass, or STOP |
| 2 | devops | Gate passed | Version bump | Every copy updated |
| 3–4 | devops | Commit | Canary deploy | **canary.dabbler.pro shows it** |
| 5 | devops | Verified canary | PR | PR open, never a push |
| 6 | devops | Merge | Production | **app.dabbler.pro shows it** |

**As of 2026-08-26 this workflow cannot complete.** Launch gate item 4 fails — KAN-24 and
KAN-25 are open unauthenticated data leaks.

### W4 — An audit refresh

analyst alone. No handoffs.

1. Read the existing `PROJECT_STATE.md` first.
2. Run the `project-audit` skill's five phases.
3. Mark fixed findings `RESOLVED`, update moved numbers, tag new ones `NEW`.
4. Append a dated changelog row.
5. Report deltas against the baseline in `.claude/agent-memory/analyst/`, not
   absolutes.

Output is findings, never fixes. Each finding names the work it implies and who should own
it — an audit that does not become assignable work has failed.

### W5 — An App Store rejection

**Owned by `devops` since 2026-09-05**, when `devops` was merged into it.
Read `agent/roles/references/app-store-review.md` first — it carries that seat's operating
procedure, guardrails and per-rejection output format.

1. **`devops`** diagnoses against the cited guideline. **Identified, never guessed.**
2. If the fix is **inside `ios/**` or App Store Connect metadata**, `devops` makes it and
   drafts the Resolution Centre reply. **It never claims a fix it cannot evidence.**
3. If the fix is **outside that scope**, `devops` writes a report naming the slice and the
   change needed, and **stops.** It does not reach into code it does not own.
4. **`po`** turns that report into a ticket. Nobody assigns it — it enters its capability
   queue and is claimed.
5. A rejection needing a **product** change goes to `cpo`; one needing an **architecture**
   change goes to `cto`. Fix the submission; escalate the direction.
6. **`devops`** bumps the version — **a rejected marketing version must be bumped, not just
   the build number** — builds, and uploads.

| Step | Seat | Receives | Produces | Done when |
|---|---|---|---|---|
| 1 | `devops` | Rejection text + guideline | A diagnosis naming the guideline and the offending behaviour | The guideline is identified, not guessed |
| 2 | `devops` | In-scope fix | The fix + a Resolution Centre reply | Change made, reply drafted, evidenced |
| 3 | `devops` | Out-of-scope fix | A report naming the slice. **STOPS** | The report exists; no out-of-scope edit was made |
| 4 | `po` | That report | A ticket | Criteria testable, owner named |
| 6 | `devops` | An approved fix | Version bump + build + upload | Build accepted by App Store Connect |

### W6 — Regenerating generated code

**Owned by `devops`.** Established by `STACKS.md` §10.5 under the Phase 0 authorisation
(`G-015`); `CONTRACT.md` §3:209 forward-references it. `CONTRACT.md` §3 already said generated
files are never hand-edited — it did not say **who regenerates them**, and this is that answer.

**It runs at commit time, after a developer's source-only commit.** It is not a step a developer
performs and not something that happens during implementation.

**Trigger:** a change to a Freezed model, a Riverpod generator, or an `.arb` file — anything whose
output lands in `lib/l10n/**`, `*.g.dart` or `*.freezed.dart` (`CONTRACT.md` §3:209).

1. **The developer commits hand-written source only** and does **not** commit `build_runner`
   output. It may run `build_runner` locally to make `flutter analyze` pass; the regenerated files
   stay out of the commit. It says in the ticket that regeneration is owed.
2. **`devops` runs `dart run build_runner build -d`** against that commit.
3. **`devops` commits the generated output as a separate commit containing nothing else** — no
   source, no formatting, no unrelated file. One commit, machine-written, reviewable by being
   skipped rather than read.
4. **`devops` runs `flutter analyze` and `flutter test` on the result** and pastes the output. A
   regeneration that breaks either is a finding, not a commit.
5. Then W1 step 7 proceeds: push `Canary`, verify canary.dabbler.pro.

| Step | Seat | Receives | Produces | Done when |
|---|---|---|---|---|
| 1 | developer | A source change | A commit of hand-written files only | **No `*.g.dart` / `*.freezed.dart` / `lib/l10n/**` in the diff**; the ticket says regeneration is owed |
| 2–3 | `devops` | That commit | A separate commit of generated output | The regeneration commit touches **only** generated paths |
| 4 | `devops` | Both commits | `analyze` + `test` output, pasted | 0 errors, tests pass |
| 5 | `devops` | A green tree | Canary deploy | **canary.dabbler.pro shows it** |

**Only one `build_runner` run at a time across the roster.** `devops` holds that lock; no other
seat runs it against `dabbler-code`. This is the same class of rule as §7 but a different surface —
§7 names four contended **files**, this names a contended **command**, and the four-file check at
dispatch does not catch it.

**Why the rule exists, measured 2026-09-05 at `dabbler-code` HEAD:** **52 generated files, 45 of
them under `lib/data/`** (`git ls-files | grep -cE '\.(g|freezed)\.dart$'` → 52;
`git ls-files 'lib/data/*' | grep -cE '\.(g|freezed)\.dart$'` → 45). A commit mixing 45
machine-written files with three hand-written ones is unreviewable — validation (§3) cannot
see the three. And at sixteen developers, two concurrent `build_runner` runs conflict in files
nobody authored, which is a merge conflict with no author to resolve it.

**`content-manager` dependency:** `STACKS.md` §10.5 and §10.0's parallel-work table tie this to the
first generated-l10n commit — **P0-5 must land before any generated-l10n Dart is committed**, not
to Phase 0's completion.

---

## 6. THE STOP CONDITION

A workflow halts mid-flight when any of these is true:

- **An open question whose answer changes the work.** Stopping is the correct output.
  A guess that keeps the session moving costs more than the pause.
- **A gate fails** — `flutter analyze` errors, a failed test, an unverified deploy.
- **The task needs a path its agent does not own** (`CONTRACT.md`).
- **The work is frozen by a decision** — `rewards` (015), the clean-arch stack (016).
- **A CRITICAL security finding is open and the workflow ends in a release.**

**What happens to the remaining steps:** they do not run. The ticket goes back to `To Do`
with a comment naming the blocker, and the blocker is added to `MANIFESTO.md` §6 if it
blocks more than this one task.

**What must not happen:** the agent must not substitute adjacent work to have something to
show. A halted task that reports the blocker is a success. A halted task that quietly
delivers something else is worse than one that delivers nothing, because the blocker stays
invisible.

---

## 7. THE CONTENTION PROTOCOL

> **WAVE 6, 2026-09-08 — CONTENTION IS DECIDED BY CLAIMABILITY, NOT BY A COORDINATOR.**
> A work item declares the repository-relative paths it touches (`surfaces`). A claim is
> refused when those paths **actually collide** with the surfaces of work already owned — an
> exact match, a directory containment, or two paths under the same governed shared prefix.
> **Not "both booleans are true":** two items can each touch a shared surface and never meet,
> and collapsing that into one flag is what forced a human to sequence by hand.
>
> **Ownership itself holds the execution slot** — there is no separate contention lock, and the
> collision clears by derivation when the owner releases. If surfaces change *after* a claim and
> create a collision, the Orchestrator may STOP the unsafe item with a `reason_ref`; it never
> silently steals from either owner. The four contended files and the shared prefixes below are
> unchanged and remain authoritative.


Four files are touched by nearly every feature change, and they are the practical limit on
how many agents can run at once:

`lib/app/app_router.dart` · `lib/providers.dart` ·
`lib/core/config/feature_flags.dart` · `lib/core/config/supabase_config.dart`

**The procedure:**

1. **Before dispatching parallel agents, the Orchestrator checks which of the four each task
   needs.** Tasks needing the same file are **sequenced, not parallelised**. This check
   happens at dispatch, not after a conflict.
2. **An agent in one of these files appends only.** Add your import, route, export, or
   constant. Do not reorder, regroup, reformat, or tidy.
3. **Your feature's block only.** Do not fix a neighbouring feature's entry, however
   obviously wrong. Report it (`MANIFESTO.md` R8).
4. **Never delete another agent's entry.** Removing a dead flag or route is cleanup work
   with its own ticket and owner.
5. **A diff touching one of these files takes the PEER route** — `shared_or_contended_surface`
   is system-derived from the paths, and it forces PEER (§3).
6. **`supabase_config.dart` is add-only for values.** Changing an existing constant's value
   redirects the whole app and needs a `DECISIONS.md` entry first.

**How many agents can safely run in parallel:** as many as have disjoint file sets. In
practice, with three developers, that means **at most three concurrent code tasks with
disjoint file sets, plus `devops`, plus `analyst`** — and only one of those inside a contended
file at a time. Parallelism beyond that produces conflicts faster than it produces work, which
is also why only two stacks are active (`AGENTS.md` §1).

**The one contended surface this section does not cover is a command, not a file.**
`dart run build_runner build -d` rewrites the 52 generated files — 45 of them under
`lib/data/` — and two concurrent runs collide in files nobody authored. That lock is
`devops`'s and the procedure is **W6** (§5): regeneration runs at commit time, after a
developer's source-only commit, and lands as a commit of its own. The four-file check at
step 1 does not catch it, because no agent declares a *command* in its file set.
