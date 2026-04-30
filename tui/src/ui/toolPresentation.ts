import {diffStats} from './diff.js'

export type ToolPresentation = {
  action: string
  target?: string
  meta?: string
  previewLabel?: string
  preview?: string
}

export function toolPresentation(name: string, args: Record<string, unknown> = {}): ToolPresentation {
  const path = stringArg(args.path) || stringArg(args.file) || stringArg(args.target)
  const query = stringArg(args.query) || stringArg(args.pattern) || stringArg(args.q)
  const command = stringArg(args.command) || stringArg(args.cmd)
  const url = stringArg(args.url)
  const patch = stringArg(args.patch) || stringArg(args.diff)
  const content = stringArg(args.content) || stringArg(args.text)

  if (name === 'filesystem.list') return {action: 'List directory', target: path || '.'}
  if (name === 'filesystem.read') return {action: 'Read file', target: path || compactValue(args)}
  if (name === 'filesystem.write') return {action: 'Write file', target: path || compactValue(args), meta: content ? `${content.length} chars · ${lineCount(content)} lines` : undefined, previewLabel: 'content', preview: content}
  if (name === 'patch.apply') return patchApplyPresentation(args, patch)
  if (name === 'search.grep') return {action: 'Search files', target: query || compactValue(args)}
  if (name === 'shell.run') return {action: 'Run shell command', target: command || compactValue(args), previewLabel: 'command', preview: command}
  if (name === 'test.run') return {action: 'Run test command', target: command || compactValue(args), previewLabel: 'command', preview: command}
  if (name === 'web.search' || name === 'web.map') return {action: 'Search web', target: query || compactValue(args)}
  if (name === 'web.extract') return {action: 'Extract web page', target: url || compactValue(args)}
  if (name === 'browser.open') return {action: 'Open browser', target: url || compactValue(args)}
  if (name === 'browser.download') return {action: 'Download file', target: url || compactValue(args)}
  return Object.keys(args).length ? {action: name, target: compactValue(args)} : {action: name}
}

export function toolSummaryFromPresentation(name: string, args: Record<string, unknown> = {}): string {
  const presentation = toolPresentation(name, args)
  return presentation.target ? `${presentation.action}: ${presentation.target}` : presentation.action
}

function stringArg(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function compactValue(value: unknown, limit = 120): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`
}

function lineCount(value: string): number {
  return value ? value.split('\n').length : 0
}

function patchApplyPresentation(args: Record<string, unknown>, patch: string): ToolPresentation {
  if (patch) {
    const stats = diffStats(patch)
    return {action: 'Apply patch', meta: `${stats.files || 1} file · +${stats.added} -${stats.removed}`, previewLabel: 'patch', preview: patch}
  }
  const operations = patchOperations(args)
  return {
    action: 'Apply patch',
    target: operations.target,
    meta: operations.meta,
    previewLabel: operations.preview ? 'operations' : undefined,
    preview: operations.preview
  }
}

function patchOperations(args: Record<string, unknown>): {target?: string; meta?: string; preview?: string} {
  const edits = Array.isArray(args.edits) ? args.edits.filter(isRecord) : []
  const creates = Array.isArray(args.creates) ? args.creates.filter(isRecord) : []
  const paths = [...edits, ...creates].map(item => stringArg(item.path)).filter(Boolean)
  const lines = [
    ...edits.map(item => `edit   ${stringArg(item.path) || '<unknown>'}${item.replace_all ? ' · replace all' : ''}`),
    ...creates.map(item => `create ${stringArg(item.path) || '<unknown>'}${item.overwrite ? ' · overwrite' : ''}`)
  ]
  return {
    target: paths.slice(0, 3).join(', ') || undefined,
    meta: `${edits.length} edit${edits.length === 1 ? '' : 's'} · ${creates.length} create${creates.length === 1 ? '' : 's'}`,
    preview: lines.join('\n')
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}
