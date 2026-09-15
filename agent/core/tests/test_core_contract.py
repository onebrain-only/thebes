#!/usr/bin/env python3
"""Phase-5 conformance: the Core contract from MASTER_ROADMAP §37–§40.

These tests assert the ARCHITECTURE, not individual functions. Several of the
§40 criteria were already structurally true before Phase 5 — minimum-context
briefing, provider neutrality, learning's inertness — and the point of asserting
them here is that they stay true. A property nothing tests is a property that
quietly stops holding.

Read-only. No Persistent State writes, no Jira, no Supabase, no Product work.
"""

import ast
import importlib
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent import core                                        # noqa: E402
from agent.core import lifecycle                              # noqa: E402
from agent.execution import brief                             # noqa: E402
from agent.state import learning                              # noqa: E402


def _without_docstrings(tree):
    """The tree with every docstring removed, so prose is not mistaken for code."""
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return tree


class SubsystemMapIsTrue(unittest.TestCase):
    """§37 draws one box. The map must name modules that actually exist."""

    def test_every_named_subsystem_resolves_to_real_modules(self):
        for responsibility, modules in core.SUBSYSTEMS.items():
            self.assertIsInstance(modules, tuple, responsibility)
            for module_path in modules:
                try:
                    importlib.import_module(module_path)
                except ImportError as exc:       # pragma: no cover - failure path
                    self.fail("%s names %s, which does not import: %s"
                              % (responsibility, module_path, exc))

    def test_the_map_covers_every_responsibility_the_roadmap_names(self):
        for responsibility in (
                "intake", "persistent_state", "company_rules", "product_state",
                "work_lifecycle", "capability_model", "authorization",
                "dependencies", "context_assembly", "validation", "learning",
                "provider_selection", "execution"):
            self.assertIn(responsibility, core.SUBSYSTEMS)

    def test_core_is_composition_and_holds_no_orchestration_of_its_own(self):
        # Phase 5 must not have added a second orchestration engine. Core's own
        # source may not claim, lease, select a provider, transition Jira or
        # write state — those belong to the subsystems it points at.
        source = "".join(inspect.getsource(module)
                         for module in (core, lifecycle))
        for forbidden in ("store.claim(", "open_execution_lease(", "select_provider(",
                          "transition_issue(", "record_execution_receipt(",
                          "store.update(", "store.create(", "record_review_result("):
            self.assertNotIn(forbidden, source,
                             "Core reimplements orchestration: %r" % forbidden)


class MinimumContextExecution(unittest.TestCase):
    """§38 — what the executor may receive, and what it may never receive."""

    #: §38's list, verbatim in intent.
    ROADMAP_FIELDS = {
        "bounded objective": "objective",
        "required constraints": "prohibited_actions",
        "required files/context references": "context_refs",
        "allowed surfaces": "allowed_surfaces",
        "validation targets": "validation_targets",
        "return contract": "return_contract",
    }

    def test_every_field_the_roadmap_allows_is_present(self):
        for description, field in self.ROADMAP_FIELDS.items():
            self.assertIn(field, brief.PRODUCT_BRIEF_FIELDS,
                          "§38 requires %s" % description)

    def test_the_brief_is_an_allow_list_so_company_history_has_no_path(self):
        # The guarantee is structural: a field absent from PRODUCT_BRIEF_FIELDS
        # cannot be rendered at all, so "no unnecessary company history" is not
        # a habit anyone has to maintain.
        for never in ("company_history", "roadmap", "decisions", "learning",
                      "telemetry", "backlog", "other_work_items", "seat_roster",
                      "operating_mode", "invocation_id", "claim_ref",
                      "execution_lease_id", "model_intent", "reasoning_effort"):
            self.assertNotIn(never, brief.PRODUCT_BRIEF_FIELDS)

    def test_control_plane_fields_are_disjoint_from_the_brief(self):
        self.assertEqual(set(),
                         set(brief.PRODUCT_BRIEF_FIELDS) & set(brief.CONTROL_PLANE_FIELDS))

    def test_the_core_entry_surface_cannot_leak_into_an_executor_brief(self):
        # Phase 5 introduced `agent.core`. If that name could ride into a brief,
        # Phase 4's firewall lesson would have been relearned the hard way.
        for text in ("Use agent.core to resolve your intent.",
                     "from agent.core import lifecycle",
                     "import agent.core and check the lifecycle_state"):
            violated = False
            for check in (brief.assert_no_control_plane_identifier,
                          brief.assert_no_control_plane_concept):
                try:
                    check(text, "objective")
                except brief.ExecutorBriefViolation:
                    violated = True
            self.assertTrue(violated, "executor brief accepts: %r" % text)

    def test_ordinary_product_english_still_passes(self):
        for text in ("Fix the RLS policy on public.profiles.",
                     "Run flutter test and report the output.",
                     "The core problem is a missing index on meetups.",
                     "Return RESULT and EVIDENCE sections."):
            for check in (brief.assert_no_control_plane_identifier,
                          brief.assert_no_control_plane_concept):
                check(text, "objective")


class LearningHasNoAuthority(unittest.TestCase):
    """§39 — learning may inform; it may never decide."""

    def test_runtime_may_only_propose(self):
        self.assertIn("candidate", learning.STATUSES)
        source = inspect.getsource(learning)
        self.assertIn("DECISION_AUTHORITIES", source)
        self.assertEqual(("ceo", "cto"), learning.DECISION_AUTHORITIES)

    def test_learning_has_no_write_path_into_work_or_governance(self):
        source = inspect.getsource(learning)
        for forbidden in ("store.claim(", "transition_issue(", "record_review_result(",
                          "set_operating_mode(", "open_execution_lease(",
                          "record_execution_approval("):
            self.assertNotIn(forbidden, source)

    def test_core_does_not_consult_learning_when_answering(self):
        # §39's line in the sand: a recommendation must not become an input to
        # a decision path by convenience. Core's answer is canonical state only.
        self.assertNotIn("learning", inspect.getsource(lifecycle))


class ConversationIndependence(unittest.TestCase):
    """§40 — company state must not depend on any chat."""

    def test_core_reads_no_conversation_source(self):
        # Executable source only. The docstrings legitimately discuss
        # "Conversation Intelligence" — §36's own term — and a test that
        # searched prose would be testing the wrong thing.
        for module in (core, lifecycle):
            tree = _without_docstrings(ast.parse(inspect.getsource(module)))
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
            names |= {node.value for node in ast.walk(tree)
                      if isinstance(node, ast.Constant) and isinstance(node.value, str)}
            executable = " ".join(str(name) for name in names).lower()
            for conversational in ("transcript", "conversation", "chat_history",
                                   "session_memory", "message_history"):
                self.assertNotIn(conversational, executable,
                                 "%s reads a conversational source" % module.__name__)

    def test_the_answer_is_reproducible_from_disk_alone(self):
        # Every input `resolve` reads is a durable record: the transport store
        # and Persistent State. Its signature takes no session, no caller
        # identity and no conversation handle.
        parameters = set(inspect.signature(lifecycle.resolve).parameters)
        self.assertEqual({"intent_id", "state_store", "transport_store"}, parameters)


class OneCanonicalLifecycle(unittest.TestCase):
    def test_core_exposes_exactly_one_external_vocabulary(self):
        self.assertEqual(set(lifecycle.LIFECYCLE_STATES),
                         {core.ACCEPTED, core.ORCHESTRATING, core.AWAITING_AUTHORITY,
                          core.COMPLETED, core.REFUSED, core.UNDELIVERED,
                          core.INDETERMINATE})

    def test_terminal_means_answered_not_successful(self):
        # A governance refusal is COMPLETED. Conflating "answered" with
        # "succeeded" is how a refusal gets read as a pass.
        self.assertIn(core.COMPLETED, lifecycle.TERMINAL_STATES)
        self.assertIn(core.REFUSED, lifecycle.TERMINAL_STATES)
        self.assertIn(core.UNDELIVERED, lifecycle.TERMINAL_STATES)
        self.assertNotIn(core.INDETERMINATE, lifecycle.TERMINAL_STATES)
        self.assertNotIn(core.AWAITING_AUTHORITY, lifecycle.TERMINAL_STATES)

    def test_core_entry_surface_is_two_verbs(self):
        public = {name for name in dir(core)
                  if not name.startswith("_") and callable(getattr(core, name))}
        self.assertEqual({"resolve", "resolve_all"}, public)


if __name__ == "__main__":
    unittest.main(verbosity=2)
