---
name: ceo-tests-localhost-first
description: "CEO 2026-10-24 — UI work is tested on a local build (localhost in his PC's in-app browser) before any push to Alpha"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-24T15:13:08.744Z
---

**REINSTATED 2026-10-30 (CEO, in chat):** app and UI changes are tested internally on localhost BEFORE anything goes to Alpha; he never told anyone to push to Alpha first. The 2026-10-27 supersession is void for app/UI work. He does not test by hand; the team or Edfu does, on localhost.

**Credential rule stays (hard):** no agent types a password or reads the keychain on a hosted site such as alpha.dabbler.pro (no staging/dev/test label in the hostname). Localhost with seed/test values is fine. Only path for hosted checks: he logs in once in his own Chrome and the agent drives that open session.


For UI tickets, the team builds its branch and serves it on localhost (e.g. `flutter run -d web-server --web-port <port>`), checks it themselves, and leaves it running. The CEO tests that URL in the in-app browser on his PC. Ops fast-forwards Alpha only after he says "موافق".

**Why:** KAN-640 R1 was pushed to Alpha and his test showed the old screen. Push → test → fail wasted a cycle. He asked for a local run instead.

**How to apply:** Every UI brief asks for a localhost URL in the report. Give the CEO that URL plus Arabic test steps. Push to Alpha only after his approval. Related: [[ceo-reviews-himself]], [[ceo-standing-approvals]].
