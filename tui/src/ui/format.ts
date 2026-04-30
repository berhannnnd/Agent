import {toolSummaryFromPresentation} from './toolPresentation.js'

export function joinMeta(values: Array<string | number | undefined>): string {
  return values.filter(value => value !== undefined && String(value).length > 0).join(' · ')
}

export function runtimeLabel(protocol?: string, model?: string): string {
  if (!protocol && !model) return 'starting'
  return `${protocol ?? ''} · ${model ?? ''}`.trim()
}

export function toolSummary(name: string, args: Record<string, unknown> = {}): string {
  return toolSummaryFromPresentation(name, args)
}

export function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${durationMs}ms`
  if (durationMs < 60_000) return `${(durationMs / 1000).toFixed(1)}s`
  const minutes = Math.floor(durationMs / 60_000)
  const seconds = Math.floor((durationMs % 60_000) / 1000)
  return `${minutes}m ${seconds}s`
}

export function compact(value: unknown, limit = 120): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`
}
