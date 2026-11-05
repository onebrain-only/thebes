import unittest

from agent.execution import conversation_dispatch as cd


class TeamWorktreeRuleTests(unittest.TestCase):
    def lines(self):
        rec = {"branch": "alpha-karnak", "checks": [{"id": "c1", "kind": "run"}]}
        return "\n".join(cd.verify_block(rec))

    def test_one_worktree_per_team_not_per_ticket(self):
        text = self.lines()
        self.assertIn("ONE worktree per team", text)
        self.assertIn("do not create a folder or worktree per ticket", text)

    def test_plans_go_to_docs_and_screenshots_are_last_resort(self):
        text = self.lines()
        self.assertIn("Dabbler/dabbler-docs/", text)
        self.assertIn("screenshot only as a last resort", text)


if __name__ == "__main__":
    unittest.main()
