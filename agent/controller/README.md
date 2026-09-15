# The Controller

**This is not the operational front door. Since Phase 4 the front door is the
Listener** — `python3 -m agent.listener submit KAN-XXX`. It dispatches this same
command, in its own process, and carries its answer back.

```sh
# normal operation, since Phase 4
python3 -m agent.listener submit KAN-XXX --wait

# what the Listener runs on your behalf — refuses if you type it yourself
python3 -m agent.controller execute KAN-XXX
```

`execute`, `resume` and `decide` orchestrate Product execution and are gated by
`agent/controller/entry.py`. Typed directly they refuse with
`direct-controller-entry-retired` and exit 2; launched by the Listener they run
unchanged and report `entry_path: listener` with the intent that authorized
them. `--maintenance-reason "<why>"` keeps the direct path for recovery,
debugging and tests, and records the reason in the result.

**That gate is a misuse guard, not authentication.** The marker is an
environment variable and any local process can set one. It makes the Listener
the default and a bypass deliberate and visible; it stops a mistake, not an
attacker. The boundary is unauthenticated, which is why it is loopback-only.

`integrate` (recovery) and the read-only `plan-sprint`, `plan-backlog` and
`authority-manifest` are **not** gated — they orchestrate nothing, and Phase 4
retired an execution front door, not an architecture.

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

## Landing validated work

```sh
python -m agent.controller integrate KAN-XXX   # recovery path; not gated
```

A separate act from `execute`, because validation happens after an execution
returns — often in another session — so integration cannot be the tail of the
wake that produced the work.

`agent/controller/integration.py` adds no git: `worktrees.assert_attribution`,
`worktrees.commit` (explicit pathspec, never `-A`) and `worktrees.integrate`
(the cross-process integration lock, stale-target refusal, `-x` cherry-pick,
exact conflict report) are used unchanged. What it adds is the gate and the
ordering.

**The gate is the canonical validation route and nothing else.**
`validation_reasons` is `queue.completion_reasons` with exactly one reason
dropped — `already-done`, because an item the Orchestrator has already moved
still needs its code to land. A completed provider result, a Jira status and a
seat's say-so all remain incapable of opening it.

Order: validated → attributed → commit → serialized integration → verified
against git → evidence recorded → workspace concluded.

Attribution runs before anything is staged: the changed files must be a subset
of the surfaces the task declared. An undeclared change is refused and left in
place, never restored or reset. A clean tree does not end the story either — if
an earlier attempt committed and failed to land, that commit is retried rather
than reported as change-free.

Outcomes, each its own fact and none of them a provider or PEER failure:

| Outcome | Meaning |
|---|---|
| `integrated` | landed on the integration branch and verified against git |
| `already-present` | the commit is already there; not landed twice |
| `no-product-commit-required` | legitimately changed nothing; no empty commit |
| `attribution-failed` | changed files the task never declared |
| `commit-failed` | the commit itself could not be made |
| `integration-conflict` | does not apply cleanly; Product remediation, workspace preserved |
| `integration-failed` | integration could not be verified afterwards |
| `validation-not-passed` | the route has not passed; nothing was staged |

Verification asks git rather than trusting an exit code: the landed commit is an
ancestor of the branch, the previous head still is too (unrelated work was not
discarded), and the expected files are present. A conflict aborts the
cherry-pick, leaves the branch exactly where it was, and preserves the worktree
as the remediation surface. `main` is never an integration target.

Evidence lands in a durable `integration_receipt` record: the Product commit,
the integrated sha, the branch, the previous head, the route and its result, the
attributed files, and whether remediation is required. Persistent State holds
the orchestration evidence; git remains the authority on the code.

## Validation is dispatched, not waited for

`execute KAN-XXX` now runs the canonical validation route itself, between the
Product execution and the integration tail. No human records a SELF, QA or PEER
verdict for routine work.

`agent/controller/validation.py` adds ordering and dispatch only. The route comes
from `policy.validation_route_for_profile`, the owner from
`policy.resolve_owner_or_wait` through `store.open_review_context`, the verdict
from `store.record_review_result`, and each FAIL from its own canonical handler.

Order, and why: **release ownership** (the only act that creates executor
evidence, which SELF's owner *is* and which PEER eligibility *excludes*) →
**transition** into the route's review status (a review context may only open on
an item canonically in review) → **open the context** (policy resolves the owner;
a PEER with no eligible peer waits with a null owner rather than being
downgraded) → **dispatch** the reviewer read-only → **record** the verdict.

A validation request is a first-class `ExecutionRequest` of kind `validation`. It
travels the same brief builder and the same firewall, and the request contract
refuses it unless it is read-only and carries an open review context — a reviewer
that could edit the work it judges is not a reviewer. It opens no claim and no
lease, because `execute_product_wake`'s ownership gate is about Product
execution and a reviewer is deliberately not the owner.

**A provider that returned `completed` has not passed anything.** The verdict is
an explicit evidence claim of kind `verdict` whose reference is `pass` or `fail`;
anything else is `validation-result-malformed` and is surfaced, never guessed. A
failed or unavailable validator is `validation-dispatch-failed` — the validation
act failing is not the Product failing review.

| FAIL | Canonical handler | Effect |
|---|---|---|
| PEER | `store.peer_fail_transfer` | reviewer becomes the evidenced executor, route becomes SELF, cycle +1, `previous_owner` recorded. No second PEER loop. |
| SELF | `store.self_fail_reentry` | execution returns to the exact same seat, ownership re-established |
| QA | none — `qa` never executes | the work returns to its executor; ownership is re-established by the ordinary claim |

## Lifecycle completion is the tail, not a third command

`execute KAN-XXX` runs integration and lifecycle completion itself. Both gate
themselves on canonical truth, so an execution whose review has not happened yet
simply reports `validation-not-passed` and changes nothing — the ordinary case.
`integrate KAN-XXX` remains for recovery and idempotent reconciliation; it runs
the same tail.

`agent/controller/completion.py` adds no lifecycle machinery.
`board.assert_transition_target` refuses a legacy or unknown destination,
`board.transition_for` names the exact transition, `jira.transition_issue`
performs it, `store.observe_lifecycle` records what Jira then says, and
`store.release` gives up ownership.

Order: evidence → gate → assert legal target → transition → **authoritative
re-read** → observe into Persistent State → release ownership → report open
leases → finalize workspace.

**The integration receipt is evidence, never authority.** It is checked against
the work item and owner it claims, its outcome, its integration branch and its
recorded shas; a foreign, failed, conflicted, protected-branch or malformed
receipt proves nothing and the gate refuses before any Jira call.

**The completion gate is `queue.completion_reasons`**, consumed whole. A
provider status does not complete work and neither does the existence of a
commit. The single exception is `already-done`, which is the idempotent case:
if Jira already says Done, no second transition is fired.

**Persistent State is written from the re-read, never from the fact that a
transition was accepted.** If Jira lands somewhere other than Done, that is
`jira-state-diverged-after-transition`: no local Done is recorded and ownership
is preserved.

Outcomes, none of which is a provider, Product or PEER failure:

| Outcome | Meaning |
|---|---|
| `completed` | transitioned, confirmed, reconciled, ownership released |
| `already-done` | Jira was already Done; zero writes, still reconciled |
| `lifecycle-not-completable` | canonical policy refuses; nothing was touched |
| `integration-evidence-invalid` | no usable integration receipt |
| `jira-transition-failed` | the transition did not happen; ownership preserved |
| `jira-state-diverged-after-transition` | Jira disagrees; no false Done |
| `ownership-release-failed` | Done is real, the release is not |
| `finalization-incomplete` | state could not be reconciled to Done |

Ownership survives every failure above, and a Jira failure is never a reason to
re-run a provider.

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
