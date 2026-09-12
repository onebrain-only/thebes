# Post-Wave-8 working-tree reconciliation

Date: 2026-09-12
Execution scope: SYSTEM_MAINTENANCE; Product/Dabbler execution remains frozen.
Canonical checkout: /Users/moatazmustapha/Desktop/Thebes-Canonical
Remote: https://github.com/onebrain-only/thebes.git
Verified branch: main
Verified HEAD and local origin/main: 3ca6f6953d14bb1bbe40d42cb9a591a3d5d54305

## Accepted input

Wave 8 is closed. The accepted read-only assessment recommends operating-mode
isolation first, then observed-condition investigation, authoritative reported
environments, and validation scope derived from causal and changed surfaces.
This record classifies existing evidence; it does not activate Product work,
promote historical architecture into current doctrine, or certify incident closure.

## Inventory and disposition

The initial status contained 22 modified tracked files and nine untracked path
groups. The tracked diff contained 12,023 insertions and 11 deletions.

| Paths | Category | Disposition |
| --- | --- | --- |
| agent/status/backend-1.md through backend-8.md; frontend-1.md through frontend-6.md; content-manager.md; cpo.md; cto.md; devops.md; po.md; qa.md | Durable Thebes operational memory | Preserve the existing journals, including Product-related execution evidence. Artifact ownership is Thebes; ticket subject does not change repository ownership. |
| agent/history/conventions-migration-window-legacy-notes.md; agent/history/thebes-target-architecture-specification.md | Durable historical evidence | Preserve as history, not replacement governance. |
| agent/roles/references/jira-edit-tool-defects.md | Durable workflow reference | Preserve; this does not authorize Jira activity. |
| agent/state/discovery-ledger.md | Durable deferred discovery memory | Preserve as a non-executable record, not a queue or authorization to create tickets. |
| .claude/settings.json; agent/WORKFLOWS.md; agent/scripts/desktop-scope-guard.sh | Durable Thebes source/configuration candidates | Preserve together. Existing changes register the desktop guard, document canonical checkout containment, and adjust Product push-deny patterns. Source classification is not behavioral acceptance of the guard. |
| agent/state/.claude-flow/ | Runtime-only session state | Keep locally; eligible for an exact ignore rule, not deletion or source checkpoint. |
| agent/state/.claude/agent-memory/ | Mixed local memory requiring curation | Keep every file. Contains reusable feedback as well as Product-specific state and local session knowledge. Do not blanket-delete or promote the directory wholesale. Curate durable workflow lessons separately before excluding this subtree from source history. |
| agent/scripts/supabase-incident-guard.sh; agent/scripts/supabase-incident-guard-postuse.sh; agent/scripts/incidents/ | Active incident tooling | Preserve in place, visible and untracked. CEO decision 2026-09-12: keep the incident active. Do not execute SQL or promote the permission lane into permanent doctrine. |

The backend-6 journal diff explicitly corrects a retired seat header and replaces
the empty-log placeholder with evidence. Numstat shows analogous three-line
deletions in backend-7 and backend-8; preserve these changes rather than restoring
old headers. A full content/credential review remains required before any source
checkpoint; this inventory is not a claim that every journal line was audited.

The incident manifest still records both payloads as used=false. This does not
prove the fixes were not applied by another route and does not prove closure.
No incident-hook reference was found in .claude/settings.json or
.claude/settings.local.json. The latter retains a permission entry for hashing
an incident SQL file; that is not an active hook. No removal is justified solely
by hook absence.

## Active incident decision — 2026-09-12

The CEO directed that the incident remain active. The incident scripts, manifest
and SQL payloads therefore remain in place and deliberately visible in `git status`.
They are not durable governance and are not committed or ignored. Active status
does not authorize execution, Product work, Jira changes or production access;
the existing payload-specific authorization and environment checks remain required.

## Exact next implementation slice

Introduce a dedicated atomic, revision-protected operating-mode record independent
of STOP/HOLD/FREEZE and ACCELERATE/NORMAL. Gate new Product claims and every Product
execution wake, including current-owner continuation. A mode transition must change
only its own record and preserve task lifecycle, ownership, executor evidence,
review context, dependencies, and interventions byte-for-byte.

Inspect store.py, queue.py and existing persistence/test conventions to choose the
smallest integration points. Update current mode terminology in CLAUDE.md and the
state/workflow documentation. Validate with isolated temporary state, including
unknown modes, concurrent/stale transitions, maintenance rejection, restored Product
gates and independent FREEZE behavior. Never run Product backlog acceptance tests
during this maintenance slice.

## Preservation boundary

No cleanup, stash, restore, reset, move, deletion, staging, commit, push, Product
execution, production access, or duplicate checkout is part of this reconciliation.
The initially dirty files remain evidence. Repository write permission is separate
from the accepted implementation scope; this session's configured writable roots
do not include the canonical Desktop checkout.
