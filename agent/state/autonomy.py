"""The autonomy constitution (CEO 2026-10-27): who decides what, in code.

`agent/state/registry/autonomy.json` is the single source. Only money, merging into
`main` and sending outside the company may reach the CEO, and only when a report
actually ASKS for that act. Every hook, gate and brief reads it from here.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "agent", "state", "registry", "autonomy.json")
SENTENCE_RE = re.compile(r"(?<=[.!?؟\n])\s+|\n+")


def load(path=PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _compile(p):
    return re.compile(p[3:] if p.startswith("re:") else r"\b%s\b" % re.escape(p), re.I)


def _negated(sentence, start, negations):
    """A negation word in the few words before the match ("nothing to main", "no spend")."""
    before = sentence[:start].lower()
    words = re.findall(r"[\w'’]+", before)[-5:]
    tail = " ".join(words)
    for n in negations:
        if n == "n't":
            if re.search(r"n['’]t\b", tail):
                return True
        elif n in words:
            return True
    return False


def ceo_hit(text, cfg=None):
    """The CEO category this text ASKS for, or None.

    A sentence counts only when it matches a category pattern, is not negated before the
    match, and carries a request cue (approve, permission, go-ahead, may I, موافق ...).
    "nothing to main", "an error spends no fix cycle" and "maintain" never escalate."""
    cfg = cfg or load()
    ceo = cfg["ceo_only"]
    cues = [c.lower() for c in ceo.get("request_cues") or []]
    negs = [n.lower() for n in ceo.get("negations") or []]
    for sentence in SENTENCE_RE.split(text or ""):
        low = sentence.lower()
        if not any(c in low for c in cues):
            continue
        for cat, spec in ceo["categories"].items():
            for p in spec["patterns"]:
                m = _compile(p).search(sentence)
                if m and not _negated(sentence, m.start(), negs):
                    return cat
    return None


def is_ops_seat(seat, cfg=None):
    cfg = cfg or load()
    return (seat or "").lower() in [s.lower() for s in cfg.get("ops_seats") or []]


def never_rule(rule_id, cfg=None):
    cfg = cfg or load()
    for r in cfg["never"]["rules"]:
        if r["id"] == rule_id:
            return r
    return None


def repeat_guard(cfg=None):
    return (cfg or load())["repeat_guard"]
