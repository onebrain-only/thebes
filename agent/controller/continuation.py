"""Prepare a continuation from a needs-input result, so a resume is possible.

`store.record_execution_continuation_preparation` and
`execute_approved_claude_continuation` both existed; nothing called the former,
so the latter could never run — a Product execution that stopped at a native
permission boundary was durably recorded and then unreachable.

This closes exactly that gap and nothing else. It builds no continuation
architecture: it derives the preparation from canonical execution state that
already exists — the needs-input receipt, its provider session, the permission
boundary it names, and the workspace the allocation milestone already realized —
and hands it to the existing writer, which re-verifies every one of those facts
against the record rather than trusting this module.

The preparation is CONTEXT, not authority. It says "here is exactly where and
how this work would resume"; it grants nothing. The approval is a separate
durable accountable-role act (`store.record_execution_approval`), and the resume itself is
`agent.execution.wake.execute_approved_claude_continuation`, which is
Thebes-side. A Product executor neither sees nor invokes any of it.
"""

import re


# The transport reports a denied native tool as a structured escalation reason.
# Tool names are read from it rather than guessed, and the receipt keeps the
# full boundary text either way.
_TOOL_NAME = re.compile(r"'tool_name':\s*'([^']+)'")


def denied_permissions(receipt):
    """Every native tool the provider was refused, in the order it asked."""
    result = (receipt or {}).get("normalized_result") or {}
    reason = str((result.get("escalation") or {}).get("reason") or "")
    seen, ordered = set(), []
    for name in _TOOL_NAME.findall(reason):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def continuable(receipt):
    """Whether this result can be resumed at all.

    Terminal completion has nothing to resume. A provider failure has no
    session to resume into. Only a needs-input Claude result that names both a
    session and a refused permission is continuable.
    """
    if not isinstance(receipt, dict):
        return False
    if receipt.get("status") != "needs_input":
        return False
    if receipt.get("provider_id") != "claude-code":
        return False
    result = receipt.get("normalized_result") or {}
    if not result.get("continuation_ref"):
        return False
    return bool(denied_permissions(receipt))


def preparation_scope(work_item_id, permissions):
    return ("resume the same %s execution in the same workspace and provider "
            "session after the native permission boundary: %s"
            % (work_item_id, ", ".join(permissions)))


def prepare(work_item_id, seat_id, receipt, realized, authorization_ref,
            state_store):
    """Record the durable continuation context for one needs-input result.

    Returns the preparation record, or None when there is nothing continuable.
    Every field is derived; the writer re-verifies identity, session and
    permission boundary against the receipt, so a foreign, stale or mismatched
    receipt is refused there rather than here.
    """
    if not continuable(receipt):
        return None
    permissions = denied_permissions(receipt)
    result = receipt.get("normalized_result") or {}
    workspace = (realized or {}).get("workspace") or {}
    return state_store.record_execution_continuation_preparation(
        original_invocation_id=receipt["invocation_id"],
        work_item_id=work_item_id,
        seat_id=seat_id,
        claude_session_id=result["continuation_ref"],
        # The writer requires one exact permission and checks it against the
        # boundary text. The first refusal is the one that stopped the run; the
        # complete set stays on the receipt this preparation is keyed to.
        permission=permissions[0],
        repository_root=realized["repository_root"],
        working_directory=workspace.get("working_directory") or realized["path"],
        worktree_path=realized["path"],
        branch=realized["branch"],
        expected_revision=realized["expected_revision"],
        authorization_ref=authorization_ref,
        authorization_scope=preparation_scope(work_item_id, permissions),
    )
