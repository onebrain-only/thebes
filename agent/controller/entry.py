"""Which callers may use the Controller's orchestrating commands.

Phase 4 moves the normal operational front door to the Listener. `execute`,
`resume` and `decide` are the three commands that orchestrate Product execution,
and after Phase 4 the ordinary way to reach them is an intent, not a shell
prompt. This module is what makes that a fact rather than a paragraph — the
program has learned repeatedly that prose does not stop a command being typed.

WHAT THIS IS NOT. It is not authentication and must never be described as
security. The marker below is an environment variable, and any local process can
set one. It stops a MISTAKE, not an attacker: it makes the Listener path the
default and makes the bypass deliberate, reasoned and visible in the result.
Phase 3 chose loopback-only precisely because the boundary is not authenticated,
and Phase 4 changes nothing about that.

The maintenance path is preserved on purpose. Recovery, debugging and tests
genuinely need to drive the Controller directly, and deleting a useful interface
to make a diagram clean would be a worse system. It simply has to say so:
`--maintenance-reason` is required, and the reason is recorded in the result.
"""

import os


# Set by the Listener's dispatcher on the subprocess it launches. Its value is
# the intent that authorized the invocation, so an operational result can be
# traced back to the intake record that caused it.
INTENT_ENV = "THEBES_LISTENER_INTENT_ID"

# The commands that orchestrate Product execution. Read-only planning and the
# recovery `integrate` path are deliberately absent: they orchestrate nothing,
# and Phase 4 is about the execution front door, not about every command.
ORCHESTRATING_COMMANDS = ("execute", "resume", "decide", "validate",
                          "dispatch-session", "session-outcome")

FRONT_DOOR_REFUSAL = "direct-controller-entry-retired"


def listener_intent_id(environ=None):
    """The intent this process was launched for, or None if it was not."""
    value = (environ if environ is not None else os.environ).get(INTENT_ENV) or ""
    return value.strip() or None


def caller(command, maintenance_reason=None, environ=None):
    """Classify this invocation. Returns (permitted, classification, detail)."""
    if command not in ORCHESTRATING_COMMANDS:
        return True, "internal-interface", None
    intent_id = listener_intent_id(environ)
    if intent_id:
        return True, "listener", intent_id
    if maintenance_reason:
        return True, "maintenance-override", maintenance_reason
    return False, FRONT_DOOR_REFUSAL, (
        "`%s` is no longer the operational front door. Normal operation enters "
        "through the Listener:\n"
        "    python3 -m agent.listener submit <WORK-ITEM>      # execute\n"
        "    python3 -m agent.listener decide <INTENT-ID> ...  # decide/resume\n"
        "The Listener dispatches this same command in its own process. For "
        "recovery, debugging or a test, pass --maintenance-reason '<why>'; the "
        "reason is recorded in the result." % command)
