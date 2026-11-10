---
name: open-items
description: Open questions, deferred items and owners as of 2026-10-09
metadata:
  type: project
---
> **Note 2026-11-10 (Thebes System).** Jira is the only task reference (`agent/DECISIONS.md` TH-063). Check every item here against the board before acting on it.

- D-042 is still a DRAFT (agent/drafts/D-042-...md), not in DECISIONS.md (last active = D-041). Items marked "?" there unverified: Ops settings scoping by directory; /plan mode through --bg --resume; non-code `exists` check kind not built. Owner: orchestrator/CEO.
- CORRECTION 2026-10-09: supabase list_migrations shows KAN-427 hardening, card_fields, notifications, KAN-436/438 push payload, KAN-439, KAN-440 (and kan441) ALREADY APPLIED live as versions 20261006080725..20261006081855. Only favourites v2 / 20261008* files were separately verified applied by CTO. Below line is STALE:
- (stale) Migration FILES written but not applied live (KAN-427 meetups WP1 hardening, KAN-438, KAN-439, KAN-440, favourites v2 for KAN-437). Applying needs Operations (Memphis)/cto after review; until D-042 section 6 is built the older "no apply_migration on live Supabase" rule holds. Owner: cto + Memphis; CEO for class C.
- KAN-184 (audit-findings, backend): AC2/4/6 production fixes stop at the CEO-only production apply boundary (status/po.md 2026-09-15). Check whether still open.
- Deferred by CEO (KAN-437): Instant booking, venue-rental price split logic, meetup requirement/Women-only tags, mutual-friends note, share counts. Not to be re-litigated; revisit as a joint design session.
- Known board hygiene: po.md is ~437KB (huge); PM should read only its tail + the ledger, not all of it.
- PM stack-activation / capacity: capacity derived by agent/state/capacity.py; do not estimate dates.

## 2026-10-23
KAN-583 follow-up wiring ticket (Content copy, comment 13835) deferred: 583 in Self-review. Create once review closes.

## 2026-10-23 (prio-88436240)
KAN-629 (Google Places UI Kit PoC, Listings 18h) held in To Do: Codex-handoff PoC, needs owner Google billing setup. Promote only on CEO go.

## 2026-10-29 (prio-ecb7738f)
KAN-684 To Do -> Ready (Auth 1h fe, 683 first by order). 683 Ready, 682 Design.

## 2026-10-30 (prio-ce534c68)
KAN-685 To Do -> Ready (Auth 4h backend, one-account conversion; Memphis applies). Rest of non-Done = epics.
- 2026-11-02 ceo-fill-idle-teams: nothing in Backlog/To Do beyond Epics; KAN-712..719 already Ready but blocked; chain links judged real.

- 2026-11-03 (prio-1b2427fe): Ready empty, nothing movable. 756/761/762 parked To Do. Next Ready candidates once blockers finish: 734,748,753,758,771,769,770,757.
- 2026-11-06 pass 3: moved KAN-865 to Ready (blockers Done). 718/866 still waiting; all approved Epics fully cut. Ready ~3.

- 2026-11-07 pass 9: nothing movable; Backlog = KAN-866 (CEO DROP hold) + uncut unapproved Epics only. 879 needs-brief.
