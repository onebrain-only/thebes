---
name: preserve-displaced-work
description: When a ruling displaces working code, copy it outside the repo before deleting — rulings get reversed, and twice in one day the preserved copy made a reversal cheap.
metadata:
  type: feedback
---

When an instruction displaces working code, copy the file somewhere outside the repo
(the job's tmp dir) before deleting it. Never leave it in `lib/` unused, and never delete it
outright.

**Why:** 2026-09-18, KAN-328. A ruling had a working `_order.md` parser deleted; a later ruling
(D-047) reversed that and asked for it back. The preserved copy turned a day of rework into an
hour. The team lead named it twice as the only reason the reversal was cheap. Rulings issued in
parallel with a build get reversed more often than they look like they will.

**How to apply:** displaced file -> copy out, delete from the tree, and **say in the report exactly
where the copy is**. Unused code left sitting in `lib/` is the wrong answer; so is an irreversible
delete.
