#!/usr/bin/env python3
"""Shared Codex app-server runtime and dispatch-origin reply routing.

Fakes only: no codex, no claude, no subprocess is started. The WebSocket
framing is exercised over a real socketpair.
"""
import json
import os
import shutil
import socket
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
from agent.execution import codex_ws                                 # noqa: E402
from agent.execution.claude_delivery import build_envelope           # noqa: E402
from agent.controller import session_dispatch as sd                  # noqa: E402
from agent.listener import contract, dispatch as ldispatch           # noqa: E402

SEAT = "po"
SID = "4d417564-5e86-4808-aacf-7158dcb65d59"
OTHER = "11111111-1111-4111-8111-111111111111"
THREAD_A = "0aaaaaaa-0000-7000-8000-00000000000a"
THREAD_B = "0bbbbbbb-0000-7000-8000-00000000000b"
DESKTOP = "01a0e382-98e9-70b2-84df-c757e3c6c517"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class FakeClient:
    """One shared-runtime connection. Records every JSON-RPC call."""
    log = []

    def __init__(self, gate=None):
        self.gate = gate

    def request(self, method, params, timeout=60):
        FakeClient.log.append((method, params))
        if method == "turn/start":
            n = sum(1 for m, _ in FakeClient.log if m == "turn/start")
            return {"turn": {"id": "turn-%d" % n}}
        return {}

    def await_turn(self, turn_id, timeout):
        if self.gate:
            self.gate["entered"].set(); self.gate["release"].wait(5)
        return {"id": turn_id, "status": "completed"}, [{"type": "agentMessage",
                                                         "text": "ACK %s" % turn_id}]

    def close(self):
        return 0


class CodexRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session(SEAT, "claude", SID, HOME, "ceo", session_name="thebes-po-c")
        for t in (THREAD_A, THREAD_B):
            store.create("codex_conversation", {"thread_id": t, "runtime_id": "shared",
                                                "label": t[:9], "registered_by": "ceo",
                                                "status": "active"}, rid=t)
        FakeClient.log = []
        self.launched = []
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        self.patches.append(mock.patch.object(cr, "_detach_drain", self.launched.append))
        self.patches.append(mock.patch.object(cr, "connect",
                                              lambda **kw: (self.client(), "gpt-6-astra")))
        self.gate = None
        for p in self.patches: p.start()
        self.n = 0

    def client(self):
        return FakeClient(self.gate)

    def tearDown(self):
        for p in self.patches: p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dispatch(self, origin, sid=SID, delivered=True):
        self.n += 1
        item = "KAN-%d" % (970 + self.n)
        did = store.new_id("session_dispatch")
        d = store.create("session_dispatch", {
            "work_item_id": item, "seat_id": SEAT, "provider": "claude", "session_id": sid,
            "worktree_path": "/wt", "branch": "exec/po/%s" % item, "execution_lease_id": "lease-x",
            "invocation_id": "fixture", "authorization_ref": "authz:fixture", "status": "dispatched",
            "outcome": None, "summary": None, "reference": None, "reported_session_id": None,
            "outcome_at": None, "recorded_by": None, "origin_provider": "codex",
            "origin_thread_id": origin, "reply_to_thread_id": origin, "target_provider": "claude",
            "target_session_id": sid, "delivery_id": did}, rid=did)
        if delivered:
            store.record_session_delivery(did, {
                "dispatch_id": did, "work_item_id": item, "seat_id": SEAT, "provider": "claude",
                "session_id": sid, "status": "DELIVERED", "stopped_before_resume": "YES",
                "resumed_same_sid": "YES", "session_count_before": 1, "session_count_after": 1,
                "delivered_at": store.now()})
        return d

    def outcome(self, d, outcome="completed", sid=SID, delivery_id=None):
        return sd.session_outcome(d["work_item_id"], d["dispatch_id"], outcome, sid,
                                  "done: %s" % outcome, "abc1234",
                                  delivery_id=delivery_id or d["dispatch_id"], state_store=store)

    def turn_starts(self):
        return [p for m, p in FakeClient.log if m == "turn/start"]

    # -- A/B exact routing ----------------------------------------------------
    def test_each_outcome_wakes_exactly_the_conversation_that_dispatched_it(self):
        a, b = self.dispatch(THREAD_A), self.dispatch(THREAD_B)
        ra, rb = self.outcome(a), self.outcome(b, "blocked")
        self.assertEqual((ra["origin_reply"]["thread_id"], rb["origin_reply"]["thread_id"]),
                         (THREAD_A, THREAD_B))
        self.assertIsNone(ra["primary_notify"], "never the global Primary path")
        self.assertEqual(sorted(self.launched), sorted([THREAD_A, THREAD_B]))
        self.assertEqual(store.read_all("primary_notification"), [])
        cr.drain(THREAD_B, state_store=store)
        cr.drain(THREAD_A, state_store=store)
        starts = self.turn_starts()
        self.assertEqual([s["threadId"] for s in starts], [THREAD_B, THREAD_A])
        self.assertIn("dispatch_id: %s" % b["dispatch_id"], starts[0]["input"][0]["text"])
        self.assertIn("dispatch_id: %s" % a["dispatch_id"], starts[1]["input"][0]["text"])
        resumes = [p["threadId"] for m, p in FakeClient.log if m == "thread/resume"]
        self.assertEqual(resumes, [THREAD_B, THREAD_A])
        self.assertNotIn(DESKTOP, json.dumps(FakeClient.log))
        for d in (a, b):
            ev = store.read("codex_turn_event", cr.result_event_id(d["dispatch_id"]))
            self.assertEqual(ev["status"], "delivered"); self.assertTrue(ev["turn_ref"])
        self.assertEqual([e for e in validate.check(store.RUNTIME) if "codex" in e], [])

    # -- explicit result prompt ------------------------------------------------
    def test_the_result_turn_input_is_the_explicit_worker_result_prompt(self):
        d = self.dispatch(THREAD_A); self.outcome(d, "decision_required")
        cr.drain(THREAD_A, state_store=store)
        (start,) = self.turn_starts()
        text = start["input"][0]["text"]
        self.assertEqual(start["input"], [{"type": "text", "text": text}])
        for line in ("THEBES_WORKER_RESULT", "task: %s" % d["work_item_id"],
                     "dispatch_id: %s" % d["dispatch_id"], "delivery_id: %s" % d["dispatch_id"],
                     "worker_seat: po", "worker_sid: %s" % SID, "outcome: decision_required",
                     "reference: abc1234", "summary: done: decision_required", "next: Route the decision"):
            self.assertIn(line, text)

    # -- wrong SID / invalid delivery → no event, no turn -----------------------
    def test_wrong_sid_or_unattested_delivery_creates_no_result_turn(self):
        d = self.dispatch(THREAD_A)
        r1 = self.outcome(d, sid=OTHER)
        r2 = self.outcome(d, delivery_id="delivery-nope")
        d2 = self.dispatch(THREAD_A, delivered=False)
        r3 = self.outcome(d2)
        for r in (r1, r2, r3):
            self.assertEqual(r["outcome_status"], "not-recorded")
            self.assertNotIn("origin_reply", r)
        self.assertEqual(store.read_all("codex_turn_event"), [])
        self.assertEqual(self.launched, [])

    # -- duplicates -------------------------------------------------------------
    def test_a_repeated_outcome_yields_no_second_result_turn(self):
        d = self.dispatch(THREAD_A)
        self.outcome(d)
        again = self.outcome(d)
        self.assertEqual(again["outcome_status"], "not-recorded")
        settled = store.read("session_dispatch", d["dispatch_id"])
        self.assertEqual(cr.schedule_worker_result(settled, state_store=store, launcher=_refuse)["status"],
                         "already-scheduled")
        cr.drain(THREAD_A, state_store=store); cr.drain(THREAD_A, state_store=store)
        self.assertEqual(len(self.turn_starts()), 1)
        self.assertEqual(len(store.read_all("codex_turn_event")), 1)

    # -- per-thread serialization ---------------------------------------------
    def test_threads_run_concurrently_and_a_busy_thread_queues_then_drains_on_release(self):
        gate_a = {"entered": threading.Event(), "release": threading.Event()}
        self.gate = gate_a                                    # A's client blocks mid-turn
        cr.enqueue(THREAD_A, "user_prompt", "first on A", state_store=store)
        holder = {}
        t = threading.Thread(target=lambda: holder.update(r=cr.drain(THREAD_A, state_store=store)))
        t.start()
        self.assertTrue(gate_a["entered"].wait(5))
        try:
            second, _ = cr.enqueue(THREAD_A, "user_prompt", "second on A", state_store=store)
            self.assertEqual(cr.drain(THREAD_A, state_store=store)["status"], "held",
                             "a second writer on A is refused at once, never waits")
            self.gate = None                                  # B's client does not block
            cr.enqueue(THREAD_B, "user_prompt", "only on B", state_store=store)
            rb = cr.drain(THREAD_B, state_store=store)
            self.assertEqual((rb["status"], len(rb["delivered"])), ("drained", 1),
                             "thread B runs while thread A is mid-turn")
        finally:
            gate_a["release"].set()
            t.join(5)
        self.assertEqual(holder["r"]["status"], "drained")
        self.assertEqual(store.read("codex_turn_event", second["event_id"])["status"], "delivered",
                         "the holder drained A's queued event right after its own turn")
        texts = [s["input"][0]["text"] for s in self.turn_starts() if s["threadId"] == THREAD_A]
        self.assertEqual(texts, ["first on A", "second on A"])

    # -- conversation creation runs its first turn on the creating connection ----
    def test_new_conversation_runs_its_first_turn_on_the_same_connection(self):
        """Live finding 2026-09-29: a thread with no turn is dropped when the
        connection that started it closes ('no rollout found' / 'thread not
        found' on the next connection). Creation therefore runs the first turn
        before closing, on that one client."""
        clients = []

        class Starts(FakeClient):
            def request(self, method, params, timeout=60):
                if method == "thread/start":
                    FakeClient.log.append((method, params))
                    return {"thread": {"id": "0ccccccc-0000-7000-8000-00000000000c"}}
                return super().request(method, params, timeout)

            def close(self):
                clients.append("closed")
                return 0

        self.patches[-1].stop()
        try:
            one = Starts()
            with mock.patch.object(cr, "connect", lambda **kw: (one, "gpt-6-astra")):
                out = cr.create_conversation("roundtrip", "ceo", "first turn text", state_store=store)
        finally:
            self.patches[-1].start()
        self.assertEqual([m for m, _ in FakeClient.log], ["thread/start", "turn/start"],
                         "thread/start then its first turn/start, no resume, one connection")
        self.assertEqual(clients, ["closed"])
        self.assertEqual(out["conversation"]["thread_id"], "0ccccccc-0000-7000-8000-00000000000c")
        self.assertEqual((out["first_event"]["status"], out["first_event"]["turn_ref"]),
                         ("delivered", "turn-1"))
        start = [p for m, p in FakeClient.log if m == "turn/start"][0]
        self.assertEqual(start["input"], [{"type": "text", "text": "first turn text"}])
        with self.assertRaises(cr.RuntimeError_) as cm:
            cr.create_conversation("x", "ceo", "   ", state_store=store)
        self.assertEqual(cm.exception.code, "first-prompt-required")

    def test_a_resume_failure_fails_closed_and_keeps_the_event_queued(self):
        from agent.execution.codex_appserver import AppServerError

        class ResumeFails(FakeClient):
            def request(self, method, params, timeout=60):
                if method == "thread/resume":
                    raise AppServerError(method, {"message": "no rollout found for thread id x"})
                return super().request(method, params, timeout)

        self.patches[-1].stop()
        try:
            with mock.patch.object(cr, "connect", lambda **kw: (ResumeFails(), "gpt-6-astra")):
                ev, _ = cr.enqueue(THREAD_A, "user_prompt", "hello", state_store=store)
                with self.assertRaises(AppServerError):
                    cr.drain(THREAD_A, state_store=store)
        finally:
            self.patches[-1].start()
        self.assertEqual(store.read("codex_turn_event", ev["event_id"])["status"], "queued")
        self.assertEqual(self.turn_starts(), [], "no turn/start after a failed resume")

    # -- registry / fail-closed -------------------------------------------------
    def test_unregistered_or_desktop_thread_is_refused_everywhere(self):
        with self.assertRaises(cr.RuntimeError_) as cm:
            cr.enqueue(DESKTOP, "user_prompt", "hi", state_store=store)
        self.assertEqual(cm.exception.code, "thread-not-in-shared-runtime")
        with self.assertRaises(cr.RuntimeError_):
            cr.drain(DESKTOP, state_store=store)

        class Refuses:
            def read(self, kind, rid):
                return None
        result = sd.dispatch_session("KAN-1", state_store=Refuses(), origin_thread_id=DESKTOP)
        self.assertEqual((result["blocker"], result["dispatch_status"]),
                         ("thread-not-in-shared-runtime", "not-prepared"))
        with self.assertRaises(cr.RuntimeError_):
            cr.create_conversation("x", "worker:po", "hi", state_store=store)

    def test_connect_fails_closed_without_a_running_shared_runtime(self):
        self.patches[-1].stop()
        try:
            with self.assertRaises(cr.RuntimeError_) as cm:
                cr.connect(state_store=store, factory=_refuse)
            self.assertEqual(cm.exception.code, "codex-runtime-not-running")
        finally:
            self.patches[-1].start()

    def test_runtime_starts_once_is_reused_and_refuses_an_inconsistent_one(self):
        spawned = []
        from agent.execution import codex_primary
        with mock.patch.object(codex_primary, "bundled_catalog_path", lambda s: "/rt/cat.json"), \
                mock.patch.object(cr, "_pid_alive", lambda pid: True):
            rec = cr.ensure_runtime(state_store=store, spawn=lambda a: spawned.append(a) or 4242,
                                    alive=lambda p: True, wait=lambda p: True)
            self.assertEqual((rec["pid"], rec["status"]), (4242, "running"))
            self.assertEqual(spawned[0][:4], ["codex", "app-server", "--listen",
                                              "unix://" + cr.socket_path(store)])
            self.assertIn('openai_base_url="https://chatgpt.com/backend-api/codex"', spawned[0])
            again = cr.ensure_runtime(state_store=store, spawn=_refuse, alive=lambda p: True,
                                      wait=_refuse)
            self.assertEqual(again["revision"], rec["revision"], "reused, not restarted")
            with self.assertRaises(cr.RuntimeError_) as cm:
                cr.ensure_runtime(state_store=store, spawn=_refuse, alive=lambda p: False)
            self.assertEqual(cm.exception.code, "codex-runtime-inconsistent")

    # -- dispatch origin + envelope + contract ------------------------------------
    def test_origin_fields_are_validated_and_the_envelope_names_the_reply_thread(self):
        d = self.dispatch(THREAD_A)
        self.assertEqual([e for e in validate.validate_record("session_dispatch", d) if "origin" in e
                          or "reply" in e or "target" in e], [])
        bad = dict(d, reply_to_thread_id=THREAD_B)
        self.assertTrue(any("reply_to_thread_id" in e for e in validate.validate_record("session_dispatch", bad)))
        env = build_envelope(d, d["dispatch_id"], stable_home=HOME)
        self.assertIn("reply_to: Thebes routes your outcome to Codex conversation %s" % THREAD_A, env)
        self.assertIn("python3 -m agent.listener session-outcome %s --dispatch %s --delivery-id %s"
                      % (d["work_item_id"], d["dispatch_id"], d["dispatch_id"]), env)

    def test_contract_carries_the_origin_thread_and_rejects_a_non_uuid(self):
        base = {"schema_version": 1, "source": "listener-cli", "actor": "ceo", "idempotency_key": "k",
                "correlation_id": "k", "intent_type": contract.PREPARE_SESSION_DISPATCH}
        ok = contract.normalize(dict(base, payload={"work_item_id": "KAN-1", "deliver": True,
                                                    "origin_thread_id": THREAD_A}))
        self.assertEqual(ldispatch.argv_for(ok)[-4:], ["KAN-1", "--deliver", "--origin-thread", THREAD_A])
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(dict(base, payload={"work_item_id": "KAN-1", "origin_thread_id": "a b"}))

    def test_listener_cli_reads_the_origin_thread_from_the_codex_environment_only(self):
        from agent.listener import __main__ as lcli
        sent = {}
        with mock.patch.object(lcli, "_post", lambda port, path, body: sent.update(b=body) or (202, {})), \
                mock.patch.dict(os.environ, {"CODEX_THREAD_ID": THREAD_A}):
            lcli.main(["session-dispatch", "KAN-1", "--deliver"])
        self.assertEqual(sent["b"]["payload"]["origin_thread_id"], THREAD_A)
        with mock.patch.object(lcli, "_post", lambda port, path, body: sent.update(b=body) or (202, {})), \
                mock.patch.dict(os.environ, {}, clear=True):
            lcli.main(["session-dispatch", "KAN-1"])
        self.assertNotIn("origin_thread_id", sent["b"]["payload"])


class WebSocketFramingTests(unittest.TestCase):
    def test_masked_client_frames_round_trip_and_the_accept_key_matches_rfc6455(self):
        self.assertEqual(codex_ws.accept_key("dGhlIHNhbXBsZSBub25jZQ=="),
                         "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")
        a, b = socket.socketpair()
        try:
            for payload in ("{}", json.dumps({"x": "y" * 300}), "z" * 70000):
                got = {}
                reader = threading.Thread(target=lambda: got.update(f=codex_ws.read_frame(b)))
                reader.start()                         # read concurrently: 70 KB > socket buffer
                a.sendall(codex_ws.encode_frame(payload))
                reader.join(5)
                fin, op, data = got["f"]
                self.assertEqual((fin, op, data.decode()), (True, codex_ws.OP_TEXT, payload))
            a.sendall(codex_ws.encode_frame("server", mask=False))
            self.assertEqual(codex_ws.read_frame(b)[2], b"server")
        finally:
            a.close(); b.close()


if __name__ == "__main__":
    unittest.main()
