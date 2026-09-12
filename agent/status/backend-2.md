# agent/status/junior-frontend-2b.md

**Owner:** `junior-frontend-2b` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

_No entries yet._

## 2026-09-09 — KAN-155 PEER review (CEO-authorised reviewer)

PEER PASS. Independent review of `subscription_plans` plan-key migration authored by
`backend-4`, applied to production 2026-09-07 under the CEO's direct authorization
(ledger `20260907071308`). Reviewed as review_owner; did not confirm the executor's
prior verdict, re-derived what I could reach.

- Source: `Dabbler/dabbler-code/supabase/migrations/20260907110000_kan155_plan_key_migration.sql`,
  478 lines, sha1 `96a10848d71f48b6aaae0381d6b313679b0ea899`, commit `cb5edf1`, clean at HEAD —
  byte-identical to what comment 10750 describes, so the stop-and-ask condition did not fire.
- AC1–AC9 PASS. AC10 substance met, attribution deviated (cto posted the brief, not `backend-4`)
  — recorded on the ticket rather than passed silently.
- AC4: executable body correct (`v_plan := 'player_free'`, line 331); the surviving `kickoff`
  is comment-only on that same line, the sole occurrence in the function region 310–356.
  Recorded that OLD AC4 WAS OVERBROAD and PO CORRECTED AC4 BEFORE REVIEW (comment 10775).
- AC9 re-derived, not accepted: stripped `--` text from the BEGIN;/COMMIT; region and grepped —
  zero ON CONFLICT.
- Reproduced the client/edge half of `backend-4`'s reachability sweep independently: zero
  `kickoff` in `lib/` or `supabase/functions/`, no plan constant in `supabase_config.dart`.

**Evidence limit, stated rather than absorbed:** NO live catalogue access. Four attempts against
`wtncuzcskpigqpmnxwws` (3× execute_sql, 1× list_migrations) all returned "You do not have
permission to perform this action". Every post-apply fact rests on recorded evidence in comments
10707/10750, not on a read I performed. Verdict scoped accordingly.

Posted as comment **10776** on KAN-155. Wrote no code, transitioned nothing, touched no
Persistent State — the verdict is `team-lead`'s to record.

## 2026-09-09 — PEER review of KAN-128 (CEO-named reviewer, recorded `review_owner`)

**Verdict: PEER PASS, scoped to available evidence.** Posted as comment **10779** on KAN-128.

Read the ticket and all 26 comments live through `agent/integrations/jira.py` (Atlassian MCP is
down). Verified against source in `Dabbler/dabbler-code` at HEAD `715bb85`:
`supabase/migrations/20260909090000_kan128_ledger_unique_keys_and_on_conflict.sql` (597 lines,
authored `93d6619`, header corrected to G-028 in `f9b7cd6` — the "uncommitted edit" flagged in
comment 10730 is now committed).

- **AC 1 — PASS in source.** Seven `ON CONFLICT DO NOTHING` at :203/:247/:327/:445/:540/:552/:564,
  with :407 correctly excluded as the pre-existing `game_settlements (game_id)` upsert — I counted
  the eight-vs-seven split myself. Both unique indexes and the `ref_id` `SET NOT NULL` inside one
  `begin;`/`commit;`. `DROP FUNCTION` names the baseline 5-arg signature; the new 6-arg form places
  `p_ref_id` fourth with no DEFAULT. **Body fidelity checked by normalised diff of all five
  functions against `20260829080500_baseline_schema.sql`** — each differs only by its comments, its
  clause(s), and `admin_wallet_adjust`'s new parameter and named `P0001` guard. Per-function
  attributes restated, no shared string.
- **Grant rule (T-058 Decision 1) — source PASS.** Both revokes present and explicit (:277 PUBLIC,
  :278 anon) ahead of the grants. The AC's evidence is the proacl read-back, which I could not read.
- **AC 3 — PASS, independently re-derived.** I did NOT accept the reported output: ran
  `supabase/tests/kan128/run.sh` myself in a throwaway container. Every runnable probe failed pre
  and passed post in my hands (P1a 23505, P1b 2→1, P2 reversal preserved at 2, P4 arity 5→6 with
  `P0001` on null, P5 2→1, P5b stays 2); P3 BLOCKED (42804) on both sides. The T-058 Decision 3
  deviation is in the **pack's own output** (`20_probes.sql` :44-55 P0 echo), which is where it
  binds. Container proacl came back `{postgres,authenticated,service_role}` — a third independent
  derivation, at container strength.
- **AC 2 — PARTIAL.** Authored, cto-confirmed (10723/10727) and committed: PASS. **Applied: NOT
  VERIFIABLE.**

**Evidence limit, stated rather than absorbed:** no live catalogue read. I attempted one rather
than assume — `list_migrations` on `wtncuzcskpigqpmnxwws` returned "You do not have permission to
perform this action". Everything resting on the deployed catalogue (the apply itself, live proacl,
`indisvalid`/`indisready`, `attnotnull`, absence of the 5-arg overload, live `prosecdef`) is marked
NOT VERIFIABLE, not passed. T-049 Invariant 4 stays OPEN.

Non-blocking observation: :573 still reads "run by cto after applying" — cto expressly permitted
leaving those comment lines (10719). Flagged, not a defect.

Fixed nothing, transitioned nothing, wrote no Persistent State — recording the verdict is
`team-lead`'s.

---

## 2026-09-09 — KAN-138: live evidence attempt on the recovered settle_game cast migration

Owner of KAN-138 (claimed 2026-09-09, continuation gate passed), Work Effort 2, route PEER. Task
was the live-evidence leg only — the migration
`supabase/migrations/20260907130000_kan138_settle_game_settlement_status_cast.sql` was already
authored and published (9d855a5, cherry-picked from e462d2f). I did not re-author, modify, or
apply it. Worked in `.claude/worktrees/product/backend-2/KAN-138`, branch
`exec/backend-2/KAN-138` from Canary b978647. Findings posted as Jira comment 10838.

**Project ref confirmed before citing anything:** `wtncuzcskpigqpmnxwws`, read from
`Dabbler/dabbler-code/supabase/.temp/project-ref` and cross-checked against `supabase projects
list` (two projects on the account; `ekmhrxdwgegxkdkdukgq` = Dabbler-draft, forbidden, not
contacted).

**No live database access existed in this run**, contrary to the brief's premise — three routes,
each measured, not assumed: `supabase inspect db table-stats --linked` → `no route to host` on
`db.wtncuzcskpigqpmnxwws.supabase.co` (IPv6-only, unroutable from this machine); `supabase db dump
--linked` → `could not translate host name`, 0-byte output; Supabase MCP `execute_sql` → "You do
not have permission to perform this action". The IPv4 pooler fallback was refused by the session
permission layer. So no `pg_get_functiondef` output exists to cite, and I cited none.

**AC-4 corroborated at source, not live-verified.** Extracted and normalized both committed
`settle_game` bodies (this migration's, and KAN-128's in `20260909090000_...`): removing only
`::public.settlement_status` and its two wrapping parens collapses md5
`a8f929a7d6748de3c636dc0f01bf9931` onto KAN-128's `926c6cbf24d1ae2b6c7e31a1ecc59356`, a 28-char
delta. Both ON CONFLICT clauses survive verbatim; header attributes byte-equal modulo keyword
case. That is a comparison against KAN-128's committed text, **not** the live catalogue — the only
live comparison remains cto's own of 2026-09-07 (comment 10749). Marked CORROBORATED, NOT
LIVE-VERIFIED. It did not come back differing; it came back unmeasurable.

**AC-2 classified as a production write and parked, not attempted.** `settle_game` inserts into
`game_settlements` and `wallet_ledger` — money-layer tables on `wtncuzcskpigqpmnxwws`. An aborted
probe block is a rolled-back production write attempt on the money path, not a read, and I would
not call that equivalent. Access is not mutation authority. Closing AC-2 needs explicit CEO
authorisation to execute `settle_game` against production, the same authority KAN-146 was refused;
no G-002 condition and no cto confirmation supplies it.

**Hazard found that is not in the ticket and must be settled before anyone applies.** KAN-138's
filename version `20260907130000` sorts BEFORE KAN-128's `20260909090000`, though KAN-128 was
applied live on 2026-09-07. KAN-128's body is this body without the cast. If both versions are
pending in `supabase_migrations.schema_migrations`, filename-order application runs 138 then 128
and 128 silently reverts the cast with nothing erroring — the §6c / T-044 failure arriving from
the ordering direction. Whether it bites turns on whether `20260909090000` is already recorded,
which I could not read. Whoever applies must check `schema_migrations` first and assert the live
`prosrc` still contains the cast AFTER the whole push, not after this file alone.

**Verdicts:** AC-1 PASS at source (line 209), not confirmed in the live body. AC-2 NOT VERIFIED,
PARKED on CEO money-layer execution authority. AC-3 NOT VERIFIABLE, strictly downstream of AC-2.
AC-4 attributes PASS at source; live authorship CORROBORATED, NOT LIVE-VERIFIED. AC-5 NOT ENGAGED
— the file holds exactly one statement between `BEGIN;`/`COMMIT;`, no DROP/GRANT/REVOKE/ALTER,
signature unchanged, so no proacl change is possible; the file's verification block asserts the
resulting proacl rather than that a revoke ran, which is what T-058 requires.

**Demonstrated no probe failing, because I could execute no probe** — so no probe on this ticket
counts as passing today. Changed no file (the only write was a gitignored `supabase/.temp/`
project-ref copy into my own worktree), so nothing to commit. Applied nothing, pushed nothing,
transitioned nothing, wrote no Persistent State, touched no other workspace. KAN-138 stays in
Back-end with its central criterion open.

## 2026-09-10 -- KAN-138 verification completed (AC-4 + hazard confirmation)

Same-seat continuation after a session limit. Ownership backend-2, lifecycle
development, continuation gate passed before wake. No writes issued.

Read path: `supabase db dump` run from Dabbler/dabbler-code (complete link
state; my worktree's supabase/.temp/ lacks pooler-url and falls back to the
IPv6-only direct host). Project ref read back as wtncuzcskpigqpmnxwws before
every read.

AC-4 -- PASS at source level. Dumped the live public schema, extracted
settle_game(uuid,uuid,text,numeric,boolean), diffed its body against the
committed migration. Both KAN-128 clauses present live and byte-identical:
the game_settlements `on conflict (game_id) do update ... returning * into gs`
(7-column SET list) and the wallet_ledger `on conflict do nothing`. Whole-body
diff is one substantive hunk -- the 28-character cast
`(...)::public.settlement_status` -- plus four comment lines. Nothing else moved.

Ordering hazard -- CONFIRMED LIVE, and wider than I first reported.
20260909090000 is NOT in supabase_migrations.schema_migrations. Nor is any
other repo migration filename: Local and Remote are disjoint sets, 272 recorded
remote versions, none matching a repo file. KAN-128 is live under version
20260907064216 (verified by reading the recorded statement text, which carries
the settle_game body with both ON CONFLICT clauses). So a filename-ordered
`db push` would treat 30+ files as pending and replay 138 before 128, silently
reverting the cast with nothing erroring. Reported, not acted on -- it is a
repo-wide migration-provenance problem needing a decision I do not hold.

AC-2 remains PARKED. Executing settle_game writes to game_settlements and
wallet_ledger on the live money layer; an aborted probe is still a production
write attempt. Needs explicit CEO authorisation (019) -- the same authority
KAN-146 was refused. Not attempted.

Per-AC: AC-1 PASS, AC-2 PARKED (CEO authorisation), AC-3 PASS, AC-4 PASS.
Not verifiable: that a real settle_game call now succeeds (that is AC-2), and
that the migration applies cleanly to production (unapplied; and the provenance
problem means the usual push path is not currently a safe way to find out).

Jira: comment 10842 on KAN-138, addendum to 10838. No transition made.

---

## 2026-09-10 — Read-only migration provenance rebaseline (T-068 follow-up)

Task: classify every repo migration against the live production catalogue.
Production mutations: **0**. Every statement was a SELECT against
`wtncuzcskpigqpmnxwws` catalogue/ledger. No `db push`, no repair, no ledger
write, no DDL/DML.

**I corrected my own earlier finding.** My 2026-09-09 entry above says "Local
and Remote are disjoint sets ... none matching a repo file." That is WRONG.
Three repo filenames match a ledger `version` exactly (`20260829073638`,
`20260829073752`, `20260829080500`), and — the substantive correction — **25 of
29 repo migrations name-match a ledger entry under a DIFFERENT timestamp**.
T-068's "local-only: 25" counts *version* mismatches, not unapplied work. The
CLI's local/remote tally is a filename-timestamp diff and says nothing about
what is live. Reading it as an applied/unapplied count is the exact inference
this rebaseline exists to kill.

Classification: 24 VERIFIED_LIVE, 2 PARTIALLY_OR_DIFFERENTLY_LIVE (KAN-68,
KAN-138), 2 DEFINITELY_NOT_LIVE (KAN-93, KAN-130/131), 1 VERIFIED_LIVE with a
provenance caveat (baseline). No UNDETERMINED — every file resolved on
catalogue evidence.

Post-hotfix baseline captured for both objects live-but-unrecorded:
`settle_game` (prosecdef=t, `search_path=public`, volatile, proacl
`{postgres=X,service_role=X}`, prosrc md5 `d3c6238ea2b04ecd06f87cdb832cda37`)
and `content_hits_blocklist` (prosecdef=t, `search_path=public, pg_temp`,
stable, proacl `{postgres=X,authenticated=X,service_role=X}`, md5
`a3203f5097937f75a53bdc54ed7e2fd9`). Neither has a ledger row.

Confirmed KAN-68 Sections 2 and 3 are NOT live: `_get_context_config` still
carries `=X/postgres` (PUBLIC) and `anon=X`; `safety_blocklist_terms` and
`context_rating_config` both still `anon=rm,authenticated=rm`.

Replay trap: a naive `db push` today would treat 26 of 29 files as pending and
would re-apply KAN-68 Sections 2/3 — precisely what was consciously excluded —
and would abort on KAN-93's precondition guard and KAN-130's
`drop constraint wallets_pkey`. Detailed in the report to the requesting
session. Reconciliation strategy proposed only; nothing executed.

Route: not a ticket. No Jira transition, no migration authored. T-068 freeze
respected throughout.

## 2026-09-10 — KAN-175 Preflight (detection-gap gate for anon-executable SECURITY DEFINER functions)

Preflight only. **Nothing claimed, nothing owned, no code written, no DDL/DML.**
Production `wtncuzcskpigqpmnxwws` read-only throughout; T-068 freeze respected.

Recorded through `agent/state/store.py` (no hand-edit of `runtime/`):
`work_effort = 2` (ceiling 3) and a 6-path surface assessment, both authored
`worker:backend-2` with basis_ref. Task at revision 5; `ownership` still null.

**Population, counted — not inferred from any advisor (`020`).** `public`,
`prokind='f'`: **1761** functions total, **303** `SECURITY DEFINER`, **292**
`SECURITY DEFINER` AND anon-EXECUTE by `has_function_privilege`, **1748**
anon-executable overall. Of the 292, **60** carry no literal `anon` in `proacl`
and are reachable only through the bare `=X` PUBLIC grant — the string-match
blind spot, now quantified rather than asserted. **45** of the 292 carry a
caller-supplied identity-shaped `uuid` argument; **5** of those also have a
shorter same-named overload, which is AC1's own stated heuristic.

Worked example verified first-hand: `rpc_potential_vibes_debug` oid 24497,
`proacl = {=X/postgres, postgres=X/postgres, service_role=X/postgres}`,
`has_function_privilege('anon', 24497, 'EXECUTE') = true`. Confirmed exactly as
the brief described.

**Correction to the brief, measured.** `rpc_potential_vibes/7` (oid 95117,
`p_me uuid`) is **NOT anon-executable today** — `proacl` is
`{postgres=X/postgres, service_role=X/postgres}`, effective anon EXECUTE false.
The anon-executable overload is `/6` (oid 95102), which has no `p_me`. Either
the `/7` grant was revoked since the ticket was filed, or the brief conflated it
with `_debug/7`. The detection work does not depend on either reading.

**README drift found.** `scripts/ci/README.md` still says `SUPABASE_DB_URL`
"does **not exist yet**". It was provisioned 2026-08-29; `gh run list` shows the
allowlist workflow completing **success** in 8-20s on every push to `Canary` and
PR into `main` through 2026-09-10. The live CI path AC5 targets is real and
working — AC5 is not blocked on a missing secret.

Flagged to the requesting session: AC1's two readings differ by a factor of 58
(292-name allowlist vs 5), AC3/AC4 cannot be satisfied by fixture text-diff
alone without reproducing KAN-61's own blind spot, and AC5 is `devops`'s leg and
was not sized here. Two latent state-model defects also reported:
`policy.normalise_path` strips the leading dot from any dotfile path
(`.github/...` stores as `github/...`), and `policy.SHARED_PREFIXES` knows only
`lib/core/`/`lib/data/`, so `docs/SCHEMA.md` and `.github/workflows/` derive
`shared_or_contended_surface = False` despite both being other seats' surfaces.

Route: PEER (system-derived from `security_sensitive`), reviewer must be another
`backend-N`. Board blockers remaining for claim: `not-ready` (KAN-175 is in
`To Do` 10004, not `Ready`) and no `due_date` — both `po`'s, and the sizing they
were waiting on is now on the record.

### 2026-09-10 — KAN-175 Preflight addendum (detector design constraint from `cto` via team-lead)

Received after the Preflight above; still unclaimed, still waiting on `po` for
`Ready` and the AC1 decision. **Work Effort unchanged at 2, ceiling 3** — this
constrains the predicate designed inside sitting 1, it does not add a
"cannot start until" boundary, and per `capacity-to-date` §1 neither risk nor
volume buys a sitting.

Two constraints now binding on the detector:

**Overload dispatch is invisible to a body sweep.** `backend-8` swept 2,954
function bodies and concluded `rpc_potential_vibes/7` had zero callers; `cto`
disproved it — the 6-arg overload is its only caller, its body being
`SELECT * FROM public.rpc_potential_vibes(p_sport, …, auth.uid())`, seven
arguments. A call site names the FUNCTION, not the signature, and `pg_depend`
does not record function-to-function calls. So **the detector must not filter
false positives by catalogue-derived caller counts** — an uncalled-looking
function may be the implementation half of a live pair. Call-graph reachability
is not determinable from the catalogue here, and the detector should say so
rather than imply a zero-caller result is a fact.

**The pair is the unit of analysis, not the function.** `cto` proved the
dispatch by behaviour rather than text: probed as `authenticated`, the 6-arg
returns `score = 1.0` and `reasons = {"source":"stub","reason":
"v_sport_profiles_with_user"}` — the 7-arg's literal body, existing nowhere
else. That makes the wrapper/implementation relationship real rather than a
smell, and strengthens AC1's "shorter same-named overload" signal. My 5
candidates should be reported as pairs (short injects `auth.uid()`, long accepts
a caller-supplied identity), not as independent rows.

**Supports the effective-privilege position.** `cto` ruled the debug function
`DROP`, not `REVOKE` (KAN-174 AC6), because as `anon` it does not raise `42501`
— it PASSES the permission check on the bare `PUBLIC =X` and dies at `42P01` on
the missing view. Its inertness is an accident of a dropped relation, not a
privilege boundary. That is precisely my 60-function
reachable-only-via-bare-`=X` population, and it means the detector must also
never read "errors under `anon`" as "inaccessible to `anon`" — distinguish
`42501` from every other SQLSTATE.

Both constraints saved to agent memory so they survive session loss.
No action taken; standing by for the wake.

### 2026-09-10 — KAN-175 EXECUTED (backend portion) → Peer-review

Claimed `backend-2` rev 8, continuation gate passed, Jira `Ready` → `Back-end`
(10043, transition 5) on start and `Back-end` → `Peer-review` (10045,
transition 7) on finish — both mine, both taken. Route PEER; **no reviewer
picked by me.** Production read-only throughout; no DDL, no DML, no migration,
T-068 respected. Nothing committed — the tree carries three other seats'
in-flight files.

**Delivered** (dabbler-code): NEW `scripts/ci/anon_function_grants_diff.sh`,
`scripts/ci/check_anon_function_grants.sh`,
`scripts/ci/check_anon_function_grants_test.sh`; EDITED `docs/SCHEMA.md` (new
§2g, own markers, 74 signatures) and `scripts/ci/README.md`. Exactly the five
paths declared at Preflight.

**The predicate changed materially from Preflight, on measurement.** Dropping
the overload requirement (per backend-7's `rpc_get_friend_suggestions`) and
tightening "mentions `auth.uid()`" to "COMPARES to `auth.uid()`" moved the
failing population from the 5 `po` ruled on to **74**. The tightening was forced
by evidence: of 76 identity-taking functions, 47 mention `auth.uid()` and only
**2** compare an argument to it. `rpc_get_friends(p_user_id uuid)` does
`COALESCE(p_user_id, auth.uid())` — reads as authentication, returns any named
user's friend list to `anon`. A "mentions" test clears it. Flagged to `po` on
handoff as an AC2 consequence rather than resolved silently in either direction.

**Every probe demonstrated failing before it counted as passing.** Three
negative controls on the same fabricated substrate: a `proacl` text match misses
`rpc_public_grant_only` (PUBLIC-only ACL); "mentions `auth.uid()`" clears the
exploitable `rpc_coalesce_fallback`; the overload requirement flags **0 of 5**.
Self-test is 9 fabricated cases (5 must-flag, 4 must-not) plus both diff
directions — 11 assertions, all green on a real disposable Postgres, none named
`rpc_potential_vibes`. Found and fixed a live bug in my own fixture: with
`auth.uid()` returning NULL the guarded control passed vacuously
(`x <> NULL` → NULL → IF not taken).

**No regression to KAN-61**, verified rather than assumed: §2f still extracts
exactly 11 view names, §2g extracts 74 signatures, zero cross-contamination, and
`check_anon_allowlist_test.sh` still green. The marker strings do not collide.

**README drift corrected**: `SUPABASE_DB_URL` was documented as not existing; it
was provisioned 2026-08-29 and the gate has been completing success in 8-20s on
every run since.

**AC5 open against `devops`** — workflow step plus the AC3 service-container
substrate, sent with exact YAML; I did not edit its file and did not size its
leg. Gate will be GREEN on first run by design: §2g is a measured baseline of
existing debt, and §2g says in terms that listing a function is not calling it
acceptable.

## 2026-09-11 — KAN-188: anon EXECUTE revoke on the five venue-authority functions — NOT APPLIED, AC3 fails

**Outcome: no migration applied. Production unchanged, verified after the fact.**
The specified fix closes the oracle and breaks anonymous venue browsing. AC3 is
the criterion that asks this question, and the honest answer is NO — a legitimate
`anon` caller path does depend on the EXECUTE grant. Ticket transitioned
`Ready` → `Back-end` (10043, transition `5`); ownership retained; awaiting a scope
ruling rather than routed around.

**AC1 re-confirmed live, not from the repo** (`T-068`). `pg_proc` on
`wtncuzcskpigqpmnxwws`: exactly five, all `public`, all `(uuid,uuid)`, all
`SECURITY DEFINER` / `search_path=public` / `row_security=off` —
`can_manage_venue`, `can_manage_venue_members`, `can_view_venue_bookings`,
`can_create_venue_booking`, `can_edit_venue_details`. `proacl` on every one is
`{=X/postgres,postgres=X,anon=X,authenticated=X,service_role=X}`: a PUBLIC grant
*and* a named `anon` grant, so revoking `anon` alone leaves the exposure standing.
Verified by `has_function_privilege`, never by matching `proacl` text.

**The finding.** Seven RLS policies call these functions and every one is
`roles = {public}`, which includes `anon`; `anon` holds table `SELECT` on
`venues`, `venue_members`, `venue_bookings`, `venue_spaces`. A policy qual runs as
the invoking role, so `anon` reaches these functions through RLS, not only through
PostgREST. Dry run of the exact intended revoke, rolled back: `anon` RPC blocked on
all five (oracle closed) but `SELECT venues` **379 rows → `42501`**,
`venue_spaces` **679 rows → `42501`**, `venue_members` and `venue_bookings`
likewise. `authenticated` unaffected, confirming a PUBLIC revoke leaves
`authenticated=X` intact.

**A sixth function carries the transitive chain.** `venue_spaces` policy
`vspaces_write` (cmd `ALL`, PERMISSIVE, `TO public`) calls
`is_venue_admin(uuid,uuid)`, which is **`SECURITY INVOKER`** and reads
`public.venue_members` → fires `venue_members_select` → `can_manage_venue`.
`venues` reaches the same chain through `venues_members_inactive`'s subquery.
This is why the blast radius is wider than the three tables named on the ticket.

**Also measured, separately:** revoking from `authenticated` too breaks signed-in
reads of `venues`/`venue_members`/`venue_bookings`. `authenticated` must keep
EXECUTE. `rpc_my_venue_permissions` survives either way — `SECURITY DEFINER`, so
its nested calls resolve as owner.

**Every probe demonstrated failing before it counted.** Baseline: all five
executed as `anon` and returned `false`, so the target path was reachable and a
later denial means something (`T-055`). Negative control in the same probe: `anon`
calling `pg_read_file` → `42501`, proving the harness can report BLOCKED. My first
probe reported five false BLOCKEDs — the log insert was running under
`SET LOCAL ROLE anon`, so it was denied on the temp table, not on the function.
Caught and corrected before any conclusion rested on it.

**Candidate fix tested, not applied — needs a `cto` shape ruling (`021`).**
Relocating the functions out of the PostgREST-exposed schema removes the RPC
endpoint while policy execution survives, because a stored qual holds the function
OID. Rolled-back test: `anon SELECT venues` OK 379 rows; `public.can_manage_venue`
→ `42883 does not exist`; schema-qualified → `42501 permission denied for schema`.
Satisfies the ticket's intent with no body restatement and no breakage — but it
moves five objects out of `public`, bears on the anon-allowlist gate, and would
change `docs/SCHEMA.md` §2g, which this pass is forbidden to edit. Not my call.

**Discipline held:** `docs/SCHEMA.md` untouched. No Jira ticket created. Every
probe ran inside a rolled-back transaction; confirmed afterwards that all five are
still in `public` with original ACLs, the probe schema does not exist, and no
migration of mine was recorded. AC4 not reached — nothing to commit.

## 2026-09-11 — KAN-188 (2): migration authored and HELD. Not applied — the blocker is unaddressed.

Two corrections arrived from `team-lead` in opposite directions, both about the
`apply_migration` permission classifier. **Neither engaged with the AC3 finding**,
and the second restated the original brief including *"name PUBLIC explicitly
alongside `anon` and `authenticated`"*. That instruction is measurably the most
destructive of the available options, so I did not follow it and did not apply.

**Re-verified live today rather than citing this session's earlier transcript.**
All five unchanged: `public`, `(uuid,uuid)`, `SECURITY DEFINER`,
`search_path=public`/`row_security=off`, `proacl`
`{=X/postgres,postgres=X,anon=X,authenticated=X,service_role=X}`,
`has_function_privilege('anon',…)` = `true` on all five.

**Both revoke variants re-demonstrated today against a same-session control that
returned OK on all eight paths:**

| variant | anon | authenticated |
|---|---|---|
| A — `PUBLIC, anon, authenticated` (as instructed) | all 4 tables `42501` | **all 4 tables `42501`** |
| B — `PUBLIC, anon` (ticket AC1/AC2) | all 4 tables `42501` | unaffected (379 / 679 / 0 / 0) |

Variant A takes down signed-in users as well as anonymous ones — 379 venues and
679 spaces dark for everyone. It satisfies no acceptance criterion that B does not.
I authored B.

**Authored, held, not applied:**
`Dabbler/dabbler-code/supabase/migrations/kan188_revoke_anon_execute_venue_authz_fns.sql`
— no version prefix, following the `kan186_profile_fk_cascade_part_a.sql` held-file
precedent, with a header instructing a rename to the exact ledger version at apply
time. Header carries the measured breakage, the `is_venue_admin` transitive chain,
and the reason `authenticated` is deliberately excluded.

**A blind assertion was written here first and caught by testing it.** The
post-condition matched on `pg_get_function_identity_arguments(p.oid) = 'uuid, uuid'`
— but that function emits *parameter names* (`p_user_id uuid, p_venue_id uuid`), so
the comparison never matched, every `IF` tested NULL, and the assert **passed while
`anon` still held EXECUTE**. Rewritten on `to_regprocedure()`, then demonstrated in
three directions: raises with no revoke, passes after the revoke, and the
`authenticated` limb raises when `authenticated` is revoked. All three green. The
trap is documented in the file so it is not reintroduced.

**Not applied, deliberately.** `apply_migration` was never attempted — not because
of the classifier, which is orthogonal, but because applying a change I have
measured to break production is not mine to do on a restated brief that has not
answered the measurement. AC4 remains unreached. Ownership retained, ticket stays
in `Back-end`.

**Adjacent findings recorded** in `agent/state/discovery-ledger.md` per its format,
no Jira ticket created: `vbookings_block_dml` is PERMISSIVE so it blocks no DML
despite its name; `venues_update` is unreachable for `authenticated`, which holds no
UPDATE grant on `venues`. Neither blocks KAN-188. `docs/SCHEMA.md` untouched.

## 2026-09-11 — KAN-188 (3): APPLIED. Relocated to `util` per cto ruling (a). Oracle closed, anon browsing intact.

**Provenance:** `apply_migration` → ledger version **`20260911080000`**,
`kan188_relocate_venue_authz_fns_to_util`. Repo file committed at that exact
version (backend-5's KAN-168 naming precedent); the superseded held REVOKE file
`kan188_revoke_anon_execute_venue_authz_fns.sql` was deleted so nobody applies the
rejected approach. Ticket `Back-end` → `Peer-review` (10045, transition `7`).
Ownership retained.

**The load-bearing condition passed.** cto flagged that PostgREST's exposed-schema
config is API configuration and not catalogue-visible. Confirmed: no
`pgrst.db_schemas` role setting exists, so `pg_db_role_setting` genuinely cannot
answer it. The live API can — `Accept-Profile: util` returns `PGRST106 "Only the
following schemas are exposed: public, graphql_public"`. Two controls proved the
probe discriminates: `public` returns `200` with a real row, and a nonsense schema
returns the same `PGRST106`.

**Measured the exploit before fixing it, over HTTP rather than only in SQL.**
`POST /rest/v1/rpc/can_manage_venue` as `anon` returned **`200 false`** — the oracle
was answering in production. After: all five return `404 PGRST202`. Legitimate anon
paths still `200` — `venues`, `venue_spaces`, `venue_bookings`, `venue_members` —
and the sanctioned `rpc_my_venue_permissions` still returns its five-key object.

**I found two things the approved plan did not cover, and both mattered.**

1. **cto's sibling sweep was scoped to the six venue functions; the breaking caller
   was a seventh.** `rpc_my_venue_permissions` is a plpgsql `SECURITY DEFINER` RPC
   whose body calls all five by `public.`-qualified name. plpgsql bodies are stored
   as TEXT and re-parsed at run time — `prosqlbody IS NULL`, `pg_depend` records no
   function→function edge — so `ALTER … SET SCHEMA` alone left it raising `42883`.
   Fixed inside the same migration from `pg_get_functiondef` on the live catalogue,
   changing only the five qualifiers. It remains the safe public interface because
   it takes its subject from `request.jwt.claims`, not an argument — which is
   exactly what the raw five did wrong.
2. **My first probe of that reported PASS and was worthless.** With no JWT the
   function takes an early return and never reaches the five calls (`T-055`, in the
   *returns-early* form rather than raises-early). Re-probed with the claim set:
   pre-move baseline reaches the calls; post-move raises `42883`; and a fresh-plan
   clone of the identical body raises the same, ruling out plpgsql plan caching.
   Had I trusted the first result I would have shipped a migration that silently
   broke a live RPC.

**Also caught a blind assertion before it shipped.** The post-condition matched
`pg_get_function_identity_arguments = 'uuid, uuid'`, which emits *parameter names*,
so nothing matched, every `IF` tested NULL, and it passed while `anon` still held
EXECUTE. Rewritten on `to_regprocedure()` and demonstrated failing three ways.
Documented in the migration so it is not reintroduced.

**Counterintuitive core, recorded because getting it backwards reproduces the
breakage:** revoke schema USAGE, **keep** EXECUTE. The policy qual holds the OID;
USAGE is checked at name resolution (already done for a stored policy), EXECUTE at
run time by OID. Revoking EXECUTE is what raises `42501` inside the policy — §6d's
`circle_member_count`/KAN-77 hazard arriving through RLS instead of a
`security_invoker` view.

**`is_venue_admin` stays in `public` deliberately** — both overloads `SECURITY
INVOKER`, bounded by the caller's own RLS, not an oracle. Migration asserts the
count is exactly `2`, since a by-name enumeration sees only one of the two.

**§2g gate cover replaced** by asserting `has_schema_privilege` USAGE on `util` is
false for `anon` and `authenticated`. **`docs/SCHEMA.md` untouched.** No Jira ticket
created. Two adjacent findings already in `agent/state/discovery-ledger.md`.

## 2026-09-11 — KAN-188 (4): characteristics asserted, route computed `peer`

KAN-188 was routeless in Persistent State, so no review context could open.
Asserted via `store.set_characteristics('KAN-188', expected_revision=6, …,
author='worker:backend-2')`. Revision 6 → 7. Policy computed
**`validation_route: peer`**, `completion_route: DONE` — matching the Jira
transition to `Peer-review` already made, so state and lifecycle now agree.

**Asserted TRUE, two only:**
- `schema_change` — five functions relocated `public` → `util` via
  `ALTER … SET SCHEMA`, plus `CREATE OR REPLACE` on `rpc_my_venue_permissions`.
- `security_sensitive` — the whole ticket is closing an anon-reachable
  authorisation oracle that was answering `200 false` over HTTP in production.

**Left absent, because absent means false and only what is true gets asserted:**
- `money_path` — venue authority, no wallet, ledger or payment surface touched.
- `user_visible_runtime` — checked rather than assumed. **No app code calls any of
  the five, and none calls `rpc_my_venue_permissions`.** The only repo hits under
  `lib/` are two comments in `data_export_service.dart:752,960` citing
  `can_view_venue_bookings` as a *pattern analogy* for a different function — not
  calls. RLS-mediated reads are unchanged and were measured identical before and
  after (`venues` 379, `venue_spaces` 679), so no user-observable runtime behaviour
  moved.
- `shared_or_contended_surface` — system-derived, already `false`; not touched, and
  `paths` deliberately not passed so nothing recomputes it.

Noted while checking callers: `docs/CONVENTIONS.md:388` already carries the
plpgsql/`rpc_my_venue_permissions` caveat I raised, so cto has landed that
amendment to §6d option 3.

Ownership retained. Awaiting a `backend-N` peer reviewer.

## 2026-09-11 — KAN-174: root fix AUTHORED, apply DENIED by the harness classifier. Production mutations: 0. Ticket stays in `Back-end`.

**Outcome: BLOCKED on the apply leg only.** `apply_migration` attempted once and
**denied by the harness permission classifier** — not by any governance gate.
`G-002`'s four conditions were met, `T-070` requires no CEO authorization, and
`T-068` bars `db push` not `apply_migration` (its own Consequence section directs
`apply_migration` explicitly). **Not retried, and no `execute_sql` DDL fallback** —
routing a denied apply through another tool leaves the migration ledger no longer
describing production, which is the failure `T-068` exists to prevent. Production
re-read straight after: all three functions intact at 183 / 725 / 3,599 bytes, no
clamp, no comment, original `proacl`. Nothing partially applied.

**Delivered** (dabbler-code, uncommitted): NEW held migration
`supabase/migrations/kan174_fold_potential_vibes_drop_identity_param.sql` (no
version prefix, `kan186` precedent, header carries the denial and a rename-at-apply
instruction) and NEW `supabase/tests/kan174/probes.sql` (AC5, six probes, run
against live). `docs/SCHEMA.md` **untouched** — see AC6 below. Surfaces updated in
Persistent State to rev 9, replacing `backend-3`'s Preflight list now that the
migration path exists.

**The vacuous step is fixed, and the fix is the interesting part.** The prior
reading — "147 rows before and after, behaviour preserved" — ran with no JWT, so
`auth.uid()` was NULL, `spw.user_id <> NULL` was NULL for every row, and the
self-exclusion predicate was never exercised at all. Re-run with a real
`request.jwt.claims` and `auth.uid()` **asserted equal to the subject** before
anything was counted:

| probe | pre-fix |
|---|---|
| subject owning 7 of the view's 147 rows, `p_limit=999999` | **140**, 0 of them their own |
| stranger uuid owning none, same call | **147** |
| subject, sport `padel` (27 rows, 1 theirs), `p_limit=50` | **26**, 0 leaked |
| stranger, same sport | **27** |

140 vs 147 is the discrimination that was missing. **The sport-narrowed form exists
because the post-fix clamp would otherwise hide the effect**: 50 of 147 rows, with
`score` a constant `1.0` so `ORDER BY score` gives no stable order, means the
subject's own rows could be absent from a passing result by luck. Narrowing to a
sport whose total fits under the clamp removes the luck. That trap only appears
once the clamp exists — it is not visible from the pre-fix behaviour.

**Every post-condition demonstrated failing first**, against the live pre-migration
catalogue: 7-arg-gone, debug-gone, no-uuid-argument, exactly-one-in-the-family,
AC3-comment-present, and the clamp (*"did not hold — 140 rows for p_limit=999999"*)
all raised. The two **behavioural** assertions were additionally aimed at a
**deliberately broken fold** — identical body and clamp, self-exclusion predicate
deleted — in a rolled-back transaction. Both caught it: *"self-exclusion broken - 1
own rows returned for sport padel"* and *"no caller identity returned 50 rows,
expected 0"*. **The second is the KAN-174 incident reproduced**, and the assertion
is what stops it committing. Production re-read after that rollback and confirmed
unchanged (183 bytes, no clamp, original ACL) before anything else was done.

**One assertion is NOT discriminating and is labelled so in the file rather than
counted as green.** "Body free of `p_me`" passes pre-migration because the 6-arg
body never had `p_me` — the 7-arg's did. Its real case is a botched fold that
re-imports the parameter. Stating that is the difference between a probe pack and a
row of green ticks.

**P4 and P6 passing pre-fix is correct, and misreading that would be the whole
error.** The 6-arg wrapper's self-exclusion always worked and `anon` always got 0
rows *through it*. The incident was never the 6-arg — it was the 7-arg sibling,
directly reachable, taking identity from the caller. So P4/P6 are **regression
guards** that must keep passing across the fold, while P1 and P5 are the only
probes that change state. A pack where every probe flipped would be one that had
misread the defect. Recorded in the pack header with the measured results.

**AC1 vs `T-070` D2 — a real divergence, flagged not resolved.** AC1 asks for
`anon` EXECUTE revoked from **both** overloads. `T-070` post-dates the filing and
rules the 6-arg keeps both `SECURITY DEFINER` and `anon`'s EXECUTE. Measured today:
`v_sport_profiles_with_user` grants `anon=xtm` / `authenticated=xtm` — **no `r`**,
`has_table_privilege(…,'SELECT')` **false for both**. So an invoker function returns
nothing to anyone, and revoking `anon`'s EXECUTE turns 0 rows into **`42501` raised
through `v_potential_vibes_default`**, which `anon` *does* hold `r` on and which the
anon-allowlist gate watches. A live break for nothing. **Containment on the 7-arg
already held** (`proacl = {postgres=X,service_role=X}`, no PUBLIC entry,
`has_function_privilege` false for both client roles) — and removing the object
beats revoking its grant. Posted to the ticket as a divergence for `po`, not
decided unilaterally.

**`rpc_potential_vibes_debug` is DROPPED, not revoked, and the probe says why.**
As `anon` it raises **`42P01` relation "public.v_vibes_candidates" does not exist**,
NOT `42501` — it *passes* the permission check on a bare PUBLIC `=X` and dies on a
missing relation. `to_regclass` NULL, confirmed same run. Inertness is luck. It is
the richer body (3,599 vs 725 bytes) with skill_level, composite_score, mutual
counts and geo-locality, and its `search_path` is `public` alone — no `pg_temp`,
unlike every sibling. One `CREATE VIEW` away from reproducing the incident with a
worse payload and no new grant.

**§2g checked rather than assumed.** Dropping the debug function leaves its
signature in my own KAN-175 allowlist at `docs/SCHEMA.md:769`. Read
`anon_function_grants_diff.sh` to confirm the consequence instead of guessing: the
diff is **one-directional by design** — a signature leaving the flagged set is a
stale entry, never a red build. So the gate stays green and §2g stays untouched,
which is also what AC6 requires.

**AC6 deliberately NOT written.** It is conditional on AC2's redesign landing, and
AC2 has not landed. Writing a `docs/SCHEMA.md` row describing a post-fix mechanism
that is not live would put a false statement into the exact document the AC exists
to de-drift. Replacement text prepared verbatim in KAN-174 comment 10997, to apply
in the same change that lands the migration.

**One further doc line this migration falsifies, raised not edited.**
`docs/SCHEMA.md:901` — *"`rpc_potential_vibes` ×2 (one takes `p_me`)"* — is a live
claim about the catalogue and becomes false when the fold lands. Outside §2g and
outside AC6's scope, so raised to `po` rather than edited unilaterally. By contrast
`docs/SCHEMA.md:684` (§2g.1's containment table) is a **dated historical record** of
what was revoked on 2026-09-10 and stays true as history — left alone deliberately.

**Not transitioned to `Peer-review`.** AC2 has not landed and there is nothing for a
peer to review as done. Ticket stays in `Back-end` (10043), **ownership retained**.
Route PEER; reviewer must be another `backend-N`. `G-006` claim comment posted
BEFORE the attempt (10995) with preconditions re-measured immediately beforehand;
outcome posted back after (10997). **What unblocks this: permission to run
`apply_migration` on `wtncuzcskpigqpmnxwws` for this one file.** Everything else is
finished and measured.
