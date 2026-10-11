#!/usr/bin/env python3
"""Workspace rules (CEO 2026-10-11): one persistent folder per team, a temporary branch dies
with its integration, reports say "on Alpha, sha X", an idle folder drops only regenerable
output; and a brief that orders a per-task worktree is refused."""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution import dispatch_brief as brief                  # noqa: E402

KARNAK = "0aaaaaaa-7777-7000-8000-00000000000a"
MEMPHIS = "0ddddddd-7777-7000-8000-00000000000d"
CHECK = "C1 | run | flutter analyze --no-pub --no-fatal-infos | exit 0"


def _brief(goal="Fix the login screen.", decisions="none", extra=""):
    return "\n".join([
        "GOAL: " + goal, "BRANCH: alpha-karnak", "ALLOWED PATHS: lib/features/auth",
        "DECISIONS MADE: " + decisions, extra, "CHECKS:", CHECK, ""])


class WorkspaceRulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _team_text(self, seat):
        base = {"dispatch_id": "cdispatch-x", "delivery_id": "cdispatch-x",
                "target_session_id": KARNAK if seat != "memphis" else MEMPHIS,
                "target_seat_id": seat, "checks": [{"id": "C1"}], "branch": "alpha-x"}
        return "\n".join(cd.team_block(base))

    def test_every_team_lane_receives_all_four_workspace_rules(self):
        for seat in ("karnak", "memphis"):
            text = self._team_text(seat)
            self.assertIn("workspace 1 (one folder)", text, seat)
            self.assertIn("git checkout -B <task-branch> origin/Alpha", text, seat)
            self.assertIn("Never create a second worktree or folder", text, seat)
            self.assertIn("workspace 2 (branch dies with its integration)", text, seat)
            self.assertIn("git checkout --detach origin/Alpha", text, seat)
            self.assertIn("git branch -d <task-branch>", text, seat)
            self.assertIn("Never `--force`", text, seat)
            self.assertIn("workspace 3 (report on Alpha)", text, seat)
            self.assertIn("on Alpha, sha X", text, seat)
            self.assertIn("workspace 4 (idle folder)", text, seat)
            self.assertIn("only `build/` and `.dart_tool/`", text, seat)

    def test_operations_also_cleans_up_after_each_integration(self):
        ops = self._team_text("memphis")
        self.assertIn("workspace (operations)", ops)
        self.assertIn("delete the merged team branch on origin", ops)
        self.assertIn("SYNCED <sha> or BLOCKED", ops)
        self.assertNotIn("workspace (operations)", self._team_text("karnak"))

    def test_the_branching_line_no_longer_orders_a_new_worktree(self):
        record = {"checks": [{"id": "C1"}], "branch": "alpha-karnak"}
        text = "\n".join(cd.verify_block(record))
        self.assertIn("ONE persistent work folder", text)
        self.assertNotIn("in your own git worktree", text)

    def test_a_brief_that_orders_a_per_task_worktree_is_refused(self):
        for goal, dec in (("Create a new worktree for KAN-9 and fix the login.", "none"),
                          ("Fix the login.", "Set up another worktree for this task."),
                          ("Fix the login.", "run git worktree add ../kan9 origin/Alpha"),
                          ("Open a separate work folder for the fix.", "none")):
            with self.assertRaises(brief.BriefError, msg=(goal, dec)) as ctx:
                brief.lint(_brief(goal, dec), "karnak")
            self.assertTrue(any("worktree/folder" in p for p in ctx.exception.problems),
                            ctx.exception.problems)

    def test_the_rule_itself_and_normal_briefs_pass(self):
        brief.lint(_brief(), "karnak")
        brief.lint(_brief(decisions="Never create a worktree; work in your own folder."),
                   "karnak")
        brief.lint(_brief(decisions="Do not add a second worktree."), "karnak")

    def test_the_serial_integration_dispatch_may_use_its_temporary_worktree(self):
        text = "\n".join([
            "GOAL: Merge alpha-karnak into Alpha.", "INTEGRATE: Alpha",
            "DECISIONS MADE: create an integrate worktree, remove it after the push.",
            "CHECKS:", CHECK, ""])
        sections, _ = brief.lint(text, "memphis")
        self.assertEqual(sections["INTEGRATE"], "Alpha")

    def test_the_template_cli_lints_a_refused_brief_with_exit_2(self):
        import json
        import contextlib
        import io
        path = os.path.join(self.tmp, "b.md")
        with open(path, "w") as fh:
            fh.write(_brief("Create a new worktree for the task."))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = brief.main(["lint", "--file", path, "--team", "karnak"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "refused")


if __name__ == "__main__":
    unittest.main()
