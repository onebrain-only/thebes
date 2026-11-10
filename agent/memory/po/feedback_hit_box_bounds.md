---
name: feedback-hit-box-bounds
description: A touch target's hit box is bounded by the pitch to its peer targets, never by the surrounding padding — padding is claimable space, not a wall
metadata:
  type: feedback
---

D-032 ruled this once (touch-target sizing generally); D-039 had to re-rule it for `top_bar.dart`
because the first ruling was misread the same way twice. Recording it here since cxo explicitly
asked for it to live somewhere durable, not just in the two DECISIONS.md entries.

**The rule:** a hit box's bound is the pitch between it and its peer targets, and the edge of what
the component owns — never the padding, margin or gap drawn around the visual mark inside it.
Padding is a drawing instruction for where the *paint* sits; it is not reserved void a touch target
must stay clear of. A target can grow into the padding around it without moving a single painted
pixel, as long as it doesn't collide with a neighbouring target's own claim.

**Why:** `top_bar.dart` (D-039) shipped `barHeight` as a *minimum* rather than the drawn fixed 62,
because a comment reasoned "45-tall actions + 2×12 padding = 69, so a hard 62 would clip them" —
treating the 12px padding as a wall. It isn't: the bar's drawn interior is 60px (62 minus 1px
borders top/bottom), and a 45-tall target centred in 60px leaves 7.5px clearance each side without
touching the glyph's own line box. The false reasoning blocked a correct ruling (D-032) from
landing in code for as long as it survived, uncorrected, in a comment nobody re-derived from
scratch.

**How to apply:** whenever sizing or reviewing a touch target against surrounding spacing, ask
"whose claim does this space belong to" before concluding a target can't grow — padding around a
drawn mark is not a claim by anything until another real target's own hit box reaches it. If a
"can't fit" argument rests on padding, treat that as a signal to re-derive from the drawn interior
dimensions rather than trust the arithmetic as given, even (especially) if the arithmetic looks
careful. See [[project_ds213_ceo_rejection]] and the wider pattern of comment-drift this session
kept finding (T-083, text_field.dart, this one) — a verifiable claim in a comment rots silently;
only the code and the drawing stay true.
