# frontend-5 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/frontend-5.md`. This file is a work log, not a rule source.

## 2026-09-08 — KAN-151 executed (pt.B), Front-end → Self-review

Claim `frontend-5` on KAN-151, continuation gate passed. Ready (10008) → Front-end (8) on
entry, Front-end → Self-review (6) on exit, route `self`. Evidence comment 10762. Commit
`931d4c8` on `Canary`, unpushed (3 ahead of `origin/Canary`). No push, no PR. **1 sitting of 1
— no rework.**

**Read the amended ticket first**, per the brief; description and AC8 as `po` wrote them in
comment 10760 — no disagreement with the dispatch prompt.

Four classes out of `notifications_screen_v2.dart` (1617 → 1153 lines) into
`presentation/widgets/`: `UnreadCounterRow`, `NotificationRow`, `AvatarChip`, `NotifEmptyState`.
AC8 renames `Chip` → `NotifChip` and `SectionHeader` → `NotifSectionHeader`, three call sites
total. `flutter analyze --no-pub --no-fatal-infos` 0 errors / 0 warnings / 55 issues;
`flutter test` 106 passed. Both unchanged from `dcc6dc9`.

**Three private helpers had to move with `NotificationRow`, and that was not in the ticket.**
`_followBackVisibleProvider`, `_visualForKind`, `_formatTime` — each grepped and each with
exactly one consumer, the class being moved. Left behind they become `unused_element` warnings
and AC6 fails. **The rule this taught: extracting a class means extracting everything only that
class uses, and the way you know is grep before the cut, not analyze after it.** Checking the
surviving imports the same way found two more (`notification_localizer`, `profile_providers`)
that had to leave with them, and confirmed the rest still had live consumers.

**BSD `sed` silently dropped `\b`.** `s/\bclass Chip extends.../` matched nothing on macOS; the
constructor and call site renamed, the two *declarations* did not. Caught by grepping for the
NEW names before running any gate. **A rename is verified by grepping for the new name, never
by the analyzer** — a latent collision raises no error until the bare name is referenced, which
is the whole reason AC8 exists. On macOS use `^class Chip` or `grep -E`, not `\b`.

**AC8's own grep command cannot pass as written, and I did not treat that as a failure.**
`grep -rn "\bChip(\|\bSectionHeader(" lib test` still matches three unrelated Material `Chip(`
constructions and `app_card.dart:69`'s `SectionHeader` — the *other side* of the collision the
ticket deliberately preserves — and does NOT match `NotifChip(`, since `\b` finds no boundary
inside it. Reported to `po` as a wording defect with the substitute check that does hold
(`grep -rn "\bChip\b\|\bSectionHeader\b" lib/features/notifications/` → nothing). **Writing a
verification command into an AC is writing a claim; this one was never run before it shipped.**

KAN-152's six classes untouched — `git diff -U0` shows no hunk in their range, only a line-number
shift. It unblocks on release of the host file.

## 2026-09-08 — KAN-152 executed (pt.C of the notifications_screen_v2 split)

Owner: `frontend-5` (Pakhet). Claim 2026-09-08T17:47:31Z, revision 6.
Commit `b60e7cf` on `Canary`, unpushed. 1 sitting, ceiling 1 — not exceeded.

Extracted 6 classes to `lib/features/notifications/presentation/widgets/`, made
public: `ActivitySummaryCard` (activity_summary_card.dart, 189),
`SparklinePainter` (sparkline_painter.dart, 64), `ActivitySearchRow`
(activity_search_row.dart, 69), `ActivityRow` (activity_row.dart, 231),
`ActivitySecurityFooter` (activity_security_footer.dart, 74),
`ActivityEmptyState` (activity_empty_state.dart, 45).

Private helper that moved: top-level `_activityVisual` travelled with
`ActivityRow`, its single consumer — same pattern as KAN-151's three helpers.
Four imports removed from the screen (app_theme, design_tokens, notif_pill,
notif_visual) after their consumers left; without that, 4 unused_import
warnings and AC6 fails. `super.key` on the five widgets, not on
`SparklinePainter` (a CustomPainter, not a widget).

AC8 measured: `notifications_screen_v2.dart` is **537 lines** (1,153 -> 537;
2,018 at chain start). team-lead-5 estimated ~554. Still 37 over the 500-line
ceiling — flagged to `po` in the ticket; no fourth ticket opened, that is po's
call. Remaining bulk is `_handleNotificationTap` and its route helpers.

Gates at b60e7cf: analyze 0 errors / 0 warnings / 55 issues; flutter test 106
passed; test/features/notifications 21 passed. All on baseline.

Transitions, both mine: Ready (10008) -> Front-end (10046) via transition 8;
Front-end -> Self-review (10044) via transition 6. Route `self`, policy-derived.
No schema/money/security/contended-surface characteristic discovered.
`lib/app/routes/notification_routes.dart` untouched (AC4).

### 2026-09-08 — KAN-152 closed

`po` passed the acceptance gate (comment 10766): all 8 ACs verified
independently, the moved private helper and the four removed imports both
accepted as necessary. Ruled separately that AC8's 37-line overage needs **no
fourth ticket** — CONVENTIONS.md §8 bars widening past the bounded scope once
legitimately inside the file, and DECISIONS.md 013 / T-010 make the 500-line
figure a non-blocking budget. `notifications_screen_v2.dart` stays at 537 lines.

Route was `self`, so the close is mine as review owner: Self-review (10044) ->
**Done (10007)** via transition **41**. Status id read back after the call per
`G-018` — `10007`, the canonical Done, not legacy 10005/10010/10006.

KAN-147 (pt.A, `dcc6dc9`) / KAN-151 (pt.B, `931d4c8`) / KAN-152 (pt.C,
`b60e7cf`) all Done. Chain complete: 2,018 -> 1,617 -> 1,153 -> 537 lines.
Four commits sit unpushed on `Canary`; pushing is not this seat's call.
Ownership of KAN-152 released.

### 2026-09-08 — KAN-152 ownership released

Verified `po`'s acceptance comment **10766** is genuinely on the ticket before
reporting the close — read back via `listJiraIssueComments`, content matches
what `po-gate-4` and `team-lead` described. **Recorded honestly: I made the
Self-review -> Done transition on `po-gate-4`'s message alone, before
`team-lead`'s verify-first instruction arrived. The verification came after the
act, not before it. The outcome is right; the order was not.**

`po` also caught my AC3 call-site line numbers being 4 high (I reported
198/200/217/378/398, actual 194/196/213/374/394) — I grepped them before
removing the four unused imports and did not re-grep after. Immaterial to the
verdict, but it is the same class of error as the pt.B `sed` near-miss: a number
reported from a pre-edit read.

Release: `store.release("KAN-152", "frontend-5", 8, <ref>)`. Revision read
immediately before the call (8) and after (9); `ownership` is now `None`.
First attempt was refused by `validate.py:153` — my `release_ref` was 456 chars
against `MAX_REF_LEN = 300`; reference fields hold identifiers, not evidence
bodies. Refusal was clean: revision stayed 8, ownership unchanged, nothing
half-written. Re-ran with a 205-char identifier ref.

I hold no work item. Not starting anything new.

---
## 2026-09-09 — KAN-148: delete 4 orphaned game-composer step screens

Owned (revision 2, continuation gate passed). SELF validation route.

Re-measured the "zero importers" claim myself rather than inheriting it:
`git grep` for each filename and each class name
(PlayerInvitationStep/ReviewConfirmationStep/SportFormatStep/VenueSlotStep)
across lib/ and test/, excluding the file's own former path — zero hits for
all four, both by filename and by class name. Checked each file's own
imports too: none of the four imports another of the four. Confirmed the two
files the ticket named as the directory's only external importers
(play_places_routes.dart, sports_library_screen.dart) reference only
game_detail_screen.dart / game_composer_screen.dart, never a step file.

LOC re-measured with `wc -l`: 571 + 749 + 1179 + 525 = 3024 — matches the
ticket's figure exactly.

Deleted all four files via `git rm`, touched nothing else.
flutter analyze --no-pub --no-fatal-infos: exit 0, 0 errors, 0 warnings, 55
infos (was 56 in the documented baseline — consistent with removing dead
code).
flutter test: exit 0, 106/106 passing.

Process anomaly (flagged to team-lead-2 and in the Jira comment): this
Dabbler/dabbler-code checkout on Canary is shared by multiple concurrent
agent sessions committing to the same working tree/index. Before I could
make my own commit, my staged `git rm` was swept into a concurrent agent's
KAN-156 commit (`a23c6d92f32c7f4f8fc8541e5cc1ce0cc5c8394a`, local only, not
pushed) alongside its own unrelated change. Verified via `git show --stat`
that the deletion inside that commit is exactly the four files I deleted.
Did not attempt to reset/rebase to separate it out — HEAD and the staged
index were observed changing between consecutive `git status` calls with no
action from me, meaning other agents were actively committing/resetting in
real time; a rewrite in that environment risks destroying concurrent
in-flight work. Reported the actual SHA and the misattribution plainly
rather than fabricating a clean KAN-148 commit. Did not push, did not
transition the Jira ticket, did not touch agent/state/runtime.

## 2026-09-09 — KAN-144 PEER review (cycle 1), reviewer not executor

Resolved review_owner for KAN-144 (PEER route, CEO-authorised). Executor was
frontend-4. Reviewed the published source at Canary b978647, not a local tree.

Verdict: PASS. All five acceptance criteria met; nothing NOT VERIFIABLE.

Re-derived rather than accepted: reference search for FeatureFlags.squads
across lib/, test/ and the whole repo (no matches, exit 1); the quoted 'squads'
key search (only squads-domain SQL, never the flag); git show --stat 7856b5e
(exactly feature_flags.dart + main.dart, 1 insertion / 3 deletions); the
history-normalisation claim, by tree hash — 7856b5e^{tree} == 61ae33e^{tree}
== a780e13, so the SHA change is content-identical as the orchestrator note
said; flutter analyze --no-pub --no-fatal-infos exit 0, 0 errors / 0 warnings
/ 55 infos; flutter test exit 0, 106/106.

Runtime consequence checked in source, not taken from the report: rpc_track_event
(baseline_schema.sql:16086) inserts an untyped jsonb properties column with no
key schema, and KAN-109's anon rule keys off _event_name = 'flags_snapshot',
not payload contents. Dropping the squads dimension therefore has no failure
mode — it is exactly the intended P-035 effect, and nothing else changes
behaviour. Read P-035 first-hand at DECISIONS.md:5004-5063; the commit executes
it exactly.

Scope call I was asked to make: the untouched squads repository, provider
wiring, session_cleanup invalidation, squadsTable constant and EN/AR copy are
correct to leave. The flag was analytics-only and gated nothing, so no code path
branched on it and no inconsistency is left behind. The open in/out scope
question is po/cpo's, not this ticket's. The "these 5" -> "these 4" comment fix
is inside a permitted file and is now factually accurate (4 flags remain in the
ANALYTICS-ONLY block); the rework trigger is files touched beyond the two named,
and no third file was touched.

Noted for cpo/pm, outside this ticket: P-035 still reads "PROPOSED — awaiting PO
ruling" in DECISIONS.md although its ticket has been executed.

Posted the review as Jira comment 10837 on KAN-144. Did not transition the
ticket, did not mark it Done, wrote no product code, committed and pushed
nothing, did not touch agent/state/runtime.

## 2026-11-03 — KAN-784 (partial; blocked on allowed paths)
- contributor_visitor_test.dart: `_now` fixed at 2026-11-01 (line 66) went stale; now `DateTime.now()`. 22/22 pass. Commit 5921c9313176d50da0594869b0bb73e19ff0933f on alpha-deir-el-bahari (worktree kan-784), not pushed.
- home_mirror_measure_test.dart "header, upcoming, tabs, post" LTR+RTL still fail: home_measure_cases.dart:236-241 hardcodes `find.text('OCT')` while home_measure_fixtures.dart:54 dates games from `DateTime.now()`. Fix needs one of those two files (forbidden in brief). Returned to caller for scope ruling.
- 2026-11-03 follow-up, ruling (a) tried: month finder derived from frameGames().first via DateFormat('MMM','en'). Finder now matches but the rect fails: design 16.66 wide is the "OCT" glyph width; "NOV" lays out 19.76 (LTR delta (-1.55,0.50,3.10,0); RTL (-0.47,0,-0.92,0) vs pinned (-0.88,0,-1.75,0)). 4-file run +78 -2. Reverted, not committed. Needs fixture month pinned to October (option b) — returned for ruling.
- 2026-11-03 ruling (b) done: homeNowProvider (home_providers.dart, defaults DateTime.now) read by home_upcoming.dart countdown; home_measure_fixtures.dart frameNow = 2026-10-14 10:00:30 + override in pumpFrameHome. All 4 files green, test/features/home 231 pass, analyze 0 warnings. Commit ee38055e93953180afa9d540e0ed1911d64674ed, not pushed. Note: the instant needs nonzero seconds or the floored countdown reads "12h 31m".
