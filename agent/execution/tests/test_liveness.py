#!/usr/bin/env python3
"""D-045: every team is probed every 5 minutes, busy or not, and what is stuck reaches the
orchestrator once, from the session's own evidence rather than from what it believes."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                  # noqa: E402
from agent.execution import liveness, review_queue                   # noqa: E402

SIDS = {t: "d0000000-0000-4000-8000-00000000000%d" % i
        for i, t in enumerate(["karnak", "habu", "luxor", "edfu", "memphis"], 1)}
TEAMS = {t: {"number": i, "lane": "code", "kind": "team"} for i, t in enumerate(SIDS, 1)}
TEAMS["ghost"] = {"number": 9, "lane": "code", "kind": "team"}
TEAMS["orchestrator"] = {"number": 0, "kind": "controller"}


class FakeCli:
    def __init__(self, states):
        self.states = states

    def agents(self, include_completed=False):
        return [{"sessionId": SIDS[t], "state": s, "startedAt": 1} for t, s in self.states.items()]


class FakeStore:
    def __init__(self, dispatches=()):
        self.dispatches = list(dispatches)

    def active_role_session(self, seat):
        return {"session_id": SIDS[seat], "stable_home": "/tmp"} if seat in SIDS else None

    def read_all(self, kind):
        return self.dispatches if kind == "conversation_dispatch" else []


class LivenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, teams.read)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        os.makedirs(store.RUNTIME)
        teams.read = lambda: TEAMS
        self.projects = os.path.join(self.tmp, "projects")
        os.makedirs(os.path.join(self.projects, "p"))
        self.now = time.time()
        # Hermetic: the sweep also lists working-column tickets, which read the real Jira board.
        from agent.execution import orphans
        self.old_scan, orphans.scan = orphans.scan, lambda **kw: []

    def tearDown(self):
        from agent.execution import orphans
        orphans.scan = self.old_scan
        store.RUNTIME, teams.read = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def transcript(self, team, quiet_seconds):
        f = os.path.join(self.projects, "p", "%s.jsonl" % SIDS[team])
        open(f, "w").close()
        os.utime(f, (self.now - quiet_seconds, self.now - quiet_seconds))

    def sweep(self, states, dispatches=()):
        snap = liveness.sweep(state_store=FakeStore(dispatches), cli=FakeCli(states),
                              now=self.now, projects=self.projects)
        return {e["team"]: e for e in snap["teams"]}

    def test_the_mode_a_session_resumes_in_is_its_last_recorded_one(self):
        # TH-073: the orchestrator went auto -> plan -> default from the app and kept it.
        f = os.path.join(self.projects, "p", "%s.jsonl" % SIDS["karnak"])
        with open(f, "w") as fh:
            for m in ("auto", "plan", "default"):
                fh.write('{"type": "permission-mode", "permissionMode": "%s"}\n' % m)
                fh.write('{"type": "user", "message": {"content": "permission-mode"}}\n')
        self.assertEqual(liveness.permission_mode(SIDS["karnak"], self.projects), "default")
        self.assertIsNone(liveness.permission_mode("no-such-session", self.projects))

    def test_every_team_is_probed_including_idle_and_sessionless(self):
        for t in SIDS:
            self.transcript(t, 60)
        got = self.sweep({t: "idle" for t in SIDS})
        self.assertEqual(sorted(got), sorted(list(SIDS) + ["ghost"]))
        self.assertEqual(got["karnak"]["status"], "free")
        self.assertEqual(got["ghost"]["status"], "no-session")

    def test_working_but_quiet_is_silent_and_working_with_a_dispatch_is_busy(self):
        self.transcript("luxor", liveness.SILENT_SECONDS + 60)
        self.transcript("habu", 30)
        d = [{"dispatch_id": "d1", "target_seat_id": "habu", "status": "delivered",
              "jira_key": "KAN-1"},
             {"dispatch_id": "d2", "target_seat_id": "luxor", "status": "delivered",
              "jira_key": "KAN-2"}]
        got = self.sweep({"luxor": "working", "habu": "working"}, d)
        self.assertEqual((got["habu"]["status"], got["habu"]["detail"]), ("busy", "KAN-1"))
        self.assertEqual(got["luxor"]["status"], "silent")

    def test_working_without_a_dispatch_is_untracked_unless_it_just_submitted(self):
        self.transcript("karnak", 30)
        self.transcript("habu", 30)
        just = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.now - 120))
        d = [{"dispatch_id": "d1", "target_seat_id": "habu", "status": "completed",
              "outcome_at": just}]
        got = self.sweep({"karnak": "working", "habu": "working"}, d)
        self.assertEqual(got["karnak"]["status"], "untracked")
        self.assertEqual(got["habu"]["status"], "busy")

    def test_an_open_dispatch_on_a_stopped_session_is_stalled(self):
        d = [{"dispatch_id": "d1", "target_seat_id": "memphis", "status": "delivered"}]
        self.assertEqual(self.sweep({}, d)["memphis"]["status"], "stalled")

    def test_review_claims_count_as_holding_work(self):
        self.transcript("edfu", 30)
        orig = (review_queue._dir, review_queue.is_done)
        claims = os.path.join(self.tmp, "claims")
        os.makedirs(claims)
        review_queue._dir = lambda name: claims
        review_queue.is_done = lambda item: False
        try:
            with open(os.path.join(claims, "c1.json"), "w") as fh:
                json.dump({"item_id": "qa-KAN-9", "thread": "claude:%s" % SIDS["edfu"],
                           "at": self.now - 60}, fh)
            got = self.sweep({"edfu": "working"})
        finally:
            review_queue._dir, review_queue.is_done = orig
        self.assertEqual((got["edfu"]["status"], got["edfu"]["detail"]),
                         ("busy", "review qa-KAN-9"))

    def test_a_problem_reaches_the_inbox_once(self):
        self.transcript("karnak", 30)
        self.sweep({"karnak": "working"})
        items = [i for i in liveness.inbox_items() if i["team"] == "karnak"]
        self.assertEqual(len(items), 1)
        self.assertIn("CEO hears none", items[0]["how"])
        liveness.mark_collected(items[0]["key"])
        self.sweep({"karnak": "working"})
        self.assertFalse([i for i in liveness.inbox_items() if i["team"] == "karnak"])

    def test_blocked_with_a_dispatch_is_left_to_the_watchdog_alert(self):
        self.transcript("luxor", 30)
        d = [{"dispatch_id": "d1", "target_seat_id": "luxor", "status": "delivered"}]
        self.sweep({"luxor": "blocked"}, d)
        self.assertFalse([e for e in liveness.problems() if e["team"] == "luxor"])

    def test_fact_rows_say_when_the_snapshot_is_stale(self):
        self.sweep({})
        self.assertNotIn("STALE", liveness.fact_rows(self.now + 60)[0])
        self.assertIn("STALE", liveness.fact_rows(self.now + liveness.STALE_SECONDS + 60)[0])
        self.assertTrue(any(r.startswith(" !ghost") for r in liveness.fact_rows(self.now)))

    def test_maybe_sweep_waits_five_minutes(self):
        self.sweep({})
        before = liveness._load("snapshot", {})["at"]
        liveness.maybe_sweep(state_store=FakeStore(), now=self.now + 60)
        self.assertEqual(liveness._load("snapshot", {})["at"], before)

    def test_a_review_team_waiting_in_its_queue_is_free_not_silent(self):
        from agent.execution import watchdog
        self.transcript("edfu", liveness.SILENT_SECONDS + 600)
        orig = watchdog.pending_tool
        watchdog.pending_tool = lambda sid, projects=None: (
            "Bash", '{"command": "python3 -m agent.execution.review_queue wait --timeout 3600"}')
        try:
            got = self.sweep({"edfu": "working"})
        finally:
            watchdog.pending_tool = orig
        self.assertEqual(got["edfu"]["status"], "free")
        self.assertFalse([e for e in liveness.problems() if e["team"] == "edfu"])


if __name__ == "__main__":
    unittest.main()
