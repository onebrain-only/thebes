---
name: location-permission-rule
description: "CEO rule (2026-10-13) for location: ask the OS permission only ONCE; if denied the user sets the location manually via a drawer; location is now needed in four places (Feeds, Games, Meetups, Sports/Venues)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-13T18:49:48.828Z
---

CEO 2026-10-13: the old rule ("request permission when the Sports screen opens") is OBSOLETE. Location is now used in four surfaces (Feeds, Games, Meetups and the Sports/Venues screen; confirm the exact four in the repo). The app asks the OS for location permission **only once**. If the user denies (or there is no access), the app NEVER asks again; instead each surface opens a drawer that says "Set location" and lets the user set it **manually**. No automatic or periodic re-prompts (for example no prompt from a 15-minute timer or from opening a screen).

**Why:** repeated OS prompts annoy users and fail anyway after a denial; the CEO wants one prompt, then a manual fallback that works everywhere location is required. It keeps his earlier standing rule: never ask the OS for notification/location permission before the user acts in the app.

**How to apply:** when writing or judging tickets about location (KAN-520, KAN-521 and anything after): a single prompt path (location intro or an explicit user action), a persistent denied state, and a manual "Set location" drawer on all four surfaces. Related: [[cleanup-after-integration]].
