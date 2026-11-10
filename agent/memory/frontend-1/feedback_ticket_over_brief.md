---
name: feedback-ticket-over-brief
description: When a dispatch brief contradicts the Jira ticket's acceptance criteria, the ticket governs — do the undisputed part and hold the disputed part until po rules
metadata:
  type: feedback
---

When a brief from team-lead (or any dispatcher) contradicts the acceptance criteria of the
Jira ticket it dispatches, **the ticket governs**. Raise the conflict to `po`, then do the
part of the work that is *not* in dispute and **hold the contradicted part until the ruling
lands**. Do not proceed on the brief "and flag it".

**Why:** on KAN-165 (2026-09-09) the brief directed adding `Semantics.identifier` to a
control the rescoped ticket said in terms needed NO change. I raised it to `po` and then
built it anyway. `po` ruled (b) — revert — and `team-lead` confirmed its own brief was
wrong: it had been written from my earlier Preflight, against a scope that had since moved.
A brief is built from a snapshot; the ticket is the current authority. Cost was a wasted
release build and a full revert.

The general judgment: "state the concern and keep building" is right for *ambiguity*, where
proceeding under a stated assumption still delivers something usable. It is wrong for a
*flat contradiction*, where one of the two instructions is definitionally wrong and building
on the wrong one produces work that must be destroyed. Ambiguity → proceed with assumption
stated. Contradiction → deliver the undisputed part, hold the rest.

**How to apply:** at Preflight, read the ticket first-hand before acting on the brief — a
brief that quotes my own earlier analysis back to me is *not* evidence the ticket still says
that. Also read the ACs of any ticket the brief claims depends on this one, rather than
accepting a relayed determination; on KAN-165 the claimed KAN-166 dependency did not exist
in KAN-166's ACs at all. See [[project-kan165-zero-diff-close]].
