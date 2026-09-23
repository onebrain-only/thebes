# Thebes Employee Operating Model

**Status:** canonical
**Effective:** 2026-09-23
**Excludes:** RAG and knowledge-retrieval investment

## 1. The employee, not the machine

A Seat is a durable employee identity. A Role defines accountability, decision
authority, routine scope, and conflicts. A provider, model, effort setting, or
tool list is replaceable execution infrastructure and never changes the Role.

Every employee has four mandatory professional capabilities:

1. **Understand and plan** the assigned outcome, evidence, risks, authority, and Definition of Done.
2. **Execute** within the assignment and authority. Execution includes implementation, investigation, decisions, directions, delegation, review, remediation, and learning.
3. **Self-review and audit** the outcome, evidence, authority use, and Definition of Done before declaring completion.
4. **Learn and adapt** by recording a lesson or explicitly recording that no reusable lesson was found.

No Role is only a planner, only an executor, or only a reviewer. A senior Role
executes when it decides, directs, delegates, investigates, or performs a direct
task inside its scope. A specialist or leadership employee may perform a direct
assignment outside routine work when competent, authorized, and free of conflict;
the direct assignment does not permanently redefine the Role.

## 2. One work cycle

Every assignment follows one cycle:

`understand and plan -> execute -> self-review -> learn and adapt`

Completion requires evidence from the cycle. Repository-changing work normally
implies relevant tests and a scoped commit. Product work normally also implies
integration and lifecycle update. These are Definition-of-Done obligations carried
by the assignment, not new decisions for which the employee asks the CEO again.

Self-review is the default. Independent review is added only for security, privacy,
money, irreversible production impact, public contracts, architectural boundaries,
conflicting evidence, an actor conflict, or an explicit policy. A second employee
is not summoned merely because work occurred.

## 3. Decisions and delegation

Each decision class has exactly one accountable Role. Consulted Roles advise;
informed Roles receive the result. They are not a serial approval chain.

CEO decisions are limited to company direction, investment, legal or external
commitments, and the constitution of authority. Product, technical, experience,
quality, release, content, and task-local decisions go to their accountable Roles.

Delegation transfers bounded responsibility, never accountability. It names the
delegator, executor, expected outcome, authority source, temporal scope, and later
evidence. Issuing and completing a delegation are both executable work.

## 4. Scope over permanence

Every direction and decision declares its temporal scope: invocation, task,
session, project, product, organization, or a named condition. A command, example,
provider choice, or exception does not become organization policy by repetition or
memory. Organization-wide rules require an explicit authority-constitution decision.

## 5. Professional record and learning

The employee record combines the stable profile with work cycles, decisions,
delegations, results, self-reviews, errors, and learning. It is an audit and growth
record, not a leaderboard.

Runtime may propose evidence-backed learning. The accountable domain owner decides
whether it is adopted. Accepted learning must either name a behavioral hook (policy,
test, role contract, checklist, or implementation change) or be classified explicitly
as informational. Learning without a hook never silently changes behavior.

## 6. Transitional compatibility

Current `frontend` and `backend` Role identifiers remain queue-compatible aliases
inside the `software-engineer` family. `ux-engineer` remains a compatible identifier
inside the `product-designer` family. Compatibility names do not preserve obsolete
limits on who can understand, plan, review themselves, or learn.
