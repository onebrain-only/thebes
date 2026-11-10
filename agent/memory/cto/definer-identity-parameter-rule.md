---
name: definer-identity-parameter-rule
description: A catalogue sweep for callers cannot see SQL overload dispatch — it reports the implementation as an orphan and the wrapper as self-contained
metadata:
  type: feedback
---

When a backend seat reports "this function has zero callers of any kind", check whether the
function is an **overload**. A body-text sweep of `pg_proc.prosrc` finds the *name* at a call site
but cannot resolve *arity*, so an implementation overload looks orphaned while its thin wrapper
looks self-contained.

**Why:** on `KAN-174` (2026-09-10), `backend-8` swept Dart, edge functions, 2,954 catalogue bodies,
`pg_depend`, triggers, `cron.job` and 24h runtime logs and concluded the 7-arg
`rpc_potential_vibes` had no callers. The 6-arg wrapper was calling it — its whole body is
`SELECT * FROM rpc_potential_vibes(..., auth.uid())`, seven arguments. Acting on "drop it as
redundant" would have broken an `anon`-allowlisted view that `anon-allowlist-check.yml` gates.
`pg_depend` does not record function-to-function calls, so that route proves nothing either.

**How to apply:** prove the dispatch by *behaviour*, not by grep — call the wrapper and check the
result carries a fingerprint unique to the suspected implementation (I used the stub's literal
`score = 1.0` and `reasons.source = 'stub'`). This is the same class as `AGENTS.md`'s rule that an
absence must be proved reachable by the search that claims it. Rule now written into
`CONVENTIONS.md` §6d. See [[supabase-sql-read-path]] for the probing mechanics.
