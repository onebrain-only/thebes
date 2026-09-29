#!/usr/bin/env python3
"""The remote Primary gateway: one authenticated POST, nothing else. A real
loopback HTTP server on an ephemeral port with a FAKE submitter — no Listener,
no Codex, no tunnel is touched.
"""
import http.client
import json
import os
import stat
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.listener import gateway as gw                              # noqa: E402

TOKEN = "t-" + "x" * 40


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.submitted = []

        def submit(message):
            self.submitted.append(message)
            return 202, {"intent_id": "intent-fake", "status": "queued"}

        self.limiter = gw.RateLimit(limit=3, window=60)
        self.httpd = gw.build(port=0, token=TOKEN, submit=submit, limiter=self.limiter)
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close()

    def call(self, method="POST", path="/primary-command", body=None, auth="Bearer " + TOKEN,
             raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if auth is not None:
            headers["Authorization"] = auth
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read() or b"{}")

    def test_binds_loopback_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_valid_request_submits_exactly_one_primary_command(self):
        status, body = self.call(body={"message": "Status check, please."})
        self.assertEqual((status, body["status"]), (202, "queued"))
        self.assertEqual(self.submitted, ["Status check, please."])

    def test_missing_token_is_401_and_wrong_token_is_403_with_nothing_submitted(self):
        self.assertEqual(self.call(body={"message": "x"}, auth=None)[0], 401)
        self.assertEqual(self.call(body={"message": "x"}, auth="Bearer wrong")[0], 403)
        self.assertEqual(self.call(body={"message": "x"}, auth=TOKEN)[0], 403, "scheme is required")
        status, body = self.call(body={"message": "x"}, auth="Bearer wrong")
        self.assertNotIn(TOKEN, json.dumps(body))
        self.assertEqual(self.submitted, [])

    def test_only_post_primary_command_exists(self):
        self.assertEqual(self.call(path="/intents", body={"message": "x"})[0], 404)
        self.assertEqual(self.call(method="GET", path="/primary-command")[0], 405)
        self.assertEqual(self.call(method="GET", path="/health")[0], 404)
        self.assertEqual(self.submitted, [])

    def test_body_and_message_validation(self):
        cases = [
            (None, b"not json", 400),
            (None, json.dumps({"message": "x", "intent_type": "EXECUTE_WORK_ITEM"}).encode(), 400),
            (None, json.dumps({"text": "x"}).encode(), 400),
            (None, json.dumps({"message": ""}).encode(), 400),
            (None, json.dumps({"message": "a\x1bb"}).encode(), 400),
            (None, json.dumps({"message": "x" * (gw.MAX_MESSAGE + 1)}).encode(), 400),
            (None, b"x" * (gw.MAX_BODY + 1), 413),
        ]
        self.limiter.limit = 100                     # validation, not rate limiting, is under test
        for _, raw, code in cases:
            self.assertEqual(self.call(raw=raw)[0], code, raw[:40])
        self.assertEqual(self.submitted, [])

    def test_rate_limit(self):
        codes = [self.call(body={"message": "m%d" % i})[0] for i in range(4)]
        self.assertEqual(codes, [202, 202, 202, 429])
        self.assertEqual(len(self.submitted), 3)

    def test_token_file_is_created_0600_and_reused(self):
        path = os.path.join(tempfile.mkdtemp(), "sub", "gateway.token")
        first = gw.load_or_create_token(path)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertGreaterEqual(len(first), 40)
        self.assertEqual(gw.load_or_create_token(path), first)

    def test_submitter_posts_only_a_primary_command_intent(self):
        seen = {}

        class Resp:
            def __init__(self, data): self.data = data
            def read(self): return self.data
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=None):
            if getattr(req, "data", None):
                seen["body"] = json.loads(req.data.decode()); seen["url"] = req.full_url
                return Resp(json.dumps({"intent_id": "intent-1"}).encode())
            return Resp(json.dumps({"intent": {"lifecycle_state": "COMPLETED"},
                                    "result": {"controller_result": {"result": {
                                        "primary_command_id": "pcmd-1", "status": "busy"}}}}).encode())

        from unittest import mock
        with mock.patch.object(gw.urllib.request, "urlopen", fake_urlopen):
            code, body = gw.listener_submit("hello", wait=2)
        self.assertEqual(seen["url"], "http://127.0.0.1:8787/intents")
        self.assertEqual((seen["body"]["intent_type"], seen["body"]["payload"], seen["body"]["actor"]),
                         ("PRIMARY_COMMAND", {"text": "hello"}, "ceo-remote"))
        self.assertEqual((code, body["primary_command_id"], body["status"]), (202, "pcmd-1", "busy"))


if __name__ == "__main__":
    unittest.main()
