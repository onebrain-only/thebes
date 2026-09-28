"""The documented Claude CLI surface the delivery adapter relies on — and
nothing else.

Three commands, all evidenced on claude 2.1.283 (2026-09-28):

  claude agents --json [--all]          list sessions (durable sessionId, pid,
                                        short id, name, status)
  claude stop <short-id>                stop one background session; the FULL
                                        UUID is refused ("No job matching")
  claude --bg --resume <FULL_SID> "<prompt>"
                                        wake THAT durable session in the
                                        background with a new user turn; with no
                                        other flags the CLI re-applies the
                                        session's saved options. If the session
                                        is still running it "starts a copy and
                                        says so" — which is why stop comes first.

A session is addressed by its durable ``sessionId`` only. Display names, pids,
job labels and sockets are not identities and are never used to choose one.
The ``runner`` seam lets tests inject a fake; production uses subprocess.run.
"""
import json
import subprocess
import time

STOP_SETTLE_POLL_SECONDS = 1.0


class ClaudeCliError(Exception):
    pass


class ClaudeCli:
    def __init__(self, runner=None, binary="claude"):
        self._run = runner or subprocess.run
        self._binary = binary

    def _exec(self, args, cwd=None, timeout=120):
        try:
            completed = self._run([self._binary] + list(args), capture_output=True,
                                  text=True, timeout=timeout, check=False, cwd=cwd)
        except FileNotFoundError as exc:
            raise ClaudeCliError("claude CLI is unavailable: %s" % exc)
        except subprocess.TimeoutExpired as exc:
            raise ClaudeCliError("claude %s timed out: %s" % (args[0], exc))
        return completed

    # -- read-only ---------------------------------------------------------
    def agents(self, include_completed=False):
        args = ["agents", "--json"] + (["--all"] if include_completed else [])
        completed = self._exec(args)
        if completed.returncode:
            raise ClaudeCliError("claude agents --json exited %d: %s"
                                 % (completed.returncode, (completed.stderr or "").strip()))
        try:
            rows = json.loads(completed.stdout or "[]")
        except ValueError as exc:
            raise ClaudeCliError("claude agents --json is not JSON: %s" % exc)
        return rows if isinstance(rows, list) else []

    @staticmethod
    def find_by_sid(rows, session_id):
        """Exact durable-id match only. A row whose NAME matches is not a match."""
        for row in rows:
            if row.get("sessionId") == session_id:
                return row
        return None

    # -- mutations ---------------------------------------------------------
    def stop(self, short_id):
        completed = self._exec(["stop", short_id])
        if completed.returncode:
            raise ClaudeCliError("claude stop %s failed: %s"
                                 % (short_id, (completed.stderr or completed.stdout or "").strip()))
        return (completed.stdout or "").strip()

    def wait_stopped(self, session_id, timeout_seconds, sleep=time.sleep):
        """Bounded wait for the SID to leave the live list. Returns True when it
        has; False at the deadline. A handful of read-only listings, not a
        loop that lives on."""
        deadline = time.monotonic() + timeout_seconds
        while True:
            if self.find_by_sid(self.agents(), session_id) is None:
                return True
            if time.monotonic() >= deadline:
                return False
            sleep(STOP_SETTLE_POLL_SECONDS)

    def bg_resume(self, session_id, prompt, cwd):
        """Flagless same-SID resume. No model/name/permission/agent flags: the
        CLI restores the session's own, and extra flags create a copy."""
        completed = self._exec(["--bg", "--resume", session_id, prompt], cwd=cwd)
        text = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
        if completed.returncode:
            raise ClaudeCliError("claude --bg --resume exited %d: %s" % (completed.returncode, text))
        return text
