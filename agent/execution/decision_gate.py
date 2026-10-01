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


class JevGate:
    """TypeSafe Jev: ONE typed Choice over the decision classes. No text."""
    gate_id = "jev"

    def __init__(self, cfg, env=None, opener=None):
        self.env = os.environ if env is None else env
        self.opener = opener or urllib.request.urlopen

    def classify(self, text):
        key = self.env.get(JEV_KEY_ENV)
        if not key:
            raise Refused("decision-gate-unavailable", "%s is not set" % JEV_KEY_ENV)
        classes = decision_classes()
        body = json.dumps({
            "model": "jev-latest",
            "state": {"question": text},
            "questions": {"decision_class": {
                "type": "choice",
                "instructions": "Which decision class of a software company owns this question?",
                "criteria": {cls: "accountable role: %s" % rule["accountable_role"]
                             for cls, rule in classes.items()}}},
        }).encode("utf-8")
        req = urllib.request.Request(JEV_URL, data=body, method="POST", headers={
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
    if verdict["confidence"] < float(cfg.get("threshold", 0.7)):
        return dict(out, route="escalate", reason="confidence-below-threshold")
    if role == CEO:
        return dict(out, route="escalate", reason="ceo-owned-decision")
    if role == TASK_OWNER:
        return dict(out, route="task-owner")
    seat = owner_seat_for_role(role)
    binding = state_store.active_role_session(seat) if seat else None
    if binding is None or binding.get("provider") != "claude":
        return dict(out, route="escalate", reason="decision-owner-unbound", owner_seat=seat)
    return dict(out, route="owner", owner_seat=seat, owner_session_id=binding["session_id"],
                owner_stable_home=binding.get("stable_home"))


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
        "asked_by: %s (session %s), working for Codex conversation %s"
        % (req["asker_seat_id"], req["asker_session_id"], req["origin_thread_id"]),
        "expected_owner_sid: %s — verify $CLAUDE_CODE_SESSION_ID matches; if not, do nothing."
        % req["owner_session_id"],
        "what_to_do: decide this question within your Role's authority (agent/roles/%s.md). Give "
        "the decision, the reason, and what the asker should do next. If it is genuinely not "
        "yours to decide, say so and name whose it is." % req["accountable_role"],
        "report: write your decision to a file and run exactly once: %s"
        % answer_command(req["decision_request_id"], capability),
        "report_rules: one answer per request; never contact Codex or the asker directly; "
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
        "report goes to the Codex conversation that asked." % req["origin_outcome"],
        "--- decision ---",
        answer_text,
    ])


def route(record, *, state_store=store, env=None, cfg=None, deliver=None, resume=None):
    """Called once a dispatch settled with a decision outcome. Returns a dict
    with `route` in {owner, task-owner, escalate} and what was done."""
    with open(record["result_ref"], encoding="utf-8") as fh:
        question = fh.read()
    resolved = classify_and_resolve(question, cfg=cfg, env=env, state_store=state_store)
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
        "capability_sha256": state_store.capability_sha256(capability),
        "status": "open", "answer_ref": None, "answered_by_session_id": None,
        "continuation_dispatch_id": None, "error": None}, rid=rid)
    if resolved["route"] == "escalate":
        return dict(resolved, decision_request_id=rid, request=state_store.update(
            "decision_request", rid, req["revision"], {"status": "escalated"}))
    if resolved["route"] == "task-owner":
        text = ("This question is task-local (%s): it is yours to decide within the brief. "
                "Decide, record why in your report, and continue." % resolved["decision_class"])
        return dict(resolved, decision_request_id=rid,
                    continuation=_resume_asker(req, text, state_store=state_store, resume=resume))
    sender = deliver or _deliver_to_owner
    try:
        sent = sender(req, request_envelope(req, capability, question), state_store=state_store)
    except Exception as exc:                        # fail closed: escalate, never lose it
        state_store.update("decision_request", rid, req["revision"],
                           {"status": "escalated", "escalation_reason": "owner-delivery-failed",
                            "error": str(exc)[:300]})
        return dict(resolved, route="escalate", reason="owner-delivery-failed",
                    decision_request_id=rid)
    return dict(resolved, decision_request_id=rid, delivery=sent)


def _deliver_to_owner(req, message, *, state_store=store):
    from agent.execution import claude_delivery
    from agent.execution.claude_cli import ClaudeCli
    base = {"dispatch_id": req["decision_request_id"], "work_item_id": None,
            "seat_id": req["owner_seat"], "provider": "claude",
            "envelope_version": "decision-v1", "expected_worker_sid": req["owner_session_id"],
            "report_to": None}
    binding = state_store.active_role_session(req["owner_seat"])
    env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}
    res = claude_delivery.deliver_prompt(
        req["decision_request_id"], req["decision_request_id"], base, req["owner_session_id"],
        binding["stable_home"], message, state_store=state_store, cli=ClaudeCli(env=env))
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
        env = dict(os.environ, CODEX_THREAD_ID=req["origin_thread_id"])
        out = cd.dispatch(text, req["asker_session_id"], env=env, state_store=state_store,
                          detach=True)
    cur = state_store.read("decision_request", req["decision_request_id"])
    state_store.update("decision_request", cur["decision_request_id"], cur["revision"],
                       {"status": "answered", "continuation_dispatch_id": out.get("dispatch_id")})
    return out


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
