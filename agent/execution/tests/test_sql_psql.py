#!/usr/bin/env python3
"""sql_psql: the psql path obeys the SQL hook and never leaks the connection string."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

from agent.state import store, validate                               # noqa: E402
from agent.execution import sql_psql                                  # noqa: E402
import sql_hook                                                      # noqa: E402

KARNAK = "0aaaaaaa-8888-7000-8000-00000000000a"
MEMPHIS = "0ddddddd-8888-7000-8000-00000000000d"
OK = "wtncuzcskpigqpmnxwws"
SECRET = "s3cr3t-pw"


class SqlPsqlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("karnak", "claude", KARNAK, "/h", "ceo")
        store.bind_role_session("memphis", "claude", MEMPHIS, "/h", "ceo")
        self._mig = sql_hook.integrated_migrations
        sql_hook.integrated_migrations = lambda runner=None: []
        self.reg = os.path.join(self.tmp, "sql_allow.json")
        json.dump({"project_id": OK, "released_migrations": []}, open(self.reg, "w"))
        self.env = os.path.join(self.tmp, "psql.env")
        self.write_env("DATABASE_URL=postgresql://postgres.%s:%s@host.example:5432/postgres\n" % (OK, SECRET))
        self.calls = []
        os.environ["SQL_HOOK_LOG"] = os.path.join(self.tmp, "sql-hook.log")

    def tearDown(self):
        sql_hook.integrated_migrations = self._mig
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        os.environ.pop("SQL_HOOK_LOG", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_env(self, text):
        open(self.env, "w").write(text)

    def runner(self, cmd, **kw):
        self.calls.append((cmd, kw))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def go(self, sql, sid=MEMPHIS):
        return sql_psql.run(sql, sid, env_file=self.env, runner=self.runner, allow_path=self.reg)

    def test_a_read_from_the_ops_team_runs_and_the_secret_stays_in_the_environment(self):
        code, msg = self.go("select 1")
        self.assertEqual((code, msg), (0, "ok"))
        cmd, kw = self.calls[0]
        self.assertNotIn(SECRET, " ".join(cmd))
        self.assertEqual(kw["env"]["PGPASSWORD"], SECRET)

    def test_a_code_team_is_refused_and_nothing_runs(self):
        code, msg = self.go("select 1", sid=KARNAK)
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])

    def test_a_destructive_statement_still_needs_its_snapshot(self):
        code, msg = self.go("delete from public.posts where id = 1")
        self.assertEqual(code, 2)
        self.assertIn("snapshot", msg)
        self.assertEqual(self.calls, [])

    def test_the_never_list_still_applies(self):
        code, msg = self.go("grant all on public.posts to public")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])

    def test_a_connection_string_for_another_project_is_refused(self):
        self.write_env("DATABASE_URL=postgresql://postgres.otherproject:%s@host.example:5432/postgres\n" % SECRET)
        code, msg = self.go("select 1")
        self.assertEqual(code, 3)
        self.assertEqual(self.calls, [])
        self.assertNotIn(SECRET, msg)

    def test_the_placeholder_and_a_missing_file_are_named_not_run(self):
        self.write_env("DATABASE_URL=postgresql://postgres.%s:[YOUR-PASSWORD]@host.example:5432/postgres\n" % OK)
        self.assertEqual(self.go("select 1")[0], 3)
        os.remove(self.env)
        self.assertEqual(self.go("select 1")[0], 3)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
