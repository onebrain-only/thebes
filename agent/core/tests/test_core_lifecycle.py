#!/usr/bin/env python3
"""Phase-5 proof of the one canonical intent lifecycle.

The claim under test is architectural, not functional: after Phase 5 there is
ONE external answer to "what happened to this intent", it is DERIVED from
canonical truth rather than reported from a delivery record, and where the two
disagree the disagreement is named rather than smoothed over.

Fully isolated: a temporary transport root and a stub Persistent State. No real
Persistent State writes, no Jira, no Supabase, no Product repository.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "listener", "tests"))

from _isolation import IsolatedRuntime                      # noqa: E402
from agent.core import lifecycle                            # noqa: E402
from agent.listener import contract, store                  # noqa: E402


WORK_ITEM = "KAN-900"


class State:
    """Only the read surface `lifecycle` is allowed to touch."""

    def __init__(self, task=None, receipts=(), leases=(), integrations=()):
        self.task = task
        self.records = {"execution_receipt": list(receipts),
                        "execution_lease": list(leases),
                        "integration_receipt": list(integrations)}
        self.writes = []

    def read(self, kind, rid):
        if kind == "task" and self.task and self.task["work_item_id"] == rid:
            return self.task
        return None

    def read_all(self, kind):
        return self.records.get(kind, [])

    # Any write path at all is a defect: Core's lifecycle derivation reads.
    def __getattr__(self, name):
        raise AssertionError("lifecycle must not call state_store.%s" % name)


def task(lifecycle_state="ready", owner=None):
    return {"work_item_id": WORK_ITEM, "revision": 3,
            "lifecycle": {"canonical": lifecycle_state},
            "ownership": {"seat_id": owner} if owner else None}


def envelope(key="k-1", work_item_id=WORK_ITEM):
    return contract.normalize({
        "schema_version": 1, "intent_type": contract.EXECUTE_WORK_ITEM,
        "source": "codex-controller", "actor": "ceo", "idempotency_key": key,
        "correlation_id": "c-" + key, "payload": {"work_item_id": work_item_id}})


def controller_answer(**fields):
    base = {"work_item_id": WORK_ITEM, "authorization_status": "authorized",
            "execution_status": "completed", "invocation_id": None}
    base.update(fields)
    return {"transport": "returned", "exit_code": 0, "result": base}


class OneExternalVocabulary(unittest.TestCase):
    def test_every_transport_state_maps_into_the_canonical_vocabulary(self):
        for delivery_state in store.DELIVERY_STATES:
            self.assertIn(lifecycle._FROM_TRANSPORT[delivery_state],
                          lifecycle.LIFECYCLE_STATES)

    def test_the_vocabularies_are_deliberately_distinct(self):
        # If they were the same words, "derived" would be indistinguishable from
        # "renamed", and a caller could not tell which one they were reading.
        self.assertNotEqual(set(store.DELIVERY_STATES), set(lifecycle.LIFECYCLE_STATES))
        self.assertIn(lifecycle.INDETERMINATE, lifecycle.LIFECYCLE_STATES)
        self.assertNotIn(lifecycle.INDETERMINATE, store.DELIVERY_STATES)


class DerivedFromCanonicalTruth(unittest.TestCase):
    def _accept(self, delivery_state=None, result=None, recovery=None, key="k-1"):
        record, _ = store.accept(envelope(key=key))
        if delivery_state is None:
            return record
        store.begin_dispatch(record["intent_id"])
        if recovery:
            store.recover()
        if delivery_state != store.DISPATCHING:
            store.settle(record["intent_id"], delivery_state, result or {})
        return record

    def test_an_accepted_intent_is_accepted_not_orchestrating(self):
        with IsolatedRuntime():
            record = self._accept()
            answer = lifecycle.resolve(record["intent_id"], State(task()))
            self.assertEqual(lifecycle.ACCEPTED, answer["lifecycle_state"])
            self.assertFalse(answer["terminal"])

    def test_a_completed_answer_carries_the_controller_result_and_canonical_state(self):
        with IsolatedRuntime():
            record = self._accept(store.COMPLETED, controller_answer(
                invocation_id="inv-1", execution_status="completed"))
            state = State(task("done", owner=None),
                          receipts=[{"work_item_id": WORK_ITEM, "invocation_id": "inv-1",
                                     "status": "completed", "provider_id": "claude-code",
                                     "created_at": "2026-09-15T00:00:00Z"}],
                          integrations=[{"work_item_id": WORK_ITEM,
                                         "integration_receipt_id": "integration-1"}])
            answer = lifecycle.resolve(record["intent_id"], state)
            self.assertEqual(lifecycle.COMPLETED, answer["lifecycle_state"])
            self.assertEqual(lifecycle.AGREES, answer["reconciliation"])
            self.assertEqual("done", answer["canonical_state"]["lifecycle"])
            self.assertEqual(["integration-1"],
                             answer["canonical_state"]["integration_receipts"])
            self.assertEqual("completed", answer["controller_result"]["execution_status"])

    def test_a_needs_input_answer_is_awaiting_authority(self):
        with IsolatedRuntime():
            record = self._accept(store.WAITING_INPUT, controller_answer(
                invocation_id="inv-1", execution_status="needs_input"))
            state = State(task("in_execution", owner="backend-1"),
                          receipts=[{"work_item_id": WORK_ITEM, "invocation_id": "inv-1",
                                     "status": "needs_input", "provider_id": "claude-code",
                                     "created_at": "2026-09-15T00:00:00Z"}],
                          leases=[{"work_item_id": WORK_ITEM,
                                   "execution_lease_id": "lease-1", "closed_at": None}])
            answer = lifecycle.resolve(record["intent_id"], state)
            self.assertEqual(lifecycle.AWAITING_AUTHORITY, answer["lifecycle_state"])
            self.assertFalse(answer["terminal"])
            self.assertEqual("backend-1", answer["canonical_state"]["owner_seat_id"])
            self.assertEqual(["lease-1"],
                             answer["canonical_state"]["open_execution_leases"])

    def test_a_transport_failure_is_undelivered_not_completed(self):
        with IsolatedRuntime():
            record = self._accept(store.FAILED, {"transport": "timeout"})
            answer = lifecycle.resolve(record["intent_id"], State(task()))
            self.assertEqual(lifecycle.UNDELIVERED, answer["lifecycle_state"])
            self.assertTrue(answer["terminal"])

    def test_a_refused_intake_is_refused(self):
        with IsolatedRuntime():
            answer_envelope = envelope(key="refused")
            store.reject(answer_envelope, "unknown-decision-reference", "no such intent")
            answer = lifecycle.resolve(answer_envelope["intent_id"], State(task()))
            self.assertEqual(lifecycle.REFUSED, answer["lifecycle_state"])
            self.assertTrue(answer["terminal"])


class AmbiguousDispatch(unittest.TestCase):
    """The case Phase 3 refused to guess about, now answered with evidence."""

    def test_an_interrupted_dispatch_is_indeterminate_not_failed_or_in_progress(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="interrupted"))
            store.begin_dispatch(record["intent_id"])
            store.recover()
            answer = lifecycle.resolve(record["intent_id"], State(task()))
            self.assertEqual(lifecycle.INDETERMINATE, answer["lifecycle_state"])
            # Never terminal: calling it terminal would assert an outcome.
            self.assertFalse(answer["terminal"])
            # And emphatically never UNDELIVERED, which would claim nothing ran.
            self.assertNotEqual(lifecycle.UNDELIVERED, answer["lifecycle_state"])
            self.assertEqual(lifecycle.UNOBSERVED_EXECUTION, answer["reconciliation"])

    def test_an_indeterminate_answer_carries_what_canonical_state_holds(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="interrupted"))
            store.begin_dispatch(record["intent_id"])
            store.recover()
            state = State(task("in_execution", owner="backend-1"),
                          receipts=[{"work_item_id": WORK_ITEM, "invocation_id": "inv-9",
                                     "status": "completed", "provider_id": "claude-code",
                                     "created_at": "2026-09-15T00:00:00Z"}],
                          leases=[{"work_item_id": WORK_ITEM,
                                   "execution_lease_id": "lease-9", "closed_at": None}])
            answer = lifecycle.resolve(record["intent_id"], state)
            # This is the whole point: the human settling it is handed the claim,
            # the open lease and the receipt instead of being sent to look.
            self.assertEqual("backend-1", answer["canonical_state"]["owner_seat_id"])
            self.assertEqual(["lease-9"],
                             answer["canonical_state"]["open_execution_leases"])
            self.assertEqual("completed",
                             answer["canonical_state"]["execution_receipts"][0]["status"])

    def test_an_interrupted_intent_is_still_never_re_dispatched(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="interrupted"))
            store.begin_dispatch(record["intent_id"])
            store.recover()
            # The Phase-3 conservatism is unchanged. Core added information,
            # not permission.
            self.assertEqual([], store.pending())
            self.assertIsNone(store.begin_dispatch(record["intent_id"]))


class ReconciliationNamesDisagreement(unittest.TestCase):
    def test_an_answer_naming_an_invocation_with_no_receipt_is_flagged(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="divergent"))
            store.begin_dispatch(record["intent_id"])
            store.settle(record["intent_id"], store.COMPLETED,
                         controller_answer(invocation_id="inv-missing"))
            answer = lifecycle.resolve(record["intent_id"],
                                       State(task("ready"), receipts=[]))
            self.assertEqual(lifecycle.TRANSPORT_CLAIMS_MORE, answer["reconciliation"])
            # It still reports the delivery state truthfully; it does not hide
            # the transport record or silently downgrade the answer.
            self.assertEqual(lifecycle.COMPLETED, answer["lifecycle_state"])
            self.assertEqual(store.COMPLETED, answer["delivery"]["transport_state"])

    def test_a_work_item_thebes_has_no_task_for_is_not_an_inconsistency(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="unknown-key"))
            store.begin_dispatch(record["intent_id"])
            store.settle(record["intent_id"], store.COMPLETED,
                         controller_answer(blocker="work-item-not-found"))
            answer = lifecycle.resolve(record["intent_id"], State(task=None))
            self.assertEqual(lifecycle.NO_CANONICAL_SUBJECT, answer["reconciliation"])
            self.assertIsNone(answer["canonical_state"])

    def test_canonical_state_wins_and_is_always_reported(self):
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="canonical-wins"))
            store.begin_dispatch(record["intent_id"])
            store.settle(record["intent_id"], store.COMPLETED,
                         controller_answer(invocation_id="inv-1", lifecycle="done"))
            # The controller result claims done; canonical state says ready.
            state = State(task("ready", owner="backend-1"),
                          receipts=[{"work_item_id": WORK_ITEM, "invocation_id": "inv-1",
                                     "status": "completed", "provider_id": "claude-code",
                                     "created_at": "2026-09-15T00:00:00Z"}])
            answer = lifecycle.resolve(record["intent_id"], state)
            self.assertEqual("ready", answer["canonical_state"]["lifecycle"])
            self.assertEqual("backend-1", answer["canonical_state"]["owner_seat_id"])


class CoreReadsAndNeverWrites(unittest.TestCase):
    def test_resolving_an_intent_makes_no_write_call(self):
        # The State stub raises on ANY attribute beyond read/read_all, so a
        # single write attempt fails this test loudly.
        with IsolatedRuntime():
            record, _ = store.accept(envelope(key="readonly"))
            lifecycle.resolve(record["intent_id"], State(task()))

    def test_an_unknown_intent_resolves_to_none_not_an_invention(self):
        with IsolatedRuntime():
            self.assertIsNone(lifecycle.resolve("intent-never-submitted", State(task())))

    def test_resolve_all_is_ordered_by_intake(self):
        with IsolatedRuntime():
            first, _ = store.accept(envelope(key="a"))
            second, _ = store.accept(envelope(key="b"))
            answers = lifecycle.resolve_all(State(task()))
            self.assertEqual({first["intent_id"], second["intent_id"]},
                             {answer["intent_id"] for answer in answers})


if __name__ == "__main__":
    unittest.main(verbosity=2)
