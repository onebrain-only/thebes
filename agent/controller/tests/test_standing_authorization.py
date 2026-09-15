#!/usr/bin/env python3
"""The bounded CEO standing authorization.

The risk this whole feature carries is that SELECTION and AUTHORITY collapse
into one actor. These tests are written against that risk rather than against
the functions: authority must come from a CEO act Thebes cannot author, and
selection must come from canonical admission rules Thebes cannot bend.

Isolated: a temporary Persistent State root. No Jira, no Supabase, no Product
repository, no provider.
"""

import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.controller import ProductAuthorization, RoadmapAuthorization  # noqa: E402
from agent.state import store                                            # noqa: E402

CEO_REF = "CEO chat message, standing grant: up to three planner-selected items"
SCOPE = "real Product backlog work satisfying every canonical admission rule"


class Runtime:
    """A throwaway Persistent State root."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="thebes-authz-")
        self._runtime, self._locks = store.RUNTIME, store.LOCKS
        store.RUNTIME = os.path.join(self.dir, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        return self

    def __exit__(self, *exc):
        store.RUNTIME, store.LOCKS = self._runtime, self._locks
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


class Roadmap:
    """Stands in for the exact-ticket record, without touching ROADMAP.md."""

    def __init__(self, selected=None):
        self.selected = selected

    def for_work_item(self, work_item_id):
        if self.selected and self.selected == work_item_id:
            return {"authorized": True, "reason": "authorized",
                    "reference": "CEO exact-ticket grant"}
        return {"authorized": False, "reason": "product-execution-not-authorized",
                "reference": None}


def grant(maximum=3):
    return store.record_product_authorization(
        authorization_ref=CEO_REF, maximum_completed_items=maximum, scope=SCOPE)


def admissible(*keys):
    """A canonical prover stub: these keys pass admission, others do not."""
    return lambda key: [] if key in keys else ["not-ready", "missing-due-date"]


class ExactTicketPathPreserved(unittest.TestCase):
    """1. The Phase-2 path must not change at all."""

    def test_exact_ticket_authorization_still_authorizes(self):
        with Runtime():
            auth = ProductAuthorization(roadmap=Roadmap("KAN-900"), state_store=store,
                                        admissibility=admissible())
            answer = auth.for_work_item("KAN-900")
            self.assertTrue(answer["authorized"])
            self.assertEqual("authorized", answer["reason"])

    def test_exact_ticket_still_refuses_a_different_key(self):
        with Runtime():
            auth = ProductAuthorization(roadmap=Roadmap("KAN-900"), state_store=store,
                                        admissibility=admissible("KAN-901"))
            self.assertFalse(auth.for_work_item("KAN-901")["authorized"])

    def test_with_no_grant_the_original_refusal_is_preserved_verbatim(self):
        with Runtime():
            auth = ProductAuthorization(roadmap=Roadmap(), state_store=store,
                                        admissibility=admissible("KAN-900"))
            self.assertEqual("product-execution-not-authorized",
                             auth.for_work_item("KAN-900")["reason"])

    def test_the_real_roadmap_reader_is_untouched(self):
        answer = RoadmapAuthorization().for_work_item("KAN-900")
        self.assertIn("authorized", answer)
        self.assertIn("reason", answer)


class PlannerSelectionUnderACeoGrant(unittest.TestCase):
    """2 and 3. Authority from the CEO; selection from canonical admission."""

    def test_a_grant_authorizes_an_admissible_planner_selection_with_no_caller_key(self):
        with Runtime():
            record = grant()
            auth = ProductAuthorization(roadmap=Roadmap(), state_store=store,
                                        admissibility=admissible("KAN-900"))
            answer = auth.for_work_item("KAN-900")
            self.assertTrue(answer["authorized"])
            self.assertEqual("bounded-authorization", answer["reason"])
            self.assertEqual(CEO_REF, answer["reference"])
            self.assertEqual(record["product_authorization_id"], answer["authorization_id"])
            self.assertEqual(3, answer["authorization_remaining"])

    def test_the_planner_cannot_authorize_an_inadmissible_ticket(self):
        with Runtime():
            grant()
            auth = ProductAuthorization(roadmap=Roadmap(), state_store=store,
                                        admissibility=admissible("KAN-900"))
            answer = auth.for_work_item("KAN-901")
            self.assertFalse(answer["authorized"])
            self.assertIn("not-admissible", answer["reason"])
            # The canonical reasons travel with the refusal.
            self.assertIn("missing-due-date", answer["reason"])

    def test_a_grant_without_an_admissibility_proof_refuses_rather_than_assumes(self):
        with Runtime():
            grant()
            auth = ProductAuthorization(roadmap=Roadmap(), state_store=store,
                                        admissibility=None)
            answer = auth.for_work_item("KAN-900")
            self.assertFalse(answer["authorized"])
            self.assertIn("requires-admissibility-proof", answer["reason"])

    def test_an_empty_queue_authorizes_nothing_without_a_grant(self):
        # D-003 intact: queue availability is not a source of permission.
        with Runtime():
            auth = ProductAuthorization(roadmap=Roadmap(), state_store=store,
                                        admissibility=admissible("KAN-900", "KAN-901"))
            self.assertFalse(auth.for_work_item("KAN-900")["authorized"])


class QuotaIsSpentOnlyByRealCompletions(unittest.TestCase):
    """4, 5 and 6."""

    def test_three_completions_exhaust_the_grant_and_a_fourth_is_refused(self):
        with Runtime():
            record = grant()
            for index, key in enumerate(("KAN-901", "KAN-902", "KAN-903"), start=1):
                record = store.consume_product_authorization(
                    record["product_authorization_id"], key, record["revision"],
                    evidence_ref="lifecycle done")
                self.assertEqual(3 - index, store.authorization_remaining(record))
            self.assertEqual("exhausted", record["status"])
            self.assertIsNone(store.active_product_authorization())
            with self.assertRaises(store.StateError):
                store.consume_product_authorization(
                    record["product_authorization_id"], "KAN-904", record["revision"],
                    evidence_ref="lifecycle done")

    def test_an_exhausted_grant_authorizes_nothing_further(self):
        with Runtime():
            record = grant(maximum=1)
            store.consume_product_authorization(
                record["product_authorization_id"], "KAN-901", record["revision"],
                evidence_ref="lifecycle done")
            auth = ProductAuthorization(roadmap=Roadmap(), state_store=store,
                                        admissibility=admissible("KAN-900"))
            self.assertFalse(auth.for_work_item("KAN-900")["authorized"])

    def test_the_same_completion_never_consumes_quota_twice(self):
        with Runtime():
            record = grant()
            first = store.consume_product_authorization(
                record["product_authorization_id"], "KAN-901", record["revision"],
                evidence_ref="lifecycle done")
            replay = store.consume_product_authorization(
                record["product_authorization_id"], "KAN-901", first["revision"],
                evidence_ref="lifecycle done, re-entered tail")
            self.assertEqual(first["revision"], replay["revision"])
            self.assertEqual(1, len(replay["completed_items"]))
            self.assertEqual(2, store.authorization_remaining(replay))

    def test_a_failed_or_blocked_outcome_consumes_nothing(self):
        from agent.controller import _consume_authorization
        with Runtime():
            record = grant()
            for evidence in ({"outcome": "lifecycle-not-completable", "lifecycle": None,
                              "jira_transition_performed": False},
                             {"outcome": "jira-transition-failed", "lifecycle": "in_review",
                              "jira_transition_performed": False},
                             {"outcome": "integration-evidence-invalid", "lifecycle": None,
                              "jira_transition_performed": False},
                             # Completed-looking, but Jira did not actually land on done.
                             {"outcome": "completed", "lifecycle": "in_review",
                              "jira_transition_performed": True}):
                self.assertEqual({}, _consume_authorization("KAN-901", evidence, store))
            self.assertEqual(3, store.authorization_remaining(
                store.read_product_authorization(record["product_authorization_id"])))

    def test_a_real_completion_consumes_exactly_one(self):
        from agent.controller import _consume_authorization
        with Runtime():
            record = grant()
            outcome = _consume_authorization(
                "KAN-901", {"outcome": "completed", "lifecycle": "done",
                            "jira_transition_performed": True}, store)
            self.assertEqual(3, outcome["authorization_remaining_before"])
            self.assertEqual(2, outcome["authorization_remaining_after"])
            self.assertEqual(record["product_authorization_id"], outcome["authorization_id"])


class ThebesCannotGrantItselfAuthority(unittest.TestCase):
    """7 and 8."""

    def test_only_the_ceo_may_approve_a_grant(self):
        with Runtime():
            for pretender in ("thebes", "controller", "orchestrator", "po", "system",
                              "canonical-thebes-planner"):
                with self.assertRaises(store.StateError):
                    store.record_product_authorization(
                        authorization_ref=CEO_REF, maximum_completed_items=3,
                        scope=SCOPE, approving_authority=pretender)

    def test_a_grant_must_name_the_human_act_it_came_from(self):
        with Runtime():
            for empty in ("", "   ", None):
                with self.assertRaises(store.StateError):
                    store.record_product_authorization(
                        authorization_ref=empty, maximum_completed_items=3, scope=SCOPE)

    def test_selection_authority_cannot_be_reassigned(self):
        with Runtime():
            with self.assertRaises(store.StateError):
                store.record_product_authorization(
                    authorization_ref=CEO_REF, maximum_completed_items=3, scope=SCOPE,
                    selection_authority="ceo")

    def test_a_grant_cannot_be_unbounded(self):
        with Runtime():
            for bad in (0, -1, None, "3", 2.5):
                with self.assertRaises(store.StateError):
                    store.record_product_authorization(
                        authorization_ref=CEO_REF, maximum_completed_items=bad,
                        scope=SCOPE)

    def test_only_one_active_grant_can_exist(self):
        with Runtime():
            grant()
            with self.assertRaises(store.StateError):
                grant()

    def test_a_grant_does_not_override_a_ceo_only_boundary(self):
        # The grant authorizes an ENVELOPE. It carries no permission field, no
        # provider, no surface and no production scope, so there is nothing in
        # it that could widen a native permission or a destructive boundary.
        with Runtime():
            record = grant()
            for reserved in ("permission", "allowed_operation", "production",
                             "destructive", "surfaces", "provider", "seat_id",
                             "native_permissions", "grants"):
                self.assertNotIn(reserved, record)
            # And its own scope is prose, not an executable widening.
            self.assertIsInstance(record["scope"], str)

    def test_only_the_ceo_may_revoke(self):
        with Runtime():
            record = grant()
            with self.assertRaises(store.StateError):
                store.revoke_product_authorization(
                    record["product_authorization_id"], record["revision"],
                    revoked_by="thebes", revocation_ref="self-revocation")
            ended = store.revoke_product_authorization(
                record["product_authorization_id"], record["revision"],
                revoked_by="ceo", revocation_ref="CEO chat message, revoked")
            self.assertEqual("revoked", ended["status"])
            self.assertIsNone(store.active_product_authorization())


class DurableAndAuditable(unittest.TestCase):
    """9 and 10."""

    def test_a_grant_survives_restart_with_its_quota_intact(self):
        with Runtime():
            record = grant()
            store.consume_product_authorization(
                record["product_authorization_id"], "KAN-901", record["revision"],
                evidence_ref="lifecycle done")
            # Nothing in memory survives; the file is all there is.
            reloaded = store.read_product_authorization(record["product_authorization_id"])
            self.assertEqual(2, store.authorization_remaining(reloaded))
            self.assertEqual(record["product_authorization_id"],
                             store.active_product_authorization()["product_authorization_id"])

    def test_the_record_stays_auditable_after_it_is_spent(self):
        with Runtime():
            record = grant(maximum=1)
            spent = store.consume_product_authorization(
                record["product_authorization_id"], "KAN-901", record["revision"],
                evidence_ref="lifecycle completed, jira transition True")
            self.assertEqual("exhausted", spent["status"])
            # Everything a later reader needs: who granted it, what it said,
            # which item consumed it, when, and on what evidence.
            self.assertEqual("ceo", spent["approving_authority"])
            self.assertEqual(CEO_REF, spent["authorization_ref"])
            self.assertEqual(SCOPE, spent["scope"])
            item = spent["completed_items"][0]
            self.assertEqual("KAN-901", item["work_item_id"])
            self.assertTrue(item["completed_at"])
            self.assertIn("jira transition", item["evidence_ref"])

    def test_a_stale_revision_is_refused(self):
        with Runtime():
            record = grant()
            store.consume_product_authorization(
                record["product_authorization_id"], "KAN-901", record["revision"],
                evidence_ref="lifecycle done")
            with self.assertRaises(store.StateError):
                store.consume_product_authorization(
                    record["product_authorization_id"], "KAN-902", record["revision"],
                    evidence_ref="lifecycle done")

    def test_the_validator_accepts_a_real_grant_and_refuses_a_forged_one(self):
        sys.path.insert(0, os.path.join(ROOT, "agent", "state"))
        import validate
        with Runtime():
            record = grant()
            self.assertEqual([], validate.validate_record("product_authorization", record))
            forged = dict(record, approving_authority="thebes")
            self.assertTrue(any("CEO act" in e for e in
                                validate.validate_record("product_authorization", forged)))
            overspent = dict(record, completed_items=[
                {"work_item_id": "KAN-901", "completed_at": "x", "evidence_ref": "e"},
                {"work_item_id": "KAN-901", "completed_at": "x", "evidence_ref": "e"}])
            self.assertTrue(any("counted twice" in e for e in
                                validate.validate_record("product_authorization", overspent)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
