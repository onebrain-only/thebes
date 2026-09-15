#!/usr/bin/env python3
"""The Product executor's standing tools and its subprocess environment.

Both exist because live Product operation proved they were needed, and both are
places where a careless future edit would quietly widen what an executor may do.
These tests are written against that risk.

No provider is launched. No Jira, no Supabase, no Product repository.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.execution import claude                               # noqa: E402
from agent.execution import codex                                # noqa: E402
from agent.execution.brief import CONTROL_PLANE_TOKENS           # noqa: E402


class StandingToolSet(unittest.TestCase):
    """What an executor may do without asking, and what it may never do."""

    def test_the_standing_set_is_exactly_the_authorized_five(self):
        self.assertEqual(
            ("Read", "Bash", "Edit", "Write", "mcp__claude_ai_Supabase__execute_sql"),
            claude.standing_tools())

    def test_production_mutation_is_never_standing(self):
        # The boundary Product execution has held since Phase 2. If this ever
        # passes with apply_migration in the set, a CEO act has become an
        # executor default.
        self.assertIn("mcp__claude_ai_Supabase__apply_migration", claude.NEVER_STANDING)
        for forbidden in claude.NEVER_STANDING:
            self.assertNotIn(forbidden, claude.standing_tools())

    def test_standing_tools_refuses_a_forbidden_addition_at_call_time(self):
        original = claude.STANDING_PRODUCT_EXECUTOR_TOOLS
        try:
            claude.STANDING_PRODUCT_EXECUTOR_TOOLS = original + (
                "mcp__claude_ai_Supabase__apply_migration",)
            with self.assertRaises(claude.ClaudeWakeError):
                claude.standing_tools()
        finally:
            claude.STANDING_PRODUCT_EXECUTOR_TOOLS = original

    def test_no_standing_tool_is_a_control_plane_identifier(self):
        # An executor's working tools must not be Thebes's own machinery.
        for tool in claude.standing_tools():
            for token in CONTROL_PLANE_TOKENS:
                self.assertNotIn(token.lower(), tool.lower())

    def test_the_standing_set_grants_no_orchestration_capability(self):
        for tool in claude.standing_tools():
            for orchestration in ("agent.controller", "agent.listener", "agent.core",
                                  "agent.execution", "lease", "claim", "approval",
                                  "continuation", "provider"):
                self.assertNotIn(orchestration, tool.lower())


class ExecutorEnvironment(unittest.TestCase):
    """Deterministic enough to work; narrow enough not to be a side channel."""

    def test_developer_dir_is_set_when_the_command_line_tools_exist(self):
        resolved = claude.developer_dir()
        if resolved is None:
            self.skipTest("Command Line Tools are not installed on this machine")
        self.assertEqual("/Library/Developer/CommandLineTools", resolved)
        self.assertTrue(os.path.isdir(resolved))

    def test_the_environment_pins_developer_dir_for_the_subprocess(self):
        env = claude.executor_environment(environ={"PATH": "/usr/bin"},
                                          developer_dir_path="/tmp/clt")
        self.assertEqual("/tmp/clt", env["DEVELOPER_DIR"])
        self.assertEqual("/usr/bin", env["PATH"])

    def test_an_absent_toolchain_leaves_the_inherited_environment_alone(self):
        # Pinning a path that does not exist would be worse than not pinning:
        # it would break a machine that was working.
        env = claude.executor_environment(environ={"PATH": "/usr/bin"},
                                          developer_dir_path="")
        self.assertNotIn("DEVELOPER_DIR", env)

    def test_the_environment_carries_no_control_plane_state(self):
        # An executor's environment is not a back door for the orchestration
        # facts the brief firewall keeps out of its prompt.
        env = claude.executor_environment(environ={"PATH": "/usr/bin"})
        for leaked in ("THEBES_LISTENER_INTENT_ID", "INVOCATION_ID", "EXECUTION_LEASE_ID",
                       "CLAIM_REF", "SEAT_ID", "OPERATING_MODE"):
            self.assertNotIn(leaked, env)

    def test_it_adds_nothing_but_developer_dir(self):
        before = {"PATH": "/usr/bin", "HOME": "/tmp"}
        after = claude.executor_environment(environ=before, developer_dir_path="/tmp/clt")
        self.assertEqual({"DEVELOPER_DIR"}, set(after) - set(before))

    def test_both_providers_use_the_same_environment_builder(self):
        # A provider-neutral contract that left one toolchain broken would not
        # be provider-neutral.
        self.assertIs(claude.executor_environment, codex.executor_environment)


class AllowedToolsCommand(unittest.TestCase):
    """What actually reaches the CLI."""

    class Wake:
        model = "opus"
        effort = "high"
        session_ref = None
        session_id = None
        prompt = "Fix the RLS policy on public.profiles."
        approved_permissions = ()

    def test_the_standing_set_reaches_the_command_line(self):
        command = claude.ClaudeCliTransport().command(self.Wake())
        self.assertIn("--allowedTools", command)
        allowed = command[command.index("--allowedTools") + 1].split(",")
        self.assertEqual(list(claude.standing_tools()), allowed)

    def test_an_invocation_scoped_grant_is_additive_and_exact(self):
        wake = self.Wake()
        wake.approved_permissions = ("mcp__claude_ai_Supabase__apply_migration",)
        command = claude.ClaudeCliTransport().command(wake)
        allowed = command[command.index("--allowedTools") + 1].split(",")
        # The CEO may still approve a production mutation for ONE invocation.
        # What must never happen is that grant becoming standing — and it has
        # not: it is present here and absent from the standing set.
        self.assertIn("mcp__claude_ai_Supabase__apply_migration", allowed)
        self.assertNotIn("mcp__claude_ai_Supabase__apply_migration",
                         claude.standing_tools())

    def test_a_duplicate_grant_is_not_listed_twice(self):
        wake = self.Wake()
        wake.approved_permissions = ("Bash",)
        command = claude.ClaudeCliTransport().command(wake)
        allowed = command[command.index("--allowedTools") + 1].split(",")
        self.assertEqual(1, allowed.count("Bash"))

    def test_the_prompt_is_still_separated_from_the_tool_list(self):
        command = claude.ClaudeCliTransport().command(self.Wake())
        self.assertEqual(self.Wake.prompt, command[-1])
        self.assertEqual("--", command[-2])

    def test_permission_prompts_remain_off(self):
        # Standing tools remove the round-trip for ORDINARY work. They do not
        # turn on interactive approval for anything else: an unlisted tool is
        # still denied and still returns as needs_input.
        command = claude.ClaudeCliTransport().command(self.Wake())
        self.assertIn("none", command)
        self.assertIn("dontAsk", command)


if __name__ == "__main__":
    unittest.main(verbosity=2)
