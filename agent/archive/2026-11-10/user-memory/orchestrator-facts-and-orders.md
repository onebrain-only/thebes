---
name: orchestrator-facts-and-orders
description: "D-044 + D-046: answer only from the fact block; reviewed work auto-merges to Alpha; supporting tickets free; only Epics/new scope need his verbatim order; never poll"
metadata:
  type: project
---

The CEO's complaint: the orchestrator created tickets/Epics he never ordered (KAN-692..707, "Recurring games"), merged into Alpha unasked, claimed a team held a ticket it had finished, and left no trace. His answers: gate only ticket/Epic creation and the Alpha merge; rotate the session "كل يوم + بعد 4 compactions".

**Why:** a session compacted 162 times answered from stale memory and authorised itself ("PM ruling + CPO ranking already adopted by the orchestrator").

**How to apply:** D-044 in `agent/DECISIONS.md` and `agent/ORCHESTRATOR.md` §8 are the source.
- `orders.py` holds CEO messages, grants and the action ledger.
- `facts.py` builds the per-turn fact block.
- `ceo_prompt_hook.py` handles UserPromptSubmit and PreCompact; `order_gate.py` handles PreToolUse/PostToolUse.
- `watchdog.rotate_orchestrator` does the rotation.

**D-046 refinement (CEO 2026-11-01, angry):** D-044 as built held reviewed work (KAN-688/689) for hours waiting on him, and the orchestrator burned tokens on a 1-minute cron while every team was idle. "احنا كده بنقول له خليك غبي".
- Review-passed work integrates into Alpha on its own.
- A ticket that supports existing work (parent, blocker, or KAN key in the summary) needs no order.
- Only an Epic or new scope needs his order.
- The orchestrator never polls: CronCreate and ScheduleWakeup are denied by order_gate.
- Never design a gate that makes the system wait on him for needed work.

Hooks load only after a session restarts. When debugging "who made this ticket", run `python3 -m agent.execution.orders log`. Related: [[autonomy-constitution]], [[never-stop-never-hand-steps]], [[po-no-followup-tickets]], [[messaging-no-po-tickets]], [[no-tickets-without-ceo-approval]].
