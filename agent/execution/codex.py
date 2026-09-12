"""Codex CLI adapter for one provider-neutral execution request.

The local runtime exposes ``codex exec`` as a repository-callable transport.
This adapter prepares its exact workspace, sandbox, model and reasoning inputs,
and a deterministic executor brief containing every core-owned constraint that
the CLI cannot enforce itself. It then normalizes the outcome into
``ExecutionResult``. It has no workflow authority and does not select, retry,
or fall back between providers.
"""

from dataclasses import dataclass
import os
import subprocess
from typing import Any, Callable, Mapping, Optional, Tuple

from agent.execution.provider import (
    ChangedFileClaim,
    EscalationRequirement,
    EvidenceClaim,
    ExecutionFeature,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    Failure,
    FailureCode,
    ModelIntent,
    MutationMode,
    ProviderCapabilities,
    ReasoningEffort,
    TestClaim,
    TestStatus,
)
from agent.state import roster


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEATS_JSON = os.path.join(ROOT, "agent", "state", "registry", "seats.json")

# These identifiers and effort levels are evidenced by the installed Codex CLI
# model cache on 2026-09-12. The neutral intent is mapped explicitly; no
# request is silently downgraded to the user's CLI default.
CODEX_MODEL_MAP = {
    ModelIntent.COST_EFFICIENT: "gpt-5.6-luna",
    ModelIntent.BALANCED: "gpt-5.6-terra",
    ModelIntent.HIGHEST_CAPABILITY: "gpt-6-astra",
}
CODEX_REASONING_EFFORTS = frozenset({
    ReasoningEffort.LOW,
    ReasoningEffort.MEDIUM,
    ReasoningEffort.HIGH,
})


class CodexInvocationError(ValueError):
    pass


class CodexTransportFailure(Exception):
    """A classified failure reported by the Codex transport."""

    code = FailureCode.EXECUTOR_PROCESS_FAILURE

    def __init__(self, message, raw_artifact_ref=None):
        super().__init__(message)
        self.raw_artifact_ref = raw_artifact_ref


class CodexUnavailable(CodexTransportFailure):
    code = FailureCode.UNAVAILABLE


class CodexAuthenticationFailure(CodexTransportFailure):
    code = FailureCode.AUTHENTICATION_FAILURE


class CodexUnsupportedModel(CodexTransportFailure):
    code = FailureCode.UNSUPPORTED_MODEL


class CodexUnsupportedEffort(CodexTransportFailure):
    code = FailureCode.UNSUPPORTED_EFFORT


class CodexUnsupportedCapability(CodexTransportFailure):
    code = FailureCode.UNSUPPORTED_CAPABILITY


class CodexTimeout(CodexTransportFailure):
    code = FailureCode.TIMEOUT


class CodexExecutorProcessFailure(CodexTransportFailure):
    code = FailureCode.EXECUTOR_PROCESS_FAILURE


class CodexMalformedResult(CodexTransportFailure):
    code = FailureCode.MALFORMED_RESULT


@dataclass(frozen=True)
class CodexInvocation:
    """One fully constrained Codex CLI invocation prepared from core input."""

    request: ExecutionRequest
    prompt: str
    model: str
    reasoning_effort: str
    sandbox: str
    session_ref: Optional[str] = None


def capabilities():
    """Only capabilities evidenced by the installed ``codex exec`` runtime."""
    return ProviderCapabilities(
        provider_id="codex-cli",
        available=True,
        execution_features=frozenset({
            ExecutionFeature.REPOSITORY_READ,
            ExecutionFeature.REPOSITORY_EDIT,
            ExecutionFeature.SHELL,
        }),
        supported_reasoning_efforts=CODEX_REASONING_EFFORTS,
        supported_model_intents=frozenset(CODEX_MODEL_MAP),
        constraints=(
            "transport is the local codex exec CLI",
            "working directory, sandbox, timeout, model, and reasoning effort are transport-enforced from the ExecutionRequest",
            "Role, context, surfaces, environment, validation, and return constraints are executor instructions in the rendered brief",
            "no browser automation, computer control, or resumable-session capability is declared",
            "transport evidence is normalized without workflow side effects",
        ),
    )


def prepare_codex_invocation(request, session_ref=None, registry_path=SEATS_JSON,
                             model_map=CODEX_MODEL_MAP,
                             supported_efforts=CODEX_REASONING_EFFORTS):
    """Validate a core request and prepare, but do not launch, Codex CLI."""
    if not isinstance(request, ExecutionRequest):
        raise CodexInvocationError("Codex requires the provider-neutral ExecutionRequest")

    neutral = roster.read(registry_path)
    if request.seat_id not in neutral:
        raise CodexInvocationError("unknown neutral Seat %r" % request.seat_id)
    role_id = neutral[request.seat_id]["role"]
    if request.required_capability != role_id:
        raise CodexInvocationError(
            "Seat %r has capability %r, not %r"
            % (request.seat_id, role_id, request.required_capability)
        )
    expected_role_ref = "agent/roles/%s.md" % role_id
    if request.role_contract_ref != expected_role_ref:
        raise CodexInvocationError(
            "Role contract must be %r for Seat %r"
            % (expected_role_ref, request.seat_id)
        )

    declared = capabilities()
    missing_features = request.required_execution_features - declared.execution_features
    if missing_features:
        raise CodexUnsupportedCapability(
            "Codex lacks execution feature(s): %s"
            % ", ".join(sorted(feature.value for feature in missing_features))
        )
    if request.model_intent not in model_map:
        raise CodexUnsupportedModel(
            "Codex has no model mapping for %r" % request.model_intent
        )
    if request.reasoning_effort not in supported_efforts:
        raise CodexUnsupportedEffort(
            "Codex does not support reasoning effort %r" % request.reasoning_effort
        )

    sandbox = {
        MutationMode.READ_ONLY: "read-only",
        MutationMode.REPOSITORY_EDIT: "workspace-write",
    }.get(request.workspace.mutation_mode)
    if sandbox is None:
        raise CodexUnsupportedCapability(
            "Codex cannot honor mutation mode %r" % request.workspace.mutation_mode
        )

    model = model_map[request.model_intent]
    effort = request.reasoning_effort.value
    return CodexInvocation(
        request=request,
        prompt=render_codex_brief(request, model, effort),
        model=model,
        reasoning_effort=effort,
        sandbox=sandbox,
        session_ref=session_ref,
    )


def render_codex_brief(request, resolved_model, resolved_effort):
    """Render one deterministic Codex brief without changing core constraints.

    The CLI can mechanically constrain cwd, sandbox, timeout, model, and
    reasoning effort. It has no path-level allowlist or environment-target
    control, so those facts remain explicit executor instructions rather than
    claimed transport enforcement.
    """
    workspace = request.workspace
    environment = request.reported_environment
    target = request.primary_target
    lines = (
        "# Thebes Authorized Execution Brief",
        "",
        "## Identity",
        "- Work item ID: %s" % request.work_item_id,
        "- Seat ID: %s" % request.seat_id,
        "- Required capability: %s" % request.required_capability,
        "- Execution kind: %s" % request.execution_kind.value,
        "",
        "## Objective",
        request.objective,
        "",
        "## Role and ordered context",
        "- Role contract reference: %s" % request.role_contract_ref,
        "- Context references (ordered):",
        *_numbered(request.context_refs),
        "",
        "## Workspace — transport-enforced",
        "- Repository root: %s" % workspace.repository_root,
        "- Working directory: %s" % workspace.working_directory,
        "- Worktree: %s" % _value(workspace.worktree_path),
        "- Expected revision: %s" % _value(workspace.expected_revision),
        "- Mutation mode: %s" % workspace.mutation_mode.value,
        "",
        "## Allowed surfaces — executor instruction",
        "- Codex sandbox limits repository write mode, not individual paths.",
        *_listed(request.allowed_surfaces),
        "",
        "## Prohibited actions — executor instruction",
        *_listed(request.prohibited_actions),
        "",
        "## Operating constraints",
        "- Operating mode: %s" % request.operating_mode,
        "- Model intent: %s" % request.model_intent.value,
        "- Resolved Codex model: %s" % resolved_model,
        "- Reasoning effort: %s" % resolved_effort,
        "- Required execution features: %s" % _features(request),
        "- Timeout seconds: %s" % request.timeout_seconds,
        "",
        "## Environment and validation — executor instruction",
        "- Reported environment: %s" % _reported_environment(environment),
        "- Primary execution target: %s" % _execution_target(target),
        "- The reported environment and primary target are authoritative.",
        "- Do not substitute another environment for convenience.",
        "- Comparative environments cannot replace primary validation.",
        "- Browser-under-test is not the browser-automation environment.",
        "- Validation targets (ordered):",
        *_validation_targets(request.validation_targets),
        "",
        "## Return contract — executor instruction",
        "- Return to: %s" % request.return_contract.return_to,
        "- Required evidence:",
        *_listed(request.return_contract.required_evidence),
        "- Required sections:",
        *_listed(request.return_contract.required_sections),
        "",
        "## Lease and claim references",
        "- Claim reference: %s" % _value(request.claim_ref),
        "- Execution lease ID: %s" % _value(request.execution_lease_id),
    )
    return "\n".join(lines) + "\n"


def _value(value):
    return value if value is not None else "none"


def _listed(values):
    return tuple("- %s" % value for value in values) or ("- none",)


def _numbered(values):
    return tuple("  %d. %s" % (index, value) for index, value in enumerate(values, 1)) or (
        "  none",
    )


def _features(request):
    return ", ".join(sorted(feature.value for feature in request.required_execution_features))


def _reported_environment(environment):
    return "locality=%s; runtime=%s; platform=%s; ref=%s" % (
        environment.locality, _value(environment.runtime), _value(environment.platform),
        _value(environment.environment_ref),
    )


def _execution_target(target):
    return ("locality=%s; runtime=%s; platform=%s; ref=%s; browser_automation=%s; "
            "launch_method=%s; launch_command=%s; source=%s") % (
                target.locality, _value(target.runtime), _value(target.platform),
                _value(target.environment_ref), str(target.browser_automation).lower(),
                _value(target.launch_method), _value(target.launch_command), target.source,
            )


def _validation_targets(targets):
    return tuple(
        "  %d. id=%s; kind=%s; required=%s; platform=%s; surface=%s" % (
            index, target.target_id, target.kind, str(target.required).lower(),
            _value(target.platform), _value(target.surface),
        )
        for index, target in enumerate(targets, 1)
    ) or ("  none",)


class CodexCliTransport:
    """Direct local transport for the evidenced ``codex exec`` command.

    Session references remain result metadata: ``codex exec resume`` does not
    expose the same workspace/sandbox controls, so this adapter does not claim
    resumable-session support.
    """

    def __init__(self, binary="codex", runner=subprocess.run):
        self._binary = binary
        self._runner = runner

    def command(self, invocation):
        return (
            self._binary,
            "exec",
            "--model", invocation.model,
            "--config", 'model_reasoning_effort="%s"' % invocation.reasoning_effort,
            "--cd", invocation.request.workspace.working_directory,
            "--sandbox", invocation.sandbox,
            "--ephemeral",
            invocation.prompt,
        )

    def __call__(self, invocation):
        try:
            completed = self._runner(
                self.command(invocation),
                capture_output=True,
                text=True,
                timeout=invocation.request.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise CodexUnavailable("Codex CLI is unavailable: %s" % exc)
        except subprocess.TimeoutExpired as exc:
            raise CodexTimeout("Codex CLI timed out: %s" % exc)
        except OSError as exc:
            raise CodexExecutorProcessFailure("Codex CLI could not start: %s" % exc)
        if completed.returncode:
            diagnostic = (completed.stderr or completed.stdout or
                          "Codex CLI exited %d" % completed.returncode)
            raise CodexExecutorProcessFailure(diagnostic.strip())
        return completed.stdout


_RESULT_KEYS = frozenset({
    "status", "summary", "evidence", "changed_files", "tests", "escalation",
    "failure_message", "duration_seconds", "continuation_ref", "raw_artifact_ref",
})


def _optional_string(value, field):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise CodexMalformedResult("%s must be a non-empty string or null" % field)
    return value


def _claims(rows, required, optional, build, field):
    if rows is None:
        return ()
    if not isinstance(rows, (list, tuple)):
        raise CodexMalformedResult("%s must be a list" % field)
    claims = []
    allowed = set(required) | set(optional)
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) - allowed:
            raise CodexMalformedResult("%s[%d] has an invalid shape" % (field, index))
        if any(not isinstance(row.get(key), str) or not row[key].strip()
               for key in required):
            raise CodexMalformedResult("%s[%d] is missing required text" % (field, index))
        try:
            claims.append(build(row))
        except (TypeError, ValueError) as exc:
            raise CodexMalformedResult("%s[%d]: %s" % (field, index, exc))
    return tuple(claims)


def _evidence_claim(row):
    return EvidenceClaim(
        row["kind"], row["reference"],
        _optional_string(row.get("summary"), "evidence summary")
    )


def _changed_file_claim(row):
    return ChangedFileClaim(
        row["path"], _optional_string(row.get("change_kind"), "change_kind")
    )


def _test_claim(row):
    evidence_ref = _optional_string(row.get("evidence_ref"), "test evidence_ref")
    exit_code = row.get("exit_code")
    if exit_code is not None and (not isinstance(exit_code, int)
                                  or isinstance(exit_code, bool)):
        raise CodexMalformedResult("test exit_code must be an integer or null")
    return TestClaim(row["command"], TestStatus(row["status"]), evidence_ref, exit_code)


def normalize_codex_result(request, invocation, raw):
    """Normalize supported Codex transport evidence without workflow inference."""
    if isinstance(raw, str):
        if not raw.strip():
            raise CodexMalformedResult("Codex returned an empty result")
        payload = {"status": "completed", "summary": raw}
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        raise CodexMalformedResult("Codex result must be text or a result mapping")

    unknown = set(payload) - _RESULT_KEYS
    if unknown:
        raise CodexMalformedResult(
            "Codex result has unknown field(s): %s" % ", ".join(sorted(unknown))
        )
    try:
        status = ExecutionStatus(payload.get("status"))
    except (TypeError, ValueError):
        raise CodexMalformedResult("Codex result has an invalid status")
    if status == ExecutionStatus.PROVIDER_FAILED:
        raise CodexMalformedResult("transport results cannot self-declare provider_failed")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise CodexMalformedResult("Codex result requires a non-empty summary")

    evidence = _claims(payload.get("evidence"), ("kind", "reference"),
                       ("summary",), _evidence_claim, "evidence")
    changed_files = _claims(payload.get("changed_files"), ("path",),
                            ("change_kind",), _changed_file_claim, "changed_files")
    tests = _claims(payload.get("tests"), ("command", "status"),
                    ("evidence_ref", "exit_code"), _test_claim, "tests")

    escalation = payload.get("escalation")
    if escalation is not None:
        if (not isinstance(escalation, Mapping)
                or set(escalation) - {"reason", "required_authority",
                                      "required_capability"}
                or not isinstance(escalation.get("reason"), str)
                or not escalation["reason"].strip()):
            raise CodexMalformedResult("escalation has an invalid shape")
        escalation = EscalationRequirement(
            escalation["reason"],
            _optional_string(escalation.get("required_authority"),
                             "escalation required_authority"),
            _optional_string(escalation.get("required_capability"),
                             "escalation required_capability"),
        )
    if status == ExecutionStatus.NEEDS_INPUT and escalation is None:
        raise CodexMalformedResult("needs_input requires a bounded escalation reason")
    if status != ExecutionStatus.NEEDS_INPUT and escalation is not None:
        raise CodexMalformedResult("escalation is valid only for needs_input")

    failure_message = payload.get("failure_message")
    if status == ExecutionStatus.EXECUTION_FAILED:
        if not isinstance(failure_message, str) or not failure_message.strip():
            raise CodexMalformedResult("execution_failed requires failure_message")
        failure = Failure(FailureCode.EXECUTION_FAILURE, failure_message)
    else:
        if failure_message is not None:
            raise CodexMalformedResult("failure_message is valid only for execution_failed")
        failure = None

    duration = payload.get("duration_seconds")
    if (duration is not None
            and (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                 or duration < 0)):
        raise CodexMalformedResult("duration_seconds must be a non-negative number")

    continuation = _optional_string(payload.get("continuation_ref"), "continuation_ref")
    artifact = _optional_string(payload.get("raw_artifact_ref"), "raw_artifact_ref")
    return ExecutionResult(
        invocation_id=request.invocation_id,
        status=status,
        summary=summary,
        evidence=evidence,
        changed_files=changed_files,
        tests=tests,
        escalation=escalation,
        failure=failure,
        provider_id="codex-cli",
        resolved_model_ref=invocation.model,
        resolved_effort_ref=invocation.reasoning_effort,
        duration_seconds=duration,
        raw_artifact_ref=artifact,
        continuation_ref=continuation or invocation.session_ref,
    )


def _provider_failure(request, code, message, invocation=None, raw_artifact_ref=None):
    return ExecutionResult(
        invocation_id=request.invocation_id,
        status=ExecutionStatus.PROVIDER_FAILED,
        summary=message,
        failure=Failure(code, message),
        provider_id="codex-cli",
        resolved_model_ref=invocation.model if invocation else None,
        resolved_effort_ref=invocation.reasoning_effort if invocation else None,
        raw_artifact_ref=raw_artifact_ref,
        continuation_ref=invocation.session_ref if invocation else None,
    )


class CodexProvider:
    """Provider-contract adapter with an explicit Codex transport dependency."""

    def __init__(self, transport: Callable[[CodexInvocation], Any], session_ref=None,
                 registry_path=SEATS_JSON, model_map=CODEX_MODEL_MAP,
                 supported_efforts=CODEX_REASONING_EFFORTS):
        if not callable(transport):
            raise CodexInvocationError("CodexProvider needs a Codex transport")
        self._transport = transport
        self._session_ref = session_ref
        self._registry_path = registry_path
        self._model_map = model_map
        self._supported_efforts = supported_efforts

    def capabilities(self):
        return capabilities()

    def execute(self, request):
        """Invoke once and normalize without workflow mutation or provider fallback."""
        try:
            invocation = prepare_codex_invocation(
                request,
                session_ref=self._session_ref,
                registry_path=self._registry_path,
                model_map=self._model_map,
                supported_efforts=self._supported_efforts,
            )
        except CodexTransportFailure as exc:
            return _provider_failure(request, exc.code, str(exc),
                                     raw_artifact_ref=exc.raw_artifact_ref)
        except (CodexInvocationError, roster.RegistryError, OSError) as exc:
            return _provider_failure(request, FailureCode.UNAVAILABLE, str(exc))

        try:
            raw = self._transport(invocation)
        except CodexTransportFailure as exc:
            return _provider_failure(request, exc.code, str(exc), invocation,
                                     exc.raw_artifact_ref)
        except TimeoutError as exc:
            return _provider_failure(request, FailureCode.TIMEOUT,
                                     str(exc) or "Codex transport timed out", invocation)
        except Exception as exc:
            return _provider_failure(request, FailureCode.EXECUTOR_PROCESS_FAILURE,
                                     str(exc) or "Codex transport failed", invocation)

        try:
            return normalize_codex_result(request, invocation, raw)
        except CodexMalformedResult as exc:
            artifact = None
            if isinstance(raw, Mapping):
                candidate = raw.get("raw_artifact_ref")
                if isinstance(candidate, str) and candidate.strip():
                    artifact = candidate
            return _provider_failure(request, FailureCode.MALFORMED_RESULT,
                                     str(exc), invocation, artifact)
