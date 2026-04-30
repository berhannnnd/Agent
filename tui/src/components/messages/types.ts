export type TranscriptItem =
  | {kind: 'user'; text: string}
  | {kind: 'assistant'; text: string}
  | {kind: 'thinking'; text: string}
  | {kind: 'status'; label: string; text?: string; level?: 'info' | 'warning' | 'error' | 'success'}
  | {kind: 'tool'; id?: string; name: string; args?: Record<string, unknown>; result?: string; detail?: string; error?: boolean; durationMs?: number}
  | {kind: 'table'; title: string; rows: Array<[string, string]>}
  | {kind: 'models'; profiles: Array<{name: string; protocol: string; model: string; endpoint?: string; active?: boolean; configured?: boolean}>}
