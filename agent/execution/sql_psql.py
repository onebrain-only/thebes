#!/usr/bin/env python3
"""Run SQL on the approved Supabase project through psql, judged by the SQL hook first.

The Supabase connector asks the human to confirm any DROP / DELETE / TRUNCATE, in the terminal,
and nothing in Thebes can answer it. This is the same act on a path with no such prompt, so the
hook's rules are the only guard and they are not skipped:

    python3 -m agent.execution.sql_psql --file query.sql

* only a session bound to an `ops`-lane team may run it (the same test the SQL hook uses);
* the statement is judged by `sql_hook.decide`, the very function the connector path runs, so
  the never-list, the snapshot-before-destroy rule and the ledger entry all apply unchanged;
* the connection comes from `agent/state/runtime/psql.env` (ignored by git, mode 600) and its
  user must carry the approved project ref, so a wrong database is refused, not reached.

The connection string is never printed and never put on the command line: psql gets it through
PG* environment variables.
"""
import argparse
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))

ENV_FILE = os.path.join(ROOT, "agent", "state", "runtime", "psql.env")


def connection(env_file=None, project=None):
    """PG* environment for psql, or raise ValueError saying what is wrong (never the secret)."""
    path = env_file or ENV_FILE
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        raise ValueError("no %s: the CEO has not saved the connection string yet" % path)
    m = re.search(r"^DATABASE_URL=(\S+)\s*$", text, re.M)
    if not m:
        raise ValueError("%s has no DATABASE_URL= line" % path)
    u = urlparse(m.group(1))
    if u.scheme not in ("postgres", "postgresql") or not u.hostname or not u.username or not u.password:
        raise ValueError("DATABASE_URL in %s is not a postgres URI with a user and password" % path)
    if "[YOUR-PASSWORD]" in m.group(1):
        raise ValueError("DATABASE_URL in %s still holds the [YOUR-PASSWORD] placeholder" % path)
    if project and project not in u.username and project not in (u.hostname or ""):
        raise ValueError("DATABASE_URL does not belong to project %s; refusing" % project)
    return {"PGHOST": u.hostname, "PGPORT": str(u.port or 5432), "PGUSER": unquote(u.username),
            "PGPASSWORD": unquote(u.password), "PGDATABASE": (u.path or "/postgres").lstrip("/") or "postgres",
            "PGSSLMODE": "require"}


def run(sql_text, session_id, *, env_file=None, runner=None, state_store=None, teams_mod=None,
        allow_path=None):
    """(exit_code, message). Judges first, runs only on an allow from an ops session."""
    import ops_guard
    import sql_hook
    team, lane = ops_guard.team_of(session_id, state_store, teams_mod)
    if lane != "ops":
        return 2, ("Only the ops team (Memphis) runs SQL through psql. Commit the SQL on your branch "
                   "and report `blocked: needs-ops`.")
    reg = sql_hook.registry(allow_path)
    project = reg.get("project_id") or sql_hook.DEFAULT_PROJECT
    verdict = sql_hook.decide({"tool_name": sql_hook.TOOL, "session_id": session_id,
                               "tool_input": {"project_id": project, "query": sql_text}},
                              state_store=state_store, teams_mod=teams_mod, allow_path=allow_path)
    if not verdict or verdict.get("decision") != "allow":
        return 2, "REFUSED by the SQL hook: %s" % ((verdict or {}).get("reason") or "no decision")
    try:
        pg = connection(env_file, project)
    except ValueError as exc:
        return 3, str(exc)
    runner = runner or subprocess.run
    done = runner(["psql", "-X", "-v", "ON_ERROR_STOP=1", "-f", "-"], input=sql_text, text=True,
                  capture_output=True, env=dict(os.environ, **pg), timeout=600)
    out = (done.stdout or "") + (done.stderr or "")
    return (0 if done.returncode == 0 else 1), out.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file", required=True, help="the SQL to run")
    args = ap.parse_args(argv)
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
    code, msg = run(open(args.file, encoding="utf-8").read(), sid)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
