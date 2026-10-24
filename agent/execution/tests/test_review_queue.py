#!/usr/bin/env python3
"""The Codex reviewer's queue (D-043 draft). Fakes only."""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, validate                               # noqa: E402
from agent.execution import review_queue as rq, review_app, verify, jira_sync    # noqa: E402

ORCH = "0eeeeeee-9999-7000-8000-00000000000e"
LUXOR = "0bbbbbbb-9999-7000-8000-00000000000b"
HOME = "/stable/home"
SHA = "a" * 40


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        os.environ["CODEX_THREAD_ID"] = "thread-A"
        self.paths = ["supabase/migrations/1.sql", "test/x_test.dart"]       # not a UI change
        self._cp = rq.changed_paths
        rq.changed_paths = lambda branch, sha, runner=None, key=None: self.paths
        rq._FILES.clear()
        self.heads = {}
        self._bh = rq.branch_head
        rq.branch_head = lambda branch, runner=None, clock=None: self.heads.get(branch)   # no network

    def tearDown(self):
        rq.branch_head = self._bh
        rq.changed_paths = self._cp
        os.environ.pop("CODEX_THREAD_ID", None)
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def judge_root(self, key="KAN-9"):
        did = store.new_id("conversation_dispatch")
        results = {"C1": {"status": "pass", "what": "analyze"},
                   "C2": {"status": "pending-judge", "what": "chips equal height",
                          "by": "judge", "cycle": 1},
                   "C3": {"status": "pending-judge", "what": "same in Arabic", "by": "judge",
                          "cycle": 1}}
        store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": LUXOR, "target_seat_id": "luxor",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "completed", "delivery_status": "DELIVERED", "outcome": "completed",
            "result_ref": "/x", "result_sha256": "0" * 64, "outcome_at": store.now(),
            "attested_delivery_id": did, "reported_session_id": LUXOR, "jira_key": key, "branch": "alpha-luxor",
            "checks": [{"id": "C1", "kind": "run", "what": "flutter analyze", "pass": "exit 0"},
                       {"id": "C2", "kind": "judge", "what": "chips equal height",
                        "pass": "screenshot en light"},
                       {"id": "C3", "kind": "judge", "what": "same in Arabic",
                        "pass": "screenshot ar"}],
            "verification": {"verdict": "needs_judge", "cycle": 1, "branch": "alpha-luxor",
                             "sha": SHA, "results": results}}, rid=did)
        return did

    def test_a_judge_item_is_offered_once_and_only_to_the_claimant(self):
        did = self.judge_root()
        item = rq.next_item(with_qa=False)
        self.assertEqual((item["kind"], item["ticket"], item["dispatch_id"]), ("judge", "KAN-9", did))
        self.assertEqual([c["id"] for c in item["checks"]], ["C2", "C3"])
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        self.assertIsNone(rq.next_item(with_qa=False), "claimed by thread A: nobody else gets it")
        os.environ["CODEX_THREAD_ID"] = "thread-A"
        self.assertEqual(rq.next_item(with_qa=False)["item_id"], item["item_id"],
                         "the holder asking again gets the same item")

    def test_a_stale_claim_is_offered_again(self):
        self.judge_root()
        item = rq.next_item(with_qa=False)
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        self.assertTrue(rq.claim(item["item_id"], now=__import__("time").time() + rq.CLAIM_SECONDS + 5))
        self.assertEqual(rq.holder(item["item_id"]), "thread-B")

    def test_only_the_claimant_can_submit_and_evidence_is_required(self):
        self.judge_root()
        item = rq.next_item(with_qa=False)
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        with self.assertRaises(rq.Refused) as ctx:
            rq.submit_judge(item["item_id"], ["C2", "C3"], {}, {}, "looked", state_store=store)
        self.assertEqual(ctx.exception.code, "not-your-claim")
        os.environ["CODEX_THREAD_ID"] = "thread-A"
        with self.assertRaises(rq.Refused) as ctx:
            rq.submit_judge(item["item_id"], ["C2", "C3"], {}, {}, "  ", state_store=store)
        self.assertEqual(ctx.exception.code, "evidence-required")

    def test_pass_and_skip_close_the_checks_and_the_item_is_done(self):
        did = self.judge_root()
        item = rq.next_item(with_qa=False)
        with mock.patch.object(jira_sync, "on_verified", return_value=None):
            out = rq.submit_judge(item["item_id"], ["C2"], {}, {"C3": "needs-write"},
                                  "opened Home en/light, screenshot x.png", state_store=store,
                                  jira=mock.Mock(), dispatcher=mock.Mock(), launcher=mock.Mock())
        self.assertEqual(out["status"], "recorded")
        res = store.read("conversation_dispatch", did)["verification"]["results"]
        self.assertEqual((res["C2"]["status"], res["C2"]["by"]), ("pass", "reviewer"))
        self.assertIn("SKIPPED", res["C3"]["detail"])
        self.assertIsNone(rq.next_item(with_qa=False), "a settled item is never offered again")
        self.assertTrue(rq.is_done(item["item_id"]))

    def test_an_environment_failure_spends_no_fix_cycle_and_goes_nowhere(self):
        """Blank canvas, no sim, no clipboard: the review environment failed, not the team."""
        from agent.execution import watchdog
        did = self.judge_root()
        item = rq.next_item(with_qa=False)
        dispatcher = mock.Mock()
        with mock.patch.object(watchdog, "_alert") as alert:
            rq.submit_judge(item["item_id"], ["C2"], {}, {}, "opened Home, screenshot x.png",
                            state_store=store, jira=mock.Mock(), dispatcher=dispatcher,
                            launcher=mock.Mock(), environment={"C3": "no clipboard on the simulator"})
        ver = store.read("conversation_dispatch", did)["verification"]
        self.assertEqual((ver["verdict"], ver["cycle"]), ("error", 1), "no cycle is charged")
        self.assertEqual(ver["results"]["C3"]["status"], "error")
        self.assertTrue(ver["results"]["C3"]["detail"].startswith("ENVIRONMENT"))
        dispatcher.assert_not_called()                     # nothing goes back to the team
        alert.assert_called_once()

    def test_an_item_whose_ticket_is_already_done_is_dropped(self):
        """Live 2026-10-13: a stale KAN-438 item the PO had closed was reviewed and failed."""
        self.judge_root("KAN-9")
        jira = mock.Mock()
        jira.get_issue.return_value = {"status": "Done"}
        self.assertEqual(rq.candidates(jira=jira, with_qa=False), [])
        self.judge_root("KAN-10")                 # the Done one is marked finished for good
        jira.get_issue.return_value = {"status": "Self-review"}
        jira.get_comments.return_value = [{"created": "t", "body": "PO accepted AC1-6"}]
        items = rq.candidates(jira=jira, with_qa=False)
        self.assertEqual(items[0]["ticket_status"], "Self-review")
        self.assertEqual(items[0]["latest_comments"][0]["text"], "PO accepted AC1-6")

    # -- the reviewer asks the orchestrator ---------------------------------------------
    def ask_one(self):
        self.judge_root("KAN-9")
        item = rq.next_item(with_qa=False)
        return item, rq.ask(item["item_id"], "Does AC3 mean the Arabic count too?")["question_id"]

    def test_a_question_reaches_the_orchestrator_and_the_answer_comes_back_through_wait(self):
        from agent.execution import inbox
        item, qid = self.ask_one()
        shown = [i for i in inbox.collect(ORCH, state_store=store) if i["kind"] == "reviewer_question"]
        self.assertEqual((len(shown), shown[0]["question_id"], shown[0]["ticket"]), (1, qid, "KAN-9"))
        self.assertIn("review_queue answer %s" % qid, shown[0]["how"])
        self.assertEqual([i for i in inbox.collect(ORCH, state_store=store)
                          if i["kind"] == "reviewer_question"], [], "shown once")
        self.assertIsNone(rq.next_answer(), "not answered yet")
        rq.answer(qid, "Yes: both languages.", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store)
        got = rq.next_answer()
        self.assertEqual((got["kind"], got["item_id"], got["answer"], got["expired"]),
                         ("answer", item["item_id"], "Yes: both languages.", False))
        self.assertIsNone(rq.next_answer(), "delivered once")
        self.assertEqual(rq.holder(item["item_id"]), "thread-A", "still the reviewer's item")

    def test_only_the_orchestrator_answers_and_only_once(self):
        _, qid = self.ask_one()
        with self.assertRaises(rq.Refused) as ctx:
            rq.answer(qid, "pass it", env={"CLAUDE_CODE_SESSION_ID": LUXOR}, state_store=store)
        self.assertEqual(ctx.exception.code, "not-orchestrator")
        rq.answer(qid, "ok", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store)
        with self.assertRaises(rq.Refused):
            rq.answer(qid, "again", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store)

    def test_a_reviewer_can_only_ask_about_an_item_it_holds_and_one_at_a_time(self):
        self.judge_root("KAN-9")
        item = rq.next_item(with_qa=False)
        os.environ["CODEX_THREAD_ID"] = "thread-B"
        with self.assertRaises(rq.Refused):
            rq.ask(item["item_id"], "can I look?")
        os.environ["CODEX_THREAD_ID"] = "thread-A"
        rq.ask(item["item_id"], "first")
        with self.assertRaises(rq.Refused) as ctx:
            rq.ask(item["item_id"], "second")
        self.assertEqual(ctx.exception.code, "question-open")

    def test_an_unanswered_question_expires_and_keeps_the_claim_alive_meanwhile(self):
        import time as _t
        item, qid = self.ask_one()
        later = _t.time() + rq.QUESTION_TTL / 2
        self.assertIsNone(rq.next_answer(later))
        self.assertGreater(rq._read(os.path.join(rq._dir("claims"), rq._safe(item["item_id"])))["at"],
                           later - 1, "claim refreshed while the question is open")
        got = rq.next_answer(_t.time() + rq.QUESTION_TTL + 5)
        self.assertTrue(got["expired"])
        self.assertIsNone(got["answer"])
        self.assertIn("needs-answer", got["next"])

    # -- the review channel (CEO 2026-10-13): Codex by default, Claude QA on his explicit order ----
    def as_claude(self, sid="edfu-session"):
        os.environ.pop("CODEX_THREAD_ID", None)
        os.environ["CLAUDE_CODE_SESSION_ID"] = sid

    def tearDownClaude(self):
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)

    def test_codex_is_the_default_and_the_other_channel_stands_by(self):
        self.judge_root("KAN-9")
        self.assertEqual(rq.get_channel(), "codex")
        self.as_claude()
        try:
            self.assertIsNone(rq.next_item(with_qa=False), "Claude QA takes no work while Codex reviews")
            self.assertTrue(rq.wait(5, sleep=lambda s: None)["standby"])
        finally:
            self.tearDownClaude()
            os.environ["CODEX_THREAD_ID"] = "thread-A"
        self.assertEqual(rq.next_item(with_qa=False)["kind"], "judge")

    def test_only_the_orchestrator_switches_and_only_with_the_ceos_words(self):
        for env, by, code in (({"CLAUDE_CODE_SESSION_ID": LUXOR}, "x", "not-orchestrator"),
                              ({"CLAUDE_CODE_SESSION_ID": ORCH}, " ", "order-required"),
                              ({"CLAUDE_CODE_SESSION_ID": ORCH}, "go", None)):
            if code:
                with self.assertRaises(rq.Refused) as ctx:
                    rq.set_channel("claude", by, env=env, state_store=store, notify=False)
                self.assertEqual(ctx.exception.code, code)
        with self.assertRaises(rq.Refused):
            rq.set_channel("gemini", "go", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store, notify=False)
        self.assertEqual(rq.get_channel(), "codex")

    def test_switching_to_claude_releases_codex_claims_and_hands_the_queue_to_edfu(self):
        self.judge_root("KAN-9")
        item = rq.next_item(with_qa=False)                       # Codex thread-A holds it
        out = rq.set_channel("claude", "run QA from Claude Code", env={"CLAUDE_CODE_SESSION_ID": ORCH},
                             state_store=store, notify=False)
        self.assertEqual((out["from"], out["to"], out["released_claims"]), ("codex", "claude", [item["item_id"]]))
        self.assertIsNone(rq.next_item(with_qa=False), "Codex now stands by")
        self.as_claude()
        try:
            got = rq.next_item(with_qa=False)
            self.assertEqual(got["item_id"], item["item_id"])
            self.assertTrue(rq.holder(got["item_id"]).startswith("claude:"))
            with mock.patch.object(jira_sync, "on_verified", return_value=None):
                done = rq.submit_judge(got["item_id"], ["C2", "C3"], {}, {}, "checked in Chrome",
                                       state_store=store, jira=mock.Mock(), dispatcher=mock.Mock(),
                                       launcher=mock.Mock())
            self.assertEqual(done["status"], "recorded")
        finally:
            self.tearDownClaude()

    def test_the_switch_wakes_edfu_to_start_and_to_stop(self):
        store.bind_role_session("edfu", "claude", "0eeeeeee-0000-7000-8000-0000000000e1", HOME, "ceo")
        sent = []
        fake = lambda text, sid, **kw: sent.append((sid, text)) or {"dispatch_id": "cdispatch-x"}
        out = rq.set_channel("claude", "go", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                             dispatch=fake)
        self.assertEqual(out["edfu"]["status"], "notified")
        self.assertIn("review_queue wait", sent[0][1])
        rq.set_channel("codex", "back to codex", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store,
                       dispatch=fake)
        self.assertIn("stop your review loop", sent[1][1].lower())

    def test_a_review_nobody_holds_for_half_an_hour_is_reported_once_and_never_switched(self):
        from agent.execution import inbox
        import time as _t
        self.judge_root("KAN-9")
        self.assertEqual(rq.stalled(now=_t.time()), [], "fresh")
        late = _t.time() + rq.STALL_SECONDS + 60
        self.assertEqual([i["ticket"] for i in rq.stalled(now=late)], ["KAN-9"])
        got = [i for i in inbox.collect(ORCH, state_store=store, now=late) if i["kind"] == "review_stalled"]
        self.assertEqual((len(got), got[0]["tickets"]), (1, ["KAN-9"]))
        self.assertIn("Do NOT switch", got[0]["how"])
        self.assertEqual([i for i in inbox.collect(ORCH, state_store=store, now=late)
                          if i["kind"] == "review_stalled"], [], "once")
        self.assertEqual(rq.get_channel(), "codex", "the system never switches by itself")

    # -- waking a headless reviewer (CEO 2026-10-17) ------------------------------------
    def headless(self, thread="01a0f777-d0e4-7000-8000-000000000001"):
        store.create("codex_conversation", {"thread_id": thread, "runtime_id": "thebes",
                                            "label": "reviewer-headless", "registered_by": "ceo",
                                            "status": "active", "runtime_socket_path": "/x",
                                            "bootstrap_event_id": None, "bootstrap_sha256": None},
                     rid=thread)
        rq.set_reviewer("headless", thread, state_store=store)
        return thread

    def test_a_desktop_reviewer_is_never_nudged(self):
        self.judge_root("KAN-9")
        self.assertEqual(rq.reviewer_config()["mode"], "desktop")
        self.assertEqual(rq.nudge(state_store=store, enqueue_fn=lambda *a, **k: self.fail("woke")), [])

    def test_headless_mode_needs_a_thread_thebes_owns(self):
        with self.assertRaises(rq.Refused) as ctx:
            rq.set_reviewer("headless", "01a0f777-d0e4-7000-8000-00000000dead", state_store=store)
        self.assertEqual(ctx.exception.code, "thread-not-registered")

    def test_a_waiting_item_wakes_the_headless_reviewer_once_and_only_when_it_is_free(self):
        thread = self.headless()
        self.judge_root("KAN-9")
        sent, drains = [], []
        enq = lambda t, kind, text, **kw: sent.append((t, kind, text, kw["event_id"]))
        jira = mock.Mock(); jira.get_issue.return_value = {"status": "Self-review"}
        jira.get_comments.return_value = []; jira.search_issues.return_value = []
        out = rq.nudge(state_store=store, jira=jira, enqueue_fn=enq, launcher=drains.append, now=1000.0)
        self.assertEqual([o["action"] for o in out], ["review-nudged"])
        self.assertEqual((sent[0][0], sent[0][1]), (thread, "alert"))
        self.assertIn("review_queue next", sent[0][2])
        self.assertIn("do NOT run `review_queue wait`", sent[0][2])
        self.assertEqual(drains, [thread])
        self.assertEqual(rq.nudge(state_store=store, jira=jira, enqueue_fn=enq, launcher=drains.append,
                                  now=1100.0), [], "not again for the same item")
        self.assertEqual(len(sent), 1)
        again = rq.nudge(state_store=store, jira=jira, enqueue_fn=enq, launcher=drains.append,
                         now=1000.0 + rq.RENUDGE_SECONDS + 5)
        self.assertEqual([o["action"] for o in again], ["review-nudged"], "a quiet reviewer is woken again")

    def test_it_waits_while_a_turn_is_running_and_ignores_a_dead_one(self):
        thread = self.headless()
        self.judge_root("KAN-9")
        ev = store.create("codex_turn_event", {
            "event_id": "cevt-busy-1", "thread_id": thread, "event_kind": "alert", "status": "running",
            "text_ref": "/x", "seq": 1, "turn_ref": None, "response_summary": None, "error": None,
            "completed_at": None}, rid="cevt-busy-1")
        jira = mock.Mock(); jira.get_issue.return_value = {"status": "Self-review"}
        jira.get_comments.return_value = []; jira.search_issues.return_value = []
        enq = lambda *a, **k: None
        self.assertEqual(rq.nudge(state_store=store, jira=jira, enqueue_fn=enq, launcher=lambda t: None), [])
        far = __import__("time").time() + rq.TURN_STALE_SECONDS + 60
        out = rq.nudge(state_store=store, jira=jira, enqueue_fn=enq, launcher=lambda t: None, now=far)
        self.assertEqual([o["action"] for o in out], ["review-nudged"])

    def test_which_changes_need_a_browser(self):
        for f in ("lib/features/social/presentation/screens/post.dart", "lib/widgets/chip.dart",
                  "lib/features/app_boot/startup_splash.dart", "ios/Runner/Info.plist",
                  "lib/l10n/app_ar.arb", "lib/core/design_system/tokens.dart"):
            self.assertTrue(rq.UI_PATH.search(f), f)
        for f in ("supabase/migrations/1.sql", "workers/messaging/load.mjs", "docs/messaging/api.yaml",
                  "test/features/x_test.dart", "lib/data/repositories/block_repository.dart",
                  "lib/features/messaging/domain/models/message.dart"):
            self.assertFalse(rq.UI_PATH.search(f), f)
        rq.changed_paths = self._cp
        self.assertTrue(rq.needs_browser("alpha-x", "a" * 40, runner=lambda *a, **k: (_ for _ in ()).throw(OSError())),
                        "cannot tell: assume it must be seen")

    def test_the_headless_reviewer_never_gets_an_item_that_must_be_seen_in_the_app(self):
        thread = self.headless()
        self.judge_root("KAN-9")
        self.paths = ["lib/features/social/presentation/screens/post.dart"]
        rq._FILES.clear()
        jira = mock.Mock(); jira.get_issue.return_value = {"status": "Self-review"}
        jira.get_comments.return_value = []; jira.search_issues.return_value = []
        self.assertTrue(rq.candidates(jira=jira, with_qa=False)[0]["needs_browser"])
        os.environ["CODEX_THREAD_ID"] = thread
        self.assertTrue(rq.is_headless_thread())
        self.assertIsNone(rq.next_item(jira=jira, with_qa=False), "headless leaves UI work alone")
        self.assertEqual(rq.nudge(state_store=store, jira=jira,
                                  enqueue_fn=lambda *a, **k: self.fail("woke for a UI item")), [])
        os.environ["CODEX_THREAD_ID"] = "thread-A"                 # the Desktop reviewer
        self.assertEqual(rq.next_item(jira=jira, with_qa=False)["ticket"], "KAN-9")

    def test_a_held_item_and_the_claude_channel_are_left_alone(self):
        self.headless()
        self.judge_root("KAN-9")
        rq.next_item(with_qa=False)                          # thread-A holds it
        jira = mock.Mock(); jira.get_issue.return_value = {"status": "Self-review"}
        jira.get_comments.return_value = []; jira.search_issues.return_value = []
        fail = lambda *a, **k: self.fail("woke")
        self.assertEqual(rq.nudge(state_store=store, jira=jira, enqueue_fn=fail), [])
        rq.set_channel("claude", "go", env={"CLAUDE_CODE_SESSION_ID": ORCH}, state_store=store, notify=False)
        self.assertEqual(rq.nudge(state_store=store, jira=jira, enqueue_fn=fail), [])

    # -- the queue is the Review column (CEO 2026-10-21) -------------------------------
    def _search(self, statuses):
        jira = mock.Mock()
        jira.get_comments.return_value = []
        raws = [{"key": k, "fields": {"updated": "2026-10-21T10:00:00.000+0000"}} for k in statuses]
        jira.search_issues.return_value = raws
        jira.normalize_issue.side_effect = lambda r: {"key": r["key"], "summary": "s",
                                                      "status": statuses[r["key"]], "description": "d"}
        return jira

    def test_the_queue_covers_every_status_of_the_review_column(self):
        for status in ("QA-Test", "Self-review", "Peer-review"):
            self.assertIn('"%s"' % status, rq.QA_JQL)
        jira = self._search({"KAN-1": "QA-Test", "KAN-2": "Self-review", "KAN-3": "Peer-review"})
        self.assertEqual(sorted(i["ticket"] for i in rq.qa_items(jira, store)), ["KAN-1", "KAN-2", "KAN-3"])

    def test_a_self_review_ticket_a_team_is_still_working_is_not_offered(self):
        self.judge_root("KAN-9")                       # KAN-9 has a finished dispatch
        real = store.read_all
        busy = {"jira_key": "KAN-5", "status": "delivered", "outcome": None}
        jira = self._search({"KAN-5": "Self-review", "KAN-6": "Self-review"})
        with mock.patch.object(store, "read_all", side_effect=lambda k: real(k) + [busy]):
            self.assertEqual([i["ticket"] for i in rq.qa_items(jira, store)], ["KAN-6"])

    # -- local review on the team's commit (CEO 2026-10-21) ---------------------------
    def test_a_qa_item_carries_the_teams_verified_commit_and_its_depth(self):
        self.judge_root("KAN-9")
        self.paths = ["lib/features/social/presentation/screens/post.dart"]
        rq._FILES.clear()
        jira = self._search({"KAN-9": "QA-Test", "KAN-8": "QA-Test"})
        items = {i["ticket"]: i for i in rq.qa_items(jira, store)}
        self.assertEqual((items["KAN-9"]["branch"], items["KAN-9"]["sha"]), ("alpha-luxor", SHA))
        self.assertEqual((items["KAN-9"]["tier"], items["KAN-9"]["platform"]), (2, "web"))
        self.assertIsNone(items["KAN-8"]["sha"], "no team record: said, not guessed")
        self.assertFalse(items["KAN-8"]["commit_resolved"])
        self.assertIn("no verified commit", items["KAN-8"]["note"])

    def _claimed_qa(self, tier):
        item_id = "qa-KAN-9@2026-10-21T10:00:00.000+0000"
        self.assertTrue(rq.claim(item_id, meta={"ticket": "KAN-9", "tier": tier, "platform": "web",
                                                "min_screenshots": {1: 0, 2: 1, 3: 2}[tier],
                                                "branch": "alpha-luxor", "sha": SHA}))
        return item_id

    def test_a_pass_on_a_screen_needs_a_screenshot_of_the_running_app(self):
        item_id = self._claimed_qa(2)
        jira = mock.Mock()
        review_app._record_render("KAN-9", SHA, True)
        with mock.patch.object(jira_sync, "_move"):
            with self.assertRaises(rq.Refused) as ctx:
                rq.submit_qa(item_id, "pass", "ok", "steps", state_store=store, jira=jira)
            self.assertEqual(ctx.exception.code, "evidence-missing")
            os.makedirs(rq.evidence_dir("KAN-9"), exist_ok=True)
            open(os.path.join(rq.evidence_dir("KAN-9"), "tc1-en-light.png"), "wb").close()
            rq.submit_qa(item_id, "pass", "ok", "steps", state_store=store, jira=jira)
        comment = jira.add_comment.call_args.args[1]
        self.assertIn("alpha-luxor at %s" % SHA[:12], comment)
        self.assertIn("app on web", comment)

    def test_a_fail_or_a_light_item_needs_no_screenshot(self):
        jira = mock.Mock()
        review_app._record_render("KAN-9", SHA, True)
        with mock.patch.object(jira_sync, "_move"):
            rq.submit_qa(self._claimed_qa(2), "fail", "button missing", "steps", state_store=store, jira=jira)
        item_id = "qa-KAN-7@x"
        rq.claim(item_id, meta={"ticket": "KAN-7", "tier": 1, "min_screenshots": 0, "sha": SHA})
        with mock.patch.object(jira_sync, "_move"):
            rq.submit_qa(item_id, "pass", "ok", "diff and tests", state_store=store, jira=jira)
        self.assertIn("diff and tests (no screen)", jira.add_comment.call_args.args[1])

    def test_a_ticket_with_a_judge_item_is_not_also_offered_as_a_qa_item(self):
        """A second item would close it without its checks."""
        self.judge_root("KAN-9")
        jira = mock.Mock()
        jira.get_issue.return_value = {"status": "QA-Test"}
        jira.get_comments.return_value = []
        raw = {"key": "KAN-9", "fields": {"updated": "2026-10-20T10:00:00.000+0000"}}
        jira.search_issues.return_value = [raw, dict(raw, key="KAN-77")]
        jira.normalize_issue.side_effect = lambda r: {"key": r["key"], "summary": "s", "status": "QA-Test", "description": "d"}
        kinds = sorted((c["kind"], c["ticket"]) for c in rq.candidates(jira=jira))
        self.assertEqual(kinds, [("judge", "KAN-9")], "KAN-77 has no branch and no sha: withheld")

    # ------------------------------------------------ every item carries branch and sha (KAN-622)
    def _no_sha(self, did, **changes):
        rec = store.read("conversation_dispatch", did)
        store.update("conversation_dispatch", did, rec["revision"],
                     dict(changes, verification={"verdict": "needs_judge", "cycle": 1, "results": {}}))

    def test_a_qa_item_without_a_verified_sha_gets_the_branch_head_and_says_so(self):
        """KAN-622: its newest dispatch had branch null and no sha, an older one named the branch."""
        did = self.judge_root("KAN-622")
        self._no_sha(did)
        self.heads["alpha-luxor"] = "b" * 40
        items = {i["ticket"]: i for i in rq.qa_items(self._search({"KAN-622": "Self-review"}), store)}
        item = items["KAN-622"]
        self.assertEqual((item["branch"], item["sha"]), ("alpha-luxor", "b" * 40))
        self.assertEqual(item["sha_from"], "branch-head")
        self.assertTrue(item["commit_resolved"])

    def test_the_branch_falls_back_to_the_teams_own_when_no_dispatch_names_one(self):
        did = self.judge_root("KAN-5")
        self._no_sha(did, branch=None)
        self.assertEqual(rq.team_branch("KAN-5"), "alpha-luxor")
        self.heads["alpha-luxor"] = "c" * 40
        self.assertEqual(rq.with_commit({"branch": None, "sha": None}, "KAN-5")["sha"], "c" * 40)

    def test_an_item_with_no_resolvable_commit_is_never_offered(self):
        self.judge_root("KAN-9")
        jira = mock.Mock()
        jira.get_issue.return_value = {"status": "QA-Test"}
        jira.get_comments.return_value = []
        raw = {"key": "KAN-31", "fields": {"updated": "2026-10-20T10:00:00.000+0000"}}
        jira.search_issues.return_value = [raw]
        jira.normalize_issue.side_effect = lambda r: {"key": r["key"], "summary": "s", "status": "QA-Test", "description": "d"}
        offered = rq.candidates(jira=jira)
        self.assertTrue(offered and all(c["branch"] and c["sha"] for c in offered))
        self.assertNotIn("KAN-31", {c["ticket"] for c in offered})

    # ------------------------------------------------ fail closed on a blank canvas
    def test_no_verdict_can_be_recorded_on_a_build_that_never_drew(self):
        jira = mock.Mock()
        review_app._record_render("KAN-9", SHA, False, "build not ready: no flt-semantics-placeholder")
        os.makedirs(rq.evidence_dir("KAN-9"), exist_ok=True)
        open(os.path.join(rq.evidence_dir("KAN-9"), "tc1.png"), "wb").close()
        with mock.patch.object(jira_sync, "_move") as move:
            for verdict in ("pass", "fail"):
                with self.assertRaises(rq.Refused) as ctx:
                    rq.submit_qa(self._claimed_qa(2), verdict, "reason", "steps", state_store=store, jira=jira)
                self.assertEqual(ctx.exception.code, "build-not-ready")
            move.assert_not_called()
        jira.add_comment.assert_not_called()

    def test_a_screen_item_on_web_needs_a_start_that_drew_for_this_sha(self):
        jira = mock.Mock()
        with mock.patch.object(jira_sync, "_move"):
            with self.assertRaises(rq.Refused) as ctx:                       # never started
                rq.submit_qa(self._claimed_qa(2), "fail", "r", "steps", state_store=store, jira=jira)
            self.assertEqual(ctx.exception.code, "build-not-ready")
            review_app._record_render("KAN-9", "d" * 40, True)               # an older commit drew
            with self.assertRaises(rq.Refused):
                rq.submit_qa(self._claimed_qa(2), "fail", "r", "steps", state_store=store, jira=jira)
            review_app._record_render("KAN-9", SHA, True)
            rq.submit_qa(self._claimed_qa(2), "fail", "r", "steps", state_store=store, jira=jira)

    def test_a_judge_item_cannot_pass_or_fail_on_a_blank_canvas_but_can_skip(self):
        did = self.judge_root("KAN-9")
        item_id = "judge-%s-c1" % did
        self.assertTrue(rq.claim(item_id))
        review_app._record_render("KAN-9", SHA, False, "build not ready")
        with self.assertRaises(rq.Refused) as ctx:
            rq.submit_judge(item_id, ["C2"], {}, {}, "looked", state_store=store)
        self.assertEqual(ctx.exception.code, "build-not-ready")
        with self.assertRaises(rq.Refused):
            rq.submit_judge(item_id, [], {"C2": "blank"}, {}, "looked", state_store=store)

    def test_a_stalled_review_gets_one_mac_notification_with_the_wake_prompt(self):
        self.judge_root("KAN-9")
        calls = []
        late = __import__("time").time() + rq.STALL_SECONDS + 60
        run = lambda argv, **kw: calls.append(argv)
        out = rq.notify_stalled(state_store=store, now=late, runner=run)
        self.assertEqual(out[0]["tickets"], ["KAN-9"])
        self.assertIn("Reviewer wake", calls[0][2])
        self.assertEqual(rq.notify_stalled(state_store=store, now=late, runner=run), [], "once")
        self.assertIn("review_queue wait", rq.wake_prompt(["KAN-9", "KAN-10"]))
        self.assertIn("KAN-9, KAN-10", rq.wake_prompt(["KAN-9", "KAN-10"]))

    def test_wait_returns_the_item_or_times_out(self):
        clock = {"t": 0.0}
        self.assertIsNone(rq.wait(10, sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
                                  clock=lambda: clock["t"]))
        self.judge_root()
        self.assertEqual(rq.wait(10, sleep=lambda s: None)["kind"], "judge")


if __name__ == "__main__":
    unittest.main()


class SendBackTests(unittest.TestCase):
    def test_a_failed_review_returns_to_its_own_lane_tagged_returned(self):
        calls = []

        class J:
            def get_issue(self, k):
                return {"status_id": "10009", "labels": ["x"]}

            def get_transitions(self, k):
                return [{"to_status_id": "10043", "id": "5"}]

            def transition_issue(self, k, t):
                calls.append(("move", t))

            def update_issue(self, k, f):
                calls.append(("labels", f["labels"]))

        class S:
            @staticmethod
            def read(kind, rid):
                return {"required_capability": "backend", "revision": 1}

            @staticmethod
            def read_all(kind):
                return []

            @staticmethod
            def observe_lifecycle(*a):
                return None

            StateError = Exception

        rq.send_back("KAN-1", J(), S)
        self.assertIn(("move", "5"), calls)
        self.assertIn(("labels", ["x", "returned"]), calls)
