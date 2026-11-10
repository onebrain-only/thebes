---
name: briefs-no-drop-no-prod-test-writes
description: "Every DB brief to a team must forbid DROP and apply_migration, and forbid test writes on the live Supabase project"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-08T16:29:51.662Z
---

**Partly SUPERSEDED 2026-10-27 by [[autonomy-constitution]]:** destructive SQL is no longer a CEO stop. Teams still never run it. Memphis runs it, taking a `thebes_backup` snapshot first and logging it in the ledger. The practical rules still stand: no apply_migration (use ordered execute_sql), and prefer RENAME + REVOKE over DROP inside team sessions.


DB briefs must say: no DROP (it ends the team session; replace via RENAME to *_legacy_vN + REVOKE), no apply_migration (it drops the MCP connection; use ordered execute_sql steps, each once), and NO writes to wtncuzcskpigqpmnxwws for testing, even rolled back (prove with read-only SQL + Flutter tests with mocks).

**Why:** 2026-10-08 teams lost ~3h to DROP/apply_migration hangs, and Luxor ran a DO block inserting test rows into real users' roster/follows/blocks on production (rolled back, CTO verified clean). Production data is a hard stop.
**How to apply:** put all three rules in FORBIDDEN of every brief touching the DB; check `conversation_dispatch stalled` when a team is quiet >15 min. Related: [[orchestrator-delegate-not-execute]].

**CEO override 2026-10-13 (scope: Messaging migrations and their permission fixes only):** all accounts and data in `wtncuzcskpigqpmnxwws` are test data and there are no real users, so Messaging migrations (and the block/anon permission fixes KAN-497/499) may be APPLIED to that project and write/Realtime tests may run there, inside each ticket's scope, after the required technical review, in dependency order, with the current state checked first and a documented rollback; use specific test data (no sweeping scans), NO DROP, no other project, and STOP if real user data appears. Record real PASS/FAIL, never count a written-but-unrun test as passed. No new approval is needed per reviewed in-scope migration. Not approved by this: D3-D29 as a block, new cost, Cloudflare resources, public Messaging rollout. Keep the practical rule: apply as ordered execute_sql steps, each once (apply_migration/DROP hung teams). Confirmed reads: GitHub is NOT linked to Supabase, Realtime public access is ON, access-token lifetime is 3600 s.

**Cloudflare approval (CEO 2026-10-14, ledger ref cloudflare-messaging-approval):** Messaging Worker + D1 on Cloudflare FREE tier only is approved. NOT approved: R2/photos, paid plans, custom domain/DNS, touching Pages `webapp` or dabbler.pro, public rollout, flags true in committed code. Secrets are never written anywhere by agents; the CEO sets values himself. Budget alert $1/month exists.
