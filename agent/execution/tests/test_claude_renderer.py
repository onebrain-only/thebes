#!/usr/bin/env python3
"""Migration Slice 3 — Claude configuration renderer."""
import json
import os
import shutil
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
SCRIPTS = os.path.join(ROOT, "agent", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import render_claude_agents as renderer  # noqa: E402


class ClaudeRendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.registry = os.path.join(self.temp, "seats.json")
        self.bindings = os.path.join(self.temp, "bindings")
        self.roles = os.path.join(self.temp, "roles")
        self.agents = os.path.join(self.temp, "agents")
        os.makedirs(self.bindings)
        os.makedirs(self.roles)

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def write_registry(self, seats):
        with open(self.registry, "w", encoding="utf-8") as fh:
            json.dump({"record_type": "seat_registry", "schema_version": 1,
                       "seats": {seat: {"role": role}
                                 for seat, role in seats.items()}}, fh)

    def write_binding(self, seat, role="backend", extra=b""):
        with open(os.path.join(self.bindings, seat + ".yml"), "wb") as fh:
            fh.write(b"name: " + seat.encode() + b"\nmodel: opus\n" + extra
                     + b"role: " + role.encode() + b"\n")

    def write_role(self, role, content=None):
        with open(os.path.join(self.roles, role + ".md"), "wb") as fh:
            fh.write(content or (b"ROLE CONTRACT: " + role.encode() + b"\n"))

    def errors(self):
        return renderer.validation_errors(self.registry, self.bindings, self.roles)

    def test_all_27_checked_in_agents_are_byte_for_byte_goldens(self):
        expected = renderer.expected_outputs()
        agent_dir = os.path.join(ROOT, ".claude", "agents")
        actual_names = sorted(f[:-3] for f in os.listdir(agent_dir)
                              if f.endswith(".md"))
        self.assertEqual(27, len(expected))
        self.assertEqual(sorted(expected), actual_names)
        for seat, content in expected.items():
            with open(os.path.join(agent_dir, seat + ".md"), "rb") as fh:
                self.assertEqual(content, fh.read(), seat)

    def test_missing_and_unknown_claude_configurations_are_rejected(self):
        self.write_registry({"backend-1": "backend"})
        self.write_role("backend")
        self.write_binding("unknown-seat")
        errors = self.errors()
        self.assertTrue(any("missing Claude configuration" in e for e in errors))
        self.assertTrue(any("has no neutral seat" in e for e in errors))

    def test_duplicate_and_mismatched_legacy_metadata_are_rejected(self):
        self.write_registry({"backend-1": "backend"})
        self.write_role("backend")
        self.write_binding("backend-1", role="frontend",
                           extra=b"name: duplicate\nrole: backend\n")
        errors = self.errors()
        self.assertTrue(any("duplicate name metadata" in e for e in errors))
        self.assertTrue(any("exactly one legacy role" in e for e in errors))

        os.unlink(os.path.join(self.bindings, "backend-1.yml"))
        self.write_binding("backend-1", role="frontend")
        errors = self.errors()
        self.assertTrue(any("neutral registry requires 'backend'" in e for e in errors))

    def test_missing_role_contract_is_rejected_from_neutral_mapping(self):
        self.write_registry({"backend-1": "missing-role"})
        self.write_binding("backend-1", role="missing-role")
        self.assertTrue(any("missing Role contract" in e for e in self.errors()))

    def test_rendering_uses_neutral_role_when_legacy_role_conflicts(self):
        configuration = (b"name: backend-1\nmodel: opus\n"
                         b"role: conflicting-provider-role\n")
        content = renderer.render_content(
            "backend-1", "neutral-backend", configuration,
            b"NEUTRAL BACKEND CONTRACT\n"
        )
        self.assertIn(b"Role:    agent/roles/neutral-backend.md", content)
        self.assertIn(b"NEUTRAL BACKEND CONTRACT", content)
        self.assertNotIn(b"conflicting-provider-role", content)

    def test_renderer_writes_from_registry_and_check_detects_drift(self):
        self.write_registry({"backend-1": "backend"})
        self.write_role("backend")
        self.write_binding("backend-1")
        self.assertEqual(0, renderer.run(False, self.registry, self.bindings,
                                         self.roles, self.agents))
        self.assertEqual(0, renderer.run(True, self.registry, self.bindings,
                                         self.roles, self.agents))
        with open(os.path.join(self.agents, "backend-1.md"), "ab") as fh:
            fh.write(b"drift\n")
        self.assertEqual(1, renderer.run(True, self.registry, self.bindings,
                                         self.roles, self.agents))

    def test_check_rejects_generated_output_for_unknown_seat(self):
        self.write_registry({"backend-1": "backend"})
        self.write_role("backend")
        self.write_binding("backend-1")
        self.assertEqual(0, renderer.run(False, self.registry, self.bindings,
                                         self.roles, self.agents))
        with open(os.path.join(self.agents, "unknown.md"), "wb") as fh:
            fh.write(b"not owned by a neutral Seat\n")
        self.assertEqual(1, renderer.run(True, self.registry, self.bindings,
                                         self.roles, self.agents))


if __name__ == "__main__":
    unittest.main(verbosity=2)
