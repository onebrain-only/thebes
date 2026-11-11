#!/usr/bin/env python3
"""Claude-only Thebes (D-039): orchestrator → team → the orchestrator's inbox.

Fakes only. No codex, no claude, no subprocess, no network.
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
from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution import decision_gate as dg                      # noqa: E402
from agent.execution import inbox                                    # noqa: E402

ORCH = "0eeeeeee-3333-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-3333-7000-8000-00000000000a"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        live = dg.config()
        self.launched, self.resumed = [], []
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        self.patches.append(mock.patch.object(
            dg, "config", lambda path=dg.CONFIG_PATH: dict(live, gate="fake")))
        self.patches.append(mock.patch.object(
            dg.urllib.request, "urlopen",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in tests"))))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- fixtures --------------------------------------------------------------
    def dispatched(self, prompt="count the Dart files"):
        out = cd.dispatch(prompt, KARNAK, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                          detach=True, launcher=lambda did, cap: self.launched.append((did, cap)))
        did, cap = self.launched[-1]
        rec = store.read("conversation_dispatch", did)
        store.update("conversation_dispatch", did, rec["revision"],
                     {"status": "delivered", "delivery_status": "DELIVERED"})
        store.record_session_delivery(did, {
            "dispatch_id": did, "work_item_id": None, "seat_id": "karnak", "provider": "claude",
            "session_id": KARNAK, "status": "DELIVERED", "stopped_before_resume": "YES",
            "resumed_same_sid": "YES", "session_count_before": 1, "session_count_after": 1,
            "delivered_at": store.now()})
        return out, did, cap

    def submit(self, did, cap, outcome, text):
        return cd.submit(did, outcome, text, env={"CLAUDE_CODE_SESSION_ID": KARNAK,
                                                  cd.CAPABILITY_ENV: cap}, state_store=store)

    def waited(self):
        return inbox.wait(1, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                          sleep=lambda s: None)

    def clean(self):
        return [e for e in validate.check(store.RUNTIME)
                if any(k in e for k in ("decision", "conversation", "role session"))]

    # -- tests -----------------------------------------------------------------
    def test_the_orchestrator_dispatches_as_itself_and_nobody_else_can(self):
        out, did, _ = self.dispatched()
        self.assertEqual(out["status"], "accepted")
        self.assertIn("inbox", out["next"])
        rec = store.read("conversation_dispatch", did)
        self.assertEqual((rec["origin_provider"], rec["origin_thread_id"]), ("claude", ORCH))
        with self.assertRaises(cd.Refused) as ctx:
            cd.dispatch("x", ORCH, env={"CLAUDE_CODE_SESSION_ID": KARNAK}, state_store=store,
                        detach=True, launcher=lambda *a: None)
        self.assertEqual(ctx.exception.code, "origin-not-orchestrator")
        self.assertEqual(self.clean(), [])

    def test_a_team_result_reaches_the_inbox_once_and_never_a_codex_turn(self):
        _, did, cap = self.dispatched()
        self.assertEqual(self.waited()["status"], "idle")
        reply = self.submit(did, cap, "completed", "728 Dart files")
        self.assertEqual(reply["origin_reply"]["status"], "inline")
        self.assertEqual(store.read_all("codex_turn_event"), [])
        got = self.waited()
        self.assertEqual(got["status"], "items")
        self.assertEqual([(i["kind"], i["outcome"], i["result"]) for i in got["items"]],
                         [("result", "completed", "728 Dart files")])
        self.assertEqual(self.waited()["status"], "idle", "collected exactly once")
        self.assertEqual(self.clean(), [])

    def test_a_wake_with_nothing_new_tells_the_orchestrator_to_write_nothing(self):
        # CEO 2026-11-11: idle and restart wakes used to end with a line to him every time.
        self.assertIn("single character ·", self.waited()["next"])
        _, did, cap = self.dispatched()
        self.submit(did, cap, "completed", "done")
        got = self.waited()
        self.assertEqual(got["status"], "items")
        self.assertIn("ceo_notice prints SEND", got["next"])

    def test_results_a_minute_apart_reach_the_orchestrator_in_one_wake(self):
        # CEO 2026-11-11: every wake re-reads the orchestrator's whole context.
        _, d1, c1 = self.dispatched("one")
        self.submit(d1, c1, "completed", "first")

        def second():
            _, d2, c2 = self.dispatched("two")
            self.submit(d2, c2, "completed", "second")
        later = [second]
        got = inbox.wait(1, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                         sleep=lambda s: later and later.pop()())
        self.assertEqual(sorted(i["result"] for i in got["items"]), ["first", "second"])
        self.assertEqual(self.waited()["status"], "idle")

    def test_a_code_change_reloads_the_waiter_in_place_without_a_wake(self):
        stamps = iter([("a",), ("b",)])
        reloaded = []
        with mock.patch.object(inbox, "_code_stamp", lambda: next(stamps)):
            inbox.wait(60, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                       sleep=lambda s: None, reexec=reloaded.append)
        self.assertEqual(len(reloaded), 1, "the waiter replaced itself on the new code")
        self.assertLessEqual(reloaded[0], 60, "and keeps only the time left")

    # -- the pusher (CEO 2026-11-11: "no wake-ups at all") -----------------------
    def pusher(self, sent):
        from agent.execution import inbox_push
        self.clock = [1000.0]
        return inbox_push.Pusher(state_store=store, clock=lambda: self.clock[0],
                                 deliver=lambda sid, text: sent.append((sid, text)) or True)

    def test_waiting_work_is_pushed_into_the_orchestrator_once_after_the_batch_settles(self):
        sent = []
        p = self.pusher(sent)
        self.assertIsNone(p.step(), "nothing waiting, nothing sent")
        _, did, cap = self.dispatched()
        self.submit(did, cap, "completed", "728 Dart files")
        self.assertIsNone(p.step(), "the first item opens a batch")
        self.clock[0] += 91
        self.assertEqual(p.step()["action"], "pushed")
        self.assertEqual(len(sent), 1)
        sid, text = sent[0]
        self.assertEqual(sid, ORCH)
        self.assertIn("inbox take", text)
        self.assertIn("Start no inbox waiter", text)
        self.assertNotIn("728 Dart files", text, "the line carries no item")
        self.clock[0] += 600
        self.assertIsNone(p.step(), "an announced set is not announced again")
        got = inbox.take(env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store)
        self.assertEqual([i["result"] for i in got["items"]], ["728 Dart files"])
        self.assertIn("Start no inbox waiter", got["next"])
        self.assertEqual(inbox.take(env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                    state_store=store)["status"], "empty")
        self.assertIsNone(p.step())
        self.assertEqual(len(sent), 1)

    def test_a_failed_push_is_retried_and_an_untaken_set_is_announced_again_after_an_hour(self):
        attempts = []
        from agent.execution import inbox_push
        clock = [0.0]
        p = inbox_push.Pusher(state_store=store, clock=lambda: clock[0],
                              deliver=lambda sid, text: attempts.append(clock[0]) or
                              len(attempts) > 1)
        _, did, cap = self.dispatched()
        self.submit(did, cap, "completed", "done")
        p.step(); clock[0] += 91
        self.assertEqual(p.step()["action"], "push-failed")
        clock[0] += 10
        self.assertIsNone(p.step(), "no retry inside a minute")
        clock[0] += 60
        self.assertEqual(p.step()["action"], "pushed")
        clock[0] += inbox_push.RESEND_SECONDS
        self.assertEqual(p.step(), {"action": "pushed", "count": 1, "resend": True})

    def test_only_the_orchestrator_takes_and_the_waiter_steps_aside_for_the_pusher(self):
        with self.assertRaises(inbox.Refused):
            inbox.take(env={"CLAUDE_CODE_SESSION_ID": KARNAK}, state_store=store)
        import fcntl
        os.makedirs(store.RUNTIME, exist_ok=True)
        with open(os.path.join(store.RUNTIME, inbox.PUSH_LOCK), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            got = self.waited()
        self.assertEqual(got["status"], "pushed")
        self.assertIn("never start the inbox waiter again", got["next"])
        self.assertEqual(self.waited()["status"], "idle", "no pusher, the waiter works")

    def test_only_the_orchestrator_reads_its_inbox(self):
        with self.assertRaises(inbox.Refused) as ctx:
            inbox.wait(1, env={"CLAUDE_CODE_SESSION_ID": KARNAK}, state_store=store)
        self.assertEqual(ctx.exception.code, "not-orchestrator")

    def test_a_team_question_waits_in_the_inbox_and_the_answer_resumes_the_team(self):
        _, did, cap = self.dispatched()
        out = self.submit(did, cap, "decision_required", "Which acceptance criteria apply to KAN-9?")
        self.assertEqual(out["decision"]["route"], "owner")
        # Nothing was stopped or resumed: no process at all (subprocess is refused).
        got = self.waited()
        kinds = [i["kind"] for i in got["items"]]
        self.assertEqual(kinds, ["decision"], "the routed question is not also a result")
        env_text = got["items"][0]["envelope"]
        self.assertIn("you_are: the Thebes ORCHESTRATOR", env_text)
        dcap = env_text.split("%s=" % dg.CAPABILITY_ENV, 1)[1].split()[0]
        rid = got["items"][0]["decision_request_id"]
        captured = {}

        def fake_dispatch(text, target, env, state_store, detach, **kw):
            captured.update(env=env, target=target)
            return {"dispatch_id": "cdispatch-cont", "status": "accepted"}
        with mock.patch.object(cd, "dispatch", fake_dispatch):
            ans = dg.answer(rid, "Use AC3.", env={"CLAUDE_CODE_SESSION_ID": ORCH,
                                                  dg.CAPABILITY_ENV: dcap}, state_store=store)
        self.assertEqual(ans["status"], "answered")
        self.assertEqual(captured["target"], KARNAK)
        self.assertEqual(captured["env"].get(cd.CLAUDE_ORIGIN_ENV), ORCH)
        self.assertNotIn("CODEX_THREAD_ID", captured["env"])
        self.assertEqual(self.clean(), [])

    def test_a_requeued_question_is_handed_over_again_with_a_fresh_capability(self):
        _, did, cap = self.dispatched()
        self.submit(did, cap, "decision_required", "Which acceptance criteria apply to KAN-9?")
        first = self.waited()["items"][0]
        self.assertEqual(dg.redeliver(first["decision_request_id"], state_store=store)["status"],
                         "requeued-to-inbox")
        second = self.waited()["items"][0]
        self.assertNotEqual(first["envelope"], second["envelope"])

    def test_the_orchestrator_holds_a_seat_for_a_ceo_order_and_no_team_can(self):
        from agent.execution import team_pool as tp
        out = tp.reserve("po", "ceo-kan-348-ready", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                         state_store=store)
        self.assertEqual((out["status"], out["team_id"]), ("reserved", "orchestrator"))
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("po-2", "ceo-x", env={"CLAUDE_CODE_SESSION_ID": KARNAK}, state_store=store)
        self.assertEqual(ctx.exception.code, "orchestrator-only-seat",
                         "D-042: a team never reserves a PO, whatever the work id")
        self.assertEqual(tp.release("po", "ceo-kan-348-ready", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                    state_store=store)["status"], "released")
        self.assertEqual(self.clean(), [])

    def test_a_watchdog_alert_reaches_the_inbox(self):
        from agent.execution import watchdog
        _, did, _ = self.dispatched()
        rec = store.read("conversation_dispatch", did)
        self.assertTrue(watchdog._alert(rec, "stalled", "Karnak stopped", state_store=store,
                                        launcher=_refuse))
        got = self.waited()
        self.assertEqual([(i["kind"], i["alert"]) for i in got["items"]], [("alert", "stalled")])


if __name__ == "__main__":
    unittest.main()
