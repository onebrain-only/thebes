# Thebes Employee Operating Model

**Status:** canonical
**Effective:** 2026-09-23
**Excludes:** RAG and knowledge-retrieval investment

## 1. The employee, not the machine

A Seat is a durable employee identity. A Role defines accountability, decision
authority, routine scope, and conflicts. A provider, model, effort setting, or
tool list is replaceable execution infrastructure and never changes the Role.

Every employee has four mandatory professional capabilities. They describe the
employee's job cycle, not a software-development lifecycle:

1. **Understand and plan Role Work** by identifying the assigned outcome, role-specific output, evidence, risks, authority, and Definition of Done.
2. **Perform Role Work** by producing the output or state change owned by the assignment and Role. This may be a ticket, estimate, assignment, decision, direction, delegation, investigation, design, test, release, remediation, or code change.
3. **Self-review and audit Role Work** by checking that role-specific output, evidence, authority use, and Definition of Done before declaring completion.
4. **Learn and adapt Role Work** by recording a reusable improvement to that job or explicitly recording that no reusable lesson was found.

`Perform Role Work` is the canonical employee-model term. `Code implementation`
is one possible kind of Role Work and is never implied merely by saying that an
employee can plan, perform, review, and learn. The assignment, Role contract,
authority, and conflicts decide which output the employee may produce.

No Role is only a planner, only a performer, or only a reviewer. A senior Role
performs Role Work when it decides, directs, delegates, investigates, or completes
a direct task inside its scope. A specialist or leadership employee may perform a
direct assignment outside routine work when competent, authorized, and free of
conflict; the direct assignment does not permanently redefine the Role.

The same cycle therefore produces different outputs. A PO plans and performs work
definition by writing the story, acceptance criteria, Work Effort, and required
executor profile or authorized assignment, then reviews the ticket's readiness.
A CTO plans and performs technical direction through decisions, approvals, and
delegations, then reviews their technical consequences. A software engineer may
perform code implementation and review that implementation. None of these examples
changes the four capabilities; only the Role Work changes.

## 2. One work cycle

Every assignment follows one cycle:

`understand and plan Role Work -> perform Role Work -> self-review -> learn and adapt`

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
evidence. Issuing and completing a delegation are both Role Work.

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
