"""Thebes Core — the canonical company runtime.

`MASTER_ROADMAP.md` §36 asks Phase 5 for a clean separation between three
intelligences, and §37 draws the middle one as a single box. This package is
that box made addressable:

    Conversation Intelligence   the CEO's controller conversation (Codex).
                               Outside this repository. Interprets intent.
                               Derives no execution detail and holds no state.

    Canonical Company          THIS. Intake, Persistent State, company rules,
    Intelligence               Product state, work lifecycle, capability model,
                               authorization, dependencies, context assembly,
                               validation, learning, provider selection and
                               execution. Conversation-independent.

    Execution Intelligence     the provider adapter and the Product executor.
                               Product work only; never orchestration.

WHAT PHASE 5 DID AND DID NOT DO. It did not rewrite the orchestration engine,
and it added no second one. Every responsibility §37 names already existed and
already worked; what did not exist was one place that owns an intent's whole
life, and one answer to "what happened to it". Core is composition plus that
answer. `SUBSYSTEMS` below is the map, and it points at the existing modules on
purpose: a Core that reimplemented them would be a fourth source of truth
wearing an architectural name.

WHAT CORE DOES NOT OWN. Jira still owns Product lifecycle. Persistent State
still owns Thebes operational truth. Git still owns code. Core coordinates
them; it outranks none of them, and where its transport records and canonical
state disagree, canonical state wins — see `lifecycle`.
"""

# The §37 responsibility map. Each entry names where the responsibility ACTUALLY
# lives, so a reader can check the claim rather than trust the diagram.
SUBSYSTEMS = {
    "intake": ("agent.listener.contract", "agent.listener.server"),
    "transport_durability": ("agent.listener.store",),
    "persistent_state": ("agent.state.store",),
    "company_rules": ("agent.state.policy",),
    "product_state": ("agent.integrations.jira", "agent.state.store"),
    "work_lifecycle": ("agent.state.board", "agent.controller.completion"),
    "capability_model": ("agent.state.roster", "agent.state.queue"),
    "authorization": ("agent.controller", "agent.state.store"),
    "dependencies": ("agent.state.queue", "agent.state.store"),
    "context_assembly": ("agent.controller.intent",),
    "validation": ("agent.controller.validation", "agent.state.policy",
                   # 2026-09-15: deterministic test execution in front of the
                   # reviewer. Routing, running and classifying live here; the
                   # verdict still lives only in agent.state.store.
                   "agent.qa.routing", "agent.qa.gate"),
    "learning": ("agent.state.telemetry", "agent.state.retrospective",
                 "agent.state.learning"),
    "provider_selection": ("agent.execution.selection",),
    "execution": ("agent.execution.wake", "agent.execution.provider"),
    "executor_boundary": ("agent.execution.brief",),
    "intent_lifecycle": ("agent.core.lifecycle",),
}

# Core's own entry surface. Deliberately two verbs: everything else a caller
# might want is a question about one of these two, and a third verb here would
# be the beginning of a second orchestration engine.
from agent.core.lifecycle import (                       # noqa: E402,F401
    ACCEPTED, AWAITING_AUTHORITY, COMPLETED, INDETERMINATE, LIFECYCLE_STATES,
    ORCHESTRATING, REFUSED, UNDELIVERED, resolve, resolve_all,
)
