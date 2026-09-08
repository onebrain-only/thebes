#!/usr/bin/env python3
"""One Brain — Agent View.

A live, READ-ONLY operational view of the orchestration system Thebes actually runs:
work, seats, ownership, capability queues, dependencies, validation, contention,
interventions and capacity — every one of them derived from the canonical Wave 6
sources through `agent/state/view.py`, and none of them derived here.

WHAT THIS SERVER IS

  A window. It serves GET and nothing else. There is no claim, wake, release, STOP,
  HOLD, FREEZE, RESUME, Jira transition, reviewer assignment or seat creation
  anywhere in this file or in the page it serves, and there is no code path that
  writes to Persistent State.

WHAT IT USED TO BE, AND WHY THAT CHANGED

  Until Wave 7 this file read Claude Code session transcripts and rendered a graph of
  one chat session. It touched no orchestration state at all: no tasks, no ownership,
  no queues, no dependencies, no interventions. What it showed instead was invented —
  a seat's "thinking" or "executing" state was computed from how far a transcript run
  had progressed (`p < 0.24 ? thinking : exec`), an idle tile counted `30 - awake`
  against a roster of 26, and the legend still listed Team Leads, a tier with no live
  seats since Wave 6. None of that was observed; all of it read as fact.

  So the fabrications are gone rather than re-pointed. Session transcripts survive in
  one clearly-labelled advisory panel, because a dispatch really did happen and that
  is worth seeing — but it is labelled SESSION DISPATCH ACTIVITY, not execution, and
  it never contradicts Persistent State.

    python3 agent/scripts/flow.py            # then open http://localhost:7373
    python3 agent/scripts/flow.py --port 8080
"""
import argparse, csv, json, os, re, sys, time, collections
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECTS = os.path.expanduser("~/.claude/projects")

sys.path.insert(0, os.path.join(ROOT, "agent", "state"))
import view                                             # noqa: E402


# ---------------------------------------------------------------- session activity
#
# ADVISORY ONLY. Everything below this line describes what a Claude Code session did,
# never what the orchestration system knows. It cannot establish ownership,
# claimability, lifecycle, review status, progress or availability.

def project_dir():
    """The transcript directory Claude Code uses for this workspace."""
    slug = ROOT.replace("/", "-")
    for cand in (slug, slug.lstrip("-")):
        p = os.path.join(PROJECTS, cand)
        if os.path.isdir(p):
            return p
    if not os.path.isdir(PROJECTS):
        return None
    dirs = [os.path.join(PROJECTS, d) for d in os.listdir(PROJECTS)]
    dirs = [d for d in dirs if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def sessions():
    d = project_dir()
    if not d:
        return []
    out = []
    for fn in os.listdir(d):
        if not fn.endswith(".jsonl"):
            continue
        p = os.path.join(d, fn)
        try:
            sz = os.path.getsize(p)
            if sz < 2000:
                continue
            out.append({"id": fn[:-6], "path": p, "size": sz, "mtime": os.path.getmtime(p)})
        except OSError:
            continue
    return sorted(out, key=lambda s: s["mtime"], reverse=True)


def dispatches(path, limit=40):
    """Agent dispatches from one transcript.

    `subagent_type` is the reliable identifier — it is the seat actually asked for.
    The instance `name` beside it is a free-form label (`backend-4-surfaces`,
    `exec-kan153`) and is shown as a label, never treated as a seat id.

    A dispatch is SESSION ACTIVITY. It is not evidence that a Wave 6 claim, wake or
    lifecycle transition occurred — only Persistent State proves that.
    """
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    x = json.loads(line)
                except ValueError:
                    continue
                ts = x.get("timestamp") or ""
                content = ((x.get("message") or {}).get("content")
                           if isinstance(x.get("message"), dict) else None)
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    if b.get("name") != "Agent":
                        continue
                    i = b.get("input") or {}
                    out.append({"subagent_type": i.get("subagent_type"),
                                "label": i.get("name") or None,
                                "at": ts,
                                "description": (i.get("description") or "")[:120]})
    except OSError:
        return []
    return out[-limit:]


def session_activity():
    ses = sessions()
    if not ses:
        return {"present": False, "state": "NO SESSION ACTIVITY OBSERVED",
                "sessions": [], "dispatches": []}
    pick = ses[0]
    d = dispatches(pick["path"])
    return {
        "present": bool(d),
        "state": "SESSION DISPATCH ACTIVITY" if d else "NO SESSION ACTIVITY OBSERVED",
        "advisory": True,
        "active_session": pick["id"],
        "session_live": (time.time() - pick["mtime"]) < 120,
        "sessions": [{"id": s["id"], "mtime": s["mtime"]} for s in ses[:8]],
        "dispatches": list(reversed(d)),
        "note": "Advisory. A dispatch is session activity, not proof of a Wave 6 "
                "claim, wake or lifecycle transition.",
    }


# ---------------------------------------------------------------- payload

def state():
    """The whole read-only payload: orchestration facts + advisory session activity."""
    payload = view.build()
    payload["session_activity"] = session_activity()
    payload["served_at"] = time.time()
    return payload


def embed_json(obj):
    """Escape so the JSON can sit inside a <script> element without closing it."""
    s = json.dumps(obj)
    for ch, esc in ((chr(0x3c), "u003c"), (chr(0x3e), "u003e"), (chr(0x26), "u0026"),
                    (chr(0x2028), "u2028"), (chr(0x2029), "u2029")):
        s = s.replace(ch, "\\" + esc)
    return s


# ---------------------------------------------------------------- page

PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thebes — Agent View</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;padding:0;background:#06080a;color:#dfe7ec}
  *{box-sizing:border-box}
  body{font-family:Geist,system-ui,-apple-system,sans-serif;font-size:13px}
  .mono{font-family:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
  .panel{border:1px solid rgba(255,255,255,.07);border-radius:13px;
    background:linear-gradient(180deg,rgba(255,255,255,.038),rgba(255,255,255,.01));
    box-shadow:0 26px 64px -32px rgba(0,0,0,.92),inset 0 1px 0 rgba(255,255,255,.045);
    padding:14px 15px 15px}
  h2{margin:0 0 10px;font-size:10px;letter-spacing:.22em;text-transform:uppercase;
    color:oklch(0.72 0.03 220);font-weight:600}
  .grid{display:grid;gap:13px;padding:13px}
  .row{display:flex;align-items:center;gap:8px;padding:5px 0;
    border-bottom:1px solid rgba(255,255,255,.045)}
  .row:last-child{border-bottom:0}
  .tag{display:inline-block;padding:2px 7px;border-radius:5px;font-size:10px;
    letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}
  .k{color:oklch(0.62 0.02 220);font-size:11px}
  .v{color:#eaf1f5}
  .muted{color:oklch(0.56 0.02 220)}
  .warn{color:oklch(0.80 0.11 78)}
  .bad{color:oklch(0.72 0.15 25)}
  .good{color:oklch(0.80 0.11 148)}
  .own{color:oklch(0.86 0.13 195)}
  .empty{color:oklch(0.56 0.02 220);font-style:normal;letter-spacing:.1em;
    text-transform:uppercase;font-size:10px}
  a{color:oklch(0.80 0.10 200);text-decoration:none}
  .scroll{max-height:340px;overflow-y:auto}
  table{border-collapse:collapse;width:100%}
  td,th{text-align:left;padding:4px 8px 4px 0;font-size:11.5px;vertical-align:top}
  th{color:oklch(0.62 0.02 220);font-weight:500;font-size:10px;letter-spacing:.12em;
    text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,.08)}
  tr.item{border-bottom:1px solid rgba(255,255,255,.04)}
  code{font-family:"Geist Mono",monospace;font-size:11px}
</style></head><body>

<div style="display:flex;align-items:center;gap:14px;padding:13px 15px 0">
  <div>
    <div style="font-size:14px;font-weight:600;letter-spacing:.26em;text-transform:uppercase">Thebes — Agent View</div>
    <div class="k">Observability. Not authority. Read-only: this page issues no state-changing request.</div>
  </div>
  <div style="flex:1"></div>
  <div id="hdr" class="mono k" style="text-align:right"></div>
</div>

<div class="grid" style="grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)">
  <div class="panel"><h2>Orchestrator</h2><div id="orch"></div></div>
  <div class="panel"><h2>Active ownership</h2><div id="own"></div></div>
</div>

<div class="grid" style="grid-template-columns:minmax(0,1fr)">
  <div class="panel"><h2>Work items</h2><div id="items" class="scroll"></div></div>
</div>

<div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)">
  <div class="panel"><h2>Capability queues</h2><div id="queues" class="scroll"></div></div>
  <div class="panel"><h2>Roster</h2><div id="seats" class="scroll"></div></div>
</div>

<div class="grid" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)">
  <div class="panel"><h2>Dependencies</h2><div id="deps"></div></div>
  <div class="panel"><h2>Interventions</h2><div id="ivs"></div></div>
  <div class="panel"><h2>Capacity</h2><div id="cap" class="scroll"></div></div>
</div>

<div class="grid" style="grid-template-columns:minmax(0,1fr)">
  <div class="panel"><h2>Session activity — advisory</h2><div id="sess"></div></div>
</div>

<script>
var DATA = __STATE_JSON__;

function el(tag, style, cls, text) {
  var e = document.createElement(tag);
  if (style) e.setAttribute("style", style);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function tag(text, color) {
  return el("span", "background:" + color + "22;color:" + color + ";border:1px solid " +
            color + "44", "tag mono", text);
}
var C = {
  live: "oklch(0.80 0.11 148)", stale: "oklch(0.80 0.11 78)",
  gone: "oklch(0.72 0.15 25)", own: "oklch(0.86 0.13 195)",
  idle: "oklch(0.58 0.02 220)", warn: "oklch(0.80 0.11 78)",
  info: "oklch(0.72 0.09 265)"
};
function freshColor(f) {
  return f === "LIVE" ? C.live : f === "STALE" ? C.stale : C.gone;
}
function emptyLine(host, text) { host.appendChild(el("div", null, "empty", text)); }

/* ---------------------------------------------------------------- header */
function header() {
  var m = DATA.meta;
  document.getElementById("hdr").innerHTML =
    "schema v" + m.state_schema + " &middot; " + m.task_count + " tasks &middot; " +
    m.dependency_count + " deps &middot; " + m.roster_count + " seats / " +
    m.generated_agent_count + " agents &middot; window " +
    m.freshness_window_seconds + "s &middot; " + m.view_generated_at;
}

/* ---------------------------------------------------------------- orchestrator */
function orchestrator() {
  var h = document.getElementById("orch"), o = DATA.orchestrator;
  var r = el("div", "display:flex;align-items:center;gap:9px;margin-bottom:7px");
  r.appendChild(el("span", "font-weight:600;font-size:14px", null, o.name));
  r.appendChild(tag("NOT A SEAT", C.info));
  r.appendChild(tag("OWNS NOTHING", C.idle));
  h.appendChild(r);
  h.appendChild(el("div", "margin-bottom:6px", "k", o.role));
  h.appendChild(el("div", "margin-bottom:8px", "k muted", o.note));
  if (o.system_freeze) {
    var f = el("div", "margin-top:6px");
    f.appendChild(tag("FREEZE — SYSTEM SCOPE", C.gone));
    f.appendChild(el("div", "margin-top:4px", "k", o.system_freeze.reason_ref));
    h.appendChild(f);
  } else {
    emptyLine(h, "No system freeze");
  }
}

/* ---------------------------------------------------------------- ownership */
function ownership() {
  var h = document.getElementById("own"), o = DATA.ownership;
  if (o.empty_state) { emptyLine(h, o.empty_state); }
  Object.keys(o.by_work_item).sort().forEach(function (k) {
    var r = el("div", null, "row");
    r.appendChild(tag("OWNING", C.own));
    r.appendChild(el("code", "color:#eaf1f5", null, k));
    r.appendChild(el("span", null, "k", "→"));
    r.appendChild(el("span", "font-weight:500", "own", o.by_work_item[k]));
    var it = (DATA.work_items || []).filter(function (w) { return w.work_item_id === k; })[0];
    if (it) {
      /* The ITEM's lifecycle, labelled as the item's. Owning an item that sits in
         Review does not make the owner the reviewer. */
      r.appendChild(el("span", "margin-left:auto", "k",
        "ITEM LIFECYCLE: " + String(it.lifecycle.canonical || "—").toUpperCase()));
    }
    h.appendChild(r);
  });
  (o.inconsistencies || []).forEach(function (m) {
    h.appendChild(el("div", "margin-top:7px", "bad mono", m));
  });
  var rev = o.review_owners || {};
  var keys = Object.keys(rev);
  var line = el("div", "margin-top:9px", "k");
  line.textContent = keys.length
    ? "Review owners: " + keys.map(function (s) { return s + " → " + rev[s].join(", "); }).join(" · ")
    : "No exact review owner named on any item";
  h.appendChild(line);
}

/* ---------------------------------------------------------------- work items */
function items() {
  var h = document.getElementById("items");
  if (DATA.meta.empty_state) { emptyLine(h, DATA.meta.empty_state); return; }
  var t = el("table"), head = el("tr");
  ["item", "lifecycle", "jira", "route / review", "surfaces", "ownership", "claimability"]
    .forEach(function (c) { head.appendChild(el("th", null, null, c)); });
  t.appendChild(head);

  DATA.work_items.forEach(function (w) {
    var r = el("tr", null, "item");

    var c1 = el("td");
    c1.appendChild(el("div", "font-weight:600", "mono", w.work_item_id));
    c1.appendChild(el("div", null, "k", (w.product_id || "?") + " / " + (w.project_id || "?")));
    c1.appendChild(el("div", null, "k", "cap " + (w.execution_profile.required_capability || "—") +
      " · WE " + (w.execution_profile.work_effort == null ? "—" : w.execution_profile.work_effort)));
    /* Jira-only fields are named as unobserved rather than left blank. */
    c1.appendChild(el("div", null, "k muted", "title/due/AC: NOT OBSERVED"));
    r.appendChild(c1);

    var c2 = el("td");
    c2.appendChild(el("div", null, "v", String(w.lifecycle.canonical || "—").toUpperCase()));
    c2.appendChild(el("div", null, "k", w.lifecycle.jira_column || ""));
    r.appendChild(c2);

    var c3 = el("td");
    c3.appendChild(tag(w.lifecycle.freshness, freshColor(w.lifecycle.freshness)));
    c3.appendChild(el("div", "margin-top:3px", "k", w.lifecycle.jira_status_name || "—"));
    c3.appendChild(el("div", null, "k muted", w.lifecycle.observed_at || "no observation"));
    r.appendChild(c3);

    var c4 = el("td");
    c4.appendChild(el("div", null, "v", String(w.review.validation_route || "—").toUpperCase()));
    c4.appendChild(el("div", null, "k muted", "alternatives: " +
      w.review.available_routes.join(" | ").toUpperCase()));
    var ds = w.review.display_state;
    var bad = ds === "REVIEW STATE UNRECONCILED";
    var wait = ds === "WAITING FOR EXACT REVIEWER";
    c4.appendChild(el("div", "margin-top:3px", bad ? "bad" : wait ? "warn" : "k", ds));
    r.appendChild(c4);

    var c5 = el("td");
    var sc = w.surfaces.state === "UNASSESSED" ? C.warn : C.idle;
    c5.appendChild(tag(w.surfaces.state.replace("_", " "), sc));
    (w.surfaces.paths || []).slice(0, 3).forEach(function (p) {
      c5.appendChild(el("div", "word-break:break-all", "k muted", p));
    });
    c5.appendChild(el("div", "margin-top:3px", "k muted", w.surfaces.mechanism));
    r.appendChild(c5);

    var c6 = el("td");
    if (w.ownership.state === "OWNING") {
      c6.appendChild(tag("OWNING", C.own));
      c6.appendChild(el("div", "margin-top:3px", "own", w.ownership.seat_id));
      c6.appendChild(el("div", null, "k muted", w.ownership.claimed_at || ""));
      if (w.execution_reasons && w.execution_reasons.length) {
        c6.appendChild(el("div", "margin-top:3px", "bad mono",
          "continuation: " + w.execution_reasons.join(", ")));
      }
    } else {
      c6.appendChild(tag("UNOWNED", C.idle));
    }
    if (w.executor_evidence.length) {
      /* History, kept visually separate from ownership so an evidenced seat on an
         unowned item never reads as one currently executing it. */
      c6.appendChild(el("div", "margin-top:5px", "k muted", "history: " +
        w.executor_evidence.map(function (e) { return e.seat_id; }).join(", ")));
    }
    if (w.active_stop) c6.appendChild(tag("STOP", C.gone));
    r.appendChild(c6);

    var c7 = el("td");
    if (w.claimable) c7.appendChild(tag("CLAIMABLE", C.live));
    else w.claimability_reasons.forEach(function (x) {
      c7.appendChild(el("div", null, "k mono", x));
    });
    if (w.dependency_blocked) c7.appendChild(el("div", null, "warn mono", "blocked by " +
      w.blocked_by.join(", ")));
    r.appendChild(c7);

    t.appendChild(r);
  });
  h.appendChild(t);
}

/* ---------------------------------------------------------------- queues */
function queues() {
  var h = document.getElementById("queues");
  DATA.queues.forEach(function (q) {
    var box = el("div", "padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)");
    var top = el("div", "display:flex;align-items:center;gap:8px");
    top.appendChild(el("span", "font-weight:600", "mono", q.capability));
    if (q.hold) top.appendChild(tag("HOLD — CAPABILITY SCOPE", C.warn));
    top.appendChild(el("span", "margin-left:auto", "k",
      "eligible " + q.eligible_depth + " · claimable " + q.claimable_count +
      " · blocked " + q.blocked_count));
    box.appendChild(top);

    var s = el("div", "margin-top:3px", "k");
    s.textContent = "defined " + q.defined_seat_count + " · owning " +
      q.busy_seats.length + " · " + q.unowned_seat_label.toLowerCase() + " " +
      q.unowned_seats.length + (q.ceiling != null ? " · ceiling " + q.ceiling : "");
    box.appendChild(s);

    var hist = q.claimability_reason_histogram, ks = Object.keys(hist);
    if (ks.length) {
      var hb = el("div", "margin-top:4px;display:flex;flex-wrap:wrap;gap:4px");
      ks.forEach(function (k) { hb.appendChild(tag(k + " " + hist[k], C.idle)); });
      box.appendChild(hb);
    } else if (!q.blocked_count && !q.claimable_count) {
      box.appendChild(el("div", "margin-top:4px", "empty", "NOTHING CLAIMABLE"));
    }
    h.appendChild(box);
  });
}

/* ---------------------------------------------------------------- seats */
function seats() {
  var h = document.getElementById("seats");
  DATA.seats.forEach(function (s) {
    var r = el("div", "padding:6px 0;border-bottom:1px solid rgba(255,255,255,.045)");
    var top = el("div", "display:flex;align-items:center;gap:7px");
    top.appendChild(el("span", "font-weight:600;min-width:118px", "mono", s.seat_id));
    top.appendChild(el("span", "min-width:88px", "k", s.capability || "—"));
    if (s.ownership_state === "OWNING") {
      top.appendChild(tag("OWNING " + s.current_work_item, C.own));
    } else {
      top.appendChild(tag("UNOWNED", C.idle));
    }
    if (s.stop_overlay) top.appendChild(tag("STOP", C.gone));
    /* Never "available": nothing observes whether this binding resolves to a real
       agent in the caller's session. */
    top.appendChild(el("span", "margin-left:auto", "k muted",
      "dispatchability " + s.dispatchability));
    r.appendChild(top);

    var sub = [];
    if (s.owned_item_lifecycle) sub.push("ITEM LIFECYCLE: " + s.owned_item_lifecycle.toUpperCase());
    if (s.is_review_owner_of) sub.push("REVIEW OWNER: " + s.is_review_owner_of.join(", "));
    if (s.history_present) sub.push("history present");
    if (!s.generated_registry_present) sub.push("NO GENERATED AGENT");
    if (sub.length) r.appendChild(el("div", "margin-top:2px", "k muted", sub.join(" · ")));
    if (s.state_inconsistency) r.appendChild(el("div", null, "bad mono", s.state_inconsistency));
    h.appendChild(r);
  });
  var ret = DATA.history.retired_status_seats || [];
  var f = el("div", "margin-top:9px", "k muted");
  f.textContent = ret.length
    ? "Retired, history only (not live): " + ret.join(", ")
    : "No retired status history";
  h.appendChild(f);
}

/* ---------------------------------------------------------------- dependencies */
function deps() {
  var h = document.getElementById("deps");
  if (!DATA.dependencies.length) { emptyLine(h, "No dependencies recorded"); return; }
  var byProduct = {};
  DATA.dependencies.forEach(function (d) {
    (byProduct[d.product_id || "—"] = byProduct[d.product_id || "—"] || []).push(d);
  });
  Object.keys(byProduct).sort().forEach(function (p) {
    h.appendChild(el("div", "margin:4px 0 2px", "k", "product " + p));
    byProduct[p].forEach(function (d) {
      var r = el("div", null, "row");
      r.appendChild(el("code", null, null, d.source_work_item));
      r.appendChild(tag(d.relation, C.info));
      r.appendChild(el("code", null, null, d.target_work_item));
      r.appendChild(el("span", "margin-left:auto", d.target_blocked ? "warn" : "good",
        d.target_blocked ? "TARGET BLOCKED" : "not blocked"));
      h.appendChild(r);
      h.appendChild(el("div", "margin:-2px 0 4px", "k muted",
        "source lifecycle " + String(d.source_lifecycle || "UNKNOWN").toUpperCase() +
        " · clears on " + d.completion_condition + " · derived, never stored" +
        (d.cross_project ? " · cross-project" : "")));
    });
  });
}

/* ---------------------------------------------------------------- interventions */
function interventions() {
  var h = document.getElementById("ivs"), iv = DATA.interventions;
  if (iv.empty_state) emptyLine(h, iv.empty_state);
  iv.active.forEach(function (i) {
    var r = el("div", null, "row");
    r.appendChild(tag(i.kind.toUpperCase() + " — " + i.scope.toUpperCase() + " SCOPE",
      i.kind === "stop" ? C.gone : C.warn));
    r.appendChild(el("code", null, null, i.target || "system"));
    h.appendChild(r);
    h.appendChild(el("div", "margin:-2px 0 4px", "k muted", i.reason_ref || ""));
  });
  h.appendChild(el("div", "margin-top:8px", "k muted", iv.note));
  if (iv.cleared.length) {
    h.appendChild(el("div", "margin-top:6px", "k",
      "cleared history: " + iv.cleared.length + " (RESUME is a clearing operation, not a kind)"));
  }
}

/* ---------------------------------------------------------------- capacity */
function capacity() {
  var h = document.getElementById("cap");
  var t = el("table"), head = el("tr");
  ["capability", "defined", "owning", "no ownership", "claimable", "blocked", "WE", "ceiling"]
    .forEach(function (c) { head.appendChild(el("th", null, null, c)); });
  t.appendChild(head);
  DATA.capacity.forEach(function (c) {
    var r = el("tr", null, "item");
    [c.capability, c.defined_seats, c.busy_seats, c.seats_without_current_ownership,
     c.claimable_items, c.blocked_items, c.work_effort_total,
     c.ceiling == null ? "—" : c.ceiling]
      .forEach(function (v, i) {
        r.appendChild(el("td", null, i === 0 ? "mono" : "mono v", String(v)));
      });
    t.appendChild(r);
  });
  h.appendChild(t);
  h.appendChild(el("div", "margin-top:7px", "k muted",
    "A ceiling is a safety bound, not a forecast. Due-date pressure: NOT OBSERVED " +
    "(due_date lives only in Jira). No utilisation, scores, forecasting or token analytics."));
}

/* ---------------------------------------------------------------- session */
function sessionPanel() {
  var h = document.getElementById("sess"), s = DATA.session_activity;
  var t = DATA.telemetry;
  var head = el("div", "display:flex;align-items:center;gap:8px;margin-bottom:6px");
  head.appendChild(tag(s.state, C.info));
  head.appendChild(tag("ADVISORY — NOT EXECUTION", C.idle));
  head.appendChild(el("span", "margin-left:auto", "k",
    t.present ? t.count + " hook events · last " + t.last_at : t.state));
  h.appendChild(head);

  if (!s.dispatches.length) { emptyLine(h, "NO SESSION ACTIVITY OBSERVED"); }
  s.dispatches.slice(0, 12).forEach(function (d) {
    var r = el("div", null, "row");
    r.appendChild(el("code", "min-width:150px", null, d.subagent_type || "?"));
    /* The instance label is free-form and is NOT a canonical seat id. */
    r.appendChild(el("span", null, "k muted", d.label ? "label " + d.label : ""));
    r.appendChild(el("span", "margin-left:auto", "k", d.at || ""));
    h.appendChild(r);
  });
  h.appendChild(el("div", "margin-top:8px", "k muted",
    "Persistent State wins every conflict. Free-form agent_type / instance labels are " +
    "not canonical seat ids and are left UNCORRELATED. A dispatch here is not proof " +
    "of a claim, wake or lifecycle transition."));
}

header(); orchestrator(); ownership(); items(); queues(); seats(); deps();
interventions(); capacity(); sessionPanel();
</script></body></html>"""


# ---------------------------------------------------------------- server

class Handler(BaseHTTPRequestHandler):
    """GET only.

    There is deliberately no do_POST / do_PUT / do_PATCH / do_DELETE. Agent View has
    no authority to change orchestration state, and the absence of these methods is
    the enforcement, not a convention — `test_wave7.py` asserts it.
    """

    def log_message(self, *a):
        pass

    def _send(self, body, ctype, code=200):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        try:
            payload = state()
        except Exception as e:                           # never 500 into a blank page
            payload = {"error": str(e), "meta": {"empty_state": "VIEW UNAVAILABLE"}}
        if self.path.startswith("/api/state"):
            self._send(json.dumps(payload), "application/json")
            return
        self._send(PAGE.replace("__STATE_JSON__", embed_json(payload)),
                   "text/html; charset=utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7373)
    a = ap.parse_args()
    p = view.build()
    print("Thebes — Agent View (read-only)")
    print("  workspace   :", ROOT)
    print("  runtime     : %s tasks, %s deps, %s active interventions"
          % (p["meta"]["task_count"], p["meta"]["dependency_count"],
             p["meta"]["intervention_count"]))
    print("  roster      : %s seats, %s generated agents"
          % (p["meta"]["roster_count"], p["meta"]["generated_agent_count"]))
    print("  ownership   : %s active" % p["ownership"]["active_count"])
    print("  open        : http://localhost:%d" % a.port)
    print("  stop        : Ctrl-C")
    try:
        ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
