import React from 'react'
import {Text} from 'ink'
import {colors} from '../../ui/theme.js'

export function ProgressBar({
  value,
  max,
  width = 24
}: {
  value: number
  max: number
  width?: number
}) {
  const ratio = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0
  const filled = Math.round(ratio * width)
  const empty = Math.max(0, width - filled)
  const tone = ratio > 0.9 ? colors.error : ratio > 0.75 ? colors.warning : colors.cyan
  return (
    <Text>
      <Text color={tone}>{'█'.repeat(filled)}</Text>
      <Text color={colors.dim}>{'░'.repeat(empty)}</Text>
      <Text dimColor> {Math.round(ratio * 100)}%</Text>
    </Text>
  )
}
