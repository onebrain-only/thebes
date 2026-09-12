"""Provider-neutral execution contract and bounded provider seams.

The contract remains provider-neutral. Concrete adapters live in their own
modules and may not acquire workflow authority.
"""

from .provider import (  # noqa: F401
    ChangedFileClaim,
    EvidenceClaim,
    EscalationRequirement,
    ExecutionFeature,
    ExecutionKind,
    ExecutionProvider,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ExecutionTarget,
    Failure,
    FailureCode,
    ModelIntent,
    MutationMode,
    ProviderCapabilities,
    ReasoningEffort,
    ReportedEnvironment,
    ReturnContract,
    TestClaim,
    TestStatus,
    ValidationTarget,
    Workspace,
)
