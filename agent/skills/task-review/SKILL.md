---
name: task-review
description: Use when judging whether work meets its acceptance criteria and fits the project — either as the substance of a validation review (SELF, PEER or QA) or when po is asked to settle a scope or acceptance question. Triggers on "review this ticket", "is KAN-NN done", "did this meet its acceptance criteria", "does this fit what we said". Applies two gates — the acceptance criteria, and alignment with the governance docs — and produces a written verdict. It is NOT a board column gate and does not itself transition a ticket.
---

# Task Review — acceptance judgement, not a column gate

> **NARROWED 2026-09-08 (Wave 5).** This skill used to be `po`'s universal gate on the
> `In Review` column: every ticket passed through it, and it ended in a `po` transition to
> `QA-Test` or back to `Ready`. **That gate is retired, and both of those columns are gone** —
> `In Review` (id 10006) is now a **legacy** status with no board column, and the `Review`
> column instead holds three alternative validation routes: `QA-Test` (10009),
> `Self-review` (10044) and `Peer-review` (10045).
>
> **What survives is the judgement, which was always the valuable part.** Use it for:
>
> 1. **the substance of a validation review** on any route — SELF, PEER or QA. The route owner
>    asks these two questions of the work regardless of who the owner is; and
> 2. **`po`'s acceptance authority**, when a route owner or the CEO raises a scope or
>    acceptance question.
>
> **This skill no longer decides a transition.** The review owner does that, on the item's
> route. Do not transition a ticket because this skill returned PASS.

A claim that work is done is a claim, not a fact. Your job is to test the claim.

Two outcomes only. **PASS** or **REWORK.** There is no "Done with notes" — a note that matters
is rework, and a note that does not matter should not be written.

---

## Prime directive

> **Verify, do not trust.** The ticket says what someone intended. The repo says what
> happened. When they disagree, the repo wins.

A review that passes everything is not a review. A review that fails everything is
not a review either. **Cite evidence for every judgement**, pass or fail.

---

## The two gates

A ticket passes only if **both** gates pass. Either one failing sends it back.

### GATE 1 — Acceptance criteria

Every acceptance criterion in the ticket description, checked individually against
the repo.

- **Read the criteria literally.** "Matrix covers every path with zero blanks" means
  you count the rows and look for blanks. It does not mean "a matrix exists".
- **Find the evidence yourself.** `file:line`, a command you ran and its output, a
  measurement. Never accept the ticket's own claim, a commit message, or an agent's
  report as proof.
- **A criterion you cannot verify has failed.** Unverifiable is not passed. Say
  which criterion and why it could not be checked.
- If the criteria themselves are wrong, ambiguous, or describe work that no longer
  makes sense, **that is a fail** — send it back naming the problem with the
  criteria. Do not silently reinterpret them into something achievable.

### GATE 2 — Alignment with the project's own logic

The work must fit the system, not just satisfy its ticket. Check it against `docs/`:

| Document | What you are checking |
|---|---|
| `docs/DECISIONS.md` | **The tie-breaker.** Does this contradict an ACTIVE decision? If it does, it fails, whatever the ticket said. |
| `docs/MANIFESTO.md` | Does it violate a non-negotiable, or the definition of done? |
| `docs/CONTRACT.md` | Did the agent write outside its permission boundary? Writing the right code in the wrong file is a fail. |
| `docs/CONVENTIONS.md` | Naming, structure, error handling, design-system rules. |
| `docs/SCHEMA.md` | Does a data change match the documented schema and RLS position? |
| `docs/ROADMAP.md` | Is this in the wave it claims to be, and does it belong there? |
| `docs/ARCHITECTURE.md` | Does it respect the layering and data flow? |

**Precedence when documents disagree:** `DECISIONS.md` (newest ACTIVE) →
`MANIFESTO.md` / `CONTRACT.md` → `CONVENTIONS.md` → everything else.

### When a governance document is still an empty spec

Several `docs/` files currently carry a `FILE STATUS: EMPTY — SPEC ONLY` banner.

**Say so. Never pass Gate 2 silently on an unwritten rule.** Record in the verdict
which documents you could not check against, so the pass is honest about its own
limits. A pass that claims alignment with a file that does not yet say anything is
a false pass, and false passes are what this agent exists to prevent.

---

## The review procedure

1. **Read the ticket in full** — description, acceptance criteria, every comment.
2. **Establish what actually changed.** `git log`, `git diff`, the files on disk.
   Run `.claude/skills/task-review/scripts/evidence.sh <KAN-NN>` for the mechanical
   sweep, then reason on top of it.
3. **Gate 1** — walk the criteria one at a time, gathering evidence for each.
4. **Gate 2** — read the relevant `docs/` files and check the work against them.
5. **Decide.** Both gates pass → **PASS**. Anything fails → **REWORK**.
6. **Write the verdict as a Jira comment.**

**Comment first.** A verdict with no explanation is indistinguishable from a guess.

**Then stop.** Whether the item moves, and where, belongs to its review owner on its route —
SELF the worker, PEER the reviewer, QA the `qa` seat. **If you are that owner, transition on
your own route.** If you are `po` answering an acceptance question, you are not.

---

## Verdict format

### PASS

```
✅ ACCEPTANCE PASSED

GATE 1 — Acceptance criteria
- [criterion] → PASS. Evidence: <file:line / command + output>
- [criterion] → PASS. Evidence: ...

GATE 2 — Project alignment
- Checked against: DECISIONS.md, CONVENTIONS.md, CONTRACT.md
- Could NOT check against: <files still empty specs>
- No conflicts found. <specific note on anything notable>

Judged by <seat>. Transition belongs to the review owner on this item's route.
```

### REWORK

The comment **is the rework brief.** Another agent picks up this ticket with no
memory of it — write for that reader.

```
🔁 REVIEW FAILED — moving back to Ready

WHAT IS WRONG
1. <criterion or rule> — FAILED.
   Expected: <what the ticket or doc requires>
   Found:    <what is actually there, with file:line>
   Fix:      <the specific change needed>

WHAT IS ALREADY FINE — do not redo this
- <what passed, so the rework does not undo good work>

WHERE TO START
<the first concrete step>

BLOCKED ON
<a PO decision, or "nothing">

Reviewed by po.
```

**Rules for a fail comment:**
- Name the file and line. "The contract is incomplete" is not actionable;
  "`docs/CONTRACT.md` matrix has no row for `supabase/functions/**`" is.
- **Always include WHAT IS ALREADY FINE.** Rework that undoes correct work is worse
  than no rework, and an agent with no context will redo everything unless told.
- Never write the fix yourself. You review; you do not implement.
- Separate "the work is wrong" from "the ticket is wrong". Both are fails; they need
  different rework.

---

## Independence

**Never review your own work.** If the ticket was executed by the same agent doing
the review, stop and say so — self-review provides no signal. Escalate to the PO.

You are **read-only on the codebase**. You never fix, refactor, or tidy what you are
reviewing, however small. The one thing you write is the Jira comment and the
transition. Work you discover that is out of scope becomes a new ticket, not an edit.

---

## Jira mechanics

Site cloudId `18c8e9f5-d139-4e03-b5d8-89122cc14937`, project `KAN`.

Transitions on this board (verified, global — any status reaches any other):

| Status (exact name) | Transition id | Status id | Column |
|---|---|---|---|
| `To Do` | `11` | 10004 | Backlog |
| `Ready` | `2` | 10008 | Ready |
| `Design` | `9` | 10047 | Operations |
| `Content` | `10` | 10048 | Operations |
| `Operations` | `12` | 10049 | Operations |
| `Front-end` | `8` | 10046 | Frontend Development |
| `Back-end` | `5` | 10043 | Backend Development |
| `QA-Test` | `3` | 10009 | Review |
| `Self-review` | `6` | 10044 | Review |
| `Peer-review` | `7` | 10045 | Review |
| `Done` | `41` | 10007 | Done |

**The transition ids break every pattern you might guess** — `Ready` is `2`, `Back-end` is `5`,
`Operations` is `12`. **A column is not a status:** `Operations` and `Review` each group three
statuses, so a column name cannot be sent to the API. **Match on the id, never the name**;
`agent/state/board.py` is the machine-readable source.

**These ids are here so a review owner can act on its own verdict, not so this skill can
transition.** Re-fetch with `getTransitionsForJiraIssue` rather than trusting this table.

Find work with JQL: `project = KAN AND status in ("QA-Test", "Self-review", "Peer-review") ORDER BY created ASC`
(oldest first — a ticket waiting in review blocks whatever depends on it). **An item with a
null review owner is waiting for an authorised validator; that is a correct state, and the fix
is for the CEO to name one — not to route around it.**

## Constraints

- Two outcomes. Never leave a judgement unposted after making it.
- Never pass a criterion you could not verify.
- Never move a ticket without a comment explaining why.
- No sycophancy. A pass is a finding, not a compliment.
