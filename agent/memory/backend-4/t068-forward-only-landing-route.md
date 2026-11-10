---
name: t068-forward-only-landing-route
description: How a new schema change lands under the T-068 migration freeze — apply_migration forward-only is explicitly sanctioned, db push is barred, and the repo file must reuse the returned version
metadata:
  type: project
---
> **Note 2026-11-10 (Thebes System).** Who applies has changed. A team seat never calls `apply_migration`; Memphis applies migrations as ordered `execute_sql` steps (`agent/DECISIONS.md` TH-054). The T-068 reading below still explains what the freeze bars.

`T-068`'s freeze bars `supabase db push`, blanket `migration repair`, and historical replay against `wtncuzcskpigqpmnxwws`. It does **not** bar new forward-only work. T-068 step 1 states the sanctioned route verbatim: *"forward-only migrations, authored fresh against live state, applied via `apply_migration` (never `db push`)."*

T-068 step 5 adds a binding obligation: **pick one channel** — a repo file applied under its own version, or `apply_migration` as the sole channel with the remote ledger as the record. The 269 orphaned remote versions exist because files were written by hand with round-hour stamps while `apply_migration` wrote its own second-precision version and never learned the filename.

**Why:** the freeze reads like "no schema tickets are possible," and it is not — the CEO ruled it must not be read that way. Quoting the freeze to block additive work is as wrong as running `db push` past it.

**How to apply:** for a purely additive change (new table, new function, nothing touching an existing object), cite T-068 step 1 as precedent rather than arguing around the freeze. Apply via `apply_migration`, then name the repo file with the **exact version the call returns**, so the two artefacts are linked and the change does not become orphan number 26. See [[live-db-state-contradicts-decisions]].
