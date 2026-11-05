import unittest
from unittest import mock

from agent.execution import conversation_dispatch as cd
from agent.execution import decision_gate as dg


class FakeStore:
    def __init__(self, reqs, live):
        self.reqs, self.live, self.updated = reqs, live, []

    def read_all(self, kind):
        return list(self.reqs) if kind == "decision_request" else []

    def read(self, kind, rid):
        if kind == "decision_request":
            return next(r for r in self.reqs if r["decision_request_id"] == rid)
        return {"dispatch_id": rid, "jira_key": "KAN-1", "origin_provider": "claude"}

    def update(self, kind, rid, rev, changes):
        self.updated.append((rid, changes))

    def active_role_session(self, seat):
        return {"session_id": self.live[seat]} if seat in self.live else None


def req(rid, asker, seat, ref):
    return {"decision_request_id": rid, "asker_session_id": asker, "asker_seat_id": seat,
            "origin_dispatch_id": "cdispatch-o", "origin_thread_id": "t", "pending_resume_ref": ref,
            "revision": 1}


class RetryResumesRebindTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        self.f.write("go")
        self.f.close()

    def run_it(self, st, sent):
        def bound(sid, state_store=None):
            if sid == "old":
                raise cd.Refused("target-session-not-bound", "gone")
        with mock.patch.object(cd, "open_work_for", return_value=[]), \
             mock.patch.object(cd, "target_binding", side_effect=bound):
            return dg.retry_resumes(state_store=st, dispatch=lambda text, sid, **k: sent.append(sid) or
                                    {"dispatch_id": "cdispatch-new"})

    def test_answer_for_a_restarted_team_goes_to_its_current_session(self):
        st = FakeStore([req("dreq-a", "old", "memphis", self.f.name)], {"memphis": "new"})
        sent = []
        out = self.run_it(st, sent)
        self.assertEqual(sent, ["new"])
        self.assertEqual([o["action"] for o in out], ["answer-delivered"])

    def test_one_unsendable_answer_does_not_hold_back_the_next(self):
        st = FakeStore([req("dreq-a", "old", "ghost", self.f.name),
                        req("dreq-b", "live", "luxor", self.f.name)], {"luxor": "live"})
        sent = []
        out = self.run_it(st, sent)
        self.assertEqual(sent, ["live"])
        self.assertEqual([o["action"] for o in out], ["answer-delivered"])


if __name__ == "__main__":
    unittest.main()
