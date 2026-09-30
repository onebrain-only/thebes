"""The Listener's bounded, exact-origin conversation dispatch boundary."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import IsolatedRuntime  # noqa: E402
from agent.listener import contract, dispatch, store  # noqa: E402
from agent.listener import __main__ as cli  # noqa: E402

A = "0aaaaaaa-0000-7000-8000-00000000000a"
SID = "55555555-5555-4555-8555-555555555555"


def envelope(prompt="Return an explicit result."):
    return contract.normalize({
        "schema_version": 1, "intent_type": contract.CONVERSATION_DISPATCH,
        "source": "codex-conversation", "actor": "codex",
        "idempotency_key": "conversation-one", "correlation_id": "conversation-one",
        "payload": {"origin_thread_id": A, "target_session_id": SID, "prompt": prompt}})


class ConversationIntentTests(unittest.TestCase):
    def test_prompt_is_one_argument_and_origin_is_pinned_in_child_environment(self):
        intent = envelope("Explain A; $(touch /tmp/never) is literal text.")
        argv = dispatch.argv_for(intent)
        self.assertEqual([sys.executable, "-m", "agent.execution.conversation_dispatch",
                          "dispatch", "--to", SID, "--prompt", intent["payload"]["prompt"]],
                         argv)
        env = dispatch.controller_environment(intent, {"CODEX_THREAD_ID": "wrong"})
        self.assertEqual(A, env["CODEX_THREAD_ID"])

    def test_intake_is_durable_and_duplicate_cannot_change_destination(self):
        with IsolatedRuntime():
            first, created = store.accept(envelope())
            self.assertTrue(created)
            again, created = store.accept(envelope())
            self.assertFalse(created)
            self.assertEqual(first["intent_id"], again["intent_id"])
            changed = dict(envelope())
            changed["payload"] = dict(changed["payload"], target_session_id=A)
            with self.assertRaises(store.ListenerStoreError):
                store.accept(changed)

    def test_worker_actor_and_invalid_prompt_are_refused(self):
        bad = {k: v for k, v in envelope().items() if k != "intent_id"}
        bad["actor"] = "worker:frontend-1"
        with self.assertRaises(contract.IntentRejected) as error:
            contract.normalize(bad)
        self.assertEqual("actor-not-permitted", error.exception.reason)
        bad["actor"] = "codex"
        bad["payload"] = dict(bad["payload"], prompt="bad\x1b[2J")
        with self.assertRaises(contract.IntentRejected):
            contract.normalize(bad)

    def test_cli_captures_origin_from_environment(self):
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": A}), mock.patch.object(
                cli, "_post", return_value=(202, {"intent_id": "intent-one"})) as post:
            self.assertEqual(0, cli.main(["conversation-dispatch", "--to", SID,
                                           "--prompt", "Do work and report."]))
        body = post.call_args.args[2]
        self.assertEqual(A, body["payload"]["origin_thread_id"])
        self.assertEqual(SID, body["payload"]["target_session_id"])


if __name__ == "__main__":
    unittest.main()
