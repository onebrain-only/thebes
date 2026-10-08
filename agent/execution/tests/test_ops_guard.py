#!/usr/bin/env python3
"""Ops guard (D-042): only the operations team writes to the database or pushes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

from agent.state import store, teams, validate                       # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402
import ops_guard                                                     # noqa: E402

ORCH = "0eeeeeee-7777-7000-8000-00000000000e"
KARNAK = "0aaaaaaa-7777-7000-8000-00000000000a"
MEMPHIS = "0ddddddd-7777-7000-8000-00000000000d"
STRANGER = "0fffffff-7777-7000-8000-00000000000f"
HOME = "/stable/home"
SB = "mcp__claude_ai_Supabase__"


class OpsGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("karnak", "claude", KARNAK, HOME, "ceo")
        store.bind_role_session("memphis", "claude", MEMPHIS, HOME, "ceo")

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def decide(self, sid, tool, **tool_input):
        return ops_guard.decide({"session_id": sid, "tool_name": tool, "tool_input": tool_input},
                                state_store=store)

    def test_memphis_is_registered_as_the_ops_lane(self):
        self.assertEqual(list(teams.lane_teams("ops")), ["memphis"])
        self.assertNotIn("memphis", teams.lane_teams("code"))

    def test_only_the_ops_team_may_write_to_the_database(self):
        for tool in ("apply_migration", "execute_sql"):
            self.assertIsNone(self.decide(MEMPHIS, SB + tool), tool)
            for sid in (KARNAK, ORCH, STRANGER, None):
                why = self.decide(sid, SB + tool)
                self.assertIsNotNone(why, (sid, tool))
                self.assertIn("Memphis", why)

    def test_read_only_sql_is_allowed_for_every_session(self):
        """Live 2026-10-09: the guard refused the cto and the PM a read-only check."""
        for q in ("select count(*) from public.venues where is_active = true",
                  "SELECT pg_get_functiondef('public.rpc_create_game'::regprocedure)",
                  "with x as (select 1) select * from x",
                  "select has_function_privilege('anon', 'public.f(uuid)', 'EXECUTE');",
                  "-- check\nselect name from public.games where name = 'drop table x'"):
            self.assertIsNone(self.decide(KARNAK, SB + "execute_sql", query=q), q)
        for q in ("delete from public.games", "select 1; drop table x",
                  "select public.rpc_delete_my_account()", "select nextval('s')",
                  "create table x(i int)", "select * into t from games", "",
                  "update games set x = 1 returning *", "select set_config('a','b',false)"):
            self.assertIsNotNone(self.decide(KARNAK, SB + "execute_sql", query=q), q)
        self.assertIsNotNone(self.decide(KARNAK, SB + "apply_migration", query="select 1"),
                             "a migration is never a read")

    def test_reads_are_never_touched(self):
        for sid in (KARNAK, STRANGER):
            self.assertIsNone(self.decide(sid, SB + "list_migrations"))
            self.assertIsNone(self.decide(sid, SB + "list_tables"))

    def test_project_destroying_tools_stay_with_the_ceo_even_for_ops(self):
        for tool in ("pause_project", "delete_branch", "restore_project"):
            self.assertIn("CEO", self.decide(MEMPHIS, SB + tool))

    def test_code_teams_cannot_push_and_others_keep_their_rules(self):
        for cmd in ("git push origin alpha-karnak", "cd x && git push",
                    "git -C Dabbler/dabbler-code push origin Alpha"):
            self.assertIsNotNone(self.decide(KARNAK, "Bash", command=cmd), cmd)
            self.assertIsNone(self.decide(MEMPHIS, "Bash", command=cmd), cmd)
            self.assertIsNone(self.decide(STRANGER, "Bash", command=cmd), cmd)
        self.assertIsNone(self.decide(KARNAK, "Bash", command="git commit -m 'KAN-1: push it'"))
        self.assertIsNone(self.decide(KARNAK, "Bash", command="git status"))

    def test_the_hook_refuses_with_exit_2_and_fails_closed_on_db_writes(self):
        hook = os.path.join(ROOT, "agent", "scripts", "ops-guard.sh")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        # An unbound session in the live runtime is refused a database write.
        run = subprocess.run([hook], input=json.dumps({"session_id": STRANGER,
                                                        "tool_name": SB + "apply_migration"}),
                             capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 2)
        self.assertIn("REFUSED by ops guard", run.stderr)
        run = subprocess.run([hook], input="not json", capture_output=True, text=True, env=env)
        self.assertEqual(run.returncode, 0, "unparseable input gets no opinion")

    def test_the_envelope_tells_each_lane_its_rules(self):
        base = {"dispatch_id": "cdispatch-x", "delivery_id": "cdispatch-x",
                "target_session_id": KARNAK}
        code = "\n".join(cd.team_block(dict(base, target_seat_id="karnak")))
        ops = "\n".join(cd.team_block(dict(base, target_seat_id="memphis")))
        self.assertIn("you are a CODE team", code)
        self.assertIn("needs-ops", code)
        self.assertIn("OPERATIONS team (Memphis", ops)
        self.assertIn("C: DROP TABLE/COLUMN", ops)
        self.assertNotIn("you are a CODE team", ops)


if __name__ == "__main__":
    unittest.main()
