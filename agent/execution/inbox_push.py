"""Push the orchestrator's inbox into its conversation (CEO 2026-11-11, "no wake-ups at all").

The orchestrator used to keep `inbox wait` running in the background. Every return of it was a
wake: idle every two hours, a restart on every Thebes commit, and each batch cost a read of the
output file and a restart call on top of the work. The CEO asked for items to arrive the way his
own messages do, answered with nothing sent to him.

This zero-token loop watches the inbox (it never takes an item) and, when work waits, has a
one-shot courier (`claude -p` on Haiku, no MCP, no saved session) SendMessage one short fixed
line into the orchestrator's live session. Nothing is stopped or resumed. The line carries no
item and no capability: the orchestrator runs `python3 -m agent.execution.inbox take`.

    python3 -m agent.execution.inbox_push serve    # started by agent/scripts/thebes-up.sh
    python3 -m agent.execution.inbox_push dry      # the line it would send now, sends nothing

Batching is the waiter's: after the first item, wait until nothing new came for
inbox.BATCH_QUIET_POLLS polls, at most inbox.BATCH_MAX_POLLS. A set already announced is not
announced again unless it is still untaken after RESEND_SECONDS (the message was lost or held).
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent.execution import inbox                                      # noqa: E402
from agent.state import store                                          # noqa: E402

COURIER_MODEL = "claude-haiku-5-5"
COURIER_TIMEOUT = 180
RESEND_SECONDS = 3600
RETRY_SECONDS = 60
ORCHESTRATOR_NAME = "thebes-orchestrator"      # watchdog.ORCHESTRATOR_NAME; its home
_KEYS = ("kind", "_key", "dispatch_id", "decision_request_id", "priority_request_id",
         "question_id", "key", "ticket", "items")
CODE_FILES = inbox.CODE_FILES + ("agent/execution/inbox_push.py",)


def message(items):
    kinds = {}
    for i in items:
        kinds[i.get("kind", "result")] = kinds.get(i.get("kind", "result"), 0) + 1
    what = ", ".join("%d %s" % (n, k) for k, n in sorted(kinds.items()))
    return ("Thebes inbox: %d item%s waiting (%s). Run `python3 -m agent.execution.inbox take` "
            "and handle every item as agent/ORCHESTRATOR.md section 1 says. Finish with `python3 -m "
            "agent.execution.inbox done` and reply with exactly what it prints. Start no inbox waiter."
            % (len(items), "" if len(items) == 1 else "s", what))


def item_key(item):
    return json.dumps({k: item.get(k) for k in _KEYS if item.get(k) is not None},
                      sort_keys=True, default=str)


def session_name(session_id, sessions_dir=None):
    """The live name other sessions address it by (~/.claude/sessions/<pid>.json)."""
    root = sessions_dir or os.path.expanduser("~/.claude/sessions")
    for path in glob.glob(os.path.join(root, "*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        if rec.get("sessionId") == session_id and rec.get("name"):
            return rec["name"]
    return ORCHESTRATOR_NAME


def courier(session_id, text):
    """Deliver `text` into the live session with a one-shot Haiku SendMessage. True on DONE.

    The courier runs in the target's permission mode: a session holds a message from a session
    in another mode for its user's approval, and that would put the CEO in the loop."""
    from agent.execution import liveness
    mode = liveness.permission_mode(session_id)
    prompt = ("You are a courier and nothing else. Call the SendMessage tool exactly once, with "
              "to=%s and message set to the text between <<< and >>>, unchanged. Load SendMessage "
              "with ToolSearch first if it is not loaded. Then reply with only DONE, or with the "
              "exact error.\n<<<\n%s\n>>>" % (json.dumps(session_name(session_id)), text))
    cmd = ["claude", "-p", "--model", COURIER_MODEL, "--no-session-persistence",
           "--strict-mcp-config", "--allowedTools=SendMessage,ToolSearch"]
    if mode:
        cmd += ["--permission-mode", mode]
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "CLAUDECODE")}
    try:
        done = subprocess.run(cmd + [prompt], cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=COURIER_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return False
    lines = [l.strip() for l in (done.stdout or "").splitlines() if l.strip()]
    return done.returncode == 0 and bool(lines) and lines[-1] == "DONE"


class Pusher:
    """One instance per process. step() is one poll; serve() loops it."""

    def __init__(self, *, state_store=store, deliver=None, clock=None):
        self.store = state_store
        self.deliver = deliver or courier
        self.clock = clock or time.time
        self.sent_keys, self.sent_at, self.failed_at = set(), 0.0, 0.0
        self.prev_keys, self.first_at, self.changed_at = set(), None, None

    def step(self):
        sid = inbox.orchestrator_session(self.store)
        if not sid:
            return None
        items = inbox.pending(sid, state_store=self.store)
        if any(i.get("_quiet") for i in items):
            inbox.collect(sid, state_store=self.store, quiet_only=True)
        loud = [i for i in items if not i.get("_quiet")]
        keys = {item_key(i) for i in loud}
        now = self.clock()
        if not keys:
            self.prev_keys, self.first_at, self.changed_at = set(), None, None
            return None
        if keys != self.prev_keys:
            self.prev_keys, self.changed_at = keys, now
            self.first_at = self.first_at or now
        quiet_for = inbox.BATCH_QUIET_POLLS * inbox.POLL_SECONDS
        max_wait = inbox.BATCH_MAX_POLLS * inbox.POLL_SECONDS
        if now - self.changed_at < quiet_for and now - self.first_at < max_wait:
            return None                                    # still batching
        news = keys - self.sent_keys
        if not news and now - self.sent_at < RESEND_SECONDS:
            return None                                    # announced; the orchestrator has it
        if now - self.failed_at < RETRY_SECONDS:
            return None
        if not self.deliver(sid, message(loud)):
            self.failed_at = now
            return {"action": "push-failed", "count": len(loud)}
        self.sent_keys, self.sent_at, self.first_at = keys, now, None
        return {"action": "pushed", "count": len(loud), "resend": not news}

    def serve(self, sleep=time.sleep, reexec=None):
        stamp = _code_stamp()
        while True:
            if _code_stamp() != stamp and reexec:
                reexec()                                   # new code, same lock, same PID
            try:
                done = self.step()
            except Exception as exc:                       # noqa: BLE001  the loop never dies
                done = {"action": "error", "error": str(exc)[:200]}
            if done:
                print(json.dumps(dict(done, at=store.now())), flush=True)
            sleep(inbox.POLL_SECONDS)


def _code_stamp():
    out = []
    for rel in CODE_FILES:
        try:
            out.append(os.path.getmtime(os.path.join(ROOT, rel)))
        except OSError:
            out.append(None)
    return tuple(out)


def _reexec():
    sys.stdout.flush()
    os.chdir(ROOT)
    os.execv(sys.executable, [sys.executable, "-m", "agent.execution.inbox_push", "serve"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent.execution.inbox_push", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("serve", "dry"))
    ns = ap.parse_args(argv)
    if ns.cmd == "dry":
        sid = inbox.orchestrator_session()
        loud = [i for i in inbox.pending(sid) if not i.get("_quiet")] if sid else []
        print(message(loud) if loud else "nothing waiting")
        return 0
    import fcntl
    os.makedirs(store.RUNTIME, exist_ok=True)
    lock = open(os.path.join(store.RUNTIME, inbox.PUSH_LOCK), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"action": "already-running"}))
        return 1
    Pusher().serve(reexec=_reexec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
