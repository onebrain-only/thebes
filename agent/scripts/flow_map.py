#!/usr/bin/env python3
"""Thebes live map — the nodes view (CEO 2026-11-03).

Thebes in the middle, the orchestrator and every team around it, each node lit by what the
team is doing right now: busy, free, silent, stalled, blocked, untracked or no session.

READ ONLY. Every fact comes from `agent/state/runtime/liveness.json`, which the watchdog's
liveness sweep writes every 5 minutes from `claude agents` and the transcripts, and from the
team registry. Nothing here is computed from how far a transcript has progressed, and a
snapshot older than STALE_SECONDS is drawn grey and labelled, never presented as live.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import teams as team_registry                       # noqa: E402

LIVENESS = os.path.join(ROOT, "agent", "state", "runtime", "liveness.json")
STALE_SECONDS = 15 * 60
LOOPS = (("watchdog", "agent.execution.watchdog serve"),
         ("ready-dispatcher", "agent.execution.ready_dispatcher serve"),
         ("listener", "agent.listener"))


def _loops():
    out = []
    try:
        ps = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True,
                            timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return [{"name": n, "up": None} for n, _ in LOOPS]
    for name, needle in LOOPS:
        out.append({"name": name, "up": any(needle in line for line in ps.splitlines())})
    return out


def build(now=None):
    now = now or time.time()
    try:
        snap = json.load(open(LIVENESS, encoding="utf-8"))
    except (OSError, ValueError):
        snap = {}
    try:
        reg = team_registry.read()
    except Exception:                                    # noqa: BLE001
        reg = {}
    seen = {e["team"]: e for e in snap.get("teams") or ()}
    tickets = {}
    for t in snap.get("tickets") or ():
        if t.get("team"):
            tickets[t["team"]] = t
    nodes = []
    for tid, meta in sorted(reg.items(), key=lambda kv: kv[1].get("number", 99)):
        e = seen.get(tid, {})
        nodes.append({
            "id": tid, "name": meta.get("display_name", tid), "kind": meta.get("kind", "team"),
            "lane": meta.get("lane"), "owns": meta.get("owns") or [],
            "status": e.get("status") or ("unprobed" if tid != "orchestrator" else "n/a"),
            "detail": e.get("detail") or "", "ticket": e.get("ticket"),
            "jira": (tickets.get(tid) or {}).get("jira"),
            "quiet_min": e.get("quiet_min"), "session": e.get("session"),
        })
    at = snap.get("at")
    age = (now - at) if at else None
    return {"read_only": True, "now": now, "snapshot_at": at, "age_seconds": age,
            "stale": age is None or age > STALE_SECONDS,
            "loops": _loops(), "nodes": nodes,
            "tickets": [t for t in snap.get("tickets") or () if t.get("state") != "ok"][:8]}


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thebes live map</title>
<style>
:root{--bg:#07090b;--fg:#ecf4f8;--mut:rgba(236,244,248,.5);--busy:#37d67a;--free:#5aa9ff;
--silent:#f5b83d;--stalled:#ff6b5b;--blocked:#ff6b5b;--untracked:#c58bff;--none:#6b7780}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:13px Geist,system-ui,sans-serif;overflow:hidden}
#top{position:absolute;left:0;right:0;top:0;display:flex;gap:18px;align-items:center;padding:12px 20px;
border-bottom:1px solid rgba(255,255,255,.06);z-index:3}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:var(--mut)}
.pill{padding:2px 9px;border:1px solid rgba(255,255,255,.12);border-radius:20px}
#legend{position:absolute;left:20px;bottom:16px;display:flex;gap:14px;flex-wrap:wrap;z-index:3}
#legend span:before{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:var(--c)}
svg{position:absolute;inset:0;width:100%;height:100%}
#tip{position:absolute;right:20px;top:60px;width:270px;padding:14px;border:1px solid rgba(255,255,255,.09);
border-radius:12px;background:rgba(14,19,22,.9);display:none;z-index:4}
#warn{position:absolute;left:50%;transform:translateX(-50%);top:54px;padding:5px 14px;border-radius:20px;
background:rgba(255,107,91,.14);color:#ff9d90;display:none;z-index:4}
@keyframes pulse{0%{r:34;opacity:.5}100%{r:52;opacity:0}}
.ring{animation:pulse 2.2s ease-out infinite;transform-box:fill-box}
@keyframes flow{to{stroke-dashoffset:-24}}
.busyline{stroke-dasharray:4 8;animation:flow 1.1s linear infinite}
</style></head><body>
<div id="top"><b>Thebes</b><span class="mono">live map &middot; read only</span>
<span class="mono pill" id="age">&hellip;</span><span id="loops" class="mono"></span></div>
<div id="warn"></div>
<svg id="svg"></svg><div id="tip"></div>
<div id="legend" class="mono"></div>
<script>
var COL={busy:"--busy",free:"--free",silent:"--silent",stalled:"--stalled",blocked:"--blocked",
untracked:"--untracked","no-session":"--none",unprobed:"--none","n/a":"--none"};
var WORD={busy:"working on a ticket",free:"free, waiting for work",silent:"working but quiet",
stalled:"has a dispatch but no running session",blocked:"waiting on something",
untracked:"working with no dispatch","no-session":"no session",unprobed:"not probed yet","n/a":""};
var css=getComputedStyle(document.documentElement),svg=document.getElementById("svg"),NS="http://www.w3.org/2000/svg";
function col(s){return css.getPropertyValue(COL[s]||"--none").trim()}
function el(n,a,p){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);(p||svg).appendChild(e);return e}
var D=null,SEL=null;
document.getElementById("legend").innerHTML=["busy","free","silent","stalled","untracked","no-session"]
 .map(function(s){return '<span style="--c:'+col(s)+'">'+s+'</span>'}).join("");
function draw(){
 svg.innerHTML="";if(!D)return;
 var W=innerWidth,H=innerHeight,cx=W/2,cy=H/2+16,R=Math.min(W*.36,H*.36),n=D.nodes.length,pos={};
 D.nodes.forEach(function(t,i){
  var orch=t.kind==="orchestrator",a=-Math.PI/2+(i/n)*2*Math.PI;
  pos[t.id]=orch?{x:cx,y:cy-R*.46}:{x:cx+R*Math.cos(a),y:cy+R*Math.sin(a)};});
 D.nodes.forEach(function(t){var p=pos[t.id],c=col(t.status),orch=t.kind==="orchestrator";
  var from=orch?{x:cx,y:cy}:(pos.orchestrator||{x:cx,y:cy});
  el("line",{x1:cx,y1:cy,x2:p.x,y2:p.y,stroke:c,"stroke-opacity":.35,"stroke-width":t.status==="busy"?2:1,
   "class":t.status==="busy"?"busyline":""});});
 // Thebes core
 var core=el("g",{});el("circle",{cx:cx,cy:cy,r:58,fill:"#0b1215",stroke:"#7fd3e6","stroke-width":1.5},core);
 var tt=el("text",{x:cx,y:cy+5,"text-anchor":"middle",fill:"#e8f6fa","font-size":17},core);tt.textContent="Thebes";
 D.nodes.forEach(function(t){var p=pos[t.id],c=col(t.status),g=el("g",{style:"cursor:pointer"});
  if(t.status==="busy")el("circle",{cx:p.x,cy:p.y,r:34,fill:"none",stroke:c,"class":"ring"},g);
  el("circle",{cx:p.x,cy:p.y,r:t.kind==="orchestrator"?34:30,fill:"#0b1215",stroke:c,"stroke-width":2.5,
   opacity:D.stale?.5:1},g);
  var a=el("text",{x:p.x,y:p.y-1,"text-anchor":"middle",fill:"#ecf4f8","font-size":11.5},g);a.textContent=t.name.length>11?t.name.slice(0,10)+"…":t.name;
  var b=el("text",{x:p.x,y:p.y+13,"text-anchor":"middle",fill:c,"font-size":10},g);b.textContent=t.ticket||t.status;
  g.addEventListener("click",function(e){e.stopPropagation();SEL=t.id;tip()});});
}
function tip(){var t=D&&D.nodes.filter(function(x){return x.id===SEL})[0],e=document.getElementById("tip");
 if(!t){e.style.display="none";return}
 e.style.display="block";
 e.innerHTML='<b>'+t.name+'</b> <span class="mono">'+t.kind+(t.lane?" · "+t.lane:"")+'</span><div style="margin:10px 0;color:'+col(t.status)+'">'+t.status+
  ' <span class="mono">'+(WORD[t.status]||"")+'</span></div>'+
  (t.ticket?'<div>'+t.ticket+(t.jira?' <span class="mono">in '+t.jira+'</span>':'')+'</div>':'')+
  (t.detail&&t.detail!==t.ticket?'<div class="mono" style="margin-top:6px">'+t.detail+'</div>':'')+
  (t.owns.length?'<div class="mono" style="margin-top:6px">owns '+t.owns.join(", ")+'</div>':'')+
  (t.quiet_min!=null?'<div class="mono" style="margin-top:6px">quiet '+t.quiet_min+' min</div>':'')+
  (t.session?'<div class="mono">session '+t.session+'</div>':'');}
document.body.addEventListener("click",function(){SEL=null;tip()});
function poll(){fetch("/api/live").then(function(r){return r.json()}).then(function(d){D=d;
 var m=d.age_seconds==null?"no snapshot":Math.round(d.age_seconds/60)+" min ago";
 document.getElementById("age").textContent="snapshot "+m;
 document.getElementById("loops").innerHTML=d.loops.map(function(l){
  return '<span style="color:'+(l.up?"var(--busy)":l.up===false?"var(--stalled)":"var(--none)")+'">'+l.name+(l.up?" up":l.up===false?" DOWN":" ?")+'</span>'}).join(" &nbsp; ");
 var w=document.getElementById("warn");
 w.style.display=d.stale?"block":"none";w.textContent=d.stale?"snapshot is stale — the watchdog may be down; colours are not live":"";
 draw();tip();}).catch(function(){})}
addEventListener("resize",draw);poll();setInterval(poll,5000);
</script></body></html>"""


SHELL = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thebes</title>
<style>
html,body{margin:0;height:100%;background:#07090b;color:#ecf4f8;font:13px Geist,system-ui,sans-serif}
#tabs{display:flex;gap:4px;padding:8px 16px 0;border-bottom:1px solid rgba(255,255,255,.07)}
#tabs button{background:none;border:0;color:rgba(236,244,248,.5);padding:8px 16px;font:inherit;cursor:pointer;
border-bottom:2px solid transparent}
#tabs button.on{color:#ecf4f8;border-bottom-color:#7fd3e6}
iframe{position:absolute;top:42px;left:0;right:0;bottom:0;width:100%;height:calc(100% - 42px);border:0;display:none}
iframe.on{display:block}
</style></head><body>
<div id="tabs"><button class="on" data-t="map">Live map</button><button data-t="view">Agent View</button></div>
<iframe class="on" id="map" src="/map"></iframe><iframe id="view" data-src="/agent-view"></iframe>
<script>
document.querySelectorAll("#tabs button").forEach(function(b){b.onclick=function(){
 document.querySelectorAll("#tabs button").forEach(function(x){x.classList.toggle("on",x===b)});
 ["map","view"].forEach(function(id){var f=document.getElementById(id);
  if(id===b.dataset.t&&!f.src&&f.dataset.src)f.src=f.dataset.src;f.classList.toggle("on",id===b.dataset.t)});
 try{location.hash=b.dataset.t}catch(e){}}});
if(location.hash==="#view")document.querySelector('[data-t="view"]').click();
</script></body></html>"""
