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
