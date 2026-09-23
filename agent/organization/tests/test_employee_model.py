#!/usr/bin/env python3
"""Focused acceptance tests for the human employee foundation."""

import os
import shutil
import tempfile
import unittest

from agent.organization import (completion_actions, decision_owner, employee_profile,
                                employees, independent_review_required,
                                validate_registries)
from agent.organization import records
from agent.organization.registry import OrganizationError
from agent.organization.authority import decision_class_for_permission


class EmployeeRegistry(unittest.TestCase):
    def test_every_employee_has_the_four_professional_capabilities(self):
        self.assertEqual([], validate_registries())
        expected = ["understand_and_plan", "execute", "self_review_and_audit",
                    "learn_and_adapt"]
        for employee in employees().values():
            self.assertEqual(expected, employee["core_capabilities"])

    def test_compatibility_roles_share_human_job_families(self):
        self.assertEqual("software-engineer",
                         employee_profile("frontend-1")["role_family"])
        self.assertEqual("software-engineer",
                         employee_profile("backend-1")["role_family"])
        self.assertEqual("product-designer",
                         employee_profile("ux-engineer-1")["role_family"])

    def test_decisions_have_one_owner_and_ceo_is_not_technical_owner(self):
        self.assertEqual(["cto"],
                         decision_owner("technical_architecture")["eligible_employees"])
        self.assertTrue(decision_owner("company_investment")["owner_decision"])
        with self.assertRaises(OrganizationError):
            from agent.organization import assert_decision_authority
            assert_decision_authority("technical_architecture", "ceo")

    def test_review_is_independent_only_for_risk_or_conflict(self):
        self.assertEqual((), independent_review_required())
        self.assertEqual(("security",),
                         independent_review_required(("security",)))
        self.assertEqual(("actor_conflict",),
                         independent_review_required(actor_conflict=True))

    def test_definition_of_done_is_implied_by_assigned_work(self):
        actions = completion_actions("implement", repository_change=True,
                                     product_work=True)
        self.assertIn("create_scoped_commit", actions)
        self.assertIn("update_product_lifecycle", actions)

    def test_permission_questions_route_to_the_domain_not_the_ceo(self):
        self.assertEqual("task_local_technical",
                         decision_class_for_permission("Bash", "git commit"))
        self.assertEqual("production_operation",
                         decision_class_for_permission("apply_migration"))
        self.assertEqual("technical_architecture",
                         decision_class_for_permission("security_policy"))


class ProfessionalLedger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="thebes-employee-model-")
        self.old_runtime = records.store.RUNTIME
        self.old_locks = records.store.LOCKS
        records.store.RUNTIME = self.temp
        records.store.LOCKS = os.path.join(self.temp, ".locks")

    def tearDown(self):
        records.store.RUNTIME = self.old_runtime
        records.store.LOCKS = self.old_locks
        shutil.rmtree(self.temp)

    def test_work_decision_and_delegation_form_an_employee_ledger(self):
        cycle = records.start_work("cto", "direct:architecture-1", "decide",
                                   "Set the bounded architecture direction")
        cycle = records.record_plan(cycle["work_cycle_id"], cycle["revision"], "cto",
                                    ["inspect", "decide"])
        cycle = records.record_execution(cycle["work_cycle_id"], cycle["revision"],
                                         "cto", ["evidence:decision"])
        cycle = records.record_self_review(cycle["work_cycle_id"], cycle["revision"],
                                           "cto", True)
        cycle = records.record_learning(cycle["work_cycle_id"], cycle["revision"],
                                        "cto")
        decision = records.record_decision(
            "technical_architecture", "cto", "Use the organization seam",
            "evidence:architecture-review", "project", scope_ref="thebes")
        delegation = records.record_delegation(
            "cto", "backend-1", "direct:architecture-1",
            "Implement the bounded organization seam", "technical_architecture",
            decision["decision_id"])
        self.assertTrue(cycle["work_cycle_id"].startswith("cycle-"))
        self.assertEqual("completed", cycle["status"])
        self.assertEqual("cto", decision["decided_by"])
        self.assertEqual("backend-1", delegation["delegated_to"])
        ledger = records.employee_ledger("cto")
        self.assertEqual(["work_cycle", "decision", "delegation"],
                         [entry["kind"] for entry in ledger])


if __name__ == "__main__":
    unittest.main()
