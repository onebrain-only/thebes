---
name: anon-execute-needs-effective-privilege
description: anon inherits EXECUTE from the bare PUBLIC "=X" grant, so string-matching proacl for "anon" misses it — use has_function_privilege
metadata:
  type: project
---

**`anon` can execute a function whose `proacl` never names it.** A bare `=X/postgres` entry is
a grant to `PUBLIC`, which `anon` inherits. So any check that string-matches `proacl` for the
literal `anon` reports a false negative.

Measured 2026-09-10 on `wtncuzcskpigqpmnxwws`, `public`, `prokind='f'`: 1761 functions, 303
`SECURITY DEFINER`, **292** both `SECURITY DEFINER` and anon-EXECUTE by effective privilege —
and **60 of those 292 carry no literal `anon` in `proacl` at all**. Worked example:
`rpc_potential_vibes_debug` oid 24497, `proacl = {=X/postgres, postgres=X/postgres,
service_role=X/postgres}`, yet `has_function_privilege('anon', 24497, 'EXECUTE')` is true.

**A function that errors for `anon` is not therefore protected.** That same debug function does
not raise `42501` (insufficient privilege) — it **passes** the permission check on the bare
`=X` and dies at `42P01` on a missing relation. Its inertness is an accident of a dropped view,
not a privilege boundary; restore the view and it is exposed. `cto` ruled it `DROP`, not
`REVOKE`, on exactly that reasoning (KAN-174 AC6).

**Why:** the KAN-61 CI gate covered views only (`relkind = 'v'`), so this whole object class
sat outside any control while the gate ran green — that is the KAN-175 detection gap.

**How to apply:** always resolve function reachability with `has_function_privilege(role, oid,
'EXECUTE')`, never by inspecting `proacl` text. And never treat an error under a role as
evidence of a privilege boundary — distinguish `42501` from every other SQLSTATE before
calling something inaccessible. See [[pg-overload-dispatch-defeats-catalogue-sweeps]].
