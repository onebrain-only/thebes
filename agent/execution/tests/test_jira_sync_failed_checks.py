import unittest
from unittest import mock

from agent.execution import jira_sync as js


class FailedChecksKeepOperationsTicketOpenTests(unittest.TestCase):
    def finish(self, text):
        rec = {"jira_key": "KAN-871", "outcome": "completed", "target_seat_id": "memphis"}
        jira = mock.Mock()
        with mock.patch.object(js, "_operations_only", return_value=True), \
             mock.patch.object(js, "_client", return_value=jira), \
             mock.patch.object(js, "_move", return_value={"moved": True}) as move, \
             mock.patch.object(js, "_note"), mock.patch.object(js, "_team_name", return_value="memphis"):
            js.on_finish(rec, text, state_store=mock.Mock())
        return move, jira

    def test_a_team_that_marks_its_own_check_fail_is_not_moved_to_done(self):
        move, jira = self.finish("parked\nVERIFY\nbranch: x\nC1: FAIL — not run: parked")
        move.assert_not_called()
        self.assertIn("NOT moved", jira.add_comment.call_args[0][1])

    def test_all_pass_still_goes_to_done(self):
        move, _ = self.finish("VERIFY\nC1: PASS — md5 equals Alpha")
        move.assert_called_once()


if __name__ == "__main__":
    unittest.main()
