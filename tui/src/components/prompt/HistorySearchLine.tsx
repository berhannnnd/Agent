import React from 'react'
import {Box, Text} from 'ink'
import {colors} from '../../ui/theme.js'

export function HistorySearchLine({
  query,
  match,
  failed
}: {
  query: string
  match?: string
  failed?: boolean
}) {
  return (
    <Box flexDirection="column" marginTop={1} paddingLeft={2}>
      <Box>
        <Text color={failed ? colors.warning : colors.dim}>{failed ? 'no matching prompt:' : 'search prompts:'}</Text>
        <Text> {query || ' '}</Text>
      </Box>
      {match ? (
        <Box paddingLeft={2}>
          <Text dimColor>{match}</Text>
        </Box>
      ) : null}
    </Box>
  )
}
