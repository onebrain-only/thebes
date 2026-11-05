#!/usr/bin/env python3
"""The gate between the orchestrator and the CEO: he hears a thing once, not every wake.

Live 2026-11-05: the same "alert came back, nothing for you" text reached the CEO again and
again, once per 5-minute wake, for hours while he was away. Wakes are cheap and frequent;
a message to the CEO is not. Before any CEO-facing text that is not a direct reply to him:

    python3 -m agent.execution.ceo_notice check <kind> <key> --text-file f.txt

prints `SEND` (and records it) or `SKIP <reason>`. Only three kinds are ever sent:

* `action`  - something only he can do (money, main, outside sending). Same key: once per 12 h.
* `update`  - a team finished a task. Same key (ticket + outcome): once, ever.
* `answer`  - not gated; a direct reply to him is never held here.

Anything else (`status`, `nothing`, `again`) is SKIPPED: say nothing and end the turn.
Identical text is also skipped inside the window, whatever kind or key it came under.
"""
import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "agent", "state", "runtime", "ceo-notices.json")

ACTION_REPEAT_SECONDS = 12 * 3600
TEXT_REPEAT_SECONDS = 12 * 3600
SENDABLE = ("action", "update")
KEEP_SECONDS = 7 * 86400


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"keys": {}, "texts": {}}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def decide(kind, key, text="", *, path=None, now=None):
    """("SEND", "") and the send is recorded, or ("SKIP", reason)."""
    path = path or LEDGER
    now = time.time() if now is None else now
    if kind == "answer":
        return "SEND", ""
    if kind not in SENDABLE:
        return "SKIP", "kind %r is not for the CEO: say nothing and end the turn" % kind
    data = _load(path)
    data["keys"] = {k: t for k, t in data.get("keys", {}).items() if now - t < KEEP_SECONDS}
    data["texts"] = {k: t for k, t in data.get("texts", {}).items() if now - t < KEEP_SECONDS}
    ident = "%s:%s" % (kind, key)
    last = data["keys"].get(ident)
    if last is not None and (kind == "update" or now - last < ACTION_REPEAT_SECONDS):
        return "SKIP", "already told him about %s" % ident
    digest = hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]
    seen = data["texts"].get(digest)
    if text.strip() and seen is not None and now - seen < TEXT_REPEAT_SECONDS:
        return "SKIP", "identical text was sent in the last 12 h"
    data["keys"][ident] = now
    if text.strip():
        data["texts"][digest] = now
    _save(path, data)
    return "SEND", ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("kind")
    c.add_argument("key")
    c.add_argument("--text-file")
    args = ap.parse_args(argv)
    text = open(args.text_file, encoding="utf-8").read() if args.text_file else ""
    verdict, why = decide(args.kind, args.key, text)
    print(verdict + (" " + why if why else ""))
    return 0 if verdict == "SEND" else 1


if __name__ == "__main__":
    sys.exit(main())
