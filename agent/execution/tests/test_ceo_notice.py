import os
import tempfile
import unittest

from agent.execution import ceo_notice as n


class CeoNoticeTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "ledger.json")

    def d(self, kind, key, text="", now=1000.0):
        return n.decide(kind, key, text, path=self.path, now=now)[0]

    def test_direct_answer_is_never_held(self):
        self.assertEqual(self.d("answer", "q"), "SEND")
        self.assertEqual(self.d("answer", "q"), "SEND")

    def test_status_and_nothing_are_skipped(self):
        for kind in ("status", "nothing", "again"):
            self.assertEqual(self.d(kind, "k", "same alert"), "SKIP")

    def test_action_repeats_only_after_twelve_hours(self):
        self.assertEqual(self.d("action", "dns", "do X", 0), "SEND")
        self.assertEqual(self.d("action", "dns", "do X again", 300), "SKIP")
        self.assertEqual(self.d("action", "dns", "do X again", 3600), "SKIP")
        self.assertEqual(self.d("action", "dns", "do X later", 13 * 3600), "SEND")

    def test_update_is_sent_once_per_ticket_outcome(self):
        self.assertEqual(self.d("update", "KAN-1:done", "KAN-1 done", 0), "SEND")
        self.assertEqual(self.d("update", "KAN-1:done", "KAN-1 done!", 99 * 3600), "SKIP")
        self.assertEqual(self.d("update", "KAN-2:done", "KAN-2 done", 5), "SEND")

    def test_pending_list_is_sent_when_it_changes_or_every_twelve_hours(self):
        self.assertEqual(self.d("pending", "a,b", "2 asks", 0), "SEND")
        self.assertEqual(self.d("pending", "b, a", "2 asks", 300), "SKIP", "same set")
        self.assertEqual(self.d("pending", "a,b,c", "3 asks", 600), "SEND", "a new ask")
        self.assertEqual(self.d("pending", "a,b,c", "3 asks", 600 + 11 * 3600), "SKIP")
        self.assertEqual(self.d("pending", "a,b,c", "3 asks", 600 + 12 * 3600), "SEND")
        self.assertEqual(self.d("pending", "", "", 13 * 3600), "SKIP", "nothing open")
        self.assertEqual(self.d("pending", "a", "1 ask", 13 * 3600 + 5), "SEND")

    def test_identical_text_under_another_key_is_skipped(self):
        self.assertEqual(self.d("action", "a", "same words", 0), "SEND")
        self.assertEqual(self.d("action", "b", "same  words", 60), "SKIP")


if __name__ == "__main__":
    unittest.main()
