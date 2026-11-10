---
name: ask-what-else-the-mechanism-predicts
description: On finding a defect caused by a structural gap, ask what ELSE that same mechanism predicts before characterising severity.
metadata:
  type: feedback
---

When a defect's cause is structural — a parser with no fallback branch, a regex with a fixed set of
alternatives, a switch with no default — **enumerate everything that cause predicts before ruling
on severity.**

**Why:** in D-050 I read `doc_page.dart`'s parser and `_spans`'s matcher, saw `###` was unhandled,
and called it "the largest defect in the rendered corpus." The same two greps already implied three
more (bold across a line break, links, list items) — one of which, links, is *more* serious because
D-033's whole non-repetition architecture rides on it. I had the mechanism in front of me, drew one
conclusion, and stopped. D-051 corrects it.

**How to apply:** the tell is a superlative — "the largest", "the only", "the last one". Before
writing one, ask what else the cause produces. Cheap: usually one more grep in the same minute.
Also: when correcting, leave the wrong figure and the wrong framing visible with a dated annotation
rather than swapping them. See [[doc-corpus-markdown-is-barely-parsed]],
[[preserve-the-wrong-reason-when-correcting]].
