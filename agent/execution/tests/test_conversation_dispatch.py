#!/usr/bin/env python3
"""Codex conversation → persistent Claude session → the SAME Codex conversation.

Fakes only: a fake `claude` runner (agents / stop / --bg --resume) and a fake
shared-runtime client. No codex, no claude, no subprocess is started.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402
from agent.state import validate                                     # noqa: E402
from agent.execution import codex_runtime as cr                      # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution.claude_cli import ClaudeCli                     # noqa: E402

SID_X = "4d417564-5e86-4808-aacf-7158dcb65d59"      # seat po
SID_Y = "1b60d87b-8328-4ba0-a201-307b4945605d"      # seat frontend-1
UNBOUND = "22222222-2222-4222-8222-222222222222"
OPERATOR = "33333333-3333-4333-8333-333333333333"
THREAD_A = "0aaaaaaa-0000-7000-8000-00000000000a"
THREAD_B = "0bbbbbbb-0000-7000-8000-00000000000b"
UNREGISTERED = "01a0e382-98e9-70b2-84df-c757e3c6c517"
HOME = "/stable/home"
CAP = re.compile(r"%s=(\S+)" % cd.CAPABILITY_ENV)


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class Completed:
    def __init__(self, stdout="", stderr="", rc=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, rc


class FakeClaude:
    """`claude agents --json [--all]`, `stop <short>`, `--bg --resume <SID> <prompt>`."""

    def __init__(self, live=(), completed=(), resume_ok=True):
        self.live, self.completed = [dict(r) for r in live], [dict(r) for r in completed]
        self.calls, self.resume_ok = [], resume_ok

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        cmd = argv[1:]
        if cmd[:2] == ["agents", "--json"]:
            return Completed(json.dumps(self.live + (self.completed if "--all" in cmd else [])))
        if cmd[0] == "stop":
            self.completed += [r for r in self.live if r["id"] == cmd[1]]
            self.live = [r for r in self.live if r["id"] != cmd[1]]
            return Completed("stopped")
        if cmd[:2] == ["--bg", "--resume"]:
            if not self.resume_ok:
                return Completed("", "resume exploded", 1)
            self.live = [r for r in self.live if r["sessionId"] != cmd[2]]
            self.live.append(row(cmd[2], pid=9001))
            return Completed("backgrounded · %s" % cmd[2][:8])
        raise AssertionError("unexpected argv %r" % argv)

    def resumes(self):
        return [(a, kw) for a, kw in self.calls if a[1:3] == ["--bg", "--resume"]]

    def capability(self):
        return CAP.search(self.resumes()[-1][0][4]).group(1)


def row(sid, pid=None):
    return {"sessionId": sid, "id": sid[:8], "name": "worker", "pid": pid}


class FakeClient:
    log = []

    def __init__(self):
        pass

    def request(self, method, params, timeout=60):
        FakeClient.log.append((method, params))
        if method == "turn/start":
            return {"turn": {"id": "turn-%d" % sum(1 for m, _ in FakeClient.log
                                                   if m == "turn/start")}}
        return {}

    def await_turn(self, turn_id, timeout):
        return {"id": turn_id, "status": "completed"}, [{"text": "ACK %s" % turn_id}]

    def close(self):
        return 0


class ConversationDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("po", "claude", SID_X, HOME, "ceo")
        store.bind_role_session("frontend-1", "claude", SID_Y, HOME, "ceo")
        store.create("codex_runtime", {"runtime_id": cr.RUNTIME_ID, "status": "running",
                                       "socket_path": cr.socket_path(store)}, rid=cr.RUNTIME_ID)
        for t in (THREAD_A, THREAD_B):
            store.create("codex_conversation", {"thread_id": t, "runtime_id": cr.RUNTIME_ID,
                                                "registered_by": "ceo", "status": "active"}, rid=t)
        FakeClient.log = []
        self.launched = []
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        self.patches.append(mock.patch.object(cr, "_detach_drain", self.launched.append))
        self.patches.append(mock.patch.object(cr, "connect", lambda **kw: (FakeClient(), "m")))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def send(self, thread, sid, prompt="Summarize KAN-1 in one line.", fake=None):
        fake = fake or FakeClaude(live=[row(sid, pid=4242)])
        out = cd.dispatch(prompt, sid, env={"CODEX_THREAD_ID": thread}, state_store=store,
                          cli=ClaudeCli(runner=fake), stop_timeout_seconds=1)
        return out, fake

    def report(self, out, fake, outcome="completed", result="RESULT-TEXT", sid=None, cap=None):
        env = {"CLAUDE_CODE_SESSION_ID": sid or out["target_session_id"],
               cd.CAPABILITY_ENV: cap if cap is not None else fake.capability()}
        return cd.submit(out["dispatch_id"], outcome, result, env=env, state_store=store)

    def refused(self, fn, code):
        with self.assertRaises(cd.Refused) as cm:
            fn()
        self.assertEqual(cm.exception.code, code)

    def turn_starts(self):
        return [p for m, p in FakeClient.log if m == "turn/start"]

    def clean(self):
        return [e for e in validate.check(store.RUNTIME)
                if any(k in e for k in ("conversation", "session_deliver", "codex"))]

    # -- 1. dispatch ---------------------------------------------------------------
    def test_origin_comes_from_the_codex_env_and_the_prompt_reaches_exactly_that_sid(self):
        out, fake = self.send(THREAD_A, SID_X)
        self.assertEqual((out["status"], out["dispatch_status"], out["delivery_status"]),
                         ("dispatched", "delivered", "DELIVERED"))
        rec = store.read("conversation_dispatch", out["dispatch_id"])
        self.assertEqual({k: rec[k] for k in ("origin_provider", "origin_thread_id",
                                              "target_provider", "target_session_id",
                                              "target_seat_id", "delivery_id")},
                         {"origin_provider": "codex", "origin_thread_id": THREAD_A,
                          "target_provider": "claude", "target_session_id": SID_X,
                          "target_seat_id": "po", "delivery_id": out["dispatch_id"]})
        kinds = [a[1] for a, _ in fake.calls]
        self.assertEqual(kinds, ["agents", "stop", "agents", "--bg", "agents"],
                         "stop the live SID, then one flagless same-SID resume")
        (argv, kw), = fake.resumes()
        self.assertEqual((argv[:4], kw["cwd"]), (["claude", "--bg", "--resume", SID_X], HOME))
        sent = argv[4]
        self.assertTrue(sent.startswith("THEBES_CONVERSATION_DISPATCH"))
        self.assertTrue(sent.endswith("Summarize KAN-1 in one line."))
        self.assertIn("expected_worker_sid: %s" % SID_X, sent)
        cap = fake.capability()
        self.assertEqual(rec["capability_sha256"], hashlib.sha256(cap.encode()).hexdigest())
        self.assertNotIn(cap, json.dumps(out), "the dispatching Codex turn never sees it")
        for dirpath, _, files in os.walk(store.RUNTIME):
            for fn in files:
                with open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore") as fh:
                    self.assertNotIn(cap, fh.read(), "capability plaintext on disk: %s" % fn)
        delivery = store.read("session_delivery", out["dispatch_id"])
        with open(delivery["message_ref"], encoding="utf-8") as fh:
            self.assertIn(cd.REDACTED, fh.read())
        self.assertEqual(self.launched, [], "dispatch returns without waiting or draining")
        self.assertEqual(self.clean(), [])

    def test_fresh_managed_conversation_knows_route_and_receives_its_own_claude_result(self):
        thread_id = "0ccccccc-0000-7000-8000-00000000000c"
        runtime = store.read("codex_runtime", cr.RUNTIME_ID)
        store.update("codex_runtime", cr.RUNTIME_ID, runtime["revision"],
                     {"socket_path": cr.socket_path(store)})

        class Starts(FakeClient):
            def request(self, method, params, timeout=60):
                if method == "thread/start":
                    FakeClient.log.append((method, params))
                    return {"thread": {"id": thread_id}}
                return super().request(method, params, timeout)

            def await_turn(self, turn_id, timeout):
                if turn_id == "turn-1":
                    return {"id": turn_id, "status": "completed"}, [{
                        "text": "THEBES_BOOTSTRAP_READY %s" % thread_id}]
                return super().await_turn(turn_id, timeout)

        self.patches[-1].stop()
        try:
            with mock.patch.object(cr, "connect", lambda **kw: (Starts(), "gpt-6-astra")):
                created = cr.create_conversation("new-worker-route", "ceo", "Delegate a task",
                                                 state_store=store, route_ready=True)
        finally:
            self.patches[-1].start()
        self.assertTrue(created["status"]["MANAGED"])
        boot = self.turn_starts()[0]["input"][0]["text"]
        self.assertIn("python3 -m agent.listener conversation-dispatch", boot)
        self.assertIn("Do not poll", boot)
        self.assertIn(SID_X, boot)
        out, fake = self.send(thread_id, SID_X, prompt="Return NEW_THREAD_ONLY")
        reply = self.report(out, fake, result="NEW_THREAD_ONLY")
        self.assertEqual(reply["origin_reply"]["thread_id"], thread_id)
        cr.drain(thread_id, state_store=store)
        result_turn = self.turn_starts()[-1]
        self.assertEqual(result_turn["threadId"], thread_id)
        self.assertIn("NEW_THREAD_ONLY", result_turn["input"][0]["text"])
        self.assertEqual(store.read("codex_turn_event", reply["origin_reply"]["event_id"])
                         ["status"], "delivered")

    def test_detached_dispatch_returns_before_claude_delivery_then_child_delivers(self):
        spawned = []
        out = cd.dispatch("A's explicit task", SID_X, env={"CODEX_THREAD_ID": THREAD_A},
                          state_store=store, detach=True,
                          launcher=lambda did, cap: spawned.append((did, cap)))
        self.assertEqual(out["status"], "accepted")
        self.assertEqual(out["dispatch_status"], "delivering")
        self.assertEqual(len(spawned), 1)
        self.assertEqual(spawned[0][0], out["dispatch_id"])
        self.assertEqual(store.read_all("session_delivery"), [])
        self.refused(lambda: cd.deliver_pending(out["dispatch_id"], env={cd.CAPABILITY_ENV: "wrong"},
                                                state_store=store), "capability-invalid")
        fake = FakeClaude(live=[row(SID_X, pid=4242)])
        delivered = cd.deliver_pending(out["dispatch_id"],
                                        env={cd.CAPABILITY_ENV: spawned[0][1]},
                                        state_store=store, cli=ClaudeCli(runner=fake))
        self.assertEqual(delivered["delivery_status"], "DELIVERED")
        self.assertEqual(delivered["dispatch_status"], "delivered")
        self.assertIn("A's explicit task", fake.resumes()[0][0][4])

    def test_the_resumed_worker_does_not_inherit_the_dispatching_shell_identity(self):
        fake = FakeClaude(live=[row(SID_X, pid=1)])
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": THREAD_A,
                                          "CLAUDE_CODE_SESSION_ID": OPERATOR}):
            out = cd.dispatch("go", SID_X, state_store=store, runner=fake, stop_timeout_seconds=1)
        self.assertEqual(out["origin_thread_id"], THREAD_A)
        for _, kw in fake.calls:
            self.assertNotIn("CODEX_THREAD_ID", kw["env"])
            self.assertNotIn("CLAUDE_CODE_SESSION_ID", kw["env"])

    def test_dispatch_refusals_send_nothing(self):
        fake = FakeClaude(live=[row(SID_X)])
        go = lambda env, sid=SID_X, prompt="p": cd.dispatch(  # noqa: E731
            prompt, sid, env=env, state_store=store, cli=ClaudeCli(runner=fake))
        self.refused(lambda: go({}), "origin-thread-missing")
        self.refused(lambda: go({"CODEX_THREAD_ID": UNREGISTERED}), "thread-not-in-shared-runtime")
        self.refused(lambda: go({"CODEX_THREAD_ID": THREAD_A}, sid=UNBOUND),
                     "target-session-not-bound")
        self.refused(lambda: go({"CODEX_THREAD_ID": THREAD_A}, sid="thebes-po-c"),
                     "target-session-invalid")
        self.refused(lambda: go({"CODEX_THREAD_ID": THREAD_A}, prompt="  "), "prompt-required")
        rt = store.read("codex_runtime", cr.RUNTIME_ID)
        store.update("codex_runtime", cr.RUNTIME_ID, rt["revision"], {"status": "stopped"})
        self.refused(lambda: go({"CODEX_THREAD_ID": THREAD_A}), "codex-runtime-not-running")
        self.assertEqual((fake.calls, store.read_all("conversation_dispatch")), ([], []))
        with self.assertRaises(SystemExit):              # there is no origin flag to supply
            cd.main(["dispatch", "--to", SID_X, "--prompt", "p", "--origin-thread", THREAD_B])

    def test_an_exited_worker_is_resumed_in_place_and_a_missing_one_is_never_replaced(self):
        out, fake = self.send(THREAD_A, SID_X, fake=FakeClaude(completed=[row(SID_X)]))
        self.assertEqual(out["delivery_status"], "DELIVERED")
        self.assertNotIn("stop", [a[1] for a, _ in fake.calls], "not live: nothing to stop")
        self.assertEqual(fake.resumes()[0][0][3], SID_X)
        out2, fake2 = self.send(THREAD_B, SID_Y, fake=FakeClaude())
        self.assertEqual((out2["status"], out2["dispatch_status"], out2["delivery_status"]),
                         ("delivery-failed", "delivery_failed", "CLAUDE_DELIVERY_WORKER_UNREACHABLE"))
        self.assertEqual(fake2.resumes(), [], "no session is created in its place")
        self.assertEqual(self.clean(), [])

    def test_a_blocked_session_without_pid_is_resumed_without_stop(self):
        blocked = row(SID_X)
        blocked["state"] = "blocked"
        out, fake = self.send(THREAD_A, SID_X, fake=FakeClaude(live=[blocked]))
        self.assertEqual(out["delivery_status"], "DELIVERED")
        self.assertNotIn("stop", [a[1] for a, _ in fake.calls])
        self.assertEqual(fake.resumes()[0][0][3], SID_X)

    # -- 2. submit ------------------------------------------------------------------
    def test_submit_gates_then_exactly_one_explicit_result_turn_on_the_origin_thread(self):
        out, fake = self.send(THREAD_A, SID_X)
        self.refused(lambda: self.report(out, fake, cap="forged"), "capability-invalid")
        self.refused(lambda: self.report(out, fake, cap=""), "capability-invalid")
        self.refused(lambda: self.report(out, fake, sid=SID_Y), "session-identity-mismatch")
        self.assertEqual((store.read_all("codex_turn_event"), self.launched), ([], []))
        ok = self.report(out, fake, "decision_required", "Pick option B.\nReasons: …")
        self.assertEqual((ok["status"], ok["origin_reply"]["status"],
                          ok["origin_reply"]["thread_id"]), ("recorded", "scheduled", THREAD_A))
        again = self.report(out, fake, "decision_required", "Pick option B.\nReasons: …")
        self.assertEqual((again["status"], again["origin_reply"]["status"]),
                         ("already-recorded", "already-scheduled"))
        self.refused(lambda: self.report(out, fake, "completed", "different"),
                     "result-already-recorded")
        self.assertEqual(self.launched, [THREAD_A], "one detached drain, for the origin only")
        self.assertEqual(len(store.read_all("codex_turn_event")), 1)
        cr.drain(THREAD_A, state_store=store)
        cr.drain(THREAD_A, state_store=store)
        (start,) = self.turn_starts()
        self.assertEqual(start["threadId"], THREAD_A)
        text = start["input"][0]["text"]
        for line in ("THEBES_CONVERSATION_RESULT", "dispatch_id: %s" % out["dispatch_id"],
                     "worker_sid: %s" % SID_X, "outcome: decision_required",
                     "--- result ---\nPick option B.\nReasons: …\n--- end result ---"):
            self.assertIn(line, text)
        rec = store.read("conversation_dispatch", out["dispatch_id"])
        self.assertEqual((rec["status"], rec["result_event_id"], rec["attested_delivery_id"]),
                         ("decision_required", cd.result_event_id(out["dispatch_id"]),
                          out["dispatch_id"]))
        self.assertEqual(self.clean(), [])

    def test_an_undelivered_or_withdrawn_dispatch_accepts_no_result(self):
        out, fake = self.send(THREAD_A, SID_X, fake=FakeClaude(live=[row(SID_X)], resume_ok=False))
        self.assertEqual(out["dispatch_status"], "delivery_failed")
        self.refused(lambda: self.report(out, fake), "dispatch-not-open")
        out2, fake2 = self.send(THREAD_A, SID_Y)
        self.refused(lambda: cd.withdraw(out2["dispatch_id"], env={"CODEX_THREAD_ID": THREAD_B},
                                         state_store=store), "not-origin-thread")
        cd.withdraw(out2["dispatch_id"], env={"CODEX_THREAD_ID": THREAD_A}, state_store=store)
        self.refused(lambda: self.report(out2, fake2), "dispatch-not-open")
        self.assertEqual((store.read_all("codex_turn_event"), self.launched), ([], []))

    def test_a_delivered_attestation_is_required_even_with_the_right_capability(self):
        out, fake = self.send(THREAD_A, SID_X)
        path = store.path_for("session_delivery", out["dispatch_id"])
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["status"] = "CLAUDE_DELIVERY_FAILED"; rec["error"] = "tampered"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        self.refused(lambda: self.report(out, fake), "outcome-delivery-unattested")

    # -- 3. busy target, A/B routing, per-thread serialization --------------------------
    def test_a_busy_target_is_refused_rather_than_interrupted(self):
        out, fake = self.send(THREAD_A, SID_X)
        self.refused(lambda: self.send(THREAD_B, SID_X), "target-session-busy")
        self.report(out, fake)
        self.assertEqual(self.send(THREAD_B, SID_X)[0]["status"], "dispatched")
        store.create("session_dispatch", {
            "work_item_id": "KAN-9", "seat_id": "frontend-1", "provider": "claude",
            "session_id": SID_Y, "worktree_path": "/wt", "branch": "b",
            "execution_lease_id": "lease-x", "invocation_id": "i", "authorization_ref": "a",
            "status": "dispatched"})
        self.refused(lambda: self.send(THREAD_A, SID_Y), "target-session-busy")

    def test_a_and_b_each_get_their_own_result_and_b_runs_while_a_is_busy(self):
        a, fa = self.send(THREAD_A, SID_X, prompt="task for A")
        b, fb = self.send(THREAD_B, SID_Y, prompt="task for B")
        self.report(a, fa, result="answer A")
        self.report(b, fb, result="answer B")
        self.assertEqual(sorted(self.launched), sorted([THREAD_A, THREAD_B]))
        with store.thread_writer(THREAD_A):                 # A is mid-turn elsewhere
            self.assertEqual(cr.drain(THREAD_A, state_store=store)["status"], "held")
            rb = cr.drain(THREAD_B, state_store=store)
            self.assertEqual((rb["status"], len(rb["delivered"])), ("drained", 1))
        self.assertEqual(cr.drain(THREAD_A, state_store=store)["status"], "drained")
        starts = self.turn_starts()
        self.assertEqual([s["threadId"] for s in starts], [THREAD_B, THREAD_A])
        self.assertIn("answer B", starts[0]["input"][0]["text"])
        self.assertIn(b["dispatch_id"], starts[0]["input"][0]["text"])
        self.assertIn("answer A", starts[1]["input"][0]["text"])
        self.assertNotIn("answer B", starts[1]["input"][0]["text"])
        self.assertEqual(self.clean(), [])

    # -- 4. queue races ----------------------------------------------------------------
    def test_queued_turns_keep_fifo_order_inside_one_second(self):
        with mock.patch.object(store, "now", lambda: "2026-09-30T12:00:00Z"):
            for i in range(8):
                cr.enqueue(THREAD_A, "user_prompt", "msg-%d" % i, state_store=store)
        cr.drain(THREAD_A, state_store=store)
        self.assertEqual([s["input"][0]["text"] for s in self.turn_starts()],
                         ["msg-%d" % i for i in range(8)])

    def test_concurrent_duplicate_enqueues_keep_the_winners_text(self):
        for round_ in range(5):
            eid, barrier, results = "cevt-race-%d" % round_, threading.Barrier(6), []

            def go(i):
                barrier.wait()
                results.append(("text-%d" % i,) + cr.enqueue(
                    THREAD_B, "user_prompt", "text-%d" % i, event_id=eid, state_store=store))
            threads = [threading.Thread(target=go, args=(i,)) for i in range(6)]
            for t in threads: t.start()
            for t in threads: t.join(5)
            winners = [text for text, _, created in results if created]
            self.assertEqual(len(winners), 1)
            with open(store.read("codex_turn_event", eid)["text_ref"], encoding="utf-8") as fh:
                self.assertEqual(fh.read(), winners[0])


if __name__ == "__main__":
    unittest.main()
