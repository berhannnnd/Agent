import React from 'react'
import {Box, Text} from 'ink'
import {colors} from '../../ui/theme.js'
import {StatusIcon, type StatusTone} from '../design/StatusIcon.js'

export function StatusMessage({
  label,
  text,
  level = 'info'
}: {
  label: string
  text?: string
  level?: 'info' | 'warning' | 'error' | 'success'
}) {
  return (
    <Box marginTop={1}>
      <StatusIcon tone={toneForLevel(level, label)} />
      <Text> </Text>
      <Text color={levelColor(level)}>{label}</Text>
      {text ? <Text dimColor> {text}</Text> : null}
    </Box>
  )
}

function toneForLevel(level: 'info' | 'warning' | 'error' | 'success', label: string): StatusTone {
  if (level === 'warning') return 'warning'
  if (level === 'error') return 'error'
  if (level === 'success') return 'success'
  if (label === 'thinking' || label === 'retry') return 'running'
  return 'muted'
}

function levelColor(level: 'info' | 'warning' | 'error' | 'success'): string {
  if (level === 'warning') return colors.warning
  if (level === 'error') return colors.error
  if (level === 'success') return colors.success
  return colors.dim
}
