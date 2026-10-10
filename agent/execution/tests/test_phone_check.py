import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution import phone_check as pc          # noqa: E402


class PhoneCheckTests(unittest.TestCase):
    def test_only_native_or_startup_changes_need_the_phone(self):
        self.assertTrue(pc.needed(["ios/Runner/Info.plist"]))
        self.assertTrue(pc.needed(["lib/features/app_boot/splash.dart"]))
        self.assertTrue(pc.needed(["pubspec.yaml"]))
        self.assertTrue(pc.needed(["lib/x.dart"], labels=["visual:native"]))
        self.assertFalse(pc.needed(["lib/features/social/create_post.dart", "test/a_test.dart"]))

    def test_no_booted_device_is_a_skip_not_a_failure_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pc, "RUNTIME", tmp):
            runner = mock.Mock(return_value=mock.Mock(stdout="{}", returncode=0))
            out = pc.run("ios", tmp, os.path.join(tmp, "a.png"), runner=runner)
            self.assertEqual(out["status"], "skipped")
            self.assertTrue(os.path.exists(os.path.join(tmp, "measured.jsonl")))

    def test_over_budget_is_skipped_so_it_can_never_cost_more_than_the_budget(self):
        def runner(cmd, **kw):
            if cmd[:3] == ["xcrun", "simctl", "list"]:
                return mock.Mock(stdout='{"devices": {"r": [{"state": "Booted", "udid": "U1"}]}}')
            raise subprocess.TimeoutExpired(cmd, 1)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pc, "RUNTIME", tmp):
            out = pc.run("ios", tmp, os.path.join(tmp, "a.png"), budget=5, runner=runner)
            self.assertEqual(out["status"], "skipped")
            self.assertIn("over budget", out["reason"])

    def test_one_team_per_device(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pc, "RUNTIME", tmp):
            with pc.Lock("U1"):
                with self.assertRaises(TimeoutError):
                    with pc.Lock("U1"):
                        pass


if __name__ == "__main__":
    unittest.main()
