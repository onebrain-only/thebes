---
name: docs-voice-and-sources
description: Voice defined for the design-system component documentation project, where usable prose lives across the three source formats, and the D-033 ten-part page template
metadata:
  type: project
---

**Context:** 2026-09-18, CEO asked the specimen gallery in `dabbler-design-system` become
real documentation. `cxo` ruled the architecture as `D-033`
(`Dabbler/dabbler-docs/DECISIONS.md:12829`) — this seat writes every word. Source audit sent
to team-lead 2026-09-18, msg_id `9a5639ea-8b9d-4327-b392-a6572f5088fe`; four-page pilot
against D-033 sent 2026-09-18, msg_id `7c2c06af-e53c-4113-a5ad-ac6e137e2ccc`.

**D-033, the ruled architecture (re-check `DECISIONS.md:12829` before relying — it can be
amended on pilot evidence):**
- **Ten-part page template**, in order: Title · Definition (one sentence, required, no
  exceptions) · Intro · Specimen (section 4, after Definition, never shrinks) · Using it
  (bold-imperative rules + rationale — the one section authored from nothing) · Axes (one
  subsection per variant the component has) · Direction (conditional — only where RTL
  behaviour genuinely differs) · Tokens used (role names, never hex) · Change log (LINKS to
  `D-` entries, never summarises — a summary of a ruling is a second ruling) · Source (one
  file path line).
- **Four global sections**: Start here (one page) · Foundations (colour, type, spacing &
  geometry, motion, icons, sports, interaction, themes & brightness, bidirectionality) ·
  Components (grouped by *purpose*, nine fixed groups, not by `lib/src/` folder) · Patterns
  (exactly three pages: Waiting, Nothing to show, Telling the user something happened — a
  fourth is refused; **if a pattern page can't be written without inventing a rule, drop it**).
- **No direction switcher exists in the gallery yet** — every RTL claim in a Direction section
  is currently verified by reading code, not by rendering. Mark such claims as such.

**Template friction found in the pilot (reported to team-lead, not yet resolved):**
- "Tokens used" doesn't fit a Foundations page whose whole subject IS the token set — stub it
  with a note rather than silently dropping it.
- A Foundations page's Specimen section may have nothing to point to (no colour-swatch gallery
  entry exists as of 2026-09-18) — write what the specimen needs to show, don't describe a
  render that doesn't exist.

**Real finding: DECISIONS.md rulings can outrun the shipped code.** D-023 rules Button gains a
tenth `text` tone; `DabblerButtonTone` in `button.dart` has nine values as of 2026-09-18 —
`text` hasn't shipped. **Always check the ruling's claimed code change against the actual
file before describing it as shipped** — link the ruling in the change log, but write the
Axes/behaviour sections from the code, not from the ruling's stated intent. This is the same
failure class as the icon-weight-inversion incident, just the other source lying.

**The voice, as I defined it (approved by team-lead 2026-09-18, unchanged):**
- Reader is a Dabbler engineer deciding whether/how to use a component (secondarily a
  designer checking a built screen) — not Apple's general "people."
- One-sentence Purpose line, no adjectives, states what the component is *for*.
- Best-practice rule: **bold imperative**, immediately followed by its one-clause reason.
  Never cite the ticket/gate/D-number that produced the rule in the body text — link it in
  Change log instead.
- Prohibition: state the forbidden thing flatly first, then why. Never "avoid"/"consider."
- Present tense. Third person for the component ("Button renders…"). Bare imperative, no
  subject, for reader instructions ("Pair with…", "Never place…"). No first person, ever.
- No promotional adjectives ("beautiful," "seamless," "delightful").
- Never write "mirrors correctly" as a blanket RTL claim — state the actual behaviour.
- Never describe behaviour not verified by reading the actual component file.

**Where usable prose lives (verified 2026-09-18, will decay — re-check before relying):**
- `.prompt.md` (64 files, design source): bimodal — ~20 substantial and near-template
  (`CodeInput`, `DateField`), ~20 are 5-17 line stubs (`Checkbox`, `Radio`, `Toggle`) needing
  a from-scratch page written against the Dart component directly (the dartdoc often carries
  real content the stub prompt.md never wrote down — confirmed on `Checkbox`).
- `components/messaging/*` (14 files) and `rooms/BottomSheet.prompt.md`: **deliberately
  excluded from Year-1 scope by the CEO's 2026-09-17 ruling** (no Year-1 pillar depends on
  them) — not merely unported. Do not write these; if the architecture needs to acknowledge
  the gap, say so rather than filling it.
- Dart dartdoc: argued and correct, written for a port-fidelity auditor (cites
  `Component.jsx:LL-LL`, AC numbers). Strip the citation apparatus, keep rule+reason.
- `DECISIONS.md` D-001–D-033: most authoritative, heaviest translation — check a ruling's
  claimed code change against the actual file (see the D-023/Button finding above) before
  describing it as current behaviour.

[[bilingual-docs-recommendation]]
