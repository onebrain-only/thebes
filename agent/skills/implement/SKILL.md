---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /code-review to review the work.

Commit your work to the current branch. In Thebes that is your team's one branch
(`staging-<team>`); you never merge into `staging`, `Alpha` or `main` (`agent/WORKFLOWS.md`), and the
reviewer is Codex (`agent/REVIEWER.md`), so `/code-review` here is your own check, not the gate.
