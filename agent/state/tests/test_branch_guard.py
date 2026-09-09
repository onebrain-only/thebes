#!/usr/bin/env python3
"""Repository-aware branch protection.

Synthetic repositories in a temp directory, each given the real `origin` URL of the
repository it stands for. Nothing here touches a real remote and nothing here
pushes.

WHAT THIS SUITE DEFENDS

  `git push origin main` is BYTE-IDENTICAL in the Product repository and in the
  canonical Thebes repository. In the first it ships to real users at
  app.dabbler.pro; in the second it is the ordinary release. Until this guard the
  distinction lived only in prose, so nothing mechanical could tell them apart — and
  an authorised Thebes release push was refused for exactly that reason.

  The guard resolves the REPOSITORY, not the command text, because a guard that
  reads the string alone is defeated by the first `cd` anybody writes.

  And it only ever DENIES. `PASS` is "no opinion, the permission layer decides" —
  never "the guard says yes". A file that could grant itself access is the shape of
  the bug a guard exists to prevent.

Stdlib only.
"""
import os
import sys
import shutil
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, section, summary, state_path                # noqa: E402

sys.path.insert(0, state_path())
import branch_guard as bg                                            # noqa: E402


def sh(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, text=True)


def repo(tmp, name, origin, branches=("main",)):
    p = os.path.join(tmp, name)
    os.makedirs(p)
    sh(p, "init", "-q", "-b", "main")
    sh(p, "config", "user.email", "t@t.invalid")
    sh(p, "config", "user.name", "t")
    sh(p, "remote", "add", "origin", origin)
    with open(os.path.join(p, "f.txt"), "w") as fh:
        fh.write("x\n")
    sh(p, "add", "-A")
    sh(p, "commit", "-qm", "base")
    for b in branches:
        if b != "main":
            sh(p, "branch", b)
    return p


TMP = tempfile.mkdtemp()
PRODUCT = repo(TMP, "webapp", "https://github.com/dabblersport/webapp.git",
               ("main", "Canary"))
THEBES = repo(TMP, "thebes", "https://github.com/onebrain-only/thebes.git")
OTHER = repo(TMP, "other", "https://github.com/someone/unrelated.git")
NOREMOTE = repo(TMP, "bare", "https://github.com/x/y.git")
sh(NOREMOTE, "remote", "remove", "origin")

section("REPOSITORY IDENTITY — from the remote, never the directory name")

ok("product repo is identified", bg.classify_repo(PRODUCT) == "product")
ok("thebes repo is identified", bg.classify_repo(THEBES) == "thebes")
ok("an unrelated repo is neither", bg.classify_repo(OTHER) == "other")
ok("a repo with no origin is neither", bg.classify_repo(NOREMOTE) == "other")
ok("a non-repository directory is neither", bg.classify_repo(TMP) == "other")
ok("identity survives an SSH-form remote",
   bg.classify_repo(PRODUCT) == "product")

section("PRODUCT MAIN — REFUSED")

v, r = bg.decide("git push origin main", PRODUCT)
ok("[T1] Product main push is REFUSED", v == bg.DENY)
ok("[T1] the refusal explains the consequence, not just the rule",
   "app.dabbler.pro" in r)
ok("[T2] Product master is refused too",
   bg.decide("git push origin master", PRODUCT)[0] == bg.DENY)
ok("[T3] a forced Product main push is refused",
   bg.decide("git push --force origin main", PRODUCT)[0] == bg.DENY)
ok("[T4] HEAD:main refspec form is refused",
   bg.decide("git push origin HEAD:main", PRODUCT)[0] == bg.DENY)
ok("[T5] refs/heads/main form is refused",
   bg.decide("git push origin HEAD:refs/heads/main", PRODUCT)[0] == bg.DENY)
ok("[T6] `git -C <product> push origin main` from elsewhere is refused",
   bg.decide("git -C %s push origin main" % PRODUCT, THEBES)[0] == bg.DENY)
ok("[T7] a leading `cd` does not evade the guard",
   bg.decide("cd %s && git push origin main" % PRODUCT, THEBES)[0] == bg.DENY)
sh(PRODUCT, "checkout", "-q", "main")
ok("[T8] a BARE `git push` on Product main is refused",
   bg.decide("git push", PRODUCT)[0] == bg.DENY)

section("PRODUCT CANARY — the ordinary integration target, unaffected")

v, r = bg.decide("git push origin Canary", PRODUCT)
ok("[T9] Product Canary push is not refused", v == bg.PASS)
ok("[T9] and is named as the integration target", "integration target" in r)
sh(PRODUCT, "checkout", "-q", "Canary")
ok("[T10] a bare push on Canary is not refused",
   bg.decide("git push", PRODUCT)[0] == bg.PASS)
sh(PRODUCT, "checkout", "-q", "main")

section("THEBES MAIN — not refused, and NOT granted by this guard")

v, r = bg.decide("git push origin main", THEBES)
ok("[T11] Thebes main push is not refused by the guard", v == bg.PASS)
ok("[T12] the guard explicitly does NOT claim to authorise it",
   "not the guard granting access" in r)
ok("[T13] and says why the branch differs — release, not production deploy",
   "release branch" in r and "production deploy" in r)
ok("[T14] the guard has exactly two verdicts; there is no ALLOW",
   not hasattr(bg, "ALLOW") and {bg.DENY, bg.PASS} == {"DENY", "PASS"})

section("EVERY OTHER REPOSITORY — policy unchanged")

v, r = bg.decide("git push origin main", OTHER)
ok("[T15] an arbitrary repo's main is not decided by this guard", v == bg.PASS)
ok("[T15] and it says so rather than implying approval",
   "repository policy applies unchanged" in r)
ok("[T16] Product protection is not weakened by the unrecognised case",
   bg.decide("git push origin main", PRODUCT)[0] == bg.DENY)

section("NON-PUSH COMMANDS ARE NOT THE GUARD'S BUSINESS")

for cmd in ("git status", "git log --oneline -5", "git fetch origin",
            "git commit -m 'push origin main'", "ls", "git pull origin main"):
    ok("[T17] no opinion on %r" % cmd[:28], bg.decide(cmd, PRODUCT)[0] == bg.PASS)
ok("[T17] a commit MESSAGE mentioning a push is not a push",
   bg.push_targets("git commit -m 'push origin main'") == [])

section("HOOK CONTRACT")

ok("[T18] a DENY maps to hook exit code 2 in main()",
   "return 2" in open(os.path.join(state_path(), "branch_guard.py")).read())
ok("[T19] the guard never shells out to anything but git",
   "subprocess.run([\"git\"]" in open(
       os.path.join(state_path(), "branch_guard.py")).read())
ok("[T20] malformed input does not raise",
   bg.decide("git push 'unclosed", PRODUCT)[0] in (bg.DENY, bg.PASS))

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(summary())
