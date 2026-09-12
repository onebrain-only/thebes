"""Claude-specific preparation for the current external Agent-tool wake.

The repository does not own a callable Claude transport. The native ``Agent``
tool remains a controller capability. This module validates one already-built
``ExecutionRequest``, resolves current Claude binding defaults, and hands an
immutable wake description to an injected controller transport exactly once.

Slice 4 deliberately returns the transport's raw value unchanged. Converting
that value into ``ExecutionResult`` belongs to Slice 5.
"""

from dataclasses import dataclass
import os
from typing import Any, Callable, Optional, Tuple

from agent.execution.provider import (
    ExecutionFeature,
    ExecutionRequest,
    ExecutionTarget,
    ModelIntent,
    ProviderCapabilities,
    ReasoningEffort,
    ReportedEnvironment,
    ReturnContract,
    ValidationTarget,
    Workspace,
)
from agent.state import roster


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEATS_JSON = os.path.join(ROOT, "agent", "state", "registry", "seats.json")
BINDINGS_DIR = os.path.join(ROOT, ".claude", "bindings")
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")


class ClaudeWakeError(ValueError):
    pass


@dataclass(frozen=True)
class ClaudeWake:
    """Exact controller handoff for one native Claude Agent-tool invocation."""

    native_tool: str
    native_arguments: Tuple[Tuple[str, str], ...]
    subagent_type: str
    prompt: str
    workspace: Workspace
    model: str
    effort: str
    role_contract_ref: str
    context_refs: Tuple[str, ...]
    allowed_surfaces: Tuple[str, ...]
    prohibited_actions: Tuple[str, ...]
    claim_ref: Optional[str]
    execution_lease_id: Optional[str]
    reported_environment: ReportedEnvironment
    primary_target: ExecutionTarget
    validation_targets: Tuple[ValidationTarget, ...]
    return_contract: ReturnContract
    session_ref: Optional[str] = None


def _binding_fields(path):
    wanted = {"name", "role", "model", "effort"}
    fields = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            key, separator, value = line.partition(":")
            if separator and key in wanted:
                if key in fields:
                    raise ClaudeWakeError(
                        "Claude configuration %s declares duplicate %s" % (path, key)
                    )
                fields[key] = value.strip().strip('"').strip("'")
    missing = sorted(wanted - set(fields))
    if missing:
        raise ClaudeWakeError(
            "Claude configuration %s is missing %s"
            % (path, ", ".join(missing))
        )
    return fields


def capabilities():
    """Capabilities of the existing Claude Code Agent-tool execution path."""
    return ProviderCapabilities(
        provider_id="claude-code",
        available=True,
        execution_features=frozenset(ExecutionFeature),
        supported_reasoning_efforts=frozenset(ReasoningEffort),
        supported_model_intents=frozenset(ModelIntent),
        constraints=(
            "transport is the controller-native external Agent tool",
            "subagent_type is the exact neutral Seat id",
            "binding model and effort remain authoritative in Slice 4",
            "raw transport results are not normalized until Slice 5",
        ),
    )


def prepare_claude_wake(request, session_ref=None, registry_path=SEATS_JSON,
                        bindings_dir=BINDINGS_DIR, agents_dir=AGENTS_DIR):
    """Validate and preserve one request without invoking external transport."""
    if not isinstance(request, ExecutionRequest):
        raise ClaudeWakeError("Claude wake requires the provider-neutral ExecutionRequest")

    neutral = roster.read(registry_path)
    if request.seat_id not in neutral:
        raise ClaudeWakeError("unknown neutral Seat %r" % request.seat_id)
    role_id = neutral[request.seat_id]["role"]
    if request.required_capability != role_id:
        raise ClaudeWakeError(
            "Seat %r has capability %r, not %r"
            % (request.seat_id, role_id, request.required_capability)
        )
    expected_role_ref = "agent/roles/%s.md" % role_id
    if request.role_contract_ref != expected_role_ref:
        raise ClaudeWakeError(
            "Role contract must be %r for Seat %r"
            % (expected_role_ref, request.seat_id)
        )

    binding_path = os.path.join(bindings_dir, request.seat_id + ".yml")
    agent_path = os.path.join(agents_dir, request.seat_id + ".md")
    if not os.path.isfile(binding_path):
        raise ClaudeWakeError(
            "neutral Seat %r has no Claude configuration" % request.seat_id
        )
    if not os.path.isfile(agent_path):
        raise ClaudeWakeError(
            "neutral Seat %r has no generated Claude agent definition"
            % request.seat_id
        )
    binding = _binding_fields(binding_path)
    if binding["name"] != request.seat_id:
        raise ClaudeWakeError(
            "Claude configuration name %r does not match Seat %r"
            % (binding["name"], request.seat_id)
        )
    if binding["role"] != role_id:
        raise ClaudeWakeError(
            "Claude legacy Role %r does not match neutral Role %r"
            % (binding["role"], role_id)
        )

    declared = capabilities()
    missing_features = request.required_execution_features - declared.execution_features
    if missing_features:
        raise ClaudeWakeError(
            "Claude wake lacks execution feature(s): %s"
            % ", ".join(sorted(feature.value for feature in missing_features))
        )

    # The already-written brief is passed byte-for-byte as the native prompt.
    # The native Agent tool resolves model/effort from the generated definition;
    # neutral intent fields do not override those binding defaults in this slice.
    arguments = (("subagent_type", request.seat_id), ("prompt", request.objective))
    return ClaudeWake(
        native_tool="Agent",
        native_arguments=arguments,
        subagent_type=request.seat_id,
        prompt=request.objective,
        workspace=request.workspace,
        model=binding["model"],
        effort=binding["effort"],
        role_contract_ref=request.role_contract_ref,
        context_refs=request.context_refs,
        allowed_surfaces=request.allowed_surfaces,
        prohibited_actions=request.prohibited_actions,
        claim_ref=request.claim_ref,
        execution_lease_id=request.execution_lease_id,
        reported_environment=request.reported_environment,
        primary_target=request.primary_target,
        validation_targets=request.validation_targets,
        return_contract=request.return_contract,
        session_ref=session_ref,
    )


class ClaudeProvider:
    """Two-operation provider seam using a controller-supplied native transport."""

    def __init__(self, transport: Callable[[ClaudeWake], Any], session_ref=None,
                 registry_path=SEATS_JSON, bindings_dir=BINDINGS_DIR,
                 agents_dir=AGENTS_DIR):
        if not callable(transport):
            raise ClaudeWakeError(
                "ClaudeProvider needs the controller-native Agent transport"
            )
        self._transport = transport
        self._session_ref = session_ref
        self._registry_path = registry_path
        self._bindings_dir = bindings_dir
        self._agents_dir = agents_dir

    def capabilities(self):
        return capabilities()

    def execute(self, request):
        """Invoke the external transport once and preserve its raw return value."""
        wake = prepare_claude_wake(
            request,
            session_ref=self._session_ref,
            registry_path=self._registry_path,
            bindings_dir=self._bindings_dir,
            agents_dir=self._agents_dir,
        )
        return self._transport(wake)
