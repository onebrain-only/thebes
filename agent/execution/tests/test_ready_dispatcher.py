#!/usr/bin/env python3
"""The Ready dispatcher (D-042): a Ready ticket is the order. Fakes only."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, teams, validate                       # noqa: E402
from agent.execution import ready_dispatcher as rd                   # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402

ORCH = "0eeeeeee-6666-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-6666-7000-8000-00000000000a"
LUXOR = "0bbbbbbb-6666-7000-8000-00000000000b"
HABU = "0ccccccc-6666-7000-8000-00000000000c"
HOME = "/stable/home"

BRIEF = """GOAL: tests for the formatter
BRANCH: alpha-<team>
ALLOWED PATHS: test/
FORBIDDEN: lib/
DECISIONS MADE: none
CHECKS:
C1 | run | flutter test test/x_test.dart | exit 0
"""


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


def issue(key, description=BRIEF, labels=(), links=(), component=None):
    return {"key": key, "id": key[4:], "fields": {
        "summary": "Ticket " + key, "status": {"name": "Ready", "id": "10008"},
        "labels": list(labels), "issuelinks": list(links),
        "components": [{"name": component}] if component else [],
        "description": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            for line in description.splitlines()]}}}


def blocked_by(key, done=False):
    return {"type": {"name": "Blocks"}, "inwardIssue": {"key": key, "fields": {
        "status": {"statusCategory": {"key": "done" if done else "indeterminate"}}}}}


class FakeJira:
    def __init__(self, issues, fresh=(), backlog=()):
        self.issues, self.comments, self.updates = list(issues), [], []
        self.fresh, self.backlog = set(fresh), list(backlog)
        from agent.integrations import jira as real
        self.normalize_issue = real.normalize_issue

    def search_issues(self, jql, fields=None, limit=50, raw=False):
        if "CHANGED TO" in jql:
            return [{"key": k} for k in self.fresh]
        if 'status = "Done"' in jql:
            return [{"key": k} for k in getattr(self, "done", [])]
        if 'status = "To Do"' in jql:
            return [{"key": k, "updated": "u"} for k in self.backlog]
        assert raw and 'status = "Ready"' in jql
        return self.issues

    def add_comment(self, key, body):
        self.comments.append((key, body))

    def update_issue(self, key, fields):
        self.updates.append((key, fields))
        for i in self.issues:
            if i["key"] == key:
                i["fields"]["labels"] = fields["labels"]


class ReadyDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        store.set_operating_mode("PRODUCT_EXECUTION", "ceo", "test")
        self.sent = []
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        real = teams.read()
        self.lanes = dict((t, dict(e)) for t, e in real.items())
        self.patches.append(mock.patch.object(teams, "read", lambda path=None: self.lanes))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dispatch(self, text, sid, env, state_store, detach, ticket, lane_capability):
        self.sent.append({"text": text, "sid": sid, "ticket": ticket, "cap": lane_capability,
                          "origin": env.get(cd.CLAUDE_ORIGIN_ENV)})
        did = state_store.new_id("conversation_dispatch")
        team = {KARNAK: "karnak", LUXOR: "luxor", HABU: "habu"}[sid]
        state_store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": sid, "target_seat_id": team,
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "delivering", "jira_key": ticket}, rid=did)
        return {"dispatch_id": did}

    def tick(self, jira):
        return rd.tick(state_store=store, jira=jira, dispatch=self.dispatch)

    def with_ops(self):
        self.lanes["habu"]["lane"] = "ops"
        store.bind_role_session("habu", "claude", HABU, HOME, "ceo")

    # -----------------------------------------------------------------------
    def test_a_ready_ticket_is_dispatched_to_a_free_code_team_with_its_branch(self):
        j = FakeJira([issue("KAN-500", labels=["cap:frontend"])])
        out = self.tick(j)
        self.assertEqual([(d["key"], d["action"], d["team"]) for d in out],
                         [("KAN-500", "dispatched", "karnak")])
        sent = self.sent[0]
        self.assertEqual((sent["ticket"], sent["cap"], sent["origin"]),
                         ("KAN-500", "frontend", ORCH), "results reach the orchestrator inbox")
        self.assertIn("BRANCH: alpha-karnak", sent["text"])
        self.assertIn("Every commit message starts with `KAN-500:`", sent["text"])
        self.assertIn("Expected effort: not estimated.", sent["text"])
        self.assertIn("Expected effort (PM's Original estimate): 3h.", rd.effort_line(10800))
        self.assertIn("1.5h", rd.effort_line(5400))
        self.assertEqual(self.tick(j), [], "an open dispatch is never sent twice")

    def test_parallel_tickets_go_to_different_teams_and_wait_when_none_is_free(self):
        j = FakeJira([issue("KAN-501", labels=["cap:frontend"]),
                      issue("KAN-502", labels=["cap:backend"]),
                      issue("KAN-503", labels=["cap:frontend"])])
        out = self.tick(j)
        self.assertEqual([(d["key"], d["action"], d.get("team") or d.get("reason")) for d in out],
                         [("KAN-501", "dispatched", "karnak"), ("KAN-502", "dispatched", "luxor"),
                          ("KAN-503", "waiting", "no-free-code-team")])

    def test_a_ticket_blocked_by_an_unfinished_one_waits(self):
        j = FakeJira([issue("KAN-504", labels=["cap:frontend"], links=[blocked_by("KAN-400")]),
                      issue("KAN-505", labels=["cap:frontend"],
                            links=[blocked_by("KAN-401", done=True)])])
        out = self.tick(j)
        self.assertEqual(out[0], {"key": "KAN-504", "action": "waiting",
                                  "blocked_by": ["KAN-400"]})
        self.assertEqual((out[1]["key"], out[1]["action"]), ("KAN-505", "dispatched"))

    def test_an_incomplete_brief_is_commented_once_and_labelled_never_looped(self):
        j = FakeJira([issue("KAN-506", description="Make the home screen nicer.",
                            labels=["cap:frontend"])])
        out = self.tick(j)
        self.assertEqual(out[0]["action"], "needs-brief")
        self.assertIn("GOAL", " ".join(out[0]["problems"]))
        self.assertEqual(len(j.comments), 1)
        self.assertIn(rd.NEEDS_BRIEF, j.issues[0]["fields"]["labels"])
        self.assertEqual(self.sent, [])
        self.tick(j); self.tick(j)
        self.assertEqual(len(j.comments), 1, "one comment, no matter how many passes")

    def test_a_missing_brief_asks_the_po_through_one_priority_request(self):
        self.with_ops()
        j = FakeJira([issue("KAN-507", description="Make it nicer.", labels=["cap:frontend"])])
        self.tick(j)
        self.assertEqual(self.sent, [], "the brief is not Memphis's job any more (D-042)")
        self.tick(j)
        reqs = store.read_all("priority_request")
        self.assertEqual(len(reqs), 1, "one open request, reasons merged")
        self.assertEqual({r["key"] for r in reqs[0]["reasons"] if r["kind"] == "needs-brief"},
                         {"KAN-507"})
        self.assertIn(rd.BRIEF_REQUESTED, j.issues[0]["fields"]["labels"])
        from agent.execution import inbox
        items = inbox.collect(ORCH, state_store=store)
        self.assertEqual([(i["kind"], i["needs_brief"]) for i in items],
                         [("priority", ["KAN-507"])])
        self.assertEqual(inbox.collect(ORCH, state_store=store), [], "collected once")

    def test_backlog_changes_ask_the_pm_at_most_hourly(self):
        j = FakeJira([], backlog=["KAN-600", "KAN-601"])
        out = self.tick(j)
        req = [d for d in out if d.get("action") == "priority-request"][0]
        self.assertEqual(set(req["reasons"]), {"backlog-changed", "ready-short"})
        from agent.execution import inbox
        inbox.collect(ORCH, state_store=store)
        self.assertFalse([d for d in self.tick(j) if d.get("action") == "priority-request"],
                         "nothing new: rate-limited within the hour")
        j.backlog.append("KAN-602")
        out = [d for d in self.tick(j) if d.get("action") == "priority-request"]
        self.assertEqual(out[0]["reasons"], ["new-in-backlog"],
                         "a NEW ticket from the desk is asked about at once")
        inbox.collect(ORCH, state_store=store)
        self.assertFalse([d for d in self.tick(j) if d.get("action") == "priority-request"])
        later = __import__("time").time() + rd.PRIORITY_MIN_SECONDS + 5
        out = rd.tick(state_store=store, jira=j, dispatch=self.dispatch, now=later)
        self.assertFalse([d for d in out if d.get("action") == "priority-request"],
                         "malfunction #28: an unchanged Backlog is not asked about again")
        j.done = ["KAN-1"]                       # something finished: the Backlog may be unblocked
        out = rd.tick(state_store=store, jira=j, dispatch=self.dispatch, now=later)
        self.assertTrue([d for d in out if d.get("action") == "priority-request"])

    def test_the_owner_team_gets_its_domain_first(self):
        j = FakeJira([issue("KAN-610", labels=["cap:frontend"], component="Listings"),
                      issue("KAN-611", labels=["cap:frontend"])])
        out = self.tick(j)
        got = {d["key"]: d["team"] for d in out if d.get("action") == "dispatched"}
        self.assertEqual(got["KAN-610"], "luxor", "Listings is Luxor's although Karnak is first")
        self.assertEqual(got["KAN-611"], "karnak")

    def test_a_fresh_owned_ticket_waits_for_its_busy_owner_then_anyone_takes_it(self):
        j = FakeJira([issue("KAN-620", labels=["cap:frontend"], component="Auth")])
        self.dispatch("x", KARNAK, {}, store, True, "KAN-999", "frontend")   # Karnak busy
        j.fresh = {"KAN-620"}
        out = self.tick(j)
        self.assertEqual(out[0], {"key": "KAN-620", "action": "waiting",
                                  "reason": "owner-busy:karnak"})
        j.fresh = set()                                    # 30 minutes later
        out = self.tick(j)
        self.assertEqual((out[0]["action"], out[0]["team"]), ("dispatched", "luxor"))

    def test_the_any_team_label_skips_the_owner_wait(self):
        j = FakeJira([issue("KAN-621", labels=["cap:frontend", "any-team"], component="Auth")])
        self.dispatch("x", KARNAK, {}, store, True, "KAN-999", "frontend")   # Karnak busy
        j.fresh = {"KAN-621"}
        out = self.tick(j)
        self.assertEqual((out[0]["action"], out[0]["team"]), ("dispatched", "luxor"))

    def test_teams_cannot_reserve_the_po_or_the_pm(self):
        with self.assertRaises(store.StateError) as ctx:
            store.reserve_seat("po", "karnak", "cdispatch-x")
        self.assertIn("orchestrator-only-seat", str(ctx.exception))
        with self.assertRaises(store.StateError):
            store.reserve_seat("pm", "luxor", "cdispatch-x")

    def test_no_capability_means_needs_brief(self):
        j = FakeJira([issue("KAN-509")])
        out = self.tick(j)
        self.assertEqual(out[0]["action"], "needs-brief")
        self.assertIn("capability", out[0]["problems"][0])

    def test_ask_and_non_code_capabilities_go_to_ops_only(self):
        j = FakeJira([issue("KAN-510", description=BRIEF.replace("alpha-<team>", "none"),
                            labels=["cap:analyst"])])
        out = self.tick(j)
        self.assertEqual(out[0]["reason"], "no-free-ops-team", "never to a code team")
        self.with_ops()
        out = self.tick(j)
        self.assertEqual((out[0]["action"], out[0]["team"]), ("dispatched", "habu"))

    def test_maintenance_mode_and_freeze_stop_all_dispatching(self):
        j = FakeJira([issue("KAN-511", labels=["cap:frontend"])])
        import operations
        cur = store.read("operating_mode", operations.CURRENT_MODE_ID)
        store.set_operating_mode("SYSTEM_MAINTENANCE", "ceo", "test",
                                 expected_revision=cur["revision"])
        self.assertEqual(self.tick(j), [{"skipped": "mode-SYSTEM_MAINTENANCE"}])
        self.assertEqual(self.sent, [])

    def test_fill_branch_replaces_the_team_and_keeps_the_base(self):
        self.assertIn("BRANCH: alpha-luxor", rd.fill_branch("BRANCH: alpha-<team>", "luxor"))
        self.assertIn("BRANCH: alpha-luxor", rd.fill_branch("BRANCH: alpha-karnak", "luxor"))
        self.assertIn("BRANCH: none", rd.fill_branch("BRANCH: none", "luxor"))
        self.assertIn("BRANCH: alpha-karnak", rd.fill_branch("BRANCH: alpha-frontend-1", "karnak"),
                      "live 2026-10-09: a seat name in the branch became alpha-frontend-1-karnak")
        self.assertIn("BRANCH: Alpha-luxor", rd.fill_branch("BRANCH: Alpha-<team> (team branch)",
                                                            "luxor"))


if __name__ == "__main__":
    unittest.main()
