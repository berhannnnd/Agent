import React from 'react'
import {Box, Text} from 'ink'
import {colors} from '../../ui/theme.js'
import {ProgressBar} from '../design/ProgressBar.js'
import {MessageResponse} from '../MessageResponse.js'

export function TableMessage({title, rows}: {title: string; rows: Array<[string, string]>}) {
  if (title === 'Context') return <ContextTable rows={rows} />

  return (
    <Box flexDirection="column" marginTop={1}>
      <Text bold>{title}</Text>
      <MessageResponse>
        {rows.map(([key, value]) => (
          <Text key={`${key}:${value}`}>
            <Text color={colors.cyan}>{key.padEnd(18)}</Text>
            <Text>{value}</Text>
          </Text>
        ))}
      </MessageResponse>
    </Box>
  )
}

function ContextTable({rows}: {rows: Array<[string, string]>}) {
  const values = Object.fromEntries(rows)
  const tokens = parseInt(values.tokens || '', 10)
  const limit = parseInt(values.limit || '', 10)
  const hasWindow = Number.isFinite(tokens) && Number.isFinite(limit) && limit > 0
  const state = hasWindow ? contextState(tokens, limit) : null
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text bold>Context</Text>
      <MessageResponse>
        {hasWindow ? (
          <Text>
            <Text color={colors.cyan}>{'window'.padEnd(18)}</Text>
            <ProgressBar value={tokens} max={limit} width={28} />
            <Text dimColor> {tokens}/{limit} tokens</Text>
          </Text>
        ) : null}
        {state ? (
          <Text>
            <Text color={colors.cyan}>{'state'.padEnd(18)}</Text>
            <Text color={state.color}>{state.label}</Text>
            <Text dimColor> {state.hint}</Text>
          </Text>
        ) : null}
        {rows.map(([key, value]) => key === 'tokens' || key === 'limit' ? null : (
          <Text key={`${key}:${value}`}>
            <Text color={colors.cyan}>{key.padEnd(18)}</Text>
            <Text>{value}</Text>
          </Text>
        ))}
      </MessageResponse>
    </Box>
  )
}

function contextState(tokens: number, limit: number): {label: string; hint: string; color: string} {
  const ratio = tokens / limit
  if (ratio >= 0.9) return {label: 'critical', hint: 'compaction should run before the next large turn', color: colors.error}
  if (ratio >= 0.75) return {label: 'high', hint: 'watch context growth', color: colors.warning}
  return {label: 'healthy', hint: 'enough room for normal tool use', color: colors.success}
}
