---
name: d049-parallel-throughput
description: "CEO 2026-11-02 D-049: ticket every 10 min; stack dependents on checked commits, tier-1 auto pass, Ready ≥10, same Epic ≠ dependency"
metadata:
  node_type: memory
  type: project
  originSessionId: 0a2fe358-3c7d-441e-b22d-9153cd1adc00
  modified: 2026-11-02T08:45:24.539Z
---

CEO approved (2026-11-02) a ticket finished every 10 minutes, work parallel even inside one Epic.

**Why:** process waits (review, Alpha, serial Blocks chains, empty Ready) were the bottleneck, not coding.

**How to apply:**
- Dependents start on the blocker's checked sha; integration holds them until the blocker passes review.
- Tier 1 auto-passes; tier 2 = one language/theme (AR+Dark when text changed); tier 3 unchanged.
- PM keeps Ready ≥10 startable by cutting already-approved Epics (no new scope), one screen/function + test per ticket, Blocks only for real code/data dependency.
- Don't propose reinstating Alpha-wait or two-language tier-2 review. Related: [[orchestrator-facts-and-orders]], [[no-tickets-without-ceo-approval]].
