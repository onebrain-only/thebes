# Setting up Thebes on a machine

Current as of 2026-11-10. This file owns one thing: what a new machine needs before Thebes
runs on it. How Thebes works is in the files `CLAUDE.md` lists.

## 1. What is in the repository and what is not

A clone of this repository carries every rule, role, seat definition, skill, script and seat
memory. Four things are deliberately outside it:

| Outside the repository | Why | How it arrives |
|---|---|---|
| `Dabbler/dabbler-docs/` | Its own repository (governance and Product knowledge) | `bootstrap.sh` clones it at the commit pinned in `CLAUDE.md` |
| `Dabbler/dabbler-code/`, `Dabbler/dabbler-design-system/` | The Product repositories | `bootstrap.sh` clones them on `staging` |
| `agent/state/runtime/`, `agent/listener/runtime/`, `agent/qa/runtime/`, `agent/.flow/` | Live records of this checkout: dispatches, bindings, logs | `bootstrap.sh` creates them empty. They are not copied between machines: a second checkout has its own runtime and coordinates with nothing |
| `.claude/settings.local.json` and every secret | Machine-local | `apply_settings.py` creates the file from the example; secrets are added by hand (section 3) |

## 2. One command

```bash
git clone <this repository> Thebes-Canonical && cd Thebes-Canonical
bash agent/scripts/bootstrap.sh
```

`bootstrap.sh` checks the tools, clones the three other repositories, creates the runtime
folders, runs `agent/scripts/apply_settings.py` and checks that the generated files
(`.claude/agents/`, `agent/skills/AVAILABLE.md`) match their sources. It is safe to run
again. It never touches an existing checkout and never writes a secret.

Tools it expects: `git` and `python3` (required: the Thebes code is standard-library Python),
then `claude`, `codex`, `flutter` and `gh` for running sessions and Product checks.

## 3. What you add by hand

1. **Jira.** `agent/integrations/jira.py` reads `JIRA_API_TOKEN`, `JIRA_ACCOUNT_EMAIL` and
   `JIRA_CLOUD_ID` from the environment, then from the macOS keychain (services
   `THEBES_JIRA_API_TOKEN`, `THEBES_JIRA_ACCOUNT_EMAIL`, `THEBES_JIRA_CLOUD_ID`). The email
   and cloud id are also in `agent/state/registry/jira.json`; only the token is a secret.
2. **The decision gate key.** `agent/state/registry/decision_gate.json` names a key file
   outside the repository (`~/.thebes/openrouter.key`, mode 0600) and the variable
   `OPENROUTER_API_KEY` as the fallback.
3. **Sign in** to `claude`, `codex` and `gh`, and connect the claude.ai connectors the seats
   use (Atlassian, Supabase).
4. **The dart-flutter plugin.** `.claude/settings.json` enables it and declares its
   marketplace; install it once with `/plugin install dart-flutter@dart-flutter`.
5. **The watchdog under launchd:** `bash agent/scripts/install-watchdog-agent.sh`. It writes
   the job with this checkout's own path.
6. **Start the sessions:** `bash agent/scripts/thebes-up.sh`, from your own terminal.

A dispatch token (`THEBES_DISPATCH_CAPABILITY`) is created per dispatch and passed in the
environment of the command that uses it. It is never stored in a settings file or a memory
file. `python3 agent/scripts/secret_scan.py` checks the tracked memory for one.

## 4. Settings

- `.claude/settings.json` is tracked and shared by every session.
- `.claude/settings.local.json` is this machine's own and is never tracked.
  `.claude/settings.local.example.json` is the tracked starting point. It carries the
  `autoMode` block, which Claude Code reads from local settings only.
- A session does not edit its own settings: the policy hook refuses it. A person changes them
  by running `python3 agent/scripts/apply_settings.py`, which holds the wanted rules and
  nothing else does. `--check` reports without changing anything.

## 5. Paths

No tracked rule file, role file or script names a home folder. A path in them is relative to
the workspace root, the folder that holds `CLAUDE.md` (`$CLAUDE_PROJECT_DIR` in a session).
The canonical workspace on the CEO's machine is `~/Desktop/Thebes-Canonical`; on another
machine it is wherever the clone is, and exactly one checkout is the live one.

## 6. Check a setup

```bash
bash agent/scripts/bootstrap.sh                       # ends with "bootstrap finished"
python3 agent/scripts/render_claude_agents.py --check # every line starts with ok
python3 agent/scripts/apply_settings.py --check       # every line starts with ok
python3 agent/scripts/knowledge_lint.py               # ends with "0 finding(s)"
sh agent/scripts/run-tests.sh                         # the test suites
```

## 7. What runs on every commit

`bootstrap.sh` points git at the tracked hook folder
(`git config core.hooksPath agent/scripts/git-hooks`). The `pre-commit` hook there runs four
checks and refuses the commit when one fails:

| Check | What it guards |
|---|---|
| `python3 agent/scripts/knowledge_lint.py` | One seat definition, counts, retired terms, home paths, links, decision IDs |
| `python3 agent/scripts/secret_scan.py` | No token in the tracked memory folders |
| `python3 agent/scripts/render_claude_agents.py --check` | `.claude/agents/` matches its sources |
| `python3 agent/scripts/render_skills_index.py --check` | `agent/skills/AVAILABLE.md` matches the skills |

A retired term is added to `STALE_TERMS` in `knowledge_lint.py` when a rule is replaced. A
line may still say that a retired thing is gone ("there are no team leads").
