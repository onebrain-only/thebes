export type Sub = { type: string; model: string; effort: string }
export type Team = {
  name: string
  busy: boolean
  work: string[]
  bound: boolean
  model?: string
  effort?: string
  subs?: Sub[]
}
export type Snapshot = { teams: Team[]; at: string; error?: string }

declare module 'claude-code' {
  interface PluginState {
    'thebes-teams': { snapshot: Snapshot }
  }
}
