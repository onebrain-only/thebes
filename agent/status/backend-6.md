# backend-6 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-6.md`. This file is a work log, not a rule source.

the set the ruling names, carry `{search_path=public,row_security=off}`.** Measured, not inferred.

**I checked whether the ruling is self-consistent before calling it, and it is not entirely.**
`is_admin(p_user uuid)` — the ruling's other named exemplar — *also* lacks `row_security=off`
(`{"search_path=public, pg_temp"}`). So "matching `is_admin` and the `util.can_*` five" has two
different referents and `backend-5` matched one of them. That is mitigation, not a pass.

**Why it is still a FAIL rather than a nit.** `row_security=off` is the guard for this ticket's own
failure mode. The functions read `role_grants` correctly today only via the owner exemption, which
T-079 §2 itself establishes as **three separately mutable conditions**. Break any one — FORCE RLS on
`role_grants`, ownership diverging — and a DEFINER function without `row_security=off` **silently
returns false again**, which is the exact silent-false regression AC5 exists to remove. With it set,
the same scenario raises instead. And the omission is undeclared: the migration header is otherwise
scrupulous about flagging deviations (it flags `TO authenticated` explicitly and invites rejection),
but `row_security` is not mentioned in the header, the guards, or the author's status log — which
records `proconfig` as "carried through unchanged", i.e. the invoker-era value was **preserved**
rather than the ruled value **set**. That reads as an oversight, not a judged deviation.

**Everything else on the brief: verified, and each probe discriminates.**

| check | result |
|---|---|
| over-reach guard, 2-arg `public.is_venue_admin(uuid,uuid)` | reachable as `authenticated`; **true** for the admin uuid, **false** for a non-admin — it discriminates, not a constant |
| `util.is_venue_admin(uuid)` / `util.is_moderator(uuid)` by name | **42501 permission denied for schema util** |
| `public.is_venue_admin(uuid)` 1-arg | **42883 does not exist** — oracle closed |
| non-admin `authenticated` SELECT `role_grants` | **0 rows**, no error |
| admin `authenticated` SELECT | **1 row** — fail-closed detector fires, no `42P17` |
| `anon` SELECT | **0 rows** |
| P7 predicate discrimination pair | `= 'is_admin(auth.uid())'` → **1**; `= 'true'` → **0** |
| storage.objects quals rebound to `util.is_venue_admin` | **3** |
| OIDs across the move | **20147 / 20148 unchanged** |
| 2-arg untouched | 1, still `public`, still INVOKER |
| INVOKER readers of `role_grants` remaining in `public`+`util` | **0** — population complete |

**Two of the author's claims I re-derived rather than relayed, because both are the overload trap.**
(1) The three plpgsql callers: read from `prosrc` myself, all three are
`public.is_venue_admin(auth.uid(), vid)` — the **2-arg**, schema-qualified. (2) `storage_quals_rebound`
= 3: my first count returned **2**, because `venue_insert_admin` is an INSERT policy and its predicate
lives in `polwithcheck`, not `polqual`. The probe pack's P10 already coalesces both and is correct —
but a reviewer counting quals only would have reported a false break. Worth carrying forward.

**A residual I could not close, stated as unproven rather than assumed.** The containment mechanism —
an OID-bound policy qual executes a `util` function for a role that lacks `util` USAGE — could **not**
be demonstrated live. Every relation carrying such a policy is empty (`venue_members` 0,
`venue_bookings` 0, `storage.objects` bucket `venue` 0), so the qual is never evaluated and a SELECT
proves nothing. It rests on Postgres semantics (USAGE is checked at name resolution, not at execution)
plus the KAN-188 precedent. Correct, I believe — but not probed, and I am not recording it as probed.

**Non-blocking observations.** `anon` retains the table-level SELECT grant and gets row-hiding rather
than permission-denied — **this is the ruled outcome, not a defect**: Amendment 2 §4 requires "zero
rows — **not an error**, and not every row", and Amendment 3 approves `TO authenticated` as reaching
the same outcome by default-deny. That closes the open question I had left. Separately, the probe
pack header states every probe sets an RLS-subject role; P10 does not and cannot (util USAGE denied),
so it runs as owner — fine for a catalogue assertion, but the header overstates.

Did not fix, did not transition, no Jira. Reported to `team-lead`.

---

## KAN-178 — PEER re-review after my FAIL (2026-09-11) — **PASS**

Fix is `20260911105846_kan178_ac5_row_security_off_on_relocated_helpers.sql`, authored and applied by
`backend-5`. Re-verified against the **live catalogue**, not the migration text.

| Assertion | Live result |
|---|---|
| `util.is_moderator(p_user uuid)` proconfig | `{"search_path=public, pg_temp",row_security=off}` |
| `util.is_venue_admin(p_user uuid)` proconfig | `{"search_path=public, pg_temp",row_security=off}` |
| OIDs | **20147 / 20148 — unchanged**, so the OID-bound policy quals are intact |
| `prosecdef` on both | true |
| `proacl` on both | `{=X/postgres,postgres=X,anon=X,authenticated=X,service_role=X}` — `anon`/`authenticated` EXECUTE retained |
| Class sweep: SECDEF in `util` lacking `row_security=off` | **empty — 0 rows.** Class closed |
| All SECDEF in `util` | 7 — five `can_*` siblings + these two, every one carrying `row_security=off` |
| `storage.objects` policies depending on 20147/20148 | **3** — `venue_insert_admin`, `venue_update_admin`, `venue_delete_admin` |
| 2-arg overload `public.is_venue_admin(p_user, p_venue)` | oid 22308, `prosecdef=false`, still `public` — untouched |
| Remote ledger | version `20260911105846` present |

**The one item deliberately left unfixed — I rule it ACCEPTABLE, and it is not a follow-up blocker.**
These two carry `search_path=public, pg_temp`; the five siblings carry `search_path=public`. The
divergence does not weaken the security property: `pg_temp` sits **last**, `pg_catalog` is searched
ahead of both entries regardless (so `=` on uuid/text cannot be shadowed by a temp operator), and both
bodies fully qualify `public.role_grants`, so the table reference never goes through search_path
resolution at all. Trailing `pg_temp` is the documented minimum-safe placement. Omitting it, as the
siblings do, is marginally stricter — a consistency point, not a vulnerability.

**And leaving it out of this migration was the right call, not a gap.** My FAIL named `row_security`
only. Bundling a second undeclared attribute change into the fix for an undeclared attribute change
would have been the same defect twice. The author raised it as an observation instead, which is
exactly the discipline the FAIL was about.

Did not fix, did not transition, no Jira. Reported to `team-lead`.

## 2026-09-11 — PEER review KAN-182. **FAIL on AC6 only.** Security substance verified sound.

Reviewed `20260911105434_kan182_process_notification_event_contain_and_definer_trg_circle_join_notify.sql`
(sha256 `3c11d41c03faaa877a2815cd777ac1aaa159e15b7285b2188e8fd2c004fe4242`) against the live
catalogue. Every claim in `backend-3`'s status entry that I re-derived independently held.

**Re-measured, not accepted from the report:**
- `proacl` = `{postgres=X/postgres,service_role=X/postgres}`. `has_function_privilege` — `anon`
  false, `authenticated` false, `service_role`/`postgres` true. PUBLIC absent (no bare `=X/`).
- **19 caller functions / 22 call sites**, counted from `pg_proc.prosrc`. Matches the header's
  figure and confirms the "21 callers" number upstream was a call-site count. **All 19 are now
  `SECURITY DEFINER` owned by `postgres`** — zero INVOKER callers remain, so the revoke strands
  nothing. `trg_circle_join_notify` is DEFINER and its trigger on `circle_members` is attached
  and `tgenabled='O'`.
- Body md5s `1b14f5666734be00236e5abd4aa13dd4` / `a2afe6754a5b774354fdb2e78e540747` — unchanged,
  as ALTER/REVOKE/COMMENT-only requires. T-058 not engaged.
- `rpc_decide_join_request` — DEFINER, owner `postgres`, `authenticated` holds EXECUTE, calls the
  target twice. Executes as `postgres`, which retains EXECUTE. **Still works.**

**I demonstrated my own probe failing before banking it.** A `SET LOCAL ROLE` + `PERFORM` harness
returned 42501 for both `anon` and `authenticated` against the target; the *same harness* against
`public.earth()` (which `authenticated` may execute) reached the body and returned P0001. A probe
whose only observed outcome is denial proves nothing about the probe.

**AC4 re-run end-to-end, and the false-pass trap reproduced deliberately.** Correct parameter
names → **HTTP 401 / `42501 permission denied`**. Bogus parameter name → **404 / `PGRST202`
schema-cache miss** — the exact false pass `backend-3` caught and rejected. Its self-rejection was
right: the 404 never reaches the permission check. Probe safe by construction —
`notifications_to_user_id_fkey → auth.users(id)` verified from `pg_constraint`, so the fabricated
uuid raises 23503 before any row could persist. No write reached `notifications`.

**AC3 — disclosed deviation, technically sound, NOT mine to close.** Gated reachability instead of
parameter deletion. AC2 names "service-role-only" as an acceptable mechanism, so AC2 is met
outright. AC3's literal mechanism is not implemented and the header says so in full rather than
silently. Its second half I verified as genuinely pre-existing, not hand-waved:
`supabase/functions/broadcast-notification/index.ts:40` calls `is_admin()` and `:95` calls
`rpc_broadcast_inapp_notification` through a service-role client. **`po` recorded this tension on
the ticket as "recorded, not resolved."** A reviewer does not resolve it by passing it; flagged up.

**AC6 IS THE FAIL, and it is narrow.** Applied at version `20260911105434` — confirmed present in
the remote migration list. But `git status` in `dabbler-code` (branch `Canary`) reports the
migration file **untracked (`??`)**, as is `supabase/tests/kan182/`. AC6 reads "applied via
`apply_migration`; repo file committed at the exact returned version" — half of it is unmet.
This is not a wave-wide artifact I should wave through: **every other applied migration in this
batch — kan168, kan170, kan171, kan178, kan181, kan185, kan188 — IS committed.** Only kan182 is
applied-and-uncommitted. While that holds, the repo no longer reconstructs the live database.

**AC5 open but externally blocked, not neglected.** No KAN-175 regression suite exists to add the
function to — KAN-175 is still in flight. The per-ticket pack at `supabase/tests/kan182/` matches
the kan128/130/173/178/181 convention. Noted so it is not lost when KAN-175 lands.

Did not fix, did not transition, no Jira. Reported to `team-lead`.

## 2026-09-11 — KAN-182 AC6 re-check (PEER, re-verify only)

**AC6 now PASSES.** The narrow fail I recorded earlier — migration and probe pack untracked on
`Canary` — is closed. Commit `f8b6006` ("fix(kan182): contain process_notification_event, definer
trg_circle_join_notify") is on `Canary` and on `origin/Canary`, and adds exactly two files:
`supabase/migrations/20260911105434_kan182_process_notification_event_contain_and_definer_trg_circle_join_notify.sql`
and `supabase/tests/kan182/probes.sql` (234 lines).

**Committed file is byte-identical to the applied statement, not merely same-named.** Ledger row
`supabase_migrations.schema_migrations` version `20260911105434`, name
`kan182_process_notification_event_contain_and_definer_trg_circle_join_notify`, one statement;
md5 of that statement = `8875af3dbef012244ac6a937f52a955b`, and md5 of the blob at `f8b6006` =
the same value (5168 bytes, no trailing newline — both trimmed and untrimmed hashes agree). So
the filename version, the ledger version and the content all agree; the repo reconstructs the
live database for this migration.

Both blobs are unchanged between `f8b6006` and the `origin/Canary` tip (`git diff --stat` empty
over those paths). Other untracked migration files remain in the worktree (kan169 x2, kan174,
kan186) but none belong to KAN-182.

AC3 was ruled accepted by `po`; not re-litigated here. No fix, no Jira, no transition.
Reported to `team-lead`.

## 2026-09-11 — KAN-179 PEER review (reviewer, not author)

Peer reviewer for KAN-179 (caller-controlled auth subject on two friends RPCs, same class as
KAN-174/T-070). Author: backend-5, ledger 20260911131216, Canary `3a3bcae`. Verdict: **PASS**,
recorded via `store.record_review_result('KAN-179', 14, 'backend-6', 'pass', ...)` → revision 15.

Verified independently against live `wtncuzcskpigqpmnxwws`, not from the report:
- `to_regprocedure`: `rpc_get_friends(uuid)` and `rpc_get_friend_suggestions(uuid,integer)` both
  NULL; `rpc_get_friends()` and `rpc_get_friend_suggestions(integer)` both present;
  `to_regclass('public.friendships')` NULL.
- New `rpc_get_friend_suggestions(integer)`: `prosecdef=true`, `proconfig={search_path=public}`,
  `proacl` grants EXECUTE to both `anon` and `authenticated` (asserted on the ACL, not on the
  GRANT having run — a DROP+CREATE drops `anon` too, `pg_default_acl` notwithstanding).
  `prosrc` contains no `p_user_id` and does contain `auth.uid()`.
- Safe 0-arg `rpc_get_friends()` untouched — still `search_path=public, pg_temp`, i.e. NOT the
  new function's `search_path=public`, which is itself evidence it was never replaced.
- AC4: 15 `public` functions reference `friendships` in `prosrc`, 13 outside the two in scope;
  `rpc_get_friendship_status(uuid)` present and unmodified.

Anon HTTP round-trip re-run by me (not trusted from the report), with the failing case shown:
- `p_user_id` payload → both RPCs `404 PGRST202` (signature absent from the schema cache) — the
  bypass path is unreachable, not merely empty.
- `p_limit`-only → `42P01 relation "friendships" does not exist`. This is the probe that matters:
  it proves the function body actually executes rather than erroring on signature match first,
  so the 404s above are a real absence and not a generic failure.
- `rpc_get_friends()` with `{}` → `[]` (anon, `auth.uid()` null). Correct.

Note: `getJiraIssue` for KAN-179 failed three times with an Atlassian 5xx, so the 4 ACs were taken
from the review brief and the migration header rather than read off the live ticket. Every AC as
stated there is evidenced above; if the live ticket text differs from the brief, this review does
not cover that difference.
