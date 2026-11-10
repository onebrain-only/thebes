---
name: verifying-fidelity-work
description: How to verify design-fidelity and token work in this package — measure computed styles off the served specimen, and put a control row in every probe
metadata:
  type: feedback
---

When checking a component against the Dabbler design, **measure, do not eyeball**,
and **include the old shape in the same measurement as the new one**.

**Why:** the whole 2026-09-17 fidelity rejection happened because components were
built from `.d.ts` / `.jsx` / prose and nobody rendered the design. Eyeballing
screenshots then produced two near-misses of my own that measurement caught
immediately, and a probe that showed only the post-fix state would have been
consistent both with the fix working and with it being unnecessary. The team lead
and `cxo` recorded the control-row form as precedent for token gates.

**How to apply:**

- The design bundle is **on disk** at `Dabbler/dabbler-design-system-design/project/`
  and is also served (8098 when running). Read its `.jsx`/`.css` for intent, then
  get exact numbers with `mcp__claude-in-chrome__javascript_tool` reading
  `getComputedStyle` / `getBoundingClientRect` off the live page. That is how
  `--accent-indigo: rgb(92,80,230)` and the Badge's `24.5 / 4px 10px / 11px 700`
  were pinned down — numbers no screenshot would have given.
- In any Flutter probe, pump a **control row** built the way the code used to be,
  beside the real ones, so the output demonstrates the *change* rather than the
  current state. Delete the probe afterwards; it is an instrument, not a test.
- `build/web` is shared and sibling agents clobber it mid-build (I caught
  `flutter_bootstrap.js` at 0 bytes). Build to `--output=$CLAUDE_JOB_DIR/tmp/web`
  and serve that on a private port instead.

See [[escalate-contended-primitives]] for when measuring reveals something bigger
than your own surface.
