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
import time
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
        if branch.lower().startswith(prefix):        # "Alpha-karnak" from before B8 too
            return {"repo": repo, "base": base, "worktree": worktree, "prefix": prefix}
    return None


def _targets():
    return [{"repo": repo, "base": base, "worktree": worktree, "prefix": prefix}
            for prefix, repo, base, worktree in BASES]


def has_commit(repo, sha, runner=None):
    """Does this repo hold the commit? (A local check; no network.)"""
    try:
        done = (runner or subprocess.run)(
            ["git", "-C", os.path.join(ROOT, repo), "cat-file", "-e", "%s^{commit}" % sha],
            capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        return done.returncode == 0
    except Exception:                                      # noqa: BLE001
        return False


def target_for(branch, sha=None, runner=None):
    """The base a verified branch@sha integrates into, by WHICH REPO HOLDS THE COMMIT.

    A branch name alone cannot say: `Alpha-deir-el-bahari` exists in the app and in the design
    system (KAN-508 lived in the design system and was never seen as integrated). An explicit
    `alpha-ds-` name is the design system; otherwise the repo that has the sha, the name's own
    repo first."""
    named = base_for(branch or "")
    if named is None:                      # canary-*, main, anything else: never auto-integrated
        return None
    if named["prefix"] == "alpha-ds-":
        return named
    if sha:
        order = [named] + [t for t in _targets() if t != named]
        for t in order:
            if has_commit(t["repo"], sha, runner):
                return t
    return named


def remote_heads(repo, branch, runner=None):
    """Every sha origin holds for this branch name, ignoring case (live 2026-10-16: Karnak pushes
    `Alpha-karnak`, Thebes asked for `alpha-karnak`, and KAN-561/563 were skipped silently)."""
    done = (runner or subprocess.run)(["git", "-C", os.path.join(ROOT, repo), "ls-remote",
                                       "--heads", "origin"], capture_output=True,
                                      text=True, timeout=60, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        return []
    want = "refs/heads/%s" % branch.lower()
    out = []
    for line in (done.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lower() == want:
            out.append(parts[0])
    return out


def remote_head(repo, branch, runner=None):
    """The sha of origin/<branch> (case-insensitive), or None."""
    heads = remote_heads(repo, branch, runner)
    return heads[0] if heads else None


def ticket_commits_on_base(repo, base, sha, key, runner=None):
    """True when none of this ticket's commits that `sha` carries is missing from origin/<base>,
    even if base holds them under another sha: a cherry-pick of one ticket out of a shared team
    branch (live 2026-10-14, KAN-505: mark-integrated refused it and KAN-509 stayed blocked).
    A commit is the ticket's when its subject starts with `KAN-n:`. `git cherry` marks commits of
    `sha` that base lacks "+" and those it has under another sha (same patch-id) "-"; a commit
    already reachable from base is not listed at all. Needs at least one such commit. Unknown ->
    False (the work is then integrated normally)."""
    if not key:
        return False
    run = runner or subprocess.run
    cwd = os.path.join(ROOT, repo)
    try:
        ch = run(["git", "-C", cwd, "cherry", "origin/%s" % base, sha], capture_output=True,
                 text=True, timeout=60, stdin=subprocess.DEVNULL)
        lg = run(["git", "-C", cwd, "log", "--format=%H %s", "-n", "400", sha],
                 capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if ch.returncode != 0 or lg.returncode != 0:
            return False
        mine = {l.split(" ", 1)[0] for l in (lg.stdout or "").splitlines()
                if l.split(" ", 1)[-1].startswith("%s:" % key)}
        missing = {l[2:].strip() for l in (ch.stdout or "").splitlines() if l.startswith("+ ")}
        return bool(mine) and not (mine & missing)
    except Exception:                                      # noqa: BLE001
        return False


# CEO 2026-10-10 let a team merge its own small ticket. In practice it fails: a code team may not
# work in the CEO's folders, and `git worktree add` there is refused (Ramesseum, KAN-531,
# 2026-10-14). Integration is the ops team's (Memphis) only, whichever team built the branch.
FAST_LANE = False
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


def already_on_base(repo, base, sha, runner=None, key=None):
    """True when `sha` is already contained in origin/<base>, or (with `key`) when every commit of
    that ticket on it is already there under another sha. Unknown -> False (integrate)."""
    try:
        done = (runner or subprocess.run)(
            ["git", "-C", os.path.join(ROOT, repo), "merge-base", "--is-ancestor", sha,
             "origin/%s" % base], capture_output=True, text=True, timeout=60,
            stdin=subprocess.DEVNULL)
        if done.returncode == 0:
            return True
    except Exception:                                      # noqa: BLE001
        return False
    return ticket_commits_on_base(repo, base, sha, key, runner)


_FETCHED = {}
FETCH_EVERY = 300


def _skipped(report, state_store, reason, key):
    """Say, once per 6 hours per (ticket, reason), that verified work is not being integrated and
    why, instead of skipping it silently."""
    if report is None:
        return
    marker = os.path.join(state_store.RUNTIME, "review", "integrate-skip-%s" %
                          "".join(c if c.isalnum() else "_" for c in "%s-%s" % (key, reason))[:120])
    try:
        if time.time() - float(open(marker).read()) < 6 * 3600:
            return
    except (OSError, ValueError):
        pass
    try:
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass
    report.append({"integrate": "skipped", "key": key, "reason": reason})


def _fetch_base(repo, base, runner=None, now=None):
    """Refresh origin/<base> at most every FETCH_EVERY seconds per repo."""
    now = now or time.time()
    if now - _FETCHED.get((repo, base), 0) < FETCH_EVERY:
        return
    _FETCHED[(repo, base)] = now
    try:
        (runner or subprocess.run)(["git", "-C", os.path.join(ROOT, repo), "fetch", "origin", base],
                                   capture_output=True, text=True, timeout=120,
                                   stdin=subprocess.DEVNULL)
    except Exception:                                      # noqa: BLE001
        pass


def reconcile(state_store=store, runner=None, fetch=True):
    """Verified work whose commit IS an ancestor of its base is integrated, whoever merged it
    (malfunction 2026-10-13: KAN-497 and KAN-508 held their dependants for hours because only
    Memphis's own report ever set integrated_at). Repo-aware; never raises."""
    done = []
    try:
        for rec in state_store.read_all("conversation_dispatch"):
            v = rec.get("verification") or {}
            if (v.get("verdict") != "pass" or not rec.get("jira_key") or rec.get("root_dispatch_id")
                    or rec.get("integrated_at") or rec.get("integration_dispatch_id")
                    or not v.get("branch") or not v.get("sha")):
                continue
            t = target_for(v["branch"], v["sha"], runner)
            if not t:
                continue
            if fetch:
                _fetch_base(t["repo"], t["base"], runner)
            if already_on_base(t["repo"], t["base"], v["sha"], runner, rec.get("jira_key")):
                cur = state_store.read("conversation_dispatch", rec["dispatch_id"])
                state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                                   {"integrated_at": state_store.now(), "integrated_sha": v["sha"],
                                    "integrated_via": "ancestor-of-%s" % t["base"]})
                done.append({"reconciled": rec["jira_key"], "base": t["base"], "sha": v["sha"][:12]})
    except Exception:                                      # noqa: BLE001
        pass
    return done


def mark_integrated(dispatch_id, base, sha, evidence, *, state_store=store, runner=None,
                    fetch=True, jira=None):
    """Record by hand that a verified dispatch is in `base` (a manual or Memphis integration
    Thebes did not see). Refused unless git agrees: the verified commit AND `sha` must both be
    contained in origin/<base> of the repo that base belongs to."""
    if not (evidence or "").strip():
        raise ValueError("evidence is required: say who integrated it and where you saw it")
    matches = [r for r in state_store.read_all("conversation_dispatch")
               if r["dispatch_id"] == dispatch_id or r["dispatch_id"].startswith(dispatch_id)]
    if len(matches) != 1:
        raise ValueError("%r matches %d dispatches" % (dispatch_id, len(matches)))
    rec = matches[0]
    v = rec.get("verification") or {}
    if rec.get("root_dispatch_id") or v.get("verdict") != "pass" or not v.get("sha"):
        raise ValueError("%s is not a verified (pass) root dispatch" % rec["dispatch_id"])
    target = next((t for t in _targets() if t["base"].lower() == (base or "").lower()), None)
    if target is None:
        raise ValueError("base must be one of: %s" % ", ".join(t["base"] for t in _targets()))
    if fetch:
        _FETCHED.pop((target["repo"], target["base"]), None)
        _fetch_base(target["repo"], target["base"], runner)
    for what, ref in (("the verified commit", v["sha"]), ("--sha", sha)):
        if not already_on_base(target["repo"], target["base"], ref, runner, rec.get("jira_key")):
            raise ValueError("%s %s is not contained in origin/%s of %s: nothing recorded"
                             % (what, ref[:12], target["base"], target["repo"]))
    cur = state_store.read("conversation_dispatch", rec["dispatch_id"])
    state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"], {
        "integrated_at": state_store.now(), "integrated_sha": sha,
        "integrated_via": "manual-mark", "integration_evidence": evidence.strip()[:500]})
    _comment(jira, rec["jira_key"], "recorded as integrated into %s at %s. Evidence: %s"
             % (target["base"], sha[:12], evidence.strip()[:300]))
    return {"status": "marked", "dispatch_id": rec["dispatch_id"], "ticket": rec["jira_key"],
            "base": target["base"], "sha": sha}


def pending(state_store=store, runner=None, skipped=None):
    """Verified, pushed, not-yet-integrated work, grouped by base. Never raises.

    A team's branch carries its tickets one after another, so a branch's head is the LATEST
    verified commit and it contains the earlier ones. A branch is integrated only when its
    remote head is exactly that latest verified commit (nothing unverified rides along); the
    merge uses that commit and every earlier verified ticket on the branch is covered by it."""
    roots = [r for r in state_store.read_all("conversation_dispatch")
             if (r.get("verification") or {}).get("verdict") == "pass" and r.get("jira_key")
             and not r.get("root_dispatch_id")]
    memo = {}

    def tgt(r):
        v = r["verification"]
        key = (v.get("branch"), v.get("sha"))
        if key not in memo:
            memo[key] = target_for(v.get("branch") or "", v.get("sha"), runner)
        return memo[key]

    latest = {}
    for r in sorted(roots, key=lambda r: r.get("verified_at") or r.get("outcome_at") or ""):
        v = r["verification"]
        t = tgt(r) if v.get("branch") and v.get("sha") else None
        if t:
            latest[(t["repo"], v["branch"])] = v["sha"]
    groups, head_ok = {}, {}
    for rec in roots:
        if (rec.get("integrated_at") or rec.get("integration_dispatch_id")
                or (rec.get("integration_attempts") or 0) >= MAX_ATTEMPTS):
            continue
        branch = rec["verification"].get("branch")
        target = tgt(rec)
        if not target or (target["repo"], branch) not in latest:
            continue
        lkey = (target["repo"], branch)
        if lkey not in head_ok:
            try:
                heads = remote_heads(target["repo"], branch, runner)
                head_ok[lkey] = latest[lkey] in heads
                why = ("branch-not-found-on-origin" if not heads else
                       None if head_ok[lkey] else "branch-moved-past-the-verified-commit")
            except Exception:                              # noqa: BLE001
                head_ok[lkey], why = False, "git-error"
            if why:
                _skipped(skipped, state_store, "branch %s: %s" % (branch, why), rec.get("jira_key"))
        if not head_ok[lkey]:
            continue
        if already_on_base(target["repo"], target["base"], latest[lkey], runner, rec.get("jira_key")):
            # B5: the orchestrator's own integration already merged this tip; an automatic
            # second one made Memphis do an empty pass. Record it and move on.
            cur = state_store.read("conversation_dispatch", rec["dispatch_id"])
            state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                               {"integrated_at": state_store.now(), "integrated_sha": latest[lkey]})
            continue
        groups.setdefault(target["base"], {"target": target, "items": []})["items"].append(
            {"dispatch_id": rec["dispatch_id"], "key": rec["jira_key"], "branch": branch,
             "sha": latest[lkey], "at": rec.get("verified_at") or rec.get("outcome_at") or ""})
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
    skipped = []
    groups = pending(state_store, runner, skipped)
    done.extend(skipped)
    for base, group in groups.items():
        if open_integration(base, state_store):
            continue
        if not push_allowed(group["target"], settings_files):
            done.append({"integrate": base, "action": "waiting",
                         "reason": "push-rule-missing: %s" % push_rule(group["target"])})
            continue
        executor, lane = binding["session_id"], "ops"
        if FAST_LANE and len(group["items"]) == 1:        # fast lane: the builder merges its own
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


def settle(state_store=store, jira=None, runner=None):
    """Read finished integration dispatches: mark integrated tickets, release the rest."""
    done = reconcile(state_store, runner)
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
