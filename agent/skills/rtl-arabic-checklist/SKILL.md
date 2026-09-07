---
name: rtl-arabic-checklist
description: Checklist for reviewing a Dabbler string or screen for Arabic/RTL correctness — icon direction, EN→AR expansion, number/date formatting, and mixed-direction strings with embedded LTR tokens. Use whenever writing, reviewing, or wiring a user-facing string, before a screen with new copy ships, or when a bug report describes garbled, reversed, or misaligned Arabic text.
---

# Arabic / RTL Checklist

Dabbler ships EN and AR. Arabic is not a translation pass on top of a finished English
screen — it is a second layout mode with its own failure surface. This checklist is the
method for [[content-manager]]'s standing rule: *a screen with English copy and a missing
Arabic key is a broken screen in Arabic, not a partially finished one.*

Run this whenever a string is added or changed, whenever a screen carrying new copy is
about to ship, or whenever a bug report describes Arabic text that reads reversed,
truncated, or garbled.

**Scope**: this is a review checklist for [[content-manager]], who supplies strings and
keys but writes no Dart. Where a fix requires a widget-level or code-generation change,
say so explicitly and hand it to a developer — do not describe it as done.

## Sources

- Apple, *Right to left* (Human Interface Guidelines) — directional icons (arrows, and
  controls whose glyph communicates a direction) should ship a flipped variant for RTL;
  Apple's own icon-mirroring page states this plainly for icon and control assets.
- Google, Material 3 — *Bidirectionality & RTL*
  (`m3.material.io/foundations/layout/understanding-layout/bidirectionality-rtl`, not the
  bare `/foundations/bidirectionality` path, which 404s). Gives the mirror / don't-mirror
  split used in the icon section below: reading order, navigation, progress indicators,
  breadcrumbs, and forward/back icons mirror; media playback controls and scrubbers,
  clocks and clockwise/refresh arrows, musical notes, checkmarks, numerals, logos, and
  code snippets do not.
- Unicode, UAX #9 — *Unicode Bidirectional Algorithm* (`unicode.org/reports/tr9/`). The
  part that matters here: neutral characters (spaces, punctuation) take their direction
  from surrounding text, which is why a Latin word or a `{placeholder}` dropped into an
  Arabic sentence can drag nearby punctuation out of order. The fix the spec recommends
  for new text is a **directional isolate** — `FSI` (U+2068) … `PDI` (U+2069) — wrapped
  around the foreign-direction run, rather than the older embedding/override controls
  (`LRE`/`RLE`/`LRO`/`RLO`), which affect surrounding text more strongly and the spec
  itself flags as legacy.

**Not verified beyond this**: I fetched the Apple and Material URLs directly and both are
client-rendered — the fetch returned only the page `<title>`, no body. The icon
mirror/don't-mirror list above and the Apple icon-flip statement come from search-indexed
snippets of those same pages, not a full read of the rendered page. Treat the *source and
URL* as confirmed, the *exact wording* as unconfirmed. UAX #9 fetched in full; that
section is a direct read.

## The checklist

### 1. Icon direction

Ask, per icon: does this glyph encode a reading-direction or navigation meaning, or is
it direction-neutral?

- **Mirror**: back/forward chevrons and arrows, breadcrumbs, progress bars, sliders,
  "continue" arrows, icon+label pairs where the icon sits before the label.
- **Do not mirror**: play/pause/scrub controls, clock faces, refresh/redo (clockwise)
  arrows, checkmarks, musical notes, numerals, logos, code snippets.

**Flutter mechanism**: `Icon(icon, matchTextDirection: true)` mirrors the glyph
horizontally when `Directionality.of(context)` is `TextDirection.rtl` — it does not
mirror by default. A grep of `lib/` found 9 files using directional icons
(`arrow_forward` / `ChevronRight` / `arrow_back_ios` family:
`lib/features/location/presentation/widgets/home_location_bar.dart`,
`lib/features/auth_onboarding/presentation/screens/landing_screen.dart`,
`lib/features/auth_onboarding/presentation/screens/email_input_screen.dart`,
`lib/features/profile/presentation/widgets/profile/danger_zone_section.dart`,
`lib/features/profile/presentation/widgets/profile/profile_completion_indicator.dart`,
and 4 more) and zero files setting `matchTextDirection` or otherwise reading
`Directionality`/`TextDirection`. **Not verified**: whether any of these actually renders
wrong in AR — I did not run the app in the AR locale. Flag it to a developer to check;
content-manager does not fix widget code.

### 2. Text-expansion ratio EN → AR

Arabic strings in this codebase run shorter or comparable in character count to their
English source (spot-checked `app_en.arb` / `app_ar.arb` pairs — e.g.
`auth_welcome_get_started_subtitle`: "Create an account or log in" vs "أنشئ حساب أو سجّل
دخولك"), but character count is not the risk — Arabic script renders wider per
glyph and carries obligatory diacritical/connector width most Latin fonts don't budget
for. Any string going into a fixed-width or single-line component needs the AR string
checked against the same width budget as the EN one, not assumed safe because it "looks
shorter." Per [[content-manager]]'s role file: *length is a design constraint, not a
preference* — ask `cxo` for the component's budget before writing a string meant to fit
one.

### 3. Number and date formatting

**Finding, this codebase**: interpolated counts (`post_card_expires_in_days`: "Expires
in {n}d" / AR "بيخلص بعد {n}ي", `time_minutes_ago`, `activity_participants_count`, etc.)
are plain `.arb` placeholders. The generated Dart (`app_localizations_ar.dart`) just
substitutes `n.toString()` — this always emits Western (0–9) digits, in both locales,
because nothing routes the value through `intl`'s locale-aware `NumberFormat`. That is a
legitimate, common choice for Arabic UI (many apps deliberately keep Western digits for
scannability against Eastern Arabic-Indic ٠١٢), but here it looks like it was never
decided — reported, not fixed. Whoever owns the `.arb` pipeline should confirm Western
digits are the intended choice for AR; if Eastern Arabic-Indic digits are ever wanted,
plain `{n}` interpolation cannot produce them — it needs `NumberFormat(locale: 'ar')`
around the value before it reaches the string.

**Dates**: no date-formatting string in the sampled `.arb` pairs uses raw interpolation
of a formatted date; flag any future one the same way — a hardcoded `MM/DD/YYYY` pattern
baked into a string is wrong in both locales, and Arabic locales commonly expect
day-month-year with Western digits, not the US month-first order.

### 4. Mixed-direction strings with embedded LTR tokens

This is the UAX #9 problem in the checklist above, and it's already present in the app.
**Finding**: `auth_welcome_google_error` — EN "Could not sign in with Google: {error}",
AR "مقدرناش ندخل بـ Google: {error}" — has an Arabic sentence carrying a bare Latin word
("Google") and an unisolated placeholder. Same shape in `otp_verify_error_prefix`,
`set_password_error_prefix`, `identity_verify_service_error`, `notif_error_prefix`
(all "Error: {error}" / "خطأ: {error}"-style AR strings). Because the `{error}` payload
is frequently an English exception message, the run of Latin text sitting mid-sentence
in an RTL string is exactly the case UAX #9 says can drag trailing Arabic punctuation
(the colon, any following text) out of visual order.

**What content-manager can do without touching code**: wrap the embedded run in the
`.arb` string itself with Unicode directional isolates — `⁨` (FSI) before the
placeholder, `⁩` (PDI) after — e.g.
`"مقدرناش ندخل بـ Google: ⁨{error}⁩"`. This is a change to the string content
content-manager already owns, not a widget change; it does not require a developer.
**Not verified**: I have not rendered this in the app to confirm the isolate marks fix
the visual symptom in Flutter's text layout — the UAX #9 recommendation is general-purpose
text-layout guidance, not Flutter-specific, and I could not find a Flutter API that
applies it automatically to interpolated `.arb` strings. If the isolate marks don't
resolve a specific visual bug, escalate to a developer rather than guessing further.

**Separately, not a mixed-direction bug but the same family**: `email_input_hint`
("email@domain.com") is pure-LTR content that will render inside a field whose ambient
direction is RTL in the Arabic locale (Flutter's `TextField` inherits
`Directionality.of(context)` unless overridden). Fields whose content is *always*
LTR — email, phone number, URL, ID/reference-number fields — should have their input
widget's `textDirection` forced to `TextDirection.ltr` regardless of locale, or the caret
and hint-text alignment can land on the wrong side in AR. **This is a widget-level fix,
not a string fix** — flag it to a developer; content-manager cannot set it from the
`.arb` file alone.

### 5. Plural forms (found during this audit, not in the original four items — kept because it broke a rule from item 3's family)

**Finding**: `profile_post_count` and `profile_follower_count` use ICU plural syntax in
both `.arb` files but define only `one` and `other` categories. Arabic's CLDR plural
rule has six categories — zero, one, two, few, many, other — and the generated code
(`app_localizations_ar.dart`) only receives `one`/`other`, confirmed by reading the
generated `Intl.pluralLogic(...)` call, which is passed just those two named arguments.
Every Arabic plural category between (0, 2, 3–10, 11–99) silently falls through to
`other`. This is a genuine gap, not a hypothetical — reported per the brief's
instruction, not fixed; `.arb` files are outside content-manager's write path per
`CONTRACT.md` §3.

## What this checklist could not translate from Apple/Material into Flutter

- Apple's and Material's icon-mirror guidance is stated as design intent for their own
  platform's icon sets (SF Symbols / Material Symbols); neither says anything about
  Flutter's `matchTextDirection` flag by name. The mapping to `matchTextDirection` above
  is my translation of platform-general intent into the one Flutter mechanism that
  implements it — verify a given icon actually mirrors correctly once `Directionality`
  is RTL rather than assuming the flag alone is sufficient (`matchTextDirection` mirrors
  the whole glyph; an icon whose meaning depends on internal asymmetric detail, per
  Material's own "mirror only if direction matches other RTL elements" caveat, still
  needs a human look).
- Neither source addresses `.arb` / ICU MessageFormat plural-category completeness at
  all — item 5 above is drawn from CLDR's plural-rules data and the visible behavior of
  this codebase's generated Dart, not from Apple or Material.
- I could not find Flutter-specific guidance for whether Unicode isolate marks
  (`⁨`/`⁩`) actually survive `.arb` → generated-Dart → widget round-trip
  unmangled. They are plain Unicode code points in a Dart string literal, so there is no
  obvious reason they wouldn't, but I have not run this in the app — say so plainly
  rather than presenting it as confirmed.
