import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from agent.execution import review_tier as rt  # noqa: E402

SCREEN = "lib/features/social/presentation/screens/feed.dart"


class ReviewTierTests(unittest.TestCase):
    def test_no_screen_is_light_even_when_sensitive(self):
        self.assertEqual(rt.tier(["supabase/migrations/1.sql", "test/a_test.dart"]), 1)
        self.assertEqual(rt.tier(["lib/data/repositories/x.dart"], ["money"]), 1)

    def test_a_screen_is_normal_and_a_sensitive_screen_is_deep(self):
        self.assertEqual(rt.tier([SCREEN]), 2)
        self.assertEqual(rt.tier(["lib/features/auth/presentation/screens/login.dart"]), 3)
        self.assertEqual(rt.tier([SCREEN], ["Money"]), 3)

    def test_unknown_paths_are_looked_at(self):
        self.assertEqual(rt.tier(None), 2)

    def test_labels_override(self):
        self.assertEqual(rt.tier([SCREEN], ["tier:1"]), 1)
        self.assertEqual(rt.tier(["test/a_test.dart"], ["tier:3"]), 3)

    def test_describe_asks_for_no_saved_screenshot(self):
        self.assertEqual(rt.describe(["test/a_test.dart"]),
                         {"tier": 1, "platform": None,
                          "coverage": "diff and tests only", "auto_pass": True})
        self.assertNotIn("min_screenshots", rt.describe([SCREEN]))
        self.assertEqual(rt.describe([SCREEN])["platform"], "web")
        self.assertEqual(rt.describe(["ios/Runner/Info.plist"])["platform"], "web")


if __name__ == "__main__":
    unittest.main()
