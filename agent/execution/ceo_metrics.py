"""CEO metrics (autonomy constitution, D-043 section 7, 2026-10-27).

The constitution's target is ZERO messages to the CEO outside money, merging into main and
sending outside the company. This counts, per UTC day, what actually happened:

    reached_ceo        decision requests escalated, by reason ("ceo-only:<category>" is legitimate;
                       anything else is a defect to fix in agent/state/registry/autonomy.json)
    held_for_orch      requests that would once have reached the CEO and went to the orchestrator
    stuck              repeat loops the repeat guard cut
    sql_hook           execute_sql answers by decision (any "ask" for Memphis is a defect)
    policy_hook        permission prompts answered by code, by decision
    live               tickets that went Done because they were live, and the median minutes
                       from review PASS to live

    python3 -m agent.execution.ceo_metrics [--days 7]
"""
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402


def _lines(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def _day(stamp):
    return (stamp or "")[:10]


def _epoch(stamp):
    try:
        import calendar
        return calendar.timegm(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def collect(days=7, *, state_store=store, now=None):
    now = now or time.time()
    keep = {time.strftime("%Y-%m-%d", time.gmtime(now - i * 86400)) for i in range(days)}
    out = defaultdict(lambda: {"reached_ceo": Counter(), "held_for_orch": 0, "stuck": 0,
                               "sql_hook": Counter(), "policy_hook": Counter(),
                               "live": 0, "_to_live": []})
    for r in state_store.read_all("decision_request"):
        d = _day(r.get("created_at"))
        if d not in keep:
            continue
        reason = r.get("escalation_reason") or ""
        if r.get("status") == "escalated":
            out[d]["reached_ceo"][reason or "unknown"] += 1
        if reason.startswith("held-for-orchestrator"):
            out[d]["held_for_orch"] += 1
        if r.get("status") == "stuck" or r.get("route") == "stuck":
            out[d]["stuck"] += 1
    for e in _lines(os.path.join(state_store.RUNTIME, "sql-hook.log")):
        d = _day(e.get("at"))
        if d in keep:
            out[d]["sql_hook"]["%s:%s" % (e.get("lane") or "?", e.get("decision"))] += 1
    for e in _lines(os.path.join(state_store.RUNTIME, "policy-hook.log")):
        d = _day(e.get("at"))
        if d in keep:
            out[d]["policy_hook"][e.get("decision")] += 1
    for e in _lines(os.path.join(state_store.RUNTIME, "review", "live-done.jsonl")):
        d = _day(e.get("at"))
        if d in keep:
            out[d]["live"] += 1
            done, passed = _epoch(e.get("at")), e.get("passed_at")
            if done and passed:
                out[d]["_to_live"].append(max(0, (done - passed) / 60))
    report = {}
    for d in sorted(out, reverse=True):
        v = out[d]
        legit = sum(n for k, n in v["reached_ceo"].items() if k.startswith("ceo-only:"))
        report[d] = {"reached_ceo": dict(v["reached_ceo"]),
                     "reached_ceo_outside_the_three": sum(v["reached_ceo"].values()) - legit,
                     "held_for_orchestrator": v["held_for_orch"], "loops_cut": v["stuck"],
                     "sql_hook": dict(v["sql_hook"]), "memphis_sql_asks": v["sql_hook"].get("ops:ask", 0),
                     "permission_prompts_answered": dict(v["policy_hook"]),
                     "done_live": v["live"],
                     "median_min_pass_to_live": (round(statistics.median(v["_to_live"]))
                                                 if v["_to_live"] else None)}
    return report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
    print(json.dumps(collect(days), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
