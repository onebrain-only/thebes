#!/usr/bin/env python3
"""Bring the Claude Code settings of this checkout to the shape Thebes expects.

A session does not edit its own settings (the policy hook refuses it), so this is a command
a person runs from a terminal. It is idempotent, backs each file up before the first change
and prints what it changed. The wanted rules are defined here and nowhere else.

    python3 agent/scripts/apply_settings.py           # apply
    python3 agent/scripts/apply_settings.py --check   # report only; exit 1 if anything differs

`.claude/settings.json` (tracked, shared by every session):
  - team branches may be pushed (`staging-<team>`, `staging-ds-<team>`), and Memphis may
    push an integration worktree to `staging`;
  - the retired `alpha-*` rules and any rule holding an absolute home path are removed;
  - a push that names `main` is denied in every repository;
  - the dart-flutter plugin marketplace is declared, so a fresh machine can install it.

`.claude/settings.local.json` (this machine only, never tracked):
  - created from `.claude/settings.local.example.json` when it does not exist;
  - rules that carry a dispatch token, a path under another user's home, a job temp folder
    or another dead path are removed (a token belongs in the environment, never in a rule);
  - the `claude-flow` MCP entry is removed (that server was archived on 2026-11-10);
  - the `autoMode` block is added from the example when it is missing.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHARED = os.path.join(ROOT, ".claude", "settings.json")
LOCAL = os.path.join(ROOT, ".claude", "settings.local.json")
EXAMPLE = os.path.join(ROOT, ".claude", "settings.local.example.json")

ALLOW = [
    "Bash(git push origin staging-*)",
    "Bash(git push -u origin staging-*)",
    "Bash(git -C Dabbler/dabbler-code push origin staging-*)",
    "Bash(git -C Dabbler/dabbler-design-system push origin staging-ds-*)",
    "Bash(git -C * push origin integrate-staging:staging)",
    "Bash(git -C * push origin integrate-staging-ds:staging)",
]
DENY = [
    "Bash(git push*main*)",
    "Bash(git -C * push*main*)",
    "Bash(git -C Dabbler/dabbler-code push*master*)",
    "Bash(git -C Dabbler/dabbler-design-system push*master*)",
]
MARKETPLACES = {"dart-flutter": {"source": {"source": "github", "repo": "flutter/agent-plugins"}}}

# A shared rule is retired when it names the old alpha branches or a home folder.
SHARED_RETIRED = re.compile(r"alpha|/Users/|/home/", re.IGNORECASE)
# A local rule is dead when it holds a token or a path that exists on no other machine.
LOCAL_DEAD = re.compile(
    r"THEBES_DISPATCH_CAPABILITY=|/\.claude/jobs/|/Users/moatazmustapha/|ds-fillof|alpha",
    re.IGNORECASE)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def wanted_shared(settings):
    out = json.loads(json.dumps(settings))
    perms = out.setdefault("permissions", {})
    allow = [r for r in perms.get("allow") or [] if not SHARED_RETIRED.search(r)]
    perms["allow"] = ALLOW + [r for r in allow if r not in ALLOW]
    deny = perms.get("deny") or []
    perms["deny"] = DENY + [r for r in deny if r not in DENY]
    known = out.setdefault("extraKnownMarketplaces", {})
    for name, value in MARKETPLACES.items():
        known.setdefault(name, value)
    return out


def wanted_local(settings, example):
    out = json.loads(json.dumps(settings))
    perms = out.setdefault("permissions", {})
    perms["allow"] = [r for r in perms.get("allow") or [] if not LOCAL_DEAD.search(r)]
    servers = [s for s in out.get("enabledMcpjsonServers") or [] if s != "claude-flow"]
    if "enabledMcpjsonServers" in out:
        out["enabledMcpjsonServers"] = servers
    if "autoMode" not in out and "autoMode" in example:
        out["autoMode"] = example["autoMode"]
    return out


def write(path, settings):
    if os.path.exists(path):
        shutil.copy2(path, "%s.bak-%s" % (path, time.strftime("%Y%m%d%H%M%S")))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def removed(before, after):
    return len((before.get("permissions") or {}).get("allow") or []) - \
        len((after.get("permissions") or {}).get("allow") or [])


def main(argv=None, shared=SHARED, local=LOCAL, example=EXAMPLE):
    check = "--check" in (argv or [])
    differs = False

    before = load(shared)
    after = wanted_shared(before)
    if after != before:
        differs = True
        print("%s .claude/settings.json" % ("WOULD CHANGE" if check else "changed"))
        if not check:
            write(shared, after)
    else:
        print("ok .claude/settings.json")

    template = load(example)
    before = load(local) if os.path.exists(local) else None
    after = wanted_local(before if before is not None else template, template)
    if after != before:
        differs = True
        # Never print a rule: a removed rule may hold a token.
        dropped = removed(before, after) if before is not None else 0
        print("%s .claude/settings.local.json (%s; %d dead rule(s) removed)" % (
            "WOULD CHANGE" if check else "changed",
            "created from the example" if before is None else "cleaned", dropped))
        if not check:
            write(local, after)
    else:
        print("ok .claude/settings.local.json")

    return 1 if (check and differs) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
