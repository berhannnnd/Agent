import React from 'react'
import {Box, Text} from 'ink'
import {useBlink} from '../hooks/useBlink.js'
import {colors, glyphs} from '../ui/theme.js'

export function ToolUseLoader({
  unresolved,
  error,
  animate = true
}: {
  unresolved: boolean
  error?: boolean
  animate?: boolean
}) {
  const visible = useBlink(Boolean(animate && unresolved && !error))
  const color = unresolved ? colors.dim : error ? colors.error : colors.success
  const mark = !unresolved || error || visible ? glyphs.active : ' '

  return (
    <Box minWidth={2}>
      <Text color={color}>{mark}</Text>
    </Box>
  )
}
