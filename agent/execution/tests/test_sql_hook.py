#!/usr/bin/env python3
"""SQL hook: Memphis gets allow or deny with the alternative, never a prompt (D-043, 2026-10-27)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

from agent.state import store, validate                               # noqa: E402
import sql_hook                                                      # noqa: E402

KARNAK = "0aaaaaaa-8888-7000-8000-00000000000a"
MEMPHIS = "0ddddddd-8888-7000-8000-00000000000d"
OK = "wtncuzcskpigqpmnxwws"
OTHER = "someotherprojectid0001"
TOOL = sql_hook.TOOL
PROBE = "begin;\ninsert into t(a) values (1);\nselect count(*) from t;\nrollback;"


class SqlHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("karnak", "claude", KARNAK, "/h", "ceo")
        store.bind_role_session("memphis", "claude", MEMPHIS, "/h", "ceo")
        self._real_mig = sql_hook.integrated_migrations
        sql_hook.integrated_migrations = lambda runner=None: []     # never hit git in tests
        self.reg = os.path.join(self.tmp, "sql_allow.json")
        with open(self.reg, "w") as fh:
            json.dump({"project_id": OK, "released_migrations": []}, fh)

    def tearDown(self):
        sql_hook.integrated_migrations = self._real_mig
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def d(self, query, sid=MEMPHIS, project=OK):
        return sql_hook.decide({"session_id": sid, "tool_name": TOOL,
                                "tool_input": {"project_id": project, "query": query}},
                               state_store=store, allow_path=self.reg)

    def kind(self, query, **kw):
        r = self.d(query, **kw)
        return r["decision"] if r else "ask"

    # -- the constitution (D-043): Memphis gets allow or deny, never a prompt ---------------
    def test_a_rollback_probe_on_the_approved_project_is_allowed_for_memphis(self):
        self.assertEqual(self.kind(PROBE), "allow")

    def test_the_wrong_project_is_denied_for_everyone(self):
        self.assertEqual(self.kind(PROBE, project=OTHER), "deny")
        self.assertEqual(self.kind("select 1", project=OTHER, sid=KARNAK), "deny")

    def test_memphis_never_gets_a_prompt(self):
        for sql in ("insert into t(a) values (1)", "create table x(a int)", "update t set a = 2",
                    "drop table t", "select 'unterminated", "", "create extension pg_cron",
                    "do $$ begin execute 'drop table t'; end $$", "drop schema public cascade"):
            self.assertIn(self.kind(sql), ("allow", "deny"), sql)

    def test_additive_writes_are_allowed_for_ops(self):
        for sql in ("insert into t(a) values (1)", "create table x(a int)",
                    "create or replace function f() returns int language sql as $$ select 1 $$",
                    "create extension pg_cron", "drop function public.f()", "drop index i",
                    "alter table t drop constraint c", "grant select on t to authenticated",
                    "drop trigger if exists tr on public.t", "drop policy p on t"):
            self.assertEqual(self.kind(sql), "allow", sql)

    def test_a_destructive_statement_needs_a_snapshot_and_says_how(self):
        for sql in ("update t set a = 2", "delete from t where a = 1", "delete from t",
                    "truncate t", "drop table t", "alter table t drop column a",
                    "do $$ begin update t set a = 1; end $$"):
            r = self.d(sql)
            self.assertEqual(r["decision"], "deny", sql)
            self.assertIn("python3 -m agent.execution.sql_snapshot public.t", r["reason"])
            self.assertNotIn("ask the CEO", r["reason"])

    def test_a_snapshot_in_the_same_call_or_in_the_last_two_hours_lets_it_through(self):
        from agent.execution import sql_snapshot
        _, snap = sql_snapshot.snapshot_sql("t", "a = 1", "KAN-1")
        self.assertEqual(self.kind(snap + "\ndelete from public.t where a = 1;"), "allow")
        self.assertEqual(self.kind("update t set a = 2"), "allow", "recorded by the call above")
        self.assertEqual(self.kind("update public.other set a = 2"), "deny", "another table")
        later = sql_snapshot.time.time() + 3 * 3600
        r = sql_hook.decide({"session_id": MEMPHIS, "tool_name": TOOL,
                             "tool_input": {"project_id": OK, "query": "update t set a = 3"}},
                            state_store=store, allow_path=self.reg, now=later)
        self.assertEqual(r["decision"], "deny", "the window closed")

    def test_a_snapshot_alone_is_allowed_and_recorded(self):
        from agent.execution import sql_snapshot
        backup, snap = sql_snapshot.snapshot_sql("public.profiles", ticket="KAN-645")
        self.assertEqual(self.kind(snap), "allow")
        self.assertEqual(sql_snapshot.recent("profiles")["backup"], backup)

    def test_a_function_body_only_defines_code_and_needs_no_snapshot(self):
        fn = ("create or replace function public.trg() returns trigger language plpgsql as $$ "
              "begin update public.t set a = 1 where id = new.id; delete from public.u where x = 1; "
              "execute 'delete from public.v'; return new; end $$;")
        self.assertEqual(self.kind(fn), "allow")
        self.assertEqual(self.kind(fn + " update public.t set a = 2;"), "deny", "the UPDATE outside runs")
        self.assertEqual(self.kind("create function f() returns void language sql as $$ "
                                   "select * from vault.secrets $$"), "deny", "never-list still scans bodies")

    def test_a_table_created_in_the_same_call_needs_no_snapshot(self):
        self.assertEqual(self.kind("create table s(a int); insert into s values (1); "
                                   "update s set a = 2; drop table s;"), "allow")

    def test_inside_a_probe_destructive_sql_is_allowed(self):
        for sql in ("begin; drop table t; rollback;", "begin; alter table t drop column a; rollback;",
                    "begin; delete from t; rollback;", "begin; update t set a = 1; rollback;"):
            self.assertEqual(self.kind(sql), "allow", sql)

    def test_the_never_list_is_denied_with_the_alternative(self):
        for sql in ("grant select on t to public", "grant all on t to anon",
                    "select pg_terminate_backend(1)", "copy t to program 'x'",
                    "select * from vault.secrets", "select email from auth.users",
                    "alter system set x = 1", "select pg_read_file('/etc/passwd')",
                    "drop schema public cascade", "drop extension pg_cron", "drop role x",
                    "begin; select * from vault.secrets; rollback;",
                    "drop table thebes_backup.public__t__20261027000000"):
            r = self.d(sql)
            self.assertEqual(r["decision"], "deny", sql)
            self.assertIn("never take it to the CEO", r["reason"])

    def test_what_looks_scary_but_is_not_passes(self):
        self.assertEqual(self.kind("select 'drop table x' as note"), "allow", "inside a literal")
        self.assertEqual(self.kind("select 1 -- drop table x"), "allow", "inside a comment")
        self.assertEqual(self.kind("select count(*) from auth.users"), "allow")
        self.assertEqual(self.kind("select md5(prosrc) from pg_proc where proname = 'f'"), "allow")

    def test_dynamic_sql_that_removes_rows_must_be_written_out(self):
        self.assertEqual(self.kind("do $$ begin execute 'drop table t'; end $$"), "deny")
        self.assertEqual(self.kind("do $$ begin execute 'delete from t'; end $$"), "deny")
        self.assertEqual(self.kind("begin; do $$ begin execute 'select 1'; end $$; rollback;"), "allow")
        self.assertEqual(self.kind("do $$ begin execute format('grant select on %I to authenticated', 't'); "
                                   "end $$"), "allow")
        self.assertEqual(self.kind("do $$ begin execute 'grant all on t to anon'; end $$"), "deny")

    def test_a_non_probe_transaction_is_judged_on_its_statements(self):
        self.assertEqual(self.kind("begin; insert into t values (1); commit;"), "allow")
        self.assertEqual(self.kind("begin; delete from t where a = 1; commit;"), "deny")
        self.assertEqual(self.kind("begin; delete from t; commit; rollback;"), "deny")

    def test_unparseable_sql_is_denied_for_ops_with_the_fix(self):
        for sql in ("select 'unterminated", "select $x$ never closed"):
            r = self.d(sql)
            self.assertEqual(r["decision"], "deny")
            self.assertIn("Close the quote", r["reason"])
        self.assertEqual(self.kind("select 'unterminated", sid=KARNAK), "ask", "the ops guard governs")

    # -- other sessions ---------------------------------------------------------------------
    def test_other_sessions_read_freely_and_are_refused_writes_elsewhere(self):
        self.assertEqual(self.kind("select 1", sid="stranger"), "allow")
        self.assertEqual(self.kind("select 1", sid=KARNAK), "allow")
        self.assertEqual(self.kind(PROBE, sid=KARNAK), "ask", "the ops guard refuses code-team writes")
        self.assertEqual(self.kind("drop table t", sid=KARNAK), "deny")
        self.assertIsNone(sql_hook.decide({"session_id": MEMPHIS, "tool_name": "Bash",
                                           "tool_input": {"command": "ls"}}, state_store=store))

    def test_a_released_migration_is_labelled(self):
        sql = "create or replace function f() returns int language sql as $$ select 1 $$;"
        with open(self.reg, "w") as fh:
            json.dump({"project_id": OK, "released_migrations": [
                {"file": "m.sql", "sha256": sql_hook.sha(sql)}]}, fh)
        r = self.d(sql)
        self.assertEqual(r["decision"], "allow")
        self.assertIn("released-migration", r["reason"])

    def test_release_cli_still_pins_the_persona_exception(self):
        import contextlib
        import io
        swap = ("alter table public.profiles drop constraint if exists profiles_persona_type_check;\n"
                "alter table public.profiles add constraint profiles_persona_type_check "
                "check (persona_type = any (array['player','contributor']));")
        path = os.path.join(self.tmp, "m.sql")
        with open(path, "w") as fh:
            fh.write(swap)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sql_hook.release_cli([path, "--allow-persona-check-drop"]), 0)
        self.assertEqual(json.loads(out.getvalue())["drop_exception"], "profiles_persona_type_check")
        self.assertEqual(self.kind(swap), "allow", "and the swap itself needs no snapshot")

    def test_the_statement_splitter_respects_quotes_comments_and_dollar_bodies(self):
        text = "select 'a;b'; -- c;d\ncreate function f() returns int as $$ select 1; select 2; $$ language sql; select 3"
        self.assertEqual(sql_hook.split_statements(text), [
            "select 'a;b'", "-- c;d\ncreate function f() returns int as $$ select 1; select 2; $$ language sql",
            "select 3"])

    # -- the log -----------------------------------------------------------------------
    def test_every_decision_is_logged_without_literals_or_secrets(self):
        self.kind("begin; insert into t(a) values ('hunter2-secret'); rollback;")
        self.kind("select 1", project=OTHER)
        with open(os.path.join(store.RUNTIME, "sql-hook.log")) as fh:
            rows = [json.loads(l) for l in fh]
        self.assertEqual([r["decision"] for r in rows], ["allow", "deny"])
        self.assertNotIn("hunter2", json.dumps(rows))
        self.assertLessEqual(max(len(r["query"]) for r in rows), 80)

    # -- the real entry point ----------------------------------------------------------
    def test_the_script_prints_the_permission_decision_json(self):
        env = dict(os.environ, SQL_HOOK_LOG=os.path.join(self.tmp, "hook.log"))
        payload = {"session_id": "x", "tool_name": TOOL,
                   "tool_input": {"project_id": OTHER, "query": "select 1"}}
        done = subprocess.run([sys.executable, os.path.join(ROOT, "agent", "scripts", "sql_hook.py")],
                              input=json.dumps(payload), capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(done.stdout, done.stderr)
        out = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        junk = subprocess.run([sys.executable, os.path.join(ROOT, "agent", "scripts", "sql_hook.py")],
                              input="not json", capture_output=True, text=True, env=env)
        self.assertEqual((junk.returncode, junk.stdout), (0, ""), "bad input: normal prompt")


if __name__ == "__main__":
    unittest.main()
