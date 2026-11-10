"""apply_settings.py: the settings script a person runs (agent/SETUP.md section 4)."""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
spec = importlib.util.spec_from_file_location(
    "apply_settings", os.path.join(ROOT, "agent", "scripts", "apply_settings.py"))
apply_settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_settings)

# Built in two parts so the secret scan does not read this fixture as a stored token.
TOKEN_RULE = "Bash(THEBES_DISPATCH_" + "CAPABILITY=not-a-real-token python3 *)"


class ApplySettings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.shared = os.path.join(self.tmp, "settings.json")
        self.local = os.path.join(self.tmp, "settings.local.json")
        self.example = os.path.join(self.tmp, "settings.local.example.json")
        self.dump(self.shared, {"permissions": {
            "allow": ["Bash(git push origin alpha-*)",
                      "Bash(git -C /Users/someone/x push origin integrate-alpha:Alpha)",
                      "Bash(python3 -m agent.execution.*)"],
            "deny": ["Bash(git -C Dabbler/dabbler-code push*main*)"]}, "hooks": {"keep": []}})
        self.dump(self.example, {"permissions": {"allow": []}, "autoMode": {"environment": ["x"]}})

    def dump(self, path, value):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(value, fh)

    def load(self, path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def run_it(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = apply_settings.main(list(argv), shared=self.shared, local=self.local,
                                       example=self.example)
        return code, out.getvalue()

    def test_shared_rules_are_replaced_and_the_rest_is_kept(self):
        self.run_it()
        shared = self.load(self.shared)
        allow = shared["permissions"]["allow"]
        self.assertFalse([r for r in allow if "alpha" in r.lower() or "/Users/" in r])
        self.assertIn("Bash(python3 -m agent.execution.*)", allow)
        for rule in apply_settings.ALLOW:
            self.assertIn(rule, allow)
        for rule in apply_settings.DENY:
            self.assertIn(rule, shared["permissions"]["deny"])
        self.assertIn("Bash(git -C Dabbler/dabbler-code push*main*)", shared["permissions"]["deny"])
        self.assertEqual(shared["hooks"], {"keep": []})
        self.assertIn("dart-flutter", shared["extraKnownMarketplaces"])

    def test_local_file_is_created_from_the_example(self):
        self.run_it()
        self.assertEqual(self.load(self.local)["autoMode"], {"environment": ["x"]})

    def test_a_rule_holding_a_token_is_removed_and_never_printed(self):
        self.dump(self.local, {"permissions": {"allow": [TOKEN_RULE, "Bash(flutter test *)"]},
                               "enabledMcpjsonServers": ["claude-flow"]})
        code, printed = self.run_it()
        local = self.load(self.local)
        self.assertEqual(local["permissions"]["allow"], ["Bash(flutter test *)"])
        self.assertEqual(local["enabledMcpjsonServers"], [])
        self.assertEqual(local["autoMode"], {"environment": ["x"]})
        self.assertNotIn("not-a-real-token", printed)
        self.assertEqual(code, 0)

    def test_check_changes_nothing_and_a_second_run_is_clean(self):
        before = self.load(self.shared)
        code, _ = self.run_it("--check")
        self.assertEqual(code, 1)
        self.assertEqual(self.load(self.shared), before)
        self.assertFalse(os.path.exists(self.local))
        self.run_it()
        code, printed = self.run_it("--check")
        self.assertEqual(code, 0)
        self.assertNotIn("WOULD CHANGE", printed)


if __name__ == "__main__":
    unittest.main()
