#!/usr/bin/env python3
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "agent", "scripts"))
import cloud_prompt                                                  # noqa: E402


class CloudPromptTests(unittest.TestCase):
    def test_the_prompt_names_the_branch_the_base_the_prefix_and_carries_the_whole_ticket(self):
        j = mock.Mock()
        j.get_issue.return_value = {"summary": "Refresh keeps content", "description": "GOAL: x\\nBRANCH: alpha-<team>\\nCHECKS:\\nC1 | run | ..."}
        text = cloud_prompt.build("KAN-606", "alpha-deir-el-bahari", jira=j)
        for part in ("git checkout -b alpha-cloud-kan-606 origin/alpha-deir-el-bahari",
                     "git push origin alpha-cloud-kan-606", "starts with `KAN-606:`",
                     "Never push, merge or open a pull request into Alpha", "flutter test --no-pub",
                     "GOAL: x", "Ignore the `BRANCH:` line"):
            self.assertIn(part, text)

    def test_a_ticket_without_a_description_is_refused(self):
        j = mock.Mock()
        j.get_issue.return_value = {"summary": "x", "description": ""}
        with self.assertRaises(SystemExit):
            cloud_prompt.build("KAN-1", "Alpha", jira=j)


if __name__ == "__main__":
    unittest.main()
