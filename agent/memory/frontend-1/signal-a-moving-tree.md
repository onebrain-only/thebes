---
name: signal-a-moving-tree
description: Send a one-line "hold, tree is moving" when a reviewer has a ruling pending on code being restructured — cxo asked for this explicitly after reading files mid-rewrite.
metadata:
  type: feedback
---

When a reviewing seat (`cxo`, `po`, a peer) has a ruling pending on code being actively
restructured, send them a one-line **"hold, tree is moving"** before the files change under them.

**Why:** 2026-09-18, KAN-328. `cxo` was reading `gallery_layout.dart` and `gallery_side_nav.dart`
live while both were being deleted and rebuilt, and ruled against a snapshot that no longer
existed. It quoted constants from files that were gone. Its own words afterwards: a one-line
heads-up "saves us both a pass". Three separate instruction/report crossings happened that day and
each cost a rebuild.

**How to apply:** the moment a restructure will delete or rename a file someone else is reviewing,
say so. Also: never delete displaced work outright — see [[preserve-displaced-work]].
