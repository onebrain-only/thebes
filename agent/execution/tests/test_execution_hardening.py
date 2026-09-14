#!/usr/bin/env python3
"""Deterministic guards for continuation authority; no Product surfaces involved."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from agent.execution.authority import (CONDITIONALLY_REQUIRED, KNOWN_REQUIRED,
                                       RUNTIME_UNKNOWN, discover_execution_authority)
from agent.execution.wake import WakeOrderError, assert_executor_permission_is_not_control_plane


class ReadOnlyStore:
    def __init__(self):
        self.before = []
        self.task = {"work_item_id": "KAN-186", "ownership": {"seat_id": "backend-2"},
                     "execution_profile": {"required_capability": "backend", "validation_route": "peer",
                                           "characteristics": {"schema_change": True}}}
        self.approvals = [{"work_item_id": "KAN-186", "permission": "Bash",
                           "allowed_operation": "python3 -c 'execute_approved_claude_continuation()'",
                           "approval_scope": "one continuation"},
                          {"work_item_id": "KAN-186", "permission": "mcp__claude_ai_Supabase__apply_migration",
                           "allowed_operation": None, "approval_scope": "production project fixture"}]
        self.receipts = [{"work_item_id": "KAN-186", "provider_id": "claude-code",
                          "continuation_of_invocation_id": "original", "status": "completed"}]

    def read(self, kind, key):
        return self.task if kind == "task" and key == "KAN-186" else None

    def read_all(self, kind):
        return {"execution_approval": list(self.approvals),
                "execution_receipt": list(self.receipts),
                "execution_continuation_preparation": []}[kind]

    def current_operating_mode(self):
        return "SYSTEM_MAINTENANCE"


class ExecutionHardeningTests(unittest.TestCase):
    def test_product_executor_bash_cannot_bootstrap_continuation(self):
        with self.assertRaisesRegex(WakeOrderError, "control-plane"):
            assert_executor_permission_is_not_control_plane(
                "Bash", "python3 -c 'execute_approved_claude_continuation()'")
        assert_executor_permission_is_not_control_plane("Bash", "git diff --check")

    def test_read_only_manifest_batches_discoverable_authority(self):
        store = ReadOnlyStore()
        manifest = discover_execution_authority("KAN-186", store)
        self.assertTrue(manifest["read_only"])
        self.assertTrue(manifest["no_product_execution"])
        classes = {item["classification"] for item in manifest["items"]}
        self.assertEqual({KNOWN_REQUIRED, CONDITIONALLY_REQUIRED, RUNTIME_UNKNOWN}, classes)
        self.assertIn("provider_tool:Bash", manifest["consolidated_ceo_decisions"])
        self.assertIn("provider_tool:mcp__claude_ai_Supabase__apply_migration",
                      manifest["consolidated_ceo_decisions"])
        self.assertIn("continuation_remediation", manifest["consolidated_ceo_decisions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
