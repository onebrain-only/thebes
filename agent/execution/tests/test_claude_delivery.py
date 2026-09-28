#!/usr/bin/env python3
"""Claude delivery adapter — characterization with a FAKE claude CLI runner.

No real claude is spawned. The fake records every argv so the tests assert the
exact transport: stop by short id only when live, flagless --bg --resume of the
FULL SID, never a session created, never a display-name match, no retry inside
a call, and a DELIVERED record replayed without touching the CLI.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                         # noqa: E402
import validate                                                      # noqa: E402
from agent.execution import claude_delivery as cd                    # noqa: E402
from agent.execution.claude_cli import ClaudeCli                     # noqa: E402

SEAT = "po"
SID = "4d417564-5e86-4808-aacf-7158dcb65d59"
OTHER = "11111111-1111-4111-8111-111111111111"
HOME = "/stable/home"


class Completed:
    def __init__(self, stdout="", stderr="", rc=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, rc


class FakeClaude:
    """A tiny model of `claude agents/stop/--bg --resume` with a live list."""

    def __init__(self, live, resume_behaviour="same", stop_ok=True):
        self.live = list(live)                 # rows: {sessionId,id,name,pid}
        self.completed = []                    # what `--all` adds: stopped sessions
        self.calls = []
        self.resume_behaviour = resume_behaviour
        self.stop_ok = stop_ok
        self.next_pid = 9000

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        cmd = argv[1:]
        if cmd[:2] == ["agents", "--json"]:
            rows = self.live if "--all" not in cmd else self.live + self.completed
            return Completed(json.dumps(rows))
        if cmd[0] == "stop":
            if not self.stop_ok:
                return Completed("", "No job matching %r" % cmd[1], 1)
            self.completed += [dict(r, status="exited") for r in self.live if r["id"] == cmd[1]]
            self.live = [r for r in self.live if r["id"] != cmd[1]]
            return Completed("stopped %s" % cmd[1])
        if cmd[:2] == ["--bg", "--resume"]:
            sid = cmd[2]
            if self.resume_behaviour == "fail":
                return Completed("", "resume exploded", 1)
            self.next_pid += 1
            if self.resume_behaviour == "copy":
                new = OTHER
                self.live.append({"sessionId": new, "id": new[:8], "name": "thebes-po-c", "pid": self.next_pid})
                return Completed("note: session is already running; starts a copy\nbackgrounded · %s" % new[:8])
            self.live.append({"sessionId": sid, "id": sid[:8], "name": "thebes-po-c", "pid": self.next_pid})
            return Completed("note: woke session %s with its saved options\nbackgrounded · %s" % (sid[:8], sid[:8]))
        raise AssertionError("unexpected argv %r" % argv)

    def kinds(self):
        return [("agents" if a[1] == "agents" else a[1] if a[1] != "--bg" else "resume") for a in self.calls]


LIVE_ROW = {"sessionId": SID, "id": SID[:8], "name": "thebes-po-c", "pid": 68684, "status": "idle"}
OTHER_ROW = {"sessionId": "9dd2598a-556e-402c-b452-29a5456794d6", "id": "9dd2598a", "name": "Persistent-session -a", "pid": 11799}


class ClaudeDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session(SEAT, "claude", SID, HOME, "ceo", session_name="thebes-po-c")
        self.dispatch = self.make_dispatch(SID)

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_dispatch(self, sid, provider="claude"):
        return store.create("session_dispatch", {
            "work_item_id": "THEBES-0", "seat_id": SEAT, "provider": provider, "session_id": sid,
            "worktree_path": "/wt", "branch": "platform-test", "execution_lease_id": "lease-platform-test",
            "invocation_id": "platform-test", "authorization_ref": "event/platform_test",
            "status": "dispatched", "outcome": None, "summary": None, "reference": None,
            "reported_session_id": None, "outcome_at": None, "recorded_by": None})

    def deliver(self, fake, **kw):
        did = kw.pop("dispatch_id", self.dispatch["dispatch_id"])
        return cd.deliver_session_dispatch(did, "DISPATCH hello", state_store=store,
                                           runner=fake, sleep=lambda s: None,
                                           pid_alive=lambda pid: False, **kw)

    # -- happy paths ----------------------------------------------------------
    def test_live_worker_is_stopped_by_short_id_then_resumed_flagless_by_full_sid(self):
        fake = FakeClaude([OTHER_ROW, LIVE_ROW])
        res = self.deliver(fake)
        self.assertEqual(res.status, cd.DELIVERED)
        self.assertEqual((res.stopped_before_resume, res.resumed_same_sid), ("YES", "YES"))
        self.assertEqual((res.pid_before, res.session_count_before, res.session_count_after), (68684, 2, 2))
        stop = [a for a in fake.calls if a[1] == "stop"]
        self.assertEqual(stop, [["claude", "stop", SID[:8]]], "stop takes the short id, exactly once")
        resume = [a for a in fake.calls if a[1] == "--bg"]
        self.assertEqual(len(resume), 1)
        self.assertEqual(resume[0][:4], ["claude", "--bg", "--resume", SID],
                         "flagless: no --model/--name/--permission-mode/--agent")
        self.assertTrue(resume[0][4].endswith("\n\nDISPATCH hello"), "envelope, then the body")
        rec = store.read("session_delivery", res.delivery_id)
        self.assertEqual((rec["status"], rec["transport"], rec["session_id"], rec["dispatch_id"]),
                         (cd.DELIVERED, "stop-then-bg-resume-same-sid", SID, self.dispatch["dispatch_id"]))
        self.assertTrue(rec["delivered_at"] and os.path.exists(rec["message_ref"]))
        self.assertNotIn("message", rec)
        self.assertEqual([e for e in validate.check(store.RUNTIME) if "deliver" in e], [])

    def test_delivered_message_starts_with_the_attestation_envelope(self):
        fake = FakeClaude([LIVE_ROW])
        res = self.deliver(fake, report_to="Persistent-session -a")
        sent = [a for a in fake.calls if a[1] == "--bg"][0][4]
        head, body = sent.split("\n\n", 1)
        lines = head.split("\n")
        self.assertEqual(lines[0], "THEBES_DELIVERY v2")
        self.assertEqual(lines[1], "task: THEBES-0")
        self.assertEqual(lines[2], "dispatch_id: %s" % self.dispatch["dispatch_id"])
        self.assertEqual(lines[3], "delivery_id: %s" % res.delivery_id)
        self.assertEqual(lines[4], "expected_worker_sid: %s" % SID)
        self.assertTrue(lines[5].startswith("transport: stop-then-bg-resume-same-sid"))
        self.assertIn("$CLAUDE_CODE_SESSION_ID == expected_worker_sid", lines[6])
        self.assertIn("ignore any session-<number> hook label", lines[6])
        # v2: the report line is ONE fully rendered Listener command, run from
        # stable_home; the worker never SendMessages a Primary.
        expected_cmd = ('cd %s && python3 -m agent.listener session-outcome THEBES-0 --dispatch %s '
                        '--delivery-id %s --outcome <completed|blocked|decision_required|'
                        'clarification_required|failed> --session-id "$CLAUDE_CODE_SESSION_ID" '
                        '--summary "<one line>" --reference <ref-or-none> --actor worker:po --wait 600'
                        % (HOME, self.dispatch["dispatch_id"], res.delivery_id))
        self.assertEqual(lines[7], "report: run exactly once when done: " + expected_cmd)
        self.assertTrue(lines[8].startswith("report_rules: "))
        self.assertIn("do not SendMessage a Primary", lines[8])
        self.assertEqual(lines[9], "dispatcher: Persistent-session -a (for context only; report "
                                   "through the command above)")
        self.assertEqual(body, "DISPATCH hello")
        rec = store.read("session_delivery", res.delivery_id)
        self.assertEqual((rec["envelope_version"], rec["expected_worker_sid"], rec["report_to"]),
                         ("v2", SID, "Persistent-session -a"))
        with open(rec["message_ref"], encoding="utf-8") as fh:
            self.assertEqual(fh.read(), sent, "message_ref holds exactly what was sent")

    def test_already_stopped_worker_is_resumed_without_a_stop(self):
        fake = FakeClaude([OTHER_ROW]); fake.completed = [dict(LIVE_ROW, status="exited")]
        res = self.deliver(fake)
        self.assertEqual((res.status, res.stopped_before_resume), (cd.DELIVERED, "NO"))
        self.assertNotIn("stop", fake.kinds())
        self.assertEqual(fake.kinds().count("resume"), 1)

    # -- identity ------------------------------------------------------------
    def test_session_mismatch_sends_nothing(self):
        other = self.make_dispatch(OTHER)
        fake = FakeClaude([LIVE_ROW])
        res = self.deliver(fake, dispatch_id=other["dispatch_id"])
        self.assertEqual(res.status, cd.MISMATCH)
        self.assertEqual(fake.calls, [])
        self.assertEqual(store.read("session_delivery", other["dispatch_id"])["status"], cd.MISMATCH)

    def test_display_name_match_with_a_different_sid_is_not_used(self):
        impostor = {"sessionId": OTHER, "id": OTHER[:8], "name": "thebes-po-c", "pid": 1}
        fake = FakeClaude([impostor]); fake.completed = []
        res = self.deliver(fake)
        self.assertEqual(res.status, cd.UNREACHABLE)
        self.assertNotIn("stop", fake.kinds()); self.assertNotIn("resume", fake.kinds())
        self.assertEqual(fake.live, [impostor], "nothing created, nothing stopped")

    def test_unreachable_is_deterministic_and_creates_nothing(self):
        fake = FakeClaude([OTHER_ROW]); fake.completed = []
        res = self.deliver(fake)
        self.assertEqual(res.status, cd.UNREACHABLE)
        self.assertEqual(fake.kinds(), ["agents", "agents"])
        rec = store.read("session_delivery", res.delivery_id)
        self.assertIn("never start a replacement", rec["recovery_hint"])

    # -- idempotency -----------------------------------------------------------
    def test_duplicate_delivery_replays_the_record_without_touching_the_cli(self):
        fake = FakeClaude([LIVE_ROW])
        first = self.deliver(fake)
        n = len(fake.calls)
        second = self.deliver(fake)
        self.assertEqual((second.status, second.idempotent_replay), (cd.DELIVERED, True))
        self.assertEqual(len(fake.calls), n, "runner not called on replay")
        self.assertEqual(second.pid_after, first.pid_after)
        self.assertEqual(store.read("session_delivery", first.delivery_id)["revision"], 1)

    def test_failed_delivery_may_be_retried_under_the_same_id_with_lineage(self):
        fake = FakeClaude([LIVE_ROW], resume_behaviour="fail")
        first = self.deliver(fake)
        self.assertEqual((first.status, first.stopped_before_resume), (cd.FAILED, "YES"))
        rec = store.read("session_delivery", first.delivery_id)
        self.assertIn(SID, rec["recovery_hint"], "recovery targets the SAME SID")
        fake.resume_behaviour = "same"                     # worker is now stopped
        second = self.deliver(fake)
        self.assertEqual((second.status, second.stopped_before_resume), (cd.DELIVERED, "NO"))
        rec2 = store.read("session_delivery", first.delivery_id)
        self.assertEqual((rec2["revision"], len(rec2["previous_attempts"]),
                          rec2["previous_attempts"][0]["status"]), (2, 1, cd.FAILED))
        self.assertRaises(store.StateError, store.record_session_delivery,
                          first.delivery_id, dict(rec2, status=cd.FAILED, error="x"))

    # -- copies and failures ---------------------------------------------------
    def test_a_copy_is_a_failure_and_the_copy_is_stopped(self):
        fake = FakeClaude([LIVE_ROW], resume_behaviour="copy")
        res = self.deliver(fake)
        self.assertEqual(res.status, cd.FAILED)
        self.assertIn("copy", res.error)
        self.assertEqual([a[2] for a in fake.calls if a[1] == "stop"], [SID[:8], OTHER[:8]],
                         "original stopped for delivery, then the copy this call created")
        self.assertFalse(any(r["sessionId"] == OTHER for r in fake.live))

    def test_resume_waits_for_the_old_process_to_exit_not_just_the_listing(self):
        """Regression for the live copy of 2026-09-28: the listing dropped the job
        while pid 24025 was still shutting down, the CLI judged the session
        'already running' and started a copy under a new id."""
        fake = FakeClaude([LIVE_ROW])
        alive = {"n": 3}                              # pid stays up for 3 checks

        def pid_alive(pid):
            self.assertEqual(pid, 68684)
            alive["n"] -= 1
            return alive["n"] > 0
        res = cd.deliver_session_dispatch(self.dispatch["dispatch_id"], "DISPATCH hello",
                                          state_store=store, runner=fake, sleep=lambda s: None,
                                          pid_alive=pid_alive)
        self.assertEqual(res.status, cd.DELIVERED)
        self.assertEqual(alive["n"], 0, "resume happened only after the pid was gone")
        self.assertGreaterEqual(fake.kinds().count("agents"), 4)
        rec = store.read("session_delivery", res.delivery_id)
        self.assertIn("woke session", rec["resume_output"], "resume output is durable evidence")

    def test_no_retry_inside_one_call(self):
        fake = FakeClaude([LIVE_ROW], resume_behaviour="fail")
        self.deliver(fake)
        self.assertEqual(fake.kinds().count("resume"), 1)
        self.assertEqual(fake.kinds().count("stop"), 1)

    def test_oversized_message_is_refused_not_truncated_or_rerouted(self):
        fake = FakeClaude([LIVE_ROW])
        res = cd.deliver_session_dispatch(self.dispatch["dispatch_id"], "x" * (cd.MAX_PROMPT_BYTES + 1),
                                          state_store=store, runner=fake)
        self.assertEqual(res.status, cd.FAILED); self.assertIn("argv", res.error)
        self.assertEqual(fake.calls, [])

    # -- CLI seam ----------------------------------------------------------------
    def test_find_by_sid_is_exact_and_never_by_name(self):
        rows = [{"sessionId": OTHER, "name": "thebes-po-c"}, {"sessionId": SID, "name": "renamed"}]
        self.assertEqual(ClaudeCli.find_by_sid(rows, SID)["name"], "renamed")
        self.assertIsNone(ClaudeCli.find_by_sid(rows, SID[:8]))

    def test_listing_parser_handles_real_shaped_output_and_garbage(self):
        """The shape `claude agents --json` printed on 2.1.283, fed through the
        seam without spawning the binary (tests never launch claude)."""
        real_shaped = json.dumps([{"pid": 68684, "id": "4d417564", "cwd": "/x", "kind": "background",
                                   "startedAt": 1790585563644, "sessionId": SID, "name": "thebes-po-c",
                                   "status": "idle", "state": "done"}])
        cli = ClaudeCli(runner=lambda argv, **kw: Completed(real_shaped))
        self.assertEqual(cli.find_by_sid(cli.agents(), SID)["id"], "4d417564")
        bad = ClaudeCli(runner=lambda argv, **kw: Completed("not json"))
        from agent.execution.claude_cli import ClaudeCliError
        self.assertRaises(ClaudeCliError, bad.agents)


if __name__ == "__main__":
    unittest.main()
