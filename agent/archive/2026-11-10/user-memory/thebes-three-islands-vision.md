---
name: thebes-three-islands-vision
description: "CEO's 2026-10-01 target for the Thebes workflow — three groups (Listener / decision layer with Jev / execution), any-chat front door, and the ChatGPT wake limit"
metadata:
  node_type: memory
  type: project
  originSessionId: 0a2fe358-3c7d-441e-b22d-9153cd1adc00
  modified: 2026-10-01T09:09:43.150Z
---

On 2026-10-01 the CEO (Moataz) described the target shape for the Thebes workflow system
(not the Dabbler app): three GROUPS, explicitly "not layers" — the Listener may talk to
execution directly; the decision group enters only when a decision is needed.

- **Listener**: a behaviour any chat can run (Codex, Claude, ChatGPT, other) — listen to the
  CEO, form a professional prompt, send to the router. The front door. One job only.
- **Decision group**: orchestrator + leadership seats (cto/cpo/cxo…), should run **Jev**
  (TypeSafe AI System-One model: typed Choice/Score/Noul decisions with confidence, no text
  generation, `POST api.typesafe.ai/v1/systemone`, key `TYPESAFE_API_KEY`). No key yet;
  plan/viability first, then he builds the API (TypeScript / OpenRouter / Vercel).
- **Execution**: executes, asks the decision group, reports done/status to the Listener.

Definition of success he gave: Model A sends to Model B, goes idle; B works; B's result
WAKES A as a new turn. ChatGPT web cannot be woken once idle (his observed failure);
Codex↔Claude already works (shared Codex runtime + conversation-dispatch, proven 2026-09-30).

He said the D-026 "infrastructure frozen" state was frozen by mistake and he wants no new
agents/layers — reuse what exists.

**Why:** every future design question in this repo should be answered against this shape.
**How to apply:** map his vocabulary onto repo names: Listener = Primary/Conversation
Intelligence (`primary_binding`, `bootstrap_prompt`); decision group = `authority.json`
decision classes + `decision_required` routing (`primary_notify.NEXT_STEP`); execution =
bound `role_session` Claude seats. Jev fits as a deterministic gate, never a seat. See
[[thebes-workflow-system-map]].
