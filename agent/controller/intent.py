"""Resolve one existing Jira work item into the inputs an ExecutionRequest needs.

This is derivation, not a second store and not a second prompt builder. Every
field comes from a source that already owns it:

    Jira              the Product work definition — summary, description, AC
    Persistent State  capability, surfaces, characteristics, validation route,
                      operational context and its environment authority
    Registry          which repository a Product project lives in
    Policy            the constants Thebes itself owns (timeouts, effort intent,
                      return-contract shape, execution features)

Nothing here asserts a task characteristic, chooses a validation route, or
infers a safety fact from prose. Those stay where `policy.py` and `store.py`
already put them: an actor asserts a typed characteristic, and only policy turns
characteristics into a route. A Jira description that *says* "security" changes
nothing.

When canonical state cannot answer, this module stops with a bounded, named
governance input rather than inventing the missing fact. The output feeds the
existing `_build_request` → `ExecutionRequest` → `agent.execution.brief` path
unchanged, so the executor-brief firewall still runs on everything derived here.
"""

import os
import re

from agent.execution.brief import ExecutorBriefViolation, assert_no_control_plane_concept
from agent.state import policy, worktrees


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRODUCTS_DIR = os.path.join(ROOT, "agent", "state", "registry", "products")

# Thebes-owned execution defaults. The profile's `model` and `reasoning_effort`
# are deliberately still null in canonical state (README: "no value is
# fabricated for them"), so the controller supplies its own declared default
# rather than pretending the profile decided.
DEFAULT_MODEL_INTENT = "balanced"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_TIMEOUT_SECONDS = 900
REQUIRED_EVIDENCE = ("changed files", "test output")
REQUIRED_SECTIONS = ("RESULT", "EVIDENCE")

# One bounded objective, not a ticket dump. The acceptance criteria are kept
# whole because they are the completion contract; the narrative around them is
# what gets trimmed.
MAX_NARRATIVE_CHARS = 2000
MAX_CRITERIA_CHARS = 2000
MIN_SUMMARY_CHARS = 8

_CRITERIA_HEADING = re.compile(
    r"^\s*#*\s*(?:\*\*)?\s*(acceptance\s+criteria|acceptance|definition\s+of\s+done|dod)"
    r"\s*(?:\*\*)?\s*:?\s*$",
    re.IGNORECASE)

# Facts an actor asserts and policy consumes. Named here only so the resolver can
# prove it never writes them; it reads characteristics and never infers them.
NEVER_INFERRED = ("schema_change", "money_path", "security_sensitive",
                  "shared_or_contended_surface", "user_visible_runtime")

# Canonical facts a manually supplied brief may never contradict.
SAFETY_FIELDS = ("return_contract.return_to", "validation_targets",
                 "reported_environment", "primary_target",
                 "workspace.repository_root")

DERIVABLE = "DERIVABLE"
CEO_INPUT_REQUIRED = "CEO_INPUT_REQUIRED"


class ExecutionIntentUnresolved(Exception):
    """Canonical state cannot answer; say exactly what is missing and who owns it."""

    def __init__(self, reason, detail, classification=CEO_INPUT_REQUIRED, owner="po"):
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail
        self.classification = classification
        self.owner = owner

    def as_governance_input(self, work_item_id):
        return {"work_item_id": work_item_id, "reason": self.reason,
                "detail": self.detail, "classification": self.classification,
                "resolved_by": self.owner}


# ------------------------------------------------------------------ Jira truth

def _clip(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[...truncated by Thebes; full text stays in Jira]"


def split_description(description):
    """Separate the narrative from the acceptance criteria without rewriting either."""
    lines = (description or "").splitlines()
    for index, line in enumerate(lines):
        if _CRITERIA_HEADING.match(line):
            return ("\n".join(lines[:index]).strip(),
                    "\n".join(lines[index + 1:]).strip())
    return ((description or "").strip(), "")


def derive_objective(work_item_id, issue, dependencies=()):
    """Build one bounded Product objective from Jira issue truth.

    Faithful, not verbatim: the summary and the acceptance criteria are carried
    whole, the narrative is clipped, and nothing is invented. A ticket too thin
    to bound is a `po` input, not a guess.
    """
    summary = (issue.get("summary") or "").strip()
    if len(summary) < MIN_SUMMARY_CHARS:
        raise ExecutionIntentUnresolved(
            "objective-not-derivable",
            "Jira %s has no usable summary; a bounded Product objective cannot be "
            "formed from it" % work_item_id)
    narrative, criteria = split_description(issue.get("description"))
    if not narrative and not criteria:
        raise ExecutionIntentUnresolved(
            "objective-not-derivable",
            "Jira %s has a summary but no description or acceptance criteria; the "
            "Product requirement is not stated anywhere Thebes can read"
            % work_item_id)
    sections = ["Deliver exactly %s: %s" % (work_item_id, summary), ""]
    if dependencies:
        sections += ["## Depends on (already satisfied)",
                     ", ".join(dependencies), ""]
    if narrative:
        sections += ["## Product requirement (Jira %s)" % work_item_id,
                     _clip(narrative, MAX_NARRATIVE_CHARS), ""]
    if criteria:
        sections += ["## Acceptance criteria (Jira %s)" % work_item_id,
                     _clip(criteria, MAX_CRITERIA_CHARS), ""]
    sections.append("Implement only this work item, inside the declared surfaces, "
                    "and return the evidence named in the return contract.")
    objective = "\n".join(sections).strip()
    # Jira prose is input, not instruction. A ticket that tells the executor to
    # orchestrate is refused here, at the derivation boundary, where the reason
    # can name the ticket instead of surfacing later as an opaque wake refusal.
    try:
        assert_no_control_plane_concept(objective, "jira_objective")
    except ExecutorBriefViolation as exc:
        raise ExecutionIntentUnresolved(
            "jira-objective-instructs-orchestration",
            "Jira %s instructs the executor to perform a control-plane act (%s: %r); "
            "Thebes owns that step, so the ticket text must be corrected"
            % (work_item_id, exc.category, exc.evidence))
    return objective


# ------------------------------------------------------- Persistent State truth

def derive_capability(work_item_id, task):
    profile = task.get("execution_profile") or {}
    capability = profile.get("required_capability")
    if not capability:
        raise ExecutionIntentUnresolved(
            "required-capability-unresolved",
            "%s has no execution profile capability; one executable work item has "
            "exactly one required_capability and only `po` assigns it" % work_item_id)
    return capability


def derive_surfaces(work_item_id, task):
    surfaces = task.get("surfaces")
    if surfaces is None:
        raise ExecutionIntentUnresolved(
            "surfaces-unassessed",
            "%s has surfaces: null — nobody has assessed the paths. That is not "
            "'no collision'; assessment is a pre-execution factual act" % work_item_id)
    if not isinstance(surfaces, list):
        raise ExecutionIntentUnresolved(
            "surfaces-unassessed",
            "%s has a malformed surfaces record" % work_item_id,
            classification=DERIVABLE, owner="orchestrator")
    return tuple(surfaces)


def derive_validation_route(work_item_id, task):
    """Consume the canonical route. Never recompute it, never default it."""
    profile = task.get("execution_profile") or {}
    route = policy.validation_route_for_profile(profile)
    if route is None:
        raise ExecutionIntentUnresolved(
            "validation-route-unresolved",
            "%s has no recorded task characteristics, so canonical policy has not "
            "produced a validation route; scheduling stays blocked rather than "
            "treating absent evidence as false" % work_item_id)
    stored = profile.get("validation_route")
    if stored and stored != route:
        raise ExecutionIntentUnresolved(
            "validation-route-incoherent",
            "%s stores validation_route %r but its characteristics compute %r"
            % (work_item_id, stored, route),
            classification=DERIVABLE, owner="orchestrator")
    return route


def derive_execution_shape(work_item_id, task):
    """Map the canonical operational intent to execution kind and mutation mode."""
    context = task.get("operational_context") or {}
    intent = context.get("intent")
    if intent is None:
        # An ordinary Development item with no reported condition is implementation.
        return "implementation", "repository_edit"
    if intent == "implementation":
        return "implementation", "repository_edit"
    if intent == "validation":
        return "validation", "read_only"
    if intent == "reproduction_request":
        return "assessment", "read_only"
    if intent == "observed_condition":
        # Investigation first; the fix is authorized once a diagnosis exists.
        return (("implementation", "repository_edit") if context.get("diagnosis")
                else ("assessment", "read_only"))
    raise ExecutionIntentUnresolved(
        "operational-intent-unknown",
        "%s records operational intent %r, which Thebes has no execution shape for"
        % (work_item_id, intent), classification=DERIVABLE, owner="orchestrator")


def derive_environment(work_item_id, task):
    """Use the recorded environment authority; never infer one from prose."""
    context = task.get("operational_context") or {}
    reported = context.get("reported_environment")
    target = context.get("primary_target")
    if not reported or not target:
        raise ExecutionIntentUnresolved(
            "environment-authority-missing",
            "%s has no operational context, so no environment has been reported and "
            "no primary target has been derived from one" % work_item_id)
    if reported.get("locality") == "unknown" or target.get("locality") == "unknown":
        raise ExecutionIntentUnresolved(
            "environment-authority-unresolved",
            "%s reports an unknown environment locality (%s); where this executes is "
            "a governance decision, not something Thebes may pick"
            % (work_item_id, reported.get("environment_ref") or "no reference"))
    return dict(reported), dict(target)


def derive_validation_targets(task, route):
    """Prefer the canonical validation plan; otherwise name the canonical route."""
    context = task.get("operational_context") or {}
    plan = context.get("validation_plan")
    if plan:
        targets = [dict(item, required=True) for item in plan.get("required") or []]
        targets += [dict(item, required=False) for item in plan.get("optional") or []]
        if targets:
            return tuple({"target_id": item["target_id"], "kind": item.get("kind") or "runtime",
                          "required": item["required"], "platform": item.get("platform"),
                          "surface": item.get("surface")} for item in targets)
    return ({"target_id": route, "kind": "review", "required": True},)


# ------------------------------------------------------------- registry truth

def read_project_repository(product_id, project_id, products_dir=PRODUCTS_DIR):
    import json
    path = os.path.join(products_dir, str(product_id), "projects", "%s.json" % project_id)
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ExecutionIntentUnresolved(
            "workspace-unresolved",
            "Product project %s/%s is not readable in the canonical registry: %s"
            % (product_id, project_id, exc), classification=DERIVABLE, owner="orchestrator")
    repository = record.get("repository")
    if not record.get("registered") or not repository:
        raise ExecutionIntentUnresolved(
            "workspace-unresolved",
            "Product project %s/%s declares no registered repository"
            % (product_id, project_id), classification=DERIVABLE, owner="orchestrator")
    return repository


def derive_workspace(work_item_id, task, seat_id, mutation_mode, root=ROOT,
                     products_dir=PRODUCTS_DIR, worktree_root=None):
    product_id, project_id = task.get("product_id"), task.get("project_id")
    if not product_id or not project_id:
        raise ExecutionIntentUnresolved(
            "workspace-unresolved",
            "%s names no Product/Project, so no repository can be resolved for it"
            % work_item_id, classification=DERIVABLE, owner="po")
    repository = read_project_repository(product_id, project_id, products_dir)
    repository_root = os.path.join(root, repository)
    worktree = worktrees.worktree_path(seat_id, work_item_id, root=worktree_root)
    return {"repository_root": repository_root, "working_directory": worktree,
            "worktree_path": worktree, "expected_revision": None,
            "mutation_mode": mutation_mode}


def derive_dependencies(work_item_id, state_store):
    """Name the predecessors this work item sits behind, if any are recorded."""
    try:
        edges = state_store.read_all("dependency")
    except Exception:
        return ()
    return tuple(sorted({
        edge.get("source_work_item") for edge in edges
        if edge.get("relation") == "BLOCKS"
        and edge.get("target_work_item") == work_item_id
        and not edge.get("retired_at") and edge.get("source_work_item")}))


# ------------------------------------------------------------------- resolver

def resolve_execution_intent(work_item_id, task, issue, seat_id, state_store,
                             root=ROOT, products_dir=PRODUCTS_DIR, worktree_root=None):
    """Derive the routine execution brief from canonical sources only.

    Returns the same brief mapping the controller already consumes, so the
    ExecutionRequest, the canonical executor brief and its firewall are unchanged.
    Raises ``ExecutionIntentUnresolved`` with a named reason when a required fact
    is not canonically available.
    """
    capability = derive_capability(work_item_id, task)
    surfaces = derive_surfaces(work_item_id, task)
    route = derive_validation_route(work_item_id, task)
    execution_kind, mutation_mode = derive_execution_shape(work_item_id, task)
    reported, target = derive_environment(work_item_id, task)
    workspace = derive_workspace(work_item_id, task, seat_id, mutation_mode, root,
                                 products_dir, worktree_root)
    objective = derive_objective(work_item_id, issue,
                                 derive_dependencies(work_item_id, state_store))
    features = ["repository_read", "shell"]
    if mutation_mode == "repository_edit":
        features.append("repository_edit")
    return {
        "execution_kind": execution_kind,
        "objective": objective,
        "context_refs": list(_context_refs(task)),
        "workspace": workspace,
        "reported_environment": reported,
        "primary_target": target,
        "validation_targets": [dict(item) for item in derive_validation_targets(task, route)],
        "model_intent": DEFAULT_MODEL_INTENT,
        "reasoning_effort": DEFAULT_REASONING_EFFORT,
        "required_execution_features": sorted(features),
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "return_contract": {"return_to": route,
                            "required_evidence": list(REQUIRED_EVIDENCE),
                            "required_sections": list(REQUIRED_SECTIONS)},
        "derived_from": {"objective": "jira", "required_capability": "execution_profile",
                         "allowed_surfaces": "task.surfaces",
                         "validation_route": "system-policy",
                         "environment": "operational_context",
                         "workspace": "project-registry"},
        "brief_source": "canonical-state",
        "validation_route": route,
        "required_capability": capability,
    }


# Product context only, resolved inside the Product workspace. Thebes internals
# are never Product executor context, and broad repository discovery is not
# needed when the task already declares its surfaces.
PRODUCT_CONTEXT_REFS = ("CLAUDE.md",)


def _context_refs(task):
    return PRODUCT_CONTEXT_REFS


def assert_manual_brief_cannot_override_canonical(supplied, derived):
    """A hand-authored brief may fill gaps; it may not contradict canonical safety.

    Only fields canonical state actually produced are protected, so a supplied
    brief for a work item whose canonical facts are absent still behaves as it
    always did. When derivation itself could not complete, ``derived`` is None
    and there is nothing canonical to contradict — that is the legitimate
    gap-filling use, and it is why the routine path never supplies a brief.
    """
    if not derived:
        return supplied
    for field in SAFETY_FIELDS:
        head, _, tail = field.partition(".")
        canonical = derived.get(head)
        offered = supplied.get(head)
        if canonical is None or offered is None:
            continue
        if tail:
            canonical, offered = canonical.get(tail), offered.get(tail)
            if canonical is None or offered is None:
                continue
        if _comparable(offered) != _comparable(canonical):
            raise ExecutionIntentUnresolved(
                "manual-brief-contradicts-canonical-state",
                "supplied brief sets %s to %r but canonical state derives %r; a "
                "hand-authored brief may not overrule a canonical safety fact"
                % (field, offered, canonical),
                classification=DERIVABLE, owner="orchestrator")
    return supplied


def _comparable(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _comparable(item)) for key, item in value.items()
                            if item is not None))
    if isinstance(value, (list, tuple)):
        return tuple(_comparable(item) for item in value)
    return value
