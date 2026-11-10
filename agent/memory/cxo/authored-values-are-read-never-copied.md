---
name: authored-values-are-read-never-copied
description: Fourth figure class (D-049(f)) — a value whose single home is a file under assets/documentation/ is read at runtime, never transcribed into Dart.
metadata:
  type: project
---

D-043 gave three classes (ruled / declared / measured). D-049(f) adds a fourth:

**AUTHORED** — its single home is a file under `assets/documentation/`. Editorial judgement,
not derivable from filenames: the nine-group order, the one-line descriptions, the reading
sequence. **Treatment: read it at runtime. Never transcribe it into Dart.**

Full test: ruled → transcribe, naming the ruling. Declared → transcribe where it distinguishes
named options. **Authored → read it; never copy it.** Measured → never transcribe.

**Why:** a *declared* figure's home is the source tree, so prose citing it is a reader crossing
between artefacts — the citation is the point. An *authored* value's home is the corpus, so Dart
copying it is one artefact holding the same value twice. `GalleryPurpose`'s declaration order was
a hand copy of `_order.md`'s nine groups, verbatim down to the dartdoc one-liners.

**How to apply:** when someone proposes a gate to check two copies agree, first ask whether the
copy is *necessary*. **Check what you cannot eliminate; eliminate what you can.** A gate guarding
a duplication you could have declined to create is worse than not creating it. That is the line
between D-043(e) (prose must state a number — unavoidable, so check it) and D-049(e) (code can
read the file — avoidable, so remove it). See [[figure-classes-ruled-declared-measured]].
