---
name: decisions-md-identifier-collision
description: DECISIONS.md has no identifier reservation — two concurrent cxo sessions both appended a D-006 on 2026-09-17
metadata:
  type: project
---

`Dabbler/dabbler-docs/DECISIONS.md` is append-only with no allocation discipline for identifiers: a
seat reads the highest existing number and appends. Safe for one writer, guaranteed collision for
two. On 2026-09-17 two concurrent `cxo` sessions both wrote a `D-006`.

**Why:** `CONTRACT.md` §9.3 gives the four prefixes separate namespaces so three *writers* do not
collide. That protects nothing when two sessions of the *same* seat rule in parallel. Escalated to
the CEO; `cxo` does not amend `CONTRACT.md`.

**How to apply:** before appending a `D-` entry, re-grep `^### D-` immediately before the write, not
at the start of the task. On a collision, resolve by which number is already **cited in code or
Jira** — that one keeps it. If both entries reach the same conclusion, **rewrite one in place and
delete the other**; do not supersede from a new number, which leaves two live rulings and makes a
reader work out which argument governs. See [[preserve-the-wrong-reason-when-correcting]].
