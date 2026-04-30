import React from 'react'
import {Box, Text} from 'ink'
import {looksLikeDiff} from '../../ui/diff.js'
import {colors} from '../../ui/theme.js'
import {CollapsibleBlock} from '../CollapsibleBlock.js'
import {DiffPreview} from './DiffPreview.js'

export function ToolResultPreview({
  name,
  detail,
  collapsed
}: {
  name: string
  detail: string
  collapsed: boolean
}) {
  const payload = parseObject(detail)
  const diff = diffFromPayload(name, payload, detail)
  if (diff) return <DiffPreview diff={diff} collapsed={collapsed} />

  if (name === 'filesystem.list' && Array.isArray(payload?.entries)) {
    const entries = payload.entries.filter(isEntry)
    const shown = collapsed ? entries.slice(0, 12) : entries
    return (
      <Box flexDirection="column">
        {shown.map(entry => (
          <Text key={`${entry.type}:${entry.path || entry.name}`}>
            <Text color={entry.type === 'directory' ? colors.cyan : colors.dim}>{entry.type === 'directory' ? 'dir ' : 'file'}</Text>
            <Text> {entry.path || entry.name}</Text>
          </Text>
        ))}
        {collapsed && entries.length > shown.length ? <Text dimColor>  … {entries.length - shown.length} entries hidden · /unfold</Text> : null}
      </Box>
    )
  }
  if ((name === 'shell.run' || name === 'test.run') && payload) {
    return (
      <Box flexDirection="column">
        {typeof payload.exit_code === 'number' ? (
          <Text>
            <Text color={payload.exit_code === 0 ? colors.success : colors.error}>exit </Text>
            <Text>{payload.exit_code}</Text>
          </Text>
        ) : null}
        {typeof payload.stdout === 'string' && payload.stdout ? (
          <>
            <Text color={colors.dim}>stdout</Text>
            <CollapsibleBlock text={payload.stdout} collapsed={collapsed} maxLines={10} />
          </>
        ) : null}
        {typeof payload.stderr === 'string' && payload.stderr ? (
          <>
            <Text color={colors.dim}>stderr</Text>
            <CollapsibleBlock text={payload.stderr} collapsed={collapsed} maxLines={10} />
          </>
        ) : null}
      </Box>
    )
  }
  return <CollapsibleBlock text={detail} collapsed={collapsed} maxLines={10} />
}

type Entry = {name?: string; path?: string; type?: string}

function isEntry(value: unknown): value is Entry {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function parseObject(text: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null
  } catch {
    return null
  }
}

function diffFromPayload(name: string, payload: Record<string, unknown> | null, detail: string): string {
  if (typeof payload?.diff === 'string' && payload.diff) return payload.diff
  if (name === 'git.diff' && typeof payload?.stdout === 'string' && looksLikeDiff(payload.stdout)) return payload.stdout
  if (looksLikeDiff(detail)) return detail
  return ''
}
