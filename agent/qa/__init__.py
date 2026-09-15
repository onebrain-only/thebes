"""Thebes QA layer — deterministic test execution in front of the reviewer.

WHAT THIS IS
    The validation route (`agent/controller/validation.py`) dispatches a reviewer
    seat as an LLM act and records its verdict through the canonical writer. Until
    2026-09-15 everything a reviewer knew about test results came from what the
    executor CLAIMED and whatever the reviewer chose to run by hand — an expensive
    model navigating an application to learn what a command could have told it.

    This package moves repetitive test EXECUTION out of that loop:

        routing   one deterministic function picks the lowest-cost sufficient
                  test layers for a change profile                 (`routing.py`)
        layers    the layer registry — command, surface, cost, trigger policy
                  and local availability                            (`layers.py`)
        runner    runs selected layers by command, writes full output to disk,
                  returns structured results with references         (`runner.py`)
        results   the failure contract: PASS / PRODUCT_DEFECT / TEST_DEFECT /
                  TEST_INFRASTRUCTURE_FAILURE / EXTERNAL_QA_FAILURE, and the
                  fold into the canonical `TestClaim` / `EvidenceClaim` model
                                                                     (`results.py`)
        retest    bounded retest semantics over the existing review cycle
                                                                     (`retest.py`)
        gate      the one seam the validation route calls              (`gate.py`)

WHAT THIS IS NOT
    Not a second orchestrator, not a seat, not a verdict writer. It selects no
    reviewer, opens no review context, records no result and transitions no Jira
    status. `store.record_review_result` still requires the exact recorded review
    owner, so a green deterministic run cannot pass a review by itself — the
    reviewer still judges; it just no longer has to re-run what a command already
    ran. A red deterministic run classified as an infrastructure failure is NOT a
    Product failure and consumes no review cycle.

    Exploratory (TestSprite), performance (k6) and device-matrix (BrowserStack)
    layers are represented so routing can name them, and are NEVER auto-run: the
    runner refuses external layers by construction, and routing selects them only
    on an explicit trigger.

Stdlib only.
"""
