export type Weight = {
  team: string
  tokens: number | null
  idle_min: number | null
  last_compacted_min_ago: number | null
}

export type Note = { text: string; at: number }

declare module 'claude-code' {
  interface PluginState {
    'thebes-context': {
      lastCompactAt: number
      isCompacting: boolean
      isHidden: boolean
      weights: Weight[] | null
      note: Note | null
    }
  }
}
