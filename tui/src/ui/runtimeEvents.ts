import type {PendingApproval, RuntimeEvent} from '../protocol/types.js'
export {formatDuration} from './format.js'

export function toolKey(event: RuntimeEvent, payload: Record<string, unknown>): string {
  return String(payload.id ?? payload.tool_call_id ?? payload.approval_id ?? event.name ?? 'tool')
}

export function argsFromPayload(payload: Record<string, unknown>): Record<string, unknown> {
  return isObject(payload.arguments) ? payload.arguments : {}
}

export function pendingApprovalFromEvent(event: RuntimeEvent, runId: string): PendingApproval {
  const payload = event.payload ?? {}
  const call = isObject(payload.tool_call) ? payload.tool_call : {}
  const impact = isObject(payload.impact) ? payload.impact : {}
  const permission = isObject(payload.permission) ? payload.permission : {}
  return {
    runId,
    approvalId: String(payload.approval_id ?? call.id ?? event.name ?? 'approval'),
    toolName: String(call.name ?? event.name ?? 'tool'),
    args: isObject(call.arguments) ? call.arguments : {},
    risk: stringField(impact.risk),
    reason: stringField(permission.reason)
  }
}

export function approvalDecisionText(event: RuntimeEvent): {approved: boolean; text: string} {
  const payload = event.payload ?? {}
  const call = isObject(payload.tool_call) ? payload.tool_call : {}
  const approved = Boolean(payload.approved)
  return {
    approved,
    text: `${String(call.name ?? event.name ?? 'tool')} · ${String(payload.scope ?? '')}`.trim()
  }
}

export function summarizeToolResult(name: string, content: unknown, isError: boolean): string {
  if (isError) return typeof content === 'string' ? content : 'tool failed'
  const parsed = parseToolContent(content)
  if (name === 'filesystem.list') {
    const entries = Array.isArray(parsed?.entries) ? parsed.entries.length : undefined
    return entries === undefined ? 'Listed directory' : `Listed ${entries} ${entries === 1 ? 'entry' : 'entries'}`
  }
  if (name === 'filesystem.read') return pathResult(parsed, 'Read file')
  if (name === 'filesystem.write') return pathResult(parsed, 'Wrote file')
  if (name === 'search.grep') return 'Searched files'
  if (name === 'patch.apply') return 'Applied patch'
  if (name === 'shell.run' || name === 'test.run') return 'Command finished'
  return 'Finished'
}

export function stringifyToolContent(content: unknown): string {
  if (typeof content === 'string') return content
  try {
    return JSON.stringify(content, null, 2)
  } catch {
    return String(content)
  }
}

export function retryText(payload: Record<string, unknown>): string {
  const failed = typeof payload.failed_attempt === 'number' ? payload.failed_attempt : undefined
  const next = typeof payload.next_attempt === 'number' ? payload.next_attempt : undefined
  const max = typeof payload.max_attempts === 'number' ? payload.max_attempts : undefined
  const delay = typeof payload.delay_seconds === 'number' ? payload.delay_seconds : undefined
  const error = typeof payload.error === 'string' ? payload.error : 'model request failed'
  const attempt = next && max ? `attempt ${next}/${max}` : failed ? `after attempt ${failed}` : ''
  const wait = delay !== undefined ? `in ${delay.toFixed(1)}s` : ''
  return [attempt, wait, error].filter(Boolean).join(' · ')
}

export function toolIds(items: Array<{kind: string; id?: string}>): string[] {
  return items.flatMap(item => item.kind === 'tool' && item.id ? [item.id] : [])
}

function parseToolContent(content: unknown): Record<string, unknown> | null {
  if (isObject(content)) return content
  if (typeof content !== 'string') return null
  try {
    const parsed = JSON.parse(content)
    return isObject(parsed) ? parsed : null
  } catch {
    return null
  }
}

function pathResult(payload: Record<string, unknown> | null, fallback: string): string {
  const path = typeof payload?.path === 'string' ? payload.path : ''
  return path ? `${fallback}: ${path}` : fallback
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function stringField(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined
}
