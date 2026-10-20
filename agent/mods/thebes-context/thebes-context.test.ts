import { expect, mock, test } from 'claude-code/testing'

const turn = (answer: string) => ({
  reason: 'answer',
  answer,
  durationMs: 1,
  isAborted: false,
  turnId: `t-${answer}`,
})

const usage = (tokens: number) => ({
  startedAt: 0,
  context: { tokens, window: 1_000_000, percent: Math.round(tokens / 10_000) },
  rateLimits: [],
})

test('a heavy session compacts itself after its turn, a light one does not', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  let tokens = 400_000
  const compacted: Array<string | undefined> = []
  on('turn.complete', (_$, e) => ({ text: (e as { answer: string }).answer }))
  on('session.usage', () => ({ value: usage(tokens) }))
  on('session.compact', (_$, e) => {
    compacted.push((e as { instructions?: string }).instructions)
    tokens = 60_000
    return { messages: [{ role: 'user', text: 'summary', toolUses: [] }] } as never
  })

  await $.turn.complete(turn('done') as never)
  await clock.advance(4000)
  await clock.advance(10_000)

  expect(compacted.length).toBe(1)
  expect(compacted[0]).toContain('Keep only what is needed')
  expect(tokens).toBe(60_000)

  // within the 20 minute cooldown nothing happens again, even if it is heavy
  tokens = 400_000
  await $.turn.complete(turn('again') as never)
  await clock.advance(10_000)
  expect(compacted.length).toBe(1)
})

test('a light session is left alone', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  const compacted: unknown[] = []
  on('turn.complete', (_$, e) => ({ text: (e as { answer: string }).answer }))
  on('session.usage', () => ({ value: usage(80_000) }))
  on('session.compact', () => {
    compacted.push(1)
    return { messages: [{ role: 'user', text: 'summary', toolUses: [] }] } as never
  })
  await $.turn.complete(turn('done') as never)
  await clock.advance(10_000)
  expect(compacted.length).toBe(0)
})
