"""Verify a team's claim; never redo its work (D-041).

A dispatch that names a ticket carries CHECKS (agent/execution/dispatch_brief.py): the agreed
scenarios for "done". When the team reports `completed` with a VERIFY block, this
module settles the claim:

    run checks    Thebes re-runs each declared command ONCE, in the team's worktree, on
                  the exact commit the team reported. No model, no tokens. Only a small
                  allowlist of read-only Flutter/Dart commands is ever executed, never
                  through a shell, and only inside a worktree Thebes can see belongs to a
                  team (under ~/.claude/jobs or this workspace's Dabbler/).
    judge checks  go to ONE reviewer for ONE pass, with the team's named evidence. The
                  orchestrator records the answer: `verify verdict`.
    PASS          every check passed → the ticket is closed (Done) when its route is SELF
                  (the policy default); a PEER or QA route keeps its review status, now
                  with verified evidence, so its reviewer checks the delta, not the work.
    FAIL          the team gets ONLY the failing checks and their output, as a
                  continuation of the same dispatch. First pass + one fix: MAX_CYCLES = 2.
                  Still failing → the review is EXHAUSTED: the ticket stays where it is,
                  the reason is written on it, and the orchestrator is alerted. No loop.

The team's report carries, anywhere in the result file:

    VERIFY
    branch: alpha-karnak
    sha: <40 hex>
    worktree: /Users/…/worktrees/alpha-karnak
    C1: PASS — flutter test test/forms/select_test.dart, 12 passed
    C3: PASS — screenshot /path/home.png vs frame "Home Feed"

    python3 -m agent.execution.verify run <dispatch_id>
    python3 -m agent.execution.verify verdict <dispatch_id> --pass C3 --fail C5:"reason"
    python3 -m agent.execution.verify status <dispatch_id>
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

MAX_CYCLES = 2                    # the first pass and one targeted fix
CHECK_TIMEOUT_SECONDS = 1200
TAIL_LINES = 25
ALLOWED_PREFIXES = (("flutter", "test"), ("flutter", "analyze"), ("dart", "analyze"),
                    ("dart", "test"))
ARG_RE = re.compile(r"^[A-Za-z0-9_./:=,@+\-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SCRUBBED = ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE",
            "THEBES_DISPATCH_CAPABILITY", "THEBES_ORIGIN_CLAUDE_SID")


def allowed_roots():
    home = os.path.expanduser("~")
    return (os.path.realpath(os.path.join(home, ".claude", "jobs")),
            os.path.realpath(os.path.join(ROOT, "Dabbler")))


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


# ------------------------------------------------------------------ commands
def command_problem(command):
    """Why a `run` check command may not be executed, or None."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return "unparseable (%s)" % exc
    if not argv:
        return "empty"
    if not any(tuple(argv[:len(p)]) == p for p in ALLOWED_PREFIXES):
        return ("only %s are run by Thebes"
                % ", ".join(" ".join(p) for p in ALLOWED_PREFIXES))
    for a in argv:
        if not ARG_RE.match(a):
            return "argument %r has characters Thebes does not pass to a command" % a
        if a == ".." or a.startswith("../") or "/../" in a or a.startswith("/"):
            return "argument %r leaves the worktree" % a
    return None


def run_command(command, cwd, timeout=CHECK_TIMEOUT_SECONDS, runner=None):
    """Execute one allowlisted command without a shell. Returns exit and output tail."""
    why = command_problem(command)
    if why:
        return {"exit": None, "tail": "refused: %s" % why, "seconds": 0}
    import time
    started = time.time()
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED}
    try:
        done = (runner or subprocess.run)(shlex.split(command), cwd=cwd, env=env,
                                          stdin=subprocess.DEVNULL, capture_output=True,
                                          text=True, timeout=timeout, shell=False)
        out = ((done.stdout or "") + (done.stderr or "")).strip().splitlines()
        return {"exit": done.returncode, "tail": "\n".join(out[-TAIL_LINES:]),
                "seconds": int(time.time() - started)}
    except subprocess.TimeoutExpired:
        return {"exit": None, "tail": "timed out after %ds" % timeout, "seconds": timeout}
    except OSError as exc:
        return {"exit": None, "tail": "could not start: %s" % exc, "seconds": 0}


# -------------------------------------------------------------------- report
def parse_report(text):
    """The VERIFY block: branch, sha, worktree and the team's claim per check."""
    out = {"branch": None, "sha": None, "worktree": None, "claims": {}}
    for line in (text or "").splitlines():
        s = line.strip().lstrip("-*• ").strip()
        m = re.match(r"^(branch|sha|worktree)\s*:\s*`?([^\s`]+)`?", s, re.I)
        if m and out[m.group(1).lower()] is None:
            out[m.group(1).lower()] = m.group(2)
            continue
        c = re.match(r"^(C\d{1,2})\s*:\s*(PASS|FAIL)\b\s*[—:\-]*\s*(.*)$", s, re.I)
        if c:
            out["claims"][c.group(1)] = {"claim": c.group(2).upper(), "evidence": c.group(3)[:300]}
    return out


def _git_head(worktree):
    done = subprocess.run(["git", "-C", worktree, "rev-parse", "HEAD"], capture_output=True,
                          text=True, timeout=30, stdin=subprocess.DEVNULL)
    return done.stdout.strip() if done.returncode == 0 else None


def worktree_problem(report, git_head=None):
    sha, wt = report.get("sha"), report.get("worktree")
    if not sha or not SHA_RE.match(sha):
        return "the report has no 40-character `sha:` line"
    if not wt or not os.path.isabs(wt):
        return "the report has no absolute `worktree:` line"
    real = os.path.realpath(wt)
    if not any(real == r or real.startswith(r + os.sep) for r in allowed_roots()):
        return "worktree %s is not under a team's job or Dabbler directory" % wt
    if not os.path.isdir(real):
        return "worktree %s does not exist" % wt
    head = (git_head or _git_head)(real)
    if head != sha:
        return "worktree HEAD is %s, not the reported %s" % ((head or "unknown")[:12], sha[:12])
    return None


# ----------------------------------------------------------------- the pass
def _root_of(rec, state_store):
    rid = rec.get("root_dispatch_id") or rec["dispatch_id"]
    return state_store.read("conversation_dispatch", rid)


def _verdict(root_checks, results):
    ids = [c["id"] for c in root_checks]
    status = [(results.get(i) or {}).get("status") for i in ids]
    if any(s == "fail" for s in status):
        return "fail"
    if any(s == "error" for s in status):
        return "error"            # Thebes could not run it: not the team's defect, no cycle spent
    if any(s != "pass" for s in status):
        return "needs_judge" if any(s == "pending-judge" for s in status) else "fail"
    return "pass"


def run(dispatch_id, *, state_store=store, runner=None, git_head=None, jira=None,
        dispatcher=None, launcher=None, force=False):
    """Settle one reported dispatch. Idempotent: a dispatch is verified once."""
    rec = state_store.read("conversation_dispatch", dispatch_id)
    if rec is None:
        raise Refused("dispatch-not-found", dispatch_id)
    root = _root_of(rec, state_store)
    if not root or not root.get("checks"):
        return {"status": "no-checks", "dispatch_id": dispatch_id}
    if rec.get("outcome") != "completed":
        return {"status": "not-completed", "dispatch_id": dispatch_id}
    if rec.get("verified_at") and not force:
        return {"status": "already-verified", "dispatch_id": dispatch_id,
                "verdict": (root.get("verification") or {}).get("verdict")}
    with open(rec["result_ref"], encoding="utf-8") as fh:
        report = parse_report(fh.read())
    cycle = rec.get("verify_cycle") or 1
    to_check = rec.get("checks") or root["checks"]
    results = dict((root.get("verification") or {}).get("results") or {})

    problem = worktree_problem(report, git_head)
    for c in to_check:
        claim = report["claims"].get(c["id"]) or {}
        if c["kind"] == "judge":
            results[c["id"]] = {"status": "pending-judge", "cycle": cycle, "by": "judge",
                                "detail": claim.get("evidence") or "no evidence line in the report",
                                "what": c["what"]}
            continue
        if problem:
            results[c["id"]] = {"status": "fail", "cycle": cycle, "by": "thebes",
                                "detail": problem, "what": c["what"]}
            continue
        ran = run_command(c["what"], os.path.realpath(report["worktree"]), runner=runner)
        ok = ran["exit"] == 0
        detail = "exit %s in %ds" % (ran["exit"], ran["seconds"])
        if ran["exit"] is None:                   # refused, timed out, or the tool is missing
            results[c["id"]] = {"status": "error", "cycle": cycle, "by": "thebes",
                                "detail": ran["tail"], "what": c["what"], "tail": ran["tail"]}
            continue
        if ok is False and claim.get("claim") == "PASS":
            detail += " — the report claimed PASS"
        results[c["id"]] = {"status": "pass" if ok else "fail", "cycle": cycle, "by": "thebes",
                            "detail": detail, "what": c["what"],
                            "tail": "" if ok else ran["tail"]}
    return _settle(rec, root, results, cycle, report, state_store=state_store, jira=jira,
                   dispatcher=dispatcher, launcher=launcher)


def _settle(rec, root, results, cycle, report, *, state_store, jira=None, dispatcher=None,
            launcher=None, mark=True):
    verdict = _verdict(root["checks"], results)
    exhausted = verdict == "fail" and cycle >= MAX_CYCLES
    final = "exhausted" if exhausted else ("retry" if verdict == "fail" else verdict)
    if final == "error":
        cycle = max(cycle - 1, 0) or 1        # an infrastructure error spends no cycle
    ver = {"cycle": cycle, "results": results, "verdict": final, "at": state_store.now(),
           "branch": report.get("branch") or (root.get("verification") or {}).get("branch"),
           "sha": report.get("sha") or (root.get("verification") or {}).get("sha")}
    cur = state_store.read("conversation_dispatch", root["dispatch_id"])
    state_store.update("conversation_dispatch", cur["dispatch_id"], cur["revision"],
                       {"verification": ver})
    if mark:
        me = state_store.read("conversation_dispatch", rec["dispatch_id"])
        state_store.update("conversation_dispatch", me["dispatch_id"], me["revision"],
                           {"verified_at": state_store.now()})
    root = state_store.read("conversation_dispatch", root["dispatch_id"])
    out = {"status": "verified", "dispatch_id": rec["dispatch_id"], "verdict": final,
           "cycle": cycle, "results": {k: v["status"] for k, v in results.items()}}
    from agent.execution import jira_sync
    if final == "pass":
        out["jira"] = jira_sync.on_verified(root, ver, state_store=state_store, jira=jira)
    elif final == "retry":
        out["continuation"] = _send_back(root, ver, state_store=state_store,
                                         dispatcher=dispatcher, launcher=launcher)
    elif final == "error":
        from agent.execution import watchdog
        root = state_store.read("conversation_dispatch", root["dispatch_id"])
        why = "; ".join("%s: %s" % (i, r["detail"]) for i, r in results.items()
                        if r["status"] == "error")
        watchdog._alert(root, "review-could-not-run",
                        "Thebes could not run the declared checks for %s (%s). This is not the "
                        "team's defect and nothing was sent back. Fix the cause, then: python3 "
                        "-m agent.execution.verify run %s --force"
                        % (root.get("jira_key") or root["dispatch_id"], why, rec["dispatch_id"]),
                        state_store=state_store)
    elif final == "exhausted":
        out["jira"] = jira_sync.on_exhausted(root, ver, state_store=state_store, jira=jira)
        from agent.execution import watchdog
        failing = ", ".join(i for i, r in results.items() if r["status"] == "fail")
        root = state_store.read("conversation_dispatch", root["dispatch_id"])  # jira note moved it
        watchdog._alert(root, "review-exhausted",
                        "Verification of %s still fails after %d passes (%s). The ticket stays "
                        "in review with the reason written on it; it needs a decision, not "
                        "another retry." % (root.get("jira_key") or root["dispatch_id"], MAX_CYCLES,
                                            failing), state_store=state_store)
    return out


def fix_brief(root, ver):
    lines = ["VERIFICATION FAILED — fix ONLY what failed. Do not redo or restyle anything else.",
             "Thebes re-ran your declared checks on commit %s. Passed checks are not re-run."
             % ((ver.get("sha") or "?")[:12]), ""]
    for cid, r in sorted(ver["results"].items()):
        if r["status"] == "fail":
            lines += ["%s FAILED — %s" % (cid, r["what"]), "  %s" % r["detail"]]
            if r.get("tail"):
                lines += ["  last output:"] + ["    " + t for t in r["tail"].splitlines()[-12:]]
    lines += ["", "This is fix 1 of 1. If it still fails, report `blocked` naming the check — "
              "do not loop.",
              "Report again with the same VERIFY block (branch, sha, worktree, a line per "
              "failed check). Same branch, same worktree."]
    return "\n".join(lines)


def _send_back(root, ver, *, state_store, dispatcher=None, launcher=None):
    from agent.execution import conversation_dispatch as cd
    failing = [c for c in root["checks"]
               if (ver["results"].get(c["id"]) or {}).get("status") == "fail"]
    env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID",)}
    env[cd.CLAUDE_ORIGIN_ENV] = root["origin_thread_id"]
    try:
        out = (dispatcher or cd.dispatch)(
            fix_brief(root, ver), root["target_session_id"], env=env, state_store=state_store,
            detach=True, launcher=launcher, ticket=root.get("jira_key"),
            lane_capability=root.get("jira_capability"), continuation=True,
            root_dispatch_id=root["dispatch_id"], verify_cycle=ver["cycle"] + 1, checks=failing)
        return {"status": "sent-back", "dispatch_id": out.get("dispatch_id"),
                "failing": [c["id"] for c in failing]}
    except Exception as exc:                                  # noqa: BLE001
        from agent.execution import watchdog
        watchdog._alert(root, "review-send-back-failed",
                        "Verification failed but the fix could not be sent back to the team: %s"
                        % exc, state_store=state_store)
        return {"status": "send-back-failed", "error": str(exc)[:300]}


# --------------------------------------------------------------- the judge
def judge_verdict(dispatch_id, passed, failed, *, env=None, state_store=store, jira=None,
                  dispatcher=None, launcher=None):
    """The orchestrator records ONE reviewer pass over the pending `judge` checks."""
    env = os.environ if env is None else env
    from agent.state import teams
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator records a review verdict")
    root = state_store.read("conversation_dispatch", dispatch_id)
    if root is None or not root.get("checks"):
        raise Refused("dispatch-not-found", dispatch_id)
    ver = dict(root.get("verification") or {})
    results = dict(ver.get("results") or {})
    for cid in list(passed) + list(failed):
        if (results.get(cid) or {}).get("status") != "pending-judge":
            raise Refused("check-not-pending", "%s is not waiting for a reviewer" % cid)
    for cid in passed:
        results[cid] = dict(results[cid], status="pass", by="judge")
    for cid, why in failed.items():
        results[cid] = dict(results[cid], status="fail", by="judge", detail=why[:400], tail="")
    if any((results.get(c["id"]) or {}).get("status") == "pending-judge" for c in root["checks"]):
        raise Refused("checks-still-pending", "give a verdict for every pending judge check")
    return _settle(root, root, results, ver.get("cycle") or 1, {}, state_store=state_store,
                   jira=jira, dispatcher=dispatcher, launcher=launcher, mark=False)


def discard(dispatch_id, reason, *, env=None, state_store=store, jira=None):
    """The orchestrator discards a DUPLICATE dispatch: no rework, never integrated, the ticket is
    not moved (the other copy owns it). A failed verdict always means rework; this does not."""
    env = os.environ if env is None else env
    from agent.state import teams
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator discards a dispatch")
    root = state_store.read("conversation_dispatch", dispatch_id)
    if root is None:
        raise Refused("dispatch-not-found", dispatch_id)
    if not (reason or "").strip():
        raise Refused("reason-required", "say why it is discarded")
    ver = dict(root.get("verification") or {}, verdict="discarded", reason=reason.strip()[:300],
               at=state_store.now())
    state_store.update("conversation_dispatch", dispatch_id, root["revision"],
                       {"verification": ver, "integrated_at": "discarded"})
    if root.get("jira_key"):
        try:
            jira = jira or __import__("agent.execution.jira_sync", fromlist=["_client"])._client(
                None, state_store)
            if jira:
                jira.add_comment(root["jira_key"], "Thebes: dispatch %s (team %s) was discarded "
                                 "as a duplicate: %s. Its work is not integrated."
                                 % (dispatch_id, root.get("target_seat_id"), reason.strip()[:200]))
        except Exception:                                    # noqa: BLE001  a comment never blocks
            pass
    return {"status": "discarded", "dispatch_id": dispatch_id}


def pending_judge(root):
    ver = root.get("verification") or {}
    return [dict(r, id=i) for i, r in sorted((ver.get("results") or {}).items())
            if r.get("status") == "pending-judge"]


def _detach_run(dispatch_id):
    log_path = os.path.join(store.RUNTIME, "verify.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED}
    with open(log_path, "a", encoding="utf-8") as log:
        subprocess.Popen([sys.executable, "-m", "agent.execution.verify", "run", dispatch_id],
                         cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("dispatch_id")
    r.add_argument("--force", action="store_true", help="re-run after an infrastructure error")
    v = sub.add_parser("verdict"); v.add_argument("dispatch_id")
    v.add_argument("--pass", dest="passed", action="append", default=[])
    v.add_argument("--fail", dest="failed", action="append", default=[],
                   help='C3:"reason" — repeat per failing check')
    d = sub.add_parser("discard", help="discard a DUPLICATE dispatch: no rework, not integrated")
    d.add_argument("dispatch_id"); d.add_argument("--reason", required=True)
    s = sub.add_parser("status"); s.add_argument("dispatch_id")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "run":
            out = run(ns.dispatch_id, force=ns.force)
        elif ns.cmd == "discard":
            out = discard(ns.dispatch_id, ns.reason)
        elif ns.cmd == "verdict":
            failed = {}
            for item in ns.failed:
                cid, _, why = item.partition(":")
                failed[cid.strip()] = why.strip() or "failed review"
            out = judge_verdict(ns.dispatch_id, ns.passed, failed)
        else:
            rec = store.read("conversation_dispatch", ns.dispatch_id)
            out = (rec or {}).get("verification")
    except Refused as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
