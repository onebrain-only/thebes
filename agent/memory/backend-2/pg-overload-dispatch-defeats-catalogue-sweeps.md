---
name: pg-overload-dispatch-defeats-catalogue-sweeps
description: A Postgres function body naming an overloaded function cannot be attributed to a signature; call-graph reachability is NOT determinable from the catalogue in this project
metadata:
  type: project
---

**A body grep over `pg_proc.prosrc` cannot establish which overload a call reaches, and
`pg_depend` does not record function-to-function calls.** So "this function has zero callers"
is not a conclusion the catalogue can support in this database. Established 2026-09-10 on
`rpc_potential_vibes`: `backend-8` swept 2,954 function bodies and reported the 7-arg overload
had zero callers; `cto` disproved it — the 6-arg overload is its only caller, and its body is
`SELECT * FROM public.rpc_potential_vibes(p_sport, …, auth.uid())`, seven arguments. The call
site names the **function**, not the signature.

`cto` proved the dispatch **by behaviour, not text**: probed as `authenticated`, the 6-arg
returns `score = 1.0` and `reasons = {"source":"stub","reason":"v_sport_profiles_with_user"}`
— the 7-arg's literal body, which exists nowhere else in the schema.

The recurring shape is a **wrapper/implementation pair**: a short overload that injects
`auth.uid()`, and a long one that accepts a caller-supplied identity `uuid`. The pair is the
unit of analysis; flagging the two halves as independent rows misreads it.

**Why:** an "uncalled" function may be the implementation half of a live pair, so dead-code
removal or false-positive filtering based on apparent callers deletes or excuses live code.
This bit a real sweep and needed a CTO probe to catch.

**How to apply:** never filter a security or dead-code finding by catalogue-derived caller
counts. If reachability actually matters, prove it by **behaviour** — probe the function as the
role in question and match a value that exists only in the suspected implementation. State
plainly that call-graph reachability is not determinable from the catalogue rather than
implying a zero-caller result is a fact. See [[anon-execute-needs-effective-privilege]].
