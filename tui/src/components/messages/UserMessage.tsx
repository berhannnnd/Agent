import React from 'react'
import {Box, Text} from 'ink'
import {colors, glyphs} from '../../ui/theme.js'

export function UserMessage({text}: {text: string}) {
  return (
    <Box marginTop={1}>
      <Text color={colors.cyan}>{glyphs.prompt} </Text>
      <Text>{text}</Text>
    </Box>
  )
}
