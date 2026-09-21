#!/usr/bin/env python3
"""VALIDATE_WORK_ITEM at the Listener boundary. (T-091)

Deterministic and isolated: contract normalisation and the argv the dispatcher
builds. No Controller runs, no Jira, no Persistent State.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.listener import contract, dispatch                     # noqa: E402


def validate_envelope(**overrides):
    base = {"schema_version": 1, "intent_type": contract.VALIDATE_WORK_ITEM,
            "source": "listener-cli", "actor": "orchestrator",
            "idempotency_key": "v-1", "correlation_id": "c-1",
            "payload": {"work_item_id": "KAN-267"}}
    base.update(overrides)
    return base


class ValidateIntent(unittest.TestCase):
    def test_the_type_is_allow_listed_and_carries_only_a_work_item(self):
        intent = contract.normalize(validate_envelope())
        self.assertEqual(contract.VALIDATE_WORK_ITEM, intent["intent_type"])
        self.assertEqual({"work_item_id": "KAN-267"}, intent["payload"])

    def test_it_cannot_name_a_reviewer_a_route_or_a_verdict(self):
        for extra in ({"reviewer": "frontend-6"}, {"route": "peer"},
                      {"verdict": "pass"}):
            with self.subTest(extra=extra):
                with self.assertRaises(contract.IntentRejected) as caught:
                    contract.normalize(validate_envelope(
                        payload={"work_item_id": "KAN-267", **extra}))
                self.assertEqual("unknown-field", caught.exception.reason)

    def test_it_dispatches_to_the_controller_validate_command(self):
        command = dispatch.argv_for(contract.normalize(validate_envelope()))
        self.assertEqual(["-m", "agent.controller", "validate", "KAN-267"], command[1:])
        self.assertEqual(sys.executable, command[0])

    def test_responds_to_is_still_only_for_decisions(self):
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(validate_envelope(responds_to="intent-x"))


if __name__ == "__main__":
    unittest.main()
