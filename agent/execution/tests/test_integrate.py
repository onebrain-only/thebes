#!/usr/bin/env python3
"""Automatic integration of verified work into Alpha (D-042). Fakes only."""
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
from agent.execution import integrate                                # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402

ORCH = "0eeeeeee-9999-7000-8000-00000000000e"
LUXOR = "0bbbbbbb-9999-7000-8000-00000000000b"
MEMPHIS = "0ddddddd-9999-7000-8000-00000000000d"
HOME = "/stable/home"
SHA = "a" * 40
SHA2 = "b" * 40


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class Done:
    def __init__(self, out="", rc=0):
        self.stdout, self.returncode = out, rc


def fake_git(remote):
    """remote: {branch: sha} for ls-remote."""
    def run(argv, **kw):
        return Done("%s\trefs/heads/%s\n" % (remote[argv[-1]], argv[-1]) if argv[-1] in remote else "")
    return run


class IntegrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        store.bind_role_session("memphis", "claude", MEMPHIS, HOME, "ceo")
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches:
            p.start()
        self.sent = []

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def root(self, key="KAN-1", branch="alpha-luxor", sha=SHA, verdict="pass", **extra):
        did = store.new_id("conversation_dispatch")
        store.create("conversation_dispatch", dict({
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": LUXOR, "target_seat_id": "luxor",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "completed", "delivery_status": "DELIVERED", "outcome": "completed",
            "result_ref": "/x", "result_sha256": "0" * 64, "outcome_at": store.now(),
            "attested_delivery_id": did, "reported_session_id": LUXOR, "jira_key": key, "checks": [{"id": "C1", "kind": "run", "what": "x", "pass": "exit 0"}],
            "verification": {"verdict": verdict, "branch": branch, "sha": sha, "results": {}},
            "verified_at": store.now()}, **extra), rid=did)
        return did

    def send(self, text, sid, env, state_store, detach, ticket):
        self.sent.append({"text": text, "sid": sid, "ticket": ticket})
        did = state_store.new_id("conversation_dispatch")
        state_store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": sid, "target_seat_id": "memphis",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "delivered", "delivery_status": "DELIVERED"}, rid=did)
        return {"dispatch_id": did}

    def run_dispatch(self, remote, allowed=True):
        import json
        rules = [integrate.push_rule(t) for t in
                 (integrate.base_for("alpha-x"), integrate.base_for("alpha-ds-x"))] if allowed else []
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w") as fh:
            json.dump({"permissions": {"allow": rules}}, fh)
        return integrate.dispatch_for(state_store=store, dispatch=self.send,
                                      runner=fake_git(remote), settings_files=[path])

    def test_without_the_push_rule_nothing_is_sent_that_would_block_memphis(self):
        self.root("KAN-1", "alpha-luxor", SHA)
        out = self.run_dispatch({"alpha-luxor": SHA}, allowed=False)
        self.assertEqual(out[0]["action"], "waiting")
        self.assertIn("Bash(git -C * push origin integrate-alpha:Alpha)", out[0]["reason"])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.run_dispatch({"alpha-luxor": SHA})[0]["action"], "dispatched",
                         "the moment the CEO adds the rule, it goes")

    def test_verified_pushed_work_is_sent_to_memphis_once_with_the_whole_recipe(self):
        a = self.root("KAN-1", "alpha-luxor", SHA)
        out = self.run_dispatch({"alpha-luxor": SHA})
        self.assertEqual((out[0]["action"], out[0]["tickets"]), ("dispatched", ["KAN-1"]))
        sent = self.sent[0]
        self.assertEqual((sent["sid"], sent["ticket"]), (MEMPHIS, None))
        for part in ("INTEGRATE", "alpha-luxor @ aaaaaaaaaaaa  (tickets: KAN-1)", "OWN worktree",
                     "flutter analyze --no-pub --no-fatal-infos", "flutter test --no-pub",
                     "BY NAME, not by count", "fails only on the merged result",
                     "Never push or merge Canary or main",
                     "INTEGRATED: <KEY> <branch> <merge-commit-sha>", "do not ask the CEO"):
            self.assertIn(part, sent["text"], part)
        self.assertIn("integrate-alpha:Alpha", sent["text"])
        self.assertEqual(self.run_dispatch({"alpha-luxor": SHA}), [], "never twice")
        self.assertTrue(store.read("conversation_dispatch", a)["integration_dispatch_id"])

    def fast_runner(self, remote, files):
        base = fake_git(remote)

        def run(argv, **kw):
            if "diff" in argv:
                return Done("\n".join(files) + "\n")
            return base(argv, **kw)
        return run

    def fast(self, files):
        import json
        rules = [integrate.push_rule(integrate.base_for("alpha-x"))]
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w") as fh:
            json.dump({"permissions": {"allow": rules}}, fh)
        return integrate.dispatch_for(state_store=store, dispatch=self.send, settings_files=[path],
                                      runner=self.fast_runner({"alpha-luxor": SHA}, files))

    def test_a_small_verified_ticket_is_merged_by_the_team_that_built_it(self):
        """Fast lane, CEO 2026-10-10."""
        self.root("KAN-1", "alpha-luxor", SHA)
        out = self.fast(["lib/a.dart", "test/a_test.dart"])
        self.assertEqual((out[0]["action"], out[0]["lane"]), ("dispatched", "team"))
        self.assertEqual(self.sent[0]["sid"], LUXOR)

    def test_big_or_risky_tickets_stay_with_memphis(self):
        self.root("KAN-1", "alpha-luxor", SHA)
        self.assertEqual(self.fast(["f%d.dart" % i for i in range(6)])[0]["lane"], "ops")
        self.assertEqual(self.sent[0]["sid"], MEMPHIS)

    def test_pubspec_database_and_unknown_are_never_small(self):
        self.assertFalse(integrate.is_small(["pubspec.yaml"]))
        self.assertFalse(integrate.is_small(["supabase/migrations/1.sql"]))
        self.assertFalse(integrate.is_small(None))
        self.assertFalse(integrate.is_small([]))
        self.assertTrue(integrate.is_small(["lib/a.dart"]))

    def test_only_what_thebes_verified_and_the_team_pushed_is_integrated(self):
        self.root("KAN-1", "alpha-luxor", SHA)
        self.assertEqual(self.run_dispatch({}), [], "not pushed")
        self.assertEqual(self.run_dispatch({"alpha-luxor": SHA2}), [],
                         "the branch moved on past what was verified")
        self.root("KAN-2", "canary-luxor", SHA)
        self.root("KAN-3", "alpha-luxor", SHA, verdict="exhausted")
        self.assertEqual(self.run_dispatch({"canary-luxor": SHA, "alpha-luxor": SHA2}), [],
                         "Canary and main are never auto-integrated; failed work is never merged")

    def test_the_design_system_goes_to_alpha_ds_and_each_base_has_its_own_integration(self):
        self.root("KAN-1", "alpha-luxor", SHA)
        self.root("KAN-2", "alpha-ds-luxor", SHA2)
        out = self.run_dispatch({"alpha-luxor": SHA, "alpha-ds-luxor": SHA2})
        self.assertEqual([o["action"] for o in out], ["dispatched", "waiting"],
                         "Memphis is one session: the second base waits")
        waiting_base = out[1]["integrate"]
        out2 = self.run_dispatch({"alpha-luxor": SHA, "alpha-ds-luxor": SHA2})
        self.assertEqual(out2, [{"integrate": waiting_base, "action": "waiting",
                                 "reason": "ops-team-busy"}])
        self.assertIn("integrate-alpha-ds:alpha-ds", " ".join(s["text"] for s in self.sent) +
                      integrate.brief({"target": integrate.base_for("alpha-ds-x"), "items": [
                          {"key": "KAN-9", "branch": "alpha-ds-x", "sha": SHA}]}))

    def test_a_finished_integration_marks_tickets_and_comments_a_blocked_one_counts_an_attempt(self):
        a = self.root("KAN-1", "alpha-luxor", SHA, verified_at="2026-10-09T05:00:00Z")
        b = self.root("KAN-2", "alpha-luxor", SHA2, verified_at="2026-10-09T05:10:00Z")
        self.run_dispatch({"alpha-luxor": SHA2})
        self.assertIn("(tickets: KAN-1, KAN-2)", self.sent[0]["text"])
        self.assertIn("alpha-luxor @ bbbbbbbbbbbb", self.sent[0]["text"],
                      "one merge of the head covers the earlier ticket on the branch")
        did = self.sent[0] and [r for r in store.read_all("conversation_dispatch")
                                if r.get("integrates_base")][0]["dispatch_id"]
        ref = os.path.join(self.tmp, "result.txt")
        with open(ref, "w") as fh:
            fh.write("Done.\nINTEGRATED: KAN-1 alpha-luxor 1234567890abcdef\nBASE_SHA: fedcba0987654321\n"
                     "Skipped KAN-2: conflict in venues_screen.dart\n")
        rec = store.read("conversation_dispatch", did)
        store.update("conversation_dispatch", did, rec["revision"],
                     {"status": "blocked", "outcome": "blocked", "result_ref": ref,
                      "outcome_at": store.now(), "reported_session_id": MEMPHIS,
                      "attested_delivery_id": did, "result_sha256": "0" * 64})
        comments = []

        class J:
            def add_comment(self, k, t):
                comments.append((k, t))
        out = integrate.settle(state_store=store, jira=J())
        self.assertIn({"integrated": "KAN-1", "branch": "alpha-luxor", "base_sha": "fedcba0987654321"},
                      out)
        self.assertTrue(store.read("conversation_dispatch", a)["integrated_at"])
        self.assertIn("Integrated into Alpha", comments[0][1])
        self.assertIn("1234567890ab", comments[0][1])
        skipped = store.read("conversation_dispatch", b)
        self.assertEqual((skipped.get("integrated_at"), skipped["integration_attempts"]), (None, 1))
        self.assertIsNone(skipped["integration_dispatch_id"], "released for one more try")
        self.assertEqual(integrate.settle(state_store=store, jira=J()), [], "settled once")

    def test_a_ticket_is_left_alone_after_two_failed_attempts(self):
        self.root("KAN-1", "alpha-luxor", SHA, integration_attempts=integrate.MAX_ATTEMPTS)
        self.assertEqual(self.run_dispatch({"alpha-luxor": SHA}), [])

    def test_the_orchestrator_hears_a_blocked_integration_as_a_plain_result(self):
        from agent.execution import inbox
        self.root("KAN-1", "alpha-luxor", SHA)
        self.run_dispatch({"alpha-luxor": SHA})
        did = [r for r in store.read_all("conversation_dispatch") if r.get("integrates_base")][0]
        ref = os.path.join(self.tmp, "r.txt")
        open(ref, "w").write("Skipped KAN-1: conflict")
        store.update("conversation_dispatch", did["dispatch_id"], did["revision"],
                     {"status": "blocked", "outcome": "blocked", "result_ref": ref,
                      "outcome_at": store.now(), "reported_session_id": MEMPHIS,
                      "attested_delivery_id": did["dispatch_id"], "result_sha256": "0" * 64})
        items = inbox.pending(ORCH, state_store=store, now=__import__("time").time() + 60)
        self.assertEqual([i["kind"] for i in items if i.get("dispatch_id") == did["dispatch_id"]],
                         ["result"])


if __name__ == "__main__":
    unittest.main()
