---
name: capacity-to-date
description: How a team lead converts capacity into a due_date without estimating, and the sitting unit that makes it arithmetic. Use whenever a date is asked for, challenged, or compressed — "when can this land", "can we finish by Friday", a re-date after a ticket runs early or late; whenever work is sized against any shared single-writer seat whose queue you do not own; whenever an exclusive grant collapses a chain onto one seat; and whenever a task cannot be sized and the honest output is a named blocker instead of a number.
---

# Capacity to date

`agent/WORKFLOWS.md:58` states the rule the whole company's scheduling runs on:

> **The date comes from capacity, not estimation.** Capacity is reported by the owning
> `team-lead-N`. The `po` may not estimate it and may not ask a developer directly.

That is a prohibition with no method behind it. A lead reading it learns what it must not do
and nothing about what to do instead. **This skill is the method.** It is written from the
five Phase 0 tickets `KAN-121`–`KAN-125`, where every number on the board came out of this
process.

**The distinction, made operational.** An estimate answers *how long will this take* — a
guess about the future wearing a number. Capacity answers *how many units does this task
consume, and how many can this seat absorb* — a count. The difference is that capacity is
**countable before the work starts** and an estimate is not. Everything below is counting.

## 1. The sitting — the unit

> **A sitting is one uninterrupted pass at a ticket by one seat, ending at a checkpoint
> where the work can be handed off, reviewed, or abandoned without losing state.**

The unit is already in live use — `KAN-124` is a two-sitting ticket on the board, and `po`
and `devops` both schedule in it — and it was defined nowhere until this file.

**The checkpoint is what makes it a sitting. Elapsed time does not.** Two sittings run
back-to-back are still two sittings, because the checkpoint between them is still there.
Hold this exact line under pace pressure: *"we work 24 hours"* is not an argument that the
work is smaller, and running two passes end to end does not merge them into one.

**A sitting is not a day.** The board renders sittings as calendar dates because `due_date`
is a date field. That mapping is a separate, stated assumption owned by `po` — see §2 input
4 and the open question at the end. Report sittings; do not report days.

### Counting sittings on a ticket

**One sitting** — the whole population of changes is enumerable before starting, and every
change is the same kind. The work is *mechanical*: you can write down what "done" looks like
in full before touching anything.

- `KAN-121` (P0-1): write one golden test file. One deliverable, one kind.
- `KAN-122` (P0-2): move 3 files, rewrite 42 import lines across 39 files. Every one of the
  39 was enumerable in advance by `grep -rln "misc/data/datasources" lib/ test/` before the
  ticket opened.

**Two or more sittings** — the ticket contains a **judgement whose output the next part of
the same ticket consumes**. That dependency boundary *is* the checkpoint, and it is what
makes the count go above one.

- `KAN-124` (P0-3b): bucket 80 top-level route entries into 6 module files, then extract
  them, and prove it with `KAN-121`'s golden test green **with no edit to the golden file**
  (`STACKS.md` §10.3). The extraction cannot start until the bucketing is settled, and the
  bucketing can be wrong. Sitting 1 ends at *modules exist, golden test not yet green* —
  a real checkpoint: reviewable, abandonable, and not done.
- `KAN-128`: author one migration, then run the AC-3 probe pack. Sitting 1 ends at
  *migration body complete and posted in `G-002` format*; sitting 2 is the probes and their
  fixtures. (An earlier version of this line carried a probe-mechanics claim, quoted from
  `senior-backend` and since retracted by it — see the mechanism proxy below. Probe mechanics
  are ticket content and do not belong here; the checkpoint is what this example is for.)

  **This example was published branched, and the branch is the lesson.** Who authored the AC-3
  probes was open: **`cto` owning them made it 1 sitting on `senior-backend`; shipping them with
  the migration made it 2.** It resolved — `cto` ruled that `senior-backend` authors the probes
  (`DECISIONS.md` commit `d939a74`) — so **the count is 2**. Read from the ticket at
  `updated 2026-09-06T05:33:20`, which also carries `due_date` **2026-09-10** as
  `team-lead-4`'s calendar ceiling against an earliest-believed 2026-09-09.

  **The sittings ceiling is 3**, read first-hand at `updated 2026-09-06T05:38:40`:
  *"Ceiling corrected 2026-09-06: 3, not 2"* — `senior-backend`'s own self-correction, on the
  reasoning that with the branch closed at a count of 2, a ceiling of 2 would carry no budget
  at all.

  **One budget, two units — not two budgets.** The ticket is explicit that
  `senior-backend`'s ceiling-3-in-sittings and `team-lead-4`'s 09-09→09-10 calendar gap are
  *the same* rework cycle expressed differently, which is why `due_date` stayed 2026-09-10
  when the sittings ceiling moved. **When you report both units, say they are one budget** —
  otherwise a reader adds them and inflates the ticket by a cycle it does not have.

  *(This block briefly asserted "ceiling 2 either way", then "the ceiling is 3" on a relay,
  then flagged it as contested after a read that was itself five minutes stale. Three wrong
  states before a correct one, on a number whose owner had it right throughout — a compact
  demonstration of §3's rule about a peer's count, produced by the document that states it.)*

  **The branch is kept here because reporting it this way is the point.** A bare "2" teaches
  the arithmetic; *"2, or 1 if a named seat owns a named deliverable, and here is who was
  asked"* teaches §4, which is the part leads get wrong. And note what happened when the ruling
  landed: the branched version needed **no rewrite**, only a resolved parenthetical, while a
  version that had guessed the number would have been silently wrong until someone checked.
  Report a branch this way rather than resolving it to the number you prefer.

### Neither risk nor volume is a checkpoint. A dependency boundary is.

**The test is whether the ticket's next part cannot start until the judgement lands** — not
how likely the judgement is to be wrong. This is the distinction a lead gets wrong at speed,
and it was got wrong on `KAN-128` before `senior-backend` corrected it.

The tempting reading was that `admin_wallet_adjust`'s signature change is a checkpoint because
it is an interface commitment with no caller to validate against, so it is hard to verify. It
is not a checkpoint: the signature is **ruled** by `T-049` (caller-generated uuid,
`NULLS NOT DISTINCT` explicitly rejected), it has **zero callers to migrate**, and its output
is consumed by one `ALTER COLUMN ref_id SET NOT NULL` in the same file. That is a decision
taken *inside* a pass.

In `senior-backend`'s own words, confirmed first-hand: *"less checkable raises the odds of a
rework cycle, which is why my ceiling is 2 rather than a flat 2. But §1's test is dependency,
not risk."*

**Risk is not discarded — it is banked in the ceiling.** Say that in the same breath as the
rule, because a lead who takes only *risk is not a checkpoint* may conclude risk goes nowhere,
which is worse than the error it replaces. Hard-to-verify work lands in the gap between your
earliest and ceiling columns (§2). That gap is where it is supposed to go, and pricing it there
is what makes the two-column report do real work. It does not buy a sitting.

**The failure is substituting a proxy for the test, and risk is only the nearest one.** The
test is a single question — *can the next part start before this lands?* Under time pressure a
lead reaches for whichever proxy is closest to hand and answers an easier question that feels
like the same one. Two have now been caught on the same lead, by the same seat:

| Proxy | The reasoning that feels right | Why it fails |
|---|---|---|
| **Risk** | less checkable, therefore a checkpoint | raises the odds of a rework cycle; creates no boundary (`KAN-128`) |
| **Volume** | materially bigger, therefore more sittings | adds no boundary unless it adds one (`KAN-130`/`KAN-131`) |
| **Mechanism** | this must be proven the way it fails in production | sizes the mechanism you want to prove, not the thing under test (`KAN-128`) |

On the volume case, `senior-backend` again: *"Volume shifts the start, not the cost — that is
your own argument about the `payment_intents` cut, and it runs symmetrically: lighter mechanical
work buys back no sitting, and heavier mechanical work adds none unless it adds a **boundary**.
I went looking for a second boundary and could not find one."* The bundle came back **2 sittings,
ceiling 3** — the same shape as the ticket it was supposed to dwarf.

**The mechanism proxy is worth reading closely, because it caught the seat that wrote the rule
about it.** Sizing `KAN-128`'s probes, `senior-backend` reasoned that a replay must be
demonstrated the way it fails in production — concurrently — since a sequential retry through
the trigger is absorbed by the `EXISTS` guard before the insert. True, and beside the point:
**the thing under test is the unique index, not the trigger.** Two direct inserts sharing the
key show it sequentially — pre-index 2 rows, post-index 1 — and concurrency-safety is then
*inherited* from the index rather than reproduced, which is the whole reason `T-049` chose a
constraint over the guard. The proxy substituted **the mechanism it wanted to prove** for
**the thing under test**, and it survived a correctness argument that was itself correct.

**Expect a fourth proxy you have not met.** Test a proposed sitting by naming the boundary out
loud; if the sentence that justifies it does not contain *"cannot start until"*, you are holding
a proxy.

*(Three instances. Two are one lead's, caught by `senior-backend`; the third is
`senior-backend`'s own, caught by itself. **Still a hypothesis about how the test gets misread,
not a measured pattern** — a third instance from a second seat strengthens it and does not make
it measured. Worth noting that the deflation half below comes from `senior-backend` first-hand,
on a different ticket, from a seat that is not a lead and has never read this document as one:
a second source of a different kind, which is worth more than another instance of the same.)*

**Read the next paragraph with this one, or the correction overshoots.** A proxy substituted for
the test **inflates**. The test applied to an unresolved fact **deflates**. Learning only the
first produces a lead who strips sittings it should have kept.

### The third answer shape: the boundary waits on a fact nobody has yet

§1's question has an answer neither `KAN-128` nor `KAN-130` had. Sometimes the next part waits
not on a judgement you will make, but on **a fact someone must go and find out** — and it can
come back either way.

Asked *"can the next part start before this lands?"* of that shape, the honest-feeling answer is
**"yes, if the fact goes the way I expect."** That is not an answer. It produces a confident
single number and a re-cost on the day the fact arrives, which is the worst of both: the
certainty of a firm estimate with none of its basis.

`KAN-130`'s `financial_ledger` erasure question is exactly this shape — it needs a `cto`/`cpo`
ruling, and `senior-backend` reported it as *"if it resolves to also scrub `financial_ledger`,
the count goes to 3"* rather than sizing past it.

**This routes to §4, not to a sitting count.** The output is *"cannot size until X, and Y holds
it"*, with everything that does not depend on X sized anyway. §1's question does not carry you
there on its own — that is why this paragraph exists. **When the answer begins with "yes, if",
stop counting and go to §4.**

### The opposite failure: a partial finish dressed as a checkpoint

The inflation direction, and it is seductive. The worked example is `senior-backend`'s own
first checkpoint on `KAN-128`, which it proposed and then discarded — a seat rejecting its own
boundary, which is better evidence than a lead rejecting someone else's:

> *"The migration file holds the constraints and 6 of 7 conflict clauses; `admin_wallet_adjust`
> untouched — reviewable and abandonable, and **not applicable**, because `ref_id NOT NULL`
> breaks `:2982` until sitting 2 lands."*

It argued that the un-appliability was what made it a checkpoint. **It is the opposite.** A
migration that cannot be applied is not a state anyone can hand off, review to a verdict, or
abandon and still have something — it is half a file, with its incompleteness dressed up as the
evidence for its completeness.

**The tell: *"it cannot be applied yet"* sounds like a boundary and is only a middle.** Test a
proposed checkpoint by asking what a reviewer would do with the artifact if the ticket stopped
there. If the answer is "nothing, it doesn't work yet," it is a pause.

### Mechanical tickets finishing early is not evidence a judgement ticket is smaller

`KAN-121` and `KAN-122` both ran clean at one sitting on 2026-09-05, faster than their board
spacing. That is what a correctly-sized mechanical ticket does — it is evidence the *spacing*
carried slack, not that the *sizing* was generous. It says nothing about `KAN-124`, which is
the only Phase 0 ticket carrying design judgement.

**Shift the start; keep the cost.** Two clean mechanical tickets buy a schedule shift and
never a re-size.

**The same rule runs in the other direction, when scope is cut mid-ticket.** Everyone's
instinct is that a smaller ticket lands sooner, and for a judgement ticket that is usually
false. `KAN-128` had `payment_intents` dropped from its scope on 2026-09-06 (no SQL writer
exists for it, so a bare constraint would have been the failure `T-049` forbids). The cut
removed DDL volume from the authoring pass and touched nothing about the probe pack that makes
the ticket two sittings. **Ask which sitting the cut came out of.** If it came out of the
mechanical one, the cost is unchanged and only the start moves.

**It runs symmetrically, and the upward direction is the one that catches people.** Lighter
mechanical work buys back no sitting; heavier mechanical work adds none — unless it adds a
boundary. A lead who has internalised the cut direction will still expect a materially bigger
ticket to cost more, because the symmetry is not obvious from reading only the downward case.
It is the same rule.

## 2. Capacity to date — the arithmetic

The conversion has exactly four inputs. **A lead supplies three and never the fourth.**

1. **Sittings per ticket** — from §1, with the reason named for anything above 1.
2. **Serialisation** — which tickets can run at the same time, and why. Phase 0: zero
   parallelism, one seat (§5).
3. **Gates and hand-offs** — everything inside the ticket that is not the author's own
   sitting. Both run on other seats' clocks and both are counted separately. Never fold
   either into a sitting.
   - A **gate** is acceptance. `WORKFLOWS.md`: *a slot frees on acceptance, not delivery* —
     a seat that has handed work to review still holds its slot. A chain of N tickets costs
     **N sittings plus N gates**.
   - A **hand-off** is a sitting on a different seat than the author, inside one ticket, that
     is *work* rather than acceptance. `KAN-128` is the shape: `senior-backend` authors the
     migration, **`cto` applies it**, `po` gates it — two sittings, one hand-off, one gate,
     across three seats. A hand-off serialises the ticket internally, so it is a dependency
     as well as a cost.

   **Each leg is sized by the seat that executes it** — see §3. The author does not size the
   hand-off and the hand-off's owner does not size the authoring. Expect this shape to be
   normal rather than exotic: `money-write-invariants` already rules that a money write is
   `senior-backend` (schema, RPC) *plus* `senior-frontend-4` (call site, controller), and D4
   carries 110 features.
4. **The calendar mapping** — sittings and gates resolved onto dates under a stated
   work-week assumption. **This is `po`'s, not yours.** Hand over counts and a rate.

### Worked example — the whole Phase 0 chain

What I reported (`agent/status/team-lead-3.md`, 2026-09-05): **6 sittings, strictly serial,
one seat, zero parallelism** — P0-1 `1`, P0-2 `1`, P0-3a `1`, P0-3b `2`, P0-4 `1`.

What `po` did with it (`agent/status/po.md`): converted **"6 sittings + 5 acceptance gates"**
under a written assumption — one sitting and one gate per working day, Mon–Fri — into
`KAN-121` 09-07 · `KAN-122` 09-09 · `KAN-123` 09-11 · `KAN-124` 09-16 · `KAN-125` 09-18.
Two board-days per sitting.

**I set none of those dates.** Every number is `po`'s, derived from my count. That split is
the whole rule: the lead owns the count, `po` owns the calendar.

### Give two dates, not one

**A `due_date` is a ceiling, not a target.** Earliest-believed and outer-bound are different
numbers and both get reported. The gap between the columns is the **rework budget, stated
openly** rather than hidden inside the ceiling as padding.

| Ticket | Sittings | Earliest believed | Ceiling committed |
|---|---:|---|---|
| `KAN-123` P0-3a | 1 | 2026-09-06 | 2026-09-07 |
| `KAN-124` P0-3b | 2 | 2026-09-07 | 2026-09-09 |
| `KAN-125` P0-4 | 1 | 2026-09-08 | 2026-09-10 |

The live board carries the ceiling column exactly (verified 2026-09-06: `KAN-123` `2026-09-07`,
`KAN-124` `2026-09-09`, `KAN-125` `2026-09-10`). The gap is roughly two rework cycles, and it
was named as such on the epic rather than left to be discovered as slack. (This column pair is
an aggregated project buffer in Goldratt's sense; the vocabulary is public, the practice here
was derived without it.)

**When two columns converge, ask where the budget went — it has moved or it has vanished, and
those look identical on the page.** A ceiling equal to the count carries no rework budget *in
that unit*. Sometimes that is correct because the budget lives in the other unit: `KAN-128` runs
2 sittings with a calendar earliest of 2026-09-09 against a ceiling of 2026-09-10, so its one
rework cycle sits in the day gap rather than in the sitting count. Sometimes it means a branch
resolved upward and nobody moved the second column, and the pair has silently collapsed back
into the single number it exists to replace.

**Both look like convergence. Say which one you have** — *"budget is the 09-09→09-10 day gap"* is
a report; two equal numbers with no stated budget is an estimate wearing a range's clothes.

### "Cheap now, expensive later" needs the right cost — name which one grows, and what starts it

A deadline derived from urgency is still a derived number, and it is wrong if you attach it to
the wrong cost. **Two costs grow at different times and they have different clocks:**

| Cost | Starts growing when | Deadline it implies |
|---|---|---|
| **Data** — a migration becomes a backfill | rows appear | when writes actually begin |
| **Code** — a model change becomes rework across dependents | dependent code is written | when building against it starts |

This seat argued that a schema model question needed answering before D4's 2026-09-14
activation, on the *data* clock — the same zero-rows asymmetry that had justified `KAN-128` a
few hours earlier. **`cpo` ruled the call right and the reasoning wrong** (`P-037`): there is no
data-migration window, because `enablePayments` is `false` and the feature goes live months
later, so **activating a stack is a lead taking tickets, not writes beginning.** The real
exposure was the *code* clock — features built against a model that would have to be unwound
across all of them, which is rework and not a backfill.

**The failure was reaching for the cost model that worked on the previous ticket.** A precedent
supplies the *shape* of an argument, never its inputs. Before quoting a deadline, say which cost
you mean and what event starts it; if you cannot name the event, you have an urgency and not a
date.

**Cheaper work does not automatically lower the ceiling — ask where the risk sits, not where
the work went.** `KAN-128`'s `financial_ledger` probe got materially cheaper on 2026-09-06 (two
direct inserts replacing a concurrency harness) and `senior-backend` explicitly declined to
lower its ceiling, because the rework risk on that ticket concentrates in the *other* half: five
function bodies rebased on live definitions, a `DROP`/`CREATE`/`REVOKE FROM PUBLIC`/re-`GRANT`
sequence, and three distinct `search_path` strings to restate exactly. **None of that changed.**
This is the ceiling-side companion to §1's scope-cut rule: a cut moves the cost only if it comes
out of the sitting that carried it, and it moves the ceiling only if it comes out of the risk.

**The stronger reason is that two numbers are auditable and one is not.** The rework budget
explains why the gap exists; this explains why a downstream seat can catch an error inside it.
On `KAN-128`, `po` first set the `due_date` to **2026-09-09**, then corrected it to
**2026-09-10** — because 09-09 was **`cto`'s apply slot, not the ceiling on `senior-backend`'s
authoring**. The wrong seat's clock.

That correction was possible only because both columns were on the record **with their bases
named**, so it reduced to a one-line reasoning fix rather than a re-derivation. A single date
would have hidden it completely: 09-09 is entirely plausible, and nothing about it looks wrong
from the outside. **State the basis of each column, not just the number** — the basis is what
makes a category error visible.

### Re-dating: move the start, keep the cost

When a ticket lands early or late, recommend a **uniform shift of the entire remaining chain
at the unchanged rate**, derived from the remaining sitting count. Do not re-size.

On 2026-09-05, with two sittings consumed and four remaining, I recommended a uniform −4 day
shift across `KAN-123`/`124`/`125` — *"derived from the four remaining sittings at the same
2-day rate, not from the fact that two tickets went fast."* Every ticket kept its sitting cost.

**Two conditions travel with a shift and are stated, not assumed:**

- **The chain is serial on `Done`, not on a review status.** A shift conditional on a predecessor
  clearing its gate shrinks one-for-one if that gate sends work back.
- **`po` owns the weekend.** My −4 arithmetic put `KAN-124` on Saturday 2026-09-12. `po` used
  Friday 09-11 instead, preserving the two-sitting cost in *working* days. Hand over sittings
  and a rate; let `po` resolve them against the calendar rather than doing that half badly
  yourself.

## 3. Sizing against a shared single-writer seat

A shared single-writer seat is any seat every team must pass through: `cto`'s `G-028`
confirmation before a schema change may be applied, `content-manager` for EN/AR copy, `devops`
for the release path. A date on such a seat's work is a claim on a queue you do not own, and a
lead that issues one is estimating.

*(Corrected 2026-09-07: this read "`senior-backend` (Shu) is one seat serving all five teams".
That seat was retired on 2026-09-06 and replaced by `backend-1..8`, one per team, so backend
**authoring** is no longer a shared queue — but `cto`'s confirmation gate still is, and the rule
below is unchanged. The `KAN-128` evidence throughout this section was measured against the
single-backend arrangement and is preserved as written.)*

> **For your own developers, report a cost and a date. For a shared seat, report a cost, no
> date, and the name of the seat that owns the queue.**
>
> **Then ask that seat for its own count, and carry it back unchanged.** The prohibition is
> on *producing* the number, not on requesting it. **A seat sizing its own work is capacity,
> not estimation** — that is the whole basis of the rule, applied one seat over.

**Naming the owner is half the job. Stopping there orphans the count.** This section said only
the first half until 2026-09-06, and the cost was measured: on `KAN-128` — a migration whose
constraint is free only while five money tables hold zero rows — **four seats refused in
sequence and every refusal was correct.** `team-lead-4` refused under this section;
`po` under `WORKFLOWS.md:58`; `pm` applying the same rule to itself; `cto` under `G-025`. Four
correct refusals, no owner, and a deadline-bound ticket standing still.

*(Provenance, since a case study is only as good as its sourcing: the first three are
first-hand from the seats themselves. `cto`'s refusal reached `team-lead-4` relayed by `pm` and
is second-hand — the grounds are almost certainly right, the chain of custody is one link
longer than the sentence above implies.)*

**A relayed status is a timestamp, not a fact.** Provenance asks *who* said it and *how
directly*; on a ticket changing hourly, the part that decays is *when*.

**And it is not only tickets — a governing document decays the same way, and is easier to
miss.** A lead spent a day re-reading every ticket before acting on its status, then carried
`CONTRACT.md` §4.1 and a landing test from its session-start context into a live escalation
without re-reading either. Both had been superseded six hours earlier by a ruling that quoted
that lead's own argument back at it. **A rule read once at the start of a session is a cached
lookup, and rulings are exactly what lands in between.** The freshness discipline is easy to
apply to the board and silently exempt the documents that govern it — re-read the clause you
are about to cite, not just the ticket you are about to move. Three relays went stale
inside one day on `KAN-128` — a seat reported its AC as outstanding after it was fixed, a lead
reported a count as awaiting confirmation after both had landed, and this seat raised a blocker
that had cleared thirty minutes earlier. **Every one was accurate when written.** So carry the
read time with a status you relay, and re-read the field before acting on a status someone
relayed to you. This does not apply to a measured line count, which does not move unless
somebody edits the file — that asymmetry is the whole point.

**There is a third category between those two, and it is this document's own subject: a sitting
count from another seat.** It is *measured*, so it reads as durable like a line count. It is
also **revisable by the seat that produced it, without warning**, like a status. A status flag
announces its own volatility — nobody reads `Ready` as permanent. A line count is inert. A
sitting count looks like the second and behaves like the first, which is why it is the one that
keeps getting re-used stale.

> **A count from another seat is that seat's current position, not a measurement you hold.
> Re-read it before you publish it, and cite when it was given.**

This file did it too: it published `KAN-128` as *"ceiling 2 either way"* after `senior-backend`
had already moved the ceiling to 3, because closing the branch at a count of 2 left the ceiling
carrying no budget. The number was measured, correctly, by the right seat — and superseded by
that same seat minutes earlier.

**The same applies to a commit sha, and it is the sharpest case because a sha reads as proof.**
A Phase 0 completion report carried *"Done… Commit `c6d3e4f`"*. The sha does not exist —
`git cat-file -t` fails on it, no log contains it — and the work was staged, never committed.
It was relayed upward as fact, written into the next developer's launching brief, and closed the
question for everyone downstream until that developer tried to build on it.

**The missing commit and the invented sha are one failure, not two: an agent reporting the
output of a command it never ran.** That is the root; the relay only propagated it. A missing
commit is visibly absent, whereas a sha that looks like a sha ends the enquiry — so the
fabrication is the more expensive half.

**An unchecked sha is not evidence**, and it is checkable in one command — the same guard as
carrying the `updated` timestamp on a relayed ticket read. The general form is worth more than
either instance: **when a report quotes the result of a command, the question is not whether the
result is plausible but whether the command was run.**

**The pairing to hold onto:** *a single-sourced claim is untested; a re-used claim is undated.*
Every ticket-reaching error on this work was found **once**, by whoever happened to check — so
convergence between two seats is not what confirms a finding. **A finding with only one source
has simply not been tested yet.**

### Convergence corroborates only when the error modes differ

**An acceptance criterion belongs to a commit, and it is measured at that commit.** Run it
against HEAD instead and you get a number that is correct and answers a different question.

`KAN-124`'s AC 8 asked for the contiguous-run count. Its executor measured **25** at `8e49b1d`,
the ticket's own commit, in a fresh detached worktree. A lead and the `po` each computed **26**
independently, matched each other bucket for bucket, and recorded the executor's answer as
wrong. Both had counted the working tree — which was `da41d3b`, one commit later, where
`KAN-125` has moved four route getters from `platform` to `play_places` and the count is
genuinely 26.

**Two independent sources agreed and both were wrong, because independence of *seat* is not
independence of *method*.** Same tree, same shortcut, same error — and the agreement read as
proof strong enough to overrule the one seat who had done it correctly. The executor was told it
was wrong by two seats holding a right answer to the wrong question.

**So before treating agreement as corroboration, ask what the two sources share.** If they read
the same artifact the same way, they can only confirm each other's blind spots. The cheap guard
is to state the *object* alongside the number — "25 at `8e49b1d`" survives this collision;
a bare "25" does not.

**What settled it was not a fourth opinion but a different question.** A third seat measured
**both** commits and reproduced both figures exactly — 25 and 26, `unresolved=0` at each. Asking
*"what is the count?"* had produced two confident wrong-object answers; asking *"what is the
count at each commit?"* ended it in one run. **When two counts disagree, vary the object before
you add a counter.**

**The root cause is in the criterion, not in anyone's arithmetic.** AC 8 asked for *"the
contiguous-run count"* as though it were a property of the route table. It is a property of a
commit, and the criterion never said which — so two competent seats produced different **right**
answers. **When you write an acceptance criterion that names a measurement, name the object it
is measured against.** *"The run count at this ticket's commit"* costs four words and forecloses
the whole failure. This is a defect in ticket-writing that looks like a defect in verification,
which is why it survived three seats.

**Related, from the same ticket:** a run-count script must **assert that every identifier
resolves**. An unresolved one silently shortens a run and the count comes out *low* — the
direction that would have falsely tripped `T-056`'s ≤20 rework trigger. A count with no such
assertion fails toward the dangerous answer.

Resolution, reached by `team-lead` on 2026-09-06 and recorded here rather than invented here:
**the lead asks the owning seat for its own count and carries it unchanged.** If you believe
that reading of `WORKFLOWS.md:58` is wrong, take it to `pm` — do not quietly resume dating a
seat you do not own.

**Ask the right seat for the right leg.** On a ticket with a hand-off (§2 input 3), each leg is
sized by the seat that executes it: `senior-backend` sizes its own authoring, `cto` sizes the
apply. Asking one seat to confirm another's count is this same error one level up, and it looks
like diligence.

### What the owning seat should hand back — the required shape

**`KAN-126` (P0-5), owned by `devops`, is the pattern to ask for by name.** `po` left the
`due_date` unset on purpose and recorded why: *"No capacity number exists for `devops`, and I
was told not to estimate one."* `devops` then supplied its own number
(`agent/status/devops.md`): **2 sittings — sitting 1 datable and fully parallel with
`senior-frontend-3` (no shared path); sitting 2 undatable, its precondition outside `devops`'s
control.**

That is the shape a shared seat owes: **a per-sitting count, which sittings are datable, and
the named blocker on any that are not.** A partial answer from the seat that owns the queue
beats a whole answer from one that does not. Ask for it in those terms — a seat asked simply
"when?" tends to return a single date, which is the estimate you were avoiding.

**What a lead may state about a shared seat without owning its date:**

- **That it is a dependency, and whether it is on the critical path.** A claim about
  ordering, not duration.
- **Disjointness — measurable, so settle it yourself.** `senior-backend` may run
  `supabase/**` alongside Phase 0 because Phase 0 touches no path under `supabase/`
  (`CONTRACT.md` §4.1). That is a fact about paths, and it is checkable.

**The characteristic error is over-coupling, and I made it.** I flagged `KAN-126` as sitting
on Phase 0's Friday critical path. It does not: `CONTRACT.md` §4.1 limits the grant to
`P0-1`–`P0-4`, and P0-5 needs no grant. Before you put a shared seat on your critical path,
read the document that defines the path.

## 4. When a task is unsizeable

> **A task is unsizeable when its sitting count depends on a fact that does not exist yet.**

The honest output is then a **named blocker and its owner** — *"cannot size until X, and Y
holds it"* — never a number with a caveat bolted on. A caveated number is read as a number.

**The mirror of that rule, and it spends other seats' capacity rather than your own: a
measurable question framed as a decision manufactures a decision.** On `KAN-130`,
`team-lead-4` raised a scope question — four lines or eight — as a choice, when it was a fact
it had not checked: `wallet_ledger` carries its own `user_id`, so the second class was never
in scope. `po` answered because it was asked, `team-lead` ratified because it looked like
judgement being exercised, and one read of the table definition would have settled it before
anyone was asked. **Before you escalate a sizing input, check whether a command or a file
answers it** — the general rule is in every role file's escalation test; the capacity-specific
cost is that a manufactured decision consumes two other seats' sittings and produces a wrong
edit.

Two shapes, both live in Phase 0:

- **The precondition sits outside the seat's control.** `devops`'s P0-5 sitting 2, above.
  Named as undatable; the number was still delivered for the half that was datable. Size the
  sizeable part and name the rest.
- **A predecessor's output is your denominator.** `KAN-124`'s two-sitting cost rests on
  `KAN-123` producing a builder→slice bucketing table for all 80 entries. If that table comes
  back thin, the basis for the cost is gone.

### Decide the contingency before the fact lands

This is the transferable move, and it is what keeps a re-cost from being an improvisation on
the day. Before `KAN-123` opened, I wrote its three branches onto the ticket:

- **Fewer than 80 entries covered** → incomplete work, not a re-cost. Straight back under the
  ticket's own rework triggers; `KAN-124`'s cost untouched.
- **Sparse collision sets** → a legitimate finding that makes `KAN-124` *cheaper*, and still
  buys back no sitting: its cost is the six-file extraction plus the golden test, not the
  ordering constraint.
- **A frozen pair spanning two buckets** → the only branch that re-costs upward, and a spec
  problem for `analyst`/`cto` rather than a sizing problem. Put on the ticket as
  **flag-on-sight, do not save for the writeup**, so it surfaces on day one.

**Measure the denominator before calling anything thin.**
`awk 'NR>=444' lib/app/app_router.dart | grep -cE '^    (GoRoute|StatefulShellRoute|ShellRoute)'`
returns **80**. Once that number was mechanical, "thin" stopped being an argument and became
a comparison.

## 5. Sizing under an exclusive grant

An exclusive grant (`CONTRACT.md` §4.1 is the live one) names a single seat as sole executor
of a set of tickets. **Capacity arithmetic changes shape, and a lead sizing during a grant
should know it is doing different arithmetic.**

- **Headcount stops being an input.** Sixteen developer seats exist; fifteen are idle on app
  code for the duration (§4.1, *The exclusion*). My own two juniors are barred outright —
  `STACKS.md` §10.0: *no junior enters any Phase 0 ticket* — and contribute zero.
- **Total is the sum of the sittings. There is no division.** Six sittings on one seat is six.
  Adding people makes it slower: `G-015` Ruling 1 — *dispatching before the split buys
  queueing, not throughput*.
- **The chain is strictly serial, so nothing parallelises out of trouble.** A slip anywhere
  shifts everything after it one-for-one. Take that to the lead and re-date; do not absorb it.
- **Only the rework budget is compressible.** A compression request may spend slack; it may
  not spend sitting cost. When Phase 0 was asked to finish by Friday 2026-09-11, the answer
  was **yes, conditional on `KAN-124` keeping two sittings and Friday carrying no ticket** —
  yes to the date, no to the shrink, with the window holding exactly one rework cycle.
- **Read the grant's own expiry test before putting anything on its critical path.** §4.1
  expires by measurement at the `STACKS.md` §10.6 landing test, not by decision. Which
  tickets are inside it is written down — check rather than infer (§3).
- **Check every clause of the expiry test against the constraints that are also live, because
  "expires by measurement" is a promise a standing freeze can quietly break.** **Six of §10.6's
  seven clauses passed on 2026-09-06** — `app_router.dart` at **441** LOC with **4** `features/`
  imports, `grep -rn "misc/data/datasources" lib/ test/` returning **0**,
  `misc/presentation/screens/` down to its **3** residual screens, `flutter analyze` at
  **0 errors / 0 warnings**, and `flutter test` at **106 across 10 files**. The seventh is
  *"the Cloudflare `Canary` build is green on `canary.dabbler.pro`"*, and no push has happened
  under the CEO's freeze. **That clause is unmet by construction, not failing** — so the grant
  does not expire, sixteen developer seats stay idle on app code, and every queued stack stays
  queued.

  **This is the capacity trap worth naming: a release condition gated on a decision nobody has
  framed as one.** The grant was written to end *without* a further decision. One clause
  referencing a pushed artifact, plus an unrelated standing freeze, converts it back into a
  decision — and because the document still says "expires by measurement," nobody is looking
  for the decision that is now required. **When a grant will not release, name the clause and
  the seat that owns it, and take it up as a decision rather than waiting on a measurement that
  cannot arrive.**

**Name what breaks under pace.** Compression pressure has predictable failure modes and they
belong in the capacity report, not in hindsight. For Phase 0 the four were: editing the golden
file to make a red test pass (which converts the only proof into evidence of nothing); a
`reset`/`checkout`/`stash` against the uncommitted tree four tickets are stacked on; a review
gate that keeps pace by becoming a rubber stamp; and a dependency on a seat outside the grant.

## What a capacity report contains

Every line, or the report is not finished:

- [ ] Sittings per ticket, with the checkpoint named for anything above 1.
- [ ] What is serial, what is parallel, and the measured reason each is so.
- [ ] Gates and hand-offs counted separately from sittings, each attributed to its seat.
- [ ] Every shared-seat count **requested from that seat and carried unchanged** — never
      produced by you, and never confirmed by a third seat on its behalf.
- [ ] Two columns — earliest believed and ceiling committed — with the gap named as the
      rework budget.
- [ ] Every shared-seat dependency named with its owning seat and **no date**.
- [ ] Anything unsizeable stated as *"cannot size until X, and Y holds it"*, with the
      sizeable part still sized.
- [ ] Contingency branches written down for any figure resting on a predecessor's unfinished
      output — decided now, not on the day.
- [ ] **No date set by the lead.** The counts go to `po` through the channel `WORKFLOWS.md`
      §4 names.

## Open questions — undefined, and deliberately not invented

**The sitting-to-calendar-day mapping has no method behind it.** `po` assumed one sitting plus
one gate per working day; the board has run at roughly two board-days per sitting. Both were
assumptions, both were stated as assumptions, and neither is derived from anything. The only
evidence is two mechanical tickets closing inside a day each, and the ticket that most needs
the mapping — `KAN-124` — is the one they say nothing about. **No rule is offered here.** A
lead reports sittings; the mapping stays `po`'s stated assumption until someone has enough
data points to derive one. Whoever gets the fifth and sixth should write it into this file.

**Two more points arrived on 2026-09-06 and still do not derive it.** `KAN-128` came out at
2 sittings on `senior-backend` plus one hand-off and one gate — but its `due_date` was never
set, so it yields a cost with no elapsed time to compare against. `team-lead-4`, who reported
it, said plainly that its data is not clean enough to derive from. Recorded so the next seat
does not re-count them as evidence: **four points, none of them a measured sitting-to-day
ratio on a judgement ticket.**

**Whether a sitting transfers to a non-developer seat is unruled.** `devops` used the unit for
a documentation write plus an end-to-end demonstration and it appeared to work. Nobody has
ruled that it generalises, and this skill does not.

## Owed elsewhere

**Closed 2026-09-06 by `po`:** `agent/WORKFLOWS.md`'s capacity-not-estimation rule now points
here for the method — *"See `agent/skills/capacity-to-date/SKILL.md` for how a lead's capacity
number becomes a `due_date` without either side estimating."* The prohibition and the method are
no longer separated.

**Still owed, and not written by this skill** — a `po` edit routed the usual way:

1. **The shared-seat resolution in §3 currently lives only in this file.** `:58` says capacity
   is reported by the owning `team-lead-N` and says nothing about a seat no lead owns — the
   silence that stalled `KAN-128` through four correct refusals. The governing document should
   carry *the lead asks the owning seat for its own count and carries it unchanged*; a company
   rule that exists only in a skill is one seat's note, and the next seat to hit this will read
   `:58`, not this file.
