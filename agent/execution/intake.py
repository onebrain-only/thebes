"""The desk's door into Jira (D-042): ChatGPT/Codex writes tickets into Backlog through here.

The desk discusses with the CEO and decides WHAT the work is. This command is the only way it
writes: one audited path that checks the ticket, refuses a duplicate, and creates it in Backlog
(To Do). It never moves a ticket to Ready (that is the PM's), never writes code, never touches
the database. The desk holds no Jira credentials: Thebes's Jira module does the writing.

    python3 -m agent.execution.intake create --file ticket.md --approved "<the CEO's own words>" [--new]
    python3 -m agent.execution.intake status            # read-only board and teams summary
    python3 -m agent.execution.intake show KAN-123      # one ticket, read-only
    python3 -m agent.execution.intake template [work|ask]

A ticket file is a header, a blank line, then the brief:

    SUMMARY: Venues list shows distance
    TYPE: work                      # work | ask
    COMPONENT: Listings             # Auth | Listings | Social | Money | Platform (required for work)
    CAPABILITY: frontend            # frontend | backend | ux-engineer | analyst | cto | cpo | cxo | ...
    ESTIMATE: 2h                    # 30m, 2h, 1d (= 6h)
    BLOCKED BY: KAN-12, KAN-13      # optional
    PARENT: KAN-10                  # optional

    GOAL: ...
    BRANCH: staging-<team>          # or `none` for an ask
    ALLOWED PATHS: ...
    FORBIDDEN: ...
    DECISIONS MADE: ...
    IF BLOCKED: ...
    CHECKS:
    C1 | run | flutter test test/x_test.dart | exit 0

    Acceptance criteria:
    1. ...
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

PROJECT = "KAN"
COMPONENTS = ("Auth", "Listings", "Social", "Money", "Platform")
CODE_CAPABILITIES = ("frontend", "backend", "ux-engineer")
OTHER_CAPABILITIES = ("analyst", "cto", "cpo", "cxo", "qa", "devops", "content")
HEADER = re.compile(r"^(SUMMARY|TYPE|COMPONENT|CAPABILITY|ESTIMATE|BLOCKED BY|PARENT)\s*:\s*(.*)$",
                    re.I)
KEY = re.compile(r"^KAN-\d+$")
MAX_PER_CALL = 5
STOP_WORDS = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "be",
              "add", "fix", "make", "update", "show", "screen", "page"}


class IntakeError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def _jira():
    from agent.integrations import jira
    return jira


def parse(text):
    """(header fields, brief). The header is the leading `FIELD: value` lines."""
    head, body, in_head = {}, [], True
    for line in (text or "").splitlines():
        if in_head:
            m = HEADER.match(line.strip())
            if m:
                head[m.group(1).upper()] = m.group(2).strip()
                continue
            if not line.strip():
                if head:
                    in_head = False
                continue
            in_head = False
        body.append(line)
    return head, "\n".join(body).strip()


def estimate_seconds(text):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(m|h|d)\s*", text or "", re.I)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2).lower()
    return int(n * {"m": 60, "h": 3600, "d": 6 * 3600}[unit])


def validate(head, body):
    """Everything wrong with the ticket, at once."""
    from agent.execution import dispatch_brief
    problems = []
    summary = head.get("SUMMARY", "")
    kind = head.get("TYPE", "").lower()
    comp = head.get("COMPONENT", "")
    cap = head.get("CAPABILITY", "").lower()
    if not 8 <= len(summary) <= 120:
        problems.append("SUMMARY: 8 to 120 characters")
    if kind not in ("work", "ask"):
        problems.append("TYPE: work or ask")
    if cap not in CODE_CAPABILITIES + OTHER_CAPABILITIES:
        problems.append("CAPABILITY: one of %s" % ", ".join(CODE_CAPABILITIES + OTHER_CAPABILITIES))
    if comp and comp not in COMPONENTS:
        problems.append("COMPONENT: one of %s" % ", ".join(COMPONENTS))
    if kind == "work" and cap in CODE_CAPABILITIES and not comp:
        problems.append("COMPONENT: required for code work (it decides the owning team)")
    if not estimate_seconds(head.get("ESTIMATE")):
        problems.append("ESTIMATE: like 30m, 2h or 1d")
    for field in ("BLOCKED BY", "PARENT"):
        for k in [x.strip() for x in head.get(field, "").split(",") if x.strip()]:
            if not KEY.match(k):
                problems.append("%s: %r is not a KAN key" % (field, k))
    try:
        dispatch_brief.lint(body.replace("<team>", "karnak"), "karnak")
    except dispatch_brief.BriefError as exc:
        problems.extend("brief: " + p for p in exc.problems)
    if "acceptance criteria" not in body.lower():
        problems.append("brief: an 'Acceptance criteria:' section with numbered criteria")
    if problems:
        raise IntakeError(problems)
    return {"summary": summary, "type": kind, "component": comp or None, "capability": cap,
            "estimate": estimate_seconds(head["ESTIMATE"]),
            "blocked_by": [x.strip() for x in head.get("BLOCKED BY", "").split(",") if x.strip()],
            "parent": head.get("PARENT") or None}


def _words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOP_WORDS}


def duplicates(summary, jira):
    """Open tickets whose summary shares most of the meaningful words."""
    mine = _words(summary)
    if not mine:
        return []
    open_issues = jira.search_issues('project = %s AND statusCategory != Done' % PROJECT,
                                     fields=["summary", "status"], limit=200)
    out = []
    for i in open_issues:
        theirs = _words(i.get("summary"))
        if theirs and len(mine & theirs) / float(len(mine | theirs)) >= 0.6:
            out.append({"key": i["key"], "summary": i["summary"], "status": i["status"]})
    return out


def create(text, *, approval, force_new=False, jira=None, by="desk"):
    """`approval` is the CEO's own words saying yes to THIS ticket. A ticket is never created on
    the first mention of an idea: the desk proposes, the CEO says go, and the quote goes on the
    ticket as a comment (an audit trail, and friction against creating on a guess).

    D-044: the words alone are not enough — a model wrote "PM ruling + CPO ranking" as its own
    approval and created an Epic and sixteen tickets nobody ordered. Creating consumes an open
    `create` order (agent/execution/orders.py), which exists only if the quote is literally in a
    message the CEO typed, and the order's quote is what goes on the ticket."""
    if not isinstance(approval, str) or len(approval.strip()) < 2:
        raise IntakeError(["approval: quote the CEO's words saying go (--approved \"...\"). "
                           "Propose the ticket in the conversation first and wait for their yes."])
    jira = jira or _jira()
    head, body = parse(text)
    t = validate(head, body)
    dup = [] if force_new else duplicates(t["summary"], jira)
    if dup:
        raise IntakeError(["possible duplicate of %s (%s, %s); update that ticket, or pass --new "
                           "if this is really different" % (d["key"], d["summary"], d["status"])
                           for d in dup])
    from agent.execution import orders
    served = orders.supports(parent=t["parent"], refs=t["blocked_by"], summary=t["summary"])
    order = None
    if served is None:
        try:
            order = orders.require("create")
        except orders.OrderRefused as exc:
            orders.log("refused-create", by, rule="D-044", detail=t["summary"])
            raise IntakeError([str(exc)])
        approval = order["quote"]
    else:
        approval = "supports %s (D-046): %s" % (served, approval.strip())
    labels = ["intake", "cap:%s" % t["capability"]] + (["ask"] if t["type"] == "ask" else [])
    key = jira.create_issue(PROJECT, t["summary"], body, labels=labels,
                            components=[t["component"]] if t["component"] else None,
                            original_estimate_seconds=t["estimate"], parent=t["parent"])
    try:
        jira.add_comment(key, ("Created by the desk at the CEO's go: \u201c%s\u201d" if order else
                               "Created by the desk to support existing work \u2014 %s")
                         % approval.strip()[:300])
    except Exception:                                      # noqa: BLE001  never blocks
        pass
    orders.log("created", by, key=key, order_ref=order["id"] if order else None,
               rule=None if order else "supports-%s" % served, detail=t["summary"])
    links = []
    for blocker in t["blocked_by"]:
        jira.link_issues_verified(blocker, key)
        links.append(blocker)
    return {"status": "created", "key": key, "where": "Backlog (To Do)",
            "component": t["component"], "capability": t["capability"],
            "blocked_by": links,
            "next": "The PM ranks the Backlog and moves it to Ready; the dispatcher sends it to "
                    "its owning team. Nothing else to do."}


def edit_line(key, old, new, *, jira=None, by=""):
    """Change ONE line of a ticket's description, server-side. Editing a description replaces the
    whole text, so a PO resent a full block for one changed line and the permission classifier
    refused it as Instruction Poisoning (KAN-514/515/516). The line must match exactly once."""
    jira = jira or _jira()
    old, new = (old or "").strip(), (new or "").strip()
    if not old or "\n" in old or "\n" in new:
        raise IntakeError(["--old and --new are each ONE line"])
    if old == new:
        raise IntakeError(["--old and --new are the same"])
    desc = jira.get_issue(key).get("description") or ""
    lines = desc.split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.strip() == old]
    if len(hits) != 1:
        raise IntakeError(["the line matches %d times in %s (it must match exactly once): %r"
                           % (len(hits), key, old[:80])])
    lines[hits[0]] = new
    jira.update_issue(key, {"description": jira.to_adf("\n".join(lines))})
    try:
        jira.add_comment(key, "Thebes: one description line edited%s.\nBefore: %s\nAfter: %s"
                         % (" by %s" % by if by else "", old[:300], new[:300]))
    except Exception:                                      # noqa: BLE001  the audit note never blocks
        pass
    return {"status": "edited", "key": key, "line": hits[0] + 1}


def create_many(texts, *, approval, **kw):
    if len(texts) > MAX_PER_CALL:
        raise IntakeError(["at most %d tickets per call" % MAX_PER_CALL])
    return [create(t, approval=approval, **kw) for t in texts]


# ------------------------------------------------------------------ read-only views
def status(*, jira=None, state_store=None):
    """What the desk tells the CEO: the board by status, who is working on what, and what
    needs the CEO. Read-only."""
    jira = jira or _jira()
    if state_store is None:
        from agent.state import store as state_store
    from agent.state import teams
    issues = jira.search_issues('project = %s AND statusCategory != Done ORDER BY rank ASC'
                                % PROJECT, fields=["summary", "status", "labels"], limit=200)
    board = {}
    for i in issues:
        board.setdefault(i["status"], []).append("%s %s" % (i["key"], i["summary"][:70]))
    needs_ceo = [i["key"] for i in issues if "needs-ceo" in (i.get("labels") or [])]
    needs_brief = [i["key"] for i in issues if "needs-brief" in (i.get("labels") or [])]
    working = {}
    for r in state_store.read_all("conversation_dispatch"):
        if r.get("status") in ("delivering", "delivered"):
            working[r.get("target_seat_id")] = r.get("jira_key") or "question"
    team_rows = []
    for tid, t in sorted(teams.delivery_teams().items(), key=lambda kv: kv[1]["number"]):
        team_rows.append({"team": t["display_name"], "owns": t.get("owns") or ["(operations)"],
                          "working_on": working.get(tid) or "free"})
    return {"board": board, "needs_ceo": needs_ceo, "needs_brief": needs_brief,
            "teams": team_rows}


def show(key, *, jira=None):
    jira = jira or _jira()
    i = jira.get_issue(key)
    comments = jira.get_comments(key, limit=10)
    return {"key": i["key"], "summary": i["summary"], "status": i["status"],
            "labels": i["labels"], "description": i.get("description"),
            "last_comments": [{"at": c["created"], "by": c["author"], "text": c["body"][:600]}
                              for c in comments[-5:]]}


TEMPLATES = {
    "work": """SUMMARY: <what, in one line>
TYPE: work
COMPONENT: <Auth | Listings | Social | Money | Platform>
CAPABILITY: <frontend | backend | ux-engineer>
ESTIMATE: <30m | 2h | 1d>
BLOCKED BY:

GOAL: <the outcome, one or two sentences>
BRANCH: staging-<team>
ALLOWED PATHS: <where the team may write>
FORBIDDEN: <what it must not touch>
DECISIONS MADE: <rulings already taken, or none>
IF BLOCKED: return decision_required with ONE question; no retry loop
CHECKS:
C1 | run | <flutter test test/... or flutter analyze lib/...> | exit 0

Acceptance criteria:
1. <testable criterion>
""",
    "ask": """SUMMARY: <the question, in one line>
TYPE: ask
COMPONENT:
CAPABILITY: <analyst | cto | cpo | cxo>
ESTIMATE: 30m

GOAL: Answer: <the question>
BRANCH: none
ALLOWED PATHS: none (no repository change)
FORBIDDEN: any write to the repository or the database
DECISIONS MADE: none
IF BLOCKED: return decision_required with ONE question
CHECKS:
C1 | judge | the answer states <what must be in it> with its evidence | the team's report

Acceptance criteria:
1. <what the answer must contain>
""",
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.intake", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("--file", required=True, action="append")
    c.add_argument("--approved", required=True, help="the CEO's own words saying go")
    c.add_argument("--new", action="store_true", help="create even if it looks like a duplicate")
    sub.add_parser("status")
    s = sub.add_parser("show"); s.add_argument("key")
    lk = sub.add_parser("links", help="list the links of a ticket, with their ids")
    lk.add_argument("key")
    el = sub.add_parser("edit-line", help="change ONE line of a ticket description (exact match, once)")
    el.add_argument("key"); el.add_argument("--old", required=True); el.add_argument("--new", required=True)
    el.add_argument("--by", default="")
    mi = sub.add_parser("mark-integrated", help="record that a verified dispatch is already in its "
                        "base (git must agree); frees the tickets it was holding")
    mi.add_argument("dispatch_id"); mi.add_argument("--base", required=True, help="staging (app) or staging-ds (design system)")
    mi.add_argument("--sha", required=True, help="the commit in the base that contains it")
    mi.add_argument("--evidence", required=True)
    rk = sub.add_parser("rank", help="move a ticket before/after another in the board rank")
    rk.add_argument("key"); g = rk.add_mutually_exclusive_group(required=True)
    g.add_argument("--before"); g.add_argument("--after")
    od = sub.add_parser("order", help="put these tickets in this order in the board rank")
    od.add_argument("keys", nargs="+")
    ul = sub.add_parser("unlink", help="remove ONE wrong link by id (see `links`)")
    ul.add_argument("link_id")
    ul.add_argument("--approved", required=True,
                    help="who asked for it: the CEO's words, or the ruling it follows")
    t = sub.add_parser("template"); t.add_argument("kind", nargs="?", default="work",
                                                   choices=sorted(TEMPLATES))
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "template":
            print(TEMPLATES[ns.kind])
            return 0
        if ns.cmd == "create":
            texts = [open(f, encoding="utf-8").read() for f in ns.file]
            out = create_many(texts, approval=ns.approved, force_new=ns.new)
        elif ns.cmd == "links":
            out = {"key": ns.key, "links": _jira().issue_links(ns.key)}
        elif ns.cmd == "edit-line":
            out = edit_line(ns.key, ns.old, ns.new, by=ns.by)
        elif ns.cmd == "mark-integrated":
            from agent.execution import integrate
            try:
                out = integrate.mark_integrated(ns.dispatch_id, ns.base, ns.sha, ns.evidence)
            except ValueError as exc:
                raise IntakeError([str(exc)])
        elif ns.cmd == "rank":
            _jira().rank_issue(ns.key, before=ns.before, after=ns.after)
            out = {"status": "ranked", "key": ns.key, "before": ns.before, "after": ns.after}
        elif ns.cmd == "order":
            for prev, key in zip(ns.keys, ns.keys[1:]):
                _jira().rank_issue(key, after=prev)
            out = {"status": "ordered", "keys": ns.keys}
        elif ns.cmd == "unlink":
            _jira().remove_link(ns.link_id)
            out = {"status": "removed", "link_id": ns.link_id, "approved": ns.approved}
        elif ns.cmd == "status":
            out = status()
        else:
            out = show(ns.key)
    except IntakeError as exc:
        print(json.dumps({"status": "refused", "problems": exc.problems}, indent=2,
                         ensure_ascii=False))
        return 2
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
