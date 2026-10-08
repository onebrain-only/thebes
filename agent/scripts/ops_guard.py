#!/usr/bin/env python3
"""Ops guard — PreToolUse hook (D-042): only the ops team writes to the database or pushes.

Every session in this checkout reads the same settings file, so a permission rule cannot
tell Memphis from Karnak. This hook can: it reads the session id Claude Code passes in,
finds which team that session is bound to in Persistent State, and decides.

    Supabase write tools   allowed ONLY for a session bound to an `ops`-lane team.
                           Everyone else (code teams, the orchestrator, unbound sessions)
                           is refused at once, so a team never stops on a permission prompt:
                           it reads the refusal and reports `blocked: needs-ops`.
    Project-destroying     (pause/restore/create project, delete/reset branch) refused for
    Supabase tools         everyone, ops included: those stay with the CEO.
    git push               refused for code-lane team sessions. The ops team and sessions
                           that are not teams keep their normal rules.

Exit 0 = no opinion (the normal permission flow continues). Exit 2 = refuse, reason on
stderr. A Supabase write the hook cannot attribute is refused (fail closed); anything else
it cannot parse gets no opinion (fail open), like the other guards.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

SUPABASE = "mcp__claude_ai_Supabase__"
WRITE_TOOLS = {"apply_migration", "execute_sql", "deploy_edge_function",
               "create_edge_function_secret", "create_branch", "merge_branch",
               "rebase_branch"}
CEO_ONLY_TOOLS = {"pause_project", "restore_project", "create_project", "delete_branch",
                  "reset_branch", "confirm_cost"}
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


def decide(payload, state_store=None, teams_mod=None):
    """Return None (no opinion) or a refusal reason."""
    tool = payload.get("tool_name") or ""
    sid = payload.get("session_id")
    if tool.startswith(SUPABASE):
        name = tool[len(SUPABASE):]
        if name in CEO_ONLY_TOOLS:
            return ("%s is the CEO's to run (D-042): it changes the Supabase project itself. "
                    "Report it as a hard stop instead." % name)
        if name not in WRITE_TOOLS:
            return None
        try:
            tid, lane = team_of(sid, state_store, teams_mod)
        except Exception as exc:                          # noqa: BLE001
            return "ops guard could not identify this session (%s); refusing a database write" % exc
        if lane == "ops":
            return None
        return ("Database writes belong to the operations team (Memphis), D-042. %s may not run "
                "%s. Commit the SQL and its probes on your branch and report `blocked: needs-ops` "
                "naming the migration; the orchestrator sends it to Memphis."
                % (tid or "This session", name))
    if tool == "Bash":
        command = (payload.get("tool_input") or {}).get("command") or ""
        if not PUSH.search(command):
            return None
        try:
            tid, lane = team_of(sid, state_store, teams_mod)
        except Exception:                                 # noqa: BLE001
            return None
        if lane == "code":
            return ("Teams do not push (D-042). Commit on your branch <base>-%s and report; "
                    "integration and pushing are done by the operations team (Memphis)." % tid)
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
        if tool.startswith(SUPABASE) and tool[len(SUPABASE):] in WRITE_TOOLS | CEO_ONLY_TOOLS:
            reason = "ops guard failed (%s); refusing a database write" % exc
        else:
            return 0
    if reason:
        sys.stderr.write("REFUSED by ops guard: %s\n" % reason)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
