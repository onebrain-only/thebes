"""Persistent-session dispatch: the same preparation as ``execute``, then STOP.

The one-shot path wakes a fresh provider process for every execution. This
path exists beside it for a worker that already lives in a durable, bound
Claude session. Thebes still does everything it owns — authorization, mode,
task, seat, Jira observation, intent and brief, claim, realized workspace,
continuation gate and execution lease — and then stops before any provider is
selected or launched. What it returns is a DISPATCH PACKET: the rendered brief
plus a short envelope. The controller conversation delivers that packet to the
bound session itself; Thebes sends nothing.

Later the same conversation reports what the worker said with
``session_outcome``. Thebes checks the reporting session id against the
binding, records the outcome durably and closes the lease. It runs no
validation, integration or Jira transition: an outcome is invocation evidence,
never Product acceptance.

Identity is the session id. Never a session name, PID, socket path or bridge
address — none of those survive a restart, and a name is not unique.
"""

import re

from agent.execution.brief import render_executor_brief
from agent.integrations import jira
from agent.state import roster, store
from agent.controller import (
    ControllerInputError,
    ProductAuthorization,
    _build_request,
    _prepare_dispatch,
    _resolve_seat,
    _result_shell,
    canonical_admissibility,
)
from agent.controller.intent import ExecutionIntentUnresolved, resolve_execution_intent
from agent.controller.workspace import WorkspaceUnavailable, realize_workspace


# The path is Claude-only in this slice. The role is not: a seat bound to a
# Codex session is refused with a structured reason, not silently rerouted.
SUPPORTED_PROVIDER = "claude"

UUID_TEXT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Outcomes a WORKER may report. worker_unreachable is recorded by the
# controller conversation when delivery fails, never claimed by a worker.
WORKER_OUTCOMES = ("completed", "blocked", "decision_required",
                   "clarification_required", "failed")


class _BindingRefused(Exception):
    """A seat-binding precondition failed before any claim was attempted."""

    def __init__(self, blocker):
        super().__init__(blocker)
        self.blocker = blocker


class _BoundSeats:
    """The seat registry narrowed to seats with an ACTIVE session binding.

    Allocation itself is unchanged: ``select_claim_seat`` still chooses, among
    the seats it is shown. It is simply not shown a seat with no bound session.
    """

    def __init__(self, seat_registry, state_store):
        self._seats = seat_registry
        self._state = state_store

    def read(self):
        return {seat_id: entry for seat_id, entry in self._seats.read().items()
                if self._state.active_role_session(seat_id) is not None}


def _dispatch_shell(work_item_id):
    result = _result_shell(work_item_id)
    result.update({"dispatch_status": "not-prepared", "dispatch_id": None,
                   "dispatch_packet": None, "execution_lease_id": None,
                   "session_id": None})
    return result


def dispatch_session(work_item_id, *, authorization=None, state_store=store,
                     jira_client=jira, seat_registry=roster,
                     intent_resolver=resolve_execution_intent,
                     workspace_allocator=realize_workspace, deliver=False,
                     deliverer=None, origin_thread_id=None):
    """Prepare one work item for a bound persistent session and return its packet.

    Never selects, constructs or launches a provider. The execution lease this
    opens stays open until ``session_outcome`` records the result.

    With ``deliver=True`` the packet is also handed to the bound session
    through ``agent.execution.claude_delivery`` (one attempt, durable
    session_delivery) and the call returns as soon as that attempt has
    settled — it never waits for preflight, execution or an outcome.
    """
    result = _dispatch_shell(work_item_id)
    result["delivery"] = None
    result["origin_thread_id"] = origin_thread_id
    if origin_thread_id is not None:
        # Fail closed before any claim: a reply can only be routed to a live
        # conversation on the shared Thebes runtime, never to a Desktop thread.
        from agent.execution.codex_runtime import RuntimeError_, require_conversation
        try:
            require_conversation(origin_thread_id, state_store)
        except RuntimeError_ as exc:
            result["blocker"] = exc.code
            return result
    result["operating_mode"] = state_store.current_operating_mode()
    authorization = authorization or ProductAuthorization(
        state_store=state_store,
        admissibility=canonical_admissibility(state_store, jira_client))
    auth = authorization.for_work_item(work_item_id)
    result.update({"authorization_status": auth["reason"],
                   "authorization_reference": auth.get("reference")})
    if not auth["authorized"]:
        return result

    bound = {}

    def resolve_bound_seat(task):
        owner = (task.get("ownership") or {}).get("seat_id")
        if owner:
            binding = state_store.active_role_session(owner)
            if binding is None:
                raise _BindingRefused("no-bound-session")
            resolved = _resolve_seat(task, seat_registry, state_store)
        else:
            capability = (task.get("execution_profile") or {}).get("required_capability")
            candidates = _BoundSeats(seat_registry, state_store)
            if not any((entry or {}).get("capability") == capability
                       for entry in candidates.read().values()):
                raise _BindingRefused("no-bound-session-for-capability")
            resolved = _resolve_seat(task, candidates, state_store)
            binding = state_store.active_role_session(resolved[0])
        if binding.get("provider") != SUPPORTED_PROVIDER:
            raise _BindingRefused("persistent-session-unsupported-provider")
        bound["binding"] = binding
        return resolved

    lease = None
    try:
        prepared = _prepare_dispatch(result, work_item_id, None, auth, state_store,
                                     jira_client, seat_registry, intent_resolver,
                                     workspace_allocator, seat_resolver=resolve_bound_seat)
        if prepared is None:
            return result
        seat_id = prepared["seat_id"]
        binding = bound["binding"]
        realized = prepared["realized"]

        task = state_store.assert_execution_permitted(work_item_id, seat_id)
        lease = state_store.open_execution_lease(work_item_id, seat_id, auth["reference"])
        result.update({"execution_lease_id": lease["execution_lease_id"],
                       "lease_closure_status": "open-until-outcome"})
        request = _build_request(task, seat_id, prepared["brief"], lease)
        rendered = render_executor_brief(request)
        # The id is generated before the record so the delivered message can
        # name it, but nothing is durably recorded — and no packet is handed
        # back — until every step that can still fail (build, render) has
        # already succeeded.
        dispatch_id = state_store.new_id("session_dispatch")
        message = render_dispatch_message(dispatch_id, work_item_id, binding, realized,
                                          rendered)
        fields = {
            "work_item_id": work_item_id, "seat_id": seat_id,
            "provider": binding["provider"], "session_id": binding["session_id"],
            "worktree_path": realized["path"], "branch": realized["branch"],
            "execution_lease_id": lease["execution_lease_id"],
            "invocation_id": request.invocation_id,
            "authorization_ref": auth["reference"], "status": "dispatched",
            "outcome": None, "summary": None, "reference": None,
            "reported_session_id": None, "outcome_at": None, "recorded_by": None,
        }
        if origin_thread_id is not None:
            fields.update({"origin_provider": "codex", "origin_thread_id": origin_thread_id,
                           "reply_to_thread_id": origin_thread_id,
                           "target_provider": "claude",
                           "target_session_id": binding["session_id"],
                           "delivery_id": dispatch_id})
        record = state_store.create("session_dispatch", fields, rid=dispatch_id)
        packet = {
            "dispatch_id": record["dispatch_id"], "work_item_id": work_item_id,
            "seat_id": seat_id, "provider": binding["provider"],
            "session_id": binding["session_id"],
            "session_name": binding.get("session_name"),
            "worktree_path": realized["path"], "branch": realized["branch"],
            "stable_home": binding["stable_home"],
            "execution_lease_id": lease["execution_lease_id"],
            "invocation_id": request.invocation_id,
            "restrictions": {"prohibited_actions": list(request.prohibited_actions),
                             "allowed_surfaces": list(request.allowed_surfaces)},
            "message": message,
        }
        result.update({"dispatch_status": "dispatched", "dispatch_id": record["dispatch_id"],
                       "dispatch_packet": packet, "session_id": binding["session_id"],
                       "invocation_id": request.invocation_id})
        if deliver:
            from agent.execution.claude_delivery import deliver_session_dispatch
            deliver_fn = deliverer or deliver_session_dispatch
            delivered = deliver_fn(record["dispatch_id"], message, state_store=state_store)
            result["delivery"] = delivered.as_dict() if hasattr(delivered, "as_dict") else delivered
        return result
    except _BindingRefused as exc:
        result["blocker"] = exc.blocker
        return result
    except WorkspaceUnavailable as exc:
        _close_lease_after_failure(state_store, lease, result)
        result.update({"blocker": str(exc), "workspace_status": exc.reason,
                       "workspace_blocker": exc.as_blocker(work_item_id,
                                                           result.get("seat_id"))})
        return result
    except ExecutionIntentUnresolved as exc:
        _close_lease_after_failure(state_store, lease, result)
        result.update({"blocker": str(exc), "needs_input": exc.detail,
                       "ceo_input_required": exc.classification == "CEO_INPUT_REQUIRED",
                       "governance_input": exc.as_governance_input(work_item_id)})
        return result
    except (ControllerInputError, store.StateError, jira.JiraError, ValueError) as exc:
        _close_lease_after_failure(state_store, lease, result)
        result["blocker"] = str(exc)
        return result


def _close_lease_after_failure(state_store, lease, result):
    """A lease opened for a dispatch that never produced a packet must not linger."""
    if lease is None:
        return
    state_store.close_execution_lease(lease["execution_lease_id"], lease["revision"],
                                      "orchestrator")
    result["lease_closure_status"] = "closed-after-preparation-failure"


def render_dispatch_message(dispatch_id, work_item_id, binding, realized, rendered_brief):
    """The full text delivered to the bound session: envelope, then the brief.

    Plain English, Thebes-authored. It names the exact workspace because
    nothing launches this worker into it — the worker must enter and verify it.
    """
    path, branch = realized["path"], realized["branch"]
    lines = (
        "DISPATCH %s %s" % (dispatch_id, work_item_id),
        "Persistent-session dispatch from Thebes. Bound session: %s." % binding["session_id"],
        "",
        "Before anything else:",
        "1. cd %s" % path,
        "2. Verify all three, exactly:",
        "   pwd                            must print %s" % path,
        "   git branch --show-current      must print %s" % branch,
        "   git rev-parse --show-toplevel  must print %s" % path,
        "   If any of them differs, change nothing and report the outcome blocked.",
        "3. Do the work in the brief below only inside that worktree. Commit on %s "
        "only if the brief requires changes." % branch,
        "4. Never run Thebes commands, never change Jira, and never start another "
        "executor or worker.",
        "5. The brief below calls its workspace transport-enforced. For this dispatch "
        "it is not: you enforce it yourself by working only in the directory above.",
        "",
        "When finished, report your outcome exactly as the THEBES_DELIVERY block at the "
        "top of this message says (the one report command, run from %s). <outcome> is "
        "one of: %s." % (binding["stable_home"], ", ".join(WORKER_OUTCOMES)),
        "Then cd back to %s." % binding["stable_home"],
        "",
        "--- brief ---",
    )
    return "\n".join(lines) + "\n" + rendered_brief


def session_outcome(work_item_id, dispatch_id, outcome, session_id, summary,
                    reference=None, *, delivery_id=None, state_store=store,
                    recorded_by="orchestrator", notifier=None):
    """Record what a bound session reported, after checking it is that session.

    No validation, integration or Jira transition runs here. The claim is
    preserved; a follow-up is a new ``dispatch_session`` for the same item.

    Once recorded, a worker-reported outcome schedules exactly one durable
    Primary notification (``agent.execution.primary_notify``) and returns
    without waiting for it. A refused or duplicate outcome schedules nothing.
    """
    result = {"work_item_id": work_item_id, "dispatch_id": dispatch_id,
              "outcome": outcome, "outcome_status": "not-recorded",
              "seat_id": None, "session_id": None, "lease_closure_status": "unchanged",
              "claim_status": "preserved", "recovery_hint": None, "blocker": None,
              "primary_notify": None}
    dispatch = state_store.read("session_dispatch", dispatch_id)
    if dispatch is None:
        result["blocker"] = "dispatch-not-found"
        return result
    if dispatch.get("work_item_id") != work_item_id:
        result["blocker"] = "dispatch-work-item-mismatch"
        return result
    result.update({"seat_id": dispatch.get("seat_id"),
                   "session_id": dispatch.get("session_id")})
    try:
        record = state_store.record_session_outcome(
            dispatch_id, outcome, summary, recorded_by,
            session_id=session_id, reference=reference, delivery_id=delivery_id)
    except store.StateError as exc:
        result["blocker"] = str(exc)
        return result
    result.update({"outcome_status": "recorded", "status": record["status"],
                   "lease_closure_status": "closed",
                   "recovery_hint": record.get("recovery_hint")})
    if outcome in WORKER_OUTCOMES and record.get("origin_provider") == "codex":
        # Codex-origin dispatch: reply to exactly the conversation that
        # dispatched, on the shared runtime — never via the global Primary.
        from agent.execution import codex_runtime
        router = notifier or codex_runtime.schedule_worker_result
        try:
            result["origin_reply"] = router(record, state_store=state_store)
        except (store.StateError, codex_runtime.RuntimeError_) as exc:
            result["origin_reply"] = {"status": "failed", "error": str(exc)}
    elif outcome in WORKER_OUTCOMES:
        from agent.execution import primary_notify
        schedule = notifier or primary_notify.schedule
        try:
            result["primary_notify"] = schedule(dispatch_id, record, state_store=state_store)
        except store.StateError as exc:
            # The outcome is recorded either way; a notification problem is
            # reported beside it, never allowed to undo the settlement.
            result["primary_notify"] = {"status": "failed", "error": str(exc)}
    return result


def bind_session(seat_id, provider, session_id, stable_home, *, session_name=None,
                 bound_by="ceo", state_store=store):
    """Bind (or rebind) one seat's persistent session. Maintenance/internal only."""
    if not UUID_TEXT.match(session_id or ""):
        return {"seat_id": seat_id, "binding_status": "refused",
                "blocker": "session-id-must-be-a-uuid"}
    current = state_store.read("role_session", seat_id)
    try:
        record = state_store.bind_role_session(
            seat_id, provider, session_id, stable_home, bound_by,
            session_name=session_name,
            expected_revision=current["revision"] if current else None)
    except store.StateError as exc:
        return {"seat_id": seat_id, "binding_status": "refused", "blocker": str(exc)}
    return {"seat_id": seat_id, "binding_status": "rebound" if current else "bound",
            "binding": record, "blocker": None}
