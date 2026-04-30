import React from 'react'
import {Box, Text} from 'ink'
import {colors, glyphs} from '../../ui/theme.js'

export function PromptLine({
  disabled,
  value,
  before,
  current,
  after,
  placeholder,
  argumentHint
}: {
  disabled?: boolean
  value: string
  before: string
  current: string
  after: string
  placeholder: string
  argumentHint?: string
}) {
  return (
    <Box paddingX={1}>
      <Text color={disabled ? colors.dim : colors.cyan}>{glyphs.prompt} </Text>
      {value ? (
        <Text>
          {before}
          <Text inverse={!disabled}>{current}</Text>
          {after}
        </Text>
      ) : (
        <Text dimColor>{placeholder}</Text>
      )}
      {argumentHint ? <Text dimColor> {argumentHint}</Text> : null}
    </Box>
  )
}
