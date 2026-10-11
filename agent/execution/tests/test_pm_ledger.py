#!/usr/bin/env python3
"""The PM's decision ledger (D-042)."""
import os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from agent.state import store                                        # noqa: E402
from agent.execution import pm_ledger                                # noqa: E402


class PmLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp, self.old = tempfile.mkdtemp(), store.RUNTIME
        store.RUNTIME = os.path.join(self.tmp, "runtime")

    def tearDown(self):
        store.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rulings_are_appended_one_line_each_and_shown_newest_last(self):
        pm_ledger.add("cto", "KAN-437", "Venues RPC: keep\n the 5-arg call compatible.")
        pm_ledger.add("cxo", None, "x" * 900)
        lines = pm_ledger.show().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("· cto · KAN-437 · Venues RPC: keep the 5-arg call compatible.", lines[0])
        self.assertTrue(lines[1].endswith("…"), "long rulings are cut to one line")
        with self.assertRaises(ValueError):
            pm_ledger.add("", "KAN-1", "x")


if __name__ == "__main__":
    unittest.main()
