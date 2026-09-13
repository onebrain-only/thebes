#!/usr/bin/env python3
"""Durable receipt recovery after the initiating observer has gone away.

The provider is deliberately invoked once in a worker thread.  The test stops
joining that worker after dispatch (the observation interruption), lets it
finish, and then uses the independent core lookup.  It proves a later
controller can recover evidence without another wake, retry, fallback, or a
synthetic Product result.
"""
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store  # noqa: E402
import validate  # noqa: E402
from agent.execution.provider import ExecutionResult, ExecutionStatus  # noqa: E402
from agent.execution.receipt import normalized_result_payload  # noqa: E402


class DurableReceiptRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_runtime, self.old_locks = store.RUNTIME, store.LOCKS
        self.old_validate_runtime = validate.RUNTIME
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        self.old_seats = validate.SEATS_JSON
        roster = os.path.join(self.tmp, "seats.json")
        with open(roster, "w") as fh:
            fh.write('{"record_type":"seat_registry","schema_version":1,"seats":{"frontend-1":{"role":"frontend"}}}')
        validate.SEATS_JSON = roster
        self.lease = store.create("execution_lease", {
            "work_item_id": "KAN-198", "seat_id": "frontend-1", "mode_revision": 12,
            "reason_ref": "authorized:KAN-198", "closed_at": None, "closed_by": None,
        })

    def tearDown(self):
        store.RUNTIME, store.LOCKS = self.old_runtime, self.old_locks
        validate.RUNTIME = self.old_validate_runtime
        validate.SEATS_JSON = self.old_seats

    def test_terminal_result_survives_observer_interruption_and_recovers_once(self):
        started, complete = threading.Event(), threading.Event()
        calls = []
        invocation = "controller-observer-interrupted"

        def provider_completion():
            calls.append("provider")
            started.set()
            complete.wait(2)
            result = ExecutionResult(invocation_id=invocation,
                                     status=ExecutionStatus.COMPLETED,
                                     summary="provider completed after observer ended",
                                     provider_id="codex-cli")
            store.record_execution_receipt(
                invocation, "KAN-198", "frontend-1",
                self.lease["execution_lease_id"], normalized_result_payload(result))
            store.close_execution_lease(self.lease["execution_lease_id"],
                                        self.lease["revision"], "orchestrator")

        worker = threading.Thread(target=provider_completion)
        worker.start()
        self.assertTrue(started.wait(1))
        # The initiating observer deliberately does not wait for completion here.
        self.assertEqual(["provider"], calls)
        self.assertIsNone(store.read_execution_receipt(invocation))
        complete.set()
        worker.join(2)

        recovered = store.read_execution_receipt(invocation)
        self.assertEqual("completed", recovered["status"])
        self.assertEqual("provider completed after observer ended",
                         recovered["normalized_result"]["summary"])
        self.assertTrue(store.read("execution_lease", self.lease["execution_lease_id"])["closed_at"])
        self.assertEqual(["provider"], calls)
        self.assertEqual("codex-cli", recovered["provider_id"])

        # Idempotent recovery stores no second result and does not invoke anything.
        again = store.record_execution_receipt(
            invocation, "KAN-198", "frontend-1", self.lease["execution_lease_id"],
            recovered["normalized_result"])
        self.assertEqual(recovered["execution_receipt_id"], again["execution_receipt_id"])
        self.assertEqual(["provider"], calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
