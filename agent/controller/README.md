# Temporary Controller Entry Point v1

Phase 2 exposes one bounded controller command:

```sh
python -m agent.controller execute KAN-XXX
```

The command accepts only one work item. It does not select backlog work, change
authorization or mode, choose a provider, or accept claim/lease/lifecycle
overrides.

## The routine path derives its own brief

No human authors an execution brief for existing Jira work.
`agent/controller/intent.py` resolves one work item into the ExecutionRequest
inputs from the sources that already own them:

| Input | Canonical source |
|---|---|
| `objective` | Jira summary + description + acceptance criteria, bounded |
| `required_capability` | `execution_profile.required_capability` |
| `allowed_surfaces` | `task.surfaces` (null = unassessed = refused) |
| `return_contract.return_to` | `policy.validation_route_for_profile` — never recomputed here |
| `validation_targets` | `operational_context.validation_plan`, else the canonical route |
| `reported_environment` / `primary_target` | `operational_context` — the recorded authority |
| `execution_kind` / `mutation_mode` | `operational_context.intent` |
| `workspace` | project registry `repository` + `worktrees.worktree_path` |
| model intent, effort, timeout, evidence/sections | Thebes-owned controller defaults |

Derivation runs **before the claim**: work Thebes cannot brief is work it must
not take ownership of. A fact canonical state does not hold produces a named,
bounded governance input — `objective-not-derivable`,
`environment-authority-missing`, `environment-authority-unresolved`,
`validation-route-unresolved`, `surfaces-unassessed`,
`required-capability-unresolved`, `workspace-unresolved` — each classified
`CEO_INPUT_REQUIRED` or `DERIVABLE`, never a guess. Safety characteristics are
read from typed state only; alarming Jira prose changes nothing.

## The workspace becomes real before dispatch

`agent/controller/workspace.py` turns the derived workspace into an allocated,
verified worktree. It adds no second workspace manager: allocation, the
protected-branch refusal, the occupied-path refusal and the dirty-tree refusal
all remain `agent/state/worktrees.py`.

Order: authorization → task → seat → Jira observe → intent derivation → **claim →
allocate → verify identity → bind revision** → lease → ExecutionRequest →
executor-brief firewall → provider selection → provider. A provider is never
pointed at a directory that has not been allocated and proven to be this seat's
own, so an allocation refusal means zero provider invocations.

After allocation the identity is checked rather than assumed — path ownership
(`owner_of`), branch name, worktree registration, and that this is not the
canonical checkout — and `expected_revision` is bound to what `git rev-parse
HEAD` actually reports in the new tree. A failed isolation is a bounded
orchestration blocker (`workspace-allocation-refused`,
`workspace-branch-mismatch`, `workspace-identity-mismatch`,
`workspace-repository-unavailable`, …). It is never a reason to execute against
the canonical Product checkout.

Release follows the Product lifecycle, not this function's scope. Preservation is
the default:

| Outcome | Workspace |
|---|---|
| `needs_input` | preserved — the continuation uses this tree |
| `execution_failed` | preserved — the evidence is in it |
| pending SELF/PEER/QA validation | preserved — the reviewer is not finished with it |
| `provider_failed`, freshly allocated, clean | released — nothing of the Product changed |
| `provider_failed`, reused or dirty | preserved |
| canonical lifecycle `done`, clean | released |
| anything holding uncommitted Product work | preserved, always |

A release keeps the branch. `worktrees.release` refuses a dirty tree, and that
refusal is reported as a preserved workspace rather than turned into an error or
a deletion.

## Exceptional brief shape

`--brief-file` survives for debugging and for work whose canonical facts are
genuinely absent. It is not the normal path, it still travels the same request
and the same executor-brief firewall, and it may not contradict a canonical
safety fact that state actually produced — `return_contract.return_to`,
`validation_targets`, `reported_environment`, `primary_target` and
`workspace.repository_root` are compared, and a contradiction is refused before
the claim.

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

`objective` is Product work only, derived or supplied. Thebes renders the executor's prompt from the
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
