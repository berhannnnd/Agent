import React from 'react'
import {Box, Text} from 'ink'
import wrapAnsi from 'wrap-ansi'
import {diffStats, parseUnifiedDiff, type DiffLineKind} from '../../ui/diff.js'
import {colors} from '../../ui/theme.js'

export function DiffPreview({
  diff,
  collapsed,
  maxLines = 18,
  width = 96
}: {
  diff: string
  collapsed: boolean
  maxLines?: number
  width?: number
}) {
  const stats = diffStats(diff)
  const lines = parseUnifiedDiff(diff).flatMap(line => wrapDiffLine(line.kind, line.text, width))
  const hidden = Math.max(0, lines.length - maxLines)
  const shown = collapsed && hidden > 0 ? lines.slice(0, maxLines) : lines

  return (
    <Box flexDirection="column">
      <Text>
        <Text color={colors.dim}>{stats.files || 1} file{(stats.files || 1) === 1 ? '' : 's'} </Text>
        <Text color={colors.success}>+{stats.added}</Text>
        <Text dimColor> </Text>
        <Text color={colors.error}>-{stats.removed}</Text>
      </Text>
      {shown.map((line, index) => (
        <Text key={index} color={toneForKind(line.kind)} dimColor={line.kind === 'context' || line.kind === 'meta'}>
          {line.text || ' '}
        </Text>
      ))}
      {collapsed && hidden > 0 ? (
        <Text color={colors.dim}>  ... {hidden} lines hidden · ctrl+o or ctrl+d</Text>
      ) : null}
    </Box>
  )
}

function wrapDiffLine(kind: DiffLineKind, text: string, width: number): Array<{kind: DiffLineKind; text: string}> {
  const wrapped = wrapAnsi(text, Math.max(24, width), {hard: true, trim: false}).split('\n')
  return wrapped.map((line, index) => ({kind, text: index === 0 ? line : `  ${line}`}))
}

function toneForKind(kind: DiffLineKind): string | undefined {
  if (kind === 'add') return colors.success
  if (kind === 'remove') return colors.error
  if (kind === 'hunk') return colors.cyan
  if (kind === 'file') return colors.cyan
  return undefined
}
