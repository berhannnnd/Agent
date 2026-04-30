import React from 'react'
import {Text} from 'ink'
import {colors, glyphs} from '../../ui/theme.js'

export type StatusTone = 'idle' | 'running' | 'success' | 'warning' | 'error' | 'muted'

export function StatusIcon({tone, active = true}: {tone: StatusTone; active?: boolean}) {
  const color = toneColor(tone)
  const mark = active ? toneMark(tone) : ' '
  return <Text color={color}>{mark}</Text>
}

function toneColor(tone: StatusTone): string {
  if (tone === 'running') return colors.cyan
  if (tone === 'success') return colors.success
  if (tone === 'warning') return colors.warning
  if (tone === 'error') return colors.error
  return colors.dim
}

function toneMark(tone: StatusTone): string {
  if (tone === 'warning') return '!'
  if (tone === 'error') return 'x'
  return glyphs.active
}
