#!/usr/bin/env python3
"""The user's Primary front door (PRIMARY_COMMAND). Fakes only — no codex,
no claude, no subprocess, no Listener process is started here.
"""
import os
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
from agent.execution import primary_command as pc                    # noqa: E402
from agent.execution import primary_notify as pn                     # noqa: E402
from agent.execution.codex_primary import WakeResult                 # noqa: E402
from agent.listener import contract, dispatch as ldispatch           # noqa: E402
from agent.controller.entry import ORCHESTRATING_COMMANDS            # noqa: E402

CODEX = "01a0e382-98e9-70b2-84df-c757e3c6c517"
CLAUDE_A = "9dd2598a-556e-402c-b452-29a5456794d6"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class FakeWaker:
    def __init__(self, status="delivered", gate=None):
        self.calls, self.status, self.gate = [], status, gate

    def __call__(self, event_kind, text, *, binding, state_store, timeout_seconds=300):
        self.calls.append((event_kind, text, binding["session_ref"]))
        if self.gate:
            self.gate["entered"].set(); self.gate["release"].wait(5)
        ok = self.status == "delivered"
        return WakeResult(self.status, None if ok else "CODEX_PRIMARY_THREAD_BUSY",
                          None if ok else "thread already has an active writer",
                          thread_id=binding["session_ref"], turn_id="turn-7" if ok else None,
                          model="gpt-6-astra", response_summary="ACK from Primary" if ok else None,
                          wake_record_id="pwake-cmd")


class PrimaryCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_primary("claude", CLAUDE_A, "STANDBY", "ceo", "ref:t", HOME)
        store.set_primary_active("claude", "ceo", "ref:t")
        store.bind_primary("codex", CODEX, "STANDBY", "ceo", "ref:t", HOME)
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def codex_active(self):
        store.set_primary_active("codex", "ceo", "ref:cutover-fixture")

    # -- one command, one turn on the SAME bound thread, durable record ------
    def test_codex_active_command_runs_one_turn_on_the_bound_thread_and_records_the_reply(self):
        self.codex_active(); w = FakeWaker()
        rec = pc.run_primary_command("What is pending?", "ceo", state_store=store, codex_waker=w)
        self.assertEqual(w.calls, [("user_command", "What is pending?", CODEX)])
        self.assertEqual((rec["status"], rec["provider"], rec["session_ref"], rec["generation"],
                          rec["turn_ref"], rec["response_summary"], rec["wake_record_id"]),
                         ("delivered", "codex", CODEX, 2, "turn-7", "ACK from Primary", "pwake-cmd"))
        with open(rec["text_ref"], encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "What is pending?")
        self.assertNotIn("text", rec)
        self.assertEqual([e for e in validate.check(store.RUNTIME) if "primary" in e], [])

    def test_a_desktop_held_thread_is_busy_not_delivered(self):
        self.codex_active()
        rec = pc.run_primary_command("hello", "ceo", state_store=store, codex_waker=FakeWaker("busy"))
        self.assertEqual((rec["status"], rec["error"]["code"], rec["turn_ref"]),
                         ("busy", "CODEX_PRIMARY_THREAD_BUSY", None))

    # -- Claude ACTIVE routing preserved: nothing sent, structured refusal ------
    def test_claude_active_is_refused_and_codex_is_never_touched(self):
        rec = pc.run_primary_command("hello", "ceo", state_store=store, codex_waker=_refuse)
        self.assertEqual((rec["status"], rec["provider"], rec["error"]["code"]),
                         ("refused", "claude", "primary-command-claude-direct"))

    def test_empty_or_oversized_text_is_refused_before_any_wake(self):
        self.codex_active()
        for text in ("   ", "x" * (pc.MAX_TEXT_BYTES + 1)):
            rec = pc.run_primary_command(text, "ceo", state_store=store, codex_waker=_refuse)
            self.assertEqual(rec["error"]["code"], "primary-command-text-invalid")

    # -- one Thebes writer: concurrent command / notification refused, not queued --
    def test_a_concurrent_writer_is_refused_at_once_and_never_waits(self):
        self.codex_active()
        gate = {"entered": threading.Event(), "release": threading.Event()}
        first = {}
        t = threading.Thread(target=lambda: first.update(rec=pc.run_primary_command(
            "first", "ceo", state_store=store, codex_waker=FakeWaker(gate=gate))))
        t.start(); self.assertTrue(gate["entered"].wait(5))
        try:
            second = pc.run_primary_command("second", "ceo", state_store=store, codex_waker=_refuse)
            self.assertEqual(second["status"], "queued", "a concurrent command is queued, never waited on")
            # a worker-outcome notification converges on the SAME writer and is refused too
            n, _ = store.create_primary_notification("dispatch-fixture-1", {
                "work_item_id": "KAN-369", "seat_id": "frontend-2",
                "worker_session_id": "7263350b-8d19-4555-bca2-9d1132ec6ffe",
                "delivery_id": "dispatch-fixture-1", "outcome": "completed", "reference": "d043ac8",
                "summary_ref": "done"})
            res = pn.deliver("dispatch-fixture-1", state_store=store, codex_waker=_refuse)
            self.assertEqual((res["status"], res["error"]["code"]), ("busy", "PRIMARY_WRITER_BUSY"))
            self.assertEqual(store.read("primary_notification", "dispatch-fixture-1")["status"], "busy")
        finally:
            gate["release"].set(); t.join(5)
        self.assertEqual(first["rec"]["status"], "delivered")
        # The first writer drained on release, in order, through the SAME waker it held:
        # the queued command, then the kept notification. Nothing polled.
        self.assertEqual(store.read("primary_command", second["primary_command_id"])["status"], "delivered")
        n = store.read("primary_notification", "dispatch-fixture-1")
        self.assertEqual((n["status"], n["notified_provider"]), ("delivered", "codex"))
        w = FakeWaker()
        self.assertEqual(pn.deliver("dispatch-fixture-1", state_store=store, codex_waker=w).get("already"),
                         True)
        self.assertEqual(w.calls, [], "a delivered notification is never sent twice")

    def test_a_delivered_turn_drains_a_desktop_busy_notification_and_stops_at_external_busy(self):
        """The KAN-369 shape: a notification kept busy because Desktop held the
        thread. The next Thebes turn that is delivered proves the thread free and
        drains it; if the thread is held again, the drain stops without looping."""
        self.codex_active()
        for i in (1, 2):
            store.create_primary_notification("dispatch-kept-%d" % i, {
                "work_item_id": "KAN-369", "seat_id": "frontend-2",
                "worker_session_id": "7263350b-8d19-4555-bca2-9d1132ec6ffe",
                "delivery_id": "dispatch-kept-%d" % i, "outcome": "completed",
                "reference": "d043ac8", "summary_ref": "done"})
            store.settle_primary_notification("dispatch-kept-%d" % i, "busy", provider="codex",
                                              error={"code": "CODEX_PRIMARY_THREAD_BUSY", "message": "x"})

        class OneThenBusy(FakeWaker):
            def __call__(self, *a, **k):
                res = super().__call__(*a, **k)
                self.status = "busy"
                return res

        w = OneThenBusy()
        pc.run_primary_command("status?", "ceo", state_store=store, codex_waker=w)
        self.assertEqual(len(w.calls), 2, "the command, then one drain attempt that met busy, then stop")
        self.assertEqual([store.read("primary_notification", "dispatch-kept-%d" % i)["status"] for i in (1, 2)],
                         ["busy", "busy"])
        w2 = FakeWaker()
        pc.run_primary_command("again", "ceo", state_store=store, codex_waker=w2)
        self.assertEqual([c[0] for c in w2.calls], ["user_command", "worker_outcome", "worker_outcome"])
        self.assertEqual([store.read("primary_notification", "dispatch-kept-%d" % i)["status"] for i in (1, 2)],
                         ["delivered", "delivered"])

    # -- Listener contract / transport ----------------------------------------
    def test_contract_accepts_a_user_command_and_refuses_a_worker(self):
        base = {"schema_version": 1, "source": "listener-cli", "idempotency_key": "k",
                "correlation_id": "k", "intent_type": contract.PRIMARY_COMMAND}
        ok = contract.normalize(dict(base, actor="ceo", payload={"text": "What is pending?"}))
        self.assertEqual(ok["payload"], {"text": "What is pending?"})
        argv = ldispatch.argv_for(ok)
        self.assertEqual(argv[1:5], ["-m", "agent.controller", "primary-command", "--submitted-by"])
        self.assertEqual(argv[5], "ceo")
        self.assertTrue(argv[7].startswith("pcmd-"))
        self.assertEqual(argv[-2:], ["--text", "What is pending?"])
        with self.assertRaises(contract.IntentRejected) as cm:
            contract.normalize(dict(base, actor="worker:po", payload={"text": "dispatch more"}))
        self.assertEqual(cm.exception.reason, "actor-not-permitted")
        for bad in ({"text": ""}, {"text": "a\x1bb"}, {"text": "x", "work_item_id": "KAN-1"}, {}):
            with self.assertRaises(contract.IntentRejected):
                contract.normalize(dict(base, actor="ceo", payload=bad))
        self.assertIn("primary-command", ORCHESTRATING_COMMANDS,
                      "direct controller entry is refused; the Listener is the front door")


if __name__ == "__main__":
    unittest.main()
