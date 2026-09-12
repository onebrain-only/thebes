"""Side-effect-free fake adapter for provider contract tests only."""

from typing import List

from .provider import (
    ExecutionProvider,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    Failure,
    FailureCode,
    ProviderCapabilities,
)


class FakeProvider(ExecutionProvider):
    """Return a configured result after checking declared provider support."""

    def __init__(self, declared: ProviderCapabilities, result: ExecutionResult):
        self._declared = declared
        self._result = result
        self.requests: List[ExecutionRequest] = []

    def capabilities(self) -> ProviderCapabilities:
        return self._declared

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.requests.append(request)
        if not self._declared.available:
            return self._failure(request, FailureCode.UNAVAILABLE,
                                 self._declared.availability_reason or "provider unavailable")
        if request.model_intent not in self._declared.supported_model_intents:
            return self._failure(request, FailureCode.UNSUPPORTED_MODEL,
                                 "provider does not support model intent %s"
                                 % request.model_intent.value)
        if request.reasoning_effort not in self._declared.supported_reasoning_efforts:
            return self._failure(request, FailureCode.UNSUPPORTED_EFFORT,
                                 "provider does not support reasoning effort %s"
                                 % request.reasoning_effort.value)
        missing = request.required_execution_features - self._declared.execution_features
        if missing:
            return self._failure(
                request, FailureCode.UNSUPPORTED_CAPABILITY,
                "provider does not support execution feature(s): %s"
                % ", ".join(sorted(feature.value for feature in missing)))
        return self._result

    def _failure(self, request: ExecutionRequest, code: FailureCode,
                 message: str) -> ExecutionResult:
        return ExecutionResult(
            invocation_id=request.invocation_id,
            status=ExecutionStatus.PROVIDER_FAILED,
            summary=message,
            failure=Failure(code=code, message=message),
            provider_id=self._declared.provider_id,
        )
