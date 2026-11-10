# backend-5 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-5.md`. This file is a work log, not a rule source.


No migration change. Probe pack updated and committed **`c54b497`**; guard shapes now classified by
name inside the file. Not pushed, not released.

### 2026-09-11 — KAN-178 AC5 APPLIED: definer AND relocate, one transaction (T-079 Am. 3)

**Correcting my own earlier framing first.** I reported the INVOKER-helper problem as a discovery
needing a `cto` ruling. It was already **AC5 on this ticket**, in the "SCOPE WIDENED" section, sized
into `backend-3`'s Work Effort. **I read the ticket as ending at AC4.** The measurement was right;
treating it as new was not, and it cost an escalation that had to be withdrawn.

Applied: ledger **`20260911081512`**, commit **`8bf9595`** on `Canary`.

**The ruling that changed the shape**, and it is why definer-only would have been worse than the bug:
as INVOKER these hold `anon` EXECUTE but leak nothing, because RLS applies to the caller. As DEFINER
they bypass RLS, read `role_grants` in full, **and still take a caller-supplied uuid** — so
`/rpc/is_venue_admin` as `anon` would disclose whether an arbitrary user holds that role. That is the
T-070 identity-parameter oracle KAN-188 closed for five siblings. **I would have opened it on two
more.** Definer-first opens the oracle; relocate-first leaves them answering false. One transaction.

**Containment is the reverse of the usual and easy to get backwards.** EXECUTE **kept** for `anon`
and `authenticated`; `util` withholds USAGE. PostgREST resolves an RPC **by name** → needs USAGE →
closed. A policy qual stores the **OID** and resolves no name → only EXECUTE is checked → still runs.
Revoking EXECUTE instead reproduces KAN-188's `42501`.

**The §6d sweep is the step that mattered, and it was the overload trap again.** Swept `pg_proc`
across every schema, `pg_policy`, views/matviews and CHECK constraints. The three plpgsql callers
(`rpc_booking_cancel`, `_hold_for_game`, `_hold_for_meetup`) all call
`public.is_venue_admin(auth.uid(), vid)` — the **2-arg** overload, schema-qualified. **Measured from
`prosrc`, not inferred from the name.** My first regex truncated at the nested `)` and showed only
`is_venue_admin(auth.uid()`, which reads exactly like the 1-arg; I widened the window rather than
act on it. Had I trusted it I would have "fixed" a break that did not exist, or worse, moved the
2-arg. `is_moderator` has **zero** callers anywhere.

**Verified live as `authenticated` after apply** — pre-state was both *reachable by name, returning
false*:

| | before | after |
|---|---|---|
| `util.is_venue_admin(uuid)` by name | reachable | **42501 permission denied for schema util** |
| `util.is_moderator(uuid)` by name | reachable | **42501** |
| `public.is_venue_admin(uuid)` 1-arg | reachable | **42883 does not exist** |
| `public.is_venue_admin(uuid,uuid)` 2-arg | reachable | **reachable, returns true** |

That last row is the over-reach guard, and it is in the probe pack as one.

**Identity preserved, asserted not assumed:** OIDs **20147 / 20148 unchanged** across the move, and
all **three** `storage.objects` quals verified rebound to `util.is_venue_admin`. `ALTER … SET SCHEMA`,
never `DROP`+`CREATE` — a new OID would have silently orphaned those quals. `proacl`, `provolatile`
(STABLE), `proconfig` and owner all carried through unchanged (T-058 / T-044).

**AC5's demonstration:** both still return **false**, and false is now the *true* answer rather than a
fail-closed artifact — 0 `moderator` and 0 `venue_admin` grants of 1 total row. I did **not** create a
grant to exercise the true-branch: that is a write to a permissions table. The RLS bypass is asserted
from the catalogue (prosecdef, owner, no FORCE) and exemplified behaviourally by `is_admin`, which has
identical properties and returns true for a non-admin caller. Said as an exemplar argument, not as a
direct demonstration, because it is one.

**Guards applied my own earlier lesson**: all count-shaped against stated expectations, asserting
**properties** (schema, prosecdef, overload arity, anon EXECUTE, OID equality) rather than existence.
Demonstrated failing pre-change — `expected 2 relocated functions in util, found 0`.

**Two of my calls approved on the record and quotable at PEER:** `TO authenticated` — cto says it is
*better than what it ruled*, since anon matches no permissive SELECT policy rather than evaluating
`is_admin(NULL)`, one fewer anon-reachable definer invocation, and it moots the recursion question
for anon. And the `FOR ALL` call — cto accepted that zero `FOR ALL` policies remaining is the stronger
end state.

**Operative constraint now discharged:** the bar on issuing a `venue_admin` or `moderator` grant is
lifted — that was conditional on this landing, and it has.

Committed my two files only; other seats' untracked migrations left alone. Not pushed, not released.
Jira transitions remain classifier-denied; `team-lead` moved this to `Back-end` and it is now ready
for `Peer-review` by another `backend-N`.

### 2026-09-11 — KAN-178 AC5 PEER FAIL (backend-6) accepted and fixed: `row_security=off`

**The FAIL is correct and I verified it rather than accepting it.** All five `util.can_*` siblings
are `prosecdef=true` with `proconfig = {search_path=public,row_security=off}`. Before the fix my two
were the **only** SECURITY DEFINER functions in `util` without it. After: **zero remain** —
`util_definer_without_rs_off` returns `[]`.

Applied: ledger **`20260911105846`**, commit **`f53a85b`** on `Canary`.

**What I actually got wrong, stated precisely.** `20260911081512` made both DEFINER and relocated
them, but **carried the invoker-era `proconfig` through verbatim**. T-058 discipline covers restating
what exists; **it does not prompt you to add what the ruling requires and the live body lacks.** That
is the gap, and it is worth naming because "restate from `pg_get_functiondef`" felt like sufficient
rigour and was not. The reviewer's sharper point: it was **undeclared** — my header flagged the `TO
authenticated` deviation explicitly and never mentioned `row_security` at all, so nothing told a
reviewer whether it had been considered and rejected or simply missed. It was missed.

**Why it is a FAIL and not a nitpick — demonstrated behaviourally, as a non-exempt role:**

| | result |
|---|---|
| `row_security` on (default) | read of `role_grants` returns **false** — silently filtered |
| `SET row_security = off` | **42501** "query would be affected by row-level security policy" — **raises** |

So without the attribute, the day any of the three owner-exemption conditions flips — and `T-079`
names `ALTER TABLE … FORCE ROW LEVEL SECURITY` as the one-line change that *looks like hardening* —
these two quietly answer `false` again. **That is precisely the regression AC5 exists to remove,
reintroduced silently, from the direction nobody watches.** The attribute is the guard against this
ticket's own bug returning.

**Guards: four of six assert things this migration does NOT change** — `prosecdef`, `search_path`,
`anon` EXECUTE, the 2-arg overload, and both OIDs. That is deliberate: `CREATE OR REPLACE` silently
drops whatever is not restated, so the properties the *previous* migration established are exactly
what a careless rework destroys. All count-shaped; demonstrated failing pre-change with
`expected 2 with row_security=off, found 0`.

**Declined to bundle a second change, and reported it instead.** The siblings carry
`search_path=public`; mine carry `public, pg_temp`. The FAIL names `row_security` only. **Quietly
folding a second undeclared attribute change into the fix for an undeclared attribute change is the
same defect twice**, and would make the diff assert something the review never agreed to. Raised as
an observation with the analysis the reviewer needs: `pg_temp` is last and both bodies fully qualify
`public.role_grants`, so the shadowing exposure is small — small is not zero, and it is the
reviewer's call.

Post-fix live: both `proconfig = {"search_path=public, pg_temp",row_security=off}`, OIDs 20147/20148
unchanged, `proacl` retained, three `storage.objects` quals still bound, 2-arg untouched, AC5
still `false`/`false`. Not pushed, not released; back to `Peer-review`.

## 2026-09-11 — KAN-140 PEER review (reviewer, not author)

**Verdict: PASS.** Recorded via `store.record_review_result('KAN-140', 15, 'backend-5', 'pass', ...)`
(task revision 15 -> 16). No Jira transition, no ownership change — Orchestrator handles closure.

- Live re-verification against `wtncuzcskpigqpmnxwws` (reads only, 0 mutations): no `public.bookings`
  reference; two-hop `INTO STRICT` join present; exactly 3 `ON CONFLICT DO NOTHING`; exactly 2
  `fn_platform_owner_id()` call sites; `prosecdef=false`; `proconfig={search_path=public, pg_temp}`;
  `proacl={=X/postgres,postgres=X/postgres,service_role=X/postgres}` (CREATE OR REPLACE, so ACL
  preserved by construction); `payment_intents_booking_id_fkey -> venue_bookings(id) ON DELETE
  RESTRICT` unchanged. Fix premise re-checked: `venue_bookings.venue_space_id` and
  `venue_spaces.venue_id` are both `NOT NULL` with enforcing FKs — the NULL branch genuinely cannot
  arise.
- Ran `supabase/tests/kan140/run.sh` myself in a disposable container: PRE-FIX raised exactly
  `42P01 relation "public.bookings" does not exist` with no ledger rows; POST-FIX raised no error
  with user/debit, platform/credit, venue/credit all present. The probe is demonstrated failing
  before it counts as passing.
- AC4: diffed the committed body against the prior definition (`20260911120529`). Only delta is the
  venue-resolution `SELECT` and its comment, plus a whitespace-only `$function$;` terminator with no
  catalogue effect.
- The two declared harness deviations (`commission_rules` missing `applies_to`/`percentage`;
  `wallets.user_id` legacy PK/FK blocking `fn_get_wallet`) are correctly NOT touched in production
  or in the migration — `T-072` Decision 2 excludes `fn_get_wallet` and the `wallets` redesign by
  name, and Decision 3 says KAN-140 is authored against current live state only.

**Caveat, reported not inferred:** the Atlassian MCP returned "We are having trouble completing this
action" on every `getJiraIssue` attempt, so KAN-140's live AC text is `not documented` to me — the
same failure `cto` recorded inside `T-072` Decision 3. I reviewed against the brief's enumerated ACs
and `T-072`'s binding shape ruling. If the landed AC text diverges from that, this review does not
cover the divergence.

**Dispatch feedback:** LOW effort was right for the judgement, but the verification (container run,
live catalogue sweep, body diff) is not low-cost work regardless of effort setting.

## 2026-11-04 — KAN-850 (unblocks KAN-844 / KAN-811 step 7): kan712.contract flag via set_config

**Commit `61ebab0d5e53792e0ea9107a98fec4abc2b86511`** on `alpha-deir-el-bahari` (worktree
`Dabbler/worktrees/kan784-deir-el-bahari`). Not pushed. 21 files, +918/-60.

- New migration 6c, `20261103105000_kan844_kan712_contract_flag_set_config.sql`. The wrapper generator
  now uses `set_config('kan712.contract','on',true)` in the body and restores the prior value, instead
  of a function-level `SET` clause. That clause needs superuser and fails with 42501 on Supabase, where
  rolsuper=f. `kan712_legacy_guard` now honours the flag only when current_user is postgres or
  supabase_admin.
- Step 7 (`20261103110000`): the assertion is the only change. Re-pinned the md5s in KAN-809, KAN-810,
  B14 and B09 (B09 was outside the named list). `20261103100000` is untouched (0-line diff).
- Local PG16 only. No remote DB.
- **C2:** the old generator, run as non-super postgres, gives RED (permission denied to set the
  parameter). After the fix it is GREEN: 29 migrations apply as non-super.
- **New test, `events_p4/kan850_contract_flag_set_config_test.sql`:**
  - 24/0 on all three chains.
  - The old chain gives 20/4; all four failures are the [K] cases.
- **Suite results on the new chain:**
  - B14: 189/0
  - B09: 35/0
  - probes_kan712: 55/0. On the old chain it fails only D4 and H8.
  - 809: 23/0
  - 810: 19/0
- **Disclosures:**
  - Authenticated C5 refuses with "permission denied for table events", not
    `kan712_direct_shared_write_refused`. Behaviour is the same as before the change.
  - service_role with a forged flag is now refused. Before, it succeeded. This is the D4 change.
  - The 6c self-check creates a function and rolls it back at apply time.
  - 810 is excluded from the order check.
  - When there is no prior value, C4 leaves '' rather than NULL.
  - rollback_kan712 was only partially exercised.
  - The commit author identity is "Karnak (Claude)", which is unresolved.
- **Route:** PEER, reviewed by another backend-N.
- **Jira transitions still owed:** Ready→Back-end and Back-end→Peer-review are blocked by the classifier.

## 2026-11-04 — KAN-851 (under KAN-844): capture run_seed_meetup_template + step-7 4d allowlist
- Commit b337a1f9 on alpha-deir-el-bahari (worktree kan784-deir-el-bahari), not pushed.
- Capture 20261103104000: prosrc md5 74e763538070a1460fa4e1dc62f7cdf6 proven on local PG16 (non-superuser postgres). The transcribed dump was 6604 chars; prod has one space on the blank line after 'no_eligible_seed_host_in_city' (unique single-char md5 match).
- Step 7 4d: one entry added. RED (origin/Alpha step 7 fails at 4d naming the function) and GREEN shown by build_kan851.sh; T1-T4 pass, T4 proves real meetups/rsvps/events rows as service_role.
- Local fixture gap: service_role lacked sequence USAGE in the harness (event_outbox_id_seq) — granted in the test fixture.
- Route PEER (backend reviewer). Jira transitions not run by me (orchestrator owns comments for this dispatch).
