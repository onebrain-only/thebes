"""Deterministic, provider-neutral selection for one existing execution request.

Selection only answers which supplied provider may execute the request. It does
not invoke a provider, change the request, or acquire workflow authority.
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from agent.execution.provider import (
    ExecutionProvider,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    Failure,
    FailureCode,
    ProviderCapabilities,
)


# Compatibility-first tie breaking is explicit policy, not a score. Unknown
# future provider ids sort after the two implemented adapters by their id.
DEFAULT_PROVIDER_ORDER = ("claude-code", "codex-cli")


@dataclass(frozen=True)
class ProviderSelection:
    """The one provider selected for a request, or a normalized selection failure."""

    provider: Optional[ExecutionProvider]
    provider_id: Optional[str]
    failure: Optional[Failure] = None
    primary_provider_id: Optional[str] = None
    primary_ineligibility: Optional[Failure] = None

    def __post_init__(self):
        if (self.provider is None) == (self.failure is None):
            raise ValueError("selection requires exactly one provider or failure")
        if self.provider is not None and not self.provider_id:
            raise ValueError("a selected provider requires provider_id")
        if self.primary_ineligibility is not None and not self.primary_provider_id:
            raise ValueError("a primary ineligibility names its primary provider")

    def failure_result(self, request):
        """Render a selection failure in the existing provider result vocabulary."""
        if self.failure is None:
            raise ValueError("a selected provider has no failure result")
        return ExecutionResult(
            invocation_id=request.invocation_id,
            status=ExecutionStatus.PROVIDER_FAILED,
            summary=self.failure.message,
            failure=self.failure,
            provider_id="thebes-provider-selection",
        )

    def receipt_evidence(self):
        """Inert selection facts persisted beside the terminal provider result."""
        evidence = {"primary_provider_id": self.primary_provider_id or self.provider_id,
                    "selected_provider_id": self.provider_id}
        if self.primary_ineligibility is not None:
            evidence["primary_ineligibility"] = {
                "code": self.primary_ineligibility.code.value,
                "message": self.primary_ineligibility.message,
            }
        return evidence


def select_provider(request, providers: Sequence[ExecutionProvider], override=None):
    """Select one eligible provider without executing it.

    ``override`` is a controller-authorized provider id. It narrows selection
    to that provider and still applies every compatibility gate.
    """
    if not isinstance(request, ExecutionRequest):
        raise TypeError("provider selection requires ExecutionRequest")

    declared = _declared_providers(providers)
    if _is_product_code_execution(request):
        return _select_product_code_provider(request, declared)
    if override is not None:
        if not isinstance(override, str) or not override.strip():
            return _failure(FailureCode.UNSUPPORTED_CAPABILITY,
                            "provider override must name a provider id")
        matching = [item for item in declared if item[1].provider_id == override]
        if not matching:
            return _failure(FailureCode.UNSUPPORTED_CAPABILITY,
                            "provider override %r is not supplied" % override)
        provider, capability = matching[0]
        reason = _ineligibility(request, capability)
        if reason is not None:
            return _failure(reason, "provider override %r cannot satisfy this request" % override)
        return ProviderSelection(provider, capability.provider_id)

    eligible = []
    reasons = []
    for provider, capability in declared:
        reason = _ineligibility(request, capability)
        if reason is None:
            eligible.append((provider, capability))
        else:
            reasons.append(reason)
    if not eligible:
        return _failure(_no_provider_reason(reasons),
                        "no supplied provider can satisfy this request")

    provider, capability = min(
        eligible, key=lambda item: _provider_rank(item[1].provider_id)
    )
    return ProviderSelection(provider, capability.provider_id)


def _is_product_code_execution(request):
    """The narrowly-scoped Claude-first policy; reasoning work is unaffected."""
    return (request.operating_mode == "PRODUCT_EXECUTION"
            and request.workspace.mutation_mode.value == "repository_edit")


def _select_product_code_provider(request, declared):
    """Select Claude first, with Codex only for pre-dispatch provider ineligibility.

    An override cannot turn the currently-running Codex controller into the Product
    executor.  This is selection-time fallback, not a second dispatch: once a provider has
    been dispatched, its normalized result is terminal evidence for that wake.
    """
    by_id = {capability.provider_id: (provider, capability)
             for provider, capability in declared}
    claude_item = by_id.get("claude-code")
    if claude_item is None:
        primary_failure = Failure(FailureCode.UNAVAILABLE,
                                  "claude-code is not declared for Product code execution")
    else:
        claude, capability = claude_item
        reason = _ineligibility(request, capability)
        if reason is None:
            return ProviderSelection(claude, "claude-code", primary_provider_id="claude-code")
        primary_failure = Failure(
            reason, _ineligibility_message("claude-code", capability, reason)
        )

    codex_item = by_id.get("codex-cli")
    if codex_item is not None:
        codex, capability = codex_item
        if _ineligibility(request, capability) is None:
            return ProviderSelection(codex, "codex-cli", primary_provider_id="claude-code",
                                     primary_ineligibility=primary_failure)

    return _failure(primary_failure.code, primary_failure.message,
                    primary_provider_id="claude-code",
                    primary_ineligibility=primary_failure)


def _declared_providers(providers):
    declared = []
    provider_ids = set()
    for provider in tuple(providers):
        if not isinstance(provider, ExecutionProvider):
            raise TypeError("provider selection requires ExecutionProvider instances")
        capability = provider.capabilities()
        if not isinstance(capability, ProviderCapabilities):
            raise TypeError("provider capabilities must be ProviderCapabilities")
        if capability.provider_id in provider_ids:
            raise ValueError("provider ids must be unique")
        provider_ids.add(capability.provider_id)
        declared.append((provider, capability))
    return tuple(declared)


def _ineligibility(request, capability):
    if not capability.available:
        return FailureCode.UNAVAILABLE
    if not request.required_execution_features <= capability.execution_features:
        return FailureCode.UNSUPPORTED_CAPABILITY
    if request.model_intent not in capability.supported_model_intents:
        return FailureCode.UNSUPPORTED_MODEL
    if request.reasoning_effort not in capability.supported_reasoning_efforts:
        return FailureCode.UNSUPPORTED_EFFORT
    return None


def _ineligibility_message(provider_id, capability, reason):
    if reason == FailureCode.UNAVAILABLE:
        detail = capability.availability_reason or "provider unavailable"
        return "%s cannot execute: %s" % (provider_id, detail)
    return "%s cannot execute: %s" % (provider_id, reason.value)


def _no_provider_reason(reasons):
    if not reasons or all(reason == FailureCode.UNAVAILABLE for reason in reasons):
        return FailureCode.UNAVAILABLE
    for code in (FailureCode.UNSUPPORTED_CAPABILITY, FailureCode.UNSUPPORTED_MODEL,
                 FailureCode.UNSUPPORTED_EFFORT):
        if code in reasons:
            return code
    return FailureCode.UNAVAILABLE


def _provider_rank(provider_id):
    try:
        return (0, DEFAULT_PROVIDER_ORDER.index(provider_id))
    except ValueError:
        return (1, provider_id)


def _failure(code, message, primary_provider_id=None, primary_ineligibility=None):
    return ProviderSelection(None, None, Failure(code, message), primary_provider_id,
                             primary_ineligibility)
