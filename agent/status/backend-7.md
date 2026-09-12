# agent/status/backend-7.md

**Owner:** `backend-7` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

## 2026-09-10 — KAN-68 (production hotfix) — content_hits_blocklist fail-open: diagnosed and confirmed, NOT applied
**Agent:** `backend-7` (Ashat), CEO-named executor under a bounded exception to the migration freeze
**Outcome:** **No production change was made. Production data mutations: 0. DDL statements applied: 0.**
Both fail-open defects in `public.content_hits_blocklist(text,text)` were independently reproduced
against live `wtncuzcskpigqpmnxwws`, and the authorized three-part fix was composed and submitted —
but the write was **denied by the Claude Code auto-mode permission classifier**, not by Postgres.
The function remains `SECURITY INVOKER` with the broken locale predicate. **The blocklist is still
failing open in production.**
**Evidence:** all measured live, read-only.
- Before state: `prosecdef=false`; `proconfig={"search_path=public, pg_temp"}`;
  `proacl={=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service_role=X/postgres}`
  (bare `=X/` PUBLIC entry **and** a separate `anon=X` entry — two independent anon-reachable sources);
  live body is `count(*)` with predicate `(locale = 'any' or locale = p_locale)`.
- `public.safety_blocklist_terms`: `relrowsecurity=true`, **0 policies**,
  `relacl={postgres=arwdDxtm/postgres,anon=rm/postgres,authenticated=rm/postgres,service_role=arwdDxtm/postgres}`.
- Population counted directly (`020`, not inferred): **2 terms, 2 non-regex, 0 regex, 2 `locale='en'`, 0 `locale='any'`.**
- Defects isolated, each demonstrated FAILING, probe proven non-vacuous:
  as `postgres` (RLS bypassed) listed-term `p_locale` default → **0** but `'en'` → **1** (locale defect);
  as `authenticated` the same `'en'` call → **0** (RLS defect); clean text → 0 in both.
  Probe text was derived from the table in-session and never surfaced.
- Canonical source read and followed: `Dabbler/dabbler-code/supabase/migrations/20260831120000_kan68_fix_safety_blocklist_fail_open.sql`
  (KAN-68, T-020, T-040). File deliberately **not** applied or replayed — it also touches
  `_get_context_config` and two tables, all out of scope.
**Not verified:** the after-state — `pg_get_functiondef`, `prosecdef`, `proconfig`, `proacl`, and the
post-fix behavioural probes are **all unverified, because nothing was applied.** Also unverified: whether
`count(*)::int` executes cleanly under `RETURNS integer` (untestable without the replace). Not attempted:
the `anon`-role probe over PostgREST. Out of scope and untouched: `_get_context_config`,
`safety_blocklist_terms`/`context_rating_config` grants, RLS policies, migration history.
**Observed drift, reported not acted on:** canonical's header comment claims both tables carry
`anon=arwdDxtm`/`authenticated=arwdDxtm`; live shows `anon=rm`/`authenticated=rm`. Table grants were out
of scope, so this was recorded rather than corrected.
**Next:** blocked on the CEO. The permission classifier must allow the Supabase DDL write, or the change
must be applied through an authorized path. **The fix must go as one transaction** — landing
`SECURITY DEFINER` without the `PUBLIC`/`anon` revokes in the same unit would convert the function into an
unauthenticated banned-term oracle over PostgREST, which is strictly worse than the current fail-open.
Splitting it to get past the denial was considered and rejected on those grounds.

## 2026-09-10 — READ-ONLY assessment: five same-class RPC candidates (KAN-175 class sweep)

**Task:** assess backend-2's five heuristic hits for exploitability in the `rpc_potential_vibes/7` class
(SECURITY DEFINER + caller-supplied identity arg + anon-EXECUTE + shorter same-named overload).
**Limits honoured:** production `wtncuzcskpigqpmnxwws` only. No DDL, no DML, no GRANT/REVOKE, no
`apply_migration`, no `db push`. T-068 freeze respected. Nothing contained by me. No write executed,
including inside rolled-back transactions. All role probes ran inside `begin; set local role …; rollback;`.
Counts and field names only; no user data surfaced.

**Effective privilege measured via `has_function_privilege`, not a `proacl` string match.** All ten
overloads across the five names are anon- AND authenticated-EXECUTE. Every one carries a bare `=X/postgres`
PUBLIC entry *and* a literal `anon=X/postgres`.

**Verdicts (detail in the returned report):**
- `rpc_get_friends(p_user_id uuid)` — **authorization bypass PROVEN, disclosure currently INERT.**
  `v_user_id := COALESCE(p_user_id, auth.uid())` — the arg is the authorization subject, never compared
  to `auth.uid()`. Matched-pair control as `anon`: `rpc_get_friends(NULL::uuid)` raises at **line 10**
  `User not authenticated`; `rpc_get_friends(<any uuid>)` reaches **line 15**, the data query. Same role,
  same function, differing only by whether an identity argument was supplied. It returns no rows solely
  because `friendships` **does not exist in any schema** — verified against `pg_class`.
- `rpc_get_friend_suggestions(p_user_id uuid DEFAULT auth.uid(), p_limit int)` — **NOT on the five;
  found during call-site sweep. Same class, strictly worse, missed by the heuristic** (no shorter
  overload). No auth check at all. Returns `display_name, username, avatar_url, bio, mutual_friend_ids`.
  Reaches its data query as `anon` at line 3. Also inert on the missing `friendships` table.
- `is_admin(p_user uuid)` — **information disclosure, but REDUNDANT.** Root finding is upstream:
  `public.role_grants` policy `role_grants_any_read` is `SELECT … TO public USING (true)`. Counted as
  `anon`: **1 of 1 rows readable directly.** T-020 breach. `is_admin/1` adds nothing anon cannot already read.
- **NOT a privilege bypass.** Swept every `public` function body and every `pg_policies` entry for
  `is_admin(` call sites: all pass `auth.uid()`, a local `me`/`v_actor` derived from it, or use `is_admin()`.
  The `can_*_venue*(p_user_id, …)` family does call `is_admin(p_user_id)` with its own argument, but every
  caller — 19 RLS policies and `rpc_my_venue_permissions` — supplies `auth.uid()`. No caller-supplied path found.
- `can_view_post/3` — **social-graph boolean oracle, real but bounded.** As `anon`: direct read of the
  target post returns **0 rows**, yet the function truthfully answers follower-relationship queries —
  true for a real follower, false for a non-follower, false for a random profile, false for a nonexistent
  post. Requires the attacker to already hold post and profile UUIDs. Only **8 of 503** posts are non-public.
- `rpc_meetup_rsvp/4` — **NOT exploitable.** Writes bind to `u := auth.uid()`; raises `auth_required` at
  line 7 as `anon`. PK `(meetup_id, user_id)` confines a caller to their own row. Residual: `p_profile_id`
  is stored unvalidated (FK to `profiles(id)`, no ownership check) — authenticated-only labelling defect.
- `toggle_venue_favorite/2` — **NOT exploitable.** `$2 <> auth.uid()` raises `Unauthorized`. Demonstrated
  both guards firing at **different lines** (anon → line 4; authenticated-with-mismatched-uid → line 8),
  which proves the probe advances when a guard is satisfied rather than failing uniformly.

**Evidence discipline:** every negative carries a positive control. The load-bearing one: as `anon`,
`role_grants` returned **1 of 1** rows while `posts` returned **0 of 503** — the same session both
returning and being denied rows, so a zero means RLS filtering and not a broken probe. `venue_favorites`
and `meetup_rsvps` are genuinely empty (0 true rows), so anon zeros there prove nothing and are reported
as such, not as safety.

**Not verified:** whether `friendships` was dropped or never created, and whether any migration would
recreate it — I did not read migration history. Whether the app calls the vulnerable overloads. Whether
PostgREST exposes these under the same resolution as a direct `SET ROLE` probe (I tested in-database, not
over HTTP). The other 40 identity-arg SECURITY DEFINER functions outside these five.

**Reported, not acted on.** Containment belongs to the authorized path, not to me.

---

## 2026-09-10 — KAN-172 PEER review (reviewer of record) — **PASS**, Done

Independent same-capability review of backend-5 (Heka)'s comment fix in
`Dabbler/dabbler-code/supabase/migrations/20260910090000_kan130_kan131_wallets_owner_and_platform_identity_migration.sql`.
Repo-only, unapplied file, `T-068` not engaged. Read-only throughout: no `apply_migration`, no DDL, no DML, no commit.

**AC1 PASS.** Both AC line numbers verified against `git show HEAD` rather than the report — `HEAD:288-291`
held the `OWED, NOT WRITTEN HERE` deferral, `HEAD:348-349` held *"deliberately unruled here"*. Both corrected.
Confirmed the in-body block's dollar-quote containment rather than assuming it: function opens `as $$` at
`:317`, closes `$$;` at `:377`, corrected comment sits at `:369` — so it is genuinely the text reaching
`pg_proc.prosrc`. Checked the new prose clause-by-clause against `P-036` at `DECISIONS.md:5062`; ruling date,
RETAIN AND DISCLOSE, both rejected remedies with `cto`'s quotes, the period-is-a-legal-determination position,
the `11` v2 §I.4 fourth-bullet home, and the zero-row basis are all faithful. No period invented.

**AC2 PASS, and the probe was demonstrated failing before it counted.** Wrote an independent SQL comment
stripper that **recurses into dollar-quoted bodies** — a stripper treating `$$…$$` as an opaque literal gets
this wrong (151/155 lines, spurious diff). Correct result: **115 executable lines both sides, md5
`8da92deaade72f6c1d3819c02b036033`, byte-identical**, reproducing the reported figure independently.
**backend-5's stated negative control does not work:** case-changing `financial_ledger_wallet_fkey` is inert
because that identifier appears only at `:125`/`:148`, both inside comments. Demonstrated three real failures
instead (case-change `v_uid` inside the body; case-change `public.delete_my_account`; insert a `delete from`
statement) plus a comment-only sentinel that correctly still passes — so the probe is neither blind nor
always-fail. Claim sound, control offered for it was not.

**AC3 PASS.** `list_migrations` on `wtncuzcskpigqpmnxwws` returns `20260907071308` as latest; `20260910090000`
absent. APPLY GATE intact at `:15`, file still ends at `commit;`. `:344` untouched — 0 occurrences in the diff.

**Defect found, outside AC scope, returned to `po` — deliberately NOT a FAIL.** Lines `:96-99` (unchanged,
from KAN-130's authorship) still assert under *"OUT OF SCOPE — deliberate absences"* that the retention
position is owed pending KAN-135 and call it an *"unruled policy"* — now contradicted by `:288-312`, which
write it. Note for grep-based auditors: **`not written here` spans a line break** (`:97`/`:98`), so a
line-based grep returns 0 and misses it; a whitespace-normalised search also finds `unruled policy` and
`owed pending`. Migration-file only, never reaches the catalogue. AC1 was deliberately narrowed by `po` to
two enumerated locations in `delete_my_account`'s comment block; `:96-99` is the file's global preamble.
Failing on it would have been inventing an acceptance criterion.

**Persistent State was materially out of lockstep and I reconciled it.** Record read `canonical: ready` /
status `10008` while Jira was at `Peer-review`, `review_context: null`, `executor_evidence: []`. Sequence:
`observe_lifecycle` → `10045`, `open_review_context`, `resolve_review_owner(backend-7)`,
`record_review_result(pass)`; `queue.completion_reasons` then returned empty; transition id `41` read back
from the live API per `G-018`; `observe_lifecycle` → `10007`. Now rev 11, `canonical: done`.

**Two things I did NOT do, both deliberate.** (1) `executor_evidence` is empty, so `resolve_review_owner`'s
exclusion of evidenced executors was **inert on this record** — the guard against an author reviewing their
own work would not have bitten. It did not matter here (backend-7 ≠ backend-5), but there is no API to add
execution evidence after the fact (`classify_executor_evidence` only downgrades to `assessment`), so I did
not fabricate one. (2) Ownership is still held by **backend-5 on a Done ticket** — `release` requires the
owner or `ceo`/`orchestrator` authority and I am neither, so I left it. Both raised for `po` / the Orchestrator.

---

## 2026-09-10 — KAN-175 PEER review (fresh, independent). Verdict: **FAIL**, narrow. Not recorded — I am not the review owner.

Reviewed `a08c057` on `Canary` as a fresh reviewer after `backend-5` was lost mid-review. Retrieved my own
evidence throughout; accepted no claim from `backend-2` or the dispatch brief as established.

**The class-level protection is real and I verified it.** The predicate resolves EFFECTIVE privilege via
`has_function_privilege('anon', p.oid, 'EXECUTE')`, never a `proacl` text match. The crux case is live and
confirmed: `rpc_potential_vibes_debug(p_me uuid, ...)` carries `proacl = =X/postgres,postgres=X/postgres,
service_role=X/postgres` — **no `anon` anywhere** — and `has_function_privilege('anon', …)` returns `true`.
A string match on `anon` certifies it safe; the shipped gate flags it.

**I reproduced the self-test against a real disposable Postgres.** 9/9 fabricated cases correct (5 must-flag,
4 must-not-flag) plus both diff directions. Every fixture is newly written, none named `rpc_potential_vibes*`,
none shares a parameter name with it (`p_me` appears in no fixture), and none has an overload at all —
so AC4's no-overload requirement is met by every must-flag case.

**I demonstrated all three negative controls failing myself**, on the shipped fixture seed, on my own
substrate — not by reading `backend-2`'s account. (1) A `proacl LIKE '%anon%'` match returns EMPTY for
`rpc_public_grant_only`, whose ACL is the bare `=X/postgres` PUBLIC form, while `has_function_privilege`
returns `t`. (2) `prosrc ~ 'auth\.uid\(\)'` is TRUE for `rpc_coalesce_fallback`, so a "mentions" test clears
the exploitable COALESCE case. (3) The dropped overload requirement flags ZERO of the 5 real offences.

**The vacuous-control fix is real.** `auth.uid()` returns a fixed uuid, not NULL (`:82-83`), and `:157-160`
asserts the guarded fixture ACTUALLY RAISES before its "not flagged" result counts. I found no other control
passing for the wrong reason.

**Shared-predicate design is genuine, not nominal.** `anon_function_predicate_sql()` is DEFINED EXACTLY ONCE
(`anon_function_grants_diff.sh:85`); both the gate (`:56`) and the self-test (`:164`) `source` that file and
invoke it. There is no second copy of the SQL anywhere in `scripts/`, `.github/` or `docs/`. Test and gate
cannot drift. This is the thing KAN-61 got wrong and it is genuinely fixed.

**No KAN-61 regression.** §2f still extracts exactly **11** view names, §2g **74** signatures; the markers
cannot collide (`ANON_ALLOWLIST_START` is not a substring of `ANON_FUNCTION_ALLOWLIST_START` — the literal
`FUNCTION_` intervenes) and I confirmed the extraction counts empirically. `check_anon_allowlist_test.sh`
still green, both directions.

**The population is 72 today, not 74 — and the gate is correctly GREEN.** I re-ran the predicate myself:
72 flagged. All 72 are on the 74-entry §2g allowlist; the 2 extras are STALE, not missed. `create_system_post`
and `process_notification_event` both now read `anon_exec = false` with no bare `=X` in their ACLs — they were
contained by REVOKE after the baseline was taken. That is the documented one-directional design behaving
exactly as intended, and it is not a defect.

**Ruling on AC1's "or derived from" — `backend-2`'s reading is CORRECT.** Read as exculpating, "derived from"
clears `v := COALESCE(p_user_id, auth.uid())`, and I confirmed `rpc_get_friends(p_user_id uuid)` is live,
`SECURITY DEFINER`, anon-executable and does exactly that. 45 of the 72 flagged functions mention `auth.uid()`;
only 2 of the 74 identity-carrying ones compare it. An exculpating reading would gut the predicate and clear
the ticket's own named worst instance. Comparison-only is right.

### Why FAIL — two narrow items, neither touching the gate's live correctness

**1. The census figures are wrong in the shipped prose, and worse than reported.** `scripts/ci/README.md:42`
reads *"SECURITY DEFINER: 303; anon-executable: 292; both: 292"*. Measured live: **303 / 1,746 / 290**.
Two errors on one line — `anon-executable` understated **~6×**, and `292` printed for two different
quantities. `docs/SCHEMA.md:600` repeats the mislabel. The RUNTIME census SQL computes all four figures
correctly, so the gate is unaffected — this is prose only. But §2g is the security document describing the
attack surface, on the one ticket that exists BECAUSE a control's documentation diverged from its coverage.
Separately stale from post-landing containment (expected drift, not a defect): `74→72` (`:605`),
`60 of 292 → 59 of 290` (`:612`, and `anon_function_grants_diff.sh:25-26`).

**2. `LIMIT 1` makes the predicate blind in its own stated dangerous direction.** The identity-argument
subquery takes only the FIRST matching `uuid` parameter and tests only that one. A function that guards its
first identity argument and leaves a second unguarded is SILENTLY CLEARED. Four live functions carry two
identity arguments — `can_view_post`, `is_blocked`, `rpc_rate_user`, `rpc_squad_create` — all currently
flagged, so there is **no live miss today**. But the script's own "known and accepted limits" section calls
the silent direction the one that matters and does not list this. The fix is one line: replace the
first-argument test with `NOT EXISTS (an unguarded identity argument)`. I ran that variant against production:
it returns **the identical 72**, so the hardening is provably non-regressive on the live estate.

**Observation, not part of the verdict.** The self-test's local docker readiness loop is racy — 1 of 3 runs
died on `FATAL: the database system is shutting down`, because `pg_isready` succeeds against the postgres
image's initdb bootstrap server. CI is unaffected (it uses the service container's own health check via
`KAN175_TEST_DB_URL`). `pg_isready -h localhost` plus a real `SELECT 1` fixed it for me, 100% across runs.

### What I did NOT do, and why

**I recorded no verdict and transitioned nothing.** `review_context.review_owner` is **`backend-5`**, the
reviewer that was lost — not me. `store.record_review_result` enforces `if reviewer != owner: raise
StateError("not-review-owner")` (`store.py:921-923`), so my verdict is REFUSED as state until review
ownership is re-resolved from `backend-5` to `backend-7`. Resolving the owner is not mine to author for
myself — the function's own docstring says deriving the owner rather than accepting one is the entire point.
**This is a blocked state, and it is the correct outcome, not a failure to route around.** Raised for the
Orchestrator. Note also that under PEER doctrine (`WORKFLOWS.md:504-512`) a FAIL transfers execution
ownership to the reviewer — so recording this FAIL hands ME both fixes, which is proportionate: both land on
surfaces already declared on the ticket and neither is a migration.

Record read at revision 11. I wrote nothing to Persistent State. Ownership still held by `backend-2`.

**Follow-up, same day — verified there is NO sanctioned path to hand me the record.** `resolve_review_owner`
(`store.py:783`) is write-once: `if rc.get("review_owner"): raise StateError("review-owner-already-resolved
... replacing a reviewer is a separate authority decision")` (`:841-846`). Confirmed at source rather than
taken from the lead's account. **The ordering matters:** the write-once guard fires BEFORE
`policy.peer_eligible` is evaluated (`:848-856`), so my being an eligible backend reviewer is irrelevant —
the call is refused on the existing owner alone. There is therefore no Orchestrator path either, and
reviewer replacement is an authority decision, not a state operation. Standing by; verdict unchanged.

---

## 2026-09-10 — KAN-175 `48e3664` independent check (second opinion, NOT the recorded verdict). **AGREE.**

Dispatched by `team-lead` as an independent check alongside `backend-5`'s cycle-2 **self**-review, because I am
the seat that found AC7 and `backend-5` had both authored the deliverable and missed the defect. I recorded
nothing and transitioned nothing — the verdict of record is `backend-5`'s. STOP on KAN-175 respected: no DDL,
no DML, no migration, no commit, no push.

**AC7 — closed, and I proved the probe fails before crediting it as passing.** I extracted the OLD predicate
straight from `48e3664^` (`git show`, not retyped), the NEW one from `48e3664`, seeded both against the SAME
fixture set on my own disposable `postgres:16`, and diffed:

* OLD (`LIMIT 1`) flags **5** — `rpc_second_arg_unguarded(p_user_id uuid, p_profile_id uuid)` **absent**.
* NEW (`EXISTS`) flags **6** — the set difference is exactly that one signature, and nothing is lost.

So the blind spot is demonstrated live, and the regression case genuinely discriminates the fix from the bug.

**The CASE J sanity check is NOT vacuous — I falsified it deliberately.** I built a sealed twin,
`rpc_second_arg_sealed`, identical but guarding BOTH arguments. Its sanity check **FAILED** (it raises; no leak)
and the new predicate correctly **did not flag** it. A fixture that cannot leak therefore cannot pass this
check, which is precisely the failure mode `team-lead` asked me to rule out. Note also that the *guard-fires*
property is asserted on CASE F (`:171-173`, same guard shape, same fixed `auth.uid()` at `:82-83`), not on
CASE J itself — adequate coupling, but worth knowing where the assertion actually lives.

**Non-regression is a THEOREM here, not just a measurement — which answers `team-lead`'s sharpest question.**
The worry was that identical counts (72 = 72) could hide changed membership. It cannot, because
**NEW ⊇ OLD by construction**: if the `LIMIT 1` form flagged a function, the argument it happened to select was
unguarded, so `EXISTS (an unguarded identity arg)` is necessarily true and the new form flags it too — whichever
argument the unordered `LIMIT 1` picked. `no_longer_flagged` is therefore empty on *any* database, not merely on
this one. Given the superset, **count equality implies set equality**, so my own earlier same-day production
measurement (the EXISTS variant returning an identical 72) already closes `newly_flagged` independently of
`backend-5`'s `EXCEPT`. The two directions corroborate.

**Self-test 12/12 green on a real disposable Postgres**, my own run, my own container: 6 must-flag, 4 must-not-flag,
2 diff directions. Was 11. Three fixture sanity checks run in addition to the 12.

**KAN-61 unregressed, and the fenced SQL does NOT leak into the parser** — the thing most likely to break a
marker-delimited block, checked empirically rather than accepted. §2f extracts exactly **11** view names, §2g
exactly **74** signatures, and *zero* extracted lines fail a shape filter in either block. The new blockquoted
```sql fence sits at `docs/SCHEMA.md:608-617`, between §2f's END (`:584`) and §2g's START (`:667`) — outside both
awk ranges. `check_anon_allowlist_test.sh` green both directions. `bash -n` clean on all four scripts.

**Scope confirmed: four files, nothing rode along.** `docs/CONVENTIONS.md` and
`20260910090000_kan130_kan131_wallets_owner_and_platform_identity_migration.sql` are dirty in the worktree and
**untouched by the commit**.

### What I could NOT verify myself, stated rather than papered over

The Supabase MCP token is **expired** this session, and no direct `SUPABASE_DB_URL` is available to me
(it is a GitHub Actions secret; reading the local `.env` was refused by the permission classifier and I did not
work around it). So I re-measured nothing against production today. What carries the AC6 figures is my OWN
measurement from earlier today, recorded above in this file: **303 / 1,746 / 290**, which matches the corrected
prose exactly. **The `1,761` total-functions denominator is new in this commit and rests on `backend-5`'s
measurement alone — I have never measured it.** It is the one AC6 number with a single source.

### Finding to carry, NOT a blocker and NOT grounds to fail

`scripts/ci/anon_function_grants_diff.sh:141-142` still reads *"Both populations are far too large to allowlist
name-by-name (**303 and 292** live)"* against "AC1's first two bullets" — the identical ~6x mislabel AC6 exists to
correct, surviving in the gate's own source comment three lines above the census SQL. AC6 names exactly two
locations (`scripts/ci/README.md:42`, `docs/SCHEMA.md:600`) and **both are corrected**, so the criterion is met as
written and I am not failing the ticket on it. But it is a real residual instance of the same defect and should be
swept. Same file, stale-not-mislabelled: `:25-26` and `:51` say `292` where `both` is now `290`, and `:57` cites
76 identity-carrying functions against the 74 I measured.

**Verdict returned to `team-lead`: AGREE.** AC7 is genuinely closed; AC6's named locations are corrected to
figures matching my own independent measurement.

---

## 2026-09-11 — KAN-193 PREFLIGHT (assessment only; no claim, no execution)

Asked by `team-lead` for Work Effort, Surfaces, and per-AC satisfiability without a live database. Read the
ticket, `scripts/ci/anon_function_grants_diff.sh`, `check_anon_function_grants.sh`,
`check_anon_function_grants_test.sh`, `.github/workflows/anon-allowlist-check.yml`, `scripts/ci/README.md`.

**Work Effort: 1 sitting.** One emission change inside `anon_function_grants_diff()`, plus a fabricated two-run
membership-change case in the self-test. The predicate SQL, the census SQL and the `comm` set difference are all
untouched, and the CI wiring does not change. The disposable `postgres:16` harness the test already uses is the
same one I built and drove earlier today under KAN-175, so there is no substrate to stand up.

**Surfaces (assessed, three paths):**
- `Dabbler/dabbler-code/scripts/ci/anon_function_grants_diff.sh`
- `Dabbler/dabbler-code/scripts/ci/check_anon_function_grants_test.sh`
- `Dabbler/dabbler-code/scripts/ci/README.md`

Deliberately NOT surfaces: `check_anon_function_grants.sh` (the emission belongs in the shared function, which is
the file's own stated reason for existing — runner and self-test must execute identical logic); `docs/SCHEMA.md`
(§2g is referenced, not edited — the allowlist must stay unmodified for AC4); `anon_allowlist_diff.sh` and the
workflow YAML (out of scope).

**Per-AC satisfiability without a live database: AC1, AC2, AC3 yes; AC4 no.**
AC1–AC3 are all exercisable against the disposable container. AC4 asserts the workflow's function-grants step runs
green against the *live* `wtncuzcskpigqpmnxwws` signature state; `SUPABASE_DB_URL` exists only as a GitHub Actions
secret and the Supabase MCP is expired, so it is observable only from the workflow run on push to `Canary`.

**One thing the AC2 wording forces, recorded before I build it:** the self-test currently calls
`anon_function_grants_diff ... >/dev/null` (`:211`) and `>/dev/null 2>&1` (`:220`), so an emission added inside
that function is swallowed by every existing assertion. AC2 needs new capture-based assertions, not a reuse of
those two. And AC1's "on any run" covers the FAIL path too — today that path names only the *offenders*, never the
full flagged population, so emitting the complete set on both paths is part of the change, not just the OK line.

**Adjacent, recorded not acted on:** `anon_allowlist_diff.sh:31` (the KAN-61 VIEW gate) has the identical
count-not-membership shape — `echo "OK: all $(wc -l < "$live_file") ... view(s) are on the allowlist."`. Out of
KAN-193's bounds (function gate only) and out of the burn-down brief's bounds (no sweep of other CI scripts). Not
recorded in the discovery ledger by me this turn: preflight is assessment, and I will decide at execution whether
it belongs there or nowhere.

Reported to `team-lead`. Awaiting claim before any execution.

## 2026-09-11 — KAN-193 EXECUTED (Back-end 10043; awaiting PEER)

Claimed by `team-lead`, continuation gate passed. Transitioned `KAN-193` to **Back-end (10043)** via
transition `5`, read back from the live API before calling (`G-018`) rather than trusted from `board.py`.

**Lifecycle discrepancy, recorded not corrected:** the claim message described the ticket as `Ready/10008`.
Jira's pre-transition status was **`To Do` (10004)**, the Backlog column — not `Ready`. `10008` is the Task
*issuetype* id, which is probably where the confusion came from. The destination was mine to set and is
correct either way; I did not silently "fix" the origin status, and `po` owns that column.

### The defect, reproduced before anything was written

Built the add-and-drop against a disposable `postgres:16`: one signature contained
(`rpc_gamma_roster`), a different one introduced (`rpc_delta_intake`), allowlist covering both so the
gate stayed **green on both runs**. Against the pre-change script the two runs' outputs were
**byte-identical** — count 3 → 3, nothing named. That is the ticket's masked case, observed rather than
argued. Post-change the same probe names exactly the departure and the entrant.

### What changed — three files, 227 insertions, 1 deletion

- `scripts/ci/anon_function_grants_diff.sh` — the full flagged population is emitted between
  `ANON_FUNCTION_FLAGGED_BEGIN/END`, `LC_ALL=C` sorted, one signature per line, **before** the pass/fail
  branch so neither exit can skip it. The `OK:` count is now derived FROM the emitted block, so the
  number and the membership cannot drift apart — a count irreconcilable with its own membership being
  the whole defect.
- `scripts/ci/check_anon_function_grants_test.sh` — capture-based assertions for AC1 (both exits) and
  AC2 (the masked add-and-drop, named in both directions).
- `scripts/ci/README.md` — documents membership-not-count, and corrects a stale case count.

**`docs/SCHEMA.md` is clean and §2g is untouched**, so AC4's "unmodified allowlist" half is true by
construction. **`comm -23` is untouched** — confirmed by `git diff -U0 | grep 'comm -23'` returning
nothing — so AC3's comparison path provably did not change.

### Every new probe demonstrated FAILING first

Ran the new self-test against a pristine copy of the pre-change diff script: exits 1, reporting
*"the diff script defines no flagged-population markers"*, both reconstruction assertions failing, and
both AC2 naming assertions failing. The two AC2 assertions that still pass under revert are the ones
asserting the *scenario* is genuinely masked (both green, counts equal) — they must hold in both worlds,
which is their job.

**That revert run found a real defect in my own test code:** `diff | sed` under `set -o pipefail` aborted
the run mid-report, swallowing every later assertion. A test whose failure path is itself broken reports
"bash error" instead of "the gate went back to printing a count". Fixed with `{ diff || true; } | sed`,
and the marker check now reports a clean FAIL rather than dying on `set -u`. I would not have found
this without running the probe in its failing state.

Also caught and fixed in my own output: the red-path message said *"The 2 signature(s) above"* where `2`
was the population count and "above" was the 1-entry offender list — a count/membership mismatch in the
very message added to fix count/membership mismatches.

### Not done, deliberately

**Did not commit.** `devops` owns commit and push. The working tree also holds other agents' uncommitted
work (`docs/CONVENTIONS.md`, `lib/data/models/squad.*`, a `kan181` migration, `test/data/models/`) and
this ledger already records two instances tonight of unrelated work being swept into a commit that
touched the same tree. File list and commit message handed to `team-lead` instead.

**AC4 not verified here** — needs the live `SUPABASE_DB_URL`, a GitHub Actions secret. Route is
`devops` pushes `Canary`, then read the job log.

Discovery ledger entry written for `anon_allowlist_diff.sh:31` — the KAN-61 **view** gate carries the
identical count-not-membership shape. Recorded, not fixed, not ticketed.

**Route: PEER. Reviewer must be another `backend-N`, never `frontend-7`.** Not released.

### 2026-09-11 — KAN-193 PEER PASS, two review items closed

`backend-6` passed it after independent reproduction (own fixtures, own names, own container) and
**refused my AC3 evidence as insufficient** — correctly. I offered `grep 'comm -23'` returning
nothing, which proves *one string survived*, not that the decision logic did. It extracted the
function body from HEAD and from the tree, stripped comments and every `echo`/`printf`, and diffed
the remainder: three assignments and one `if` added, predicate/branch/returns byte-identical and in
order. **Structural, not textual.** Adopting that as my standard for "I didn't touch the logic" —
a grep for an unchanged line is evidence about a line, not about behaviour.

**Its README finding was my own defect class, and worse than the original.** `:107` still read "nine
cases (five that must be flagged, four that must not)" while `:111`, two lines below, said ten and
six — *and my parenthetical claimed in the past tense that :107 had already been corrected.* I wrote
a correction note for a correction I never made. Fixed by removing the count from `:107` entirely:
**the count now exists in exactly one place**, because carrying it in two is how the stale one
survived KAN-175 in the first place. The note records what happened and credits the catch.

**Stream observation, decided and recorded in-source.** The block goes to stdout, the failure
message to stderr, and that message claimed the block was "earlier in this log" — a positional claim
across two pipes that buffering does not guarantee. Options were: route the block to the verdict's
stream, or drop the positional claim. **Chose to keep the block on stdout unconditionally** and name
the stream instead ("printed in full ON STDOUT, between the markers"). Making the block's stream
depend on exit status would force a consumer to know how the run ended before it could find the
block, which is backwards. Reasoning left as a comment so it is not "tidied" later.

Re-verified after both edits: self-test exit **0**, all AC1/AC2 assertions pass; revert run against
the pristine lib exits **1** with 8 FAIL lines and still reaches the final verdict line. Surfaces
still exactly three; `docs/SCHEMA.md` clean.

Not committed, not released. AC4 remains with the Canary job log.

### 2026-09-11 — KAN-193 characteristics asserted; AC4 closed on the live log

`store.set_characteristics('KAN-193', expected_revision=5, changes={'security_sensitive': True},
author='worker:backend-7')` → revision 6, route **`peer`** derived by `system-policy`.

**Asserted exactly one true, and did not write `False` for the other three.** Absent means false;
writing an explicit false would stamp provenance saying I *asserted* a fact I am merely not
claiming. Basis for each recorded in Jira comment `10993`, because `set_characteristics` stores
only `{by, at}` and a basis kept nowhere is a basis lost.

**`schema_change` is FALSE and that deserved thought rather than reflex.** My seat's work is
usually schema work, and my role contract says my schema work is always PEER *computed from
`schema_change`*. This ticket is a bash script — no DDL, no grant, no migration; the self-test's
functions live in a container destroyed on exit, which is fixture data. Asserting `schema_change`
would have produced the right route (PEER) for the wrong reason, and a false fact in the record is
worse than a missing one. PEER here comes from `security_sensitive`.

**`security_sensitive` TRUE**, on the argument that a control which cannot attribute a change in
what it controls has a degraded security property even with its pass/fail logic untouched — not on
"it touches a security file". `backend-6` made the same call on a census that mutated nothing.

**AC4 closed on the live job log**, and the block proved itself on its *second* run: devops diffed
this run's `ANON_FUNCTION_FLAGGED` block against the preceding run's — byte-identical, 65 lines,
zero diff. "65, unchanged" is now a measured fact rather than an unattributable count. It mattered
at once: KAN-188 relocated five functions out of `public` in that same window, and the diff shows
none were in the flagged set before or after — unanswerable a day ago.

**Reported, not corrected:** Persistent State `lifecycle` still reads `ready`/`10008` observed
2026-09-10T23:46Z while Jira has been `Peer-review` since I transitioned it. Jira is lifecycle
authority and reconciliation is not a worker's write.

Not released.
