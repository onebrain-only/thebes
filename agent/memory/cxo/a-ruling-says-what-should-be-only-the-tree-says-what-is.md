---
name: a-ruling-says-what-should-be-only-the-tree-says-what-is
description: Never infer what the corpus or code contains from a ruling that says it should. Open the tree.
metadata:
  type: feedback
---

**A ruling says what should be. Only the tree says what is.** Before ranking, scoping or
prioritising on the basis of an architecture a `DECISIONS.md` entry established, grep for it.

**Why:** D-051(c) ranked broken links as the most serious renderer defect because D-033 fixed the
architecture "a component page links to a foundation; it never repeats it" — so I reasoned the
corpus was full of such links and that breaking them withheld rules from readers.
`grep -rlE '\]\([^)]*foundations' components/` returns **zero files**. The architecture was never
built. Links fell from first place to last and from 87 instances to 9 (D-052).

This is D-037(c)'s own distinction turned on its author: a decision is true because it was ruled;
a claim about the world is true only if the world says so.

**How to apply:** the tell is a sentence of the form "X is carried by Y, and Y is broken" where X
comes from a ruling. One grep settles it. Related trap from the same day: finding one instance of
a structural cause and stopping — [[ask-what-else-the-mechanism-predicts]]. And when correcting,
preserve the abandoned reasoning visibly —
[[preserve-the-wrong-reason-when-correcting]].
