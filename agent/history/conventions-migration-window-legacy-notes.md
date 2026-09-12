> **HISTORICAL / REFERENCE ONLY — preserved 2026-09-10.**
> Salvaged from an uncommitted `docs/CONVENTIONS.md` diff found in
> `~/Desktop/Thebes/Dabbler/dabbler-code` (an unregistered legacy clone) during Desktop
> single-root cleanup. Neither section below exists in Canonical's
> `Dabbler/dabbler-code/docs/CONVENTIONS.md`. **This file does not edit Product code or make
> either rule active doctrine** — `CONVENTIONS.md` is owned by `cto`; only `cto` may accept,
> adapt, or reject this into the live document. Preserved verbatim here so the content is not
> lost when the legacy clone is deleted.

---

## 1. Migration window rule ("author and apply in one sitting") — CONFLICTS WITH CURRENT GOVERNANCE, NOT ACTIVE

Originally added 2026-09-07 by `cto` (`T-067`) to the live `docs/CONVENTIONS.md` §6, after
`team-lead-4` found a third unrecorded same-function migration collision
(`trgfn_payment_to_ledger`: `KAN-128`, `KAN-131`, `KAN-140`). Its operating premise is that
migrations are being authored against a live catalogue and applied normally.

**Current production migration governance takes precedence and supersedes this premise.**
`Dabbler/dabbler-docs/DECISIONS.md` T-068 (2026-09-10, `cto`) records a CEO migration safety
freeze: the remote ledger is authoritative for what ran, the repo is authoritative for nothing,
and `supabase db push` is barred entirely until the repo is rebaselined. A rule about *how* to
safely apply a migration is moot while applying migrations is barred outright — so this text is
kept as historical context only, not reactivated, until `cto` clears the freeze and re-evaluates
whether the rule still applies as written.

Original text, verbatim:

> **Two pending migrations may target the same function. Ordering between them is not the
> control — freshness of the authored text is.** The live-catalogue rule above already makes
> whoever authors second correct by construction, *whichever* order they land in, because the
> second author reads a catalogue that already contains the first change. What it does not
> survive is a **gap**: text authored from the catalogue, then left sitting while a different
> migration replaces the same function, then applied. At that moment the authored body is a
> snapshot of a function that no longer exists, and applying it reverts the change that landed
> in between — silently, with no error, exactly as the table above describes.
>
> **So the rule is about the window, not the queue: author and apply in one sitting, and if any
> migration touching the same function applies between your authoring and your apply, re-read
> `pg_get_functiondef` and re-author.** A ticket does not need to enumerate which other pending
> tickets touch its function — that duty scales with the square of the backlog and is precisely
> what goes unrecorded. It needs the author to check the catalogue is still the one they wrote
> against, which is one query and answers for every collision at once, including the ones nobody
> knew to list.
>
> Where a ticket *does* state an ordering (`KAN-131`, `KAN-140` AC5), that is a scheduling fact
> for the lead, not the thing keeping the body correct. Do not read a ticket that is silent on
> ordering as therefore unsafe.

---

## 2. `prosrc` comment-stripping rule (UNNUMBERED draft) — NOT FOUND IN CONFLICT, NOT YET ADOPTED

> **The number `§12j` is TAKEN and this draft is not it.** This section originally called the draft
> below "§12j". As of 2026-09-11, `CONVENTIONS.md` §12j is a **different, committed rule** — "Live
> state resembling a migration's target is not evidence the migration partly ran" (generalising
> T-073, committed at `0e9f066`). The draft below was never adopted and holds **no section number**;
> if it is ever adopted it needs a fresh one. Corrected in place rather than silently renumbered,
> because the original label is what a reader of the git history will see. Found by `backend-3`
> while checking a section number during the 2026-09-11 burn-down.

A second, separate addition existed in the same uncommitted diff (beyond what this cleanup task
named): a draft, "Strip comments from `prosrc` before pattern-matching it." No governance
conflict was found for this one — it is a code-review/verification technique, not a migration
application rule — but it is likewise not present in Canonical's `CONVENTIONS.md` and was never
committed anywhere. Recorded here as additional unique material found during preservation, for
`cto` to evaluate independently of the migration-window rule above.

Original text, verbatim:

> **Rule.** Any verification that greps a function body for a pattern — a removed predicate, a
> retired identifier, a clause that must still be present — **matches against executable code, not
> against the comments that explain it.** Strip comments first:
>
> ```sql
> -- The predicate is GONE from the code:
> select regexp_replace(prosrc, '--[^\n]*', '', 'g') ilike '%prime%'
>   from pg_proc where oid = 'public.some_fn(uuid)'::regprocedure;   -- -> false
> ```
>
> Use the same normalization on both sides when comparing an authored migration body against the
> live one, and add `regexp_replace(…, '\s+', '', 'g')` when the comparison must survive
> reindentation. **Never** narrow the search pattern instead — see below.
>
> **Why this is not a nicety.** §6g requires whole-body authoring from the live catalogue, and
> `T-058`/`10716` require a replaced predicate to be **documented in place** — a comment saying what
> was removed and why, so a dormant path is distinguishable from an abandoned one. Those two rules
> together guarantee that the removed token is still present in `prosrc`, quoted inside the comment
> that records its removal. A raw `prosrc ILIKE '%<token>%'` therefore returns **true on a correctly
> fixed function**, and returns it *because* the fix was documented as required.
>
> **Both available responses are wrong, and the second one is worse.**
>
> - Report the match as a leftover, and the seat re-fixes code that was already correct.
> - **Narrow the pattern until the false positive disappears** — and the check quietly stops
>   detecting the real thing. A grep tightened to dodge a comment is a grep that will not catch the
>   silent revert §6g exists to catch. **This trades a false positive for a false negative on
>   exactly the check whose whole purpose is catching the false negative.**
>
> **Two measured instances, one day, two different causes** (2026-09-07). On `KAN-150`,
> `backend-4` found `prosrc ILIKE '%prime%'` true on both functions after the fix — the fix's own
> required explanatory comments quoted the removed predicate. Earlier the same morning,
> `posts_mapping_check` produced the same shape from an unrelated seat's identifier. **The cause
> differs; the failure is identical**, which is why the rule is about the method and not about
> either token.
>
> **The general form, since this is not only about comments.** A pattern match over source text
> proves something about the *text*, not about the *program*. Before reporting on a grep of
> `prosrc`, ask what else in that text could satisfy the pattern without the code doing the thing —
> a comment, a string literal, a column name that contains the token, a different function inlined
> into the same body. §12 exists because the correct measurement, read wrong, is the expensive
> error; this is that failure with the search doing the lying.
