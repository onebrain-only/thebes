# Misplaced agent-memory snapshot reconciliation

Date: 2026-09-12
Source: `agent/state/.claude/agent-memory/`
Disposition: preserve locally and exclude from Git as runtime residue.

This subtree is not the canonical local memory path. Runtime agent definitions
write to `.claude/agent-memory/`, and a directory comparison proved the two trees
diverge. The misplaced snapshot contains 26 Markdown files across backend-2 through
backend-7, cto, frontend-1, po and qa. It is neither a complete copy of canonical
agent memory nor a coherent source module.

Reusable workflow lessons represented in the snapshot include:

- catalogue sweeps do not prove PostgreSQL overload reachability;
- effective privilege, not a direct grant alone, determines anonymous execution;
- recomputation tests must distinguish recompute from increment;
- denied write tooling does not authorize a substitute write path;
- organisation authority and harness permission are separate facts;
- acceptance criteria must be reread before recording a verdict;
- Jira transition/tool failures require trying the authorised route, not inventing state;
- review closure ordering must preserve lifecycle and review-context coherence.

Product-specific or time-bound entries include live database observations, incident
write constraints, Jira cloud identity, KAN-167 QA story state, migration landing
notes and ticket-specific close procedures. Those are evidence, not standing Thebes
policy. Their operational history is already retained in the committed seat journals;
this record does not promote live Product observations into current doctrine.

No file in the snapshot was deleted, moved, merged into canonical agent memory or
executed. The subtree remains available locally for later forensic comparison. An
exact ignore rule prevents this misplaced runtime snapshot from keeping the Thebes
source tree dirty or being committed wholesale as a second memory authority.
