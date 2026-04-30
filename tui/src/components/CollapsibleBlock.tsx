import React from 'react'
import {Box, Text} from 'ink'
import wrapAnsi from 'wrap-ansi'
import {colors} from '../ui/theme.js'

export function CollapsibleBlock({
  text,
  collapsed,
  maxLines = 12,
  width = 92
}: {
  text: string
  collapsed: boolean
  maxLines?: number
  width?: number
}) {
  const lines = wrapText(text, width)
  const hidden = Math.max(0, lines.length - maxLines)
  const shown = collapsed && hidden > 0 ? lines.slice(0, maxLines) : lines

  return (
    <Box flexDirection="column">
      {shown.map((line, index) => (
        <Text key={index}>{line || ' '}</Text>
      ))}
      {collapsed && hidden > 0 ? (
        <Text color={colors.dim}>  … {hidden} lines hidden · /unfold</Text>
      ) : null}
    </Box>
  )
}

function wrapText(text: string, width: number): string[] {
  if (!text) return []
  return text
    .split('\n')
    .flatMap(line => wrapAnsi(line, Math.max(20, width), {hard: true, trim: false}).split('\n'))
}
