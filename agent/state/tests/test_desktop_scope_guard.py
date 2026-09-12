"""Regression coverage for the canonical Desktop checkout guard."""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, section, summary, repo_root

GUARD = os.path.join(repo_root(), "agent", "scripts", "desktop-scope-guard.sh")


def verdict(command, cwd=None):
    payload = json.dumps({"tool_input": {"command": command, "cwd": cwd}})
    return subprocess.run([GUARD], input=payload, text=True, capture_output=True)


section("DESKTOP SINGLE-ROOT GUARD")
ok("ordinary commands receive no opinion", verdict("git status").returncode == 0)
ok("clone to another Desktop directory is refused",
   verdict("git clone x ~/Desktop/Unauthorized").returncode == 2)
ok("canonical name in clone URL cannot bypass destination check",
   verdict("git clone https://example.com/Thebes-Canonical.git ~/Desktop/Unauthorized").returncode == 2)
ok("mixed mkdir destinations cannot hide an unauthorized path",
   verdict("mkdir ~/Desktop/Unauthorized ~/Desktop/Thebes-Canonical/allowed").returncode == 2)
ok("relative mkdir after cd Desktop is refused",
   verdict("cd ~/Desktop && mkdir Unauthorized").returncode == 2)
ok("relative clone through git -C Desktop is refused",
   verdict("git -C ~/Desktop clone x Unauthorized").returncode == 2)
ok("Bash tool cwd is authoritative for relative destinations",
   verdict("mkdir Unauthorized", os.path.expanduser("~/Desktop")).returncode == 2)
ok("directory creation inside canonical checkout is unaffected",
   verdict("mkdir ~/Desktop/Thebes-Canonical/.claude/worktrees/test").returncode == 0)

sys.exit(summary())
