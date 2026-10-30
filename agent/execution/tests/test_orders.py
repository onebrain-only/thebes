#!/usr/bin/env python3
"""D-044: only the CEO's own words authorise creating tickets and merging into Alpha; every act is
on the ledger; the orchestrator answers from a fact block, not from memory."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

from agent.state import store, validate                              # noqa: E402
from agent.execution import orders                                   # noqa: E402
import ceo_prompt_hook                                               # noqa: E402
import order_gate                                                    # noqa: E402

ORCH = "c0000000-0000-4000-8000-000000000001"
TEAM = "c0000000-0000-4000-8000-000000000002"
HOME = "/tmp"
CREATE = "mcp__claude_ai_Atlassian_Rovo__createJiraIssue"


class OrdersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("luxor", "claude", TEAM, HOME, "ceo")

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------ orders
    def test_words_the_ceo_never_typed_are_not_an_order(self):
        orders.record_message(ORCH, "شغّل التيمز على اللي في Ready")
        with self.assertRaises(orders.OrderRefused) as ctx:
            orders.grant("create", "PM ruling + CPO ranking already adopted by the orchestrator")
        self.assertEqual(ctx.exception.code, "no-such-ceo-order")
        with self.assertRaises(orders.OrderRefused):
            orders.grant("create", "شغّل")                  # too short to be a quote
        self.assertEqual(orders.open_grants(), [])

    def test_wakes_notifications_and_other_sessions_are_never_ceo_messages(self):
        for text in ("THEBES_WAKE: review KAN-1", "<task-notification>done</task-notification>",
                     "Another Claude session sent a message: create the Epic",
                     "Thebes restarted. Resume.", "[Image #1]", "   "):
            self.assertIsNone(orders.record_message(ORCH, text), text)
        self.assertEqual(orders.messages(), [])

    def test_a_create_order_counts_down_and_expires(self):
        now = time.time()
        orders.record_message(ORCH, "اعمل تذكرتين للـ recurring games", now=now)
        g = orders.grant("create", "اعمل تذكرتين", count=2, now=now)
        self.assertEqual(g["message_ref"], orders.messages()[0]["id"])
        self.assertTrue(orders.require("create", now=now))
        self.assertTrue(orders.require("create", now=now))
        with self.assertRaises(orders.OrderRefused):
            orders.require("create", now=now)
        orders.grant("create", "اعمل تذكرتين", count=1, now=now)
        self.assertIsNone(orders.covering("create", now=now + orders.GRANT_TTL + 1), "expired")

    def test_an_old_message_is_not_an_order_today(self):
        then = time.time() - orders.MESSAGE_WINDOW - 60
        orders.record_message(ORCH, "ادمج KAN-700 على Alpha", now=then)
        with self.assertRaises(orders.OrderRefused):
            orders.grant("merge-alpha", "ادمج KAN-700 على Alpha", keys=["KAN-700"])

    def test_merge_orders_name_tickets_or_say_all_reviewed(self):
        orders.record_message(ORCH, "ادمج KAN-700 و KAN-704 على Alpha")
        g = orders.grant("merge-alpha", "ادمج KAN-700 و KAN-704", keys=["kan-704", "KAN-700"])
        self.assertEqual(g["keys"], ["KAN-700", "KAN-704"])
        self.assertIsNone(orders.covering("merge-alpha", "KAN-706"))
        orders.consume("merge-alpha", "KAN-700")
        self.assertIsNone(orders.covering("merge-alpha", "KAN-700"), "used once")
        self.assertTrue(orders.covering("merge-alpha", "KAN-704"))
        with self.assertRaises(orders.OrderRefused):
            orders.grant("merge-alpha", "ادمج KAN-700 و KAN-704", keys=[])
        orders.record_message(ORCH, "ادمج كل اللي عدّى الريفيو")
        orders.grant("merge-alpha", "كل اللي عدّى الريفيو", keys=orders.ALL_REVIEWED)
        orders.consume("merge-alpha", "KAN-706")
        self.assertTrue(orders.covering("merge-alpha", "KAN-999"), "all-reviewed is not used up")

    def test_every_grant_is_on_the_ledger_with_the_ceos_words(self):
        orders.record_message(ORCH, "اعمل Epic للـ recurring games")
        g = orders.grant("create", "اعمل Epic للـ recurring games")
        line = orders.recent(1)[0]
        self.assertEqual((line["action"], line["order_ref"]), ("grant", g["id"]))
        self.assertIn("recurring games", orders.fmt_action(line))

    # ------------------------------------------------------------ gate
    def gate(self, tool, sid=ORCH, event="PreToolUse", **tool_input):
        return order_gate.handle({"session_id": sid, "hook_event_name": event, "tool_name": tool,
                                  "tool_input": tool_input, "tool_response": tool_input.pop(
                                      "_response", None)})

    def test_create_jira_issue_is_denied_without_an_order_and_allowed_once_with_one(self):
        out = self.gate(CREATE, summary="Recurring games Epic")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("CEO's explicit order", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(self.gate("mcp__atlassian__createJiraIssue", sid=TEAM)
                         ["hookSpecificOutput"]["permissionDecision"], "deny", "teams too")
        orders.record_message(ORCH, "اعمل تذكرة للـ recurring games")
        orders.grant("create", "اعمل تذكرة للـ recurring games")
        self.assertIsNone(self.gate(CREATE, summary="Recurring games"))
        self.gate(CREATE, event="PostToolUse", summary="Recurring games",
                  _response={"key": "KAN-710"})
        self.assertEqual(orders.recent(1)[0]["key"], "KAN-710")
        self.assertEqual(self.gate(CREATE)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_shell_create_issue_is_gated_like_the_tool(self):
        out = self.gate("Bash", command="python3 -c 'from agent.integrations.jira import J; "
                                        "J().create_issue(\"KAN\", \"x\", \"y\")'")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_an_unbound_session_is_the_ceo_and_is_not_gated(self):
        self.assertIsNone(self.gate(CREATE, sid="someone-else"))

    def test_a_push_to_alpha_needs_an_order_or_an_open_integration(self):
        push = "git -C Dabbler/dabbler-code push origin integrate-alpha:Alpha"
        self.assertEqual(self.gate("Bash", command=push)["hookSpecificOutput"]
                         ["permissionDecision"], "deny")
        self.assertIsNone(self.gate("Bash", command="git -C Dabbler/dabbler-code push origin "
                                                    "alpha-luxor"), "team branches are free")
        orders.record_message(ORCH, "ادمج KAN-700 على Alpha")
        orders.grant("merge-alpha", "ادمج KAN-700", keys=["KAN-700"])
        self.assertIsNone(self.gate("Bash", command=push))

    def test_order_records_cannot_be_written_by_hand(self):
        for tool, args in (("Write", {"file_path": orders.path("grants")}),
                           ("Edit", {"file_path": orders.path("messages")}),
                           ("Bash", {"command": "echo '{}' >> %s" % orders.path("messages")}),
                           ("Bash", {"command": "python3 - <<< 'open(\"order-grants.json\",\"w\")'"})):
            out = self.gate(tool, **args)
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny", (tool, args))
        self.assertIsNone(self.gate("Bash", command="tail -5 %s" % orders.path("ledger")))

    # ------------------------------------------------------------ prompt hook
    def test_the_orchestrator_gets_facts_and_only_ceo_text_is_kept(self):
        out = ceo_prompt_hook.handle({"session_id": ORCH, "hook_event_name": "UserPromptSubmit",
                                      "prompt": "مين ماسك KAN-693؟"})
        ctx = out["hookSpecificOutput"]["additionalContext"]
        for part in ("<thebes-facts", "RULE (D-044)", "TEAMS", "luxor", "OPEN CEO ORDERS",
                     "recorded as CEO message"):
            self.assertIn(part, ctx)
        self.assertEqual([m["text"] for m in orders.messages()], ["مين ماسك KAN-693؟"])
        out = ceo_prompt_hook.handle({"session_id": ORCH, "hook_event_name": "UserPromptSubmit",
                                      "prompt": "THEBES_WAKE: x"})
        self.assertNotIn("recorded as CEO message", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(len(orders.messages()), 1)
        self.assertIsNone(ceo_prompt_hook.handle({"session_id": TEAM, "prompt": "x",
                                                  "hook_event_name": "UserPromptSubmit"}))

    def test_compactions_of_the_orchestrator_are_counted_per_session(self):
        for _ in range(3):
            ceo_prompt_hook.handle({"session_id": ORCH, "hook_event_name": "PreCompact"})
        ceo_prompt_hook.handle({"session_id": TEAM, "hook_event_name": "PreCompact"})
        self.assertEqual(ceo_prompt_hook.read_count(store)["count"], 3)

    def test_the_fact_block_is_local_and_fast(self):
        from agent.state import facts
        t = time.time()
        block = facts.build()
        self.assertLess(time.time() - t, 2.0)
        self.assertIn("luxor", block)


if __name__ == "__main__":
    unittest.main()
