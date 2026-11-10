---
name: one-orchestrator-conversation
description: "CEO 2026-11-02 D-048: one orchestrator chat forever; rotation off; retired chats block prompts and relay them"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 0a2fe358-3c7d-441e-b22d-9153cd1adc00
  modified: 2026-11-02T05:04:35.492Z
---

The orchestrator lives in ONE conversation (session b9b99f0a as of 2026-11-02). Daily and after-compaction rotation (D-044) is off: `watchdog.ROTATION_ENABLED = False`.

**Why:** every rotated chat was named `thebes-orchestrator`, so the CEO couldn't tell which was live. Typing into an old chat revived it, and three ran at once.

**How to apply:**
- Never propose re-enabling rotation or opening a fresh orchestrator chat.
- When asked "which one", read `store.active_role_session('orchestrator')`.
- A prompt typed into a retired chat is blocked by `ceo_prompt_hook` and reaches the live orchestrator as a `ceo_retired` inbox item.
