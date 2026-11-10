# CLAUDE.md

Thebes keeps every Claude and agent file in `agent/` (CEO order 2026-11-10). Claude Code reads
this file and `.claude/` by fixed path, so only this stub and the harness config stay at the root.

The project instructions are in [agent/CLAUDE.md](agent/CLAUDE.md), imported here:

@agent/CLAUDE.md

Also in `agent/`: `AGENTS_DESK.md` (the root AGENTS.md desk card), `CONTEXT.md`, `docs/github-scheme.md`, agent memory
(`agent/memory/`, linked from `.claude/agent-memory`) and `claude-flow/`.
Plans and project docs live in `Dabbler/dabbler-docs/<project>/`.
Team checkouts are created on demand under `agent/state/runtime/worktrees/`.
