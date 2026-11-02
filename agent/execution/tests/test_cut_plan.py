import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

from agent.execution import cut_plan as cp  # noqa: E402

SCREEN_A = "lib/features/explore/presentation/screens/events_screen.dart"
SCREEN_B = "lib/features/explore/presentation/screens/event_detail_screen.dart"


def t(i, kind="function", surfaces=None, blocked_by=None, est=40, tcs=0, component="Listings"):
    return {"id": i, "kind": kind, "component": component, "estimate_min": est, "tcs": tcs,
            "surfaces": surfaces if surfaces is not None else ["lib/x/%s.dart" % i,
                                                               "test/%s_test.dart" % i],
            "blocked_by": blocked_by or {}}


class CutPlanTests(unittest.TestCase):
    def test_a_contract_then_fan_out_is_clean(self):
        plan = {"tickets": [
            t("T0", "contract", ["lib/features/explore/domain/event.dart"]),
            t("T1", "screen", [SCREEN_A, "test/a_test.dart"], {"T0": "renders Event"}, tcs=3),
            t("T2", "screen", [SCREEN_B, "test/b_test.dart"], {"T0": "renders Event"}, tcs=2),
            t("T3"), t("T4"), t("T5")]}
        res = cp.check(plan)
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["waves"], [["T0", "T3", "T4", "T5"], ["T1", "T2"]])
        self.assertEqual(res["critical_min"], 80)

    def test_parallel_tickets_on_the_same_file_are_an_error(self):
        res = cp.check({"tickets": [t("T1", surfaces=["lib/a.dart", "test/a_test.dart"]),
                                    t("T2", surfaces=["lib/a.dart", "test/b_test.dart"])]})
        self.assertTrue(any("same files" in e for e in res["errors"]))

    def test_generated_l10n_files_never_collide(self):
        gen = "lib/l10n/app_localizations.dart"
        res = cp.check({"tickets": [t("T1", surfaces=[gen, "lib/a.dart", "test/a_test.dart"]),
                                    t("T2", surfaces=[gen, "lib/b.dart", "test/b_test.dart"])]})
        self.assertEqual(res["errors"], [])

    def test_a_link_needs_a_reason_and_an_ordering_link_is_flagged(self):
        res = cp.check({"tickets": [t("T1"), t("T2", blocked_by={"T1": ""})]})
        self.assertTrue(any("no reason" in e for e in res["errors"]))
        res = cp.check({"tickets": [t("T1"), t("T2", blocked_by={"T1": "same epic"})]})
        self.assertTrue(any("ordering-only" in w for w in res["warnings"]))

    def test_size_screens_tests_and_scenarios(self):
        res = cp.check({"tickets": [
            t("T1", est=90),
            t("T2", "screen", [SCREEN_A, SCREEN_B, "test/a_test.dart"], tcs=1),
            t("T3", surfaces=["lib/c.dart"]),
            t("T4", "screen", [SCREEN_A, "test/d_test.dart"])]})
        joined = " | ".join(res["errors"])
        for needle in ("over 50", "2 screens", "T3: no test", "T4: a screen ticket needs"):
            self.assertIn(needle, joined)

    def test_cycles_and_unassessed_surfaces(self):
        res = cp.check({"tickets": [t("T1", blocked_by={"T2": "x"}),
                                    t("T2", blocked_by={"T1": "y"})]})
        self.assertTrue(any("cycle" in e for e in res["errors"]))
        bad = t("T1")
        bad["surfaces"] = None
        self.assertTrue(any("not assessed" in e for e in cp.check({"tickets": [bad]})["errors"]))

    def test_strings_outside_a_strings_ticket_and_hotspots_warn(self):
        res = cp.check({"tickets": [t("T1", surfaces=["lib/app/app_router.dart",
                                                      "lib/l10n/app_ar.arb", "test/a_test.dart"])]},
                       hot={"lib/app/app_router.dart": 25})
        self.assertTrue(any(".arb" in w for w in res["warnings"]))
        self.assertTrue(any("hotspot" in w for w in res["warnings"]))


if __name__ == "__main__":
    unittest.main()
