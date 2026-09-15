"""Bounded retest semantics — over the review cycle that already exists.

NOTHING NEW IS INVENTED HERE. `review_context.review_cycle` already counts
reopenings, and the three FAIL semantics (PEER transfer, SELF re-entry, QA
return-to-executor) already exist in `agent/state/store.py`. What did not exist
was a ceiling: a developer -> QA -> developer -> QA loop could run forever, each
cycle spending a reviewer dispatch, with nothing to make the repetition visible.

THE CEILING is `policy.MAX_REVIEW_CYCLES`, enforced in the canonical writer
(`store.open_review_context`) so no caller can route around it. This module is
the read-only explanation of that rule for anyone who needs to reason before
writing — the same shape as `assert_execution_permitted` beside a lease.

WHAT REACHING THE CEILING MEANS. The item stays exactly where it is — same
owner, same execution status, its last FAIL still on the record — and the next
reopen is refused with `retest-limit-reached`. That is a finding for a human: a
bounded intervention or a CEO decision, never an automatic retry, never a quiet
downgrade to an easier route.

INFRASTRUCTURE FAILURES DO NOT COUNT. A cycle is consumed only when a review
context is reopened after a recorded verdict. A deterministic gate that could
not run refuses BEFORE any verdict exists, so it never advances the count.
"""

from agent.state import policy

RETEST_LIMIT_REACHED = "retest-limit-reached"


def next_cycle(review_context):
    """The cycle a reopen would create."""
    if not isinstance(review_context, dict):
        return 1
    return int(review_context.get("review_cycle") or 1) + 1


def retest_permitted(review_context, limit=None):
    """(permitted, reason). Read-only; the writer enforces the same rule."""
    limit = policy.MAX_REVIEW_CYCLES if limit is None else int(limit)
    if not isinstance(review_context, dict):
        return True, "no review context yet"
    if review_context.get("review_result") != "fail":
        return True, "no failed review to retest"
    proposed = next_cycle(review_context)
    if proposed > limit:
        return False, ("%s: cycle %d would exceed MAX_REVIEW_CYCLES=%d; a bounded "
                       "intervention or CEO decision is required, not another retry"
                       % (RETEST_LIMIT_REACHED, proposed, limit))
    return True, "cycle %d of %d" % (proposed, limit)
