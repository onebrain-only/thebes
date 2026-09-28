#!/usr/bin/env python3
"""Async Primary notification: worker outcome → Listener/session_outcome →
one durable primary_notification → the ACTIVE Primary, once. Fakes only;
no claude, no codex, no subprocess is ever spawned here.
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

from agent.state import store                                        # noqa: E402
from agent.state import validate                                     # noqa: E402
from agent.controller import session_dispatch as sd                  # noqa: E402
from agent.execution import primary_notify as pn                     # noqa: E402
from agent.execution.brief import assert_no_control_plane_identifier, ExecutorBriefViolation  # noqa: E402
from agent.execution.claude_delivery import build_envelope           # noqa: E402
from agent.execution.codex_primary import WakeResult                 # noqa: E402
from agent.listener import contract, dispatch as ldispatch           # noqa: E402

SEAT = "po"
SID = "4d417564-5e86-4808-aacf-7158dcb65d59"
OTHER = "11111111-1111-4111-8111-111111111111"
CODEX = "01a0e382-98e9-70b2-84df-c757e3c6c517"
CLAUDE_A = "9dd2598a-556e-402c-b452-29a5456794d6"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("nothing here may spawn a process or wait on one")


class FakeCodexWaker:
    def __init__(self, status="delivered"):
        self.calls, self.status = [], status

    def __call__(self, event_kind, text, *, binding, state_store):
        self.calls.append((event_kind, text, binding["session_ref"]))
        return WakeResult(self.status, None if self.status == "delivered" else "CODEX_PRIMARY_THREAD_BUSY",
                          None if self.status == "delivered" else "busy", thread_id=binding["session_ref"],
                          turn_id="turn-1" if self.status == "delivered" else None,
                          wake_record_id="pwake-fake")


class FakeClaudeCli:
    """The Claude Primary as `claude agents --json` shows it."""
    def __init__(self, status="idle"):
        self.rows = [{"sessionId": CLAUDE_A, "id": CLAUDE_A[:8], "pid": 11799, "status": status}]
        self.calls = []

    def agents(self, include_completed=False):
        self.calls.append("agents"); return list(self.rows)

    @staticmethod
    def find_by_sid(rows, sid):
        return next((r for r in rows if r["sessionId"] == sid), None)

    def stop(self, short_id):
        self.calls.append(("stop", short_id)); self.rows = []

    def wait_stopped(self, sid, timeout, pid=None, **kw):
        self.calls.append("wait"); return True

    def bg_resume(self, sid, text, cwd):
        self.calls.append(("resume", sid, text)); self.rows = [{"sessionId": sid, "id": sid[:8], "pid": 2}]
        return "backgrounded"


class AsyncPrimaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session(SEAT, "claude", SID, HOME, "ceo", session_name="thebes-po-c")
        store.bind_primary("claude", CLAUDE_A, "STANDBY", "ceo", "ref:t", HOME)
        store.set_primary_active("claude", "ceo", "ref:t")
        store.bind_primary("codex", CODEX, "STANDBY", "ceo", "ref:t", HOME)
        self.launched = []
        self.patches = [mock.patch.object(pn, "_detach", lambda d: self.launched.append(d))]
        self.patches += [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches: p.start()
        self.n = 0

    def tearDown(self):
        for p in self.patches: p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- fixtures -----------------------------------------------------------
    def codex_active(self):
        store.set_primary_active("codex", "ceo", "ref:cutover-fixture")

    def dispatch(self, sid=SID, delivered=True):
        self.n += 1
        item = "KAN-%d" % (960 + self.n)
        d = store.create("session_dispatch", {
            "work_item_id": item, "seat_id": SEAT, "provider": "claude", "session_id": sid,
            "worktree_path": "/wt", "branch": "exec/po/%s" % item, "execution_lease_id": "lease-fixture",
            "invocation_id": "fixture", "authorization_ref": "authz:fixture", "status": "dispatched",
            "outcome": None, "summary": None, "reference": None, "reported_session_id": None,
            "outcome_at": None, "recorded_by": None})
        if delivered:
            store.record_session_delivery(d["dispatch_id"], {
                "dispatch_id": d["dispatch_id"], "work_item_id": item, "seat_id": SEAT,
                "provider": "claude", "session_id": sid, "status": "DELIVERED",
                "stopped_before_resume": "YES", "resumed_same_sid": "YES",
                "session_count_before": 1, "session_count_after": 1, "delivered_at": store.now()})
        return d

    def outcome(self, d, outcome="completed", sid=SID, delivery_id=None, **kw):
        return sd.session_outcome(d["work_item_id"], d["dispatch_id"], outcome, sid, "done: %s" % outcome,
                                  "b2f46e7", delivery_id=delivery_id or d["dispatch_id"],
                                  state_store=store, **kw)

    # -- 1. worker outcome → Listener path records, schedules, returns at once --
    def test_accepted_outcome_records_then_schedules_exactly_one_notification_and_returns(self):
        d = self.dispatch()
        res = self.outcome(d)
        self.assertEqual(res["outcome_status"], "recorded")
        self.assertEqual(res["primary_notify"], {"status": "scheduled", "dispatch_id": d["dispatch_id"],
                                                 "notification_status": "scheduled"})
        self.assertEqual(self.launched, [d["dispatch_id"]], "one detached delivery, nothing awaited")
        n = store.read("primary_notification", d["dispatch_id"])
        self.assertEqual((n["status"], n["outcome"], n["worker_session_id"], n["delivery_id"],
                          n["work_item_id"], n["reference"], n["attempts"]),
                         ("scheduled", "completed", SID, d["dispatch_id"], d["work_item_id"], "b2f46e7", 0))
        self.assertEqual([e for e in validate.check(store.RUNTIME) if "notification" in e], [])

    # -- 2. two outstanding dispatches are independent -------------------------
    def test_two_outstanding_outcomes_get_two_independent_notifications(self):
        a, b = self.dispatch(), self.dispatch()
        self.outcome(a, "completed"); self.outcome(b, "blocked")
        self.assertEqual(sorted(self.launched), sorted([a["dispatch_id"], b["dispatch_id"]]))
        w = FakeCodexWaker(); self.codex_active()
        pn.deliver(a["dispatch_id"], state_store=store, codex_waker=w)
        self.assertEqual(store.read("primary_notification", b["dispatch_id"])["status"], "scheduled")
        pn.deliver(b["dispatch_id"], state_store=store, codex_waker=w)
        self.assertEqual([c[1].split("\n")[1] for c in w.calls],
                         ["task: %s" % a["work_item_id"], "task: %s" % b["work_item_id"]])

    # -- 3. completed / decision_required / blocked wake the SAME Codex thread ----
    def test_codex_active_wakes_the_bound_thread_with_the_structured_event(self):
        self.codex_active()
        for outcome in ("completed", "decision_required", "blocked"):
            d = self.dispatch(); self.outcome(d, outcome)
            w = FakeCodexWaker()
            res = pn.deliver(d["dispatch_id"], state_store=store, codex_waker=w)
            self.assertEqual((res["status"], res["provider"], res["wake_record_id"]),
                             ("delivered", "codex", "pwake-fake"))
            (kind, text, thread), = w.calls
            self.assertEqual((kind, thread), ("worker_outcome", CODEX))
            self.assertIn("dispatch_id: %s" % d["dispatch_id"], text)
            self.assertIn("worker_sid: %s" % SID, text)
            self.assertIn("delivery_id: %s" % d["dispatch_id"], text)
            self.assertIn("outcome: %s" % outcome, text)
            self.assertIn("reference: b2f46e7", text)
            self.assertIn("next: " + pn.NEXT_STEP[outcome][:30], text)
            n = store.read("primary_notification", d["dispatch_id"])
            self.assertEqual((n["status"], n["notified_provider"], n["attempts"]), ("delivered", "codex", 1))
        self.assertIn("SAME worker session on the SAME ticket", pn.NEXT_STEP["blocked"])
        self.assertIn("Do not invent or dispatch further work", pn.NEXT_STEP["completed"])

    # -- 4. duplicate outcome → no second notification, no second wake ----------
    def test_duplicate_outcome_schedules_nothing_and_a_delivered_notification_never_rewakes(self):
        d = self.dispatch(); self.outcome(d)
        again = self.outcome(d)
        self.assertEqual(again["outcome_status"], "not-recorded")
        self.assertIsNone(again["primary_notify"])
        self.assertEqual(self.launched, [d["dispatch_id"]])
        self.assertEqual(pn.schedule(d["dispatch_id"], store.read("session_dispatch", d["dispatch_id"]),
                                     state_store=store, launcher=_refuse)["status"], "already-scheduled")
        self.codex_active(); w = FakeCodexWaker()
        pn.deliver(d["dispatch_id"], state_store=store, codex_waker=w)
        pn.deliver(d["dispatch_id"], state_store=store, codex_waker=w)
        self.assertEqual(len(w.calls), 1, "a delivered notification is never sent twice")
        self.assertRaises(store.StateError, store.settle_primary_notification, d["dispatch_id"], "failed",
                          error={"code": "x", "message": "x"})

    # -- 5. wrong SID / invalid delivery → rejected before any wake -------------
    def test_wrong_sid_or_unattested_delivery_is_rejected_before_any_notification(self):
        d = self.dispatch()
        r1 = self.outcome(d, sid=OTHER)
        r2 = self.outcome(d, delivery_id="delivery-nope")
        d2 = self.dispatch(delivered=False)
        r3 = self.outcome(d2)
        for r, frag in ((r1, "session-identity-mismatch"), (r2, "outcome-delivery-unattested"),
                        (r3, "outcome-delivery-unattested")):
            self.assertEqual(r["outcome_status"], "not-recorded"); self.assertIn(frag, r["blocker"])
            self.assertIsNone(r["primary_notify"])
        self.assertEqual(self.launched, [])
        self.assertEqual(store.read_all("primary_notification"), [])

    # -- 6/7. only the ACTIVE Primary, never both ------------------------------
    def test_claude_active_wakes_only_claude_and_codex_active_only_codex(self):
        d = self.dispatch(); self.outcome(d)
        w, cli = FakeCodexWaker(), FakeClaudeCli()
        res = pn.deliver(d["dispatch_id"], state_store=store, codex_waker=w, claude_cli=cli)
        self.assertEqual((res["status"], res["provider"]), ("delivered", "claude"))
        self.assertEqual(w.calls, [])
        self.assertEqual([c for c in cli.calls if isinstance(c, tuple)][0], ("stop", CLAUDE_A[:8]))
        resumes = [c for c in cli.calls if isinstance(c, tuple) and c[0] == "resume"]
        self.assertEqual(len(resumes), 1)
        self.assertEqual(resumes[0][1], CLAUDE_A)
        self.assertIn("WORKER_OUTCOME", resumes[0][2])
        d2 = self.dispatch(); self.outcome(d2); self.codex_active()
        w, cli = FakeCodexWaker(), FakeClaudeCli()
        res = pn.deliver(d2["dispatch_id"], state_store=store, codex_waker=w, claude_cli=cli)
        self.assertEqual((res["provider"], len(w.calls), cli.calls), ("codex", 1, []))

    # -- 8. busy Primary: kept durably, one attempt, no loop ------------------
    def test_busy_primary_keeps_the_notification_durable_without_retrying(self):
        self.codex_active(); d = self.dispatch(); self.outcome(d)
        w = FakeCodexWaker(status="busy")
        res = pn.deliver(d["dispatch_id"], state_store=store, codex_waker=w)
        n = store.read("primary_notification", d["dispatch_id"])
        self.assertEqual((res["status"], n["status"], n["attempts"], n["error"]["code"], len(w.calls)),
                         ("busy", "busy", 1, "CODEX_PRIMARY_THREAD_BUSY", 1))
        d3 = self.dispatch(); self.outcome(d3)
        store.set_primary_active("claude", "ceo", "ref:back")
        cli = FakeClaudeCli(status="busy")
        res = pn.deliver(d3["dispatch_id"], state_store=store, codex_waker=_refuse, claude_cli=cli)
        self.assertEqual((res["status"], res["error"]["code"]), ("busy", "CLAUDE_PRIMARY_BUSY"))
        self.assertNotIn(("stop", CLAUDE_A[:8]), cli.calls, "a busy Primary is never stopped")
        # a later attempt on the kept notification delivers it
        w = FakeCodexWaker(); self.codex_active()
        self.assertEqual(pn.deliver(d["dispatch_id"], state_store=store, codex_waker=w)["status"], "delivered")

    # -- 9. every worker outcome notifies; worker_unreachable does not ---------
    def test_all_five_worker_outcomes_notify_and_unreachable_does_not(self):
        for outcome in sd.WORKER_OUTCOMES:
            d = self.dispatch(); res = self.outcome(d, outcome)
            self.assertEqual(res["primary_notify"]["status"], "scheduled", outcome)
        d = self.dispatch(delivered=False)
        res = sd.session_outcome(d["work_item_id"], d["dispatch_id"], "worker_unreachable", None,
                                 "no answer", state_store=store)
        self.assertEqual((res["outcome_status"], res["primary_notify"]), ("recorded", None))
        self.assertEqual(len(self.launched), len(sd.WORKER_OUTCOMES))

    # -- 10. contract: worker actor narrowed; deliver flag; brief firewall -------
    def test_worker_actor_may_only_report_an_outcome(self):
        base = {"schema_version": 1, "source": "listener-cli", "actor": "worker:po",
                "idempotency_key": "k1", "correlation_id": "k1"}
        ok = contract.normalize(dict(base, intent_type=contract.RECORD_SESSION_OUTCOME, payload={
            "work_item_id": "KAN-960", "dispatch_id": "dispatch-x", "outcome": "completed",
            "summary": "done", "session_id": SID, "delivery_id": "dispatch-x"}))
        self.assertEqual(ok["actor"], "worker:po")
        for kind, payload in ((contract.EXECUTE_WORK_ITEM, {"work_item_id": "KAN-960"}),
                              (contract.PREPARE_SESSION_DISPATCH, {"work_item_id": "KAN-960"}),
                              (contract.VALIDATE_WORK_ITEM, {"work_item_id": "KAN-960"})):
            with self.assertRaises(contract.IntentRejected) as cm:
                contract.normalize(dict(base, intent_type=kind, payload=payload))
            self.assertEqual(cm.exception.reason, "actor-not-permitted")
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(dict(base, actor="worker:Bad Seat", intent_type=contract.RECORD_SESSION_OUTCOME,
                                    payload={"work_item_id": "KAN-960", "dispatch_id": "d", "outcome": "completed",
                                             "summary": "s", "session_id": SID}))

    def test_prepare_with_deliver_maps_to_the_deliver_flag_only_when_true(self):
        base = {"schema_version": 1, "source": "listener-cli", "actor": "ceo",
                "idempotency_key": "k2", "correlation_id": "k2", "intent_type": contract.PREPARE_SESSION_DISPATCH}
        plain = contract.normalize(dict(base, payload={"work_item_id": "KAN-960"}))
        self.assertNotIn("--deliver", ldispatch.argv_for(plain))
        with_it = contract.normalize(dict(base, payload={"work_item_id": "KAN-960", "deliver": True}))
        self.assertEqual(ldispatch.argv_for(with_it)[-2:], ["KAN-960", "--deliver"])
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(dict(base, payload={"work_item_id": "KAN-960", "deliver": "yes"}))

    def test_envelope_carries_the_listener_command_but_a_product_brief_still_refuses_it(self):
        d = self.dispatch()
        env = build_envelope(d, d["dispatch_id"], stable_home=HOME)
        self.assertIn("python3 -m agent.listener session-outcome", env)
        self.assertIn("--actor worker:po --wait 600", env)
        with self.assertRaises(ExecutorBriefViolation):
            assert_no_control_plane_identifier(env, "objective")
        with self.assertRaises(ExecutorBriefViolation):
            assert_no_control_plane_identifier("report via python3 -m agent.listener", "objective")


if __name__ == "__main__":
    unittest.main()
