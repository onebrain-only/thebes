# D-042 — DRAFT (not active): the desk, the Ready dispatcher and the Operations lane

**Status:** DRAFT for CEO review, 2026-10-08. Nothing here is built or in force. Agreed in
conversation with the CEO on the points marked ✔; points marked ? are open or unverified.

## 1. What we are doing
Work should go from the CEO's ideas to verified, finished tickets with as little of the CEO's
attention and as few Claude tokens as possible. Thinking and discussion move to a cheap
front (ChatGPT/Codex, "the desk"); execution stays on Claude; **Jira is the only link** and
a ticket in `Ready` **is the order**.

## 2. Who runs where ✔
| Role | Runtime | Notes |
|---|---|---|
| Discussion, requirements, ticket writing (CPO and PM hats), market research, status answers | **Desk** (ChatGPT/Codex) | Reads git read-only, Jira, Notion; advice only, never binding rulings. Answers itself when it can; creates an `ask` ticket only when Claude is needed |
| Orchestrator + Jev | **One layer** (Claude model + code) | Dispatcher (code) does the routine; the model handles exceptions and decisions. **Runs no subagents** |
| Code teams (Karnak, Luxor, …) | Claude, `auto` mode | Work and push on their own branch only. No Supabase writes, no merge into a base branch. A hook enforces it |
| Operations team (Habu) | Claude, `auto` mode, own settings directory with allow rules | Runs subagents: cto (migrations, schema), devops (integration), analyst, cpo/cxo/po, judge reviewers |
| Verification | Code (`verify.py`) + one reviewer for `judge` checks | D-041 |

## 3. Flow ✔
1. CEO and desk discuss. Desk creates tickets in Jira (`To Do`, label `intake`) through a Thebes
   `intake` command, the single audited write path: template and CHECKS lint, duplicate search,
   a cap per call. The desk never holds Jira credentials.
2. CEO says "go" in the desk → the desk moves tickets that pass the lint to **Ready**. Ready is the order.
3. The dispatcher (a background process, polls Jira every ~60 s, zero tokens) takes Ready tickets,
   respects BLOCKS edges and a cap of 3 parallel teams, builds the brief from the ticket and
   dispatches by capability: code → code teams, no-code and `ask` → Operations.
4. Results are verified by code (D-041). Pass → Done. Fail → only the failing checks go back, once.
5. Anything that needs the CEO gets label `needs-ceo` plus a comment; the desk reports it.

## 4. Tickets ✔
- Types: `work`, `ask`. Field `executor: desk | claude` (default `claude` for anything touching
  repo or database). The desk may move its own `executor: desk` tickets between To Do, Operations
  and Done via a Thebes command; every other transition stays with Thebes.
- One executable ticket = one capability. A feature is a non-executable **parent** with
  children (design → backend SQL → **ops: apply migration** → frontend), linked by BLOCKS. Each
  child is verified by its own CHECKS; the parent closes after all children are Done.
- Every ticket carries GOAL, DECISIONS MADE, AUTHORIZED, FORBIDDEN, CHECKS (D-041 brief).
- **Ask:** "ask / find out / check / see / compare / analyse" in the desk means an `ask` ticket
  unless the desk can answer from git, Jira, Notion or the web, then it answers in the chat.
  An answer never starts execution; work needs a new "go". This is a desk skill.
- Non-code deliverables get a check of kind `exists` (file or comment present with the
  required headings) plus `judge` where an eye is needed. ? not built.

## 5. Decisions ✔
Jev and the orchestrator are one layer. Order of sources:
1. Written in the ticket (DECISIONS MADE, AUTHORIZED), authored by the CEO and the desk before work.
2. Routine actions: the Jev approval table (D-033).
3. Everything else: the orchestrator decides; if it needs an investigation it creates an `ask`
   ticket for Operations and does not block.
4. Hard stops go to the CEO: main, production **data**, money and secrets, sending outside the company.

Narrowing of the production hard stop: **schema** migrations are delegated; production **data**
and destructive schema changes stay with the CEO.

## 6. Migrations ✔
- A migration is its own ticket, executed in Operations by the cto subagent after review. Teams
  write the SQL and probes on their branch; the dispatcher detects `supabase/migrations/*` and
  creates the Ops ticket if the desk did not.
- Code extracts a migration request: objects touched, destructive statements, whether `main` or
  `Canary` use the objects (git grep), rollback notes, probes. Classes:
  **A** additive or `CREATE OR REPLACE` → orchestrator approves. **B** `DROP` of a function, view
  or policy → orchestrator approves after the live-app compatibility check passes. **C** `DROP`
  of a table or column, row deletes or updates, `TRUNCATE` → needs `AUTHORIZED` naming it, written
  by the CEO, otherwise `needs-ceo`.
- Supersedes the 2026-10-08 rule "no DROP / apply_migration on live Supabase" once built.

## 7. Branches and integration ✔
- Main branches: **Alpha, Canary, main**. Each team has one branch per base, `<base>-<team>`
  (e.g. `alpha-karnak`), not one per ticket. First step of every ticket: sync it from the base.
- Teams push their own branch (CEO 2026-10-09: branches keep teams apart; pushing is normal). They never merge into a base. Integration into a base is one serial `INTEGRATE` dispatch executed
  by Operations (devops). Delegated for **Alpha only**; Canary and main stay with the CEO, and
  main stays frozen (P-030).

## 8. Permissions and modes ✔
- Code teams: `auto` mode, **deny rules** on Supabase write tools (and push/merge), so a call is
  refused at once and the team reports `blocked: needs-ops` instead of waiting on a prompt.
- Operations: its own project directory and settings with allow rules for `apply_migration`,
  `execute_sql`, `list_migrations`, `list_tables`, `get_advisors`; destructive project tools
  stay denied. Per the docs an allow rule is resolved before the classifier, and a background
  session's mode persists across stop/resume. ? verify settings scoping by directory.
- **A session's mode cannot be changed by another session** (docs). No Planner session.
  `/plan <task>` at the very start of a message enters plan mode for that task. ? Unverified for
  our `--bg --resume` delivery; plan mode persists until the plan is approved (which then switches
  the session to an editing mode) or the user toggles it. Use only for work the CEO wants to
  approve before it runs; pure planning tickets use a plan-only brief instead. Test first.
- State `blocked` is never idle: the watchdog reports it at once with the pending tool.

## 9. Visibility ✔
A read-only `status` command (teams, state, why blocked, open dispatches, escalations,
verification), the `needs-ceo` label in Jira, optional pushed critical alerts, and a phone
notification through the orchestrator. The desk reads these; nothing wakes the desk.

## 10. Jira and GitHub ✔
Link for display only (GitHub for Jira on the `dabblersport` organisation, `KAN-123:` at the
start of every commit and PR title). Never enable automation that moves status from GitHub
events: Thebes owns the lifecycle.

## 11. Build order
1. Fix the watchdog (`blocked` ≠ idle; name the pending tool). 2. Deny rules for code teams and
the Operations settings directory. 3. Jira↔GitHub link. 4. `intake` command, ticket template,
`ask` skill, desk `AGENTS.md`. 5. The dispatcher, status command, `lane: code | ops` in the team
registry. 6. Migration tickets and classes. 7. End-to-end run with one small ticket.

## 12. Supersedes
D-034 (the orchestrator no longer runs seats), D-038 (the one Codex conversation becomes the
desk), the routing part of D-039, the "inferred ticket" part of D-040.
