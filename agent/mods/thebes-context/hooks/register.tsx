import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Weight } from '../types'

// CEO 2026-10-20: team sessions grew to 350k-540k tokens and every wake after the prompt cache
// expired re-sent all of it (~36M tokens a day). This mod shrinks a session from the inside, at
// the end of a turn while its cache is still warm, and shows the weight where the CEO can act.

const GUARD_TOKENS = 150_000 // compact itself above this
const COOLDOWN_MS = 20 * 60 * 1000 // never twice within 20 minutes
const PANE = 'teams'
const KEEP =
  'Keep only what is needed to continue as this Thebes session: its role and lane rules, the tickets ' +
  'in progress or just finished (key, branch, worktree, last commit, what is left), decisions taken ' +
  'and by whom, and any open question. Drop tool output, file contents, test logs and exploration.'

const lastCompactAt = atom({ plugin: 'thebes-context', key: 'lastCompactAt' } as const, 0)
const isCompacting = atom({ plugin: 'thebes-context', key: 'isCompacting' } as const, false)
const isHidden = atom({ plugin: 'thebes-context', key: 'isHidden' } as const, false)
const weights = atom({ plugin: 'thebes-context', key: 'weights' } as const, null)
const note = atom({ plugin: 'thebes-context', key: 'note' } as const, null)

const k = (n: number | null | undefined) => (n == null ? '-' : `${Math.round(n / 1000)}k`)

// Compacts between turns. `$.session.compact` rejects while a turn runs, so it asks again a little
// later instead of failing.
async function compactNow($: any, why: string) {
  if (await read($, isCompacting)) return
  await update($, isCompacting, () => true)
  try {
    const before = (await $.session.usage()).context.tokens
    for (let tries = 0; tries < 4; tries += 1) {
      try {
        const done = await $.session.compact({ instructions: KEEP })
        if ('skip' in done && done.skip) {
          $.ui.toast(`Compaction skipped: ${done.skip}`)
        } else {
          const after = (await $.session.usage()).context.tokens
          await update($, lastCompactAt, () => Date.now())
          await update($, note, () => ({ text: `${why}: ${k(before)} -> ${k(after)}`, at: Date.now() }))
          $.ui.toast(`Context compacted: ${k(before)} -> ${k(after)}`)
        }
        return
      } catch {
        await $.clock.sleep(5000)
      }
    }
  } finally {
    await update($, isCompacting, () => false)
  }
}

async function refresh($: any) {
  const run = await $.process.run(['python3', '-m', 'agent.execution.session_weight', 'report'], {
    timeoutMs: 20_000,
  })
  if (run.exitCode === 0) await update($, weights, () => JSON.parse(run.stdout) as Weight[])
}

async function compactTeam($: any, team: string) {
  const run = await $.process.run(
    ['python3', '-m', 'agent.execution.session_weight', 'compact-team', team],
    { timeoutMs: 60_000 },
  )
  const out = run.exitCode === 0 ? JSON.parse(run.stdout) : { reason: run.stderr }
  $.ui.toast(`${team}: ${out.action ?? 'refused'} ${out.reason ?? ''}`)
  await refresh($)
}

export const register: Register = on => {
  // 1. The guard: the main conversation, at the end of a turn, when heavy.
  on('turn.complete', async ($, e, next) => {
    const ran = await next(e)
    if (e.agentId !== undefined) return ran
    const { context } = await $.session.usage()
    const quiet = Date.now() - (await read($, lastCompactAt)) < COOLDOWN_MS
    if ((context.tokens ?? 0) >= GUARD_TOKENS && !quiet) {
      $.clock.after(3000, () => compactNow($, 'auto'))
    }
    return ran
  })

  // 2. The band above the prompt: this session's weight and quota, with the button.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || (await read($, isHidden))) return next(e)
    const { context, rateLimits } = await $.session.usage()
    const { Box, Button, Text } = $.ui.resolve(e)
    const quota = rateLimits
      .map((r: { kind: string; percentUsed: number }) => `${r.kind.replace('_', ' ')} ${r.percentUsed}%`)
      .join(' · ')
    const last = await read($, note)
    const busy = await read($, isCompacting)
    return (
      <Box>
        <Text dimColor>
          Context {k(context.tokens)} of {k(context.window)} ({context.percent ?? 0}%)
          {quota ? ` · ${quota}` : ''}
          {last ? ` · last: ${last.text}` : ''}{' '}
        </Text>
        <Button
          key="compact"
          label={busy ? 'Compacting...' : 'Compact'}
          onPress={() => compactNow($, 'manual')}
        />
        <Button key="hide" label="Hide" onPress={() => update($, isHidden, () => true)} />
      </Box>
    )
  })

  // 3. /teams: every Thebes team session with its context and a Compact button each.
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'teams',
      description: 'Track the context size of every Thebes team session and compact one',
    })
    return next(e)
  })

  on('command.run', { command: 'teams' }, async $ => {
    await refresh($)
    await $.ui.open({ id: PANE, title: 'Thebes teams' })
    $.clock.every(30_000, () => refresh($))
    return { text: 'Teams pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const list = await read($, weights)
    if (list === null) return <Text dimColor>Reading the sessions...</Text>
    return (
      <Box flexDirection="column">
        {list.map(w => (
          <Box key={w.team}>
            <Text>
              {w.team.padEnd(15)} {k(w.tokens).padStart(5)} · idle {w.idle_min ?? '-'} min
              {w.last_compacted_min_ago != null ? ` · compacted ${w.last_compacted_min_ago} min ago` : ''}{' '}
            </Text>
            {w.team !== 'orchestrator' && (
              <Button
                key={`c-${w.team}`}
                label="Compact"
                onPress={() => compactTeam($, w.team)}
              />
            )}
          </Box>
        ))}
        <Text dimColor>The orchestrator compacts itself (band above its prompt).</Text>
      </Box>
    )
  })
}
