#!/usr/bin/env python3
"""Phase-3 proof that the Listener is a real, separate, restartable process.

This suite starts `python3 -m agent.listener serve` for real, talks to it over
loopback HTTP, kills it, and starts it again. Its inbox is a throwaway
directory; the Controller it reaches is the real one, which refuses at the real
authorization gate and changes nothing — no claim, no lease, no provider, no
Jira, no Product file.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.listener import contract, server                # noqa: E402


def free_port():
    with socket.socket() as sock:
        sock.bind((server.HOST, 0))
        return sock.getsockname()[1]


def request(port, path, body=None, timeout=20):
    url = "http://%s:%d%s" % (server.HOST, port, path)
    payload = None if body is None else json.dumps(body).encode("utf-8")
    call = urllib.request.Request(
        url, data=payload, method=("POST" if payload else "GET"),
        headers={"Content-Type": "application/json"} if payload else {})
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class Listener:
    """A real Listener process with its own durable inbox."""

    def __init__(self, runtime, port):
        self.runtime, self.port, self.process = runtime, port, None

    def start(self):
        environment = dict(os.environ, THEBES_LISTENER_RUNTIME=self.runtime)
        self.process = subprocess.Popen(
            [sys.executable, "-m", "agent.listener", "--port", str(self.port),
             "serve", "--idle-wait", "0.5"],
            cwd=ROOT, env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise AssertionError("listener exited: %s" % self.process.stdout.read())
            try:
                status, _ = request(self.port, "/health", timeout=2)
                if status == 200:
                    return self
            except OSError:
                time.sleep(0.1)
        raise AssertionError("listener did not become healthy")

    def kill(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=20)
        if self.process.stdout is not None:
            self.process.stdout.close()

    def wait_for(self, intent_id, states, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status, body = request(self.port, "/intents/%s" % intent_id)
            if status == 200 and body["intent"]["delivery_state"] in states:
                return body
            time.sleep(0.25)
        raise AssertionError("intent %s never reached %s" % (intent_id, states))


def submit(port, work_item_id, key):
    return request(port, "/intents", {
        "schema_version": contract.SCHEMA_VERSION,
        "intent_type": contract.EXECUTE_WORK_ITEM,
        "source": "listener-test", "actor": "ceo",
        "idempotency_key": key, "correlation_id": "corr-" + key,
        "payload": {"work_item_id": work_item_id}})


class SeparateProcess(unittest.TestCase):
    def setUp(self):
        self.runtime = tempfile.mkdtemp(prefix="thebes-listener-server-")
        self.port = free_port()
        self.listener = Listener(self.runtime, self.port).start()

    def tearDown(self):
        self.listener.kill()
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_listener_starts_independently_and_answers_a_local_probe(self):
        self.assertIsNone(self.listener.process.poll())
        status, body = request(self.port, "/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", body["status"])
        self.assertEqual("thebes-listener", body["listener"])
        self.assertEqual(sorted(contract.INTENT_TYPES), sorted(body["intent_types"]))

    def test_listener_binds_loopback_only(self):
        # A second bind on a routable address would be the regression that
        # turns a local boundary into a network service.
        connections = subprocess.run(
            ["lsof", "-nP", "-iTCP:%d" % self.port, "-sTCP:LISTEN"],
            capture_output=True, text=True)
        if connections.returncode == 0 and connections.stdout.strip():
            for line in connections.stdout.strip().splitlines()[1:]:
                self.assertIn("127.0.0.1:%d" % self.port, line)

    def test_submission_is_durable_before_the_caller_is_answered(self):
        status, body = submit(self.port, "KAN-999999", "durable-1")
        self.assertEqual(202, status)
        self.assertFalse(body["duplicate"])
        # The file is already on disk at the moment the caller heard "accepted".
        path = os.path.join(self.runtime, "intents", body["intent_id"] + ".json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as handle:
            self.assertEqual("KAN-999999", json.load(handle)["payload"]["work_item_id"])

    def test_duplicate_submission_is_harmless_and_collapses(self):
        first_status, first = submit(self.port, "KAN-999999", "dup-1")
        second_status, second = submit(self.port, "KAN-999999", "dup-1")
        self.assertEqual(202, first_status)
        self.assertEqual(200, second_status)
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["intent_id"], second["intent_id"])
        self.listener.wait_for(first["intent_id"], {"COMPLETED"})
        _, listing = request(self.port, "/intents")
        self.assertEqual(1, len([row for row in listing["intents"]
                                 if row["intent_id"] == first["intent_id"]]))

    def test_intent_reaches_the_real_controller_and_the_answer_is_durable(self):
        _, accepted = submit(self.port, "KAN-999999", "real-1")
        settled = self.listener.wait_for(accepted["intent_id"], {"COMPLETED", "FAILED"})
        self.assertEqual("COMPLETED", settled["intent"]["delivery_state"])
        controller = settled["result"]["controller_result"]
        self.assertEqual("returned", controller["transport"])
        self.assertEqual("product-execution-not-authorized",
                         controller["result"]["authorization_status"])
        self.assertEqual("corr-real-1", settled["result"]["correlation_id"])

    def test_the_answer_survives_killing_and_restarting_the_listener(self):
        _, accepted = submit(self.port, "KAN-999999", "restart-1")
        self.listener.wait_for(accepted["intent_id"], {"COMPLETED", "FAILED"})
        self.listener.kill()
        self.listener = Listener(self.runtime, self.port).start()
        status, body = request(self.port, "/intents/%s" % accepted["intent_id"])
        self.assertEqual(200, status)
        self.assertEqual("COMPLETED", body["intent"]["delivery_state"])
        self.assertIsNotNone(body["result"]["controller_result"])
        # Nothing is re-dispatched by the restart: the attempt count is the
        # single dispatch that already happened.
        self.assertEqual(1, body["intent"]["dispatch_attempts"])

    def test_malformed_and_unknown_intents_never_become_intents(self):
        for body, reason in (
                ({"intent_type": "RUN_SHELL", "source": "s", "actor": "ceo",
                  "idempotency_key": "x", "correlation_id": "x", "payload": {}},
                 "unknown-intent-type"),
                ({"intent_type": contract.EXECUTE_WORK_ITEM, "source": "s",
                  "actor": "ceo", "idempotency_key": "y", "correlation_id": "y",
                  "payload": {"work_item_id": "KAN-1", "command": "rm -rf /"}},
                 "unknown-field")):
            status, answer = request(self.port, "/intents", body)
            self.assertEqual(400, status)
            self.assertEqual(reason, answer["reason"])
        _, listing = request(self.port, "/intents")
        self.assertEqual([], listing["intents"])

    def test_unknown_paths_expose_nothing(self):
        for path in ("/", "/execute", "/intents/nope", "/../../etc/passwd"):
            status, _ = request(self.port, path)
            self.assertIn(status, (404, 400))


if __name__ == "__main__":
    unittest.main(verbosity=2)
