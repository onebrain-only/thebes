"""Claude-specific preparation for the current external Agent-tool wake.

The repository does not own a callable Claude transport. The native ``Agent``
tool remains a controller capability. This module validates one already-built
``ExecutionRequest``, resolves current Claude binding defaults, renders the one
canonical Product executor brief through ``agent.execution.brief``, and hands an
immutable wake description to an injected controller transport exactly once,
then normalizes only supported transport evidence into ``ExecutionResult``.

The prompt an executor receives is Product work only: control-plane mechanics
stay with Thebes and have no rendering path into this prompt.
"""

from dataclasses import dataclass, replace
import json
import os
import subprocess
from typing import Any, Callable, Mapping, Optional, Tuple

from agent.execution.provider import (
    ExecutionFeature,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ExecutionTarget,
    EvidenceClaim,
    ChangedFileClaim,
    EscalationRequirement,
    Failure,
    FailureCode,
    ModelIntent,
    ProviderCapabilities,
    ReasoningEffort,
    ReportedEnvironment,
    ReturnContract,
    TestClaim,
    TestStatus,
    ValidationTarget,
    Workspace,
)
from agent.execution.brief import render_executor_brief
from agent.state import roster


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEATS_JSON = os.path.join(ROOT, "agent", "state", "registry", "seats.json")
BINDINGS_DIR = os.path.join(ROOT, ".claude", "bindings")
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")


class ClaudeWakeError(ValueError):
    pass


class ClaudeTransportFailure(Exception):
    """A classified failure reported by the external controller transport."""

    code = FailureCode.EXECUTOR_PROCESS_FAILURE

    def __init__(self, message, raw_artifact_ref=None):
        super().__init__(message)
        self.raw_artifact_ref = raw_artifact_ref


class ClaudeUnavailable(ClaudeTransportFailure):
    code = FailureCode.UNAVAILABLE


class ClaudeAuthenticationFailure(ClaudeTransportFailure):
    code = FailureCode.AUTHENTICATION_FAILURE


class ClaudeUnsupportedModel(ClaudeTransportFailure):
    code = FailureCode.UNSUPPORTED_MODEL


class ClaudeUnsupportedEffort(ClaudeTransportFailure):
    code = FailureCode.UNSUPPORTED_EFFORT


class ClaudeUnsupportedCapability(ClaudeTransportFailure):
    code = FailureCode.UNSUPPORTED_CAPABILITY


class ClaudeExecutorProcessFailure(ClaudeTransportFailure):
    code = FailureCode.EXECUTOR_PROCESS_FAILURE


class ClaudeTimeout(ClaudeTransportFailure):
    code = FailureCode.TIMEOUT


class ClaudeMalformedResult(ClaudeTransportFailure):
    code = FailureCode.MALFORMED_RESULT


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
    timeout_seconds: int
    session_ref: Optional[str] = None
    session_id: Optional[str] = None
    approved_permissions: Tuple[str, ...] = ()


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
            "binding model and effort remain authoritative",
            "transport evidence is normalized without workflow side effects",
            "Product execution is foreground-only; observable async execution is unsupported",
        ),
    )


def prepare_claude_wake(request, session_ref=None, registry_path=SEATS_JSON,
                        bindings_dir=BINDINGS_DIR, agents_dir=AGENTS_DIR):
    """Validate and preserve one request without invoking external transport."""
    if not isinstance(request, ExecutionRequest):
        raise ClaudeWakeError("Claude wake requires the provider-neutral ExecutionRequest")
    if not any("launch another" in action.lower() for action in request.prohibited_actions):
        raise ClaudeWakeError("Claude Product request must prohibit executor delegation")

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
    if binding["model"] not in ("opus", "sonnet"):
        raise ClaudeUnsupportedModel(
            "Claude configuration model %r is unsupported" % binding["model"]
        )
    if binding["effort"] not in tuple(effort.value for effort in ReasoningEffort):
        raise ClaudeUnsupportedEffort(
            "Claude configuration effort %r is unsupported" % binding["effort"]
        )

    declared = capabilities()
    missing_features = request.required_execution_features - declared.execution_features
    if missing_features:
        raise ClaudeUnsupportedCapability(
            "Claude wake lacks execution feature(s): %s"
            % ", ".join(sorted(feature.value for feature in missing_features))
        )

    # The prompt is the one canonical Product brief, rendered by
    # ``agent.execution.brief`` from this request and nothing else. The native
    # Agent tool resolves model/effort from the generated definition; neutral
    # intent fields do not override those binding defaults in this slice.
    prompt = render_executor_brief(request)
    arguments = (("subagent_type", request.seat_id), ("prompt", prompt))
    return ClaudeWake(
        native_tool="Agent",
        native_arguments=arguments,
        subagent_type=request.seat_id,
        prompt=prompt,
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
        timeout_seconds=request.timeout_seconds,
        session_ref=session_ref,
    )


def _exact_permissions(approved_permissions):
    if isinstance(approved_permissions, str):
        approved_permissions = (approved_permissions,)
    if (not isinstance(approved_permissions, (tuple, list)) or not approved_permissions
            or len(set(approved_permissions)) != len(approved_permissions)
            or any(not isinstance(item, str) or not item.strip() or "*" in item
                   for item in approved_permissions)):
        raise ClaudeWakeError("Claude continuation requires exact permission(s)")
    return tuple(approved_permissions)


def prepare_claude_continuation_wake(request, session_ref, approved_permissions,
                                     registry_path=SEATS_JSON,
                                     bindings_dir=BINDINGS_DIR, agents_dir=AGENTS_DIR):
    """Prepare one same-session resume after an exact, durable CEO approval."""
    permissions = _exact_permissions(approved_permissions)
    if session_ref is not None and (not isinstance(session_ref, str) or not session_ref.strip()):
        raise ClaudeWakeError("Claude continuation requires one exact session and permission")
    wake = prepare_claude_wake(request, session_ref=session_ref,
                               registry_path=registry_path, bindings_dir=bindings_dir,
                               agents_dir=agents_dir)
    return replace(
        wake,
        prompt=("%s\n## Newly available capability\n"
                "These tool capabilities are now available to you for this work item: %s.\n"
                "Continue the existing task and only the preserved work item; do not start a new task, "
                "replay history, or change scope.\n"
                % (wake.prompt, ", ".join(permissions))),
        approved_permissions=permissions,
    )


def prepare_claude_authorized_wake(request, session_id, approved_permissions,
                                   registry_path=SEATS_JSON,
                                   bindings_dir=BINDINGS_DIR, agents_dir=AGENTS_DIR):
    """Prepare one new, foreground Claude session with exact CEO-granted tools.

    This is intentionally distinct from a continuation: the caller supplies a
    fresh native session id, so the original immutable Product objective is
    retained and no historical Claude session is resumed.
    """
    permissions = _exact_permissions(approved_permissions)
    if session_id is not None and (not isinstance(session_id, str) or not session_id.strip()):
        raise ClaudeWakeError("authorized Claude execution session id must be non-empty text")
    wake = prepare_claude_wake(
        request, registry_path=registry_path, bindings_dir=bindings_dir,
        agents_dir=agents_dir,
    )
    return replace(wake, session_id=session_id, approved_permissions=permissions)


# ---------------------------------------------------------------- standing tools
#
# The Product executor's ordinary working tools. Live operation established why
# this has to exist: the CLI runs with `--permission-mode dontAsk`, so WITHOUT a
# standing set every single tool call — every read, every edit, every shell
# command — was denied and became a separate Thebes approval plus a full resume
# invocation. One work item burned four invocations on catalogue reads and a
# file write. That is not a governance control, it is a tax, and it made routine
# operation impossible while protecting nothing: each of those denials was
# approved anyway, one round-trip later.
#
# What this deliberately does NOT contain is the whole point of the list.
STANDING_PRODUCT_EXECUTOR_TOOLS = (
    "Read",
    "Bash",
    "Edit",
    "Write",
    # READ-ONLY by the environment authority that authorizes it. The tool itself
    # can mutate, so the read-only limit is enforced where it belongs — in the
    # operational_context the CEO granted and in the brief the executor reads —
    # not by hoping a tool name is safe.
    "mcp__claude_ai_Supabase__execute_sql",
)

# Never standing, at any time, for any work item. A production mutation is a
# separate CEO act every time it happens; putting one of these in the standing
# set would silently convert "the CEO approves each migration" into "the executor
# may apply migrations", which is the single boundary Product execution has held
# since Phase 2.
NEVER_STANDING = (
    "mcp__claude_ai_Supabase__apply_migration",
    "mcp__claude_ai_Supabase__deploy_edge_function",
    "mcp__claude_ai_Supabase__create_branch",
    "mcp__claude_ai_Supabase__merge_branch",
    "mcp__claude_ai_Supabase__delete_branch",
    "mcp__claude_ai_Supabase__reset_branch",
    "mcp__claude_ai_Supabase__pause_project",
    "mcp__claude_ai_Supabase__restore_project",
)

assert not set(STANDING_PRODUCT_EXECUTOR_TOOLS) & set(NEVER_STANDING), (
    "a production-mutating tool reached the standing executor set")


def standing_tools():
    """The executor's ordinary tools, verified against the exclusion list.

    Checked at call time as well as import time: this is the list that decides
    what a Product executor can do without asking, and a future edit that adds
    `apply_migration` to it should fail loudly rather than ship quietly.
    """
    forbidden = set(STANDING_PRODUCT_EXECUTOR_TOOLS) & set(NEVER_STANDING)
    if forbidden:
        raise ClaudeWakeError(
            "standing executor tools may never include %s" % ", ".join(sorted(forbidden)))
    return STANDING_PRODUCT_EXECUTOR_TOOLS


def developer_dir():
    """The Command Line Tools path, when it is present and usable.

    Live operation hit a machine whose full Xcode licence was not accepted, which
    makes `/usr/bin/python3` — and therefore every Thebes tool, git helper and
    build command an executor runs — fail with a licence error. The Command Line
    Tools carry no such gate.

    Process-scoped on purpose. Thebes sets this for the subprocesses it launches
    and changes nothing about the machine: accepting a licence on the CEO's
    behalf is not Thebes's to do, and a machine-wide change to fix one
    subprocess would be a much larger act than the problem needs. Returns None
    when the path is absent, in which case the inherited environment stands.
    """
    path = "/Library/Developer/CommandLineTools"
    return path if os.path.isdir(path) else None


def executor_environment(environ=None, developer_dir_path=None):
    """The environment a Product executor subprocess runs in.

    Inherits the caller's environment and pins only what has been shown to break
    without pinning. It adds no secret, no credential and no Thebes identifier —
    an executor's environment is not a side channel for control-plane state.
    """
    base = dict(os.environ if environ is None else environ)
    resolved = developer_dir_path if developer_dir_path is not None else developer_dir()
    if resolved:
        base["DEVELOPER_DIR"] = resolved
    return base


class ClaudeCliTransport:
    """Direct local transport for the installed Claude Code CLI.

    This is intentionally a narrow Phase-2 bridge.  ``--permission-prompts
    none`` means a native Claude permission request is denied and returned as
    structured ``needs_input`` evidence; it is never approved by Thebes or the
    controller.  The CLI's working directory and timeout are transport-enforced.
    """

    def __init__(self, binary="claude", runner=subprocess.run):
        self._binary = binary
        self._runner = runner

    def command(self, wake):
        command = (
            self._binary,
            "--print",
            "--output-format", "json",
            "--permission-mode", "dontAsk",
            "--permission-prompts", "none",
            "--model", wake.model,
            "--effort", wake.effort,
        )
        if wake.session_ref and wake.session_id:
            raise ClaudeWakeError("Claude wake cannot resume and create a session together")
        if wake.session_ref:
            command += ("--resume", wake.session_ref)
        if wake.session_id:
            command += ("--session-id", wake.session_id)
        # The standing working set, plus any invocation-scoped grant the CEO
        # approved for THIS boundary. The scoped grants are additive and still
        # exact: a standing Read does not imply a standing apply_migration, and
        # nothing here can widen the never-standing list.
        allowed = list(standing_tools())
        for permission in wake.approved_permissions or ():
            if permission not in allowed:
                allowed.append(permission)
        if allowed:
            # Claude CLI parses this option as a variadic list.  Keeping it as
            # one comma-separated argument prevents the final prompt from
            # being swallowed as another allowed tool.
            command += ("--allowedTools", ",".join(allowed))
            # Current Claude CLI parses --allowedTools as variadic.  The
            # separator keeps the immutable Product prompt from being consumed
            # as a tool name.
            command += ("--",)
        return command + (wake.prompt,)

    def __call__(self, wake):
        try:
            completed = self._runner(
                self.command(wake), capture_output=True, text=True,
                timeout=wake.timeout_seconds, check=False,
                cwd=wake.workspace.working_directory,
                env=executor_environment(),
            )
        except FileNotFoundError as exc:
            raise ClaudeUnavailable("Claude CLI is unavailable: %s" % exc)
        except subprocess.TimeoutExpired as exc:
            raise ClaudeTimeout("Claude CLI timed out: %s" % exc)
        except OSError as exc:
            raise ClaudeExecutorProcessFailure("Claude CLI could not start: %s" % exc)
        if completed.returncode:
            diagnostic = (completed.stderr or completed.stdout or
                          "Claude CLI exited %d" % completed.returncode)
            raise ClaudeExecutorProcessFailure(diagnostic.strip())
        return _normalize_cli_output(completed.stdout)


def _normalize_cli_output(raw):
    """Map only documented CLI result fields into the existing result contract."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ClaudeMalformedResult("Claude CLI returned invalid JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise ClaudeMalformedResult("Claude CLI result must be an object")
    summary = payload.get("result")
    if not isinstance(summary, str) or not summary.strip():
        summary = "Claude CLI returned no result text"
    # The local CLI can acknowledge dispatch with a human-facing background
    # task id while providing no provider-readable completion handle.  That is
    # neither completion nor a controllable async execution: fail closed until
    # the provider exposes a poll/cancel-capable handle contract.
    if "running in the background (task `" in summary:
        raise ClaudeExecutorProcessFailure(
            "Claude CLI acknowledged an unobservable background task; no terminal result exists"
        )
    session_id = payload.get("session_id")
    continuation = session_id if isinstance(session_id, str) and session_id else None
    artifact = "claude-session:%s" % session_id if continuation else None
    denials = payload.get("permission_denials") or []
    if denials:
        detail = "; ".join(str(item) for item in denials)
        return {
            "status": "needs_input",
            "summary": summary,
            "escalation": {
                "reason": "Claude Code native permission required: %s" % detail,
                "required_authority": "CEO",
            },
            "continuation_ref": continuation,
            "raw_artifact_ref": artifact,
        }
    if payload.get("is_error") is True:
        return {
            "status": "execution_failed",
            "summary": summary,
            "failure_message": summary,
            "continuation_ref": continuation,
            "raw_artifact_ref": artifact,
        }
    return {
        "status": "completed",
        "summary": summary,
        "continuation_ref": continuation,
        "raw_artifact_ref": artifact,
    }


_RESULT_KEYS = frozenset({
    "status", "summary", "evidence", "changed_files", "tests", "escalation",
    "failure_message", "duration_seconds", "continuation_ref", "raw_artifact_ref",
})


def _optional_string(value, field):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ClaudeMalformedResult("%s must be a non-empty string or null" % field)
    return value


def _claims(rows, required, optional, build, field):
    if rows is None:
        return ()
    if not isinstance(rows, (list, tuple)):
        raise ClaudeMalformedResult("%s must be a list" % field)
    claims = []
    allowed = set(required) | set(optional)
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) - allowed:
            raise ClaudeMalformedResult("%s[%d] has an invalid shape" % (field, index))
        if any(not isinstance(row.get(key), str) or not row[key].strip()
               for key in required):
            raise ClaudeMalformedResult("%s[%d] is missing required text" % (field, index))
        try:
            claims.append(build(row))
        except (TypeError, ValueError) as exc:
            raise ClaudeMalformedResult("%s[%d]: %s" % (field, index, exc))
    return tuple(claims)


def _evidence_claim(row):
    summary = _optional_string(row.get("summary"), "evidence summary")
    return EvidenceClaim(row["kind"], row["reference"], summary)


def _changed_file_claim(row):
    change_kind = _optional_string(row.get("change_kind"), "change_kind")
    return ChangedFileClaim(row["path"], change_kind)


def _test_claim(row):
    evidence_ref = _optional_string(row.get("evidence_ref"), "test evidence_ref")
    exit_code = row.get("exit_code")
    if exit_code is not None and (not isinstance(exit_code, int)
                                  or isinstance(exit_code, bool)):
        raise ClaudeMalformedResult("test exit_code must be an integer or null")
    return TestClaim(
        row["command"], TestStatus(row["status"]), evidence_ref, exit_code
    )


def normalize_claude_result(request, wake, raw):
    """Normalize only explicit Claude transport evidence; never infer workflow state."""
    if isinstance(raw, str):
        if not raw.strip():
            raise ClaudeMalformedResult("Claude returned an empty result")
        payload = {"status": "completed", "summary": raw}
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        raise ClaudeMalformedResult("Claude result must be text or a result mapping")

    unknown = set(payload) - _RESULT_KEYS
    if unknown:
        raise ClaudeMalformedResult(
            "Claude result has unknown field(s): %s" % ", ".join(sorted(unknown))
        )
    status_value = payload.get("status")
    try:
        status = ExecutionStatus(status_value)
    except (TypeError, ValueError):
        raise ClaudeMalformedResult("Claude result has invalid status %r" % status_value)
    if status == ExecutionStatus.PROVIDER_FAILED:
        raise ClaudeMalformedResult("transport results cannot self-declare provider_failed")
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ClaudeMalformedResult("Claude result requires a non-empty summary")

    evidence = _claims(
        payload.get("evidence"), ("kind", "reference"), ("summary",),
        _evidence_claim,
        "evidence",
    )
    changed_files = _claims(
        payload.get("changed_files"), ("path",), ("change_kind",),
        _changed_file_claim,
        "changed_files",
    )
    tests = _claims(
        payload.get("tests"), ("command", "status"),
        ("evidence_ref", "exit_code"),
        _test_claim,
        "tests",
    )

    escalation = payload.get("escalation")
    if escalation is not None:
        if (not isinstance(escalation, Mapping)
                or set(escalation) - {"reason", "required_authority",
                                      "required_capability"}
                or not isinstance(escalation.get("reason"), str)
                or not escalation["reason"].strip()):
            raise ClaudeMalformedResult("escalation has an invalid shape")
        required_authority = _optional_string(
            escalation.get("required_authority"), "escalation required_authority"
        )
        required_capability = _optional_string(
            escalation.get("required_capability"), "escalation required_capability"
        )
        escalation = EscalationRequirement(
            escalation["reason"], required_authority, required_capability
        )
    if status == ExecutionStatus.NEEDS_INPUT and escalation is None:
        raise ClaudeMalformedResult("needs_input requires a bounded escalation reason")
    if status != ExecutionStatus.NEEDS_INPUT and escalation is not None:
        raise ClaudeMalformedResult("escalation is valid only for needs_input")

    failure_message = payload.get("failure_message")
    if status == ExecutionStatus.EXECUTION_FAILED:
        if not isinstance(failure_message, str) or not failure_message.strip():
            raise ClaudeMalformedResult("execution_failed requires failure_message")
        failure = Failure(FailureCode.EXECUTION_FAILURE, failure_message)
    else:
        if failure_message is not None:
            raise ClaudeMalformedResult("failure_message is valid only for execution_failed")
        failure = None

    duration = payload.get("duration_seconds")
    if (duration is not None
            and (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                 or duration < 0)):
        raise ClaudeMalformedResult("duration_seconds must be a non-negative number")
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
        provider_id="claude-code",
        resolved_model_ref=wake.model,
        resolved_effort_ref=wake.effort,
        duration_seconds=duration,
        raw_artifact_ref=artifact,
        continuation_ref=continuation or wake.session_ref,
    )


def _provider_failure(request, code, message, wake=None, raw_artifact_ref=None):
    return ExecutionResult(
        invocation_id=request.invocation_id,
        status=ExecutionStatus.PROVIDER_FAILED,
        summary=message,
        failure=Failure(code, message),
        provider_id="claude-code",
        resolved_model_ref=wake.model if wake else None,
        resolved_effort_ref=wake.effort if wake else None,
        raw_artifact_ref=raw_artifact_ref,
        continuation_ref=wake.session_ref if wake else None,
    )


class ClaudeProvider:
    """Two-operation provider seam using a controller-supplied native transport."""

    def __init__(self, transport: Callable[[ClaudeWake], Any], session_ref=None,
                 session_id=None, approved_permission=None, approved_permissions=None,
                 authorized_execution=False,
                 registry_path=SEATS_JSON, bindings_dir=BINDINGS_DIR,
                 agents_dir=AGENTS_DIR):
        if not callable(transport):
            raise ClaudeWakeError(
                "ClaudeProvider needs the controller-native Agent transport"
            )
        self._transport = transport
        self._session_ref = session_ref
        self._session_id = session_id
        self._authorized_execution = authorized_execution
        if session_ref is not None and session_id is not None:
            raise ClaudeWakeError("ClaudeProvider cannot resume and create a session together")
        if approved_permission is not None and approved_permissions is not None:
            raise ClaudeWakeError("use approved_permission or approved_permissions, not both")
        supplied = approved_permissions if approved_permissions is not None else approved_permission
        self._approved_permissions = None if supplied is None else _exact_permissions(supplied)
        if authorized_execution and self._approved_permissions is None:
            raise ClaudeWakeError("authorized Claude execution requires exact permission(s)")
        if authorized_execution and session_ref is not None:
            raise ClaudeWakeError("authorized Claude execution cannot resume a session")
        self._registry_path = registry_path
        self._bindings_dir = bindings_dir
        self._agents_dir = agents_dir

    def capabilities(self):
        return capabilities()

    @property
    def approved_permissions(self):
        """Exact continuation permissions, exposed only for core parity checking."""
        return self._approved_permissions or ()

    def execute(self, request):
        """Invoke once and normalize without retry, fallback, or workflow mutation."""
        try:
            if self._approved_permissions is None:
                wake = prepare_claude_wake(
                    request, session_ref=self._session_ref,
                    registry_path=self._registry_path, bindings_dir=self._bindings_dir,
                    agents_dir=self._agents_dir,
                )
            elif not self._authorized_execution:
                wake = prepare_claude_continuation_wake(
                    request, self._session_ref, self._approved_permissions,
                    registry_path=self._registry_path, bindings_dir=self._bindings_dir,
                    agents_dir=self._agents_dir,
                )
            else:
                wake = prepare_claude_authorized_wake(
                    request, self._session_id, self._approved_permissions,
                    registry_path=self._registry_path, bindings_dir=self._bindings_dir,
                    agents_dir=self._agents_dir,
                )
        except ClaudeTransportFailure as exc:
            return _provider_failure(request, exc.code, str(exc),
                                     raw_artifact_ref=exc.raw_artifact_ref)
        except (ClaudeWakeError, roster.RegistryError, OSError) as exc:
            return _provider_failure(request, FailureCode.UNAVAILABLE, str(exc))

        try:
            raw = self._transport(wake)
        except ClaudeTransportFailure as exc:
            return _provider_failure(request, exc.code, str(exc), wake,
                                     exc.raw_artifact_ref)
        except TimeoutError as exc:
            return _provider_failure(request, FailureCode.TIMEOUT,
                                     str(exc) or "Claude transport timed out", wake)
        except Exception as exc:
            return _provider_failure(request, FailureCode.EXECUTOR_PROCESS_FAILURE,
                                     str(exc) or "Claude transport failed", wake)

        try:
            return normalize_claude_result(request, wake, raw)
        except ClaudeMalformedResult as exc:
            artifact = None
            if isinstance(raw, Mapping):
                candidate = raw.get("raw_artifact_ref")
                if isinstance(candidate, str) and candidate.strip():
                    artifact = candidate
            return _provider_failure(
                request, FailureCode.MALFORMED_RESULT, str(exc), wake, artifact
            )
