import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from agent.execution import decision_gate as dg, dispatch_brief as db, exhaustion as ex   # noqa: E402

LIMIT = ("Running-app AR/RTL + Dark check could not be run: Codex cannot switch locale or theme "
         "without writing live account prefs. EN/Light passed.")
DEFECT = "The retry button is missing and the screen shows a raw exception after tapping Try again."
OK = {"status": "pass", "detail": "ok"}


class ExhaustionTests(unittest.TestCase):
    def results(self, qa=LIMIT, **extra):
        return dict({"C1": OK, "C2": OK, "C3": OK, "QA": {"status": "fail", "detail": qa}}, **extra)

    def test_only_a_lone_failing_qa_check_is_eligible(self):
        self.assertEqual(ex.eligible(self.results()), LIMIT)
        self.assertIsNone(ex.eligible(self.results(C2={"status": "fail", "detail": "x"})))
        self.assertIsNone(ex.eligible(self.results(C2={"status": "pending-judge"})))
        self.assertIsNone(ex.eligible({"C1": OK, "QA": OK}))

    def test_the_fallback_gate_accepts_a_limit_and_never_a_defect(self):
        cfg = {"gate": "fake"}
        self.assertEqual(dg.exhaustion_verdict(LIMIT, cfg=cfg)["verdict"], "accept")
        self.assertEqual(dg.exhaustion_verdict(DEFECT, cfg=cfg)["verdict"], "return")
        self.assertEqual(dg.exhaustion_verdict("it looked fine", cfg=cfg)["verdict"], "return")

    def test_a_defect_wording_beats_a_confident_model(self):
        with mock.patch.object(dg.JevExhaustionGate, "classify",
                               return_value={"choice": "coverage_limit", "confidence": 0.99, "gate": "jev"}):
            self.assertEqual(dg.exhaustion_verdict(DEFECT, cfg={"gate": "jev"})["verdict"], "return")

    def test_an_unavailable_gate_falls_back_to_the_strict_table(self):
        with mock.patch.object(dg.JevExhaustionGate, "classify",
                               side_effect=dg.Refused("decision-gate-unavailable", "no key")):
            out = dg.exhaustion_verdict(LIMIT, cfg={"gate": "jev"})
        self.assertEqual(out["verdict"], "accept")
        self.assertIn("fake-fallback", out["gate"])

    def test_decide_closes_the_ticket_and_writes_the_unverified_part(self):
        jira = mock.Mock()
        with mock.patch("agent.execution.jira_sync.on_accepted", return_value={"status": "ok"}) as acc, \
                mock.patch("agent.execution.jira_sync._client", return_value=jira), \
                mock.patch("agent.execution.jira_sync._note"), \
                mock.patch("agent.execution.pm_ledger.add") as ledger:
            out = ex.decide({"jira_key": "KAN-602", "dispatch_id": "d"}, self.results(),
                            gate=lambda r: {"verdict": "accept", "reason": "coverage-limit", "gate": "jev"})
        self.assertTrue(out["accepted"])
        self.assertTrue(acc.call_args.args[1].startswith("ACCEPTED"))
        self.assertIn("NOT verified", jira.add_comment.call_args.args[1])
        ledger.assert_called_once()

    def test_a_defect_is_left_for_the_orchestrator(self):
        out = ex.decide({"jira_key": "KAN-1", "dispatch_id": "d"}, self.results(qa=DEFECT),
                        gate=lambda r: dg.exhaustion_verdict(r, cfg={"gate": "fake"}))
        self.assertFalse(out["accepted"])


class BriefChecksTests(unittest.TestCase):
    def test_a_compound_run_check_is_split_and_loose_pass_text_is_read_as_exit_0(self):
        checks = db._normalise_run_checks([
            {"id": "C1", "kind": "run", "what": "flutter analyze --no-pub --no-fatal-infos and flutter test test/a",
             "pass": "both exit 0, logs attached"},
            {"id": "C2", "kind": "judge", "what": "looks right", "pass": "reviewer can reproduce"}])
        self.assertEqual([(c["id"], c["what"], c["pass"]) for c in checks],
                         [("C1", "flutter analyze --no-pub --no-fatal-infos", "exit 0"),
                          ("C3", "flutter test test/a", "exit 0"),
                          ("C2", "looks right", "reviewer can reproduce")])

    def test_a_pass_text_that_allows_failure_is_not_read_as_exit_0(self):
        c = db._normalise_run_checks([{"id": "C1", "kind": "run", "what": "flutter test", "pass": "exit 0 or non-zero"}])
        self.assertNotEqual(c[0]["pass"], "exit 0")


if __name__ == "__main__":
    unittest.main()
