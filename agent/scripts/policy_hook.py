#!/usr/bin/env python3
"""Policy hook — PermissionRequest (autonomy constitution, D-043, 2026-10-27).

A permission prompt in a Thebes session is a question nobody should be asked: the teams run
in the background and the CEO is out of the product cycle. Claude Code raises this event
just before it would show a prompt; this hook answers it, by code, for every session bound
to a team or the orchestrator in Persistent State:

    deny    the never-list (wrong Supabase project, vault/auth secrets, GRANT to anon/public,
            force push, pushing main, project lifecycle), anything another guard refuses,
            system and security settings, and the CEO's three (money, merging into main,
            sending outside the company) — every refusal names the alternative and is
            never a question for the CEO;
    allow   everything else the session's lane may do.

It never answers "ask". A session that is not bound to a team or the orchestrator gets no
opinion (the CEO's own interactive sessions keep the normal prompt). Fails closed: if the
hook breaks on a bound session, it denies with the error so the worker retries or reports.

    {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                            "decision": {"behavior": "allow" | "deny", "message": "..."}}}
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import ops_guard                                                     # noqa: E402
import sql_hook                                                      # noqa: E402

NOT_CEO = " This is an answer, not a question: never take it to the CEO (D-043)."
HOME = os.path.expanduser("~")
WRITE_ROOTS = tuple(os.path.realpath(p) for p in (
    ROOT, os.path.join(HOME, ".claude", "jobs"), "/tmp", "/private/tmp", "/var/folders",
    "/private/var/folders"))
PROTECTED_FILES = re.compile(
    r"(^|/)\.claude/settings(\.local)?\.json$|(^|/)\.ssh/|(^|/)\.(zshrc|zprofile|bashrc|bash_profile|"
    r"profile|gitconfig|netrc|npmrc)$|^/etc/|^/Library/|(^|/)Library/(LaunchAgents|LaunchDaemons|"
    r"Keychains)/|(^|/)\.aws/|(^|/)\.config/gh/")

# (pattern, refusal) for shell commands; first match wins.
SHELL_DENY = (
    (re.compile(r"(^|[;&|(\s])sudo\s"), "No sudo: work in user space inside your worktree."),
    (re.compile(r"(^|[;&|(\s])(defaults\s+write|launchctl|csrutil|spctl|networksetup|systemsetup|"
                r"scutil|pmset|security\s+(add|delete|set|import|unlock|find-generic-password|"
                r"find-internet-password|dump))\b"),
     "System and security settings are never changed by a team."),
    (re.compile(r"(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(sh|bash|zsh|python3?)\b"),
     "Do not pipe a download into a shell: add the dependency through the project's package manager."),
    (re.compile(r"\bchmod\s+-R\s+0?777\b|\bchown\s+-R\b"), "No recursive permission or owner changes."),
    (re.compile(r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*\s+)+(/|~|\$HOME|/Users/?[^/\s]*/?)(\s|$|\*)"),
     "Never remove a home or system directory. Remove only the files you created inside your worktree."),
    (re.compile(r"\bgit(\s+-C\s+\S+)*\s+push\b[^;&|]*(\s--force\S*|\s-f\b|\s--mirror\b|\s\+\S+)"),
     "No force push (never-list): push a new commit."),
    (re.compile(r"\bgh\s+pr\s+merge\b"),
     "Merging a PR into main is the CEO's (P-030). Integrate into staging with git; leave the PR open."),
    (re.compile(r"\bgh\s+release\b|\bnpm\s+publish\b|\bfastlane\b[^;&|]*\b(deliver|supply|pilot|upload_to_\w+)\b|"
                r"\bxcrun\s+altool\b|\btransporter\b"),
     "Publishing to users or stores is sending outside the company — the CEO's (D-043). Report "
     "`blocked: needs-ceo: external` with what would be published, and carry on."),
    (re.compile(r"\bsupabase\s+(projects\s+(create|delete)|orgs\b|db\s+reset\b)"),
     "Project lifecycle and remote resets are on the never-list. Use project wtncuzcskpigqpmnxwws "
     "and snapshot-then-change instead."),
    (re.compile(r"(\.claude/settings(\.local)?\.json|~/\.claude/settings)"),
     "Claude settings are not edited by a session; the hooks and settings come from the repository."),
)
CODE_ONLY_DENY = (
    (re.compile(r"\bwrangler\b[^;&|]*\b(deploy|publish|pages\s+deploy)\b"),
     "Deploys are Memphis's: push your branch and report it ready; Memphis integrates and deploys."),
    (re.compile(r"\bsupabase\s+(db\s+push|functions\s+deploy|secrets\s+set|migration\s+up)\b"),
     "Database and edge-function changes are Memphis's: commit them on your branch and report "
     "`blocked: needs-ops`."),
)
PROJECT_REF = re.compile(r"--project-ref[=\s]+([a-z0-9]{20})")

MCP_MONEY = re.compile(r"__(buy_|purchase|checkout|confirm_cost|get_purchase_quote$|ads_studio_generate|"
                       r"generate_(image|video|audio|3d)|upscale_|execute_preset|create_sandboxes|"
                       r"start_rolling_release)")
MCP_EXTERNAL = re.compile(r"__(send_message|reply|forward|slack_send|slack_schedule|schedule_message|"
                          r"publish|tiktok_|share_file|board_share|space_share|deploy_website|"
                          r"notion-send-message|request_promote|assign_alias|unpublish)")


def bound(session_id, state_store=None, teams_mod=None):
    """(seat_id, lane, kind) for a session bound to a team or the orchestrator, else None."""
    if not session_id:
        return None
    if state_store is None:
        from agent.state import store as state_store
    if teams_mod is None:
        from agent.state import teams as teams_mod
    for rec in state_store.read_all("role_session"):
        if rec.get("status") == "active" and rec.get("session_id") == session_id:
            seat = rec.get("seat_id")
            entry = teams_mod.read().get(seat) or {}
            kind = entry.get("kind", "team") if entry else None
            if kind in ("team", "orchestrator"):
                return seat, (entry.get("lane") if kind == "team" else "orchestrator"), kind
    return None


def _inside(path, cwd):
    full = os.path.realpath(os.path.join(cwd or ROOT, os.path.expanduser(path)))
    return any(full == r or full.startswith(r + os.sep) for r in WRITE_ROOTS), full


def judge(payload, state_store=None, teams_mod=None):
    """('allow'|'deny', message) for a bound session, or None for no opinion."""
    who = bound(payload.get("session_id"), state_store, teams_mod)
    if not who:
        return None
    seat, lane, _ = who
    tool = payload.get("tool_name") or ""
    args = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or ROOT

    refusal = ops_guard.decide(payload, state_store, teams_mod)
    if refusal:
        return "deny", refusal

    if tool == sql_hook.TOOL:
        r = sql_hook.decide(payload, state_store, teams_mod)
        if r:
            return r["decision"], r["reason"]
        return "deny", ("Database writes belong to Memphis: commit the SQL on your branch and "
                        "report `blocked: needs-ops`." + NOT_CEO)

    if tool.startswith("mcp__"):
        if MCP_MONEY.search(tool):
            return "deny", ("This spends money — the CEO's (D-043). Report `blocked: needs-ceo: money` "
                            "with the amount and why, and carry on with other work.")
        if MCP_EXTERNAL.search(tool):
            return "deny", ("This sends outside the company — the CEO's (D-043). Report "
                            "`blocked: needs-ceo: external` with the exact text and recipient, and "
                            "carry on with other work.")
        return "allow", "policy hook: %s may use %s (D-043)." % (seat, tool)

    if tool == "Bash":
        command = args.get("command") or ""
        for pat, why in SHELL_DENY:
            if pat.search(command):
                return "deny", why + NOT_CEO
        if lane == "code":
            for pat, why in CODE_ONLY_DENY:
                if pat.search(command):
                    return "deny", why + NOT_CEO
        for ref in PROJECT_REF.findall(command):
            if ref != ops_guard.PROJECT:
                return "deny", ("Only Supabase project %s is ever used." % ops_guard.PROJECT) + NOT_CEO
        if ops_guard.PUSH.search(command) and re.search(r"\s(\S+:)?(refs/heads/)?(main|master)(\s|$)",
                                                        command):
            if lane != "orchestrator" or "dabbler" in command.lower() or "/.claude/jobs/" in cwd \
                    or os.path.realpath(cwd) != os.path.realpath(ROOT):
                return "deny", ("Pushing main is on the never-list for the product (P-030): staging "
                                "is the integration branch and Alpha the customer trial (D-052)." + NOT_CEO)
        return "allow", "policy hook: shell command within %s's lane (D-043)." % seat

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = args.get("file_path") or args.get("notebook_path") or ""
        ok, full = _inside(path, cwd)
        if PROTECTED_FILES.search(full) or PROTECTED_FILES.search(path):
            return "deny", ("%s is a settings or credentials file; a session never edits it." % path) + NOT_CEO
        if not ok:
            return "deny", ("Write inside the workspace or your worktree under ~/.claude/jobs, not %s."
                            % full) + NOT_CEO
        return "allow", "policy hook: file edit inside the workspace."

    return "allow", "policy hook: %s within %s's lane (D-043)." % (tool or "tool", seat)


def _log(payload, behavior, message):
    """One line per answered prompt, for ceo_metrics. Best effort."""
    try:
        from agent.state import store
        import time
        who = bound(payload.get("session_id")) or (None, None, None)
        with open(os.path.join(store.RUNTIME, "policy-hook.log"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "team": who[0], "lane": who[1], "tool": payload.get("tool_name"),
                                 "decision": behavior, "reason": (message or "")[:160]}) + "\n")
    except Exception:                                     # noqa: BLE001
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:                                     # noqa: BLE001
        return 0
    try:
        verdict = judge(payload)
    except Exception as exc:                              # noqa: BLE001
        try:
            is_bound = bound(payload.get("session_id"))
        except Exception:                                 # noqa: BLE001
            is_bound = None
        if not is_bound:
            return 0
        verdict = ("deny", "The policy hook failed (%s). Retry once; if it fails again report "
                   "`blocked` to the orchestrator with this text.%s" % (str(exc)[:160], NOT_CEO))
    if not verdict:
        return 0
    behavior, message = verdict
    _log(payload, behavior, message)
    decision = {"behavior": behavior}
    if behavior == "deny":
        decision["message"] = message
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                                        "decision": decision}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
