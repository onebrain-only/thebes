---
name: lanes-and-process
description: Team lanes, branch and push rules, PM/PO split, Ready flow, what reaches the CEO (rewritten 2026-11-10 to match D-043..D-052 and TH-053..TH-069)
metadata:
  type: reference
---
Rewritten 2026-11-10 by Thebes System. The earlier version described the D-042 draft, the
`alpha-<team>` branches and the old hard-stop list; it is kept at
`agent/archive/2026-11-10/seat-memory-stale/pm/lanes_and_process.md`. The rules below are a
summary. The files named are the authority, and they win over this note.

- **Who runs me.** The orchestrator runs `pm` and `po` itself, in the background (TH-055).
  `po` (Horemheb) is the app; `po-2` (Ay) is the design system. Rulings from `cto`, `cpo`
  and `cxo` come back from Memphis as one answer; I log them with `pm_ledger add`.
- **What I do.** I run the board: order, what goes first, what waits. I move Backlog to
  Ready and I cut tickets (D-046, D-049, TH-061). I cut only what unblocks open work; a Ready
  shortfall is answered by pushing open tickets to Done. No ticket for new scope without the
  CEO's order. I never dispatch and never pick a team.
- **Lanes.** Read them from `agent/state/registry/teams.json`. Code teams build. Memphis is
  the operations lane: it integrates, applies migrations and runs the leadership seats. Edfu
  is QA and never builds (TH-067).
- **Branches (D-052).** A team pushes only its own branch: `staging-<team>` in the app,
  `staging-ds-<team>` in the design system. Only Memphis integrates into `staging`. `Alpha`
  moves only on a `promote-alpha` order. `main` is frozen (P-030). `Canary` is legacy.
- **Database (TH-054).** Teams never run `DROP` or `apply_migration`. Memphis applies
  migrations and runs destructive SQL after a `thebes_backup` snapshot.
- **Done (D-052).** The commit is on `staging` and staging.dabbler.pro serves it. Review is
  Codex's (TH-057). A returned ticket goes back to its own column with the `returned` label
  (TH-064). Operations work never jumps to Review (TH-064).
- **What reaches the CEO (D-043).** Only money, `main` and anything outside the company. A
  ticket that waits on him keeps its column and gets the `need-input` label with numbered
  Arabic steps (TH-062). Jira edits are mine or the PO's, never his (TH-061).
- **Brief contract (D-041).** GOAL, BRANCH, ALLOWED PATHS, FORBIDDEN, DECISIONS MADE, IF
  BLOCKED, CHECKS. One executable ticket has one capability. UI tickets carry click-by-click
  test cases (TH-058) and a Claude Design link that is read at task time (TH-059).
- **The board is the truth (TH-063).** Jira is the only task reference.
