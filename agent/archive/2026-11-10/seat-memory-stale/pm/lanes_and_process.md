---
name: lanes-and-process
description: Team/lane facts, D-042 push rule, PM/PO split, ready dispatcher, label flow, hard stops
metadata:
  type: reference
---
Sources: agent/ORCHESTRATOR.md, agent/drafts/D-042-desk-dispatcher-operations.md (DRAFT, CEO review; parts built: Ready dispatcher, Memphis ops team, ops guard hook), D-032..D-041 in agent/DECISIONS.md.

- PO split: `po` (Horemheb) = app; `po-2` (Ay) = design system. A PO writes/completes briefs and accepts work for its own project only. PM supervises, is the knowledge hub, logs rulings with `pm_ledger add`.
- PM runs only in background when orchestrator gets a `priority` item (`board` kind). Moves To Do -> Ready in rank order, only what free teams can take; each needs ONE domain component (Auth, Listings, Social, Money, Platform) + Original estimate. Never dispatches, never picks a team.
- Ready dispatcher (agent.execution.ready_dispatcher): polls Jira ~60s, sends Ready tickets to a free team by lane; max 3 code teams in parallel; code -> code teams (Karnak, Luxor, ...), no-code and `ask` -> Operations team (Memphis; draft doc calls it Habu). Ticket lacking a complete brief gets a comment + label `needs-brief` (PO writes brief, removes needs-brief and brief-requested). `needs-ceo` label = awaiting CEO.
- Code teams: auto mode, write ONLY to own branch `<base>-<team>` (e.g. alpha-karnak); no Supabase writes, no push, no merge; deny rules enforce it (report `blocked: needs-ops`). Operations team: own settings, allowed apply_migration/execute_sql etc.; runs cto, devops, analyst subagents; integration into base is one serial INTEGRATE dispatch. Database writes are Memphis-only (ops guard hook, commit 8be6f1e).
- Integration delegated for Alpha ONLY. Canary and main stay with CEO; main FROZEN (P-030) - PR may be opened, never merged without CEO go.
- Brief contract (D-041): GOAL, BRANCH, ALLOWED PATHS, FORBIDDEN, DECISIONS MADE, IF BLOCKED, CHECKS. Review = code re-runs declared checks once (verify.py), MAX_CYCLES=2, judge checks to one reviewer. One executable ticket = one capability; features = non-executable parent + BLOCKS-linked children (design -> backend SQL -> ops apply migration -> frontend).
- Hard stops to CEO: main, production DATA, money/secrets, sending outside the company. Schema migrations delegated (draft): class A additive -> orchestrator; B DROP function/view/policy -> orchestrator after live-compat check; C DROP table/column, row deletes/updates, TRUNCATE -> needs CEO-written AUTHORIZED else needs-ceo.
- Decisions are delegated to the orchestrator (D-035); no bureaucracy: decide and go (D-035 addendum). Ticket lifecycle comments stay with the executing seat.
- Seats: PM/PO do not write code; PM does not write tickets (PO only). Strategy -> cpo, technical -> cto, experience -> cxo; log answers in pm_ledger.
- Codex "desk" is a DRAFT proposal (front for discussion/ticket intake); D-039 says CEO currently talks to the Claude orchestrator directly.
