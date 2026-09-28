#!/usr/bin/env python3
"""Codex Primary wake adapter — characterization with a FAKE app-server.

No real codex runs. The fake records every JSON-RPC call so the tests can
assert exact call counts: never thread/start, never a retry, never a turn
after a busy resume or a failed preflight.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))

import store                                                     # noqa: E402
import validate                                                  # noqa: E402
from agent.execution import codex_primary as cp                  # noqa: E402
from agent.execution.codex_appserver import AppServerError       # noqa: E402

THREAD = "01a0e382-98e9-70b2-84df-c757e3c6c517"
TURN = "01a0e738-7d60-71e2-b052-a4bfa80000a0"
GOOD_URL = cp.CHATGPT_CODEX_BASE_URL


class FakeClient:
    """Scripted app-server. ``script`` maps method -> result or Exception."""
    instances = []

    def __init__(self, args, log_path, stderr_path, script=None, turn_messages=None):
        self.args = args
        self.calls = []
        self.closed = False
        self.script = script or {}
        self.turn_messages = turn_messages or []
        FakeClient.instances.append(self)

    def initialize(self):
        self.calls.append(("initialize", None))
        return {}

    def request(self, method, params, timeout=60):
        self.calls.append((method, params))
        r = self.script.get(method)
        if isinstance(r, Exception):
            raise r
        return r

    def await_turn(self, turn_id, timeout):
        self.calls.append(("await_turn", turn_id))
        return {"id": turn_id, "status": "completed", "error": None}, self.turn_messages

    def close(self):
        self.closed = True
        return 0


def good_script(catalog):
    return {
        "account/read": {"account": {"type": "chatgpt", "planType": "plus"}},
        "config/read": {"config": {"openai_base_url": GOOD_URL, "model_catalog_json": catalog}},
        "model/list": {"data": [{"id": "gpt-6-astra", "isDefault": True, "hidden": False},
                                {"id": "gpt-5.5", "isDefault": False, "hidden": False}]},
        "thread/resume": {"thread": {"id": THREAD}},
        "turn/start": {"turn": {"id": TURN, "status": "inProgress"}},
    }


class CodexPrimaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        self.catalog = cp.bundled_catalog_path(store, runner=self._fake_dump)
        self.binding = store.bind_primary("codex", THREAD, "STANDBY", "ceo", "ref:test",
                                          "/stable/home")
        FakeClient.instances = []

    def tearDown(self):
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _fake_dump(cmd, **kw):
        class R:
            returncode = 0
            stdout = json.dumps({"models": [{"slug": "gpt-6-astra"}]})
            stderr = ""
        return R()

    def launcher(self, script, messages=None):
        def make(args, log_path, stderr_path):
            return FakeClient(args, log_path, stderr_path, script=script, turn_messages=messages)
        return make

    def methods(self):
        return [m for m, _ in FakeClient.instances[0].calls]

    # -- launch shape -------------------------------------------------------
    def test_launch_carries_exactly_the_proof_04_override(self):
        args = cp.launch_args("/rt/codex/bundled_catalog.json")
        self.assertEqual(args, ["codex", "app-server",
                                "-c", 'openai_base_url="https://chatgpt.com/backend-api/codex"',
                                "-c", 'model_catalog_json="/rt/codex/bundled_catalog.json"'])
        self.assertTrue(self.catalog.startswith(store.RUNTIME))

    # -- success path -------------------------------------------------------
    def test_success_records_delivered_wake_with_turn_id_and_only_this_turns_messages(self):
        msgs = [{"type": "agentMessage", "text": "PRIMARY_STATUS: STANDBY"}]
        res = cp.wake_codex_primary("platform_test", "STANDBY CHECK", binding=self.binding,
                                    state_store=store, launcher=self.launcher(good_script(self.catalog), msgs))
        self.assertEqual(res.status, "delivered")
        self.assertEqual(res.turn_id, TURN)
        self.assertEqual(res.model, "gpt-6-astra")
        self.assertEqual(res.agent_messages, ["PRIMARY_STATUS: STANDBY"])
        self.assertEqual(self.methods(), ["initialize", "account/read", "config/read", "model/list",
                                          "thread/resume", "turn/start", "await_turn"])
        self.assertNotIn("thread/start", self.methods())
        fake = FakeClient.instances[0]
        self.assertTrue(fake.closed)
        self.assertEqual(fake.args, cp.launch_args(self.catalog))
        turn_params = dict(fake.calls)["turn/start"]
        self.assertEqual(turn_params["threadId"], THREAD)
        self.assertEqual(turn_params["input"][0]["text"], "THEBES_EVENT platform_test gen=0\nSTANDBY CHECK")
        self.assertEqual(turn_params["sandboxPolicy"], {"type": "readOnly", "networkAccess": False})
        self.assertEqual(turn_params["approvalPolicy"], "untrusted")
        rec = store.read("primary_wake", res.wake_record_id)
        self.assertEqual((rec["status"], rec["turn_ref"], rec["session_ref"]),
                         ("delivered", TURN, THREAD))
        self.assertEqual(store.read("primary_binding", "codex")["status"], "STANDBY",
                         "a wake is not a cutover")

    # -- busy path ----------------------------------------------------------
    def test_busy_thread_returns_busy_code_and_never_starts_a_turn_or_retries(self):
        script = good_script(self.catalog)
        script["thread/resume"] = AppServerError("thread/resume", {
            "code": -32600, "message": "thread %s already has an active writer" % THREAD})
        res = cp.wake_codex_primary("platform_test", "x", binding=self.binding,
                                    state_store=store, launcher=self.launcher(script))
        self.assertEqual((res.status, res.code), ("busy", cp.CODE_BUSY))
        self.assertEqual(self.methods().count("thread/resume"), 1)
        self.assertNotIn("turn/start", self.methods())
        self.assertNotIn("thread/start", self.methods())
        self.assertEqual(len(FakeClient.instances), 1, "no second launch")
        self.assertTrue(FakeClient.instances[0].closed)
        rec = store.read("primary_wake", res.wake_record_id)
        self.assertEqual((rec["status"], rec["error"]["code"]), ("busy", cp.CODE_BUSY))

    # -- preflight ----------------------------------------------------------
    def test_non_chatgpt_route_refuses_before_resume(self):
        for bad in ({"openai_base_url": "http://127.0.0.1:11434/api/codex/v1",
                     "model_catalog_json": self.catalog},
                    {"openai_base_url": GOOD_URL, "model_catalog_json": "/Users/x/.codex/ollama.json"}):
            FakeClient.instances = []
            script = good_script(self.catalog)
            script["config/read"] = {"config": bad}
            res = cp.wake_codex_primary("platform_test", "x", binding=self.binding,
                                        state_store=store, launcher=self.launcher(script))
            self.assertEqual((res.status, res.code), ("failed", cp.CODE_NOT_CHATGPT))
            self.assertNotIn("thread/resume", self.methods())
            self.assertNotIn("turn/start", self.methods())

    def test_api_key_account_refuses_before_resume(self):
        script = good_script(self.catalog)
        script["account/read"] = {"account": {"type": "apiKey"}}
        res = cp.wake_codex_primary("platform_test", "x", binding=self.binding,
                                    state_store=store, launcher=self.launcher(script))
        self.assertEqual((res.status, res.code), ("failed", cp.CODE_NOT_CHATGPT))
        self.assertEqual(self.methods(), ["initialize", "account/read"])

    # -- binding guards -----------------------------------------------------
    def test_retired_or_non_codex_binding_never_launches(self):
        retired = dict(self.binding, status="RETIRED")
        res = cp.wake_codex_primary("platform_test", "x", binding=retired, state_store=store,
                                    launcher=self.launcher(good_script(self.catalog)))
        self.assertEqual((res.status, res.code), ("failed", cp.CODE_NOT_STANDBY))
        res = cp.wake_codex_primary("platform_test", "x", binding=dict(self.binding, provider="claude"),
                                    state_store=store, launcher=self.launcher(good_script(self.catalog)))
        self.assertEqual(res.code, cp.CODE_WRONG_PROVIDER)
        self.assertEqual(FakeClient.instances, [])

    def test_cli_dry_run_reads_binding_and_writes_nothing(self):
        payload = os.path.join(self.tmp, "p.txt")
        with open(payload, "w") as fh:
            fh.write("hello")
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cp.main(["wake", "--event", "platform_test", "--payload-file", payload, "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("THEBES_EVENT platform_test gen=0\\nhello", out.getvalue())
        self.assertEqual(store.read_all("primary_wake"), [])


if __name__ == "__main__":
    unittest.main()
