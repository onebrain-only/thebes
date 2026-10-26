#!/usr/bin/env python3
"""SQL hook (maintenance 2026-10-13): Memphis's approved Messaging probes stop asking a human."""
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

    # -- the four cases the CEO named -------------------------------------------------
    def test_a_rollback_probe_on_the_approved_project_is_allowed_for_memphis(self):
        self.assertEqual(self.kind(PROBE), "allow")

    def test_the_wrong_project_is_denied_for_everyone(self):
        self.assertEqual(self.kind(PROBE, project=OTHER), "deny")
        self.assertEqual(self.kind("select 1", project=OTHER, sid=KARNAK), "deny")

    def test_drop_is_denied_even_inside_a_probe(self):
        self.assertEqual(self.kind("begin; drop table t; rollback;"), "deny")
        self.assertEqual(self.kind("begin; alter table t drop column a; rollback;"), "deny")

    def test_an_unlisted_write_asks_the_human(self):
        self.assertEqual(self.kind("insert into t(a) values (1)"), "ask")
        self.assertEqual(self.kind("update t set a = 2"), "ask")
        self.assertEqual(self.kind("create table x(a int)"), "ask")

    # -- more of the deny list ---------------------------------------------------------
    def test_the_rest_of_the_deny_list(self):
        for sql in ("truncate t", "delete from t", "begin; delete from t; rollback;",
                    "grant select on t to public", "grant all on t to anon",
                    "create extension pg_cron", "select pg_terminate_backend(1)",
                    "copy t to program 'x'", "select * from vault.secrets",
                    "select email from auth.users", "select * from auth.users",
                    "alter system set x = 1", "select pg_read_file('/etc/passwd')"):
            self.assertEqual(self.kind(sql), "deny", sql)

    def test_what_looks_scary_but_is_not_passes(self):
        self.assertEqual(self.kind("select 'drop table x' as note"), "allow", "inside a literal")
        self.assertEqual(self.kind("select 1 -- drop table x"), "allow", "inside a comment")
        self.assertEqual(self.kind("select count(*) from auth.users"), "allow")
        self.assertEqual(self.kind("begin; delete from t where a = 1; rollback;"), "allow")

    def test_code_inside_a_dollar_quoted_body_is_scanned(self):
        self.assertEqual(self.kind("begin; do $$ begin drop table t; end $$; rollback;"), "deny")

    def test_dynamic_sql_hides_nothing_and_is_never_auto_allowed(self):
        self.assertEqual(self.kind("do $$ begin execute 'drop table t'; end $$"), "deny")
        self.assertEqual(self.kind("begin; do $$ begin execute 'select 1'; end $$; rollback;"), "ask")

    # -- what a probe is ---------------------------------------------------------------
    def test_a_probe_must_begin_first_rollback_last_and_never_commit(self):
        for sql in ("begin; insert into t values (1); commit;",
                    "begin; insert into t values (1);",
                    "insert into t values (1); rollback;",
                    "begin; insert into t values (1); rollback; insert into t values (2); rollback;",
                    "begin; insert into t values (1); commit; insert into t values (2); rollback;",
                    "begin; do $$ begin commit; end $$; rollback;"):
            self.assertEqual(self.kind(sql), "ask", sql)
        self.assertEqual(self.kind("begin; savepoint s; insert into t values (1); "
                                   "rollback to savepoint s; rollback;"), "allow")

    # -- who it applies to -------------------------------------------------------------
    def test_only_the_ops_team_is_ever_allowed(self):
        self.assertEqual(self.kind(PROBE, sid=KARNAK), "ask", "the ops guard governs code teams")
        self.assertEqual(self.kind("select 1", sid="stranger"), "ask")
        self.assertIsNone(sql_hook.decide({"session_id": MEMPHIS, "tool_name": "Bash",
                                           "tool_input": {"command": "ls"}}, state_store=store))

    def test_unparseable_sql_asks(self):
        self.assertEqual(self.kind("select 'unterminated"), "ask")
        self.assertEqual(self.kind("select $x$ never closed"), "ask")

    # -- released migrations -----------------------------------------------------------
    def test_a_released_migration_passes_only_while_it_is_unchanged(self):
        sql = "create or replace function f() returns int language sql as $$ select 1 $$;"
        self.assertEqual(self.kind(sql), "ask")
        with open(self.reg, "w") as fh:
            json.dump({"project_id": OK, "released_migrations": [
                {"file": "m.sql", "sha256": sql_hook.sha(sql)}]}, fh)
        self.assertEqual(self.kind(sql), "allow")
        self.assertEqual(self.kind("  " + sql.replace(" ", "  ") + "\n"), "allow", "whitespace only")
        self.assertEqual(self.kind(sql.replace("select 1", "select 2")), "ask", "edited: un-released")
        self.assertEqual(self.kind("drop function f();"), "deny")

    # -- the one DROP exception: CEO 2026-10-26, KAN-644 -------------------------------------
    SWAP = ("alter table public.profiles drop constraint if exists profiles_persona_type_check;\n"
            "alter table public.profiles add constraint profiles_persona_type_check "
            "check (persona_type = any (array['player','contributor']));")

    def release(self, sql, marker=sql_hook.DROP_EXCEPTION):
        entry = {"file": "m.sql", "sha256": sql_hook.sha(sql)}
        if marker:
            entry["drop_exception"] = marker
        with open(self.reg, "w") as fh:
            json.dump({"project_id": OK, "released_migrations": [entry]}, fh)

    def test_a_released_migration_may_drop_exactly_the_persona_type_check(self):
        self.release(self.SWAP)
        self.assertEqual(self.kind(self.SWAP), "allow")
        self.assertEqual(self.kind("  " + self.SWAP.replace(" ", "  ") + "\n"), "allow", "whitespace only")

    def test_the_exception_needs_the_release_and_the_marker_and_the_ops_team(self):
        self.assertEqual(self.kind(self.SWAP), "deny", "unreleased")
        self.release(self.SWAP, marker=None)
        self.assertEqual(self.kind(self.SWAP), "deny", "released without the exception marker")
        self.release(self.SWAP, marker="some_other_constraint")
        self.assertEqual(self.kind(self.SWAP), "deny", "marker names another constraint")
        self.release(self.SWAP)
        self.assertEqual(self.kind(self.SWAP, sid=KARNAK), "deny", "code teams never")
        self.assertEqual(self.kind(self.SWAP, project=OTHER), "deny", "other project")
        self.assertEqual(self.kind(self.SWAP.replace("player", "player2")), "deny", "edited: un-released")

    def test_every_other_drop_stays_denied_in_a_released_exception_migration(self):
        ok = "alter table public.profiles drop constraint if exists profiles_persona_type_check;\n"
        for body in ("alter table public.profiles drop constraint if exists profiles_other_check;",
                     "alter table public.profiles drop constraint profiles_persona_type_check;",
                     "alter table public.profiles drop constraint if exists profiles_persona_type_check cascade;",
                     "alter table public.profiles drop constraint if exists profiles_persona_type_check, "
                     "drop column onboard;",
                     "alter table public.profiles drop column onboard;",
                     "alter table public.player drop constraint if exists profiles_persona_type_check;",
                     "alter table profiles drop constraint if exists profiles_persona_type_check;",
                     "alter table public.profiles drop constraint if exists \"profiles_persona_type_check\";",
                     "drop trigger if exists trg_player_profile_persona_guard on public.player;",
                     "drop function public.trgfn_limit_active_profiles();",
                     "drop table public.profiles;",
                     "drop schema public cascade;",
                     "drop index if exists idx_one_active_profile_per_user;",
                     "truncate public.profiles;",
                     "do $$ begin alter table public.profiles drop constraint if exists "
                     "profiles_persona_type_check; end $$;"):
            sql = ok + body
            self.release(sql)
            self.assertEqual(self.kind(sql), "deny", body)
        only_hidden = "do $$ begin execute 'alter table public.profiles drop constraint if exists " \
                      "profiles_persona_type_check'; end $$;"
        self.release(only_hidden)
        self.assertEqual(self.kind(only_hidden), "deny", "inside dynamic SQL")
        for body in ("drop table public.profiles;", "truncate public.profiles;"):
            self.release(body)
            self.assertEqual(self.kind(body), "deny", "no allowed statement at all: " + body)

    def test_release_cli_refuses_the_exception_unless_asked_and_pins_the_marker(self):
        import contextlib
        import io
        path = os.path.join(self.tmp, "m.sql")
        with open(path, "w") as fh:
            fh.write(self.SWAP)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sql_hook.release_cli([path]), 2)
        self.assertIn("refused", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sql_hook.release_cli([path, "--allow-persona-check-drop"]), 0)
        entry = json.loads(out.getvalue())
        self.assertEqual(entry["drop_exception"], "profiles_persona_type_check")
        self.assertEqual(entry["sha256"], sql_hook.sha(self.SWAP))
        with open(path, "w") as fh:
            fh.write(self.SWAP + "\ndrop table public.profiles;")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sql_hook.release_cli([path, "--allow-persona-check-drop"]), 2)

    # -- integrated migrations: a technical approval is not the CEO's (2026-10-14) ----------
    MIG = ("-- KAN-522\nbegin;\ncreate or replace function public.f() returns int language sql as "
           "$$ select 1; $$;\nrevoke all on function public.f() from public;\n"
           "grant execute on function public.f() to authenticated;\n"
           "do $$ begin assert true; end $$;\ncommit;\n")

    def dm(self, query, files, sid=MEMPHIS):
        r = sql_hook.decide({"session_id": sid, "tool_name": TOOL, "_migrations": files,
                             "tool_input": {"project_id": OK, "query": query}},
                            state_store=store, allow_path=self.reg)
        return r["decision"] if r else "ask"

    def test_sql_that_is_a_statement_or_the_whole_of_an_integrated_migration_needs_no_human(self):
        files = [("supabase/migrations/20261013_x.sql", self.MIG)]
        stmt = "create or replace function public.f() returns int language sql as $$ select 1; $$"
        self.assertEqual(self.dm(stmt, files), "allow", "one statement")
        self.assertEqual(self.dm("revoke all on function public.f() from public;", files), "allow")
        self.assertEqual(self.dm(self.MIG, files), "allow", "the whole file")
        self.assertEqual(self.dm("  " + stmt.replace(" ", "   ") + " ;", files), "allow", "whitespace only")

    def test_anything_not_in_an_integrated_file_still_asks_or_is_denied(self):
        files = [("supabase/migrations/20261013_x.sql", self.MIG)]
        self.assertEqual(self.dm("create or replace function public.f() returns int language sql as "
                                 "$$ select 2; $$", files), "ask", "edited text")
        self.assertEqual(self.dm("create or replace function public.g() returns int language sql as "
                                 "$$ select 1; $$", files), "ask", "a different function")
        self.assertEqual(self.dm("select 1", []), "allow", "read-only is allowed anyway")
        self.assertEqual(self.dm("update t set a = 1", files), "ask")
        self.assertEqual(self.dm("drop function public.f()", files), "deny")
        self.assertEqual(self.dm("create or replace function public.f() returns int language sql as "
                                 "$$ select 1; $$", files, sid=KARNAK), "ask", "code teams never")

    def test_a_migration_with_data_changes_or_drops_never_qualifies(self):
        for body in ("update t set a = 1;", "insert into t values (1);", "drop table t;",
                     "alter table t drop column a;", "delete from t where a = 1;"):
            mig = self.MIG + body
            files = [("supabase/migrations/20261013_y.sql", mig)]
            stmt = "revoke all on function public.f() from public"
            self.assertEqual(self.dm(stmt, files), "ask", body)
        self.assertEqual(self.dm("select 'x'", []), "allow")

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
        out = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        junk = subprocess.run([sys.executable, os.path.join(ROOT, "agent", "scripts", "sql_hook.py")],
                              input="not json", capture_output=True, text=True, env=env)
        self.assertEqual((junk.returncode, junk.stdout), (0, ""), "bad input: normal prompt")


if __name__ == "__main__":
    unittest.main()
