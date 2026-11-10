---
name: feedback-specimen-is-spec
description: Ticket acceptance for anything ported from the design bundle must include a rendered-specimen visual comparison, not just testable prose criteria
metadata:
  type: feedback
---

For any component or screen ported from `Dabbler/dabbler-design-system-design/`, acceptance
criteria must require a visual comparison against the design bundle's own rendered specimen
(the `*.card.html` pages under `project/components/<area>/`) at the built viewport width — not
only testable criteria drawn from `.d.ts`/`.jsx`/`.prompt.md` prose.

**Why:** the CEO rejected the entire KAN-213 build (36/36 tickets, all criteria met, package-wide
tests green) on 2026-09-17 because it was visually unfaithful — Material-default chrome, missing
fonts, wrong default brightness, and components under-built against what the design actually
draws (e.g. CardTicket shipped 2 colours/1 action where `cards.card.html` draws 5 colours/2
actions). Every ticket in that epic was written and reviewed against prose and testable acceptance
criteria; nobody rendered the `.card.html` specimens against the built output. The bundle's
README says not to open the HTML "as a live app" — that was read as "never look at it," which
was the mistake. See `KAN-213`'s 2026-09-17 comment in Jira for the CEO's full rejection and the
six follow-up fidelity tickets (KAN-287–292) it produced.

**How to apply:** when writing a ticket against this design source, add an explicit AC of the
form "a screenshot of the built component at [width] must be indistinguishable from
[specific `.card.html` file]'s drawn variant" alongside the testable criteria. The prose files
remain useful for behavior, tokens and edge cases the specimen doesn't show — they are supporting
evidence, not the contract. When reviewing work claimed Done, actually render it (or ask the
executing agent for a screenshot) rather than trusting a green test suite alone for anything
visual. See [[project_ds213_ceo_rejection]] for the incident this rule comes from.
