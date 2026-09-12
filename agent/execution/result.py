"""Provider-neutral receipt boundary for normalized execution results.

Receiving an executor result is not a lifecycle, review, authorization, routing,
or acceptance decision. The controller may inspect and independently verify the
claims, then perform a separately authorized bounded action elsewhere.
"""

from agent.execution.provider import ExecutionResult


def receive_execution_result(result):
    """Validate the normalized type and return the same inert evidence object."""
    if not isinstance(result, ExecutionResult):
        raise TypeError("core result handling requires ExecutionResult")
    return result
