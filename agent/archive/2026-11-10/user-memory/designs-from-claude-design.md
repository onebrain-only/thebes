---
name: designs-from-claude-design
description: CEO 2026-10-15 — every design reference means the Claude Design project; Messaging UI is project 60c6ce9d (Messaging.dc.html + ds-components/messaging/messaging.jsx)
metadata:
  type: feedback
---

CEO 2026-10-15: "In all designs just refer to Claude design." Any ticket or brief that needs a design points to the Claude Design project through the DesignSync tool (list_files / get_file, read-only, files capped at 256 KiB), never to invented layouts.

Messaging project: id 60c6ce9d-7bc1-48b0-855b-550493932c60. Files: Messaging.dc.html, Messaging Design System.dc.html, MESSAGING_DS_ADDITIONS.md, ds-components/messaging/messaging.jsx, plus the _ds tokens (colors, spacing, typography, glass, fonts) and _ds_bundle.js.

**Why:** one source of truth for UI; teams must not guess.
**How to apply:** put the project id and file names in the DECISIONS MADE of every UI ticket brief (KAN-546..554 and later messaging UI). Related: [[ui-tickets-test-scenarios]].
