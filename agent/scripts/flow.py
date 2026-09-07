#!/usr/bin/env python3
"""
One Brain — live agent flow.

Reads Claude Code session transcripts and the local agent roster, and serves a
live node graph of the company actually working: which seat was dispatched, what
it ran, what came back, and what is in flight right now.

Standard library only. No install step.

    python3 agent/scripts/flow.py            # then open http://localhost:7373
    python3 agent/scripts/flow.py --port 8080
"""
import argparse, csv, json, os, re, sys, time, collections
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECTS = os.path.expanduser("~/.claude/projects")


def project_dir():
    """The transcript directory Claude Code uses for this workspace."""
    slug = ROOT.replace("/", "-")
    for cand in (slug, slug.lstrip("-")):
        p = os.path.join(PROJECTS, cand)
        if os.path.isdir(p):
            return p
    # fall back to the most recently written project dir
    if not os.path.isdir(PROJECTS):
        return None
    dirs = [os.path.join(PROJECTS, d) for d in os.listdir(PROJECTS)]
    dirs = [d for d in dirs if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


# ---------------------------------------------------------------- roster

def naming():
    """Seat -> identity, read from agent/NAMING.csv.

    The CSV is the single source for the Egyptian name, glyph and lore. This
    file used to carry a second copy of that data inside the page, keyed to
    seat slugs that no longer exist; two maps of the same thing is how they
    came to disagree.
    """
    out = {}
    path = os.path.join(ROOT, "agent", "NAMING.csv")
    if not os.path.exists(path):
        return out
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                seat = (row.get("Seat") or "").strip()
                if not seat or seat == "\u2014":
                    continue
                out[seat] = {
                    "deity": re.sub(r"^[^(]*\(|\)$", "", (row.get("Given Name (Arabic)") or "").strip()).strip()
                             or (row.get("Code Name") or seat).strip(),
                    "glyph": (row.get("Hieroglyphs") or "").strip(),
                    "lore": (row.get("Ancient Pharaonic Lore") or "").strip(),
                }
    except Exception:
        return {}
    return out


def roster():
    """Every seat with a binding: tier, identity, and whether it has logged work.

    The binding directory is the roster. Nothing here is a fixed list, so a
    seat added or renamed in .claude/bindings/ appears without editing code.
    """
    seats = {}
    ident = naming()
    bind = os.path.join(ROOT, ".claude", "bindings")
    if not os.path.isdir(bind):
        return seats
    for fn in sorted(os.listdir(bind)):
        if not fn.endswith(".yml"):
            continue
        name = fn[:-4]
        model = effort = "—"
        for line in open(os.path.join(bind, fn), encoding="utf-8", errors="replace"):
            if line.startswith("model:"):
                model = line.split(":", 1)[1].strip()
            elif line.startswith("effort:"):
                effort = line.split(":", 1)[1].strip()
        st = os.path.join(ROOT, "agent", "status", name + ".md")
        logged = False
        if os.path.exists(st):
            logged = "_No entries yet._" not in open(st, encoding="utf-8", errors="replace").read()
        lvl = level_of(name)
        idn = ident.get(name, {})
        seats[name] = {"name": name, "model": model, "effort": effort, "logged": logged,
                       "level": lvl, "group": GROUP_OF.get(lvl, "DEVELOPERS"),
                       "deity": idn.get("deity", name), "glyph": idn.get("glyph", ""),
                       "lore": idn.get("lore", "")}
    return seats


GROUP_OF = {"company": "COMPANY", "product": "PRODUCT",
            "project": "PROJECT", "developer": "DEVELOPERS"}


def level_of(n):
    if n in ("cto", "cpo", "cxo", "analyst"):
        return "company"
    if n in ("pm", "devops", "content-manager"):
        return "product"
    if n == "po" or n == "qa" or n.startswith("team-lead"):
        return "project"
    return "developer"


# ---------------------------------------------------------------- transcript

TOOL_SHORT = {"mcp__atlassian__": "jira:", "mcp__supabase__": "db:", "mcp__github-dabbler__": "gh:"}


def shorten(tool):
    for pre, rep in TOOL_SHORT.items():
        if tool.startswith(pre):
            return rep + tool[len(pre):]
    return tool


def parse(path):
    """Flatten one transcript into events, dispatches and a file-attention map."""
    events, dispatches, messages = [], [], []
    files = collections.Counter()
    tools = collections.Counter()
    use = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "think": 0, "msgs": 0}
    model_seen = collections.Counter()
    turns = 0
    first = last = None

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue

            ts = d.get("timestamp")
            if ts:
                first = first or ts
                last = ts

            typ = d.get("type")
            msg = d.get("message") or {}
            content = msg.get("content")

            u = msg.get("usage")
            if isinstance(u, dict):
                use["msgs"] += 1
                use["in"] += u.get("input_tokens", 0) or 0
                use["out"] += u.get("output_tokens", 0) or 0
                use["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
                use["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
                det = u.get("output_tokens_details") or {}
                use["think"] += det.get("thinking_tokens", 0) or 0
                if msg.get("model"):
                    model_seen[msg["model"]] += 1

            if typ == "user" and isinstance(content, str) and content.strip():
                txt = content.strip()
                m = re.search(r'teammate_id="([^"]+)"', txt)
                if m or txt.startswith("Another Claude session sent a message"):
                    who = m.group(1) if m else "agent"
                    body = re.sub(r"<[^>]+>", " ", txt)
                    body = re.sub(r'^.*?(?:summary="([^"]*)")?\s*', lambda x: x.group(1) or "", body, count=1)
                    body = re.sub(r'\{"type":"[^"]*","from":"[^"]*"[^}]*', "returned", body)
                    events.append({"kind": "return", "ts": ts, "who": who,
                                   "text": " ".join(body.split())[:220]})
                    continue
                turns += 1
                events.append({"kind": "prompt", "ts": ts, "text": txt[:400]})
                continue

            if not isinstance(content, list):
                continue

            # some agent replies arrive as structured content rather than a plain
            # string; catch those too or the run never closes
            if typ == "user":
                joined = " ".join(b.get("text", "") for b in content
                                  if isinstance(b, dict) and b.get("type") == "text")
                m = re.search(r'teammate_id="([^"]+)"', joined)
                if not m:
                    m = re.search(r'"from"\s*:\s*"([^"]+)"', joined)
                if m:
                    body = re.sub(r"<[^>]+>", " ", joined)
                    body = re.sub(r'\{"type":"[^"]*","from":"[^"]*"[^}]*', "returned", body)
                    events.append({"kind": "return", "ts": ts, "who": m.group(1),
                                   "text": " ".join(body.split())[:220]})
                    continue

            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and typ == "assistant":
                    t = (b.get("text") or "").strip()
                    if t:
                        events.append({"kind": "say", "ts": ts, "text": t[:400]})
                elif b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    inp = b.get("input") or {}
                    tools[shorten(name)] += 1
                    if name == "Agent":
                        seat = inp.get("subagent_type", "?")
                        inst = inp.get("name") or seat
                        dispatches.append({"seat": seat, "instance": inst, "ts": ts,
                                           "desc": inp.get("description", ""),
                                           "model": inp.get("model", "")})
                        events.append({"kind": "dispatch", "ts": ts, "seat": seat, "instance": inst,
                                       "text": inp.get("description", "")})
                    elif name == "SendMessage":
                        messages.append({"to": inp.get("to", "?"), "ts": ts,
                                         "summary": inp.get("summary", "")})
                        events.append({"kind": "message", "ts": ts, "to": inp.get("to", "?"),
                                       "text": inp.get("summary", "")})
                    else:
                        label = ""
                        for k in ("file_path", "command", "pattern", "skill", "query", "url"):
                            if isinstance(inp.get(k), str):
                                label = inp[k]
                                break
                        fp = inp.get("file_path")
                        if isinstance(fp, str):
                            files[os.path.relpath(fp, ROOT) if fp.startswith(ROOT) else fp] += 1
                        if name == "Bash":
                            for m in re.findall(r"[\w][\w./-]{3,}\.(?:dart|md|yml|json|sql|py|ts|html)", label or ""):
                                if not m.startswith("-"):
                                    files[m.lstrip("./")] += 1
                        events.append({"kind": "tool", "ts": ts, "tool": shorten(name),
                                       "text": (label or "")[:200]})

    # pair each dispatch with the reply that came back, so a run has a real duration
    def secs(a, b):
        try:
            from datetime import datetime
            f = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
            return max(0, int((f(b) - f(a)).total_seconds()))
        except Exception:
            return None

    runs, open_by = [], {}
    order = 0
    for e in events:
        if e["kind"] == "dispatch":
            order += 1
            r = {"seat": e["seat"], "instance": e["instance"], "start": e["ts"], "end": None,
                 "desc": e.get("text", ""), "secs": None, "order": order, "tools": 0}
            runs.append(r); open_by[e["instance"]] = r
        elif e["kind"] == "return":
            r = open_by.get(e["who"])
            if r and not r["end"]:
                r["end"] = e["ts"]; r["secs"] = secs(r["start"], e["ts"])
        elif e["kind"] == "tool":
            for r in runs:
                if r["end"] is None:
                    r["tools"] += 1

    # Claude Opus 5 list price, verified: $5.00 / MTok in, $25.00 / MTok out.
    # Cache read and write are deliberately NOT priced here — the rate depends on
    # the cache TTL in use and guessing it would put a wrong number on screen.
    model = model_seen.most_common(1)[0][0] if model_seen else "—"
    RATE = {"claude-opus-5": (5.0, 25.0)}.get(model)
    use["model"] = model
    use["priced"] = bool(RATE)
    use["cost"] = round(use["in"] / 1e6 * RATE[0] + use["out"] / 1e6 * RATE[1], 2) if RATE else None

    return {"events": events, "dispatches": dispatches, "messages": messages, "runs": runs,
            "usage": use,
            "tools": tools.most_common(14), "files": files.most_common(16),
            "turns": turns, "first": first, "last": last}


_CACHE = {}


def parse_cached(path):
    """Re-parse only when the transcript actually changed."""
    try:
        sig = (os.path.getmtime(path), os.path.getsize(path))
    except OSError:
        return parse(path)
    hit = _CACHE.get(path)
    if hit and hit[0] == sig:
        return hit[1]
    out = parse(path)
    _CACHE[path] = (sig, out)
    return out


def subagent_runs(session_id):
    """What each dispatched seat actually did, from its own transcript.

    Every subagent writes a full transcript under
      ~/.claude/projects/<project>/<session>/subagents/agent-a<instance>-<hash>.jsonl
    These were there all along. An earlier version of this file claimed a
    dispatched seat's tool calls were unrecorded, on the strength of finding no
    `isSidechain` rows in the parent transcript. That was a wrong inference from
    the wrong file.
    """
    d = project_dir()
    if not d:
        return {}
    sub = os.path.join(d, session_id, "subagents")
    if not os.path.isdir(sub):
        return {}
    out = {}
    for fn in os.listdir(sub):
        if not fn.endswith(".jsonl") or not fn.startswith("agent-a"):
            continue
        inst = fn[len("agent-a"):-len(".jsonl")]
        inst = inst.rsplit("-", 1)[0]          # drop the trailing hash
        path = os.path.join(sub, fn)
        tools = collections.Counter()
        files = collections.Counter()
        rows = 0
        tok = {"out": 0, "think": 0, "cache_read": 0}
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        x = json.loads(line)
                    except Exception:
                        continue
                    rows += 1
                    m = x.get("message") or {}
                    u = m.get("usage") or {}
                    tok["out"] += u.get("output_tokens", 0) or 0
                    tok["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
                    tok["think"] += (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0
                    c = m.get("content")
                    if not isinstance(c, list):
                        continue
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            tools[shorten(b.get("name", "?"))] += 1
                            i = b.get("input") or {}
                            fp = i.get("file_path")
                            if isinstance(fp, str):
                                files[os.path.relpath(fp, ROOT) if fp.startswith(ROOT) else fp] += 1
        except OSError:
            continue
        out[inst] = {"rows": rows, "tools": tools.most_common(10),
                     "tool_total": sum(tools.values()),
                     "files": files.most_common(6),
                     "out": tok["out"], "think": tok["think"],
                     "cache_read": tok["cache_read"],
                     "cost": round(tok["out"] / 1e6 * 25.0, 2)}
    return out


def hook_events():
    """Events written by agent/scripts/flow-hook.sh, if hooks are configured.

    Absent until the CEO reloads settings once (/hooks). Until then the graph
    shows dispatch and reply and says plainly that the inside is not recorded.
    """
    p = os.path.join(ROOT, "agent", ".flow", "events.jsonl")
    if not os.path.exists(p):
        return {"live": False, "count": 0, "by_event": [], "by_session": []}
    ev = collections.Counter()
    ses = collections.Counter()
    n = 0
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                n += 1
                ev[d.get("event", "?")] += 1
                sid = d.get("session_id")
                if sid:
                    ses[sid] += 1
    except OSError:
        pass
    return {"live": n > 0, "count": n,
            "by_event": ev.most_common(), "by_session": ses.most_common(12)}


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


def embed_json(obj):
    r"""Serialise for embedding inside a <script> element.

    json.dumps does not escape "<", so a "</script>" sequence arriving from
    NAMING.csv would close the element early and everything after it would be
    parsed as markup. Escaping the three HTML-significant characters as \uXXXX
    escapes keeps the value a valid JSON string and inert to the HTML parser.
    U+2028 and U+2029 are escaped too: legal in JSON, historically illegal in a
    JavaScript string literal.
    """
    out = json.dumps(obj)
    for ch, esc in ((chr(0x3c), "u003c"), (chr(0x3e), "u003e"), (chr(0x26), "u0026"),
                    (chr(0x2028), "u2028"), (chr(0x2029), "u2029")):
        out = out.replace(ch, chr(0x5c) + esc)
    return out


def state(session_id=None):
    ses = sessions()
    if not ses:
        return {"error": "No session transcripts found under ~/.claude/projects.", "sessions": []}
    pick = next((s for s in ses if s["id"] == session_id), ses[0])
    data = parse_cached(pick["path"])
    inner = subagent_runs(pick["id"])
    for r in data.get("runs", []):
        r["inner"] = inner.get(r["instance"])
    data["inner_found"] = sum(1 for r in data.get("runs", []) if r.get("inner"))
    seats = roster()
    used = collections.Counter(d["seat"] for d in data["dispatches"])
    for name, s in seats.items():
        s["dispatched"] = used.get(name, 0)
    return {
        "sessions": [{"id": s["id"], "size": s["size"], "mtime": s["mtime"],
                      "live": (time.time() - s["mtime"]) < 120} for s in ses],
        "active": pick["id"],
        "live": (time.time() - pick["mtime"]) < 120,
        "seats": sorted(seats.values(), key=lambda x: x["name"]),
        "generated": time.time(),
        "hooks": hook_events(),
        **data,
    }


# ---------------------------------------------------------------- page

PAGE = r"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>One Brain — Command Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Noto+Sans+Egyptian+Hieroglyphs&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;padding:0;background:#06080a}
  *{box-sizing:border-box}
  a{color:oklch(0.80 0.10 200);text-decoration:none}
  a:hover{color:oklch(0.88 0.10 200)}
  ::-webkit-scrollbar{width:7px;height:7px}
  ::-webkit-scrollbar-thumb{background:rgba(255,255,255,.09);border-radius:4px}
  ::-webkit-scrollbar-track{background:transparent}
  @keyframes ob-breathe{0%,100%{opacity:.4}50%{opacity:.72}}
  @keyframes ob-spin{to{transform:rotate(360deg)}}
  @keyframes ob-spin-rev{to{transform:rotate(-360deg)}}
  @keyframes ob-pulse{0%{transform:scale(.84);opacity:.5}72%{transform:scale(1.22);opacity:0}100%{opacity:0}}
  @keyframes ob-flow{to{stroke-dashoffset:-260}}
  @keyframes ob-drift{0%,100%{transform:translate(0,0)}50%{transform:translate(16px,-26px)}}
  @keyframes ob-core{0%,100%{opacity:.45;transform:scale(1)}50%{opacity:.8;transform:scale(1.05)}}
  @keyframes ob-blink{0%,100%{opacity:1}50%{opacity:.25}}
  @keyframes ob-grid{to{transform:translate(64px,64px)}}
  .ob-hex{clip-path:polygon(50% 2%,93% 26%,93% 74%,50% 98%,7% 74%,7% 26%)}
  .mono{font-family:'Geist Mono',ui-monospace,monospace}
  .glyph{font-family:'Noto Sans Egyptian Hieroglyphs',serif}
  .hoverline{transition:border-color 240ms ease}
  .hoverline:hover{border-color:rgba(255,255,255,.22)}
  .seatrow:hover{background:rgba(255,255,255,.055)!important}
  .xbtn{transition:color 240ms ease}
  .xbtn:hover{color:rgba(236,244,248,.9)!important}
</style></head>
<body>
<div id="root" style="position:relative;width:100%;height:100vh;min-width:1200px;min-height:800px;overflow:hidden;background:radial-gradient(1300px 1000px at 50% 46%,#0b1014 0%,#07090b 56%,#050607 100%);font-family:Geist,ui-sans-serif,system-ui,sans-serif;color:rgba(236,244,248,.92);display:grid;grid-template-rows:56px minmax(0,1fr) auto">

  <div style="position:absolute;inset:0;pointer-events:none;opacity:.5;background:linear-gradient(rgba(255,255,255,.02) 1px,transparent 1px) 0 0/64px 64px,linear-gradient(90deg,rgba(255,255,255,.02) 1px,transparent 1px) 0 0/64px 64px;animation:ob-grid 40s linear infinite;mask:radial-gradient(1000px 780px at 50% 44%,#000 0%,transparent 76%)"></div>

  <div style="position:relative;display:flex;align-items:center;gap:18px;padding:0 22px;border-bottom:1px solid rgba(255,255,255,.055);background:linear-gradient(180deg,rgba(255,255,255,.03),rgba(255,255,255,.006));backdrop-filter:blur(20px)">
    <div style="display:flex;align-items:center;gap:9px">
      <div class="ob-hex" style="position:relative;width:16px;height:16px;background:oklch(0.80 0.10 200);filter:drop-shadow(0 0 7px oklch(0.80 0.10 200 / .55))">
        <div class="ob-hex" style="position:absolute;inset:1.3px;background:#080b0d"></div>
      </div>
      <div style="font-size:14px;font-weight:600;letter-spacing:.26em;text-transform:uppercase">One Brain</div>
    </div>
    <div style="display:flex;align-items:center;gap:6px">
      <div id="livedot" style="width:6px;height:6px;border-radius:50%;background:oklch(0.78 0.09 155);box-shadow:0 0 9px oklch(0.78 0.09 155 / .85);animation:ob-blink 2.6s ease-in-out infinite"></div>
      <span id="livelabel" class="mono" style="font-size:11px;letter-spacing:.1em;color:oklch(0.84 0.05 155)">live</span>
    </div>
    <div class="hoverline mono" id="sesbtn" style="display:flex;align-items:center;gap:8px;padding:5px 10px 5px 11px;border:1px solid rgba(255,255,255,.085);border-radius:7px;background:rgba(255,255,255,.028);font-size:11.5px;color:rgba(236,244,248,.8);cursor:pointer">
      <span style="width:5px;height:5px;border-radius:50%;background:oklch(0.80 0.10 200)"></span>
      <span id="sesid">—</span><span style="opacity:.4;font-size:9px">&#9662;</span>
    </div>
    <div style="display:flex;gap:2px;padding:2px;border:1px solid rgba(255,255,255,.07);border-radius:8px;background:rgba(255,255,255,.018)">
      <div id="tabflow" class="mono" style="padding:4px 14px;border-radius:6px;font-size:11px;cursor:pointer;transition:all 280ms ease">flow</div>
      <div id="taborg" class="mono" style="padding:4px 14px;border-radius:6px;font-size:11px;cursor:pointer;transition:all 280ms ease">org</div>
    </div>
    <div style="flex:1"></div>
    <div class="mono" style="display:flex;align-items:center;gap:9px;font-size:12px;color:rgba(236,244,248,.52)">
      <span><strong id="hdRuns" style="color:rgba(236,244,248,.95);font-weight:500">0</strong> runs</span>
      <span style="opacity:.28">&middot;</span>
      <span><strong id="hdWoken" style="color:rgba(236,244,248,.95);font-weight:500">—</strong> seats woken</span>
      <span style="opacity:.28">&middot;</span>
      <span><strong id="hdOut" style="color:rgba(236,244,248,.95);font-weight:500">0</strong> out</span>
    </div>
  </div>

  <div style="position:relative;display:grid;grid-template-columns:268px minmax(0,1fr) 320px;gap:13px;padding:13px;min-height:0">

    <div style="position:relative;display:flex;flex-direction:column;min-height:0;border:1px solid rgba(255,255,255,.06);border-radius:13px;background:linear-gradient(180deg,rgba(255,255,255,.036),rgba(255,255,255,.01));backdrop-filter:blur(24px);box-shadow:0 26px 64px -32px rgba(0,0,0,.92),inset 0 1px 0 rgba(255,255,255,.045)">
      <div style="display:flex;align-items:baseline;justify-content:space-between;padding:13px 14px 10px;border-bottom:1px solid rgba(255,255,255,.05)">
        <div class="mono" style="font-size:10px;letter-spacing:.2em;color:rgba(236,244,248,.5)">SEATS</div>
        <div class="mono" id="awakeLabel" style="font-size:10px;color:rgba(236,244,248,.5)">— awake</div>
      </div>
      <div id="seatList" style="flex:1;min-height:0;overflow-y:auto;padding:8px 8px 12px"></div>
      <div style="padding:11px 13px 12px;border-top:1px solid rgba(255,255,255,.05)">
        <div class="mono" style="font-size:9px;letter-spacing:.2em;color:rgba(236,244,248,.5);margin-bottom:8px">STATUS &middot; RING</div>
        <div id="legend" style="display:grid;grid-template-columns:1fr 1fr;gap:7px 10px"></div>
        <div class="mono" style="font-size:9px;letter-spacing:.2em;color:rgba(236,244,248,.5);margin:13px 0 8px">TIER &middot; BODY</div>
        <div id="tiers" style="display:grid;grid-template-columns:1fr 1fr;gap:6px 10px"></div>
      </div>
    </div>

    <div id="canvas" style="position:relative;min-width:0;min-height:0;overflow:hidden;border:1px solid rgba(255,255,255,.05);border-radius:13px;background:radial-gradient(760px 580px at 50% 46%,rgba(255,255,255,.018),transparent 70%);cursor:grab">
      <div id="particles"></div>
      <div id="stage" style="position:absolute;left:50%;top:50%;width:1300px;height:1080px;margin:-540px 0 0 -650px;transform-origin:center center">
        <svg id="wires" viewBox="0 0 1300 1080" width="1300" height="1080" style="position:absolute;inset:0;overflow:visible">
          <path id="rings" fill="none" stroke="rgba(255,255,255,.035)" stroke-width="1" stroke-dasharray="1 8"></path>
          <g id="identEdges"></g>
          <path id="eDone" fill="none" stroke="oklch(0.78 0.09 155)" stroke-width="1.1" opacity=".34"></path>
          <path id="eWaiting" fill="none" stroke="oklch(0.78 0.09 70)" stroke-width="1.2" opacity=".45"></path>
          <path id="eThinking" fill="none" stroke="oklch(0.78 0.09 300)" stroke-width="1.3" opacity=".6"></path>
          <path id="eExec" fill="none" stroke="oklch(0.80 0.10 200)" stroke-width="1.3" opacity=".62"></path>
          <path id="eExecF" fill="none" stroke="oklch(0.93 0.09 200)" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="2 24" style="animation:ob-flow 2.8s linear infinite"></path>
          <path id="eThinkingF" fill="none" stroke="oklch(0.90 0.08 300)" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="2 34" style="animation:ob-flow 5s linear infinite"></path>
          <path id="eWaitingF" fill="none" stroke="oklch(0.88 0.08 70)" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 44" style="animation:ob-flow 7s linear infinite"></path>
        </svg>
        <div id="nodes"></div>
        <div id="toolLabels"></div>
        <div id="core" style="position:absolute;width:280px;height:210px;margin:-105px 0 0 -140px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;z-index:7;transition:left 700ms cubic-bezier(.2,.8,.2,1),top 700ms cubic-bezier(.2,.8,.2,1)">
          <div style="position:absolute;left:50%;top:50%;width:320px;height:320px;margin:-160px 0 0 -160px;border-radius:50%;background:radial-gradient(circle,oklch(0.80 0.10 200 / .1) 0%,transparent 60%);animation:ob-core 6.5s ease-in-out infinite"></div>
          <div class="mono" id="coreTools" style="font-size:11px;color:rgba(236,244,248,.55)">0 tool calls</div>
          <div style="position:relative;width:126px;height:126px;display:flex;align-items:center;justify-content:center">
            <div style="position:absolute;inset:0;border-radius:50%;border:1px solid oklch(0.80 0.10 200 / .26);animation:ob-spin 30s linear infinite"></div>
            <div style="position:absolute;inset:10px;border-radius:50%;border:1px dashed oklch(0.80 0.10 200 / .18);animation:ob-spin-rev 46s linear infinite"></div>
            <div class="ob-hex" id="coreHex" style="position:relative;width:84px;height:84px;background:oklch(0.80 0.10 200);filter:drop-shadow(0 0 22px oklch(0.80 0.10 200 / .6));transition:filter 700ms ease">
              <div class="ob-hex" style="position:absolute;inset:2px;background:linear-gradient(160deg,#0d181c,#080b0d);display:flex;align-items:center;justify-content:center">
                <div id="corePad" style="display:flex;flex-direction:column;align-items:center;gap:3px;padding:11px">
                  <div class="glyph" id="coreGlyph" style="font-size:13px;line-height:1;color:oklch(0.93 0.05 200)">&#77888;&#77903;&#78230;</div>
                  <div id="coreName" style="font-family:Geist,sans-serif;font-weight:500;font-size:13px;letter-spacing:.04em;color:oklch(0.95 0.03 200)">Thebes</div>
                </div>
              </div>
            </div>
          </div>
          <div class="mono" id="coreLabel" style="max-width:150px;font-size:11px;letter-spacing:.1em;line-height:1.45;color:rgba(236,244,248,.45);text-align:center;transition:color 600ms ease">ALL SEATS ON STANDBY</div>
        </div>
      </div>

      <div style="position:absolute;left:14px;top:13px;display:flex;flex-direction:column;gap:5px;pointer-events:none">
        <div class="mono" id="viewLabel" style="font-size:9.5px;letter-spacing:.2em;color:rgba(236,244,248,.38)">FLOW &middot; THEBES TOPOLOGY</div>
        <div class="mono" id="viewSub" style="font-size:9.5px;color:rgba(236,244,248,.3)">&mdash;</div>
      </div>

      <div style="position:absolute;right:13px;top:12px;display:flex;align-items:center;gap:8px;z-index:12">
        <div class="mono" id="zoomLabel" style="font-size:9.5px;color:rgba(236,244,248,.4);min-width:34px;text-align:right">100%</div>
        <div id="camButtons" style="display:flex;gap:2px;padding:2px;border:1px solid rgba(255,255,255,.08);border-radius:8px;background:rgba(10,14,17,.72);backdrop-filter:blur(16px)"></div>
      </div>

      <div id="detail" hidden style="position:absolute;left:14px;bottom:34px;width:296px;padding:15px 16px 16px;border:1px solid rgba(255,255,255,.1);border-radius:12px;background:rgba(9,12,15,.86);backdrop-filter:blur(26px);box-shadow:0 30px 70px -30px rgba(0,0,0,.95),inset 0 1px 0 rgba(255,255,255,.05);z-index:14">
        <div style="display:flex;align-items:flex-start;gap:11px">
          <div class="ob-hex" id="dIdent" style="position:relative;width:38px;height:38px;flex:none">
            <div class="ob-hex" style="position:absolute;inset:1.5px;background:#0a0e11"></div>
            <div class="glyph" id="dLead" style="position:absolute;inset:7px;display:flex;align-items:center;justify-content:center;font-size:13px;line-height:1"></div>
          </div>
          <div style="flex:1;min-width:0">
            <div id="dName" style="font-family:Geist,sans-serif;font-weight:500;font-size:15px;letter-spacing:.01em;color:rgba(242,248,251,.96)"></div>
            <div class="mono" id="dSlug" style="font-size:10px;color:rgba(236,244,248,.45);margin-top:3px;word-break:break-all"></div>
          </div>
          <div class="xbtn mono" id="dClose" style="flex:none;padding:2px 7px;border-radius:5px;font-size:11px;color:rgba(236,244,248,.4);cursor:pointer">&#10005;</div>
        </div>
        <div class="glyph" id="dGlyph" style="font-size:19px;line-height:1.35;margin-top:12px"></div>
        <div style="display:flex;align-items:center;gap:9px;margin-top:12px">
          <div id="dPill" style="display:flex;align-items:center;gap:6px;padding:3px 9px;border:1px solid;border-radius:20px">
            <div id="dPillDot" style="width:5px;height:5px;border-radius:50%"></div>
            <div class="mono" id="dState" style="font-size:9.5px;letter-spacing:.08em"></div>
          </div>
          <div class="mono" id="dMeta" style="font-size:9.5px;color:rgba(236,244,248,.45)"></div>
        </div>
        <div id="dLore" style="font-family:Geist,sans-serif;font-size:11.5px;line-height:1.6;color:rgba(236,244,248,.72);margin-top:12px;text-wrap:pretty"></div>
        <div style="display:flex;align-items:center;gap:8px;margin-top:14px">
          <div class="mono" id="dRunCount" style="font-size:9px;letter-spacing:.2em;color:rgba(236,244,248,.36);white-space:nowrap"></div>
          <div style="flex:1;height:1px;background:rgba(255,255,255,.06)"></div>
        </div>
        <div id="dRuns" style="display:flex;flex-direction:column;gap:5px;margin-top:8px"></div>
      </div>

      <div style="position:absolute;left:0;right:0;bottom:9px;display:flex;justify-content:center;pointer-events:none;z-index:13">
        <div class="mono" style="padding:4px 13px;border-radius:20px;border:1px solid rgba(255,255,255,.06);background:rgba(9,12,15,.82);backdrop-filter:blur(12px);font-size:9.5px;letter-spacing:.1em;color:rgba(236,244,248,.42);white-space:nowrap">drag to pan &middot; scroll to zoom &middot; click a node for details</div>
      </div>
    </div>

    <div style="position:relative;display:flex;flex-direction:column;min-height:0;gap:12px">
      <div style="flex:none;padding:13px 14px 14px;border:1px solid rgba(255,255,255,.06);border-radius:13px;background:linear-gradient(180deg,rgba(255,255,255,.042),rgba(255,255,255,.01));backdrop-filter:blur(24px);box-shadow:0 26px 64px -32px rgba(0,0,0,.92),inset 0 1px 0 rgba(255,255,255,.045)">
        <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:11px">
          <div class="mono" style="font-size:10px;letter-spacing:.2em;color:rgba(236,244,248,.5)">ORCHESTRATION</div>
          <div class="mono" id="elapsed" style="font-size:10.5px;color:rgba(236,244,248,.62)">00:00 elapsed</div>
        </div>
        <div id="tiles" style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:11px"></div>
        <div style="display:flex;align-items:center;gap:9px;margin-bottom:11px">
          <div style="flex:1;height:3px;border-radius:3px;background:rgba(255,255,255,.07);overflow:hidden">
            <div id="ovBar" style="height:100%;width:0%;background:linear-gradient(90deg,oklch(0.78 0.09 155),oklch(0.80 0.10 200));transition:width 200ms linear"></div>
          </div>
          <div class="mono" id="ovPct" style="font-size:10px;color:rgba(236,244,248,.55);width:32px;text-align:right">0%</div>
        </div>
        <div class="mono" id="runsHead" style="font-size:9.5px;letter-spacing:.2em;color:rgba(236,244,248,.42);margin-bottom:8px">RUNS &middot; 0</div>
        <div id="runList" style="max-height:168px;overflow-y:auto;display:flex;flex-direction:column;gap:3px;margin-right:-4px;padding-right:4px"></div>
      </div>

      <div style="flex:1;min-height:0;overflow-y:auto;padding:15px 16px 16px;border:1px solid rgba(255,255,255,.06);border-radius:13px;background:linear-gradient(180deg,rgba(255,255,255,.036),rgba(255,255,255,.008));backdrop-filter:blur(24px);box-shadow:0 26px 64px -32px rgba(0,0,0,.92),inset 0 1px 0 rgba(255,255,255,.045)">
        <div id="cost" style="font-family:Geist,sans-serif;font-size:29px;font-weight:500;letter-spacing:-.02em;line-height:1">$0.00</div>
        <div class="mono" id="costSub" style="font-size:10.5px;color:rgba(236,244,248,.5);margin-top:7px">&mdash;</div>
        <div style="height:1px;background:rgba(255,255,255,.06);margin:14px 0"></div>
        <div id="tokRows" style="display:flex;flex-direction:column;gap:8px"></div>
        <div class="mono" style="font-size:9.5px;letter-spacing:.2em;color:rgba(236,244,248,.42);margin:16px 0 9px">CACHE</div>
        <div id="cacheRows" style="display:flex;flex-direction:column;gap:8px"></div>
        <div class="mono" style="font-size:9.5px;letter-spacing:.2em;color:rgba(236,244,248,.42);margin:16px 0 9px">AGENTS</div>
        <div id="agentRows" style="display:flex;flex-direction:column;gap:8px"></div>
        <div class="mono" style="font-size:9.5px;letter-spacing:.2em;color:rgba(236,244,248,.42);margin:16px 0 9px">THEBES TOOLS</div>
        <div id="toolRows" style="display:flex;flex-direction:column;gap:10px"></div>
        <div style="margin-top:16px;padding-top:13px;border-top:1px solid rgba(255,255,255,.06);font-family:Geist,sans-serif;font-size:11px;line-height:1.55;color:rgba(236,244,248,.5);text-wrap:pretty">Cost covers input and output at the published Opus 5 rate. Cache is shown in tokens and deliberately not priced &mdash; the rate depends on the TTL in use.</div>
      </div>
    </div>
  </div>

  <div style="position:relative;margin:0 13px 13px;padding:11px 15px;border:1px solid rgba(255,255,255,.06);border-radius:13px;background:linear-gradient(180deg,rgba(255,255,255,.034),rgba(255,255,255,.008));backdrop-filter:blur(24px);display:flex;align-items:center;gap:14px">
    <div class="mono" style="font-size:9.5px;letter-spacing:.2em;color:rgba(236,244,248,.42);flex:none">ACTIVITY</div>
    <div class="mono" id="tStart" style="font-size:11px;color:rgba(236,244,248,.5);flex:none">&mdash;</div>
    <div id="track" style="position:relative;flex:1;height:40px">
      <div style="position:absolute;left:0;right:0;top:50%;height:1px;background:rgba(255,255,255,.065)"></div>
      <div id="events"></div>
      <div id="playhead" style="position:absolute;top:2px;bottom:2px;left:0%;width:1px;background:oklch(0.94 0.05 200 / .85);box-shadow:0 0 12px oklch(0.80 0.10 200 / .85)">
        <div style="position:absolute;left:-2.5px;top:-3px;width:6px;height:6px;border-radius:50%;background:oklch(0.94 0.05 200)"></div>
      </div>
    </div>
    <div class="mono" id="tEnd" style="font-size:11px;color:rgba(236,244,248,.5);flex:none">&mdash;</div>
  </div>
</div>

<script>
const SEATS_DATA = __SEATS_JSON__;
/* ================================================================
   One Brain — Command Center
   Presentation layer implemented from the Claude Design handoff
   "One Brain Command Center.dc.html". Layout maths, palette, node
   states, edge routing and motion are reproduced from that file.
   The data behind it is live: everything is driven by /api/state,
   which is unchanged.
   ================================================================ */

const PAL = {
  idle:     "oklch(0.62 0.012 230)",
  waiting:  "oklch(0.80 0.10 78)",
  thinking: "oklch(0.72 0.13 320)",
  exec:     "oklch(0.86 0.13 195)",
  done:     "oklch(0.80 0.11 148)",
  error:    "oklch(0.74 0.08 40)"
};
const RANK = { idle: 0, done: 1, waiting: 2, thinking: 3, exec: 4 };

const HUE = {
  cto: 300, cpo: 95, cxo: 175, analyst: 250,
  "content-manager": 330, devops: 265, pm: 145,
  po: 60, qa: 115
};
const TIER_LABEL = [
  ["Thebes", 200], ["CTO", 300], ["CPO", 95], ["CXO", 175],
  ["Analyst", 250], ["Content", 330], ["DevOps", 265], ["PM", 145],
  ["PO", 60], ["QA", 115], ["Team leads", 285], ["Frontend", 210], ["Backend", 160]
];
function hueFor(slug) {
  if (HUE[slug] != null) return HUE[slug];
  if (slug.indexOf("team-lead") === 0) return 285;
  if (slug.indexOf("backend") === 0) return 160;
  return 210;
}
function ident(h, a) { return "oklch(0.78 0.085 " + h + (a == null ? "" : " / " + a) + ")"; }

/* The roster is injected by the server from .claude/bindings/ and
   agent/NAMING.csv. It is never written here: a second copy of the roster
   inside this page is what let it drift a whole restructure behind. */
function shortName(slug) {
  return slug
    .replace(/^team-lead-/, "tl-")
    .replace(/^frontend-/, "fe-")
    .replace(/^backend-/, "be-")
    .replace(/^content-manager$/, "content");
}
const SEATS = (SEATS_DATA || []).map(function (r) {
  return {
    group: r.group || "DEVELOPERS",
    slug:  r.name,
    short: shortName(r.name),
    name:  r.name,
    model: String(r.model || "\u2014").slice(0, 4),
    deity: r.deity || r.name,
    glyph: r.glyph || "\u25cb",
    lore:  r.lore || "",
    hue:   hueFor(r.name)
  };
});
const BY_SLUG = {};
SEATS.forEach(s => { BY_SLUG[s.slug] = s; });

function rnd(i) { const v = Math.sin(i * 12.9898) * 43758.5453; return v - Math.floor(v); }

const HEX = 52;
const CORE_HEX = 84;
const GAP = 6;
const HEXPTS = [[0, -0.48], [0.43, -0.24], [0.43, 0.24], [0, 0.48], [-0.43, 0.24], [-0.43, -0.24]];

function hexRadius(ux, uy, size) {
  let best = Infinity;
  for (let i = 0; i < 6; i++) {
    const a = HEXPTS[i], b = HEXPTS[(i + 1) % 6];
    const ax = a[0] * size, ay = a[1] * size;
    const ex = b[0] * size - ax, ey = b[1] * size - ay;
    const den = ux * ey - uy * ex;
    if (Math.abs(den) < 1e-9) continue;
    const t = (ax * ey - ay * ex) / den;
    if (t <= 0) continue;
    const s = Math.abs(ex) > Math.abs(ey) ? (ux * t - ax) / ex : (uy * t - ay) / ey;
    if (s >= -0.002 && s <= 1.002) best = Math.min(best, t);
  }
  return best === Infinity ? size * 0.45 : best;
}

var GROUPS = ["COMPANY", "PRODUCT", "PROJECT", "DEVELOPERS"];
var CORE_FLOW = { x: 650, y: 540 };
var CORE_ORG  = { x: 650, y: 200 };

/* ---------------------------------------------------------------- state */

var S = { t: 1, view: "flow", sel: null, cam: "follow",
          z: 1, px: 650, py: 540, dragging: false, scale: 0.4 };

var DATA = null, RUNS = [], TOOLS = [], USAGE = {}, TOTAL_TOOLS = 0,
    SPAN_MIN = 0, T_START = "—", T_END = "—", SESSION = "—",
    IS_LIVE = false, INNER = { found: 0, of: 0, tools: 0, out: 0, cost: 0 };

var _flowPos = null, _orgPos = null;

function flowPositions() {
  if (_flowPos) return _flowPos;
  var tiers = [
    { seats: SEATS.filter(function (s) { return s.group === "COMPANY"; }), r: 212, a0: -90 },
    { seats: SEATS.filter(function (s) { return s.group === "PRODUCT" || s.group === "PROJECT"; }), r: 348, a0: -96 },
    { seats: SEATS.filter(function (s) { return s.group === "DEVELOPERS"; }), r: 486, a0: -101 }
  ];
  var out = {};
  tiers.forEach(function (t) {
    var n = t.seats.length;
    t.seats.forEach(function (s, i) {
      var a = (t.a0 + (360 / n) * i) * Math.PI / 180;
      out[s.name] = { x: CORE_FLOW.x + Math.cos(a) * t.r, y: CORE_FLOW.y + Math.sin(a) * t.r };
    });
  });
  _flowPos = out; return out;
}

function orgPositions() {
  if (_orgPos) return _orgPos;
  var devs = SEATS.filter(function (s) { return s.group === "DEVELOPERS"; });
  var rows = [
    { seats: SEATS.filter(function (s) { return s.group === "COMPANY"; }), y: 400 },
    { seats: SEATS.filter(function (s) { return s.group === "PRODUCT" || s.group === "PROJECT"; }), y: 610 },
    { seats: devs.slice(0, 8), y: 830 },
    { seats: devs.slice(8), y: 985 }
  ];
  var out = {};
  rows.forEach(function (r) {
    var n = r.seats.length;
    var span = Math.min(1030, n * 132);
    r.seats.forEach(function (s, i) {
      var x = 650 - span / 2 + (n === 1 ? span / 2 : (span / (n - 1)) * i);
      out[s.name] = { x: x, y: r.y };
    });
  });
  _orgPos = out; return out;
}

function runState(r, t) {
  if (t <= 0) return null;
  if (t < r.s - 0.028) return null;
  if (t < r.s) return { st: "waiting", p: 0 };
  // An open run has a dispatch and no reply yet. While the session is live that
  // means the seat is working now, so it reads as executing. On a session that
  // has gone quiet the same row is a run that never closed, and stays waiting.
  if (t >= r.e) return r.open ? { st: IS_LIVE ? "exec" : "waiting", p: 1 } : { st: "done", p: 1 };
  var p = (t - r.s) / (r.e - r.s);
  return { st: p < 0.24 ? "thinking" : "exec", p: p };
}

/* ---------------------------------------------------------------- data */

function ms(x) { var v = Date.parse(x); return isFinite(v) ? v : null; }
function fmt(n) {
  n = n || 0;
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return String(n);
}

function ingest(d) {
  DATA = d;
  var t0 = ms(d.first), t1 = ms(d.last);
  var span = (t0 != null && t1 != null && t1 > t0) ? (t1 - t0) : 1;
  SPAN_MIN = Math.max(1, Math.round(span / 60000));
  var clock = function (x) {
    var v = ms(x); if (v == null) return "—";
    var dt = new Date(v);
    return String(dt.getHours()).padStart(2, "0") + ":" + String(dt.getMinutes()).padStart(2, "0");
  };
  T_START = clock(d.first); T_END = clock(d.last);
  SESSION = (d.active || "—").slice(0, 8);
  IS_LIVE = !!d.live;

  RUNS = (d.runs || []).map(function (r) {
    var a = ms(r.start), b = r.end ? ms(r.end) : null;
    var s = a != null && t0 != null ? (a - t0) / span : 0;
    var e = b != null && t0 != null ? (b - t0) / span : 1;
    if (e < s) e = s;
    if (e - s < 0.004) e = s + 0.004;
    var inner = r.inner || null;
    var tool = inner && inner.tools && inner.tools.length ? inner.tools[0][0] : (r.desc || "—");
    return {
      seat: r.seat, instance: r.instance, desc: r.desc || "",
      dur: r.secs, tools: inner ? inner.tool_total : (r.tools || 0),
      s: Math.max(0, Math.min(1, s)), e: Math.max(0, Math.min(1, e)),
      tool: tool, open: !r.end
    };
  });

  TOOLS = (d.tools || []).slice(0, 6).map(function (x) { return { name: x[0], n: x[1] }; });
  TOTAL_TOOLS = (d.tools || []).reduce(function (a, x) { return a + x[1]; }, 0);
  USAGE = d.usage || {};

  INNER = { found: d.inner_found || 0, of: RUNS.length, tools: 0, out: 0, cost: 0 };
  (d.runs || []).forEach(function (r) {
    if (!r.inner) return;
    INNER.tools += r.inner.tool_total || 0;
    INNER.out += r.inner.out || 0;
    INNER.cost += r.inner.cost || 0;
  });

  // the roster is the truth for the model; the design shows it abbreviated to
  // four characters so the slug beside it is never truncated ("sonn", "opus")
  (d.seats || []).forEach(function (s) {
    if (BY_SLUG[s.name] && s.model) BY_SLUG[s.name].model = String(s.model).slice(0, 4);
  });

  S.t = 1;   // this is a live tracker: the frame on screen is always now
}

/* ---------------------------------------------------------------- camera */

var canvas = document.getElementById("canvas");

function measure() {
  var w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  var k = Math.min(w / 1300, h / 1080) * 0.94;
  if (Math.abs(k - S.scale) > 0.002) S.scale = k;
}

function camera(live, pos, core) {
  if (S.cam === "manual") return { z: S.z, px: S.px, py: S.py, ease: !S.dragging };
  if (S.cam === "focus" && S.sel && pos[S.sel]) return { z: 1.75, px: pos[S.sel].x, py: pos[S.sel].y, ease: true };
  if (S.cam === "fit") return { z: S.scale || 0.4, px: core.x, py: core.y, ease: true };
  var names = Object.keys(live);
  if (!names.length) return { z: 1, px: core.x, py: core.y, ease: true };
  var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  names.concat(["__core"]).forEach(function (n) {
    var p = n === "__core" ? core : pos[n];
    if (!p) return;
    x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x);
    y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y);
  });
  var pad = 210;
  var w = (x1 - x0) + pad * 2, h = (y1 - y0) + pad * 2;
  var cw = canvas.clientWidth || 900, ch = canvas.clientHeight || 700;
  var z = Math.max(0.45, Math.min(1.9, Math.min(cw / w, ch / h)));
  return { z: z, px: (x0 + x1) / 2, py: (y0 + y1) / 2, ease: true };
}

/* ---------------------------------------------------------------- build */

function el(tag, style, cls) {
  var e = document.createElement(tag);
  if (style) e.setAttribute("style", style);
  if (cls) e.className = cls;
  return e;
}
function svg(tag) { return document.createElementNS("http://www.w3.org/2000/svg", tag); }

var NODE = {}, SEATROW = {}, IDENT = {}, TOOLPOOL = [], EVBARS = [], RUNROWS = [], TILES = [];

function buildNodes() {
  var host = document.getElementById("nodes");
  var idHost = document.getElementById("identEdges");
  SEATS.forEach(function (s, i) {
    var n = el("div", "position:absolute;width:0;height:0;cursor:pointer;transition:left 700ms cubic-bezier(.2,.8,.2,1),top 700ms cubic-bezier(.2,.8,.2,1),opacity 700ms ease");
    var wrap = el("div", "position:absolute;left:-43px;top:-43px;width:86px;height:86px;display:flex;align-items:center;justify-content:center;transition:transform 700ms cubic-bezier(.2,.8,.2,1)");
    var glow = el("div", "position:absolute;inset:-20px;border-radius:50%;transition:opacity 800ms ease");
    var arc  = el("div", "position:absolute;inset:0;border-radius:50%;transition:opacity 600ms ease");
    arc.style.mask = "radial-gradient(farthest-side,transparent calc(100% - 2px),#000 calc(100% - 2px))";
    arc.style.webkitMask = arc.style.mask;
    var spin = el("div", "position:absolute;inset:-8px;border-radius:50%;border:1.5px solid transparent;animation:ob-spin 3.6s linear infinite;transition:opacity 500ms ease");
    var dash = el("div", "position:absolute;inset:-8px;border-radius:50%;border:1px dashed;animation:ob-spin-rev 16s linear infinite;transition:opacity 500ms ease");
    var puls = el("div", "position:absolute;inset:-4px;border-radius:50%;border:1.5px solid;animation:ob-pulse 3s ease-out infinite;transition:opacity 500ms ease");
    var hex  = el("div", "position:relative;width:52px;height:52px;animation:ob-breathe 7s ease-in-out infinite;transition:background 700ms ease,filter 700ms ease", "ob-hex");
    var hexin = el("div", "position:absolute;inset:2px;transition:background 700ms ease", "ob-hex");
    var hexg = el("div", "position:absolute;display:flex;align-items:center;justify-content:center;line-height:1;transition:opacity 600ms ease", "glyph");
    hexg.textContent = Array.from(s.glyph)[0];
    hex.appendChild(hexin); hex.appendChild(hexg);
    [glow, arc, spin, dash, puls, hex].forEach(function (c) { wrap.appendChild(c); });
    var badge = el("div", "position:absolute;transform:translate(-50%,-50%);padding:1px 5px;border-radius:20px;white-space:nowrap;letter-spacing:.06em;pointer-events:none;transition:opacity 500ms ease", "mono");
    var label = el("div", "position:absolute;width:200px;margin-left:-100px;transform:translateY(-50%);display:flex;flex-direction:column;align-items:center;pointer-events:none");
    var nm = el("div", "font-family:Geist,sans-serif;font-weight:500;letter-spacing:.02em;white-space:nowrap;transition:all 600ms ease");
    var mt = el("div", "letter-spacing:.03em;white-space:nowrap;transition:color 600ms ease", "mono");
    var bar = el("div", "width:42px;height:2px;border-radius:2px;background:rgba(255,255,255,.07);overflow:hidden;transition:opacity 500ms ease");
    var fill = el("div", "height:100%;width:0%;transition:width 220ms linear");
    bar.appendChild(fill);
    label.appendChild(nm); label.appendChild(mt); label.appendChild(bar);
    n.appendChild(wrap); n.appendChild(badge); n.appendChild(label);
    n.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (S.sel === s.name) { S.sel = null; S.cam = "follow"; } else { S.sel = s.name; S.cam = "focus"; }
      render();
    });
    host.appendChild(n);
    NODE[s.name] = { n: n, wrap: wrap, glow: glow, arc: arc, spin: spin, dash: dash, puls: puls,
                     hex: hex, hexin: hexin, hexg: hexg, badge: badge, label: label,
                     nm: nm, mt: mt, bar: bar, fill: fill, i: i };
    var p = svg("path");
    p.setAttribute("fill", "none"); p.setAttribute("stroke-width", "1");
    idHost.appendChild(p); IDENT[s.name] = p;
  });
  for (var i = 0; i < 30; i++) {
    var tl = el("div", "position:absolute;display:flex;align-items:center;gap:5px;transform:translate(-50%,-50%);opacity:0;transition:opacity 700ms ease;pointer-events:none;z-index:6");
    var d = el("div", "width:3px;height:3px;border-radius:50%;flex:none");
    var tx = el("div", "color:rgba(236,244,248,.6);white-space:nowrap", "mono");
    tl.appendChild(d); tl.appendChild(tx);
    document.getElementById("toolLabels").appendChild(tl);
    TOOLPOOL.push({ e: tl, d: d, t: tx });
  }
}

function buildSeatRail() {
  var host = document.getElementById("seatList");
  GROUPS.forEach(function (g) {
    var seats = SEATS.filter(function (s) { return s.group === g; });
    var box = el("div", "margin-bottom:11px");
    var head = el("div", "display:flex;align-items:center;gap:8px;padding:6px 6px 7px");
    var h1 = el("div", "font-size:9.5px;letter-spacing:.22em;color:rgba(236,244,248,.58)", "mono"); h1.textContent = g;
    var line = el("div", "flex:1;height:1px;background:rgba(255,255,255,.05)");
    var h2 = el("div", "font-size:9.5px;color:rgba(236,244,248,.56)", "mono"); h2.textContent = seats.length;
    head.appendChild(h1); head.appendChild(line); head.appendChild(h2);
    box.appendChild(head);
    seats.forEach(function (s) {
      var row = el("div", "display:flex;align-items:center;gap:9px;padding:5px 8px;border-radius:6px;cursor:pointer;transition:all 420ms ease", "seatrow");
      var dot = el("div", "width:6px;height:6px;flex:none;border-radius:50%;transition:all 500ms ease");
      var mid = el("div", "flex:1;min-width:0;display:flex;flex-direction:column;gap:2px");
      var nm = el("div", "font-family:Geist,sans-serif;font-weight:500;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:color 500ms ease");
      nm.textContent = s.deity;
      var sub = el("div", "display:flex;align-items:center;gap:6px;min-width:0");
      var gl = el("div", "flex:none;font-size:12px;line-height:1.1;transition:opacity 500ms ease", "glyph");
      gl.textContent = s.glyph; gl.style.color = ident(s.hue);
      var sl = el("div", "flex:1;min-width:0;font-size:9.5px;color:rgba(236,244,248,.56);white-space:nowrap;overflow:hidden;text-overflow:ellipsis", "mono");
      sl.textContent = s.slug;
      sub.appendChild(gl); sub.appendChild(sl);
      mid.appendChild(nm); mid.appendChild(sub);
      var meta = el("div", "font-size:10px;flex:none;transition:color 500ms ease", "mono");
      row.appendChild(dot); row.appendChild(mid); row.appendChild(meta);
      row.addEventListener("click", function () {
        if (S.sel === s.name) { S.sel = null; S.cam = "follow"; } else { S.sel = s.name; S.cam = "focus"; }
        render();
      });
      box.appendChild(row);
      SEATROW[s.name] = { row: row, dot: dot, nm: nm, gl: gl, meta: meta };
    });
    host.appendChild(box);
  });
}

function buildStatics() {
  var lg = document.getElementById("legend");
  ["idle", "thinking", "exec", "waiting", "done", "error"].forEach(function (k) {
    var r = el("div", "display:flex;align-items:center;gap:7px");
    var d = el("div", "width:7px;height:7px;flex:none;border-radius:50%;border:1.5px solid " + PAL[k] +
      ";opacity:" + (k === "idle" ? .45 : 1) + ";box-shadow:" + (k === "idle" ? "none" : "0 0 6px " + PAL[k]));
    var t = el("div", "font-size:9.5px;letter-spacing:.06em;color:rgba(236,244,248,.58)", "mono");
    t.textContent = k === "exec" ? "executing" : k;
    r.appendChild(d); r.appendChild(t); lg.appendChild(r);
  });
  var tr = document.getElementById("tiers");
  TIER_LABEL.forEach(function (x) {
    var r = el("div", "display:flex;align-items:center;gap:7px");
    var d = el("div", "width:8px;height:8px;flex:none;background:" + ident(x[1]), "ob-hex");
    var t = el("div", "font-size:9.5px;letter-spacing:.04em;color:rgba(236,244,248,.58);white-space:nowrap;overflow:hidden;text-overflow:ellipsis", "mono");
    t.textContent = x[0];
    r.appendChild(d); r.appendChild(t); tr.appendChild(r);
  });
  var pt = document.getElementById("particles");
  for (var i = 0; i < 16; i++) {
    var sz = (1 + rnd(i + 80) * 1.6).toFixed(1);
    pt.appendChild(el("div", "position:absolute;left:" + (rnd(i) * 96 + 2).toFixed(1) + "%;top:" +
      (rnd(i + 40) * 92 + 4).toFixed(1) + "%;width:" + sz + "px;height:" + sz +
      "px;border-radius:50%;background:rgba(205,232,242,.55);opacity:" + (0.12 + rnd(i + 120) * 0.26).toFixed(2) +
      ";animation:ob-drift " + (16 + rnd(i + 160) * 20).toFixed(1) + "s ease-in-out infinite;animation-delay:" +
      (-rnd(i + 200) * 20).toFixed(1) + "s"));
  }
  var cb = document.getElementById("camButtons");
  [["follow", "follow"], ["one", "1:1"], ["fit", "fit"]].forEach(function (b) {
    var e = el("div", "padding:4px 10px;border-radius:6px;font-size:10px;cursor:pointer;transition:all 260ms ease", "mono");
    e.textContent = b[1];
    e.addEventListener("click", function () {
      var core = S.view === "org" ? CORE_ORG : CORE_FLOW;
      if (b[0] === "one") { S.cam = "manual"; S.z = 1; S.px = core.x; S.py = core.y; S.sel = null; }
      else if (b[0] === "fit") { S.cam = "fit"; S.sel = null; }
      else { S.cam = "follow"; S.sel = null; }
      render();
    });
    cb.appendChild(e); e._key = b[0];
  });
  var tiles = document.getElementById("tiles");
  ["EXECUTING", "THINKING", "WAITING", "FINISHED", "SLEEPING", "SESSION"].forEach(function (lbl) {
    var box = el("div", "padding:8px 9px;border:1px solid rgba(255,255,255,.06);border-radius:8px;background:rgba(255,255,255,.012);transition:all 500ms ease");
    var top = el("div", "display:flex;align-items:center;gap:5px;margin-bottom:5px");
    var d = el("div", "width:4px;height:4px;border-radius:50%");
    var t = el("div", "font-size:8.5px;letter-spacing:.1em;color:rgba(236,244,248,.5)", "mono"); t.textContent = lbl;
    top.appendChild(d); top.appendChild(t);
    var v = el("div", "font-size:16px;font-weight:500;transition:color 500ms ease", "mono");
    box.appendChild(top); box.appendChild(v); tiles.appendChild(box);
    TILES.push({ box: box, dot: d, val: v });
  });
}

function row2(label, value) {
  var r = el("div", "display:flex;justify-content:space-between;font-size:11.5px", "mono");
  var a = el("span", "color:rgba(236,244,248,.62)"); a.textContent = label;
  var b = el("span"); b.textContent = value;
  r.appendChild(a); r.appendChild(b); return r;
}

function buildData() {
  var ev = document.getElementById("events");
  ev.textContent = ""; EVBARS = [];
  for (var i = 0; i < 92; i++) {
    var f = i / 91;
    var active = RUNS.filter(function (r) { return f >= r.s && f <= r.e; });
    if (active.length === 0 && rnd(i) > 0.5) continue;
    var h = 4 + active.length * 3 + rnd(i + 7) * 5;
    var b = el("div", "position:absolute;left:" + (f * 100).toFixed(2) + "%;top:50%;width:3px;height:" +
      h.toFixed(1) + "px;margin-top:" + (-h / 2).toFixed(1) + "px;border-radius:2px;transition:opacity 300ms ease,background 300ms ease");
    ev.appendChild(b);
    EVBARS.push({ e: b, f: f, active: active });
  }
  var rl = document.getElementById("runList");
  rl.textContent = ""; RUNROWS = [];
  RUNS.forEach(function (r) {
    var row = el("div", "display:flex;align-items:center;gap:8px;padding:4px 7px;border-radius:6px;transition:background 420ms ease");
    var d = el("div", "width:5px;height:5px;flex:none;border-radius:50%;transition:all 420ms ease");
    var nm = el("div", "flex:1;min-width:0;font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:color 420ms ease", "mono");
    nm.textContent = (BY_SLUG[r.seat] ? BY_SLUG[r.seat].deity : r.seat) + "  ·  " + r.seat;
    var mt = el("div", "font-size:9.5px;color:rgba(236,244,248,.45);flex:none", "mono");
    mt.textContent = (r.dur ? r.dur + "s" : "open") + " · " + r.tools + " tools";
    row.appendChild(d); row.appendChild(nm); row.appendChild(mt);
    rl.appendChild(row);
    RUNROWS.push({ row: row, dot: d, nm: nm, r: r });
  });
  var tk = document.getElementById("tokRows"); tk.textContent = "";
  tk.appendChild(row2("output", fmt(USAGE.out)));
  tk.appendChild(row2("of which thinking", fmt(USAGE.think)));
  tk.appendChild(row2("input", fmt(USAGE["in"])));
  var ch = document.getElementById("cacheRows"); ch.textContent = "";
  ch.appendChild(row2("read", fmt(USAGE.cache_read)));
  ch.appendChild(row2("written", fmt(USAGE.cache_write)));
  var ag = document.getElementById("agentRows"); ag.textContent = "";
  ag.appendChild(row2("runs with inner record", INNER.found + "/" + INNER.of));
  ag.appendChild(row2("their tool calls", INNER.tools));
  ag.appendChild(row2("their output", fmt(INNER.out)));
  ag.appendChild(row2("their cost", "$" + INNER.cost.toFixed(2)));
  var tr = document.getElementById("toolRows"); tr.textContent = "";
  var top = TOOLS.length ? TOOLS[0].n : 1;
  TOOLS.forEach(function (t) {
    var box = el("div", "");
    var line = el("div", "display:flex;justify-content:space-between;gap:10px;align-items:baseline");
    var a = el("span", "font-size:11px;color:rgba(236,244,248,.76);word-break:break-all;line-height:1.35", "mono");
    a.textContent = t.name;
    var b = el("span", "font-size:11px;flex:none", "mono"); b.textContent = t.n;
    line.appendChild(a); line.appendChild(b);
    var barbg = el("div", "margin-top:5px;height:2px;border-radius:2px;background:rgba(255,255,255,.06);overflow:hidden");
    barbg.appendChild(el("div", "height:100%;width:" + (t.n / top * 100).toFixed(1) + "%;background:oklch(0.80 0.10 200 / .5)"));
    box.appendChild(line); box.appendChild(barbg); tr.appendChild(box);
  });
  document.getElementById("cost").textContent = USAGE.priced ? "$" + Number(USAGE.cost).toFixed(2) : "—";
  document.getElementById("costSub").textContent = (USAGE.model || "—") + " · " + (USAGE.msgs || 0) + " messages";
  document.getElementById("coreTools").textContent = TOTAL_TOOLS + " tool calls";
  document.getElementById("runsHead").textContent = "RUNS · " + RUNS.length;
  document.getElementById("tStart").textContent = T_START;
  document.getElementById("tEnd").textContent = T_END;
  document.getElementById("sesid").textContent = SESSION;
  var ld = document.getElementById("livedot"), ll = document.getElementById("livelabel");
  ld.style.background = IS_LIVE ? "oklch(0.78 0.09 155)" : "rgba(236,244,248,.3)";
  ld.style.boxShadow = IS_LIVE ? "0 0 9px oklch(0.78 0.09 155 / .85)" : "none";
  ld.style.animationPlayState = IS_LIVE ? "running" : "paused";
  ll.textContent = IS_LIVE ? "live" : "idle";
  ll.style.color = IS_LIVE ? "oklch(0.84 0.05 155)" : "rgba(236,244,248,.42)";
}

/* ---------------------------------------------------------------- render */

function render() {
  var t = S.t, org = S.view === "org";
  var core = org ? CORE_ORG : CORE_FLOW;
  var pos = org ? orgPositions() : flowPositions();

  var live = {};
  RUNS.forEach(function (r, i) {
    var rs = runState(r, t);
    if (!rs) return;
    var cur = live[r.seat];
    if (!cur || RANK[rs.st] > RANK[cur.st] || (RANK[rs.st] === RANK[cur.st] && rs.p > cur.p))
      live[r.seat] = { st: rs.st, p: rs.p, run: r, idx: i };
  });

  var counts = { exec: 0, thinking: 0, waiting: 0, done: 0 };
  Object.keys(live).forEach(function (k) { counts[live[k].st] = (counts[live[k].st] || 0) + 1; });
  var awake = Object.keys(live).length;

  var cam = camera(live, pos, core);
  var sc = cam.z;
  var f = Math.max(0.72, Math.min(1.8, sc)) / sc;
  var inv = function (n) { return (n * f).toFixed(1) + "px"; };

  var stage = document.getElementById("stage");
  stage.style.transform = "translate(" + (-(cam.px - 650) * sc).toFixed(1) + "px," +
    (-(cam.py - 540) * sc).toFixed(1) + "px) scale(" + sc.toFixed(3) + ")";
  stage.style.transition = cam.ease ? "transform 800ms cubic-bezier(.22,.8,.24,1)" : "none";
  canvas.style.cursor = S.dragging ? "grabbing" : "grab";
  document.getElementById("zoomLabel").textContent = Math.round(sc * 100) + "%";

  var edges = { done: "", waiting: "", thinking: "", exec: "" };
  var tlUsed = 0;

  SEATS.forEach(function (s, i) {
    var p = pos[s.name] || { x: core.x, y: core.y };
    var l = live[s.name];
    var st = l ? l.st : "idle";
    var on = st !== "idle";
    var color = PAL[st];
    var isSel = S.sel === s.name;
    var N = NODE[s.name];

    var mx = (p.x + core.x) / 2 + (p.y - core.y) * 0.09;
    var my = (p.y + core.y) / 2 - (p.x - core.x) * 0.09;
    var k = on ? 1 : 0.7;
    var a0x = mx - core.x, a0y = my - core.y;
    var a0 = Math.sqrt(a0x * a0x + a0y * a0y) || 1;
    var u0x = a0x / a0, u0y = a0y / a0;
    var r0 = hexRadius(u0x, u0y, CORE_HEX) + GAP;
    var s0x = core.x + u0x * r0, s0y = core.y + u0y * r0;
    var a1x = p.x - mx, a1y = p.y - my;
    var a1 = Math.sqrt(a1x * a1x + a1y * a1y) || 1;
    var u1x = a1x / a1, u1y = a1y / a1;
    var r1 = hexRadius(-u1x, -u1y, HEX * k) + GAP;
    var e1x = p.x - u1x * r1, e1y = p.y - u1y * r1;
    var d = "M" + s0x.toFixed(1) + " " + s0y.toFixed(1) + "Q" + mx.toFixed(1) + " " + my.toFixed(1) +
            " " + e1x.toFixed(1) + " " + e1y.toFixed(1);

    if (st === "idle") {
      IDENT[s.name].setAttribute("d", d);
      IDENT[s.name].setAttribute("stroke", ident(s.hue, 0.3));
      IDENT[s.name].style.display = "";
    } else {
      IDENT[s.name].style.display = "none";
      edges[st] += d;
    }

    if (l && (st === "exec" || st === "thinking" || st === "waiting") && tlUsed < TOOLPOOL.length) {
      var T = TOOLPOOL[tlUsed++];
      T.e.style.left = (core.x * 0.42 + p.x * 0.58 + (p.y - core.y) * 0.06).toFixed(0) + "px";
      T.e.style.top = (core.y * 0.42 + p.y * 0.58 - (p.x - core.x) * 0.06).toFixed(0) + "px";
      T.e.style.opacity = st === "waiting" ? 0.55 : 0.95;
      T.d.style.background = color;
      T.t.style.fontSize = inv(10);
      T.t.textContent = l.run.tool;
    }

    var secs = l && l.run.dur ? Math.max(1, Math.round(l.run.dur * (st === "done" ? 1 : l.p))) : null;
    var meta;
    if (!l) meta = s.short;
    else if (l.run.open) meta = "open · " + l.run.tools + " tools";
    else meta = secs + "s · " + l.run.tools + " tools";

    var vx = p.x - core.x, vy = p.y - core.y;
    var vlen = Math.sqrt(vx * vx + vy * vy) || 1;
    var push = HEX * 0.62 + 34 * f;
    var badge = (l && l.run.open) ? "OPEN" : st === "exec" ? "EXEC" : st === "thinking" ? "THINK" :
                st === "waiting" ? "WAIT" : st === "done" ? "DONE" : "";
    var pct = (l ? (st === "done" ? 1 : l.p) : 0);

    N.n.style.left = p.x.toFixed(0) + "px";
    N.n.style.top = p.y.toFixed(0) + "px";
    N.n.style.opacity = on ? 1 : isSel ? 0.86 : 0.4;
    N.n.style.zIndex = on ? 5 : isSel ? 4 : 2;
    N.wrap.style.transform = "scale(" + k + ")";
    N.glow.style.background = "radial-gradient(circle," + color + " 0%,transparent 64%)";
    N.glow.style.opacity = st === "exec" ? .26 : st === "thinking" ? .2 : st === "waiting" ? .13 : st === "done" ? .11 : 0;
    N.arc.style.background = "conic-gradient(from -90deg," + color + " 0turn " + pct.toFixed(3) +
      "turn,rgba(255,255,255,.05) " + pct.toFixed(3) + "turn 1turn)";
    N.arc.style.opacity = on && !(l && l.run.open) ? .9 : 0;
    N.spin.style.borderTopColor = color; N.spin.style.borderRightColor = color;
    N.spin.style.opacity = st === "thinking" ? .9 : 0;
    N.dash.style.borderColor = color; N.dash.style.opacity = st === "exec" ? .32 : 0;
    N.puls.style.borderColor = color; N.puls.style.opacity = st === "exec" ? .5 : st === "waiting" ? .28 : 0;
    N.hex.style.background = ident(s.hue);
    N.hex.style.filter = "drop-shadow(0 0 " + (st === "exec" ? "18px" : st === "thinking" ? "14px" :
      st === "waiting" ? "10px" : st === "done" ? "9px" : "0px") + " " + color + ")";
    N.hex.style.animationPlayState = on ? "paused" : "running";
    N.hex.style.animationDelay = (i % 9) * 0.7 + "s";
    N.hexin.style.background = on ? "#080c0e" : "#080a0c";
    N.hexg.style.inset = (HEX * 0.19).toFixed(1) + "px";
    N.hexg.style.fontSize = (HEX * 0.4).toFixed(1) + "px";
    N.hexg.style.color = ident(s.hue);
    N.hexg.style.opacity = on ? .95 : .5;
    N.badge.style.left = (-vx / vlen * (HEX * 0.56 + 12 * f)).toFixed(1) + "px";
    N.badge.style.top = (-vy / vlen * (HEX * 0.56 + 12 * f)).toFixed(1) + "px";
    N.badge.textContent = badge;
    N.badge.style.opacity = badge ? 1 : 0;
    N.badge.style.background = badge ? "rgba(8,12,14,.9)" : "transparent";
    N.badge.style.border = "1px solid " + (badge ? color : "transparent");
    N.badge.style.color = badge ? color : "transparent";
    N.badge.style.fontSize = inv(9.5);
    N.label.style.left = (vx / vlen * push).toFixed(1) + "px";
    N.label.style.top = (vy / vlen * push).toFixed(1) + "px";
    N.label.style.gap = (5 * f).toFixed(1) + "px";
    N.nm.textContent = s.deity;
    N.nm.style.fontSize = on ? inv(15) : inv(13);
    N.nm.style.color = on ? "rgba(240,247,250,.95)" : isSel ? "rgba(236,244,248,.8)" : "rgba(236,244,248,.5)";
    N.mt.textContent = meta;
    N.mt.style.fontSize = inv(11);
    N.mt.style.color = on ? "rgba(236,244,248,.6)" : "rgba(236,244,248,.32)";
    N.bar.style.opacity = on && !(l && l.run.open) ? 1 : 0;
    N.fill.style.width = (pct * 100).toFixed(1) + "%";
    N.fill.style.background = color;

    var R = SEATROW[s.name];
    R.dot.style.background = color;
    R.dot.style.opacity = on ? 1 : .34;
    R.dot.style.boxShadow = on ? "0 0 8px " + color : "none";
    R.row.style.background = on ? "rgba(255,255,255,.055)" : "transparent";
    R.row.style.boxShadow = isSel ? "inset 0 0 0 1px rgba(255,255,255,.16)" : "none";
    R.nm.style.color = on ? "rgba(240,247,250,.95)" : "rgba(236,244,248,.55)";
    R.gl.style.opacity = on ? 1 : .62;
    var nruns = RUNS.filter(function (r) { return r.seat === s.name; }).length;
    R.meta.textContent = on ? (st === "exec" ? "exec" : st === "thinking" ? "think" : st === "waiting" ? "wait" : "done")
                            : (nruns ? "×" + nruns : (s.model || "—"));
    R.meta.style.color = on ? color : "rgba(236,244,248,.56)";
  });

  for (var q = tlUsed; q < TOOLPOOL.length; q++) TOOLPOOL[q].e.style.opacity = 0;

  document.getElementById("eDone").setAttribute("d", edges.done);
  document.getElementById("eWaiting").setAttribute("d", edges.waiting);
  document.getElementById("eThinking").setAttribute("d", edges.thinking);
  document.getElementById("eExec").setAttribute("d", edges.exec);
  document.getElementById("eExecF").setAttribute("d", edges.exec);
  document.getElementById("eThinkingF").setAttribute("d", edges.thinking);
  document.getElementById("eWaitingF").setAttribute("d", edges.waiting);

  var rings = "";
  if (!org) [212, 348, 486].forEach(function (r) {
    rings += "M" + (core.x - r) + " " + core.y + "a" + r + " " + r + " 0 1 0 " + (r * 2) +
             " 0a" + r + " " + r + " 0 1 0 " + (-r * 2) + " 0";
  });
  document.getElementById("rings").setAttribute("d", rings);

  var coreEl = document.getElementById("core");
  coreEl.style.left = core.x + "px"; coreEl.style.top = core.y + "px";
  var doneRuns = RUNS.filter(function (r) { return t >= r.e && !r.open; }).length;
  var doneFrac = RUNS.length ? doneRuns / RUNS.length : 0;
  document.getElementById("coreHex").style.filter =
    "drop-shadow(0 0 " + (awake ? (22 + awake * 4) : 14) + "px oklch(0.80 0.10 200 / .6))";
  var cl = document.getElementById("coreLabel");
  cl.textContent = awake ? awake + (awake === 1 ? " SEAT AWAKE" : " SEATS AWAKE") : "ALL SEATS ON STANDBY";
  cl.style.color = awake ? "oklch(0.86 0.07 200)" : "rgba(236,244,248,.45)";
  cl.style.fontSize = inv(11);
  document.getElementById("coreTools").style.fontSize = inv(11);
  document.getElementById("coreGlyph").style.fontSize = inv(13);
  document.getElementById("coreName").style.fontSize = inv(13);
  document.getElementById("corePad").style.padding = (11 * f).toFixed(1) + "px";

  document.getElementById("awakeLabel").textContent = awake + "/" + SEATS.length + " awake";
  document.getElementById("hdRuns").textContent = RUNS.length;
  document.getElementById("hdWoken").textContent = new Set(RUNS.map(function (r) { return r.seat; })).size + "/" + SEATS.length;
  document.getElementById("hdOut").textContent = fmt(USAGE.out);
  document.getElementById("viewLabel").textContent = org ? "ORG · REPORTING LINES" : "FLOW · THEBES TOPOLOGY";
  document.getElementById("viewSub").textContent = SEATS.length + " seats persistent · " + RUNS.length + " runs";

  var mins = Math.floor(t * SPAN_MIN);
  document.getElementById("elapsed").textContent =
    String(Math.floor(mins / 60)).padStart(2, "0") + ":" + String(mins % 60).padStart(2, "0") + " elapsed";
  document.getElementById("ovBar").style.width = (doneFrac * 100).toFixed(1) + "%";
  document.getElementById("ovPct").textContent = Math.round(doneFrac * 100) + "%";
  document.getElementById("playhead").style.left = "100%";

  var tv = [[counts.exec || 0, "exec"], [counts.thinking || 0, "thinking"], [counts.waiting || 0, "waiting"],
            [doneRuns, "done"], [30 - awake, "idle"], [IS_LIVE ? "LIVE" : "IDLE", "exec"]];
  TILES.forEach(function (T, i) {
    var v = tv[i][0], key = tv[i][1];
    var lit = i === 4 ? true : (i === 5 ? IS_LIVE : v > 0);
    T.dot.style.background = PAL[key];
    T.dot.style.opacity = lit ? 1 : .3;
    T.box.style.borderColor = lit ? "rgba(255,255,255,.12)" : "rgba(255,255,255,.06)";
    T.box.style.background = lit ? "rgba(255,255,255,.045)" : "rgba(255,255,255,.012)";
    T.val.textContent = v;
    T.val.style.color = lit ? "rgba(242,248,251,.96)" : "rgba(236,244,248,.5)";
  });

  RUNROWS.forEach(function (R) {
    var rs = runState(R.r, t);
    var st = rs ? rs.st : "idle";
    var on = !!rs;
    R.dot.style.background = PAL[st];
    R.dot.style.opacity = on ? 1 : .28;
    R.dot.style.boxShadow = on && st !== "done" ? "0 0 7px " + PAL[st] : "none";
    R.row.style.background = on && st !== "done" ? "rgba(255,255,255,.05)" : "transparent";
    R.nm.style.color = on ? "rgba(240,247,250,.92)" : "rgba(236,244,248,.42)";
  });

  EVBARS.forEach(function (B) {
    var rs = B.active.length ? runState(B.active[B.active.length - 1], B.f) : null;
    var st = B.f > t ? "future" : (rs ? rs.st : "idle");
    B.e.style.background = st === "future" ? "rgba(255,255,255,.14)" : (PAL[st] || PAL.idle);
    B.e.style.opacity = st === "future" ? .55 : .85;
  });

  document.getElementById("tabflow").style.background = !org ? "rgba(255,255,255,.1)" : "transparent";
  document.getElementById("tabflow").style.color = !org ? "rgba(245,250,252,.96)" : "rgba(236,244,248,.5)";
  document.getElementById("taborg").style.background = org ? "rgba(255,255,255,.1)" : "transparent";
  document.getElementById("taborg").style.color = org ? "rgba(245,250,252,.96)" : "rgba(236,244,248,.5)";

  Array.prototype.forEach.call(document.getElementById("camButtons").children, function (b) {
    var act = (b._key === "follow" && S.cam === "follow") || (b._key === "fit" && S.cam === "fit") ||
              (b._key === "one" && S.cam === "manual" && Math.abs(S.z - 1) < 0.001);
    b.style.background = act ? "rgba(255,255,255,.1)" : "transparent";
    b.style.color = act ? "rgba(245,250,252,.96)" : "rgba(236,244,248,.5)";
  });

  renderDetail(live, t);
}

function renderDetail(live, t) {
  var box = document.getElementById("detail");
  var s = BY_SLUG[S.sel];
  if (!s) { box.hidden = true; return; }
  box.hidden = false;
  var l = live[s.slug];
  var st = l ? l.st : "idle";
  document.getElementById("dIdent").style.background = ident(s.hue);
  var lead = document.getElementById("dLead");
  lead.textContent = Array.from(s.glyph)[0]; lead.style.color = ident(s.hue);
  document.getElementById("dName").textContent = s.deity;
  document.getElementById("dSlug").textContent = s.slug;
  var g = document.getElementById("dGlyph");
  g.textContent = s.glyph; g.style.color = ident(s.hue);
  document.getElementById("dPill").style.borderColor = PAL[st];
  var pd = document.getElementById("dPillDot");
  pd.style.background = PAL[st]; pd.style.boxShadow = "0 0 7px " + PAL[st];
  var ds = document.getElementById("dState");
  ds.textContent = st === "exec" ? "executing" : st === "idle" ? "standby" : st;
  ds.style.color = PAL[st];
  document.getElementById("dMeta").textContent = s.group + " · " + (s.model || "—");
  document.getElementById("dLore").textContent = s.lore || "";
  var mine = [];
  RUNS.forEach(function (r, i) { if (r.seat === s.slug) mine.push({ r: r, i: i }); });
  document.getElementById("dRunCount").textContent =
    mine.length ? mine.length + (mine.length === 1 ? " run" : " runs") : "no runs";
  var host = document.getElementById("dRuns");
  host.textContent = "";
  mine.forEach(function (x) {
    var rs = runState(x.r, t);
    var row = el("div", "display:flex;align-items:center;gap:8px;opacity:" + (rs ? 1 : .4) + ";transition:opacity 400ms ease");
    row.appendChild(el("div", "width:5px;height:5px;flex:none;border-radius:50%;background:" + PAL[rs ? rs.st : "idle"]));
    var a = el("div", "font-size:10px;color:rgba(236,244,248,.72);flex:none", "mono");
    a.textContent = "#" + (x.i + 1) + "  " + (x.r.dur ? x.r.dur + "s" : "open") + " · " + x.r.tools + " tools";
    var b = el("div", "flex:1;min-width:0;font-size:9px;color:rgba(236,244,248,.34);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right", "mono");
    b.textContent = x.r.tool;
    row.appendChild(a); row.appendChild(b); host.appendChild(row);
  });
}

/* ---------------------------------------------------------------- input */

document.getElementById("tabflow").addEventListener("click", function () { S.view = "flow"; render(); });
document.getElementById("taborg").addEventListener("click", function () { S.view = "org"; render(); });
document.getElementById("dClose").addEventListener("click", function () { S.sel = null; S.cam = "follow"; render(); });

var drag = null;
canvas.addEventListener("mousedown", function (ev) {
  var org = S.view === "org", core = org ? CORE_ORG : CORE_FLOW;
  var cam = camera(liveNow(), org ? orgPositions() : flowPositions(), core);
  drag = { x: ev.clientX, y: ev.clientY, px: cam.px, py: cam.py };
  S.cam = "manual"; S.z = cam.z; S.px = cam.px; S.py = cam.py; S.dragging = true;
  render();
});
addEventListener("mouseup", function () { drag = null; if (S.dragging) { S.dragging = false; render(); } });
addEventListener("mousemove", function (ev) {
  if (!drag) return;
  var z = S.z || 1;
  S.px = drag.px - (ev.clientX - drag.x) / z;
  S.py = drag.py - (ev.clientY - drag.y) / z;
  render();
});
canvas.addEventListener("wheel", function (ev) {
  ev.preventDefault();
  var org = S.view === "org", core = org ? CORE_ORG : CORE_FLOW;
  var cam = camera(liveNow(), org ? orgPositions() : flowPositions(), core);
  var k = Math.exp(-ev.deltaY / 420);
  var base = S.cam === "manual" ? S.z : cam.z;
  if (S.cam !== "manual") { S.px = cam.px; S.py = cam.py; }
  S.cam = "manual";
  S.z = Math.max(0.3, Math.min(3, base * k));
  render();
}, { passive: false });
canvas.addEventListener("click", function () { if (S.sel) { S.sel = null; S.cam = "follow"; render(); } });
addEventListener("resize", function () { measure(); render(); });

function liveNow() {
  var live = {};
  RUNS.forEach(function (r, i) {
    var rs = runState(r, S.t);
    if (!rs) return;
    var cur = live[r.seat];
    if (!cur || RANK[rs.st] > RANK[cur.st] || (RANK[rs.st] === RANK[cur.st] && rs.p > cur.p))
      live[r.seat] = { st: rs.st, p: rs.p, run: r, idx: i };
  });
  return live;
}

/* ---------------------------------------------------------------- loop */

buildNodes(); buildSeatRail(); buildStatics(); measure();

setInterval(measure, 250);

function poll() {
  fetch("/api/state" + (location.search || "")).then(function (r) { return r.json(); }).then(function (d) {
    if (d.error) { document.getElementById("coreLabel").textContent = "NO TRANSCRIPT"; return; }
    ingest(d); buildData(); render();
  }).catch(function () { /* server restarting — keep the last frame on screen */ });
}
poll(); setInterval(poll, 2000);
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        b = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            sid = None
            if "?s=" in self.path:
                sid = self.path.split("?s=", 1)[1].split("&")[0]
            try:
                self._send(json.dumps(state(sid)), "application/json")
            except Exception as e:
                self._send(json.dumps({"error": str(e), "sessions": []}), "application/json")
        else:
            try:
                seats = sorted(roster().values(), key=lambda x: (x["name"]))
            except Exception:
                seats = []
            page = PAGE.replace("__SEATS_JSON__", embed_json(seats))
            self._send(page, "text/html; charset=utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7373)
    a = ap.parse_args()
    d = project_dir()
    print("Thebes — agent flow")
    print("  workspace   :", ROOT)
    print("  transcripts :", d or "NOT FOUND")
    print("  seats       :", len(roster()))
    print("  open        : http://localhost:%d" % a.port)
    print("  stop        : Ctrl-C")
    try:
        ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
