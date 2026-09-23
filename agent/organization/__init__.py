"""Human organization model for Thebes.

This is the public seam. Callers ask who owns a decision, what an employee may
do, what review risk requires, or write one auditable work record. Provider and
model selection deliberately do not appear here.
"""

from .authority import (assert_decision_authority, decision_owner,
                        independent_review_required)
from .registry import employee_profile, employees, validate_registries
from .work import completion_actions, new_work_cycle

__all__ = (
    "assert_decision_authority", "completion_actions", "decision_owner",
    "employee_profile", "employees", "independent_review_required",
    "new_work_cycle", "validate_registries",
)
