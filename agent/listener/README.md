# Thebes Listener — Phase 3

The Listener is a **communication boundary**. A CEO instruction enters Thebes
through it instead of through `python3 -m agent.controller ...`, and the
Controller's answer comes back through it. That is the whole job.

**Since Phase 4 it is the operational front door, and that is enforced.** The
Controller's three orchestrating commands — `execute`, `resume`, `decide` —
refuse a direct operational invocation (`direct-controller-entry-retired`,
exit 2) and run only when the Listener launches them. The authorizing intent id
travels into that subprocess and comes back on the result as `entry_path` /
`entry_reference`, so an operational run can be traced to the intake that caused
it. See `agent/controller/entry.py`.

That gate is a **misuse guard, not authentication** — the marker is an
environment variable, and any local process can set one. It makes this door the
default and a bypass deliberate and visible. `--maintenance-reason "<why>"`
keeps the direct path for recovery, debugging and tests. `integrate` and the
read-only planning commands are not gated, because they orchestrate nothing.

**Phase 4 moved no authority.** The Listener owns exactly what it owned in
Phase 3. Only the normal door changed.

**It is not a second Controller.** It owns no orchestration decision of any
kind, and it never will: the moment it decides something about Product work,
the separation Phase 3 exists to establish is gone.

## Responsibility split

| The Listener owns | The Controller owns |
| --- | --- |
| receiving an instruction | Jira interpretation |
| validating transport shape | Product authorization |
| normalizing it into a bounded intent | planning and capability resolution |
| durable intake acknowledgement | seat selection, claims, leases |
| idempotency and duplicate suppression | workspace allocation |
| correlation | provider selection and execution |
| durable result delivery | validation routing and remediation |
| carrying a CEO decision back to the same workflow | integration, lifecycle completion, reconciliation |

Jira remains Product lifecycle truth. Persistent State remains Thebes
operational truth. Git remains code truth. The Listener is authority for none
of them.

## The intent contract

One envelope, transport-neutral, in `contract.py`:

```json
{
  "schema_version": 1,
  "intent_type": "EXECUTE_WORK_ITEM",
  "source": "listener-cli",
  "actor": "ceo",
  "idempotency_key": "...",
  "correlation_id": "...",
  "responds_to": "<intent id>",
  "payload": { }
}
```

`intent_id` is **derived**, not supplied: `sha256(intent_type + idempotency_key)`.
The same logical request submitted twice is literally the same record.

Two allow-listed families, and nothing else reaches a dispatcher:

| Family | Payload | Means |
| --- | --- | --- |
| `EXECUTE_WORK_ITEM` | `work_item_id` only | run the work item the Controller already knows about |
| `DECISION_RESPONSE` | `work_item_id`, `original_invocation_id`, `decision`, `permission`, `approval_scope`, optional `allowed_operation` | answer a boundary Thebes already reported, on the workflow it reported it from |

There is no field anywhere that carries a command, a file path, a seat, a
provider, a workspace, a validation route or a lifecycle. Unknown fields are
**rejected**, not ignored.

## Durable inbox and outbox

`store.py`, under `agent/listener/runtime/` — deliberately **outside**
`agent/state/runtime/`, so nothing here can be mistaken for Product operational
truth. `agent/state/validate.py` does not know it exists. It borrows exactly two
mechanics from Persistent State: the same-directory atomic write and the same
`flock` discipline.

Delivery states describe the fate of a **message**, never of Product work:

```
RECEIVED ──▶ DISPATCHING ──▶ WAITING_INPUT | COMPLETED | FAILED
    └──────────────────────▶ REJECTED
```

`COMPLETED` means **the Controller returned an authoritative answer** — a
refusal (`product-execution-not-authorized`, `system-maintenance-active`,
`dependency-blocked`) is a COMPLETED delivery carrying a refusal. `FAILED` is
reserved for the Controller producing no authoritative answer at all.

`WAITING_INPUT` is terminal for that intent; the workflow continues through a
correlated `DECISION_RESPONSE`, which is its own intent. Resuming is therefore
never re-running.

## What is and is not guaranteed

The guarantee is **durable intake + idempotent dispatch + durable result + no
silent duplicate Product execution**. It is deliberately *not* distributed
exactly-once, which the underlying operations cannot provide.

- **Acknowledged means on disk.** The record is written and fsynced before the
  caller hears anything. There is no window in which a caller was told
  "accepted" about something that is not durable.
- **Result before settlement.** `settle()` writes the result file first, then
  transitions the intent. A crash between them leaves the intent `DISPATCHING`
  and the result already on disk — recoverable and truthful. It can never leave
  an intent `COMPLETED` with nothing behind it.
- **An interrupted dispatch is never retried.** On restart a `DISPATCHING`
  intent is marked `dispatch-interrupted` and left non-eligible. The Listener
  cannot prove the Controller did not already run, and a Product execution it
  cannot prove did not happen must not be repeated on a hunch. A human decides,
  with canonical state in front of them.
- **A terminal intent is never re-dispatched or re-settled.**

## Restart semantics

| Failure | After restart |
| --- | --- |
| crash before dispatch | intent is still `RECEIVED` and still eligible |
| crash mid-dispatch | intent is `DISPATCHING`, marked `dispatch-interrupted`, **not** re-dispatched |
| Controller produced no answer | `FAILED`, with the transport reason; never `COMPLETED` |
| crash after the Controller answered, before the caller saw it | the result is already durable; `GET /intents/<id>` returns it without re-running anything |
| the same intent delivered again | same `intent_id`, one execution, `duplicate: true` |

## The authority-response flow

Phase 2 already had `needs_input` receipts, continuation preparation,
invocation-scoped approvals and `resume`. Phase 3 adds **no new approval
architecture** — it transports decisions into that machinery.

```
EXECUTE_WORK_ITEM
   → Controller returns needs_input (invocation I)
      → Listener records WAITING_INPUT carrying I
         → CEO submits DECISION_RESPONSE responds_to=<that intent>, invocation=I
            → Listener binds it: same intent, still waiting, same work item, same invocation
               → python3 -m agent.controller decide ...
                  → store.record_execution_approval  (the EXISTING writer)
                     → controller.resume             (the EXISTING resume)
                        → same workflow, same provider session, same tail
```

The seat and the provider session are **derived from the canonical continuation
preparation**, never accepted from the caller: a decision may answer a question,
not redirect it at another seat or another session. The approval writer then
re-verifies identity, session and the exact permission boundary against the
durable receipt, and refuses anything that does not match. Two gates; the
canonical one is the second.

Refused, each with its own reason: `unknown-decision-reference`,
`decision-target-not-waiting`, `decision-work-item-mismatch`,
`decision-invocation-mismatch`. A duplicate decision is idempotent three times
over — the intent id, the content-addressed approval id, and `resume`'s
already-executed detection.

## Transport and safety

**Loopback only.** `127.0.0.1`, with a defensive client-address check behind the
bind. It is not a network service and must not become one in this phase.

- allow-listed intent types; unknown fields rejected
- bounded body (64 KiB), refused before parsing
- malformed JSON rejected
- no intent field carries a command, path, provider, seat or workspace
- argv is built as an **array**; `shell=False` always; no interpolation
- a caller cannot bypass Product authorization — the Controller's gate is
  unchanged and runs first, exactly as it does for a human

**Not authenticated.** Phase 3 is local-only precisely because `actor` records
who submitted without proving it. Any non-local exposure requires authentication
first; that is Phase 4+ work, not a Phase 3 gap being ignored.

## Operator commands

```sh
python3 -m agent.listener serve                 # run it (loopback only)
python3 -m agent.listener health                # liveness + queue depth
python3 -m agent.listener submit KAN-183        # one EXECUTE_WORK_ITEM
python3 -m agent.listener submit KAN-183 --wait # ...and block for the answer
python3 -m agent.listener status                # every intent's delivery state
python3 -m agent.listener show <intent-id>      # the intent and its durable result
python3 -m agent.listener decide <intent-id> \
    --invocation <id> --permission <tool> --scope "why"
```

`THEBES_LISTENER_RUNTIME` points the inbox at a throwaway directory. It is for
tests and experiments; it is not a way to point the Listener at Persistent State.

## Tests

```sh
for t in agent/listener/tests/test_*.py; do python3 "$t"; done
```

`test_front_door.py` (Phase 4: the gate, the real refusing and permitted
Controller processes, intent provenance, the decision path across the real
boundary, and the executor firewall),
`test_contract_store.py` (contract, durability, idempotency, correlation),
`test_dispatch.py` (process boundary, one execution per intent, restart, truthful
failure, one real Controller subprocess), `test_server.py` (the real Listener
process, killed and restarted), `test_decision_loop.py` (the authority loop and
every refusal, plus `controller.decide` itself).
