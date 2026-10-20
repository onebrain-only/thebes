#!/usr/bin/env python3
"""The cloud lane (CEO 2026-10-20): detect, verify, report, hand off. Fakes only."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                               # noqa: E402
from agent.execution import cloud_lane as cl                         # noqa: E402

SHA = "a" * 40
SHA2 = "b" * 40


class Done:
    def __init__(self, out="", rc=0):
        self.stdout, self.stderr, self.returncode = out, "", rc


class CloudLaneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        self.spawned = []

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def jira(self, keys=("KAN-606",)):
        j = mock.Mock()
        j.search_issues.return_value = [{"key": k} for k in keys]
        j.get_issue.return_value = {"summary": "s", "description": "GOAL: x\nALLOWED PATHS: lib/**"}
        return j

    def remote(self, branches):
        def run(argv, **kw):
            if "ls-remote" in argv:
                return Done("".join("%s\trefs/heads/%s\n" % (v, k) for k, v in branches.items()))
            return Done("")
        return run

    def scan(self, branches, now, keys=("KAN-606",)):
        return cl.scan(jira=self.jira(keys), now=now, runner=self.remote(branches),
                       spawn=lambda k, s: self.spawned.append((k, s)))

    def test_a_cloud_branch_in_any_letter_case_is_seen_then_verified_only_after_it_goes_quiet(self):
        out = self.scan({"Alpha-Cloud-KAN-606": SHA}, 1000)
        self.assertEqual(out[0]["action"], "branch-seen")
        self.assertEqual(self.scan({"Alpha-Cloud-KAN-606": SHA}, 1000 + cl.QUIET_SECONDS - 5), [], "still quiet-waiting")
        out = self.scan({"Alpha-Cloud-KAN-606": SHA}, 1000 + cl.QUIET_SECONDS + 5)
        self.assertEqual(out[0]["action"], "verify-started")
        self.assertEqual(self.spawned, [("KAN-606", SHA)])
        self.assertEqual(self.scan({"Alpha-Cloud-KAN-606": SHA}, 2000), [], "already verifying: not twice")

    def test_a_new_push_restarts_the_quiet_period(self):
        self.scan({"alpha-cloud-kan-606": SHA}, 1000)
        out = self.scan({"alpha-cloud-kan-606": SHA2}, 1000 + cl.QUIET_SECONDS + 50)
        self.assertEqual(out[0]["action"], "branch-seen", "the cloud session pushed again")
        self.assertEqual(self.spawned, [])

    def test_a_ticket_without_a_cloud_branch_is_ignored(self):
        self.assertEqual(self.scan({"alpha-habu": SHA}, 1000), [])

    def verify(self, results, jira):
        """results: {'pub get': rc, 'analyze': rc, 'test': rc} with a canned tail."""
        def run(argv, **kw):
            if argv[:2] == ["git", "-C"] and "remote" in argv:
                return Done("https://github.com/dabblersport/webapp.git\n")
            if "diff" in argv:
                return Done("lib/features/social/providers/feed_notifier.dart\ntest/a_test.dart\n")
            if argv[0] == "flutter":
                label = "pub get" if argv[1] == "pub" else argv[1]
                rc = results.get(label, 0)
                tail = "" if rc == 0 else "00:03 +4 -1: Home feed refresh keeps items [E]\nSome tests failed."
                return Done(tail, rc)
            return Done("")
        cl.write_state("KAN-606", {"branch": "alpha-cloud-kan-606", "seen_sha": SHA})
        return cl.verify("KAN-606", SHA, runner=run, jira=jira, now=1.0)

    def test_green_checks_comment_and_move_the_ticket_to_qa_test(self):
        j = self.jira()
        with mock.patch("agent.execution.jira_sync._move") as move:
            out = self.verify({}, j)
        self.assertTrue(out["ok"])
        self.assertEqual(move.call_args.args[:2], ("KAN-606", "10009"))
        text = j.add_comment.call_args.args[1]
        for part in ("alpha-cloud-kan-606", SHA[:12], "Files changed against Alpha: 2", "ANALYZE: PASS", "TEST: PASS",
                     "QA-Test"):
            self.assertIn(part, text)
        self.assertEqual(cl.cloud_info("KAN-606")["sha"], SHA)
        self.assertEqual(self.scan({"alpha-cloud-kan-606": SHA}, 99999), [], "a judged commit is not verified again")

    def test_a_failing_test_stays_put_and_the_comment_carries_the_next_cloud_prompt(self):
        j = self.jira()
        with mock.patch("agent.execution.jira_sync._move") as move:
            out = self.verify({"test": 1}, j)
        self.assertFalse(out["ok"])
        move.assert_not_called()
        text = j.add_comment.call_args.args[1]
        self.assertIn("TEST: FAIL", text)
        self.assertIn("Home feed refresh keeps items", text)
        self.assertIn("git checkout alpha-cloud-kan-606   (it already exists", text)
        self.assertIsNone(cl.cloud_info("KAN-606"), "never offered to the reviewer")
        self.assertEqual(cl.read_state("KAN-606")["failed_sha"], SHA)

    def test_failing_test_names_are_read_from_flutter_output(self):
        out = "00:01 +3: ok\n00:04 +3 -1: Search a failed search shows Retry [E]\n00:05 +3 -2: Other [E]"
        self.assertEqual(cl.failing_tests(out), ["Search a failed search shows Retry", "Other"])

    def test_a_clone_that_fails_is_reported_not_swallowed(self):
        j = self.jira()
        cl.write_state("KAN-606", {"branch": "x"})
        run = lambda argv, **kw: Done("fatal: no", 128) if "clone" in argv else Done("https://x\n")
        with mock.patch("agent.execution.jira_sync._move"):
            out = cl.verify("KAN-606", SHA, runner=run, jira=j, now=1.0)
        self.assertFalse(out["ok"])
        self.assertIn("clone", j.add_comment.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
