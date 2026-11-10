---
name: touch-target-is-not-the-painted-mark
description: A 45 touch target does not require a 45 painted element or a square hit box — grow into the pitch instead (D-032).
metadata:
  type: feedback
---

When a target floor costs fidelity, the defect is almost always that the hit box was made square
and equal to the drawing. **Paint the drawn size; grow the hit box into the space between marks, up
to but never past the pitch.**

**Why:** `NavigationTopBar` lost its fixed 62 height and widened 22px glyphs from pitch 34 to 45,
for nothing — a 34×45 box meets the floor, overlaps nobody and leaves no dead gap. `Calendar` grew
39 cells to 45 and added ~36px to the grid; the pitch is 42, so 42×48 is the honest target and the
3px shortfall beats overlapping date cells (D-032).

**How to apply:** compute the PITCH before accepting any "the floor forced it". Overlapping targets
are the one thing that is worse than a short axis. Bound any accepted shortfall to contiguous grids
of peer targets; isolated controls get the full floor.
