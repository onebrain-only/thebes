# Codex Primary wake adapter

`agent/execution/codex_primary.py` delivers ONE external event as ONE new turn on the SAME
durable Codex thread. It is control-plane maintenance tooling, not Product execution: it
never goes through the Listener, provider selection, leases or receipts, and it never names
a Product work item. Proven live 2026-09-28 as `CODEX_EXTERNAL_INFERENCE_PROOF_04`.

**This is NOT cutover.** Claude Primary A stays ACTIVE; the Codex thread stays STANDBY.
A wake to a STANDBY Primary leaves it STANDBY.

## The binding (`primary_binding`, dir `primary-bindings`)

Natural key = `provider` (`claude` | `codex`). Fields: `session_ref` (Claude session id or
Codex thread id — a UUID, never a name/PID/socket), `status` (`ACTIVE` | `STANDBY` |
`RETIRED`), `generation`, `stable_home`, `changed_by`, `reason_ref`, `previous_session_refs`.

- `store.bind_primary(provider, session_ref, status, changed_by, reason_ref, stable_home,
  expected_revision=None)` creates or CAS-rebinds. **It refuses `ACTIVE`** unless that
  provider is already the ACTIVE one; a bind can never create a second Primary.
- `store.set_primary_active(provider, changed_by, reason_ref)` is the ONLY cutover
  primitive. Under the `execution-domain` lock it demotes the current ACTIVE to STANDBY and
  promotes the target with `generation = max(existing) + 1`, in one locked section.
  It is implemented and tested; **it is not called for Codex.**
- `store.active_primary()` returns the one ACTIVE record or `None`, and raises on two.
- `validate.py --check` refuses a runtime holding two ACTIVE bindings.

## The wake (`primary_wake`, dir `primary-wakes`, prefix `pwake-`)

Immutable evidence written once per wake: `provider`, `session_ref`, `generation`,
`event_kind`, `payload_ref` (the raw JSONL log), `status` (`delivered` | `busy` |
`failed`), `turn_ref`, `response_summary`, `error` (structured `{code, message}`),
`started_at`, `completed_at`. A `delivered` wake must name its turn; `busy`/`failed` must
carry an error.

## The process-local override

The child is launched as exactly

```
codex app-server -c 'openai_base_url="https://chatgpt.com/backend-api/codex"' \
                 -c 'model_catalog_json="agent/state/runtime/codex/bundled_catalog.json"'
```

`-c` overrides apply to that process only; nothing under `~/.codex` is written. The URL is
the runtime's own built-in default for ChatGPT-account auth (`CHATGPT_CODEX_BASE_URL`,
openai/codex tag `rust-v0.154.0`, `codex-rs/model-provider-info/src/lib.rs`). The catalog
is the runtime's bundled list, dumped on first use with `codex debug models --bundled` into
the gitignored runtime dir. Before any thread call the adapter verifies from the runtime
itself (`account/read`, `config/read`, `model/list`): account type `chatgpt`, effective
`openai_base_url` is that URL (never `127.0.0.1:11434`), catalog path is ours, and a
default model exists — else `failed` with code `codex-runtime-not-chatgpt-route`.
No API key is ever used.

## Lock / busy semantics

The Codex thread has a single writer. If Codex Desktop has it loaded, `thread/resume`
fails with "already has an active writer"; the adapter returns `busy` with code
`CODEX_PRIMARY_THREAD_BUSY`, records the wake, shuts down cleanly (stdin EOF releases any
lock), and does **not** retry and does **not** create a replacement thread. A busy answer is
an answer.

## The turn

`thread/resume` (read-only sandbox, `approvalPolicy: untrusted`) → one `turn/start` with
input `THEBES_EVENT <event_kind> gen=<generation>\n<payload>`, the catalog's default model,
`readOnly` sandbox, network off. Every approval request from the server is declined. The
process blocks on the JSON-RPC stream until `turn/completed` for that turn id (or the
timeout) — a client wait, not a model loop, not a poll. Only `agentMessage` items carrying
this turn id are collected. `thread/start` is never called.

## CLI (maintenance semantics, not the Listener)

```
python3 -m agent.execution.codex_primary status
python3 -m agent.execution.codex_primary bind --provider codex --session-ref <thread> \
    --status STANDBY --stable-home <home> --changed-by ceo --reason-ref <ref>
python3 -m agent.execution.codex_primary wake --event <kind> --payload-file <path> [--dry-run]
```

`bind` accepts only `STANDBY`/`RETIRED`; ACTIVE is a transition, not a bind.

## Primary ownership and the user front door (2026-09-29)

**Thebes is the runtime owner of the ACTIVE Codex Primary thread.** A Codex thread has exactly
one writer. While Codex Desktop has the thread loaded, Desktop's own app-server holds the writer
lock and every Thebes turn on that thread is `CODEX_PRIMARY_THREAD_BUSY` (verified: the lock on
`01a0e382-…` was held by Desktop's app-server, pid 2745). Thebes can start a turn only when
Desktop does not hold the thread. Cutover therefore requires Codex Desktop to be closed.

**User → Primary:** `python3 -m agent.listener primary-command "<text>" --wait` submits a
`PRIMARY_COMMAND` intent. The Listener runs it once: a durable `primary_command` record (text in
a `text_ref` file), the canonical ACTIVE binding re-read, ONE turn on the bound thread through the
same codex_primary adapter, and the result (`delivered` with turn id and reply, or `busy` /
`failed` / `refused`). It waits for that one turn only, never for a worker. A Claude ACTIVE
Primary is refused (`primary-command-claude-direct`: talk to it directly). A `worker:` actor is
refused at intake.

**One writer inside Thebes:** user commands and worker-outcome notifications both take the
non-blocking `primary_writer` lock; a second concurrent writer is refused as
`PRIMARY_WRITER_BUSY`, never queued or waited on.

**Pending notification after cutover:** a `busy` notification is kept durably. Once Desktop is
closed, deliver it exactly once with
`python3 -m agent.execution.primary_notify deliver <dispatch_id>`; a delivered notification is
never sent again.

**Serialized queue (2026-09-29):** a user command that meets another Thebes writer is recorded
`queued`, not refused. The writer that holds the lock, right after its own turn is delivered and
while still holding it, drains queued commands and kept (`busy`) notifications oldest first, one
turn each, stopping at the first that is not delivered. The trigger is a Thebes turn completing;
nothing polls. Limit: a thread held by Codex Desktop is outside Thebes, so its release is not an
event Thebes can observe. A kept notification such as KAN-369's is delivered by the next Thebes
turn that succeeds (for example the next `primary-command` once Desktop no longer holds the
thread), or by one explicit `primary_notify deliver <dispatch_id>`.

## Shared Codex app-server and per-conversation reply routing (2026-09-30)

One Thebes-owned `codex app-server --listen unix://agent/state/runtime/codex/shared.sock`
(same ChatGPT-route process-local override as above) is shared by many Thebes-managed Codex
conversations. Clients connect over WebSocket on that Unix socket and disconnect; the server is
never started per message. Desktop-owned threads are never registered or touched.

```
python3 -m agent.execution.codex_runtime start                      # start once / reuse; fails closed if inconsistent
python3 -m agent.execution.codex_runtime status                     # runtime record + registered conversations
python3 -m agent.execution.codex_runtime new-conversation --label X --prompt "<first turn>"
                                     # thread/start + its first turn on ONE connection (a thread with
                                     # no turn is dropped when its creating connection closes)
python3 -m agent.execution.codex_runtime prompt <thread_id> "<text>" # one user turn; prints the event incl. turn_ref
python3 -m agent.execution.codex_runtime events <thread_id>          # every queued/delivered turn with turn_ref
```

**Dispatch from a conversation.** Inside a registered conversation, Codex runs
`python3 -m agent.listener session-dispatch <KEY> --deliver` from its own tool shell. The Listener
CLI reads `CODEX_THREAD_ID` from that environment (never typed, never chosen by the worker); the
Controller refuses it unless it is an active conversation on the shared runtime, then records
`origin_provider=codex, origin_thread_id, reply_to_thread_id, target_provider=claude,
target_session_id, delivery_id` on the dispatch. The worker's envelope names the reply thread.

**Reply.** The worker reports through the Listener; the existing gate (exact SID + DELIVERED
delivery) accepts it once. `session_outcome` enqueues ONE `worker_result` turn event for the
origin thread (id `cevt-result-<dispatch uuid>`, so a repeat can never add a second) and detaches
`codex_runtime drain <thread>`, which runs `thread/resume` + `turn/start(threadId=origin,
input=<THEBES_WORKER_RESULT prompt>)` on the shared runtime. Codex-origin dispatches never use
the global primary_binding.

**Serialization is per thread** (`thread_writer(<thread_id>)`, non-blocking): different threads
run concurrently; a second writer on the same thread is refused, its event stays queued, and the
current writer drains it right after its own turn and re-checks after releasing. No polling.
Enqueue is one critical section (check, text write, create) so a concurrent duplicate can never
overwrite a created event's text, and queued turns carry `seq` so FIFO holds inside one second.
A detached drain appends to `agent/state/runtime/codex/drain.log`.

## Free-text conversation dispatch (2026-09-30)

`agent/execution/conversation_dispatch.py`: a Codex conversation hands an explicit prompt to one
persistent Claude session and gets the explicit result back as a real turn on **the same thread**.
Not Product: no Jira item, claim or lease. Record `conversation_dispatch` (dir
`conversation-dispatches`, prefix `cdispatch-`); prompt/result text live in `*_ref` files and the
worker capability only as `capability_sha256`.

```
# run the existing Listener once, outside the Codex sandbox
python3 -m agent.listener serve
# from a registered conversation's own tool shell (origin = $CODEX_THREAD_ID; there is no flag for it)
python3 -m agent.listener conversation-dispatch --to <CLAUDE_SID> --prompt-file <path>
# from the target Claude session, exactly as its envelope renders it
THEBES_DISPATCH_CAPABILITY=<cap> python3 -m agent.execution.conversation_dispatch \
    submit <cdispatch-id> --outcome <completed|blocked|decision_required|clarification_required|failed> \
    --result-file <path>
python3 -m agent.execution.conversation_dispatch withdraw <cdispatch-id>   # origin thread only
python3 -m agent.execution.conversation_dispatch status [<cdispatch-id>]
```

- **dispatch** enters through the durable Listener inbox. The Listener's worker runs outside the
  Codex tool sandbox so its detached Claude delivery can reach the background service. Codex
  receives the intake acknowledgement and ends its turn; the worker does not wait for Claude's
  result. The `conversation_dispatch` gate refuses unless `CODEX_THREAD_ID` is an active conversation on the running shared
  runtime and `--to` is the durable SID of exactly one active Claude `role_session` (its
  `stable_home` is where `--resume` runs). Under a per-SID lock it refuses a target with any open
  conversation or Product dispatch (`target-session-busy` — delivery stops a live session, which
  would kill in-flight work), records the dispatch, and delivers `envelope + prompt` with the same
  stop → `claude --bg --resume <SID>` → verify transport as Product (`claude_delivery.deliver_prompt`;
  an exited session is resumed, a missing one is `delivery_failed`, never replaced). The child
  `claude` gets the environment without `CODEX_THREAD_ID`/`CLAUDE_CODE_SESSION_ID`/`CLAUDECODE`.
  The Listener worker detaches delivery and returns immediately; the capability is never shown to Codex and is redacted in the
  stored `message_ref`.
- **submit** is accepted once, under the dispatch lock: capability hash (constant-time) + exact
  `CLAUDE_CODE_SESSION_ID` + a DELIVERED `session_delivery` for this dispatch. An identical repeat
  returns `already-recorded`; a different second result is `result-already-recorded`. Thebes then
  renders `THEBES_CONVERSATION_RESULT` (ids, outcome, the worker text verbatim) and queues it on the
  STORED origin thread as `cevt-cresult-<uuid>` — one event per dispatch — and detaches
  `codex_runtime drain <thread>`.
- **withdraw** closes an open dispatch whose worker will never report; a later submit is refused.
