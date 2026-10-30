"""The review queue the Codex reviewer works from (D-043 draft, agent/REVIEWER.md).

Claude teams hand over evidence and stop reviewing; ONE Codex conversation, "Reviewer", looks at
the finished work with its own eyes. Nothing wakes it from outside (a Desktop conversation cannot
be woken): it runs `wait` as one long command, gets an item, reviews, submits, and waits again.
This module is the zero-token side of that loop.

    python3 -m agent.execution.review_queue wait [--timeout 300]   # blocks; prints ONE item
    python3 -m agent.execution.review_queue next                   # one pass, no waiting
    python3 -m agent.execution.review_queue submit <item_id> --pass C2 --fail C3:"why" \\
        --skip C4:"needs-write" --evidence "<paths and steps>"      # a `judge` item
    python3 -m agent.execution.review_queue submit <item_id> --verdict pass|fail \\
        --reason "..." --evidence "..."                              # a `qa` item
    python3 -m agent.execution.review_queue status

Two kinds of item:
  judge  a verified-by-code dispatch whose only open checks are `judge` checks (an eye must
         settle them). A verdict goes through `verify.judge_verdict`, so a fail sends only
         that check back to the team and the round limit is Thebes's.
  qa     a Jira ticket in the Review column (QA-Test / Self-review / Peer-review). Pass -> Done. Fail -> comment, back to the
         lane status, and a priority request so the PM/orchestrator re-plans it.

An item is CLAIMED atomically for one Codex thread (O_EXCL file); a claim older than
CLAIM_SECONDS is offered again, so a reviewer that died never strands work. A verdict is only
accepted from the thread that holds the claim. `skip` (for example needs-write) is recorded as a
pass whose detail says SKIPPED, so the Jira comment shows what was not verified.
"""
import argparse
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402

CLAIM_SECONDS = 20 * 60
POLL_SECONDS = 5
JIRA_POLL_SECONDS = 60
# The Codex reviewer's queue is the Jira Review column, all three of its statuses (CEO 2026-10-21:
# "the Review column is what I rely on; Codex works on whatever is in it, nothing outside it").
# The board's Review column also holds the old `In Review` status (board config, 2026-10-21).
QA_JQL = ('project = KAN AND status in ("QA-Test", "Self-review", "Peer-review", "In Review") '
          'ORDER BY updated ASC')
# CEO 2026-10-24: the Returned column is gone. A failed review sends the ticket back to the
# column it belongs in (Front-end / Back-end, or its Operations lane) with this label.
RETURNED_LABEL = "returned"
DONE_STATUS_ID = "10007"
TEXT_LIMIT = 6000


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def _dir(sub):
    path = os.path.join(store.RUNTIME, "review", sub)
    os.makedirs(path, exist_ok=True)
    return path


def _safe(item_id):
    return "".join(c if c.isalnum() or c in "-_@." else "_" for c in item_id)


def _thread():
    """Who is asking: a Codex conversation, or (the fallback QA conversation) a Claude session."""
    if os.environ.get("CODEX_THREAD_ID"):
        return os.environ["CODEX_THREAD_ID"]
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    return "claude:%s" % sid if sid else ""


def reviewer_kind(thread=None):
    return "claude" if (thread if thread is not None else _thread()).startswith("claude:") else "codex"


# ------------------------------------------------------------------ which channel reviews
CHANNELS = ("codex", "claude")


def _channel_path():
    return os.path.join(store.RUNTIME, "review", "channel.json")


def get_channel():
    """`codex` (the default) or `claude`. Only the CEO's explicit order, through the orchestrator,
    ever changes it; the channel that is not active stands by and takes no work."""
    return (_read(_channel_path()) or {}).get("channel") or "codex"


def set_channel(channel, by, *, env=None, state_store=store, notify=True, dispatch=None):
    """Switch the review channel (CEO 2026-10-13: Codex is the default; when Codex has no tokens
    the CEO tells the orchestrator to run QA from Claude Code, and back). Orchestrator only.
    Claims held by the OTHER channel are released so nothing is stranded, and the fallback QA
    conversation (Edfu) is woken to start, or told to stop."""
    from agent.state import teams
    env = os.environ if env is None else env
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator switches the review channel, and "
                      "only on the CEO's explicit order")
    if channel not in CHANNELS:
        raise Refused("channel-invalid", "channel is codex or claude")
    if not (by or "").strip():
        raise Refused("order-required", "quote the CEO's words ordering the switch (--by)")
    before = get_channel()
    os.makedirs(os.path.dirname(_channel_path()), exist_ok=True)
    with open(_channel_path(), "w", encoding="utf-8") as fh:
        json.dump({"channel": channel, "by": by.strip()[:300], "at": time.time()}, fh)
    released = []
    for name in os.listdir(_dir("claims")):
        c = _read(os.path.join(_dir("claims"), name)) or {}
        if c.get("thread") and reviewer_kind(c["thread"]) != channel and not is_done(c.get("item_id", "")):
            os.unlink(os.path.join(_dir("claims"), name))
            released.append(c.get("item_id"))
    out = {"status": "switched", "from": before, "to": channel, "released_claims": released}
    if notify:
        out["edfu"] = _wake_edfu(channel, state_store, dispatch)
    return out


def _wake_edfu(channel, state_store, dispatch=None):
    from agent.state import teams
    edfu = next(iter(teams.lane_teams("qa")), None)
    sid = (state_store.active_role_session(edfu) or {}).get("session_id") if edfu else None
    if not sid:
        return {"status": "not-started",
                "next": "Edfu has no session: the CEO runs `bash agent/scripts/start-teams.sh edfu`"}
    if channel == "claude":
        text = ("THEBES REVIEW CHANNEL: CLAUDE. The CEO ordered QA to run from Claude Code. Follow "
                "agent/REVIEWER.md (Claude variant) now: start `python3 -m agent.execution."
                "review_queue wait --timeout 3600` with run_in_background, handle every item it "
                "returns, submit verdicts, and start the wait again each time. Report in one line "
                "that the loop is running, then end your turn.")
    else:
        text = ("THEBES REVIEW CHANNEL: CODEX. The CEO sent QA back to Codex. Stop your review "
                "loop now: do not start another `review_queue wait`, finish any item you have "
                "already submitted, report in one line that you stood down, and go idle.")
    from agent.execution import conversation_dispatch as cd
    env = {k: v for k, v in os.environ.items() if k not in ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID")}
    env[cd.CLAUDE_ORIGIN_ENV] = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    env.update(THEBES_ACTOR="review-queue", THEBES_RULE="review")
    try:
        out = (dispatch or cd.dispatch)(text, sid, env=env, state_store=state_store, detach=True, ticket=None)
        return {"status": "notified", "dispatch_id": out.get("dispatch_id")}
    except Exception as exc:                                # noqa: BLE001
        return {"status": "notify-failed", "error": str(exc)[:200],
                "next": "dispatch the same text to Edfu by hand (conversation_dispatch dispatch --to %s)" % sid}


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _text(path, limit=TEXT_LIMIT):
    try:
        with open(path or "", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def is_done(item_id):
    return os.path.exists(os.path.join(_dir("done"), _safe(item_id)))


def claim(item_id, now=None, meta=None):
    """Atomically claim for this thread. True if claimed (or this thread already holds it).
    `meta` (tier, platform, branch, sha) is kept with the claim for the evidence gate."""
    now = now or time.time()
    path = os.path.join(_dir("claims"), _safe(item_id))
    body = {"item_id": item_id, "thread": _thread(), "at": now, "meta": meta or {}}
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            cur = _read(path) or {}
            if cur.get("thread") == body["thread"] and now - cur.get("at", 0) < CLAIM_SECONDS:
                if meta and cur.get("meta") != meta:
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(dict(cur, meta=meta), fh)
                return True
            if now - cur.get("at", 0) < CLAIM_SECONDS:
                return False
            try:                                  # stale: the reviewer that held it is gone
                os.unlink(path)
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(body, fh)
        return True
    return False


def claim_record(item_id):
    return _read(os.path.join(_dir("claims"), _safe(item_id))) or {}


def holder(item_id):
    return claim_record(item_id).get("thread")


def finish(item_id, outcome):
    with open(os.path.join(_dir("done"), _safe(item_id)), "w", encoding="utf-8") as fh:
        json.dump({"item_id": item_id, "outcome": outcome, "at": time.time(),
                   "claimed_at": claim_record(item_id).get("at"), "thread": _thread()}, fh)


# ------------------------------------------------------------------- finding work
# A headless reviewer has a shell, repo history, the Keychain and (with the registry's extra
# roots) flutter, but NO browser (probe 2026-10-17). Work that has to be SEEN in the running app is
# the Desktop reviewer's: any change under a screen/widget/presentation folder, boot code, native
# folders, the design system's assets, or an ARB file.
from agent.execution import review_tier                                # noqa: E402
UI_PATH = review_tier.UI_PATH
_FILES = {}


def ticket_files(repo, sha, key, runner=None):
    """Files this ticket's own commits (subject `KAN-n:`) in `sha`'s history change, or None.
    A team branch carries several tickets, and once integrated the commit is already in Alpha
    (live 2026-10-21: the diff against Alpha was empty and every ticket looked screen-less)."""
    import subprocess
    run = runner or subprocess.run
    cwd = os.path.join(ROOT, repo)
    lg = run(["git", "-C", cwd, "log", "--format=%H %s", "-n", "400", sha],
             capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    if lg.returncode != 0:
        return None
    mine = [l.split(" ", 1)[0] for l in (lg.stdout or "").splitlines()
            if l.split(" ", 1)[-1].startswith("%s:" % key)]
    files = set()
    for commit in mine:
        done = run(["git", "-C", cwd, "show", "--name-only", "--format=", commit],
                   capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            return None
        files.update(f for f in (done.stdout or "").splitlines() if f.strip())
    return sorted(files) if mine else None


def changed_paths(branch, sha, runner=None, key=None):
    """Files the ticket changes: its own commits when they can be found, else the commit's diff
    against its base (local refs, no network), else None."""
    cache = (branch, sha, key)
    if cache not in _FILES:
        try:
            from agent.execution import integrate
            t = integrate.target_for(branch or "", sha, runner)
            files = ticket_files(t["repo"], sha, key, runner) if (t and key) else None
            if not files and t:
                files = integrate.changed_files(t["repo"], t["base"], sha, runner, fetch=False) or None
            _FILES[cache] = files
        except Exception:                                  # noqa: BLE001
            _FILES[cache] = None
    return _FILES[cache]


def needs_browser(branch, sha, runner=None, labels=(), key=None):
    """True when the change must be looked at in the app (tier 2 or 3, or when we cannot tell)."""
    return review_tier.tier(changed_paths(branch, sha, runner, key) if sha else None, labels) >= 2


def depth(branch, sha, labels=(), runner=None, key=None):
    """tier, platform and the screenshots a PASS needs (agent/execution/review_tier.py)."""
    out = review_tier.describe(changed_paths(branch, sha, runner, key) if sha else None, labels)
    out["needs_browser"] = out["tier"] >= 2
    return out


def is_headless_thread():
    cfg = reviewer_config()
    return cfg.get("mode") == "headless" and bool(cfg.get("thread_id")) and _thread() == cfg["thread_id"]


def _superseded(rec, all_recs):
    """A newer dispatch for the same ticket exists outside this root's own continuations, or the
    root was discarded: its commit is no longer what the ticket is about (defect 5, 2026-10-29:
    stale roots kept raising judge items and review_stalled alerts)."""
    if rec.get("integrated_at") == "discarded":
        return True
    family = {rec["dispatch_id"]}
    for other in all_recs:
        if other.get("root_dispatch_id") == rec["dispatch_id"]:
            family.add(other["dispatch_id"])
    return any(o.get("jira_key") == rec.get("jira_key") and o["dispatch_id"] not in family
               and (o.get("created_at") or "") > (rec.get("created_at") or "")
               and o.get("status") not in ("delivery_failed", "withdrawn")
               for o in all_recs)


def judge_items(state_store=store):
    from agent.execution import verify, conversation_dispatch as cd
    out = []
    all_recs = state_store.read_all("conversation_dispatch")
    for rec in all_recs:
        if rec.get("root_dispatch_id") or not rec.get("jira_key") or not cd.is_product(rec):
            continue                       # text/ops deliverables stay with the orchestrator
        pending = verify.pending_judge(rec)
        if not pending:
            continue
        if (rec.get("verification") or {}).get("verdict") != "needs_judge" or _superseded(rec, all_recs):
            continue                       # a fix is in flight, or a newer dispatch owns the ticket
        ver = rec.get("verification") or {}
        by_id = {c["id"]: c for c in rec.get("checks") or []}
        commit = with_commit({"branch": ver.get("branch") or rec.get("branch"), "sha": ver.get("sha")},
                             rec["jira_key"], state_store)
        ver = dict(ver, branch=commit["branch"], sha=commit["sha"])
        brief = _text(rec.get("prompt_ref"))
        out.append({
            "item_id": "judge-%s-c%s" % (rec["dispatch_id"], ver.get("cycle") or 1),
            "kind": "judge", "dispatch_id": rec["dispatch_id"], "ticket": rec["jira_key"],
            "team": rec.get("target_seat_id"), "branch": ver.get("branch"), "sha": ver.get("sha"),
            "commit_resolved": commit["commit_resolved"],
            "checks": [{"id": p["id"], "what": (by_id.get(p["id"]) or {}).get("what") or p.get("what"),
                        "evidence_named": (by_id.get(p["id"]) or {}).get("pass")}
                       for p in pending],
            **depth(ver.get("branch"), ver.get("sha"), key=rec["jira_key"],
                    labels=("tier:1",) if cd.NO_UI.search(brief or "") else ()),
            "team_report": _text(rec.get("result_ref")),
            "brief": brief,
            "at": rec.get("outcome_at") or rec.get("created_at") or ""})
    return out


def _team_working(key, state_store=store):
    """A team still holds an open dispatch for this ticket (no outcome yet), so a Self-review status
    on it is the team's own work in progress, not a finished ticket waiting for review."""
    for rec in state_store.read_all("conversation_dispatch"):
        if (rec.get("jira_key") == key and not rec.get("outcome")
                and rec.get("status") not in ("delivery_failed", "withdrawn")):
            return True
    return False


def team_commit(key, state_store=store):
    """The team's last verified commit for this ticket: {branch, sha, team} or {} (cloud tickets
    carry their own). The latest completed dispatch with a verified sha wins."""
    best = None
    for rec in state_store.read_all("conversation_dispatch"):
        ver = rec.get("verification") or {}
        if rec.get("jira_key") != key or not ver.get("sha"):
            continue
        stamp = rec.get("outcome_at") or rec.get("created_at") or ""
        if best is None or stamp > best[0]:
            best = (stamp, {"branch": ver.get("branch") or rec.get("branch"), "sha": ver["sha"],
                            "team": rec.get("target_seat_id")})
    return best[1] if best else {}


APP_REPO = "Dabbler/dabbler-code"
HEAD_TTL = 60
_HEADS = {}


def team_branch(key, state_store=store):
    """The branch this ticket's dispatches name, newest first, else the team's own `alpha-<seat>`
    (live 2026-10-22: KAN-622's newest dispatch carried no branch and no verified sha)."""
    recs = sorted((r for r in state_store.read_all("conversation_dispatch") if r.get("jira_key") == key),
                  key=lambda r: r.get("outcome_at") or r.get("created_at") or "", reverse=True)
    for rec in recs:
        named = rec.get("branch") or (rec.get("verification") or {}).get("branch")
        if named:
            return named
    return "alpha-%s" % recs[0]["target_seat_id"] if recs and recs[0].get("target_seat_id") else None


def branch_head(branch, runner=None, clock=time.time):
    """origin's sha for the branch (case-insensitive), or None. Cached for HEAD_TTL: the queue polls
    every few seconds and this asks the network."""
    hit = _HEADS.get(branch)
    if hit and clock() - hit[0] < HEAD_TTL:
        return hit[1]
    try:
        from agent.execution import integrate
        base = integrate.base_for(branch)
        sha = integrate.remote_head(base["repo"] if base else APP_REPO, branch, runner)
    except Exception:                                      # noqa: BLE001  no network: unresolved
        sha = None
    _HEADS[branch] = (clock(), sha)
    return sha


def with_commit(commit, key, state_store=store, runner=None):
    """`commit` ({branch, sha, ...}) with BOTH filled in when they can be: the branch from the ticket's
    dispatches, the sha from the branch head on origin. A sha taken from the head is marked
    `sha_from: branch-head` (not a team-verified commit). `commit_resolved` says whether both exist."""
    branch, sha = commit.get("branch"), commit.get("sha")
    out = dict(commit)
    if not branch:
        branch = team_branch(key, state_store)
    if branch and not sha:
        sha = branch_head(branch, runner)
        if sha:
            out["sha_from"] = "branch-head"
            out.pop("note", None)
    out.update(branch=branch, sha=sha, commit_resolved=bool(branch and sha))
    return out


def qa_items(jira=None, state_store=store):
    if jira is None:
        from agent.execution import jira_sync
        jira = jira_sync._client(None, store)
    if jira is None:
        return []
    out = []
    for raw in jira.search_issues(QA_JQL, fields=["summary", "status", "description", "updated", "labels"],
                                  limit=20, raw=True):
        issue = jira.normalize_issue(raw)
        key = issue["key"]
        if (issue.get("status") or "").lower() == "self-review" and _team_working(key, state_store):
            continue
        if is_awaiting(key):                                # passed; waits only to go live
            continue
        cloud = None
        try:
            from agent.execution import cloud_lane
            cloud = cloud_lane.cloud_info(key)
        except Exception:                                   # noqa: BLE001
            pass
        labels = (raw.get("fields") or {}).get("labels") or issue.get("labels") or []
        if cloud:
            commit = {"branch": cloud.get("cloud_branch"), "sha": cloud.get("sha")}
        else:
            commit = team_commit(key, state_store) or {"branch": None, "sha": None,
                                                       "note": "no verified commit: review the branch head"}
        commit = with_commit(commit, key, state_store)
        out.append({"item_id": "qa-%s@%s" % (key, (raw.get("fields") or {}).get("updated")),
                    "kind": "qa", "ticket": key, "summary": issue.get("summary"),
                    **commit, **(cloud or {}), "labels": labels,
                    **depth(commit.get("branch"), commit.get("sha"), labels, key=key),
                    "status": issue.get("status"), "description": (issue.get("description") or "")[:TEXT_LIMIT],
                    "at": (raw.get("fields") or {}).get("updated") or ""})
    return out


def _enrich_judges(items, jira=None):
    """A judge item whose ticket is already Done in Jira is stale (live 2026-10-13: a 5-day-old
    KAN-438 item the PO had closed with live-DB evidence was reviewed and failed). Drop those;
    for the rest add the ticket's status and latest comments so the reviewer sees the context."""
    if not items:
        return items
    if jira is None:
        from agent.execution import jira_sync
        jira = jira_sync._client(None, store)
    if jira is None:
        return items
    out = []
    for item in items:
        try:
            issue = jira.get_issue(item["ticket"])
            if (issue.get("status") or "").lower() == "done":
                finish(item["item_id"], {"skipped": "ticket-already-done"})
                continue
            item["ticket_status"] = issue.get("status")
            item["latest_comments"] = [
                {"at": c.get("created") or c.get("at"), "text": (c.get("body") or c.get("text") or "")[:500]}
                for c in (jira.get_comments(item["ticket"], limit=50) or [])[-3:]]
        except Exception:                                   # noqa: BLE001  Jira down: keep as is
            pass
        out.append(item)
    return out


def candidates(state_store=store, jira=None, with_qa=True):
    items = _enrich_judges(judge_items(state_store), jira)
    if with_qa:
        try:
            judged = {i["ticket"] for i in items}
            # a ticket with a pending judge item is reviewed through it (its dispatch carries the
            # checks); a second `qa` item for the same ticket would close it without them
            items += [q for q in qa_items(jira, state_store) if q["ticket"] not in judged]
        except Exception:                                   # noqa: BLE001  Jira down: judges only
            pass
    # Every offered item names its branch AND sha (KAN-622 once had neither); one that cannot be
    # resolved is withheld and shown by status() as `no_commit`, never handed out to guess.
    return sorted((i for i in items if not is_done(i["item_id"]) and i.get("commit_resolved", True)
                   and i.get("branch") and i.get("sha")), key=lambda i: i["at"])


def next_item(state_store=store, jira=None, with_qa=True):
    if reviewer_kind() != get_channel():
        return None                                         # this channel is standing by
    headless = is_headless_thread()
    for item in candidates(state_store, jira, with_qa):
        if headless and item.get("needs_browser"):
            continue                       # it has no browser: that item is the Desktop reviewer's
        meta = {k: item.get(k) for k in ("ticket", "tier", "platform", "min_screenshots", "branch", "sha")}
        if claim(item["item_id"], meta=meta):
            return item
    return None


def wait(timeout, *, state_store=store, jira=None, sleep=time.sleep, clock=time.time):
    start, last_jira, with_qa = clock(), -JIRA_POLL_SECONDS, True
    if reviewer_kind() != get_channel():
        return {"standby": True, "channel": get_channel(),
                "next": "The review channel is %s, not yours: do not start another wait; go idle "
                        "until the orchestrator or the CEO tells you the channel is yours."
                        % get_channel()}
    while clock() - start < timeout:
        poll_qa = clock() - last_jira >= JIRA_POLL_SECONDS
        if poll_qa:
            last_jira = clock()
        item = next_answer(clock()) or next_item(state_store, jira, with_qa=poll_qa)
        if item:
            return item
        sleep(POLL_SECONDS)
    return None


# ------------------------------------------------------------------- the verdict
def _owner_check(item_id):
    held = holder(item_id)
    if held is None:
        raise Refused("not-claimed", "%s is not claimed; run `wait` or `next` first" % item_id)
    if held != _thread():
        raise Refused("not-your-claim", "%s is claimed by another reviewer thread" % item_id)


SHOT_EXT = (".png", ".jpg", ".jpeg")


def evidence_dir(ticket):
    return os.path.join(store.RUNTIME, "review-evidence", ticket)


def screenshots(ticket, since=0):
    d = evidence_dir(ticket)
    try:
        return sorted(os.path.join(d, f) for f in os.listdir(d)
                      if f.lower().endswith(SHOT_EXT) and os.path.getmtime(os.path.join(d, f)) >= since)
    except OSError:
        return []


def evidence_gate(item_id, ticket):
    """A PASS on a tier-2/3 item needs screenshots taken during this review (CEO 2026-10-21: the
    reviewer looks at the running app of the team's branch, and shows it). Returns the meta."""
    rec = claim_record(item_id)
    meta = rec.get("meta") or {}
    need = int(meta.get("min_screenshots") or 0)
    since = (rec.get("at") or 0) - CLAIM_SECONDS
    shots = screenshots(ticket, since)
    if len(shots) < need:
        raise Refused("evidence-missing",
                      "tier %s needs %d screenshot(s) of the running app in %s taken during this "
                      "review; found %d. Run `review_queue app %s`, test, save screenshots there, "
                      "then submit again." % (meta.get("tier"), need, evidence_dir(ticket),
                                              len(shots), item_id))
    return dict(meta, screenshots=shots)


def render_gate(item_id, ticket):
    """Fail closed (live 2026-10-22: six tickets judged on a blank canvas). No PASS or FAIL while the
    last web start of this commit did not draw (`flt-semantics-placeholder`), and a screen item on
    web needs a start that did. The reviewer reports "build not ready" instead."""
    from agent.execution import review_app
    meta = claim_record(item_id).get("meta") or {}
    rec = review_app.render_record(ticket)
    same = not (rec and meta.get("sha") and rec.get("sha")) or rec["sha"] == meta["sha"]
    if rec and same and not rec.get("rendered"):
        raise Refused("build-not-ready", "%s: %s. Report the build as not ready; do not record PASS or "
                      "FAIL on it." % (ticket, rec.get("reason") or "the app never drew"))
    if meta.get("platform") == "web" and int(meta.get("min_screenshots") or 0) > 0 \
            and not (rec and same and rec.get("rendered")):
        raise Refused("build-not-ready", "%s is a screen change on web: run `review_queue app %s` and "
                      "wait until the app has drawn before any verdict." % (ticket, item_id))


def tested_line(meta):
    """What was tested, for the Jira comment."""
    if not meta.get("tier"):
        return ""
    return "Tested: %s at %s, tier %s, %s.%s\n" % (
        meta.get("branch") or "branch head", (meta.get("sha") or "?")[:12], meta.get("tier"),
        "app on %s" % meta["platform"] if meta.get("platform") else "diff and tests (no screen)",
        " Screenshots: %d." % len(meta.get("screenshots") or []) if meta.get("screenshots") else "")


def _evidence_file(ticket, evidence):
    d = os.path.join(store.RUNTIME, "review-evidence", ticket)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "verdict-%d.txt" % int(time.time()))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(evidence)
    return path


def submit_judge(item_id, passed, failed, skipped, evidence, *, state_store=store, jira=None,
                 dispatcher=None, launcher=None, environment=None):
    from agent.execution import verify
    _owner_check(item_id)
    if not (evidence or "").strip():
        raise Refused("evidence-required", "name what you looked at and the steps you took")
    dispatch_id = item_id.split("-", 1)[1].rsplit("-c", 1)[0]
    rec = state_store.read("conversation_dispatch", dispatch_id)
    if rec is None:
        raise Refused("dispatch-not-found", dispatch_id)
    if passed or failed:
        render_gate(item_id, rec.get("jira_key") or "unknown")
    meta = evidence_gate(item_id, rec.get("jira_key") or "unknown") if passed and not failed else {}
    ev_path = _evidence_file(rec.get("jira_key") or "unknown", evidence)
    notes = {c: "reviewer: %s%s (evidence %s)" % (tested_line(meta), evidence.strip()[:200], ev_path)
             for c in passed}
    for cid, why in skipped.items():
        notes[cid] = "SKIPPED, not verified: %s" % why
    out = verify.judge_verdict(dispatch_id, list(passed) + list(skipped), failed,
                               state_store=state_store, jira=jira, dispatcher=dispatcher,
                               launcher=launcher, reviewer=_thread() or "reviewer", notes=notes,
                               environment=environment)
    if failed and rec.get("jira_key"):              # the ticket goes back to its own column, tagged returned
        try:
            from agent.execution import jira_sync
            client = jira_sync._client(jira, state_store)
            if client is not None:
                send_back(rec["jira_key"], client, state_store)
        except Exception:                            # noqa: BLE001  the send-back already happened
            pass
    elif passed and rec.get("jira_key"):             # the tag comes off once it passes
        try:
            from agent.execution import jira_sync
            client = jira_sync._client(jira, state_store)
            if client is not None:
                _set_returned(rec["jira_key"], client, False)
        except Exception:                            # noqa: BLE001
            pass
    finish(item_id, {"pass": sorted(passed), "fail": sorted(failed), "skip": sorted(skipped)})
    return {"status": "recorded", "item_id": item_id, "evidence": ev_path, "result": out}


def _working_status(ticket, state_store):
    """The status a returned ticket goes back to: its own lane, never Review or Done."""
    import board
    task = state_store.read("task", ticket) or {}
    cap = task.get("required_capability") or \
        (task.get("execution_profile") or {}).get("required_capability")
    if not cap:
        for rec in sorted(state_store.read_all("conversation_dispatch"),
                          key=lambda r: r.get("created_at") or "", reverse=True):
            if rec.get("jira_key") == ticket and rec.get("jira_capability"):
                cap = rec["jira_capability"]
                break
    sid = board.execution_status_for(cap) if cap and cap not in board.NO_EXECUTION_CAPABILITIES else None
    return sid or board.CAPABILITY_TO_STATUS_ID["frontend"]


def _set_returned(ticket, jira, on):
    """Best effort: the tag is a signal, the move is the fact."""
    try:
        labels = list(jira.get_issue(ticket).get("labels") or [])
    except Exception:                                # noqa: BLE001
        return
    if on and RETURNED_LABEL not in labels:
        jira.update_issue(ticket, {"labels": labels + [RETURNED_LABEL]})
    elif not on and RETURNED_LABEL in labels:
        jira.update_issue(ticket, {"labels": [l for l in labels if l != RETURNED_LABEL]})


def send_back(ticket, jira, state_store):
    """Failed review: back to the ticket's own column, tagged `returned`."""
    from agent.execution import jira_sync
    jira_sync._move(ticket, _working_status(ticket, state_store), jira, state_store)
    _set_returned(ticket, jira, True)


def close_passed(ticket, jira, state_store):
    """Passed review: Done, and the `returned` tag comes off."""
    from agent.execution import jira_sync
    jira_sync._move(ticket, DONE_STATUS_ID, jira, state_store)
    _set_returned(ticket, jira, False)


# ------------------------------------------------------------------ Done = live (D-043 section 6)
# The CEO's part resumes when he SEES the work live, so a PASS is Done only once the reviewed
# commit is on Alpha and alpha.dabbler.pro serves it. Until then the ticket stays in review,
# recorded under awaiting-live/, out of the reviewer's queue; the dispatcher's sweep closes it.
LIVE_LATE_SECONDS = 15 * 60          # on Alpha this long and still not deployed: ops problem
INTEGRATE_LATE_SECONDS = 24 * 3600   # passed this long and still not on Alpha: integration stuck
SITE_URL = re.compile(r"https?://alpha\.dabbler\.pro(/[^\s)\]|>\"']*)?")


def _awaiting_path(ticket):
    return os.path.join(_dir("awaiting-live"), "%s.json" % _safe(ticket))


def awaiting():
    out = []
    for name in sorted(os.listdir(_dir("awaiting-live"))):
        rec = _read(os.path.join(_dir("awaiting-live"), name))
        if rec and rec.get("ticket"):
            out.append(rec)
    return out


def is_awaiting(ticket):
    return os.path.exists(_awaiting_path(ticket))


def live_link(description):
    """The alpha.dabbler.pro address the ticket's test scenarios name, else the site itself."""
    from agent.execution import live_check
    if not isinstance(description, str):                    # ADF or missing
        description = json.dumps(description) if isinstance(description, (dict, list)) else ""
    m = SITE_URL.search(description)
    return m.group(0).rstrip(".,;") if m else live_check.SITE


def live_comment(ticket, summary, reason, link, verified, sha):
    """The one Arabic Done comment the CEO reads: what was done, where to open it."""
    lines = ["خلصت ✅ وشغالة لايف على Alpha." if verified else
             "خلصت ✅ ووصلت Alpha (الموقع ما بيقولش رقم البيلد، فاللايف متأكدش منه بالكود).",
             "اتعمل إيه: %s" % (summary or ticket)]
    if (reason or "").strip():
        lines.append("نتيجة المراجعة: %s" % reason.strip()[:300])
    lines.append("تشوفها فين: افتح %s" % link)
    if sha:
        lines.append("الكوميت: %s" % sha[:12])
    return "Thebes: " + "\n".join(lines)


def _close_live(ticket, rec, live, jira, state_store):
    close_passed(ticket, jira, state_store)
    summary, description = rec.get("summary"), rec.get("description")
    if summary is None:
        try:
            issue = jira.get_issue(ticket)
            summary, description = issue.get("summary"), issue.get("description")
        except Exception:                            # noqa: BLE001
            pass
    summary = summary if isinstance(summary, str) else None
    link = live_link(description)
    try:                                             # the "what's new" page and ceo_metrics read it
        with open(os.path.join(store.RUNTIME, "review", "live-done.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "ticket": ticket, "summary": summary, "link": link, "live": live,
                                 "sha": rec.get("sha"), "passed_at": rec.get("at")},
                                ensure_ascii=False) + "\n")
    except OSError:
        pass
    jira.add_comment(ticket, live_comment(ticket, summary, rec.get("reason"), link,
                                          live == "live", rec.get("sha")))


def close_or_await(ticket, meta, reason, jira, state_store, *, now=None, check=None):
    """PASS: Done now if the commit is live (or on Alpha and the site cannot say), else wait."""
    from agent.execution import live_check
    sha = (meta or {}).get("sha")
    live = (check or live_check.status)(sha) if sha else "no-commit"
    rec = {"ticket": ticket, "sha": sha, "branch": (meta or {}).get("branch"),
           "reason": (reason or "").strip()[:300], "at": now or time.time()}
    if live in ("live", "on-alpha-unverified", "no-commit"):
        _close_live(ticket, rec, live, jira, state_store)
        return live
    if live == "on-alpha":
        rec["on_alpha_at"] = rec["at"]
    with open(_awaiting_path(ticket), "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    jira.add_comment(ticket, "Thebes: PASS — waiting to go live (%s). It moves to Done by itself "
                     "once %s is on Alpha and alpha.dabbler.pro serves it." % (live, (sha or "")[:12]))
    return live


def sweep_live(*, state_store=store, jira=None, now=None, check=None):
    """Dispatcher tick: close every awaiting ticket that is now live; flag the late ones to the
    orchestrator (never the CEO). Never raises."""
    from agent.execution import live_check
    now = now or time.time()
    done = []
    try:
        recs = awaiting()
        if not recs:
            return []
        from agent.execution import jira_sync
        jira = jira_sync._client(jira, state_store)
        if jira is None:
            return []
        for rec in recs:
            ticket = rec["ticket"]
            try:
                live = (check or live_check.status)(rec.get("sha"))
                if live in ("live", "on-alpha-unverified"):
                    _close_live(ticket, rec, live, jira, state_store)
                    os.unlink(_awaiting_path(ticket))
                    done.append({"action": "done-live", "ticket": ticket, "live": live})
                    continue
                if live == "on-alpha" and not rec.get("on_alpha_at"):
                    rec["on_alpha_at"] = now
                late = (now - rec["on_alpha_at"] >= LIVE_LATE_SECONDS if rec.get("on_alpha_at")
                        else now - rec.get("at", now) >= INTEGRATE_LATE_SECONDS)
                if late and not rec.get("late_flagged"):
                    rec["late_flagged"] = now
                    done.append({"action": "not-live-late", "ticket": ticket, "live": live})
                with open(_awaiting_path(ticket), "w", encoding="utf-8") as fh:
                    json.dump(rec, fh)
            except Exception as exc:                 # noqa: BLE001  one ticket never stops the rest
                done.append({"action": "live-check-failed", "ticket": ticket, "error": str(exc)[:200]})
    except Exception as exc:                         # noqa: BLE001
        done.append({"action": "sweep-live-failed", "error": str(exc)[:200]})
    return done


def not_live_for_inbox():
    """Awaiting tickets flagged late and not yet handed to the orchestrator."""
    return [r for r in awaiting() if r.get("late_flagged") and not r.get("late_collected")]


def mark_not_live_collected(ticket):
    rec = _read(_awaiting_path(ticket))
    if rec:
        rec["late_collected"] = time.time()
        with open(_awaiting_path(ticket), "w", encoding="utf-8") as fh:
            json.dump(rec, fh)


def submit_qa(item_id, verdict, reason, evidence, *, state_store=store, jira=None):
    from agent.execution import jira_sync
    _owner_check(item_id)
    if verdict not in ("pass", "fail"):
        raise Refused("verdict-invalid", "--verdict pass|fail")
    if verdict == "fail" and not (reason or "").strip():
        raise Refused("reason-required", "a failing verdict needs a reason a developer can act on")
    if not (evidence or "").strip():
        raise Refused("evidence-required", "name what you looked at and the steps you took")
    ticket = item_id[len("qa-"):].split("@")[0]
    render_gate(item_id, ticket)
    meta = evidence_gate(item_id, ticket) if verdict == "pass" else (claim_record(item_id).get("meta") or {})
    ev_path = _evidence_file(ticket, evidence)
    jira = jira_sync._client(jira, state_store)
    if jira is None:
        raise Refused("jira-unavailable", "cannot record a qa verdict without Jira")
    if verdict == "pass":
        jira.add_comment(ticket, "Thebes reviewer (Codex): PASS. %s\n%sEvidence: %s"
                         % ((reason or "").strip()[:500], tested_line(meta), ev_path))
        close_or_await(ticket, meta, reason, jira, state_store)
    else:
        send_back(ticket, jira, state_store)
        jira.add_comment(ticket, "Thebes reviewer (Codex): FAIL.\n%s\n%sEvidence: %s"
                         % (reason.strip()[:1500], tested_line(meta), ev_path))
        try:                                         # the PM / orchestrator re-plans the rework
            state_store.create("priority_request", {
                "reasons": [{"kind": "qa-failed", "key": ticket, "reason": reason.strip()[:300]}],
                "status": "open", "backlog_signature": "qa-failed|%s|%d" % (ticket, time.time()),
                "collected_at": None})
        except Exception:                            # noqa: BLE001
            pass
    finish(item_id, {"verdict": verdict})
    return {"status": "recorded", "item_id": item_id, "evidence": ev_path}


def reopen(dispatch_id, *, state_store=store):
    """Offer a verified-but-unverified product item to the reviewer again: every check that was
    SKIPPED goes back to pending, so the ticket can still close by itself."""
    rec = state_store.read("conversation_dispatch", dispatch_id)
    ver = dict((rec or {}).get("verification") or {})
    skipped = [i for i, r in (ver.get("results") or {}).items()
               if str(r.get("detail") or "").startswith(("SKIPPED", "ENVIRONMENT"))]
    if not rec or not skipped:
        raise Refused("nothing-to-reopen", "no skipped check on %s" % dispatch_id)
    results = dict(ver["results"])
    for i in skipped:
        results[i] = dict(results[i], status="pending-judge", detail="")
    ver.update(results=results, verdict="needs_judge", unverified=[])
    state_store.update("conversation_dispatch", dispatch_id, rec["revision"], {"verification": ver})
    for name in os.listdir(_dir("done")):
        if dispatch_id in name:
            os.unlink(os.path.join(_dir("done"), name))
    for name in os.listdir(_dir("claims")):
        if dispatch_id in name:
            os.unlink(os.path.join(_dir("claims"), name))
    return {"status": "reopened", "dispatch_id": dispatch_id, "checks": skipped}


# ------------------------------------------------------------------ asking the orchestrator
QUESTION_TTL = 30 * 60
ANSWER_LIMIT = 4000


def _qdir():
    return _dir("questions")


def _qpath(qid):
    return os.path.join(_qdir(), "%s.json" % _safe(qid))


def _qsave(q):
    tmp = _qpath(q["qid"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(q, fh)
    os.replace(tmp, _qpath(q["qid"]))


def questions():
    out = []
    for name in sorted(os.listdir(_qdir())):
        if name.endswith(".json"):
            q = _read(os.path.join(_qdir(), name))
            if q:
                out.append(q)
    return out


def ask(item_id, question, *, now=None):
    """The reviewer is stuck on an item it holds: put ONE question to the orchestrator. The answer
    comes back through `wait` as an item of kind `answer` (a Desktop conversation cannot be woken,
    so the reviewer polls, as it already does for work). The claim on the item is kept alive."""
    _owner_check(item_id)
    if not (question or "").strip():
        raise Refused("question-required", "say exactly what you cannot decide and what you tried")
    if any(q["item_id"] == item_id and q["answered_at"] is None for q in questions()):
        raise Refused("question-open", "you already have an open question on %s; wait for its answer"
                      % item_id)
    now = now or time.time()
    ticket = (item_id[len("qa-"):].split("@")[0] if item_id.startswith("qa-")
              else _ticket_of_judge(item_id))
    qid = "q-%d-%s" % (now, os.urandom(3).hex())
    q = {"qid": qid, "item_id": item_id, "ticket": ticket, "thread": _thread(),
         "question": question.strip()[:ANSWER_LIMIT], "asked_at": now, "collected_at": None,
         "answered_at": None, "answer": None, "answered_by": None, "delivered_at": None}
    _qsave(q)
    return {"status": "asked", "question_id": qid,
            "next": "run `review_queue wait` as usual: the answer arrives as an item of kind "
                    "`answer`. If none comes in %d minutes you will get it as expired: then submit "
                    "your best verdict, or --skip with the reason needs-answer." % (QUESTION_TTL // 60)}


def _ticket_of_judge(item_id):
    did = item_id.split("-", 1)[1].rsplit("-c", 1)[0]
    rec = store.read("conversation_dispatch", did) or {}
    return rec.get("jira_key") or ""


def answer(qid, text, *, env=None, state_store=store):
    """The orchestrator's answer. Only the orchestrator session may give one."""
    from agent.state import teams
    env = os.environ if env is None else env
    orch = (state_store.active_role_session(teams.ORCHESTRATOR_ID) or {}).get("session_id")
    if not orch or env.get("CLAUDE_CODE_SESSION_ID") != orch:
        raise Refused("not-orchestrator", "only the orchestrator answers a reviewer question")
    q = _read(_qpath(qid))
    if not q:
        raise Refused("question-not-found", qid)
    if q["answered_at"] is not None:
        raise Refused("already-answered", qid)
    if not (text or "").strip():
        raise Refused("answer-required", "an empty answer helps nobody")
    q.update(answer=text.strip()[:ANSWER_LIMIT], answered_at=time.time(), answered_by="orchestrator")
    _qsave(q)
    return {"status": "answered", "question_id": qid, "ticket": q["ticket"]}


def questions_for_inbox():
    """Unanswered questions the orchestrator has not been shown yet."""
    return [q for q in questions() if q["answered_at"] is None and q["collected_at"] is None
            and time.time() - q["asked_at"] < QUESTION_TTL]


def mark_collected(qid):
    q = _read(_qpath(qid))
    if q and q["collected_at"] is None:
        q["collected_at"] = time.time()
        _qsave(q)


def next_answer(now=None):
    """An answer (or an expiry) for a question THIS thread asked, delivered once. While a question
    is open the claim on its item is kept alive so the work is not offered to someone else."""
    now = now or time.time()
    me = _thread()
    for q in questions():
        if q["thread"] != me or q["delivered_at"] is not None:
            continue
        expired = q["answered_at"] is None and now - q["asked_at"] >= QUESTION_TTL
        if q["answered_at"] is None and not expired:
            cpath = os.path.join(_dir("claims"), _safe(q["item_id"]))
            claim_rec = _read(cpath)
            if claim_rec and claim_rec.get("thread") == me:
                claim_rec["at"] = now
                with open(cpath, "w", encoding="utf-8") as fh:
                    json.dump(claim_rec, fh)
            continue
        q["delivered_at"] = now
        _qsave(q)
        return {"kind": "answer", "question_id": q["qid"], "item_id": q["item_id"],
                "ticket": q["ticket"], "question": q["question"], "answer": q["answer"],
                "expired": expired,
                "next": ("Continue the SAME item with this answer, then submit." if not expired else
                         "No answer arrived. Submit your best verdict on %s, or --skip the check with "
                         "the reason needs-answer; never guess a PASS." % q["item_id"]),
                "at": ""}
    return None


# ------------------------------------------------------------------ waking the reviewer
# A Codex Desktop conversation cannot be woken from outside, so a reviewer that lives there only
# works while its own wait loop runs: it dies with a restart, a sleep, a closed app or empty
# tokens, and the whole flow stands still (CEO 2026-10-17). The alternative is a HEADLESS reviewer:
# a Codex thread Thebes itself owns (codex_runtime), woken with one turn per review item and idle,
# at zero tokens, in between. `reviewer.json` says which kind is in use.
RENUDGE_SECONDS = 30 * 60
TURN_STALE_SECONDS = 20 * 60


def _reviewer_path():
    return os.path.join(store.RUNTIME, "review", "reviewer.json")


def reviewer_config():
    return _read(_reviewer_path()) or {"mode": "desktop"}


def set_reviewer(mode, thread_id=None, *, state_store=store):
    """`desktop` (the reviewer runs its own wait loop) or `headless` (Thebes wakes `thread_id`)."""
    if mode not in ("desktop", "headless"):
        raise Refused("mode-invalid", "mode is desktop or headless")
    if mode == "headless":
        conv = state_store.read("codex_conversation", thread_id or "none")
        if not conv or conv.get("status") != "active":
            raise Refused("thread-not-registered", "%s is not an active conversation Thebes owns; "
                          "create it with codex_runtime new-conversation first" % thread_id)
    os.makedirs(os.path.dirname(_reviewer_path()), exist_ok=True)
    with open(_reviewer_path(), "w", encoding="utf-8") as fh:
        json.dump({"mode": mode, "thread_id": thread_id if mode == "headless" else None,
                   "at": time.time()}, fh)
    return {"status": "set", "mode": mode, "thread_id": thread_id}


def _age(stamp, now):
    import calendar
    try:
        return now - calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


def _thread_busy(thread_id, state_store, now):
    for ev in state_store.read_all("codex_turn_event"):
        if ev.get("thread_id") != thread_id or ev.get("status") not in ("queued", "running"):
            continue
        if _age(ev.get("updated_at") or ev.get("created_at"), now) < TURN_STALE_SECONDS:
            return True                      # a dead "running" turn stops counting after 20 min
    return False


def nudge_text(item):
    return "\n".join([
        "THEBES_REVIEW_REQUEST (you are the Thebes reviewer; this turn is for ONE review item).",
        "Read agent/REVIEWER.md and follow it, with this change: do NOT run `review_queue wait` "
        "(it would hold this turn). Run `python3 -m agent.execution.review_queue next`, review "
        "exactly the item it returns, submit your verdict with `review_queue submit`, then END the "
        "turn with one line saying what you decided. If `next` returns empty, say so and end the turn.",
        "Waiting: %s %s" % (item.get("kind"), item.get("ticket")),
    ])


def nudge(*, state_store=store, jira=None, now=None, enqueue_fn=None, launcher=None):
    """Zero tokens until there is work: wake the headless reviewer once per waiting review item.
    Does nothing for a Desktop reviewer (which polls by itself) or when Codex is not the channel.
    Never raises; the Ready dispatcher calls it every tick."""
    now = now or time.time()
    try:
        cfg = reviewer_config()
        if cfg.get("mode") != "headless" or get_channel() != "codex":
            return []
        thread = cfg.get("thread_id")
        if _thread_busy(thread, state_store, now):
            return []
        from agent.execution import codex_runtime
        for item in candidates(state_store, jira):
            if holder(item["item_id"]) or item.get("needs_browser"):
                continue                     # held, or a UI item only the Desktop reviewer can see
            marker = os.path.join(_dir("nudged"), _safe(item["item_id"]))
            try:
                last = float(open(marker).read())
            except (OSError, ValueError):
                last = None
            if last is not None and now - last < RENUDGE_SECONDS:
                continue
            (enqueue_fn or codex_runtime.enqueue)(
                thread, "alert", nudge_text(item), state_store=state_store,
                event_id="cevt-review-%s-%d" % (_safe(item["item_id"])[:60], int(now)))
            with open(marker, "w") as fh:
                fh.write(str(now))
            (launcher or codex_runtime._detach_drain)(thread)
            return [{"action": "review-nudged", "ticket": item["ticket"], "kind": item["kind"]}]
    except Exception as exc:                                 # noqa: BLE001
        return [{"action": "review-nudge-failed", "error": str(exc)[:200]}]
    return []


STALL_SECONDS = 15 * 60


def stalled(state_store=store, now=None):
    """Product items waiting for review longer than STALL_SECONDS with nobody holding them (the
    channel is probably out of tokens or closed). The orchestrator tells the CEO; it never
    switches the channel by itself."""
    import calendar
    now = now or time.time()
    out = []
    for item in judge_items(state_store):
        if is_done(item["item_id"]) or holder(item["item_id"]):
            continue
        try:
            age = now - calendar.timegm(time.strptime(item["at"], "%Y-%m-%dT%H:%M:%SZ"))
        except (TypeError, ValueError):
            continue
        if age >= STALL_SECONDS:
            out.append({"item_id": item["item_id"], "ticket": item["ticket"], "age_min": int(age / 60)})
    return out


WAKE_PROMPT = ("Reviewer wake: review work is waiting ({tickets}). Re-read agent/REVIEWER.md if you "
               "lost it, then run `python3 -m agent.execution.review_queue wait --timeout 300` and keep "
               "running it: review each item it returns, submit, and wait again. Do not stop on your own.")


def wake_prompt(tickets):
    """The prompt that restarts a Reviewer conversation's loop. The orchestrator uses it; it is
    never handed to the CEO (constitution 2026-10-27)."""
    return WAKE_PROMPT.format(tickets=", ".join(tickets) or "see review_queue status")


def notify_stalled(*, state_store=store, now=None, runner=None, wake=None):
    """Once per stalled review, wake the reviewer of the ACTIVE channel — never the CEO
    (constitution 2026-10-27: no notification, no wake prompt for him to paste). Claude channel:
    Edfu is re-dispatched its loop. Codex channel: a Desktop conversation cannot be woken from
    outside, so the item waits in the orchestrator's inbox (review_stalled), which may switch the
    channel to claude itself. Never raises; `runner` is unused and kept for old callers."""
    late = []
    try:
        for i in stalled(state_store, now):
            m = os.path.join(_dir("stalled-notified"), _safe(i["item_id"]))
            if not os.path.exists(m):
                late.append((i, m))
        if not late:
            return []
        tickets = [i["ticket"] for i, _ in late]
        woke = None
        if get_channel() == "claude":
            woke = (wake or _wake_edfu)("claude", state_store)
        for _, m in late:
            with open(m, "w") as fh:
                fh.write("1")
        return [{"action": "review-stalled-woke-reviewer", "channel": get_channel(),
                 "tickets": tickets, "wake": woke}]
    except Exception:                                      # noqa: BLE001
        return []


def mark_stalled_alerted(item_id):
    with open(os.path.join(_dir("stalled-alerted"), _safe(item_id)), "w") as fh:
        fh.write("1")


def stalled_unalerted(state_store=store, now=None):
    return [i for i in stalled(state_store, now)
            if not os.path.exists(os.path.join(_dir("stalled-alerted"), _safe(i["item_id"])))]


def status(state_store=store):
    items = candidates(state_store, with_qa=False)
    claims = {}
    for name in os.listdir(_dir("claims")):
        c = _read(os.path.join(_dir("claims"), name)) or {}
        claims[c.get("item_id")] = c
    return {"channel": get_channel(), "waiting_judge_items": [i["item_id"] for i in items],
            "no_commit": sorted(i["item_id"] for i in judge_items(state_store) if not i.get("commit_resolved")),
            "review_time": _review_times(),
            "claimed": {k: {"thread": v.get("thread"), "age_s": int(time.time() - v.get("at", 0))}
                        for k, v in claims.items() if k and not is_done(k)}}


def app(item_id, *, stop=False, listing=False):
    """Run (or stop) the claimed item's commit on the web: agent/execution/review_app.py."""
    from agent.execution import review_app
    if listing or not item_id:
        return review_app.list_running()
    meta = claim_record(item_id).get("meta") or {}
    ticket = meta.get("ticket") or (item_id[len("qa-"):].split("@")[0] if item_id.startswith("qa-")
                                    else item_id if item_id.upper().startswith("KAN-") else None)
    if stop:
        if not ticket:
            raise Refused("unknown-item", "name a claimed item_id or a ticket key")
        return review_app.stop(ticket)
    if holder(item_id) != _thread():
        raise Refused("not-your-claim", "run `wait` or `next` first: only the reviewer holding %s "
                                        "runs its app" % item_id)
    try:
        return review_app.start(meta)
    except RuntimeError as exc:
        raise Refused("build-not-ready" if str(exc).startswith("build not ready") else "app-not-started",
                      str(exc))


def _review_times(limit=20):
    """Claim-to-verdict seconds of the latest verdicts: is review becoming the bottleneck?"""
    done = []
    for name in os.listdir(_dir("done")):
        rec = _read(os.path.join(_dir("done"), name)) or {}
        if rec.get("claimed_at") and rec.get("at") and "skipped" not in (rec.get("outcome") or {}):
            done.append((rec["at"], rec["at"] - rec["claimed_at"]))
    last = [d for _, d in sorted(done)[-limit:]]
    return {"verdicts_timed": len(last),
            "avg_minutes": round(sum(last) / len(last) / 60, 1) if last else None,
            "max_minutes": round(max(last) / 60, 1) if last else None}


def _pairs(values):
    out = {}
    for v in values or []:
        cid, _, why = v.partition(":")
        out[cid.strip()] = why.strip() or "no reason given"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.review_queue", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait"); w.add_argument("--timeout", type=int, default=300)
    sub.add_parser("next")
    sub.add_parser("status")
    ap_ = sub.add_parser("app", help="build and run the item's commit on the web for review")
    ap_.add_argument("item_id", nargs="?")
    ap_.add_argument("--stop", action="store_true", help="stop it and remove its folder")
    ap_.add_argument("--list", action="store_true", help="what is running")
    ro = sub.add_parser("reopen"); ro.add_argument("dispatch_id")
    aq = sub.add_parser("ask", help="the reviewer is stuck: put ONE question to the orchestrator")
    aq.add_argument("item_id"); aq.add_argument("--question", required=True)
    an = sub.add_parser("answer", help="orchestrator only: answer a reviewer question")
    an.add_argument("question_id"); an.add_argument("--text", required=True)
    sub.add_parser("questions")
    rv = sub.add_parser("reviewer", help="show or set how the Codex reviewer is woken: "
                        "desktop (it polls) or headless (a Thebes-owned thread, woken per item)")
    rv.add_argument("mode", nargs="?", choices=("desktop", "headless")); rv.add_argument("--thread")
    sub.add_parser("nudge", help="wake the headless reviewer now if an item waits (the dispatcher does this every tick)")
    ch = sub.add_parser("channel", help="show the review channel, or (orchestrator, on the CEO's "
                        "explicit order) switch it to codex or claude")
    ch.add_argument("to", nargs="?", choices=CHANNELS)
    ch.add_argument("--by", default="", help="the CEO's words ordering the switch")
    s = sub.add_parser("submit"); s.add_argument("item_id")
    s.add_argument("--pass", dest="passed", action="append", default=[])
    s.add_argument("--fail", dest="failed", action="append", default=[])
    s.add_argument("--skip", dest="skipped", action="append", default=[])
    s.add_argument("--env", dest="env", action="append", default=[],
                   help="C<n>:why the REVIEW ENVIRONMENT could not run it (blank canvas, no simulator, "
                        "no clipboard): no verdict, no fix cycle spent")
    s.add_argument("--verdict"); s.add_argument("--reason", default="")
    s.add_argument("--evidence", default="")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "wait":
            item = wait(ns.timeout)
            print(json.dumps(item if item else {"status": "timeout", "waited_s": ns.timeout},
                             indent=2, ensure_ascii=False))
            return 0 if (item and not item.get("standby")) else 3
        if ns.cmd == "next":
            item = next_item()
            print(json.dumps(item if item else {"status": "empty"}, indent=2, ensure_ascii=False))
            return 0
        if ns.cmd == "status":
            print(json.dumps(status(), indent=2))
            return 0
        if ns.cmd == "reviewer":
            print(json.dumps(set_reviewer(ns.mode, ns.thread) if ns.mode else reviewer_config(), indent=2))
            return 0
        if ns.cmd == "nudge":
            print(json.dumps(nudge(), indent=2))
            return 0
        if ns.cmd == "channel":
            out = (set_channel(ns.to, ns.by) if ns.to else {"channel": get_channel()})
            print(json.dumps(out, indent=2))
            return 0
        if ns.cmd == "ask":
            print(json.dumps(ask(ns.item_id, ns.question), indent=2))
            return 0
        if ns.cmd == "answer":
            print(json.dumps(answer(ns.question_id, ns.text), indent=2))
            return 0
        if ns.cmd == "questions":
            print(json.dumps([{k: q[k] for k in ("qid", "ticket", "question", "answered_at")}
                              for q in questions()], indent=2))
            return 0
        if ns.cmd == "reopen":
            print(json.dumps(reopen(ns.dispatch_id), indent=2))
            return 0
        if ns.cmd == "app":
            print(json.dumps(app(ns.item_id, stop=ns.stop, listing=ns.list), indent=2, default=str))
            return 0
        if ns.item_id.startswith("qa-"):
            out = submit_qa(ns.item_id, ns.verdict, ns.reason, ns.evidence)
        else:
            out = submit_judge(ns.item_id, [p.strip() for p in ns.passed], _pairs(ns.failed),
                               _pairs(ns.skipped), ns.evidence, environment=_pairs(ns.env))
    except (Refused, __import__("agent.execution.verify", fromlist=["Refused"]).Refused) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
