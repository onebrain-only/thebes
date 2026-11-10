---
name: epic-cut
description: Cut a CEO-approved Epic into small tickets that several teams build at the same time without touching the same files, then prove the cut with `cut_plan check` before any ticket is written. Use on every `ready-below-target` or `serial-chain` priority item, whenever an approved Epic needs tickets, whenever Ready tickets sit waiting on Blocks links, and whenever a ticket is bigger than one screen or one function plus its test. D-049, CEO 2026-11-02.
---

# Epic cut

The CEO's target is a ticket finished every 10 minutes across five code teams (D-049). Coding
is not the bottleneck. These are:

- a team with nothing startable in Ready;
- a chain of Blocks links that only records an order;
- two tickets fighting over the same file.

Your cut decides all three. A good cut has a small first wave that unblocks a wide second wave.
No two parallel tickets share a file. Every Blocks link names the code or data it waits for.

**Scope fence.** You cut only Epics the CEO already approved. A ticket that adds scope the Epic
does not contain needs his order: list it under `not cut: new scope` and stop there. Supporting
tickets inside an approved Epic need no order (D-046).

## 1. Read before you cut

1. **The Epic, its children and their comments** in Jira. If the Epic carries a design link,
   open it now and cut from what it shows. Never cut from a copy or from memory.
2. **The code that exists.** Grep the feature folder (`Dabbler/dabbler-code/lib/features/<x>/`)
   and name the real files each piece will touch. A path you guessed is not a surface: the
   checker treats it as true, and so will claimability.
3. **Hotspots.** Run `python3 -m agent.execution.cut_plan hotspots`. These are the files most
   recent work touched. Measured 2026-11-02:
   - `app_en.arb` and `app_ar.arb`: about 140 commits each in 30 days.
   - `app_router.dart`: 25 commits.
   - The big screens: home, profile, games, the composers.

   A hotspot edited by two parallel tickets is a merge conflict on `staging`.

## 2. The four shapes that make an Epic parallel

**a. Contract first (wave 1, one ticket, ≤40 min).**
- It holds the domain model, the repository interface, and a stub that returns fixed data.
- It holds the additive migration, if one is needed.
- The frontend builds against the stub while the backend fills the real implementation.
- Everything under `lib/core/` or `lib/data/` belongs here. Those two prefixes are governed
  shared surfaces: any two tickets inside either one collide, whatever the file
  (`agent/state/policy.py` `SHARED_PREFIXES`).
- Put new code in the feature slice (`lib/features/<x>/data|domain`) wherever the
  conventions allow.

**b. Strings first (wave 1, `kind: strings`, the `content` capability).**
- One ticket adds every EN and AR key the Epic needs.
- Screen tickets wait on it and only read the keys, so they never edit an `.arb` file.
- The generated `app_localizations*.dart` files never count as a collision; the checker drops
  them.

**c. Wiring once (wave 1 or 2).**
- One ticket adds the Epic's routes behind its `FeatureFlags` flag and its providers.
- That keeps `app_router.dart` and `providers.dart` to one editor per Epic.

**d. Fan out (wave 2).**
- **One screen** = one file under `presentation/screens/`, its widgets, its widget test, and
  click-by-click test scenarios.
- **One function** = one repository method, use case or edge function, plus its test.
- Each one is 30-50 minutes and touches its own files.

**Destructive steps go last**, in their own ticket: a column drop or a rename that breaks old
readers. Teams never write DROP; that ticket goes to Memphis.

## 3. A Blocks link must pass one test

> If the blocker were never merged, would this ticket fail to compile, or would its test fail?

- **Yes:** keep the link, and write the reason in the plan, e.g. `"T0": "reads table events_v2"`.
- **No:** there is no link.

Being in the same Epic, being phase 2 of something, or "it reads better in this order" are
not reasons. A real link no longer costs an Alpha wait. Thebes starts the dependent on the
blocker's checked commit and holds only its integration (D-049). So keep the true links and
drop the rest without worry.

## 4. Write the plan, prove it, then hand it over

Write `$CLAUDE_JOB_DIR/tmp/<EPIC>-cut.json`, or the session's tmp folder:

```json
{"epic": "KAN-708",
 "tickets": [
  {"id": "T0", "summary": "Event contract: model, repository interface, stub",
   "component": "Listings", "capability": "backend", "kind": "contract",
   "surfaces": ["lib/features/explore/domain/event.dart",
                "lib/features/explore/data/event_repository.dart"],
   "blocked_by": {}, "estimate_min": 35, "tcs": 0},
  {"id": "T1", "summary": "Events list screen", "component": "Listings",
   "capability": "frontend", "kind": "screen",
   "surfaces": ["lib/features/explore/presentation/screens/events_screen.dart",
                "test/features/explore/events_screen_test.dart"],
   "blocked_by": {"T0": "renders Event from EventRepository"}, "estimate_min": 45, "tcs": 4}
 ]}
```

Then run `python3 -m agent.execution.cut_plan check <file>`.

- **Errors exit 1.** Fix every one: a collision, an unexplained link, a ticket over 50
  minutes, two screens in one ticket, a screen or function without a test file, a screen
  without scenarios, missing surfaces, a cycle.
- **Warnings:** fix each one, or answer it in one line in your handover. These are an
  ordering-only link, a hotspot edit, an `.arb` edit outside the strings ticket, and a first
  wave narrower than five teams.
- **The output** gives `waves` (who starts now, who starts next) and `critical_min` (the
  longest chain in minutes). Aim for a first wave of five or more and the shortest critical
  path.

**Handover.**
1. The `po` of the project writes each ticket from the plan, as written. Every ticket carries:
   - the acceptance criteria;
   - a **Planned surfaces** list;
   - the Blocks reason;
   - click-by-click testing scenarios with the expected result;
   - the domain component;
   - a `cap:<capability>` label;
   - the Original estimate.
2. You set the Blocks links and move tickets into Ready in wave order.
3. Keep at least **10 startable** tickets in Ready. Log the cut with `pm_ledger add`.

## 5. Breaking an existing chain (`serial-chain`)

1. For each waiting ticket the priority item lists, read the ticket and its blocker. Apply the
   test in §3.
2. Remove every link that fails it. Write a comment on the ticket naming the test and the
   reason.
3. If a link is real but the dependent is big, cut the part that does not need the blocker
   into its own ticket, and let it start now.

## Anti-patterns

- **Horizontal layers:** "all backend, then all frontend". The frontend waits a whole Epic.
  Put the contract first instead.
- **Phase tickets:** "P2", "P3", "polish", "wire-up later". These are an order, not work.
- **A ticket that says "and"** across two screens or two functions. Split it.
- **Two tickets editing `lib/data/` or `lib/core/` in the same wave.** They serialize anyway,
  and the checker says so.
- **Surfaces copied from the Epic's description** instead of read from the code.
