import React from 'react'
import {Box, Text} from 'ink'
import type {CommandDef} from '../../ui/commands.js'
import {colors} from '../../ui/theme.js'
import {ShortcutHint} from '../design/ShortcutHint.js'
import {HistorySearchLine} from './HistorySearchLine.js'
import {PromptSuggestions} from './PromptSuggestions.js'

export function PromptFooter({
  suggestions,
  selected,
  historySearch,
  disabled,
  disabledReason
}: {
  suggestions: CommandDef[]
  selected: number
  historySearch?: {
    active: boolean
    query: string
    match?: string
    failed?: boolean
  }
  disabled?: boolean
  disabledReason?: string
}) {
  if (historySearch?.active) {
    return <HistorySearchLine query={historySearch.query} match={historySearch.match} failed={historySearch.failed} />
  }
  if (suggestions.length) {
    return <PromptSuggestions commands={suggestions} selected={selected} />
  }
  return (
    <Box marginTop={1} paddingLeft={2}>
      {disabled ? (
        <Text dimColor>{disabledReason || 'waiting for current turn'}</Text>
      ) : (
        <ShortcutHint items={[['/', 'cmd'], ['@', 'file'], ['esc', 'clear'], ['^r', 'history'], ['^o', 'fold'], ['^t', 'tool']]} />
      )}
      <Text color={colors.dim}> </Text>
    </Box>
  )
}
