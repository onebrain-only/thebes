# backend-7 status log

> Entries before 2026-11-10 are in `agent/archive/2026-11-10/status/backend-7.md`. This file is a work log, not a rule source.

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
