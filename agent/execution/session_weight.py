#!/usr/bin/env python3
"""How heavy is a team session, and compact it while the cache is still warm (CEO 2026-10-20).

Measured over 24 hours: team sessions carried 90k-540k tokens of context, and every wake after the
prompt cache had expired re-sent ALL of it at the full price. 13-23 cold rebuilds per session per
day added up to ~36 million tokens (Memphis alone 11M) before any work started. The cheapest moment
to shrink a session is right after it finished, while its cache is warm: the compaction reads the
context at the cached price, and every later wake then rebuilds only the small summary.

    python3 -m agent.execution.session_weight report      # read-only: context per session
    python3 -m agent.execution.session_weight compact     # one pass of the policy below

Policy (the watchdog runs it every few minutes, zero tokens to decide):
    a delivery team, with no open dispatch, not mid-turn, whose context is above COMPACT_ABOVE
    tokens and whose last turn ended less than WARM_SECONDS ago (or above COMPACT_COLD_ABOVE
    whatever its cache), and that was not compacted in the last COMPACT_EVERY seconds, gets `/compact <what to keep>`. While it runs, the team counts as
    busy (a marker) so no dispatch stops it half way.
The orchestrator is never compacted from here (its waiter and inbox are running): the CEO sends it
`/compact` himself when it is idle.
"""
import argparse
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import store, teams                                  # noqa: E402

COMPACT_ABOVE = 150_000
COMPACT_COLD_ABOVE = 300_000   # a huge session is worth shrinking even when its cache is cold:
                               # its next wake pays that read anyway, and every later turn is smaller
WARM_SECONDS = 45 * 60
COMPACT_EVERY = 3 * 3600
COMPACTING_SECONDS = 10 * 60
TAIL_BYTES = 3_000_000
KEEP = ("/compact Keep only what is needed to continue as this Thebes team: your team name and lane "
        "rules, the tickets you are working or just finished (key, branch, worktree path, last "
        "commit, what is left), decisions already taken and who took them, and any open question. "
        "Drop tool output, file contents, test logs and exploration.")


def transcript_path(session_id):
    hits = glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % session_id))
    return hits[0] if hits else None


def context_of(session_id):
    """{tokens, at} from the LAST assistant turn of the session's transcript, or None."""
    path = transcript_path(session_id)
    if not path:
        return None
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    import calendar
    for line in reversed(tail.splitlines()):
        if '"usage"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        u = (d.get("message") or {}).get("usage")
        if d.get("type") != "assistant" or not u:
            continue
        try:
            at = calendar.timegm(time.strptime((d.get("timestamp") or "")[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            at = 0
        return {"tokens": (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                           + u.get("cache_creation_input_tokens", 0)), "at": at, "path": path}
    return None


def _marker(sub, sid):
    d = os.path.join(store.RUNTIME, "compaction")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s-%s" % (sub, sid))


def _stamp(path):
    try:
        return float(open(path).read())
    except (OSError, ValueError):
        return 0.0


def compacting(session_id, now=None):
    """True while a compaction Thebes started is (presumably) still running."""
    return (now or time.time()) - _stamp(_marker("running", session_id)) < COMPACTING_SECONDS


def compact_idle(*, state_store=store, cli=None, now=None, context_fn=None, teams_mod=teams):
    """One pass of the policy. Returns the list of what it did. Never raises."""
    from agent.execution import conversation_dispatch as cd
    from agent.execution.claude_cli import ClaudeCli
    now = now or time.time()
    context_fn = context_fn or context_of
    done = []
    try:
        cli = cli or ClaudeCli()
        rows = cli.agents()
        for tid, entry in sorted(teams_mod.delivery_teams().items()):
            binding = state_store.active_role_session(tid)
            if not binding:
                continue
            sid = binding["session_id"]
            run = _marker("running", sid)
            row = cli.find_by_sid(rows, sid)
            if os.path.exists(run) and (row is None or row.get("state") != "working"):
                os.unlink(run)                                # the compaction turn ended
            if (row is None or row.get("state") == "working" or cd.open_work_for(sid, state_store)
                    or compacting(sid, now) or now - _stamp(_marker("last", sid)) < COMPACT_EVERY):
                continue
            ctx = context_fn(sid)
            if not ctx or ctx["tokens"] < COMPACT_ABOVE:
                continue
            if now - ctx["at"] > WARM_SECONDS and ctx["tokens"] < COMPACT_COLD_ABOVE:
                continue
            with open(run, "w") as fh:
                fh.write(str(now))
            with open(_marker("last", sid), "w") as fh:
                fh.write(str(now))
            try:
                cli.stop(sid[:8])
                if not cli.wait_stopped(sid, 30, pid=row.get("pid")):
                    raise RuntimeError("session did not stop in 30s")
                cli.bg_resume(sid, KEEP, binding["stable_home"])
                done.append({"action": "compact-started", "team": tid, "tokens": ctx["tokens"]})
            except Exception as exc:                          # noqa: BLE001
                os.unlink(run) if os.path.exists(run) else None
                done.append({"action": "compact-failed", "team": tid, "error": str(exc)[:160]})
    except Exception as exc:                                  # noqa: BLE001
        done.append({"action": "compact-pass-failed", "error": str(exc)[:160]})
    return done


def report(state_store=store):
    rows = []
    for tid, entry in sorted(teams.read().items(), key=lambda kv: kv[1]["number"]):
        b = state_store.active_role_session(tid)
        c = context_of(b["session_id"]) if b else None
        rows.append({"team": tid, "tokens": (c or {}).get("tokens"),
                     "idle_min": int((time.time() - c["at"]) / 60) if c and c["at"] else None,
                     "last_compacted_min_ago": (int((time.time() - _stamp(_marker("last", b["session_id"]))) / 60)
                                                if b and _stamp(_marker("last", b["session_id"])) else None)})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.session_weight", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("report", "compact"))
    ns = ap.parse_args(argv)
    print(json.dumps(report() if ns.cmd == "report" else compact_idle(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
