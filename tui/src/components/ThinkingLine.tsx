import React, {useRef} from 'react'
import {Box, Text} from 'ink'
import {useTicker} from '../hooks/useTicker.js'
import {formatDuration} from '../ui/format.js'
import {colors} from '../ui/theme.js'

const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

export function ThinkingLine({
  label,
  active = true
}: {
  label: string
  active?: boolean
}) {
  const startedAt = useRef(Date.now())
  const tick = useTicker(active, 120)
  const elapsed = Date.now() - startedAt.current
  const frame = active ? frames[tick % frames.length] : '●'

  return (
    <Box marginTop={1}>
      <Text color={colors.cyan}>{frame} </Text>
      <Text color={colors.cyan} bold>thinking</Text>
      <Text dimColor> {label}</Text>
      <Text dimColor> · {formatDuration(elapsed)}</Text>
    </Box>
  )
}
