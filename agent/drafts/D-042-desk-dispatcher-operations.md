# D-042 — DRAFT (not active): the desk, the Ready dispatcher, domain teams and Operations

**Status:** DRAFT for CEO review, updated 2026-10-09. Most of it is **built and proven live**
(marked ✔ built). The desk (§2, §3.1) is not built yet: it is the next step, and this
decision becomes active once the desk has run end to end. Items marked ? are open.

## 1. What we are doing
Work goes from the CEO's ideas to verified, finished tickets with as little of the CEO's
attention and as few Claude tokens as possible. Thinking and discussion happen on a cheap
front (ChatGPT/Codex, "the desk"); execution stays on Claude; **Jira is the only link**, and a
ticket in `Ready` **is the order**. Every routine step is code (zero tokens); a model is used
only where judgement is needed.

## 2. Who runs where
| Role | Runtime | Notes |
|---|---|---|
| Discussion, requirements, ticket writing, market research, status answers | **Desk** (ChatGPT/Codex) — ? not built | Reads git read-only, Jira, Notion. Writes tickets to Backlog only. Advice, never binding rulings |
| Orchestrator + Jev | **One decision layer** (Claude model + code) ✔ built | Handles exceptions and decisions. Runs **only the PM and the POs**, always in the background |
| PM (one, all projects) | Subagent of the orchestrator ✔ built | The knowledge hub and the board's priorities (§4) |
| PO per project | Subagent of the orchestrator ✔ built | `po` = app, `po-2` = design system; later admin, web. Briefs and acceptance for its project only |
| Code teams | Claude sessions, `auto` mode ✔ built | Five, each owning a domain (§5). Work and push their own branch |
| Memphis (Operations) | Claude session, `auto` mode ✔ built | The only team that writes to the database and integrates into Alpha. Runs cto, cpo, cxo, qa, devops, analyst as subagents: migrations, integration, rulings, `judge` reviews, questions |
| Ready dispatcher | Code, background, every 60 s ✔ built | Distributes Ready tickets; raises `priority` requests |
| Verification | Code (`verify.py`) ✔ built (D-041) | Re-runs declared checks; `judge` checks go to one reviewer |

## 3. Flow ✔ built (except 3.1)
1. **3.1 Desk:** the CEO discusses with the desk, which writes tickets into **Backlog (To Do)**.
   ? not built: the write path (a Thebes `intake` command or a connector) is the next step.
2. The dispatcher notices the Backlog changed (or Ready runs short) and raises one
   `priority_request`; the orchestrator's inbox hands it over and the orchestrator runs the
   **PM** in the background. At most hourly for board changes; at once for missing briefs.
3. The PM ranks the Backlog (new tickets, work returned from a failed verification, new
   sub-tasks), gives each ticket a domain component and an **Original estimate**, and moves only
   what the free teams can take into **Ready**, in rank order.
4. The dispatcher sends each Ready ticket to its **owning team** first (§5), in the PM's order.
   A ticket whose brief is incomplete gets one comment and the label `needs-brief`; the
   project's PO writes the brief (through a `priority` request) and the ticket is picked up.
5. The team works on its branch, pushes it, and reports. Verification re-runs the checks:
   pass → Done; fail → only the failing checks go back, once (D-041).
6. Anything that needs the CEO gets the label `needs-ceo` and a comment.

**Proven live:** KAN-441 (code, Luxor), KAN-442 (ask, Memphis), KAN-443 (no brief → brief
written → Karnak), KAN-444 (CPO + CTO rulings → PM → Ready → Memphis → verified → Done, a
real production permission change).

## 4. The PM and the POs ✔ built
- **The PM is the knowledge hub.** It reads, first in every run, its ledger
  (`python3 -m agent.execution.pm_ledger show`: every ruling by cpo, cto, cxo, the CEO and the
  decision gate) and its memory (`.claude/agent-memory/pm/`). Answers through the decision gate
  are logged by code; the orchestrator logs every other ruling at once. A PO that is stuck asks
  the PM first, and the PM must have the answer or obtain it.
- **The PM runs the priorities**: it is the one that moves Backlog into Ready. It never
  dispatches and never picks a team.
- **POs are per project** and work only on their project: complete briefs, accept work.
- **Teams can never reserve the PM or a PO** (enforced in the seat pool). So neither is ever
  busy inside one team while another team or the board needs it.
- Channels are flexible: anyone may ask the cto directly. The PM is not a gate every ticket
  passes through; it is the one who always knows.

## 5. Domain teams ✔ built
Each code team **owns one Jira component** (its domain):

| Team | Component | Domain |
|---|---|---|
| Karnak | Auth | Login, sign-up, accounts, users, delete/remove account, permissions |
| Luxor | Listings | Venues, games, meetups, listings and their creation |
| Habu | Social | Messages, friends (add/remove), followers, communication |
| Ramesseum | Money | Wallet, payments |
| Deir el-Bahari | Platform | Notifications, search, settings |
| Memphis | — (ops lane) | Operations |

- The owner gets its domain first, in the PM's rank order. A fresh owned ticket waits up to
  **30 minutes** for a busy owner, then any free team takes it. A team with nothing in its
  domain takes other work at lower priority.
- Each code team has a dedicated frontend, backend and ux-engineer seat. ux-engineer was
  raised from 2 to **5** (ux-engineer-3 Wadjet, -4 Meretseger, -5 Neith).
- At most 3 code dispatches run in parallel.

## 6. Decisions and rulings ✔ built
Jev and the orchestrator are one layer. Sources, in order:
1. Written in the ticket (DECISIONS MADE, AUTHORIZED) before work.
2. Routine actions: the Jev approval table (D-033).
3. Everything else: decided in the orchestrator layer. A **cto, cpo or cxo ruling** is ONE
   dispatch to **Memphis**, without a ticket, naming every seat it needs; Memphis runs them in
   parallel and returns one answer. The orchestrator never runs those seats itself.
4. **`judge` checks** follow the same rule: design fidelity → Memphis (cxo); behaviour →
   Memphis (qa). Only an acceptance judge on a project's own ticket may use that project's PO.
5. Hard stops stay with the CEO: main, production **data**, money and secrets, sending outside.
   **Schema** migrations are delegated (§7); production data and destructive schema stay the CEO's.

## 7. Migrations ✔ built
- A migration is its own ticket, applied by Memphis (cto) after review. Code teams write the SQL
  and probes on their branch and report `needs-ops`.
- Classes: **A** additive or `CREATE OR REPLACE` → approved in the orchestrator layer.
  **B** `DROP` of a function, view or policy → approved after checking that `origin/main` and
  `origin/Canary` do not use the object. **C** `DROP TABLE/COLUMN`, row deletes or updates,
  `TRUNCATE` → only with an `AUTHORIZED` line naming the migration, written by the CEO;
  otherwise `needs-ceo`.
- Before applying, compare the file with the live database: a stale file is reported, never
  applied (live 2026-10-09: four old files would have overwritten newer functions).
- Supersedes the 2026-10-08 rule "no DROP / apply_migration on live Supabase".

## 8. Branches ✔ built
- Base branches: **Alpha, Canary, main** (and `alpha-ds` in the design system).
- Each team has one branch per base: `<base>-<team>` (e.g. `alpha-karnak`), or
  `<base>-ds-<team>` in the design system. Not one branch per ticket. The dispatcher fills the
  team in, whatever the brief says.
- **Teams push their own branch normally** (CEO 2026-10-09: branches exist so teams never block
  each other), so commits show on their Jira tickets. Every commit starts with the ticket key.
- Teams never merge into a base, never push another team's branch, never force-push.
  Integration into a base is one serial `INTEGRATE` dispatch by Memphis, **Alpha only**;
  Canary and main stay with the CEO, and main stays frozen (P-030).

## 9. Permissions and the ops guard ✔ built
- One shared hook, `agent/scripts/ops_guard.py`, decides per session from its team binding:
  - Database **writes** (`apply_migration`, write SQL, edge-function deploys): Memphis only.
    Everyone else is refused at once (fail closed), so no session stops on a permission prompt.
  - **Read-only SQL** (one SELECT/WITH/EXPLAIN/SHOW, no write keyword, no non-allowlisted
    function call): allowed for every session.
  - Project-destroying Supabase tools (pause, restore, create project, delete/reset branch):
    the CEO only, Memphis included.
  - **Push** from a code team: its own branch only, as in §8.
- A session's permission mode cannot be changed by another session. `/plan <task>` at the start
  of a message puts that session in plan mode for that task (proven 2026-10-09); a normal
  message delivered by resume returns it to `auto`.
- ? Settings allow rules for pushing team branches and Alpha are the CEO's to add.

## 10. Visibility
- The orchestrator's inbox: results, `verification`, `judge`, `priority`, alerts. The waiter
  restarts itself when Thebes code changes ✔ built.
- The `needs-ceo` label in Jira. ? A read-only `status` command for the desk: not built.
- ? The watchdog does not yet tell a `blocked` session (waiting on a permission) from an idle one.

## 11. Jira and GitHub ✔ built
GitHub for Jira is connected (all `dabblersport` repos), for display only. Never enable
automation that moves a status from GitHub events: Thebes owns the lifecycle.

## 12. Still to build
1. The desk: ChatGPT/Codex writes tickets into Backlog (write path, ticket template, the `ask`
   skill, `AGENTS.md`). Then one end-to-end run from a conversation to Done.
2. A start-up script for the dispatcher, the watchdog and the team sessions after a reboot.
3. The watchdog's `blocked` state; the read-only `status` command.
4. Archive `agent/status/po.md` (437 KB; the PM could not read it whole).

## 13. Supersedes
D-034 (the orchestrator runs seats), D-038 (one Codex conversation as the front), the routing
part of D-039, the "inferred ticket" part of D-040, and D-037's rule that a team may hold a PO.
