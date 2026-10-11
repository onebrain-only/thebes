"""Automatic integration into Alpha (D-042): verified work reaches Alpha without waiting on the CEO.

When a team's ticket has passed verification (D-041) and its branch is pushed, the Ready
dispatcher asks Memphis, the operations team, to merge it into the base. The CEO delegated
Alpha; Canary and main are never touched here (a branch named canary-* or main-* is ignored).

    app             alpha-<team>      → Alpha        in Dabbler/dabbler-code
    design system   alpha-ds-<team>   → alpha-ds     in Dabbler/dabbler-design-system

One integration per base at a time (Memphis is one session, and the dispatcher never opens a
second while one is open), batching everything pending for that base. Memphis merges in its OWN
worktree, runs the analyzer and the tests on the merged result, and pushes the base only if both
pass. It returns one INTEGRATED line per merged branch; the dispatcher marks those tickets
integrated and comments on them. A conflict it cannot resolve, or a failing check, comes back as
`blocked` to the orchestrator's inbox, which decides; after two failed attempts a ticket is left
alone until someone looks.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                  # noqa: E402

MAX_BATCH = 5
MAX_ATTEMPTS = 2
BASES = (
    # (branch prefix, repo path, base branch, worktree/branch name for the integrator)
    ("alpha-ds-", "Dabbler/dabbler-design-system", "alpha-ds", "integrate-alpha-ds"),
    ("alpha-", "Dabbler/dabbler-code", "Alpha", "integrate-alpha"),
)
INTEGRATED = re.compile(r"^INTEGRATED:\s*(KAN-\d+)\s+(\S+)\s+([0-9a-f]{7,40})", re.M)
FINAL_SHA = re.compile(r"^BASE_SHA:\s*([0-9a-f]{7,40})", re.M)


def base_for(branch):
    for prefix, repo, base, worktree in BASES:
        if branch.startswith(prefix):
            return {"repo": repo, "base": base, "worktree": worktree, "prefix": prefix}
    return None


def remote_head(repo, branch, runner=None):
    """The sha of origin/<branch>, or None."""
    done = (runner or subprocess.run)(["git", "-C", os.path.join(ROOT, repo), "ls-remote",
                                       "--heads", "origin", branch], capture_output=True,
                                      text=True, timeout=60, stdin=subprocess.DEVNULL)
    parts = (done.stdout or "").split()
    return parts[0] if done.returncode == 0 and parts else None


SMALL_MAX_FILES = 5
NOT_SMALL = ("pubspec.yaml", "pubspec.lock", "supabase/")


def changed_files(repo, base, sha, runner=None):
    """Files `sha` changes against origin/<base>, or None when git cannot say."""
    run = runner or subprocess.run
    cwd = os.path.join(ROOT, repo)
    try:
        run(["git", "-C", cwd, "fetch", "origin", base], capture_output=True, text=True,
            timeout=120, stdin=subprocess.DEVNULL)
        done = run(["git", "-C", cwd, "diff", "--name-only", "origin/%s...%s" % (base, sha)],
                   capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            return None
        return [f for f in (done.stdout or "").splitlines() if f.strip()]
    except Exception:                                      # noqa: BLE001
        return None


def is_small(files):
    """Fast lane (CEO 2026-10-10): a verified ticket of at most 5 files, no pubspec and no
    database change is merged by the team that built it. Anything unknown is NOT small."""
    if files is None or not files or len(files) > SMALL_MAX_FILES:
        return False
    return not any(f == n or f.startswith(n) for f in files for n in NOT_SMALL)


def pending(state_store=store, runner=None):
    """Verified, pushed, not-yet-integrated work, grouped by base. Never raises.

    A team's branch carries its tickets one after another, so a branch's head is the LATEST
    verified commit and it contains the earlier ones. A branch is integrated only when its
    remote head is exactly that latest verified commit (nothing unverified rides along); the
    merge uses that commit and every earlier verified ticket on the branch is covered by it."""
    roots = [r for r in state_store.read_all("conversation_dispatch")
             if (r.get("verification") or {}).get("verdict") == "pass" and r.get("jira_key")
             and not r.get("root_dispatch_id")]
    latest = {}
    for r in sorted(roots, key=lambda r: r.get("verified_at") or r.get("outcome_at") or ""):
        v = r["verification"]
        if v.get("branch") and v.get("sha"):
            latest[v["branch"]] = v["sha"]
    groups, head_ok = {}, {}
    for rec in roots:
        if (rec.get("integrated_at") or rec.get("integration_dispatch_id")
                or (rec.get("integration_attempts") or 0) >= MAX_ATTEMPTS):
            continue
        branch = rec["verification"].get("branch")
        target = base_for(branch or "")
        if not target or branch not in latest:
            continue
        if branch not in head_ok:
            try:
                head_ok[branch] = remote_head(target["repo"], branch, runner) == latest[branch]
            except Exception:                              # noqa: BLE001
                head_ok[branch] = False
        if not head_ok[branch]:
            continue
        groups.setdefault(target["base"], {"target": target, "items": []})["items"].append(
            {"dispatch_id": rec["dispatch_id"], "key": rec["jira_key"], "branch": branch,
             "sha": latest[branch], "at": rec.get("verified_at") or rec.get("outcome_at") or ""})
    for g in groups.values():
        g["items"].sort(key=lambda i: i["at"])
        g["items"] = g["items"][:MAX_BATCH]
    return groups


def push_rule(target):
    return "Bash(git -C * push origin %s:%s)" % (target["worktree"], target["base"])


def push_allowed(target, settings_files=None):
    """Memphis can push the base only if the CEO added the allow rule for it: without it the
    permission check stops Memphis on a prompt nobody can answer, and a blocked ops team stops
    migrations and rulings too. So the dispatcher waits for the rule instead of sending work
    that would block (live 2026-10-09). The rule is the CEO's one-time grant."""
    home = os.path.expanduser("~")
    files = settings_files or [os.path.join(ROOT, ".claude", "settings.json"),
                               os.path.join(ROOT, ".claude", "settings.local.json"),
                               os.path.join(home, ".claude", "settings.json")]
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                if push_rule(target) in ((json.load(fh).get("permissions") or {}).get("allow") or []):
                    return True
        except (OSError, ValueError):
            continue
    return False


def open_integration(base, state_store=store):
    return next((r for r in state_store.read_all("conversation_dispatch")
                 if r.get("integrates_base") == base
                 and r.get("status") in store.CONVERSATION_DISPATCH_OPEN), None)


def brief(group):
    t, items = group["target"], group["items"]
    lines = ["THEBES_INTEGRATION %s" % t["base"],
             "Merge the verified branches below into %s in %s, in this order. This is routine and "
             "delegated (D-042): do not ask the CEO." % (t["base"], t["repo"]), ""]
    by_branch = {}
    for i in items:
        by_branch.setdefault((i["branch"], i["sha"]), []).append(i["key"])
    lines += ["  %s @ %s  (tickets: %s)" % (b, sha[:12], ", ".join(keys))
              for (b, sha), keys in by_branch.items()]
    lines += ["",
              "Do it in your OWN worktree, never in the shared checkout (it may hold someone's "
              "unsaved changes):",
              "1. git -C %s fetch origin; create a worktree on a new local branch `%s` from "
              "origin/%s (if it exists from before, remove it first)." % (t["repo"], t["worktree"],
                                                                         t["base"]),
              "2. For each branch, in order: git merge --no-ff <sha> -m \"Integrate <KEYS>: <summary>\". "
              "A conflict you can settle without changing behaviour (imports, formatting, "
              "adjacent additions): settle it and say so. Otherwise git merge --abort, skip that "
              "branch and report the files and hunks.",
              "3. Run `flutter analyze --no-pub --no-fatal-infos` and `flutter test --no-pub` on the "
              "UNMERGED origin/%s first, then on the merged result. `analyze` must exit 0. A "
              "red base does not stop delivery (live 2026-10-09: 59 render tests were already "
              "failing on Alpha): compare the failing tests BY NAME, not by count. Any test that "
              "fails only on the merged result blocks the integration." % t["base"],
              "4. Push only if analyze exits 0 and no test fails only on the merged result: "
              "git -C <worktree> push origin %s:%s. Otherwise push NOTHING, reset the worktree to "
              "origin/%s and report the new failures. Save both failing lists in your report." % (
                  t["worktree"], t["base"], t["base"]),
              "5. Never push or merge Canary or main, never force-push, never touch the database.",
              "",
              "Report ONE result. For every TICKET whose branch is now in %s write exactly one line:" % t["base"],
              "  INTEGRATED: <KEY> <branch> <merge-commit-sha>",
              "and then:  BASE_SHA: <the sha of %s after your push>" % t["base"],
              "List separately every branch you skipped and why. Outcome `completed` when every "
              "branch is integrated; `blocked` when any was skipped or nothing was pushed (the "
              "orchestrator decides what happens next)."]
    return "\n".join(lines)


def dispatch_for(state_store=store, jira=None, dispatch=None, runner=None, settings_files=None):
    """Open at most one integration per base. Returns what it did."""
    from agent.execution import conversation_dispatch as cd
    done = []
    memphis = next(iter(teams.lane_teams("ops")), None)
    binding = state_store.active_role_session(memphis) if memphis else None
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not binding or not orch:
        return done
    busy = {r["target_session_id"] for r in state_store.read_all("conversation_dispatch")
            if r.get("status") in store.CONVERSATION_DISPATCH_OPEN}
    for base, group in pending(state_store, runner).items():
        if open_integration(base, state_store):
            continue
        if not push_allowed(group["target"], settings_files):
            done.append({"integrate": base, "action": "waiting",
                         "reason": "push-rule-missing: %s" % push_rule(group["target"])})
            continue
        executor, lane = binding["session_id"], "ops"
        if len(group["items"]) == 1:                      # fast lane: the builder merges its own
            item = group["items"][0]
            root = state_store.read("conversation_dispatch", item["dispatch_id"]) or {}
            builder = root.get("target_session_id")
            seat = teams.read().get(root.get("target_seat_id"), {})
            if (builder and seat.get("lane", "code") == "code" and builder not in busy
                    and is_small(changed_files(group["target"]["repo"], base, item["sha"], runner))):
                executor, lane = builder, "team"
        if executor in busy:
            done.append({"integrate": base, "action": "waiting", "reason": "ops-team-busy"})
            continue
        env = {k: v for k, v in os.environ.items()
               if k not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID")}
        env[cd.CLAUDE_ORIGIN_ENV] = orch
        try:
            out = (dispatch or cd.dispatch)(brief(group), executor, env=env,
                                            state_store=state_store, detach=True, ticket=None)
        except cd.Refused as exc:
            done.append({"integrate": base, "action": "refused", "code": exc.code})
            continue
        did = out.get("dispatch_id")
        rec = state_store.read("conversation_dispatch", did)
        state_store.update("conversation_dispatch", did, rec["revision"],
                           {"integrates_base": base,
                            "integrates": [i["dispatch_id"] for i in group["items"]]})
        for item in group["items"]:
            root = state_store.read("conversation_dispatch", item["dispatch_id"])
            state_store.update("conversation_dispatch", item["dispatch_id"], root["revision"],
                               {"integration_dispatch_id": did})
        busy.add(executor)
        done.append({"integrate": base, "action": "dispatched", "dispatch_id": did, "lane": lane,
                     "tickets": [i["key"] for i in group["items"]]})
    return done


def settle(state_store=store, jira=None):
    """Read finished integration dispatches: mark integrated tickets, release the rest."""
    done = []
    for rec in state_store.read_all("conversation_dispatch"):
        if (not rec.get("integrates_base") or rec.get("settled_at")
                or rec.get("status") not in store.CONVERSATION_RESULT_OUTCOMES):
            continue
        try:
            with open(rec["result_ref"], encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, TypeError, KeyError):
            text = ""
        merged = {(m.group(1), m.group(2)): m.group(3) for m in INTEGRATED.finditer(text)}
        base_sha = (FINAL_SHA.search(text) or [None, None])[1] if FINAL_SHA.search(text) else None
        for rid in rec.get("integrates") or []:
            root = state_store.read("conversation_dispatch", rid)
            if not root:
                continue
            ver = root.get("verification") or {}
            key, branch = root.get("jira_key"), ver.get("branch")
            changes = {"integration_dispatch_id": None}
            if (key, branch) in merged:
                changes["integrated_at"] = state_store.now()
                changes["integrated_sha"] = merged[(key, branch)]
                done.append({"integrated": key, "branch": branch, "base_sha": base_sha})
                _comment(jira, key, "Integrated into %s: branch %s, merge commit %s%s."
                         % (rec["integrates_base"], branch, merged[(key, branch)][:12],
                            (", %s now at %s" % (rec["integrates_base"], base_sha[:12]))
                            if base_sha else ""))
            else:
                changes["integration_attempts"] = (root.get("integration_attempts") or 0) + 1
                done.append({"not-integrated": key, "attempts": changes["integration_attempts"]})
            state_store.update("conversation_dispatch", rid, root["revision"], changes)
        cur = state_store.read("conversation_dispatch", rec["dispatch_id"])
        state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                           {"settled_at": state_store.now()})
    return done


def _comment(jira, key, text):
    try:
        if jira is None:
            from agent.execution import jira_sync
            jira = jira_sync._client(None, store)
        if jira is not None:
            jira.add_comment(key, "Thebes: " + text)
    except Exception:                                      # noqa: BLE001  never blocks
        pass
