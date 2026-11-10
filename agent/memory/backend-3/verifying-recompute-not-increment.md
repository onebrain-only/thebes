---
name: verifying-recompute-not-increment
description: An equality assertion on a balance proves a full recompute only if the increment path would produce a different number — test with a DELETE instead.
metadata:
  type: project
---

When verifying that a money-path function **recomputes** a balance from a ledger rather than
**incrementing** it (T-049 Invariant 3), an equality assertion on the resulting balance is
usually *not* sufficient evidence. Delete a ledger row and assert the balance **falls**.

**Why:** In the KAN-173 peer review (2026-09-10) the probe pack asserted `balance = 35.00`
after ledger rows of `10.00` and `25.00`. That passes under an incrementing implementation too
(`10`, then `10 + 25` = `35`), so the assertion was consistent with the exact defect it claimed
to exclude. `public._wallet_recalc` genuinely recomputes, but P2 was not what proved it —
deleting the `25.00` row and observing `35.00 → 10.00` was, because no accumulator produces a
decrease. `trg_wallet_ledger_recalc` fires on `AFTER INSERT OR DELETE OR UPDATE`, which is what
makes the DELETE probe available.

**How to apply:** Whenever reviewing or writing a probe for a derived-total invariant, ask
"what would the wrong implementation print here?" before accepting the number. If the correct
and incorrect implementations agree on the test value, the test is decorative. Prefer a
monotonicity-breaking operation (DELETE, or a reversal) over a sum that both paths reach.
Applies to `_wallet_recalc` and to [[kan130-wallet-owner-arbiter]] when it restates the same
function owner-keyed.
