"""Small provider-neutral seam for one bounded executor invocation.

Thebes has already selected and authorised the exact work before this interface
is used.  A provider can describe its execution capabilities and execute one
immutable request.  It cannot select work, claim ownership, change operating
mode, choose validation, appoint a reviewer, mutate Jira/lifecycle, or launch a
second executor.  Provider output is evidence to verify, never workflow truth.

There is intentionally no caller and no Claude/Codex adapter in this slice.
"""

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional, Protocol, Tuple, runtime_checkable


class ExecutionKind(str, Enum):
    ASSESSMENT = "assessment"
    IMPLEMENTATION = "implementation"
    VALIDATION = "validation"
    REVIEW = "review"
    DECISION = "decision"


class MutationMode(str, Enum):
    READ_ONLY = "read_only"
    REPOSITORY_EDIT = "repository_edit"


class ExecutionFeature(str, Enum):
    REPOSITORY_READ = "repository_read"
    REPOSITORY_EDIT = "repository_edit"
    SHELL = "shell"
    BROWSER_AUTOMATION = "browser_automation"
    COMPUTER_CONTROL = "computer_control"
    RESUMABLE_SESSIONS = "resumable_sessions"


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModelIntent(str, Enum):
    COST_EFFICIENT = "cost_efficient"
    BALANCED = "balanced"
    HIGHEST_CAPABILITY = "highest_capability"


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    EXECUTION_FAILED = "execution_failed"
    PROVIDER_FAILED = "provider_failed"


class FailureCode(str, Enum):
    UNAVAILABLE = "unavailable"
    AUTHENTICATION_FAILURE = "authentication_failure"
    UNSUPPORTED_MODEL = "unsupported_model"
    UNSUPPORTED_EFFORT = "unsupported_effort"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    TIMEOUT = "timeout"
    EXECUTOR_PROCESS_FAILURE = "executor_process_failure"
    MALFORMED_RESULT = "malformed_result"
    EXECUTION_FAILURE = "execution_failure"


PROVIDER_FAILURE_CODES = frozenset({
    FailureCode.UNAVAILABLE,
    FailureCode.AUTHENTICATION_FAILURE,
    FailureCode.UNSUPPORTED_MODEL,
    FailureCode.UNSUPPORTED_EFFORT,
    FailureCode.UNSUPPORTED_CAPABILITY,
    FailureCode.TIMEOUT,
    FailureCode.EXECUTOR_PROCESS_FAILURE,
    FailureCode.MALFORMED_RESULT,
})


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class Workspace:
    repository_root: str
    working_directory: str
    mutation_mode: MutationMode
    worktree_path: Optional[str] = None
    expected_revision: Optional[str] = None

    def __post_init__(self):
        if not self.repository_root or not self.working_directory:
            raise ValueError("repository_root and working_directory are required")


@dataclass(frozen=True)
class ReportedEnvironment:
    locality: str
    runtime: Optional[str] = None
    platform: Optional[str] = None
    environment_ref: Optional[str] = None

    def __post_init__(self):
        if self.locality not in ("local", "deployed", "unknown"):
            raise ValueError("unknown reported-environment locality %r" % self.locality)


@dataclass(frozen=True)
class ExecutionTarget:
    locality: str
    runtime: Optional[str] = None
    platform: Optional[str] = None
    environment_ref: Optional[str] = None
    browser_automation: bool = False
    launch_method: Optional[str] = None
    launch_command: Optional[str] = None
    source: str = "reported_environment"


@dataclass(frozen=True)
class ValidationTarget:
    target_id: str
    kind: str
    required: bool
    platform: Optional[str] = None
    surface: Optional[str] = None

    def __post_init__(self):
        if not self.target_id or not self.kind:
            raise ValueError("validation target_id and kind are required")


@dataclass(frozen=True)
class ReturnContract:
    return_to: str
    required_evidence: Tuple[str, ...] = ()
    required_sections: Tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence))
        object.__setattr__(self, "required_sections", tuple(self.required_sections))
        if not self.return_to:
            raise ValueError("return_to is required")


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    available: bool
    execution_features: FrozenSet[ExecutionFeature]
    supported_reasoning_efforts: FrozenSet[ReasoningEffort]
    supported_model_intents: FrozenSet[ModelIntent]
    constraints: Tuple[str, ...] = ()
    availability_reason: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "execution_features", frozenset(self.execution_features))
        object.__setattr__(self, "supported_reasoning_efforts",
                           frozenset(self.supported_reasoning_efforts))
        object.__setattr__(self, "supported_model_intents",
                           frozenset(self.supported_model_intents))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        if not self.provider_id:
            raise ValueError("provider_id is required")
        if self.available and self.availability_reason:
            raise ValueError("an available provider cannot have an availability_reason")
        if not self.available and not self.availability_reason:
            raise ValueError("an unavailable provider must explain why")


@dataclass(frozen=True)
class ExecutionRequest:
    invocation_id: str
    work_item_id: str
    seat_id: str
    required_capability: str
    execution_kind: ExecutionKind
    objective: str
    role_contract_ref: str
    context_refs: Tuple[str, ...]
    workspace: Workspace
    allowed_surfaces: Tuple[str, ...]
    prohibited_actions: Tuple[str, ...]
    operating_mode: str
    operating_mode_revision: int
    claim_ref: Optional[str]
    execution_lease_id: Optional[str]
    reported_environment: ReportedEnvironment
    primary_target: ExecutionTarget
    validation_targets: Tuple[ValidationTarget, ...]
    model_intent: ModelIntent
    reasoning_effort: ReasoningEffort
    required_execution_features: FrozenSet[ExecutionFeature]
    timeout_seconds: int
    return_contract: ReturnContract

    def __post_init__(self):
        for name in ("context_refs", "allowed_surfaces", "prohibited_actions",
                     "validation_targets"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "required_execution_features",
                           frozenset(self.required_execution_features))
        required = {
            "invocation_id": self.invocation_id,
            "work_item_id": self.work_item_id,
            "seat_id": self.seat_id,
            "required_capability": self.required_capability,
            "objective": self.objective,
            "role_contract_ref": self.role_contract_ref,
        }
        missing = sorted(name for name, value in required.items()
                         if not isinstance(value, str) or not value.strip())
        if missing:
            raise ValueError("required request fields are empty: %s" % ", ".join(missing))
        if self.operating_mode not in ("SYSTEM_MAINTENANCE", "PRODUCT_EXECUTION"):
            raise ValueError("unknown operating mode %r" % self.operating_mode)
        if self.operating_mode_revision < 0:
            raise ValueError("operating_mode_revision cannot be negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.operating_mode == "PRODUCT_EXECUTION":
            if not self.claim_ref or not self.execution_lease_id:
                raise ValueError("Product execution requires an existing claim and execution lease")
        for path in self.allowed_surfaces:
            if not path or path.startswith("/") or ".." in path.split("/") or "\\" in path:
                raise ValueError("allowed surface must be a normalized repository-relative path: %r"
                                 % path)


@dataclass(frozen=True)
class EvidenceClaim:
    kind: str
    reference: str
    summary: Optional[str] = None


@dataclass(frozen=True)
class ChangedFileClaim:
    path: str
    change_kind: Optional[str] = None

    def __post_init__(self):
        if not self.path:
            raise ValueError("changed-file claim path is required")


@dataclass(frozen=True)
class TestClaim:
    command: str
    status: TestStatus
    evidence_ref: Optional[str] = None
    exit_code: Optional[int] = None


@dataclass(frozen=True)
class EscalationRequirement:
    reason: str
    required_authority: Optional[str] = None
    required_capability: Optional[str] = None


@dataclass(frozen=True)
class Failure:
    code: FailureCode
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    invocation_id: str
    status: ExecutionStatus
    summary: str
    evidence: Tuple[EvidenceClaim, ...] = ()
    changed_files: Tuple[ChangedFileClaim, ...] = ()
    tests: Tuple[TestClaim, ...] = ()
    escalation: Optional[EscalationRequirement] = None
    failure: Optional[Failure] = None
    provider_id: Optional[str] = None
    resolved_model_ref: Optional[str] = None
    resolved_effort_ref: Optional[str] = None
    duration_seconds: Optional[float] = None
    raw_artifact_ref: Optional[str] = None
    continuation_ref: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "changed_files", tuple(self.changed_files))
        object.__setattr__(self, "tests", tuple(self.tests))
        if not self.invocation_id or not self.summary:
            raise ValueError("invocation_id and summary are required")
        if self.status == ExecutionStatus.PROVIDER_FAILED:
            if self.failure is None or self.failure.code not in PROVIDER_FAILURE_CODES:
                raise ValueError("provider_failed requires a provider failure code")
        elif self.status == ExecutionStatus.EXECUTION_FAILED:
            if self.failure is None or self.failure.code != FailureCode.EXECUTION_FAILURE:
                raise ValueError("execution_failed requires execution_failure")
        elif self.failure is not None:
            raise ValueError("completed/needs_input results cannot carry a failure")


@runtime_checkable
class ExecutionProvider(Protocol):
    """The complete provider interface.  No workflow mutation belongs here."""

    def capabilities(self) -> ProviderCapabilities:
        ...

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...
