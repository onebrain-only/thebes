"""knowledge_lint.py and secret_scan.py: the two checks the pre-commit hook runs."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, "agent", "scripts", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lint = load("knowledge_lint")
secret_scan = load("secret_scan")

NAMING_HEAD = "Seat,Code Name,Given Name (Arabic),Hieroglyphs,Ancient Pharaonic Lore\n"


class Workspace(unittest.TestCase):
    """A small workspace that passes; each test breaks one thing."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.write("agent/state/registry/seats.json",
                   json.dumps({"seats": {"pm": {"role": "pm"}, "qa": {"role": "qa"}}}))
        self.write("agent/state/registry/topology.json", json.dumps({"capabilities": {
            "pm": {"defined_seats": 1, "ceiling": 1}, "qa": {"defined_seats": 1, "ceiling": 3}}}))
        self.write("agent/NAMING.csv", NAMING_HEAD
                   + "pm,PM,أنوبيس (Anubis),x,lore\n"
                   + "qa,QA,عمعموت (Ammut),x,lore\n"
                   + "team:memphis,Memphis,منف (Memphis),x,lore\n")
        for seat, name in (("pm", "Anubis"), ("qa", "Ammut")):
            self.write(".claude/bindings/%s.yml" % seat, 'name: "%s"\nrole: %s\n' % (seat, seat))
            self.write("agent/roles/%s.md" % seat, "A role.\n")
            self.write(".claude/agents/%s.md" % seat,
                       '---\ndescription: "**%s.** A seat."\n---\n- **Name:** You are **%s**.\n'
                       % (name, name))
        self.write("CLAUDE.md", "Read [the roles](agent/roles/pm.md) and `agent/NAMING.csv`.\n")
        self.write("agent/DECISIONS.md", "## TH-001 — One\n\n## TH-002 — Two\n")

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def found(self, check):
        return [what for kind, _, what in lint.run(self.root) if kind == check]

    def test_a_consistent_workspace_has_no_findings(self):
        self.assertEqual(lint.run(self.root), [])

    def test_a_seat_without_a_naming_row_is_found(self):
        self.write("agent/NAMING.csv", NAMING_HEAD + "pm,PM,أنوبيس (Anubis),x,lore\n")
        self.assertIn("seat qa has 0 naming rows, expected 1", self.found("seats"))

    def test_a_seat_without_a_binding_or_role_is_found(self):
        os.remove(os.path.join(self.root, ".claude/bindings/qa.yml"))
        os.remove(os.path.join(self.root, "agent/roles/qa.md"))
        self.assertEqual(self.found("seats"), ["binding missing for seat qa",
                                               "role file missing for seat qa"])

    def test_an_agent_that_carries_another_name_is_found(self):
        self.write(".claude/agents/qa.md",
                   '---\ndescription: "**Scribe.** A seat."\n---\nYou are **Scribe**.\n')
        self.assertEqual(len(self.found("seats")), 2)

    def test_two_seats_with_one_name_are_found(self):
        self.write("agent/NAMING.csv", NAMING_HEAD
                   + "pm,PM,أنوبيس (Anubis),x,lore\nqa,QA,أنوبيس (Anubis),x,lore\n")
        self.assertIn("name Anubis is used by pm, qa", self.found("seats"))

    def test_a_binding_or_naming_row_without_a_seat_is_found(self):
        self.write(".claude/bindings/ghost.yml", "role: pm\n")
        self.write("agent/NAMING.csv", NAMING_HEAD
                   + "pm,PM,أنوبيس (Anubis),x,lore\nqa,QA,عمعموت (Ammut),x,lore\n"
                   + "team-lead-1,Lead,قديم (Old),x,lore\n")
        self.assertEqual(sorted(self.found("seats")),
                         ["binding has no seat in seats.json",
                          "naming row team-lead-1 is not a seat in seats.json"])

    def test_a_wrong_count_is_found(self):
        self.write("agent/state/registry/topology.json", json.dumps({"capabilities": {
            "pm": {"defined_seats": 4, "ceiling": 5}}}))
        self.write("agent/ORCHESTRATOR.md", "Thebes has 26 seats.\nThebes has 2 seats.\n")
        self.assertEqual(self.found("counts"), ["pm: defined_seats 4, seats.json has 1",
                                                "says 26 seats; seats.json has 2 seats"])

    def test_a_retired_term_is_found_unless_the_line_says_it_is_gone(self):
        self.write("agent/WORKFLOWS.md", "Push to alpha-karnak.\nAsk your team lead.\n"
                   "There are no team leads.\nThe merge-alpha lane was removed.\n")
        self.assertEqual(len(self.found("stale")), 2)

    def test_history_may_name_retired_things(self):
        self.write("agent/archive/2026-11-10/old.md", "Push to alpha-karnak from /Users/someone/x.\n")
        self.assertEqual(lint.run(self.root), [])

    def test_an_absolute_home_path_is_found(self):
        self.write("agent/SETUP.md", "Open /Users/someone/Desktop/x.\nOr /Users/<you>/x.\n")
        self.assertEqual(self.found("paths"), ["absolute home path"])

    def test_a_link_or_path_to_a_missing_file_is_found(self):
        self.write("CLAUDE.md", "See [gone](agent/GONE.md), `agent/roles/none.md`, "
                   "`agent/roles/<seat>.md`, `agent/state/runtime/x.json`, "
                   "[web](https://example.com) and `- [Title](file.md)`.\n")
        self.assertEqual(self.found("links"), ["agent/GONE.md does not exist",
                                               "agent/roles/none.md does not exist"])

    def test_a_decision_defined_twice_is_found(self):
        self.write("agent/DECISIONS.md", "## TH-001 — One\n\n## TH-001 — Again\n\n## D-001 — Ours\n")
        self.write("Dabbler/dabbler-docs/DECISIONS.md", "### D-001 — Theirs\n\n### P-001 — One\n")
        self.assertEqual(self.found("decisions"), ["TH-001 is already defined at line 1"])
        self.write("Dabbler/dabbler-docs/DECISIONS.md", "### TH-002 — Clash\n")
        self.write("agent/DECISIONS.md", "## TH-002 — Two\n")
        self.assertEqual(self.found("decisions"), ["TH-002 is also defined in agent/DECISIONS.md"])

    def test_main_exits_one_on_a_finding(self):
        self.assertEqual(lint.main(["--root", self.root]), 0)
        os.remove(os.path.join(self.root, "agent/roles/qa.md"))
        self.assertEqual(lint.main(["--root", self.root]), 1)


class RepositoryIsClean(unittest.TestCase):
    def test_this_repository_has_no_findings(self):
        self.assertEqual(lint.run(ROOT), [])


class SecretScan(unittest.TestCase):
    def names(self, text):
        return [name for _, name in secret_scan.scan_text(text)]

    def test_token_shapes_are_found(self):
        # Each sample is built in parts so this file does not trip the scan itself.
        samples = {
            "atlassian-token": "ATA" + "TT3xFfGF0abcdefghij",
            "github-token": "gh" + "p_" + "a" * 24,
            "api-key-sk": "s" + "k-" + "b" * 24,
            "aws-key": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
            "private-key": "-----BEGIN RSA " + "PRIVATE KEY-----",
            "long-hex": "c0ffee" * 8,
            "assigned-secret": "THEBES_DISPATCH_" + "CAPABILITY=" + "x" * 20,
        }
        for name, sample in samples.items():
            self.assertIn(name, self.names("value " + sample), name)

    def test_ordinary_text_is_not_a_secret(self):
        text = ("ask-what-else-is-needed-for-the-next-step\n"
                "The token is read from the environment.\n"
                "commit 9624bb23ad34e01b06c8fa2167319bf496d3b9b5\n")
        self.assertEqual(secret_scan.scan_text(text), [])

    def test_the_line_number_is_reported(self):
        hits = secret_scan.scan_text("clean\nclean\n" + "AK" + "IA" + "ABCDEFGHIJKLMNOP" + "\n")
        self.assertEqual(hits, [(3, "aws-key")])


if __name__ == "__main__":
    unittest.main()
