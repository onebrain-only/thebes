"""The decision group: a gate in front of the accountable role (D-031).

When a team or seat ends a conversation dispatch with `decision_required`,
`blocked` or `clarification_required`, the question does NOT go back to the
Codex Listener. It goes here:

  1. the GATE classifies the question into one decision class of
     `agent/state/registry/authority.json` and scores its confidence
     (FakeGate: keyword table; JevGate: TypeSafe Jev typed Choice). The gate
     never writes the decision — it only says WHO owns it and how sure it is;
  2. below the threshold, or when the owner is the CEO, or when the gate or the
     owner's session is unavailable, the question ESCALATES: it returns to the
     origin Codex conversation exactly as before (D-031's degradation rule);
  3. otherwise a `decision_request` is recorded and the question is delivered
     to the accountable role's bound session (po, cto, cpo, cxo, pm, qa, devops,
     analyst, content-manager) as one THEBES_DECISION_REQUEST turn;
  4. the owner answers once (`decision_gate answer`, identity = its own session
     id plus the request's capability); Thebes then resumes the SAME asking
     island/seat with a THEBES_DECISION_ANSWER dispatch on the same origin
     thread, so the final `completed` still reaches Codex and Codex never sees
     the loop.

`task_owner` classes are the asker's own authority: the answer is "you own
this; decide and continue", delivered straight back to the asker.

    python3 -m agent.execution.decision_gate classify "<question text>"
    THEBES_DECISION_CAPABILITY=<cap> python3 -m agent.execution.decision_gate answer <dreq-id> \\
        (--answer "<text>" | --answer-file <path>)
    python3 -m agent.execution.decision_gate status [<dreq-id>]
"""
import argparse
import hmac
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.state import roster, store                              # noqa: E402

CONFIG_PATH = os.path.join(ROOT, "agent", "state", "registry", "decision_gate.json")
AUTHORITY_PATH = os.path.join(ROOT, "agent", "state", "registry", "authority.json")
DECISION_OUTCOMES = ("decision_required", "blocked", "clarification_required")
CAPABILITY_ENV = "THEBES_DECISION_CAPABILITY"
JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_KEY_ENV = "TYPESAFE_API_KEY"
MAX_ANSWER_BYTES = 100_000
CEO = "ceo"
TASK_OWNER = "task_owner"
SCRUBBED_ENV = ("CODEX_THREAD_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", CAPABILITY_ENV)


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__("%s: %s" % (code, message))
        self.code = code


def config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def decision_classes(path=AUTHORITY_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["decision_classes"]


# ---------------------------------------------------------------- gates
class FakeGate:
    """Deterministic keyword classifier. P2 only; never a judgement."""
    gate_id = "fake"

    def __init__(self, cfg):
        self.table = cfg.get("fake_keywords") or {}

    def classify(self, text):
        low = (text or "").lower()
        # A phrase outweighs a word: "acceptance criteria" is a stronger signal
        # than "scope" appearing somewhere in a long report (seen live, P2).
        hits = {cls: sum(len(kw.split()) for kw in kws if kw in low)
                for cls, kws in self.table.items()}
        best = max(hits.items(), key=lambda kv: kv[1]) if hits else (None, 0)
        if best[1] == 0:
            return {"decision_class": "task_local_technical", "confidence": 0.4,
                    "gate": self.gate_id, "evidence": "no keyword matched"}
        tied = [c for c, v in hits.items() if v == best[1] and c != best[0]]
        if tied:
            return {"decision_class": best[0], "confidence": 0.5, "gate": self.gate_id,
                    "evidence": "tie between %s and %s" % (best[0], ", ".join(tied))}
        others = sum(v for k, v in hits.items() if k != best[0])
        return {"decision_class": best[0], "confidence": 0.9 if others == 0 else 0.75,
                "gate": self.gate_id, "evidence": "weight %d, others %d" % (best[1], others)}


def read_key(provider, env=None):
    """The gate's API key: a 0600 file outside the repo first (sessions started
    by Thebes do not inherit a terminal's variables), then the variable."""
    env = os.environ if env is None else env
    path = os.path.expanduser(provider.get("key_file") or "")
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            key = fh.read().strip()
        if key:
            return key
    return (env.get(provider.get("key_env") or JEV_KEY_ENV) or "").strip()


class JevGate:
    """TypeSafe Jev: ONE typed Choice over the decision classes. No text.

    The route is configuration (D-031): `jev_provider` in decision_gate.json
    names the base URL, model id and key location, so direct TypeSafe,
    OpenRouter and the Vercel AI Gateway are one edit apart."""
    gate_id = "jev"

    def __init__(self, cfg, env=None, opener=None):
        self.env = os.environ if env is None else env
        self.opener = opener or urllib.request.urlopen
        self.provider = dict({"url": JEV_URL, "model": "jev-latest", "key_env": JEV_KEY_ENV},
                             **(cfg.get("jev_provider") or {}))

    def classify(self, text):
        key = read_key(self.provider, self.env)
        if not key:
            raise Refused("decision-gate-unavailable",
                          "no API key in %s or $%s" % (self.provider.get("key_file"),
                                                       self.provider.get("key_env")))
        classes = decision_classes()
        body = json.dumps({
            "model": self.provider["model"],
            "state": {"question": text},
            "questions": {"decision_class": {
                "type": "choice",
                "instructions": "Which decision class of a software company owns this question?",
                "criteria": {cls: "accountable role: %s" % rule["accountable_role"]
                             for cls, rule in classes.items()}}},
        }).encode("utf-8")
        req = urllib.request.Request(self.provider["url"], data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer %s" % key})
        try:
            with self.opener(req, timeout=30) as resp:
                answer = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise Refused("decision-gate-unavailable", "jev: %s" % exc)
        a = ((answer.get("answers") or {}).get("decision_class") or {})
        choice, confidence = a.get("choice"), a.get("confidence")
        if choice not in classes or not isinstance(confidence, (int, float)):
            raise Refused("decision-gate-malformed", json.dumps(a)[:300])
        return {"decision_class": choice, "confidence": float(confidence), "gate": self.gate_id,
                "evidence": json.dumps(a.get("probabilities") or {})[:300]}


def gate_for(cfg=None, env=None):
    cfg = cfg or config()
    name = cfg.get("gate", "fake")
    if name == "jev":
        return JevGate(cfg, env=env)
    if name == "fake":
        return FakeGate(cfg)
    raise Refused("decision-gate-unknown", name)


# ---------------------------------------------------------------- approvals (D-033)
def ceo_only_hit(text, cfg=None):
    """The deny-list, matched in plain code before any model is asked.
    Returns the category name, or None.

    The three CEO categories come from the autonomy constitution (CEO 2026-10-27): the
    sentence must ASK for the act and not negate it ("nothing to main" is not a request).
    The keyword categories left in decision_gate.json are the orchestrator's to decide."""
    from agent.state import autonomy
    cat = autonomy.ceo_hit(text)
    if cat:
        return cat
    cfg = cfg or config()
    low = (text or "").lower()
    for category, patterns in ((cfg.get("approval") or {}).get("ceo_only") or {}).items():
        for p in patterns:
            if p.startswith("re:"):
                if re.search(p[3:], low):
                    return category
            elif p in low:
                return category
    return None


class FakeApprovalGate:
    gate_id = "fake"

    def __init__(self, cfg):
        self.routine = (cfg.get("approval") or {}).get("routine") or {}
        self.hints = {
            "branch_or_commit": ["commit", "branch"], "run_checks": ["test", "lint", "analyze"],
            "code_generation": ["build_runner", "codegen"], "read_only_query": ["read-only", "query"],
            "jira_comment": ["comment"], "open_pull_request": ["pull request", " pr "],
            "retry_once": ["retry"], "release_worktree": ["worktree", "temp"]}

    def classify(self, text):
        low = (text or "").lower()
        for action, words in self.hints.items():
            if any(w in low for w in words):
                return {"action": action, "confidence": 0.9, "gate": self.gate_id}
        return {"action": "not_routine", "confidence": 0.9, "gate": self.gate_id}


class JevApprovalGate(JevGate):
    """ONE typed Choice over the routine actions plus `not_routine`."""

    def classify(self, text):
        key = read_key(self.provider, self.env)
        if not key:
            raise Refused("decision-gate-unavailable", "no API key")
        routine = (config().get("approval") or {}).get("routine") or {}
        body = json.dumps({
            "model": self.provider["model"], "state": {"request": text},
            "questions": {"action": {
                "type": "choice",
                "instructions": "A software worker asks permission for this. Which routine action "
                                "is it, exactly? If it is a question, a judgement, or an action not "
                                "listed, choose not_routine.",
                "criteria": routine}}}).encode("utf-8")
        req = urllib.request.Request(self.provider["url"], data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer %s" % key})
        try:
            with self.opener(req, timeout=30) as resp:
                answer = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise Refused("decision-gate-unavailable", "jev: %s" % exc)
        a = (answer.get("answers") or {}).get("action") or {}
        if a.get("choice") not in routine or not isinstance(a.get("confidence"), (int, float)):
            raise Refused("decision-gate-malformed", json.dumps(a)[:300])
        return {"action": a["choice"], "confidence": float(a["confidence"]), "gate": "jev",
                "evidence": json.dumps(a.get("probabilities") or {})[:300]}


def approval_verdict(text, *, cfg=None, env=None):
    """D-033 in one call. Returns {verdict: ceo|approved|not_routine|unavailable, ...}."""
    cfg = cfg or config()
    hit = ceo_only_hit(text, cfg)
    if hit:
        return {"verdict": "ceo", "reason": "ceo-only:%s" % hit}
    name = cfg.get("gate", "fake")
    try:
        gate = JevApprovalGate(cfg, env=env) if name == "jev" else FakeApprovalGate(cfg)
        v = gate.classify(text)
    except Refused as exc:
        return {"verdict": "unavailable", "reason": exc.code}
    threshold = float((cfg.get("approval") or {}).get("threshold", 0.7))
    if v["action"] == "not_routine" or v["confidence"] < threshold:
        return dict(v, verdict="not_routine", reason="not-routine-or-unsure")
    return dict(v, verdict="approved", reason="routine:%s" % v["action"])


# ------------------------------------------------------- exhausted reviews
# CEO 2026-10-22 ("this kind of message should go and get approved directly"): a review that is
# still failing after MAX_CYCLES because the reviewer could not EXECUTE part of the scope (a
# locale or theme it cannot switch without writing live data, a device it does not have) is not a
# product defect, and asking the CEO to say "accepted" is exactly the blind approval D-035 removes.
# Thebes asks ONE typed Choice and decides; a defect still goes back to the team.
EXHAUSTION_CHOICES = {
    "coverage_limit": "the reviewer could not run or see part of the scope (an environment, device, "
                      "locale, theme or data limit) and did not observe anything wrong",
    "product_defect": "the reviewer observed behaviour that is wrong, missing or failing an "
                      "acceptance criterion",
}
LIMIT_RE = re.compile(r"not run|could not|cannot|can't|unable to|without writing|no device|"
                      r"not available|needs a real device", re.I)
DEFECT_RE = re.compile(r"crash|wrong|incorrect|broken|regress|raw exception|does not (?:show|work|"
                       r"keep|open|appear)|fails? to|still (?:shows|empty|blank)|missing button|"
                       r"error is shown|no longer", re.I)


class FakeExhaustionGate:
    """Deterministic and conservative: only an explicit limit with no defect wording is a limit."""
    gate_id = "fake"

    def __init__(self, cfg):
        pass

    def classify(self, text):
        limit = bool(LIMIT_RE.search(text)) and not DEFECT_RE.search(text)
        return {"choice": "coverage_limit" if limit else "product_defect", "confidence": 0.8,
                "gate": self.gate_id}


class JevExhaustionGate(JevGate):
    def classify(self, text):
        key = read_key(self.provider, self.env)
        if not key:
            raise Refused("decision-gate-unavailable", "no API key")
        body = json.dumps({
            "model": self.provider["model"], "state": {"reviewer_failure_reason": text},
            "questions": {"cause": {
                "type": "choice",
                "instructions": "A reviewer failed a ticket's last check. Is the failure a limit of "
                                "what the reviewer could execute, or a defect it observed in the "
                                "product? If anything wrong was observed choose product_defect.",
                "criteria": EXHAUSTION_CHOICES}}}).encode("utf-8")
        req = urllib.request.Request(self.provider["url"], data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer %s" % key})
        try:
            with self.opener(req, timeout=30) as resp:
                answer = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise Refused("decision-gate-unavailable", "jev: %s" % exc)
        a = (answer.get("answers") or {}).get("cause") or {}
        if a.get("choice") not in EXHAUSTION_CHOICES or not isinstance(a.get("confidence"), (int, float)):
            raise Refused("decision-gate-malformed", json.dumps(a)[:300])
        return {"choice": a["choice"], "confidence": float(a["confidence"]), "gate": "jev"}


def exhaustion_verdict(reason, *, cfg=None, env=None):
    """accept (a limit, confident, and no defect wording) | return (anything else). A wording check
    in code backs the model: a reason that names a defect is never accepted, whatever it says."""
    cfg = cfg or config()
    if DEFECT_RE.search(reason or ""):
        return {"verdict": "return", "reason": "defect-wording"}
    try:
        gate = JevExhaustionGate(cfg, env=env) if cfg.get("gate") == "jev" else FakeExhaustionGate(cfg)
        v = gate.classify(reason)
    except Refused as exc:
        v = FakeExhaustionGate(cfg).classify(reason)          # the gate is down: the strict fallback
        v["gate"] = "fake-fallback:%s" % exc.code
    threshold = float((cfg.get("approval") or {}).get("threshold", 0.7))
    if v["choice"] == "coverage_limit" and v["confidence"] >= threshold:
        return dict(v, verdict="accept", reason="coverage-limit")
    return dict(v, verdict="return", reason="defect-or-unsure")


# ---------------------------------------------------------------- owners
def owner_seat_for_role(role):
    """The one seat instantiating a leadership role, or None."""
    seats = sorted(s for s, e in roster.read().items() if (e or {}).get("role") == role)
    return seats[0] if seats else None


def classify_and_resolve(text, *, cfg=None, env=None, state_store=store):
    """Gate → decision class → accountable role → bound owner session.
    Every path that cannot reach an owner is an ESCALATION with a reason."""
    cfg = cfg or config()
    try:
        verdict = gate_for(cfg, env).classify(text)
    except Refused as exc:
        return {"route": "escalate", "reason": exc.code, "gate": cfg.get("gate"),
                "decision_class": None, "accountable_role": None, "confidence": None}
    role = decision_classes()[verdict["decision_class"]]["accountable_role"]
    out = dict(verdict, accountable_role=role, owner_seat=None, owner_session_id=None)
    if role == TASK_OWNER and verdict["confidence"] >= float(cfg.get("threshold", 0.7)):
        return dict(out, route="task-owner")
    from agent.state import teams
    orch = state_store.active_role_session(teams.ORCHESTRATOR_ID)
    orch_ok = orch is not None and orch.get("provider") == "claude"
    # D-035: the CEO delegated every decision to the orchestrator except the
    # D-033 hard-stop list (checked before this function runs). So an unsure
    # gate, a CEO-class question or an unbound seat all go to the orchestrator,
    # which decides who answers; only an UNBOUND orchestrator escalates.
    unsure = verdict["confidence"] < float(cfg.get("threshold", 0.7))
    seat = None if role in (CEO, TASK_OWNER) else owner_seat_for_role(role)
    if orch_ok:
        return dict(out, route="owner", owner_seat=seat, owner_session_id=orch["session_id"],
                    owner_stable_home=orch.get("stable_home"), via="orchestrator",
                    reason=("gate-unsure" if unsure else
                            "ceo-class-delegated" if role == CEO else None))
    if unsure:
        return dict(out, route="escalate", reason="orchestrator-unbound:gate-unsure")
    if role == CEO:
        return dict(out, route="escalate", reason="orchestrator-unbound:ceo-class")
    binding = state_store.active_role_session(seat) if seat else None
    if binding is None or binding.get("provider") != "claude":
        return dict(out, route="escalate", reason="decision-owner-unbound", owner_seat=seat)
    return dict(out, route="owner", owner_seat=seat, owner_session_id=binding["session_id"],
                owner_stable_home=binding.get("stable_home"), via="seat")


# ---------------------------------------------------------------- the request
def _ref(state_store, sub, rid):
    d = os.path.join(state_store.RUNTIME, sub)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.txt" % rid)


def answer_command(request_id, capability):
    return ("cd %s && %s=%s python3 -m agent.execution.decision_gate answer %s "
            "--answer-file <path-to-your-decision.md>"
            % (ROOT, CAPABILITY_ENV, capability, request_id))


def request_envelope(req, capability, question):
    return "\n".join([
        "THEBES_DECISION_REQUEST decision-v1",
        "decision_request_id: %s" % req["decision_request_id"],
        "decision_class: %s (you are the accountable role: %s)"
        % (req["decision_class"], req["accountable_role"]),
        "asked_by: %s (session %s), working for origin conversation %s"
        % (req["asker_seat_id"], req["asker_session_id"], req["origin_thread_id"]),
        "expected_owner_sid: %s — verify $CLAUDE_CODE_SESSION_ID matches; if not, do nothing."
        % req["owner_session_id"],
    ] + ([
        ("you_are: the Thebes ORCHESTRATOR (D-034). Run the accountable seat `%s` as a subagent "
         "in THIS session (Agent tool, subagent_type=%s) after reserving it: cd %s && python3 -m "
         "agent.execution.team_pool reserve %s --dispatch %s . Its decision is the answer; you "
         "may add a second seat only if the question genuinely spans two roles. The reservation "
         "is released when you answer."
         % (req["owner_seat"], req["owner_seat"], ROOT, req["owner_seat"],
            req["decision_request_id"])) if req.get("owner_seat") else
        ("you_are: the Thebes ORCHESTRATOR (D-034). The gate could not name one owner "
         "(%s). YOU decide which leadership seat answers — cpo (scope, product), cto "
         "(technical), cxo (experience), pm (priority, next work), po (acceptance, tickets), "
         "qa, devops, analyst, content-manager — reserve it (cd %s && python3 -m "
         "agent.execution.team_pool reserve <seat> --dispatch %s), run it as a subagent, and "
         "answer." % (req.get("escalation_reason") or "unsure", ROOT, req["decision_request_id"])),
        "delegation (autonomy constitution, CEO 2026-10-27): the CEO is out of the product "
        "cycle and has delegated EVERY decision to you. Never answer 'this needs the CEO', "
        "'ask the CEO', or 'awaiting CEO decision'. Decide within the roles and say who "
        "decided. Production data, migrations, DROPs, deploys and secrets are Memphis's or "
        "yours, never his. The ONLY three things that reach him are enforced by Thebes before "
        "you see a question: spending money, merging into main, sending outside the company.",
    ] if req.get("via") == "orchestrator" else []) + [
        "what_to_do: decide this question within the Role's authority (agent/roles/%s.md). Give "
        "the decision, the reason, and what the asker should do next. If it is genuinely not "
        "that Role's to decide, say so and name whose it is." % req["accountable_role"]
        + (" ACCEPTANCE: start the answer with the single word ACCEPTED or REJECTED; ACCEPTED "
           "closes the ticket in Jira by itself, REJECTED leaves it for rework."
           if req.get("decision_class") == "work_acceptance" else ""),
        "report: write your decision to a file and run exactly once: %s"
        % answer_command(req["decision_request_id"], capability),
        "report_rules: one answer per request; never contact the origin or the asker directly; "
        "Thebes resumes the asker with your answer.",
        "",
        "--- question ---",
        question,
    ])


def answer_envelope(req, answer_text):
    return "\n".join([
        "THEBES_DECISION_ANSWER decision-v1",
        "decision_request_id: %s" % req["decision_request_id"],
        "in_reply_to_dispatch: %s" % req["origin_dispatch_id"],
        "decided_by: %s (%s)" % (req["accountable_role"], req.get("owner_seat") or TASK_OWNER),
        "Continue the original task you reported %s on, using this decision. When the task is "
        "done, report `completed` through the report command in THIS envelope's header — the "
        "report goes to the conversation that asked." % req["origin_outcome"],
        "--- decision ---",
        answer_text,
    ])


def recorded_approval(state_store=store, cfg=None):
    """Has the CEO recorded an approval that covers in-scope production work? A line in the PM
    ledger written by `ceo` under one of the configured refs (e.g. supabase-messaging-approval)."""
    cfg = cfg or config()
    refs = set((cfg.get("approval") or {}).get("recorded_refs") or [])
    try:
        from agent.execution import pm_ledger
        with open(pm_ledger.path(state_store), encoding="utf-8") as fh:
            for line in fh:
                parts = [x.strip() for x in line.lstrip("- ").split(" · ", 3)]
                if len(parts) >= 3 and parts[1] == "ceo" and parts[2] in refs:
                    return True
    except OSError:
        pass
    return False


def decides_inside(approval, state_store=store, cfg=None):
    """CEO 2026-10-14: a prompt that reaches the CEO is approved without being read, so it is not a
    safety check; only money, merging into main and sending outside the company are his
    (autonomy constitution, 2026-10-27). A deny-list
    hit in any other category is the ORCHESTRATOR's to decide (and `production` too once a CEO
    approval is recorded). Returns True for those categories."""
    cfg = cfg or config()
    a = cfg.get("approval") or {}
    cat = str(approval.get("reason") or "").split(":", 1)[-1]
    if cat in (a.get("orchestrator_decides") or []):
        return True
    return cat in (a.get("orchestrator_decides_with_recorded_approval") or []) and \
        recorded_approval(state_store, cfg)


def _to_orchestrator(state_store, base, reason):
    """Route to the orchestrator's inbox. With no orchestrator session bound the request still
    waits there (owner_session_id None) and the next orchestrator session collects it — it never
    falls through to the CEO."""
    from agent.state import teams
    orch = state_store.active_role_session(teams.ORCHESTRATOR_ID)
    bound = orch is not None and orch.get("provider") == "claude"
    return dict(base, route="owner", via="orchestrator", owner_seat=None,
                owner_session_id=orch["session_id"] if bound else None,
                owner_stable_home=orch.get("stable_home") if bound else None,
                decision_class=base.get("decision_class") or "technical_architecture",
                accountable_role=base.get("accountable_role") or "cto", reason=reason)


def question_hash(text):
    """The same block reported again: digits ("61st identical answer") and whitespace are
    not what makes two reports different."""
    import hashlib
    t = re.sub(r"\d+", "#", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()[:4000]
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def _epoch(ts):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def repeat_count(repeat_key, qhash, *, state_store=store, now=None):
    """(same, burst) for one ticket: earlier requests with this question hash inside the window,
    and all requests inside the burst window. Requests before the ticket's last `stuck` do not
    count — a new brief after a stop starts clean."""
    import time
    from agent.state import autonomy
    g = autonomy.repeat_guard()
    now = now or time.time()
    mine = [r for r in state_store.read_all("decision_request") if r.get("repeat_key") == repeat_key]
    last_stuck = max([_epoch(r.get("created_at")) for r in mine if r.get("route") == "stuck"] or [0])
    same = burst = 0
    for r in mine:
        t = _epoch(r.get("created_at"))
        if t <= last_stuck or r.get("route") == "stuck":
            continue
        if r.get("question_hash") == qhash and now - t <= g["window_hours"] * 3600:
            same += 1
        if now - t <= g["burst_hours"] * 3600:
            burst += 1
    return same, burst


def _mark_stuck(ticket, why, *, state_store=store, jira=None):
    """Best effort: label the ticket `stuck` and say why. Never raises. `jira=False` skips it."""
    if not ticket or jira is False:
        return None
    try:
        from agent.execution import jira_sync
        from agent.state import autonomy
        label = autonomy.repeat_guard()["label"]
        jira = jira_sync._client(jira, state_store)
        if jira is None:
            return None
        labels = list(jira.get_issue(ticket).get("labels") or [])
        if label not in labels:
            jira.update_issue(ticket, {"labels": labels + [label]})
        jira.add_comment(ticket, "Thebes: stopped a loop on this ticket. %s The team will not be "
                                 "resumed with the same answer again; the orchestrator re-briefs "
                                 "it (remove the `%s` label when the new brief is in)." % (why, label))
        return {"status": "ok"}
    except Exception as exc:                                  # noqa: BLE001
        return {"status": "failed", "error": str(exc)[:200]}


def route(record, *, state_store=store, env=None, cfg=None, deliver=None, resume=None, jira=None):
    """Called once a dispatch settled with a decision outcome. Returns a dict
    with `route` in {owner, task-owner, approved, escalate, stuck} and what was done."""
    with open(record["result_ref"], encoding="utf-8") as fh:
        question = fh.read()
    from agent.state import autonomy
    guard = autonomy.repeat_guard()
    qhash = question_hash(question)
    repeat_key = record.get("jira_key") or record.get("root_dispatch_id") or record["dispatch_id"]
    same, burst = repeat_count(repeat_key, qhash, state_store=state_store)
    # D-033 first: a routine permission is approved by policy and the worker
    # resumes at once — no owner, no CEO, no Claude session woken. The deny-list
    # inside approval_verdict runs before any model and wins over any score.
    approval = approval_verdict(question, cfg=cfg, env=env)
    if same + 1 >= guard["stuck_at"] or burst + 1 > guard["burst_max"]:
        # The loop breaker (KAN-645, 140 dispatches in a night): the same answer did not help
        # twice, so a third resume would not either. Stop, label, tell the orchestrator. Never
        # the CEO — not even when the question is one of his categories, it is a loop first.
        why = ("The team reported the same block %d times." % (same + 1) if same + 1 >= guard["stuck_at"]
               else "%d decision requests in %d hours." % (burst + 1, guard["burst_hours"]))
        resolved = {"route": "stuck", "reason": "repeat:%s" % why, "gate": "repeat-guard",
                    "decision_class": None, "accountable_role": "orchestrator", "confidence": None}
    elif same + 1 >= guard["orchestrator_at"] and approval["verdict"] != "ceo":
        # Second identical report: "it is yours to decide" did not unblock it. The orchestrator
        # decides differently (a ruling, a re-brief), instead of the same automatic answer.
        resolved = _to_orchestrator(state_store, {
            "gate": "repeat-guard", "decision_class": "technical_architecture",
            "accountable_role": "cto", "confidence": None},
            "repeat:%d identical reports; the automatic answer did not unblock it — decide "
            "differently (a ruling or a new brief), not 'it is yours'" % (same + 1))
    elif approval["verdict"] == "ceo" and decides_inside(approval, state_store, cfg):
        resolved = classify_and_resolve(question, cfg=cfg, env=env, state_store=state_store)
        if resolved["route"] == "escalate":              # no gate answer: still the orchestrator's
            from agent.state import teams
            orch = state_store.active_role_session(teams.ORCHESTRATOR_ID)
            if orch and orch.get("provider") == "claude":
                resolved = dict(resolved, route="owner", via="orchestrator", owner_seat=None,
                                owner_session_id=orch["session_id"],
                                owner_stable_home=orch.get("stable_home"),
                                decision_class=resolved.get("decision_class") or "technical_architecture",
                                accountable_role=resolved.get("accountable_role") or "cto")
        resolved["reason"] = "orchestrator-decides:%s" % approval["reason"]
    elif approval["verdict"] == "ceo":
        resolved = {"route": "escalate", "reason": approval["reason"], "gate": "policy",
                    "decision_class": None, "accountable_role": CEO, "confidence": None}
    elif approval["verdict"] == "approved":
        resolved = {"route": "approved", "reason": approval["reason"], "gate": approval["gate"],
                    "decision_class": "routine_action", "accountable_role": "policy",
                    "confidence": approval["confidence"], "action": approval["action"]}
    else:
        resolved = classify_and_resolve(question, cfg=cfg, env=env, state_store=state_store)
    ceo_reasons = {"ceo-only:%s" % c for c in autonomy.load()["ceo_only"]["categories"]}
    if resolved["route"] == "escalate" and resolved.get("reason") not in ceo_reasons:
        # Constitution: only the three CEO categories may escalate. A gate that is down, an
        # unsure classification or an unbound orchestrator is Thebes's problem — the request
        # waits in the orchestrator's inbox instead of reaching the CEO.
        resolved = _to_orchestrator(state_store, resolved, "held-for-orchestrator:%s"
                                    % resolved.get("reason"))
    rid = state_store.new_id("decision_request")
    question_ref = _ref(state_store, "decision-questions", rid)
    with open(question_ref, "w", encoding="utf-8") as fh:
        fh.write(question)
    capability = secrets.token_urlsafe(32)
    req = state_store.create("decision_request", {
        "decision_request_id": rid, "origin_dispatch_id": record["dispatch_id"],
        "origin_thread_id": record["origin_thread_id"], "origin_outcome": record["outcome"],
        "asker_seat_id": record["target_seat_id"], "asker_session_id": record["target_session_id"],
        "question_ref": question_ref, "gate": resolved.get("gate"),
        "decision_class": resolved.get("decision_class"),
        "accountable_role": resolved.get("accountable_role"),
        "confidence": resolved.get("confidence"), "route": resolved["route"],
        "escalation_reason": resolved.get("reason"), "owner_seat": resolved.get("owner_seat"),
        "owner_session_id": resolved.get("owner_session_id"),
        "owner_stable_home": resolved.get("owner_stable_home"), "via": resolved.get("via"),
        "approved_action": resolved.get("action"),
        "capability_sha256": state_store.capability_sha256(capability),
        "repeat_key": repeat_key, "question_hash": qhash,
        "status": "open", "answer_ref": None, "answered_by_session_id": None,
        "continuation_dispatch_id": None, "error": None}, rid=rid)
    if resolved["route"] == "stuck":
        cur = state_store.update("decision_request", rid, req["revision"], {"status": "stuck"})
        return dict(resolved, decision_request_id=rid, request=cur,
                    jira=_mark_stuck(record.get("jira_key"), resolved["reason"][len("repeat:"):],
                                     state_store=state_store, jira=jira))
    if resolved["route"] == "escalate":
        return dict(resolved, decision_request_id=rid, request=state_store.update(
            "decision_request", rid, req["revision"], {"status": "escalated"}))
    if resolved["route"] == "approved":
        text = ("APPROVED by policy (D-033): %s. Gate %s, confidence %.2f. Proceed with exactly "
                "that action and continue the task; do not ask again for the same action."
                % (resolved["action"], resolved["gate"], resolved["confidence"]))
        return dict(resolved, decision_request_id=rid,
                    continuation=_resume_asker(req, text, state_store=state_store, resume=resume))
    if resolved["route"] == "task-owner":
        text = ("This question is task-local (%s): it is yours to decide within the brief. "
                "Decide, record why in your report, and continue." % resolved["decision_class"])
        return dict(resolved, decision_request_id=rid,
                    continuation=_resume_asker(req, text, state_store=state_store, resume=resume))
    sender = deliver or (_deliver_to_inbox if req.get("via") == "orchestrator"
                         else _deliver_to_owner)
    try:
        sent = sender(req, request_envelope(req, capability, question), state_store=state_store)
    except Exception as exc:                        # fail closed: the orchestrator's inbox, never lost
        cur = state_store.read("decision_request", rid)
        state_store.update("decision_request", rid, cur["revision"], {
            "via": "orchestrator", "owner_seat": None,
            "owner_session_id": _to_orchestrator(state_store, {}, "")["owner_session_id"],
            "escalation_reason": "owner-delivery-failed", "error": str(exc)[:300]})
        sent = _deliver_to_inbox(req, None, state_store=state_store)
        return dict(resolved, route="owner", via="orchestrator", reason="owner-delivery-failed",
                    decision_request_id=rid, delivery=sent)
    return dict(resolved, decision_request_id=rid, delivery=sent)


def _deliver_to_inbox(req, message, *, state_store=store):
    """D-039: the orchestrator is the CEO's live conversation, so it is never
    stopped and resumed. The request waits in its inbox; `agent.execution.inbox
    wait` hands it over with a fresh capability. `message` is not stored: it
    carries the capability, which never touches disk."""
    cur = state_store.read("decision_request", req["decision_request_id"])
    state_store.update("decision_request", cur["decision_request_id"], cur["revision"],
                       {"delivery": "inbox", "inbox_collected_at": None})
    return {"status": "INBOX", "decision_request_id": req["decision_request_id"]}


def _deliver_to_owner(req, message, *, state_store=store, delivery_id=None):
    from agent.execution import claude_delivery
    from agent.execution.claude_cli import ClaudeCli
    from agent.state import teams
    target_seat = teams.ORCHESTRATOR_ID if req.get("via") == "orchestrator" else req["owner_seat"]
    delivery_id = delivery_id or req["decision_request_id"]
    base = {"dispatch_id": req["decision_request_id"], "work_item_id": None,
            "seat_id": target_seat, "provider": "claude",
            "envelope_version": "decision-v1", "expected_worker_sid": req["owner_session_id"],
            "report_to": None}
    home = req.get("owner_stable_home") or (state_store.active_role_session(target_seat) or {}).get(
        "stable_home")
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}
    res = claude_delivery.deliver_prompt(
        delivery_id, req["decision_request_id"], base, req["owner_session_id"],
        home, message, state_store=state_store, cli=ClaudeCli(env=env))
    if res.status != claude_delivery.DELIVERED:
        raise Refused("owner-delivery-failed", res.error or res.status)
    return res.as_dict()


def _resume_asker(req, answer_text, *, state_store=store, resume=None):
    """One continuation dispatch to the SAME asker session on the SAME origin
    thread. Its `completed` is what Codex finally hears."""
    text = answer_envelope(req, answer_text)
    if resume is not None:                                      # test seam
        out = resume(req, text, state_store=state_store)
    else:
        from agent.execution import conversation_dispatch as cd
        origin = state_store.read("conversation_dispatch", req["origin_dispatch_id"]) or {}
        env = {k: v for k, v in os.environ.items()
               if k not in ("CODEX_THREAD_ID", cd.CLAUDE_ORIGIN_ENV)}
        if origin.get("origin_provider") == "claude":       # D-039: the orchestrator asked
            env[cd.CLAUDE_ORIGIN_ENV] = req["origin_thread_id"]
            env.update(THEBES_ACTOR="decision-gate", THEBES_RULE="decision-gate")
        else:
            env["CODEX_THREAD_ID"] = req["origin_thread_id"]
        # The answer continues the SAME work, so it keeps the same review: the origin's checks,
        # its root and its cycle. Without them (live 2026-10-13, KAN-499) the finished work had
        # no VERIFY block, was never verified, and never reached the reviewer.
        try:
            out = cd.dispatch(text, req["asker_session_id"], env=env, state_store=state_store,
                              detach=True, ticket=origin.get("jira_key"),
                              lane_capability=origin.get("jira_capability"),
                              continuation=True, checks=origin.get("checks") or None,
                              root_dispatch_id=origin.get("root_dispatch_id")
                              or (origin.get("dispatch_id") if origin.get("checks") else None),
                              verify_cycle=origin.get("verify_cycle"))
        except cd.Refused as exc:
            if exc.code != "target-session-busy":
                raise
            # The asker is on another dispatch right now. The answer must not be lost (2026-10-14):
            # keep it, mark the request, and retry_resumes() sends it the moment the team is free.
            path = _ref(state_store, "decision-resume", req["decision_request_id"])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            cur = state_store.read("decision_request", req["decision_request_id"])
            state_store.update("decision_request", cur["decision_request_id"], cur["revision"],
                               {"status": "answered", "pending_resume_ref": path})
            return {"status": "queued", "reason": str(exc)[:200]}
    cur = state_store.read("decision_request", req["decision_request_id"])
    state_store.update("decision_request", cur["decision_request_id"], cur["revision"],
                       {"status": "answered", "continuation_dispatch_id": out.get("dispatch_id")})
    return out


def retry_resumes(*, state_store=store, dispatch=None):
    """Send every answer that was queued because its asker was busy, as soon as it is free.
    Never raises; the Ready dispatcher calls it every tick."""
    from agent.execution import conversation_dispatch as cd
    done = []
    try:
        for req in state_store.read_all("decision_request"):
            ref = req.get("pending_resume_ref")
            if not ref or req.get("continuation_dispatch_id"):
                continue
            if cd.open_work_for(req["asker_session_id"], state_store):
                continue
            origin = state_store.read("conversation_dispatch", req["origin_dispatch_id"]) or {}
            env = {k: v for k, v in os.environ.items()
                   if k not in ("CODEX_THREAD_ID", cd.CLAUDE_ORIGIN_ENV)}
            if origin.get("origin_provider") == "claude":
                env[cd.CLAUDE_ORIGIN_ENV] = req["origin_thread_id"]
                env.update(THEBES_ACTOR="decision-gate", THEBES_RULE="decision-gate")
            else:
                env["CODEX_THREAD_ID"] = req["origin_thread_id"]
            with open(ref, encoding="utf-8") as fh:
                text = fh.read()
            out = (dispatch or cd.dispatch)(
                text, req["asker_session_id"], env=env, state_store=state_store, detach=True,
                ticket=origin.get("jira_key"), lane_capability=origin.get("jira_capability"),
                continuation=True, checks=origin.get("checks") or None,
                root_dispatch_id=origin.get("root_dispatch_id")
                or (origin.get("dispatch_id") if origin.get("checks") else None),
                verify_cycle=origin.get("verify_cycle"))
            cur = state_store.read("decision_request", req["decision_request_id"])
            state_store.update("decision_request", cur["decision_request_id"], cur["revision"],
                               {"continuation_dispatch_id": out.get("dispatch_id"),
                                "pending_resume_ref": None})
            done.append({"action": "answer-delivered", "key": origin.get("jira_key"),
                         "request": req["decision_request_id"][-8:]})
    except Exception as exc:                               # noqa: BLE001
        done.append({"action": "answer-retry-failed", "error": str(exc)[:200]})
    return done


def redeliver(request_id, *, state_store=store, deliver=None):
    """Re-send an OPEN owner request whose owner lost its turn (seen live:
    'API Error: Connection lost mid-response' ended the orchestrator's turn
    before it answered). A fresh capability is issued — the old one is
    invalidated by replacing its hash — and the same envelope is delivered to
    the same owner session. Bounded by the caller (D-033: retry once)."""
    req = state_store.read("decision_request", request_id)
    if req is None:
        raise Refused("decision-request-not-found", request_id)
    if req["status"] != "open" or req["route"] != "owner":
        raise Refused("decision-request-not-open", "%s is %s/%s" % (request_id, req["status"],
                                                                     req["route"]))
    if req.get("delivery") == "inbox" and deliver is None:
        # The orchestrator's inbox hands it over again on its next collection.
        state_store.update("decision_request", request_id, req["revision"],
                           {"inbox_collected_at": None, "redelivered_at": state_store.now()})
        return {"status": "requeued-to-inbox", "decision_request_id": request_id}
    with open(req["question_ref"], encoding="utf-8") as fh:
        question = fh.read()
    capability = secrets.token_urlsafe(32)
    req = state_store.update("decision_request", request_id, req["revision"], {
        "capability_sha256": state_store.capability_sha256(capability),
        "redelivered_at": state_store.now()})
    # A new delivery id: the first delivery is DELIVERED and final by design.
    delivery_id = "%s-redeliver-%s" % (request_id, secrets.token_hex(3))
    sender = deliver or (lambda r, m, state_store: _deliver_to_owner(
        r, m, state_store=state_store, delivery_id=delivery_id))
    sent = sender(req, request_envelope(req, capability, question), state_store=state_store)
    return {"status": "redelivered", "decision_request_id": request_id, "delivery": sent}


def answer(request_id, answer_text, *, env=None, state_store=store, resume=None):
    """The accountable owner's single answer; then the asker is resumed."""
    env = os.environ if env is None else env
    if not isinstance(answer_text, str) or not answer_text.strip():
        raise Refused("answer-required", "explicit decision text is required")
    if len(answer_text.encode("utf-8")) > MAX_ANSWER_BYTES:
        raise Refused("answer-too-large", "%d bytes" % len(answer_text.encode("utf-8")))
    # The gates run on a fresh read and the write is a revision CAS: a second
    # answer racing this one loses at `update` (stale revision) or at the
    # `open` check, so no record lock is held across the write (store.update
    # takes the record lock itself, and flock does not nest).
    req = state_store.read("decision_request", request_id)
    if req is None:
        raise Refused("decision-request-not-found", request_id)
    cap = env.get(CAPABILITY_ENV) or ""
    if not hmac.compare_digest(state_store.capability_sha256(cap), req["capability_sha256"]):
        raise Refused("capability-invalid", "not the capability issued for %s" % request_id)
    if env.get("CLAUDE_CODE_SESSION_ID") != req.get("owner_session_id"):
        raise Refused("owner-identity-mismatch", "answers come from the owner session only")
    if req["status"] != "open":
        raise Refused("decision-request-not-open", req["status"])
    ref = _ref(state_store, "decision-answers", request_id)
    with open(ref, "w", encoding="utf-8") as fh:
        fh.write(answer_text)
    try:
        req = state_store.update("decision_request", request_id, req["revision"], {
            "answer_ref": ref, "answered_by_session_id": env.get("CLAUDE_CODE_SESSION_ID")})
    except state_store.StateError as exc:
        raise Refused("decision-request-not-open", "lost the race: %s" % exc)
    state_store.release_seat_reservations(request_id, "decision-answered")
    try:                                     # D-042: the PM knows every ruling
        from agent.execution import pm_ledger
        pm_ledger.add(req.get("accountable_role") or "orchestrator",
                      req.get("origin_dispatch_id"), answer_text, state_store=state_store)
    except Exception:                        # noqa: BLE001  the ledger never blocks an answer
        pass
    if req.get("decision_class") == "work_acceptance":       # malfunction #18
        try:
            from agent.execution import jira_sync
            origin = state_store.read("conversation_dispatch", req.get("origin_dispatch_id")) or {}
            jira_sync.on_accepted(origin.get("jira_key"), answer_text, state_store=state_store)
        except Exception:                    # noqa: BLE001  closing a ticket never blocks an answer
            pass
    cont = _resume_asker(req, answer_text, state_store=state_store, resume=resume)
    return {"status": "answered", "decision_request_id": request_id, "continuation": cont}


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.decision_gate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify"); c.add_argument("text")
    a = sub.add_parser("answer"); a.add_argument("request_id")
    a.add_argument("--answer"); a.add_argument("--answer-file")
    rd = sub.add_parser("redeliver", help="re-send an open owner request whose owner lost its turn")
    rd.add_argument("request_id")
    s = sub.add_parser("status"); s.add_argument("request_id", nargs="?")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "classify":
            out = classify_and_resolve(ns.text)
        elif ns.cmd == "answer":
            if (ns.answer is None) == (ns.answer_file is None):
                raise Refused("text-source-required", "give exactly one of --answer/--answer-file")
            if ns.answer is not None:
                text = ns.answer
            else:
                with open(ns.answer_file, encoding="utf-8") as fh:
                    text = fh.read()
            out = answer(ns.request_id, text)
        elif ns.cmd == "redeliver":
            out = redeliver(ns.request_id)
        elif ns.request_id:
            out = store.read("decision_request", ns.request_id)
        else:
            out = sorted(store.read_all("decision_request"),
                         key=lambda r: r.get("created_at") or "")
    except Refused as exc:
        print(json.dumps({"status": "refused", "code": exc.code, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
