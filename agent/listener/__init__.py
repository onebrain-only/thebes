"""Thebes Listener — the Phase-3 communication boundary.

The Listener receives an instruction, validates its shape, normalizes it into a
bounded intent, writes it down durably, and hands it to the existing Thebes
Controller in a separate process. It carries the Controller's answer back, and
it carries a CEO decision forward into the continuation machinery that already
exists.

IT IS NOT A SECOND CONTROLLER. It never interprets Jira, authorizes Product
work, resolves capability, selects a seat or a provider, allocates a workspace,
claims, leases, routes validation, integrates, or moves a lifecycle. Every one
of those remains the Controller's, and the Controller re-derives them from
canonical sources on each invocation exactly as it did before this package
existed.

Its records are communication evidence, never authority. See `store` for that
boundary, `contract` for what may cross it, `dispatch` for the process seam and
`server` for the process itself.
"""
