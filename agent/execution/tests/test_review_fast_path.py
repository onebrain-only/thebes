#!/usr/bin/env python3
"""D-049 (CEO 2026-11-02): tier-1 work passes by itself; tier 2 is one language and theme."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution import review_tier, review_queue                    # noqa: E402


class TierRulesTest(unittest.TestCase):
    def test_auto_pass_only_for_known_non_screen_non_sensitive_paths(self):
        self.assertTrue(review_tier.auto_pass(["lib/data/repositories/x_impl.dart"]))
        self.assertFalse(review_tier.auto_pass(None))                       # unknown: look
        self.assertFalse(review_tier.auto_pass([]))
        self.assertFalse(review_tier.auto_pass(["lib/features/x/presentation/screens/a.dart"]))
        self.assertFalse(review_tier.auto_pass(["supabase/migrations/1_x.sql"]))
        self.assertFalse(review_tier.auto_pass(["lib/features/wallet/data/w.dart"]))
        self.assertFalse(review_tier.auto_pass(["lib/data/x.dart"], labels=["money"]))

    def test_tier_two_is_one_language_and_arabic_when_text_changed(self):
        screen = "lib/features/x/presentation/screens/a.dart"
        self.assertEqual(review_tier.coverage([screen]), "one of EN+Light or AR+Dark")
        self.assertEqual(review_tier.coverage([screen, "lib/l10n/app_ar.arb"]),
                         "AR+Dark only (text changed)")
        self.assertIn("EN+Light and AR+Dark", review_tier.coverage(
            ["lib/features/auth/presentation/screens/a.dart"]))


class AutoPassTest(unittest.TestCase):
    def test_tier_one_items_are_passed_and_finished_others_are_left(self):
        items = [{"item_id": "judge-d1-c1", "dispatch_id": "d1", "ticket": "KAN-1", "sha": "a" * 40,
                  "auto_pass": True, "checks": [{"id": "QA"}, {"id": "C2"}]},
                 {"item_id": "judge-d2-c1", "dispatch_id": "d2", "ticket": "KAN-2", "sha": "b" * 40,
                  "auto_pass": False, "checks": [{"id": "QA"}]}]
        with mock.patch.object(review_queue, "is_done", return_value=False), \
                mock.patch.object(review_queue, "claim", return_value=True) as claim, \
                mock.patch.object(review_queue, "finish") as finish, \
                mock.patch("agent.execution.verify.judge_verdict") as jv:
            out = review_queue.auto_pass_tier1(state_store=mock.Mock(), items=items)
        self.assertEqual(out, [{"auto_pass": "KAN-1", "checks": ["QA", "C2"]}])
        jv.assert_called_once()
        self.assertEqual(jv.call_args.args[:3], ("d1", ["QA", "C2"], {}))
        self.assertEqual(jv.call_args.kwargs["reviewer"], review_queue.AUTO_REVIEWER)
        claim.assert_called_once()
        finish.assert_called_once()

    def test_an_item_a_reviewer_already_holds_is_not_touched(self):
        items = [{"item_id": "judge-d1-c1", "dispatch_id": "d1", "ticket": "KAN-1", "sha": "a" * 40,
                  "auto_pass": True, "checks": [{"id": "QA"}]}]
        with mock.patch.object(review_queue, "is_done", return_value=False), \
                mock.patch.object(review_queue, "claim", return_value=False), \
                mock.patch("agent.execution.verify.judge_verdict") as jv:
            self.assertEqual(review_queue.auto_pass_tier1(state_store=mock.Mock(), items=items), [])
        jv.assert_not_called()

    def test_the_call_fits_the_real_judge_verdict_signature(self):
        # 2026-11-03: failed=[] crashed judge_verdict on failed.items(); the mock above hid it.
        import inspect
        from agent.execution import verify
        items = [{"item_id": "judge-d1-c1", "dispatch_id": "d1", "ticket": "KAN-1", "sha": "a" * 40,
                  "auto_pass": True, "checks": [{"id": "QA"}]}]
        sig = inspect.signature(verify.judge_verdict)
        seen = {}

        def fake(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            seen.update(bound.arguments)
            dict(bound.arguments["failed"]).items()

        with mock.patch.object(review_queue, "is_done", return_value=False), \
                mock.patch.object(review_queue, "claim", return_value=True), \
                mock.patch.object(review_queue, "finish") as finish, \
                mock.patch("agent.execution.verify.judge_verdict", side_effect=fake):
            out = review_queue.auto_pass_tier1(state_store=mock.Mock(), items=items)
        self.assertEqual(out, [{"auto_pass": "KAN-1", "checks": ["QA"]}])
        self.assertIsInstance(seen["failed"], dict)
        self.assertNotIn("skipped", str(finish.call_args))

    def test_a_failed_auto_pass_marker_is_retried_after_the_wait(self):
        tmp = tempfile.mkdtemp()
        try:
            with mock.patch.object(review_queue.store, "RUNTIME", tmp):
                review_queue.finish("judge-d1-c1", {"skipped": "auto-pass-failed: boom"})
                self.assertTrue(review_queue.is_done("judge-d1-c1"))
                self.assertFalse(review_queue._auto_pass_failed("judge-d1-c1"))
                later = time.time() + review_queue.AUTO_RETRY_SECONDS + 1
                self.assertTrue(review_queue._auto_pass_failed("judge-d1-c1", now=later))
                review_queue.finish("judge-d2-c1", {"passed": True})
                self.assertFalse(review_queue._auto_pass_failed("judge-d2-c1", now=later))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
