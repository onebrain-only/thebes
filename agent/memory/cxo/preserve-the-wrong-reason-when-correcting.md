---
name: preserve-the-wrong-reason-when-correcting
description: When a ruling's conclusion is right but its argument is wrong, record the correction visibly instead of swapping the reasoning out
metadata:
  type: feedback
---

When revising a decision whose conclusion holds but whose reasoning is wrong, say in the entry that
the reason was wrong and what it was, rather than quietly replacing it.

**Why:** D-013 (Section title weight) originally rejected `fontWeight: 300` as *unrenderable*. It is
not — `--weight-light: 300` is declared in `tokens/typography.css:55` and `meral-sans-light.ttf`
ships; only the *display* ramp is single-weight. The right rejection is "unmotivated, unique,
inconsistent with the other four `title3` call sites". The difference is load-bearing: "impossible"
would have pre-refused a future light-sans-heading variant for a cause that does not exist.

**How to apply:** an entry that changes its argument states the old one and why it failed. A reader
who acts on a ruling needs to know what it does NOT decide, and a wrong reason silently removed
still governs anyone who read it first. Applies to `D-` entries and to role-contract corrections
alike. See [[measure-before-ruling-on-contrast]], [[decisions-md-identifier-collision]].
