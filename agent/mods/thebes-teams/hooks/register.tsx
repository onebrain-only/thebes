import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Snapshot, Team } from '../types'

const PANE = 'thebes-teams'
const snapshot = atom({ plugin: 'thebes-teams', key: 'snapshot' } as const, {
  teams: [],
  at: '',
} as Snapshot)

const SCRIPT = `
import json, os, re, glob, time
from agent.state import store
from agent.execution import team_pool
PROJ = os.path.expanduser("~/.claude/projects/-Users-moataz-Desktop-Thebes-Canonical")
def last(path, size=300000):
    model = effort = ""
    try:
        with open(path, "rb") as f:
            f.seek(max(0, os.path.getsize(path) - size))
            tail = f.read().decode("utf-8", "ignore")
        m = re.findall(r'"model":"(claude-[^"]+)"', tail)
        e = re.findall(r'"effort":"([^"]+)"', tail)
        model, effort = (m[-1] if m else ""), (e[-1] if e else "")
    except OSError:
        pass
    return model.replace("claude-", ""), effort
recs = {r["dispatch_id"]: r for r in store.read_all("conversation_dispatch")}
now = time.time()
out = []
for t in team_pool.team_bindings():
    if t["team_id"] == "edfu":
        continue
    work = []
    for d in t["open_dispatches"]:
        r = recs.get(d, {})
        work.append(r.get("jira_key") or r.get("ticket") or "ops")
    sid = t["session_id"]
    model = effort = ""
    subs = []
    if sid:
        model, effort = last(os.path.join(PROJ, sid + ".jsonl"))
        for p in glob.glob(os.path.join(PROJ, sid, "subagents", "*.jsonl")):
            if now - os.path.getmtime(p) > 120:
                continue
            kind = "agent"
            try:
                kind = json.load(open(p[:-6] + ".meta.json")).get("agentType") or kind
            except Exception:
                pass
            m, e = last(p, 100000)
            subs.append({"type": kind, "model": m, "effort": e})
    out.append({"name": t["display_name"], "busy": t["busy"], "work": work, "bound": bool(sid),
                "model": model, "effort": effort, "subs": subs})
print(json.dumps(out))
`

const me = (t: Team) => [t.model, t.effort].filter(Boolean).join(' · ') || '?'
const subsLine = (t: Team) => {
  const subs = t.subs ?? []
  if (subs.length === 0) return 'subagents: 0'
  return `subagents: ${subs.length} — ` + subs.map(s => `${s.type} (${[s.model, s.effort].filter(Boolean).join(' · ') || '?'})`).join(', ')
}

const summary = (s: Snapshot) => {
  const working = s.teams.filter(t => t.busy)
  const idle = s.teams.filter(t => !t.busy)
  const line = (t: Team) => `  ${t.name} [${me(t)}]${t.work.length ? ' ' + t.work.join(', ') : ''}\n    ${subsLine(t)}`
  return [
    `Working (${working.length}):`,
    ...working.map(line),
    `Idle (${idle.length}):`,
    ...idle.map(line),
    `updated ${s.at || '-'}${s.error ? ' · error: ' + s.error : ''}`,
  ].join('\n')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'thebes-teams', description: 'Show working and idle Thebes teams' })
    const refresh = async () => {
      const at = new Date().toLocaleTimeString()
      try {
        const { exitCode, stdout, stderr } = await $.process.run(
          ['python3', '-c', SCRIPT],
        )
        if (exitCode !== 0) {
          await update($, snapshot, s => ({ ...s, at, error: String(stderr).slice(-200) }))
          return
        }
        await update($, snapshot, () => ({ teams: JSON.parse(String(stdout)), at }))
      } catch (err) {
        await update($, snapshot, s => ({ ...s, at, error: String(err) }))
      }
    }
    void refresh()
    $.clock.every(20000, () => void refresh())
    void $.ui.open({ id: PANE, title: 'Thebes teams' })
    return next(e)
  })

  on('command.run', { command: 'thebes-teams' }, async $ => {
    void $.ui.open({ id: PANE, title: 'Thebes teams' })
    return { text: summary(await read($, snapshot)) }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const s = await read($, snapshot)
    if (e.props.hasSurvey || s.teams.length === 0) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const working = s.teams.filter(t => t.busy)
    const idle = s.teams.filter(t => !t.busy)
    return (
      <Box>
        <Text color="green">Working: {working.map(t => `${t.name} (${t.work.join(', ')}; ${me(t)}; ${(t.subs ?? []).length} sub)`).join(' · ') || 'none'}</Text>
        <Text>   </Text>
        <Text color="yellow">Idle: {idle.map(t => t.name).join(' · ') || 'none'}</Text>
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const s = await read($, snapshot)
    const working = s.teams.filter(t => t.busy)
    const idle = s.teams.filter(t => !t.busy)
    return (
      <Box flexDirection="column">
        <Text bold color="green">Working ({working.length})</Text>
        {working.length === 0 && <Text dimColor>  none</Text>}
        {working.map(t => (
          <Box flexDirection="column">
            <Text>  ● {t.name}  <Text color="cyan">{me(t)}</Text>  <Text dimColor>{t.work.join(', ')}</Text></Text>
            <Text dimColor>      {subsLine(t)}</Text>
          </Box>
        ))}
        <Text> </Text>
        <Text bold color="yellow">Idle ({idle.length})</Text>
        {idle.length === 0 && <Text dimColor>  none</Text>}
        {idle.map(t => (
          <Text>  ○ {t.name}{t.bound ? '' : ' (no session)'}  <Text color="cyan">{me(t)}</Text>  <Text dimColor>{subsLine(t)}</Text></Text>
        ))}
        <Text> </Text>
        <Text dimColor>updated {s.at || '…'}{s.error ? ` · error: ${s.error}` : ''}</Text>
      </Box>
    )
  })
}
