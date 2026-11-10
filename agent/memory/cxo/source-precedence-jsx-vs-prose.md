---
name: source-precedence-jsx-vs-prose
description: When a design-source .jsx and its .d.ts/.prompt.md disagree, which one wins and the one case where the .jsx loses.
metadata:
  type: project
---

`.jsx` is the design system; `.d.ts` and `.prompt.md` are descriptions of it, so a drifted
description is corrected to the implementation (D-005). **Exception, ruled in D-013:** the `.jsx`
loses when its value carries no rationale AND the system cannot render it — Gloock and Wingx each
ship a single weight, so `Section.jsx`'s inline weight-300 title is an export artefact, not a
decision, and the three prose sources saying `title3` win.

**Why:** D-005 gave the `.jsx` authority because it carried a *reasoned* statement about the Figma
drawing. Authority comes from the reasoning, not from the file extension.

**How to apply:** on any source contradiction, ask first whether either side states a reason, then
whether the value is renderable at all. Only then fall back to file precedence. See
[[measure-before-ruling-on-contrast]] and [[token-source-of-truth]].
