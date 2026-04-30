import React from 'react'
import {Box} from 'ink'
import {AssistantMessage} from './messages/AssistantMessage.js'
import {ThinkingMessage} from './messages/ThinkingMessage.js'
import {ThinkingLine} from './ThinkingLine.js'

export function LiveTurn({
  assistant,
  reasoning,
  label,
  collapsed
}: {
  assistant: string
  reasoning: string
  label: string
  collapsed: boolean
}) {
  if (assistant || reasoning) {
    return (
      <Box flexDirection="column">
        {reasoning ? <ThinkingMessage text={reasoning} collapsed={collapsed} live /> : null}
        {assistant ? <AssistantMessage text={assistant} collapsed={collapsed} live /> : null}
      </Box>
    )
  }
  return <ThinkingLine label={label} />
}
