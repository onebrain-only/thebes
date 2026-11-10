---
name: governance-citations-are-not-links
description: A D-/T-/P-/G- citation renders as its identifier and seat, never as a link to DECISIONS.md (D-052(d)).
metadata:
  type: project
---

`[D-004 (cxo)](../../../../dabbler-docs/DECISIONS.md)` is defective **independently of any
renderer**, on three counts: it addresses the top of a 13,000-line file rather than the entry (the
**identifier is the real address**); it escapes into a separate git repository that is local-only
while `dabbler-design-system` is public; and a relative filesystem path is meaningless against
bundled assets at runtime.

Ruled: such a citation renders as plain text — `D-004 (cxo)` — and the link syntax comes out of the
corpus. That was 78 of the corpus's 87 rendered-page links.

**Why this is NOT a breach of D-051(b)** ("the renderer completes to the corpus; the corpus is
never constrained to the renderer"): D-051(b) forbids fixing the correct artefact to suit an
incomplete one. Here the citation is wrong on its own terms — the ruling would be identical if
`_spans` were complete tomorrow. **Keep that distinction explicit**, or this gets cited as the
precedent that reopens D-051(b).

**How to apply:** also the general rule from D-052(f) — making a link tappable before its target
resolves produces a *confidently broken* link, which is worse than inert text. Inert text is ugly
and honest. See [[doc-corpus-markdown-is-barely-parsed]].
