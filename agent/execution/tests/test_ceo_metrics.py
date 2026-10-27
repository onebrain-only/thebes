#!/usr/bin/env python3
"""ceo_metrics (D-043 section 7): what reached the CEO, counted by code."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402
from agent.execution import ceo_metrics                                # noqa: E402


class FakeStore:
    def __init__(self, runtime, requests):
        self.RUNTIME, self.requests = runtime, requests

    def read_all(self, kind):
        return self.requests if kind == "decision_request" else []


class CeoMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, rows):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")

    def test_counts_by_day_and_flags_what_is_outside_the_three(self):
        now = time.mktime(time.strptime("2026-10-27 12:00", "%Y-%m-%d %H:%M")) - time.timezone
        day = "2026-10-27T10:00:00Z"
        reqs = [{"created_at": day, "status": "escalated", "escalation_reason": "ceo-only:money"},
                {"created_at": day, "status": "escalated", "escalation_reason": "gate-unavailable"},
                {"created_at": day, "status": "open", "escalation_reason": "held-for-orchestrator:x"},
                {"created_at": day, "status": "stuck"},
                {"created_at": "2026-09-01T00:00:00Z", "status": "escalated"}]
        self.write("sql-hook.log", [{"at": day, "lane": "ops", "decision": "allow"},
                                    {"at": day, "lane": "ops", "decision": "ask"}])
        self.write("policy-hook.log", [{"at": day, "decision": "deny"}])
        passed = now - 3600 * 3
        self.write("review/live-done.jsonl", [{"at": "2026-10-27T11:00:00Z", "ticket": "KAN-1",
                                               "passed_at": passed}])
        r = ceo_metrics.collect(2, state_store=FakeStore(self.tmp, reqs), now=now)
        self.assertEqual(list(r), ["2026-10-27"])
        d = r["2026-10-27"]
        self.assertEqual(d["reached_ceo_outside_the_three"], 1)
        self.assertEqual((d["held_for_orchestrator"], d["loops_cut"]), (1, 1))
        self.assertEqual(d["memphis_sql_asks"], 1)
        self.assertEqual(d["permission_prompts_answered"], {"deny": 1})
        self.assertEqual((d["done_live"], d["median_min_pass_to_live"]), (1, 120))


if __name__ == "__main__":
    unittest.main()
