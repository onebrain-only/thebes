# agent/state — Persistent Thebes State

**Added Wave 4, 2026-09-07.** An independent system layer. It is **not an agent, not a seat,
not a Role, not Orchestrator memory and not Main Session memory** — the Main Session reads and
writes it operationally, and will hand that to the Orchestrator in Wave 6.

## What this layer IS

- Orchestration state — what is currently being coordinated.
- Current execution context.
- Execution Profile persistence.
- Routing context — the durable form of what Wave 3 carried in prompt text.
- Exception context — likewise.
- Product dependency relationships.

## What this layer IS NOT

Jira · a second ticket database · a copy of acceptance criteria · Git architecture history ·
`dabbler-docs` governance · a Role contract · Role Learning · telemetry · agent memory ·
Main Session memory · Orchestrator memory.

## The non-duplication rule

**Persistent State stores identifiers, references, minimum orchestration facts, timestamps and
provenance. It never stores canonical prose owned elsewhere.**

| GOOD | BAD |
|---|---|
| `"work_item_id": "KAN-137"` | the ticket's description |
| `"decision_ref": "G-028"` + source + governance baseline | `G-028`'s text |
| `"project_id": "app"` | what the App project is |
| `"evidence_ref": "jira-comment:10453"` | the comment body |
| `"required_capability": "backend"` | the Role's behaviour |

The validator enforces a length ceiling on reference fields, which catches a pasted ticket body
or a rule copied in. **A second copy of a canonical fact is a second authority** — the defect
Wave 1 spent a whole closure removing from `CONTRACT.md`.

## Tracked vs runtime — the hybrid boundary

**If System Maintenance authors it, it is tracked. If a seat writes it during execution, it is
local-durable and git-ignored.**

| Tracked | Local-durable, git-ignored |
|---|---|
| this README · `store.py` · `validate.py` | `runtime/tasks/` · `runtime/routing/` |
| `registry/` — Company, Product, Projects | `runtime/exceptions/` · `runtime/dependencies/` |
| | `runtime/.locks/` |

Tracking mutable records would keep the working tree dirty during normal Product execution, let
unrelated product commits sweep runtime state, and make Git responsible for a live orchestration
database. `.gitignore` carries one rule: `/agent/state/runtime/`.

## Workspace-local — NOT global truth

**Runtime state is durable across sessions that share this working copy. It is not shared
across different clones, worktrees or cloud checkouts.**

`fcntl.flock` serialises processes on one filesystem. It is **not distributed locking**, and
none is invented here. A different checkout has entirely independent runtime state — which is
safe precisely because runtime records are never committed, so there is nothing to merge or
diverge. **Never describe this state as global occupancy or global truth.** Compatibility debt;
revisited in Wave 6.

## Every operational write goes through `store.py`

`read` · `create` · `update` · `create_dependency`. **No DELETE** — records are retired or
withdrawn, never removed.

`update` requires `expected_revision`. **There is no force mode**, because an optional safety
check is an absent one.

**Why a utility and not direct file writes.** Read-modify-check-write across four syscalls is
not compare-and-swap: two writers can both read revision 5, both re-check 5, and both write 6,
the second silently destroying the first. `os.replace()` makes a write atomic for *readers*; it
does nothing to serialise *writers*. So the revision check and the write happen inside one
`flock` region.

**Dependency mutations take a Product graph lock**, not a per-edge lock. Per-edge locking cannot
protect a graph invariant: two sessions adding `X→Y` and `Y→X` under different locks each pass a
cycle check alone and together make a cycle.

**System Maintenance may edit this README, the tooling and `registry/` directly** — reviewed
configuration, not concurrent runtime writes.

**Honest limit:** `validate.py` **cannot prove a record went through `store.py`.** Runtime files
carry no write ledger, so a careful manual edit is indistinguishable from a store write. The
no-direct-edit rule is contractual, exactly like the no-delegation rule.

## Record shapes

Documented here; enforced by `validate.py`. **These are executable Thebes rules, not JSON
Schema** — no `jsonschema` package is installed and none is added. There are deliberately no
`*.schema.json` files, because formal-looking files that nothing reads are worse than none.

Every record carries `schema_version`, `revision`, `created_at`, `updated_at`.

**Task** — `runtime/tasks/<JIRA-KEY>.json`. `work_item_id` · `product_id` · `project_id` ·
`record_type` · `lifecycle` · `executor_evidence` (list) · `execution_profile` (object or null) ·
`review_context`. (`schema_version: 1` records carry the flat Wave 4 `canonical_lifecycle` /
`jira_operational_column` nulls instead; both versions validate.)

**`record_type` — `executable` or `container`. ONE EXECUTABLE WORK ITEM = ONE
`required_capability`.** That single capability decides the Development column, the valid PEER
reviewer, execution authority and the future Wave 6 queue. An Epic, a split parent or any
coordination item is a **container**: it may span capabilities, and it carries no capability, no
Work Effort, no validation route and no review context. **A parent is not executable merely
because its children are**, and no board column exists for parents.

**`lifecycle` — an OBSERVATION of Jira, never an independent authority.** `canonical`
(ready/development/review/done) · **`jira_column`** · `jira_status_id` · `jira_status_name` ·
`source: "jira"` · `observed_at`.

**A COLUMN IS NOT A STATUS, so all three are recorded.** The live board groups several statuses
into one column — `Operations` holds `Design`/`Content`/`Operations`, and `Review` holds
`QA-Test`/`Self-review`/`Peer-review`. None of the three facts derives the other two:

```json
{ "canonical": "review", "jira_column": "Review",
  "jira_status_id": "10045", "jira_status_name": "Peer-review",
  "observed_at": "2026-09-08T00:00:00Z", "source": "jira" }
```

**The board model lives in `agent/state/board.py` — one file, machine-readable, and the only
place the board's shape is written down.** `canonical` and `jira_column` are both *derived from
the status id*, and the validator recomputes them rather than trusting the stored words.
**Ids, not names, are the key.** **When Jira and this record disagree, Jira wins**; state is
reconciled by re-reading Jira, never the reverse. The validator checks shape and the mapping;
it **cannot** tell you the observation is still current, which is why `observed_at` is
mandatory.

**Three legacy statuses still exist and are not targets** — `In Progress` (10005),
`Development` (10010), `In Review` (10006). They stay mapped because every historical changelog
entry names them and Sprint reconstruction replays that history.

**Historical readability is not current transition authority**, and the two functions are
deliberately separate:

| Need | Function | Legacy id |
|---|---|---|
| read history / replay a changelog | `board.canonical_for()` | **accepted** |
| observe what Jira currently says | `store.observe_lifecycle()` | **accepted**, validator says WARN |
| choose where to MOVE something | `board.assert_transition_target()` · `store.transition_target()` | **REFUSED** |

Observing a legacy status is a **WARNING**, not an error — a migration state, not a corrupt
one, and hard-failing it would make the migration unwritable. Choosing one as a destination is
refused outright.

**Both grouped columns are sets of ALTERNATIVES, never sequences.** One capability picks one
execution status; one policy decision picks one review status. Nothing flows
`Design → Content`, and nothing flows `Self-review → Peer-review`.

**The Jira review status IS the active route — one authority, not two.** Policy chooses the
route before the transition; once the transition succeeds, the Jira status is authoritative
evidence of which route is active and state is reconciled to it. Three outcomes:

| Jira vs local | Treatment |
|---|---|
| equal | coherent |
| Jira **stricter** | **WARN, repairable** — `store.reconcile_review_from_jira()` adopts it. This is the state a successful Jira transition plus a failed local write leaves behind, and it must stay repairable |
| Jira **weaker than the policy floor** | **ERROR.** Transitions here are global and unconditional, so anyone can drag `Peer-review`→`Self-review`. The repair is to move the issue back in Jira, never to lower the route |

**One authorised exception below the floor:** after a PEER-fail transfer the reviewer
SELF-reviews its own fix, so a peer-floor item legitimately sits in `Self-review`.
`previous_owner` — set atomically by `peer_fail_transfer()` and by nothing else — is what
distinguishes that from an ordinary drag.

**`review_context` — CURRENT review state, not a history.** `review_type` (self/peer/qa) ·
`review_owner` (**nullable, and null is a real answer**) · `review_result` · `review_cycle` ·
`started_at` · `previous_owner`. Jira's changelog and the ticket's comments already hold the
cycle history; a second copy here would drift. **`review_type` is initialised from the policy's
output and never edited** — the only legal divergence from `validation_route` is after a
PEER-fail transfer, which is why that transfer sets `previous_owner`.

**`executor_evidence` is evidence, not CLAIM.** A list of `{seat_id, evidence_ref,
evidenced_at}`. Zero entries = no evidenced executor. One unique seat = usable MODEL C evidence.
**Two or more unique seats = conflicting evidence, and routing must refuse** — not pick the
latest, lowest or first. **CLAIM does not exist**; Wave 6 adds a separate claim structure.

**Execution Profile** — embedded 1:1 in a task, or null. **Provenance is per field**, so the
validator can accept `work_effort` authored by `po` while rejecting `model` authored by `po` in
the same record. **The binding's `model:` and `effort:` remain the actual harness execution
defaults** — nothing here controls execution yet.

Wave 5 makes six fields operational: `project_id` (on the record), `required_capability`,
`work_effort`, `characteristics`, `validation_route`, `completion_route`. `profile_status` is
**`partial`**, and `effective_fields` must **truthfully** list only those — the validator checks
every named field is actually non-null. **`effective` stays forbidden until Wave 6**, because
five fields are still deferred and calling the profile effective would be untrue.
`execution_complexity`, `risk`, `model`, `reasoning_effort` and `parallelism` remain null; **no
value is fabricated for them**, and the policy does not consume them, which is exactly why it can
be deterministic now.

### Task characteristics are facts; the validation route is a consequence

    TASK CHARACTERISTICS  are facts about the work.   Actors assert them.
    VALIDATION ROUTE      is derived.                 Only policy.py computes it.

If an actor could write `validation_route` it would choose its own reviewer. If it could freely
assert the characteristics that *determine* the route, it would choose its own reviewer
indirectly — the same defect wearing a different field name. So `validation_route` carries
provenance `system-policy` and nothing else, and the validator **recomputes the route from the
characteristics and rejects a stored route weaker than the computed one.**

The five characteristics, their authority, and the one nobody may assert, are declared in
`policy.py`. `shared_or_contended_surface` is **system-derived from the paths the work names**
(CONTRACT.md §4's contended files plus `lib/core/**` and `lib/data/**`) and has no author at all.

**Escalation is one-way.** A worker who discovers mid-execution that ordinary work needs an RLS
migration raises `schema_change` and the route moves SELF → PEER. Nobody walks it back: only
`cto` may withdraw a safety characteristic, only before review has begun, and the route floor
never drops within a lifecycle. Escalation is available to whoever finds the danger;
de-escalation is not available to whoever would benefit from an easier review.

**A PEER route with no available peer WAITS.** `review_owner` stays null and the item sits in
`Peer-review`. It is never downgraded to QA or SELF for throughput — the absence of a
validator does not make the work less dangerous, and a silent downgrade is invisible where
waiting is visible on the board. A PEER reviewer must share the task's `required_capability`,
because PEER FAIL transfers execution ownership and a reviewer who cannot fix is not a reviewer.
**The frontend-N/backend-N pair is consultation only; pairing grants no execution authority
across the boundary.**

**Mutations that must be atomic have their own store operations.** `set_characteristics()`
recomputes and escalates the route inside the same lock as the write, so no writer can race a
characteristic in and a route out of step with it. `peer_fail_transfer()` moves evidence,
review type, owner, cycle and `previous_owner` in one CAS'd write, because a half-applied
transfer is exactly the state someone could sit in to reach an easier route.

**Routing request** — `runtime/routing/rr-<uuid4>.json`. **NOT A QUEUE.** Nothing claims from
it, nothing pulls from it, nothing orders it. `selected_seat` stays null unless MODEL C evidence
determines one, and an open request with no seat stays open indefinitely.

**Exception** — `runtime/exceptions/exc-<uuid4>.json`. `redirect_count` is 0 or 1; the validator
rejects 2, because a second redirect is the relay chain the architecture forbids. **Wave 4
persists the record; it does not route automatically.**

**Dependency** — `runtime/dependencies/dep-<uuid4>.json`. One canonical direction: `source
BLOCKS target`. `IS_BLOCKED_BY` is a **derived query, never a second record**. Cross-Project
inside one Product is legal; cross-Product is rejected. `completion_condition` is `DONE`, so a
prerequisite in review has not satisfied anything. **Satisfaction is derived, never stored** —
`state`/`active`/`resolved`/`satisfied` are rejected outright. `retired_at`/`retired_reason`
describe the *edge* being cancelled, not the prerequisite completing.

**Endpoints are Jira keys and do not require local task records.** A task record is created only
when there is genuine task-level state to hold — executor evidence or an execution profile.
**No stubs, no backfill.**

## Checks

```
python3 agent/state/validate.py --check
```

Exit 0 clean; non-zero names the path and the reason. **`WARN` lines do not fail the check and do
not block a write** — they mark a state that is legitimate but wants a human eye, such as a legacy
item observed in review before its route has been reconciled. Treating them as fatal would make
the honest migration path unwritable and push callers toward inventing a route to satisfy the
validator.

## Sprint — a derived window, and historical truth from Jira

`sprint.py`. **Nothing opens or closes a Sprint.** `sprint_id(now)` is the Monday of the current
week and `is_open(now)` is `Monday 00:00 <= now < Friday 19:00` in the canonical timezone — both
pure functions of the clock. That is stronger than an automation rule: it cannot fail to fire,
cannot double-fire and needs no running process, which matters because nothing in Thebes wakes
autonomously.

**Timezone lives in `registry/company.json` as an IANA id** (`Asia/Dubai`), never a fixed offset:
`UTC+4` names an offset, not a zone, and cannot express a DST rule. Dubai has none today, which
is precisely why writing the offset would look correct until the day it isn't.

| Sprint fact | Source |
|---|---|
| Window | Pure function of the clock, canonical timezone |
| Membership | `sprint-YYYY-MM-DD` labels — **replayed to the cutoff**, not read later |
| `state_at_close` | **Jira changelog replay to Friday 19:00** |
| Carry-over | Member at the cutoff whose status at the cutoff was not Done |
| Mid-sprint scope change | In-window changelog entries for labels, Rank, priority, status, parent |

**A later current-state read is not "state at close".** If an item is in Review at Friday 19:00
and someone transitions it to Done on Saturday morning, a Saturday read reports Done at close and
is wrong. So the replay runs **backwards from the value we know for certain** — today's value,
undoing every change after the cutoff — which also means an issue's unrecorded initial status is
never needed.

**A truncated changelog refuses rather than answers.** Jira caps the embedded changelog; beyond
that cap `histories` is a page, not the record, and a replay over a page yields a confident wrong
answer. `require_complete_changelog()` asserts `total == len(histories)` and raises otherwise.
**Do not substitute the current Jira status when it raises.**
