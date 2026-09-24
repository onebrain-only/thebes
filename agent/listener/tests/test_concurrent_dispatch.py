"""Bounded concurrent dispatch (CEO, 2026-09-25): at most MAX_CONCURRENT_DISPATCHES
intents execute at once, independent intents really do overlap, and a third waits.

The safety rules concurrency must not bypass (claims, seat ownership, dependencies,
surfaces, leases) live in the Controller and Persistent State; their concurrent
behaviour is covered by agent/state/tests/test_concurrent_claims.py.
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import IsolatedRuntime                      # noqa: E402, ROOT on sys.path
from agent.listener import contract, dispatch, server, store  # noqa: E402

WAIT = 10.0


def envelope(work_item_id, key):
    return contract.normalize({
        "schema_version": 1, "intent_type": contract.EXECUTE_WORK_ITEM,
        "source": "listener-cli", "actor": "ceo", "idempotency_key": key,
        "correlation_id": "c-" + key, "payload": {"work_item_id": work_item_id}})


class GatedController:
    """A controller stand-in that holds each run open until released."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = 0
        self.peak = 0
        self.started = []
        self.release = threading.Event()
        self.two_running = threading.Event()

    def __call__(self, intent, timeout=None):
        with self.lock:
            self.running += 1
            self.peak = max(self.peak, self.running)
            self.started.append(dispatch.argv_for(intent)[-1])
            if self.running >= 2:
                self.two_running.set()
        self.release.wait(WAIT)
        with self.lock:
            self.running -= 1
        return {"transport": "returned", "exit_code": 0,
                "result": {"work_item_id": dispatch.argv_for(intent)[-1]}}


def accept(work_item_id, key):
    record, _ = store.accept(envelope(work_item_id, key))
    return record


class ConcurrentDispatchTests(unittest.TestCase):

    def worker(self, controller, **kw):
        return server.Worker(dispatcher=lambda intent_id:
                             dispatch.dispatch(intent_id, runner=controller), **kw)

    def test_default_bound_is_two(self):
        self.assertEqual(2, server.MAX_CONCURRENT_DISPATCHES)
        with self.assertRaises(ValueError):
            server.Worker(max_concurrency=0)

    def test_two_independent_intents_execute_concurrently(self):
        with IsolatedRuntime():
            controller = GatedController()
            accept("KAN-900", "a")
            accept("KAN-901", "b")
            worker = self.worker(controller)
            drained = threading.Thread(target=worker.drain_once)
            drained.start()
            # Both are inside the controller at the same time: serial dispatch
            # could never set this event, because the first run blocks.
            self.assertTrue(controller.two_running.wait(WAIT))
            controller.release.set()
            drained.join(WAIT)
            self.assertEqual({"KAN-900", "KAN-901"}, set(controller.started))

    def test_bound_is_respected_and_a_third_intent_waits(self):
        with IsolatedRuntime():
            controller = GatedController()
            records = [accept("KAN-9%02d" % i, "k%d" % i) for i in range(3)]
            ids = [r["intent_id"] for r in records]
            worker = self.worker(controller)
            drained = threading.Thread(target=worker.drain_once)
            drained.start()
            self.assertTrue(controller.two_running.wait(WAIT))
            time.sleep(0.3)                                  # give a 3rd slot a chance
            self.assertEqual(2, len(controller.started))
            self.assertEqual(2, len(worker.in_flight()))
            waiting = [r for r in records
                       if dispatch.argv_for(r)[-1] not in controller.started]
            self.assertEqual(1, len(waiting))
            self.assertEqual(store.RECEIVED,                  # still queued
                             store.read_intent(waiting[0]["intent_id"])["delivery_state"])
            controller.release.set()
            drained.join(WAIT)
            self.assertEqual(3, len(controller.started))
            self.assertEqual(2, controller.peak)
            self.assertTrue(all(store.read_intent(i)["delivery_state"] == store.COMPLETED
                                for i in ids))

    def test_a_bound_of_one_is_strictly_serial(self):
        with IsolatedRuntime():
            controller = GatedController()
            controller.release.set()
            for i in range(3):
                accept("KAN-95%d" % i, "s%d" % i)
            self.worker(controller, max_concurrency=1).drain_once()
            self.assertEqual(1, controller.peak)
            self.assertEqual(3, len(controller.started))

    def test_single_ticket_execution_is_unchanged(self):
        with IsolatedRuntime():
            controller = GatedController()
            controller.release.set()
            record = accept("KAN-990", "only")
            settled = self.worker(controller).drain_once()
            self.assertEqual(1, len(settled))
            self.assertEqual(store.COMPLETED, settled[0]["delivery_state"])
            self.assertEqual(["KAN-990"], controller.started)
            self.assertEqual(store.COMPLETED,
                             store.read_intent(record["intent_id"])["delivery_state"])

    def test_one_intent_is_never_dispatched_twice_by_concurrent_slots(self):
        with IsolatedRuntime():
            controller = GatedController()
            controller.release.set()
            accept("KAN-991", "dup")
            worker = self.worker(controller)
            threads = [threading.Thread(target=worker.drain_once) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(WAIT)
            self.assertEqual(["KAN-991"], controller.started)


if __name__ == "__main__":
    unittest.main()
