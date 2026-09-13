#!/usr/bin/env python3
"""One manual, isolated end-to-end smoke for the Phase-2 controller bridge.

It uses a temporary Persistent State root, a factual in-memory Jira response,
and the installed Claude CLI.  It never addresses a Product worktree, Jira, or
production.  This is intentionally not part of the ordinary unit-test suite:
it exercises a real executor transport.
"""

import copy
import json
import os
import shutil
import sys
import tempfile


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.controller import available_provider_registry, execute  # noqa: E402
from agent.state import store  # noqa: E402
import store as legacy_store  # noqa: E402


class Authorization:
    def for_work_item(self, work_item_id):
        return {"authorized": True, "reason": "isolated-smoke-authorized",
                "reference": "isolated controller smoke only"}


class Jira:
    def get_issue(self, work_item_id):
        return {"key": work_item_id, "status_id": "10008"}


def _fixture_task():
    source = os.path.join(ROOT, "agent", "state", "runtime", "tasks", "KAN-183.json")
    with open(source, encoding="utf-8") as fh:
        task = json.load(fh)
    task = copy.deepcopy(task)
    task["work_item_id"] = "KAN-900"
    task["ownership"] = None
    task.pop("executor_evidence", None)
    task["surfaces"] = []
    task["logical_surfaces"] = []
    task["execution_profile"]["required_capability"] = "content"
    task["execution_profile"]["provenance"]["required_capability"]["by"] = "po"
    task["lifecycle"] = {
        "canonical": "ready", "jira_column": "Ready", "jira_status_id": "10008",
        "jira_status_name": "Ready", "observed_at": "2026-09-13T00:00:00Z", "source": "jira",
    }
    return task


def _brief(workspace):
    return {
        "seat_id": "content-manager", "execution_kind": "assessment",
        "objective": (
            "This is an isolated Thebes controller smoke. Do not inspect, create, edit, "
            "or delete files. Do not call external services. Reply exactly: "
            "THEBES_CONTROLLER_SMOKE_OK."
        ),
        "context_refs": ["agent/MASTER_ROADMAP.md"],
        "workspace": {"repository_root": workspace, "working_directory": workspace,
                      "mutation_mode": "read_only"},
        "reported_environment": {"locality": "unknown", "environment_ref": "isolated-smoke"},
        "primary_target": {"locality": "unknown", "environment_ref": "isolated-smoke"},
        "validation_targets": [{"target_id": "claude-cli", "kind": "transport",
                                "required": True}],
        "model_intent": "cost_efficient", "reasoning_effort": "low",
        "required_execution_features": ["repository_read"], "timeout_seconds": 120,
        "return_contract": {"return_to": "controller", "required_evidence": [],
                            "required_sections": ["RESULT"]},
    }


def main():
    state_modules = (store, legacy_store)
    saved = {module: {name: getattr(module, name)
                      for name in ("ROOT", "STATE", "RUNTIME", "REGISTRY", "LOCKS")}
             for module in state_modules}
    with tempfile.TemporaryDirectory(prefix="thebes-controller-smoke-") as root:
        workspace = os.path.join(root, "workspace")
        os.makedirs(workspace)
        for module in state_modules:
            module.ROOT = root
            module.STATE = os.path.join(root, "agent", "state")
            module.RUNTIME = os.path.join(module.STATE, "runtime")
            module.REGISTRY = os.path.join(ROOT, "agent", "state", "registry")
            module.LOCKS = os.path.join(module.RUNTIME, ".locks")
        try:
            mode = store.set_operating_mode("PRODUCT_EXECUTION", "system-maintenance",
                                            "isolated controller smoke", None)
            assert mode["mode"] == "PRODUCT_EXECUTION"
            store.create("task", _fixture_task(), rid="KAN-900")
            outcome = execute("KAN-900", _brief(workspace), authorization=Authorization(),
                              state_store=store, jira_client=Jira(),
                              providers=available_provider_registry())
            assert outcome["selected_provider"] == "claude-code", outcome
            assert outcome["execution_status"] == "completed", outcome
            assert outcome["result_receipt_status"] == "received", outcome
            assert outcome["lease_closure_status"] == "closed", outcome
            assert outcome["summary"].strip().startswith("THEBES_CONTROLLER_SMOKE_OK"), outcome
            # Claude persists its own session metadata so a native-permission
            # continuation can resume.  It is transport metadata in this temp
            # directory, not executor-created Product work.
            assert set(os.listdir(workspace)) <= {".claude-flow"}, os.listdir(workspace)
            print(json.dumps(outcome, indent=2, sort_keys=True))
        finally:
            for module, values in saved.items():
                for name, value in values.items():
                    setattr(module, name, value)


if __name__ == "__main__":
    main()
