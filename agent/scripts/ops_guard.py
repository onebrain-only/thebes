#!/usr/bin/env python3
"""Ops guard — PreToolUse hook (D-042, D-043): only the ops team writes to the database or pushes.

Every session in this checkout reads the same settings file, so a permission rule cannot
tell Memphis from Karnak. This hook can: it reads the session id Claude Code passes in,
finds which team that session is bound to in Persistent State, and decides.

    Supabase write tools   allowed ONLY for a session bound to an `ops`-lane team.
                           Everyone else (code teams, the orchestrator, unbound sessions)
                           is refused at once, so a team never stops on a permission prompt:
                           it reads the refusal and reports `blocked: needs-ops`.
    Project lifecycle      (pause/restore/create project) refused for everyone: never needed
    and money tools        for product work. confirm_cost is money, the CEO's (D-043).
    git push               code teams push only their own branch; the ops team pushes staging
                           (and Alpha only on the CEO's promotion order, order_gate, D-052).

Autonomy constitution (D-043, 2026-10-27): a permitted act is ANSWERED, not left to a prompt.
The hook prints an explicit allow for an ops-team Supabase write on the approved project
(execute_sql excepted: the SQL hook judges each query), a Supabase read on the approved
project, and a plain push the rules permit. Exit 2 = refuse, reason on stderr, and every
refusal carries the alternative and is never a question for the CEO. A Supabase write the
hook cannot attribute is refused (fail closed); anything else it cannot parse gets no
opinion (fail open), like the other guards.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

SUPABASE = "mcp__claude_ai_Supabase__"
PROJECT = "wtncuzcskpigqpmnxwws"
WRITE_TOOLS = {"apply_migration", "execute_sql", "deploy_edge_function",
               "create_edge_function_secret", "create_branch", "merge_branch",
               "rebase_branch", "delete_branch", "reset_branch"}
NEVER_TOOLS = {"pause_project", "restore_project", "create_project", "confirm_cost"}
CEO_ONLY_TOOLS = NEVER_TOOLS                              # kept for callers of the old name
READ_TOOLS = {"list_tables", "list_extensions", "list_migrations", "get_advisors", "get_logs",
              "query_logs", "list_edge_functions", "get_edge_function", "search_docs",
              "get_project", "get_project_url", "get_publishable_keys", "get_anon_key",
              "list_branches", "generate_typescript_types", "list_projects", "get_organization",
              "list_organizations", "get_cost"}
NOT_CEO = " This is an answer, not a question: never take it to the CEO (D-043)."
# A read-only query any session may run (D-042 amendment, 2026-10-09): reviewers and the PM
# must be able to LOOK at the live database. Deliberately conservative: one statement,
# starting with SELECT / WITH / EXPLAIN / SHOW, no write or DDL keyword anywhere, and no call
# to a function outside a small allowlist (a SELECT can call a function that writes).
READ_START = re.compile(r"^\s*(select|with|explain|show)\b", re.I)
WRITE_WORDS = re.compile(r"\b(insert|update|delete|merge|upsert|drop|alter|create|grant|revoke|"
                         r"truncate|copy|call|do|vacuum|reindex|cluster|lock|refresh|comment|"
                         r"security|set|reset|discard|notify|listen|prepare|execute|into|"
                         r"nextval|setval|pg_sleep|dblink|lo_\w+|pg_read\w*|pg_write\w*)\b",
                         re.I)
SAFE_FUNCS = {"count", "sum", "min", "max", "avg", "coalesce", "nullif", "greatest", "least",
              "now", "lower", "upper", "length", "trim", "substr", "substring", "left",
              "right", "concat", "array_agg", "string_agg", "json_agg", "jsonb_agg",
              "jsonb_build_object", "json_build_object", "to_jsonb", "row_to_json",
              "exists", "cast", "date_trunc", "extract", "round", "abs", "unnest",
              "array_length", "cardinality", "format_type", "pg_get_functiondef",
              "pg_get_viewdef", "pg_get_function_arguments", "pg_get_function_result",
              "pg_get_userbyid", "has_function_privilege", "has_table_privilege",
              "has_schema_privilege", "to_regprocedure", "to_regclass", "obj_description",
              "col_description", "pg_get_expr", "pg_get_constraintdef", "pg_get_indexdef",
              "pg_relation_size", "pg_total_relation_size", "pg_size_pretty", "quote_ident",
              "current_setting", "current_user", "session_user", "version", "any", "all",
              "in", "filter", "over", "partition", "values", "as", "and", "or", "not", "on",
              "from", "where", "case", "when", "then", "else", "end", "select", "is", "using"}
FUNC_CALL = re.compile(r"([A-Za-z_][\w.]*)\s*\(")


def read_only_sql(query):
    """True only for a query that cannot write. When unsure, False."""
    if not isinstance(query, str) or not query.strip():
        return False
    q = re.sub(r"--[^\n]*", " ", query)
    q = re.sub(r"/\*.*?\*/", " ", q, flags=re.S)
    q = re.sub(r"'(?:[^']|'')*'", "''", q)            # string literals cannot write
    statements = [x for x in q.split(";") if x.strip()]
    if len(statements) != 1 or not READ_START.match(statements[0]):
        return False
    if WRITE_WORDS.search(statements[0]):
        return False
    for name in FUNC_CALL.findall(statements[0]):
        if name.split(".")[-1].lower() not in SAFE_FUNCS:
            return False
    return True


GIT_WRITE = re.compile(r"(^|[;&|(\s])git(\s+-C\s+\S+)*\s+(checkout|switch|commit|merge|rebase|"
                       r"reset|stash|cherry-pick|pull|restore|clean|am|revert)(\s|$)")
CEO_FOLDERS = tuple(os.path.realpath(os.path.join(ROOT, "Dabbler", d))
                    for d in ("dabbler-code", "dabbler-design-system"))


def in_ceo_folder(command, cwd):
    """Does a git write in `command` act on one of the CEO's own checkouts?"""
    dirs = []
    m = re.match(r"\s*cd\s+(\S+)\s*&&", command)
    base = os.path.join(cwd, m.group(1)) if m else cwd
    for c in re.findall(r"git((?:\s+-C\s+\S+)+)\s+(?:checkout|switch|commit|merge|rebase|reset|"
                        r"stash|cherry-pick|pull|restore|clean|am|revert)\b", command):
        target = base
        for d in re.findall(r"-C\s+(\S+)", c):
            target = os.path.join(target, d.strip("'\""))
        dirs.append(target)
    if not dirs:
        dirs.append(base)
    return any(os.path.realpath(d) in CEO_FOLDERS for d in dirs)


PUSH = re.compile(r"(^|[;&|(\s])git(\s+-C\s+\S+)*\s+push(\s|$)")


def team_of(session_id, state_store=None, teams_mod=None):
    """(team_id, lane) for the session, or (None, None)."""
    if not session_id:
        return None, None
    if state_store is None:
        from agent.state import store as state_store
    if teams_mod is None:
        from agent.state import teams as teams_mod
    for rec in state_store.read_all("role_session"):
        if rec.get("status") == "active" and rec.get("session_id") == session_id:
            tid = rec.get("seat_id")
            entry = teams_mod.read().get(tid)
            if entry and entry.get("kind", "team") == "team":
                return tid, entry.get("lane", "code")
            return tid, None
    return None, None


DESKTOP = os.path.realpath(os.path.expanduser("~/Desktop"))
MAKES = re.compile(r"\b(mkdir|git\s+(-C\s+\S+\s+)?(clone|worktree\s+add)|cp\s+-\w*r|rsync|touch|mv)\b|>\s*\S")


def desktop_stray(command, cwd):
    """A path this command would create on the Desktop outside the Thebes repo, else None."""
    if not MAKES.search(command):
        return None
    for tok in re.findall(r"(?:~|/Users/[^/\s]+)/Desktop/[^\s;&|'\"]*", command):
        path = os.path.realpath(os.path.expanduser(tok))
        if path.startswith(DESKTOP + os.sep) and not (path == ROOT or path.startswith(ROOT + os.sep)):
            return tok
    return None


def decide(payload, state_store=None, teams_mod=None):
    """Return None (no opinion) or a refusal reason."""
    tool = payload.get("tool_name") or ""
    sid = payload.get("session_id")
    if tool.startswith(SUPABASE):
        name = tool[len(SUPABASE):]
        project = (payload.get("tool_input") or {}).get("project_id")
        if project and project != PROJECT:
            return ("Only Supabase project %s is ever used; %r is not it. Re-run on %s."
                    % (PROJECT, project, PROJECT) + NOT_CEO)
        if name == "confirm_cost":
            return ("Spending money is the CEO's (D-043). Do not confirm a cost: report "
                    "`blocked: needs-ceo: money` with the amount and why, and carry on with other work.")
        if name in NEVER_TOOLS:
            return ("%s is never needed for product work (it creates, pauses or restores a whole "
                    "project, which costs money). Work inside project %s." % (name, PROJECT) + NOT_CEO)
        if name == "apply_migration":
            return ("apply_migration is not used (it hangs sessions and is outside the approved "
                    "route). Run the migration's statements through execute_sql in one or more "
                    "calls; snapshot first if it removes or changes rows." + NOT_CEO)
        if name not in WRITE_TOOLS:
            return None
        if name == "execute_sql" and read_only_sql((payload.get("tool_input") or {}).get("query")):
            return None                                   # anyone may read
        try:
            tid, lane = team_of(sid, state_store, teams_mod)
        except Exception as exc:                          # noqa: BLE001
            return "ops guard could not identify this session (%s); refusing a database write" % exc
        if lane == "ops":
            return None
        return ("Database writes belong to the operations team (Memphis), D-042. %s may not run "
                "%s. Commit the SQL and its probes on your branch and report `blocked: needs-ops` "
                "naming the migration; the orchestrator sends it to Memphis."
                % (tid or "This session", name) + NOT_CEO)
    if tool == "Bash":
        command = (payload.get("tool_input") or {}).get("command") or ""
        stray = desktop_stray(command, payload.get("cwd") or ROOT)
        if stray:
            try:
                is_team = bool(team_of(sid, state_store, teams_mod)[1])
            except Exception:                             # noqa: BLE001
                is_team = False
            if is_team:
                return ("CEO 2026-11-10: nothing is created on the Desktop outside the Thebes repo "
                        "(%s). Work in your branch's worktree under .claude/worktrees/ and put "
                        "documents in Dabbler/dabbler-docs/." % stray)
        if GIT_WRITE.search(command):
            try:
                tid, lane = team_of(sid, state_store, teams_mod)
            except Exception:                             # noqa: BLE001
                tid, lane = None, None
            if lane and in_ceo_folder(command, payload.get("cwd") or ROOT):
                return ("The CEO's folders (Dabbler/dabbler-code, Dabbler/dabbler-design-system) "
                        "are never a team's checkout: they may hold the CEO's unsaved work "
                        "(B15, Ramesseum 2026-10-13). Work in your own worktree: git -C "
                        "Dabbler/dabbler-code worktree add <your folder> <branch>.")
        if not PUSH.search(command):
            return None
        try:
            tid, lane = team_of(sid, state_store, teams_mod)
        except Exception:                                 # noqa: BLE001
            return None
        if lane == "ops":
            return ops_push_problem(command, payload.get("cwd"))
        if lane == "qa":
            return "The QA lane (%s) reviews; it never pushes (D-043)." % tid
        if lane == "code":
            return push_problem(command, tid)
    return None


BASES = ("staging", "canary", "main")
INTEGRATION_REFS = ("integrate-staging:staging", "integrate-staging-ds:staging")
PUSH_ARGS = re.compile(r"git(?:\s+-C\s+\S+)*\s+push\b(?P<rest>[^;&|]*)")


PROTECTED = ("main", "master", "canary")
# D-052: team branches are staging-<team>; a merged legacy alpha-<…> branch may still be deleted.
# staging, Alpha and every staging-<team> are kept (the CEO's keep list), so never deletable here.
ALPHA_BRANCH = re.compile(r"^alpha(-ds)?-[a-z0-9][a-z0-9-]*$", re.I)
KEPT_BRANCH = re.compile(r"^(main|master|canary|staging|alpha|alpha-ds|staging-.+)$", re.I)
# Any other merged branch may go too (CEO order 2026-11-05), but only once a live check finds
# none of its work missing from every base: git cherry, then a content comparison for work that
# was squash-merged or re-applied under other commits.
INTEGRATED_BASES = ("staging", "Alpha", "alpha-ds")
GIT_C = re.compile(r"git\s+-C\s+(\S+)")


def _git(repo, *args):
    import subprocess
    out = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                         timeout=60)
    return out.returncode, out.stdout


def unintegrated_work(repo, branch, git=None):
    """Why `origin/<branch>` still holds work no base has, or None when every base check passes.
    A commit counts as integrated when git cherry finds it in any base; failing that, the
    branch counts as integrated when every file it changed is identical in some base."""
    git = git or _git
    if git(repo, "rev-parse", "--verify", "-q", "origin/%s" % branch)[0] != 0:
        return "origin/%s not found in %s (fetch first)" % (branch, repo)
    bases = [b for b in INTEGRATED_BASES
             if git(repo, "rev-parse", "--verify", "-q", "origin/%s" % b)[0] == 0]
    if not bases:
        return "no base (staging, Alpha, alpha-ds) found in %s" % repo
    missing = None
    for base in bases:
        rc, out = git(repo, "cherry", "origin/%s" % base, "origin/%s" % branch)
        if rc != 0:
            return "git cherry failed against origin/%s" % base
        plus = {line.split()[1] for line in out.splitlines() if line.startswith("+")}
        missing = plus if missing is None else missing & plus
    if not missing:
        return None
    for base in bases:
        rc, mb = git(repo, "merge-base", "origin/%s" % base, "origin/%s" % branch)
        if rc != 0:
            continue
        rc, names = git(repo, "diff", "--name-only", mb.strip(), "origin/%s" % branch)
        files = [n for n in names.splitlines() if n]
        if rc == 0 and files and git(repo, "diff", "--quiet", "origin/%s" % base,
                                     "origin/%s" % branch, "--", *files)[0] == 0:
            return None
    return "%d commit(s) on %s are in no base: %s" % (
        len(missing), branch, ", ".join(sorted(c[:8] for c in missing)))


def ops_push_problem(command, cwd=None, git=None):
    """The ops team (Memphis) integrates into staging and deletes merged branches, nothing else:
    no force, no tags, nothing to main, master or Canary, and never a delete of a kept branch
    (main, Canary, staging, Alpha, alpha-ds, any staging-<team>). A legacy `alpha-*` team branch
    may be deleted as before; any other branch only after unintegrated_work() finds nothing
    (CEO 2026-10-14: refuse the dangerous automatically; allow the routine). A push to Alpha is
    judged by order_gate (the CEO's promotion order, D-052)."""
    for m in PUSH_ARGS.finditer(command):
        words = m.group("rest").split()
        flags = [w for w in words if w.startswith("-")]
        args = [w for w in words if not w.startswith("-")]
        if any(f in ("-f", "--force", "--force-with-lease", "--mirror", "--all", "--tags")
               or f.startswith("--force") or f.startswith("--force-with-lease") for f in flags):
            return "No force push, mirror, --all or tags (CEO 2026-10-14): push plainly."
        deleting = any(f in ("--delete", "-d") for f in flags)
        c = GIT_C.match(m.group(0))
        repo = os.path.join(cwd or ROOT, c.group(1)) if c else (cwd or ROOT)
        for ref in args[1:]:
            dst = ref.split(":")[-1].replace("refs/heads/", "").lstrip("+")
            if dst.lower() in PROTECTED or dst.lower().startswith(("main-", "master-")):
                return ("Memphis pushes staging only, not %r: Canary is the orchestrator's "
                        "release step and main is merged only by the CEO (P-030). Push the work "
                        "to staging." % dst + NOT_CEO)
            if deleting and KEPT_BRANCH.match(dst):
                return ("%r is kept: main, Canary, staging, Alpha, alpha-ds and every "
                        "staging-<team> are never deleted (D-052)." % dst + NOT_CEO)
            if deleting and not ALPHA_BRANCH.match(dst):
                why = unintegrated_work(repo, dst, git)
                if why:
                    return ("A branch is deleted only when all its work is on staging or Alpha; "
                            "%s. Integrate it first, or keep it and list it." % why + NOT_CEO)
            if not deleting and ref.startswith(":"):
                return "A refspec that deletes (%r) must use --delete." % ref
    return None


def push_problem(command, team_id):
    """A code team pushes ITS OWN branch, `<base>-<team>`, and nothing else (CEO 2026-10-09):
    branches keep teams apart; merging into staging, Alpha, Canary or main is the operations team's.
    Explicit refspecs only, no force, no tags. None = allowed."""
    for m in PUSH_ARGS.finditer(command):
        words = m.group("rest").split()
        flags = [w for w in words if w.startswith("-")]
        args = [w for w in words if not w.startswith("-")]
        if any(f in ("-f", "--force", "--force-with-lease", "--mirror", "--all", "--tags",
                     "--delete", "-d") or f.startswith("--force") for f in flags):
            return ("Teams push without force, tags or deletes (D-042). Push your branch "
                    "plainly: git push origin <base>-%s" % team_id)
        refs = args[1:]
        if not refs:
            return ("Name the branch when you push (D-042): git push origin <base>-%s. "
                    "A bare push could push another branch." % team_id)
        for ref in refs:
            if ref in INTEGRATION_REFS:       # fast lane (CEO 2026-10-10): the builder merges its own small ticket
                continue
            dst = ref.split(":")[-1].replace("refs/heads/", "").lstrip("+")
            base = dst.split("-")[0].lower()
            # exactly `<base>-<team_id>` in the app or `<base>-ds-<team_id>` in the design
            # system; team ids may contain hyphens themselves (deir-el-bahari)
            if base not in BASES or dst.lower() not in ("%s-%s" % (base, team_id),
                                                       "%s-ds-%s" % (base, team_id)):
                return ("Teams push only their own branch, <base>-%s (e.g. staging-%s); %r is "
                        "not yours. Merging into staging, Alpha, Canary or main is done by the "
                        "operations team (Memphis)." % (team_id, team_id, dst))
    return None


PURE_SEGMENT = re.compile(r"^\s*(cd\s+\S+|git(\s+-C\s+\S+)*\s+(push|fetch|status|log|rev-parse|"
                          r"branch\s+--show-current|ls-remote)\b[^;&|<>`$()]*)\s*$")


def pure_push(command):
    """A command that only changes directory, fetches, inspects and pushes: nothing else to judge."""
    if not PUSH.search(command) or "\n" in command.strip():
        return False
    return all(PURE_SEGMENT.match(seg) for seg in re.split(r"&&|;", command) if seg.strip())


def allow_reason(payload, state_store=None, teams_mod=None):
    """An explicit allow for what the rules permit (call only when decide() refused nothing)."""
    tool = payload.get("tool_name") or ""
    if tool.startswith(SUPABASE):
        name = tool[len(SUPABASE):]
        if name in READ_TOOLS:
            return "ops guard: Supabase read on the approved project."
        if name in WRITE_TOOLS and name not in ("execute_sql", "apply_migration"):
            tid, lane = team_of(payload.get("session_id"), state_store, teams_mod)
            if lane == "ops":
                return "ops guard: %s by the ops team on the approved project (D-043)." % name
        return None
    if tool == "Bash":
        command = (payload.get("tool_input") or {}).get("command") or ""
        if pure_push(command):
            tid, lane = team_of(payload.get("session_id"), state_store, teams_mod)
            if lane in ("ops", "code"):
                return "ops guard: a plain push of a branch %s may push." % tid
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:                                     # noqa: BLE001
        return 0
    try:
        reason = decide(payload)
    except Exception as exc:                              # noqa: BLE001
        tool = payload.get("tool_name") or ""
        if tool.startswith(SUPABASE) and tool[len(SUPABASE):] in WRITE_TOOLS | NEVER_TOOLS:
            reason = "ops guard failed (%s); refusing a database write. Retry once." % exc + NOT_CEO
        else:
            return 0
    if reason:
        sys.stderr.write("REFUSED by ops guard: %s\n" % reason)
        return 2
    try:
        ok = allow_reason(payload)
    except Exception:                                     # noqa: BLE001
        ok = None
    if ok:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "allow",
            "permissionDecisionReason": ok}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
