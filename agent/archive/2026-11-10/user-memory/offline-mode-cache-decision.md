---
name: offline-mode-cache-decision
description: "CEO 2026-10-20 offline-mode product decisions from KAN-599 — cache on device, open on cached feed, offline banner, offline settings sync"
metadata:
  node_type: memory
  type: project
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-20T07:23:17.953Z
---

CEO decided (2026-10-20) the offline behaviour of the app after the KAN-599 review:

- Cache feeds and listings ON DEVICE, like Facebook/Instagram. Overrules the review's D1 ("memory only"). CEO: no privacy issue.
- App start must open straight on the Home feed from the cache (today it loads forever with no connection), then refresh in the background.
- Small banner between the location chip and the tabs: "No internet connection - offline mode" / "poor connection" (needs a Claude Design reference).
- Offline: read all cached data, read cached messages, edit settings (saved locally, synced when the connection returns).
- Later: scheduled cache cleanup, e.g. every 24h.

**Why:** users must always feel the app is up to date, even on a poor connection.

**How to apply:** tickets are drafted by the PO and CEO creates them via the Codex gate ([[messaging-no-po-tickets]]); the banner ticket waits for design ([[designs-from-claude-design]]). My own additions: cache keyed per account and wiped on sign-out; offline settings sync is last-write-wins; offline message sending and offline creates are out of scope until creates are idempotent.
