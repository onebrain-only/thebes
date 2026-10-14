#!/usr/bin/env python3
"""SQL hook — PreToolUse hook for `mcp__claude_ai_Supabase__execute_sql` (maintenance 2026-10-13).

The CEO approved Memphis's Messaging probes and migrations on ONE Supabase project (PM ledger
ref supabase-messaging-approval): test data only, no DROP, no other project. A plain allow rule
matches the tool NAME only, so it cannot say "that project, that kind of SQL". This hook can.

    DENY    the project is not the approved one, or the SQL does any of: DROP, TRUNCATE,
            DELETE without WHERE, GRANT to public/anon, CREATE EXTENSION, pg_terminate_backend,
            COPY ... PROGRAM / server files, vault.*, auth.users/identities secret columns,
            ALTER SYSTEM/ROLE/USER, dblink. Applies to every session.
    ALLOW   only for a session bound to an `ops`-lane team (Memphis), on the approved project,
            when the SQL is (a) read-only, (b) a probe: exactly one BEGIN first and one ROLLBACK
            last, no COMMIT anywhere, or (c) a migration released by maintenance in
            agent/state/registry/sql_allow.json (pinned by sha256 of the whitespace-normalised
            text, so editing the file un-releases it). The deny list is checked first, always.
    ASK     (no decision) everything else: the normal permission prompt still appears.

Comments and string literals are stripped before the keyword scans (a 'drop' inside a literal or
a comment is not a DROP). Dollar-quoted bodies (function / DO blocks) are NOT stripped: they are
code, and are scanned. Dynamic SQL (an EXECUTE outside a literal) also scans the literals, and
is never auto-allowed. Anything the lexer cannot parse gets no decision.

Every decision is logged to agent/state/runtime/sql-hook.log: time, team, project id, decision,
reason, the first 80 characters of the query with every string literal and long token masked.

    python3 agent/scripts/sql_hook.py release <migration.sql> [--write]   # maintenance only

Exit code is always 0; the decision is the JSON on stdout (none = ask).
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
    ("grant-to-public", re.compile(r"\bgrant\b[^;]*\bto\b[^;]*\b(public|anon)\b")),
    ("create-extension", re.compile(r"\bcreate\s+extension\b")),
    ("pg-terminate", re.compile(r"\bpg_(terminate|cancel)_backend\b")),
    ("copy-program-or-file", re.compile(r"\bcopy\b[^;]*\b(program|from\s+''|to\s+'')")),
    ("server-files", re.compile(r"\b(pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|"
                                r"lo_import|lo_export)\b")),
    ("secrets-vault", re.compile(r"\bvault\s*\.|\bdecrypted_secrets\b")),
    ("alter-system-or-role", re.compile(r"\balter\s+(system|role|user)\b|\bcreate\s+(role|user)\b")),
    ("dblink", re.compile(r"\bdblink\w*\b|\bpostgres_fdw\b")),
)
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
ENDS_TX = re.compile(r"^(commit|end|abort|prepare\s+transaction|begin|start\s+transaction|"
                     r"rollback(?!\s+to\b))")


def deny_reason(scan, lit):
    """The first hard-deny rule the SQL trips, or None."""
    views = [scan] + ([lit] if DYNAMIC.search(scan) else [])   # dynamic SQL hides in literals
    for view in views:
        low = view.lower()
        for name, pat in DENY:
            if pat.search(low):
                return name
        if AUTH_TABLE.search(low) and AUTH_SECRET_COLS.search(re.sub(r"count\s*\(\s*\*\s*\)", " ", low)):
            return "auth-secrets"
        for piece in low.split(";"):
            if DELETE.search(piece) and not WHERE.search(piece):
                return "delete-without-where"
    return None


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


def released(query, reg):
    digest = sha(query)
    return any(e.get("sha256") == digest for e in reg.get("released_migrations") or [])


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


def decide(payload, state_store=None, teams_mod=None, allow_path=None):
    """{'decision': allow|deny, 'reason': ...} or None (= ask: the normal prompt)."""
    if (payload.get("tool_name") or "") != TOOL:
        return None
    args = payload.get("tool_input") or {}
    project, query = args.get("project_id"), args.get("query")
    reg = registry(allow_path)
    approved = reg.get("project_id") or DEFAULT_PROJECT
    try:
        import ops_guard
        team, lane = ops_guard.team_of(payload.get("session_id"), state_store, teams_mod)
    except Exception:                                      # noqa: BLE001
        team, lane = None, None
    base = {"team": team, "lane": lane, "project_id": project, "query": mask(query)}

    def done(decision, reason, public):
        log(dict(base, decision=decision or "ask", reason=reason))
        return {"decision": decision, "reason": public} if decision else None

    if project != approved:
        return done("deny", "wrong-project",
                    "Only the approved Supabase project may be used; %r is not it (the CEO said "
                    "never to touch the other project)." % (project,))
    if not isinstance(query, str) or not query.strip():
        return done(None, "no-query", None)
    try:
        top, scan, lit = lex(query)
    except LexError as exc:
        return done(None, "unparseable: %s" % exc, None)
    why = deny_reason(scan, lit)
    if why:
        return done("deny", "deny:" + why,
                    "Refused by the SQL hook (%s): outside the CEO's Messaging approval "
                    "(supabase-messaging-approval): test data, no DROP, no other project." % why)
    if lane != "ops":
        return done(None, "not-ops-session", None)         # the ops guard governs everyone else
    if DYNAMIC.search(scan):
        return done(None, "dynamic-sql", None)
    import ops_guard
    if ops_guard.read_only_sql(query):
        kind = "read-only"
    elif is_probe(top, scan):
        kind = "probe"
    elif released(query, reg):
        kind = "released-migration"
    else:
        try:
            src = in_integrated_migration(query, (payload.get("_migrations")))
        except Exception:                                  # noqa: BLE001  git trouble: ask
            src = None
        if not src:
            return done(None, "unlisted-write", None)
        kind = "integrated-migration:%s" % os.path.basename(src)
    return done("allow", kind, "SQL hook: %s on the approved project (supabase-messaging-approval)." % kind)


def main():
    try:
        payload = json.load(sys.stdin)
        result = decide(payload)
    except Exception as exc:                               # noqa: BLE001  fail to the normal prompt
        log({"decision": "ask", "reason": "hook-error: %s" % str(exc)[:120]})
        return 0
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
    why = deny_reason(scan, lit)
    if why:
        print("refused: the hook would deny this migration anyway (%s)" % why)
        return 2
    entry = {"file": os.path.relpath(os.path.abspath(path), ROOT), "sha256": sha(text)}
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
