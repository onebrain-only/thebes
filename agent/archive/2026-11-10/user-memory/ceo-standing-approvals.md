---
name: ceo-standing-approvals
description: "CEO 2026-10-22 standing approvals - additive migrations, QA test data, Worker/Alpha deploys, free Cloudflare resources; no per-action ask"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c49d2414-5cd1-4c32-85cc-5909f4f333c9
  modified: 2026-10-21T20:33:35.448Z
---

**SUPERSEDED 2026-10-27 by [[autonomy-constitution]]:** Memphis owns all DB work, including DROP/DELETE/UPDATE (snapshot first, then the ledger), and owns alpha deploys. The "still ask him for destructive/production/secrets" line is void. Only money, merging into main and sending outside go to him.


On 2026-10-22 the CEO gave standing approval, in chat, for four kinds of action. I no longer ask him about these.

1. **Additive migrations only**, on Supabase wtncuzcskpigqpmnxwws and on messaging D1. Allowed: new functions, views, columns and indexes. Not allowed: DROP, DELETE/UPDATE of data, or anything destructive. Memphis applies them via execute_sql with probes before and after.
2. **Codex test data on the QA test account for any ticket.** Codex reads the authorization from the ticket description only, so the PM adds the `AUTHORIZED: write test data` line to each ticket's description when it goes to QA-Test.
3. **Deploys** of the messaging Worker and of Alpha (alpha.dabbler.pro). This never includes main, production or store releases.
4. **Free Cloudflare resources** inside the existing account: private R2 buckets, bindings, flags. No new paid plan.

**Why:** the CEO found per-ticket approvals too heavy and wants fewer interruptions.

**How to apply:** each time a standing approval is used, comment on the ticket: "under CEO standing approval 2026-10-22 (<category>)". Still ask him per action, in chat as in [[ceo-approves-in-chat]], for anything destructive, main/production, paid, secrets, or store work. Related: [[briefs-no-drop-no-prod-test-writes]] (its live-test-write rule is relaxed only for QA test-account data).
