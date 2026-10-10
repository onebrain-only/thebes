#!/usr/bin/env python3
"""Review quality (D-041): a brief with agreed checks, a team claim that Thebes verifies by
re-running the checks once, a bounded fix loop, and a ticket that actually closes.

Fakes only: a fake Jira, a fake command runner and a fake git. No process is spawned.
"""
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

from agent.state import store, validate                              # noqa: E402
from agent.execution import dispatch_brief as brief, inbox, jira_sync, verify         # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution.tests.test_jira_sync import FakeJira            # noqa: E402

ORCH = "0eeeeeee-5555-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-5555-7000-8000-00000000000a"
LUXOR = "0bbbbbbb-5555-7000-8000-00000000000b"
HOME = "/stable/home"
SHA = "a" * 40
SHA2 = "b" * 40

BRIEF = """Build the thing for KAN-50.

GOAL: Home shows the feed
BRANCH: alpha-karnak
ALLOWED PATHS: lib/
FORBIDDEN: pushing, the shared Alpha branch
DECISIONS MADE: none
CHECKS:
C1 | run   | flutter test test/home_test.dart | exit 0
C2 | run   | flutter analyze lib/home         | exit 0
C3 | judge | Home matches frame "Home Feed"    | screenshot vs frame
"""


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class Done:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


class FakeRunner:
    def __init__(self, failing=()):
        self.failing, self.calls = set(failing), []

    def __call__(self, argv, **kw):
        cmd = " ".join(argv)
        self.calls.append((cmd, kw.get("cwd"), kw.get("shell")))
        return Done(1 if cmd in self.failing else 0, "boom: expected 1 got 2" if cmd in self.failing
                    else "All tests passed")


def report(branch="alpha-karnak", sha=SHA, wt=None, c=(("C1", "PASS"), ("C2", "PASS"),
                                                       ("C3", "PASS"))):
    lines = ["Did the work.", "", "VERIFY", "branch: %s" % branch, "sha: %s" % sha,
             "worktree: %s" % wt]
    lines += ["%s: %s — evidence for %s" % (cid, st, cid) for cid, st in c]
    return "\n".join(lines)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.wt = os.path.join(self.tmp, "jobs", "1ee27200", "worktrees", "alpha-karnak")
        os.makedirs(self.wt)
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        self.jira = FakeJira("10046")
        self.launched, self.verifies, self.sent = [], [], []
        self.head = SHA
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        real = jira_sync._client
        self.patches.append(mock.patch.object(
            jira_sync, "_client", lambda jira, state_store: real(jira or self.jira, state_store)))
        self.patches.append(mock.patch.object(
            verify, "allowed_roots", lambda: (os.path.realpath(os.path.join(self.tmp, "jobs")),)))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- fixtures --------------------------------------------------------------
    def deliver(self, did):
        rec = store.read("conversation_dispatch", did)
        rec = store.update("conversation_dispatch", did, rec["revision"],
                           {"status": "delivered", "delivery_status": "DELIVERED"})
        store.record_session_delivery(did, {
            "dispatch_id": did, "work_item_id": None, "seat_id": rec["target_seat_id"],
            "provider": "claude", "session_id": rec["target_session_id"], "status": "DELIVERED",
            "stopped_before_resume": "YES", "resumed_same_sid": "YES",
            "session_count_before": 1, "session_count_after": 1, "delivered_at": store.now()})
        jira_sync.on_start(rec, state_store=store)

    def dispatch(self, prompt=BRIEF, to=KARNAK, **kw):
        kw.setdefault("ticket", "KAN-50")
        cd.dispatch(prompt, to, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                    detach=True, launcher=lambda d, c: self.launched.append((d, c)),
                    lane_capability="frontend", **kw)
        did, cap = self.launched[-1]
        self.deliver(did)
        return did, cap

    def submit(self, did, cap, text, outcome="completed", sid=KARNAK):
        return cd.submit(did, outcome, text, env={"CLAUDE_CODE_SESSION_ID": sid,
                                                  cd.CAPABILITY_ENV: cap}, state_store=store,
                         decision_router=lambda r, state_store: {"route": "escalate"},
                         verify_launcher=self.verifies.append)

    def verify_run(self, did, runner=None, **kw):
        return verify.run(did, state_store=store, runner=runner or FakeRunner(),
                          git_head=lambda wt: self.head, jira=self.jira,
                          launcher=lambda d, c: self.sent.append((d, c)), **kw)

    def deliver_sent(self):
        did, cap = self.sent[-1]
        self.deliver(did)
        return did, cap

    def collect(self):
        return inbox.collect(ORCH, state_store=store)

    # -- the brief -------------------------------------------------------------
    def test_a_ticket_dispatch_without_a_brief_is_refused_naming_everything_missing(self):
        with self.assertRaises(cd.Refused) as ctx:
            cd.dispatch("Implement KAN-50 please.", KARNAK,
                        env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store, detach=True,
                        launcher=_refuse, ticket="KAN-50")
        msg = str(ctx.exception)
        self.assertEqual(ctx.exception.code, "brief-incomplete")
        for part in ("GOAL", "DECISIONS MADE", "BRANCH", "CHECKS"):
            self.assertIn(part, msg)

    def test_a_dispatch_with_no_ticket_needs_no_brief_even_if_it_mentions_one(self):
        out = cd.dispatch("Summarize KAN-1 in one line", KARNAK, env={"CLAUDE_CODE_SESSION_ID": ORCH},
                          state_store=store, detach=True, launcher=lambda d, c: None)
        self.assertEqual(out["status"], "accepted")

    def test_one_branch_per_team_and_only_allowlisted_commands(self):
        with self.assertRaises(brief.BriefError) as ctx:
            brief.lint(BRIEF.replace("alpha-karnak", "Alpha"), "karnak")
        self.assertIn("must end with -karnak", str(ctx.exception))
        for bad in ("flutter test; rm -rf /", "bash -c 'x'", "flutter test /etc/passwd",
                    "flutter test ../other", "git push", "flutter test $(whoami)"):
            self.assertIsNotNone(verify.command_problem(bad), bad)
        self.assertIsNone(verify.command_problem("flutter test --no-pub test/a_test.dart"))
        with self.assertRaises(brief.BriefError):
            brief.lint(BRIEF.replace("flutter analyze lib/home", "git push origin main"), "karnak")

    def test_a_duplicate_can_be_discarded_without_rework_or_integration(self):
        """Report item 12: a failed verdict always meant rework."""
        did, cap = self.dispatch()
        with self.assertRaises(verify.Refused):
            verify.discard(did, "dup", env={"CLAUDE_CODE_SESSION_ID": LUXOR}, state_store=store)
        out = verify.discard(did, "KAN-484 duplicate", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                             state_store=store, jira=mock.Mock())
        self.assertEqual(out["status"], "discarded")
        rec = store.read("conversation_dispatch", did)
        self.assertEqual(rec["verification"]["verdict"], "discarded")
        self.assertEqual(rec["integrated_at"], "discarded")

    def test_only_one_integration_into_a_base_at_a_time(self):
        integ = BRIEF.replace("BRANCH: alpha-karnak", "INTEGRATE: Alpha")
        self.dispatch(integ)
        with self.assertRaises(cd.Refused) as ctx:
            cd.dispatch(integ, LUXOR, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                        detach=True, launcher=_refuse, ticket="KAN-50")
        self.assertEqual(ctx.exception.code, "integration-busy")

    def test_the_envelope_tells_the_team_the_verify_block_and_the_branch_rule(self):
        did, cap = self.dispatch()
        env = cd.build_envelope(store.read("conversation_dispatch", did), cap)
        for s in ("VERIFY", "sha: <full 40-character commit>", "C3: PASS|FAIL",
                  "Never check out or commit to the shared base branch"):
            self.assertIn(s, env)

    # -- verification ------------------------------------------------------------
    def test_all_checks_pass_then_one_judge_pass_then_the_ticket_closes(self):
        did, cap = self.dispatch()
        self.submit(did, cap, report(wt=self.wt))
        self.assertEqual(self.verifies, [did], "verification starts by itself")
        self.assertEqual(self.jira.moves[-1], ("KAN-50", "10044"), "review on report")
        runner = FakeRunner()
        out = self.verify_run(did, runner)
        self.assertEqual(out["verdict"], "needs_judge")
        self.assertEqual([c[0] for c in runner.calls],
                         ["flutter test test/home_test.dart", "flutter analyze lib/home"])
        self.assertTrue(all(c[2] is False for c in runner.calls), "never through a shell")
        self.assertTrue(all(c[1] == os.path.realpath(self.wt) for c in runner.calls))
        got = self.collect()
        self.assertEqual([i["kind"] for i in got], ["judge"], "not a bare 'completed'")
        self.assertEqual([p["id"] for p in got[0]["pending"]], ["C3"])
        with self.assertRaises(verify.Refused):
            verify.judge_verdict(did, ["C3"], {}, env={"CLAUDE_CODE_SESSION_ID": KARNAK},
                                 state_store=store)
        res = verify.judge_verdict(did, ["C3"], {}, env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                   state_store=store, jira=self.jira)
        self.assertEqual(res["verdict"], "pass")
        self.assertEqual(self.jira.moves[-1], ("KAN-50", "10007"), "Done")
        self.assertIn("closed this", self.jira.comments[-1][1])
        self.assertIn("C1 PASS", self.jira.comments[-1][1])
        final = self.collect()
        self.assertEqual([(i["kind"], i["verdict"]) for i in final], [("verification", "pass")])
        self.assertEqual(self.clean(), [])

    def test_a_failing_check_sends_back_only_that_check_and_the_fix_closes_it(self):
        brief_run_only = "\n".join(l for l in BRIEF.splitlines() if "| judge |" not in l)
        did, cap = self.dispatch(brief_run_only)
        self.submit(did, cap, report(wt=self.wt, c=(("C1", "PASS"), ("C2", "PASS"))))
        out = self.verify_run(did, FakeRunner(failing={"flutter analyze lib/home"}))
        self.assertEqual(out["verdict"], "retry")
        self.assertEqual(out["continuation"]["failing"], ["C2"])
        fix_did, fix_cap = self.deliver_sent()
        fix = store.read("conversation_dispatch", fix_did)
        self.assertEqual((fix["root_dispatch_id"], fix["verify_cycle"], fix["jira_key"]),
                         (did, 2, "KAN-50"))
        self.assertEqual([c["id"] for c in fix["checks"]], ["C2"])
        text = open(fix["prompt_ref"]).read()
        self.assertIn("C2 FAILED", text)
        self.assertIn("boom: expected 1 got 2", text)
        self.assertNotIn("C1 FAILED", text, "passed checks are not re-sent")
        self.assertEqual(self.jira.moves[-1], ("KAN-50", "10046"), "back to its lane")
        self.head = SHA2
        self.submit(fix_did, fix_cap, report(sha=SHA2, wt=self.wt, c=(("C2", "PASS"),)))
        runner = FakeRunner()
        out2 = self.verify_run(fix_did, runner)
        self.assertEqual([c[0] for c in runner.calls], ["flutter analyze lib/home"],
                         "only the failed check is re-run")
        self.assertEqual(out2["verdict"], "pass")
        self.assertEqual(self.jira.moves[-1], ("KAN-50", "10007"))
        self.assertEqual([i["kind"] for i in self.collect() if i["kind"] != "alert"],
                         ["verification"])

    def test_still_failing_after_the_fix_is_exhausted_not_looped(self):
        brief_run_only = "\n".join(l for l in BRIEF.splitlines() if "| judge |" not in l)
        did, cap = self.dispatch(brief_run_only)
        self.submit(did, cap, report(wt=self.wt, c=(("C1", "PASS"), ("C2", "PASS"))))
        bad = FakeRunner(failing={"flutter test test/home_test.dart"})
        self.verify_run(did, bad)
        fix_did, fix_cap = self.deliver_sent()
        self.submit(fix_did, fix_cap, report(wt=self.wt, c=(("C1", "PASS"),)))
        out = self.verify_run(fix_did, bad)
        self.assertEqual(out["verdict"], "exhausted")
        self.assertEqual(len(self.sent), 1, "no third pass")
        self.assertNotEqual(self.jira.moves[-1], ("KAN-50", "10007"), "not closed")
        self.assertIn("needs a decision, not another retry", self.jira.comments[-1][1])
        root = store.read("conversation_dispatch", did)
        self.assertEqual(root["watchdog_alert"]["kind"], "review-exhausted")
        kinds = [(i["kind"], i.get("verdict") or i.get("alert")) for i in self.collect()]
        self.assertIn(("verification", "exhausted"), kinds)

    def test_a_check_thebes_could_not_run_is_not_the_teams_defect(self):
        brief_run_only = "\n".join(l for l in BRIEF.splitlines() if "| judge |" not in l)
        did, cap = self.dispatch(brief_run_only)
        self.submit(did, cap, report(wt=self.wt, c=(("C1", "PASS"), ("C2", "PASS"))))

        def no_flutter(argv, **kw):
            raise FileNotFoundError("flutter")
        out = self.verify_run(did, no_flutter)
        self.assertEqual(out["verdict"], "error")
        self.assertEqual(self.sent, [], "nothing is sent back to the team")
        root = store.read("conversation_dispatch", did)
        self.assertEqual(root["watchdog_alert"]["kind"], "review-could-not-run")
        self.assertEqual(root["verification"]["cycle"], 1, "no review cycle was spent")
        again = self.verify_run(did, FakeRunner(), force=True)
        self.assertEqual(again["verdict"], "pass")

    def test_a_claimed_pass_that_fails_when_re_run_is_called_out(self):
        did, cap = self.dispatch()
        self.submit(did, cap, report(wt=self.wt))
        self.verify_run(did, FakeRunner(failing={"flutter test test/home_test.dart"}))
        root = store.read("conversation_dispatch", did)
        self.assertIn("the report claimed PASS", root["verification"]["results"]["C1"]["detail"])

    def test_a_missing_or_wrong_commit_fails_every_run_check_without_running_anything(self):
        did, cap = self.dispatch()
        self.submit(did, cap, "All done, trust me.")
        runner = FakeRunner()
        out = self.verify_run(did, runner)
        self.assertEqual(runner.calls, [])
        self.assertEqual(out["verdict"], "retry")
        did2, cap2 = self.dispatch(to=LUXOR, prompt=BRIEF.replace("alpha-karnak", "alpha-luxor"))
        self.submit(did2, cap2, report(wt="/etc", sha=SHA), sid=LUXOR)
        r2 = FakeRunner()
        self.verify_run(did2, r2)
        self.assertEqual(r2.calls, [], "a worktree outside the teams' directories is never used")
        self.head = SHA2
        self.assertIn("HEAD is", verify.worktree_problem(
            {"sha": SHA, "worktree": self.wt}, git_head=lambda w: SHA2))

    def test_a_peer_route_ticket_is_verified_but_not_closed_by_thebes(self):
        t = store.admit_task("KAN-50", "app", "10046", "frontend", "po", "po: ui",
                             work_effort=1)
        prof = dict(t["execution_profile"], validation_route="peer")
        store.update("task", "KAN-50", t["revision"], {"execution_profile": prof})
        brief_run_only = "\n".join(l for l in BRIEF.splitlines() if "| judge |" not in l)
        did, cap = self.dispatch(brief_run_only)
        self.submit(did, cap, report(wt=self.wt, c=(("C1", "PASS"), ("C2", "PASS"))))
        out = self.verify_run(did)
        self.assertEqual(out["verdict"], "pass")
        self.assertEqual(self.jira.moves[-1], ("KAN-50", "10045"), "stays in Peer-review")
        self.assertIn("peer reviewer checks only what the checks do not cover",
                      self.jira.comments[-1][1])

    def test_verification_is_idempotent_and_skips_dispatches_without_checks(self):
        did, cap = self.dispatch()
        self.submit(did, cap, report(wt=self.wt))
        self.verify_run(did)
        self.assertEqual(self.verify_run(did)["status"], "already-verified")
        out = cd.dispatch("count files", KARNAK, env={"CLAUDE_CODE_SESSION_ID": ORCH},
                          state_store=store, detach=True, launcher=lambda d, c: None)
        self.assertEqual(verify.run(out["dispatch_id"], state_store=store)["status"], "no-checks")

    def test_if_verification_never_ran_the_plain_result_still_arrives(self):
        did, cap = self.dispatch()
        self.submit(did, cap, report(wt=self.wt))
        self.assertEqual(self.collect(), [], "held for verification")
        rec = store.read("conversation_dispatch", did)
        later = (__import__("time").time() + inbox.VERIFY_GRACE_SECONDS + 60)
        got = inbox.collect(ORCH, state_store=store, now=later)
        self.assertEqual([i["kind"] for i in got], ["result"])
        self.assertEqual(rec["status"], "completed")

    def clean(self):
        return [e for e in validate.check(store.RUNTIME)
                if any(k in e for k in ("task", "conversation", "decision"))]


if __name__ == "__main__":
    unittest.main()
