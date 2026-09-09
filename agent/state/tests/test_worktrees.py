#!/usr/bin/env python3
"""Isolated Product worktrees and serialized integration.

Every test runs against a SYNTHETIC git repository in a temp directory. Nothing
here touches ~/Desktop/Thebes-Canonical/Dabbler/dabbler-code, and nothing here can
reach a real branch — a suite that proved `main` is protected by trying to write to
the real `main` would be the defect it claims to defend against.

WHAT THIS SUITE DEFENDS

  The 2026-09-09 incident, restated as executable rules. Six seats shared one
  working tree and one index. One seat's staged deletions landed inside another
  seat's commit; the second seat then tried to "restore" them, which would have
  reverted a ticket that had already passed review; and undoing that transiently
  orphaned a third seat's commit.

  The claim under test is NOT "agents will be more careful". It is that the shared
  mutable surface is gone: separate checkout, separate index, separate HEAD, and a
  refusal — not a race — when a seat reaches outside its own tree.

  The second claim is the split that makes parallelism safe: execution is parallel,
  integration is serial, and a conflicting integration fails closed rather than
  guessing a merge.

Stdlib only.
"""
import os
import sys
import shutil
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, state_path      # noqa: E402

sys.path.insert(0, state_path())
import worktrees as wt                                             # noqa: E402


def sh(cwd, *args):
    p = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("git %s -> %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def fresh_repo():
    """A synthetic Product repo: a Canary branch, a protected main, two files."""
    tmp = tempfile.mkdtemp()
    repo = os.path.join(tmp, "product")
    os.makedirs(repo)
    sh(repo, "init", "-q", "-b", "main")
    sh(repo, "config", "user.email", "test@example.invalid")
    sh(repo, "config", "user.name", "test")
    for name in ("alpha.dart", "beta.dart"):
        with open(os.path.join(repo, name), "w") as fh:
            fh.write("// %s\n" % name)
    sh(repo, "add", "-A")
    sh(repo, "commit", "-qm", "baseline")
    sh(repo, "branch", "Canary")
    sh(repo, "checkout", "-q", "Canary")
    return tmp, repo, os.path.join(tmp, "wt")


TMP, REPO, WTROOT = fresh_repo()


def write(path, name, text):
    with open(os.path.join(path, name), "w") as fh:
        fh.write(text)


# ------------------------------------------------------- 1. separate worktrees

section("ISOLATION — two concurrent executors never share a surface")

a = wt.allocate("frontend-5", "KAN-148", repo=REPO, root=WTROOT)
b = wt.allocate("frontend-6", "KAN-156", repo=REPO, root=WTROOT)

ok("[1] two concurrent executors receive DIFFERENT worktrees", a["path"] != b["path"])
ok("[1] both worktree paths exist on disk",
   os.path.isdir(a["path"]) and os.path.isdir(b["path"]))
ok("[1] each executor gets its own branch", a["branch"] != b["branch"])
ok("[1] neither worktree is the canonical checkout",
   os.path.realpath(a["path"]) != os.path.realpath(REPO)
   and os.path.realpath(b["path"]) != os.path.realpath(REPO))
ok("[1] worktree identity is deterministic from (seat, work item)",
   wt.allocate("frontend-5", "KAN-148", repo=REPO, root=WTROOT)["path"] == a["path"])
ok("[1] re-allocating the same identity REUSES rather than creating a second tree",
   wt.allocate("frontend-5", "KAN-148", repo=REPO, root=WTROOT)["reused"] is True)

# The original incident in miniature: A deletes four files, B edits one comment.
for f in ("alpha.dart",):
    os.remove(os.path.join(a["path"], f))
write(b["path"], "beta.dart", "// corrected comment\n")

# ------------------------------------------------------- 2. no leakage

section("NO LEAKAGE — A's changes never appear in B")

ok("[2] A sees only A's change", wt.changed_files("frontend-5", "KAN-148", WTROOT)
   == ["alpha.dart"])
ok("[2] B sees only B's change", wt.changed_files("frontend-6", "KAN-156", WTROOT)
   == ["beta.dart"])
ok("[2] A's deletion is NOT unstaged in B",
   "alpha.dart" not in wt.changed_files("frontend-6", "KAN-156", WTROOT))
ok("[2] B's edit is NOT unstaged in A",
   "beta.dart" not in wt.changed_files("frontend-5", "KAN-148", WTROOT))
ok("[2] the canonical checkout is untouched by either", sh(REPO, "status", "--porcelain") == "")
ok("[2] A's file still exists on disk in B (separate checkout)",
   os.path.exists(os.path.join(b["path"], "alpha.dart")))

# ------------------------------------------------------- 3. cannot stage B's files

section("MUTATION BOUNDARY — a seat may mutate only its own worktree")

raises("[3] A cannot mutate B's worktree",
       lambda: wt.assert_mutation_allowed("frontend-5", "KAN-148",
                                          os.path.join(b["path"], "beta.dart"), WTROOT),
       "cross-worktree-mutation")
raises("[3] B cannot mutate A's worktree",
       lambda: wt.assert_mutation_allowed("frontend-6", "KAN-156",
                                          os.path.join(a["path"], "alpha.dart"), WTROOT),
       "cross-worktree-mutation")
raises("[3] no executor may mutate the canonical integration checkout",
       lambda: wt.assert_mutation_allowed("frontend-5", "KAN-148",
                                          os.path.join(REPO, "alpha.dart"), WTROOT),
       "outside-worktree")
ok("[3] a seat MAY mutate its own worktree",
   wt.assert_mutation_allowed("frontend-5", "KAN-148",
                              os.path.join(a["path"], "alpha.dart"), WTROOT) is True)
raises("[3] the refusal names the other seat, so the report is actionable",
       lambda: wt.assert_mutation_allowed("frontend-5", "KAN-148",
                                          os.path.join(b["path"], "beta.dart"), WTROOT),
       "frontend-6")

# ------------------------------------------------------- 4. reset cannot cross

section("HISTORY — one seat cannot rewrite another's branch or tree")

sh(a["path"], "add", "-A")
sh(a["path"], "commit", "-qm", "KAN-148: delete alpha")
a_head = sh(a["path"], "rev-parse", "HEAD")
b_before = sh(b["path"], "rev-parse", "HEAD")
sh(a["path"], "reset", "--hard", "HEAD~1")

ok("[4] A's reset did not move B's HEAD", sh(b["path"], "rev-parse", "HEAD") == b_before)
ok("[4] A's reset did not touch B's working tree",
   wt.changed_files("frontend-6", "KAN-156", WTROOT) == ["beta.dart"])
ok("[4] git itself refuses to check out a branch already held by another worktree",
   subprocess.run(["git", "-C", a["path"], "checkout", b["branch"]],
                  capture_output=True).returncode != 0)
sh(a["path"], "reset", "--hard", a_head)
ok("[4] A can still rewrite its OWN history freely",
   sh(a["path"], "rev-parse", "HEAD") == a_head)

# ------------------------------------------------------- 5. commit attribution

section("ATTRIBUTION — a task commit holds only that task's changes")

write(b["path"], "alpha.dart", "// B touched a file its ticket never named\n")
raises("[5] commit REFUSES when the tree carries undeclared changes",
       lambda: wt.commit("frontend-6", "KAN-156", "KAN-156: comment", ["beta.dart"],
                         root=WTROOT),
       "unrelated-changes")
raises("[5] the refusal names the undeclared path",
       lambda: wt.assert_attribution("frontend-6", "KAN-156", expected=["beta.dart"],
                                     root=WTROOT),
       "alpha.dart")
sh(b["path"], "checkout", "--", "alpha.dart")
b_sha = wt.commit("frontend-6", "KAN-156", "KAN-156: correct comment", ["beta.dart"],
                  root=WTROOT)
touched = sh(REPO, "show", "--name-only", "--format=", b_sha).split()
ok("[5] the resulting commit contains ONLY the declared path", touched == ["beta.dart"])
ok("[5] and does NOT contain the other seat's deletion — the original defect",
   "alpha.dart" not in touched)

# ------------------------------------------------------- 6/7/8. integration

section("INTEGRATION — serialized, fails closed, never main")

canary_head = sh(REPO, "rev-parse", "Canary")
r1 = wt.integrate("frontend-6", "KAN-156", b_sha, canary_head, repo=REPO, root=WTROOT)
ok("[6] a clean task commit integrates onto Canary", r1["result"] == "integrated")
ok("[6] Canary advanced", sh(REPO, "rev-parse", "Canary") != canary_head)
ok("[6] integration carried only that task's files", r1["files"] == ["beta.dart"])

raises("[6] integration is serialized by expected-head: a stale caller is REFUSED",
       lambda: wt.integrate("frontend-5", "KAN-148", a_head, canary_head,
                            repo=REPO, root=WTROOT),
       "stale-integration")

now_head = sh(REPO, "rev-parse", "Canary")
r2 = wt.integrate("frontend-5", "KAN-148", a_head, now_head, repo=REPO, root=WTROOT)
ok("[6] the second task integrates once it names the CURRENT head",
   r2["result"] == "integrated")
ok("[6] re-integrating an already-present commit is a no-op, not a duplicate",
   wt.integrate("frontend-5", "KAN-148", a_head, sh(REPO, "rev-parse", "Canary"),
                repo=REPO, root=WTROOT)["result"] == "already-present")

# A genuine conflict: two seats change the same line from the same base.
c = wt.allocate("frontend-1", "KAN-900", repo=REPO, root=WTROOT)
d = wt.allocate("frontend-2", "KAN-901", repo=REPO, root=WTROOT)
write(c["path"], "beta.dart", "// c wins\n")
write(d["path"], "beta.dart", "// d wins\n")
c_sha = wt.commit("frontend-1", "KAN-900", "KAN-900", ["beta.dart"], root=WTROOT)
d_sha = wt.commit("frontend-2", "KAN-901", "KAN-901", ["beta.dart"], root=WTROOT)
wt.integrate("frontend-1", "KAN-900", c_sha, sh(REPO, "rev-parse", "Canary"),
             repo=REPO, root=WTROOT)
head_before_conflict = sh(REPO, "rev-parse", "Canary")
raises("[7] a conflicting integration FAILS CLOSED and names the paths",
       lambda: wt.integrate("frontend-2", "KAN-901", d_sha, head_before_conflict,
                            repo=REPO, root=WTROOT),
       "integration-conflict")
ok("[7] Canary is unchanged after the failed integration",
   sh(REPO, "rev-parse", "Canary") == head_before_conflict)
ok("[7] no cherry-pick is left in progress", sh(REPO, "status", "--porcelain") == "")

raises("[8] main is never an integration target",
       lambda: wt.integrate("frontend-1", "KAN-900", c_sha,
                            sh(REPO, "rev-parse", "Canary"), repo=REPO, root=WTROOT,
                            integration_branch="main"),
       "protected-branch")
raises("[8] main is never an allocation base",
       lambda: wt.allocate("frontend-3", "KAN-902", repo=REPO, root=WTROOT, base="main"),
       "protected-branch")
ok("[8] main never moved", sh(REPO, "rev-parse", "main")
   == sh(REPO, "rev-list", "--max-parents=0", "main"))

# A failing gate must roll the integration back rather than leave it half-landed.
e = wt.allocate("frontend-4", "KAN-903", repo=REPO, root=WTROOT)
write(e["path"], "gamma.dart", "// new\n")
e_sha = wt.commit("frontend-4", "KAN-903", "KAN-903", ["gamma.dart"], root=WTROOT)
pre_gate = sh(REPO, "rev-parse", "Canary")
raises("[7] a failing gate rolls the integration back",
       lambda: wt.integrate("frontend-4", "KAN-903", e_sha, pre_gate, repo=REPO,
                            root=WTROOT, gates=[("fake-ci", ["false"])]),
       "gate-failed")
ok("[7] Canary is back where it started after a failed gate",
   sh(REPO, "rev-parse", "Canary") == pre_gate)
ok("[7] a PASSING gate lets the integration stand",
   wt.integrate("frontend-4", "KAN-903", e_sha, pre_gate, repo=REPO, root=WTROOT,
                gates=[("fake-ci", ["true"])])["result"] == "integrated")

# ------------------------------------------------------- 9. lifecycle coherence

section("LIFECYCLE — same seat, new task")

n1 = wt.allocate("frontend-5", "KAN-910", repo=REPO, root=WTROOT)
ok("[9] the same seat on a NEW task gets a different worktree", n1["path"] != a["path"])
ok("[9] and a different branch", n1["branch"] != a["branch"])
ok("[9] its base is the integration branch, not the seat's previous task",
   n1["base"] == "Canary")
ok("[9] the seat's earlier worktree is untouched", os.path.isdir(a["path"]))

# ------------------------------------------------------- 10. cleanup

section("CLEANUP — releasing one worktree cannot reach another")

write(n1["path"], "beta.dart", "// uncommitted\n")
raises("[10] release REFUSES a worktree with uncommitted work",
       lambda: wt.release("frontend-5", "KAN-910", repo=REPO, root=WTROOT),
       "dirty-worktree")
sh(n1["path"], "checkout", "--", "beta.dart")
rel = wt.release("frontend-5", "KAN-910", repo=REPO, root=WTROOT)
ok("[10] a clean worktree releases", rel["result"] == "released")
ok("[10] releasing it did NOT remove another active worktree", os.path.isdir(b["path"]))
ok("[10] nor the other seat's", os.path.isdir(a["path"]))
ok("[10] nor the canonical checkout", os.path.isdir(REPO))
ok("[10] the task branch is kept by default — unintegrated history is not discarded",
   rel["branch_kept"] == wt.branch_name("frontend-5", "KAN-910"))
ok("[10] releasing an unallocated identity is a no-op, not a deletion",
   wt.release("frontend-7", "KAN-999", repo=REPO, root=WTROOT)["result"]
   == "not-allocated")
# Craft the one identity whose computed path IS the canonical checkout, and prove
# the explicit guard — not luck — is what refuses it.
_evil_root = os.path.dirname(os.path.dirname(REPO))
_evil_seat = os.path.basename(os.path.dirname(REPO))
ok("[10] the crafted identity really does resolve to the canonical checkout",
   os.path.realpath(wt.worktree_path(_evil_seat, "product", _evil_root))
   == os.path.realpath(REPO))
raises("[10] and releasing it is REFUSED by an explicit guard",
       lambda: wt.release(_evil_seat, "product", repo=REPO, root=_evil_root),
       "canonical integration checkout")
ok("[10] the canonical checkout still exists",
   os.path.isdir(REPO) and os.path.isdir(os.path.join(REPO, ".git")))

# ------------------------------------------------------- 11. no shared index

section("NO SHARED-INDEX PATH REMAINS")

reg = {w["path"]: w.get("branch") for w in wt.list_worktrees(REPO)}
execs = [p for p in reg if wt.owner_of(p, root=WTROOT)]
ok("[11] every executor worktree has its own path", len(execs) == len(set(execs)))
ok("[11] every executor worktree has its own branch",
   len({reg[p] for p in execs}) == len(execs))
ok("[11] no executor worktree shares the canonical checkout's path",
   os.path.realpath(REPO) not in execs)
ok("[11] each worktree has its own index file",
   len({os.path.realpath(sh(p, "rev-parse", "--git-path", "index")) for p in execs})
   == len(execs))
ok("[11] the canonical checkout's index is none of theirs",
   os.path.realpath(sh(REPO, "rev-parse", "--git-path", "index"))
   not in {os.path.realpath(sh(p, "rev-parse", "--git-path", "index")) for p in execs})
raises("[11] worktree identity refuses a missing seat or work item",
       lambda: wt.worktree_path("", "KAN-1"),
       "needs both a seat and a work item")

# ------------------------------------------------------- 12. plan vs integrate

section("PARALLEL PLAN, SERIAL INTEGRATION")

sys.path.insert(0, state_path())
import capacity                                                     # noqa: E402

ok("[12] safe_parallel_plan is a PLANNER and holds no integration authority",
   "integrate" not in capacity.__dict__ and hasattr(capacity, "safe_parallel_plan"))
ok("[12] integration authority lives only in the worktree layer",
   hasattr(wt, "integrate"))
ok("[12] multiple executors may hold worktrees simultaneously",
   len([p for p in wt.list_worktrees(REPO) if wt.owner_of(p["path"], root=WTROOT)]) >= 2)
ok("[12] but integration takes an exclusive lock",
   wt._IntegrationLock(REPO).p.endswith("thebes-integration.lock"))

# --------------------------------------------- 13. re-attribution adoption

section("ADOPTION — re-attribute unpublished history, never change content")

sh(REPO, "checkout", "-q", "Canary")
sh(REPO, "update-ref", "refs/remotes/origin/Canary", sh(REPO, "rev-list", "--max-parents=0", "Canary"))
_head = sh(REPO, "rev-parse", "Canary")
# A rebuild that reaches the SAME tree by different commits.
sh(REPO, "branch", "-f", "rebuilt", _head)
raises("[13] adoption refuses a stale expected head",
       lambda: wt.adopt_reconstructed("rebuilt", "0000000", repo=REPO),
       "stale-adoption")
r = wt.adopt_reconstructed("rebuilt", _head, repo=REPO)
ok("[13] an identical-tree adoption is allowed", r["result"] == "adopted")
ok("[13] and preserves the tree exactly",
   r["tree"] == sh(REPO, "rev-parse", "Canary^{tree}"))

# A rebuild whose tree genuinely differs must be refused.
f = wt.allocate("frontend-8", "KAN-950", repo=REPO, root=WTROOT)
write(f["path"], "beta.dart", "// smuggled content\n")
f_sha = wt.commit("frontend-8", "KAN-950", "KAN-950", ["beta.dart"], root=WTROOT)
sh(REPO, "branch", "-f", "smuggle", f_sha)
raises("[13] adoption REFUSES a reconstruction that changes content",
       lambda: wt.adopt_reconstructed("smuggle", sh(REPO, "rev-parse", "Canary"),
                                      repo=REPO),
       "content-change-refused")
ok("[13] Canary did not move on the refusal",
   sh(REPO, "rev-parse", "Canary") == r["new_head"])
raises("[13] adoption never targets main",
       lambda: wt.adopt_reconstructed("rebuilt", _head, repo=REPO,
                                      branch="main"),
       "protected-branch")

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(summary())
