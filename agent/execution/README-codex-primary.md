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
