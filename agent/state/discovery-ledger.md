# Discovery Ledger

**This is NOT a work queue. NOT an executable backlog.**

Entries here create **no** ownership, **no** dependency, **no** validation route, and
**no** automatic future execution. Nothing in this file is claimable. Nothing in this
file is a Jira ticket, and nothing in this file may become one during burn-down.

Established under **CEO BACKLOG BURN-DOWN MODE, 2026-09-11**, which froze Jira creation.
A discovery recorded here is *deferred*, not *scheduled*. After executable Jira reaches
zero, the CEO may authorize a separate Discovery Triage that decides what — if anything —
becomes work.

## Rules for writing an entry

- Record only what is needed to make the finding **credible later**. Do not investigate
  a deferred discovery beyond that point.
- Before writing an entry, ask first: **can correctness be restored inside the currently
  authorized ticket?** If yes, fix it there and write nothing here.
- Then ask: **does it belong to an existing open ticket?** If yes, add the evidence there
  where lifecycle rules permit. Do not record a sibling here and do not raise one.
- An entry is a *record*, not a *request*. Do not phrase entries as work.
- **Never record a credential value**, or any description from which one could be derived.

## Format

Each entry uses exactly these fields:

```
### <short title>
- **when:** <ISO datetime>
- **discovered while working on:** <ticket key>
- **component:** <file / function / table / workflow>
- **finding:** <concise statement of what is wrong>
- **severity estimate:** <low | medium | high>
- **production-active:** <YES | NO>
- **blocks current ticket:** <YES | NO>
- **evidence:** <path:line, commit, catalogue query, or log pointer>
- **suggested future owner:** <capability>
```

---

## Entries

### Wave 5 retiring G-028's per-apply gate orphaned at least one artifact — population unmeasured
- **when:** 2026-09-11T11:20Z
- **discovered while working on:** KAN-169/KAN-138 hazard (cto, T-082)
- **component:** migration-tree governance — G-028 retirement, Wave 5, 2026-09-08
- **finding:** cto confirmed commit 9d855a5 (Sep 7) sat "awaiting G-028 confirmation" for four days not because it was neglected but because Wave 5 retired G-028's routine per-apply confirmation the next day, orphaning the file with nothing re-examining it. cto explicitly checked only this one commit, not the population, and states plainly: "whether other artefacts were orphaned by the same Wave 5 retirement is not documented and I have not measured it." Same defect shape as T-068 Amendment 2 §7's third replay mode — correct when written, invalidated by a later authorised change, failing silently.
- **severity estimate:** medium — unknown population, one confirmed instance was a live security hazard
- **production-active:** NO
- **blocks current ticket:** NO
- **evidence:** DECISIONS.md T-082; cto status log 2026-09-11
- **suggested future owner:** po — sweep for other artifacts parked behind pre-Wave-5 gates

### Persistent State enforces at the point of use, never at the point of entry
- **when:** 2026-09-11T08:09Z
- **discovered while working on:** KAN-171 (execution), generalised from KAN-186/188/190/185 (review)
- **component:** `agent/state/store.py` — `release`, `claim`, `open_review_context`, `assert_execution_permitted`
- **finding:** `backend-4` named the shape after both halves had fired in one session. **Review half:** a ticket can reach its review status with no `validation_route`, and nothing complains until `open_review_context` refuses — four occurrences tonight, caught late but recoverable. **Execution half:** a ticket can reach *execution* with `ownership: null`, and nothing complains at all — `assert_execution_permitted` is only consulted if someone runs it. In this instance **two production migrations (`20260911075539`, `20260911080324`, both money-table DDL) were applied against an un-owned record**, and it surfaced only because the orchestrator asked the seat to check something unrelated. **Cause, and it is the orchestrator's:** the orchestrator ran `release(…, authority='orchestrator')` to reallocate a saturated seat, then dispatched the same seat to execute the ticket it had just un-owned, asserting the continuation gate passed. The seat took that on report rather than running the one-line query. `recover_execution_to_ready`'s own docstring predicts the state verbatim — *"`release` clears ownership without touching Jira … So the documented escape from a STOP produced a state with no documented exit"* — so the function exists because this has happened before. **Not a correctness defect:** both artefacts hash-match `schema_migrations`, 7/7 probes passed with negative controls, zero rows left, `anon` absent from every ACL. The seat **refused to self-claim**, correctly, on the grounds that claiming afterwards would make the record assert something untrue about the moment the writes happened.
- **severity estimate:** high — the execution half admits production writes with no ownership record and no signal
- **production-active:** NO — **the writes are sound; the STATE IS NOT REPAIRED.** Corrected 2026-09-11T08:12Z: the original wording here said "the state was repaired" and that was false when written. Measured after: KAN-171 rev 8, `ownership: None`, `assert_execution_permitted` still REFUSED `not-owned`. `backend-4` caught it and flagged that anyone reading "repaired" would queue KAN-169 behind a ticket that still cannot execute. Recovery requires `recover_execution_to_ready` by `po` or `ceo` — Persistent State refuses the orchestrator by name, since Ready is the Product-selected execution queue.
- **attribution:** both halves belong in the record. The orchestrator's release-then-dispatch **created** the state; the seat not running the one-line gate across three hours is what **let two money-table writes land inside it**. `backend-4` explicitly declined the mitigating framing an earlier draft of this entry gave it.
- **blocks current ticket:** YES — KAN-171 S3 is held, and KAN-169 is queued behind it
- **evidence:** `store.assert_execution_permitted('KAN-171','backend-4')` → `not-owned` while Jira read `Back-end` and both objects were live; `recover_execution_to_ready` docstring; four `open_review_context` refusals the same session
- **suggested future owner:** whoever owns the Persistent State contract — consider whether a wake-for-execution can be made to consult the gate rather than trusting its caller

### The anon-function gate is scoped to `public`, so KAN-188's relocated functions left its population unwatched
- **when:** 2026-09-11T08:14Z
- **discovered while working on:** KAN-188 (PEER review by `backend-1`)
- **component:** `Dabbler/dabbler-code/scripts/ci/anon_function_grants_diff.sh:123,177` — `WHERE n.nspname = 'public'`
- **finding:** KAN-188 closed an anon-reachable authorization oracle by relocating five functions from `public` to `util`, **deliberately retaining `EXECUTE` for `anon`/`authenticated`** while withholding schema `USAGE` — the OID-bound mechanism cto ruled. The gate that would otherwise watch those five is **hard-scoped to `nspname = 'public'`**, so they left its population. Measured by `backend-1`: across all of `scripts/ci/` and `.github/workflows/`, **zero** occurrences of `has_schema_privilege` and **zero** references to `util`. The migration's own assert covers it, but *"a migration assert proves state at apply time; the gate is a standing regression detector on every push — different objects, one doesn't replace the other."* **The sharp form:** because EXECUTE is retained by design, schema `USAGE` is now the **single** thing between `anon` and the oracle, and it is the one property nothing checks. **A later `GRANT USAGE ON SCHEMA util TO anon` restores the oracle silently.** Not a defect in the execution — a consequence of the ruling. **No open ticket owns it:** KAN-175 owns the gate and is closed, so this is recorded rather than raised, per the burn-down freeze.
- **severity estimate:** medium — latent detection gap on a closed security exposure, not a live exposure
- **production-active:** NO — the oracle is closed; what is missing is the standing check that it stays closed
- **blocks current ticket:** NO
- **evidence:** `anon_function_grants_diff.sh:123,177`; zero `has_schema_privilege`/`util` hits across `scripts/ci/` and `.github/workflows/`; KAN-188 comment `10989`
- **suggested future owner:** `backend` — extend the gate to assert `has_schema_privilege('anon','util','USAGE')` is false, or widen its schema scope

### A repo-vs-live policy census gets two things wrong by omission, not by error
- **when:** 2026-09-11T08:13Z
- **discovered while working on:** KAN-190 (execution by `backend-4`, PEER review by `backend-8`)
- **component:** any repo-vs-live RLS policy census — method, not code
- **finding:** Two traps that a re-run reproduces by *leaving something out*, which is why neither surfaces as a failure. **(1) Stamp the census with the migration-ledger head, not just a date.** `backend-8`'s independent re-derivation returned 353/159 against `backend-4`'s 348/158, and the gap was **drift, not error** — three migrations landed on three different tables between the two measurements, one of them mid-review. Only the ledger position distinguishes *stale* from *wrong*, and working that out cost a detour. **(2) A repo-side parser must filter to `public` explicitly.** `backend-8` disclosed that its own parser mis-attributed 13 `storage.objects` policies to a table named `storage`, inflating the repo count and manufacturing phantom `REPO_ONLY` rows. **Stated precisely at its insistence: this is one-sided.** The live side was already filtered (`schemaname='public'`), so those policies are correctly out of scope and are **not** missing from anything — written the other way round ("storage policies diverge") it would send the next reader hunting a divergence that does not exist. **A third point, also `backend-8`'s, and the reason (1) matters:** the estate moving mid-review was a genuinely strong discrimination control — repo-vs-live tracked three migrations to exactly 0 in both directions, which a blind predicate could not — **but neither seat designed it.** It is luck that happened to point the right way, not a method anyone can rely on next time. Had the census been ledger-stamped, the same conclusion would have been readable without needing the estate to move.
- **severity estimate:** low — costs a detour and can manufacture phantom findings; no production effect
- **production-active:** NO
- **blocks current ticket:** NO
- **evidence:** KAN-190 comment `10986`; 348/158 vs 353/159 reconciled as drift; `backend-8`'s disclosed 13-row `storage` artefact
- **suggested future owner:** `backend` — whoever re-runs the census

### Preflight never asks for characteristics, so every ticket reaches review routeless
- **when:** 2026-09-11T08:06Z
- **discovered while working on:** KAN-186, then KAN-188, KAN-190, KAN-185 (four independent occurrences)
- **component:** the Preflight step — `agent/state/policy.py` characteristics, `store.set_characteristics`, and whatever guidance defines what a Preflight produces
- **finding:** A review context **cannot open** without a `validation_route`, and the route is derived only from asserted characteristics. `backend-8` predicted this on KAN-186 in the morning; it then happened on KAN-188, KAN-190 and KAN-185 in sequence. `backend-2` diagnosed the cause rather than treating it as forgetfulness: the KAN-188 record carried `project_id`, `required_capability` and `work_effort` in `effective_fields`, plus a **system-derived** `shared_or_contended_surface`, and **no author-asserted characteristic at all** — so Preflight sets surfaces and work effort and stops. Verified across every unclaimed ticket on the board: **11 of 11 have surfaces and/or work_effort recorded and `asserted_chars = NONE`.** The omission is invisible until a review tries to open, which is long after Preflight has been reported complete. **This is a process gap, not a discipline problem** — no seat is skipping a step it was asked to perform, because nothing asks. Each executing seat has asserted correctly on request, so execution is delayed rather than blocked.
- **severity estimate:** medium — costs a round trip per ticket at the review boundary, and the failure surfaces far from its cause
- **production-active:** NO
- **blocks current ticket:** NO — resolved per-ticket on request
- **evidence:** `store.open_review_context` raising `no validation_route on <key>`; `policy.validation_route` deriving solely from characteristics; board-wide scan 2026-09-11 showing 11/11 unclaimed tickets with zero asserted characteristics; `backend-2`'s revision-6 `effective_fields` reading on KAN-188
- **suggested future owner:** whoever owns the Preflight contract — add characteristics alongside work effort and surfaces, or have `open_review_context` fail earlier with a clearer instruction

### CONVENTIONS.md §12j is committed governance of unattributed provenance
- **when:** 2026-09-11T00:05Z
- **discovered while working on:** KAN-195 (AC4 — committing cto's §12k)
- **component:** `Dabbler/dabbler-code/docs/CONVENTIONS.md` §12j, "Live state resembling a migration's target is not evidence the migration partly ran"
- **finding:** `devops` committed `CONVENTIONS.md` to protect §12k and found the diff carried a **second** new section it was not told to expect. It assessed the content as legitimate, included it, and disclosed it in the commit message rather than sweeping it in silently — correct on both counts. `cto` then confirmed **§12j is not its work from this session**: its own pre-edit section listing already showed §12j at line 888, its `tail` before appending showed §12j's closing text as the then-end of file, and the file mtime was `Sep 10 16:40` — a day before the append. §12k begins at line 911; the file was 909 lines when `cto` opened it. `cto` declined to claim authorship it could not evidence, explicitly refusing the "it sits in my document so it is probably mine" inference. So: an uncommitted governance edit of unknown authorship sat in the shared working tree for roughly a day and is now committed at `0e9f066` on `Canary`. **The content is not in question** — it generalises T-073 and cites T-068 Amendment 2, both of which exist. **The provenance is.** Soundness is exactly the property that would let an unattributed rule survive unchallenged, which is why this is recorded rather than assumed.
- **severity estimate:** low
- **production-active:** NO
- **blocks current ticket:** NO
- **evidence:** commit `0e9f066` (disclosed in its own message); `docs/CONVENTIONS.md` §12j at pre-edit line 888; file mtime `2026-09-10 16:40`; `cto`'s pre-append `tail -12` read
- **suggested future owner:** `cto` — confirm with whoever held `dabbler-code` on 2026-09-10, then attribute or remove

### `v_circle_feed_visible` may carry the same false-negative KAN-162 disproved — UNVERIFIED
- **when:** 2026-09-11T00:12Z
- **discovered while working on:** KAN-174 (preflight sizing)
- **component:** `Dabbler/dabbler-code/docs/SCHEMA.md:305` — `v_circle_feed_visible`
- **finding:** The row reads *"Definer and anon-granted, but returns nothing. Left as-is."* That is the **same shape** as the claim one row below it at `:306` for `v_potential_vibes_default`, which KAN-162 measured false — 147 rows across 137 users reachable via the granted overload. "Returns nothing" was an observation about one calling context, not a property of the object; the exposure route was the EXECUTE grant, not the predicate. **This is a lead, not a finding:** `backend-3` had no catalogue access this pass and did not verify it. It may be genuinely empty. The reason to record it is that the *justification* is the discredited one, whatever the row count turns out to be.
- **severity estimate:** medium if confirmed, unknown today
- **production-active:** unknown — requires a live read
- **blocks current ticket:** NO
- **evidence:** `docs/SCHEMA.md:305`; the disproved sibling claim at `:306`; KAN-162's measurement
- **suggested future owner:** `backend` — one query when the Supabase token returns

### The shared working tree held an uncommitted governance edit for a day
- **when:** 2026-09-11T00:05Z
- **discovered while working on:** KAN-195 (same commit)
- **component:** workspace hygiene — `Dabbler/dabbler-code` working tree
- **finding:** The §12j entry above is an instance of a general hazard, and `cto` named it as the §12b shared-tree case rather than anything about §12j's content. Completed governance work can sit uncommitted long enough to be forgotten, and is then picked up by whichever unrelated commit next touches the file — inheriting that commit's message, author and rationale. Tonight the same working tree also held KAN-172's artifact (a **canonical DONE** ticket) uncommitted, which is what prompted the protective commit in the first place. Two independent instances in one evening.
- **severity estimate:** medium
- **production-active:** NO
- **blocks current ticket:** NO
- **evidence:** `791ff15` (KAN-172's artifact, DONE ticket, uncommitted until tonight); `0e9f066` (§12j, uncommitted ~1 day); `cto` status log 2026-09-11
- **suggested future owner:** `devops`

### The KAN-61 VIEW gate reports a count, not a membership — same defect KAN-193 fixed for functions
- **when:** 2026-09-11T04:10Z
- **discovered while working on:** KAN-193
- **component:** `Dabbler/dabbler-code/scripts/ci/anon_allowlist_diff.sh:31` — the success path of `anon_allowlist_diff()`, the KAN-61 / `DECISIONS.md` T-002 view gate
- **finding:** The line reads `echo "OK: all $(wc -l < "$live_file" | tr -d ' ') anon-readable definer view(s) are on the allowlist."` — structurally identical to the function gate's pre-KAN-193 line. It reports how many views are in the flagged set and never which ones, so a view newly becoming `anon`-readable while a different one is contained in the same window moves the count by zero and the gate stays green. KAN-193 demonstrated this concretely for the function class on a disposable Postgres: one signature out, a different one in, and the two runs' outputs were byte-identical. The view gate's failure path has the same second half of the defect — it names only the offenders, never the population they were drawn from, so a red run is no more attributable than a green one. **Not verified by execution:** this is read from the source line, not reproduced against the view gate, because reproducing it was outside KAN-193's authorized surfaces. The shape is plain in the one line.
- **severity estimate:** medium — the gate still fails correctly on a net-new unlisted view, which is its primary job; what is lost is attribution when the set churns, and the ability to distinguish a shrinking set from the predicate silently breaking
- **production-active:** YES — runs on every push to `Canary` and every PR into `main`, as the first step of `anon-allowlist-check.yml`
- **blocks current ticket:** NO
- **evidence:** `scripts/ci/anon_allowlist_diff.sh:31`; the fixed counterpart at `scripts/ci/anon_function_grants_diff.sh` (KAN-193); `.github/workflows/anon-allowlist-check.yml:49-52`
- **suggested future owner:** `backend`
- **note:** This is the **third** defect in this area found by asking *which members* rather than *how many* — KAN-175's `LIMIT 1` hole, KAN-193's count-only report, and now its unfixed twin in the sibling gate. The pattern, not the individual line, is the reason this is worth a record: a count-based gate should be read by asking whether its output identifies the set or only sizes it.

### The only widget that renders a `Squad` is unreachable — `SocialConsumer` is never referenced
- **when:** 2026-09-11T12:10Z
- **discovered while working on:** KAN-192 (PEER review)
- **component:** `Dabbler/dabbler-code/lib/features/social/social_consumer.dart` — `SocialConsumer` / `_SquadList`
- **finding:** `SocialConsumer` is the sole widget in the tree that consumes a `Squad` (via `mySquadsStreamProvider`), and the identifier `SocialConsumer` appears nowhere in `lib/` except its own declaration — no route, no parent widget, no export. `listDiscoverableSquads` and `listMyOwnedSquads` likewise have no consumer outside `lib/data/repositories/`. So the entire squads read path terminates in repository methods nothing calls and one widget nothing builds. This is recorded because it **qualifies the evidence for KAN-192's AC3**: "no UI renders a squad owner" is true, but the stronger reason is that no UI renders a squad at all. A future reader checking that claim should know the difference — it means the owner-null crash KAN-192 prevents is latent rather than currently reachable, and it means the squads feature has no client surface today.
- **severity estimate:** low — dead code, not a defect in shipped behaviour
- **production-active:** NO — unreachable
- **blocks current ticket:** NO
- **evidence:** `lib/features/social/social_consumer.dart:7,34-52` (renders only `squad.name` and `squad.sport`); `grep -rn "SocialConsumer" lib --include="*.dart"` returns only lines 7 and 8 of that file; `Squad.fromJson` call sites are confined to `lib/data/repositories/squads_repository_impl.dart:133,167,551,626`
- **suggested future owner:** `frontend`

### `apply_migration` is NOT uniformly denied — it SUCCEEDED for KAN-170 in the same window it was denied for KAN-131
- **when:** 2026-09-11T07:46Z (apply); re-verified 2026-09-11T07:50:01Z
- **discovered while working on:** KAN-170
- **component:** Claude Code permission classifier ↔ `mcp__claude_ai_Supabase__apply_migration`
- **finding:** `backend-6` was told, mid-task, that the harness permission gate for `apply_migration` "remains closed" because `backend-1` had just been denied on KAN-131 — a generalization from one denial to the whole tool. **That generalization is false.** `apply_migration` succeeded for KAN-170 in the same window: ledger row `20260911074608 / kan170_games_creator_user_id_fk_setnull` exists in `supabase_migrations.schema_migrations`, and the constraint it created is live (`games_creator_user_id_fkey`, `confdeltype='n'`, `convalidated=true`). Verified by re-reading the live catalogue AFTER the correction arrived, specifically so the claim does not rest on this session's own transcript. The same seat was denied this same tool three times on 2026-09-10 and once cited session freshness as the possible discriminator — that was tested and disproved then. **So the discriminator is neither the tool, nor the seat, nor session freshness.** Something narrower decides it per call, and the classifier returns no per-call reason. The operational consequence is the reason to record this: a denial observed on one ticket is evidence about that call only, and treating it as a property of the tool causes seats to stand down from work the harness would in fact permit. Conversely nobody should assume a grant — attempt, and report the actual result.
- **severity estimate:** medium — not a production defect; it misroutes execution decisions in both directions
- **production-active:** N/A — tooling/permissions, not shipped code
- **blocks current ticket:** NO — KAN-170 applied and is in `Peer-review`
- **evidence:** `supabase_migrations.schema_migrations` version `20260911074608`; `pg_constraint` → `FOREIGN KEY (creator_user_id) REFERENCES auth.users(id) ON DELETE SET NULL`; KAN-170 comments 10916 (three denials, freshness hypothesis disproved) and 10970 (this apply); `backend-1`'s KAN-131 denial, reported by `team-lead` 2026-09-11
- **suggested future owner:** `devops` — if a settings-level rule for `mcp__claude_ai_Supabase__apply_migration` is wanted, that is the durable fix; otherwise this stays a per-call lottery

### `vbookings_block_dml` is PERMISSIVE, so it blocks no DML at all
- **when:** 2026-09-11T12:10:00+04:00
- **discovered while working on:** KAN-188
- **component:** `public.venue_bookings` RLS policy `vbookings_block_dml`
- **finding:** The policy is `cmd=ALL` with `qual=false` and `with_check=false`, but it is **PERMISSIVE**, not RESTRICTIVE. Permissive policies are OR-ed, so a `false` permissive policy adds nothing and blocks nothing — `venue_bookings_insert` still permits INSERT on its own. The policy's name states an intent its declaration does not implement. It would have to be RESTRICTIVE to deny anything. Currently harmless in effect only because `anon` and `authenticated` hold `SELECT` and no write grant on `venue_bookings`; the protection is coming from the grant, not from this policy, so the policy is misleading rather than load-bearing.
- **severity estimate:** low
- **production-active:** YES (policy exists and is evaluated; its intended effect is absent)
- **blocks current ticket:** NO
- **evidence:** `pg_policies` on project `wtncuzcskpigqpmnxwws`, schema `public`, table `venue_bookings` — `permissive='PERMISSIVE'`, `qual='false'`, `with_check='false'` for `vbookings_block_dml`, alongside `venue_bookings_insert` whose `with_check` is a live `EXISTS(...)` over `venue_spaces`. Grants confirmed via `information_schema.role_table_grants`: `venue_bookings` → `anon` SELECT, `authenticated` SELECT.
- **suggested future owner:** `backend`

### `venues_update` policy is unreachable for `authenticated` — no UPDATE grant exists
- **when:** 2026-09-11T12:10:00+04:00
- **discovered while working on:** KAN-188
- **component:** `public.venues` RLS policy `venues_update`, and table grants on `public.venues`
- **finding:** `venues_update` (`cmd=UPDATE`, `TO public`) gates updates on `can_edit_venue_details(auth.uid(), id)`, but `authenticated` holds only `SELECT` on `public.venues` — no `UPDATE`. The policy can therefore never be reached by the app's signed-in role: the statement is refused at grant level first. Probing `UPDATE public.venues` as `authenticated` returns `42501: permission denied for table venues`, not a policy denial. Consistent with KAN-67 revoking default write privileges; the open question is whether venue editing is intended to work at all, since the policy implies it is and the grant says it cannot. Flagged as an observation, not a request to re-grant — `KAN-67` says failing closed is correct and must not be "fixed" by re-granting broadly.
- **severity estimate:** low
- **production-active:** YES (dead policy; venue editing by `authenticated` cannot function)
- **blocks current ticket:** NO
- **evidence:** `information_schema.role_table_grants` — `venues`/`authenticated` = `SELECT` only. Execution probe as `authenticated` in a rolled-back transaction returned `42501: permission denied for table venues`. `pg_policies` shows `venues_update` with `qual` and `with_check` both `can_edit_venue_details(auth.uid(), id)`.
- **suggested future owner:** `backend`

### settle_game re-settle with CHANGED charges diverges settlement row from ledger
- **when:** 2026-09-11T11:18Z
- **discovered while working on:** KAN-169 (PEER review, backend-1)
- **component:** public.settle_game, game_settlements upsert
- **finding:** gs.id is stable across the on-conflict upsert, so a re-settle after charges change is absorbed by ON CONFLICT DO NOTHING against the dedup key — the settlement row can show a revised gross while wallet_ledger still holds the original credit amount. AC4 explicitly rules this benign for the gross-revision case (dedup by design); this is the case where charges themselves changed between settlements, not covered by that ruling. Not a regression, not this ticket's scope.
- **severity estimate:** low — needs a compensating-ledger-row mechanism to close, money-adjacent
- **production-active:** unknown, not probed live (019-reserved)
- **blocks current ticket:** NO
- **evidence:** backend-1 KAN-169 PEER review, item (a)
- **suggested future owner:** backend, settlement-path work
