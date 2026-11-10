---
name: supabase-sql-read-path
description: cto CAN run MCP execute_sql against wtncuzcskpigqpmnxwws, including role-switched anon/authenticated probes — T-068's "no seat can execute SQL" is false
metadata:
  type: project
---

`mcp__claude_ai_Supabase__execute_sql` works against project `wtncuzcskpigqpmnxwws` for the `cto`
seat. Verified 2026-09-10 across ~12 read-only statements while ruling `T-070`–`T-072`.

**Why:** `DECISIONS.md` `T-068` states MCP `execute_sql` is "denied on this project" and concludes
no seat can execute SQL remotely. That generalisation was wrong and has been cited to justify not
measuring things. Corrected in `T-068` Amendment 3, 2026-09-10. The *pooler credential* really is
unset (literal `[YOUR-PASSWORD]`), so `psql` and `supabase db dump` remain blocked — only the
generalisation from that is withdrawn.

**How to apply:** never accept "there is no SQL read path" as a reason a measurement was skipped —
try `execute_sql` first. Role-switched probing works and is the way to prove an access claim
instead of reading an ACL by eye:

```sql
create or replace function pg_temp.probe() returns table(probe text, outcome text) language plpgsql as $$
begin
  set local role anon;
  begin ... exception when others then outcome := sqlstate||' '||sqlerrm; end; return next;
  reset role;
end $$;
```

For an authenticated probe, `perform set_config('request.jwt.claims',
json_build_object('sub', uid::text,'role','authenticated')::text, true)` before `set local role
authenticated`. `RAISE NOTICE` output is **not** returned through this MCP — collect results into a
returned table instead.

Not established: whether other seats have the same access. `backend-3` hit the wall independently;
a seat that needs it should test and report. Related: [[definer-identity-parameter-rule]].
