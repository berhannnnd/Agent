import React, {useMemo} from 'react'
import {Box, Text} from 'ink'
import {colors} from '../ui/theme.js'
import {parseMarkdown, type MarkdownInline, type MarkdownLine} from '../ui/markdown.js'

export function MarkdownBlock({
  text,
  collapsed,
  maxLines = 14
}: {
  text: string
  collapsed: boolean
  maxLines?: number
}) {
  const lines = useMemo(() => parseMarkdown(text), [text])
  const hidden = Math.max(0, lines.length - maxLines)
  const shown = collapsed && hidden > 0 ? lines.slice(0, maxLines) : lines

  return (
    <Box flexDirection="column">
      {shown.map((line, index) => (
        <MarkdownRow key={index} line={line} />
      ))}
      {collapsed && hidden > 0 ? (
        <Text color={colors.dim}>  … {hidden} blocks hidden · ctrl+o or /unfold</Text>
      ) : null}
    </Box>
  )
}

function MarkdownRow({line}: {line: MarkdownLine}) {
  if (line.kind === 'blank') return <Text> </Text>
  if (line.kind === 'rule') return <Text color={colors.dim}>────────────────────────────────────────────────</Text>
  if (line.kind === 'code') {
    return (
      <Text color={colors.dim}>
        │ <Text>{line.text || ' '}</Text>
      </Text>
    )
  }
  if (line.kind === 'table') return <MarkdownTable rows={line.rows} />
  if (line.kind === 'heading') {
    return (
      <Box marginTop={line.level <= 2 ? 1 : 0}>
        <Text color={colors.cyan} bold>{renderInline(line.parts)}</Text>
      </Box>
    )
  }
  if (line.kind === 'quote') {
    return (
      <Text color={colors.dim}>
        │ <Text>{renderInline(line.parts)}</Text>
      </Text>
    )
  }
  if (line.kind === 'bullet') {
    const indent = '  '.repeat(line.depth)
    const marker = /^\d/.test(line.marker) ? line.marker : '•'
    return (
      <Text>
        <Text color={colors.dim}>{indent}{marker} </Text>
        {renderInline(line.parts)}
      </Text>
    )
  }
  return <Text>{renderInline(line.parts)}</Text>
}

function MarkdownTable({rows}: {rows: string[][]}) {
  const widths = columnWidths(rows)
  return (
    <Box flexDirection="column" marginY={1}>
      {rows.map((row, rowIndex) => (
        <Box key={rowIndex}>
          {widths.map((width, cellIndex) => (
            <Text key={cellIndex} color={rowIndex === 0 ? colors.cyan : undefined} bold={rowIndex === 0}>
              {(row[cellIndex] ?? '').padEnd(width)}
              {cellIndex < widths.length - 1 ? <Text dimColor>  </Text> : null}
            </Text>
          ))}
        </Box>
      ))}
    </Box>
  )
}

function renderInline(parts: MarkdownInline[]) {
  return parts.map((part, index) => {
    if (part.kind === 'code') {
      return <Text key={index} color={colors.cyan}>{part.text}</Text>
    }
    if (part.kind === 'strong') {
      return <Text key={index} bold>{part.text}</Text>
    }
    return <Text key={index}>{part.text}</Text>
  })
}

function columnWidths(rows: string[][]): number[] {
  const count = Math.max(0, ...rows.map(row => row.length))
  return Array.from({length: count}, (_, index) => Math.max(3, ...rows.map(row => (row[index] ?? '').length)))
}
