---
name: chrome-second-tab-contention
description: Verifying a second, independently-triggered flutter run -d chrome scenario (e.g. a failure path) via a manually-navigated browser tab can hang indefinitely with zero console signal when other stale flutter/chrome processes are still running on the machine.
metadata:
  type: feedback
---

When two `flutter run -d chrome` web sessions run concurrently on this machine (mine plus
leftover stale sessions from an earlier/different agent run), navigating my own
extension-controlled Chrome tab to the second session's URL can hang indefinitely
mid-DDC-compile (stuck at "DDC is about to load N/N scripts", never rendering, zero
console errors) even though all network requests return 200. This happened validating
KAN-196's failure path (2026-09-12) — the first session (happy path) loaded fine in ~10s,
the second (deliberately-broken `.env`) never rendered after 2+ minutes.

**Why:** likely CPU/resource contention from multiple concurrent dart/chrome processes,
some orphaned from prior sessions (~19h old PIDs found still running). Not a code
regression — the terminal log for the flutter-managed Chrome instance already showed the
expected exception (`App bootstrap failed: ...`) fires correctly.

**How to apply:** before spending more than a few checks waiting on a stuck screenshot,
check `ps aux` for other `dartvm ... flutter_tools.snapshot run` processes and stale
Chrome instances holding old ports. If present and not mine to kill, don't keep waiting —
fall back to: (1) the terminal log line proving the code path executed, (2) reading the
source to confirm the logic is unconditional/correct, (3) running any existing unit/widget
test that covers the same rendering behavior. Report the browser check as inconclusive
(not negative) rather than treating a stuck tab as a finding, and say explicitly in the
verdict that the visual confirmation for that specific path was blocked by environment
contention.

See [[qa]] status log entry 2026-09-12 KAN-196 for the full incident.
