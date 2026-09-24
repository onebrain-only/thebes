"""The reviewer must receive the evidence it judges, whole or explicitly marked.

Regression for KAN-359 / KAN-362 (2026-09-25): `validation_objective` clipped the
executor report to 1,500 characters and the acceptance criteria to 2,000, so two
complete audits failed self-review on a truncated copy of their own deliverable.
"""
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.controller.validation import (                          # noqa: E402
    MAX_REVIEW_CRITERIA_CHARS, MAX_REVIEW_REPORT_CHARS, review_evidence,
    validation_objective,
)

TASK = {"work_item_id": "KAN-990", "surfaces": [],
        "execution_profile": {"required_capability": "ux-engineer",
                              "validation_route": "self"},
        "review_context": {"review_type": "self", "review_result": "pending"}}


def objective(summary, description):
    execution = types.SimpleNamespace(summary=summary, changed_files=(), tests=())
    issue = {"summary": "Parity audit", "description": description}
    return validation_objective("KAN-990", TASK, issue, execution, "receipt-1")


def numbered(prefix, count):
    """Distinct lines, so the LAST one proves nothing after the old cut was lost."""
    return "\n".join("%s %04d: design 48px vs implementation 45px" % (prefix, i)
                     for i in range(count))


class ReviewEvidenceTests(unittest.TestCase):

    def test_long_executor_report_reaches_the_reviewer_intact(self):
        report = numbered("FINDING", 400)                     # ~20,000 chars
        self.assertGreater(len(report), 1500 * 10)
        text = objective(report, "AC1 short.")
        self.assertIn(report, text)
        self.assertIn("FINDING 0399", text)
        self.assertNotIn("[TRUNCATED", text)

    def test_long_acceptance_criteria_reach_the_reviewer_intact(self):
        criteria = numbered("AC", 200)                        # ~10,000 chars
        self.assertGreater(len(criteria), 2000 * 4)
        text = objective("short report", criteria)
        self.assertIn(criteria, text)
        self.assertIn("AC 0199", text)
        self.assertNotIn("[TRUNCATED", text)

    def test_content_beyond_the_safety_cap_is_marked_not_cut_silently(self):
        over = "x" * (MAX_REVIEW_REPORT_CHARS + 500)
        text = objective(over, "AC1 short.")
        self.assertIn("[TRUNCATED: reviewer received %d of %d characters]"
                      % (MAX_REVIEW_REPORT_CHARS, len(over)), text)
        over_ac = "y" * (MAX_REVIEW_CRITERIA_CHARS + 10)
        text = objective("short report", over_ac)
        self.assertIn("[TRUNCATED: reviewer received %d of %d characters]"
                      % (MAX_REVIEW_CRITERIA_CHARS, len(over_ac)), text)

    def test_short_code_ticket_review_is_unchanged(self):
        report = "Changed lib/foo.dart; flutter test passed."
        criteria = "AC1 the button renders.\nAC2 tests pass."
        text = objective(report, criteria)
        self.assertIn(report, text)
        self.assertIn(criteria, text)
        self.assertNotIn("[TRUNCATED", text)
        self.assertEqual(review_evidence(report, 1500), report)


if __name__ == "__main__":
    unittest.main()
