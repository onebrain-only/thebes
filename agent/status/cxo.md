# agent/status/cxo.md

**Owner:** `cxo` (write) · all agents (read)

Append newest-first, in the FORMAT block of `agent/STATUS.md`. **`agent/WORKFLOWS.md` §1 rule 5:**
no task is complete until its entry is saved — a refusal, a diagnosis or a question answered
still gets one.

---

# LOG

_No entries yet._

## 2026-09-06 — Skills audit of the cxo seat (survey, no changes)

**Task:** team-lead skills survey — four questions against `agent/skills/` (74 repo skills),
`agent/skills/AVAILABLE.md` (~450 installed plugin skills), and `agent/roles/cxo.md`.
Read-only; nothing created, edited or deleted except this entry. **First task this seat has run.**

- **Verified:** `ls agent/skills/` = 74 entries incl. `AVAILABLE.md`; opened the SKILL.md body
  (frontmatter + framework sections) of all 11 candidates named in the brief, plus
  `ui-ux-pro-max`, plus 5 of the 22 `claude-design-skillstack` skills.
- **Claimed, having opened them:** `refactoring-ui`, `ux-heuristics`, `microinteractions`,
  `design-everyday-things`, `ios-hig-design`, `web-typography`. All six are platform-agnostic
  design frameworks with severity/scoring rubrics, not code catalogues.
- **Rejected after opening:** `top-design` (Awwwards agency craft — wrong product), and all 22
  of `claude-design-skillstack` (web animation libraries; Dabbler is Flutter/CanvasKit).
  `steve-jobs-design-review` rejected on the boundary rule — its verdicts are scope calls (`cpo`).
  `hooked-ux`, `lean-ux`, `design-sprint` belong to `cpo`/`po`, not this seat.
- **Role-file correction found:** the file says "Dabbler has **two** design systems." There are
  **four** trees on disk — `lib/core/design_system/`, `lib/design_system/tokens/`, `lib/themes/`,
  `lib/core/theme/`. The `G-011` standing question is bigger than my own file states.
- **Gap named, with evidence:** `Dabbler/dabbler-code/scripts/generate_token_json.py` (72 lines)
  generates `lib/design_system/tokens/*.json` from the Dart token files — one direction only,
  and `grep` over `.github/` and `scripts/ci/` finds **no CI invocation**. It also does not touch
  `lib/themes/app_theme.dart`, the third synced place. The three-place token trap has a partial,
  unenforced generator and no drift check.
- **Not verified:** the running app (never opened it); whether the four trees are genuinely
  four systems or two plus two façades — that is the `G-011` ruling, not measured here;
  the remaining ~430 installed plugin skills beyond the 16 bodies I opened.
