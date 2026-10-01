#!/usr/bin/env python3
"""The decision group (D-031): gate → accountable owner → same asker resumed.

Fakes only. The FakeGate is the real one (deterministic keywords); owner
delivery and asker resume are seams; JevGate is exercised against a fake
HTTP opener. No process is spawned.
"""
import json
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
from agent.execution import codex_runtime as cr                      # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402
from agent.execution import decision_gate as dg                      # noqa: E402

KARNAK = "0aaaaaaa-2222-7000-8000-00000000000a"
PO = "0bbbbbbb-2222-7000-8000-00000000000b"
CTO = "0ccccccc-2222-7000-8000-00000000000c"
THREAD = "0ddddddd-2222-7000-8000-00000000000d"
HOME = "/stable/home"


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class DecisionGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        store.bind_role_session("po", "claude", PO, HOME, "ceo")
        store.bind_role_session("cto", "claude", CTO, HOME, "ceo")
        store.create("codex_runtime", {"runtime_id": cr.RUNTIME_ID, "status": "running",
                                       "socket_path": cr.socket_path(store)}, rid=cr.RUNTIME_ID)
        store.create("codex_conversation", {"thread_id": THREAD, "runtime_id": cr.RUNTIME_ID,
                                            "registered_by": "ceo", "status": "active"}, rid=THREAD)
        self.delivered, self.resumed, self.launched = [], [], []
        # Hermetic: the live config may select the real Jev gate (and a real key
        # file); a test must never reach the network or spend money.
        live = dg.config()
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        self.patches.append(mock.patch.object(
            dg, "config", lambda path=dg.CONFIG_PATH: dict(live, gate="fake")))
        self.patches.append(mock.patch.object(
            dg.urllib.request, "urlopen",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in tests"))))
        self.patches.append(mock.patch.object(cr, "_detach_drain", self.launched.append))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- fixtures --------------------------------------------------------------
    def settled(self, outcome, text, asker="karnak", sid=KARNAK):
        """A dispatch to the asker, delivered, then settled with `outcome`."""
        did = store.new_id("conversation_dispatch")
        cap = "cap-" + did
        store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "codex", "origin_thread_id": THREAD,
            "target_provider": "claude", "target_session_id": sid, "target_seat_id": asker,
            "delivery_id": did, "capability_sha256": store.capability_sha256(cap),
            "prompt_ref": "/x", "status": "delivered", "delivery_status": "DELIVERED",
            "outcome": None, "result_ref": None, "result_sha256": None,
            "reported_session_id": None, "attested_delivery_id": None, "outcome_at": None,
            "result_event_id": None, "error": None}, rid=did)
        store.record_session_delivery(did, {
            "dispatch_id": did, "work_item_id": None, "seat_id": asker, "provider": "claude",
            "session_id": sid, "status": "DELIVERED", "stopped_before_resume": "YES",
            "resumed_same_sid": "YES", "session_count_before": 1, "session_count_after": 1,
            "delivered_at": store.now()})
        return did, cap

    def submit(self, did, cap, outcome, text, router=None):
        return cd.submit(did, outcome, text, env={"CLAUDE_CODE_SESSION_ID": KARNAK,
                                                  cd.CAPABILITY_ENV: cap},
                         state_store=store, decision_router=router)

    def deliver(self, req, message, state_store):
        self.delivered.append((req, message))
        return {"status": "DELIVERED"}

    def resume(self, req, text, state_store):
        self.resumed.append((req, text))
        return {"dispatch_id": "cdispatch-continuation", "status": "accepted"}

    def router(self, record, state_store):
        return dg.route(record, state_store=state_store, deliver=self.deliver, resume=self.resume)

    def clean(self):
        return [e for e in validate.check(store.RUNTIME)
                if any(k in e for k in ("decision", "conversation", "role session"))]

    # -- the gate ---------------------------------------------------------------
    def test_fake_gate_maps_keywords_to_the_accountable_role_and_scores_confidence(self):
        r = dg.classify_and_resolve("Which acceptance criteria apply to KAN-9?", state_store=store)
        self.assertEqual((r["decision_class"], r["accountable_role"], r["route"], r["owner_seat"]),
                         ("work_acceptance", "po", "owner", "po"))
        self.assertEqual(r["owner_session_id"], PO)
        r = dg.classify_and_resolve("Should the schema use a junction table?", state_store=store)
        self.assertEqual((r["accountable_role"], r["route"]), ("cto", "owner"))
        r = dg.classify_and_resolve("What budget can we invest in this vendor?", state_store=store)
        self.assertEqual((r["accountable_role"], r["route"], r["reason"]),
                         ("ceo", "escalate", "ceo-owned-decision"))
        r = dg.classify_and_resolve("Which colour should the toast use?", state_store=store)
        self.assertEqual((r["accountable_role"], r["route"], r["reason"]),
                         ("cxo", "escalate", "decision-owner-unbound"), "cxo has no session")
        r = dg.classify_and_resolve("The build has a weird error I cannot explain", state_store=store)
        self.assertEqual((r["route"], r["reason"]), ("escalate", "confidence-below-threshold"))

    def test_jev_gate_sends_one_typed_choice_and_degrades_to_escalation(self):
        calls = []

        class Resp:
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(self.body).encode()

        def opener(req, timeout=30):
            calls.append((req.full_url, req.get_header("Authorization"), json.loads(req.data)))
            return Resp({"answers": {"decision_class": {"choice": "technical_architecture",
                                                         "confidence": 0.93,
                                                         "probabilities": {"technical_architecture": 0.93}}}})
        # key_file is blanked so this test can never read (or print) a real key.
        cfg = dict(dg.config(), gate="jev")
        cfg["jev_provider"] = dict(cfg["jev_provider"], key_file="")
        gate = dg.JevGate(cfg, env={"OPENROUTER_API_KEY": "sk-test"}, opener=opener)
        v = gate.classify("Should we move to a junction table?")
        self.assertEqual((v["decision_class"], v["confidence"], v["gate"]),
                         ("technical_architecture", 0.93, "jev"))
        url, auth, body = calls[0]
        self.assertEqual((url, auth), ("https://openrouter.ai/api/v1/systemone",
                                       "Bearer sk-test"))
        self.assertEqual(body["model"], "typesafe/jev-1.13")
        self.assertEqual(body["questions"]["decision_class"]["type"], "choice")
        self.assertIn("work_acceptance", body["questions"]["decision_class"]["criteria"])
        self.assertEqual(body["state"], {"question": "Should we move to a junction table?"})
        with mock.patch.object(dg, "gate_for", lambda cfg=None, env=None:
                               dg.JevGate(cfg, env={}, opener=opener)):
            r = dg.classify_and_resolve("anything", cfg=cfg, state_store=store)
        self.assertEqual((r["route"], r["reason"]), ("escalate", "decision-gate-unavailable"))

    # -- the loop ----------------------------------------------------------------
    def test_a_decision_outcome_goes_to_the_owner_not_to_codex(self):
        did, cap = self.settled("decision_required", "")
        out = self.submit(did, cap, "decision_required",
                          "Which acceptance criteria apply to KAN-9? AC3 contradicts AC5.",
                          router=self.router)
        self.assertEqual(out["decision"]["route"], "owner")
        self.assertEqual(out["decision"]["owner_seat"], "po")
        self.assertEqual(self.launched, [], "no result turn reached the Codex thread")
        self.assertEqual(len(self.delivered), 1)
        req, message = self.delivered[0]
        self.assertTrue(message.startswith("THEBES_DECISION_REQUEST"))
        self.assertIn("expected_owner_sid: %s" % PO, message)
        self.assertIn("AC3 contradicts AC5", message)
        self.assertIn("decision_gate answer %s" % req["decision_request_id"], message)
        rec = store.read("decision_request", req["decision_request_id"])
        self.assertEqual((rec["status"], rec["asker_seat_id"], rec["origin_outcome"]),
                         ("open", "karnak", "decision_required"))
        self.assertEqual(self.clean(), [])

    def test_the_owner_answers_once_with_identity_and_the_same_asker_is_resumed(self):
        did, cap = self.settled("decision_required", "")
        self.submit(did, cap, "decision_required", "Which acceptance criteria apply to KAN-9?",
                    router=self.router)
        req, message = self.delivered[0]
        dcap = message.split("%s=" % dg.CAPABILITY_ENV, 1)[1].split()[0]
        rid = req["decision_request_id"]
        with self.assertRaises(dg.Refused) as ctx:
            dg.answer(rid, "use AC3", env={"CLAUDE_CODE_SESSION_ID": CTO, dg.CAPABILITY_ENV: dcap},
                      state_store=store, resume=self.resume)
        self.assertEqual(ctx.exception.code, "owner-identity-mismatch")
        with self.assertRaises(dg.Refused) as ctx:
            dg.answer(rid, "use AC3", env={"CLAUDE_CODE_SESSION_ID": PO, dg.CAPABILITY_ENV: "x"},
                      state_store=store, resume=self.resume)
        self.assertEqual(ctx.exception.code, "capability-invalid")
        out = dg.answer(rid, "Use AC3; AC5 is superseded.",
                        env={"CLAUDE_CODE_SESSION_ID": PO, dg.CAPABILITY_ENV: dcap},
                        state_store=store, resume=self.resume)
        self.assertEqual(out["status"], "answered")
        (rreq, text), = self.resumed
        self.assertEqual(rreq["asker_session_id"], KARNAK, "the SAME island continues")
        self.assertTrue(text.startswith("THEBES_DECISION_ANSWER"))
        self.assertIn("in_reply_to_dispatch: %s" % did, text)
        self.assertIn("Use AC3; AC5 is superseded.", text)
        rec = store.read("decision_request", rid)
        self.assertEqual((rec["status"], rec["continuation_dispatch_id"]),
                         ("answered", "cdispatch-continuation"))
        with self.assertRaises(dg.Refused) as ctx:
            dg.answer(rid, "again", env={"CLAUDE_CODE_SESSION_ID": PO, dg.CAPABILITY_ENV: dcap},
                      state_store=store, resume=self.resume)
        self.assertEqual(ctx.exception.code, "decision-request-not-open")
        self.assertEqual(self.clean(), [])

    def test_task_local_questions_go_straight_back_to_the_asker(self):
        did, cap = self.settled("clarification_required", "")
        cfg = dict(dg.config(), threshold=0.0)
        router = lambda record, state_store: dg.route(record, state_store=state_store, cfg=cfg,
                                                      deliver=self.deliver, resume=self.resume)
        out = self.submit(did, cap, "clarification_required",
                          "Should I name the helper _fmt or _format?", router=router)
        self.assertEqual(out["decision"]["route"], "task-owner")
        self.assertEqual(self.delivered, [])
        (req, text), = self.resumed
        self.assertIn("yours to decide", text)
        self.assertEqual(store.read("decision_request", req["decision_request_id"])["status"],
                         "answered")

    def test_escalation_returns_to_codex_marked_and_a_delivery_failure_escalates(self):
        did, cap = self.settled("blocked", "")
        out = self.submit(did, cap, "blocked", "We need budget approval to pay for the vendor.",
                          router=self.router)
        self.assertEqual(out["origin_reply"]["escalated"]["reason"],
                         "ceo-only:money_or_secrets", "the D-033 deny-list fires before any gate")
        self.assertEqual(self.launched, [THREAD], "the question reached the Codex thread")
        ev = store.read("codex_turn_event", out["origin_reply"]["event_id"])
        with open(ev["text_ref"], encoding="utf-8") as fh:
            self.assertIn("ESCALATED TO THE CEO", fh.read())

        def broken(req, message, state_store):
            raise OSError("daemon down")
        did2, cap2 = self.settled("decision_required", "")
        router = lambda record, state_store: dg.route(record, state_store=state_store,
                                                      deliver=broken, resume=self.resume)
        out = self.submit(did2, cap2, "decision_required", "Which acceptance criteria apply?",
                          router=router)
        self.assertEqual(out["origin_reply"]["escalated"]["reason"], "owner-delivery-failed")
        reqs = [r for r in store.read_all("decision_request") if r["origin_dispatch_id"] == did2]
        self.assertEqual((reqs[0]["status"], reqs[0]["escalation_reason"]),
                         ("escalated", "owner-delivery-failed"))
        self.assertEqual(self.clean(), [])

    def test_a_decision_delivery_record_validates(self):
        """Live P2 run 2 failed here: the delivery record for a dreq- id was refused by
        the validator AFTER the owner had already been resumed. The record must be legal."""
        rec = store.record_session_delivery("dreq-11111111-1111-4111-8111-111111111111", {
            "dispatch_id": "dreq-11111111-1111-4111-8111-111111111111", "work_item_id": None,
            "seat_id": "po", "provider": "claude", "session_id": PO, "status": "DELIVERED",
            "stopped_before_resume": "YES", "resumed_same_sid": "YES",
            "session_count_before": 1, "session_count_after": 1, "delivered_at": store.now()})
        self.assertEqual(rec["status"], "DELIVERED")
        self.assertEqual([e for e in validate.check(store.RUNTIME) if "session_deliver" in e], [])

    # -- D-033 approvals ---------------------------------------------------------
    def test_deny_list_runs_before_any_gate_and_regexes_catch_phrasing(self):
        for q, cat in [("Can I push this to main now?", "merge_or_push_main"),
                       ("Should I delete the old branch exec/karnak/KAN-8?", "destructive_git"),
                       ("Shall I pick up the next ticket KAN-370?", "next_ticket"),
                       ("May I apply the migration to production?", "production"),
                       ("Can I add a new package for charts?", "design_or_governance"),
                       ("OK to push to canary?", "push_canary")]:
            self.assertEqual(dg.ceo_only_hit(q), cat, q)
        self.assertIsNone(dg.ceo_only_hit("May I commit the test file?"))
        self.assertIsNone(dg.ceo_only_hit("May I install a package already in the lock file?"))

    def test_a_routine_permission_is_approved_by_policy_and_the_worker_resumes_at_once(self):
        did, cap = self.settled("decision_required", "")
        out = self.submit(did, cap, "decision_required",
                          "May I commit the new test file on my working branch before continuing?",
                          router=self.router)
        self.assertEqual(out["decision"]["route"], "approved")
        self.assertEqual(self.delivered, [], "no owner, no orchestrator woken")
        self.assertEqual(self.launched, [], "nothing reached Codex")
        (req, text), = self.resumed
        self.assertIn("APPROVED by policy (D-033): branch_or_commit", text)
        rec = store.read("decision_request", req["decision_request_id"])
        self.assertEqual((rec["route"], rec["approved_action"], rec["status"]),
                         ("approved", "branch_or_commit", "answered"))
        self.assertEqual(self.clean(), [])

    def test_a_ceo_only_request_escalates_even_when_phrased_as_routine(self):
        did, cap = self.settled("decision_required", "")
        out = self.submit(did, cap, "decision_required",
                          "Quick routine commit, then I'll push to main — ok?", router=self.router)
        self.assertEqual(out["origin_reply"]["escalated"]["reason"], "ceo-only:merge_or_push_main")
        self.assertEqual(self.resumed, [])

    # -- D-034 orchestrator -------------------------------------------------------
    def test_an_owned_question_is_delivered_to_the_orchestrator_session_when_bound(self):
        ORCH = "0eeeeeee-2222-7000-8000-00000000000e"
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        r = dg.classify_and_resolve("Which acceptance criteria apply to KAN-9?", state_store=store)
        self.assertEqual((r["route"], r["owner_seat"], r["owner_session_id"], r["via"]),
                         ("owner", "po", ORCH, "orchestrator"))
        did, cap = self.settled("decision_required", "")
        self.submit(did, cap, "decision_required", "Which acceptance criteria apply to KAN-9?",
                    router=self.router)
        req, message = self.delivered[0]
        self.assertEqual(req["owner_session_id"], ORCH)
        self.assertIn("you_are: the Thebes ORCHESTRATOR", message)
        self.assertIn("subagent_type=po", message)
        rid = req["decision_request_id"]
        self.assertIn("team_pool reserve po --dispatch %s" % rid, message,
                      "the orchestrator reserves against ITS request, not the asker's dispatch")
        # Live P3b: reserving against the asker's dispatch was refused. Against the
        # request it succeeds for the orchestrator and for nobody else.
        from agent.execution import team_pool as tp
        self.assertEqual(tp.reserve("po", rid, env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                    state_store=store)["status"], "reserved")
        with self.assertRaises(tp.Refused) as ctx:
            tp.reserve("po", rid, env={"CLAUDE_CODE_SESSION_ID": KARNAK}, state_store=store)
        self.assertEqual(ctx.exception.code, "not-your-dispatch",
                         "another island cannot reserve against the orchestrator's request")
        self.assertIsNotNone(store.active_seat_reservation("po"))
        # the orchestrator session answers; po's own session is not the identity
        dcap = message.split("%s=" % dg.CAPABILITY_ENV, 1)[1].split()[0]
        with self.assertRaises(dg.Refused):
            dg.answer(req["decision_request_id"], "x", env={"CLAUDE_CODE_SESSION_ID": PO,
                                                             dg.CAPABILITY_ENV: dcap},
                      state_store=store, resume=self.resume)
        out = dg.answer(req["decision_request_id"], "Use AC3.",
                        env={"CLAUDE_CODE_SESSION_ID": ORCH, dg.CAPABILITY_ENV: dcap},
                        state_store=store, resume=self.resume)
        self.assertEqual(out["status"], "answered")
        self.assertEqual(self.resumed[0][0]["asker_session_id"], KARNAK)
        self.assertIsNone(store.active_seat_reservation("po"), "released on answer")
        self.assertEqual(self.clean(), [])

    def test_an_open_owner_request_can_be_redelivered_once_with_a_fresh_capability(self):
        """Live: the orchestrator's turn died ('Connection lost mid-response') before it
        answered; the request stayed open with no way to re-send it."""
        ORCH = "0eeeeeee-2222-7000-8000-00000000000e"
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        did, cap = self.settled("decision_required", "")
        self.submit(did, cap, "decision_required", "Which acceptance criteria apply to KAN-9?",
                    router=self.router)
        req, first = self.delivered[0]
        old_cap = first.split("%s=" % dg.CAPABILITY_ENV, 1)[1].split()[0]
        out = dg.redeliver(req["decision_request_id"], state_store=store, deliver=self.deliver)
        self.assertEqual(out["status"], "redelivered")
        req2, second = self.delivered[1]
        new_cap = second.split("%s=" % dg.CAPABILITY_ENV, 1)[1].split()[0]
        self.assertNotEqual(old_cap, new_cap)
        with self.assertRaises(dg.Refused) as ctx:
            dg.answer(req["decision_request_id"], "x", env={"CLAUDE_CODE_SESSION_ID": ORCH,
                                                             dg.CAPABILITY_ENV: old_cap},
                      state_store=store, resume=self.resume)
        self.assertEqual(ctx.exception.code, "capability-invalid", "the old capability is dead")
        self.assertEqual(dg.answer(req["decision_request_id"], "Use AC3.",
                                   env={"CLAUDE_CODE_SESSION_ID": ORCH, dg.CAPABILITY_ENV: new_cap},
                                   state_store=store, resume=self.resume)["status"], "answered")
        with self.assertRaises(dg.Refused):
            dg.redeliver(req["decision_request_id"], state_store=store, deliver=self.deliver)

    def test_bootstrap_tells_codex_about_the_orchestrator_and_when_to_use_it(self):
        text = cr.bootstrap_prompt(THREAD, store)
        self.assertIn("ORCHESTRATOR is not bound yet", text)
        ORCH = "0eeeeeee-2222-7000-8000-00000000000e"
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        text = cr.bootstrap_prompt(THREAD, store)
        self.assertIn("The ORCHESTRATOR (one Claude session; D-034): %s" % ORCH, text)
        self.assertIn("Do NOT route work through it", text)
        self.assertNotIn("Orchestrator (orchestrator)", text, "never listed as a delivery team")

    def test_a_completed_outcome_never_touches_the_gate(self):
        did, cap = self.settled("completed", "")
        called = []
        out = self.submit(did, cap, "completed", "done, 728 files",
                          router=lambda record, state_store: called.append(1))
        self.assertEqual(called, [])
        self.assertEqual(self.launched, [THREAD])


if __name__ == "__main__":
    unittest.main()
