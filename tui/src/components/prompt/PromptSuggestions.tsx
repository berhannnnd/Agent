import React from 'react'
import {Box, Text} from 'ink'
import figures from 'figures'
import type {CommandDef} from '../../ui/commands.js'
import {colors} from '../../ui/theme.js'

export function PromptSuggestions({
  commands,
  selected,
  maxVisible = 6
}: {
  commands: CommandDef[]
  selected: number
  maxVisible?: number
}) {
  if (!commands.length) return null
  const start = Math.max(0, Math.min(selected - Math.floor(maxVisible / 2), commands.length - maxVisible))
  const visible = commands.slice(start, start + maxVisible)

  return (
    <Box flexDirection="column" marginTop={1} paddingLeft={2}>
      {visible.map(command => {
        const index = commands.indexOf(command)
        const active = index === selected
        if (command.kind === 'file') {
          return (
            <Box key={command.name}>
              <Text color={active ? colors.cyan : colors.dim}>{active ? figures.pointer : ' '} + </Text>
              <Text color={active ? colors.cyan : undefined}>{command.name}</Text>
              <Text dimColor>  {command.description}</Text>
            </Box>
          )
        }
        return (
          <Box key={command.name}>
            <Text color={active ? colors.cyan : colors.dim}>
            {active ? figures.pointer : ' '} {command.name.padEnd(13)}
          </Text>
          {command.local ? <Text dimColor>[local] </Text> : null}
          {command.availability === 'idle' ? <Text dimColor>[idle] </Text> : null}
          <Text color={active ? colors.cyan : colors.dim}>{command.description}</Text>
            {command.argumentHint ? <Text color={colors.dim}>  {command.argumentHint}</Text> : null}
          </Box>
        )
      })}
    </Box>
  )
}
