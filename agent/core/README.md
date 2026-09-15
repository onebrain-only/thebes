# Thebes Core

`MASTER_ROADMAP.md` §36 asks Phase 5 for a clean separation between three
intelligences. §37 draws the middle one as a single box. This is that box.

```text
CEO
 ↓  natural language
Conversation Intelligence     the controller conversation (Codex).
 ↓  canonical intent envelope  Outside this repository. Interprets intent,
                               derives no execution detail, holds no state.
THEBES CORE                   ← this package, and the runtime that hosts it
 ├── Intake                    agent.listener.contract / .server
 ├── Persistent State          agent.state.store
 ├── Company Rules             agent.state.policy
 ├── Product State             agent.integrations.jira + task records
 ├── Work Lifecycle            agent.state.board + agent.controller.completion
 ├── Capability Model          agent.state.roster + agent.state.queue
 ├── Authorization             agent.controller + execution leases
 ├── Dependencies              agent.state.queue + dependency edges
 ├── Context Assembly          agent.controller.intent
 ├── Validation                agent.controller.validation + agent.state.policy
 ├── Learning                  agent.state.telemetry / .retrospective / .learning
 ├── Provider Selection        agent.execution.selection
 └── Execution                 agent.execution.wake + .provider
 ↓
Execution Intelligence         provider adapter → executor. Product work only.
```

`SUBSYSTEMS` in `__init__.py` is that map in code, and a test imports every
entry. A map nobody checks is a diagram.

## What Phase 5 did, and did not do

It did **not** rewrite the orchestration engine and added no second one. Every
responsibility above already existed and already worked. Core is **composition
plus one thing that did not exist**: a single answer to *what happened to this
intent*.

It did not rename the Listener either. The Listener is Core's intake subsystem —
same process, same durability, same authority (none).

## The defect Phase 5 closed

After Phase 4 an intent had **two state machines**:

| | said |
|---|---|
| Listener transport record | `RECEIVED` / `DISPATCHING` / `COMPLETED` … |
| Persistent State | whether a claim existed, a lease was open, a receipt landed, where lifecycle stood |

Nothing reconciled them. They could disagree indefinitely and no caller could
tell. "One canonical intent lifecycle" is exactly that reconciliation.

**The rule.** The transport record is evidence of *delivery* — authority for
whether a message arrived, never for what happened to the work. Canonical state
is authority for the work. Where they disagree, **canonical state wins and the
disagreement is reported**, never smoothed over: a reconciler that quietly picks
a winner is how a fourth source of truth is born.

## One external vocabulary

| State | Means |
|---|---|
| `ACCEPTED` | durable, not yet dispatched |
| `ORCHESTRATING` | with the Controller, no answer yet |
| `AWAITING_AUTHORITY` | stopped at an authority boundary; a `DECISION_RESPONSE` continues it |
| `COMPLETED` | the Controller gave an **authoritative answer** |
| `REFUSED` | refused at intake; never orchestrated |
| `UNDELIVERED` | no authoritative answer was produced |
| `INDETERMINATE` | dispatch interrupted; the outcome was never observed |

`COMPLETED` means **answered**, not succeeded. A governance refusal is a
completed delivery carrying a refusal, and the answer says which. `INDETERMINATE`
is deliberately **not terminal**.

Reconciliation values: `agrees`, `no-canonical-subject`, `unobserved-execution`,
`transport-claims-more-than-canonical-state-shows`.

## The ambiguous dispatch

Phase 3 refused to retry an interrupted dispatch, because nothing can prove the
Controller did not already run. **That rule is unchanged — Core added
information, not permission.** What changed is that Phase 4's answer was
"interrupted, a human decides" with no statement of what canonical state held.
Core now answers `INDETERMINATE` *and* hands over the claim, the open leases,
the receipts and the work item's lifecycle. Strictly more information; identical
conservatism. It still never guesses that an ambiguous Product mutation did not
occur, and the intent is still never re-dispatched.

## Core reads

`lifecycle.resolve` has no write path into Persistent State, Jira, a provider or
a task record. The test stub raises on any attribute beyond `read`/`read_all`
rather than taking that on trust. Learning is deliberately **not** consulted
when answering (§39): a recommendation must not become an input to a decision
path by convenience.

## Using it

```sh
python3 -m agent.listener serve                    # the Core runtime
python3 -m agent.listener submit KAN-XXX --wait    # submit and read the answer
python3 -m agent.listener show <INTENT-ID>         # canonical answer + evidence
python3 -m agent.listener status                   # every intent's lifecycle_state
```

```python
from agent import core
core.resolve(intent_id)      # one intent's canonical answer
core.resolve_all()           # all of them, oldest intake first
```

`GET /intents/<id>` returns Core's answer under `intent`, the Phase-3/4 delivery
record under `transport_record` (the audit trail — kept readable on purpose),
and the raw stored result under `result`.

## Tests

```sh
for t in agent/core/tests/test_*.py; do python3 "$t"; done
```

`test_core_lifecycle.py` — the derivation, every state from its evidence, the
ambiguous dispatch, and reconciliation naming disagreement.
`test_core_contract.py` — the §37–§40 architecture: the subsystem map imports,
Core holds no orchestration of its own, §38's minimum-context list field by
field, §39's learning boundary, §40's conversation independence.
