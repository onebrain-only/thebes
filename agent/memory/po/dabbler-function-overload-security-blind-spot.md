---
name: dabbler-function-overload-security-blind-spot
description: Postgres function overloads (same name, different signature/security behavior) repeatedly defeat name-based security sweeps in the Dabbler schema — verify by reading each function's own body, never by name alone.
metadata:
  type: project
---

In the `dabbler` Supabase schema, several security-relevant functions exist as multiple
overloads under the same name, where different overloads have materially different
`SECURITY DEFINER`/`INVOKER` status and different exposure to a given defect. A name-pattern
or name-based sweep (e.g. "find all `can_*` functions", "find all callers of `X`") reliably
misses the dangerous overload because it matches the name, not the resolved signature.

Confirmed instances, 2026-09-10 closure sprint (same session, three separate findings):
1. `rpc_potential_vibes` — 7-arg overload takes `p_me uuid` as caller-supplied (exposed,
   contained); 6-arg overload injects `auth.uid()` internally (safe). A name sweep alone
   cannot tell them apart.
2. `trgfn_organiser_profile_persona_guard` (KAN-177) — a trigger function referencing the
   missing `organiser_profiles` table, invisible to a `can_*`-named-predicate sweep because
   it isn't named like the others in its class.
3. `is_venue_admin` (KAN-178) — 1-arg overload is `SECURITY INVOKER` and reads `role_grants`
   directly (exposed to RLS policy changes on that table); 2-arg overload routes through
   `SECURITY DEFINER is_admin` and is immune. `cto` also independently confirmed: "a
   catalogue-body sweep cannot see overload dispatch — the call site names the function, not
   the resolved signature."

**Why:** Postgres resolves overloads by argument signature, not name. Any sweep tool that
greps/matches on function name (in `pg_proc`, in call sites, in migration text) will conflate
overloads unless it also reads each `pg_get_functiondef()` body and checks `prosecdef`/args
independently.

**How to apply:** When doing a security sweep or Preflight assessment against this schema —
especially anything touching `SECURITY DEFINER`, RLS-referenced functions, or "does X call
Y" — always resolve every overload of a candidate function name and check each one's own
`SECURITY DEFINER`/`INVOKER` status and body, not just its name. Treat a "name matches, so
it's covered" sweep result as unverified until each overload has been checked individually.
This has now cost three separate re-scoped tickets (KAN-174/175's predicate design, KAN-177,
KAN-178) in one session because it wasn't caught the first time.

See also [[dabbler-security-sweep-2026-09-10]] if that gets written up — link is aspirational,
not yet a real memory file.
