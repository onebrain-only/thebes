---
name: autonomy-constitution
description: "CEO 2026-10-27 — only money, merging into main and sending outside the company reach him; everything technical is Thebes's, enforced in agent/state/registry/autonomy.json"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0a2fe358-3c7d-441e-b22d-9153cd1adc00
  modified: 2026-10-27T17:04:07.227Z
---

The CEO is out of the product cycle. His work ends at tasks (via Codex), headlines and designs; after that he sees the result live on alpha.dabbler.pro. Only three things may reach him, each as ONE Arabic question with full context:
- spending money
- merging into `main`
- sending anything outside the company

DB work, DROP/DELETE, user-data edits, deploys and permission prompts are never his. Memphis owns the DB, snapshotting before anything destructive. The orchestrator decides everything else.

**Why:** "انا مش ديفلوبر، انا CEO … مهمتي بتنتهي عند التاسكات وعايز اشوف الحاجة لايف". He approves technical prompts unread, so asking him is not a safety check.

**How to apply:** The source of truth is `agent/state/registry/autonomy.json` (decision D-043 in `agent/DECISIONS.md`). If something reaches him outside the three, fix it in autonomy.json or the code, not in memory. Supersedes [[ceo-standing-approvals]], [[ceo-approves-in-chat]] and [[ceo-tests-localhost-first]]. Related: [[ceo-delegates-decisions]], [[never-stop-never-hand-steps]].

Enforcement (commit bbb06c0):
- `agent/scripts/policy_hook.py` answers PermissionRequest for team and orchestrator sessions. It only works once the CEO has run `python3 agent/scripts/apply_autonomy_settings.py`.
- Done means live. Review PASS closes the ticket only when the sha is on `origin/Alpha` (`live_check.py`), and posts an Arabic "Thebes: خلصت" comment with the alpha link.
- The CEO's view is the «الجديد» artifact, https://claude.ai/artifact/MU6TCUdcZxmq5oeaR1qjGa. It reads Jira live and parses that comment.
- To measure progress, run `python3 -m agent.execution.ceo_metrics`. The target is `reached_ceo_outside_the_three` = 0.

**Narrowed by D-044 (CEO 2026-10-30):** autonomy covers HOW work is done, not WHAT new work exists. Creating Jira tickets/Epics and merging into Alpha need his own words, lifted with `python3 -m agent.execution.orders grant` and enforced by `agent/scripts/order_gate.py`. A PM ruling, a CPO ranking or the orchestrator's own decision is not an order. Moving tickets to Ready and adopting CPO/CTO defaults stay autonomous. See [[orchestrator-facts-and-orders]].
