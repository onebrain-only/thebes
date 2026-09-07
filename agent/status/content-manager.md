# agent/status/content-manager.md

**Owner:** `content-manager` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

## 2026-09-06 — no ticket — Arabic/RTL checklist authored (content-manager)
**Agent:** content-manager
**Outcome:** Authored `agent/skills/rtl-arabic-checklist/SKILL.md` — no `disable-model-invocation`, invocable. Covers icon direction (mirror vs. not, mapped to Flutter's `Icon(matchTextDirection: true)`), EN→AR text-expansion risk, number/date formatting, and mixed-direction strings with embedded LTR tokens, per team-lead's brief. Wired into my own reflex table in `agent/roles/content-manager.md` (§SKILL REFLEXES, new row).

Sources actually opened: UAX #9 (`unicode.org/reports/tr9/`) fetched and read in full by me — directional isolates (FSI/PDI) over legacy embeddings is its own stated recommendation. Apple HIG right-to-left (`developer.apple.com/design/human-interface-guidelines/right-to-left`) and Material 3 bidirectionality (`m3.material.io/foundations/layout/understanding-layout/bidirectionality-rtl`) — I fetched both directly myself and both are client-rendered; the fetch returned only the page `<title>`, no body. The icon mirror/don't-mirror list and Apple's icon-flip statement in the skill come from search-indexed snippets of those same URLs, not a full read — the skill says this plainly and marks exact wording unconfirmed. `analyst` had separately confirmed both URLs resolve (not 404) and that the earlier `/foundations/bidirectionality` path does not.

Read `lib/l10n/app_en.arb` and `lib/l10n/app_ar.arb` in full, plus `lib/l10n/app_localizations_ar.dart`, before writing — the checklist cites real strings, not hypothetical ones. Found and reported (not fixed, per `CONTRACT.md` §3 — outside my write path):
- `profile_post_count` / `profile_follower_count` define only ICU `one`/`other` plural categories; Arabic's CLDR rule has six (zero/one/two/few/many/other), confirmed by reading the generated `Intl.pluralLogic(...)` call, which only receives two named args. Every count in 0, 2, 3–10, 11–99 falls through to `other`.
- `auth_welcome_google_error`, `otp_verify_error_prefix`, `set_password_error_prefix`, `identity_verify_service_error`, `notif_error_prefix` embed a bare Latin word or an `{error}`/`{message}` placeholder (often an English exception string) mid-Arabic-sentence with no directional isolation — the exact UAX #9 failure mode. Proposed fix is a `.arb`-level one I can make myself (wrap the placeholder in FSI/PDI marks) but have not applied it — a proposal in the skill, not yet an edit.
- Interpolated counts (`post_card_expires_in_days`, `time_minutes_ago`, etc.) always render Western digits in AR via raw `n.toString()` — flagged as an undecided choice, not necessarily wrong.
- `email_input_hint` ("email@domain.com") is pure-LTR content that will sit in an RTL-direction field in the AR locale — flagged as a widget-level fix (`TextField(textDirection: TextDirection.ltr)`) for a developer, not something I can set from the `.arb`.

Grepped `lib/` for icon and inset patterns: 9 files use directional icons (`arrow_forward`/`ChevronRight`/`arrow_back_ios`), zero use `Directionality`/`TextDirection`/`matchTextDirection`; `EdgeInsetsDirectional` appears once vs. 30 uses of `EdgeInsets.only(left:/right:)` — noted in the skill as a developer-facing signal, not something I fixed (not code I own).

Could not translate into Flutter: neither Apple nor Material names Flutter's `matchTextDirection` API — the mapping from their platform-general icon guidance to that flag is my own translation, stated as such. Neither source addresses `.arb`/ICU plural-category completeness at all (that finding came from CLDR data and the generated Dart, not from either cited source). Could not confirm Unicode isolate marks survive `.arb` → generated-Dart → widget rendering unmangled in this app — I have not run the app in the AR locale to check any of these findings visually.
**Evidence:** `/Users/moatazmustapha/Desktop/Thebes/agent/skills/rtl-arabic-checklist/SKILL.md`, `/Users/moatazmustapha/Desktop/Thebes/agent/roles/content-manager.md` (§SKILL REFLEXES), `Dabbler/dabbler-code/lib/l10n/app_en.arb`, `Dabbler/dabbler-code/lib/l10n/app_ar.arb`, `Dabbler/dabbler-code/lib/l10n/app_localizations_ar.dart`, `unicode.org/reports/tr9/`.
**Not verified:** exact body text of the Apple and Material pages (title-only fetch; content taken from search snippets of the same URL) · whether any flagged icon actually renders wrong in the AR locale (not run in-app) · whether the proposed FSI/PDI fix resolves a real visual symptom in Flutter's text layout.
**Next:** none from me — widget-level items (icon `matchTextDirection`, email field `TextDirection.ltr`) and the plural-category gap are developer/`.arb`-owner work; I proposed but did not apply the FSI/PDI wrap.

## 2026-09-06 — no ticket — Skills audit (content-manager)
**Agent:** content-manager
**Outcome:** Read-only survey per team-lead's four-question audit. Read `agent/roles/content-manager.md`, `agent/skills/AVAILABLE.md`, and opened the full SKILL.md bodies for `marketingskills/aso`, `copywriting`, `copy-editing`, `emails`, `onboarding`, `signup`, `paywalls`, `offers`. Reply sent to team-lead via SendMessage with four numbered answers: (1) skills already reached for — `storybrand-messaging`, `positioning-statement`, `made-to-stick`, `contagious`, `writing-for-agents`, plus newly-claimed `aso`, `copy-editing`, `emails`; (2) none of the four named skills are dead weight; (3) claiming `aso` (direct fit, store listings), `copy-editing` (direct fit, revising existing strings), `emails` (direct fit, notification/lifecycle copy is explicitly owned) — partial/borderline on `copywriting` (overlaps `storybrand-messaging`, mostly marketing-site shaped), `onboarding`/`signup`/`paywalls` (the copy slice is mine, the flow/conversion decision is `pm`/`cxo`), rejecting `offers` (pricing/offer construction is a `cpo`/`pm` decision, not copy) and leaving `press-release`/`voice-of-customer-miner` (pm-skills) to `pm` to claim or not; (4) real gap confirmed — no installed skill, repo or plugin, addresses Arabic copy or RTL layout consequence; the role file already carries this as prose (own section), not as a skill. No public resource was verified this session (no browsing done) — named only as things I know exist and have not confirmed current: Apple HIG right-to-left guidelines, Google Material bidirectionality guidance, W3C Arabic/Persian/Urdu layout requirements.
**Evidence:** `agent/roles/content-manager.md`, `agent/skills/AVAILABLE.md`, `/Users/moatazmustapha/.claude/plugins/marketplaces/marketingskills/skills/{aso,copywriting,copy-editing,emails,onboarding,signup,paywalls,offers}/SKILL.md`
**Not verified:** did not open `press-release` or `voice-of-customer-miner` SKILL.md bodies (judged from description only, deferred to `pm`). Did not verify the named external RTL/Arabic resources are current or still at those names — flagged as unconfirmed in the reply.
**Next:** none — survey only, no work claimed.
