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
  "seat_id": "backend-1",
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
neutral registry must confirm that `seat_id` has that capability. The controller
brief becomes the immutable request objective without a second prompt format.

Product authorization remains a roadmap governance fact and Product execution
remains gated by the runtime operating mode. In the current maintenance state,
the command returns a structured non-execution result before Jira, state writes,
leases, or providers are touched.

When both local providers are available, the existing selector remains the only
selection policy. The local Claude CLI bridge runs non-interactively and reports
native permission denials as `needs_input`; it never approves them or silently
switches to Codex.
