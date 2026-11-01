"""CEO orders, by code (D-044): what may be created or merged is the CEO's, and every act says why.

Three append-only records, local to this workspace (runtime is gitignored):

    ceo-messages.jsonl   every message the CEO typed to the orchestrator, verbatim. Written by the
                         UserPromptSubmit hook (agent/scripts/ceo_prompt_hook.py), i.e. by the
                         harness, never by the model, so a model cannot invent an order.
    order-grants.json    an order the orchestrator lifted from one of those messages: what it
                         allows (create | merge-alpha), the CEO's exact words, and how much is left.
    action-ledger.jsonl  one line per act that changes the board or Alpha: who, what, which
                         ticket, and the order or the rule that allowed it.

A grant is accepted only when its quote is a literal part of a CEO message from the last
MESSAGE_WINDOW. Creating a Jira issue (agent/scripts/order_gate.py, intake.create) and merging
into Alpha (integrate.dispatch_for, a direct push) need an open grant; nothing else does.

    python3 -m agent.execution.orders grant --what create --quote "<CEO words>" [--count 3]
    python3 -m agent.execution.orders grant --what merge-alpha --quote "<CEO words>" --keys KAN-1,KAN-2
    python3 -m agent.execution.orders grant --what merge-alpha --quote "<CEO words>" --keys all-reviewed
    python3 -m agent.execution.orders open | log [--last 30] | messages [--last 10]
"""
import argparse
import calendar
import hashlib
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                        # noqa: E402

WHATS = ("create", "merge-alpha")
ALL_REVIEWED = "all-reviewed"
MESSAGE_WINDOW = 24 * 3600
GRANT_TTL = 2 * 3600
MIN_QUOTE = 8
MAX_COUNT = 20
KEY = re.compile(r"^KAN-\d+$")
# A user turn that did not come from the CEO's keyboard: envelopes, wakes, task notifications,
# messages from other sessions. Never an order.
NOT_CEO = re.compile(r"^\s*(THEBES_|<|\[|Another Claude session|Thebes restarted|Caveat:)", re.I)
FILES = {"messages": "ceo-messages.jsonl", "grants": "order-grants.json",
         "ledger": "action-ledger.jsonl"}


class OrderRefused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def path(name, state_store=store):
    return os.path.join(state_store.RUNTIME, FILES[name])


def _epoch(stamp):
    try:
        return calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


def _stamp(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _append(name, rec, state_store):
    os.makedirs(state_store.RUNTIME, exist_ok=True)
    with open(path(name, state_store), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _jsonl(name, state_store):
    try:
        with open(path(name, state_store), encoding="utf-8") as fh:
            out = []
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
            return out
    except FileNotFoundError:
        return []


def _norm(text):
    return " ".join((text or "").split())


# ------------------------------------------------------------------ CEO messages
def is_ceo_text(text):
    return bool(_norm(text)) and not NOT_CEO.match(text or "")


def retired_orchestrator(session_id, state_store=store):
    """The live orchestrator's session id when `session_id` is one it rotated away from, else None.
    The CEO can still type into a retired session; it has no gate and no fact block of its own."""
    if not session_id:
        return None
    rec = state_store.active_role_session("orchestrator") or {}
    if session_id in (rec.get("previous_session_ids") or []):
        return rec.get("session_id")
    return None


def record_message(session_id, text, *, state_store=store, now=None, retired=False):
    """Keep one CEO message verbatim. Returns its id, or None for a turn that is not the CEO's.
    `retired`: typed into a retired orchestrator session; the live one must still act on it."""
    if not is_ceo_text(text):
        return None
    now = now or time.time()
    mid = "msg-%s-%s" % (time.strftime("%Y%m%d%H%M%S", time.gmtime(now)),
                         hashlib.sha256(text.encode("utf-8")).hexdigest()[:8])
    rec = {"id": mid, "at": _stamp(now), "sid": session_id, "text": text}
    if retired:
        rec["retired_session"] = True
    _append("messages", rec, state_store)
    return mid


def messages(*, state_store=store, since=None, now=None):
    now = now or time.time()
    since = now - MESSAGE_WINDOW if since is None else since
    return [m for m in _jsonl("messages", state_store) if _epoch(m.get("at")) >= since]


def find_quote(quote, *, state_store=store, now=None):
    """The newest CEO message (in the window) that literally contains the quote, or None."""
    q = _norm(quote)
    if len(q) < MIN_QUOTE:
        return None
    for m in reversed(messages(state_store=state_store, now=now)):
        if q in _norm(m.get("text")):
            return m
    return None


# ------------------------------------------------------------------ grants
def _read_grants(state_store):
    try:
        with open(path("grants", state_store), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return {}


def _write_grants(grants, state_store):
    os.makedirs(state_store.RUNTIME, exist_ok=True)
    tmp = path("grants", state_store) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(grants, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path("grants", state_store))


def _live(g, now):
    if _epoch(g.get("expires_at")) <= now:
        return False
    if g["what"] == "create":
        return (g.get("remaining") or 0) > 0
    return g.get("keys") == ALL_REVIEWED or bool(g.get("keys"))


def grant(what, quote, *, keys=None, count=1, by="orchestrator", state_store=store, now=None):
    """Lift one order from a CEO message. Raises OrderRefused when the words are not the CEO's."""
    now = now or time.time()
    if what not in WHATS:
        raise OrderRefused("bad-what", "what must be one of %s" % ", ".join(WHATS))
    msg = find_quote(quote, state_store=state_store, now=now)
    if msg is None:
        raise OrderRefused("no-such-ceo-order",
                           "no CEO message in the last 24h contains these words (at least %d "
                           "characters, copied exactly). Nothing the CEO did not type is an order; "
                           "if he did not order it, do not do it." % MIN_QUOTE)
    rec = {"what": what, "quote": _norm(quote)[:500], "message_ref": msg["id"],
           "message_at": msg["at"], "by": by, "created_at": _stamp(now),
           "expires_at": _stamp(now + GRANT_TTL)}
    if what == "create":
        if not 1 <= int(count) <= MAX_COUNT:
            raise OrderRefused("bad-count", "count is 1..%d" % MAX_COUNT)
        rec["remaining"] = rec["count"] = int(count)
    else:
        if keys == ALL_REVIEWED or keys == [ALL_REVIEWED]:
            rec["keys"] = ALL_REVIEWED
        else:
            ks = sorted({k.strip().upper() for k in (keys or []) if k.strip()})
            bad = [k for k in ks if not KEY.match(k)]
            if not ks or bad:
                raise OrderRefused("bad-keys", "merge-alpha needs --keys KAN-1,KAN-2 or %s"
                                   % ALL_REVIEWED)
            rec["keys"] = ks
    with store._Lock("orders"):
        grants = _read_grants(state_store)
        gid = "grant-%s-%s" % (time.strftime("%Y%m%d%H%M%S", time.gmtime(now)),
                               hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:6])
        rec["id"] = gid
        grants[gid] = rec
        _write_grants(grants, state_store)
    log("grant", by, keys=rec.get("keys") if what != "create" else None, order_ref=gid,
        detail="%s: %s" % (what, rec["quote"][:160]), state_store=state_store, now=now)
    return rec


def open_grants(what=None, *, state_store=store, now=None):
    now = now or time.time()
    return [g for g in _read_grants(state_store).values()
            if (what is None or g["what"] == what) and _live(g, now)]


def covering(what, key=None, *, state_store=store, now=None):
    """An open grant that allows this act (for merge-alpha, this key), without consuming it."""
    for g in sorted(open_grants(what, state_store=state_store, now=now),
                    key=lambda g: g["created_at"]):
        if what == "create" or key is None or g["keys"] == ALL_REVIEWED or key in g["keys"]:
            return g
    return None


def consume(what, key=None, *, state_store=store, now=None):
    """Use one unit of an open grant. Returns the grant (as it was), or None when none covers it."""
    now = now or time.time()
    with store._Lock("orders"):
        grants = _read_grants(state_store)
        g = covering(what, key, state_store=state_store, now=now)
        if g is None:
            return None
        cur = grants[g["id"]]
        if what == "create":
            cur["remaining"] = cur["remaining"] - 1
        elif key and cur["keys"] != ALL_REVIEWED:
            cur["keys"] = [k for k in cur["keys"] if k != key]
        _write_grants(grants, state_store)
        return g


def require(what, key=None, *, state_store=store, now=None):
    g = consume(what, key, state_store=state_store, now=now)
    if g is None:
        raise OrderRefused("no-ceo-order", refusal(what, key))
    return g


def refusal(what, key=None):
    act = {"create": "Creating a Jira ticket or Epic",
           "merge-alpha": "Merging%s into Alpha" % (" " + key if key else "")}[what]
    return ("%s needs the CEO's explicit order (D-044), and there is no open one. If the CEO "
            "ordered it, lift his exact words first: python3 -m agent.execution.orders grant "
            "--what %s --quote \"<his words>\"%s. If he did not, do not do it and do not ask him "
            "to approve it: propose it in one line and carry on with ordered work."
            % (act, what, " --keys %s" % (key or "KAN-N") if what == "merge-alpha" else ""))


# ------------------------------------------------------------------ action ledger
def log(action, seat, *, key=None, keys=None, order_ref=None, rule=None, sid=None, detail=None,
        state_store=store, now=None):
    """One line in the action ledger. Never raises: the ledger must not stop the act it records."""
    try:
        rec = {"at": _stamp(now or time.time()), "seat": seat, "action": action}
        for k, v in (("key", key), ("keys", keys), ("order_ref", order_ref), ("rule", rule),
                     ("sid", sid), ("detail", (detail or "")[:300] or None)):
            if v:
                rec[k] = v
        _append("ledger", rec, state_store)
        return rec
    except Exception:                                    # noqa: BLE001
        return None


def recent(last=30, *, state_store=store):
    return _jsonl("ledger", state_store)[-last:]


def fmt_action(r):
    if r.get("order_ref"):
        why = "order %s" % r["order_ref"]
    elif r.get("rule"):
        why = "rule %s" % r["rule"]
    elif r["action"] in ("created", "pushed-alpha", "integration-dispatched"):
        why = "NO ORDER"
    else:
        why = "own call"
    keys = r.get("keys")
    what = r.get("key") or (keys if isinstance(keys, str) else ",".join(keys or []))
    local = time.strftime("%m-%d %H:%M", time.localtime(_epoch(r.get("at")))) if r.get("at") else "?"
    return "%s  %-12s %-16s %-10s %s%s" % (local, r.get("seat") or "-",
                                           r["action"], what or "-", why,
                                           ("  — " + r["detail"]) if r.get("detail") else "")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.orders", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grant")
    g.add_argument("--what", required=True, choices=WHATS)
    g.add_argument("--quote", required=True)
    g.add_argument("--keys", default="")
    g.add_argument("--count", type=int, default=1)
    sub.add_parser("open")
    lg = sub.add_parser("log"); lg.add_argument("--last", type=int, default=30)
    ms = sub.add_parser("messages"); ms.add_argument("--last", type=int, default=10)
    ns = ap.parse_args(argv)
    if ns.cmd == "grant":
        keys = ns.keys.strip()
        keys = ALL_REVIEWED if keys == ALL_REVIEWED else [k for k in keys.split(",") if k.strip()]
        try:
            print(json.dumps(grant(ns.what, ns.quote, keys=keys, count=ns.count),
                             ensure_ascii=False, indent=1))
        except OrderRefused as exc:
            print(str(exc), file=sys.stderr)
            return 2
    elif ns.cmd == "open":
        print(json.dumps(open_grants(), ensure_ascii=False, indent=1))
    elif ns.cmd == "log":
        for r in recent(ns.last):
            print(fmt_action(r))
    else:
        for m in messages()[-ns.last:]:
            print("%s  %s  %s" % (m["at"], m["id"], _norm(m["text"])[:200]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
