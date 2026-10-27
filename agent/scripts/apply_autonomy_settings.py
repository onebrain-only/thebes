#!/usr/bin/env python3
"""One-time CEO step (autonomy constitution, D-043, 2026-10-27).

Registers the policy hook on PermissionRequest in the project's .claude/settings.json, so a
permission prompt in any team or orchestrator session is answered allow/deny by code and
never reaches the CEO's phone. A session may not edit its own settings, which is why this is
the one command the CEO runs himself. Idempotent; backs the file up first and verifies.

    python3 agent/scripts/apply_autonomy_settings.py
"""
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS = os.path.join(ROOT, ".claude", "settings.json")
SOURCE = os.path.join(ROOT, "agent", "state", "registry", "team-settings.json")


def wanted():
    with open(SOURCE, encoding="utf-8") as fh:
        return json.load(fh)["hooks"]["PermissionRequest"][0]


def has_hook(settings, entry):
    cmd = entry["hooks"][0]["command"]
    return any(h.get("command") == cmd
               for e in (settings.get("hooks") or {}).get("PermissionRequest") or []
               for h in e.get("hooks") or [])


def main(path=SETTINGS):
    with open(path, encoding="utf-8") as fh:
        settings = json.load(fh)
    entry = wanted()
    if has_hook(settings, entry):
        print("OK — already registered; nothing to do.")
        return 0
    backup = "%s.bak-%s" % (path, time.strftime("%Y%m%d%H%M%S"))
    shutil.copy2(path, backup)
    settings.setdefault("hooks", {}).setdefault("PermissionRequest", []).append(entry)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    with open(path, encoding="utf-8") as fh:
        if not has_hook(json.load(fh), entry):
            shutil.copy2(backup, path)
            print("FAILED — restored the backup.")
            return 1
    print("OK — registered. Backup: %s" % os.path.relpath(backup, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
