---
name: d047e-is-about-object-sets-not-reads
description: D-047(e)'s "neither calls the other" forbids merging two views over DIFFERENT object sets — not a second read of _order.md.
metadata:
  type: project
---

D-047(e) withdrew the instruction that the nav call `GalleryIndex._bands()`. The reason was
**object sets**: the nav carries 58 doc pages, `_bands()` carries 45 specimen pages, and deriving
either from the other breaks one. It is **not** a rule that `_order.md` may be opened once.

`_order.md` is not a derivation — it is the authored source both views are views of. Two readers
of one authored file are not two derivations calling each other.

**Why:** D-049 nearly got refused on D-047(e) grounds, which would have used a ruling to protect
the exact thing its own reasoning condemns — `gallery_index_order.dart`'s header says the nav is
parsed from that file "and from nothing else, because a hand-written list in Dart would be a
second spine and the two would drift."

**How to apply:** when a containment or no-merge ruling is cited against a proposal, check what
the ruling's *reason* was, not its summary sentence. Also standing: the index IS the navigation
below 1000 (D-047(d)), so the index may never degrade on a failed file read the way the nav may —
any runtime read from `_bands()` needs a fallback. See [[authored-values-are-read-never-copied]],
[[foundations-are-not-a-purpose-group]].
