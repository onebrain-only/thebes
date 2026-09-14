"""Read-only authority discovery for one proposed Product execution.

The manifest is evidence, not authorization.  It opens no lease, invokes no
provider, changes no claim, and deliberately has no Jira/Supabase write path.
"""

from agent.execution.wake import _CONTROL_PLANE_TOKENS

KNOWN_REQUIRED = "KNOWN_REQUIRED"
CONDITIONALLY_REQUIRED = "CONDITIONALLY_REQUIRED"
RUNTIME_UNKNOWN = "RUNTIME_UNKNOWN"


def discover_execution_authority(work_item_id, state_store):
    task = state_store.read("task", work_item_id)
    if task is None:
        raise ValueError("work item does not exist")
    profile = task.get("execution_profile") or {}
    owner = task.get("ownership") or {}
    receipts = [r for r in state_store.read_all("execution_receipt")
                if r.get("work_item_id") == work_item_id]
    approvals = [r for r in state_store.read_all("execution_approval")
                 if r.get("work_item_id") == work_item_id]
    preparation = next((r for r in state_store.read_all("execution_continuation_preparation")
                        if r.get("work_item_id") == work_item_id), None)
    items = []
    def add(key, classification, detail, ceo=False):
        items.append({"key": key, "classification": classification,
                      "detail": detail, "ceo_decision_required": ceo})

    add("product_execution_authorization", KNOWN_REQUIRED,
        "Product execution needs an explicit governance envelope", True)
    add("work_item", KNOWN_REQUIRED, work_item_id)
    add("seat", KNOWN_REQUIRED, owner.get("seat_id") or "unassigned")
    add("required_capability", KNOWN_REQUIRED, profile.get("required_capability") or "missing")
    add("expected_provider", KNOWN_REQUIRED, "claude-code" if receipts or preparation else "provider unresolved")
    if preparation:
        add("workspace", KNOWN_REQUIRED, preparation["working_directory"])
    else:
        add("workspace", RUNTIME_UNKNOWN, "no continuation workspace has been prepared")
    add("operating_mode", KNOWN_REQUIRED, state_store.current_operating_mode())
    add("jira_governance", KNOWN_REQUIRED, "Ready lifecycle and due-date governance must be current", True)
    add("validation_route", KNOWN_REQUIRED, profile.get("validation_route") or "missing")
    if (profile.get("characteristics") or {}).get("schema_change"):
        add("mutation_class", KNOWN_REQUIRED, "schema_change", True)
    provider_tools = sorted({r.get("permission") for r in approvals if r.get("permission")})
    for tool in provider_tools:
        add("provider_tool:%s" % tool, KNOWN_REQUIRED, tool, True)
    production = next((r for r in approvals if "production project" in (r.get("approval_scope") or "")), None)
    if production:
        add("production_environment", KNOWN_REQUIRED, production["approval_scope"], True)
    else:
        add("production_environment", RUNTIME_UNKNOWN, "target has not been evidenced")
    unsafe = [r for r in approvals if r.get("permission") == "Bash" and any(
        token.lower() in (r.get("allowed_operation") or "").lower() for token in _CONTROL_PLANE_TOKENS)]
    completed = [r for r in receipts if r.get("continuation_of_invocation_id") and r.get("status") != "needs_input"]
    if unsafe or completed:
        add("continuation_remediation", KNOWN_REQUIRED,
            "retire unsafe historical session and prepare exactly one linked replacement", True)
    else:
        add("continuation_remediation", CONDITIONALLY_REQUIRED,
            "only if the provider session becomes unusable")
    add("additional_native_permission", CONDITIONALLY_REQUIRED,
        "only if Claude reaches a new provider-native permission boundary")
    add("runtime_product_data", RUNTIME_UNKNOWN,
        "live catalogue/fixture state may change after preflight")
    decisions = [item["key"] for item in items if item["classification"] == KNOWN_REQUIRED
                 and item["ceo_decision_required"]]
    return {
        "manifest_kind": "execution_authority_manifest", "read_only": True,
        "work_item_id": work_item_id, "items": items,
        "consolidated_ceo_decisions": decisions,
        "no_product_execution": True, "no_jira_mutation": True, "no_supabase_mutation": True,
    }
