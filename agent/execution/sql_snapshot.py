"""Snapshot before destructive SQL (autonomy constitution, D-043, 2026-10-27).

Memphis owns DROP / DELETE / UPDATE / TRUNCATE on the approved Supabase project; the CEO is
never asked. What makes that safe is that it can be undone: before a statement that changes or
removes rows, the rows are copied into the `thebes_backup` schema. The SQL hook refuses the
destructive statement until a snapshot of its table was taken in the last `TTL_HOURS`, and
records every snapshot it lets through in a ledger.

    python3 -m agent.execution.sql_snapshot public.profiles [--where "id = '...'"] --ticket KAN-645

prints the SQL to run through execute_sql (one call), then run the destructive statement.
To restore: `insert into <schema.table> select * from thebes_backup.<backup>;` (rows), or
`create table <schema.table> as table thebes_backup.<backup>;` (a dropped table).
"""
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SCHEMA = "thebes_backup"
TTL_HOURS = 2
_IDENT = r"[a-z_][a-z0-9_$]*"
SNAPSHOT_STMT = re.compile(
    r"^create\s+table\s+(?:if\s+not\s+exists\s+)?" + SCHEMA + r"\s*\.\s*(" + _IDENT + r")\s+as\s+"
    r"(?:table\s+(?:only\s+)?(" + _IDENT + r"(?:\s*\.\s*" + _IDENT + r")?)|"
    r"select\s+\*\s+from\s+(?:only\s+)?(" + _IDENT + r"(?:\s*\.\s*" + _IDENT + r")?))", re.I)


def qualify(name):
    """`profiles` -> `public.profiles`; whitespace and case normalised."""
    name = re.sub(r"\s+", "", name or "").lower()
    return name if "." in name else "public." + name


def ledger_path():
    if os.environ.get("SQL_SNAPSHOT_LEDGER"):
        return os.environ["SQL_SNAPSHOT_LEDGER"]
    from agent.state import store
    return os.path.join(store.RUNTIME, "sql-snapshots.jsonl")


def backup_name(table, ticket=None, now=None):
    schema, tbl = qualify(table).split(".", 1)
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(now or time.time()))
    tail = "__" + stamp + ("__" + re.sub(r"[^a-z0-9]", "", ticket.lower()) if ticket else "")
    head = (schema + "__" + tbl)[:63 - len(tail)]
    return head + tail


def snapshot_sql(table, where=None, ticket=None, now=None):
    """(backup_name, sql) — one execute_sql call that copies the rows a statement will touch."""
    table = qualify(table)
    backup = backup_name(table, ticket, now)
    sql = ("create schema if not exists %s;\n"
           "revoke all on schema %s from public, anon, authenticated;\n"
           "create table %s.%s as select * from %s%s;"
           % (SCHEMA, SCHEMA, SCHEMA, backup, table, (" where " + where.strip().rstrip(";")) if where else ""))
    return backup, sql


def snapshots_in(statements):
    """[(backup, table)] for every snapshot statement among `statements` (top-level, lowercased ok)."""
    out = []
    for s in statements:
        m = SNAPSHOT_STMT.match(s.strip())
        if m:
            out.append((m.group(1).lower(), qualify(m.group(2) or m.group(3))))
    return out


def record(table, backup, team=None, now=None):
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time())),
             "epoch": int(now or time.time()), "table": qualify(table), "backup": backup, "team": team}
    path = ledger_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def recent(table, now=None, ttl_hours=TTL_HOURS):
    """The newest snapshot of `table` taken inside the window, or None."""
    want, cutoff = qualify(table), (now or time.time()) - ttl_hours * 3600
    best = None
    try:
        with open(ledger_path(), encoding="utf-8") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("table") == want and e.get("epoch", 0) >= cutoff:
                    best = e
    except OSError:
        return None
    return best


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    table, where, ticket = argv[0], None, None
    if "--where" in argv:
        where = argv[argv.index("--where") + 1]
    if "--ticket" in argv:
        ticket = argv[argv.index("--ticket") + 1]
    backup, sql = snapshot_sql(table, where, ticket)
    print("-- 1. run this through execute_sql (one call); the SQL hook records the snapshot:")
    print(sql)
    print("-- 2. then run the destructive statement on %s (allowed for %dh)." % (qualify(table), TTL_HOURS))
    print("-- restore rows:  insert into %s select * from %s.%s;" % (qualify(table), SCHEMA, backup))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
