#!/usr/bin/env python3
"""A VALIDATION workspace must contain the integration branch. (T-095)

Synthetic git repository, no Jira, no store, no provider.

WHAT WENT WRONG WITHOUT THIS
  `allocate` returns a registered worktree untouched, so the "branch is created
  FROM the integration branch" contract held only at first allocation. On the
  SELF route the reviewer IS the executor, so a review allocated the executor's
  own preserved worktree — which on KAN-219 stood weeks and several commits
  behind Canary. The reviewer failed committed work that met its criterion,
  spending one of three review cycles, and the receipt filed that verdict under
  the word "integration".

WHAT THESE TESTS DEFEND
  That a caller can demand the base and get it or a refusal; that a CLEAN tree
  is fast-forwarded and says so; that a DIRTY tree is refused and its paths
  named rather than reset; and that execution is untouched, because an
  executor's uncommitted work is the very thing its review is about to read.
"""

import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.controller.workspace import WorkspaceUnavailable, realize_workspace  # noqa: E402
from agent.controller.tests.test_workspace_allocation import fresh_repo, sh  # noqa: E402
from agent.state import worktrees  # noqa: E402

SEAT, ITEM = "backend-1", "KAN-800"


class Freshness(unittest.TestCase):
    def setUp(self):
        self.tmp, self.repo, self.wtroot = fresh_repo()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.first = worktrees.allocate(SEAT, ITEM, repo=self.repo, root=self.wtroot)
        self.path = self.first["path"]

    def advance_canary(self, name="gamma.dart"):
        """One commit on Canary that the seat's worktree has never seen."""
        with open(os.path.join(self.repo, name), "w") as handle:
            handle.write("// %s\n" % name)
        sh(self.repo, "add", "-A")
        sh(self.repo, "commit", "-qm", "canary moves on")
        return sh(self.repo, "rev-parse", "Canary")

    def head_of(self, path):
        return sh(path, "rev-parse", "HEAD")

    def test_a_clean_reused_worktree_behind_the_base_is_fast_forwarded(self):
        tip = self.advance_canary()
        self.assertNotEqual(tip, self.head_of(self.path))
        again = worktrees.allocate(SEAT, ITEM, repo=self.repo, root=self.wtroot,
                                   require_base=True)
        self.assertEqual(tip, again["rebased_to"])
        self.assertEqual(tip, self.head_of(self.path))
        self.assertTrue(os.path.exists(os.path.join(self.path, "gamma.dart")))

    def test_a_worktree_already_containing_the_base_is_not_touched(self):
        before = self.head_of(self.path)
        again = worktrees.allocate(SEAT, ITEM, repo=self.repo, root=self.wtroot,
                                   require_base=True)
        self.assertIsNone(again["rebased_to"])
        self.assertEqual(before, self.head_of(self.path))

    def test_a_dirty_reused_worktree_is_refused_and_its_paths_named(self):
        self.advance_canary()
        with open(os.path.join(self.path, "alpha.dart"), "a") as handle:
            handle.write("// the executor's uncommitted work\n")
        with open(os.path.join(self.path, "untracked.dart"), "w") as handle:
            handle.write("// never added\n")
        with self.assertRaises(worktrees.WorktreeError) as caught:
            worktrees.allocate(SEAT, ITEM, repo=self.repo, root=self.wtroot,
                               require_base=True)
        detail = str(caught.exception)
        self.assertTrue(detail.startswith("stale-workspace:"), detail)
        self.assertIn("alpha.dart", detail)
        self.assertIn("untracked.dart", detail)
        # Refused, never repaired: both files are still exactly as they were.
        with open(os.path.join(self.path, "alpha.dart")) as handle:
            self.assertIn("uncommitted work", handle.read())
        self.assertTrue(os.path.exists(os.path.join(self.path, "untracked.dart")))

    def test_without_require_base_a_stale_tree_is_reused_untouched(self):
        # This is the execution path: the executor's own work-in-progress is
        # the point of reusing its tree, and `execute` must never lose it.
        self.advance_canary()
        with open(os.path.join(self.path, "alpha.dart"), "a") as handle:
            handle.write("// work in progress\n")
        before = self.head_of(self.path)
        again = worktrees.allocate(SEAT, ITEM, repo=self.repo, root=self.wtroot)
        self.assertTrue(again["reused"])
        self.assertIsNone(again.get("rebased_to"))
        self.assertEqual(before, self.head_of(self.path))

    def test_realize_workspace_maps_the_refusal_to_its_own_reason(self):
        self.advance_canary()
        with open(os.path.join(self.path, "untracked.dart"), "w") as handle:
            handle.write("// never added\n")
        mapping = {"repository_root": self.repo, "working_directory": None,
                   "worktree_path": None, "expected_revision": None,
                   "mutation_mode": "repository_edit"}
        with self.assertRaises(WorkspaceUnavailable) as caught:
            realize_workspace(ITEM, SEAT, mapping, root=self.wtroot,
                              require_base=True)
        self.assertEqual("workspace-stale-for-validation", caught.exception.reason)
        self.assertIn("untracked.dart", caught.exception.detail)

    def test_realize_workspace_carries_rebased_to_when_it_moved(self):
        tip = self.advance_canary()
        mapping = {"repository_root": self.repo, "working_directory": None,
                   "worktree_path": None, "expected_revision": None,
                   "mutation_mode": "repository_edit"}
        realized = realize_workspace(ITEM, SEAT, mapping, root=self.wtroot,
                                     require_base=True)
        self.assertEqual(tip, realized["rebased_to"])
        self.assertEqual(tip, realized["expected_revision"])


if __name__ == "__main__":
    unittest.main()
