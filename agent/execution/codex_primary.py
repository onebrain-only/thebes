"""Minimum Codex Primary wake adapter — control-plane, not Product execution.

Delivers ONE external event as ONE new turn on the SAME durable Codex thread
that a ``primary_binding`` names, over the officially supported app-server
JSON-RPC interface (``initialize -> thread/resume -> turn/start``, proven
2026-09-28 as CODEX_EXTERNAL_INFERENCE_PROOF_04). It records a
``primary_wake`` either way, so the wake is durable evidence and not a claim.

What it deliberately is NOT:
  * not a cutover — a wake to a STANDBY Primary leaves it STANDBY, and only
    ``store.set_primary_active`` changes who is ACTIVE;
  * not a Product executor — provider selection, leases and receipts are
    untouched, and no Product work item is ever named here;
  * not a poll — the process blocks on the JSON-RPC stream until the one turn
    it started completes;
  * not a retry — a busy thread (the Desktop holds the single writer) is
    reported as ``busy`` once, and no replacement thread is ever created.

Runtime routing: the launch carries EXACTLY the PROOF_04 process-local
override, so the child uses the ChatGPT-account route and the runtime's own
bundled model catalog instead of whatever ``~/.codex/config.toml`` routes to.
Nothing is written under ``~/.codex``; the override lives in this process's
argv and dies with it.

    python3 -m agent.execution.codex_primary status
    python3 -m agent.execution.codex_primary bind --provider codex --session-ref <thread>
        --status STANDBY --stable-home <home> --changed-by ceo --reason-ref <ref>
    python3 -m agent.execution.codex_primary wake --event <kind> --payload-file <path> [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

from agent.execution.codex_appserver import (  # noqa: E402
    AppServerError, AppServerTimeout, CodexAppServerClient)

CHATGPT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
OLLAMA_MARKER = "127.0.0.1:11434"
BUSY_MARKER = "already has an active writer"
CODE_BUSY = "CODEX_PRIMARY_THREAD_BUSY"
CODE_NOT_CHATGPT = "codex-runtime-not-chatgpt-route"
CODE_NOT_STANDBY = "primary-not-standby-or-active"
CODE_WRONG_PROVIDER = "primary-binding-not-codex"


@dataclass
class WakeResult:
    status: str                       # delivered | busy | failed
    code: Optional[str] = None        # structured error code when not delivered
    error: Optional[str] = None
    thread_id: Optional[str] = None
    turn_id: Optional[str] = None
    model: Optional[str] = None
    agent_messages: list = field(default_factory=list)
    response_summary: Optional[str] = None
    wake_record_id: Optional[str] = None
    log_path: Optional[str] = None

    def as_dict(self):
        return asdict(self)


# ---------------------------------------------------------------- runtime dir
def runtime_dir(state_store):
    d = os.path.join(state_store.RUNTIME, "codex")
    os.makedirs(d, exist_ok=True)
    return d


def bundled_catalog_path(state_store, runner=subprocess.run):
    """The runtime's own bundled catalog, dumped once on first use with
    ``codex debug models --bundled`` into the gitignored runtime dir."""
    path = os.path.join(runtime_dir(state_store), "bundled_catalog.json")
    if not os.path.exists(path):
        completed = runner(["codex", "debug", "models", "--bundled"],
                           capture_output=True, text=True, check=False)
        if completed.returncode or not completed.stdout.strip():
            raise RuntimeError("codex debug models --bundled failed: %s"
                               % (completed.stderr or completed.returncode))
        json.loads(completed.stdout)                # must be a catalog, not a banner
        tmp = path + ".tmp.%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(completed.stdout)
        os.replace(tmp, path)
    return path


def launch_args(catalog_path):
    """EXACTLY the PROOF_04 process-local override; nothing else."""
    return ["codex", "app-server",
            "-c", 'openai_base_url="%s"' % CHATGPT_CODEX_BASE_URL,
            "-c", 'model_catalog_json="%s"' % catalog_path]


def envelope(event_kind, generation, payload_text):
    return "THEBES_EVENT %s gen=%d\n%s" % (event_kind, generation, payload_text)


# ---------------------------------------------------------------- preflight
def preflight(client, catalog_path):
    """Refuse before any thread call unless the runtime reports the ChatGPT
    route, ChatGPT-account auth and OUR catalog. Returns the default model."""
    account = (client.request("account/read", {"refreshToken": False}) or {}).get("account") or {}
    if account.get("type") != "chatgpt":
        raise PreflightError(CODE_NOT_CHATGPT, "account type is %r, not chatgpt" % account.get("type"))
    cfg = (client.request("config/read", {"includeLayers": False}) or {}).get("config") or {}
    base_url = str(cfg.get("openai_base_url") or "")
    if OLLAMA_MARKER in base_url or base_url != CHATGPT_CODEX_BASE_URL:
        raise PreflightError(CODE_NOT_CHATGPT, "effective openai_base_url is %r" % base_url)
    if cfg.get("model_catalog_json") != catalog_path:
        raise PreflightError(CODE_NOT_CHATGPT, "model_catalog_json is %r, not ours"
                             % cfg.get("model_catalog_json"))
    models = (client.request("model/list", {"includeHidden": False}) or {}).get("data") or []
    default = [m.get("id") for m in models if m.get("isDefault") and not m.get("hidden")]
    if not default:
        raise PreflightError(CODE_NOT_CHATGPT, "model/list reports no default model")
    return default[0]


class PreflightError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------- the wake
def wake_codex_primary(event_kind, payload_text, *, binding, state_store=None,
                       launcher=None, timeout_seconds=300, log_dir=None):
    """Deliver one event to the bound Codex Primary thread as one new turn.

    ``launcher(args, log_path, stderr_path)`` returns a client with the
    CodexAppServerClient surface; tests pass a fake, production passes None.
    """
    if state_store is None:
        import store as state_store                              # noqa: E402
    started_at = state_store.now()
    provider = binding.get("provider")
    if provider != "codex":
        return WakeResult("failed", CODE_WRONG_PROVIDER,
                          "binding provider is %r" % provider)
    if binding.get("status") == "RETIRED":
        return WakeResult("failed", CODE_NOT_STANDBY, "codex primary is RETIRED")
    thread_id = binding["session_ref"]
    generation = int(binding.get("generation") or 0)
    log_dir = log_dir or os.path.join(runtime_dir(state_store), "wake-logs")
    os.makedirs(log_dir, exist_ok=True)
    stamp = started_at.replace(":", "").replace("-", "")
    log_path = os.path.join(log_dir, "wake-%s-%s.jsonl" % (stamp, event_kind))
    stderr_path = log_path + ".stderr"

    def finish(result):
        result.thread_id = thread_id
        result.log_path = log_path
        rec = state_store.record_primary_wake({
            "provider": "codex", "session_ref": thread_id, "generation": generation,
            "event_kind": event_kind, "payload_ref": log_path, "status": result.status,
            "turn_ref": result.turn_id, "response_summary": result.response_summary,
            "error": ({"code": result.code, "message": result.error}
                      if result.status != "delivered" else None),
            "started_at": started_at, "completed_at": state_store.now()})
        result.wake_record_id = rec["primary_wake_id"]
        return result

    try:
        catalog = bundled_catalog_path(state_store)
    except (RuntimeError, ValueError, OSError) as exc:
        return finish(WakeResult("failed", CODE_NOT_CHATGPT, "no bundled catalog: %s" % exc))
    launcher = launcher or CodexAppServerClient
    try:
        client = launcher(launch_args(catalog), log_path, stderr_path)
    except OSError as exc:
        return finish(WakeResult("failed", "codex-app-server-unavailable", str(exc)))
    try:
        client.initialize()
        try:
            model = preflight(client, catalog)
        except PreflightError as exc:
            return finish(WakeResult("failed", exc.code, str(exc)))
        try:
            client.request("thread/resume", {"threadId": thread_id, "sandbox": "read-only",
                                             "approvalPolicy": "untrusted",
                                             "excludeTurns": True}, timeout=120)
        except AppServerError as exc:
            if BUSY_MARKER in str(exc.error.get("message") or ""):
                return finish(WakeResult("busy", CODE_BUSY, str(exc)))
            return finish(WakeResult("failed", "codex-thread-resume-failed", str(exc)))
        turn = client.request("turn/start", {
            "threadId": thread_id,
            "input": [{"type": "text", "text": envelope(event_kind, generation, payload_text)}],
            "model": model,
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            "approvalPolicy": "untrusted"}, timeout=120)
        turn_id = (turn.get("turn") or {}).get("id")
        completed, messages = client.await_turn(turn_id, timeout_seconds)
        texts = [m.get("text") or "" for m in messages]
        result = WakeResult("delivered" if completed.get("status") == "completed" else "failed",
                            None if completed.get("status") == "completed" else "codex-turn-%s"
                            % completed.get("status"),
                            json.dumps(completed.get("error")) if completed.get("error") else None,
                            turn_id=turn_id, model=model, agent_messages=texts,
                            response_summary=(texts[-1][:500] if texts else None))
        return finish(result)
    except AppServerTimeout as exc:
        return finish(WakeResult("failed", "codex-app-server-timeout", str(exc)))
    except AppServerError as exc:
        return finish(WakeResult("failed", "codex-app-server-error", str(exc)))
    finally:
        client.close()


# ---------------------------------------------------------------- CLI
def _cmd_status(store):
    bindings = store.read_all("primary_binding")
    wakes = sorted(store.read_all("primary_wake"), key=lambda r: r.get("completed_at") or "")
    print(json.dumps({"bindings": bindings, "last_wake": wakes[-1] if wakes else None},
                     indent=2, sort_keys=True))
    return 0


def _cmd_bind(store, ns):
    rec = store.bind_primary(ns.provider, ns.session_ref, ns.status, ns.changed_by,
                             ns.reason_ref, ns.stable_home,
                             expected_revision=ns.expected_revision)
    print(json.dumps(rec, indent=2, sort_keys=True))
    return 0


def _cmd_wake(store, ns):
    binding = store.read("primary_binding", "codex")
    if binding is None:
        print(json.dumps({"status": "failed", "code": "primary-binding-missing"}))
        return 2
    with open(ns.payload_file, encoding="utf-8") as fh:
        payload = fh.read()
    if ns.dry_run:
        print(json.dumps({"dry_run": True, "thread_id": binding["session_ref"],
                          "status": binding["status"], "args": launch_args("<catalog>"),
                          "input": envelope(ns.event, binding.get("generation") or 0, payload)},
                         indent=2))
        return 0
    result = wake_codex_primary(ns.event, payload, binding=binding, state_store=store,
                                timeout_seconds=ns.timeout)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.status == "delivered" else 1


def main(argv=None):
    import store                                                 # noqa: E402
    ap = argparse.ArgumentParser(prog="agent.execution.codex_primary", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    b = sub.add_parser("bind")
    b.add_argument("--provider", required=True, choices=sorted(store.ROLE_SESSION_PROVIDERS))
    b.add_argument("--session-ref", required=True)
    b.add_argument("--status", required=True, choices=["STANDBY", "RETIRED"],
                   help="ACTIVE is a transition (set_primary_active), never a bind")
    b.add_argument("--stable-home", required=True)
    b.add_argument("--changed-by", required=True)
    b.add_argument("--reason-ref", required=True)
    b.add_argument("--expected-revision", type=int, default=None)
    w = sub.add_parser("wake")
    w.add_argument("--event", required=True)
    w.add_argument("--payload-file", required=True)
    w.add_argument("--timeout", type=int, default=300)
    w.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    return {"status": lambda: _cmd_status(store),
            "bind": lambda: _cmd_bind(store, ns),
            "wake": lambda: _cmd_wake(store, ns)}[ns.cmd]()


if __name__ == "__main__":
    sys.exit(main())
