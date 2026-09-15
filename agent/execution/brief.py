"""The one canonical Product executor brief and its control-plane firewall.

Thebes owns orchestration; a Product executor owns Product work. This module is
the single place where an already-authorized ``ExecutionRequest`` becomes the
text an executor reads, so there is exactly one answer to "what does the
executor see".

Two invariants, both small:

1. **Structural.** ``render_executor_brief`` reads only ``PRODUCT_BRIEF_FIELDS``.
   Control-plane fields of the request — invocation id, seat allocation, claim,
   execution lease, operating mode and its revision, provider/model/effort
   intent — have no rendering path at all, so they cannot leak by accident.
2. **Textual.** The caller-authored text inside those fields is checked before
   dispatch. The *instruction surface* (objective, context, surfaces,
   validation, return contract) may not carry a control-plane concept, and no
   executor-visible field of any kind may carry a Thebes internal identifier.

``prohibited_actions`` is deliberately exempt from the concept check: telling an
executor not to transition Jira is a Product constraint, not an orchestration
instruction. It is still checked for internal identifiers, which is exactly the
KAN-186 defect — a prohibition that named ``execute_approved_claude_continuation``
put the continuation driver's name into the executor's prompt.
"""

import re


# Every request field an executor may ever see. Anything absent here is
# control-plane by construction and has no path into a brief.
PRODUCT_BRIEF_FIELDS = (
    "work_item_id",
    "required_capability",
    "execution_kind",
    "objective",
    "role_contract_ref",
    "context_refs",
    "workspace",
    "allowed_surfaces",
    "prohibited_actions",
    "required_execution_features",
    "timeout_seconds",
    "reported_environment",
    "primary_target",
    "validation_targets",
    "return_contract",
)

# Request fields that exist for Thebes and are never rendered.
CONTROL_PLANE_FIELDS = (
    "invocation_id",
    "seat_id",
    "claim_ref",
    "execution_lease_id",
    "operating_mode",
    "operating_mode_revision",
    "model_intent",
    "reasoning_effort",
    "review_context_ref",
)

# Thebes internal names. These are mechanism, not English: an executor-visible
# string containing one is a leak wherever it appears, including a prohibition.
CONTROL_PLANE_TOKENS = (
    "execute_approved_claude_continuation",
    "build_prepared_continuation_request",
    "prepare_replacement_execution",
    "retire_execution_session",
    "prepare_claude_wake",
    "prepare_claude_continuation_wake",
    "prepare_claude_authorized_wake",
    "prepare_codex_invocation",
    "execute_product_wake",
    "select_provider",
    "assert_execution_permitted",
    "open_execution_lease",
    "close_execution_lease",
    "record_execution_receipt",
    "ClaudeCliTransport",
    "CodexCliTransport",
    "ClaudeProvider(",
    "CodexProvider(",
    "agent.execution.wake",
    "agent.execution.brief",
    "agent.controller",
    # Phase 3 created a second control-plane surface and this list did not know
    # it existed. A Listener intent is an orchestration act: an executor told to
    # submit one is orchestrating its own execution by a new route.
    "agent.listener",
    "EXECUTE_WORK_ITEM",
    "DECISION_RESPONSE",
    "claude --resume",
    "claude -p",
    "--session-id",
    "--allowedTools",
    "subagent_type",
    "execution_lease_id",
    "claim_ref",
)

# Concepts an executor may not be instructed to perform. Phrase-level, not a
# vocabulary blocklist: the words "provider" or "lease" alone are harmless.
CONTROL_PLANE_CONCEPTS = (
    ("executor_self_invocation", (
        r"\b(?:launch|start|spawn|invoke|run|open|wake)\s+(?:a|an|another|the|yourself|one)?\s*"
        r"(?:new\s+|second\s+|additional\s+)?(?:claude|codex|executor|subagent|agent\s+tool)\b",
        r"\bresume\s+yourself\b",
        r"\bre-?invoke\s+yourself\b",
        r"\borchestrate\s+your\s+own\b",
    )),
    ("continuation_driver", (
        r"\b(?:run|invoke|call|trigger|drive)\s+(?:the\s+)?continuation\b",
        r"\bcontinuation\s+(?:driver|gate|preparation|approval)\b",
        r"\b(?:approve|grant)\s+(?:your\s+own\s+|the\s+)?(?:native\s+)?permission",
    )),
    ("lease_or_claim_orchestration", (
        r"\b(?:open|close|renew|extend|reopen|mutate|manage)\s+(?:an?|the|your|its)?\s*"
        r"(?:execution\s+)?lease\b",
        r"\b(?:claim|re-?claim|release|reassign|steal)\s+(?:the|this|another|a|your)?\s*"
        r"(?:work\s*item|ticket|task|ownership)\b",
        r"\btake\s+ownership\s+of\b",
    )),
    ("provider_selection", (
        r"\b(?:select|choose|pick|switch|change|swap|override|fall\s*back(?:\s+to)?)\s+"
        r"(?:to\s+)?(?:a|an|another|the|your)?\s*(?:execution\s+)?provider\b",
        r"\bprovider\s+(?:selection|registry|override|routing|fallback)\b",
        r"\b(?:retry|rerun)\s+(?:this|the\s+work)?\s*(?:with|on)\s+(?:another|a\s+different)\s+"
        r"(?:provider|model|executor)\b",
    )),
    ("controller_bootstrap", (
        r"\bpython3?\s+-m\s+agent\b",
        r"\bfrom\s+agent\.(?:execution|controller|state|listener)\b",
        r"\bimport\s+agent\.(?:execution|controller|state|listener)\b",
        r"\b(?:run|execute|start)\s+(?:the\s+)?(?:thebes|controller)\s+(?:bootstrap|entry|loop)\b",
    )),
    ("session_mechanics", (
        r"\b(?:create|allocate|resume|retire|replace)\s+(?:a|an|the|your|one)?\s*"
        r"(?:new\s+|native\s+|claude\s+|existing\s+)?session\b",
        r"\bsession[\s_-]?(?:id|ref|handle)\b",
    )),
    # The Listener is the front door, which makes it a control-plane surface an
    # executor must never be pointed at. Phrase-level like its neighbours: the
    # word "intent" alone is ordinary English and stays harmless.
    ("listener_intake", (
        r"\b(?:submit|send|post|deliver|queue|file|raise)\s+(?:an?|the|your|one)?\s*"
        r"(?:new\s+|follow-?up\s+)?intent\b",
        r"\b(?:the\s+|thebes\s+)?listener\b",
        r"\bintent\s+(?:envelope|contract|id|type)\b",
        r"\bidempotency[\s_-]?key\b",
        r"\b/intents\b",
        r"\b127\.0\.0\.1:\d+\b",
        r"\blocalhost:\d+\b",
    )),
    ("jira_orchestration", (
        r"\b(?:transition|move|advance|progress|close|reopen)\s+(?:the\s+|this\s+|its\s+)?"
        r"(?:jira|ticket|issue|work\s*item)\b",
        r"\bjira\s+(?:lifecycle|transition|workflow)\b",
        r"\b(?:select|pick|choose|start)\s+(?:the\s+)?next\s+(?:work\s*item|ticket|task)\b",
        r"\b(?:appoint|assign|choose)\s+(?:a\s+|the\s+)?(?:peer\s+)?reviewer\b",
        r"\b(?:choose|select|set)\s+(?:a\s+|the\s+)?validation\s+route\b",
    )),
)

_COMPILED_CONCEPTS = tuple(
    (category, tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns))
    for category, patterns in CONTROL_PLANE_CONCEPTS
)


class ExecutorBriefViolation(ValueError):
    """One executor-visible field carried control-plane instruction."""

    def __init__(self, category, field, evidence):
        super().__init__(
            "executor brief field %r carries control-plane instruction (%s): %r"
            % (field, category, evidence)
        )
        self.category = category
        self.field = field
        self.evidence = evidence


def instruction_surface(request):
    """Executor-visible text that instructs; prohibitions are not here."""
    workspace = request.workspace
    fields = [
        ("objective", request.objective),
        ("role_contract_ref", request.role_contract_ref),
        ("workspace.repository_root", workspace.repository_root),
        ("workspace.working_directory", workspace.working_directory),
        ("workspace.worktree_path", workspace.worktree_path),
        ("return_contract.return_to", request.return_contract.return_to),
    ]
    fields += [("context_refs[%d]" % i, v) for i, v in enumerate(request.context_refs)]
    fields += [("allowed_surfaces[%d]" % i, v) for i, v in enumerate(request.allowed_surfaces)]
    fields += [("return_contract.required_evidence[%d]" % i, v)
               for i, v in enumerate(request.return_contract.required_evidence)]
    fields += [("return_contract.required_sections[%d]" % i, v)
               for i, v in enumerate(request.return_contract.required_sections)]
    for index, target in enumerate(request.validation_targets):
        fields.append(("validation_targets[%d].target_id" % index, target.target_id))
        fields.append(("validation_targets[%d].surface" % index, target.surface))
    return tuple((name, value) for name, value in fields if isinstance(value, str) and value)


def _prohibition_surface(request):
    return tuple(("prohibited_actions[%d]" % index, value)
                 for index, value in enumerate(request.prohibited_actions)
                 if isinstance(value, str) and value)


def assert_no_control_plane_identifier(text, field):
    """Refuse a Thebes internal name anywhere an executor can read it."""
    lowered = text.lower()
    for token in CONTROL_PLANE_TOKENS:
        if token.lower() in lowered:
            raise ExecutorBriefViolation("control_plane_identifier", field, token)


def assert_no_control_plane_concept(text, field):
    """Refuse an instruction to perform an orchestration act."""
    for category, patterns in _COMPILED_CONCEPTS:
        for pattern in patterns:
            found = pattern.search(text)
            if found:
                raise ExecutorBriefViolation(category, field, found.group(0))


def assert_product_scoped(request):
    """The control-plane firewall, run before any Product executor dispatch."""
    for field, text in instruction_surface(request):
        assert_no_control_plane_identifier(text, field)
        assert_no_control_plane_concept(text, field)
    for field, text in _prohibition_surface(request):
        assert_no_control_plane_identifier(text, field)
    return request


def render_executor_brief(request):
    """Build the one canonical Product-only brief from an authorized request.

    Only ``PRODUCT_BRIEF_FIELDS`` are read. The workspace, timeout and mutation
    mode are enforced by the transport that launches the executor; surfaces,
    environment, validation and return shape cannot be mechanically enforced and
    remain explicit executor instructions.
    """
    assert_product_scoped(request)
    workspace = request.workspace
    environment = request.reported_environment
    target = request.primary_target
    lines = (
        "# Thebes Product Execution Brief",
        "",
        "## Work item",
        "- Work item ID: %s" % request.work_item_id,
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
        "- Work only inside the declared surfaces below.",
        *_listed(request.allowed_surfaces),
        "",
        "## Prohibited actions — executor instruction",
        *_listed(request.prohibited_actions),
        "",
        "## Available capabilities and budget",
        "- Available execution features: %s" % _features(request),
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
        "- Return evidence for the work above and stop; Thebes verifies it and",
        "  decides what happens next.",
    )
    brief = "\n".join(lines) + "\n"
    assert_no_control_plane_identifier(brief, "rendered_brief")
    return brief


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
