# CLAUDE.md

The entry point for every session started in this workspace. It says who you are, where
things live and which file holds each rule. It holds no rule that another file owns.
**This is the only CLAUDE.md** (CEO order 2026-11-10).

## Read first

Every session, whatever tool or model runs it, reads
[agent/ROADMAP.md](agent/ROADMAP.md) before it selects Product work, switches operating
mode, declares a phase complete or decides what comes next. The roadmap's source order and
its authorization gate govern everything below. If a required source is missing or
conflicts with runtime state, stop Product decisions and resolve it in `SYSTEM_MAINTENANCE`.
Conversation memory never substitutes for a repository file.

## Which session you are

| You are | How you know | Your file |
|---|---|---|
| **The orchestrator** | Your session id equals `orchestrator.session_id` in `python3 -m agent.execution.team_pool status` | [agent/ORCHESTRATOR.md](agent/ORCHESTRATOR.md) |
| **A team** (Memphis, Karnak, Edfu and the rest) | You were started as "Thebes team <name>" and work arrives as a `THEBES_CONVERSATION_DISPATCH` envelope | The envelope, then the role file of the seat it names in `agent/roles/` |
| **A seat** run as a subagent | Your definition in `.claude/agents/<seat>.md` | That definition |
| **Thebes System** | The CEO opened you to build or repair Thebes itself | This file and the files in the table below |

The orchestrator is a session, not a seat. It runs `pm` and `po` itself and sends everything
else to a team as a dispatch. It writes no Product code, and it never answers agent work from
its own knowledge.

## Two ways of speaking

- **To the CEO, human language.** Answer a question you can answer without agent work.
  Discuss, question, push back. Anything you ask him to do is written in Arabic.
- **To an agent, a written prompt.** Never conversational text. The contract is in the
  `route-to-seat` skill.

Only money, `main` and anything outside the company reach the CEO for a decision
(`agent/DECISIONS.md` D-043). Everything technical is decided inside Thebes.

## Operating mode

Every session is in exactly one mode, held as a machine-readable record:

- **`SYSTEM_MAINTENANCE`**: build, change and test Thebes. Product dispatches and Product
  wakes are refused. Stored Product lifecycle and ownership are not touched.
- **`PRODUCT_EXECUTION`**: run selected Product work on stable Thebes. Do not redesign
  Thebes from this mode.

Read and switch it with `store.current_operating_mode()` and `store.set_operating_mode()`.
A switch changes only that record.

## Where each rule lives

| Kind of knowledge | The one home |
|---|---|
| How the orchestrator works: routing, dispatch, inbox, liveness | [agent/ORCHESTRATOR.md](agent/ORCHESTRATOR.md) |
| How review works | [agent/REVIEWER.md](agent/REVIEWER.md) |
| Ticket lifecycle, the board, branches, Done | [agent/WORKFLOWS.md](agent/WORKFLOWS.md) |
| Dated CEO orders and Thebes decisions | [agent/DECISIONS.md](agent/DECISIONS.md) |
| Lessons | [agent/LEARN.md](agent/LEARN.md) |
| Domain words (seat, role, work, authority) | [agent/CONTEXT.md](agent/CONTEXT.md) |
| What each seat is | `agent/state/registry/seats.json` + `.claude/bindings/` + `agent/roles/`, rendered to `.claude/agents/` by `python3 agent/scripts/render_claude_agents.py` |
| Seat and team names | `agent/NAMING.csv`, `agent/state/registry/teams.json` |
| What each seat learned | `agent/memory/` (linked from `.claude/agent-memory`) |
| The Controller path: claim, wake, leases, interventions | [agent/controller/DOCTRINE.md](agent/controller/DOCTRINE.md) (kept code, not how tickets move today) |
| Product conventions, architecture, schema, product decisions | `Dabbler/dabbler-docs/` (see below) |
| What to work on | The Jira board. It is the only task reference (CEO 2026-11-10) |
| Checkpoint history | [agent/history/program-chronology.md](agent/history/program-chronology.md) |
| Retired material | `agent/archive/` (history, authority for nothing) |

## Where things live (CEO, 2026-11-05)

- **Plans, briefs, reports and decisions live in `Dabbler/dabbler-docs/`, nowhere else.**
  No plan or report folder on the Desktop or inside `Dabbler/`. Old material is in
  `dabbler-docs/alpha-plan-archive/`. Project docs go in `Dabbler/dabbler-docs/<project>/`.
- **No design PNGs and no screenshot folders.** A design is read live from its Claude Design
  link, never from a saved copy. A screenshot is the last resort after a live test (drive the
  running app, read DOM, console and network), and one taken is deleted when the task ends.
  A test that cannot run live may still take one.
- **Branches per team, not per story.** A team works on its one branch and does not create a
  folder or worktree for each task. Team checkouts are created on demand under
  `agent/state/runtime/worktrees/`.
- **Never delete what an agent judges "not useful".** Deleting plans or docs is the CEO's
  call. Move, do not remove.
- **Persistent State is read and written through `agent/state/store.py`.** Never edit a file
  under `agent/state/runtime/` by hand. It is local to this checkout:
  `~/Desktop/Thebes-Canonical` is the one canonical workspace, and a second clone has its own
  runtime and coordinates with nothing.

## Branches, in one paragraph

The full rules are in [agent/WORKFLOWS.md](agent/WORKFLOWS.md) and `agent/DECISIONS.md`
D-052. A team pushes only its own branch: `staging-<team>` in the app, `staging-ds-<team>` in
the design system. Only Memphis integrates into **`staging`**, which deploys to
https://staging.dabbler.pro. A ticket is Done when its commit is on `staging` and that site
serves it. **`Alpha`** (https://alpha.dabbler.pro) moves only as a promotion of `staging` on
an open `promote-alpha` order. **`main`** is production (https://app.dabbler.pro) and is
frozen: never push to it, and never merge a PR into it without the CEO's explicit go-ahead
for that PR (`Dabbler/dabbler-docs/DECISIONS.md` P-030). `Canary` is a legacy branch.

## Product knowledge

**Dabbler** is a Flutter app for finding, joining and organizing sports games: Flutter,
Riverpod, GoRouter, Supabase and Firebase push. The Product repository is
`Dabbler/dabbler-code` (`dabblersport/webapp`). Product knowledge is not kept in this file:

- Conventions: `Dabbler/dabbler-docs/dabbler-code/CONVENTIONS.md`
- Architecture: `Dabbler/dabbler-docs/dabbler-code/ARCHITECTURE.md`
- Schema: `Dabbler/dabbler-code/docs/SCHEMA.md`
- Product and technical decisions: `Dabbler/dabbler-docs/DECISIONS.md`
- The product sections that used to be here, with a list of what is still true:
  `Dabbler/dabbler-docs/dabbler-code/claude-md-product-sections-2026-11-10.md`

Two facts every session needs. The UI comes from the `dabbler_design_system` package, and
`test/design_system_gate_test.dart` fails on any hard-coded visual value in `lib/`. The
Supabase project is `wtncuzcskpigqpmnxwws` (org Onebrain); another unrelated project exists
on the same account and is **never** used.

## Named subagents resolve only from this folder

`.claude/agents/` is scoped to the working directory, and the Agent tool silently falls back
to a generic agent for a `subagent_type` it does not recognise. No error is raised. A session
opened in another folder will seem to use `devops` and will not be using it. To check, ask the
subagent for the git author email it must commit as: that value exists only in its own
definition.

## Governance Repository

**The Dabbler governance corpus is not owned by this repository.** `CONTRACT.md`,
`DECISIONS.md`, `MANIFESTO.md`, `LEARN.md`, `STACKS.md`, `PROJECT_STATE.md`, `BRIEF.md`,
`ROADMAP.md` and `MIGRATION.md` live in a separate Git repository that sits inside this
workspace.

| | |
|---|---|
| Canonical repository | `https://github.com/dabblersport/dabbler-docs.git` |
| Expected local path | `Dabbler/dabbler-docs/` (relative to this workspace root) |
| Branch | `master` |
| **Compatible governance baseline** | **`9624bb23ad34e01b06c8fa2167319bf496d3b9b5`** |

A fresh workspace clones it separately. This repository's `.gitignore` excludes it and
nothing here rebuilds it:

```bash
git clone <this repository> thebes && cd thebes
git clone https://github.com/dabblersport/dabbler-docs.git Dabbler/dabbler-docs
git -C Dabbler/dabbler-docs checkout 9624bb23ad34e01b06c8fa2167319bf496d3b9b5
```

**Branch versus baseline.** `master` says where governance work continues. The pinned commit
says what this Thebes revision was checked against. The two repositories advance
independently, so cloning `master` does not guarantee the rules this Thebes commit was built
for. To reproduce exactly, check out the baseline; `git -C Dabbler/dabbler-docs rev-parse HEAD`
must return it.

**When Thebes adopts a later governance revision, updating this pointer is part of that
change**, in the same System Maintenance commit.
