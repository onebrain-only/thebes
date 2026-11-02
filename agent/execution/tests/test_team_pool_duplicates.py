#!/usr/bin/env python3
"""D-050: one live session per team. Leftover same-named sessions are stopped or removed;
the bound session, and any session a dispatch still depends on, is never touched."""
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution import team_pool                                 # noqa: E402
from agent.execution.claude_cli import ClaudeCliError                 # noqa: E402

NOW = 2_000_000_000.0
OLD = int((NOW - 7 * 3600) * 1000)
NEW = int((NOW - 600) * 1000)


class FakeCli:
    def __init__(self, rows, refuse_rm=()):
        self.rows, self.refuse_rm, self.calls = rows, set(refuse_rm), []

    def agents(self, include_completed=False):
        return self.rows

    def stop(self, short_id):
        self.calls.append(("stop", short_id))

    def rm(self, short_id):
        if short_id in self.refuse_rm:
            raise ClaudeCliError("claude rm %s refused: unpushed commits" % short_id)
        self.calls.append(("rm", short_id))


class FakeStore:
    def __init__(self, bound, dispatches=()):
        self.bound, self.dispatches, self.ledger = bound, list(dispatches), []

    def read_all(self, kind):
        if kind == "role_session":
            return [{"status": "active", "session_id": s} for s in self.bound]
        return self.dispatches if kind == "conversation_dispatch" else []


def row(name, sid, state, started=OLD):
    return {"name": name, "sessionId": sid, "id": sid[:8], "state": state, "startedAt": started}


class DuplicateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_archive = team_pool.ARCHIVE
        team_pool.ARCHIVE = os.path.join(self.tmp, "archive")
        self.projects = os.path.join(self.tmp, "projects")
        os.makedirs(os.path.join(self.projects, "p"))
        import agent.execution.orders as orders
        self.orders, self.old_log = orders, orders.log
        self.logged = []
        orders.log = lambda *a, **k: self.logged.append((a, k))

    def tearDown(self):
        team_pool.ARCHIVE = self.old_archive
        self.orders.log = self.old_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_sweep(self, rows, bound, dispatches=(), refuse_rm=()):
        cli = FakeCli(rows, refuse_rm)
        out = team_pool.sweep_duplicates(state_store=FakeStore(bound, dispatches), cli=cli,
                                         now=NOW, projects=self.projects)
        return out, cli.calls

    def test_bound_session_is_never_touched_and_live_copy_is_stopped(self):
        out, calls = self.run_sweep([row("thebes-team-karnak", "aaaaaaaa-1", "blocked"),
                                     row("thebes-team-karnak", "bbbbbbbb-2", "working")],
                                    bound=["aaaaaaaa-1"])
        self.assertEqual(calls, [("stop", "bbbbbbbb")])
        self.assertEqual(out[0]["team"], "karnak")

    def test_finished_old_copy_is_archived_then_removed(self):
        open(os.path.join(self.projects, "p", "cccccccc-3.jsonl"), "w").write("{}\n")
        out, calls = self.run_sweep([row("thebes-team-edfu", "cccccccc-3", "done")], bound=[])
        self.assertEqual(calls, [("rm", "cccccccc")])
        self.assertTrue(os.path.exists(os.path.join(team_pool.ARCHIVE, "cccccccc-3.jsonl")))

    def test_recently_finished_copy_waits(self):
        out, calls = self.run_sweep([row("thebes-team-edfu", "cccccccc-3", "done", NEW)], bound=[])
        self.assertEqual((out, calls), ([], []))

    def test_session_a_dispatch_targets_or_reports_to_is_left_alone(self):
        d = [{"status": "delivered", "target_session_id": "dddddddd-4",
              "origin_thread_id": "claude:eeeeeeee-5"}]
        out, calls = self.run_sweep([row("thebes-team-luxor", "dddddddd-4", "blocked"),
                                     row("thebes-orchestrator", "eeeeeeee-5", "idle")],
                                    bound=[], dispatches=d)
        self.assertEqual(calls, [])

    def test_refused_rm_is_logged_and_left(self):
        out, calls = self.run_sweep([row("thebes-team-habu", "ffffffff-6", "stopped")], bound=[],
                                    refuse_rm={"ffffffff"})
        self.assertEqual(out[0]["result"], "refused")
        self.assertEqual(calls, [])
        self.assertEqual(len(self.logged), 1)

    def test_non_thebes_sessions_are_never_touched(self):
        out, calls = self.run_sweep([row("Thebes System", "11111111-7", "working"),
                                     row("Claude code controlling Google TV", "22222222-8", "idle"),
                                     row(None, "33333333-9", "stopped")], bound=[])
        self.assertEqual(calls, [])

    def test_dispatch_copy_is_retired(self):
        out, calls = self.run_sweep([row("conversation-dispatch-31b61638", "hhhhhhhh-1", "blocked")],
                                    bound=[])
        self.assertEqual((out[0]["team"], calls), ("dispatch-copy", [("stop", "hhhhhhhh")]))

    def test_dry_run_changes_nothing(self):
        cli = FakeCli([row("thebes-team-karnak", "bbbbbbbb-2", "working")])
        out = team_pool.sweep_duplicates(state_store=FakeStore([]), cli=cli, dry_run=True, now=NOW)
        self.assertEqual((len(out), cli.calls), (1, []))

    def test_one_team_only(self):
        out, calls = self.run_sweep([row("thebes-team-karnak", "bbbbbbbb-2", "working"),
                                     row("thebes-team-habu", "gggggggg-0", "working")], bound=[])
        self.assertEqual(len(calls), 2)
        cli = FakeCli([row("thebes-team-karnak", "bbbbbbbb-2", "working"),
                       row("thebes-team-habu", "gggggggg-0", "working")])
        team_pool.sweep_duplicates(state_store=FakeStore([]), cli=cli, team="habu", now=NOW)
        self.assertEqual(cli.calls, [("stop", "gggggggg")])


if __name__ == "__main__":
    unittest.main()
