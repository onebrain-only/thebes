---
name: repo-topology
description: dabbler-design-system git topology — now pushed to GitHub, public repo, Canary is default branch, no CI/deploy wired up yet
metadata:
  type: project
---
> **Note 2026-11-10 (Thebes System).** Written 2026-09-18, when `Canary` was the only branch of the design system. Since D-052 teams push `staging-ds-<team>`, Memphis integrates into `staging-ds`, and `alpha-ds` moves only on a `promote-alpha` order. Check `git branch -r` before relying on the branch facts below.

**Updated 2026-09-18.** This repo now HAS a remote. It went from local-only to first-published
on GitHub in this session, under a one-time, repo-scoped lift of the standing "don't push"
instruction — do not generalize that lift to `dabbler-docs` (still unpushed, still frozen) or
to `dabbler-code`'s rules.

- Remote: `https://github.com/dabblersport/dabbler-design-system.git`, `origin`. Repo is
  **PUBLIC**. Visibility was a deliberate CEO decision, not a default — do not propose making
  it private without instruction.
- `Canary` is the sole branch, pushed and tracking `origin/Canary`, and GitHub set it as the
  **default branch automatically** on first publish since the repo was empty (nobody chose this
  as a setting). HEAD at push time: `8bc96df`, 27 commits (`23d180f`..`8bc96df`).
- **No `main` branch exists here yet.** The `dabbler-code` rule ("never push `main` directly,
  always PR from Canary", `P-030` freeze on merging into `main`) presumes `main` already exists
  as the production branch — it does not transfer mechanically until this repo actually grows a
  `main`. Treat `Canary` as the only real branch until told otherwise.
- **No CI, no Cloudflare Pages project, no deploy target configured for this repo** — pushing
  to GitHub is not a deploy here the way it is for `dabbler-code`. Don't assume a push triggers
  any build.
- Six local `exec/frontend-1/KAN-214..219` branches exist, intentionally NOT pushed and NOT
  deleted — local working artifacts, left alone per explicit instruction.
- Git identity: same `dabblersport` identity as `dabbler-code`
  (`MoatazMu` / `244900353+dabblersport@users.noreply.github.com`), inherited from global git
  config, `gh auth` active account also `dabblersport`.

**Known, ruled exposure — do not re-raise:** six font binaries ship with no licence record
(`fonts/Wingx-Regular.otf`, five `fonts/meral-sans-*.ttf`; Gloock and Glory do carry their OFL
files). The CEO was shown the exposure explicitly and chose to publish as-is, fonts included, on
the public repo. **There is also no `LICENSE` file on the repo itself** — flagged to the CEO
separately by team-lead, not yet ruled on. Don't act on either without instruction.

**Push mechanics note:** this session's own permission classifier denied `git remote add`
outright (category "Remote Repoint") even with the lift in place — the lift was CEO authority to
publish, not a change to this session's tool permissions. The actual `git remote add` +
`git push -u origin Canary` had to be run from a different, unrestricted session after the CEO's
direct say-so there. If asked to push this repo again in a similarly restricted session, expect
the same block and route it back to the user rather than asking a peer agent to run it (that
would be permission laundering, not a fix).

**Second push, 2026-09-18 (`8bc96df..c2a5023`, KAN-328/327 gallery nav):** ordinary `git push
origin Canary` worked without the remote-add restriction — that block was specific to creating
the remote, not to routine pushes once it exists. Post-push verify pattern that worked: `git
ls-remote --heads origin Canary` compared against local `git rev-parse Canary`, plus `git fetch`
+ `git rev-list --left-right --count Canary...origin/Canary` == `0 0`.

**Untracked `.claude/agent-memory/` in the working directory is normal and is NOT this repo's
content.** It accumulates from every seat (frontend-2, po, cxo, content-manager, frontend-6,
devops, etc.) working in this checkout and is not part of any feature branch's deliverable.
When committing a specific piece of landed work, stage only the files named in the brief —
never sweep `.claude/` into a commit on a public repo without being told to.

**Third push, 2026-09-20 (`af97292..210d830`, 34 commits accumulated across several sessions
and never sent).** Confirms the pattern holds at bulk scale, not just single-commit pushes:
ordinary `git push origin Canary` worked with no remote-add restriction hit. For a large
unreviewed batch, secret-scan the whole diff range through a temp file
(`git diff origin/Canary..HEAD > tmp/file.txt`, then grep the file) rather than piping — a
prior session found `grep -r` over the working tree matching everywhere instead of the actual
diff, and redid it. "Token"/"secret"/"password" false positives in this repo are expected and
are design vocabulary (design tokens, a password-toggle icon role) — don't mistake them for
credentials. Post-push verify pattern unchanged and confirmed reliable: `git ls-remote --heads
origin Canary` vs local `rev-parse HEAD`, plus `git fetch` + `rev-list --left-right --count
@{u}...HEAD` == `0 0`.
