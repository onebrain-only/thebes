#!/usr/bin/env python3
"""Maintenance prompt 2026-10-14..16: the things that kept stopping the flow. Fakes only."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                               # noqa: E402
from agent.execution import (conversation_dispatch as cd, decision_gate as dg,   # noqa: E402
                             intake, ticket_ruling)

ORCH = "0eeeeeee-6666-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-6666-7000-8000-00000000000a"
CODEX = "01a0f777-d0e4-7000-8000-000000000009"


class NoSessions:
    """A `claude` with nothing running: withdraw looks for the worker and finds no turn to stop."""
    find_by_sid = staticmethod(lambda rows, sid: None)

    def agents(self, include_completed=False):
        return []


NO_SESSIONS = NoSessions()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, "/h", "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, "/h", "ceo")

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def open_dispatch(self, key="KAN-9", origin=CODEX, provider="codex", outcome=None):
        did = store.new_id("conversation_dispatch")
        rec = {"dispatch_id": did, "origin_provider": provider, "origin_thread_id": origin,
               "target_provider": "claude", "target_session_id": KARNAK, "target_seat_id": "karnak",
               "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
               "status": "delivered", "delivery_status": "DELIVERED", "jira_key": key}
        if outcome:                                   # an already reported dispatch (not open)
            rec.update(status=outcome, outcome=outcome, result_ref="/x", result_sha256="0" * 64,
                       outcome_at=store.now(), attested_delivery_id=did, reported_session_id=KARNAK)
        store.create("conversation_dispatch", rec, rid=did)
        return did


class WithdrawAndReapTests(Base):
    def test_the_orchestrator_withdraws_any_open_dispatch_a_stranger_cannot(self):
        """B8: the orchestrator's own withdraw was refused with not-origin-thread."""
        did = self.open_dispatch()
        with self.assertRaises(cd.Refused):
            cd.withdraw(did, env={"CLAUDE_CODE_SESSION_ID": "somebody-else"}, state_store=store)
        out = cd.withdraw(did, env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store, cli=NO_SESSIONS)
        self.assertEqual(out["status"], "withdrawn")
        self.assertEqual(store.read("conversation_dispatch", did)["status"], "withdrawn")

    def test_a_codex_origin_still_withdraws_its_own(self):
        did = self.open_dispatch()
        self.assertEqual(cd.withdraw(did, env={"CODEX_THREAD_ID": CODEX}, state_store=store,
                                     cli=NO_SESSIONS)["status"], "withdrawn")

    def test_an_open_dispatch_for_a_done_ticket_is_reaped_after_half_an_hour(self):
        did = self.open_dispatch("KAN-9")
        keep = self.open_dispatch("KAN-10")
        jira = mock.Mock()
        jira.get_issue.side_effect = lambda k: {"status": "Done" if k == "KAN-9" else "Front-end"}
        self.assertEqual(cd.reap_stale(jira=jira, state_store=store, now=time.time()), [], "too young")
        out = cd.reap_stale(jira=jira, state_store=store, now=time.time() + cd.STALE_OPEN_SECONDS + 60)
        self.assertEqual([o["key"] for o in out], ["KAN-9"])
        self.assertEqual(store.read("conversation_dispatch", did)["status"], "withdrawn")
        self.assertEqual(store.read("conversation_dispatch", keep)["status"], "delivered")


class DecisionAnswerQueueTests(Base):
    def test_an_answer_for_a_busy_team_is_kept_and_sent_when_it_is_free(self):
        """2026-10-14: a decision answer to a busy team was lost (target-session-busy)."""
        origin = self.open_dispatch("KAN-9", origin=ORCH, provider="claude", outcome="decision_required")
        busy = self.open_dispatch("KAN-10")                 # the team is busy with another ticket
        req = {"decision_request_id": "dreq-q1", "origin_dispatch_id": origin,
               "asker_session_id": KARNAK, "origin_thread_id": ORCH, "asker_seat_id": "karnak",
               "decision_class": "x", "accountable_role": "cto", "owner_seat": "cto",
               "origin_outcome": "decision_required", "owner_session_id": ORCH,
               "capability_sha256": "0" * 64, "revision": 1}
        st = mock.Mock()
        st.RUNTIME = store.RUNTIME
        store_state = {"req": dict(req)}
        st.read.side_effect = lambda kind, rid: (store.read(kind, rid) if kind == "conversation_dispatch"
                                                 else dict(store_state["req"]))
        st.update.side_effect = lambda kind, rid, rev, ch: store_state["req"].update(ch) or store_state["req"]
        with mock.patch.object(cd, "dispatch", side_effect=cd.Refused("target-session-busy", "busy")):
            out = dg._resume_asker(req, "yes, go", state_store=st)
        self.assertEqual(out["status"], "queued")
        pend = store_state["req"]
        self.assertTrue(os.path.exists(pend["pending_resume_ref"]))
        # still busy: nothing is sent
        st.read_all.side_effect = lambda kind: ([dict(pend)] if kind == "decision_request" else
                                                store.read_all(kind))
        sent = []
        self.assertEqual(dg.retry_resumes(state_store=st, dispatch=lambda *a, **k: sent.append(a) or {}), [])
        store.update("conversation_dispatch", busy, store.read("conversation_dispatch", busy)["revision"],
                     {"status": "withdrawn", "withdrawn_at": store.now()})
        out = dg.retry_resumes(state_store=st, dispatch=lambda *a, **k: sent.append((a, k)) or
                               {"dispatch_id": "cdispatch-next"})
        self.assertEqual([o["action"] for o in out], ["answer-delivered"])
        self.assertIn("yes, go", sent[0][0][0])
        self.assertTrue(sent[0][1]["continuation"])
        self.assertEqual(store_state["req"]["continuation_dispatch_id"], "cdispatch-next")


class GateAuthorityTests(Base):
    def cfg(self):
        return dg.config()

    def test_destructive_git_and_governance_words_go_to_the_orchestrator_not_the_ceo(self):
        for reason in ("ceo-only:destructive_git", "ceo-only:governance_files", "ceo-only:other_repository",
                       "ceo-only:push_canary", "ceo-only:production", "ceo-only:secrets_and_credentials"):
            self.assertTrue(dg.decides_inside({"verdict": "ceo", "reason": reason}, store, self.cfg()), reason)

    def test_money_main_and_sending_outside_stay_the_ceos(self):
        for reason in ("ceo-only:money", "ceo-only:merge_or_push_main", "ceo-only:external_send"):
            self.assertFalse(dg.decides_inside({"verdict": "ceo", "reason": reason}, store, self.cfg()), reason)

    def test_production_is_the_orchestrators_without_asking_the_ceo(self):
        a = {"verdict": "ceo", "reason": "ceo-only:production"}
        self.assertTrue(dg.decides_inside(a, store, self.cfg()), "CEO 2026-10-25: never a technical permission")

    def test_route_sends_an_in_scope_production_question_to_the_orchestrator_inbox(self):
        from agent.execution import pm_ledger
        pm_ledger.add("ceo", "supabase-messaging-approval", "approved", state_store=store)
        did = self.open_dispatch("KAN-9")
        ref = os.path.join(self.tmp, "q.txt")
        with open(ref, "w") as fh:
            fh.write("Apply the reviewed migration to the production database now?")
        rec = dict(store.read("conversation_dispatch", did), result_ref=ref, outcome="decision_required",
                   status="decision_required")
        fake = mock.Mock(side_effect=lambda req, msg, state_store=None: {"sent": True})
        # The keyword gate: the configured one calls the provider with the key from the home folder.
        out = dg.route(rec, state_store=store, deliver=fake, cfg=dict(dg.config(), gate="fake"))
        self.assertEqual(out["route"], "owner")
        self.assertTrue(str(out["reason"]).startswith("orchestrator-decides:ceo-only:production"))
        self.assertEqual(store.read("decision_request", out["decision_request_id"])["status"], "open")


class OneLineEditTests(unittest.TestCase):
    def jira(self, description):
        j = mock.Mock()
        j.get_issue.return_value = {"description": description}
        j.to_adf = lambda t: {"adf": t}
        return j

    def test_one_matching_line_is_replaced_and_nothing_else_changes(self):
        j = self.jira("GOAL: x\nBRANCH: alpha-<team>\nCHECKS:\nC1 | run | flutter analyze | exit 0")
        out = intake.edit_line("KAN-9", "C1 | run | flutter analyze | exit 0",
                               "C1 | run | flutter analyze --no-pub | exit 0", jira=j, by="po")
        self.assertEqual((out["status"], out["line"]), ("edited", 4))
        sent = j.update_issue.call_args.args[1]["description"]["adf"]
        self.assertEqual(sent, "GOAL: x\nBRANCH: alpha-<team>\nCHECKS:\nC1 | run | flutter analyze --no-pub | exit 0")
        self.assertIn("Before:", j.add_comment.call_args.args[1])

    def test_no_match_a_double_match_or_a_multi_line_edit_is_refused(self):
        j = self.jira("a\nb\nb")
        for old, new in (("zzz", "q"), ("b", "q"), ("a", "x\ny"), ("a", "a"), ("", "q")):
            with self.assertRaises(intake.IntakeError):
                intake.edit_line("KAN-9", old, new, jira=j)
        j.update_issue.assert_not_called()


class TicketRulingTests(Base):
    def jira(self, status_id, status="Front-end", desc="GOAL: x"):
        j = mock.Mock()
        j.get_issue.return_value = {"status_id": status_id, "status": status, "description": desc}
        j.to_adf = lambda t: {"adf": t}
        return j

    def test_only_the_orchestrator_may_rule(self):
        with self.assertRaises(ticket_ruling.Refused) as ctx:
            ticket_ruling.rule("KAN-9", "yes", env={"CLAUDE_CODE_SESSION_ID": KARNAK},
                               state_store=store, jira=self.jira("10046"))
        self.assertEqual(ctx.exception.code, "not-orchestrator")

    def test_a_ruling_is_appended_and_the_ticket_goes_back_to_ready(self):
        j = self.jira("10046")
        with mock.patch("agent.execution.jira_sync._move") as move:
            out = ticket_ruling.rule("KAN-9", "Use the second option.", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                     state_store=store, jira=j, today="2026-10-16 10:00")
        self.assertEqual((out["status"], out["moved_to_ready"]), ("ruled", True))
        text = j.update_issue.call_args.args[1]["description"]["adf"]
        self.assertTrue(text.startswith("GOAL: x\n\nORCHESTRATOR RULING (2026-10-16 10:00)\n"))
        self.assertTrue(text.endswith("Use the second option."))
        self.assertEqual(move.call_args.args[:2], ("KAN-9", "10008"))

    def test_a_ready_ticket_gets_the_text_without_a_move_and_other_statuses_are_refused(self):
        j = self.jira("10008", "Ready")
        with mock.patch("agent.execution.jira_sync._move") as move:
            out = ticket_ruling.rule("KAN-9", "ok", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                     state_store=store, jira=j)
        self.assertFalse(out["moved_to_ready"])
        move.assert_not_called()
        for sid, name in (("10007", "Done"), ("10000", "To Do"), ("10044", "Self-review")):
            with self.assertRaises(ticket_ruling.Refused) as ctx:
                ticket_ruling.rule("KAN-9", "ok", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                   state_store=store, jira=self.jira(sid, name))
            self.assertEqual(ctx.exception.code, "status-not-allowed")

    def test_an_empty_or_huge_ruling_is_refused(self):
        for text in ("  ", "x" * (ticket_ruling.MAX_TEXT + 1)):
            with self.assertRaises(ticket_ruling.Refused):
                ticket_ruling.rule("KAN-9", text, env={"CLAUDE_CODE_SESSION_ID": ORCH},
                                   state_store=store, jira=self.jira("10046"))


if __name__ == "__main__":
    unittest.main()
