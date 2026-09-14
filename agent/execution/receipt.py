"""Durable, inert serialization for normalized provider evidence.

The inverse exists so a terminal result can be recovered from its own receipt
without re-waking a provider — which is what makes an interrupted flow
resumable from durable evidence rather than by running the work again.
"""

from dataclasses import asdict, is_dataclass
from enum import Enum

from agent.execution.provider import (
    ChangedFileClaim, EscalationRequirement, EvidenceClaim, ExecutionResult,
    ExecutionStatus, Failure, FailureCode, TestClaim, TestStatus,
)


def normalized_result_payload(result):
    """Convert an immutable ``ExecutionResult`` to JSON-safe inert evidence."""
    return _json_value(asdict(result))


def _json_value(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, frozenset)):
        return [_json_value(item) for item in value]
    return value


def execution_result_from_payload(payload):
    """Rebuild the immutable result a receipt recorded. Adds nothing to it."""
    if not isinstance(payload, dict):
        raise TypeError("a normalized result payload is required")
    escalation = payload.get("escalation")
    failure = payload.get("failure")
    return ExecutionResult(
        invocation_id=payload["invocation_id"],
        status=ExecutionStatus(payload["status"]),
        summary=payload["summary"],
        evidence=tuple(EvidenceClaim(item["kind"], item["reference"],
                                     item.get("summary"))
                       for item in payload.get("evidence") or ()),
        changed_files=tuple(ChangedFileClaim(item["path"], item.get("change_kind"))
                            for item in payload.get("changed_files") or ()),
        tests=tuple(TestClaim(item["command"], TestStatus(item["status"]),
                              item.get("evidence_ref"), item.get("exit_code"))
                    for item in payload.get("tests") or ()),
        escalation=(EscalationRequirement(
            escalation["reason"], escalation.get("required_authority"),
            escalation.get("required_capability")) if escalation else None),
        failure=(Failure(FailureCode(failure["code"]), failure["message"],
                         bool(failure.get("retryable"))) if failure else None),
        provider_id=payload.get("provider_id"),
        resolved_model_ref=payload.get("resolved_model_ref"),
        resolved_effort_ref=payload.get("resolved_effort_ref"),
        duration_seconds=payload.get("duration_seconds"),
        raw_artifact_ref=payload.get("raw_artifact_ref"),
        continuation_ref=payload.get("continuation_ref"),
    )
