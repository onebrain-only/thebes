#!/usr/bin/env python3
"""T-093(A): a SELF-review FAIL re-entry is admissible for the SAME seat.

Real store on a temp runtime (test_validation_dispatch fixtures), a Jira
double. `canonical_admissibility` is the prover the standing bounded grant
uses; before T-093 it always asked the CLAIM gate, which answers not-ready +
already-owned for an owned item in an execution status by construction, so
the seat a SELF FAIL handed the work back to could never be woken again.
"""

import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                       # noqa: E402

from agent.controller import canonical_admissibility               # noqa: E402
from agent.controller.tests.test_validation_dispatch import (      # noqa: E402
    BACKEND_DEV, PEER_REVIEW, SELF_REVIEW, Jira, isolated_runtime, make_task,
)
from agent.state import board                                      # noqa: E402

READY = "10008"


class Reentry(unittest.TestCase):
    def setUp(self):
        self.tmp = isolated_runtime()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def reentered(self, key="KAN-970", owner="backend-1", review_owner=None,
                  result="fail", route_ch=None, status_id=BACKEND_DEV):
        task = make_task(key, characteristics=route_ch or {}, status_id=status_id,
                         owner=owner)
        cur = store.read("task", key)
        cur["review_context"] = {"review_type": "self", "review_owner": review_owner or owner,
                                 "review_result": result, "review_cycle": 1,
                                 "started_at": store.now()}
        # Written the way self_fail_reentry leaves the record: owned by the
        # same seat, review self/fail, lifecycle back in development.
        store._atomic_write(store.path_for("task", key), cur)
        return store.read("task", key)

    def prove(self, key, jira):
        return canonical_admissibility(state_store=store, jira_client=jira)(key)

    def test_the_same_seat_is_admitted_through_the_continuation_gate(self):
        self.reentered()
        self.assertEqual([], self.prove("KAN-970", Jira(BACKEND_DEV)))

    def test_a_stop_on_the_item_refuses_the_continuation(self):
        self.reentered("KAN-971")
        store.create("intervention", {"kind": "stop", "target": "KAN-971", "scope": "task",
                                      "created_by": "ceo", "reason_ref": "test",
                                      "cleared_at": None})
        self.assertIn("task-stopped", self.prove("KAN-971", Jira(BACKEND_DEV)))

    def test_a_different_owner_than_the_review_names_is_not_a_reentry(self):
        self.reentered("KAN-972", owner="backend-2", review_owner="backend-1")
        reasons = self.prove("KAN-972", Jira(BACKEND_DEV))
        self.assertIn("already-owned", reasons)

    def test_still_in_self_review_is_not_a_reentry(self):
        self.reentered("KAN-973", status_id=SELF_REVIEW)
        reasons = self.prove("KAN-973", Jira(SELF_REVIEW))
        self.assertNotEqual([], reasons)

    def test_a_pending_review_is_not_a_reentry(self):
        self.reentered("KAN-974", result="pending")
        self.assertIn("already-owned", self.prove("KAN-974", Jira(BACKEND_DEV)))

    def test_a_peer_route_is_never_admitted_this_way(self):
        task = make_task("KAN-975", characteristics={"schema_change": True},
                         status_id=BACKEND_DEV, owner="backend-1")
        cur = store.read("task", "KAN-975")
        cur["review_context"] = {"review_type": "peer", "review_owner": "backend-2",
                                 "review_result": "fail", "review_cycle": 1,
                                 "started_at": store.now(), "previous_owner": "backend-1"}
        store._atomic_write(store.path_for("task", "KAN-975"), cur)
        self.assertIn("already-owned", self.prove("KAN-975", Jira(BACKEND_DEV)))

    def test_an_ordinary_owned_ready_item_is_still_already_owned(self):
        make_task("KAN-976", characteristics={}, status_id=READY, owner="backend-1")
        self.assertIn("already-owned", self.prove("KAN-976", Jira(READY)))

    def test_the_execution_status_is_looked_up_from_the_board_not_hard_coded(self):
        self.assertEqual(BACKEND_DEV, str(board.execution_status_for("backend")))
        self.reentered("KAN-977")
        # Live Jira says Ready while the store says development: not a re-entry.
        self.assertNotEqual([], self.prove("KAN-977", Jira(READY)))


if __name__ == "__main__":
    unittest.main()
