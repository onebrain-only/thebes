#!/usr/bin/env python3
"""SQL hook — PreToolUse hook for `mcp__claude_ai_Supabase__execute_sql`.

Autonomy constitution (D-043, CEO 2026-10-27): the database is Memphis's, never the CEO's, and
this hook ANSWERS every ops query — allow or deny with the alternative — so no permission prompt
ever reaches a human. A refusal is an answer: the team reads it and continues; it is never a
question for the CEO.

    DENY    everyone: another Supabase project; GRANT to public/anon; vault.* / auth secret
            columns; server files, COPY PROGRAM, dblink, pg_terminate_backend, ALTER SYSTEM/ROLE;
            DROP SCHEMA/DATABASE/OWNED/ROLE/EXTENSION; dropping a thebes_backup snapshot.
    ALLOW   ops (Memphis), everything else on the approved project. A statement that removes or
            changes rows — DROP TABLE, DROP COLUMN, TRUNCATE, DELETE, UPDATE — needs a snapshot
            of its table first (agent/execution/sql_snapshot.py, taken in the last 2h or at the
            start of the same call); without one it is refused with the exact command to run.
            Inside BEGIN … ROLLBACK (a probe) nothing persists, so no snapshot is needed.
    ALLOW   everyone else: a read-only query. Their writes are refused by the ops guard.

Comments and string literals are stripped before the keyword scans (a 'drop' inside a literal or
a comment is not a DROP). Dollar-quoted bodies (function / DO blocks) are NOT stripped: they are
code, and are scanned. Dynamic SQL (an EXECUTE outside a literal) also scans the literals.

Every decision is logged to agent/state/runtime/sql-hook.log: time, team, project id, decision,
reason, the first 80 characters of the query with every string literal and long token masked.

    python3 agent/scripts/sql_hook.py release <migration.sql> [--write]   # maintenance only

Exit code is always 0; the decision is the JSON on stdout.
"""
import hashlib
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TOOL = "mcp__claude_ai_Supabase__execute_sql"
DEFAULT_PROJECT = "wtncuzcskpigqpmnxwws"
ALLOW_FILE = os.path.join(ROOT, "agent", "state", "registry", "sql_allow.json")


class LexError(Exception):
    pass


# ------------------------------------------------------------------------------- lexer
_DOLLAR = re.compile(r"\$([A-Za-z_]\w*)?\$")


def lex(text):
    """(top, scan, lit): three views of the SQL with comments removed.

    top   statements' skeleton: strings -> '', dollar bodies -> $$   (split on ';' for statements)
    scan  strings -> '', dollar bodies replaced by their own scan view (code is scanned)
    lit   like scan but string literal content kept (used when the SQL builds SQL dynamically)
    """
    top, scan, lit = [], [], []
    i, n = 0, len(text)
    while i < n:
        c, two = text[i], text[i:i + 2]
        if two == "--":
            j = text.find("\n", i)
            i = n if j < 0 else j
            for v in (top, scan, lit):
                v.append(" ")
        elif two == "/*":
            depth, j = 1, i + 2
            while depth:
                a, b = text.find("/*", j), text.find("*/", j)
                if b < 0:
                    raise LexError("unterminated block comment")
                if 0 <= a < b:
                    depth, j = depth + 1, a + 2
                else:
                    depth, j = depth - 1, b + 2
            i = j
            for v in (top, scan, lit):
                v.append(" ")
        elif c == "'":
            escape = i > 0 and text[i - 1] in "eE" and (i < 2 or not (text[i - 2].isalnum() or text[i - 2] == "_"))
            j = i + 1
            while True:
                if j >= n:
                    raise LexError("unterminated string")
                if escape and text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "'":
                    if text[j + 1:j + 2] == "'":
                        j += 2
                        continue
                    break
                j += 1
            top.append("''")
            scan.append("''")
            lit.append("'" + text[i + 1:j] + "'")
            i = j + 1
        elif c == '"':
            j = i + 1
            while True:
                if j >= n:
                    raise LexError("unterminated identifier")
                if text[j] == '"':
                    if text[j + 1:j + 2] == '"':
                        j += 2
                        continue
                    break
                j += 1
            top.append('""')
            scan.append('""')
            lit.append(text[i:j + 1])
            i = j + 1
        elif c == "$" and not (i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_")) \
                and _DOLLAR.match(text, i):
            m = _DOLLAR.match(text, i)
            end = text.find(m.group(0), m.end())
            if end < 0:
                raise LexError("unterminated dollar quote")
            body_top, body_scan, body_lit = lex(text[m.end():end])
            top.append("$$")
            scan.append(" " + body_scan + " ")
            lit.append(" " + body_lit + " ")
            i = end + len(m.group(0))
        else:
            for v in (top, scan, lit):
                v.append(c)
            i += 1
    return "".join(top), "".join(scan), "".join(lit)


# ------------------------------------------------------------------------------ the rules
DENY = (
    ("drop", re.compile(r"\bdrop\b")),
    ("truncate", re.compile(r"\btruncate\b")),
    ("grant-to-public", None),                       # judged by _grant_to_public (KAN-845 carve-out)
    ("create-extension", re.compile(r"\bcreate\s+extension\b")),
    ("pg-terminate", re.compile(r"\bpg_(terminate|cancel)_backend\b")),
    ("copy-program-or-file", re.compile(r"\bcopy\b[^;]*\b(program|from\s+''|to\s+'')")),
    ("server-files", re.compile(r"\b(pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|"
                                r"lo_import|lo_export)\b")),
    ("secrets-vault", re.compile(r"\bvault\s*\.|\bdecrypted_secrets\b")),
    ("alter-system-or-role", re.compile(r"\balter\s+(system|role|user)\b|\bcreate\s+(role|user)\b")),
    ("dblink", re.compile(r"\bdblink\w*\b|\bpostgres_fdw\b")),
)
GRANT_TO_PUBLIC = re.compile(r"\bgrant\b[^;]*\bto\b[^;]*\b(public|anon)\b")
HARD = ("grant-to-public", "pg-terminate", "copy-program-or-file", "server-files", "secrets-vault",
        "alter-system-or-role", "dblink")
DROP_SCOPE = re.compile(r"\bdrop\s+(schema|database|owned|role|user|group|tablespace|server|extension|"
                        r"publication|subscription|foreign\s+data\s+wrapper)\b")
AUTH_TABLE = re.compile(r"\bauth\s*\.\s*(users|identities)\b")
AUTH_SECRET_COLS = re.compile(r"\b(email|phone|encrypted_password|raw_user_meta_data|"
                              r"raw_app_meta_data|recovery_token|confirmation_token|"
                              r"identity_data)\b|\*")
DELETE = re.compile(r"\bdelete\s+from\b")
WHERE = re.compile(r"\bwhere\b")
DYNAMIC = re.compile(r"\bexecute\b(?!\s+(on|function|procedure)\b)")   # the privilege / trigger forms are not dynamic SQL
BEGIN = re.compile(r"^(begin|start\s+transaction)(\s+(work|transaction))?"
                   r"(\s+(isolation\s+level\s+\w+(\s+\w+)?|read\s+(write|only)|(not\s+)?deferrable))*$")
ROLLBACK = re.compile(r"^(rollback|abort)(\s+(work|transaction))?$")
# CTO ruling dreq-fd5f4a36 (KAN-845, CEO-approved 2026-11-04): ONE narrow carve-out from
# grant-to-public. EXECUTE only, on exactly these four (uuid) predicates, to anon/authenticated/
# service_role only. PUBLIC, ALL, WITH GRANT OPTION, table grants and any other function stay denied,
# and every other statement in the batch is still judged against the full DENY list.
_KAN845_FN = r"public\.kan713_meetup_(visible|can_read_row|attendee_visible|can_write_row)\(uuid\)"
_KAN845_ROLE = r"(anon|authenticated|service_role)"
KAN845_GRANT = re.compile(r"grant\s+execute\s+on\s+function\s+" + _KAN845_FN
                          + r"(\s*,\s*" + _KAN845_FN + r")*\s+to\s+" + _KAN845_ROLE
                          + r"(\s*,\s*" + _KAN845_ROLE + r")*\s*")


def _grant_to_public(low):
    """grant-to-public, statement by statement, minus the one KAN-845 carve-out."""
    return any(GRANT_TO_PUBLIC.search(piece) and not KAN845_GRANT.fullmatch(piece.strip())
               for piece in low.split(";"))


ENDS_TX = re.compile(r"^(commit|end|abort|prepare\s+transaction|begin|start\s+transaction|"
                     r"rollback(?!\s+to\b))")


# CEO 2026-10-26 ("DROP KAN-644"): ONE narrow exception to the DROP rule. A RELEASED migration whose
# registry entry carries DROP_EXCEPTION may contain exactly this statement and no other DROP. No
# wildcard: one constraint, on public.profiles, with IF EXISTS, and nothing else in the statement.
DROP_EXCEPTION = "profiles_persona_type_check"
ALLOWED_STMT = (r"\balter\s+table\s+public\s*\.\s*profiles\s+drop\s+constraint\s+if\s+exists\s+"
                + DROP_EXCEPTION + r"\s*")
ALLOWED_DROP = re.compile(ALLOWED_STMT + r"(?=;|$)", re.I)


def without_allowed_drop(top, scan, lit):
    """(scan, lit) with the one allowed DROP statement removed, or the views unchanged when the
    statement is not exactly that: every occurrence must stand alone as a top-level statement
    (none hidden in a dollar-quoted body, none sharing its ALTER TABLE with another action)."""
    stmts = [s.strip().lower() for s in top.split(";")]
    alone = sum(1 for s in stmts if re.fullmatch(ALLOWED_STMT, s))
    if not alone or alone != len(ALLOWED_DROP.findall(scan.lower())):
        return scan, lit
    return ALLOWED_DROP.sub(" ", scan), ALLOWED_DROP.sub(" ", lit)


def deny_reason(scan, lit):
    """The first hard-deny rule the SQL trips, or None."""
    views = [scan] + ([lit] if DYNAMIC.search(scan) else [])   # dynamic SQL hides in literals
    for view in views:
        low = view.lower()
        for name, pat in DENY:
            if (_grant_to_public(low) if pat is None else pat.search(low)):
                return name
        if AUTH_TABLE.search(low) and AUTH_SECRET_COLS.search(re.sub(r"count\s*\(\s*\*\s*\)", " ", low)):
            return "auth-secrets"
        for piece in low.split(";"):
            if DELETE.search(piece) and not WHERE.search(piece):
                return "delete-without-where"
    return None


def hard_deny_reason(scan, lit):
    """The never-list (autonomy.json `never`): refused for every session, ops included."""
    views = [scan] + ([lit] if DYNAMIC.search(scan) else [])
    for view in views:
        low = view.lower()
        for name, pat in DENY:
            if name in HARD and (_grant_to_public(low) if pat is None else pat.search(low)):
                return name
        if DROP_SCOPE.search(low):
            return "drop-scope"
        if AUTH_TABLE.search(low) and AUTH_SECRET_COLS.search(re.sub(r"count\s*\(\s*\*\s*\)", " ", low)):
            return "auth-secrets"
    return None


# ------------------------------------------------- statements that remove or change rows
_NAME = r'(""|[a-z_][\w$]*)(?:\s*\.\s*(""|[a-z_][\w$]*))?'
_ROWS = (
    ("delete", re.compile(r"\bdelete\s+from\s+(?:only\s+)?" + _NAME)),
    ("update", re.compile(r"\bupdate\s+(?:only\s+)?" + _NAME + r"(?:\s+(?:as\s+)?[a-z_]\w*)?\s+set\b")),
    ("drop-column", re.compile(r"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?" + _NAME +
                               r"[^;]*?\bdrop\s+(?!constraint\b|default\b|not\s+null\b|identity\b|"
                               r"expression\b)")),
)
_LISTS = (
    ("drop-table", re.compile(r"\bdrop\s+table\s+(?:if\s+exists\s+)?([^;]+)")),
    ("truncate", re.compile(r"\btruncate\s+(?:table\s+)?([^;]+)")),
)
_CREATED = re.compile(r"\bcreate\s+(?:(?:global|local)\s+)?(?:temp|temporary|unlogged)?\s*table\s+"
                      r"(?:if\s+not\s+exists\s+)?" + _NAME)
_LIST_TAIL = re.compile(r"\b(cascade|restrict|restart\s+identity|continue\s+identity)\b.*$")


def _join(a, b):
    return a + "." + b if b else a


def row_targets(view):
    """[(kind, table)] for every statement in `view` that removes or changes rows. A quoted name
    comes back as '""' (the scan view blanks quoted identifiers)."""
    from agent.execution import sql_snapshot
    low, out = view.lower(), []
    for kind, pat in _ROWS:
        for m in pat.finditer(low):
            out.append((kind, sql_snapshot.qualify(_join(m.group(1), m.group(2)))))
    for kind, pat in _LISTS:
        for m in pat.finditer(low):
            names = _LIST_TAIL.sub("", m.group(1)).replace("only ", " ")
            for n in names.split(","):
                if n.strip():
                    out.append((kind, sql_snapshot.qualify(n.strip())))
    return out


def created_tables(view):
    from agent.execution import sql_snapshot
    return {sql_snapshot.qualify(_join(m.group(1), m.group(2))) for m in _CREATED.finditer(view.lower())}


def leading_snapshots(top):
    """Snapshots taken at the START of the same call (before any other statement) count."""
    from agent.execution import sql_snapshot
    found = []
    for stmt in (x.strip().lower() for x in top.split(";") if x.strip()):
        snap = sql_snapshot.snapshots_in([stmt])
        if snap:
            found.extend(snap)
        elif BEGIN.match(stmt) or re.match(r"^(create\s+schema\s+if\s+not\s+exists|revoke\b[^;]*\bon\s+schema)"
                                            r"\s*[^;]*\b" + sql_snapshot.SCHEMA + r"\b", stmt):
            continue
        else:
            break
    return found


_DEFINES = re.compile(r"^\s*create\s+(or\s+replace\s+)?(function|procedure)\b", re.I)


def executed(query):
    """(scan, lit) of the code this call RUNS: a CREATE FUNCTION/PROCEDURE body only defines
    code, so the UPDATE inside a trigger function needs no snapshot; a DO block runs now."""
    scans, lits = [], []
    for stmt in split_statements(query):
        _, sc, li = lex(stmt)
        if not _DEFINES.match(sc):
            scans.append(sc)
            lits.append(li)
    return " ; ".join(scans), " ; ".join(lits)


def is_probe(top, scan):
    """BEGIN ... ROLLBACK and nothing that could commit in between."""
    stmts = [s.strip().lower() for s in top.split(";") if s.strip()]
    if len(stmts) < 3 or not BEGIN.match(stmts[0]) or not ROLLBACK.match(stmts[-1]):
        return False
    if any(ENDS_TX.match(s) for s in stmts[1:-1]):
        return False
    return not re.search(r"\bcommit\b", scan.lower())      # no COMMIT hidden in a DO block


def normalise(query):
    return re.sub(r"\s+", " ", query).strip().rstrip(";").strip()


def sha(query):
    return hashlib.sha256(normalise(query).encode("utf-8")).hexdigest()


def registry(path=None):
    try:
        with open(path or ALLOW_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------- integrated migrations (auto-decision)
# CEO 2026-10-14: a technical approval is the CTO's, not the CEO's. By the time Memphis applies a
# migration it has passed the CTO's review, the team's checks, QA and integration into Alpha, so
# the proof of approval is that the SQL IS, byte for byte, a statement of a migration file
# committed on origin/Alpha. That is what the hook checks, instead of asking a human. Only
# additive/ACL statement classes qualify; anything else keeps the normal prompt.
APP_REPO = os.path.join(ROOT, "Dabbler", "dabbler-code")
MIGRATIONS_REF, MIGRATIONS_DIR, RECENT_FILES = "origin/Alpha", "supabase/migrations", 80
AUTO_CLASSES = re.compile(
    r"^(create\s+(or\s+replace\s+)?function\b|alter\s+function\b|revoke\b|grant\b|"
    r"comment\s+on\b|do\b|begin\b|start\s+transaction\b|commit\b|end\b|"
    r"create\s+(unique\s+)?index\s+(concurrently\s+)?if\s+not\s+exists\b|"
    r"create\s+table\s+if\s+not\s+exists\b|create\s+policy\b|"
    r"alter\s+table\s+\S+\s+(add\s+column\s+if\s+not\s+exists\b|enable\s+row\s+level\s+security\b))", re.I)


def split_statements(text):
    """Top-level statements of a SQL file, original text, split on ';' outside comments, strings
    and dollar quotes. Raises LexError when it cannot tell."""
    out, buf, i, n = [], [], 0, len(text)
    while i < n:
        two, c = text[i:i + 2], text[i]
        if two == "--":
            j = text.find("\n", i); j = n if j < 0 else j
            buf.append(text[i:j]); i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            if j < 0:
                raise LexError("unterminated block comment")
            buf.append(text[i:j + 2]); i = j + 2
        elif c in "'\"":
            j = i + 1
            while True:
                if j >= n:
                    raise LexError("unterminated quote")
                if text[j] == c:
                    if text[j + 1:j + 2] == c:
                        j += 2; continue
                    break
                j += 1
            buf.append(text[i:j + 1]); i = j + 1
        elif c == "$" and _DOLLAR.match(text, i) and not (i and (text[i - 1].isalnum() or text[i - 1] == "_")):
            m = _DOLLAR.match(text, i)
            j = text.find(m.group(0), m.end())
            if j < 0:
                raise LexError("unterminated dollar quote")
            buf.append(text[i:j + len(m.group(0))]); i = j + len(m.group(0))
        elif c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []; i += 1
        else:
            buf.append(c); i += 1
    tail = "".join(buf).strip()
    if tail and re.sub(r"--[^\n]*|/\*.*?\*/", "", tail, flags=re.S).strip():
        out.append(tail)
    return out


def _skeleton(stmt):
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*|/\*.*?\*/", " ", stmt, flags=re.S)).strip()


def integrated_migrations(runner=None):
    """[(file, text)] for the most recent migration files committed on origin/Alpha (local ref)."""
    import subprocess
    run = runner or subprocess.run
    ls = run(["git", "-C", APP_REPO, "ls-tree", "--name-only", MIGRATIONS_REF, MIGRATIONS_DIR + "/"],
             capture_output=True, text=True, timeout=5)
    files = sorted(f for f in ls.stdout.split() if f.endswith(".sql"))[-RECENT_FILES:]
    out = []
    for f in files:
        got = run(["git", "-C", APP_REPO, "show", "%s:%s" % (MIGRATIONS_REF, f)],
                  capture_output=True, text=True, timeout=5)
        if got.returncode == 0:
            out.append((f, got.stdout))
    return out


def in_integrated_migration(query, migrations=None):
    """The migration file that contains this SQL exactly (the whole file, or one statement of it)
    and whose statements are all of the auto-allowed classes; else None."""
    want = normalise(query)
    for name, text in (migrations if migrations is not None else integrated_migrations()):
        try:
            stmts = split_statements(text)
        except LexError:
            continue
        if not stmts or not all(AUTO_CLASSES.match(_skeleton(x)) for x in stmts):
            continue
        if want == normalise(text) or any(want == normalise(x) for x in stmts):
            return name
        parts = [x for x in split_statements(query)] if want else []
        if parts and all(any(normalise(p) == normalise(x) for x in stmts) for p in parts):
            return name
    return None


def released(query, reg, drop_exception=False):
    digest = sha(query)
    return any(e.get("sha256") == digest
               and (not drop_exception or e.get("drop_exception") == DROP_EXCEPTION)
               for e in reg.get("released_migrations") or [])


# ------------------------------------------------------------------------------- the hook
def mask(query):
    q = re.sub(r"'(?:[^']|'')*'", "'?'", query or "")
    q = re.sub(r"eyJ[\w\-.]+", "<jwt>", q)
    q = re.sub(r"\b[A-Za-z0-9_\-]{32,}\b", "<tok>", q)
    return re.sub(r"\s+", " ", q).strip()[:80]


def log(entry):
    try:
        from agent.state import store
        path = os.environ.get("SQL_HOOK_LOG") or os.path.join(store.RUNTIME, "sql-hook.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(entry, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                                sort_keys=True) + "\n")
    except Exception:                                      # noqa: BLE001  logging never decides
        pass


NOT_CEO = " This is an answer, not a question: never take it to the CEO (D-043)."


def decide(payload, state_store=None, teams_mod=None, allow_path=None, now=None):
    """{'decision': allow|deny, 'reason': ...}, or None for a session that is not the ops team
    and is not reading (the ops guard refuses its writes)."""
    if (payload.get("tool_name") or "") != TOOL:
        return None
    from agent.execution import sql_snapshot
    args = payload.get("tool_input") or {}
    project, query = args.get("project_id"), args.get("query")
    reg = registry(allow_path)
    approved = reg.get("project_id") or DEFAULT_PROJECT
    try:
        import ops_guard
        team, lane = ops_guard.team_of(payload.get("session_id"), state_store, teams_mod)
    except Exception:                                      # noqa: BLE001
        team, lane = None, None
    ops = lane == "ops"
    base = {"team": team, "lane": lane, "project_id": project, "query": mask(query)}

    def done(decision, reason, public):
        log(dict(base, decision=decision or "none", reason=reason))
        return {"decision": decision, "reason": public} if decision else None

    if project != approved:
        return done("deny", "wrong-project",
                    "Only Supabase project %s is ever used; %r is not it. Re-run on %s." % (approved, project, approved)
                    + NOT_CEO)
    if not isinstance(query, str) or not query.strip():
        return done("deny" if ops else None, "no-query", "Send the SQL text in `query`." + NOT_CEO)
    try:
        top, scan, lit = lex(query)
    except LexError as exc:
        return done("deny" if ops else None, "unparseable: %s" % exc,
                    "The SQL hook could not read this (%s). Close the quote or comment, or send the "
                    "statements in smaller calls." % exc + NOT_CEO)
    if not ops:
        why = deny_reason(scan, lit)
        if why:
            return done("deny", "deny:" + why,
                        "Refused by the SQL hook (%s). Database writes are Memphis's: commit the SQL on "
                        "your branch and report `blocked: needs-ops`." % why + NOT_CEO)
        import ops_guard
        if ops_guard.read_only_sql(query):
            return done("allow", "read-only", "SQL hook: read-only query on the approved project.")
        return done(None, "not-ops-session", None)         # the ops guard refuses the write
    why = hard_deny_reason(scan, lit)
    if why:
        rule = {"secrets-vault": "secrets-vault", "auth-secrets": "secrets-vault",
                "grant-to-public": "grant-public"}.get(why)
        alt = (autonomy_instead(rule) if rule else None) or "do it without this statement"
        return done("deny", "deny:" + why, "Refused by the SQL hook (%s): it is on the never-list. "
                    "Instead: %s." % (why, alt) + NOT_CEO)
    probe = is_probe(top, scan)
    run_scan, run_lit = executed(query)
    targets = row_targets(run_scan)
    if DYNAMIC.search(run_scan) and not probe and row_targets(run_lit):
        return done("deny", "dynamic-destructive",
                    "This EXECUTEs SQL that changes or removes rows, which the hook cannot snapshot. "
                    "Write those statements out literally (snapshot first), or test it inside "
                    "BEGIN … ROLLBACK." + NOT_CEO)
    if any(t.startswith(sql_snapshot.SCHEMA + ".") for k, t in targets if k in ("drop-table", "truncate", "delete")):
        return done("deny", "drop-backup", "thebes_backup snapshots are kept; do not remove them." + NOT_CEO)
    if any('""' in t for _, t in targets):
        return done("deny", "quoted-target",
                    "Write the table name unquoted (schema.table) so the hook can match its snapshot." + NOT_CEO)
    if not probe:
        covered = {t for _, t in leading_snapshots(top)} | created_tables(scan)
        missing = sorted({t for _, t in targets if t not in covered and not sql_snapshot.recent(t, now=now)})
        if missing:
            cmds = "; ".join("python3 -m agent.execution.sql_snapshot %s [--where '<the same WHERE>'] "
                             "--ticket <KEY>" % t for t in missing)
            return done("deny", "needs-snapshot:" + ",".join(missing),
                        "This changes or removes rows of %s. Snapshot first — run: %s — then run the SQL "
                        "it prints through execute_sql, then this statement again (allowed for %dh). "
                        "You own this; it is not a CEO decision (D-043)."
                        % (", ".join(missing), cmds, sql_snapshot.TTL_HOURS))
    import ops_guard
    if ops_guard.read_only_sql(query):
        kind = "read-only"
    elif probe:
        kind = "probe"
    elif released(query, reg):
        kind = "released-migration"
    elif targets:
        kind = "snapshotted:" + ",".join(sorted({t for _, t in targets}))
    else:
        kind = "write"
    snaps = sql_snapshot.snapshots_in(x for x in top.split(";") if x.strip()) if not probe else []
    for backup, table in snaps:
        try:
            sql_snapshot.record(table, backup, team=team, now=now)
        except OSError:
            pass
    if snaps:
        kind = "snapshot:" + ",".join(t for _, t in snaps) + ("+" + kind if kind != "write" else "")
    return done("allow", kind, "SQL hook: %s on the approved project (ops owns the database, D-043)." % kind)


def autonomy_instead(rule_id):
    try:
        from agent.state import autonomy
        r = autonomy.never_rule(rule_id)
        return r and r.get("instead")
    except Exception:                                      # noqa: BLE001
        return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:                                      # noqa: BLE001  not a tool call at all
        return 0
    try:
        result = decide(payload)
    except Exception as exc:                               # noqa: BLE001  answer, never fall to a prompt
        log({"decision": "deny", "reason": "hook-error: %s" % str(exc)[:120]})
        result = {"decision": "deny", "reason": "The SQL hook failed (%s). Retry once; if it fails "
                  "again, report `blocked` to the orchestrator with this text.%s" % (str(exc)[:120], NOT_CEO)}
    if result:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": result["decision"],
            "permissionDecisionReason": result["reason"]}}))
    return 0


def release_cli(argv):
    path = argv[0]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        top, scan, lit = lex(text)
    except LexError as exc:
        print("refused: cannot parse %s (%s)" % (path, exc))
        return 2
    entry = {"file": os.path.relpath(os.path.abspath(path), ROOT), "sha256": sha(text)}
    if "--allow-persona-check-drop" in argv:
        scan, lit = without_allowed_drop(top, scan, lit)
        entry["drop_exception"] = DROP_EXCEPTION
    why = deny_reason(scan, lit)
    if why:
        print("refused: the hook would deny this migration anyway (%s)" % why)
        return 2
    if "--write" in argv:
        reg = registry()
        reg.setdefault("project_id", DEFAULT_PROJECT)
        reg.setdefault("released_migrations", [])
        reg["released_migrations"] = [e for e in reg["released_migrations"] if e.get("file") != entry["file"]] + [entry]
        with open(ALLOW_FILE, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=2)
            fh.write("\n")
    print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "release":
        sys.exit(release_cli(sys.argv[2:]))
    sys.exit(main())
