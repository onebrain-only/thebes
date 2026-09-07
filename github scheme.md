| company/project  | local folder  | Repo  | account  | git  | Column 6  |
|:----------|:----------|:----------|:----------|:----------|:----------|
| One Brain    | '~/Desktop/Thebes'    | `https://github.com/onebrain-only/structure`    | @onebrain-only    | !gitignore    | agents files - docs    |
| Dabbler App    | '~/Desktop/Thebes/Dabbler/dabbler-code'    | `https://github.com/dabblersport/webapp`    | @dabblersport    | git    | code files only    |
| Dabbler DS    |   '~/Desktop/Thebes/Dabbler/dabbler-design-system'  | `https://github.com/dabblersport/dabbler-design-system`    | @dabblersport    | git    | All files    |
| Dabbler Dashboard    | '~/Desktop/Thebes/Dabbler/dabbler-admin'    | `https://github.com/dabblersport/onebrain-dashboard`    | @dabblersport    | git    | All files    |
| Dabbler Website    | '~/Desktop/Thebes/Dabbler/dabbler-web'    | `https://github.com/dabblersport/website`    | @dabblersport    | git    | All files    |

---

## Rules

**One GitHub account per product. `onebrain-only` is the holding account.**
Dabbler is `@dabblersport`. Nestler and Ram-Rambler will each get their own account when they
exist. **No account is ever made a collaborator on another's repo** — the products are separate
businesses and the isolation is deliberate, not incidental.

**`cto` owns the One Brain repo, and is the only seat that may commit or push to it.**

**The `devops` of each project owns that project's repo.** Only the app is staffed today; the
other projects are declared and unstaffed, so their `devops` seats do not exist yet.

**Everything is currently being tested on the app only.** Nothing below the app row should be
treated as live until its seats exist.

## How each repo authenticates

| Repo | Method |
|---|---|
| `onebrain-only/structure` | Fine-grained PAT scoped to this repo alone, embedded in the remote URL. **Verified working 2026-09-05.** |
| The four `dabblersport/*` repos | `gh` CLI, active account `dabblersport` |

**A known limit of the `gh` route:** `gh` holds one active account at a time. When a second
product's account exists, pushing to it requires switching accounts first — which is the kind
of step that gets forgotten. **The per-repo token in the remote URL has no such limit** and is
the pattern to extend when the next product arrives.

**A paste hazard, hit twice on 2026-09-05.** A leading space in the remote URL makes git fail
with `protocol ' https' is not supported`, which reads like a protocol problem and is not.
To clear it:

```bash
git -C "<repo>" remote set-url origin "$(git -C "<repo>" remote get-url origin | tr -d '[:space:]')"
```

## Known gaps

| Gap | Detail |
|---|---|
| `dabbler-admin` has **no remote** | `dabblersport/onebrain-dashboard` exists and is writable; the local folder is simply not connected. **29 uncommitted files sit there with no backup.** |
| All four `dabblersport/*` repos are **public** | `private=false` on all four. Unconfirmed whether that is intended. |
| `dabbler-docs` is **not version-controlled** | Deliberate (CEO, 2026-09-05). Backed up via the env repo or Notion instead. History up to `67cf424` remains in this repo's past commits. |

