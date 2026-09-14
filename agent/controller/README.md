# Temporary Controller Entry Point v1

Phase 2 exposes one bounded controller command:

```sh
python -m agent.controller execute KAN-XXX --brief-file /path/to/brief.json
```

The Codex controller prepares the JSON brief after it has read the selected
ticket and canonical context. The command accepts only one work item. It does
not select backlog work, change authorization or mode, choose a provider, or
accept claim/lease/lifecycle overrides.

## Brief shape

```json
{
  "execution_kind": "implementation",
  "objective": "The controller's bounded professional execution brief.",
  "context_refs": ["agent/roles/backend.md"],
  "workspace": {
    "repository_root": "/absolute/repository/root",
    "working_directory": "/absolute/working/directory",
    "mutation_mode": "repository_edit",
    "worktree_path": null,
    "expected_revision": null
  },
  "reported_environment": {
    "locality": "local",
    "runtime": "flutter",
    "platform": "chrome",
    "environment_ref": "reported:localhost"
  },
  "primary_target": {
    "locality": "local",
    "runtime": "flutter",
    "platform": "chrome",
    "environment_ref": "reported:localhost",
    "browser_automation": false,
    "launch_method": "flutter-run"
  },
  "validation_targets": [
    {"target_id": "local-chrome", "kind": "runtime", "required": true}
  ],
  "model_intent": "balanced",
  "reasoning_effort": "medium",
  "required_execution_features": ["repository_read", "repository_edit", "shell"],
  "timeout_seconds": 900,
  "return_contract": {
    "return_to": "controller",
    "required_evidence": ["test output"],
    "required_sections": ["RESULT", "EVIDENCE"]
  }
}
```

The task record supplies the required capability and declared surfaces. The
controller deterministically selects the first free active neutral-registry seat
with that exact capability; existing claims exclude seats. A task may carry an
explicit `execution_profile.pinned_seat_id`, in which case only that declared,
free, exact-capability seat is eligible. Historical `executor_evidence` never
pins a future claim. The controller brief becomes the immutable request objective
without a second prompt format.

`objective` is Product work only. Thebes renders the executor's prompt from the
immutable request through the one canonical builder in `agent/execution/brief.py`,
so a controller never writes the prompt itself and never adds a second prompt
format. Control-plane internals — invocation id, seat, claim, execution lease,
operating mode and revision, model/effort intent — have no rendering path into
that prompt. A brief whose objective, context, surfaces, validation or return
contract instructs the executor to continue, resume or launch itself, choose a
provider, open or close a lease, claim or release work, or drive Jira lifecycle
is refused before any provider is selected, and the command returns that refusal
as its blocker.

Product authorization remains a roadmap governance fact and Product execution
remains gated by the runtime operating mode. In the current maintenance state,
the command returns a structured non-execution result before Jira, state writes,
leases, or providers are touched.

When both local providers are available, the existing selector remains the only
selection policy. The local Claude CLI bridge runs non-interactively and reports
native permission denials as `needs_input`; it never approves them or silently
switches to Codex.
