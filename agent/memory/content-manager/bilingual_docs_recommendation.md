---
name: bilingual-docs-recommendation
description: Recommendation (not yet a decision) on whether the design-system documentation itself ships in Arabic, vs. English-only docs for a bilingual system
metadata:
  type: project
---

Recommended to team-lead 2026-09-18 (not decided — flagged as CEO's cost tradeoff to
weigh, msg_id `9a5639ea-8b9d-4327-b392-a6572f5088fe`): the component documentation ships
**English-only**; the *system* it documents stays bilingual EN/AR as it already is.

**Why:** every piece of this org's own working documentation (CLAUDE.md, DECISIONS.md,
every agent role file) is English-only regardless of the product being bilingual — the
reader of component docs is a Dabbler engineer, not an app user. Translating ~50 pages
compounds forever: every future `D-0xx` ruling that revises a rule needs re-translation to
stay in sync (D-027 revised D-003 two days before this recommendation was written — this
happens often). The per-page template isn't even ruled yet, so translating a moving target
is waste on top of that.

**Revisit if:** Arabic-first designers/engineers join the docs' actual readership, or the
doc set goes outside the org (e.g. shared with a contracted studio).

**Regardless of (a) — every component page still needs a named RTL section** (keep it as
its own section like the `.prompt.md` template already does, not folded into Behaviour).
Must state per component: whether it mirrors at all (say so even when the answer is
"yes, by default" — silence reads as "not considered"); any direction-pinning deviation,
named with its reason, verified by reading the code (e.g. `CodeInput`'s LTR digit pin,
`DateField`'s Western-numeral date string, `Calendar`'s caller-supplied `firstWeekday`);
numerals, stated per component rather than assumed system-wide.

**Rule for writing that section:** never write "mirrors correctly" as a blanket claim —
state the actual behaviour. "Correctly" isn't something a doc page can verify.

See [[docs-voice-and-sources]] for the full source audit this recommendation came out of.
